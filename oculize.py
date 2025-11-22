import os
import time
import threading
import curses
import argparse
import platform
from curses import wrapper
from oculizer import Oculizer, SceneManager
import logging
from collections import deque, OrderedDict
import sounddevice as sd
import math
import random

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
    'info': (curses.COLOR_WHITE, curses.COLOR_BLACK),
    'error': (curses.COLOR_WHITE, curses.COLOR_BLACK),
    'warning': (curses.COLOR_WHITE, curses.COLOR_BLACK),
    'ascii_art': (curses.COLOR_WHITE, curses.COLOR_BLACK),
    'log': (curses.COLOR_WHITE, curses.COLOR_BLACK),
    'controls': (curses.COLOR_WHITE, curses.COLOR_BLACK),
    'skull': (curses.COLOR_WHITE, curses.COLOR_BLACK),
    # Toggle mode colors
    'toggle_active': (curses.COLOR_WHITE, curses.COLOR_GREEN),  # Active scene (when not overridden)
    'toggle_selected': (curses.COLOR_BLACK, curses.COLOR_YELLOW),  # Selected for navigation
    'toggle_hover': (curses.COLOR_WHITE, curses.COLOR_BLUE),  # Mouse hover
    'toggle_normal': (curses.COLOR_WHITE, curses.COLOR_BLACK),  # Default
    'toggle_predicted': (curses.COLOR_WHITE, curses.COLOR_BLACK),  # Predicted by AI (not active)
    'toggle_override': (curses.COLOR_BLACK, curses.COLOR_MAGENTA),  # Manually overridden scene (active)
    # Glitch static colors
    'glitch_red': (curses.COLOR_WHITE, curses.COLOR_BLACK),
    'glitch_green': (curses.COLOR_WHITE, curses.COLOR_BLACK),
    'glitch_blue': (curses.COLOR_WHITE, curses.COLOR_BLACK),
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

# Toggle mode helper functions (from toggle.py)
def sort_scenes_alphabetically(scenes):
    return OrderedDict(sorted(scenes.items()))

def find_scene_by_prefix(scenes, prefix):
    if not prefix:
        return -1
    prefix = prefix.lower()
    for i, (scene, _) in enumerate(scenes):
        if scene.lower().startswith(prefix):
            return i
    return -1

