# 🎯 LASER TAG ROBOT COMPETITION SYSTEM

## 📋 System Overview

This is a complete competition system for laser tag robotics featuring:
- **Multi-Robot Support**: Up to 255 teams can compete simultaneously
- **Real-Time Video**: Dual-stream camera to laptop and game viewer
- **Hit Detection**: IR-based laser tag with automatic scoring
- **Game Management**: Centralized game viewer for tournament control
- **Modular Design**: Separate Pi, Laptop, and Game Viewer applications

## 🏗️ Architecture

```
┌─────────────────┐         ┌─────────────────┐
│   RASPBERRY PI  │◄───────►│     LAPTOP      │
│   (Robot Code)  │  UDP    │  (Keyboard GUI) │
│                 │  5005   │                 │
│  • Motors       │         │  • WASD Control │
│  • IR System    │         │  • Video View   │
│  • Camera       │         │  • Ready System │
│  • Servos/GPIO  │         │  • Debug Mode   │
└────────┬────────┘         └─────────────────┘
         │                           
         │ UDP 6000+                 
         │ Video 5000+team_id        
         ▼                           
┌─────────────────┐
│  GAME VIEWER    │
│  (Tournament)   │
│                 │
│  • 4-Way Video  │
│  • Leaderboard  │
│  • Hit Tracking │
│  • Admin Tools  │
└─────────────────┘
```

## 📦 Components

### 1. Raspberry Pi (`/Pi/`)
- **main.py**: Main entry point
- **config_manager.py**: Configuration loader
- **motor_controller.py**: Mecanum drive
- **ir_controller.py**: IR transmit/receive (PROTECTED)
- **servo_controller.py**: Servo control
- **gpio_controller.py**: GPIO and lights
- **camera_streamer.py**: Dual video output
- **game_client.py**: Game viewer communication (PROTECTED)
- **team_config.json**: Team configuration file

### 2. Laptop (`/Laptop/`)
- **laptop_control.py**: Main GUI application
- **laptop_config.json**: Laptop settings (auto-generated)

### 3. Game Viewer (`/GameViewer/`)
- **game_viewer.py**: Main tournament application
- **game_config.json**: Game settings

## 🚀 Quick Start

### Pi Setup
```bash
cd Pi/
chmod +x start_robot.sh
./start_robot.sh
```

### Laptop Setup
```bash
cd Laptop/
python laptop_control.py
```

### Game Viewer Setup
```bash
cd GameViewer/
python game_viewer.py
```

## ⚙️ Configuration

### Pi Configuration (`team_config.json`)
Teams must configure:
- **Team ID** (1-255, unique)
- **Team Name** and Robot Name
- **Network IPs** (laptop and game viewer)
- **GPIO Pins** (servos, lights, extra GPIOs)

**PROTECTED SETTINGS** (DO NOT CHANGE):
- Motor pins (A, B, C, D)
- IR transmitter/receiver pins
- IR protocol timing

### Laptop Configuration
Configure via GUI Settings button:
- Robot IP and ports
- Video port
- Controller sensitivity
- Team information

### Game Viewer Configuration
- Game modes and rules
- Points per hit
- Game duration
- Network settings

## 🎮 Game Flow

1. **Startup**: All robots connect to Game Viewer
2. **Registration**: Robots send team info, camera starts
3. **Ready Check**: Game Viewer asks teams if ready
4. **Game Start**: Timer begins, robots can fire
5. **Gameplay**: Hits tracked, points awarded
6. **Game End**: Final scores displayed, stats saved

## 🔫 IR Protocol

### Transmission
- **Carrier**: 38kHz modulated IR
- **Encoding**: 10-burst sequence
  - Start burst: 2400μs
  - 8 data bits: 800μs (0) or 1600μs (1)
  - End burst: 2400μs
- **Payload**: 8-bit team ID
- **Cooldown**: 500ms between shots

### Reception
- **3 receivers** for 360° coverage
- **Automatic decoding** with tolerance
- **Self-hit filtering** (own team ID ignored)
- **Hit logging** with timestamps

## 🏆 Scoring System

- **Hit Scored**: +100 points (configurable)
- **Death**: -0 points (no penalty, but tracked)
- **Disable Time**: 7 seconds when hit
- **Respawn**: Automatic after disable timer

## 📊 Features

### Pi Features
- ✅ Mecanum drive with omnidirectional control
- ✅ PWM motor speed control
- ✅ IR laser tag system with hit detection
- ✅ Hit logging with timestamps
- ✅ 2 servo channels (1000-2000μs)
- ✅ 2 status lights (D1, D2)
- ✅ 4 configurable GPIO pins
- ✅ Dual video streaming (laptop + GV)
- ✅ Game viewer integration
- ✅ Heartbeat system
- ✅ Power saving mode
- ✅ Emergency stop
- ✅ Protected code files

