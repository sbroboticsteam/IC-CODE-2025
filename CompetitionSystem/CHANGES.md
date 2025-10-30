# CHANGES - WASD Keyboard Controls Update

## Overview
Major update to the Laptop Control system and Game Viewer to improve usability and game flow.

---

## 🎮 LAPTOP CONTROL - NEW FEATURES

### 1. **WASD Keyboard Controls** (Xbox Controller Removed)
- **Movement**: W/A/S/D for forward/left/backward/right
- **Boost**: Shift key for speed boost
- **Fire**: Spacebar to fire laser
- **Servos**: Q/Z for Servo 1, E/C for Servo 2
- **GPIO**: 1/2/3/4 to toggle GPIO pins
- **Lights**: L to toggle status lights
- All keys are **configurable** in laptop_config.json

### 2. **Debug Mode vs Game Mode**
- **Debug Mode (Default)**:
  - Test your robot freely
  - Full control access
  - Practice before competition
  
- **Game Mode** (After Ready Up):
  - Activated by clicking "READY UP" button
  - Robot control disabled until game starts
  - Only active during official game time
  
### 3. **Ready-Up System**
- Teams click "READY UP" when prepared for game
- Game Viewer can check ready status of all teams
- Can un-ready before game starts
- Game starts when GV sends GAME_START message

### 4. **Improved UI**
- Clear mode indicator (DEBUG/GAME MODE/GAME ACTIVE)
- Real-time servo position display (percentage)
- Timer countdown during active game
- Points and stats tracking
- Connection status indicators

---

## 🎯 GAME VIEWER - NEW FEATURES

### 1. **Configurable Game Timer**
- **Default**: 120 seconds (2 minutes)
- Adjustable via Settings dialog
- Timer sent to all laptops in GAME_START message
- All teams start synchronized countdown

### 2. **Settings Dialog**
Access via "⚙️ Settings" button:
- **Game Duration**: Set match length in seconds
- **Points per Hit**: Configure scoring
- **Max Teams**: Maximum team capacity

### 3. **Enhanced Game Flow**
1. Teams connect and ready up
2. GV sends Ready Check (optional)
3. GV clicks "Start Game"
4. GAME_START message sent with duration
5. All laptops enter Game Mode and start timer
6. Game runs for configured duration
7. GV clicks "End Game" or timer expires
8. GAME_END message sent to all teams

---

## 📡 PROTOCOL CHANGES

### Updated Messages

#### GAME_START (from GV to Laptops)
```json
{
  "type": "GAME_START",
  "duration": 120  // NEW: Game duration in seconds
}
```

#### READY_STATUS (from Laptop to GV)
```json
{
  "type": "READY_STATUS",
  "team_id": 1,
  "ready": true  // true when ready, false when not ready
}
```

#### REGISTER (from Laptop to GV)
```json
{
  "type": "REGISTER",
  "team_id": 1,
  "team_name": "Team Alpha",
  "robot_name": "Alpha-1",
  "listen_port": 12345  // NEW: Port for receiving GV messages
}
```

---

## 🔧 CONFIGURATION CHANGES

### laptop_config.json (NEW STRUCTURE)
```json
{
  "robot_ip": "192.168.1.10",
  "robot_port": 5005,
  "gv_ip": "192.168.1.50",
  "gv_port": 6000,
  "video_port": 5100,
  "team_id": 1,
  "team_name": "Team Alpha",
  "robot_name": "Alpha-1",
  "controls": {
    "base_speed": 0.6,
    "boost_speed": 1.0,
    "forward": "w",
    "backward": "s",
    "left": "a",
    "right": "d",
    "boost": "shift_l",
    "fire": "space",
    "servo1_up": "q",
    "servo1_down": "z",
    "servo2_up": "e",
    "servo2_down": "c",
    "gpio1_toggle": "1",
    "gpio2_toggle": "2",
    "gpio3_toggle": "3",
    "gpio4_toggle": "4",
    "lights_toggle": "l"
  }
}
```

### game_viewer_config.json
```json
{
  "gv_ip": "0.0.0.0",
  "gv_port": 6000,
  "max_teams": 8,
  "game_duration": 120,  // CHANGED: Default 2 minutes (was 5)
  "points_per_hit": 100,
  "video_ports_start": 5001
}
```

---

## 🚀 COMPETITION WORKFLOW

