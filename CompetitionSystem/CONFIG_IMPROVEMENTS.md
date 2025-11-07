# Configuration Improvements - Quality of Life Update

## Summary
Cleaned up configuration redundancies and hardcoded competition-standard values that should not be user-configurable.

## Changes Made

### 1. **Removed Redundant Team Information**
   - **Before**: Team name and robot name were defined in both Pi and Laptop configs
   - **After**: Only defined in Pi's `team_config.json`, automatically synced to laptop via Game Viewer registration
   - **Benefit**: Single source of truth, no sync issues

### 2. **Auto-Calculated Video Ports**
   - **Before**: Hardcoded ports in both configs (`laptop_video_port`, `game_viewer_video_port`)
   - **After**: Automatically calculated based on team_id:
     - **Laptop video port**: `5100 + team_id`
     - **Game Viewer port**: `5000 + team_id`
   - **Benefit**: No port conflicts, consistent with competition rules

### 3. **Hardcoded IR Protocol Constants**
   - **Before**: IR protocol timing was in config file (carrier frequency, burst timings, tolerances)
   - **After**: Hardcoded as constants in `ir_controller.py`
   - **Constants**:
     ```python
     IR_CARRIER_FREQ = 38000
     IR_BIT_0_BURST_US = 800
     IR_BIT_1_BURST_US = 1600
     IR_START_END_BURST_US = 2400
     IR_TOLERANCE_US = 200
     IR_WEAPON_COOLDOWN_MS = 2000
     IR_HIT_DISABLE_TIME_S = 10.0
     ```
   - **Benefit**: Prevents accidental modification of competition-required values

## Updated Configuration Files

### Pi: `team_config.json`
```json
{
  "team": {
    "team_id": 1,
    "team_name": "Admin",
    "robot_name": "Admin_Robot"
  },
  
  "network": {
    "_comment": "Video ports are auto-calculated: GV = 5000+team_id, Laptop = 5100+team_id",
    "laptop_ip": "192.168.50.142",
    "laptop_port": 4999,
    "game_viewer_ip": "192.168.50.87",
    "game_viewer_control_port": 6000,
    "robot_listen_port": 5005
  },
  
  "ir_system": {
    "_comment": "IR GPIO pins - protocol is fixed by competition rules",
    "transmitter_gpio": 20,
    "receiver_gpios": [3, 25, 21]
  }
  
  // ... motors, servos, etc. remain configurable
}
```

### Laptop: `laptop_config.json` (default config)
```json
{
  "robot_ip": "192.168.50.147",
  "robot_port": 5005,
  "gv_ip": "192.168.50.67",
  "gv_port": 6000,
  "team_id": 1,
  "controls": {
    "base_speed": 0.6,
    "boost_speed": 1.0,
    // ... key bindings
  }
}
```

**Removed fields:**
- ❌ `video_port` (now auto-calculated)
- ❌ `team_name` (synced from Pi via GV)
- ❌ `robot_name` (synced from Pi via GV)

## What's Still Configurable

### ✅ Motors & Servos
- Pin assignments
- PWM settings
- Servo ranges
- Direction offsets

### ✅ Network Settings
- IP addresses
- Control ports
- Robot listen port

### ✅ Camera Settings
- Resolution
- Framerate
- Bitrate

### ✅ Safety Settings
- Timeouts
- Max speed

### ✅ GPIO Pins
- IR transmitter/receiver GPIOs
- Extra GPIO assignments
- Light assignments

## Migration Notes

### For Existing Systems:
1. **Pi Config**: Remove `laptop_video_port` and `game_viewer_video_port` from network section
2. **Laptop Config**: Remove `video_port`, `team_name`, and `robot_name` fields
3. **Team name/robot name** will automatically sync from Pi when laptop connects to Game Viewer

### Testing:
- Verify video streams work on correct ports (5100+team_id for laptop)
- Confirm team info displays correctly in laptop GUI after GV registration
- Check IR system works with hardcoded protocol values
