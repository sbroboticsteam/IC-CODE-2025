# 🚀 INSTALLATION GUIDE - Laser Tag Competition System

## 📋 Table of Contents
1. [Raspberry Pi Setup](#raspberry-pi-setup)
2. [Laptop Setup](#laptop-setup)
3. [Game Viewer Setup](#game-viewer-setup)
4. [Network Configuration](#network-configuration)
5. [Testing](#testing)
6. [Troubleshooting](#troubleshooting)

---

## 🤖 Raspberry Pi Setup

### 1. Operating System
Install Raspberry Pi OS (32-bit or 64-bit) on your Pi
```bash
# Update system
sudo apt-get update
sudo apt-get upgrade -y
```

### 2. Install System Dependencies
```bash
# Install pigpio daemon
sudo apt-get install -y pigpio python3-pigpio

# Install GStreamer
sudo apt-get install -y \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav

# Install rpicam-vid (for Pi Camera Module 3)
sudo apt-get install -y rpicam-apps
```

### 3. Enable Interfaces
```bash
# Enable camera and I2C
sudo raspi-config
# Navigate to Interface Options → Camera → Enable
# Navigate to Interface Options → I2C → Enable
```

### 4. Install Python Dependencies
```bash
pip3 install pigpio
```

### 5. Enable pigpiod at Boot
```bash
sudo systemctl enable pigpiod
sudo systemctl start pigpiod
```

### 6. Configure Team Settings
```bash
cd CompetitionSystem/Pi/
nano team_config.json
```

Edit the following:
- `team_id`: Your unique team ID (1-255)
- `team_name`: Your team name
- `robot_name`: Your robot name
- `laptop_ip`: Your laptop's IP address
- `game_viewer_ip`: Game viewer IP address
- GPIO pins for servos, lights, and extra GPIOs

### 7. Test the System
```bash
# Make startup script executable
chmod +x start_robot.sh

# Test run
./start_robot.sh
```

### 8. Set File Permissions (Automatic)
The startup script automatically sets IR and game client files to read-only.

---

## 💻 Laptop Setup (Windows/Linux)

### Windows Setup

#### 1. Install Python
Download Python 3.9+ from [python.org](https://www.python.org/downloads/)

Make sure to check "Add Python to PATH" during installation!

#### 2. Install GStreamer
Download GStreamer from: https://gstreamer.freedesktop.org/download/

Install both:
- MinGW runtime installer
- Development installer

Add GStreamer to PATH:
```
C:\gstreamer\1.0\msvc_x86_64\bin
```

#### 3. Install Python Packages
```cmd
pip install pygame
```

#### 4. Run Laptop Control
```cmd
cd CompetitionSystem\Laptop\
python laptop_control.py
```

### Linux Setup

#### 1. Install Dependencies
```bash
# Ubuntu/Debian
sudo apt-get install -y \
    python3-pip \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-* \
    python3-pygame

# Or install pygame via pip
pip3 install pygame
```

#### 2. Run Laptop Control
```bash
cd CompetitionSystem/Laptop/
python3 laptop_control.py
```

---

## 🎮 Game Viewer Setup

### Requirements
- Dedicated computer (Windows/Linux)
- Python 3.9+
- GStreamer (for video viewing)
- Network access to all robots

### Installation

#### Windows
```cmd
# Install Python packages
pip install pygame

# Install GStreamer (same as laptop setup)
```

#### Linux
```bash
# Install dependencies
sudo apt-get install -y \
    python3-tk \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-*

# For PyQt5 version (optional)
pip3 install PyQt5
```

### Configuration
```bash
cd CompetitionSystem/GameViewer/
nano game_viewer_config.json
```

Edit:
- `gv_ip`: Game viewer IP (use 0.0.0.0 to listen on all interfaces)
- `gv_port`: Control port (default 6000)
- `game_duration`: Game length in seconds
- `points_per_hit`: Points awarded per hit

### Run Game Viewer
```bash
python3 game_viewer.py
```

---

## 🌐 Network Configuration

### Network Topology
```
Router (192.168.1.1)
├── Game Viewer (192.168.1.50)
├── Team 1 Pi (192.168.1.101)
├── Team 1 Laptop (192.168.1.201)
├── Team 2 Pi (192.168.1.102)
├── Team 2 Laptop (192.168.1.202)
└── ...
```

### Recommended IP Scheme
- **Game Viewer**: `192.168.1.50` (static)
- **Pi robots**: `192.168.1.101-150` (static)
- **Laptops**: `192.168.1.201-250` (DHCP or static)

### Port Usage
| Service | Port | Direction |
|---------|------|-----------|
| Robot Control | 5005 | Laptop → Pi |
| Robot Video | 5100 | Pi → Laptop |
| GV Video (Team 1) | 5001 | Pi → GV |
| GV Video (Team 2) | 5002 | Pi → GV |
| GV Control | 6000 | Pi ↔ GV |
| GV Team Ports | 6001+ | GV → Pi |

### Firewall Rules (if needed)
```bash
# Ubuntu/Linux - allow UDP ports
sudo ufw allow 5000:6100/udp

# Windows - add firewall rule
netsh advfirewall firewall add rule name="LaserTag" dir=in action=allow protocol=UDP localport=5000-6100
```

### Setting Static IP (Raspberry Pi)
```bash
sudo nano /etc/dhcpcd.conf
```

Add at the end:
```
interface wlan0
static ip_address=192.168.1.101/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1 8.8.8.8
```

Reboot:
```bash
sudo reboot
```

---

## ✅ Testing

### Test 1: Pi Self-Test
```bash
# On Pi
cd CompetitionSystem/Pi/

# Test configuration
python3 -c "from config_manager import ConfigManager; c = ConfigManager(); print('Config OK!' if c.config else 'Config FAIL!')"

# Test pigpio
python3 -c "import pigpio; pi = pigpio.pi(); print('pigpio OK!' if pi.connected else 'pigpio FAIL!')"

# Test motors (CAREFUL!)
python3 -c "from motor_controller import MotorController; from config_manager import ConfigManager; import pigpio; pi = pigpio.pi(); cfg = ConfigManager(); m = MotorController(pi, cfg.config); print('Motors OK!'); m.cleanup(); pi.stop()"
```

### Test 2: Network Connectivity
```bash
# From Pi, ping laptop
ping 192.168.1.201

# From Pi, ping game viewer
ping 192.168.1.50

# From laptop, ping Pi
ping 192.168.1.101
```

### Test 3: Camera Stream
```bash
# On Pi - test camera
rpicam-vid -t 5000 -o test.h264

# On Pi - test stream
rpicam-vid -t 0 --width 1280 --height 720 --framerate 30 --codec h264 -o - | \
gst-launch-1.0 fdsrc ! h264parse ! rtph264pay ! udpsink host=192.168.1.201 port=5100

# On Laptop - receive stream
gst-launch-1.0 udpsrc port=5100 caps="application/x-rtp,media=video,encoding-name=H264" ! rtph264depay ! h264parse ! avdec_h264 ! autovideosink
```

### Test 4: Full System Test
1. **Start Game Viewer**
   ```bash
   python3 game_viewer.py
   ```

2. **Start Pi (each robot)**
   ```bash
   ./start_robot.sh
   ```

3. **Start Laptop (each team)**
   ```bash
   python laptop_control.py
   ```

4. **Verify in Game Viewer**:
   - All teams appear in "Connected Teams"
   - Heartbeats show "🟢 ONLINE"
   - Ready status updates

5. **Test Game Flow**:
   - Click "📢 Ready Check" in GV
   - Click "✅ Ready Up" on each laptop
   - Click "▶️ Start Game" in GV
   - Test firing and hit detection
   - Verify points update on laptops

---

## 🐛 Troubleshooting

### Pi Issues

**Problem: pigpiod not running**
```bash
# Check status
sudo systemctl status pigpiod

# Start manually
sudo pigpiod

# Check for errors
sudo journalctl -u pigpiod
```

**Problem: Camera not detected**
```bash
# Check camera
vcgencmd get_camera

# Should output: supported=1 detected=1

# If not, enable in raspi-config
sudo raspi-config
```

**Problem: Motors not responding**
```bash
# Check standby pins are high
python3 -c "import pigpio; pi = pigpio.pi(); pi.set_mode(9, pigpio.OUTPUT); pi.write(9, 1); pi.set_mode(11, pigpio.OUTPUT); pi.write(11, 1); print('Standby enabled'); pi.stop()"

# Test single motor
python3 -c "import pigpio; pi = pigpio.pi(); pi.set_mode(18, pigpio.OUTPUT); pi.set_PWM_dutycycle(18, 128); print('Motor should spin'); import time; time.sleep(2); pi.set_PWM_dutycycle(18, 0); pi.stop()"
```

**Problem: GStreamer stream not working**
```bash
# Test GStreamer installation
gst-launch-1.0 --version

# Check rpicam-vid
rpicam-vid --version

# Test simple stream
rpicam-vid -t 10000 -o - | gst-launch-1.0 fdsrc ! fakesink
```

### Laptop Issues

**Problem: Controller not detected**
```python
# Test pygame
python -c "import pygame; pygame.init(); pygame.joystick.init(); print(f'Controllers: {pygame.joystick.get_count()}')"
```

**Problem: Can't see video**
```bash
# Windows - check GStreamer PATH
where gst-launch-1.0

# Test UDP reception
gst-launch-1.0 udpsrc port=5100 ! fakesink
```

**Problem: Can't connect to robot**
```bash
# Test UDP connectivity
# On laptop (Windows PowerShell)
Test-NetConnection -ComputerName 192.168.1.101 -Port 5005 -InformationLevel Detailed
```

### Game Viewer Issues

**Problem: Teams not connecting**
```bash
# Check GV is listening
sudo netstat -ulnp | grep 6000

# Check firewall
sudo ufw status
```

**Problem: Video streams not appearing**
```bash
# Manually test receiving team 1 video
gst-launch-1.0 udpsrc port=5001 caps="application/x-rtp,media=video,encoding-name=H264" ! rtph264depay ! h264parse ! avdec_h264 ! autovideosink
```

### Network Issues

**Problem: High latency**
```bash
# Check ping times
ping -c 10 192.168.1.101

# Should be < 10ms on local network
```

**Problem: Packet loss**
```bash
# Check network stats
netstat -s | grep -i "packet"

# Use iperf3 to test bandwidth
# On Pi
iperf3 -s

# On laptop
iperf3 -c 192.168.1.101
```

---

## 📚 Additional Resources

- [GStreamer Documentation](https://gstreamer.freedesktop.org/documentation/)
- [pigpio Documentation](http://abyz.me.uk/rpi/pigpio/)
- [Raspberry Pi Camera Docs](https://www.raspberrypi.com/documentation/computers/camera_software.html)
- [Python Socket Programming](https://docs.python.org/3/library/socket.html)

---

## 🆘 Getting Help

If you encounter issues:
1. Check console output for error messages
2. Review configuration files
3. Test network connectivity
4. Consult troubleshooting section
5. Contact competition officials

---

**Good luck with the setup! 🏆🤖**
