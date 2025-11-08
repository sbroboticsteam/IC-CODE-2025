# Raspberry Pi Setup Instructions

The Raspberry Pi serves as the robot's onboard computer, managing motor control, IR weapon/sensor systems, camera streaming, servo control, and network communication with the laptop and game viewer.

## Prerequisites

**Before beginning, contact your team lead for:**
- Raspberry Pi hostname or IP address
- SSH credentials (username/password)
- Team configuration details (Team ID, robot name)
- Network configuration (router IP, Game Viewer IP)

## Initial Access

### SSH into the Raspberry Pi

**From Windows (PowerShell):**
```powershell
ssh pi@[ROBOT_IP_ADDRESS]
# Example: ssh pi@192.168.50.10
```

**From Linux/Mac:**
```bash
ssh pi@[ROBOT_IP_ADDRESS]
```

Default credentials (if not changed):
- Username: `pi`
- Password: `raspberry`

**Note:** Change default password immediately after first login using `passwd`

## System Setup

### 1. Update System Packages

```bash
sudo apt update
sudo apt upgrade -y
```

This may take 10-15 minutes depending on how outdated the system is.

### 2. Install pigpio Daemon

pigpio provides hardware-timed GPIO control essential for precise motor control and IR communication.

**Install dependencies:**
```bash
sudo apt install -y git python3-dev python3-setuptools
```

**Build from source:**
```bash
cd ~
git clone https://github.com/joan2937/pigpio.git
cd pigpio
make
sudo make install
```

**Enable pigpio daemon to start on boot:**
```bash
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
```

**Verify installation:**
```bash
sudo pigpiod -v
```

### 3. Install GStreamer

GStreamer handles video encoding and streaming to the laptop.

```bash
sudo apt install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    python3-gst-1.0
```

**Verify installation:**
```bash
gst-launch-1.0 --version
```

### 4. Install Python Dependencies

```bash
pip3 install --upgrade pip
pip3 install pigpio RPi.GPIO
```

**Note:** Do not use virtual environments - install globally for system service compatibility.

### 5. Clone Repository

```bash
cd ~
git clone https://github.com/sbroboticsteam/IC-CODE-2025.git
cd IC-CODE-2025/CompetitionSystem/Pi
```

### 6. Configure Team Settings

Edit the team configuration file:

```bash
nano team_config.json
```

**Example configuration:**
```json
{
  "team": {
    "team_id": 1,
    "team_name": "Team Alpha",
    "robot_name": "Alpha-Bot-01"
  },
  "network": {
    "robot_ip": "192.168.50.10",
    "robot_port": 5005,
    "game_viewer_ip": "192.168.50.87",
    "game_viewer_control_port": 6000,
    "video_stream_port": 5001
  }
}
```

**Important fields:**
- `team_id` - Unique identifier (1-254)
- `robot_ip` - This Pi's IP address
- `game_viewer_ip` - Tournament server IP
- `video_stream_port` - Base port + team_id - 1 (Team 1 = 5001, Team 2 = 5002, etc.)

Save with `Ctrl+O`, exit with `Ctrl+X`

### 7. Set Execution Permissions

```bash
chmod +x start_robot.sh
```

## Running the Robot System

### Manual Start (for testing)

```bash
cd ~/IC-CODE-2025/CompetitionSystem/Pi
sudo python3 main.py
```

Press `Ctrl+C` to stop.

### Automatic Start (using script)

```bash
cd ~/IC-CODE-2025/CompetitionSystem/Pi
./start_robot.sh
```

The script will:
1. Check if pigpiod is running (start if needed)
2. Launch main.py with proper permissions
3. Display system output for monitoring

### Auto-start on Boot (optional)

To have the robot system start automatically when the Pi boots:

1. Create systemd service:
```bash
sudo nano /etc/systemd/system/robot.service
```

