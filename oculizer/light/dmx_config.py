"""
DMXKing ultraDMX MAX Configuration

This file contains configuration settings for the DMXKing ultraDMX MAX interface.
The system automatically detects the correct DMX port and caches it for instant
startup on subsequent runs.

Port Detection (Smart Caching):
- First run: Scans all ports to find DMX device (takes 2-5 seconds)
- Subsequent runs: Uses cached port for INSTANT connection (< 0.1 seconds)
- Cache location: config/dmx_port_cache.txt
- Auto-recovery: If cached port fails, automatically rescans all ports
- Manual override: You can manually set DMX_CONFIG['port'] below to skip auto-detection

To clear the cache and force a rescan:
  >>> from oculizer.light.dmx_config import clear_cached_port
  >>> clear_cached_port()

Common port assignments:
- Linux: '/dev/ttyUSB0', '/dev/ttyUSB1', etc.
- Windows: 'COM3', 'COM4', etc.
- macOS: '/dev/cu.usbserial-*', '/dev/cu.usbmodem*'

To find your device port manually:
- Linux: ls /dev/ttyUSB* or ls /dev/ttyACM*
- Windows: Check Device Manager under "Ports (COM & LPT)"
- macOS: ls /dev/cu.*
"""

import os

# DMX Controller Configuration
DMX_CONFIG = {
    # Serial port for DMXKing ultraDMX MAX
    # Set to None for automatic detection, or specify a port manually
    # Examples:
    # 'port': None,  # Auto-detect DMX port (recommended)
    # 'port': '/dev/cu.usbmodem001A193809581',  # Manual port (macOS)
    # 'port': 'COM3',  # Manual port (Windows)
    # 'port': '/dev/ttyUSB0',  # Manual port (Linux)
    'port': None,  # Auto-detect DMX port
    
    # Serial communication settings
    'baudrate': 57600,  # Standard for Enttec Pro protocol
    'timeout': 1.0,     # Serial timeout in seconds
    
    # DMX settings
    'max_channels': 512,  # Maximum DMX channels per universe
}

# Alternative port configurations for different systems
ALTERNATIVE_PORTS = {
    'linux': [
        '/dev/ttyUSB0',
        '/dev/ttyUSB1', 
        '/dev/ttyACM0',
        '/dev/ttyACM1'
    ],
    'windows': [
        'COM1',
        'COM2', 
        'COM3',
        'COM4',
        'COM5'
    ],
    'macos': [
        '/dev/cu.usbserial-*',
        '/dev/cu.usbmodem*',
        '/dev/cu.SLAB_USBtoUART'
    ]
}

def get_dmx_config(skip_cache=False):
    """
    Get DMX configuration settings with automatic port detection.
    
    Args:
        skip_cache: If True, ignore cached port and scan all ports
    
    Returns:
        DMX configuration dictionary with detected port
    """
    config = DMX_CONFIG.copy()
    
    # If port is None, try to auto-detect
    if config['port'] is None:
        detected_port = detect_dmx_port(skip_cache=skip_cache)
        if detected_port:
            config['port'] = detected_port
            if not skip_cache:
                print(f"Using auto-detected DMX port: {detected_port}")
        else:
            # Fallback to manual configuration
            print("Auto-detection failed. Please manually configure the DMX port in dmx_config.py")
            print("Set DMX_CONFIG['port'] to your DMX interface port path")
            raise RuntimeError("No DMX interface found. Please check your connection and configuration.")
    
    return config

def get_port_for_system(system='auto'):
    """
    Get suggested port for the current system.
    
    Args:
        system: 'linux', 'windows', 'macos', or 'auto'
    
    Returns:
        List of suggested ports for the system
    """
    import platform
    
    if system == 'auto':
        system = platform.system().lower()
    
    if system == 'linux':
        return ALTERNATIVE_PORTS['linux']
    elif system == 'windows':
        return ALTERNATIVE_PORTS['windows']
    elif system == 'darwin':  # macOS
        return ALTERNATIVE_PORTS['macos']
    else:
        return ALTERNATIVE_PORTS['linux']  # Default fallback


