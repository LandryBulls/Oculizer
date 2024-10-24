import os
import json
import time
import mido
import curses
from collections import OrderedDict
import random

from oculizer.light import Oculizer
from oculizer.scenes import SceneManager
from oculizer.spotify import Spotifizer
import spotipy

def load_song_data(song_data_dir):
    song_data = {}
    for filename in os.listdir(song_data_dir):
        if filename.endswith('.json'):
            with open(os.path.join(song_data_dir, filename), 'r') as f:
                song_data[filename[:-5]] = json.load(f)
    return song_data

def save_song_data(song_data, song_data_dir):
    for song_id, data in song_data.items():
        with open(os.path.join(song_data_dir, f"{song_id}.json"), 'w') as f:
            json.dump(data, f, indent=2)

def get_all_sections(song_data):
    for song_id, data in song_data.items():
        for i, section in enumerate(data.get('sections', [])):
            yield song_id, i, section.get('scene')

def create_midi_scene_map(scenes):
    return {scene_data.get('midi'): scene_name for scene_name, scene_data in scenes.items() if 'midi' in scene_data}

def exponential_backoff(attempt, max_delay=60):
    delay = min(random.uniform(0, 2**attempt), max_delay)
    time.sleep(delay)

def find_unassigned_sections(song_data):
    unassigned_sections = []
    for song_id, data in song_data.items():
        for i, section in enumerate(data.get('sections', [])):
            if section.get('scene') is None:
                unassigned_sections.append((song_id, i))
    return unassigned_sections

def save_song_data(song_data, song_data_dir, current_song_id):
    filepath = os.path.join(song_data_dir, f"{current_song_id}.json")
    with open(filepath, 'w') as f:
        json.dump(song_data[current_song_id], f, indent=2)
    return filepath