def calculate_grid_dimensions(scene_list, max_x, max_y):
    # Find the longest scene name to determine column width
    max_name_length = max(len(scene[0]) for scene in scene_list) + 2  # Add 2 for padding
    
    # Calculate number of columns that can fit
    num_columns = max(1, min(len(scene_list), max_x // max_name_length))
    
    # Calculate number of rows needed
    num_rows = math.ceil(len(scene_list) / num_columns)
    
    # Adjust column width to be uniform
    column_width = max_x // num_columns
    
    return num_rows, num_columns, column_width

def get_grid_position(index, num_columns):
    row = index // num_columns
    col = index % num_columns
    return row, col

def get_index_from_position(row, col, num_columns, total_scenes):
    index = row * num_columns + col
    return min(index, total_scenes - 1)

class AudioOculizerController:
    def __init__(self, stdscr, profile='garage', input_device='scarlett', 
                 dual_stream=True, prediction_device=None, predictor_version='v1',
                 average_dual_channels=False, scene_cache_size=25, prediction_channels=None,
                 test_mode=False):
        self.stdscr = stdscr
        curses.curs_set(0)
        self.stdscr.nodelay(1)
        self.test_mode = test_mode
        
        # Load profile first to get available fixtures for SceneManager
        profile_fixtures = self._load_profile_fixtures(profile)
        
        # Initialize SceneManager with profile awareness for scene fallbacks
        self.scene_manager = SceneManager('scenes', 
                                         profile_name=profile, 
                                         available_fixtures=profile_fixtures)
        
        # Initialize Oculizer with scene prediction support
        # dual_stream=True: Use separate device for scene prediction (default)
        # dual_stream=False: Use same audio stream for both FFT and prediction
        # average_dual_channels=True: Average first two input channels for FFT
        self.oculizer = Oculizer(
            profile_name=profile,
            scene_manager=self.scene_manager,
            input_device=input_device,
            scene_prediction_enabled=True,
            scene_prediction_device=prediction_device if dual_stream else None,
            predictor_version=predictor_version,
            average_dual_channels=average_dual_channels,
            scene_cache_size=scene_cache_size,
            prediction_channels=prediction_channels,
            test_mode=test_mode
        )
        
        self.dual_stream = dual_stream
        self.predictor_version = predictor_version
        self.average_dual_channels = average_dual_channels
        self.profile_name = profile
        self.error_message = ""
        self.info_message = ""
        
        # Glitch effect variables
        self.glitch_particles = []
        self.last_glitch_time = time.time()
        self.flicker_state = 0
        
        # Set up logging for curses display
        self.log_messages = deque(maxlen=9)
        self.log_handler = self.LogHandler(self.log_messages)
        logging.getLogger().addHandler(self.log_handler)
    
    def _load_profile_fixtures(self, profile_name):
        """Load profile and extract available fixture names."""
        try:
            import json
            from pathlib import Path
            
            # Construct path to profile
            current_dir = Path(__file__).resolve().parent
            profile_path = current_dir / 'profiles' / f'{profile_name}.json'
            
            if not profile_path.exists():
                logging.warning(f"Profile '{profile_name}' not found at {profile_path}")
                return set()
            
            with open(profile_path, 'r') as f:
                profile = json.load(f)
            
            # Extract fixture names
            fixtures = set()
            if 'lights' in profile:
                for light in profile['lights']:
                    if 'name' in light:
                        fixtures.add(light['name'])
            
            logging.info(f"Loaded profile '{profile_name}' with {len(fixtures)} fixtures: {', '.join(sorted(fixtures))}")
            return fixtures
            
        except Exception as e:
            logging.error(f"Error loading profile fixtures: {e}")
            return set()

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

    def update_loop(self):
        """Update lighting based on real-time audio predictions."""
        last_scene = None
        
        while True:
            try:
                # Get current scene from oculizer's integrated prediction
                current_scene = self.oculizer.current_predicted_scene
                
                if current_scene and current_scene != last_scene:
                    # Scene has changed
                    if current_scene in self.scene_manager.scenes:
                        self.info_message = f"Changing to scene: {current_scene}"
                        logging.info(f"Changing to scene: {current_scene}")
                        self.oculizer.change_scene(current_scene)
                        last_scene = current_scene
                    else:
                        logging.warning(f"Scene '{current_scene}' not found in scene manager")
                        
            except Exception as e:
                self.error_message = f"Error in update loop: {str(e)}"
                logging.error(f"Error in update loop: {str(e)}")
            
            time.sleep(0.1)

    def turn_off_all_lights(self):
        # Skip in test mode
        if self.test_mode:
            return
            
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
            logging.error(f"Error turning off lights: {str(e)}")

    def run_toggle_mode(self):
        """
        Run interactive toggle mode with live prediction visualization.
        
        Features:
        - Shows predicted scenes in CYAN (not active)
        - Shows active scene in GREEN (when following predictions)
        - Press Ctrl+O to override with manual selection (MAGENTA when active)
        - Press Ctrl+O again to resume following predictions
        """
        # Sort scenes alphabetically
        original_scenes = self.scene_manager.scenes.copy()
        self.scene_manager.scenes = sort_scenes_alphabetically(self.scene_manager.scenes)
        
        # Enable mouse events
        curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
        print('\033[?1003h')  # Enable mouse movement tracking
        self.stdscr.keypad(1)
        
        # Initialize variables
        selected_index = 0
        current_scene_name = self.scene_manager.current_scene['name']
        search_string = ""
        last_search_time = time.time()
        hover_pos = (-1, -1)
        
        # Override state
        override_active = False
        override_scene = None
        last_prediction = None
        
        try:
            while True:
                self.stdscr.clear()
                max_y, max_x = self.stdscr.getmaxyx()
                scene_list = list(self.scene_manager.scenes.items())
                total_scenes = len(scene_list)
                
                # Get current prediction
                predicted_scene = self.oculizer.current_predicted_scene
                
                # Update current scene name based on override state
                if not override_active and predicted_scene and predicted_scene != last_prediction:
                    # Prediction changed and we're following predictions
                    if predicted_scene in self.scene_manager.scenes:
                        self.oculizer.change_scene(predicted_scene)
                        current_scene_name = predicted_scene
                        last_prediction = predicted_scene
                
                # Calculate grid layout
                num_rows, num_columns, column_width = calculate_grid_dimensions(scene_list, max_x, max_y - 6)
                
                # Display header with override status
                if override_active:
                    mode_status = f"OVERRIDE ACTIVE (Manual: {override_scene})"
                    status_color = COLOR_PAIRS['warning']
                else:
                    mode_status = f"FOLLOWING PREDICTIONS (Auto: {current_scene_name})"
                    status_color = COLOR_PAIRS['info']
                
                header_text = f"TOGGLE MODE - {mode_status}"
                commands_text = "[Ctrl+T] Exit  [Ctrl+Q] Quit  [Ctrl+R] Reload"
                if search_string:
                    header_text += f" [Search: {search_string}]"
                
                try:
                    self.stdscr.addstr(0, 0, header_text[:max_x-1], curses.color_pair(status_color) | curses.A_BOLD)
                    self.stdscr.addstr(1, 0, commands_text[:max_x-1], curses.color_pair(COLOR_PAIRS['controls']))
                    
                    # Show prediction info
                    if predicted_scene:
                        pred_info = f"Current Prediction: {predicted_scene}"
                        self.stdscr.addstr(2, 0, pred_info[:max_x-1], curses.color_pair(COLOR_PAIRS['toggle_predicted']))
                    
                    self.stdscr.addstr(3, 0, "Available scenes:", curses.color_pair(COLOR_PAIRS['info']))
                except curses.error:
                    pass
                
                # Display scenes in grid
                for i, (scene, _) in enumerate(scene_list):
                    row, col = get_grid_position(i, num_columns)
                    if row >= num_rows or row >= max_y - 6:
                        break
                    
                    display_y = row + 5  # Start after header (now 5 to account for extra line)
                    display_x = col * column_width
                    
                    scene_str = scene
                    if len(scene_str) > column_width - 2:
                        scene_str = scene_str[:column_width - 5] + "..."
                    
                    # Determine scene display style with new override logic
                    if override_active and scene == override_scene:
                        # Manually overridden scene (active)
                        color = curses.color_pair(COLOR_PAIRS['toggle_override'])
                    elif not override_active and scene == current_scene_name:
                        # Active scene when following predictions
                        color = curses.color_pair(COLOR_PAIRS['toggle_active'])
                    elif predicted_scene and scene == predicted_scene and override_active:
                        # Predicted scene when override is active (show but not active)
                        color = curses.color_pair(COLOR_PAIRS['toggle_predicted'])
                    elif i == selected_index:
                        # Selected for navigation
                        color = curses.color_pair(COLOR_PAIRS['toggle_selected'])
                    elif (row, col) == hover_pos:
                        # Mouse hover
                        color = curses.color_pair(COLOR_PAIRS['toggle_hover'])
                    else:
                        # Normal scene
                        color = curses.color_pair(COLOR_PAIRS['toggle_normal'])
                    
                    # Pad scene name to column width
                    scene_str = scene_str.ljust(column_width - 1)
                    try:
                        self.stdscr.addstr(display_y, display_x, scene_str[:max_x-display_x-1], color)
                    except curses.error:
                        pass
                
                # Display instructions with color legend
                legend = "🟢=Active 🟣=Override ⚫=Available"
                if override_active:
                    legend += " 🔵=Predicted"
                instructions = f"{legend} | Enter: Select Scene (Override) | ESC: Resume Predictions | Type: Search"
                try:
                    self.stdscr.addstr(max_y-1, 0, instructions[:max_x-1], curses.color_pair(COLOR_PAIRS['controls']))
                except curses.error:
                    pass
                
                self.stdscr.refresh()
                
                try:
                    event = self.stdscr.getch()
                    current_time = time.time()
                    
                    if search_string and current_time - last_search_time > 1.0:
                        search_string = ""
                    
                    if event == 17:  # Ctrl+Q
                        print('\033[?1003l')  # Disable mouse tracking
                        curses.mousemask(0)
                        self.stop()
                        exit()
                    elif event == 20:  # Ctrl+T
                        # Return to oculizer mode
                        break
                    elif event == 18:  # Ctrl+R
                        try:
                            self.scene_manager.reload_scenes()
                            self.scene_manager.scenes = sort_scenes_alphabetically(self.scene_manager.scenes)
                            if override_active:
                                self.oculizer.change_scene(override_scene)
                            else:
                                self.oculizer.change_scene(current_scene_name)
                            scene_list = list(self.scene_manager.scenes.items())
                            total_scenes = len(scene_list)
                            self.info_message = "Scenes reloaded"
                            logging.info("Scenes reloaded")
                        except Exception as e:
                            self.error_message = f"Error reloading: {str(e)}"
                            logging.error(f"Error reloading scenes: {str(e)}")
                        time.sleep(1)
                    elif event in [curses.KEY_UP, curses.KEY_DOWN, curses.KEY_LEFT, curses.KEY_RIGHT]:
                        row, col = get_grid_position(selected_index, num_columns)
                        
                        if event == curses.KEY_UP and row > 0:
                            row -= 1
                        elif event == curses.KEY_DOWN and row < num_rows - 1:
                            row += 1
                        elif event == curses.KEY_LEFT and col > 0:
                            col -= 1
                        elif event == curses.KEY_RIGHT and col < num_columns - 1:
                            col += 1
                        
                        new_index = get_index_from_position(row, col, num_columns, total_scenes)
                        if 0 <= new_index < total_scenes:
                            selected_index = new_index
                            search_string = ""
                    elif event == curses.KEY_MOUSE:
                        _, mx, my, _, bstate = curses.getmouse()
                        if my >= 5 and my < min(5 + num_rows, max_y - 1):  # Adjusted for new header line
                            row = my - 5
                            col = mx // column_width
                            hover_pos = (row, col)
                            
                            if bstate & curses.BUTTON1_CLICKED:
                                new_index = get_index_from_position(row, col, num_columns, total_scenes)
                                if 0 <= new_index < total_scenes:
                                    new_scene = scene_list[new_index][0]
                                    self.oculizer.change_scene(new_scene)
                                    current_scene_name = new_scene
                                    selected_index = new_index
                                    search_string = ""
                                    
                                    # Automatically enable override when clicking a scene
                                    override_active = True
                                    override_scene = new_scene
                                    
                                    self.info_message = f"Override: {new_scene} (ESC to resume predictions)"
                                    logging.info(f"Mouse selection: {new_scene} - override enabled")
                    elif event in [curses.KEY_ENTER, 10, 13]:  # Enter key
                        # Check if Shift+Enter (KEY_ENTER with shift modifier doesn't work reliably)
                        # We'll use a different approach - check for specific key codes
                        # In curses, we can't easily detect Shift+Enter, so we'll use a workaround
                        # Let's use regular Enter for selection and implement Shift+Enter detection
                        if 0 <= selected_index < total_scenes:
                            new_scene = scene_list[selected_index][0]
                            self.oculizer.change_scene(new_scene)
                            current_scene_name = new_scene
                            search_string = ""
                            
                            # Automatically enable override when manually selecting a scene
                            override_active = True
                            override_scene = new_scene
                            
                            self.info_message = f"Override: {new_scene} (ESC to resume predictions)"
                            logging.info(f"Manual scene selection: {new_scene} - override enabled")
                    elif event == 27:  # ESC key
                        # ESC: Resume following predictions if override is active
                        if override_active:
                            override_active = False
                            override_scene = None
                            # Switch back to predicted scene if available
                            if predicted_scene and predicted_scene in self.scene_manager.scenes:
                                self.oculizer.change_scene(predicted_scene)
                                current_scene_name = predicted_scene
                            self.info_message = "Override disabled - following predictions"
                            logging.info("Toggle mode: Override disabled via ESC, resuming predictions")
                        search_string = ""
                    elif event in [curses.KEY_BACKSPACE, 127, 8]:  # Backspace
                        search_string = search_string[:-1]
                        last_search_time = current_time
                        new_index = find_scene_by_prefix(scene_list, search_string)
                        if new_index != -1:
                            selected_index = new_index
                    elif 32 <= event <= 126:  # Printable characters
                        search_string += chr(event)
                        last_search_time = current_time
                        new_index = find_scene_by_prefix(scene_list, search_string)
                        if new_index != -1:
                            selected_index = new_index
                
                except curses.error:
                    pass
                
                time.sleep(0.01)
        
        finally:
            # Clean up mouse tracking
            print('\033[?1003l')
            curses.mousemask(0)
            # Restore original scene order if needed
            # self.scene_manager.scenes = original_scenes

    def handle_user_input(self):
        try:
            key = self.stdscr.getch()
            if key == ord('q'):
                self.stop()
                exit()
            elif key == 20:  # Ctrl+T
                # Enter toggle mode
                logging.info("Entering toggle mode")
                self.info_message = "Entering toggle mode..."
                self.run_toggle_mode()
                # Returned from toggle mode
                logging.info("Returned to oculizer mode")
                self.info_message = "Returned to oculizer mode"
            elif key == ord('r'):
                self.scene_manager.reload_scenes()
                self.info_message = "Scenes reloaded"
                logging.info("Scenes reloaded")
        except Exception as e:
            self.error_message = f"Error handling user input: {str(e)}"
            logging.error(f"Error handling user input: {str(e)}")

    def update_glitch_particles(self, height, width):
        """Update and generate glitch particles for static effect."""
        current_time = time.time()
        
        # Remove expired particles
        self.glitch_particles = [p for p in self.glitch_particles if current_time - p['time'] < 0.1]
        
        # Spawn new particles (more frequent - 8% chance per frame)
        if random.random() < 0.08:
            num_particles = random.randint(2, 5)
            for _ in range(num_particles):
                y = random.randint(0, height - 1)
                x = random.randint(0, width - 1)
                color = 'title'  # All white static
                char = random.choice([
                    '█', '▓', '▒', '░', '◆', '◇', '●', '○', '■', '□',
                    '▀', '▄', '▌', '▐', '░', '▒', '▓', '█',
                    '╔', '╗', '╚', '╝', '╠', '╣', '╦', '╩', '╬',
                    '┌', '┐', '└', '┘', '├', '┤', '┬', '┴', '┼',
                    '⚡', '⚠', '◢', '◣', '◤', '◥', '⬒', '⬓', '⬔', '⬕',
                    '⌘', '⌥', '⎋', '⏎', '⏏', '⌫', '⌦',
                    '☰', '☱', '☲', '☳', '☴', '☵', '☶', '☷',
                    '⊕', '⊗', '⊙', '⊚', '⊛', '⊜', '⊝',
                    '⟁', '⟂', '⟐', '⟡', '⟢', '⟣',
                    '▸', '▹', '►', '▻', '◂', '◃', '◄', '◅',
                    '※', '‡', '⁂', '⁎', '⁕', '⁜', '⁂',
                    '◉', '◎', '◐', '◑', '◒', '◓', '◔', '◕',
                    '0', '1', '2', '3', '4', '5', '6', '7', '8', '9',
                ])
                self.glitch_particles.append({
                    'y': y,
                    'x': x,
                    'color': color,
                    'char': char,
                    'time': current_time
                })
    
    def render_glitch_particles(self):
        """Render static glitch particles on screen."""
        for particle in self.glitch_particles:
            try:
                self.stdscr.addstr(
                    particle['y'], 
                    particle['x'], 
                    particle['char'], 
                    curses.color_pair(COLOR_PAIRS[particle['color']]) | curses.A_BOLD
                )
            except curses.error:
                pass  # Ignore errors from drawing at screen edges
    
    def get_flicker_attribute(self):
        """Get brightness flicker attribute (fast frequency)."""
        # Simple every-other-frame flicker
        self.flicker_state = (self.flicker_state + 1) % 2
        
        # curses.A_DIM is too dark, so we'll just return normal
        # The flicker effect will be provided by the static glitches instead
        return curses.A_NORMAL

    def update_display(self):
        try:
            self.stdscr.clear()
            height, width = self.stdscr.getmaxyx()
            
            # Update glitch particles
            self.update_glitch_particles(height, width)

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

            # Display audio device info with channel details (top left)
            if self.test_mode:
                # In test mode, only show prediction device
                pred_device_info = sd.query_devices(self.oculizer.scene_prediction_device)
                pred_device_name = pred_device_info['name']
                
                # Prediction channel info
                if self.oculizer.prediction_channel_indices:
                    pred_ch = f" ch{[i+1 for i in self.oculizer.prediction_channel_indices]}"
                else:
                    pred_ch = " all"
                
                audio_info = f"Prediction: {pred_device_name[:30]}{pred_ch}"
            elif self.dual_stream and self.oculizer.scene_prediction_device:
                fft_device_info = sd.query_devices(self.oculizer.device_idx)
                fft_device_name = fft_device_info['name']
                pred_device_info = sd.query_devices(self.oculizer.scene_prediction_device)
                pred_device_name = pred_device_info['name']
                
                # FFT channel info
                if self.average_dual_channels:
                    fft_ch = " ch1-2"
                else:
                    fft_ch = " ch1"
                
                # Prediction channel info
                if self.oculizer.prediction_channel_indices:
                    pred_ch = f" ch{[i+1 for i in self.oculizer.prediction_channel_indices]}"
                else:
                    pred_ch = " all"
                
                audio_info = f"FFT: {fft_device_name[:20]}{fft_ch} | Pred: {pred_device_name[:20]}{pred_ch}"
            else:
                fft_device_info = sd.query_devices(self.oculizer.device_idx)
                fft_device_name = fft_device_info['name']
                if self.average_dual_channels:
                    fft_ch = " ch1-2"
                else:
                    fft_ch = " ch1"
                audio_info = f"Audio: {fft_device_name}{fft_ch}"
            
            self.stdscr.addstr(2, 0, audio_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))
            
            # Display profile
            profile_info = f"Profile: {self.oculizer.profile_name}"
            self.stdscr.addstr(3, 0, profile_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))

            # Display predictor version
            predictor_info = f"Predictor: {self.predictor_version}"
            self.stdscr.addstr(4, 0, predictor_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))
            
            # Display stream mode
            if self.test_mode:
                stream_mode = "Stream Mode: TEST (prediction only, no FFT/DMX)"
            elif self.dual_stream:
                stream_mode = "Stream Mode: DUAL (separate devices for FFT and prediction)"
            else:
                stream_mode = "Stream Mode: SINGLE (shared device for FFT and prediction)"
            self.stdscr.addstr(5, 0, stream_mode[:width-1], curses.color_pair(COLOR_PAIRS['info']))

            # Display channel mode
            row_offset = 6
            if self.average_dual_channels:
                channel_info = "FFT Mode: Dual Channel (Averaged)"
                self.stdscr.addstr(row_offset, 0, channel_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))
                row_offset += 1

            # Display current scene (top left)
            current_scene_name = self.scene_manager.current_scene['name']
            scene_info = f"Current scene: {current_scene_name}"
            scene_row = row_offset
            self.stdscr.addstr(scene_row, 0, scene_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))
            
            # Display prediction and fallback info
            pred_row = scene_row + 1
            if self.oculizer.current_predicted_scene is not None:
                predicted_scene = self.oculizer.current_predicted_scene
                
                # Check if fallback was applied
                fallback_scene = None
                if hasattr(self.scene_manager, 'fallback_mappings') and predicted_scene in self.scene_manager.fallback_mappings:
                    fallback_scene = self.scene_manager.fallback_mappings[predicted_scene]
                
                if fallback_scene and fallback_scene == current_scene_name:
                    # Fallback was applied
                    pred_info = f"Predicted: {predicted_scene} → {fallback_scene} (fallback)"
                    self.stdscr.addstr(pred_row, 0, pred_info[:width-1], curses.color_pair(COLOR_PAIRS['warning']))
                    pred_row += 1
                else:
                    # No fallback, show normal prediction
                    pred_info = f"Predicted: {predicted_scene}"
                    self.stdscr.addstr(pred_row, 0, pred_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))
                    pred_row += 1
            
            if self.oculizer.latest_prediction is not None:
                pred_info = f"Latest prediction: {self.oculizer.latest_prediction}"
                self.stdscr.addstr(pred_row, 0, pred_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))
            
            if self.oculizer.current_cluster is not None:
                cluster_info = f"Cluster: {self.oculizer.current_cluster}"
                self.stdscr.addstr(pred_row + 2, 0, cluster_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))

            # Display log messages (bottom)
            log_start = height - len(self.log_messages) - 4
            self.stdscr.addstr(log_start, 0, "Log Messages:", curses.color_pair(COLOR_PAIRS['log']) | curses.A_BOLD)
            for i, message in enumerate(self.log_messages):
                self.stdscr.addstr(log_start + i + 1, 0, message[:width-1], curses.color_pair(COLOR_PAIRS['log']))

            # Display info message (bottom - with blank line above)
            if self.info_message:
                self.stdscr.addstr(height-3, 0, self.info_message[:width-1], curses.color_pair(COLOR_PAIRS['info']) | curses.A_BOLD)

            # Display error message (bottom)
            if self.error_message:
                self.stdscr.addstr(height-2, 0, self.error_message[:width-1], curses.color_pair(COLOR_PAIRS['error']))

            # Display controls (bottom)
            controls = "Press 'q' to quit, Ctrl+T for toggle mode, 'r' to reload scenes"
            self.stdscr.addstr(height-1, 0, controls[:width-1], curses.color_pair(COLOR_PAIRS['controls']))

            # Render glitch particles on top of everything
            self.render_glitch_particles()

            self.stdscr.refresh()
        except Exception as e:
            import sys
            print(f"Error updating display: {str(e)}", file=sys.stderr)
            logging.error(f"Error updating display: {str(e)}")

    def stop(self):
        try:
            self.oculizer.stop()
            # Use timeout to avoid hanging indefinitely on Windows
            self.oculizer.join(timeout=3.0)
            if self.oculizer.is_alive():
                logging.warning("Oculizer thread did not stop within timeout")
            logging.info("Audio Oculizer Controller stopped")
        except Exception as e:
            self.error_message = f"Error stopping controller: {str(e)}"
            logging.error(f"Error stopping controller: {str(e)}")

