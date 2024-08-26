import os
import json

def load_json(filename):
    with open(filename, 'r') as f:
        data = json.load(f)
    return data