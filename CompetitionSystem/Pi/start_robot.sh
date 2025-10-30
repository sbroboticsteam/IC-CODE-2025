#!/bin/bash
# Startup script for competition robot
# Run this to start the robot system

echo "=================================="
echo "  Competition Robot Startup"
echo "=================================="

# Check if pigpiod is running
if ! pgrep -x "pigpiod" > /dev/null; then
    echo "Starting pigpiod daemon..."
    sudo pigpiod
    sleep 1
fi

# Set file permissions (protect IR and game client code)
echo "Setting file permissions..."
chmod 444 ir_controller.py
chmod 444 game_client.py
chmod 644 team_config.json
chmod 755 main.py

# Make sure we're in the right directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the robot system
echo "Starting robot system..."
python3 main.py

# Cleanup on exit
echo "Stopping pigpiod..."
sudo killall pigpiod

echo "Shutdown complete"
