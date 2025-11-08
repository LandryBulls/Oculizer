#!/usr/bin/env python3
"""
Scene Analysis Tool - Identifies fixture usage patterns in scene files.

This script analyzes all scene JSON files to determine which lighting fixtures 
each scene uses, helping to identify compatibility issues with different profiles.
"""

import json
import os
from collections import defaultdict
from typing import Set, Dict, List

def get_scene_fixtures(scene_data: dict) -> Set[str]:
    """
    Extract all fixture names used in a scene.
    
    Args:
        scene_data: Scene configuration dictionary
        
    Returns:
        Set of fixture names used in the scene
    """
    fixtures = set()
    
    # Check lights section
    if 'lights' in scene_data:
        for light in scene_data['lights']:
            if 'name' in light:
                fixtures.add(light['name'])
    
    # Check orchestrator section for target_lights
    if 'orchestrator' in scene_data:
        orchestrator = scene_data['orchestrator']
        if 'config' in orchestrator and 'target_lights' in orchestrator['config']:
            fixtures.update(orchestrator['config']['target_lights'])
    
    return fixtures

def get_fixture_types(fixtures: Set[str]) -> Dict[str, Set[str]]:
    """
    Categorize fixtures by type based on naming conventions.
    
    Args:
        fixtures: Set of fixture names
        
    Returns:
        Dictionary mapping fixture types to sets of fixture names
    """
    types = defaultdict(set)
    
    for fixture in fixtures:
        if fixture.startswith('rockville'):
            types['rockville'].add(fixture)
        elif fixture.startswith('rgb'):
            types['rgb'].add(fixture)
        elif fixture.startswith('orb'):
            types['orb'].add(fixture)
        elif fixture == 'pinspot':
            types['pinspot'].add(fixture)
        elif fixture == 'strobe':
            types['strobe'].add(fixture)
        elif fixture == 'laser' or fixture == 'lasers':
            types['laser'].add(fixture)
        elif fixture == 'ropes':
            types['ropes'].add(fixture)
        else:
            types['other'].add(fixture)
    
    return types

def analyze_scenes(scenes_dir: str) -> Dict:
    """
    Analyze all scene files in a directory.
    
    Args:
        scenes_dir: Path to scenes directory
        
    Returns:
        Dictionary with analysis results
    """
    results = {
        'scenes': {},
        'no_rockville': [],
        'only_rockville': [],
        'summary': defaultdict(int)
    }
    
    # Load all scene files
    for filename in sorted(os.listdir(scenes_dir)):
        if not filename.endswith('.json'):
            continue
            
        scene_name = filename[:-5]
        filepath = os.path.join(scenes_dir, filename)
        
        try:
            with open(filepath, 'r') as f:
                scene_data = json.load(f)
            
            # Extract fixtures
            fixtures = get_scene_fixtures(scene_data)
            fixture_types = get_fixture_types(fixtures)
            
            # Store results
            has_rockville = len(fixture_types['rockville']) > 0
            has_other = any(len(v) > 0 for k, v in fixture_types.items() if k != 'rockville')
            
            results['scenes'][scene_name] = {
                'fixtures': sorted(fixtures),
                'types': {k: sorted(v) for k, v in fixture_types.items()},
                'has_rockville': has_rockville,
                'rockville_count': len(fixture_types['rockville']),
                'total_fixtures': len(fixtures)
            }
            
            # Categorize scenes
            if not has_rockville:
                results['no_rockville'].append(scene_name)
                results['summary']['no_rockville'] += 1
            elif not has_other:
                results['only_rockville'].append(scene_name)
                results['summary']['only_rockville'] += 1
            else:
                results['summary']['mixed'] += 1
                
        except Exception as e:
            print(f"Error processing {filename}: {e}")
            continue
    
    results['summary']['total'] = len(results['scenes'])
    
    return results

