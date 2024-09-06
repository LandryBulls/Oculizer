
# %%
import librosa
import numpy as np
from pathlib import Path
import allin1 as ai1
from tqdm import tqdm

# %%
songdir = Path('../../music/halloween2k24')
savedir = Path('../../music/halloween2k24_features')
songs = [str(i) for i in songdir.glob('*.mp3')]
# %%
results = ai1.analyze(songs, out_dir=savedir, include_embeddings=True, include_activations=True)
