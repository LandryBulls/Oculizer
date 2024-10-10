import os
import json
import time
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# Spotify API rate limit is 1000 requests per 5 minutes
# We'll use a conservative limit of 100 requests per minute
RATE_LIMIT = 100
RATE_LIMIT_WINDOW = 60  # seconds

def load_credentials():
    credspath = os.path.join(os.path.dirname(__file__), 'spotify_credentials.txt')
    with open(credspath) as f:
        lines = f.readlines()
        client_id = lines[0].strip().split(' ')[1]
        client_secret = lines[1].strip().split(' ')[1]
    return client_id, client_secret

def get_playlist_tracks(sp, playlist_id):
    results = sp.playlist_tracks(playlist_id)
    tracks = results['items']
    while results['next']:
        results = sp.next(results)
        tracks.extend(results['items'])
    return tracks

def fetch_audio_analysis(sp, track):
    track_id = track['track']['id']
    track_name = track['track']['name']
    track_artists = ', '.join([artist['name'] for artist in track['track']['artists']])
    filename = f"song_data/{track_id}.json"
    
    if os.path.exists(filename):
        print(f"Audio analysis for track '{track_name}' (ID: {track_id}) already exists. Skipping.")
        return None

    try:
        analysis = sp.audio_analysis(track_id)
        # Add track name to the analysis data
        analysis['track'] = analysis.get('track', {})
        analysis['track']['name'] = track_name
        analysis['track']['artists'] = track_artists
        return analysis
    except Exception as e:
        print(f"Error fetching audio analysis for track '{track_name}' (ID: {track_id}): {str(e)}")
        return None

def save_audio_analysis(track_id, analysis):
    if not os.path.exists('song_data'):
        os.makedirs('song_data')
    
    filename = f"song_data/{track_id}.json"
    
    with open(filename, 'w') as f:
        json.dump(analysis, f, indent=2)
    print(f"Saved audio analysis for track '{analysis['track']['name']}' (ID: {track_id})")

def analyze_playlist(playlist_url):
    client_id, client_secret = load_credentials()
    client_credentials_manager = SpotifyClientCredentials(client_id=client_id, client_secret=client_secret)
    sp = spotipy.Spotify(client_credentials_manager=client_credentials_manager)

    playlist_id = playlist_url.split('/')[-1].split('?')[0]
    tracks = get_playlist_tracks(sp, playlist_id)

    request_count = 0
    start_time = time.time()

    for item in tracks:
        if request_count >= RATE_LIMIT:
            elapsed = time.time() - start_time
            if elapsed < RATE_LIMIT_WINDOW:
                sleep_time = RATE_LIMIT_WINDOW - elapsed
                print(f"Rate limit reached. Sleeping for {sleep_time:.2f} seconds")
                time.sleep(sleep_time)
            start_time = time.time()
            request_count = 0

        analysis = fetch_audio_analysis(sp, item)
        if analysis:
            save_audio_analysis(item['track']['id'], analysis)
            request_count += 1

    print("Finished analyzing playlist")

if __name__ == "__main__":
    playlist_url = input("Enter the Spotify playlist URL: ")
    analyze_playlist(playlist_url)
