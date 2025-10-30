# 🎯 QUICK REFERENCE GUIDE

## 📝 Startup Checklist

### Before Competition Day
- [ ] Configure `team_config.json` with team info and GPIO pins
- [ ] Test robot motors and movement
- [ ] Verify IR transmitter and receivers work
- [ ] Test camera stream to laptop
- [ ] Confirm network connectivity to Game Viewer
- [ ] Practice with Xbox controller
- [ ] Have backup batteries charged

### Competition Day Setup
1. **Power on robot and wait for boot**
2. **Connect laptop to same network**
3. **Start Pi code**: `./start_robot.sh`
4. **Start laptop control**: `python laptop_control.py`
5. **Click "Settings"** and verify IPs
6. **Click "Start Camera"** to view feed
7. **Test controller** - move robot
8. **Click "Ready Up"** when Game Viewer asks

---

## ⌨️ Xbox Controller Quick Reference

### Movement
- **Left Stick Up/Down**: Forward/Backward
- **Left Stick Left/Right**: Strafe Left/Right
- **Right Stick Left/Right**: Rotate

### Speed Control
- **Right Trigger (RT)**: Variable boost (50%-100% speed)
- **LB Button**: Full boost (100% speed)
- **Left Trigger (LT)**: Slow mode (30%-50% speed)

### Weapons & Combat
- **A Button**: Fire laser (single shot)
- **RB Button**: Fire laser (alternative)

### Servo Control
- **D-Pad Up/Down**: Control Servo 1
- **D-Pad Left/Right**: Control Servo 2

### System
- **B Button**: Emergency stop (stops all motors)
- **BACK Button**: Reconnect controller
- **START Button**: Quit application

---

## 🔧 Common Commands

### Pi Commands
```bash
# Start robot system
cd CompetitionSystem/Pi/
./start_robot.sh

# Check if running
ps aux | grep python

# Stop robot
pkill -f main.py

# View logs
tail -f /var/log/syslog | grep -i robot

# Restart pigpiod
sudo systemctl restart pigpiod

# Check network
ip addr show wlan0
ping <laptop_ip>
ping <game_viewer_ip>
```

### Laptop Commands
```bash
# Start laptop control
cd CompetitionSystem/Laptop/
python laptop_control.py

# Test controller
python -c "import pygame; pygame.init(); pygame.joystick.init(); print(f'Controllers: {pygame.joystick.get_count()}')"

# Test video reception
gst-launch-1.0 udpsrc port=5100 caps="application/x-rtp,media=video,encoding-name=H264" ! rtph264depay ! h264parse ! avdec_h264 ! autovideosink
```

### Game Viewer Commands
```bash
# Start game viewer
cd CompetitionSystem/GameViewer/
python game_viewer.py

# Export game log
# (Use GUI button: "💾 Export Log")
```

---

## 🚨 Emergency Procedures

### Robot Not Responding
1. Press **B button** on controller (emergency stop)
2. Check laptop shows "Robot: Connected" (green)
3. If red, check Pi is running and network works
4. Restart Pi code if needed

### Controller Disconnected
1. Click **"🔄 Reconnect"** button in GUI
2. Or press **BACK button** on controller
3. Check USB cable is plugged in
4. Try different USB port

### Robot Hit and Won't Respawn
- Wait for 7-second timer to complete
- Check Game Viewer shows correct team ID
- Verify game is active (not ended)

### Camera Feed Not Showing
1. Click **"📹 Start Camera"** button
2. Check Pi shows camera is streaming
3. Verify video port in settings (default 5100)
4. Test with GStreamer command

### Motors Running Wild
1. **IMMEDIATELY** press **B button** (emergency stop)
2. If doesn't work, power off robot
3. Check motor direction offsets in config
4. Contact officials before restart

---

## 📊 Status Indicators

### Laptop GUI Colors

#### Controller Status
- 🟢 **Green "Connected"**: Controller working
- 🔴 **Red "Disconnected"**: No controller detected

#### Robot Connection
- 🟢 **Green "Connected"**: Robot responding (< 2s latency)
- 🔴 **Red "Disconnected"**: No response from robot

#### Game Status
- 🟡 **Yellow "Waiting"**: Game not started
- 🟢 **Green "GAME ACTIVE"**: Game in progress
- 🟡 **Yellow "Game Ended"**: Game finished

#### Robot Combat Status
- 🟢 **Green "Active"**: Robot can move and fire
- 🔴 **Red "DISABLED"**: Robot hit, waiting to respawn

### Game Viewer Indicators

