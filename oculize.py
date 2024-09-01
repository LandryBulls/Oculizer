import os
import json
import time
import threading
import curses
import argparse
import traceback
import spotipy
from curses import wrapper
from oculizer import Oculizer, SceneManager
from oculizer.scenes.scene_prediction import ScenePredictor
from oculizer.spotify import Spotifizer
import logging
from collections import deque

# ASCII art for Oculizer
OCULIZER_ASCII = """
    ____            _ _              
   / __ \          | (_)             
  | |  | | ___ _   | |_ _______ _ __ 
  | |  | |/ __| | | | | |_  / _ \ '__|
  | |__| | (__| |_| | | |/ /  __/ |   
   \____/ \___|\__,_|_|_/___\___|_|   
"""

# ASCII skull animations
SKULL_OPEN = """
  _____ 
 /     \\
|(o) (o)|
 \  ^  /
  |||||

  |||||
"""

SKULL_CLOSED = """
  _____ 
 /     \\
|(.) (.)|
 \  -  /
  |||||
  |||||
"""

COLOR_PAIRS = {
    'title': (curses.COLOR_WHITE, curses.COLOR_BLACK),
    'info': (curses.COLOR_CYAN, curses.COLOR_BLACK),
    'error': (curses.COLOR_RED, curses.COLOR_BLACK),
    'warning': (curses.COLOR_YELLOW, curses.COLOR_BLACK),
    'ascii_art': (curses.COLOR_MAGENTA, curses.COLOR_BLACK),
    'log': (curses.COLOR_GREEN, curses.COLOR_BLACK),
    'controls': (curses.COLOR_MAGENTA, curses.COLOR_BLACK),
    'skull': (curses.COLOR_GREEN, curses.COLOR_BLACK),
}

def setup_logging():
    """Set up logging configuration for all modules"""
    log_format = '%(asctime)s - %(levelname)s - %(message)s'
    log_file = os.path.join(os.path.dirname(__file__), 'oculizer.log')
    
    # Clear any existing handlers to avoid duplicates
    root_logger = logging.getLogger()
    root_logger.handlers = []
    
    # Set up file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(log_format))
    
    # Configure the root logger
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[file_handler]
    )

def setup_colors():
    curses.start_color()
    for i, (name, (fg, bg)) in enumerate(COLOR_PAIRS.items(), start=1):
        curses.init_pair(i, fg, bg)
        COLOR_PAIRS[name] = i

class WatchdogTimer:
    def __init__(self, timeout, callback):
        self.timeout = timeout
        self.callback = callback
        self.timer = threading.Timer(self.timeout, self.handle_timeout)
        self.last_reset = time.time()

    def reset(self):
        self.timer.cancel()
        self.last_reset = time.time()
        self.timer = threading.Timer(self.timeout, self.handle_timeout)
        self.timer.start()

    def handle_timeout(self):
        if time.time() - self.last_reset >= self.timeout:
            self.callback()

    def stop(self):
        self.timer.cancel()

