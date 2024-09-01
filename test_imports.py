from oculizer import AudioListener, LightController, SceneManager
from oculizer.config import audio_parameters

print("AudioListener imported successfully")
print("LightController imported successfully")
print("SceneManager imported successfully")
print(f"Audio parameters: {audio_parameters}")

# Instantiate AudioListener to ensure it works
listener = AudioListener()
print("AudioListener instantiated successfully")

# Instantiate LightController to ensure it works
controller = LightController(listener, 'testing', SceneManager('scenes'))
print("LightController instantiated successfully")

# Instantiate SceneManager to ensure it works
manager = SceneManager('scenes')
print("SceneManager instantiated successfully")