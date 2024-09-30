import json
import os
from collections import OrderedDict

def custom_key_order(key):
    # Define the desired order of keys
    order = ['name', 'description', 'type', 'midi', 'key_command', 'lights']
    
    # Return the index of the key if it's in the order list, otherwise return a high number
    return order.index(key) if key in order else len(order)

def order_dict(item):
    if isinstance(item, dict):
        
        return OrderedDict(sorted(item.items(), key=lambda x: custom_key_order(x[0])))
    elif isinstance(item, list):
        return [order_dict(i) for i in item]
    return item

scene_dir = 'scenes'
scenes = []

# Load the scenes
for scene_file in os.listdir(scene_dir):
    if scene_file.endswith('.json'):
        with open(os.path.join(scene_dir, scene_file)) as f:
            scenes.append(json.load(f))

# Add type to scenes (if not already done) and order the dictionaries
ordered_scenes = []
for scene in scenes:
    name = scene['name']
    if 'type' not in scene:
        if 'build' in name:
            scene['type'] = 'build'
        elif 'drop' in name:
            scene['type'] = 'drop'
        elif 'ambient' in name:
            scene['type'] = 'ambient'
        else:
            scene['type'] = 'effect'
    
    # Order the scene dictionary and its nested structures
    ordered_scenes.append(order_dict(scene))

# Custom JSON encoder to handle OrderedDict
class OrderedDictEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, OrderedDict):
            return {k: self.default(v) for k, v in obj.items()}
        return super().default(obj)

# Save scenes back to JSON files with improved formatting and custom order
for scene in ordered_scenes:
    filename = os.path.join(scene_dir, scene['name'] + '.json')
    with open(filename, 'w') as f:
        json.dump(scene, f, indent=2, cls=OrderedDictEncoder)

print("All scene files have been updated with improved formatting and custom key order.")
