"""
DMXKing ultraDMX MAX Configuration

This file contains configuration settings for the DMXKing ultraDMX MAX interface.
Update the DMX_PORT setting based on your operating system and USB port assignment.

Common port assignments:
- Linux: '/dev/ttyUSB0', '/dev/ttyUSB1', etc.
- Windows: 'COM3', 'COM4', etc.
- macOS: '/dev/cu.usbserial-*', '/dev/cu.usbmodem*'

To find your device port:
- Linux: ls /dev/ttyUSB* or ls /dev/ttyACM*
- Windows: Check Device Manager under "Ports (COM & LPT)"
- macOS: ls /dev/cu.*
"""

# DMX Controller Configuration
DMX_CONFIG = {
    # Serial port for DMXKing ultraDMX MAX
    # Update this to match your system's port assignment
    'port': '/dev/cu.usbmodem001A193809581',  # DMXKing ultraDMX MAX on macOS
    
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
    """Get DMX configuration settings."""
    return DMX_CONFIG.copy()

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