def print_analysis(results: Dict):
    """Print formatted analysis results."""
    print("\n" + "="*80)
    print("SCENE ANALYSIS RESULTS")
    print("="*80)
    
    print(f"\n📊 Summary:")
    print(f"  Total scenes: {results['summary']['total']}")
    print(f"  Scenes without Rockvilles: {results['summary']['no_rockville']}")
    print(f"  Scenes with only Rockvilles: {results['summary']['only_rockville']}")
    print(f"  Mixed scenes: {results['summary']['mixed']}")
    
    # Scenes without rockvilles (incompatible with mobile profile)
    if results['no_rockville']:
        print(f"\n🚨 Scenes WITHOUT Rockvilles ({len(results['no_rockville'])}):")
        print("   These scenes will go dark on the mobile profile!")
        print("   " + "-"*76)
        for scene_name in sorted(results['no_rockville']):
            scene_info = results['scenes'][scene_name]
            fixture_summary = []
            for ftype, fixtures in scene_info['types'].items():
                if fixtures:
                    fixture_summary.append(f"{len(fixtures)} {ftype}")
            print(f"   • {scene_name:30s} uses: {', '.join(fixture_summary)}")
    
    # Scenes with only rockvilles (safe for mobile)
    if results['only_rockville']:
        print(f"\n✅ Scenes with ONLY Rockvilles ({len(results['only_rockville'])}):")
        print("   These scenes are fully compatible with mobile profile!")
        print("   " + "-"*76)
        for scene_name in sorted(results['only_rockville']):
            count = results['scenes'][scene_name]['rockville_count']
            print(f"   • {scene_name:30s} uses: {count} rockvilles")
    
    print("\n" + "="*80)

def get_scene_colors_and_vibe(scene_name: str, scene_data: dict) -> Dict[str, any]:
    """
    Analyze a scene to extract color palette and vibe for matching.
    
    Args:
        scene_name: Name of the scene
        scene_data: Scene configuration dictionary
        
    Returns:
        Dictionary with color and vibe information
    """
    colors = set()
    has_strobe = False
    has_bass = False
    is_fast = False
    
    # Extract colors from lights
    if 'lights' in scene_data:
        for light in scene_data['lights']:
            if 'color' in light:
                color = light['color']
                if isinstance(color, str):
                    colors.add(color.lower())
            if 'colors' in light:
                if isinstance(light['colors'], list):
                    colors.update(c.lower() for c in light['colors'])
            if 'effect' in light and 'colors' in light['effect']:
                if isinstance(light['effect']['colors'], list):
                    colors.update(c.lower() for c in light['effect']['colors'])
            
            # Check for strobe
            if 'strobe' in light and light['strobe'] not in [0, '0']:
                has_strobe = True
            if 'panel_strobe' in light.get('panel', {}) and light['panel']['panel_strobe'] not in [0, '0']:
                has_strobe = True
            
            # Check for bass reactivity
            if 'mfft_range' in light:
                mfft_range = light['mfft_range']
                if isinstance(mfft_range, list) and len(mfft_range) == 2:
                    if mfft_range[1] <= 30:  # Low frequency = bass
                        has_bass = True
    
    # Check orchestrator for additional hints
    if 'orchestrator' in scene_data:
        orch_type = scene_data['orchestrator'].get('type', '')
        if orch_type in ['hopper', 'racer']:
            is_fast = True
    
    # Determine vibe from scene name
    vibe_keywords = {
        'chill': ['chill', 'ambient', 'fade', 'wave'],
        'intense': ['supernova', 'quasar', 'vortex', 'hypno', 'electric'],
        'party': ['party', 'disco', 'dance'],
        'bass': ['bass', 'pulse'],
        'strobe': ['strobe', 'flicker'],
        'psychedelic': ['psychedelic', 'trippy', 'goosebumps', 'temple']
    }
    
    vibes = []
    scene_lower = scene_name.lower()
    for vibe, keywords in vibe_keywords.items():
        if any(keyword in scene_lower for keyword in keywords):
            vibes.append(vibe)
    
    if has_strobe:
        vibes.append('strobe')
    if has_bass:
        vibes.append('bass')
    if is_fast:
        vibes.append('fast')
    
    return {
        'colors': sorted(colors),
        'vibes': vibes,
        'has_strobe': has_strobe,
        'has_bass': has_bass,
        'is_fast': is_fast
    }

def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    scenes_dir = os.path.join(script_dir, 'scenes')
    
    if not os.path.exists(scenes_dir):
        print(f"Error: Scenes directory not found at {scenes_dir}")
        return
    
    # Run analysis
    results = analyze_scenes(scenes_dir)
    print_analysis(results)
    
    # Save detailed analysis to file
    output_file = os.path.join(script_dir, 'scene_analysis.json')
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n💾 Detailed analysis saved to: {output_file}\n")

if __name__ == "__main__":
    main()

