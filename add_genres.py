import os
import json
import time
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from pathlib import Path
from typing import List, Dict, Optional, Set
import logging
import random

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class GenreUpdater:
    def __init__(self, client_id: str, client_secret: str):
        self.sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
            client_id=client_id,
            client_secret=client_secret
        ))
        self.song_data_dir = Path('song_data')
        self.batch_size = 50  # Process 50 tracks at a time
        self.rate_limit_delay = 1  # Delay between batch requests in seconds
        self.max_retries = 3

    def exponential_backoff(self, attempt: int, max_delay: float = 60.0):
        delay = min(random.uniform(0, 2**attempt), max_delay)
        time.sleep(delay)

    def get_track_with_artists(self, track_id: str, attempt: int = 0) -> Optional[Dict]:
        """Fetch track data with full artist information."""
        try:
            track = self.sp.track(track_id)
            return track
        except Exception as e:
            if attempt < self.max_retries:
                logging.warning(f"Retrying track fetch for {track_id} after error: {str(e)}")
                self.exponential_backoff(attempt)
                return self.get_track_with_artists(track_id, attempt + 1)
            else:
                logging.error(f"Failed to fetch track {track_id} after {self.max_retries} attempts: {str(e)}")
                return None

    def get_artist_genres(self, artist_id: str, attempt: int = 0) -> Set[str]:
        """Fetch genres for a specific artist with retries."""
        try:
            artist = self.sp.artist(artist_id)
            return set(genre.lower() for genre in artist.get('genres', []))
        except Exception as e:
            if attempt < self.max_retries:
                logging.warning(f"Retrying genre fetch for artist {artist_id} after error: {str(e)}")
                self.exponential_backoff(attempt)
                return self.get_artist_genres(artist_id, attempt + 1)
            else:
                logging.error(f"Failed to fetch genres for artist {artist_id} after {self.max_retries} attempts: {str(e)}")
                return set()

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

    def process_song_file(self, filepath: Path) -> bool:
        """Process a single song file."""
        song_data = self.load_song_data(filepath)
        if not song_data:
            return False

        # Skip if already has non-empty genres
        if 'track' in song_data and 'genres' in song_data['track'] and song_data['track']['genres']:
            logging.info(f"Skipping {filepath.stem} - already has genres")
            return False

        try:
            # Get track data with proper artist information
            track_id = filepath.stem
            track_data = self.get_track_with_artists(track_id)
            
            if not track_data:
                logging.warning(f"Could not fetch track data for {track_id}")
                return False

            # Get genres for all artists
            all_genres = set()
            artist_details = []

            for artist in track_data['artists']:
                artist_id = artist['id']
                artist_genres = self.get_artist_genres(artist_id)
                all_genres.update(artist_genres)
                
                # Store detailed artist info
                artist_details.append({
                    'name': artist['name'],
                    'id': artist_id,
                    'genres': list(artist_genres)
                })

            # Update the song data while preserving existing info
            if 'track' not in song_data:
                song_data['track'] = {}

            # Update with new artist and genre information
            song_data['track']['artists'] = track_data['artists']  # Full artist objects from Spotify
            song_data['track']['genres'] = list(all_genres)
            song_data['track']['artist_details'] = artist_details
            
            # Update metadata
            if 'metadata' not in song_data:
                song_data['metadata'] = {}
            song_data['metadata']['last_updated'] = time.strftime('%Y-%m-%d %H:%M:%S')

            # Save updated data
            self.save_song_data(filepath, song_data)
            logging.info(f"Updated {filepath.stem} with {len(all_genres)} genres for {len(artist_details)} artists")
            return True

        except Exception as e:
            logging.error(f"Error processing {filepath.stem}: {str(e)}")
            return False

    def update_song_data_files(self):
        """Update all song data files with genre information."""
        # Get list of all song data files
        song_files = list(self.song_data_dir.glob('*.json'))
        total_files = len(song_files)
        logging.info(f"Found {total_files} song data files")
        updated_count = 0
        error_count = 0

        # Process files in batches
        for i in range(0, total_files, self.batch_size):
            batch_files = song_files[i:i + self.batch_size]
            batch_num = i//self.batch_size + 1
            total_batches = (total_files + self.batch_size - 1)//self.batch_size
            logging.info(f"Processing batch {batch_num} of {total_batches}")

            for filepath in batch_files:
                try:
                    if self.process_song_file(filepath):
                        updated_count += 1
                except Exception as e:
                    error_count += 1
                    logging.error(f"Error in batch processing for {filepath.stem}: {str(e)}")

            # Respect rate limits
            time.sleep(self.rate_limit_delay)

        logging.info(f"Finished processing {total_files} files:")
        logging.info(f"  - Successfully updated: {updated_count}")
        logging.info(f"  - Errors encountered: {error_count}")
        logging.info(f"  - Skipped: {total_files - updated_count - error_count}")

def main():
    # Read Spotify credentials
    credspath = Path('spotify_credentials.txt')
    try:
        with open(credspath) as f:
            lines = f.readlines()
            client_id = lines[0].strip().split(' ')[1]
            client_secret = lines[1].strip().split(' ')[1]
    except Exception as e:
        logging.error(f"Error reading credentials: {str(e)}")
        return

    updater = GenreUpdater(client_id, client_secret)
    updater.update_song_data_files()

if __name__ == "__main__":
    main()