"""
Description: Provides Spotifizer class which runs a thread to continuously pull song info from Spotify API.
Must have a Spotify Premium account, the app on the same device, have set up the app, etc. 
"""


import spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth
import threading
import queue
import time
import curses
import os

# get the client id and client secret from the text file
with open('spotify_credentials.txt') as f:
    client_id = f.readline().strip().split(' ')[1]
    client_secret = f.readline().strip().split(' ')[1]
    uri = f.readline().split(' ')[1][:-1]
    username = f.readline().split(' ')[1][:-1]

uri = 'http://localhost:8000'

# set the environment variables
os.environ['SPOTIPY_CLIENT_ID'], os.environ['SPOTIFY_CLIENT_ID'] = client_id, client_id
os.environ['SPOTIPY_CLIENT_SECRET'], os.environ['SPOTIFY_CLIENT_SECRET'] = client_secret, client_secret
os.environ['SPOTIPY_REDIRECT_URI'], os.environ['SPOTIFY_REDIRECT_URI'] = uri, uri

auth_manager = SpotifyClientCredentials()
sp = spotipy.Spotify(auth_manager=auth_manager)

scopes = ['user-library-read',
            'user-read-recently-played',
            'user-top-read',
            'user-follow-read',
            'user-read-playback-position',
            'user-read-playback-state',
            'user-read-currently-playing',
            'user-modify-playback-state',
            'user-read-private',
            'playlist-read-private',
            'playlist-read-collaborative',
            'playlist-modify-public',
            'playlist-modify-private']

token = spotipy.util.prompt_for_user_token(username, scopes)

if token:
    sp = spotipy.Spotify(auth=token)
    saved_tracks_resp = sp.current_user_saved_tracks(limit=50)
else:
    print('Couldn\'t get token for that username')

user = sp.user(username)
sp.user = user

class Spotifizer(threading.Thread):
    def __init__(self, update_interval=1):
        super().__init__()
        self.running = threading.Event()
        self.error_queue = queue.Queue()
        self.info_queue = queue.Queue()
        self.spotify = sp
        self.playing = False
        self.volume = 0
        self.current_track_id = None
        self.current_track_info = None
        self.update_interval = update_interval

    def run(self):
        self.running.set()
        try:
            while self.running.is_set():
                self.update_current_track()
                time.sleep(self.update_interval)
        except Exception as e:
            self.error_queue.put(f"Error in Spotifizer: {str(e)}")

    def update_current_track(self):
        current_playback = self.spotify.current_playback()
        if current_playback and current_playback['is_playing']:
            new_track_id = current_playback['item']['id']
            if new_track_id != self.current_track_id:
                self.current_track_id = new_track_id
                self.fetch_track_info()
            
            self.playing = current_playback['is_playing']
            self.volume = current_playback['device']['volume_percent']
        else:
            self.playing = False
            self.current_track_id = None
            self.current_track_info = None

    def fetch_track_info(self):
        track_info = {}
        track_info['audio_analysis'] = self.spotify.audio_analysis(self.current_track_id)
        track_info['audio_features'] = self.spotify.audio_features(self.current_track_id)[0]
        track_info['name'] = self.spotify.track(self.current_track_id)['name']
        track_info['artist'] = self.spotify.track(self.current_track_id)['artists'][0]['name']
        self.current_track_info = track_info
        self.info_queue.put(track_info)

    def get_current_track_info(self):
        return self.current_track_info

    def play(self):
        try:
            if not self.playing:
                self.spotify.start_playback()
                self.playing = True
        except Exception as e:
            self.error_queue.put(f"Error playing in Spotifizer: {str(e)}")

    def pause(self):
        try:
            if self.playing:
                self.spotify.pause_playback()
                self.playing = False
        except Exception as e:
            self.error_queue.put(f"Error pausing in Spotifizer: {str(e)}")

    def quiet(self, volume=50):
        try:
            self.spotify.volume(volume)
        except Exception as e:
            self.error_queue.put(f"Error setting volume in Spotifizer: {str(e)}")

    def loud(self, volume=100):
        try:
            self.spotify.volume(volume)
        except Exception as e:
            self.error_queue.put(f"Error setting volume in Spotifizer: {str(e)}")

    def next(self):
        try:
            self.spotify.next_track()
        except Exception as e:
            self.error_queue.put(f"Error playing next track in Spotifizer: {str(e)}")

    def previous(self):
        try:
            self.spotify.previous_track()
        except Exception as e:
            self.error_queue.put(f"Error playing previous track in Spotifizer: {str(e)}")


def main():
    stdscr = curses.initscr()
    spotifizer = Spotifizer()
    spotifizer.start()
    spotifizer.pause()
    spotifizer.spotify.volume(50)
    spotifizer.play()
    print('Listening to Spotify...')
    try:
        while True:
            info = spotifizer.get_info()
            if info:
                stdscr.addstr(0, 0, f"Track: {info['track_name']}")
                stdscr.addstr(1, 0, f"Artist: {info['artist_name']}")
                stdscr.addstr(2, 0, f"Playing: {spotifizer.playing}")
                stdscr.addstr(3, 0, f"Volume: {spotifizer.volume}")
                stdscr.addstr(4, 0, f"Genre: {info['audio_features'][0]['genre']}")
                stdscr.refresh()
            else:
                stdscr.addstr(0, 0, "No track playing...")
    except KeyboardInterrupt:
        spotifizer.stop()
        print('Stopped listening to Spotify...')
        time.sleep(1)
    
    finally:
        spotifizer.stop()
        spotifizer.join()
        curses.endwin()

if __name__ == "__main__":
    main()

