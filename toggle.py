import os
import json
import threading
import curses
import time
import argparse
import platform
from collections import OrderedDict
import math

from oculizer.light import Oculizer
from oculizer.scenes import SceneManager

def parse_args():
    # Detect OS and set defaults
    is_macos = platform.system() == 'Darwin'
    
    # macOS defaults (match oculize.py defaults)
    if is_macos:
        default_input = 'scarlett'
        default_profile = 'mobile'
    else:
        # Windows/Linux defaults
        default_input = 'scarlett'
        default_profile = 'bbgv'
    
    parser = argparse.ArgumentParser(description='Interactive scene toggler for Oculizer')
    parser.add_argument('-p', '--profile', type=str, default=default_profile,
                      help=f'Profile to use (default: {default_profile})')
    parser.add_argument('-i', '--input', type=str, default=default_input,
                      help=f'Audio input device to use (default: {default_input}, options: cable, blackhole, scarlett)')
    parser.add_argument('--average-dual-channels', action='store_true',
                      help='Average first two input channels together for FFT (useful for Scarlett 18i20)')
    return parser.parse_args()

def sort_scenes_alphabetically(scenes):
    return OrderedDict(sorted(scenes.items()))

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    # Active scene: White text on green background
    curses.init_pair(1, curses.COLOR_WHITE, curses.COLOR_GREEN)
    # Selected scene: Black text on yellow background
    curses.init_pair(2, curses.COLOR_BLACK, curses.COLOR_YELLOW)
    # Hover scene: White text on blue background
    curses.init_pair(3, curses.COLOR_WHITE, curses.COLOR_BLUE)
    # Normal scene: White text on default background
    curses.init_pair(4, curses.COLOR_WHITE, -1)
    # Info text: Cyan text on default background
    curses.init_pair(5, curses.COLOR_CYAN, -1)
    # Instructions: Magenta text on default background
    curses.init_pair(6, curses.COLOR_MAGENTA, -1)
    # Search text: Yellow text on default background
    curses.init_pair(7, curses.COLOR_YELLOW, -1)

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

def main(stdscr, profile, input_device, average_dual_channels):
    # Load profile fixtures for scene manager
    from pathlib import Path
    profile_fixtures = set()
    try:
        profile_path = Path(__file__).resolve().parent / 'profiles' / f'{profile}.json'
        if profile_path.exists():
            with open(profile_path, 'r') as f:
                profile_data = json.load(f)
                if 'lights' in profile_data:
                    profile_fixtures = {light['name'] for light in profile_data['lights'] if 'name' in light}
    except Exception as e:
        pass  # Fall back to no profile awareness
    
    # Initialize scene manager with profile awareness
    scene_manager = SceneManager('scenes', profile_name=profile, available_fixtures=profile_fixtures)
    scene_manager.set_scene('party')  # Set an initial scene
    light_controller = Oculizer(profile, scene_manager, input_device, 
                               average_dual_channels=average_dual_channels)
    light_controller.start()

    # Sort scenes alphabetically
    scene_manager.scenes = sort_scenes_alphabetically(scene_manager.scenes)

    # Enable mouse events and keyboard input
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    print('\033[?1003h')  # Enable mouse movement tracking
    stdscr.keypad(1)
    stdscr.nodelay(1)
    init_colors()

    # Initialize variables
    selected_index = 0
    current_scene_name = scene_manager.current_scene['name']
    search_string = ""
    last_search_time = time.time()
    hover_pos = (-1, -1)

    try:
        while True:
            stdscr.clear()
            max_y, max_x = stdscr.getmaxyx()
            scene_list = list(scene_manager.scenes.items())
            total_scenes = len(scene_list)

            # Calculate grid layout
            num_rows, num_columns, column_width = calculate_grid_dimensions(scene_list, max_x, max_y - 5)

            # Display header
            header_text = f"Current scene: {current_scene_name} (Profile: {profile})"
            commands_text = "Commands: [^Q] Quit  [^R] Reload"
            if search_string:
                header_text += f" [Search: {search_string}]"
            
            padding = max(1, max_x - len(header_text) - len(commands_text))
            stdscr.addstr(0, 0, header_text, curses.color_pair(5))
            stdscr.addstr(0, len(header_text) + padding, commands_text, curses.color_pair(6))
            stdscr.addstr(1, 0, "Available scenes:", curses.color_pair(5))

            # Display scenes in grid
            for i, (scene, _) in enumerate(scene_list):
                row, col = get_grid_position(i, num_columns)
                if row >= num_rows or row >= max_y - 5:  # Account for header and footer
                    break

                display_y = row + 3  # Start after header
                display_x = col * column_width

                scene_str = scene
                if len(scene_str) > column_width - 2:
                    scene_str = scene_str[:column_width - 5] + "..."

                # Determine scene display style
                if scene == current_scene_name:
                    color = curses.color_pair(1)
                elif i == selected_index:
                    color = curses.color_pair(2)
                elif (row, col) == hover_pos:
                    color = curses.color_pair(3)
                else:
                    color = curses.color_pair(4)

                # Pad scene name to column width
                scene_str = scene_str.ljust(column_width - 1)
                stdscr.addstr(display_y, display_x, scene_str, color)

            # Display instructions
            instructions = "Ctrl+Q to quit, Ctrl+R to reload, type to search, Arrow keys to navigate, Enter to activate"
            stdscr.addstr(max_y-1, 0, instructions, curses.color_pair(6))

            stdscr.refresh()

            try:
                event = stdscr.getch()
                current_time = time.time()

                if search_string and current_time - last_search_time > 1.0:
                    search_string = ""

                if event == 17:  # Ctrl+Q
                    break
                elif event == 18:  # Ctrl+R
                    try:
                        scene_manager.reload_scenes()
                        scene_manager.scenes = sort_scenes_alphabetically(scene_manager.scenes)
                        light_controller.change_scene(current_scene_name)
                        scene_list = list(scene_manager.scenes.items())
                        total_scenes = len(scene_list)
                        stdscr.addstr(max_y-1, 0, "Scenes reloaded successfully.", curses.color_pair(5))
                    except Exception as e:
                        stdscr.addstr(max_y-1, 0, f"Error reloading scenes: {str(e)}", curses.color_pair(1))
                    stdscr.refresh()
                    time.sleep(2)
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
                    if my >= 3 and my < min(3 + num_rows, max_y - 1):
                        row = my - 3
                        col = mx // column_width
                        hover_pos = (row, col)
                        
                        if bstate & curses.BUTTON1_CLICKED:
                            new_index = get_index_from_position(row, col, num_columns, total_scenes)
                            if 0 <= new_index < total_scenes:
                                selected_index = new_index
                                search_string = ""
                elif event in [curses.KEY_ENTER, 10, 13]:  # Enter key
                    if 0 <= selected_index < total_scenes:
                        new_scene = scene_list[selected_index][0]
                        light_controller.change_scene(new_scene)
                        current_scene_name = new_scene
                        search_string = ""
                elif event == 27:  # ESC key
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
        print('\033[?1003l')
        light_controller.stop()
        light_controller.join()
        curses.endwin()

if __name__ == '__main__':
    args = parse_args()
    curses.wrapper(lambda stdscr: main(stdscr, args.profile, args.input.lower(), args.average_dual_channels)) 