def main(stdscr):
    # Initialize components
    scene_manager = SceneManager('scenes')
    scene_manager.scenes = OrderedDict(sorted(scene_manager.scenes.items(), key=lambda x: x[1].get('midi', float('inf'))))
    midi_scene_map = create_midi_scene_map(scene_manager.scenes)
    
    light_controller = Oculizer('garage', scene_manager)
    light_controller.start()

    # Read Spotify credentials
    credspath = os.path.join(os.path.dirname(__file__), 'spotify_credentials.txt')
    with open(credspath) as f:
        lines = f.readlines()
        client_id = lines[0].strip().split(' ')[1]
        client_secret = lines[1].strip().split(' ')[1]
        redirect_uri = lines[2].strip().split(' ')[1]
    
    spotify_controller = Spotifizer(client_id, client_secret, redirect_uri)
    spotify_controller.start()

    # Load song data
    song_data_dir = 'song_data'
    song_data = load_song_data(song_data_dir)
    
    # Set up MIDI input
    try:
        inport = mido.open_input()
    except IOError:
        stdscr.addstr(0, 0, "No MIDI input port found. Please connect a MIDI device and restart.")
        stdscr.refresh()
        time.sleep(5)
        return

    # Set up curses
    curses.curs_set(0)
    stdscr.nodelay(1)

    # Main loop
    unassigned_sections = find_unassigned_sections(song_data)
    current_index = 0
    max_retries = 5
    section_start_time = None
    local_progress = 0

    while True:
        stdscr.clear()

        if current_index < len(unassigned_sections):
            current_song_id, current_section_index = unassigned_sections[current_index]
            current_song = song_data[current_song_id]
            current_section = current_song['sections'][current_section_index]

            # Display current song and section info
            try:
                stdscr.addstr(0, 0, f"Song: {current_song['track']['name']} by {', '.join(current_song['track']['artists'])}")
                stdscr.addstr(1, 0, f"Section: {current_section_index + 1}/{len(current_song['sections'])}")
                stdscr.addstr(2, 0, f"Start: {current_section['start']:.2f}s, Duration: {current_section['duration']:.2f}s")
                stdscr.addstr(3, 0, f"Loudness: {current_section['loudness']:.2f}dB, Tempo: {current_section['tempo']:.2f} BPM")
                stdscr.addstr(4, 0, f"Current scene: {scene_manager.current_scene['name']}")
                stdscr.addstr(5, 0, f"Assigned scene: {current_section.get('scene', 'None')}")
                # add the track id
                
                stdscr.addstr(7, 0, f"Track ID: {current_song_id}")
            except Exception as e:
                print(current_song.keys())
                # close the program if there is an error
                stdscr.addstr(0, 0, f"Error: {str(e)}. Song info: {current_song_id}")
                stdscr.refresh()
                time.sleep(5)
                return


            # Play the current section
            if spotify_controller.current_track_id != current_song_id or section_start_time is None:
                for attempt in range(max_retries):
                    try:
                        spotify_controller.spotify.start_playback(uris=[f"spotify:track:{current_song_id}"])
                        break
                    except spotipy.exceptions.SpotifyException as e:
                        if e.http_status == 429:  # Rate limiting error
                            stdscr.addstr(len(scene_manager.scenes) + 12, 0, f"Rate limit hit. Retrying in a moment...")
                            stdscr.refresh()
                            exponential_backoff(attempt)
                        else:
                            raise
                else:
                    stdscr.addstr(len(scene_manager.scenes) + 12, 0, f"Failed to start playback after {max_retries} attempts.")
                    stdscr.refresh()
                    time.sleep(2)
                    continue

                time.sleep(0.5)  # Wait for playback to start
                section_start = current_section['start'] * 1000  # Convert to milliseconds
                spotify_controller.seek_to_timestamp(int(section_start))
                section_start_time = time.time()
                local_progress = 0

            # Update local progress
            if section_start_time is not None:
                local_progress = (time.time() - section_start_time) * 1000  # in milliseconds

            # Display progress
            section_duration = current_section['duration'] * 1000  # in milliseconds
            progress_percent = min(100, (local_progress / section_duration) * 100)
            stdscr.addstr(6, 0, f"Progress: {progress_percent:.1f}%")

            # Loop the current section
            if local_progress >= section_duration:
                section_start_time = time.time()
                local_progress = 0
                spotify_controller.seek_to_timestamp(int(current_section['start'] * 1000))

            # Display available scenes
            stdscr.addstr(8, 0, "Available scenes:")
            for i, (scene_name, scene_data) in enumerate(scene_manager.scenes.items()):
                midi_note = scene_data.get('midi', 'N/A')
                stdscr.addstr(i+9, 0, f"{scene_name} | MIDI Note: {midi_note}")

            stdscr.addstr(len(scene_manager.scenes) + 10, 0, "Press Enter to assign current scene, <- -> to navigate sections")
            stdscr.addstr(len(scene_manager.scenes) + 11, 0, "Press 'r' to reload scenes, 'q' to quit")

        else:
            stdscr.addstr(0, 0, "No unassigned sections found in song data.")
            stdscr.addstr(1, 0, "Press 'q' to quit.")

        # Handle user input
        key = stdscr.getch()
        if key == ord('\n'):  # Enter key
            current_section['scene'] = scene_manager.current_scene['name']
            song_data[current_song_id]['sections'][current_section_index]['scene'] = current_section['scene']
            
            # Save the updated data immediately
            saved_file = save_song_data(song_data, song_data_dir, current_song_id)
            
            stdscr.addstr(len(scene_manager.scenes) + 12, 0, f"Scene {scene_manager.current_scene['name']} assigned to section {current_section_index + 1}/{len(current_song['sections'])}")
            stdscr.addstr(len(scene_manager.scenes) + 13, 0, f"Data saved to {saved_file}")
            stdscr.refresh()
            time.sleep(1)
        elif key == curses.KEY_RIGHT:
            current_index = (current_index + 1) % len(unassigned_sections)
            section_start_time = None  # Reset timer for new section
        elif key == curses.KEY_LEFT:
            current_index = (current_index - 1) % len(unassigned_sections)
            section_start_time = None  # Reset timer for new section
        elif key == ord('r'):
            scene_manager.reload_scenes()
            scene_manager.scenes = OrderedDict(sorted(scene_manager.scenes.items(), key=lambda x: x[1].get('midi', float('inf'))))
            midi_scene_map = create_midi_scene_map(scene_manager.scenes)
            light_controller.scene_manager = scene_manager  # Update the light controller with the new scenes
            stdscr.addstr(len(scene_manager.scenes) + 12, 0, "Scenes reloaded.")
            stdscr.refresh()
            time.sleep(1)
        elif key == ord('q'):
            stdscr.addstr(len(scene_manager.scenes) + 12, 0, "Quitting and saving data...")
            stdscr.refresh()
            break

        # Handle MIDI input
        for msg in inport.iter_pending():
            if msg.type == 'note_on' and msg.note in midi_scene_map:
                scene_name = midi_scene_map[msg.note]
                light_controller.change_scene(scene_name)

        stdscr.refresh()
        time.sleep(0.01)

    # Clean up
    light_controller.stop()
    light_controller.join()
    spotify_controller.stop()
    spotify_controller.join()
    save_song_data(song_data, song_data_dir)

if __name__ == "__main__":
    curses.wrapper(main)

