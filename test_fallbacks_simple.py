#!/usr/bin/env python3
"""
Simple test to verify profile_fallbacks.json structure and basic logic.
"""

import json
import os

def test_fallback_file():
    """Test that profile_fallbacks.json exists and is valid."""
    print("\n" + "="*80)
    print("TESTING profile_fallbacks.json")
    print("="*80 + "\n")
    
    fallback_path = 'profile_fallbacks.json'
    
    if not os.path.exists(fallback_path):
        print(f"❌ File not found: {fallback_path}")
        return False
    
    try:
        with open(fallback_path, 'r') as f:
            data = json.load(f)
        
        print(f"✅ Successfully loaded {fallback_path}")
        print(f"\nProfiles defined: {[k for k in data.keys() if not k.startswith('_')]}")
        
        if 'mobile' in data:
            mobile_fallbacks = data['mobile']
            print(f"\nMobile profile has {len(mobile_fallbacks)} fallback mappings:")
            print(f"\nSample fallbacks:")
            for i, (source, target) in enumerate(list(mobile_fallbacks.items())[:10]):
                print(f"  {source:25s} → {target}")
            if len(mobile_fallbacks) > 10:
                print(f"  ... and {len(mobile_fallbacks) - 10} more")
        
        return True
        
    except Exception as e:
        print(f"❌ Error loading file: {e}")
        return False

def test_profile_fixtures():
    """Test loading profile fixtures."""
    print("\n" + "="*80)
    print("TESTING PROFILE FIXTURE EXTRACTION")
    print("="*80 + "\n")
    
    profiles_to_test = ['mobile', 'garage2025']
    
    for profile_name in profiles_to_test:
        profile_path = f'profiles/{profile_name}.json'
        
        if not os.path.exists(profile_path):
            print(f"⚠️  Profile not found: {profile_path}")
            continue
        
        try:
            with open(profile_path, 'r') as f:
                profile = json.load(f)
            
            fixtures = []
            if 'lights' in profile:
                for light in profile['lights']:
                    if 'name' in light:
                        fixtures.append(light['name'])
            
            print(f"✅ Profile '{profile_name}':")
            print(f"   - Total fixtures: {len(fixtures)}")
            
            # Count fixture types
            rockville_count = sum(1 for f in fixtures if f.startswith('rockville'))
            rgb_count = sum(1 for f in fixtures if f.startswith('rgb'))
            
            print(f"   - Rockvilles: {rockville_count}")
            print(f"   - RGB lights: {rgb_count}")
            print(f"   - Others: {len(fixtures) - rockville_count - rgb_count}")
            
        except Exception as e:
            print(f"❌ Error loading profile '{profile_name}': {e}")
    
    print()

def test_scene_analysis():
    """Test scene fixture detection."""
    print("\n" + "="*80)
    print("TESTING SCENE FIXTURE DETECTION")
    print("="*80 + "\n")
    
    # Test a few representative scenes
    test_scenes = {
        'bass_hopper_rainbow': 'scenes/bass_hopper_rainbow.json',
        'disco': 'scenes/disco.json',
        'supernova': 'scenes/supernova.json'
    }
    
    for scene_name, scene_path in test_scenes.items():
        if not os.path.exists(scene_path):
            print(f"⚠️  Scene not found: {scene_path}")
            continue
        
        try:
            with open(scene_path, 'r') as f:
                scene_data = json.load(f)
            
            # Extract fixtures
            fixtures = set()
            if 'lights' in scene_data:
                for light in scene_data['lights']:
                    if 'name' in light:
                        fixtures.add(light['name'])
            
            has_rockville = any(f.startswith('rockville') for f in fixtures)
            has_rgb = any(f.startswith('rgb') for f in fixtures)
            
            print(f"Scene '{scene_name}':")
            print(f"   - Fixtures: {', '.join(sorted(fixtures))}")
            print(f"   - Has rockvilles: {'✅' if has_rockville else '❌'}")
            print(f"   - Has RGB: {'✅' if has_rgb else '❌'}")
            print()
            
        except Exception as e:
            print(f"❌ Error loading scene '{scene_name}': {e}")

def main():
    """Run all simple tests."""
    print("\n" + "="*80)
    print("SCENE FALLBACK SYSTEM - SIMPLE VALIDATION")
    print("="*80)
    
    test_fallback_file()
    test_profile_fixtures()
    test_scene_analysis()
    
    print("\n" + "="*80)
    print("✅ ALL SIMPLE TESTS COMPLETED")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()

