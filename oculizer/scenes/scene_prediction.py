import os
import json
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from scipy.spatial.distance import cosine

# Define the fixed set of available scenes
CANDIDATE_SCENES = [
    'ambient1',
    #'chill_pink',
    'chill_blue',
    'chill_white',
    'drop1',
    'party',
    'bloop',
    'brainblaster',
    'flicker',
    'hell',
    'wobble',
    'temple',
    'rightround',
    'discovibe', 
    'disco',
    'discolaser',
    'red_bass_pulse',
    'blue_bass_pulse',
    'green_bass_pulse',
    'pink_bass_pulse',
    'white_bass_pulse',
    'fullstrobe',
    'electric',
    'fairies',
    'hypno',
    'temple',
    'pink_bulse',
    'blue_bulse',
    'red_bulse',
    'red_echo', 
    'white_echo',
    'slime',
    'whispers'
]

class ScenePredictor:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        """Initialize the scene predictor with Spotify credentials."""
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="user-read-playback-state"
        ))
        self.song_data_dir = 'song_data'

    def _calculate_song_similarity(self, features1: Dict, features2: Dict) -> float:
        """Calculate similarity between two songs based on their audio features."""
        feature_keys = [
            'danceability', 'energy', 'acousticness', 'instrumentalness', 
            'valence', 'tempo', 'loudness'
        ]
        
        # Normalize tempo and loudness
        max_tempo = 200  # Reasonable max tempo
        min_loudness = -60  # Typical min loudness in dB
        
        vec1 = []
        vec2 = []
        
        for key in feature_keys:
            if key == 'tempo':
                vec1.append(features1[key] / max_tempo)
                vec2.append(features2[key] / max_tempo)
            elif key == 'loudness':
                vec1.append((features1[key] - min_loudness) / -min_loudness)
                vec2.append((features2[key] - min_loudness) / -min_loudness)
            else:
                vec1.append(features1[key])
                vec2.append(features2[key])
        
        return 1 - cosine(vec1, vec2)  # Convert distance to similarity

    def _find_similar_songs(self, track_data: Dict) -> List[str]:
        """Find the three most similar songs from the annotated songs."""
        if 'track' not in track_data or 'audio_features' not in track_data['track']:
            return []
            
        target_features = track_data['track']['audio_features']
        similarities = []
        
        # Iterate through all songs in song_data directory
        for filename in os.listdir(self.song_data_dir):
            if not filename.endswith('.json'):
                continue
                
            song_id = filename.replace('.json', '')
            if song_id == track_data.get('metadata', {}).get('spotify_id'):
                continue
                
            try:
                with open(os.path.join(self.song_data_dir, filename)) as f:
                    song_data = json.load(f)
                    
                if ('track' in song_data and 
                    'audio_features' in song_data['track'] and
                    'sections' in song_data):
                    
                    # Check if any sections have assigned scenes
                    has_scenes = any('scene' in section and 
                                   section['scene'] in CANDIDATE_SCENES 
                                   for section in song_data['sections'])
                    
                    if has_scenes:
                        similarity = self._calculate_song_similarity(
                            target_features,
                            song_data['track']['audio_features']
                        )
                        similarities.append((song_id, similarity))
                    
            except Exception as e:
                logging.error(f"Error processing {filename}: {str(e)}")
                continue
        
        # Sort by similarity and return top 3 song IDs
        similarities.sort(key=lambda x: x[1], reverse=True)
        return [s[0] for s in similarities[:3]]

    def _get_section_features(self, section: Dict) -> List[float]:
        """Extract normalized feature vector from a section with improved weighting."""
        return [
            section.get('loudness', -60) / -60 * 2.0,  # Increased weight for loudness
            section.get('tempo', 120) / 200,
            section.get('tempo_confidence', 0.5),
            section.get('key_confidence', 0.5),
            section.get('time_signature_confidence', 0.5),
            # Add new features for better section differentiation
            section.get('duration', 30.0) / 60.0,  # Normalized duration
            1.0 if section.get('time_signature', 4) == 4 else 0.5,  # Common time signature bias
        ]

    def _find_most_similar_scene(self, section: Dict, reference_songs: List[str]) -> str:
        """Find the most similar scene by comparing section features directly."""
        current_features = self._get_section_features(section)
        section_similarities = []
        
        for song_id in reference_songs:
            try:
                with open(os.path.join(self.song_data_dir, f"{song_id}.json")) as f:
                    song_data = json.load(f)
                    
                # Compare with each individual section that has a scene assigned
                for ref_section in song_data.get('sections', []):
                    if 'scene' not in ref_section or ref_section['scene'] not in CANDIDATE_SCENES:
                        continue
                        
                    ref_features = self._get_section_features(ref_section)
                    similarity = 1 - cosine(current_features, ref_features)
                    
                    section_similarities.append({
                        'scene': ref_section['scene'],
                        'similarity': similarity,
                        'loudness': ref_section.get('loudness', -60),
                        'tempo': ref_section.get('tempo', 120)
                    })
                        
            except Exception as e:
                logging.error(f"Error processing sections from {song_id}: {str(e)}")
                continue
        
        if not section_similarities:
            return 'party'  # Default scene if no matches found
        
        # Sort by similarity
        section_similarities.sort(key=lambda x: x['similarity'], reverse=True)
        
        # Take top 5 most similar sections and look for patterns
        top_matches = section_similarities[:5]
        
        # Weight scenes by their similarity and count
        scene_scores = {}
        for match in top_matches:
            scene = match['scene']
            # Weight by similarity and how close the tempo and loudness are
            tempo_diff = abs(match['tempo'] - section.get('tempo', 120)) / 200  # Normalize by max reasonable tempo
            loudness_diff = abs(match['loudness'] - section.get('loudness', -60)) / 60  # Normalize by typical loudness range
            
            # Combined score with more weight on similarity
            score = match['similarity'] * 0.6 + (1 - tempo_diff) * 0.2 + (1 - loudness_diff) * 0.2
            
            if scene in scene_scores:
                scene_scores[scene] += score
            else:
                scene_scores[scene] = score
        
        # Return the scene with the highest weighted score
        return max(scene_scores.items(), key=lambda x: x[1])[0]

    def process_new_track(self, track_id: str) -> Optional[Dict]:
        """Process a new track and save its data with predicted scenes."""
        try:
            # Get track data and audio features from Spotify
            track_info = self.sp.track(track_id)
            audio_features = self.sp.audio_features([track_id])[0]
            audio_analysis = self.sp.audio_analysis(track_id)
            
            # Combine the data
            track_data = {
                'track': {
                    **track_info,
                    'audio_features': {
                        'danceability': audio_features['danceability'],
                        'energy': audio_features['energy'],
                        'acousticness': audio_features['acousticness'],
                        'instrumentalness': audio_features['instrumentalness'],
                        'valence': audio_features['valence'],
                        'tempo': audio_features['tempo'],
                        'loudness': audio_features['loudness']
                    }
                },
                'sections': audio_analysis['sections'],
                'metadata': {
                    'spotify_id': track_id,
                    'last_updated': datetime.now().isoformat()
                }
            }
            
            # Find similar songs
            similar_songs = self._find_similar_songs(track_data)
            
            if not similar_songs:
                logging.warning(f"No similar songs found for {track_id}")
                # Assign default scenes
                for section in track_data['sections']:
                    section['scene'] = 'party'
            else:
                # Predict scenes for each section
                for section in track_data['sections']:
                    scene = self._find_most_similar_scene(section, similar_songs)
                    section['scene'] = scene
            
            # Save the processed data
            output_path = os.path.join(self.song_data_dir, f"{track_id}.json")
            with open(output_path, 'w') as f:
                json.dump(track_data, f, indent=2)
                
            return track_data
            
        except Exception as e:
            logging.error(f"Error processing track {track_id}: {str(e)}")
            return None