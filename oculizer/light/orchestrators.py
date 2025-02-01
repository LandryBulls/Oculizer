from abc import ABC, abstractmethod
import time
import numpy as np

class Orchestrator(ABC):
    def __init__(self, config: dict):
        self.config = config
        self.state = {}
    
    @abstractmethod
    def process(self, lights: list, mfft_data: np.ndarray, current_time: float) -> dict:
        """
        Process the current state and return a dict of light modifications.
        Returns: {light_name: {'active': bool, 'modifiers': {...}}}
        """
        pass

class HopperOrchestrator(Orchestrator):
    def __init__(self, config: dict):
        super().__init__(config)
        self.state = {
            'current_light_idx': 0,
            'last_trigger_time': 0,
            'active_light': None,
            'transition_start': 0
        }
    
    def process(self, lights: list, mfft_data: np.ndarray, current_time: float) -> dict:
        target_lights = self.config['target_lights']
        trigger_config = self.config['trigger']
        transition_config = self.config.get('transition', {})
        
        # Check for trigger
        mfft_range = trigger_config['mfft_range']
        power = np.mean(mfft_data[mfft_range[0]:mfft_range[1]])
        
        modifications = {light: {'active': False, 'modifiers': {}} for light in lights}
        
        if power >= trigger_config['threshold']:
            if current_time - self.state['last_trigger_time'] > transition_config.get('duration', 0.1):
                # Trigger new light
                self.state['last_trigger_time'] = current_time
                self.state['transition_start'] = current_time
                self.state['current_light_idx'] = (self.state['current_light_idx'] + 1) % len(target_lights)
                self.state['active_light'] = target_lights[self.state['current_light_idx']]
        
        # Apply modifications
        active_light = self.state['active_light']
        if active_light:
            modifications[active_light] = {
                'active': True,
                'modifiers': {
                    'brightness_scale': 1.0,
                    'transition_progress': (current_time - self.state['transition_start']) / transition_config.get('duration', 0.1)
                }
            }
            
        return modifications

# Dictionary mapping orchestrator types to their respective classes
ORCHESTRATORS = {
    'hopper': HopperOrchestrator
}