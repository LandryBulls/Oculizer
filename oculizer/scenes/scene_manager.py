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
- Handles profile-specific scene fallbacks for incompatible fixtures
"""
import os
import json
import logging
from typing import Set, Optional

class SceneManager:
    def __init__(self, scenes_directory, profile_name: Optional[str] = None, 
                 available_fixtures: Optional[Set[str]] = None):
        """
        Initialize SceneManager with profile awareness.
        
        Args:
            scenes_directory: Path to scenes directory
            profile_name: Name of the current profile (e.g., 'garage2025', 'mobile')
            available_fixtures: Set of fixture names available in the current profile
        """
        # two dirs up from the current file
        scenes_directory = os.path.join(os.path.dirname(__file__), '..', '..', scenes_directory)
        self.scenes_directory = scenes_directory
        self.scenes = self.load_json_files(scenes_directory)
        if not self.scenes:
            raise ValueError("No valid scenes found in directory")
        
        # Profile awareness
        self.profile_name = profile_name
        self.available_fixtures = available_fixtures or set()
        self.fallback_mappings = self._load_fallback_mappings()
        
        # Analyze scenes for compatibility
        self.scene_compatibility = self._analyze_scene_compatibility()
        
        # Log incompatible scenes
        if self.profile_name and self.available_fixtures:
            incompatible = [name for name, compat in self.scene_compatibility.items() if not compat]
            if incompatible:
                logging.info(f"Profile '{self.profile_name}' has {len(incompatible)} incompatible scenes (fallbacks will be used)")
                logging.debug(f"Incompatible scenes: {', '.join(sorted(incompatible))}")
        
        # Default to 'party' scene if available, otherwise use first available scene
        if 'party' in self.scenes:
            self.current_scene = self.scenes['party']
            logging.info("Defaulting to 'party' scene")
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

    def _load_fallback_mappings(self) -> dict:
        """Load scene fallback mappings from profile_fallbacks.json"""
        try:
            fallback_path = os.path.join(os.path.dirname(__file__), '..', '..', 'profile_fallbacks.json')
            if os.path.exists(fallback_path):
                with open(fallback_path, 'r') as f:
                    data = json.load(f)
                    # Return the mappings for current profile, or empty dict
                    if self.profile_name and self.profile_name in data:
                        logging.info(f"Loaded {len(data[self.profile_name])} fallback mappings for profile '{self.profile_name}'")
                        return data[self.profile_name]
            return {}
        except Exception as e:
            logging.warning(f"Could not load fallback mappings: {e}")
            return {}
    
    def _get_scene_fixtures(self, scene_data: dict) -> Set[str]:
        """Extract all fixture names used in a scene."""
        fixtures = set()
        if 'lights' in scene_data:
            for light in scene_data['lights']:
                if 'name' in light:
                    fixtures.add(light['name'])
        if 'orchestrator' in scene_data:
            orchestrator = scene_data['orchestrator']
            if 'config' in orchestrator and 'target_lights' in orchestrator['config']:
                fixtures.update(orchestrator['config']['target_lights'])
        return fixtures
    
    def _is_scene_compatible(self, scene_data: dict) -> bool:
        """
        Check if a scene is compatible with the current profile.
        
        A scene is compatible if it uses at least one fixture from the available fixtures.
        Returns True if no profile/fixtures are configured (backwards compatibility).
        """
        if not self.available_fixtures:
            return True  # No profile filtering
        
        scene_fixtures = self._get_scene_fixtures(scene_data)
        if not scene_fixtures:
            return True  # Scene with no fixtures is technically compatible
        
        # Scene is compatible if it uses at least one available fixture
        return len(scene_fixtures & self.available_fixtures) > 0
    
    def _analyze_scene_compatibility(self) -> dict:
        """Analyze all scenes for compatibility with current profile."""
        compatibility = {}
        for scene_name, scene_data in self.scenes.items():
            compatibility[scene_name] = self._is_scene_compatible(scene_data)
        return compatibility
    
    def get_fallback_scene(self, scene_name: str) -> Optional[str]:
        """
        Get the fallback scene for an incompatible scene.
        
        Args:
            scene_name: Name of the requested scene
            
        Returns:
            Fallback scene name if one exists, otherwise None
        """
        if scene_name in self.fallback_mappings:
            fallback = self.fallback_mappings[scene_name]
            if fallback in self.scenes:
                return fallback
            else:
                logging.warning(f"Fallback scene '{fallback}' for '{scene_name}' not found")
        return None
    
    def set_scene(self, scene_name: str, apply_fallback: bool = True):
        """
        Set the current scene, applying fallback if defined.
        
        Args:
            scene_name: Name of the scene to activate
            apply_fallback: If True, apply fallback mapping if one exists
        """
        if scene_name not in self.scenes:
            raise ValueError(f"Scene '{scene_name}' not found")
        
        # Apply fallback if one exists in the mapping (regardless of compatibility)
        target_scene = scene_name
        if apply_fallback:
            fallback = self.get_fallback_scene(scene_name)
            if fallback:
                is_compatible = self.scene_compatibility.get(scene_name, True)
                if is_compatible:
                    logging.info(f"Scene '{scene_name}' replaced with '{fallback}' (forced by profile '{self.profile_name}' fallback mapping)")
                else:
                    logging.info(f"Scene '{scene_name}' incompatible with profile '{self.profile_name}', using fallback '{fallback}'")
                target_scene = fallback
            elif not self.scene_compatibility.get(scene_name, True):
                # No fallback defined but scene is incompatible
                logging.warning(f"Scene '{scene_name}' incompatible with profile '{self.profile_name}' and no fallback found - using anyway")
        
        self.current_scene = self.scenes[target_scene]

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