import os
import json
import time
import threading
import pygame
from pygame.locals import *
from oculizer import Oculizer, SceneManager
from oculizer.spotify import Spotifizer
import logging
from collections import deque

# Initialize Pygame
pygame.init()

# Constants
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
FPS = 30

# Colors
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
CYAN = (0, 255, 255)
GREEN = (0, 255, 0)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
MAGENTA = (255, 0, 255)

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
    def __init__(self, client_id, client_secret, redirect_uri):
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Spotify Oculizer Controller")
        self.clock = pygame.time.Clock()
        
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
        
        # Set up logging
        self.log_messages = deque(maxlen=10)
        logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
        self.log_handler = self.LogHandler(self.log_messages)
        logging.getLogger().addHandler(self.log_handler)

        # Fonts
        self.title_font = pygame.font.Font(None, 36)
        self.info_font = pygame.font.Font(None, 24)
        self.log_font = pygame.font.Font(None, 18)

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

        running = True
        while running:
            for event in pygame.event.get():
                if event.type == QUIT:
                    running = False
                elif event.type == KEYDOWN:
                    if event.key == K_q:
                        running = False
                    elif event.key == K_r:
                        self.scene_manager.reload_scenes()
                        self.info_message = "Scenes reloaded"
                        logging.info("Scenes reloaded")

            if self.reinitialize_flag.is_set():
                self.perform_reinitialization()

            self.update_display()
            self.watchdog.reset()  # Reset the watchdog timer
            self.clock.tick(FPS)

        self.stop()

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
                    self.scene_manager.set_scene('flicker')
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
            self.oculizer.dmx_controller.update()
            logging.info("All lights turned off")
        except Exception as e:
            if not 'OpenDMXController' in str(e):
                self.error_message = f"Error turning off lights: {str(e)}"
                logging.error(f"Error turning off lights: {str(e)}")

    def update_lighting(self, force_update=False):
        try:
            if self.current_song_data is None:
                self.turn_off_all_lights()
                self.scene_manager.set_scene('chill_pink')
                self.info_message = "No song data found. Using default scene."
                logging.info("No song data found. Using default scene.")
                return

            sections = self.current_song_data.get('sections', [])

            if not sections:
                self.turn_off_all_lights()
                self.scene_manager.set_scene('flicker')
                self.info_message = "No sections found in song data. Using default scene."
                logging.warning("No sections found in song data. Using default scene.")
                return

            if self.current_section_index is not None:
                current_section = sections[self.current_section_index]
                scene = current_section.get('scene', 'flicker')
                
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

    def update_display(self):
        self.screen.fill(BLACK)

        # Display title
        title = "Spotify Oculizer Controller"
        title_surface = self.title_font.render(title, True, CYAN)
        title_rect = title_surface.get_rect(center=(WINDOW_WIDTH // 2, 30))
        self.screen.blit(title_surface, title_rect)

        # Display ASCII art with animated skulls
        ascii_lines = OCULIZER_ASCII.split('\n')
        ascii_height = len(ascii_lines) * 20  # Adjust line height as needed
        start_y = (WINDOW_HEIGHT - ascii_height) // 2

        skull = SKULL_OPEN if int(time.time() * 2) % 2 == 0 else SKULL_CLOSED
        skull_lines = skull.split('\n')

        for i, line in enumerate(ascii_lines):
            text_surface = self.info_font.render(line, True, MAGENTA)
            text_rect = text_surface.get_rect(center=(WINDOW_WIDTH // 2, start_y + i * 20))
            self.screen.blit(text_surface, text_rect)

        # Add skulls on both sides
        skull_x_left = 50
        skull_x_right = WINDOW_WIDTH - 150
        for i, line in enumerate(skull_lines):
            skull_surface_left = self.info_font.render(line, True, GREEN)
            skull_surface_right = self.info_font.render(line, True, GREEN)
            self.screen.blit(skull_surface_left, (skull_x_left, start_y + i * 20))
            self.screen.blit(skull_surface_right, (skull_x_right, start_y + i * 20))

        # Display current song and progress
        if self.spotifizer.playing:
            song_info = f"Now playing: {self.spotifizer.title} by {self.spotifizer.artist}"
            song_surface = self.info_font.render(song_info, True, GREEN)
            self.screen.blit(song_surface, (10, WINDOW_HEIGHT - 100))

            progress = f"Progress: {self.spotifizer.progress / 1000:.2f}s"
            progress_surface = self.info_font.render(progress, True, GREEN)
            self.screen.blit(progress_surface, (10, WINDOW_HEIGHT - 70))
        else:
            no_song_surface = self.info_font.render("No song playing", True, YELLOW)
            self.screen.blit(no_song_surface, (10, WINDOW_HEIGHT - 100))

        # Display current scene
        scene_info = f"Current scene: {self.scene_manager.current_scene['name']}"
        scene_surface = self.info_font.render(scene_info, True, GREEN)
        self.screen.blit(scene_surface, (10, WINDOW_HEIGHT - 40))

        # Display log messages
        log_start_y = 100
        for i, message in enumerate(self.log_messages):
            log_surface = self.log_font.render(message, True, WHITE)
            self.screen.blit(log_surface, (10, log_start_y + i * 20))

        # Display info message
        if self.info_message:
            info_surface = self.info_font.render(self.info_message, True, GREEN)
            self.screen.blit(info_surface, (10, WINDOW_HEIGHT - 130))

        # Display error message
        if self.error_message:
            error_surface = self.info_font.render(self.error_message, True, RED)
            self.screen.blit(error_surface, (10, WINDOW_HEIGHT - 160))

    # Display controls
        controls = "Press 'q' to quit, 'r' to reload scenes"
        controls_surface = self.info_font.render(controls, True, MAGENTA)
        self.screen.blit(controls_surface, (10, WINDOW_HEIGHT - 30))

        pygame.display.flip()

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

def main():
    try:
        credspath = os.path.join(os.path.dirname(__file__), 'spotify_credentials.txt')
        with open(credspath) as f:
            lines = f.readlines()
            client_id = lines[0].strip().split(' ')[1]
            client_secret = lines[1].strip().split(' ')[1]
            redirect_uri = lines[2].strip().split(' ')[1]
    except Exception as e:
        print(f"Error reading Spotify credentials: {str(e)}")
        return

    controller = SpotifyOculizerController(client_id, client_secret, redirect_uri)
    
    try:
        controller.start()
    except KeyboardInterrupt:
        controller.stop()
    except Exception as e:
        print(f"Unhandled error: {str(e)}")
    finally:
        pygame.quit()

if __name__ == "__main__":
    main()