class SpotifyOculizerController:
    def __init__(self, client_id, client_secret, redirect_uri, stdscr, profile='garage'):
        self.stdscr = stdscr
        curses.curs_set(0)
        self.stdscr.nodelay(1)
        
        self.scene_manager = SceneManager('scenes')
        self.oculizer = Oculizer(profile, self.scene_manager)
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.spotifizer = self.create_spotifizer()
        self.scene_predictor = ScenePredictor(spotify_client=self.spotifizer.spotify, auth_manager=self.spotifizer.auth_manager)
        self.song_data_dir = 'song_data'
        self.current_song_id = None
        self.current_song_data = None
        self.current_section_index = None
        self.error_message = ""
        self.info_message = ""
        self.watchdog = WatchdogTimer(10, self.reinitialize)  # 10-second timeout
        self.reinitialize_flag = threading.Event()
        
        # Set up logging for curses display
        self.log_messages = deque(maxlen=9)
        self.log_handler = self.LogHandler(self.log_messages)
        logging.getLogger().addHandler(self.log_handler)

    class LogHandler(logging.Handler):
        def __init__(self, log_messages):
            super().__init__()
            self.log_messages = log_messages

        def emit(self, record):
            log_entry = self.format(record)
            self.log_messages.append(log_entry)

    def start(self):
        try:
            self.oculizer.start()
            self.spotifizer.start()
            self.watchdog.reset()
            self.run()
        except Exception as e:
            self.error_message = f"Error starting controller: {str(e)}"
            logging.error(f"Error starting controller: {str(e)}")

    def run(self):
        update_thread = threading.Thread(target=self.update_loop)
        update_thread.daemon = True
        update_thread.start()

        while True:
            if self.reinitialize_flag.is_set():
                self.perform_reinitialization()
            self.handle_user_input()
            self.update_display()
            self.watchdog.reset()  # Reset the watchdog timer
            time.sleep(0.05)

    def create_spotifizer(self):
        return Spotifizer(self.client_id, self.client_secret, self.redirect_uri)

    def refresh_spotify_token(self):
        try:
            self.spotifizer.stop()
            self.spotifizer = self.create_spotifizer()
            self.spotifizer.start()
            logging.info("Spotify token refreshed successfully")
        except Exception as e:
            logging.error(f"Error refreshing Spotify token: {str(e)}")

    def update_loop(self):
        while True:
            try:
                if self.spotifizer.playing:
                    song_changed = self.check_and_update_song()
                    self.update_current_section()
                    self.update_lighting(force_update=song_changed)
                else:
                    self.scene_manager.set_scene('party')
            except spotipy.SpotifyException as e:
                if e.http_status == 401 and 'The access token expired' in str(e):
                    logging.warning("Spotify access token expired. Refreshing...")
                    self.refresh_spotify_token()
                else:
                    self.error_message = f"Spotify API error: {str(e)}"
                    logging.error(f"Spotify API error: {str(e)}")
            except Exception as e:
                self.error_message = f"Error in update loop: {str(e)}"
                logging.error(f"Error in update loop: {str(e)}")
            time.sleep(0.1)

    def reinitialize(self):
        logging.warning("Watchdog detected a freeze. Triggering reinitialization.")
        self.reinitialize_flag.set()

    def perform_reinitialization(self):
        logging.info("Performing reinitialization...")
        self.stop()
        time.sleep(1)  # Allow time for threads to stop

        # Reinitialize components
        self.scene_manager = SceneManager('scenes')
        self.oculizer = Oculizer('garage', self.scene_manager)
        self.spotifizer = self.create_spotifizer()

        # Restart components
        self.oculizer.start()
        self.spotifizer.start()

        self.reinitialize_flag.clear()
        self.watchdog.reset()
        logging.info("Reinitialization complete.")

    def check_and_update_song(self):
        if self.spotifizer.current_track_id != self.current_song_id:
            self.current_song_id = self.spotifizer.current_track_id
            self.current_song_data = self.load_song_data(self.current_song_id)
            self.current_section_index = None  # Reset section index
            self.info_message = f"Now playing: {self.spotifizer.title} by {self.spotifizer.artist}"
            logging.info(f"Now playing: {self.spotifizer.title} by {self.spotifizer.artist}")
            return True
        return False

    def update_current_section(self):
        if self.current_song_data is None:
            return

        current_time = self.spotifizer.progress / 1000
        sections = self.current_song_data.get('sections', [])

        new_section_index = next((i for i, section in enumerate(sections) if section['start'] <= current_time < (section['start'] + section['duration'])), None)
        time.sleep(0.1)

        if new_section_index != self.current_section_index:
            self.current_section_index = new_section_index
            logging.info(f"Updated to section index: {self.current_section_index}")

    def load_song_data(self, song_id):
        """Modified to use scene prediction for new songs."""
        try:
            filename = os.path.join(self.song_data_dir, f"{song_id}.json")
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    return json.load(f)
            else:
                # Process new track with scene prediction
                self.info_message = f"Processing new track {song_id} with scene prediction..."
                logging.info(f"Processing new track {song_id} with scene prediction...")
                
                track_data = self.scene_predictor.process_new_track(song_id)
                if track_data:
                    self.info_message = f"Scene prediction completed for {song_id}"
                    logging.info(f"Scene prediction completed for {song_id}")
                    return track_data
                else:
                    self.info_message = f"Failed to process track {song_id}"
                    logging.warning(f"Failed to process track {song_id}")
                    return None
                    
        except Exception as e:
            self.error_message = f"Error loading/predicting song data: {str(e)}"
            logging.error(f"Error loading/predicting song data: {str(e)}")
            return None

    def turn_off_all_lights(self):
        try:
            for light_name, light_fixture in self.oculizer.controller_dict.items():
                # Get the light type from the profile
                light_type = next((light['type'] for light in self.oculizer.profile['lights'] 
                                if light['name'] == light_name), None)
                
                if light_type == 'laser':
                    # Special handling for laser - set all channels to 0
                    light_fixture.set_channels([0] * 10)
                elif hasattr(light_fixture, 'dim'):
                    light_fixture.dim(0)
                elif hasattr(light_fixture, 'set_channels'):
                    light_fixture.set_channels([0] * light_fixture.channels)
            
            self.oculizer.dmx_controller.update()  # this is a magic piece of code that is broken, but it saves the day somehow
            logging.info("All lights turned off")
        except Exception as e:
            if not 'OpenDMXController' in str(e):
                self.error_message = f"Error turning off lights: {str(e)}\n{traceback.format_exc()}"
                logging.error(f"Error turning off lights: {str(e)}\n{traceback.format_exc()}")

    def update_lighting(self, force_update=False):
        """Update lighting based on current section with improved scene handling."""
        try:
            if self.current_song_data is None:
                self.turn_off_all_lights()
                self.scene_manager.set_scene('party')
                self.info_message = "No song data found. Using default scene."
                logging.info("No song data found. Using default scene.")
                return

            sections = self.current_song_data.get('sections', [])

            if not sections:
                self.turn_off_all_lights()
                self.scene_manager.set_scene('party')
                self.info_message = "No sections found in song data. Using default scene."
                logging.warning("No sections found in song data. Using default scene.")
                return

            if self.current_section_index is not None:
                current_section = sections[self.current_section_index]
                
                # Check if section has a valid scene
                scene = current_section.get('scene')
                if not scene or scene not in self.scene_manager.scenes:
                    # If no valid scene, try to predict based on audio features
                    scene = self._predict_fallback_scene(current_section)
                    
                if scene != self.scene_manager.current_scene['name'] or force_update:
                    self.info_message = f"Changing to scene: {scene}"
                    logging.info(f"Changing to scene: {scene}")
                    self.turn_off_all_lights()
                    self.scene_manager.set_scene(scene)
                    
            else:
                logging.warning(f"Current section index is None.")
                
        except Exception as e:
            self.error_message = f"Error updating lighting: {str(e)}"
            logging.error(f"Error updating lighting: {str(e)}")

    def _predict_fallback_scene(self, section):
        """Predict a scene based on section characteristics if no scene is assigned."""
        try:
            # Get basic audio features
            loudness = section.get('loudness', -60)
            tempo = section.get('tempo', 120)
            duration = section.get('duration', 30)
            
            # Simple rule-based fallback prediction
            if loudness > -5 and tempo > 150:
                return 'brainblaster'
            elif loudness > -10 and tempo > 140:
                return 'electric'
            elif loudness > -15 and tempo > 130:
                return 'party'
            elif duration < 15:  # Short section
                return 'rightround'
            elif tempo < 100:  # Slower tempo
                return 'ambient1'
            else:
                return 'party'
                
        except Exception as e:
            logging.error(f"Error in fallback scene prediction: {str(e)}")
            return 'party'

    def handle_user_input(self):
        try:
            key = self.stdscr.getch()
            if key == ord('q'):
                self.stop()
                exit()
            elif key == ord('r'):
                self.scene_manager.reload_scenes()
                self.info_message = "Scenes reloaded"
                logging.info("Scenes reloaded")
        except Exception as e:
            self.error_message = f"Error handling user input: {str(e)}"
            logging.error(f"Error handling user input: {str(e)}")

    def update_display(self):
        try:
            self.stdscr.clear()
            height, width = self.stdscr.getmaxyx()

            # Display title
            title = "https://github.com/LandryBulls/Oculizer"
            self.stdscr.addstr(0, (width - len(title)) // 2, title, curses.color_pair(COLOR_PAIRS['title']) | curses.A_BOLD)

            # Display ASCII art with animated skulls
            ascii_lines = OCULIZER_ASCII.split('\n')
            ascii_height = len(ascii_lines)
            start_row = (height - ascii_height) // 2
            ascii_width = max(len(line) for line in ascii_lines)
            ascii_start = (width - ascii_width) // 2

            skull = SKULL_OPEN if int(time.time() * 2) % 2 == 0 else SKULL_CLOSED
            skull_lines = skull.split('\n')
            skull_height = len(skull_lines)
            skull_width = max(len(line) for line in skull_lines)

            for i, line in enumerate(ascii_lines):
                self.stdscr.addstr(start_row + i, ascii_start, line, curses.color_pair(COLOR_PAIRS['ascii_art']))
                
                # Add skulls on both sides if there's enough vertical space
                if i < skull_height:
                    self.stdscr.addstr(start_row + i, ascii_start - skull_width - 2, skull_lines[i], curses.color_pair(COLOR_PAIRS['skull']))
                    self.stdscr.addstr(start_row + i, ascii_start + ascii_width + 2, skull_lines[i], curses.color_pair(COLOR_PAIRS['skull']))

            # Display current song and progress (top left)
            if self.spotifizer.playing:
                song_info = f"Now playing: {self.spotifizer.title} by {self.spotifizer.artist}"
                self.stdscr.addstr(2, 0, song_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))
                progress = f"Progress: {self.spotifizer.progress / 1000:.2f}s"
                self.stdscr.addstr(3, 0, progress, curses.color_pair(COLOR_PAIRS['info']))
            else:
                self.stdscr.addstr(2, 0, "No song playing", curses.color_pair(COLOR_PAIRS['warning']))

            # Display current scene (top left, below song info)
            scene_info = f"Current scene: {self.scene_manager.current_scene['name']}"
            self.stdscr.addstr(5, 0, scene_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))

            # Display log messages (bottom)
            log_start = height - len(self.log_messages) - 3
            self.stdscr.addstr(log_start, 0, "Log Messages:", curses.color_pair(COLOR_PAIRS['log']) | curses.A_BOLD)
            for i, message in enumerate(self.log_messages):
                self.stdscr.addstr(log_start + i + 1, 0, message[:width-1], curses.color_pair(COLOR_PAIRS['log']))

            # Display info message (bottom)
            if self.info_message:
                self.stdscr.addstr(height-3, 0, self.info_message[:width-1], curses.color_pair(COLOR_PAIRS['info']) | curses.A_BOLD)

            # Display error message (bottom)
            if self.error_message:
                self.stdscr.addstr(height-2, 0, self.error_message[:width-1], curses.color_pair(COLOR_PAIRS['error']))

            # Display controls (bottom)
            controls = "Press 'q' to quit, 'r' to reload scenes"
            self.stdscr.addstr(height-1, 0, controls[:width-1], curses.color_pair(COLOR_PAIRS['controls']))

            self.stdscr.refresh()
        except Exception as e:
            import sys
            print(f"Error updating display: {str(e)}", file=sys.stderr)
            logging.error(f"Error updating display: {str(e)}")

    def stop(self):
        try:
            self.oculizer.stop()
            self.spotifizer.stop()
            self.oculizer.join()
            self.spotifizer.join()
            self.watchdog.stop()
            logging.info("Spotify Oculizer Controller stopped")
        except Exception as e:
            self.error_message = f"Error stopping controller: {str(e)}"
            logging.error(f"Error stopping controller: {str(e)}")

