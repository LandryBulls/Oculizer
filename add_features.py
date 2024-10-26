import os
import json
import time
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from pathlib import Path
from typing import List, Dict, Optional
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class SongDataUpdater:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str):
        self.sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="user-read-playback-state"
        ))
        self.song_data_dir = Path('song_data')
        self.batch_size = 100  # Spotify allows up to 100 tracks per request
        self.rate_limit_delay = 1  # Delay between batch requests in seconds

    def load_song_data(self, filepath: Path) -> Optional[Dict]:
        """Load a single song data file."""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"Error loading {filepath}: {str(e)}")
            return None

    def save_song_data(self, filepath: Path, data: Dict):
        """Save updated song data file."""
        try:
            with open(filepath, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logging.error(f"Error saving {filepath}: {str(e)}")

    def process_song_batch(self, track_ids: List[str]) -> Dict[str, Dict]:
        """Get audio features for a batch of tracks."""
        try:
            audio_features = self.sp.audio_features(track_ids)
            features_dict = {}
            for track_id, features in zip(track_ids, audio_features):
                if features:
                    features_dict[track_id] = {
                        'danceability': features['danceability'],
                        'energy': features['energy'],
                        'acousticness': features['acousticness'],
                        'instrumentalness': features['instrumentalness'],
                        'valence': features['valence'],
                        'tempo': features['tempo'],
                        'loudness': features['loudness']
                    }
            return features_dict
        except Exception as e:
            logging.error(f"Error fetching audio features: {str(e)}")
            return {}

    def update_song_data_files(self):
        """Update all song data files with audio features."""
        # Get list of all song data files
        song_files = list(self.song_data_dir.glob('*.json'))
        total_files = len(song_files)
        logging.info(f"Found {total_files} song data files")

        # Process files in batches
        for i in range(0, total_files, self.batch_size):
            batch_files = song_files[i:i + self.batch_size]
            batch_data = {}
            track_ids = []

            # Load all files in batch and collect track IDs
            for filepath in batch_files:
                song_data = self.load_song_data(filepath)
                if song_data:
                    track_id = filepath.stem  # filename without extension
                    batch_data[track_id] = song_data
                    track_ids.append(track_id)

            # Get audio features for batch
            if track_ids:
                logging.info(f"Processing batch of {len(track_ids)} tracks")
                audio_features = self.process_song_batch(track_ids)

                # Update and save each file in batch
                for track_id, song_data in batch_data.items():
                    if track_id in audio_features:
                        # Update track info while preserving existing data
                        if 'track' not in song_data:
                            song_data['track'] = {}
                        song_data['track']['audio_features'] = audio_features[track_id]
                        
                        # Save updated file
                        filepath = self.song_data_dir / f"{track_id}.json"
                        self.save_song_data(filepath, song_data)
                        logging.info(f"Updated {filepath}")

            # Respect rate limits
            time.sleep(self.rate_limit_delay)

def main():
    # Read Spotify credentials
    credspath = Path('spotify_credentials.txt')
    try:
        with open(credspath) as f:
            lines = f.readlines()
            client_id = lines[0].strip().split(' ')[1]
            client_secret = lines[1].strip().split(' ')[1]
            redirect_uri = lines[2].strip().split(' ')[1]
    except Exception as e:
        logging.error(f"Error reading credentials: {str(e)}")
        return

    updater = SongDataUpdater(client_id, client_secret, redirect_uri)
    updater.update_song_data_files()

if __name__ == "__main__":
    main()