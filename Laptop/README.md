# Laptop Setup Instructions

The laptop serves as the operator control station, providing keyboard-based robot control, live video feed display, and game status monitoring.

## Prerequisites

### 1. Install Microsoft Visual Studio Build Tools 2022

Download and install from: https://visualstudio.microsoft.com/downloads/

1. Scroll down to "All Downloads"
2. Expand "Tools for Visual Studio 2022"
3. Download "Build Tools for Visual Studio 2022"
4. Run the installer
5. Select "Desktop development with C++" workload
6. Click Install

### 2. Install GStreamer

GStreamer is required for video streaming functionality.

**Download both packages:**
- Runtime Installer: https://gstreamer.freedesktop.org/download/#windows
- Development Installer: https://gstreamer.freedesktop.org/download/#windows

**Installation steps:**
1. Download the MSVC 64-bit runtime installer (e.g., `gstreamer-1.0-msvc-x86_64-1.22.0.msi`)
2. Download the MSVC 64-bit development installer (e.g., `gstreamer-1.0-devel-msvc-x86_64-1.22.0.msi`)
3. Run both installers with default options
4. **Important**: During installation, select "Complete" installation (not Typical)

**Add GStreamer to PATH:**
1. Open System Properties → Environment Variables
2. Under System Variables, find and edit "Path"
3. Add: `C:\gstreamer\1.0\msvc_x86_64\bin`
4. Click OK to save

**Verify installation:**
```powershell
gst-launch-1.0 --version
```

### 3. Install Python 3.11

Download Python 3.11 from: https://www.python.org/downloads/

**Installation:**
1. Download Python 3.11.x (latest stable release)
2. Run the installer
3. **Check "Add Python to PATH"**
4. Select "Install Now"
5. After installation, verify:
```powershell
python --version
```

### 4. Clone the Repository

```powershell
cd C:\Users\[YourUsername]\Desktop
git clone https://github.com/sbroboticsteam/IC-CODE-2025.git
cd IC-CODE-2025\CompetitionSystem
```

### 5. Install Python Dependencies

```powershell
pip install pynput keyboard
```

**Note:** GStreamer Python bindings are accessed via system GStreamer installation, not pip.

## Configuration

### First-Time Setup

1. **Obtain Robot IP Address**
   - Contact your team lead for your robot's IP address
   - Typical format: `192.168.50.X` where X is your team number

2. **Run the Laptop Control Interface**
   ```powershell
   cd Laptop
   python laptop_control.py
   ```

3. **Enter Robot IP**
   - On first run, you'll be prompted to enter the robot's IP address
   - This is saved to `last_robot_ip.txt` for future sessions

4. **Configure Controls (Optional)**
   - Default controls are pre-configured (see Controls section)
   - Custom mappings can be edited in `laptop_controls.json` after first run

## Controls

### Default Keyboard Mappings

**Movement:**
- `W` - Forward
- `S` - Backward
- `A` - Strafe Left
- `D` - Strafe Right
- `Arrow Left/Right` - Rotate
- `Left Shift` - Boost (increase speed)

**Combat:**
- `Space` - Fire IR weapon

**Servos:**
- `Q` - Toggle Servo 1 (Max/Min)
- `Z` - Toggle Servo 1 (Max/Min)
- `E` - Toggle Servo 2 (Max/Min)
- `C` - Toggle Servo 2 (Max/Min)

**GPIO:**
- `1` - Toggle GPIO 1
- `2` - Toggle GPIO 2
- `3` - Toggle GPIO 3
- `4` - Toggle GPIO 4

**Accessories:**
- `L` - Toggle Lights

**System:**
- `ESC` - Emergency Stop (disables all motors)

## User Interface

### Main Window Sections

**Connection Status**
- Robot connection indicator (green = connected, red = disconnected)
- Game Viewer connection status
- Heartbeat monitoring

**Game Mode Controls**
- `Ready Up` - Mark team as ready for match
- `Not Ready` - Return to debug mode (allows free movement)
- Mode indicator shows current state (DEBUG/WAITING/GAME ACTIVE)

**Game Status**
- Match timer (when game is active)
- Current points
- Hits taken
- Disabled timer (when hit by opponent)

**Team Information**
- Team name and ID
- Robot name
- Configuration details

**Video Streaming**
- `Start Stream` - Opens GStreamer video viewer
- Stream status indicator

### Operating Modes

**DEBUG MODE (Default)**
- Full robot control
- No game restrictions
- Used for testing and setup

**WAITING MODE (After Ready Up)**
- Robot movement locked
- Waiting for Game Viewer to start match
- Prevents accidental movement before game

**GAME ACTIVE**
- Full control enabled during match
- Timer counts down
- Points tracking active
- Hit detection enabled

**DISABLED (After Being Hit)**
- 10-second lockout period
- Robot cannot move or fire
- Red overlay on screen
- Countdown timer displayed

## Troubleshooting

### Robot Not Connecting
1. Verify robot IP address is correct
2. Check that robot is powered on and running `main.py`
3. Ensure both devices are on same network
4. Check Windows Firewall settings (allow Python through firewall)

### Video Stream Not Working
1. Verify GStreamer is installed correctly: `gst-launch-1.0 --version`
2. Check PATH environment variable includes GStreamer bin directory
3. Restart terminal/PowerShell after installing GStreamer
4. Verify robot camera streaming is active

### Game Viewer Not Connecting
1. Confirm Game Viewer is running on the correct IP address
2. Check `team_config.json` on robot for correct GV IP
3. Verify firewall allows UDP traffic on ports 6000 and 6100+

### Controls Not Responding
1. Ensure laptop window has focus (click on window)
2. Check that DEBUG mode is active (not WAITING mode)
3. Verify robot connection is established
4. Try restarting the laptop control interface

### Python Import Errors
1. Reinstall dependencies: `pip install --force-reinstall pynput keyboard`
2. Verify Python version: `python --version` (should be 3.11.x)
3. Check for conflicting Python installations

## Advanced Configuration

### Custom Control Mappings

Edit `laptop_controls.json` to customize keyboard bindings:

```json
{
  "base_speed": 0.6,
  "boost_speed": 1.0,
  "forward": "w",
  "backward": "s",
  "left": "a",
  "right": "d",
  "boost": "shift_l",
  "fire": "space"
}
```

### Network Configuration

If using a different network configuration, robot IP can be changed:
1. Delete `last_robot_ip.txt`
2. Restart `laptop_control.py`
3. Enter new IP when prompted

## Running the Game Viewer

The Game Viewer application runs on one designated laptop for tournament management.

**Requirements:**
- Same setup as standard laptop
- Additional dependency: PyGObject (for embedded camera viewer)

**Installation (Windows):**
```powershell
# Install PyGObject dependencies
pip install PyGObject

# May require additional setup - see PyGObject Windows documentation
```

**Running:**
```powershell
cd GameViewer
python game_viewer.py
```

**Game Viewer Features:**
- Team registration and management
- Match scheduling and control
- Real-time scoring and leaderboard
- Embedded camera feeds (up to 4 teams)
- Referee web interface
- Match statistics export

## Support

For technical issues or questions:
1. Check this documentation thoroughly
2. Verify all prerequisites are installed correctly
3. Contact your team lead for assistance
4. Check robot-side logs for connection issues

## Next Steps

Once laptop setup is complete:
1. Coordinate with team lead to verify robot IP address
2. Test connection by running `laptop_control.py`
3. Practice with controls in DEBUG mode
4. Coordinate with other teams for tournament testing
