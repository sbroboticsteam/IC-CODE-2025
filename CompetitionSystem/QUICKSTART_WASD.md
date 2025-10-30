# 🚀 QUICK START - NEW WASD SYSTEM

## What Changed?

### ✅ GOOD NEWS
- **No Xbox Controller Needed!** Use WASD keyboard controls
- **Debug Mode** - Test your robot anytime without GV
- **Easier Setup** - Just keyboard and mouse
- **Fair Competition** - All teams start game timer together

### 📋 New Workflow

#### 1. Testing Phase (No Game Viewer Needed)
```bash
# On Pi
cd CompetitionSystem/Pi/
./start_robot.sh

# On Laptop
cd CompetitionSystem/Laptop/
python laptop_control.py

# You're now in DEBUG MODE!
# Use WASD to drive, Space to fire
# Test everything freely
```

#### 2. Competition Phase (With Game Viewer)
```bash
# Admin starts Game Viewer
cd CompetitionSystem/GameViewer/
python game_viewer.py

# Teams: Click "Ready Up" when prepared
# Admin: Click "Start Game" 
# All teams enter Game Mode simultaneously
# Timer counts down on all screens
```

---

## 🎮 CONTROLS CHEAT SHEET

```
┌─────────────────────────────────────┐
│          MOVEMENT (WASD)            │
├─────────────────────────────────────┤
│  W - Forward                        │
│  S - Backward                       │
│  A - Strafe Left                    │
│  D - Strafe Right                   │
│  Shift - Boost Speed                │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│            COMBAT                   │
├─────────────────────────────────────┤
│  Space - Fire Laser                 │
│  (500ms cooldown)                   │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│           SERVOS                    │
├─────────────────────────────────────┤
│  Q - Servo 1 Up                     │
│  Z - Servo 1 Down                   │
│  E - Servo 2 Up                     │
│  C - Servo 2 Down                   │
└─────────────────────────────────────┘

┌─────────────────────────────────────┐
│          GPIO & LIGHTS              │
├─────────────────────────────────────┤
│  1 - Toggle GPIO 1                  │
│  2 - Toggle GPIO 2                  │
│  3 - Toggle GPIO 3                  │
│  4 - Toggle GPIO 4                  │
│  L - Toggle Status Lights           │
└─────────────────────────────────────┘
```

---

## 🎯 GAME MODES EXPLAINED

### 🛠️ DEBUG MODE (Green)
- **When**: Default state, or after unreadying
- **Controls**: ✅ Full control enabled
- **Purpose**: Test robot freely
- **To Exit**: Click "Ready Up"

### ⏳ WAITING MODE (Orange)
- **When**: After clicking "Ready Up"
- **Controls**: ❌ Disabled (waiting for game)
- **Purpose**: Confirmed ready for competition
- **To Exit**: Click "Not Ready" OR game starts

### 🔥 GAME ACTIVE (Red)
- **When**: GV sends GAME_START
- **Controls**: ✅ Full control enabled
- **Timer**: Counting down
- **Purpose**: COMPETE!
- **Duration**: Set by admin (default 2 min)

---

## ⚙️ FIRST-TIME SETUP

### 1. Edit Configuration
```bash
# On Laptop
cd CompetitionSystem/Laptop/
notepad laptop_config.json

# Change these:
{
  "team_id": 1,           # Your team number
  "team_name": "Hawks",   # Your team name
  "robot_name": "Hawk-1", # Your robot name
  "robot_ip": "192.168.1.101",  # Your Pi's IP
  "gv_ip": "192.168.1.50"       # Admin's GV IP
}
```

### 2. Test Controls (Optional)
You can customize key bindings in the "controls" section:
```json
{
  "controls": {
    "forward": "w",      # Change to "i" for IJKL layout
    "backward": "s",
    "left": "a",
    "right": "d",
    "boost": "shift_l",
    "fire": "space"
    // ... etc
  }
}
```

---

## 🎬 COMPETITION DAY

### Pre-Game Checklist
- [ ] Pi is powered on and `start_robot.sh` is running
- [ ] Laptop is on same network as Pi and GV
- [ ] `laptop_control.py` is running
- [ ] Settings are correct (click ⚙️ Settings)
- [ ] Video stream works (click ▶ Start Stream)
- [ ] Robot responds to WASD in Debug Mode

### During Competition
1. **Wait for announcement** from admin
2. **Test controls** in Debug Mode one last time
3. **Click "Ready Up"** when announced
4. **Keep laptop window focused** (click on it)
5. **Wait for game start** - controls will activate
6. **PLAY!** Timer shows remaining time
7. **After game ends** - view final score

### Game Rules
- **Control locked**: Can't move until game starts
- **Fair start**: All teams get timer at same time
- **No early fire**: Shots only count during game
- **Timer is king**: Game ends when timer hits 0:00

---

## 🔧 ADMIN SETUP (Game Viewer)

### Configure Game Settings
```bash
# Start Game Viewer
python game_viewer.py

# Click "⚙️ Settings"
# Adjust:
- Game Duration: 120 seconds (2 min)
- Points per Hit: 100
- Max Teams: 8
```

### Run Competition
1. Wait for teams to connect (they appear in Teams list)
2. Click "📢 Ready Check" (optional)
3. Verify ready checkmarks ✅ appear
4. Click "▶️ Start Game"
5. Monitor leaderboard and timer
6. Click "⏹️ End Game" when done
7. Click "💾 Export Log" to save results

---

## 💡 PRO TIPS

### For Teams
- **Practice in Debug Mode** as much as you want
- **Keep window focused** - click laptop window before playing
- **Hold Shift** for boost during movement
- **Servo keys** work continuously while held
- **GPIO toggles** happen instantly on press

### For Admins
- **Set timer** before first match
- **Ready Check** helps coordinate start
- **Export logs** after each match
- **Longer duration** = more strategic play
- **Shorter duration** = more intense action

---

## 🆘 TROUBLESHOOTING

### "Controls don't work!"
- Click on the laptop window to focus it
- Make sure you're in Debug Mode or Game Active
- Check that no text box is selected

### "Timer not showing"
- Make sure GV sent GAME_START
- Check network connection to GV
- Verify you clicked "Ready Up"

### "Can't move after readying"
- **This is normal!** Wait for GV to start game
- Control unlocks when game starts
- Click "Not Ready" if you need to go back

### "Timer different from others"
- Small differences (<1 sec) are normal
- Network delay causes slight drift
- Use GV timer as official time

---

## 📚 MORE INFO

- **Full Manual**: See `README.md`
- **Complete Changes**: See `CHANGES.md`
- **Quick Reference**: See `QUICK_REFERENCE.md`
- **Competition Rules**: See `INSTALLATION.md`

---

## 🎉 READY TO COMPETE!

You now have:
- ✅ Keyboard controls (no Xbox needed)
- ✅ Debug mode for testing
- ✅ Fair synchronized starts
- ✅ Clear game state indicators
- ✅ Configurable game duration

**Go build an awesome robot and have fun!** 🤖🔥