def parse_args():
    # Detect OS and set defaults
    is_macos = platform.system() == 'Darwin'
    
    # macOS defaults (optimized for Mac setup with Scarlett + BlackHole)
    if is_macos:
        default_input_device = 'scarlett'
        default_prediction_device = 'blackhole'
        default_single_stream = False  # Use dual-stream on Mac
        default_scene_cache_size = 1  # Instant response
        default_prediction_channels = '1'  # BlackHole channel 1
        default_profile = 'mobile'  # Mobile profile for Mac
    else:
        # Windows/Linux defaults
        default_input_device = 'scarlett'
        default_prediction_device = 'cable_output'
        default_single_stream = False
        default_scene_cache_size = 25  # Heavy smoothing
        default_prediction_channels = None  # Auto-detect
        default_profile = 'garage2025'
    
    parser = argparse.ArgumentParser(
        description='Real-time audio-based Oculizer controller with dual-stream support',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Dual-stream mode (default):
  - FFT stream: Scarlett 2i2 interface loopback (delayed through Ableton) for DMX modulation
  - Prediction stream: VB Cable Output (real-time, auto-detected by name) for scene prediction
  - Predictor: v4 (default)
  
Single-stream mode (--single-stream):
  - Uses the same audio source for both FFT and scene prediction

Dual-channel averaging (--average-dual-channels):
  - Averages first two input channels of your audio interface (useful for Scarlett 18i20)
  - Can be combined with dual-stream mode to use VB Cable Output for predictions

Device Selection:
  - Devices are auto-detected by name (e.g., 'cable_output', 'scarlett')
  - This is more reliable than device indices which can change between sessions
  - You can still use device indices if needed (e.g., --prediction-device 84)

Scene Cache Size:
  - Controls smoothing of scene predictions (default: 1 on macOS, 25 on others)
  - 1: Instant response, may flicker between scenes
  - 3-5: Minimal smoothing (~0.3-0.5s)
  - 25: Heavy smoothing (2.5s lag) - tested behavior on Windows
        """
    )
    parser.add_argument('-p', '--profile', type=str, default=default_profile,
                      help=f'Lighting profile to use (default: {default_profile})')
    parser.add_argument('-i', '--input-device', type=str, default=default_input_device,
                      help=f'Audio input device for FFT/DMX (default: {default_input_device})')
    parser.add_argument('--prediction-device', type=str, default=None,
                      help=f'Device for scene prediction in dual-stream mode (default: {default_prediction_device} if dual-stream, otherwise None). Can be a device name (cable_output, scarlett, etc.) or device index number.')
    parser.add_argument('--single-stream', action='store_true', default=default_single_stream,
                      help=f'Use single audio stream for both FFT and prediction (default: {not default_single_stream})')
    parser.add_argument('--predictor-version', '--predictor', type=str, default='v4',
                      choices=['v1', 'v3', 'v4', 'v5'],
                      help='Scene predictor version to use (default: v4)')
    parser.add_argument('--average-dual-channels', action='store_true',
                      help='Average first two input channels together for FFT (useful for Scarlett 18i20)')
    parser.add_argument('--scene-cache-size', type=int, default=default_scene_cache_size,
                      help=f'Number of recent predictions to cache for smoothing (default: {default_scene_cache_size}). 1=instant, 25=heavy smoothing')
    parser.add_argument('--prediction-channels', type=str, default=default_prediction_channels,
                      help=f'Channels to use from prediction device (e.g., "1" for channel 1, "1,2" for channels 1-2 averaged, "1-16" for all 16 channels averaged). Default: {default_prediction_channels if default_prediction_channels else "auto-detect"}')
    parser.add_argument('--test', action='store_true',
                      help='Test mode: Enable scene predictions only, disable FFT reactivity and DMX output. Uses virtual cable (BlackHole on macOS, Cable Output on Windows) for predictions.')
    parser.add_argument('--list-devices', action='store_true',
                      help='List available audio devices and exit')
    return parser.parse_args()

def main(stdscr, profile, input_device, dual_stream, prediction_device, predictor_version, average_dual_channels, scene_cache_size, prediction_channels, test_mode):
    setup_colors()
    controller = AudioOculizerController(
        stdscr, 
        profile=profile,
        input_device=input_device,
        dual_stream=dual_stream,
        prediction_device=prediction_device,
        predictor_version=predictor_version,
        average_dual_channels=average_dual_channels,
        scene_cache_size=scene_cache_size,
        prediction_channels=prediction_channels,
        test_mode=test_mode
    )
    
    try:
        controller.start()
    except KeyboardInterrupt:
        controller.stop()
    except Exception as e:
        stdscr.addstr(0, 0, f"Unhandled error: {str(e)}", curses.color_pair(COLOR_PAIRS['error']))
        stdscr.refresh()
        time.sleep(5)

if __name__ == "__main__":
    # Parse args first to handle --list-devices without curses
    args = parse_args()
    setup_logging()  # Set up logging before creating any objects
    
    # List devices if requested (don't use curses for this)
    if args.list_devices:
        print("\nAvailable audio devices:")
        devices = sd.query_devices()
        print(devices)
        print("\n=== Input Devices ===")
        for i, device in enumerate(devices):
            if isinstance(device, dict) and device.get('max_input_channels', 0) > 0:
                print(f"{i}: {device['name']} ({device['max_input_channels']} channels)")
    else:
        # Handle test mode
        if args.test:
            # In test mode, set up prediction-only with virtual cable
            is_macos = platform.system() == 'Darwin'
            if is_macos:
                args.prediction_device = 'blackhole'
                args.prediction_channels = '1'
                args.scene_cache_size = 1
            else:
                args.prediction_device = 'cable_output'
                args.prediction_channels = None
                args.scene_cache_size = 25
            
            # Disable FFT stream by using a dummy device that won't be used
            args.input_device = args.prediction_device
            dual_stream = True  # Use dual-stream setup (prediction device will be used)
            
            logging.info("TEST MODE enabled: Scene predictions only, no FFT/DMX")
            logging.info(f"  Using {args.prediction_device} for predictions")
        else:
            # Determine if dual-stream mode should be used
            # If user explicitly specifies --single-stream, respect it
            # Otherwise, use the OS default
            dual_stream = not args.single_stream
            
            # If user explicitly provided a prediction device, enable dual-stream
            # (unless they explicitly requested single-stream)
            if args.prediction_device is not None and not args.single_stream:
                dual_stream = True
                logging.info(f"Enabling dual-stream mode (prediction device explicitly specified: '{args.prediction_device}')")
        
        # Convert prediction_device to int if it's a numeric string
        # Apply default prediction device if dual-stream is enabled and no device was specified
        if dual_stream and args.prediction_device is None:
            prediction_device = default_prediction_device
            logging.info(f"Using default prediction device for dual-stream mode: {prediction_device}")
        else:
            prediction_device = args.prediction_device
        
        if dual_stream and prediction_device is not None:
            try:
                prediction_device = int(prediction_device)
            except (ValueError, TypeError):
                # Keep as string if not numeric
                pass
        
        # Log the final configuration
        if dual_stream:
            logging.info(f"Starting in DUAL-STREAM mode:")
            logging.info(f"  FFT/Reactivity device: {args.input_device}")
            logging.info(f"  Prediction device: {prediction_device}")
            if args.prediction_channels:
                logging.info(f"  Prediction channels: {args.prediction_channels}")
        else:
            logging.info(f"Starting in SINGLE-STREAM mode:")
            logging.info(f"  Device: {args.input_device} (used for both FFT and prediction)")
        
        wrapper(lambda stdscr: main(
            stdscr, 
            args.profile, 
            args.input_device,
            dual_stream,
            prediction_device if dual_stream else None,
            args.predictor_version,
            args.average_dual_channels,
            args.scene_cache_size,
            args.prediction_channels,
            args.test
        ))