import os
import json
import threading
import curses
import time
import argparse
from collections import OrderedDict

from oculizer.light import Oculizer
from oculizer.scenes import SceneManager

def parse_args():
    parser = argparse.ArgumentParser(description='Interactive scene toggler for Oculizer')
    parser.add_argument('-p', '--profile', type=str, default='rockville',
                      help='Profile to use (default: rockville)')
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

def main(stdscr, profile):
    # Initialize scene manager and light controller
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('party')  # Set an initial scene
    light_controller = Oculizer(profile, scene_manager)
    light_controller.start()

    # Sort scenes alphabetically
    scene_manager.scenes = sort_scenes_alphabetically(scene_manager.scenes)

    # Enable mouse events and keyboard input with extended mouse tracking
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    print('\033[?1003h')  # Enable mouse movement tracking
    stdscr.keypad(1)  # Enable keypad mode for arrow keys
    stdscr.nodelay(1)  # Non-blocking input
    init_colors()

    # Initialize navigation variables
    scroll_position = 0  # Current scroll position
    selected_index = 0  # Currently selected (but not activated) scene index
    current_scene_name = scene_manager.current_scene['name']
    hover_y = -1  # Track mouse hover position
    search_string = ""  # Track current search string
    last_search_time = time.time()  # Track when the last search character was entered

    try:
        while True:
            stdscr.clear()
            max_y, max_x = stdscr.getmaxyx()
            visible_range = max_y - 5  # Reserve space for header and footer
            total_scenes = len(scene_manager.scenes)
            scene_list = list(scene_manager.scenes.items())

            # Display header
            header_text = f"Current scene: {current_scene_name} (Profile: {profile})"
            commands_text = "Commands: [^Q] Quit  [^R] Reload"
            if search_string:
                header_text += f" [Search: {search_string}]"
            
            # Calculate padding to right-align commands
            padding = max(1, max_x - len(header_text) - len(commands_text))
            
            # Display header line with right-aligned commands
            stdscr.addstr(0, 0, header_text, curses.color_pair(5))
            stdscr.addstr(0, len(header_text) + padding, commands_text, curses.color_pair(6))
            
            stdscr.addstr(1, 0, "Available scenes:", curses.color_pair(5))

            # Display scenes
            for i, (scene, _) in enumerate(scene_list[scroll_position:scroll_position+visible_range]):
                if i >= visible_range:
                    break
                
                display_y = i + 3
                scene_str = scene
                if len(scene_str) > max_x:
                    scene_str = scene_str[:max_x-3] + "..."

                # Determine scene display style
                if scene == current_scene_name:
                    color = curses.color_pair(1)  # White on green for active scene
                elif i + scroll_position == selected_index:
                    color = curses.color_pair(2)  # Black on yellow for selected scene
                elif display_y == hover_y:
                    color = curses.color_pair(3)  # White on blue for hover
                else:
                    color = curses.color_pair(4)  # White on default for other scenes

                # Pad the scene name with spaces to fill the line for full-width highlighting
                scene_str = scene_str.ljust(max_x)

                stdscr.addstr(display_y, 0, scene_str, color)

            # Display scroll information and instructions
            if total_scenes > visible_range:
                stdscr.addstr(max_y-2, 0, f"Scroll: {scroll_position+1}-{min(scroll_position+visible_range, total_scenes)}/{total_scenes}")
            stdscr.addstr(max_y-1, 0, "Ctrl+Q to quit, Ctrl+R to reload, type to search, Up/Down/Mouse to navigate, Enter to activate", curses.color_pair(6))

            stdscr.refresh()

            # Handle input
            try:
                event = stdscr.getch()
                current_time = time.time()

                # Reset search string if more than 1 second has passed since last character
                if search_string and current_time - last_search_time > 1.0:
                    search_string = ""

                # Check for Ctrl+Q (17 is Ctrl+Q in ASCII)
                if event == 17:  # Ctrl+Q
                    break
                # Check for Ctrl+R (18 is Ctrl+R in ASCII)
                elif event == 18:  # Ctrl+R
                    try:
                        scene_manager.reload_scenes()
                        scene_manager.scenes = sort_scenes_alphabetically(scene_manager.scenes)
                        light_controller.change_scene(current_scene_name)
                        scene_list = list(scene_manager.scenes.items())
                        total_scenes = len(scene_list)
                        stdscr.addstr(max_y-1, 0, "Scenes reloaded successfully.", curses.color_pair(5))
                    except ValueError as e:
                        # Split error message into lines if it's too long
                        error_lines = str(e).split('\n')
                        for i, line in enumerate(error_lines[:3]):  # Show up to 3 lines of errors
                            if i == 2 and len(error_lines) > 3:
                                line += f" (and {len(error_lines)-3} more errors)"
                            stdscr.addstr(max_y-3+i, 0, line.ljust(max_x), curses.color_pair(1))
                    except Exception as e:
                        stdscr.addstr(max_y-1, 0, f"Error reloading scenes: {str(e)}", curses.color_pair(1))
                    stdscr.refresh()
                    time.sleep(2)  # Give more time to read errors
                elif event == curses.KEY_UP and selected_index > 0:
                    selected_index -= 1
                    if selected_index < scroll_position:
                        scroll_position = selected_index
                    search_string = ""  # Clear search when using arrow keys
                elif event == curses.KEY_DOWN and selected_index < total_scenes - 1:
                    selected_index += 1
                    if selected_index >= scroll_position + visible_range:
                        scroll_position = selected_index - visible_range + 1
                    search_string = ""  # Clear search when using arrow keys
                elif event == curses.KEY_MOUSE:
                    _, mx, my, _, bstate = curses.getmouse()
                    if my >= 3 and my < min(3 + visible_range, 3 + total_scenes):
                        hover_y = my
                        if bstate & curses.BUTTON1_CLICKED:  # Left click
                            new_index = scroll_position + (my - 3)
                            if new_index < total_scenes:
                                selected_index = new_index
                                search_string = ""  # Clear search when clicking
                elif event == curses.KEY_ENTER or event == 10 or event == 13:  # Enter key
                    if 0 <= selected_index < total_scenes:
                        new_scene = scene_list[selected_index][0]
                        light_controller.change_scene(new_scene)
                        current_scene_name = new_scene
                        search_string = ""  # Clear search when activating scene
                elif event == 27:  # ESC key
                    search_string = ""  # Clear search string
                elif event == curses.KEY_BACKSPACE or event == 127 or event == 8:  # Backspace
                    search_string = search_string[:-1]
                    last_search_time = current_time
                    new_index = find_scene_by_prefix(scene_list, search_string)
                    if new_index != -1:
                        selected_index = new_index
                        # Adjust scroll position if necessary
                        if selected_index < scroll_position:
                            scroll_position = selected_index
                        elif selected_index >= scroll_position + visible_range:
                            scroll_position = selected_index - visible_range + 1
                elif 32 <= event <= 126:  # Printable characters
                    search_string += chr(event)
                    last_search_time = current_time
                    new_index = find_scene_by_prefix(scene_list, search_string)
                    if new_index != -1:
                        selected_index = new_index
                        # Adjust scroll position if necessary
                        if selected_index < scroll_position:
                            scroll_position = selected_index
                        elif selected_index >= scroll_position + visible_range:
                            scroll_position = selected_index - visible_range + 1

            except curses.error:
                pass

            time.sleep(0.01)

    finally:
        # Clean up mouse tracking
        print('\033[?1003l')
        # Clean up light controller
        light_controller.stop()
        light_controller.join()
        curses.endwin()

if __name__ == '__main__':
    args = parse_args()
    curses.wrapper(lambda stdscr: main(stdscr, args.profile)) 