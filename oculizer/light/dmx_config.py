"""
DMXKing ultraDMX MAX Configuration

This file contains configuration settings for the DMXKing ultraDMX MAX interface.
The system now automatically detects the correct DMX port, but you can still manually
specify a port if needed.

Common port assignments:
- Linux: '/dev/ttyUSB0', '/dev/ttyUSB1', etc.
- Windows: 'COM3', 'COM4', etc.
- macOS: '/dev/cu.usbserial-*', '/dev/cu.usbmodem*'

To find your device port manually:
- Linux: ls /dev/ttyUSB* or ls /dev/ttyACM*
- Windows: Check Device Manager under "Ports (COM & LPT)"
- macOS: ls /dev/cu.*
"""

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

def get_dmx_config():
    """
    Get DMX configuration settings with automatic port detection.
    
    Returns:
        DMX configuration dictionary with detected port
    """
    config = DMX_CONFIG.copy()
    
    # If port is None, try to auto-detect
    if config['port'] is None:
        detected_port = detect_dmx_port()
        if detected_port:
            config['port'] = detected_port
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


def detect_dmx_port():
    """
    Automatically detect the DMX interface port.
    
    Returns:
        Port path if found, None if not found
    """
    print("Scanning for DMX interface...")
    
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
            return port
        else:
            print(f"✗ {port} is not a DMX interface")
    
    print("No DMX interface found on any available port")
    return None
