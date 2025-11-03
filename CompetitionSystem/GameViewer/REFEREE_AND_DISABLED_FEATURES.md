# 🎮 New Features: Referee Web Interface & Robot Disable Overlay

## ✅ Changes Implemented

### 1. **Updated Point System**
- **IR Hits:** 100 → **10 points** (One Shot, One Kill)
- **Tesseract Retrieval:** **+15 points** (first capture)
- **Tesseract Steal:** **+20 points** (stealing from Safe Zone)
- **Tesseract Possession Bonus:** **+30 points** (in Safe Zone at match end)

### 2. **Mobile Referee Web Interface**
A beautiful, mobile-optimized web interface for referees to award points!

**Access:**
- Open any mobile browser
- Navigate to: `http://<game-viewer-ip>:6001`
- Default port: **6001**

**Features:**
- 📱 Mobile-first responsive design
- 🎯 Real-time team status display
- 👆 Tap team card to expand actions
- 🟢 Live game status indicator
- 🔄 Auto-refresh every 2 seconds
- ⚡ Instant point awards with feedback

**Point Categories:**
1. **📦 Tesseract Retrieval** (+15 pts)
2. **🎯 Tesseract Steal** (+20 pts)
3. **👑 Possession Bonus** (+30 pts)

**When Can Points Be Awarded?**
- ✅ During active game
- ✅ After game ends (5-minute grace period)
- ❌ Before game starts
- ❌ More than 5 minutes after game ends

### 3. **Robot Disabled Overlay on Camera Feeds**
When a robot is hit, the camera feed shows a visual indicator!

**What You See:**
- 🔴 **Red semi-transparent overlay** over entire video
- 🚫 **Large "DISABLED" text** in center
- ⏱️ **Countdown timer** showing seconds remaining
- 📊 **Status indicator** shows "🔴 DISABLED (Xs)"

**Duration:** Configurable (default 10 seconds)

**Behavior:**
- Appears immediately when robot is hit
- Updates countdown every second
- Automatically disappears when time expires
- Visible on all camera viewer windows

## 📱 Referee Interface Guide

### Setup

1. **Start Game Viewer**
   ```bash
   python3 game_viewer.py
   ```
   Output will show:
   ```
   [Referee] Web interface started on port 6001
   [Referee] Access at: http://<your-ip>:6001
   ```

2. **Find Game Viewer IP**
   ```bash
   hostname -I
   ```

3. **Connect from Mobile**
   - Open browser on phone/tablet
   - Enter: `http://192.168.1.xxx:6001`
   - Bookmark for easy access!

### Using the Interface

**Step 1: Select Team**
- Tap on a team card
- Card expands and highlights green
- Action buttons appear

**Step 2: Award Points**
- Tap appropriate button:
  - **Tesseract Retrieval** - First pickup
  - **Tesseract Steal** - Stolen from another team
  - **Possession Bonus** - Holding at match end

**Step 3: Confirmation**
- Green notification appears: "✅ [Category] awarded!"
- Points update automatically
- Event logged in Game Viewer

### Interface Elements

```
┌─────────────────────────────────────┐
│   🎯 REFEREE CONTROL PANEL          │
│   🟢 GAME ACTIVE                    │
├─────────────────────────────────────┤
│   [🔄 Refresh Teams]                │
├─────────────────────────────────────┤
│ ┌─────────────────────────────────┐ │
│ │ Team 1: Red Dragons     500 pts│ │
│ │ K: 5 | D: 2                    │ │
│ │ ┌─────────────────────────────┐ │ │
│ │ │ 📦 Tesseract Retrieval      │ │ │
│ │ │    +15 points               │ │ │
│ │ ├─────────────────────────────┤ │ │
│ │ │ 🎯 Tesseract Steal          │ │ │
│ │ │    +20 points               │ │ │
│ │ ├─────────────────────────────┤ │ │
│ │ │ 👑 Possession Bonus         │ │ │
│ │ │    +30 points               │ │ │
│ │ └─────────────────────────────┘ │ │
│ └─────────────────────────────────┘ │
│ [More teams...]                     │
└─────────────────────────────────────┘
```

## 🎥 Camera Feed Disabled Overlay

### Visual Example

**Normal Feed:**
```
┌──────────────────────────────┐
│ 14:32:15          [LIVE] 🟢 │
│                              │
│     [Robot Camera View]      │
│                              │
│                              │
└──────────────────────────────┘
```

**Disabled Feed:**
```
┌──────────────────────────────┐
│ 14:32:15      [DISABLED] 🔴  │
│  [RED TINTED OVERLAY]        │
│                              │
│      🚫 DISABLED              │
│          7s                  │
│                              │
└──────────────────────────────┘
```