def parse_args():
    parser = argparse.ArgumentParser(description='Spotify-integrated Oculizer controller')
    parser.add_argument('-p', '--profile', type=str, default='garage',
                      help='Profile to use (default: garage)')
    return parser.parse_args()

def main(stdscr):
    setup_colors()
    setup_logging()  # Set up logging before creating any objects
    args = parse_args()

    try:
        credspath = os.path.join(os.path.dirname(__file__), 'spotify_credentials.txt')
        with open(credspath) as f:
            lines = f.readlines()
            client_id = lines[0].strip().split(' ')[1]
            client_secret = lines[1].strip().split(' ')[1]
            redirect_uri = lines[2].strip().split(' ')[1]
    except Exception as e:
        stdscr.addstr(0, 0, f"Error reading Spotify credentials: {str(e)}", curses.color_pair(1))
        stdscr.refresh()
        time.sleep(5)
        return

    controller = SpotifyOculizerController(client_id, client_secret, redirect_uri, stdscr, args.profile)
    
    try:
        controller.start()
    except KeyboardInterrupt:
        controller.stop()
    except Exception as e:
        stdscr.addstr(0, 0, f"Unhandled error: {str(e)}", curses.color_pair(COLOR_PAIRS['error']))
        stdscr.refresh()
        time.sleep(5)

if __name__ == "__main__":
    wrapper(main)