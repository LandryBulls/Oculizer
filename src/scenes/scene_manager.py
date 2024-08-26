import os
import json

class SceneManager:
    def __init__(self, scenes_directory):
        self.scenes = self.load_json_files(scenes_directory)
        self.current_scene = self.scenes[list(self.scenes.keys())[0]]

    def load_json_files(self, directory):
        data = {}
        for filename in os.listdir(directory):
            if filename.endswith('.json'):
                with open(os.path.join(directory, filename), 'r') as file:
                    data[filename[:-5]] = json.load(file)
        return data

    def set_scene(self, scene_name):
        if scene_name in self.scenes:
            self.current_scene = self.scenes[scene_name]
        else:
            raise ValueError(f"Scene '{scene_name}' not found")

    def reload_scenes(self):
        self.scenes = self.load_json_files('scenes')

def main():
    scene_manager = SceneManager('scenes')
    scene_manager.set_scene('testing')
    print(scene_manager.current_scene)

if __name__ == '__main__':
    main()