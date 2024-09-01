import curses
from oculizer.light import AudioLightController, load_controller, load_json, load_profile
from oculizer.scenes import SceneManager

stdscr = curses.initscr()

def main():
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('hell')

    audio_light_controller = AudioLightController('testing', scene_manager)

    scene_commands = {ord(scene_manager.scenes[scene]['key_command']): scene for scene in scene_manager.scenes}

    audio_light_controller.start()

    while True:
        stdscr.clear()
        stdscr.addstr(0, 0, f"Current scene: {scene_manager.current_scene['name']}")
        stdscr.addstr(1, 0, "Available scenes:")
        for i, scene in enumerate(scene_manager.scenes):
            stdscr.addstr(i+2, 0, f"{scene} | Commands: {scene_manager.scenes[scene]['key_command']}")
        
        errors = audio_light_controller.get_errors()
        if errors:
            for i, error in enumerate(errors):
                max_error_length = curses.COLS - 1  # Maximum length of error message
                error_message = f"Error: {error}"
                truncated_error = error_message[:max_error_length]
                stdscr.addstr(i+len(scene_manager.scenes)+3, 0, truncated_error)
        
        stdscr.refresh()

        key = stdscr.getch()
        if key == ord('q'):
            break
        elif key in scene_commands:
            try:
                audio_light_controller.change_scene(scene_commands[key])
                stdscr.addstr(len(scene_manager.scenes)+3, 0, f"Changed to scene: {scene_commands[key]}")
            except Exception as e:
                stdscr.addstr(len(scene_manager.scenes)+2, 0, f"Error changing scene: {str(e)}")
        elif key == ord('r'):
            scene_manager.reload_scenes()
            audio_light_controller.change_scene(scene_manager.current_scene['name'])
            stdscr.addstr(len(scene_manager.scenes) + 4, 0, "Scenes reloaded")
        
        stdscr.refresh()

    audio_light_controller.stop()
    audio_light_controller.join()
    curses.endwin()

if __name__ == '__main__':
    main()
