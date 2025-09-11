# Xbox Controller Robot Interface

A comprehensive Xbox controller interface for controlling your mecanum wheel robot with a GUI showing camera stream and controls.

## Features

- **Xbox Controller Support**: Full Xbox controller integration with intuitive controls
- **Live Camera Stream**: Real-time video feed from robot in the GUI
- **Power Saving Mode**: Automatically puts motor drivers in standby after 10 seconds of no input
- **Visual Interface**: Clean GUI showing controls, status, and current values
- **Robust Connection**: Automatic reconnection and error handling

## Xbox Controller Mapping

| Control | Function |
|---------|----------|
| **Left Stick** | Robot Movement (Forward/Back, Strafe Left/Right) |
| **Right Stick X** | Robot Rotation (Turn Left/Right) |
| **Right Trigger (RT)** | Boost Speed (up to 100%) |
| **Left Trigger (LT)** | Slow Mode (down to 30%) |
| **A Button** | Emergency Stop |
| **Back Button** | Reconnect Controller |

## Setup Instructions

### Windows Setup

1. **Connect Xbox Controller**
   - Connect your Xbox controller to Windows (USB or wireless)
   - Make sure Windows recognizes it in Device Manager

2. **Install Required Packages**
   ```powershell
   python install_requirements.py
   ```
   
   Or manually:
   ```powershell
   pip install pygame opencv-python pillow pynput
   ```

3. **Update Configuration**
   - Open `xbox_control.py`
   - Update `PI_IP` to your Raspberry Pi's IP address
   - Update `PC_VIDEO_IP` in the Pi server to your Windows laptop's IP

4. **Install GStreamer (for video)**
   - Download from: https://gstreamer.freedesktop.org/download/
   - Install the runtime and development packages
   - Add to your system PATH

### Raspberry Pi Setup

1. **Copy the server file**
   ```bash
   scp mecanum_server_xbox.py pi@192.168.1.94:~/
   ```

2. **Update Configuration**
   - Edit `mecanum_server_xbox.py` on the Pi
   - Set `PC_VIDEO_IP` to your Windows laptop's IP address
   - Verify motor pin assignments in `MOTORS` dict
   - Adjust `STBY_PINS` if different

3. **Install Dependencies**
   ```bash
   sudo apt update
   sudo apt install pigpio gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good
   ```

4. **Enable pigpiod**
   ```bash
   sudo systemctl enable pigpiod
   sudo systemctl start pigpiod
   ```

## Usage

### Starting the System

1. **Start the Pi Server**
   ```bash
   python3 mecanum_server_xbox.py
   ```

2. **Start the Windows Client**
   ```powershell
   python xbox_control.py
   ```

### Using the Interface

- The GUI will open showing:
  - **Left side**: Live camera feed from robot
  - **Right side**: Controller status, controls guide, and current values
  
- Connect your Xbox controller and it should be detected automatically
- Use the controller as mapped above to control the robot
- The interface shows real-time values for all inputs

### Power Saving

The system automatically:
- Enters standby mode after 10 seconds of no controller input
- Disables motor driver chips (STBY pins go LOW)
- Wakes up immediately when controller input is detected
- Shows power state in the console

## Troubleshooting

### Controller Issues
- **Not detected**: Check Device Manager, try different USB port
- **Reconnect**: Use the "Reconnect Controller" button in GUI
- **Lag**: Make sure controller drivers are updated

### Video Stream Issues
- **No video**: Check GStreamer installation and PATH
- **Poor quality**: Adjust bitrate in Pi server configuration
- **Lag**: Reduce resolution or framerate in server

### Network Issues
- **Can't connect**: Verify IP addresses in both files
- **Timeout**: Check firewall settings on Windows
- **Packet loss**: Ensure stable WiFi connection

### Robot Issues
- **Motors don't move**: Check pigpiod is running on Pi
- **Wrong direction**: Adjust `DIR_OFFSET` values in server
- **Weak movement**: Check power supply and connections

## Configuration Options

### Speed Settings
```python
BASE_SPEED = 0.6    # Normal speed (60%)
BOOST_SPEED = 1.0   # Boost speed (100%)
```

### Power Saving
```python
POWER_SAVE_TIMEOUT_S = 10.0  # Standby after 10 seconds
```

### Network
```python
SEND_HZ = 30  # Command rate (30 Hz)
PI_PORT = 5005  # UDP port
```

### Motor Configuration
```python
# Adjust if wheels turn wrong direction
DIR_OFFSET = {"A": 1, "B": 1, "C": 1, "D": 1}

# Standby pins for power saving
STBY_PINS = [9, 11]
```

## File Structure

```
ICCode/
├── xbox_control.py           # Windows Xbox controller client with GUI
├── mecanum_server_xbox.py    # Pi server with power saving
├── install_requirements.py   # Package installer
├── control.py               # Original keyboard control (backup)
└── README.md                # This file
```

## Safety Features

- **Emergency Stop**: A button stops all motors immediately
- **Command Timeout**: Robot stops if no commands received for 0.8 seconds
- **Power Saving**: Motor drivers enter standby to save power and heat
- **Connection Monitoring**: GUI shows connection status for controller and robot

Enjoy controlling your robot with the Xbox controller! 🎮🤖
