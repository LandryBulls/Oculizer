#!/usr/bin/env python3
"""
Test script for scene fallback system.

This script verifies that the profile-aware scene fallback system works correctly
by simulating scene changes with different profiles.
"""

import json
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Import SceneManager
from oculizer.scenes.scene_manager import SceneManager

def load_profile_fixtures(profile_name):
    """Load profile and extract available fixture names."""
    try:
        current_dir = Path(__file__).resolve().parent
        profile_path = current_dir / 'profiles' / f'{profile_name}.json'
        
        if not profile_path.exists():
            print(f"❌ Profile '{profile_name}' not found at {profile_path}")
            return set()
        
        with open(profile_path, 'r') as f:
            profile = json.load(f)
        
        # Extract fixture names
        fixtures = set()
        if 'lights' in profile:
            for light in profile['lights']:
                if 'name' in light:
                    fixtures.add(light['name'])
        
        print(f"✅ Loaded profile '{profile_name}' with {len(fixtures)} fixtures")
        return fixtures
        
    except Exception as e:
        print(f"❌ Error loading profile fixtures: {e}")
        return set()

def test_scene_fallback(profile_name):
    """Test scene fallback system for a specific profile."""
    print(f"\n{'='*80}")
    print(f"TESTING SCENE FALLBACK SYSTEM FOR PROFILE: {profile_name}")
    print(f"{'='*80}\n")
    
    # Load profile fixtures
    fixtures = load_profile_fixtures(profile_name)
    if not fixtures:
        print(f"❌ Could not load fixtures for profile '{profile_name}'")
        return
    
    print(f"Available fixtures: {', '.join(sorted(fixtures))}\n")
    
    # Create SceneManager with profile awareness
    scene_manager = SceneManager('scenes', profile_name=profile_name, available_fixtures=fixtures)
    
    # Test scenes that should require fallbacks
    test_scenes = [
        'bass_hopper_rainbow',  # Uses rgb1-8 (not in mobile profile)
        'disco',                # Uses rgb1-8 + rockvilles (should be OK)
        'party',                # Uses lots of fixtures
        'supernova',            # Uses rgb1-8 + rockvilles
        'off',                  # Uses many fixtures
        'orb_racer',           # Uses orbs only
    ]
    
    print(f"Testing scene changes:\n")
    
    for scene_name in test_scenes:
        if scene_name not in scene_manager.scenes:
            print(f"⚠️  Scene '{scene_name}' not found")
            continue
        
        # Check if scene is compatible
        is_compatible = scene_manager.scene_compatibility.get(scene_name, True)
        fallback = scene_manager.get_fallback_scene(scene_name) if not is_compatible else None
        
        # Set the scene (which will apply fallback if needed)
        scene_manager.set_scene(scene_name)
        actual_scene = scene_manager.current_scene['name']
        
        # Display result
        if actual_scene != scene_name:
            print(f"🔄 {scene_name:25s} → {actual_scene:25s} (fallback applied)")
        else:
            status = "✅" if is_compatible else "⚠️ "
            print(f"{status} {scene_name:25s} → {actual_scene:25s} ({'compatible' if is_compatible else 'used anyway'})")
    
    print(f"\n{'='*80}\n")

def test_garage_profile():
    """Test that garage2025 profile doesn't use fallbacks (all scenes compatible)."""
    print(f"\n{'='*80}")
    print(f"TESTING GARAGE2025 PROFILE (Should have no fallbacks)")
    print(f"{'='*80}\n")
    
    # Load garage profile
    fixtures = load_profile_fixtures('garage2025')
    if not fixtures:
        print("❌ Could not load garage2025 profile")
        return
    
    # Create SceneManager
    scene_manager = SceneManager('scenes', profile_name='garage2025', available_fixtures=fixtures)
    
    # Check how many scenes are compatible
    compatible = sum(1 for compat in scene_manager.scene_compatibility.values() if compat)
    incompatible = sum(1 for compat in scene_manager.scene_compatibility.values() if not compat)
    
    print(f"Total scenes: {len(scene_manager.scenes)}")
    print(f"Compatible scenes: {compatible}")
    print(f"Incompatible scenes: {incompatible}")
    
    if incompatible == 0:
        print(f"\n✅ All scenes are compatible with garage2025 profile!")
    else:
        print(f"\n⚠️  Some scenes are incompatible with garage2025 profile:")
        for scene_name, compat in scene_manager.scene_compatibility.items():
            if not compat:
                print(f"   - {scene_name}")
    
    print(f"\n{'='*80}\n")

def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("SCENE FALLBACK SYSTEM TEST")
    print("="*80)
    
    # Test mobile profile (should use many fallbacks)
    test_scene_fallback('mobile')
    
    # Test garage2025 profile (should use no fallbacks)
    test_garage_profile()
    
    print("\n✅ All tests completed!\n")

if __name__ == "__main__":
    main()