2. Add the following content:
```ini
[Unit]
Description=Robot Competition System
After=network.target pigpiod.service

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/IC-CODE-2025/CompetitionSystem/Pi
ExecStart=/usr/bin/python3 /home/pi/IC-CODE-2025/CompetitionSystem/Pi/main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

3. Enable and start the service:
```bash
sudo systemctl enable robot.service
sudo systemctl start robot.service
```

4. Check status:
```bash
sudo systemctl status robot.service
```

## System Architecture

### Module Overview

#### `main.py` - Core System Controller
**Purpose:** Main entry point that initializes and coordinates all subsystems

**Responsibilities:**
- Initializes pigpio daemon connection
- Loads team configuration from `team_config.json`
- Creates and manages all controller instances
- Processes incoming laptop commands via UDP
- Coordinates state transitions (standby, active, disabled)
- Handles graceful shutdown

**Key Features:**
- Timeout detection (auto-standby if no commands for 3 seconds)
- Emergency stop handling
- Command forwarding to appropriate controllers

#### `config_manager.py` - Configuration Handler
**Purpose:** Loads and validates team configuration

**Functionality:**
- Reads `team_config.json`
- Validates required fields
- Provides configuration access to all modules
- Handles missing or malformed configuration

**Configuration Sections:**
- Team information (ID, names)
- Network settings (IPs, ports)
- Hardware pin assignments (motors, servos, GPIOs, IR)
- Camera settings
- Performance tuning parameters

#### `motor_controller.py` - Mecanum Drive System
**Purpose:** Controls 4-wheel mecanum drive base

**Capabilities:**
- Omnidirectional movement (forward/backward, strafe, rotation)
- Speed control with software limiting (0.0 to 1.0)
- Emergency stop functionality
- Standby mode (disables motors)
- Ramp control for smooth acceleration

**Hardware Interface:**
- PWM motor speed control
- Direction pins for each motor
- Supports standard DC motor drivers (L298N, TB6612, etc.)

#### `ir_controller.py` - IR Weapon & Sensor System
**Purpose:** Manages IR transmitter and receiver for laser tag functionality

**Transmitter (Weapon):**
- 38kHz carrier frequency modulation
- Team ID encoding in IR signal
- 2-second cooldown between shots
- Shot counter tracking

**Receiver (Hit Detection):**
- Decodes incoming IR signals
- Validates team IDs (ignores friendly fire)
- Triggers 10-second disable period when hit
- Reports hits to Game Viewer
- Maintains hit log with timestamps

**Game Integration:**
- Tracks game state (active/inactive)
- Only processes hits during active games
- Sends hit reports via UDP to Game Viewer

#### `servo_controller.py` - Servo Management
**Purpose:** Controls servos for mechanisms (arms, grippers, launchers, etc.)

**Features:**
- Pulse-width control (500-2500µs range)
- Position limits (min/max) per servo
- Toggle mode support (min/max positions)
- Up to 2 servos configurable

**Configuration:**
- Individual min/max pulse widths
- GPIO pin assignment per servo
- Position presets for common mechanisms

#### `gpio_controller.py` - General Purpose I/O
**Purpose:** Controls digital outputs for accessories

**Capabilities:**
- 4 general-purpose GPIOs
- 2 dedicated light outputs
- High/Low state control
- Toggle functionality

**Common Uses:**
- LED indicators
- Relay control
- Solenoid activation
- Additional mechanism control

#### `camera_streamer.py` - Video Streaming
**Purpose:** Captures and streams camera feed to laptop and Game Viewer

**Technical Details:**
- H.264 video encoding for low latency
- UDP streaming (RTP protocol)
- Configurable resolution and framerate
- Auto-start when laptop connects
- Dual streaming (laptop + Game Viewer)

**GStreamer Pipeline:**
```
Camera → H.264 Encoder → RTP Packager → UDP Multicast
```

**Default Settings:**
- Resolution: 640x480
- Framerate: 30 fps
- Bitrate: 1 Mbps

#### `game_client.py` - Game Server Communication
**Purpose:** Maintains connection with Game Viewer for tournament management

**Functionality:**
- Team registration on startup
- Heartbeat transmission (every 2 seconds)
- Game state synchronization
- Point updates reception
- Ready check response

**Message Types:**
- `REGISTER` - Initial team registration
- `HEARTBEAT` - Keep-alive signal
- `GAME_START` - Match begin notification
- `GAME_END` - Match end notification
- `POINTS_UPDATE` - Score synchronization
- `READY_CHECK` - Pre-match ready status

## Hardware Pin Assignments

Pin assignments are configured in `team_config.json`. Typical layout:

**Motors:** (4x for mecanum)
- Motor 1 PWM: GPIO 12, Direction: GPIO 16, GPIO 20
- Motor 2 PWM: GPIO 13, Direction: GPIO 19, GPIO 26
- Motor 3 PWM: GPIO 18, Direction: GPIO 23, GPIO 24
- Motor 4 PWM: GPIO 19, Direction: GPIO 5, GPIO 6

**IR System:**
- Transmitter: GPIO 17
- Receiver: GPIO 27

**Servos:**
- Servo 1: GPIO 22
- Servo 2: GPIO 25

**GPIOs:**
- GPIO 1-4: Configurable
- Lights: GPIO pins for LED control

**Note:** Verify your specific hardware configuration before modifying pins.

## Network Communication

### UDP Ports Summary

**Robot (Pi) Listening:**
- Port 5005 - Laptop control commands

**Robot (Pi) Sending:**
- Port 5000+ - Video stream to laptop (5000 + team_id)
- Port 6000 - Hit reports to Game Viewer
- Port 6000 - Registration/heartbeat to Game Viewer

**Protocol:**
- All messages use JSON encoding
- UDP for low-latency communication
- No acknowledgment required (best-effort delivery)

### Message Flow

**Laptop → Pi (Control):**
```json
{
  "type": "CONTROL",
  "vx": 0.5,
  "vy": 0.0,
  "vr": 0.0,
  "fire": false,
  "servo1_toggle": true,
  "gpio": [false, false, false, false]
}
```

**Pi → Game Viewer (Hit Report):**
```json
{
  "type": "HIT_REPORT",
  "data": {
    "attacking_team": 2,
    "defending_team": 1,
    "timestamp": 1699484523.45
  }
}
```

## Troubleshooting

### pigpiod Not Running
```bash
sudo systemctl status pigpiod
sudo systemctl start pigpiod
```

### Permission Denied Errors
Run with sudo:
```bash
sudo python3 main.py
```

### Camera Not Streaming
1. Check camera connection: `vcgencmd get_camera`
2. Enable camera in raspi-config: `sudo raspi-config` → Interface Options → Camera
3. Reboot after enabling: `sudo reboot`

### Network Connection Issues
1. Verify IP address: `ip addr show`
2. Check network configuration in `team_config.json`
3. Test connectivity: `ping [LAPTOP_IP]`
4. Verify firewall: `sudo ufw status`

### GPIO Control Not Working
1. Verify pigpiod is running
2. Check pin numbers in configuration (BCM numbering)
3. Test with `gpio readall` to verify pin states
4. Check for hardware conflicts (pins already in use)

### IR System Not Responding
1. Verify IR LED is connected correctly (check polarity)
2. Test IR receiver with TV remote (should blink on receive)
3. Check pin configuration matches hardware
4. Verify 38kHz carrier frequency in code

## Performance Optimization

### Reduce CPU Usage
- Lower camera resolution in `team_config.json`
- Decrease video framerate
- Disable unused features (servos, GPIOs)

### Improve Response Time
- Use wired Ethernet instead of WiFi when possible
- Reduce network congestion
- Increase control update rate (SEND_HZ in laptop code)

### Battery Life
- Disable camera streaming when not needed
- Reduce motor PWM frequency
- Implement sleep modes during standby

## Safety Considerations

1. **Emergency Stop**: Laptop ESC key triggers immediate motor shutoff
2. **Timeout Protection**: Robot enters standby after 3 seconds of no commands
3. **Disable on Hit**: 10-second lockout prevents runaway robots
4. **Low Voltage Cutoff**: Monitor battery voltage to prevent over-discharge

## Logs and Debugging

**View live system output:**
```bash
sudo journalctl -u robot.service -f
```

**Check for errors:**
```bash
sudo journalctl -u robot.service --since "5 minutes ago"
```

**Debug mode:**
Add verbose logging by modifying `main.py` - increase print statement frequency

## Updates and Maintenance

**Pull latest code:**
```bash
cd ~/IC-CODE-2025
git pull origin main
```

**Restart system:**
```bash
sudo systemctl restart robot.service
```

**Backup configuration:**
```bash
cp team_config.json team_config.json.backup
```

## Support

For Raspberry Pi setup assistance:
1. Contact your team lead
2. Verify all installation steps were completed
3. Check system logs for error messages
4. Test individual components in isolation

## Next Steps

After setup is complete:
1. Verify all hardware connections
2. Test motor control with laptop interface
3. Calibrate servo positions
4. Test IR weapon and hit detection
5. Verify camera streaming to laptop
6. Register with Game Viewer for tournament
