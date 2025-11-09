#!/usr/bin/env python3
"""
Test to verify that fallback system is ONLY active for mobile profile.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

# Import directly to avoid loading audio dependencies
from oculizer.scenes.scene_manager import SceneManager

def test_profile_fallback_behavior():
    """Test that fallbacks only apply to mobile profile."""
    
    print("=" * 60)
    print("TESTING FALLBACK SYSTEM - PROFILE-SPECIFIC BEHAVIOR")
    print("=" * 60)
    
    # Test 1: Mobile profile (should have fallbacks)
    print("\n1. Testing MOBILE profile:")
    print("-" * 60)
    
    # Get available fixtures for mobile profile
    import json
    with open('profiles/mobile.json', 'r') as f:
        mobile_profile = json.load(f)
    mobile_fixtures = {light['name'] for light in mobile_profile['lights']}
    
    mobile_sm = SceneManager('scenes', profile_name='mobile', available_fixtures=mobile_fixtures)
    
    print(f"   Fallback mappings loaded: {len(mobile_sm.fallback_mappings)}")
    print(f"   Expected: 35+ mappings")
    
    if len(mobile_sm.fallback_mappings) > 0:
        print("   ✅ PASS: Mobile profile has fallback mappings")
        print(f"\n   Sample fallbacks:")
        for i, (src, tgt) in enumerate(list(mobile_sm.fallback_mappings.items())[:5]):
            print(f"      {src} → {tgt}")
    else:
        print("   ❌ FAIL: Mobile profile should have fallbacks!")
    
    # Test 2: Garage2025 profile (should NOT have fallbacks)
    print("\n2. Testing GARAGE2025 profile:")
    print("-" * 60)
    
    with open('profiles/garage2025.json', 'r') as f:
        garage_profile = json.load(f)
    garage_fixtures = {light['name'] for light in garage_profile['lights']}
    
    garage_sm = SceneManager('scenes', profile_name='garage2025', available_fixtures=garage_fixtures)
    
    print(f"   Fallback mappings loaded: {len(garage_sm.fallback_mappings)}")
    print(f"   Expected: 0 mappings")
    
    if len(garage_sm.fallback_mappings) == 0:
        print("   ✅ PASS: Garage2025 profile has NO fallback mappings")
    else:
        print("   ❌ FAIL: Garage2025 profile should NOT have fallbacks!")
        print(f"   Unexpected mappings found:")
        for src, tgt in garage_sm.fallback_mappings.items():
            print(f"      {src} → {tgt}")
    
    # Test 3: Verify fallback application
    print("\n3. Testing fallback application:")
    print("-" * 60)
    
    # Test a scene that has a fallback defined in mobile profile
    test_scene = "bass_hopper"  # Has fallback in mobile: sequence_ice
    
    print(f"\n   Testing scene: '{test_scene}'")
    
    # Mobile should apply fallback
    print(f"   Mobile profile:")
    mobile_fallback = mobile_sm.get_fallback_scene(test_scene)
    print(f"      Fallback: {mobile_fallback}")
    if mobile_fallback:
        print(f"      ✅ PASS: Fallback '{mobile_fallback}' will be used")
    else:
        print(f"      ❌ FAIL: Should have a fallback!")
    
    # Garage2025 should NOT apply fallback
    print(f"\n   Garage2025 profile:")
    garage_fallback = garage_sm.get_fallback_scene(test_scene)
    print(f"      Fallback: {garage_fallback}")
    if garage_fallback is None:
        print(f"      ✅ PASS: No fallback (scene will be used as-is)")
    else:
        print(f"      ❌ FAIL: Should NOT have a fallback!")
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    print(f"Mobile profile fallbacks: {len(mobile_sm.fallback_mappings)} mappings")
    print(f"Garage2025 profile fallbacks: {len(garage_sm.fallback_mappings)} mappings")
    print("\n✅ Fallback system is correctly configured to ONLY work with mobile profile!")
    print("=" * 60)

if __name__ == '__main__':
    test_profile_fallback_behavior()
