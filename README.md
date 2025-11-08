# Competition System

A comprehensive laser tag tournament system designed for autonomous robot competitions. This system provides real-time control, game management, IR-based hit detection, and live video streaming capabilities.

## System Overview

The Competition System consists of three primary components:

1. **Raspberry Pi (Robot)** - Onboard control system running motor control, IR weapon/sensor systems, camera streaming, and game state management
2. **Laptop (Operator Station)** - Remote control interface with keyboard input, video feed display, and game status monitoring
3. **Game Viewer (Tournament Management)** - Centralized tournament server managing multiple teams, scoring, match scheduling, and referee controls

## Architecture

```
┌─────────────────┐         ┌──────────────────┐         ┌─────────────────┐
│   Raspberry Pi  │◄───────►│     Laptop       │◄───────►│  Game Viewer    │
│   (On Robot)    │  UDP    │  (Operator)      │  UDP    │  (Tournament)   │
└─────────────────┘         └──────────────────┘         └─────────────────┘
      │                            │                             │
      ├─ Motor Control             ├─ Keyboard Input            ├─ Scoring
      ├─ IR Weapon/Sensor          ├─ Video Display             ├─ Team Management
      ├─ Camera Streaming          ├─ Status Display            ├─ Match Control
      ├─ Servo Control             └─ Game Timer                ├─ Leaderboard
      └─ GPIO Control                                            └─ Referee Interface
```

## Communication Protocol

- **Pi ↔ Laptop**: UDP on port 5005 (control commands) and 5000+ (video streams)
- **Laptop ↔ Game Viewer**: UDP on port 6000 (game viewer) and 6100+ (laptop listeners)
- **Pi → Game Viewer**: Direct UDP for hit reports and registration
- All messages use JSON encoding for structured data exchange

## Quick Start

Detailed setup instructions are provided in component-specific README files:

- **[Laptop Setup Instructions](Laptop/README.md)** - For operators controlling robots
- **[Raspberry Pi Setup Instructions](Pi/README.md)** - For robot onboard systems
- **Game Viewer Setup** - Requires Laptop setup plus running `GameViewer/game_viewer.py`

## Features

### Robot Control
- Mecanum drive control with keyboard input (WASD)
- Dual servo control for mechanisms
- GPIO control for accessories
- Emergency stop functionality
- Boost speed mode

### IR Combat System
- IR transmitter for shooting (38kHz modulated)
- IR receiver for hit detection
- Team ID encoding in IR signals
- 10-second disable period after hits
- Automatic hit reporting to Game Viewer

### Game Management
- Team registration and ready checking
- Configurable match duration
- Real-time scoring and leaderboard
- Kill/Death tracking
- Point awards (hits, objectives)
- Match history and statistics export

### Video Streaming
- H.264 encoded video via GStreamer
- Low-latency UDP streaming
- Multi-camera support (up to 8 teams)
- Embedded camera viewer in Game Viewer

## Configuration

Each component uses JSON configuration files:

- **Pi**: `team_config.json` - Team ID, robot name, network settings, hardware pins
- **Laptop**: `laptop_controls.json` - Keyboard mappings (auto-generated)
- **Game Viewer**: `game_viewer_config.json` - Match duration, scoring rules, network settings

## System Requirements

### Laptop
- Windows 10/11
- Python 3.9 or higher
- GStreamer runtime and development libraries
- Microsoft Visual Studio Build Tools 2022
- 8GB RAM minimum
- Network connectivity to robot and game viewer

### Raspberry Pi
- Raspberry Pi 4B (4GB+ recommended)
- Raspbian OS (Bullseye or newer)
- Python 3.9 or higher
- pigpio daemon
- GStreamer libraries
- Camera module (optional for video streaming)

### Game Viewer
- Same requirements as Laptop
- Additional: PyGObject for embedded video display

## License

[Add your license information here]

## Contributing

[Add contribution guidelines here]

## Support

For technical support or questions, contact your team lead.
