#!/usr/bin/env python3
"""
Generate scene fallback mappings for different profiles.

This script analyzes scenes and creates intelligent fallback mappings for profiles
that don't support all fixtures (e.g., mobile profile with only rockvilles).
"""

import json
import os
from typing import Dict, List, Set

def get_scene_characteristics(scene_name: str, scene_data: dict) -> Dict:
    """Extract characteristics for scene matching."""
    colors = set()
    vibes = []
    has_strobe = False
    has_bass = False
    is_fast = False
    
    # Extract colors from lights
    if 'lights' in scene_data:
        for light in scene_data['lights']:
            # Direct color property
            if 'color' in light:
                color = light['color']
                if isinstance(color, str):
                    colors.add(color.lower())
            
            # Colors array
            if 'colors' in light:
                if isinstance(light['colors'], list):
                    colors.update(c.lower() for c in light['colors'])
            
            # Effect colors
            if 'effect' in light and 'colors' in light['effect']:
                if isinstance(light['effect']['colors'], list):
                    colors.update(c.lower() for c in light['effect']['colors'])
            
            # Panel colors
            if 'panel' in light and 'color' in light['panel']:
                colors.add(light['panel']['color'].lower())
            
            # Check for strobe
            if 'strobe' in light:
                strobe_val = light['strobe']
                if strobe_val not in [0, '0', 255]:  # 255 is no strobe in some contexts
                    has_strobe = True
            
            # Check panel strobe
            if 'panel' in light and 'strobe' in light['panel']:
                if light['panel']['strobe'] not in [0, '0']:
                    has_strobe = True
            
            # Effect panel strobe
            if 'effect' in light and 'panel_strobe' in light['effect']:
                if light['effect']['panel_strobe'] not in [0, '0']:
                    has_strobe = True
            
            # Check for bass reactivity (low frequency MFFT)
            if 'mfft_range' in light:
                mfft_range = light['mfft_range']
                if isinstance(mfft_range, list) and len(mfft_range) == 2:
                    if mfft_range[1] <= 30:
                        has_bass = True
    
    # Check orchestrator
    if 'orchestrator' in scene_data:
        orch_type = scene_data['orchestrator'].get('type', '')
        if orch_type in ['hopper', 'racer']:
            is_fast = True
            vibes.append(orch_type)
    
    # Determine vibe from scene name
    scene_lower = scene_name.lower()
    
    # Color-based vibes
    if 'rainbow' in scene_lower:
        vibes.append('rainbow')
        colors.update(['red', 'orange', 'yellow', 'green', 'blue', 'purple', 'pink'])
    
    # Intensity vibes
    if any(w in scene_lower for w in ['chill', 'ambient', 'fade', 'wave']):
        vibes.append('chill')
    if any(w in scene_lower for w in ['supernova', 'quasar', 'vortex', 'hypno', 'electric']):
        vibes.append('intense')
    if any(w in scene_lower for w in ['party', 'disco', 'dance']):
        vibes.append('party')
    
    # Activity vibes
    if 'bass' in scene_lower or 'pulse' in scene_lower:
        vibes.append('bass')
        has_bass = True
    if 'strobe' in scene_lower or 'flicker' in scene_lower:
        vibes.append('strobe')
        has_strobe = True
    if 'speed' in scene_lower or 'racer' in scene_lower:
        vibes.append('fast')
        is_fast = True
    if any(w in scene_lower for w in ['hopper', 'hop']):
        vibes.append('hopper')
    
    # Psychedelic vibes
    if any(w in scene_lower for w in ['goosebumps', 'temple', 'swamp']):
        vibes.append('psychedelic')
    
    return {
        'colors': sorted(colors),
        'vibes': vibes,
        'has_strobe': has_strobe,
        'has_bass': has_bass,
        'is_fast': is_fast
    }

