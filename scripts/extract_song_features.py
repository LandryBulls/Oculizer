# %%
import librosa
import numpy as np
from pathlib import Path
import allin1
from allin1.helpers import save_results
from tqdm import tqdm
import json
import argparse

"""
This script extracts features from all the songs in a directory and saves them to a json file.
** THIS INCLUDES SEGMENTS **

Usage:
    python extract_features.py --input-dir <input_directory> --output-dir <output_directory>

Arguments:
    --input-dir  : Required. Path to the directory containing MP3 files to process
    --output-dir : Required. Path where the extracted features will be saved as JSON files

Example:
    python extract_features.py --input-dir /path/to/songs --output-dir /path/to/features

Notes:
    - The script will process all MP3 files in the input directory
    - Each song's features will be saved as a separate JSON file in the output directory
    - Files that have already been processed (exist in output directory) will be skipped
    - The output directory will be created if it doesn't exist
"""

def parse_args():
	parser = argparse.ArgumentParser(description='Extract features from audio files in a directory')
	parser.add_argument('--input-dir', type=str, required=True,
					  help='Directory containing the input audio files')
	parser.add_argument('--output-dir', type=str, required=True,
					  help='Directory where feature files will be saved')
	return parser.parse_args()

def main():
	args = parse_args()
	
	# Convert string paths to Path objects and resolve them
	songdir = Path(args.input_dir).resolve()
	savedir = Path(args.output_dir).resolve()
	
	# Ensure directories exist
	if not songdir.exists():
		raise ValueError(f"Input directory does not exist: {songdir}")
	
	# Create output directory if it doesn't exist
	savedir.mkdir(parents=True, exist_ok=True)
	
	# Get all MP3 files in the input directory
	songs = [str(i) for i in songdir.glob('*.mp3')]
	
	if not songs:
		print(f"No MP3 files found in {songdir}")
		return
		
	for s, song in enumerate(songs):
		# check if song has been processed
		output_file = savedir / f"{Path(song).stem}.json"
		if not output_file.exists():
			print(f"Processing song {s+1}/{len(songs)}: {song}")
			result = allin1.analyze(song, demix_dir='demix', keep_byproducts=True, include_activations=True, include_embeddings=True)
			save_results(result, savedir)
		else:
			print(f"{Path(song).stem} already processed. Skipping")

if __name__ == '__main__':
	main()
