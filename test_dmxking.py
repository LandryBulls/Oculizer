#!/usr/bin/env python3
"""
DMXKing ultraDMX MAX Test Script

This script tests the connection to your DMXKing ultraDMX MAX interface
and performs basic functionality tests.

Usage:
    python test_dmxking.py

Make sure to:
1. Connect your DMXKing ultraDMX MAX to your computer
2. Update the port in oculizer/light/dmx_config.py if needed
3. Connect a DMX fixture to test output
"""

import sys
import time
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

from oculizer.light.enttec_controller import EnttecProController
from oculizer.light.dmx_config import get_dmx_config, get_port_for_system
import platform

def test_dmx_connection():
    """Test DMXKing ultraDMX MAX connection."""
    print("DMXKing ultraDMX MAX Connection Test")
    print("=" * 40)
    
    # Get configuration
    config = get_dmx_config()
    print(f"Using port: {config['port']}")
    print(f"Baudrate: {config['baudrate']}")
    print(f"Timeout: {config['timeout']}s")
    print()
    
    # Show alternative ports for current system
    system = platform.system().lower()
    if system == 'darwin':
        system = 'macos'
    
    suggested_ports = get_port_for_system(system)
    print(f"Suggested ports for {system}: {', '.join(suggested_ports)}")
    print()
    
    try:
        # Initialize controller
        print("Initializing DMX controller...")
        controller = EnttecProController(
            port=config['port'],
            baudrate=config['baudrate'],
            timeout=config['timeout']
        )
        print("✓ Controller initialized successfully!")
        print()
        
        # Test basic DMX output
        print("Testing DMX output...")
        
        # Test channel 1 (dimmer)
        print("Setting channel 1 to 50% (128)...")
        controller.set_channel(1, 128)
        time.sleep(1)
        
        print("Setting channel 1 to 100% (255)...")
        controller.set_channel(1, 255)
        time.sleep(1)
        
        print("Setting channel 1 to 0% (0)...")
        controller.set_channel(1, 0)
        time.sleep(1)
        
        # Test RGB channels (channels 1-3)
        print("Testing RGB channels (1-3)...")
        print("Setting RGB to red (255, 0, 0)...")
        controller.set_channels([1, 2, 3], [255, 0, 0])
        time.sleep(1)
        
        print("Setting RGB to green (0, 255, 0)...")
        controller.set_channels([1, 2, 3], [0, 255, 0])
        time.sleep(1)
        
        print("Setting RGB to blue (0, 0, 255)...")
        controller.set_channels([1, 2, 3], [0, 0, 255])
        time.sleep(1)
        
        print("Turning off all channels...")
        controller.blackout()
        time.sleep(1)
        
        print("✓ DMX output test completed!")
        print()
        
        # Close controller
        print("Closing DMX controller...")
        controller.close()
        print("✓ Controller closed successfully!")
        
        print("\n🎉 All tests passed! Your DMXKing ultraDMX MAX is working correctly.")
        print("\nNext steps:")
        print("1. Connect your DMX fixtures")
        print("2. Update your profile configuration")
        print("3. Run your Oculizer application")
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Check that your DMXKing ultraDMX MAX is connected")
        print("2. Verify the port in oculizer/light/dmx_config.py")
        print("3. Try a different USB port")
        print("4. Check device permissions (Linux/macOS)")
        print("5. Install drivers if needed")
        
        # Show available ports
        print(f"\nTry these ports for {system}:")
        for port in suggested_ports:
            print(f"  - {port}")
        
        return False
    
    return True

def main():
    """Main test function."""
    print("DMXKing ultraDMX MAX Test")
    print("Make sure your DMXKing ultraDMX MAX is connected!")
    print()
    
    input("Press Enter to start the test...")
    print()
    
    success = test_dmx_connection()
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
