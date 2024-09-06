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
# get the client id and client secret from the text file
with open('../../spotify_credentials.txt') as f:
    client_id = f.readline().strip().split(' ')[1]
    client_secret = f.readline().strip().split(' ')[1]
    uri = f.readline().split(' ')[1][:-1]
    username = f.readline().split(' ')[1][:-1]
    token = f.readline().split(' ')[1][:-1]

# set the environment variables
os.environ['SPOTIPY_CLIENT_ID'], os.environ['SPOTIFY_CLIENT_ID'] = client_id, client_id
os.environ['SPOTIPY_CLIENT_SECRET'], os.environ['SPOTIFY_CLIENT_SECRET'] = client_secret, client_secret
os.environ['SPOTIPY_REDIRECT_URI'], os.environ['SPOTIFY_REDIRECT_URI'] = uri, uri

auth_manager = SpotifyClientCredentials()
sp = spotipy.Spotify(auth_manager=auth_manager)

# just add all the scopes
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

if token:
    sp = spotipy.Spotify(auth=token)
    saved_tracks_resp = sp.current_user_saved_tracks(limit=50)
else:
    print('Couldn\'t get token for that username')

user = sp.user(username)
sp.user = user

class Spotifizer(threading.Thread):
    def __init__(self, update_interval=0.1):
        super().__init__()
        self.running = threading.Event()
        self.error_queue = queue.Queue()
        self.info_queue = queue.Queue()
        self.spotify = sp
        self.playing = False
        self.volume = 0
        self.current_track_id = None
        self.current_track_info = None 
        self.artist = None
        self.title = None
        self.update_interval = update_interval
        self.progress = 0
        self.suggested_scene = 'testing'

    def run(self):
        self.running.set()
        try:
            while self.running.is_set():
                self.update_current_track()
        except Exception as e:
            self.error_queue.put(f"Error in Spotifizer: {str(e)}")

    def update_current_track(self):
        current_playback = self.spotify.current_playback()
        if current_playback is not None:
            if current_playback['is_playing']:
                self.playing = True
                self.current_track_id = current_playback['item']['id']
                self.current_track_info = current_playback['item']
                self.artist = current_playback['item']['artists'][0]['name']
                self.title = current_playback['item']['name']
                self.volume = current_playback['device']['volume_percent']
                self.progress = current_playback['progress_ms'] + 500
        else:
            self.playing = False
            self.current_track_id = None
            self.current_track_info = None

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

    def stop(self):
        self.running.clear()


def main():
    stdscr = curses.initscr()
    spotifizer = Spotifizer()
    spotifizer.start()
    spotifizer.pause()
    spotifizer.spotify.volume(50)
    if not spotifizer.spotify.current_playback()['is_playing']:
        spotifizer.play()
    print('Listening to Spotify...')
    try:
        while True:
            if spotifizer.current_track_info is not None:
                stdscr.clear()
                stdscr.addstr(0, 0, f"Track: {spotifizer.title}")
                stdscr.addstr(1, 0, f"Artist: {spotifizer.artist}")
                stdscr.addstr(2, 0, f"Playing: {spotifizer.playing}")
                stdscr.addstr(3, 0, f"Volume: {spotifizer.volume}")
                stdscr.addstr(4, 0, f"Progress_ms: {spotifizer.progress}")
                stdscr.refresh()
            else:
                stdscr.addstr(0, 0, "No track playing...")
                stdscr.refresh()

    except KeyboardInterrupt:
        spotifizer.stop()
        print('Stopped listening to Spotify...')
        time.sleep(1)
    
    finally:

        spotifizer.join()
        curses.endwin()

if __name__ == "__main__":
    main()
