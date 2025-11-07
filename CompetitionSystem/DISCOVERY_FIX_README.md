# Discovery Mechanism Fix

## Problem
When Game Viewer is restarted while robots are already running, the robots don't appear in the Game Viewer because they only register once at startup.

## Solution
Added a discovery mechanism with these components:

### 1. Game Viewer Changes
- **Discovery Broadcasting**: Sends DISCOVERY messages every 15 seconds to find existing robots
- **Startup Discovery**: Immediately broadcasts discovery when Game Viewer starts
- **Discovery Response Handling**: Processes DISCOVERY_RESPONSE messages to register found robots

### 2. Robot Changes (Pi)
- **Discovery Response**: Responds to DISCOVERY messages with DISCOVERY_RESPONSE
- **Periodic Re-registration**: Re-registers every 30 seconds automatically
- **Connection Loss Detection**: Re-registers when Game Viewer contact is lost

### 3. Laptop Changes
- **Discovery Response**: Responds to DISCOVERY messages with registration
- **Periodic Re-registration**: Re-registers every 30 seconds automatically
- **Connection Loss Detection**: Re-registers when Game Viewer contact is lost

## How It Works

1. **Game Viewer starts** → Immediately broadcasts DISCOVERY message
2. **Running robots receive DISCOVERY** → Send DISCOVERY_RESPONSE with their info
3. **Game Viewer receives responses** → Registers robots and they appear in the interface
4. **Ongoing**: Every 15 seconds, Game Viewer broadcasts DISCOVERY
5. **Ongoing**: Every 30 seconds, robots re-register automatically

## Testing

### Manual Testing
1. Start a robot (Pi + Laptop)
2. Start Game Viewer - robot should appear
3. Close Game Viewer
4. Restart Game Viewer - robot should reappear within 15 seconds

### Automated Testing
Run the test script:
```bash
cd /home/rbandaru/Desktop/IC-CODE-2025/CompetitionSystem
python3 test_discovery.py
```

Choose option 1 to simulate a robot listener, then start Game Viewer to see discovery messages.

## Network Configuration

The discovery system uses these communication patterns:

- **Discovery Broadcasts**: Game Viewer → Broadcast addresses (255.255.255.255:6100, 192.168.50.255:6100)
- **Discovery Responses**: Robots → Game Viewer (IP:6000)
- **Registration**: Robots → Game Viewer (periodic)

## Troubleshooting

### Robots Still Don't Appear
1. Check network connectivity between devices
2. Verify firewall allows UDP traffic on ports 6000, 6100
3. Check that robots are listening on correct ports
4. Look for discovery messages in console logs

### Discovery Not Working
1. Ensure Game Viewer has broadcast permissions (automatically enabled)
2. Check subnet configuration (discovery targets 192.168.50.x)
3. Verify robots are bound to 0.0.0.0 (all interfaces)

## Log Messages

Look for these messages to verify discovery is working:

**Game Viewer:**
```
[GV] Discovery thread started
[GV] Immediate discovery broadcast sent - looking for existing robots
[GV] Discovery broadcast sent
[GV] ✅ New team registered: Team Name (ID: 1) on port 6100
[GV] 🔄 Team 1 reconnected: 192.168.50.61:6100
```

**Robot (Pi):**
```
[GameClient] 📡 Discovery received - sending registration
[GameClient] ✅ Registration acknowledged
```

**Laptop:**
```
[GV] 📡 Discovery received - sending registration
[GV] Registration acknowledged
```

## Files Modified

- `GameViewer/game_viewer.py` - Added discovery broadcasting and response handling
- `Pi/game_client.py` - Added discovery response and periodic re-registration
- `Laptop/laptop_control.py` - Added discovery response and periodic re-registration