import json
from pathlib import Path

def load_audio_parameters():
    current_dir = Path(__file__).resolve().parent
    json_path = current_dir.parent / 'config' / 'audio_parameters.json'
    
    try:
        with open(json_path, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: audio_parameters.json not found at {json_path}")
        return {}  # or some default parameters
    except json.JSONDecodeError:
        print(f"Error: audio_parameters.json at {json_path} is not valid JSON")
        return {}  # or some default parameters

audio_parameters = load_audio_parameters()