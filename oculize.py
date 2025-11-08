import os
import time
import threading
import curses
import argparse
import platform
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
                 dual_stream=True, prediction_device=None, predictor_version='v1',
                 average_dual_channels=False, scene_cache_size=25, prediction_channels=None):
        self.stdscr = stdscr
        curses.curs_set(0)
        self.stdscr.nodelay(1)
        
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
            prediction_channels=prediction_channels
        )
        
        self.dual_stream = dual_stream
        self.predictor_version = predictor_version
        self.average_dual_channels = average_dual_channels
        self.profile_name = profile
        self.error_message = ""
        self.info_message = ""
        
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

            # Display audio device info with channel details (top left)
            fft_device_info = sd.query_devices(self.oculizer.device_idx)
            fft_device_name = fft_device_info['name']
            
            if self.dual_stream and self.oculizer.scene_prediction_device:
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
            if self.dual_stream:
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
            
            # Display scene compatibility info if using fallback
            if hasattr(self.scene_manager, 'scene_compatibility'):
                is_compatible = self.scene_manager.scene_compatibility.get(current_scene_name, True)
                if not is_compatible:
                    fallback_info = f"  ⚠️  Incompatible scene (using fallback)"
                    self.stdscr.addstr(scene_row + 1, 0, fallback_info[:width-1], curses.color_pair(COLOR_PAIRS['warning']))
                    scene_row += 1
            
            # Display prediction info
            pred_row = scene_row + 1
            if self.oculizer.latest_prediction is not None:
                pred_info = f"Latest prediction: {self.oculizer.latest_prediction}"
                self.stdscr.addstr(pred_row, 0, pred_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))
            
            if self.oculizer.current_predicted_scene is not None:
                mode_info = f"Prediction mode: {self.oculizer.current_predicted_scene}"
                self.stdscr.addstr(pred_row + 1, 0, mode_info[:width-1], curses.color_pair(COLOR_PAIRS['info']))
            
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
        default_profile = 'garage2025'
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
    parser.add_argument('--prediction-device', type=str, default=default_prediction_device,
                      help=f'Device for scene prediction in dual-stream mode (default: {default_prediction_device}). Can be a device name (cable_output, scarlett, etc.) or device index number.')
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
    parser.add_argument('--list-devices', action='store_true',
                      help='List available audio devices and exit')
    return parser.parse_args()

def main(stdscr, profile, input_device, dual_stream, prediction_device, predictor_version, average_dual_channels, scene_cache_size, prediction_channels):
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
        prediction_channels=prediction_channels
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
        # Determine if dual-stream mode should be used
        # If user explicitly specifies a prediction device, use dual-stream mode
        # Otherwise, use the OS default (single-stream on macOS)
        dual_stream = not args.single_stream
        
        # Convert prediction_device to int if it's a numeric string
        prediction_device = args.prediction_device
        
        # Override single-stream default if user explicitly specifies a prediction device
        # that differs from the input device
        if not dual_stream and prediction_device and prediction_device != args.input_device:
            dual_stream = True
            logging.info(f"Enabling dual-stream mode (prediction device '{prediction_device}' differs from input device '{args.input_device}')")
        
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
            args.prediction_channels
        ))