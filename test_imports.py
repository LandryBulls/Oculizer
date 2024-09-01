from oculizer import AudioListener, LightController, SceneManager
from oculizer.config import audio_parameters
import time

print("AudioListener imported successfully")
print("LightController imported successfully")
print("SceneManager imported successfully")
print(f"Audio parameters: {audio_parameters}")

# Instantiate AudioListener to ensure it works
listener = AudioListener()
print("AudioListener instantiated successfully")

listener.start()  # Use start() instead of run()
time.sleep(2)
listener.stop()
listener.join()  # Wait for the thread to finish
print('AudioListener started, stopped, and joined successfully')

# Instantiate LightController to ensure it works
controller = LightController(listener, 'testing', SceneManager('scenes'))
print("LightController instantiated successfully")

controller.start()  # Use start() instead of run()
time.sleep(2)
controller.stop()
controller.join()  # Wait for the thread to finish
print('LightController started, stopped, and joined successfully')

# Instantiate SceneManager to ensure it works
manager = SceneManager('scenes')
print("SceneManager instantiated successfully")

print('SceneManager started, stopped, and joined successfully')

print("All imports and instantiations successful")