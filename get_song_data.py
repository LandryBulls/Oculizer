import os
import json
import time
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from typing import List, Dict, Set

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

def get_artist_genres(sp, artist_id: str) -> Set[str]:
    """Fetch genres for a specific artist."""
    try:
        artist = sp.artist(artist_id)
        return set(genre.lower() for genre in artist.get('genres', []))
    except Exception as e:
        print(f"Error fetching genres for artist {artist_id}: {str(e)}")
        return set()

def fetch_track_data(sp, track, request_count):
    track_id = track['track']['id']
    track_name = track['track']['name']
    filename = f"song_data/{track_id}.json"
    
    if os.path.exists(filename):
        print(f"Track data for '{track_name}' (ID: {track_id}) already exists. Skipping.")
        return None, request_count

    try:
        # Get all required data
        analysis = sp.audio_analysis(track_id)
        request_count += 1
        features = sp.audio_features([track_id])[0]
        request_count += 1
        track_info = track['track']

        # Get genres for all artists
        all_genres = set()
        artist_details = []
        for artist in track_info['artists']:
            artist_id = artist['id']
            artist_genres = get_artist_genres(sp, artist_id)
            request_count += 1
            all_genres.update(artist_genres)
            
            # Store detailed artist info including their specific genres
            artist_details.append({
                'name': artist['name'],
                'id': artist_id,
                'genres': list(artist_genres)
            })

        # Extract and combine the relevant audio features with genres
        relevant_features = {
            'danceability': features['danceability'],
            'energy': features['energy'],
            'acousticness': features['acousticness'],
            'instrumentalness': features['instrumentalness'],
            'valence': features['valence'],
            'tempo': features['tempo'],
            'loudness': features['loudness'],
            'genres': list(all_genres)  # Add genres to audio_features for ScenePredictor compatibility
        }

        # Combine all the data
        combined_data = {
            'track': {
                **track_info,  # Keep original track info (including original artists array)
                'audio_features': relevant_features,  # Audio features including genres
                'name': track_name,
                'artist_details': artist_details,  # Add detailed artist info as a separate field
            },
            'sections': analysis['sections'],
            'annotation_source': 'manual',
            'metadata': {
                'last_updated': time.strftime('%Y-%m-%d %H:%M:%S'),
                'spotify_id': track_id
            }
        }

        return combined_data, request_count
        
    except Exception as e:
        print(f"Error fetching track data for '{track_name}' (ID: {track_id}): {str(e)}")
        return None, request_count

def save_track_data(track_id, data):
    if not os.path.exists('song_data'):
        os.makedirs('song_data')
    
    filename = f"song_data/{track_id}.json"
    if os.path.exists(filename):
        print(f"Track data for '{data['track']['name']}' (ID: {track_id}) already exists. Not overwriting.")
        
    else:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Saved track data for '{data['track']['name']}' (ID: {track_id})")
        # Print some info about the saved data
        print(f"  Genres: {', '.join(data['track']['genres'][:5])}{'...' if len(data['track']['genres']) > 5 else ''}")
        print(f"  Artists: {', '.join(artist['name'] for artist in data['track']['artists'])}")

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

        track_data, new_requests = fetch_track_data(sp, item, request_count)
        request_count = new_requests
        
        if track_data:
            save_track_data(item['track']['id'], track_data)

    print("Finished analyzing playlist")

if __name__ == "__main__":
    playlist_url = input("Enter the Spotify playlist URL: ")
    analyze_playlist(playlist_url)