"""
v5 Scene Predictor with enhanced audio features.

This predictor combines:
- EfficientAT embeddings (1920-dim)
- MFCC mean (128-dim)
- MFCC std (128-dim)
- Spectral features (12-dim): centroid, rolloff, bandwidth, contrast×7, ZCR, RMS
= Total: 2188-dimensional feature vector

Pipeline: Extract features -> Scale -> PCA -> KMeans -> Map to scene
"""

import joblib
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
import torch
from efficientat import get_mn, get_dymn, AugmentMelSTFT, NAME_TO_WIDTH
import librosa
import json
import os
from pathlib import Path
import logging
import random

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set random seeds for reproducibility
def set_deterministic_seeds(seed=0):
    """Set all random seeds for deterministic behavior."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
    # Set PyTorch to deterministic mode
    torch.backends.cudnn.deterministic = True
    torch.backends.cudnn.benchmark = False


class ScenePredictor:
    def __init__(self, model_dir=None, sr=48000, seed=0):
        """
        Initialize the v5 scene predictor with trained models.
        
        Args:
            model_dir: Directory containing the trained models. If None, uses current directory.
            sr: Sample rate for audio processing
            seed: Random seed for deterministic behavior
        """
        # Set deterministic seeds
        set_deterministic_seeds(seed)
        
        if model_dir is None:
            model_dir = Path(__file__).parent
        
        self.model_dir = Path(model_dir)
        self.sr = sr
        
        # Audio feature extraction parameters (matching training)
        self.n_mfcc = 128
        self.n_fft = 2048
        self.hop_length = 512
        
        # Load preprocessing models
        try:
            self.scaler = joblib.load(self.model_dir / 'scaler.pkl')
            self.pca = joblib.load(self.model_dir / 'pca_95.pkl')
            self.kmeans = joblib.load(self.model_dir / 'kmeans_100.pkl')
            
            with open(self.model_dir / 'scene_mapping.json', 'r') as f:
                self.scene_map = json.load(f)
                
            logger.info("Successfully loaded v5 preprocessing models")
            logger.info(f"PCA components: {self.pca.n_components_}")
            logger.info(f"Number of clusters: {len(self.scene_map)}")
        except Exception as e:
            logger.error(f"Failed to load preprocessing models: {e}")
            raise

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Load EfficientAT model
        self._load_efficientat_model()

    def _load_efficientat_model(self):
        """Load and initialize the EfficientAT model."""
        try:
            model_name = "dymn20_as"
            width_mult = NAME_TO_WIDTH(model_name)

            # Create mel spectrogram without augmentation for deterministic behavior
            self.mel = AugmentMelSTFT(
                n_mels=128, 
                sr=48000, 
                win_length=800, 
                hopsize=320, 
                fmax=23000
            ).to(self.device)

            self.mel.eval()
            
            # Create model (auto-downloads weights into a local resources cache)
            if model_name.startswith("dymn"):
                self.model = get_dymn(pretrained_name=model_name, width_mult=width_mult, strides=(2,2,2,2))
            else:
                self.model = get_mn(pretrained_name=model_name, width_mult=width_mult, strides=(2,2,2,2), head_type="mlp")
            
            self.model = self.model.to(self.device).eval()
            
            # Ensure model is in eval mode and disable dropout
            self.model.train(False)
            for module in self.model.modules():
                if hasattr(module, 'dropout'):
                    module.dropout.p = 0.0
                if hasattr(module, 'drop_rate'):
                    module.drop_rate = 0.0
            
            logger.info(f"EfficientAT model loaded on {self.device}")
        except Exception as e:
            logger.error(f"Failed to load EfficientAT model: {e}")
            raise
    
    @torch.no_grad()
    def get_efficientat_embedding(self, audio):
        """
        Generate embeddings using EfficientAT model.
        
        Args:
            audio: Audio data as numpy array
            
        Returns:
            numpy array: Audio embeddings (1920-dim)
        """
        try:
            # Validate input
            if not isinstance(audio, np.ndarray):
                raise ValueError("Audio data must be a numpy array")
            
            if len(audio) == 0:
                raise ValueError("Audio data cannot be empty")
            
            wav_resampled = audio.copy()
            
            # Ensure the audio is long enough for STFT processing
            min_length = 1024
            if len(wav_resampled) < min_length:
                wav_resampled = np.pad(wav_resampled, (0, min_length - len(wav_resampled)), mode='constant')
            
            wav_tensor = torch.from_numpy(wav_resampled[None, :]).to(self.device)
            
            spec = self.mel(wav_tensor)
            logits, feats = self.model(spec.unsqueeze(0))
            embeddings = feats.cpu().numpy().squeeze()
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating EfficientAT embeddings: {e}")
            raise
    
    def extract_audio_features(self, audio):
        """
        Extract comprehensive audio features from audio chunk.
        
        Features extracted:
        - MFCC mean (128-dim)
        - MFCC std (128-dim)
        - Spectral centroid (1-dim)
        - Spectral rolloff (1-dim)
        - Spectral bandwidth (1-dim)
        - Spectral contrast (7-dim)
        - Zero crossing rate (1-dim)
        - RMS energy (1-dim)
        
        Args:
            audio: Audio data as numpy array
            
        Returns:
            numpy array: Combined audio features (268 dimensions)
        """
        try:
            # Pad audio if it's shorter than n_fft
            if len(audio) < self.n_fft:
                audio = np.pad(audio, (0, self.n_fft - len(audio)), mode='constant')
            
            # Extract MFCCs
            mfccs = librosa.feature.mfcc(
                y=audio,
                sr=self.sr,
                n_mfcc=self.n_mfcc,
                n_fft=self.n_fft,
                hop_length=self.hop_length
            )
            
            # MFCC statistics
            mfcc_mean = np.mean(mfccs, axis=1)
            mfcc_std = np.std(mfccs, axis=1)
            
            # Spectral features for brightness/tone
            spectral_centroid = np.mean(librosa.feature.spectral_centroid(
                y=audio, sr=self.sr, n_fft=self.n_fft, hop_length=self.hop_length
            ))
            
            spectral_rolloff = np.mean(librosa.feature.spectral_rolloff(
                y=audio, sr=self.sr, n_fft=self.n_fft, hop_length=self.hop_length
            ))
            
            spectral_bandwidth = np.mean(librosa.feature.spectral_bandwidth(
                y=audio, sr=self.sr, n_fft=self.n_fft, hop_length=self.hop_length
            ))
            
            # Spectral contrast for texture (7 frequency bands)
            spectral_contrast = np.mean(
                librosa.feature.spectral_contrast(
                    y=audio, sr=self.sr, n_fft=self.n_fft, hop_length=self.hop_length
                ),
                axis=1
            )
            
            # Zero crossing rate for percussiveness
            zero_crossing_rate = np.mean(librosa.feature.zero_crossing_rate(audio))
            
            # RMS energy for loudness
            rms_energy = np.mean(librosa.feature.rms(y=audio))
            
            # Combine all features
            features = np.concatenate([
                mfcc_mean,              # 128
                mfcc_std,               # 128
                [spectral_centroid,     # 1
                 spectral_rolloff,      # 1
                 spectral_bandwidth,    # 1
                 zero_crossing_rate,    # 1
                 rms_energy],           # 1
                spectral_contrast       # 7
            ])  # Total: 268 dimensions
            
            return features
            
        except Exception as e:
            logger.error(f"Error extracting audio features: {e}")
            raise
    
    @torch.no_grad()
    def predict(self, audio_data, return_cluster=False):
        """
        Predict scene from audio data.
        
        Args:
            audio_data: Audio data as numpy array (4-second chunk at self.sr Hz)
            return_cluster: Whether to return the cluster number
            
        Returns:
            str or tuple: Predicted scene name, optionally with cluster number
        """
        try:
            # 1. Extract EfficientAT embeddings (1920-dim)
            efficientat_embedding = self.get_efficientat_embedding(audio_data)
            
            # 2. Extract comprehensive audio features (268-dim)
            audio_features = self.extract_audio_features(audio_data)
            
            # 3. Concatenate to form full feature vector (2188-dim)
            full_embedding = np.concatenate([efficientat_embedding, audio_features])
            
            # Reshape to 2D for sklearn (single sample)
            full_embedding = full_embedding.reshape(1, -1)
            
            # 4. Apply preprocessing pipeline: Scale -> PCA
            embeddings_scaled = self.scaler.transform(full_embedding)
            embeddings_pca = self.pca.transform(embeddings_scaled)
            
            # 5. Predict cluster
            cluster = self.kmeans.predict(embeddings_pca)
            
            # 6. Map cluster to scene
            scene = self.scene_map[str(cluster[0])]
            
            logger.debug(f"Predicted scene: {scene} (cluster: {cluster[0]})")
            
            if return_cluster:
                return scene, cluster[0]
            else:
                return scene
            
        except Exception as e:
            logger.error(f"Error in prediction: {e}")
            # Return a default scene on error
            return 'party'
    
    def predict_batch(self, audio_chunks):
        """
        Predict scenes for multiple audio chunks.
        
        Args:
            audio_chunks: List of audio data arrays
            
        Returns:
            list: List of predicted scene names
        """
        predictions = []
        for chunk in audio_chunks:
            predictions.append(self.predict(chunk))
        return predictions


# Global predictor instance for backward compatibility
_predictor_instance = None

def get_predictor():
    """Get or create the global predictor instance."""
    global _predictor_instance
    if _predictor_instance is None:
        _predictor_instance = ScenePredictor()
    return _predictor_instance

def predict(audio_data):
    """
    Convenience function for backward compatibility.
    
    Args:
        audio_data: Audio data as numpy array
        
    Returns:
        str: Predicted scene name
    """
    predictor = get_predictor()
    return predictor.predict(audio_data)


if __name__ == '__main__':
    # Test the predictor
    try:
        # Create a test audio chunk (4 seconds at 48000 Hz)
        test_audio = np.random.randn(4 * 48000)
        
        # Test prediction
        scene = predict(test_audio)
        print(f"Predicted scene: {scene}")
        
    except Exception as e:
        print(f"Error testing predictor: {e}")

