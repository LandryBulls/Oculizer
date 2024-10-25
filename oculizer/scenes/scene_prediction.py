import numpy as np
from scipy.spatial.distance import cosine
import spotipy
from spotipy.oauth2 import SpotifyOAuth
import json
import os
from datetime import datetime
import logging
from typing import Dict, List, Optional, Tuple, Set

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
        self.annotated_sections_cache = self._load_annotated_sections()
        
        # EDM genres set
        self.edm_genres = {
            'edm', 'electronic', 'dance', 'house', 'techno', 'trance', 'dubstep', 
            'drum-and-bass', 'electro', 'electronic dance', 'electronica', 'deep-house',
            'tech-house', 'progressive-house', 'tropical-house', 'bass', 'future-bass',
            'electropop', 'synthpop', 'ambient', 'idm'
        }
        
    def _load_annotated_sections(self) -> List[Dict]:
        """Load all annotated sections from existing song data."""
        annotated_sections = []
        
        if not os.path.exists(self.song_data_dir):
            os.makedirs(self.song_data_dir)
            return annotated_sections
            
        for filename in os.listdir(self.song_data_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(self.song_data_dir, filename), 'r') as f:
                        song_data = json.load(f)
                        if 'sections' in song_data:
                            for section in song_data['sections']:
                                if 'scene' in section:
                                    section['song_id'] = filename.replace('.json', '')
                                    annotated_sections.append(section)
                except Exception as e:
                    logging.error(f"Error loading {filename}: {str(e)}")
                    continue
        
        return annotated_sections

    def _get_artist_genres(self, artist_name: str) -> Set[str]:
        """Get genres for an artist by name."""
        try:
            # Search for the artist
            results = self.sp.search(q=artist_name, type='artist', limit=1)
            if not results['artists']['items']:
                logging.warning(f"No artist found for {artist_name}")
                return set()
            
            # Get the first artist's genres
            artist = results['artists']['items'][0]
            return {genre.lower() for genre in artist.get('genres', [])}
            
        except Exception as e:
            logging.error(f"Error getting genres for {artist_name}: {str(e)}")
            return set()

    def _is_edm(self, track_data: Dict) -> bool:
        """Determine if a song is EDM based on its genres."""
        try:
            all_genres = set()
            
            # Get artist names from track data
            artist_names = []
            if isinstance(track_data, dict):
                track_info = track_data.get('track', {})
                if isinstance(track_info, dict):
                    artist_names = [artist.get('name') for artist in track_info.get('artists', [])]
                    
            if not artist_names:
                logging.warning("No artists found in track data")
                return False
            
            # Get genres for each artist
            for artist_name in artist_names:
                if artist_name:  # Check if name is not None/empty
                    all_genres.update(self._get_artist_genres(artist_name))
            
            # Check for EDM genres
            is_edm = bool(all_genres & self.edm_genres)
            logging.info(f"Artist genres: {all_genres}")
            logging.info(f"Is EDM: {is_edm}")
            return is_edm
            
        except Exception as e:
            logging.error(f"Error in _is_edm: {str(e)}")
            return False

    def predict_scene(self, track_id: str, section_index: int) -> Optional[str]:
            """Predict the scene for a given section of a track."""
            try:
                # First, try to load existing data
                cache_path = os.path.join(self.song_data_dir, f"{track_id}.json")
                if os.path.exists(cache_path):
                    with open(cache_path, 'r') as f:
                        track_data = json.load(f)
                else:
                    track_data = self._get_track_features(track_id)
                    if track_data:
                        with open(cache_path, 'w') as f:
                            json.dump(track_data, f)
                    else:
                        logging.error("Failed to get track features")
                        return 'party'

                if 'track' in track_data and 'artists' in track_data['track']:
                    artist_names = [artist.get('name', '').lower() for artist in track_data['track']['artists']]
                    if 'xcx' in any(artist_name for artist_name in artist_names):
                        logging.info("Charli XCX detected, using XCX scene")
                        return 'wobble' if np.random.random() < 0.5 else 'green_bass_pulse'
                
                try:
                    if 'track' in track_data and 'album' in track_data['track']:
                        release_date = track_data['track']['album'].get('release_date', '')
                        if release_date:
                            release_year = int(release_date[:4])
                            if release_year < 1990:
                                logging.info(f"Pre-1990 song detected ({release_year}), using disco scene")
                                return 'disco'
                except (ValueError, TypeError) as e:
                    logging.error(f"Error parsing release date: {str(e)}")
                
                # First check if we have valid section data
                if not track_data or 'sections' not in track_data:
                    logging.error("No sections found in track data")
                    return 'party'
                    
                if section_index >= len(track_data['sections']):
                    logging.error(f"Section index {section_index} out of range")
                    return 'party'

                current_section = track_data['sections'][section_index]
                
                # Try to find a similar section based on audio features
                similar_scene = self._find_most_similar_section(current_section)
                if similar_scene:
                    logging.info(f"Found similar section with scene: {similar_scene}")
                    return similar_scene
                
                # Check if song is EDM
                if self._is_edm(track_data):
                    edm_scenes = ['wobble', 'blue_bass_pulse', 'green_bass_pulse', 'pink_bass_pulse', 'red_bass_pulse']
                    selected_scene = np.random.choice(edm_scenes)
                    logging.info(f"EDM detected, using scene: {selected_scene}")
                    return selected_scene
                
                # Default fallback
                general_scenes = ['party', 'chill_pink', 'chill_blue', 'disco', 'discovibe', 'discolaser']
                selected_scene = np.random.choice(general_scenes)
                logging.info(f"Using general scene: {selected_scene}")
                return selected_scene
                
            except Exception as e:
                logging.error(f"Error in predict_scene: {str(e)}")
                return 'party'

    def _get_track_features(self, track_id: str) -> Optional[Dict]:
        """Get audio features and metadata for a track."""
        try:
            # Get basic track info
            track_info = self.sp.track(track_id)
            # Get audio features
            audio_features = self.sp.audio_features([track_id])[0]
            # Get audio analysis
            audio_analysis = self.sp.audio_analysis(track_id)
            
            # Combine all the data
            track_data = {
                'track': track_info,  # Keep the full track info
                'audio_features': audio_features,
                'sections': audio_analysis['sections']
            }
            
            return track_data
            
        except Exception as e:
            logging.error(f"Error getting track features: {str(e)}")
            return None

    def _get_section_feature_vector(self, section: Dict) -> np.ndarray:
        """Convert section features to a numerical vector for comparison."""
        features = [
            section.get('loudness', 0),
            section.get('tempo', 0),
            section.get('key', 0),
            section.get('mode', 0),
            section.get('duration', 0)
        ]
        return np.array(features)

    def _find_most_similar_section(self, current_section: Dict) -> Optional[str]:
        """Find the most similar annotated section based on features."""
        if not self.annotated_sections_cache:
            return None
            
        try:
            current_features = self._get_section_feature_vector(current_section)
            min_distance = float('inf')
            most_similar_scene = None
            
            for annotated_section in self.annotated_sections_cache:
                if 'scene' not in annotated_section:
                    continue
                    
                annotated_features = self._get_section_feature_vector(annotated_section)
                distance = cosine(current_features, annotated_features)
                
                if distance < min_distance:
                    min_distance = distance
                    most_similar_scene = annotated_section['scene']
            
            return most_similar_scene
            
        except Exception as e:
            logging.error(f"Error finding similar section: {str(e)}")
            return None

    def process_new_track(self, track_id: str) -> Optional[Dict]:
        """Process a new track and save its data with predicted scenes."""
        try:
            track_data = self._get_track_features(track_id)
            if not track_data:
                return None
                
            # Predict scenes for each section
            for i, section in enumerate(track_data['sections']):
                predicted_scene = self.predict_scene(track_id, i)
                section['scene'] = predicted_scene
                
            # Save the processed data
            cache_path = os.path.join(self.song_data_dir, f"{track_id}.json")
            with open(cache_path, 'w') as f:
                json.dump(track_data, f)
                
            return track_data
            
        except Exception as e:
            logging.error(f"Error processing new track: {str(e)}")
            return None