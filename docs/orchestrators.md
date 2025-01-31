# Orchestrators

Orchestrators provide high-level control over groups of lights in a scene. They can coordinate multiple lights to create complex patterns and behaviors that would be difficult to achieve with individual light configurations alone.

## Using Orchestrators

To add an orchestrator to a scene, include an `orchestrator` section in your scene JSON:

```json
{
    "name": "hopping_lights",
    "description": "Lights hop from fixture to fixture on beats",
    "orchestrator": {
        "type": "hopper",
        "config": {
            "target_lights": ["rgb1", "rgb2", "rgb3", "rgb4"],
            "trigger": {
                "type": "rms",
                "threshold": 0.6,
                "mfft_range": [0, 20]
            },
            "transition": {
                "type": "fade",
                "duration": 0.2
            }
        }
    },
    "lights": [
        // ... individual light configs ...
    ]
}
```

## Available Orchestrators

### Hopper
Makes lights "hop" from fixture to fixture based on audio triggers.

**Parameters:**
- `target_lights`: List of light names to coordinate
- `trigger`: Trigger configuration
- `transition`: Transition configuration

```json
    {
    "orchestrator": {
    "type": "wave",
    "config": {
    "target_lights": ["rgb1", "rgb2", "rgb3", "rgb4"],
    "wave_speed": 1.0, // waves per second
    "overlap": 0.5, // portion of wave that overlaps (0.0 to 1.0)
            "direction": "forward" // "forward" or "reverse"
        }
    }
}
```

## Interaction with Light Effects

Orchestrators work alongside individual light effects. The orchestrator determines:
1. Which lights are active at any given time
2. Any modifications to the light's base behavior

Individual light configurations still control the base behavior (color, patterns, etc.) when a light is active.

## Creating Custom Orchestrators

Custom orchestrators can be created by:
1. Subclassing the `Orchestrator` base class
2. Implementing the `process()` method
3. Adding the orchestrator to the `ORCHESTRATORS` dictionary

Example:

```python:docs/orchestrators.md
class CustomOrchestrator(Orchestrator):
    def process(self, lights: list, mfft_data: np.ndarray, current_time: float) -> dict:
        # Return dict of modifications for each light
        return {light: {'active': bool, 'modifiers': {}} for light in lights}

ORCHESTRATORS['custom'] = CustomOrchestrator
```

## Tips
- Use orchestrators for coordinated light movements and patterns
- Combine with effects for complex behaviors
- Monitor CPU usage when using complex orchestrators with many lights
- Test orchestrator timing with different audio inputs