### Laptop Features
- ✅ **WASD keyboard controls** (No Xbox controller needed!)
- ✅ Full mecanum drive control
- ✅ Variable speed (Shift for boost)
- ✅ Servo control (Q/Z, E/C keys)
- ✅ GPIO control (1/2/3/4 keys)
- ✅ Video feed display
- ✅ Settings GUI
- ✅ **Debug Mode** for free testing
- ✅ **Game Mode** with ready system
- ✅ Real-time stats display
- ✅ Game status monitoring
- ✅ Ready-up button
- ✅ Points/K/D tracking
- ✅ Hit notifications
- ✅ Connection monitoring
- ✅ Synchronized game timer

### Game Viewer Features
- ✅ 4-way split video display
- ✅ Team name overlays
- ✅ Points leaderboard
- ✅ Hit tracking and logging
- ✅ **Configurable game timer** (Settings dialog)
- ✅ Ready check system
- ✅ Game start/stop controls
- ✅ Admin panel
- ✅ **Duration synchronization** with all laptops
- ✅ Automatic scoring
- ✅ Export game logs

## 🔒 Security

### Protected Files
The following files are READ-ONLY on Pi:
- `ir_controller.py` - IR protocol implementation
- `game_client.py` - Game viewer communication

These files are set to permissions `444` (read-only) by `start_robot.sh` to prevent teams from modifying the competition protocol.

### Integrity Checks
- Configuration validation on startup
- GPIO pin conflict detection
- Network connectivity verification

## 🐛 Troubleshooting

### Pi Issues

**pigpiod not running**
```bash
sudo pigpiod
sudo systemctl enable pigpiod
```

**Camera not working**
```bash
# Test camera
rpicam-vid -t 5000 -o test.h264

# Check camera interface
vcgencmd get_camera
```

**GPIO permissions**
```bash
sudo usermod -a -G gpio $USER
sudo reboot
```

**Network unreachable**
```bash
# Check IP
ip addr show wlan0

# Test connectivity
ping <laptop_ip>
ping <game_viewer_ip>
```

### Laptop Issues

**Keyboard controls not working**
- Ensure laptop window has focus (click on it)
- Check that no text fields are active
- Verify key bindings in `laptop_config.json`

**Video not displaying**
- Check GStreamer installation
- Verify video port matches Pi config
- Ensure firewall allows UDP on video port

**Robot not responding**
- Verify robot IP in settings
- Check network connection
- Ensure Pi is running

### Game Viewer Issues

**Teams not connecting**
- Verify GV IP is reachable
- Check firewall rules
- Ensure all teams use correct GV IP

**Video streams missing**
- Check ports 5001-5255 are open
- Verify GStreamer is installed
- Test individual streams

## 📋 Requirements

### Raspberry Pi
```bash
# System packages
sudo apt-get install python3-pip python3-pigpio \
    gstreamer1.0-tools gstreamer1.0-plugins-*

# Python packages
pip3 install pigpio
```

### Laptop (Windows/Linux)
```bash
# Python packages
pip install pygame

# GStreamer (Windows)
# Download from: https://gstreamer.freedesktop.org/download/

# GStreamer (Linux)
sudo apt-get install gstreamer1.0-tools gstreamer1.0-plugins-*
```

### Game Viewer
```bash
# Python packages
pip install tkinter  # Usually included
# OR for PyQt5 version:
pip install PyQt5

# GStreamer (same as laptop)
```

## 📚 Documentation

- [Pi README](Pi/README.md) - Detailed Pi setup
- [Laptop README](Laptop/README.md) - Laptop interface guide
- [Game Viewer README](GameViewer/README.md) - Tournament management

## 🎯 Competition Rules

1. **Team Registration**: Each team gets unique ID (1-255)
2. **Safety**: Emergency stop available at all times
3. **Disable Time**: 7 seconds when hit
4. **Self-Hits**: Ignored (won't disable own robot)
5. **Weapon Cooldown**: 500ms between shots
6. **Game Duration**: Set by game viewer
7. **Scoring**: Automatic via game viewer
8. **Fair Play**: No modification of protected files

## 🤝 Support

For competition support:
1. Check console output for errors
2. Review configuration files
3. Test network connectivity
4. Contact competition officials

## 📝 Credits

Competition System developed for Robotics Competition 2025

---

**Good luck to all teams! 🏆🤖**
