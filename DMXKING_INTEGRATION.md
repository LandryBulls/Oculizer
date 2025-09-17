# DMXKing ultraDMX MAX Integration

This document explains how to use the DMXKing ultraDMX MAX with Oculizer.

## Overview

The DMXKing ultraDMX MAX is a USB DMX interface that uses the Enttec USB DMX Pro protocol. Since PyDMXControl doesn't natively support this device, we've created a custom `EnttecProController` class that implements the Enttec Pro protocol.

## Files Added/Modified

### New Files
- `oculizer/light/enttec_controller.py` - Custom controller for DMXKing ultraDMX MAX
- `oculizer/light/dmx_config.py` - Configuration settings for DMX interface
- `test_dmxking.py` - Test script to verify DMXKing ultraDMX MAX connection

### Modified Files
- `oculizer/light/control.py` - Updated to use EnttecProController instead of OpenDMXController

## Setup Instructions

### 1. Install Required Dependencies

Make sure you have the required Python packages:

```bash
pip install pyserial
```

### 2. Configure the DMX Port

Edit `oculizer/light/dmx_config.py` and update the port setting:

```python
DMX_CONFIG = {
    'port': '/dev/ttyUSB0',  # Change this to your actual port
    'baudrate': 57600,
    'timeout': 1.0,
}
```

**Common port assignments:**
- **Linux**: `/dev/ttyUSB0`, `/dev/ttyUSB1`, `/dev/ttyACM0`
- **Windows**: `COM3`, `COM4`, `COM5`
- **macOS**: `/dev/cu.usbserial-*`, `/dev/cu.usbmodem*`

### 3. Find Your Device Port

**Linux:**
```bash
ls /dev/ttyUSB*
ls /dev/ttyACM*
```

**Windows:**
- Check Device Manager under "Ports (COM & LPT)"

**macOS:**
```bash
ls /dev/cu.*
```

### 4. Test the Connection

Run the test script to verify your DMXKing ultraDMX MAX is working:

```bash
python test_dmxking.py
```

This will:
- Test the serial connection
- Send test DMX data
- Verify the device responds correctly

### 5. Run Oculizer

Once the test passes, you can run Oculizer normally:

```bash
python run_full.py
# or any other run script
```

## Troubleshooting

### Connection Issues

1. **Device not found**: Check that the DMXKing ultraDMX MAX is connected and powered
2. **Wrong port**: Update the port in `dmx_config.py` to match your system
3. **Permission denied** (Linux/macOS): Add your user to the dialout group:
   ```bash
   sudo usermod -a -G dialout $USER
   ```
   Then log out and back in.

4. **Driver issues**: Install the appropriate drivers for your operating system

### DMX Output Issues

1. **No DMX signal**: Check that DMX cables are properly connected
2. **Wrong DMX address**: Verify your fixture DMX addresses match your profile
3. **Signal quality**: Use proper DMX cables and avoid long cable runs without termination

## Technical Details

### Enttec USB DMX Pro Protocol

The DMXKing ultraDMX MAX uses the Enttec USB DMX Pro protocol over a Virtual COM Port (VCP). The protocol uses:

- **Baudrate**: 57600
- **Message format**: Start byte (0x7E) + Command + Length + Data + End byte (0xE7)
- **DMX data**: 512 channels + start code

### Controller Features

The `EnttecProController` class provides:

- Serial communication with DMXKing ultraDMX MAX
- DMX channel control (single and multiple channels)
- Widget parameter reading
- Proper connection management
- Error handling and retry logic

### Fixture Support

All existing fixture types are supported:
- **Dimmer**: Single channel dimming
- **RGB**: 6-channel RGB control
- **Strobe**: 2-channel strobe control
- **Laser**: 10-channel laser control
- **Rockville864**: 39-channel Rockville fixture control

## Performance Notes

- The EnttecProController sends DMX data at the standard DMX512 rate (~44Hz)
- Serial communication adds minimal latency
- The controller automatically handles DMX packet formatting
- Connection retry logic ensures reliable operation

## Compatibility

This integration has been tested with:
- DMXKing ultraDMX MAX
- Enttec USB DMX Pro protocol compatible devices
- Python 3.7+
- PySerial 3.0+

## Support

If you encounter issues:
1. Run the test script first
2. Check the troubleshooting section
3. Verify your DMX setup
4. Check the DMXKing ultraDMX MAX manual for device-specific issues