### Configuration

Change disable duration in `game_viewer.py`:

```python
GV_CONFIG = {
    "robot_disable_duration": 10,  # Seconds (default)
}
```

Or via Settings GUI in Game Viewer.

## 🔧 Technical Details

### Network Architecture

```
┌─────────────┐    UDP 6000    ┌──────────────┐
│   Robots    │ ──────────────> │ Game Viewer  │
└─────────────┘                 │              │
                                │ Port 6000    │
┌─────────────┐    HTTP 6001   │ Port 6001    │
│   Referee   │ <──────────────>│              │
│   Mobile    │                 │              │
└─────────────┘                 └──────────────┘
```

### Point Award Flow

1. Referee taps button on mobile
2. HTTP POST to `/api/award_points`
3. Game Viewer receives request
4. Points added to team
5. Update sent to team's Pi
6. Log entry created
7. Confirmation sent to mobile

### Disabled Robot Tracking

```python
# When robot is hit:
self.disabled_robots[team_id] = time.time() + 10

# Camera viewer checks:
if team_id in disabled_robots:
    if current_time < disable_until:
        # Show DISABLED overlay
    else:
        # Remove from tracking
```

## 📊 Match Logging

All referee actions are logged:

```
[14:32:15] REFEREE: Red Dragons - Tesseract Retrieval: +15 pts
[14:33:42] REFEREE: Blue Team - Tesseract Steal: +20 pts
[14:35:00] REFEREE: Green Squad - Tesseract Possession Bonus: +30 pts
```

Logs appear in:
- Game Viewer hit log panel
- Console output
- Saved match results file

## 🎯 Example Tournament Workflow

### Pre-Match
```
1. Referee opens mobile browser
2. Navigates to http://192.168.1.100:6001
3. Sees "⏸️ Game Not Active"
4. Point awarding is disabled
```

### During Match
```
1. Game Viewer operator starts game
2. Referee sees "🟢 GAME ACTIVE"
3. Team 1 retrieves Tesseract
4. Referee:
   - Taps Team 1 card
   - Taps "📦 Tesseract Retrieval"
   - Sees "✅ Tesseract Retrieval awarded!"
5. Team 1's points: 0 → 15
```

### After Match
```
1. Game ends automatically (timer expires)
2. Referee still sees "can award points"
3. 5-minute grace period to award missed points
4. After 5 minutes, awarding disabled
```

## 🐛 Troubleshooting

### Referee Interface Not Loading?

**Check Game Viewer:**
```
[Referee] Web interface started on port 6001  ← Should see this
```

**Check Firewall:**
```bash
sudo ufw allow 6001/tcp
```

**Find Correct IP:**
```bash
hostname -I
# Use first IP address shown
```

**Test from Computer:**
Open browser on same network:
```
http://<gv-ip>:6001
```

### Points Not Updating?

1. **Check game status** - Must be active or recently ended
2. **Refresh teams** - Click 🔄 button
3. **Check console** - Look for error messages
4. **Verify network** - Phone and GV on same network?

### Disabled Overlay Not Showing?

1. **Check camera viewer is open** - Must have video window active
2. **Hit was registered** - Check hit log in main window
3. **Time hasn't expired** - Overlay only shows for 10 seconds
4. **Check team ID** - Correct robot was hit?

### Mobile Interface Too Small?

- Pinch to zoom (interface is responsive)
- Use landscape mode for more space
- Buttons are large enough for finger taps

## 📝 Configuration Options

### Change Referee Port

```python
GV_CONFIG = {
    "referee_port": 8080,  # Change from 6001
}
```

### Change Point Values

```python
GV_CONFIG = {
    "points_tesseract_retrieval": 20,  # Change from 15
    "points_tesseract_steal": 25,      # Change from 20
    "points_tesseract_possession": 40, # Change from 30
}
```

### Change Grace Period

In `start_referee_server()` method:
```python
time.time() - game_viewer.game_ended_time < 600  # 10 minutes
```

## 🎉 Summary

**Referee Interface:**
✅ Mobile-optimized web interface on port 6001
✅ Real-time team status and points
✅ Award Tesseract points during/after game
✅ 5-minute grace period after match ends
✅ Beautiful, responsive design

**Disabled Overlay:**
✅ Red overlay on camera feeds when robot hit
✅ Large "DISABLED" text with countdown
✅ Automatic removal after 10 seconds
✅ Visible on all camera viewer instances

**Point System:**
✅ IR Hits: 10 points
✅ Tesseract Retrieval: 15 points
✅ Tesseract Steal: 20 points
✅ Possession Bonus: 30 points

Everything is integrated, tested, and ready for tournament use! 🏆
