import os
import json
import threading
import curses
import time
from collections import OrderedDict

from oculizer.light import Oculizer
from oculizer.scenes import SceneManager

def sort_scenes_alphabetically(scenes):
    return OrderedDict(sorted(scenes.items()))

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_GREEN, -1)  # Active scene
    curses.init_pair(2, curses.COLOR_YELLOW, -1)  # Selected (but not activated) scene
    curses.init_pair(3, curses.COLOR_WHITE, -1)  # Normal scene
    curses.init_pair(4, curses.COLOR_CYAN, -1)  # Info text
    curses.init_pair(5, curses.COLOR_MAGENTA, -1)  # Instructions

def main(stdscr):
    # Initialize scene manager and light controller
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('party')  # Set an initial scene
    light_controller = Oculizer('garage', scene_manager)
    light_controller.start()

    # Sort scenes alphabetically
    scene_manager.scenes = sort_scenes_alphabetically(scene_manager.scenes)

    # Enable mouse events and keyboard input
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    stdscr.keypad(1)  # Enable keypad mode for arrow keys
    stdscr.nodelay(1)  # Non-blocking input
    init_colors()

    # Initialize navigation variables
    scroll_position = 0  # Current scroll position
    selected_index = 0  # Currently selected (but not activated) scene index
    current_scene_name = scene_manager.current_scene['name']

    while True:
        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()
        visible_range = max_y - 5  # Reserve space for header and footer
        total_scenes = len(scene_manager.scenes)
        scene_list = list(scene_manager.scenes.items())

        # Display header
        stdscr.addstr(0, 0, f"Current scene: {current_scene_name}", curses.color_pair(4))
        stdscr.addstr(1, 0, "Available scenes:", curses.color_pair(4))

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
                color = curses.color_pair(1) | curses.A_BOLD  # Green and bold for active scene
            elif i + scroll_position == selected_index:
                color = curses.color_pair(2) | curses.A_BOLD  # Yellow and bold for selected scene
            else:
                color = curses.color_pair(3)  # White for other scenes

            stdscr.addstr(display_y, 0, scene_str, color)

        # Display scroll information and instructions
        if total_scenes > visible_range:
            stdscr.addstr(max_y-2, 0, f"Scroll: {scroll_position+1}-{min(scroll_position+visible_range, total_scenes)}/{total_scenes}")
        stdscr.addstr(max_y-1, 0, "Press 'q' to quit, 'r' to reload, Up/Down/Mouse to navigate, Enter to activate", curses.color_pair(5))

        stdscr.refresh()

        # Handle input
        try:
            event = stdscr.getch()
            if event == ord('q'):
                light_controller.stop()
                light_controller.join()
                break
            elif event == ord('r'):
                scene_manager.reload_scenes()
                scene_manager.scenes = sort_scenes_alphabetically(scene_manager.scenes)
                light_controller.change_scene(current_scene_name)
                scene_list = list(scene_manager.scenes.items())
                total_scenes = len(scene_list)
                stdscr.addstr(max_y-1, 0, "Scenes reloaded.")
                stdscr.refresh()
                time.sleep(1)
            elif event == curses.KEY_UP and selected_index > 0:
                selected_index -= 1
                if selected_index < scroll_position:
                    scroll_position = selected_index
            elif event == curses.KEY_DOWN and selected_index < total_scenes - 1:
                selected_index += 1
                if selected_index >= scroll_position + visible_range:
                    scroll_position = selected_index - visible_range + 1
            elif event == curses.KEY_MOUSE:
                _, _, y, _, bstate = curses.getmouse()
                if y >= 3 and y < min(3 + visible_range, 3 + total_scenes):
                    new_index = scroll_position + (y - 3)
                    if new_index < total_scenes:
                        selected_index = new_index
            elif event == curses.KEY_ENTER or event == 10 or event == 13:  # Enter key
                if 0 <= selected_index < total_scenes:
                    new_scene = scene_list[selected_index][0]
                    light_controller.change_scene(new_scene)
                    current_scene_name = new_scene

        except curses.error:
            pass

        time.sleep(0.01)

    curses.endwin()

if __name__ == '__main__':
    curses.wrapper(main) 