"""
SceneManager - Scene configuration loader and manager for Oculizer lighting system.

This module provides the SceneManager class which handles loading, managing, and 
switching between lighting scene configurations stored as JSON files. Each scene 
defines specific lighting parameters and behaviors that can be applied to the 
lighting system.

The SceneManager:
- Loads all scene JSON files from a specified directory
- Validates scene data and provides error handling for malformed files
- Maintains the current active scene
- Supports runtime scene switching and reloading
"""
import os
import json
import logging

class SceneManager:
    def __init__(self, scenes_directory):
        # two dirs up from the current file
        scenes_directory = os.path.join(os.path.dirname(__file__), '..', '..', scenes_directory)
        self.scenes = self.load_json_files(scenes_directory)
        if not self.scenes:
            raise ValueError("No valid scenes found in directory")
        # Default to 'party' scene if available, otherwise use first available scene
        if 'party' in self.scenes:
            self.current_scene = self.scenes['party']
            logging.info("Error - Defaulting to 'party' scene")
        else:
            self.current_scene = self.scenes[list(self.scenes.keys())[0]]
            logging.warning("'party' scene not found, defaulting to '%s'", list(self.scenes.keys())[0])

    def load_json_files(self, directory):
        data = {}
        errors = []
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                filepath = os.path.join(directory, filename)
                try:
                    with open(filepath, 'r') as file:
                        scene_data = json.load(file)
                        data[filename[:-5]] = scene_data
                except json.JSONDecodeError as e:
                    error_msg = f"Error loading scene '{filename}': {str(e)}"
                    errors.append(error_msg)
                    logging.error(error_msg)
                except Exception as e:
                    error_msg = f"Unexpected error loading scene '{filename}': {str(e)}"
                    errors.append(error_msg)
                    logging.error(error_msg)
        
        if errors:
            raise ValueError("\n".join(errors))
        return data

    def set_scene(self, scene_name):
        if scene_name in self.scenes:
            self.current_scene = self.scenes[scene_name]
        else:
            raise ValueError(f"Scene '{scene_name}' not found")

    def reload_scenes(self):
        """Reload all scenes from disk, preserving current scene if possible"""
        current_scene_name = self.current_scene['name']
        self.scenes = self.load_json_files('scenes')
        # Try to restore the previous scene, fall back to 'party' or first scene if not found
        if current_scene_name in self.scenes:
            self.current_scene = self.scenes[current_scene_name]
        elif 'party' in self.scenes:
            self.current_scene = self.scenes['party']
            logging.warning("Previous scene '%s' not found, defaulting to 'party'", current_scene_name)
        else:
            self.current_scene = self.scenes[list(self.scenes.keys())[0]]
            logging.warning("Previous scene '%s' and 'party' not found, defaulting to '%s'", 
                          current_scene_name, list(self.scenes.keys())[0])

def main():
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('testing')
    print(scene_manager.current_scene)

if __name__ == '__main__':
    main()