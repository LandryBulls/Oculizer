"""
interface.py

Description: This script provides a command line interface for toggling light mappings and controlling the Spotify API.

Author: Landry Bulls
Date: 8/20/24
"""

import curses
import keyboard
from audio_listener import AudioListener
from control import LightController, SceneManager
import time

oculizer_title = """
      ___           ___           ___           ___                   ___           ___           ___     
     /\  \         /\  \         /\__\         /\__\      ___        /\  \         /\  \         /\  \    
    /::\  \       /::\  \       /:/  /        /:/  /     /\  \       \:\  \       /::\  \       /::\  \   
   /:/\:\  \     /:/\:\  \     /:/  /        /:/  /      \:\  \       \:\  \     /:/\:\  \     /:/\:\  \  
  /:/  \:\  \   /:/  \:\  \   /:/  /  ___   /:/  /       /::\__\       \:\  \   /::\~\:\  \   /::\~\:\  \ 
 /:/__/ \:\__\ /:/__/ \:\__\ /:/__/  /\__\ /:/__/     __/:/\/__/ _______\:\__\ /:/\:\ \:\__\ /:/\:\ \:\__\ 
 \:\  \ /:/  / \:\  \  \/__/ \:\  \ /:/  / \:\  \    /\/:/  /    \::::::::/__/ \:\~\:\ \/__/ \/_|::\/:/  /
  \:\  /:/  /   \:\  \        \:\  /:/  /   \:\  \   \::/__/      \:\~~\~~      \:\ \:\__\      |:|::/  / 
   \:\/:/  /     \:\  \        \:\/:/  /     \:\  \   \:\__\       \:\  \        \:\ \/__/      |:|\/__/  
    \::/  /       \:\__\        \::/  /       \:\__\   \/__/        \:\__\        \:\__\        |:|  |    
     \/__/         \/__/         \/__/         \/__/                 \/__/         \/__/         \|__|    
"""

def main(stdscr):
    scene_manager = SceneManager('scenes_directory', 'profiles_directory')
    audio_listener = AudioListener()
    dmx_controller = Controller()
    light_controller = LightController(audio_listener, dmx_controller, scene_manager)

    audio_listener.start()
    light_controller.start()

    scenes = list(scene_manager.scenes.keys())
    current_scene_index = 0

    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, oculizer_title)
        stdscr.addstr(1, 0, f"Current scene: {scenes[current_scene_index]}")
        stdscr.addstr(2, 0, "Press 'n' for next scene, 'p' for previous scene, 'q' to quit")
        stdscr.refresh()

        key = stdscr.getch()
        if key == ord('n'):
            current_scene_index = (current_scene_index + 1) % len(scenes)
            scene_manager.set_scene(scenes[current_scene_index])
        elif key == ord('p'):
            current_scene_index = (current_scene_index - 1) % len(scenes)
            scene_manager.set_scene(scenes[current_scene_index])
        elif key == ord('q'):
            break

    audio_listener.stop()
    light_controller.stop()
    audio_listener.join()
    light_controller.join()

if __name__ == "__main__":
    curses.wrapper(main)


