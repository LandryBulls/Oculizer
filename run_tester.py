"""
For testing the light controller and audio listener in a curses environment.
"""


"""
For testing the light controller and audio listener in a curses environment.
"""

import os
import json
import threading
import queue
import numpy as np
import curses
import signal
import logging
import traceback

from oculizer.light import LightController, load_controller, load_json, load_profile
from oculizer.audio import AudioListener
from oculizer.scenes import SceneManager

logging.basicConfig(filename='oculizer_debug.log', level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def signal_handler(sig, frame):
    curses.endwin()
    os._exit(0)

def main(stdscr):
    signal.signal(signal.SIGINT, signal_handler)
    audio_listener = None
    light_controller = None

    try:
        logger.debug("Initializing curses")
        stdscr.clear()
        stdscr.refresh()
        stdscr.nodelay(1)

        logger.debug("Creating AudioListener")
        audio_listener = AudioListener()

        logger.debug("Creating SceneManager")
        scene_manager = SceneManager('scenes')
        logger.debug("Setting initial scene to 'hell'")
        scene_manager.set_scene('hell')

        logger.debug("Loading profile")
        profile = load_profile('testing')

        logger.debug("Creating LightController")
        try:
            light_controller = LightController(audio_listener, profile, scene_manager)
        except Exception as e:
            logger.error(f"Failed to create LightController: {str(e)}")
            raise

        scene_commands = {ord(scene_manager.scenes[scene]['key_command']): scene for scene in scene_manager.scenes}

        logger.debug("Starting audio listener")
        audio_listener.start()
        logger.debug("Starting light controller")
        light_controller.start()

        logger.debug("Entering main loop")
        while True:
            try:
                stdscr.clear()
                height, width = stdscr.getmaxyx()

                stdscr.addstr(0, 0, f"Current scene: {scene_manager.current_scene['name']}"[:width-1])
                
                stdscr.addstr(1, 0, "Available scenes:"[:width-1])
                for i, scene in enumerate(scene_manager.scenes):
                    if i + 2 < height:
                        scene_info = f"{scene} | Command: {scene_manager.scenes[scene]['key_command']}"
                        stdscr.addstr(i+2, 0, scene_info[:width-1])

                queue_size = audio_listener.fft_queue.qsize()
                stdscr.addstr(height-1, 0, f"Audio queue size: {queue_size}"[:width-1])

                stdscr.refresh()

                key = stdscr.getch()
                if key == ord('q'):
                    logger.debug("Quit command received")
                    break
                elif key in scene_commands:
                    logger.debug(f"Changing scene to: {scene_commands[key]}")
                    light_controller.change_scene(scene_commands[key])
                elif key == ord('r'):
                    logger.debug("Reloading scenes")
                    scene_manager.reload_scenes()
                    light_controller.change_scene(scene_manager.current_scene['name'])

                curses.napms(100)

            except curses.error:
                logger.error(f"Curses error: {traceback.format_exc()}")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                logger.error(traceback.format_exc())
                break

    except Exception as e:
        logger.exception(f"An error occurred: {str(e)}")
    finally:
        logger.debug("Cleaning up")
        if audio_listener:
            logger.debug("Stopping audio listener")
            audio_listener.stop()
        if light_controller:
            logger.debug("Stopping light controller")
            light_controller.stop()
        if audio_listener:
            logger.debug("Joining audio listener thread")
            audio_listener.join()
        if light_controller:
            logger.debug("Joining light controller thread")
            light_controller.join()
        logger.debug("Ending curses")
        curses.endwin()
        logger.debug("Cleanup complete")

if __name__ == '__main__':
    curses.wrapper(main)