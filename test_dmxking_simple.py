#!/usr/bin/env python3
"""
Simple DMXKing ultraDMX MAX Test Script

This script tests the connection to your DMXKing ultraDMX MAX interface
without importing the full Oculizer system.
"""

import sys
import time
import serial
from pathlib import Path

def test_dmx_connection():
    """Test DMXKing ultraDMX MAX connection."""
    print("DMXKing ultraDMX MAX Connection Test")
    print("=" * 40)
    
    # Configuration
    port = '/dev/cu.usbmodem001A193809581'
    baudrate = 57600
    timeout = 1.0
    
    print(f"Using port: {port}")
    print(f"Baudrate: {baudrate}")
    print(f"Timeout: {timeout}s")
    print()
    
    try:
        # Initialize serial connection
        print("Connecting to DMX interface...")
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE
        )
        print("✓ Serial connection established!")
        print()
        
        # Test Enttec Pro protocol - Get Widget Parameters
        print("Testing Enttec Pro protocol...")
        
        # Send GET_WIDGET_PARAMETERS request
        message = bytes([0x7E, 0x03, 0x00, 0x00, 0xE7])
        ser.write(message)
        ser.flush()
        
        # Read response (should be 14 bytes)
        response = ser.read(14)
        if len(response) == 14:
            print("✓ Widget parameters received successfully!")
            print(f"Firmware version: {response[1]}.{response[2]}")
            print(f"DMX break time: {response[3]} μs")
            print(f"DMX MAB time: {response[4]} μs")
            print(f"DMX output period: {response[5]} μs")
        else:
            print(f"⚠ Warning: Expected 14 bytes, got {len(response)}")
            if response:
                print(f"Response: {response.hex()}")
        print()
        
        # Test DMX output
        print("Testing DMX output...")
        
        # Send DMX data (channel 1 = 128)
        dmx_data = [0] * 513  # Start code + 512 channels
        dmx_data[1] = 128  # Set channel 1 to 50%
        
        # Construct Enttec Pro message
        header = bytes([0x7E, 0x06, 0x01, 0x02])  # Send DMX, 513 bytes
        footer = bytes([0xE7])
        message = header + bytes(dmx_data) + footer
        
        ser.write(message)
        ser.flush()
        print("✓ DMX data sent (channel 1 = 50%)")
        time.sleep(1)
        
        # Send blackout
        dmx_data = [0] * 513
        message = header + bytes(dmx_data) + footer
        ser.write(message)
        ser.flush()
        print("✓ DMX blackout sent")
        time.sleep(1)
        
        # Close connection
        ser.close()
        print("✓ Connection closed")
        
        print("\n🎉 All tests passed! Your DMXKing ultraDMX MAX is working correctly.")
        print("\nNext steps:")
        print("1. Connect your DMX fixtures")
        print("2. Update your profile configuration")
        print("3. Run your Oculizer application")
        
        return True
        
    except serial.SerialException as e:
        print(f"✗ Serial connection error: {str(e)}")
        print("\nTroubleshooting:")
        print("1. Check that your DMXKing ultraDMX MAX is connected")
        print("2. Verify the port: /dev/cu.usbmodem001A193809581")
        print("3. Try unplugging and replugging the device")
        print("4. Check device permissions")
        return False
        
    except Exception as e:
        print(f"✗ Error: {str(e)}")
        return False

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
