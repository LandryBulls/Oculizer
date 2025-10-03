import os
import time
import threading
import curses
import argparse
from curses import wrapper
from oculizer import Oculizer, SceneManager
import logging
from collections import deque
import sounddevice as sd

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

class AudioOculizerController:
    def __init__(self, stdscr, profile='garage', input_device='scarlett', 
                 dual_stream=True, prediction_device=None):
        self.stdscr = stdscr
        curses.curs_set(0)
        self.stdscr.nodelay(1)
        
        self.scene_manager = SceneManager('scenes')
        
        # Initialize Oculizer with scene prediction support
        # dual_stream=True: Use separate device for scene prediction (default)
        # dual_stream=False: Use same audio stream for both FFT and prediction
        self.oculizer = Oculizer(
            profile_name=profile,
            scene_manager=self.scene_manager,
            input_device=input_device,
            scene_prediction_enabled=True,
            scene_prediction_device=prediction_device if dual_stream else None
        )
        
        self.dual_stream = dual_stream
        self.error_message = ""
        self.info_message = ""
        
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

            # Display audio device info (top left)
            fft_device_info = sd.query_devices(self.oculizer.device_idx)
            fft_device_name = fft_device_info['name']
            
            if self.dual_stream and self.oculizer.scene_prediction_device:
                pred_device_info = sd.query_devices(self.oculizer.scene_prediction_device)
                pred_device_name = pred_device_info['name']
                audio_info = f"FFT: {fft_device_name[:30]} | Prediction: {pred_device_name[:30]}"
            else:
                audio_info = f"Audio: {fft_device_name}"
            
            self.stdscr.addstr(2, 0, audio_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))
            
            # Display profile
            profile_info = f"Profile: {self.oculizer.profile_name}"
            self.stdscr.addstr(3, 0, profile_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))

            # Display current scene (top left)
            scene_info = f"Current scene: {self.scene_manager.current_scene['name']}"
            self.stdscr.addstr(5, 0, scene_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))
            
            # Display prediction info
            if self.oculizer.latest_prediction is not None:
                pred_info = f"Latest prediction: {self.oculizer.latest_prediction}"
                self.stdscr.addstr(6, 0, pred_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))
            
            if self.oculizer.current_predicted_scene is not None:
                mode_info = f"Prediction mode: {self.oculizer.current_predicted_scene}"
                self.stdscr.addstr(7, 0, mode_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))
            
            if self.oculizer.current_cluster is not None:
                cluster_info = f"Cluster: {self.oculizer.current_cluster}"
                self.stdscr.addstr(8, 0, cluster_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))

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
            self.oculizer.join()
            logging.info("Audio Oculizer Controller stopped")
        except Exception as e:
            self.error_message = f"Error stopping controller: {str(e)}"
            logging.error(f"Error stopping controller: {str(e)}")

def parse_args():
    parser = argparse.ArgumentParser(
        description='Real-time audio-based Oculizer controller with dual-stream support',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Dual-stream mode (default):
  - FFT stream: Scarlett 2i2 loopback (delayed through Ableton) for DMX modulation
  - Prediction stream: CABLE Output (real-time) for scene prediction
  
Single-stream mode (--single-stream):
  - Uses the same audio source for both FFT and scene prediction
        """
    )
    parser.add_argument('-p', '--profile', type=str, default='garage',
                      help='Lighting profile to use (default: garage)')
    parser.add_argument('-i', '--input-device', type=str, default='scarlett',
                      help='Audio input device for FFT/DMX (default: scarlett)')
    parser.add_argument('--prediction-device', type=int, default=1,
                      help='Device index for scene prediction in dual-stream mode (default: 1)')
    parser.add_argument('--single-stream', action='store_true',
                      help='Use single audio stream for both FFT and prediction')
    parser.add_argument('--list-devices', action='store_true',
                      help='List available audio devices and exit')
    return parser.parse_args()

def main(stdscr, profile, input_device, dual_stream, prediction_device):
    setup_colors()
    controller = AudioOculizerController(
        stdscr, 
        profile=profile,
        input_device=input_device,
        dual_stream=dual_stream,
        prediction_device=prediction_device
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
        dual_stream = not args.single_stream
        wrapper(lambda stdscr: main(
            stdscr, 
            args.profile, 
            args.input_device,
            dual_stream,
            args.prediction_device if dual_stream else None
        ))