#### Team Status
- 🟢 **ONLINE**: Heartbeat received < 5s ago
- 🔴 **OFFLINE**: No heartbeat for > 5s

#### Ready Status
- ✅ **Checkmark**: Team is ready
- ⏳ **Hourglass**: Team not ready yet

---

## 📈 Scoring

### Points
- **Hit Enemy**: +100 points (default)
- **Get Hit**: No point penalty (but disabled 7 seconds)

### K/D Ratio
- **K** (Kills): Number of hits you scored
- **D** (Deaths): Number of times you were hit
- **K/D Ratio**: Kills divided by Deaths (higher is better)

---

## 🎮 Game Modes (Game Viewer)

### Standard Deathmatch
- Fixed time limit (default 5 minutes)
- Most points wins
- All hits count

### Team Elimination
- Each team has 3 "lives"
- Eliminated after 3 hits
- Last team standing wins

### Capture Points
- Hold designated areas for points
- Continuous scoring over time
- Strategic positioning required

---

## 🔍 Debugging Tips

### Check Pi Logs
```bash
# View realtime logs
journalctl -f -u pigpiod

# Check Python errors
python3 main.py 2>&1 | tee robot.log
```

### Test Individual Components

**Test Motors Only**
```python
from motor_controller import MotorController
from config_manager import ConfigManager
import pigpio

pi = pigpio.pi()
cfg = ConfigManager()
motor = MotorController(pi, cfg.config)

# Test drive forward
motor.drive_mecanum(0.5, 0, 0, 0.5)
time.sleep(2)
motor.stop_all()
motor.cleanup()
pi.stop()
```

**Test IR Transmitter**
```python
from ir_controller import IRController
from config_manager import ConfigManager
import pigpio

pi = pigpio.pi()
cfg = ConfigManager()
ir = IRController(pi, cfg.config, 1, "192.168.1.50", 6000)

# Fire test shot
ir.fire()
time.sleep(1)

ir.cleanup()
pi.stop()
```

**Test Servos**
```python
from servo_controller import ServoController
from config_manager import ConfigManager
import pigpio

pi = pigpio.pi()
cfg = ConfigManager()
servo = ServoController(pi, cfg.config)

# Move servo 1 to center
servo.set_servo_pulse('servo_1', 1500)
time.sleep(1)

servo.cleanup()
pi.stop()
```

### Network Diagnostics
```bash
# Check open ports
sudo netstat -tulnp

# Monitor UDP traffic
sudo tcpdump -i wlan0 udp port 5005 -n

# Test latency
ping -c 100 <robot_ip> | tail -1
```

---

## 📞 Support Contacts

### During Competition
- **Technical Support**: See competition officials
- **Rule Questions**: See head referee
- **Equipment Issues**: See tech booth

### Before Competition
- Check documentation in `README.md`
- Review `INSTALLATION.md` for setup help
- Test system thoroughly before event

---

## 💡 Pro Tips

1. **Practice Makes Perfect**: Spend time driving before the competition
2. **Know Your Layout**: Learn the arena before matches start
3. **Conserve Fire**: Don't spam - 500ms cooldown between shots
4. **Watch K/D**: Staying alive is as important as getting hits
5. **Communicate**: If using team mode, coordinate with teammates
6. **Check Battery**: Always monitor robot battery levels
7. **Test Everything**: Don't wait until match day to test features
8. **Have Backups**: Extra batteries, cables, controllers ready
9. **Stay Calm**: Robot issues happen - stay cool and troubleshoot
10. **Have Fun**: It's a competition, but enjoy the experience!

---

## 📋 Competition Day Checklist

### Equipment
- [ ] Robot (fully assembled and tested)
- [ ] Raspberry Pi (configured and tested)
- [ ] Charged batteries (2-3 recommended)
- [ ] Laptop with software installed
- [ ] Xbox controller (with cable)
- [ ] Network cables (if needed)
- [ ] Backup USB drive with code
- [ ] Printed copy of this guide

### Pre-Match
- [ ] Robot powered on and connected
- [ ] Laptop running control software
- [ ] Controller connected and tested
- [ ] Camera feed visible
- [ ] Game Viewer shows team online
- [ ] Team is marked ready

### During Match
- [ ] Watch timer
- [ ] Monitor hit status
- [ ] Track points/K/D
- [ ] Stay aware of other robots
- [ ] Use cover strategically

### Post-Match
- [ ] Note final score
- [ ] Save any logs if requested
- [ ] Prepare for next match
- [ ] Check robot for damage
- [ ] Recharge batteries

---

**May the best team win! 🏆**
