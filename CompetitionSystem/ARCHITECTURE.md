# 🎯 SYSTEM ARCHITECTURE DIAGRAM

```
╔═══════════════════════════════════════════════════════════════════════════╗
║                    LASER TAG COMPETITION SYSTEM                           ║
║                         Architecture Overview                              ║
╚═══════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────┐
│                          TEAM 1 STATION                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  ┌──────────────────┐                  ┌──────────────────┐            │
│  │  RASPBERRY PI    │◄────────UDP─────►│     LAPTOP       │            │
│  │   (Robot Brain)  │      5005        │  (Controller)    │            │
│  │                  │                  │                  │            │
│  │  • main.py       │    Video         │  • Xbox Ctrl     │            │
│  │  • motors        │─────5100────────►│  • GUI           │            │
│  │  • IR system     │                  │  • Settings      │            │
│  │  • camera        │                  │  • Stats         │            │
│  │  • servos/GPIO   │                  │                  │            │
│  └────────┬─────────┘                  └──────────────────┘            │
│           │                                                              │
│           │ Video: 5001                                                 │
│           │ Control: 6001                                               │
└───────────┼──────────────────────────────────────────────────────────────┘
            │
            │
┌───────────┼──────────────────────────────────────────────────────────────┐
│           │                      TEAM 2 STATION                           │
├───────────┼──────────────────────────────────────────────────────────────┤
│           │                                                               │
│  ┌────────▼─────────┐                  ┌──────────────────┐            │
│  │  RASPBERRY PI    │◄────────UDP─────►│     LAPTOP       │            │
│  │   (Robot Brain)  │      5005        │  (Controller)    │            │
│  │                  │                  │                  │            │
│  │  • main.py       │    Video         │  • Xbox Ctrl     │            │
│  │  • motors        │─────5100────────►│  • GUI           │            │
│  │  • IR system     │                  │  • Settings      │            │
│  │  • camera        │                  │  • Stats         │            │
│  │  • servos/GPIO   │                  │                  │            │
│  └────────┬─────────┘                  └──────────────────┘            │
│           │                                                              │
│           │ Video: 5002                                                 │
│           │ Control: 6002                                               │
└───────────┼──────────────────────────────────────────────────────────────┘
            │
            │
            ▼
╔═══════════════════════════════════════════════════════════════════════════╗
║                         GAME VIEWER STATION                               ║
║                    (Tournament Central Control)                           ║
╠═══════════════════════════════════════════════════════════════════════════╣
║                                                                           ║
║  ┌─────────────────────────────────────────────────────────────────┐    ║
║  │                      game_viewer.py                              │    ║
║  │                                                                  │    ║
║  │  ╔════════════════╗  ╔════════════════╗  ╔════════════════╗    │    ║
║  │  ║   LEADERBOARD  ║  ║   GAME TIMER   ║  ║   HIT LOG      ║    │    ║
║  │  ║                ║  ║                ║  ║                ║    │    ║
║  │  ║ 1. Team A: 450 ║  ║   03:27 / 5:00 ║  ║ [12:34] A→B    ║    │    ║
║  │  ║ 2. Team B: 380 ║  ║                ║  ║ [12:35] B→C    ║    │    ║
║  │  ║ 3. Team C: 290 ║  ║   [▶️ Start]   ║  ║ [12:37] C→A    ║    │    ║
║  │  ║ 4. Team D: 150 ║  ║   [⏹️ Stop]    ║  ║ [12:39] A→D    ║    │    ║
║  │  ╚════════════════╝  ╚════════════════╝  ╚════════════════╝    │    ║
║  │                                                                  │    ║
║  │  ╔════════════════════════════════════════════════════════╗    │    ║
║  │  ║           TEAM STATUS (Real-time Monitoring)           ║    │    ║
║  │  ║                                                         ║    │    ║
║  │  ║  ✅ Team 1: Alpha Squad     🟢 ONLINE  (0.2s ago)     ║    │    ║
║  │  ║  ✅ Team 2: Beta Force      🟢 ONLINE  (0.5s ago)     ║    │    ║
║  │  ║  ⏳ Team 3: Gamma Unit      🟡 OFFLINE (6.1s ago)     ║    │    ║
║  │  ║  ✅ Team 4: Delta Squad     🟢 ONLINE  (0.3s ago)     ║    │    ║
║  │  ╚════════════════════════════════════════════════════════╝    │    ║
║  │                                                                  │    ║
║  │  [📢 Ready Check] [▶️ Start Game] [⏹️ End Game] [💾 Export]   │    ║
║  └─────────────────────────────────────────────────────────────────┘    ║
║                                                                           ║
║  Receiving:                                                              ║
║    • Video streams: Ports 5001-5008 (Team 1-8)                          ║
║    • Control data: Port 6000 (UDP)                                      ║
║    • Heartbeats: Every 1 second from each robot                         ║
║    • Hit reports: Real-time from robots                                 ║
║                                                                           ║
╚═══════════════════════════════════════════════════════════════════════════╝


╔═══════════════════════════════════════════════════════════════════════════╗
║                         DATA FLOW DIAGRAM                                 ║
╚═══════════════════════════════════════════════════════════════════════════╝

┌──────────┐                                              ┌──────────┐
│  Laptop  │────── Movement Commands (UDP:5005) ────────►│   Pi     │
│  (Xbox)  │                                              │  Robot   │
│          │◄────── Robot Status (UDP:5005) ─────────────│          │
│          │                                              │          │
│          │◄────── Video Stream (UDP:5100) ─────────────│          │
└──────────┘                                              └────┬─────┘
                                                               │
                                                               │
                                                               ▼
                          ┌────────────────────────────────────────────┐
                          │         GAME VIEWER (UDP:6000)              │
                          ├────────────────────────────────────────────┤
                          │  Receives:                                 │
                          │    • REGISTER - Team joins                 │
                          │    • HEARTBEAT - Keep alive (1 Hz)         │
                          │    • READY_STATUS - Team ready             │
                          │    • HIT_REPORT - Robot hit notification   │
                          │                                             │
                          │  Sends:                                    │
                          │    • READY_CHECK - Ask if ready            │
                          │    • GAME_START - Begin game               │
                          │    • GAME_END - End game                   │
                          │    • POINTS_UPDATE - Score updates         │
                          └────────────────────────────────────────────┘


╔═══════════════════════════════════════════════════════════════════════════╗
║                    ROBOT INTERNAL ARCHITECTURE                            ║
╚═══════════════════════════════════════════════════════════════════════════╝

┌─────────────────────────────────────────────────────────────────────────┐
│                           main.py (Orchestrator)                         │
└───┬──────────┬──────────┬──────────┬──────────┬──────────┬─────────────┘
    │          │          │          │          │          │
    ▼          ▼          ▼          ▼          ▼          ▼
┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│config_ │ │motor_  │ │ir_     │ │servo_  │ │gpio_   │ │camera_ │
│manager │ │control │ │control │ │control │ │control │ │streamer│
└────────┘ └────────┘ └────────┘ └────────┘ └────────┘ └────────┘
    │          │          │          │          │          │
    │          │          │          │          │          ▼
    │          ▼          ▼          ▼          ▼      ┌──────────┐
    │      ┌───────┐  ┌──────┐  ┌──────┐  ┌──────┐   │GStreamer │
    │      │4 Motors│ │IR TX │  │Servo1│  │GPIO 1│   │ Pipeline │
    │      │ A B C D│ │IR RX │  │Servo2│  │GPIO 2│   └──────────┘
    │      └───────┘  └──────┘  └──────┘  │GPIO 3│        │
    │                                      │GPIO 4│        │
    ▼                                      │D1 D2 │        ▼
┌────────────────┐                        └──────┘   Video Out
│team_config.json│                                    (Dual Stream)
│                │
│ • Team Info    │
│ • Network IPs  │               ┌──────────────┐
│ • GPIO Pins    │               │game_client.py│◄──── Game Events
│ • Motor Config │               │  (PROTECTED) │
│ • IR Settings  │               └──────────────┘
└────────────────┘                      │
                                        ▼
                                To Game Viewer


╔═══════════════════════════════════════════════════════════════════════════╗
║                         MESSAGE PROTOCOL                                  ║
╚═══════════════════════════════════════════════════════════════════════════╝

REGISTER (Pi → GV)
┌────────────────────────────────────────┐
│ type: "REGISTER"                       │
│ team_id: 1                             │
│ team_name: "Alpha Squad"               │
│ robot_name: "Alpha-1"                  │
│ timestamp: 1234567890.123              │
└────────────────────────────────────────┘

HEARTBEAT (Pi → GV)
┌────────────────────────────────────────┐
│ type: "HEARTBEAT"                      │
│ team_id: 1                             │
│ game_active: true                      │
│ points: 450                            │
│ timestamp: 1234567891.123              │
└────────────────────────────────────────┘

HIT_REPORT (Pi → GV)
┌────────────────────────────────────────┐
│ type: "HIT_REPORT"                     │
│ team_id: 2                             │
│ data: {                                │
│   attacking_team: 1                    │
│   defending_team: 2                    │
│   timestamp: "2025-10-30T12:34:56"     │
│   game_time: 45.2                      │
│ }                                      │
└────────────────────────────────────────┘

GAME_START (GV → Pi)
┌────────────────────────────────────────┐
│ type: "GAME_START"                     │
└────────────────────────────────────────┘

POINTS_UPDATE (GV → Pi)
┌────────────────────────────────────────┐
│ type: "POINTS_UPDATE"                  │
│ points: 450                            │
│ kills: 4                               │
│ deaths: 1                              │
└────────────────────────────────────────┘


╔═══════════════════════════════════════════════════════════════════════════╗
║                    IR LASER TAG PROTOCOL                                  ║
╚═══════════════════════════════════════════════════════════════════════════╝

Transmission Format (10 bursts):
┌─────┬───┬───┬───┬───┬───┬───┬───┬───┬─────┐
│START│B7 │B6 │B5 │B4 │B3 │B2 │B1 │B0 │ END │
└─────┴───┴───┴───┴───┴───┴───┴───┴───┴─────┘

Burst Widths:
• START/END: 2400μs (38kHz modulated)
• BIT 0:      800μs (38kHz modulated)
• BIT 1:     1600μs (38kHz modulated)
• Tolerance: ±200μs

Example: Team ID = 5 (0b00000101)
┌─────┬───┬───┬───┬───┬───┬───┬───┬───┬─────┐
│2400 │800│800│800│800│800│1600│800│1600│2400│
└─────┴───┴───┴───┴───┴───┴───┴───┴───┴─────┘
        0   0   0   0   0   1   0   1


╔═══════════════════════════════════════════════════════════════════════════╗
║                      FILE STRUCTURE                                       ║
╚═══════════════════════════════════════════════════════════════════════════╝

CompetitionSystem/
│
├── README.md ........................... Main overview
├── INSTALLATION.md .................... Setup guide
├── QUICK_REFERENCE.md ................. Cheat sheet
├── IMPLEMENTATION_SUMMARY.md .......... This diagram
├── requirements.txt ................... Python deps
│
├── Pi/ ................................ Robot code
│   ├── main.py ........................ Entry point ⭐
│   ├── config_manager.py .............. Config loader
│   ├── motor_controller.py ............ Mecanum drive
│   ├── ir_controller.py ............... IR (PROTECTED) 🔒
│   ├── servo_controller.py ............ Servo control
│   ├── gpio_controller.py ............. GPIO/Lights
│   ├── camera_streamer.py ............. Video
│   ├── game_client.py ................. GV comm (PROTECTED) 🔒
│   ├── team_config.json ............... Config ⚙️
│   ├── start_robot.sh ................. Startup script
│   └── README.md ...................... Pi docs
│
├── Laptop/ ............................ Control interface
│   ├── laptop_control.py .............. Main GUI ⭐
│   └── laptop_config.json ............. (Auto-generated)
│
└── GameViewer/ ........................ Tournament system
    ├── game_viewer.py ................. Main app ⭐
    └── game_viewer_config.json ........ (Auto-generated)


Legend:
⭐ = Entry point / Main file
🔒 = Protected (read-only)
⚙️ = Configuration file
```
