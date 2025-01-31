# Orchestrators

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