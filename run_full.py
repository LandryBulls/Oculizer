"""
For testing the functionality of the program.
"""

import os
import json
import threading
import queue
import numpy as np
import curses
import time

#from control import load_json, load_profile, load_controller, LightController
from oculizer.light import Oculizer
from oculizer.audio import AudioListener
from oculizer.scenes import SceneManager
from oculizer.spotify import Spotifizer

stdscr = curses.initscr()

try:
    credspath = os.path.join(os.path.dirname(__file__), 'spotify_credentials.txt')
    with open(credspath) as f:
        lines = f.readlines()
        client_id = lines[0].strip().split(' ')[1]
        client_secret = lines[1].strip().split(' ')[1]
        redirect_uri = lines[2].strip().split(' ')[1]

except Exception as e:
    stdscr.addstr(0, 0, f"Error reading Spotify credentials: {str(e)}", curses.color_pair(1))
    stdscr.refresh()
    time.sleep(5)
    exit()

def main():
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('hell')
    light_controller = Oculizer('garage', scene_manager)
    spotifizer = Spotifizer(client_id, client_secret, redirect_uri, update_interval=0.05, time_offset=1.0)

    scene_commands = {ord(scene_manager.scenes[scene]['key_command']): scene for scene in scene_manager.scenes}

    light_controller.start()
    spotifizer.start()

    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, f"Current scene: {scene_manager.current_scene['name']}")
        stdscr.addstr(1, 0, "Available scenes:")
        for i, scene in enumerate(scene_manager.scenes):
            stdscr.addstr(i+2, 0, f"{scene} | Commands: {scene_manager.scenes[scene]['key_command']}")
            
        # highlight the current scene
        stdscr.addstr(2+list(scene_manager.scenes.keys()).index(scene_manager.current_scene['name']), 0, f"{scene_manager.current_scene['name']}", curses.A_REVERSE)
        stdscr.addstr(len(scene_manager.scenes)+3, 0, f"Press 'q' to quit. Press 'r' to reload scenes.")
        stdscr.refresh()

        key = stdscr.getch()
        if key == ord('q'):
            light_controller.stop()
            light_controller.join()
            break
        elif key in scene_commands:
            try:
                light_controller.change_scene(scene_commands[key])
            except Exception as e:
                stdscr.addstr(len(scene_manager.scenes)+2, 0, f"Error changing scene: {str(e)}")

        elif key == ord('r'):
            scene_manager.reload_scenes()
            light_controller.change_scene(scene_manager.current_scene['name'])  # Reapply current scene
            stdscr.addstr(len(scene_manager.scenes)+2, 0, "Scenes reloaded.")
            stdscr.refresh()
            time.sleep(1)

        stdscr.refresh()
        time.sleep(0.1)

    curses.endwin()

if __name__ == '__main__':
    main()
