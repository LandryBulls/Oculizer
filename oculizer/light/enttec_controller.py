"""
EnttecProController for DMXKing ultraDMX MAX

This module provides a custom controller class that implements the Enttec USB DMX Pro protocol
to support DMXKing ultraDMX MAX devices with PyDMXControl.

Author: AI Assistant
Date: 2024
"""

import serial
import time
from typing import Optional, List


class EnttecProController:
    """
    Custom controller for DMXKing ultraDMX MAX using Enttec USB DMX Pro protocol.
    
    The ultraDMX MAX uses a Virtual COM Port (VCP) driver and communicates via
    the Enttec USB DMX Pro protocol over serial connection.
    """
    
    # Enttec Pro protocol constants
    START_OF_MESSAGE = 0x7E
    END_OF_MESSAGE = 0xE7
    SEND_DMX_RQ = 0x06
    RECEIVE_DMX_ON_CHANGE = 0x05
    RECEIVE_DMX_ON_CHANGE_ONLY = 0x09
    GET_WIDGET_PARAMETERS = 0x03
    SET_WIDGET_PARAMETERS = 0x04
    SEND_RDM_DISCOVERY_REQUEST = 0x10
    
    def __init__(self, port: str, baudrate: int = 57600, timeout: float = 1.0):
        """
        Initialize the Enttec Pro controller.
        
        Args:
            port: Serial port path (e.g., '/dev/ttyUSB0' on Linux, 'COM3' on Windows)
            baudrate: Serial communication baud rate (default: 57600)
            timeout: Serial timeout in seconds
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial: Optional[serial.Serial] = None
        self.dmx_data = [0] * 513  # DMX universe (512 channels + start code)
        self.dmx_data[0] = 0  # Start code
        
        # Initialize serial connection
        self._connect()
        
        # Get widget parameters to verify connection
        self._get_widget_parameters()
    
    def _connect(self):
        """Establish serial connection to the DMX interface."""
        try:
            self.serial = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            print(f"Connected to DMX interface on {self.port}")
            
            # Small delay to ensure connection is stable
            time.sleep(0.1)
            
        except serial.SerialException as e:
            raise IOError(f"Failed to connect to DMX interface on {self.port}: {str(e)}")
    
    def _get_widget_parameters(self):
        """Get widget parameters to verify the connection."""
        if not self.serial:
            return
            
        try:
            # Send GET_WIDGET_PARAMETERS request
            message = bytes([self.START_OF_MESSAGE, self.GET_WIDGET_PARAMETERS, 0x00, 0x00, self.END_OF_MESSAGE])
            self.serial.write(message)
            self.serial.flush()
            
            # Read response (should be 14 bytes)
            response = self.serial.read(14)
            if len(response) == 14:
                print("Widget parameters received successfully")
                print(f"Firmware version: {response[1]}.{response[2]}")
                print(f"DMX break time: {response[3]} μs")
                print(f"DMX MAB time: {response[4]} μs")
                print(f"DMX output period: {response[5]} μs")
            else:
                print("Warning: Could not read widget parameters")
                
        except Exception as e:
            print(f"Warning: Error getting widget parameters: {str(e)}")
    
    def send_dmx(self, data: List[int], start_channel: int = 1):
        """
        Send DMX data to the interface.
        
        Args:
            data: List of DMX values (0-255)
            start_channel: Starting DMX channel (1-512)
        """
        if not self.serial:
            raise IOError("Serial connection not established")
        
        # Validate input
        if start_channel < 1 or start_channel > 512:
            raise ValueError("Start channel must be between 1 and 512")
        
        if not data:
            return
        
        # Update internal DMX data
        end_channel = min(start_channel + len(data) - 1, 512)
        for i, value in enumerate(data):
            channel = start_channel + i
            if channel <= 512:
                self.dmx_data[channel] = max(0, min(255, int(value)))
        
        # Send DMX data using Enttec Pro protocol
        self._send_dmx_packet()
    
    def _send_dmx_packet(self):
        """Send DMX packet using Enttec Pro protocol."""
        if not self.serial:
            return
        
        try:
            # Calculate packet size (512 channels + start code)
            packet_size = 513
            
            # Construct message header
            header = bytes([
                self.START_OF_MESSAGE,
                self.SEND_DMX_RQ,
                packet_size & 0xFF,        # LSB of packet size
                (packet_size >> 8) & 0xFF  # MSB of packet size
            ])
            
            # Convert DMX data to bytes
            dmx_bytes = bytes(self.dmx_data)
            
            # Construct complete message
            message = header + dmx_bytes + bytes([self.END_OF_MESSAGE])
            
            # Send message
            self.serial.write(message)
            self.serial.flush()
            
        except Exception as e:
            print(f"Error sending DMX packet: {str(e)}")
    
    def set_channel(self, channel: int, value: int):
        """
        Set a single DMX channel value.
        
        Args:
            channel: DMX channel (1-512)
            value: DMX value (0-255)
        """
        if 1 <= channel <= 512:
            self.dmx_data[channel] = max(0, min(255, int(value)))
            self._send_dmx_packet()
    
    def set_channels(self, channels: List[int], values: List[int]):
        """
        Set multiple DMX channels.
        
        Args:
            channels: List of DMX channel numbers (1-512)
            values: List of DMX values (0-255)
        """
        if len(channels) != len(values):
            raise ValueError("Channels and values lists must have the same length")
        
        for channel, value in zip(channels, values):
            if 1 <= channel <= 512:
                self.dmx_data[channel] = max(0, min(255, int(value)))
        
        self._send_dmx_packet()
    
    def blackout(self):
        """Set all DMX channels to 0."""
        self.dmx_data = [0] * 513
        self.dmx_data[0] = 0  # Keep start code
        self._send_dmx_packet()
    
    def close(self):
        """Close the serial connection."""
        if self.serial and self.serial.is_open:
            # Send blackout before closing
            self.blackout()
            time.sleep(0.1)
            
            self.serial.close()
            print("DMX interface connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
    
    def __del__(self):
        """Destructor to ensure connection is closed."""
        self.close()