def find_best_fallback(source_scene: str, source_chars: Dict, 
                       compatible_scenes: List[str], all_scenes: Dict) -> str:
    """Find the best fallback scene based on characteristics."""
    best_match = None
    best_score = -1
    
    for candidate in compatible_scenes:
        if candidate == source_scene:
            continue
            
        # Load candidate scene
        candidate_chars = get_scene_characteristics(candidate, all_scenes[candidate])
        
        # Calculate similarity score
        score = 0
        
        # Color matching (high weight)
        if source_chars['colors'] and candidate_chars['colors']:
            color_overlap = len(set(source_chars['colors']) & set(candidate_chars['colors']))
            color_union = len(set(source_chars['colors']) | set(candidate_chars['colors']))
            if color_union > 0:
                score += (color_overlap / color_union) * 40
        
        # Vibe matching (high weight)
        if source_chars['vibes'] and candidate_chars['vibes']:
            vibe_overlap = len(set(source_chars['vibes']) & set(candidate_chars['vibes']))
            score += vibe_overlap * 15
        
        # Specific characteristic matching
        if source_chars['has_bass'] == candidate_chars['has_bass']:
            score += 10
        if source_chars['has_strobe'] == candidate_chars['has_strobe']:
            score += 8
        if source_chars['is_fast'] == candidate_chars['is_fast']:
            score += 8
        
        # Special handling for specific scene types
        source_lower = source_scene.lower()
        candidate_lower = candidate.lower()
        
        # Color-specific scenes
        for color in ['red', 'blue', 'green', 'pink', 'white', 'purple', 'orange']:
            if color in source_lower and color in candidate_lower:
                score += 25
        
        # Pattern matching (hopper, racer, pulse, etc.)
        for pattern in ['hopper', 'racer', 'pulse', 'speedracer', 'bass']:
            if pattern in source_lower and pattern in candidate_lower:
                score += 20
        
        if score > best_score:
            best_score = score
            best_match = candidate
    
    return best_match

def generate_fallback_mapping(scenes_dir: str) -> Dict:
    """Generate fallback mappings for mobile profile."""
    
    # Load all scenes
    all_scenes = {}
    for filename in os.listdir(scenes_dir):
        if not filename.endswith('.json'):
            continue
        scene_name = filename[:-5]
        with open(os.path.join(scenes_dir, filename), 'r') as f:
            all_scenes[scene_name] = json.load(f)
    
    # Identify scenes with and without rockvilles
    scenes_with_rockville = []
    scenes_without_rockville = []
    
    for scene_name, scene_data in all_scenes.items():
        has_rockville = False
        if 'lights' in scene_data:
            for light in scene_data['lights']:
                if 'name' in light and light['name'].startswith('rockville'):
                    has_rockville = True
                    break
        
        if has_rockville:
            scenes_with_rockville.append(scene_name)
        else:
            scenes_without_rockville.append(scene_name)
    
    # Generate fallback mappings
    fallback_map = {}
    
    print("\n" + "="*80)
    print("GENERATING FALLBACK MAPPINGS FOR MOBILE PROFILE")
    print("="*80 + "\n")
    
    for source_scene in sorted(scenes_without_rockville):
        source_chars = get_scene_characteristics(source_scene, all_scenes[source_scene])
        fallback = find_best_fallback(source_scene, source_chars, 
                                     scenes_with_rockville, all_scenes)
        
        if fallback:
            fallback_chars = get_scene_characteristics(fallback, all_scenes[fallback])
            fallback_map[source_scene] = fallback
            
            # Print the mapping with reasoning
            print(f"🔄 {source_scene:30s} → {fallback:30s}")
            
            # Show matching characteristics
            reasons = []
            if source_chars['colors'] and fallback_chars['colors']:
                matching_colors = set(source_chars['colors']) & set(fallback_chars['colors'])
                if matching_colors:
                    reasons.append(f"colors: {', '.join(sorted(matching_colors))}")
            
            if source_chars['vibes'] and fallback_chars['vibes']:
                matching_vibes = set(source_chars['vibes']) & set(fallback_chars['vibes'])
                if matching_vibes:
                    reasons.append(f"vibes: {', '.join(sorted(matching_vibes))}")
            
            if reasons:
                print(f"   └─ Matched on: {'; '.join(reasons)}")
            print()
    
    print("="*80 + "\n")
    
    return fallback_map

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scenes_dir = os.path.join(script_dir, 'scenes')
    
    if not os.path.exists(scenes_dir):
        print(f"Error: Scenes directory not found at {scenes_dir}")
        return
    
    # Generate fallback mappings
    fallback_map = generate_fallback_mapping(scenes_dir)
    
    # Create the profile fallbacks structure
    profile_fallbacks = {
        "_comment": "Scene fallback mappings for profiles with limited fixture support",
        "_usage": "When a scene uses fixtures not available in the current profile, map to the fallback scene",
        "mobile": fallback_map
    }
    
    # Save to JSON file
    output_file = os.path.join(script_dir, 'profile_fallbacks.json')
    with open(output_file, 'w') as f:
        json.dump(profile_fallbacks, f, indent=2)
    
    print(f"✅ Generated {len(fallback_map)} fallback mappings")
    print(f"💾 Saved to: {output_file}\n")

if __name__ == "__main__":
    main()

