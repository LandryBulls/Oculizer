import json
from pathlib import Path

def load_audio_parameters():
    current_dir = Path(__file__).resolve().parent
    json_path = current_dir.parent / 'config' / 'audio_parameters.json'
    
    with open(json_path, 'r') as f:
        return json.load(f)

audio_parameters = load_audio_parameters()
audio_parameters['HOP_LENGTH'] = int(audio_parameters['BLOCKSIZE'] / 2)