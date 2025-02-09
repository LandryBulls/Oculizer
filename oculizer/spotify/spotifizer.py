import os
import json
import time
import threading
import queue
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

class Spotifizer(threading.Thread):
    def __init__(self, client_id, client_secret, redirect_uri, update_interval=0.05, time_offset=1.0):
        super().__init__()
        self.running = threading.Event()
        self.error_queue = queue.Queue()
        self.info_queue = queue.Queue()
        self.auth_manager = self._create_auth_manager(client_id, client_secret, redirect_uri)
        self.spotify = self._initialize_spotify()
        self.playing = False
        self.current_track_id = None
        self.current_track_info = None 
        self.artist = None
        self.title = None
        self.update_interval = update_interval
        self.time_offset = time_offset  # Time offset in seconds
        self.progress = 0
        self.audio_analysis = None
        self.current_section = None
        self.last_update_time = 0
        self.audio_analysis_lock = threading.Lock()
        self.section_lock = threading.Lock()

    def _create_auth_manager(self, client_id, client_secret, redirect_uri):
        scopes = [
            'user-read-playback-state',
            'user-modify-playback-state',
            'user-library-read'
        ]
        return SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=' '.join(scopes)
        )

    def _initialize_spotify(self):
        token_info = self.auth_manager.get_cached_token()
        print(f"Initial token info: {token_info}")
        
        if token_info is None:
            print("No cached token found. Attempting to get new token...")
            token_info = self.auth_manager.get_access_token()
        elif self.auth_manager.is_token_expired(token_info):
            print("Token expired. Attempting to refresh...")
            if 'refresh_token' in token_info:
                token_info = self.auth_manager.refresh_access_token(token_info['refresh_token'])
            else:
                print("No refresh token available. Getting new token...")
                token_info = self.auth_manager.get_access_token()
        
        if token_info and 'access_token' in token_info:
            return Spotify(auth=token_info['access_token'])
        else:
            raise Exception("Failed to obtain valid Spotify access token")

    def run(self):
        self.running.set()
        while self.running.is_set():
            self._check_token()
            self.update_current_track()
            time.sleep(self.update_interval)

    def _check_token(self):
        if self.auth_manager.is_token_expired(self.auth_manager.get_cached_token()):
            token_info = self.auth_manager.refresh_access_token(self.auth_manager.get_cached_token()['refresh_token'])
            self.spotify = Spotify(auth=token_info['access_token'])

    def update_current_track(self):
        current_time = time.time()
        if current_time - self.last_update_time < self.update_interval:
            return

        current_playback = self.spotify.current_playback()
        if current_playback is not None and current_playback['is_playing']:
            self.playing = True
            new_track_id = current_playback['item']['id']
            self.progress = current_playback['progress_ms'] + int(self.time_offset * 1000)  # Add offset

            if new_track_id != self.current_track_id:
                self.current_track_id = new_track_id
                self.current_track_info = current_playback['item']
                self.artist = self.current_track_info['artists'][0]['name']
                self.title = self.current_track_info['name']
                self.fetch_audio_analysis()

            self.update_current_section()
        else:
            self.playing = False
            self.current_track_id = None
            self.current_track_info = None
            with self.audio_analysis_lock:
                self.audio_analysis = None
            with self.section_lock:
                self.current_section = None

        self.last_update_time = current_time

    def fetch_audio_analysis(self):
        filename = f"song_data/{self.current_track_id}.json"
        
        # Check if the audio analysis file already exists
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    self.audio_analysis = json.load(f)
                print(f"Loaded existing audio analysis for track {self.current_track_id}")
                return
            except json.JSONDecodeError:
                print(f"Error reading existing audio analysis file for track {self.current_track_id}. Will fetch from API.")

        # If file doesn't exist or couldn't be read, fetch from API
        try:
            analysis = self.spotify.audio_analysis(self.current_track_id)
            with self.audio_analysis_lock:
                self.audio_analysis = analysis
            self.save_audio_analysis()
        except Exception as e:
            self.error_queue.put(f"Error fetching audio analysis: {str(e)}")

    def save_audio_analysis(self):
        if not os.path.exists('song_data'):
            os.makedirs('song_data')
        
        filename = f"song_data/{self.current_track_id}.json"
        
        # Check if the file already exists
        if not os.path.exists(filename):
            with open(filename, 'w') as f:
                json.dump(self.audio_analysis, f)
            print(f"Saved new audio analysis for track {self.current_track_id}")
        else:
            print(f"Audio analysis file already exists for track {self.current_track_id}. Not overwriting.")

    def update_current_section(self):
        with self.audio_analysis_lock:
            if self.audio_analysis and 'sections' in self.audio_analysis:
                for section in self.audio_analysis['sections']:
                    section_start = section['start'] * 1000
                    section_end = section_start + (section['duration'] * 1000)
                    if section_start <= self.progress < section_end:
                        with self.section_lock:
                            self.current_section = section
                        break

    def seek_to_timestamp(self, timestamp_ms):
        try:
            self.spotify.seek_track(timestamp_ms)
            self.progress = timestamp_ms
        except Exception as e:
            self.error_queue.put(f"Error seeking to timestamp: {str(e)}")

    def loop_current_section(self):
        if self.current_section:
            start_ms = int(self.current_section['start'] * 1000)
            duration_ms = int(self.current_section['duration'] * 1000)
            end_ms = start_ms + duration_ms

            if self.progress >= end_ms:
                self.seek_to_timestamp(start_ms)

    def stop(self):
        self.running.clear()

def main():
    # Read the credentials from the file
    credspath = os.path.join(os.path.dirname(__file__), '../../spotify_credentials.txt')
    with open(credspath) as f:
        lines = f.readlines()
        client_id = lines[0].strip().split(' ')[1]
        client_secret = lines[1].strip().split(' ')[1]
        redirect_uri = lines[2].strip().split(' ')[1]

    spotifizer = Spotifizer(client_id, client_secret, redirect_uri, update_interval=0.05, time_offset=1.0)
    spotifizer.start()

    try:
        while True:
            if spotifizer.playing and spotifizer.current_track_info:
                print(f"\nNow playing: {spotifizer.title} by {spotifizer.artist}")
                with spotifizer.section_lock:
                    current_section = spotifizer.current_section
                if current_section:
                    with spotifizer.audio_analysis_lock:
                        if spotifizer.audio_analysis and 'sections' in spotifizer.audio_analysis:
                            try:
                                section_index = spotifizer.audio_analysis['sections'].index(current_section)
                                total_sections = len(spotifizer.audio_analysis['sections'])
                                print(f"Current section: {section_index + 1}/{total_sections}")
                                print(f"Section start time: {current_section['start']:.2f}s")
                                print(f"Section duration: {current_section['duration']:.2f}s")
                                print(f"Current progress: {spotifizer.progress / 1000:.2f}s")
                                print(f"Section loudness: {current_section['loudness']:.2f}dB")
                                print(f"Section tempo: {current_section['tempo']:.2f} BPM")
                                print(f"Section key: {current_section['key']}")
                                print(f"Section mode: {'Major' if current_section['mode'] == 1 else 'Minor'}")
                            except ValueError:
                                print("Section information temporarily unavailable")
                else:
                    print("Waiting for section information...")
            else:
                print("Waiting for track to start playing...")
            
            time.sleep(0.1)  # Update every 0.1 seconds
    
    except KeyboardInterrupt:
        print("\nStopping Spotifizer...")
        spotifizer.stop()
        spotifizer.join()

if __name__ == "__main__":
    main()