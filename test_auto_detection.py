#!/usr/bin/env python3
"""
Test script for automatic DMX port detection

This script tests the automatic DMX port detection functionality
without running the full Oculizer system.
"""

import sys
from pathlib import Path

# Add the oculizer package to the path
sys.path.insert(0, str(Path(__file__).parent))

from oculizer.light.dmx_config import detect_dmx_port, scan_available_ports, test_dmx_port

def main():
    print("DMX Port Auto-Detection Test")
    print("=" * 40)
    
    # Test port scanning
    print("\n1. Scanning for available ports...")
    ports = scan_available_ports()
    
    if ports:
        print(f"Found {len(ports)} ports:")
        for port in ports:
            print(f"  - {port}")
    else:
        print("No ports found")
        return
    
    # Test DMX detection
    print("\n2. Testing DMX interface detection...")
    dmx_port = detect_dmx_port()
    
    if dmx_port:
        print(f"\n✓ Success! DMX interface detected on: {dmx_port}")
        
        # Test the detected port
        print(f"\n3. Validating detected port...")
        if test_dmx_port(dmx_port):
            print(f"✓ Port {dmx_port} responds to DMX commands")
        else:
            print(f"✗ Port {dmx_port} does not respond to DMX commands")
    else:
        print("\n✗ No DMX interface detected")
        print("\nTroubleshooting:")
        print("- Make sure your DMX interface is connected")
        print("- Check that the correct drivers are installed")
        print("- Try manually specifying the port in dmx_config.py")

if __name__ == "__main__":
    main()
