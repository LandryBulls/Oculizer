import os
import json
import time
import threading
import curses
from curses import wrapper
from oculizer import Oculizer, SceneManager
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

# set up curses color pairs
COLOR_PAIRS = {
    'title': (curses.COLOR_CYAN, curses.COLOR_BLACK),
    'info': (curses.COLOR_GREEN, curses.COLOR_BLACK),
    'error': (curses.COLOR_RED, curses.COLOR_BLACK),
    'warning': (curses.COLOR_YELLOW, curses.COLOR_BLACK),
    'ascii_art': (curses.COLOR_MAGENTA, curses.COLOR_BLACK),
    'log': (curses.COLOR_WHITE, curses.COLOR_BLACK),
    'controls': (curses.COLOR_BLUE, curses.COLOR_BLACK),
}

def setup_colors():
    curses.start_color()
    for i, (name, (fg, bg)) in enumerate(COLOR_PAIRS.items(), start=1):
        curses.init_pair(i, fg, bg)
        COLOR_PAIRS[name] = i

class SpotifyOculizerController:
    def __init__(self, client_id, client_secret, redirect_uri, stdscr):
        self.stdscr = stdscr
        curses.curs_set(0)
        self.stdscr.nodelay(1)
        
        self.scene_manager = SceneManager('scenes')
        self.oculizer = Oculizer('garage', self.scene_manager)
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.spotifizer = self.create_spotifizer()
        self.song_data_dir = 'song_data'
        self.current_song_id = None
        self.current_song_data = None
        self.current_section_index = 0
        self.error_message = ""
        self.info_message = ""
        
        # Set up logging
        self.log_messages = deque(maxlen=50)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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
            self.run()
        except Exception as e:
            self.error_message = f"Error starting controller: {str(e)}"
            logging.error(f"Error starting controller: {str(e)}")

    def run(self):
        update_thread = threading.Thread(target=self.update_loop)
        update_thread.daemon = True
        update_thread.start()

        while True:
            self.handle_user_input()
            self.update_display()
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
                    self.check_and_update_song()
                    self.update_lighting()
                else:
                    self.scene_manager.set_scene('off')
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

    def check_and_update_song(self):
        if self.spotifizer.current_track_id != self.current_song_id:
            self.current_song_id = self.spotifizer.current_track_id
            self.current_song_data = self.load_song_data(self.current_song_id)
            self.current_section_index = 0
            self.info_message = f"Now playing: {self.spotifizer.title} by {self.spotifizer.artist}"
            logging.info(f"Now playing: {self.spotifizer.title} by {self.spotifizer.artist}")

    def load_song_data(self, song_id):
        try:
            filename = os.path.join(self.song_data_dir, f"{song_id}.json")
            if os.path.exists(filename):
                with open(filename, 'r') as f:
                    return json.load(f)
            else:
                self.info_message = f"Song data not found for {song_id}. Using default scene."
                logging.warning(f"Song data not found for {song_id}. Using default scene.")
                return None
        except Exception as e:
            self.error_message = f"Error loading song data: {str(e)}"
            logging.error(f"Error loading song data: {str(e)}")
            return None

    def turn_off_all_lights(self):
        try:
            for light_name, light_fixture in self.oculizer.controller_dict.items():
                if hasattr(light_fixture, 'dim'):
                    light_fixture.dim(0)
                elif hasattr(light_fixture, 'set_channels'):
                    light_fixture.set_channels([0] * light_fixture.channels)
            
            time.sleep(0.1)
            logging.info("All lights turned off")
        except Exception as e:
            self.error_message = f"Error turning off lights: {str(e)}"
            logging.error(f"Error turning off lights: {str(e)}")

    def update_lighting(self):
        try:
            if self.current_song_data is None:
                self.turn_off_all_lights()
                self.oculizer.change_scene('suave')
                return

            current_time = self.spotifizer.progress / 1000
            sections = self.current_song_data.get('sections', [])

            if not sections:
                self.turn_off_all_lights()
                self.oculizer.change_scene('suave')
                return

            while (self.current_section_index < len(sections) - 1 and
                   current_time >= sections[self.current_section_index + 1]['start']):
                self.current_section_index += 1

            current_section = sections[self.current_section_index]
            scene = current_section.get('scene', 'suave')
            
            if scene != self.scene_manager.current_scene['name']:
                self.info_message = f"Changing to scene: {scene}"
                logging.info(f"Changing to scene: {scene}")
                self.turn_off_all_lights()
                self.oculizer.change_scene(scene)
        except Exception as e:
            self.error_message = f"Error updating lighting: {str(e)}"
            logging.error(f"Error updating lighting: {str(e)}")

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
            title = "Spotify Oculizer Controller"
            self.stdscr.addstr(0, (width - len(title)) // 2, title, curses.color_pair(COLOR_PAIRS['title']) | curses.A_BOLD)

            # Display current song and progress
            if self.spotifizer.playing:
                song_info = f"Now playing: {self.spotifizer.title} by {self.spotifizer.artist}"
                self.stdscr.addstr(2, 0, song_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))
                progress = f"Progress: {self.spotifizer.progress / 1000:.2f}s"
                self.stdscr.addstr(3, 0, progress, curses.color_pair(COLOR_PAIRS['info']))
            else:
                self.stdscr.addstr(2, 0, "No song playing", curses.color_pair(COLOR_PAIRS['warning']))

            # Display current scene
            scene_info = f"Current scene: {self.scene_manager.current_scene['name']}"
            self.stdscr.addstr(5, 0, scene_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))

            # Display ASCII art
            ascii_lines = OCULIZER_ASCII.split('\n')
            start_row = (height - len(ascii_lines)) // 2
            for i, line in enumerate(ascii_lines):
                self.stdscr.addstr(start_row + i, (width - len(line)) // 2, line, curses.color_pair(COLOR_PAIRS['ascii_art']))

            # Display log messages
            log_start = height - len(self.log_messages) - 2
            self.stdscr.addstr(log_start - 1, 0, "Log Messages:", curses.color_pair(COLOR_PAIRS['log']) | curses.A_BOLD)
            for i, message in enumerate(self.log_messages):
                self.stdscr.addstr(log_start + i, 0, message[:width-1], curses.color_pair(COLOR_PAIRS['log']))

            # Display info message
            if self.info_message:
                self.stdscr.addstr(height-3, 0, self.info_message[:width-1], curses.color_pair(COLOR_PAIRS['info']) | curses.A_BOLD)

            # Display error message
            if self.error_message:
                self.stdscr.addstr(height-2, 0, self.error_message[:width-1], curses.color_pair(COLOR_PAIRS['error']))

            # Display controls
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
            logging.info("Spotify Oculizer Controller stopped")
        except Exception as e:
            self.error_message = f"Error stopping controller: {str(e)}"
            logging.error(f"Error stopping controller: {str(e)}")

def main(stdscr):
    setup_colors()

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

    controller = SpotifyOculizerController(client_id, client_secret, redirect_uri, stdscr)
    
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