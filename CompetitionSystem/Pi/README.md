# 🤖 Competition Robot - Raspberry Pi Code

## 📋 Overview
This is the complete robot control system for the laser tag competition. The system includes:
- **Motor Control**: Mecanum drive with PWM speed control
- **IR System**: Transmit/receive for laser tag gameplay
- **Servo Control**: 2 configurable servo channels
- **GPIO Control**: 4 extra GPIOs + 2 status lights
- **Camera Streaming**: Dual output to laptop and game viewer
- **Game Communication**: Real-time updates with game viewer

## 📁 File Structure
```
Pi/
├── main.py                  # Main entry point - RUN THIS
├── config_manager.py        # Configuration loader
├── motor_controller.py      # Mecanum drive control
├── ir_controller.py         # IR system (PROTECTED)
├── servo_controller.py      # Servo control
├── gpio_controller.py       # GPIO and lights
├── camera_streamer.py       # Video streaming
├── game_client.py           # Game viewer comm (PROTECTED)
├── team_config.json         # YOUR CONFIGURATION FILE
├── start_robot.sh           # Startup script
└── README.md                # This file
```

## 🔧 Setup Instructions

### 1. Install Dependencies
```bash
sudo apt-get update
sudo apt-get install -y python3-pip python3-pigpio gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good gstreamer1.0-plugins-bad

pip3 install pigpio
```

### 2. Enable pigpiod
```bash
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
```

### 3. Configure Your Robot
Edit `team_config.json` and fill in:
- Team ID and name
- Network IPs (laptop, game viewer)
- GPIO pins for servos, lights, and extra GPIOs
- Motor direction offsets (if needed)

**DO NOT MODIFY** the motor pin assignments or IR system settings!

### 4. Test Configuration
```bash
python3 -c "from config_manager import ConfigManager; c = ConfigManager(); print('Config valid!' if c.config else 'Config invalid!')"
```

### 5. Run the Robot
```bash
chmod +x start_robot.sh
./start_robot.sh
```

Or directly:
```bash
sudo pigpiod
python3 main.py
```

## ⚙️ Configuration Guide

### Team Settings
```json
"team": {
  "team_id": 1,          # 1-255, must be unique
  "team_name": "Team Alpha",
  "robot_name": "Alpha-1"
}
```

### Network Settings
```json
"network": {
  "laptop_ip": "192.168.1.100",              # Your laptop IP
  "laptop_port": 4999,                        # Laptop control port
  "laptop_video_port": 5100,                  # Laptop video port
  "game_viewer_ip": "192.168.1.50",          # Game viewer IP
  "game_viewer_video_port": 5001,            # GV video (5000 + team_id)
  "game_viewer_control_port": 6000,          # GV control port
  "robot_listen_port": 5005                   # Robot listen port
}
```

### Servo Configuration
```json
"servo_1": {
  "gpio": 13,                # BCM GPIO pin
  "min_pulse_us": 1000,      # Min pulse width
  "max_pulse_us": 2000,      # Max pulse width
  "default_position": 1500,  # Center position
  "enabled": true            # Enable/disable
}
```

### Lights Configuration
```json
"d1": {
  "gpio": 21,               # BCM GPIO pin
  "initial_state": 0,       # 0=off, 1=on
  "enabled": true           # Enable/disable
}
```

### Extra GPIO Configuration
```json
"gpio_1": {
  "gpio": 14,                        # BCM GPIO pin
  "mode": "output",                  # "input" or "output"
  "initial_state": 0,                # For outputs
  "pull": "none",                    # "up", "down", or "none" for inputs
  "enabled": true,
  "description": "Custom sensor"     # Your description
}
```

## 🎮 System Features

### Motor Control
- **Mecanum drive** with omnidirectional movement
- **PWM speed control** with configurable min/max duty cycles
- **Direction offsets** for motor polarity correction
- **Standby mode** for power saving

### IR System (Protected)
- **38kHz carrier frequency** for reliable transmission
- **8-bit team ID encoding**
- **Self-hit filtering** (won't register hits from own team)
- **Hit logging** with timestamps
- **7-second disable time** when hit
- **Weapon cooldown** (500ms between shots)
- **Automatic GV notification** on hits

### Servo Control
- **1000-2000μs pulse width** control
- **Normalized (-1 to 1)** or percentage (0-100) input
- **Independent control** of two servos

### GPIO & Lights
- **4 configurable GPIOs** - set as input or output
- **2 status lights** (D1, D2)
- **PWM support** on GPIO outputs
- **Pull-up/down** resistors for inputs

### Camera Streaming
- **Dual output** using GStreamer `tee` element
- **H.264 encoding** for low latency
- **1280x720 @ 30fps** (configurable)
- **Streams to both** laptop and game viewer simultaneously

### Game Communication
- **Auto-registration** with game viewer
- **Heartbeat system** (1 Hz)
- **Ready check** response
- **Points tracking** (kills, deaths)
- **Hit reports** sent automatically
- **Game start/end** notifications

## 🔒 Protected Files

The following files are **READ-ONLY** and should not be modified by teams:
- `ir_controller.py` - IR transmission/reception protocol
- `game_client.py` - Game viewer communication

These files have restricted permissions and are integrity-checked.

## 🐛 Troubleshooting

### pigpiod not running
```bash
sudo pigpiod
```

### Camera not streaming
```bash
# Test camera
rpicam-vid -t 5000 -o test.h264

# Check GStreamer
gst-launch-1.0 --version
```

### GPIO permissions error
```bash
sudo adduser $USER gpio
sudo reboot
```

### Network issues
```bash
# Test connection to laptop
ping <laptop_ip>

# Test connection to game viewer
ping <game_viewer_ip>

# Check UDP port
sudo netstat -ulnp | grep 5005
```

### Motor not working
- Check `DIR_OFFSET` values in config
- Verify standby pins are high
- Test motors individually with `motor_controller.py`

### IR not firing
- Check if robot is hit (can't fire when disabled)
- Verify transmitter GPIO is correct
- Check weapon cooldown (500ms between shots)

## 📊 System Status

The system provides real-time status through:
1. **Console output** - detailed logging
2. **Network responses** - status sent to laptop
3. **Status lights** - D1/D2 for visual feedback
4. **Game viewer** - points and hit tracking

## 🎯 Competition Rules

- **7-second disable** when hit by another team
- **Self-hits ignored** (your own IR won't disable you)
- **500ms weapon cooldown** between shots
- **Points awarded** by game viewer based on hits
- **Auto-respawn** after disable timer expires

## 🆘 Support

For technical support during the competition:
1. Check console output for error messages
2. Verify `team_config.json` is valid
3. Ensure all network IPs are correct
4. Contact competition officials

## 📝 License

Competition code - For educational use only.

---
**Good luck in the competition! 🏆**