def scan_available_ports():
    """
    Scan for available serial ports on the current system.
    
    Returns:
        List of available serial port paths
    """
    import serial.tools.list_ports
    import platform
    
    available_ports = []
    
    # Get all available ports
    ports = serial.tools.list_ports.comports()
    
    for port in ports:
        port_path = port.device
        available_ports.append(port_path)
    
    # Also check common port patterns for each OS
    system = platform.system().lower()
    
    if system == 'linux':
        import glob
        # Check for USB serial devices
        usb_ports = glob.glob('/dev/ttyUSB*') + glob.glob('/dev/ttyACM*')
        available_ports.extend(usb_ports)
    elif system == 'darwin':  # macOS
        import glob
        # Check for USB serial devices
        usb_ports = glob.glob('/dev/cu.usb*') + glob.glob('/dev/cu.SLAB*')
        available_ports.extend(usb_ports)
    elif system == 'windows':
        # Windows ports are typically handled by pyserial's list_ports
        pass
    
    # Remove duplicates and sort
    available_ports = sorted(list(set(available_ports)))
    
    return available_ports


def test_dmx_port(port, baudrate=57600, timeout=1.0):
    """
    Test if a port responds to DMX commands.
    
    Args:
        port: Serial port path to test
        baudrate: Serial baud rate
        timeout: Serial timeout
    
    Returns:
        True if port responds to DMX commands, False otherwise
    """
    import serial
    import time
    
    try:
        # Try to connect to the port
        ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE
        )
        
        # Small delay to ensure connection is stable
        time.sleep(0.1)
        
        # Test DMX protocol - send GET_WIDGET_PARAMETERS request
        message = bytes([0x7E, 0x03, 0x00, 0x00, 0xE7])
        ser.write(message)
        ser.flush()
        
        # Try to read response (any response indicates DMX compatibility)
        response = ser.read(14)
        
        ser.close()
        
        # If we got any response, it's likely a DMX interface
        return len(response) > 0
        
    except Exception:
        return False


def get_cached_port_path():
    """Get the path to the cached DMX port file."""
    cache_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'config')
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, 'dmx_port_cache.txt')


def load_cached_port():
    """
    Load the last known working DMX port from cache.
    
    Returns:
        Cached port path if exists, None otherwise
    """
    try:
        cache_file = get_cached_port_path()
        if os.path.exists(cache_file):
            with open(cache_file, 'r') as f:
                cached_port = f.read().strip()
                if cached_port:
                    return cached_port
    except Exception as e:
        print(f"Warning: Could not read DMX port cache: {e}")
    return None


def save_cached_port(port):
    """
    Save the working DMX port to cache for faster startup next time.
    
    Args:
        port: The port path to cache
    """
    try:
        cache_file = get_cached_port_path()
        with open(cache_file, 'w') as f:
            f.write(port)
        print(f"💾 Saved DMX port to cache: {port}")
    except Exception as e:
        print(f"Warning: Could not save DMX port cache: {e}")


def clear_cached_port():
    """
    Clear the cached DMX port. Use this if you need to force a full port scan.
    """
    try:
        cache_file = get_cached_port_path()
        if os.path.exists(cache_file):
            os.remove(cache_file)
            print("🗑️  Cleared DMX port cache")
            return True
    except Exception as e:
        print(f"Warning: Could not clear DMX port cache: {e}")
    return False


def detect_dmx_port(skip_cache=False):
    """
    Automatically detect the DMX interface port.
    Uses cached port for instant connection, or scans all ports if needed.
    
    Args:
        skip_cache: If True, ignore cache and scan all ports
    
    Returns:
        Port path if found, None if not found
    """
    # Try cached port first (unless explicitly skipped)
    if not skip_cache:
        cached_port = load_cached_port()
        if cached_port:
            print(f"⚡ Using cached DMX port: {cached_port} (instant connect!)")
            return cached_port
    
    # No cache or cache skipped - do full scan
    print("🔎 Scanning for DMX interface...")
    
    # Get all available ports
    available_ports = scan_available_ports()
    
    if not available_ports:
        print("No serial ports found")
        return None
    
    print(f"Found {len(available_ports)} serial ports: {', '.join(available_ports)}")
    
    # Test each port for DMX compatibility
    for port in available_ports:
        print(f"Testing port {port}...")
        if test_dmx_port(port):
            print(f"✓ DMX interface found on {port}")
            # Save this port to cache for next time
            save_cached_port(port)
            return port
        else:
            print(f"✗ {port} is not a DMX interface")
    
    print("No DMX interface found on any available port")
    return None
