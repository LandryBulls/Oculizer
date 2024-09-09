
# %%
import librosa
import numpy as np
from pathlib import Path
import allin1
from allin1.helpers import save_results
from tqdm import tqdm
import json

# %%
songdir = Path('../../music/halloween2k24')
savedir = Path('../../music/halloween2k24_features')
songs = [str(i) for i in songdir.glob('*.mp3')]
# %%

def main():
	for s, song in enumerate(songs):
		# check if song has been processed
		if not Path(f'../../music/halloween2k24_features/{Path(song).stem}.json').exists():
			print(f"Processing song {s}: {song}")
			result = allin1.analyze(song, demix_dir='demix', keep_byproducts=True, include_activations=True, include_embeddings=True)
			save_results(result, savedir)
		else:
			print(f"{Path(song).stem} already processed. Skipping")
		
if __name__ == '__main__':
	main()
