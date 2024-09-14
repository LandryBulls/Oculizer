import os
import json
import threading
import queue
import numpy as np
import curses
import time
import mido

from oculizer.light import Oculizer
from oculizer.scenes import SceneManager

def create_midi_scene_map(scenes):
    midi_scene_map = {}
    for scene_name, scene_data in scenes.items():
        if 'midi' in scene_data:
            midi_scene_map[scene_data['midi']] = scene_name
    return midi_scene_map

def main(stdscr):
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('default')  # Set an initial scene
    light_controller = Oculizer('garage', scene_manager)

    # Create MIDI scene map from scene configurations
    midi_scene_map = create_midi_scene_map(scene_manager.scenes)

    light_controller.start()

    # Open the MIDI input port
    try:
        inport = mido.open_input()
    except IOError:
        stdscr.addstr(0, 0, "No MIDI input port found. Please connect a MIDI device and restart.")
        stdscr.refresh()
        time.sleep(5)
        return

    stdscr.nodelay(1)  # Make getch non-blocking

    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, f"Current scene: {scene_manager.current_scene['name']}")
        stdscr.addstr(1, 0, "Available scenes:")
        for i, (scene, data) in enumerate(scene_manager.scenes.items()):
            midi_note = data.get('midi', 'N/A')
            stdscr.addstr(i+2, 0, f"{scene} | MIDI Note: {midi_note} | Key: {data.get('key_command', 'N/A')}")

        stdscr.addstr(len(scene_manager.scenes)+3, 0, "Press 'q' to quit. Press 'r' to reload scenes.")
        stdscr.refresh()

        # Check for MIDI input
        for msg in inport.iter_pending():
            if msg.type == 'note_on':
                if msg.note in midi_scene_map:
                    try:
                        light_controller.change_scene(midi_scene_map[msg.note])
                    except Exception as e:
                        stdscr.addstr(len(scene_manager.scenes)+2, 0, f"Error changing scene: {str(e)}")

        # Check for keyboard input
        key = stdscr.getch()
        if key == ord('q'):
            light_controller.stop()
            light_controller.join()
            break
        elif key == ord('r'):
            scene_manager.reload_scenes()
            midi_scene_map = create_midi_scene_map(scene_manager.scenes)  # Recreate MIDI map
            light_controller.change_scene(scene_manager.current_scene['name'])
            stdscr.addstr(len(scene_manager.scenes)+2, 0, "Scenes reloaded.")
            stdscr.refresh()
            time.sleep(1)
        elif key != -1:  # -1 is returned if no key is pressed
            key_char = chr(key) if 0 <= key <= 255 else None
            if key_char in [scene['key_command'] for scene in scene_manager.scenes.values() if 'key_command' in scene]:
                for scene, data in scene_manager.scenes.items():
                    if data.get('key_command') == key_char:
                        light_controller.change_scene(scene)
                        break

        time.sleep(0.01)  # Short sleep to prevent CPU hogging

    curses.endwin()

if __name__ == '__main__':
    curses.wrapper(main)