### Pre-Competition Setup
1. **Teams**: Configure laptop_config.json with team details
2. **Teams**: Test in Debug Mode (no GV needed)
3. **Admin**: Configure game settings in GV Settings dialog

### Competition Day
1. **Teams**: Start laptop_control.py
2. **Teams**: Verify robot connection (green indicator)
3. **Admin**: Start game_viewer.py
4. **Admin**: Wait for teams to connect
5. **Teams**: Click "READY UP" when prepared
6. **Admin**: Click "📢 Ready Check" (optional)
7. **Admin**: Click "▶️ Start Game"
8. **All**: Game runs for configured duration
9. **All**: Timer counts down on all screens
10. **Admin**: Click "⏹️ End Game" or wait for timer
11. **Admin**: Review leaderboard and export log

---

## ⚠️ BREAKING CHANGES

### Removed
- ❌ **Xbox Controller Support** (pygame still imported but not used)
  - Teams can re-implement if desired
  - Would need to modify KeyboardController class
  
- ❌ **Always-On Control** 
  - Now restricted to Debug Mode or Active Game
  - No control when ready but game hasn't started

### Changed
- ⚠️ **Control Message Format**: Now includes servo and GPIO states every frame
- ⚠️ **GAME_START Message**: Now includes duration field
- ⚠️ **Ready System**: New READY_STATUS message type

---

## 🔑 KEY BENEFITS

### For Teams
- ✅ **Easier Control**: WASD is more intuitive than Xbox controller
- ✅ **No Special Hardware**: Works with any keyboard
- ✅ **Customizable Keys**: Remap controls in config file
- ✅ **Clear Game State**: Always know if you're in debug or game mode
- ✅ **Fair Start**: All teams start timer simultaneously

### For Competition Admin
- ✅ **Configurable Duration**: Adjust match length easily
- ✅ **Ready Tracking**: See which teams are prepared
- ✅ **Synchronized Start**: All laptops receive start signal together
- ✅ **Easy Settings**: GUI dialog for configuration

---

## 🐛 KNOWN ISSUES / NOTES

1. **Keyboard Focus**: Laptop window must have focus for controls to work
2. **Fire Cooldown**: 500ms between shots (configurable in code)
3. **Servo Update Rate**: 100ms for smooth movement
4. **Network Reliability**: UDP means messages can be lost (acceptable for game)
5. **Timer Sync**: Small drift possible (<1s over 2 min) due to network/processing delays

---

## 📝 TODO FOR TEAMS

If teams want to add Xbox controller support back:
1. Keep the `KeyboardController` class as-is
2. Create a new `XboxController` class
3. Add a toggle in GUI to switch between keyboard/xbox
4. Modify control_loop to use selected controller

Custom key bindings:
- Edit `laptop_config.json` under "controls" section
- Use tkinter key names (e.g., "shift_l", "control_l", "alt_l")
- Restart laptop_control.py to apply changes

---

## 📚 UPDATED FILES

- `CompetitionSystem/Laptop/laptop_control.py` - Complete rewrite (1000+ lines)
- `CompetitionSystem/GameViewer/game_viewer.py` - Added settings dialog and duration in GAME_START
- `CHANGES.md` - This document

---

## ✅ TESTING CHECKLIST

### Laptop Control
- [ ] WASD movement works
- [ ] Shift boost works
- [ ] Space fires laser (with cooldown)
- [ ] Q/Z and E/C control servos
- [ ] 1/2/3/4 toggle GPIO
- [ ] L toggles lights
- [ ] Ready up button works
- [ ] Mode changes correctly
- [ ] Timer counts down during game
- [ ] Points update correctly

### Game Viewer
- [ ] Settings dialog opens
- [ ] Can change game duration
- [ ] Can change points per hit
- [ ] Ready check works
- [ ] Game start sends duration
- [ ] Timer matches laptop timers
- [ ] End game works correctly

### Integration
- [ ] Multiple teams can connect
- [ ] All timers start together
- [ ] All timers match (within 1 second)
- [ ] Hit detection works
- [ ] Points update correctly
- [ ] Game end cleans up properly

---

## 🎉 SUMMARY

This update transforms the competition system into a more user-friendly, fair, and configurable platform. The WASD controls lower the barrier to entry (no Xbox controller needed), the debug mode allows teams to test freely, and the synchronized game start ensures fair competition. The configurable timer gives admins flexibility for different tournament formats.

**Ready for competition! 🚀**
