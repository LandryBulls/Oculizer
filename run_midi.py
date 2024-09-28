import os
import json
import threading
import queue
import numpy as np
import curses
import time
import mido
from collections import OrderedDict

from oculizer.light import Oculizer
from oculizer.scenes import SceneManager

def create_midi_scene_map(scenes):
    midi_scene_map = {}
    for scene_name, scene_data in scenes.items():
        if 'midi' in scene_data:
            midi_scene_map[scene_data['midi']] = scene_name
    return midi_scene_map

def sort_scenes_by_midi(scenes):
    scene_list = [(data.get('midi', float('inf')), name, data) for name, data in scenes.items()]
    sorted_scenes = sorted(scene_list, key=lambda x: x[0])
    return OrderedDict((name, data) for _, name, data in sorted_scenes)

def init_colors():
    curses.start_color()
    curses.use_default_colors()
    curses.init_pair(1, curses.COLOR_RED, -1)
    curses.init_pair(2, curses.COLOR_GREEN, -1)
    curses.init_pair(3, curses.COLOR_YELLOW, -1)
    curses.init_pair(4, curses.COLOR_BLUE, -1)
    curses.init_pair(5, curses.COLOR_MAGENTA, -1)
    curses.init_pair(6, curses.COLOR_CYAN, -1)
    curses.init_pair(7, curses.COLOR_WHITE, -1)
    curses.init_pair(8, curses.COLOR_BLACK, curses.COLOR_WHITE)  # For highlighting

def main(stdscr):
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('party')  # Set an initial scene
    light_controller = Oculizer('garage', scene_manager)

    scene_manager.scenes = sort_scenes_by_midi(scene_manager.scenes)
    midi_scene_map = create_midi_scene_map(scene_manager.scenes)

    light_controller.start()

    try:
        inport = mido.open_input()
    except IOError:
        stdscr.addstr(0, 0, "No MIDI input port found. Please connect a MIDI device and restart.")
        stdscr.refresh()
        time.sleep(5)
        return

    stdscr.nodelay(1)
    init_colors()

    scroll_position = 0
    max_y, max_x = stdscr.getmaxyx()

    while True:
        stdscr.clear()
        max_y, max_x = stdscr.getmaxyx()

        stdscr.addstr(0, 0, f"Current scene: {scene_manager.current_scene['name']}", curses.color_pair(4))
        stdscr.addstr(1, 0, "Available scenes (sorted by MIDI):")

        visible_range = max_y - 5
        total_scenes = len(scene_manager.scenes)
        
        for i, (scene, data) in enumerate(list(scene_manager.scenes.items())[scroll_position:scroll_position+visible_range]):
            if i >= visible_range:
                break
            midi_note = data.get('midi', 'N/A')
            scene_str = f"{scene} | MIDI Note: {midi_note}"
            if len(scene_str) > max_x:
                scene_str = scene_str[:max_x-3] + "..."
            
            if scene == scene_manager.current_scene['name']:
                stdscr.attron(curses.color_pair(8) | curses.A_BOLD)
                stdscr.addstr(i+3, 0, scene_str)
                stdscr.attroff(curses.color_pair(8) | curses.A_BOLD)
            else:
                stdscr.addstr(i+3, 0, scene_str, curses.color_pair(2))

        if total_scenes > visible_range:
            stdscr.addstr(max_y-2, 0, f"Scroll: {scroll_position+1}-{min(scroll_position+visible_range, total_scenes)}/{total_scenes}")
        stdscr.addstr(max_y-1, 0, "Press 'q' to quit. 'r' to reload. Up/Down to scroll.", curses.color_pair(5))
        
        stdscr.refresh()

        for msg in inport.iter_pending():
            if msg.type == 'note_on':
                if msg.note in midi_scene_map:
                    try:
                        light_controller.change_scene(midi_scene_map[msg.note])
                    except Exception as e:
                        stdscr.addstr(max_y-1, 0, f"Error changing scene: {str(e)}")

        key = stdscr.getch()
        if key == ord('q'):
            light_controller.stop()
            light_controller.join()
            break
        elif key == ord('r'):
            scene_manager.reload_scenes()
            scene_manager.scenes = sort_scenes_by_midi(scene_manager.scenes)
            midi_scene_map = create_midi_scene_map(scene_manager.scenes)
            light_controller.change_scene(scene_manager.current_scene['name'])
            stdscr.addstr(max_y-1, 0, "Scenes reloaded.")
            stdscr.refresh()
            time.sleep(1)
        elif key == curses.KEY_UP and scroll_position > 0:
            scroll_position -= 1
        elif key == curses.KEY_DOWN and scroll_position < total_scenes - visible_range:
            scroll_position += 1
        elif key != -1:
            key_char = chr(key) if 0 <= key <= 255 else None
            if key_char in [scene['key_command'] for scene in scene_manager.scenes.values() if 'key_command' in scene]:
                for scene, data in scene_manager.scenes.items():
                    if data.get('key_command') == key_char:
                        light_controller.change_scene(scene)
                        break

        time.sleep(0.01)

    curses.endwin()

if __name__ == '__main__':
    curses.wrapper(main)