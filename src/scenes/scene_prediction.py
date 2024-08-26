"""
Predict the lighting scene based on spotify features, real-time audio analysis, and user preferences. 
"""

import numpy as np
from scipy.spatial import distance
import time
import threading
import queue
import json
import os
import random
from config import audio_parameters
import librosa
from sklearn.cluster import KMeans

