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
import random
import pygame
from threading import Lock
import traceback

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
        self.current_section_index = None
        self.error_message = ""
        self.info_message = ""
        self.watchdog = WatchdogTimer(10, self.reinitialize)  # 10-second timeout
        self.reinitialize_flag = threading.Event()
        self.song_counter = 0
        self.stinger_folder = '../halloween/2024/horror_scenes_trimmed'
        self.stinger_mode_enabled = False
        self.lock = Lock()
            
        # Set up logging
        self.log_messages = deque(maxlen=9)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.log_handler = self.LogHandler(self.log_messages)
        logging.getLogger().addHandler(self.log_handler)

        # set up pygame mixer
        pygame.mixer.init()

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
            self.error_message = f"Error starting controller: {str(e)}\n{traceback.format_exc()}"
            logging.error(f"Error starting controller: {str(e)}\n{traceback.format_exc()}")

    def run(self):
        update_thread = threading.Thread(target=self.update_loop)
        update_thread.daemon = True
        update_thread.start()

        while True:
            try:
                if self.reinitialize_flag.is_set():
                    self.perform_reinitialization()
                self.handle_user_input()
                self.update_display()
                self.watchdog.reset()  # Reset the watchdog timer
                time.sleep(0.05)
            except Exception as e:
                logging.error(f"Error in main loop: {str(e)}\n{traceback.format_exc()}")
                self.error_message = f"Error in main loop: {str(e)}\n{traceback.format_exc()}"

    def create_spotifizer(self):
        return Spotifizer(self.client_id, self.client_secret, self.redirect_uri)

    def refresh_spotify_token(self):
        try:
            self.spotifizer.stop()
            self.spotifizer = self.create_spotifizer()
            self.spotifizer.start()
            logging.info("Spotify token refreshed successfully")
        except Exception as e:
            logging.error(f"Error refreshing Spotify token: {str(e)}\n{traceback.format_exc()}")

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
                    self.error_message = f"Spotify API error: {str(e)}\n{traceback.format_exc()}"
                    logging.error(f"Spotify API error: {str(e)}\n{traceback.format_exc()}")
            except Exception as e:
                self.error_message = f"Error in update loop: {str(e)}\n{traceback.format_exc()}"
                logging.error(f"Error in update loop: {str(e)}\n{traceback.format_exc()}")
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
            self.song_counter += 1
            self.current_song_id = self.spotifizer.current_track_id
            self.current_song_data = self.load_song_data(self.current_song_id)
            self.current_section_index = None  # Reset section index
            self.info_message = f"Now playing: {self.spotifizer.title} by {self.spotifizer.artist}"
            logging.info(f"Now playing: {self.spotifizer.title} by {self.spotifizer.artist}")
            if self.stinger_mode_enabled and self.song_counter > 0 and self.song_counter % 5 == 0:
                self.watchdog.stop()
                self.play_stinger()
                self.watchdog.reset()
    
            return True
        return False

    def play_stinger(self):
        threading.Thread(target=self._play_stinger_thread).start()

    def _play_stinger_thread(self):
        self.watchdog.stop()
        with self.lock:
            try:
                # Save the current scene
                previous_scene = self.scene_manager.current_scene['name']

                self.spotifizer.spotify.pause_playback()
                self.scene_manager.set_scene('off')
                time.sleep(0.5)
                self.scene_manager.set_scene('faint_flicker')

                stinger_files = [f for f in os.listdir(self.stinger_folder) if f.endswith('.wav')]
                if stinger_files:
                    stinger_file = random.choice(stinger_files)
                    pygame.mixer.music.load(os.path.join(self.stinger_folder, stinger_file))
                    pygame.mixer.music.play()
                    while pygame.mixer.music.get_busy():
                        pygame.time.Clock().tick(10)

                self.spotifizer.spotify.start_playback()
                time.sleep(1)  # Wait for playback to resume
                
                # Update the song data
                self.current_song_data = self.load_song_data(self.current_song_id)

                # Get the current section
                self.update_current_section()

                self.info_message = f"Played stinger: {stinger_file}"
                logging.info(f"Played stinger: {stinger_file}")

                # Restore the previous scene
                self.scene_manager.set_scene(previous_scene)
                # add change_scene to oculizer
                self.oculizer.change_scene(previous_scene)
                #self.oculizer.change_scene(previous_scene)

            except Exception as e:
                self.error_message = f"Error playing stinger: {str(e)}\n{traceback.format_exc()}"
                logging.error(f"Error playing stinger: {str(e)}\n{traceback.format_exc()}")
            finally:
                self.watchdog.reset()

    def toggle_stinger_mode(self):
        self.stinger_mode_enabled = not self.stinger_mode_enabled
        status = "enabled" if self.stinger_mode_enabled else "disabled"
        self.info_message = f"Stinger mode {status}"
        

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
        def _load_song_data_thread():
            try:
                filename = os.path.join(self.song_data_dir, f"{song_id}.json")
                if os.path.exists(filename):
                    with open(filename, 'r') as f:
                        data = json.load(f)
                    with self.lock:
                        self.current_song_data = data
                else:
                    self.info_message = f"Song data not found for {song_id}. Using default scene."
                    logging.warning(f"Song data not found for {song_id}. Using default scene.")
            except Exception as e:
                self.error_message = f"Error loading song data: {str(e)}\n{traceback.format_exc()}"
                logging.error(f"Error loading song data: {str(e)}\n{traceback.format_exc()}")

        threading.Thread(target=_load_song_data_thread).start()

    def turn_off_all_lights(self):
        try:
            for light_name, light_fixture in self.oculizer.controller_dict.items():
                if hasattr(light_fixture, 'dim'):
                    light_fixture.dim(0)
                elif hasattr(light_fixture, 'set_channels'):
                    light_fixture.set_channels([0] * light_fixture.channels)
            self.oculizer.dmx_controller.update()       # this is a magic piece of code that is broken, but it saves the day somehow
            logging.info("All lights turned off")
        except Exception as e:
            if not 'OpenDMXController' in str(e):
                self.error_message = f"Error turning off lights: {str(e)}\n{traceback.format_exc()}"
                logging.error(f"Error turning off lights: {str(e)}\n{traceback.format_exc()}")

    def update_lighting(self, force_update=False):
        with self.lock:
            try:
                if self.current_song_data is None:
                    self.turn_off_all_lights()
                    self.scene_manager.set_scene('party')
                    self.oculizer.change_scene('party')
                    self.info_message = "No song data found. Using default scene."
                    logging.info(self.info_message)
                    return

                sections = self.current_song_data.get('sections', [])

                if not sections:
                    self.turn_off_all_lights()
                    self.scene_manager.set_scene('party')
                    self.oculizer.change_scene('party')
                    self.info_message = "No sections found in song data. Using default scene."
                    logging.warning("No sections found in song data. Using default scene.")
                    return

                if self.current_section_index is not None:
                    current_section = sections[self.current_section_index]
                    scene = current_section.get('scene', 'party')
                    
                    # Always apply the scene change
                    #self.info_message = f"Changing to scene: {scene}"
                    #Elogging.info(f"Changing to scene: {scene}")
                    self.turn_off_all_lights()
                    if scene in self.scene_manager.scenes:
                        self.scene_manager.set_scene(scene)
                        self.oculizer.change_scene(scene)
                    else:
                        logging.warning(f"Scene {scene} not found. Using default scene.")
                        self.scene_manager.set_scene('party')
                        self.oculizer.change_scene('party')
                else:
                    logging.warning(f"Current section index is None.")
            except Exception as e:
                self.error_message = f"Error updating lighting: {str(e)}\n{traceback.format_exc()}"
                logging.error(f"Error updating lighting: {str(e)}\n{traceback.format_exc()}")

    def handle_user_input(self):
        try:
            key = self.stdscr.getch()
            if key == ord('q'):
                self.stop()
                exit()
            elif key == ord('r'):
                self.scene_manager.reload_scenes()
                self.info_message = "Scenes reloaded"
            elif key == ord('s'):
                self.toggle_stinger_mode()
            elif key == ord(' '):  # Spacebar
                if self.stinger_mode_enabled:
                    self.play_stinger()
        except Exception as e:
            self.error_message = f"Error handling user input: {str(e)}\n{traceback.format_exc()}"
        finally:
            self.watchdog.reset()

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

            # Add display for stinger mode status
            stinger_status = "ENABLED" if self.stinger_mode_enabled else "DISABLED"
            self.stdscr.addstr(height-4, 0, f"Stinger Mode: {stinger_status}", curses.color_pair(COLOR_PAIRS['info']))
            # Update controls display
            controls = "Press 'q' to quit, 'r' to reload scenes, 's' to toggle stinger mode, 'space' to play stinger"
            self.stdscr.addstr(height-1, 0, controls[:width-1], curses.color_pair(COLOR_PAIRS['controls']))

            self.stdscr.refresh()

        except Exception as e:
            import sys
            print(f"Error updating display: {str(e)}\n{traceback.format_exc()}", file=sys.stderr)
            logging.error(f"Error updating display: {str(e)}\n{traceback.format_exc()}")

    def stop(self):
        try:
            self.oculizer.stop()
            self.spotifizer.stop()
            self.oculizer.join()
            self.spotifizer.join()
            self.watchdog.stop()
            pygame.mixer.quit()
            self.stdscr.clear()
            logging.info("Spotify Oculizer Controller stopped")
        except Exception as e:
            self.error_message = f"Error stopping controller: {str(e)}\n{traceback.format_exc()}"
            logging.error(f"Error stopping controller: {str(e)}\n{traceback.format_exc()}")

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
        stdscr.addstr(0, 0, f"Unhandled error: {str(e)}\n{traceback.format_exc()}", curses.color_pair(COLOR_PAIRS['error']))
        stdscr.refresh()
        time.sleep(5)

if __name__ == "__main__":
    wrapper(main)