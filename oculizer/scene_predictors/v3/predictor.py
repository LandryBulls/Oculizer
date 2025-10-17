import joblib
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import KNeighborsClassifier
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
def set_deterministic_seeds(seed=42):
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
    def __init__(self, model_dir=None, sr=32000, seed=42):
        """
        Initialize the scene predictor with trained models.
        
        Args:
            model_dir: Directory containing the trained models. If None, uses current directory.
            sr: Sample rate
            seed: Random seed for deterministic behavior
        """
        # Set deterministic seeds
        set_deterministic_seeds(seed)
        
        if model_dir is None:
            model_dir = Path(__file__).parent
        
        self.model_dir = Path(model_dir)
        
        # Load preprocessing models
        try:
            self.pca = joblib.load(self.model_dir / 'pca_300.pkl')
            self.scaler = joblib.load(self.model_dir / 'scaler.pkl')
            self.knn = joblib.load(self.model_dir / 'kmeans_120.pkl')
            
            with open(self.model_dir / 'scene_mapping.json', 'r') as f:
                self.scene_map = json.load(f)
                
            logger.info("Successfully loaded preprocessing models")
        except Exception as e:
            logger.error(f"Failed to load preprocessing models: {e}")

        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.sr = sr
        
        # Load EfficientAT model
        self._load_efficientat_model()


        
    def _load_efficientat_model(self):
        """Load and initialize the EfficientAT model."""
        try:
            model_name = "dymn20_as"  # or "mn10_as"
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
    def get_embed(self, audio):
        """
        Generate embeddings using EfficientAT model.
        
        Args:
            audio: Audio data as numpy array
            
        Returns:
            numpy array: Audio embeddings
        """
        try:
            # Validate input
            if not isinstance(audio, np.ndarray):
                raise ValueError("Audio data must be a numpy array")
            
            if len(audio) == 0:
                raise ValueError("Audio data cannot be empty")
            
            wav_resampled = audio.copy()
            
            # Ensure the audio is long enough for STFT processing
            min_length = 1024  # This should match the n_fft parameter in AugmentMelSTFT
            if len(wav_resampled) < min_length:
                # Pad with zeros to reach minimum length
                wav_resampled = np.pad(wav_resampled, (0, min_length - len(wav_resampled)), mode='constant')
            
            wav_tensor = torch.from_numpy(wav_resampled[None, :]).to(self.device)
            
            # Remove redundant torch.no_grad() context manager since method is decorated
            spec = self.mel(wav_tensor)
            logits, feats = self.model(spec.unsqueeze(0))
            embeddings = feats.cpu().numpy().squeeze()
            
            return embeddings
            
        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            raise
    
    @torch.no_grad()
    def predict(self, audio_data, return_cluster=False):
        """
        Predict scene from audio data.
        
        Args:
            audio_data: Audio data as numpy array (4-second chunk at the self.sr (default 48000))
            return_cluster: Whether to return the cluster number
        Returns:
            str: Predicted scene name
        """
        try:
            # Generate embeddings
            embeddings = self.get_embed(audio_data)

            # Reshape to 2D for scaler (single sample)
            embeddings = embeddings.reshape(1, -1)
            
            # Scale them
            embeddings = self.scaler.transform(embeddings)

            # Apply preprocessing
            embeddings = self.pca.transform(embeddings)
            
            # Predict cluster
            cluster = self.knn.predict(embeddings)
            
            # Map cluster to scene
            scene = self.scene_map[str(cluster[0])]
            
            logger.debug(f"Predicted scene: {scene} (cluster: {cluster[0]})")
            return scene, cluster[0] if return_cluster else scene
            
        except Exception as e:
            logger.error(f"Error in prediction: {e}")
            # Return a default scene on error
            return 'party'
    
    def predict_batch(self, audio_chunks):
        """
        Predict scenes for multiple audio chunks.
        
        Args:
            audio_chunks: List of audio data arrays
            sr: Sample rate (default: self.sr)
            
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
        sr: Sample rate (default: self.sr)
        
    Returns:
        str: Predicted scene name
    """
    predictor = get_predictor()
    return predictor.predict(audio_data)

if __name__ == '__main__':
    # Test the predictor
    try:
        # Load test audio
        audio_data = librosa.load('test.wav', sr=32000)[0]
        
        # Test prediction
        scene = predict(audio_data)
        print(f"Predicted scene: {scene}")
        
    except FileNotFoundError:
        print("test.wav not found. Please provide a test audio file.")
    except Exception as e:
        print(f"Error testing predictor: {e}")
