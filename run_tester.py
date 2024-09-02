"""
For testing the functionality of the program.
"""

import os
import json
import threading
import queue
import numpy as np
import curses

#from control import load_json, load_profile, load_controller, LightController
from oculizer.light import load_controller, load_json, load_profile, Oculizer
from oculizer.audio import AudioListener
from oculizer.scenes import SceneManager

stdscr = curses.initscr()

def main():
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('hell')
    light_controller = Oculizer('testing', scene_manager)

    scene_commands = {ord(scene_manager.scenes[scene]['key_command']): scene for scene in scene_manager.scenes}

    light_controller.start()

    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, f"Current scene: {scene_manager.current_scene['name']}")
        stdscr.addstr(1, 0, "Available scenes:")
        for i, scene in enumerate(scene_manager.scenes):
            stdscr.addstr(i+2, 0, f"{scene} | Commands: {scene_manager.scenes[scene]['key_command']}")
        
        # Print any errors from the audio listener
        errors = light_controller.get_errors()
        if errors:
            for i, error in enumerate(errors):
                stdscr.addstr(i+len(scene_manager.scenes)+3, 0, f"Error: {error}")
        
        stdscr.refresh()

        key = stdscr.getch()
        if key == ord('q'):
            light_controller.stop()
            light_controller.join()
            break
        elif key in scene_commands:
            try:
                light_controller.change_scene(scene_commands[key])
                stdscr.addstr(len(scene_manager.scenes)+3, 0, f"Changed to scene: {scene_commands[key]}")
            except Exception as e:
                stdscr.addstr(len(scene_manager.scenes)+2, 0, f"Error changing scene: {str(e)}")
        elif key == ord('r'):
            scene_manager.reload_scenes()
            light_controller.change_scene(scene_manager.current_scene['name'])  # Reapply current scene
            stdscr.addstr(len(scene_manager.scenes) + 4, 0, "Scenes reloaded")
        
        stdscr.refresh()

    curses.endwin()

if __name__ == '__main__':
    main()
