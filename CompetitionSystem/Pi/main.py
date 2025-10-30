#!/usr/bin/env python3
"""
Main Robot Control System
Competition Laser Tag Robot - Complete Integration
"""

import asyncio
import pigpio
import signal
import sys
import time
import json
from typing import Optional

# Import all controllers
from config_manager import ConfigManager
from motor_controller import MotorController
from ir_controller import IRController
from servo_controller import ServoController
from gpio_controller import GPIOController
from camera_streamer import CameraStreamer
from game_client import GameClient

class RobotSystem:
    """Main robot control system"""
    
    def __init__(self):
        print("=" * 60)
        print("🤖 LASER TAG ROBOT COMPETITION SYSTEM 🤖")
        print("=" * 60)
        
        # Load configuration
        self.config_manager = ConfigManager("team_config.json")
        if not self.config_manager.config:
            print("FATAL: Failed to load configuration!")
            sys.exit(1)
        
        self.config = self.config_manager.config
        
        # Initialize pigpio
        self.pi = None
        self.init_pigpio()
        
        # Initialize controllers
        self.motor_controller: Optional[MotorController] = None
        self.ir_controller: Optional[IRController] = None
        self.servo_controller: Optional[ServoController] = None
        self.gpio_controller: Optional[GPIOController] = None
        self.camera_streamer: Optional[CameraStreamer] = None
        self.game_client: Optional[GameClient] = None
        
        # Robot state
        self.vx = 0.0
        self.vy = 0.0
        self.omega = 0.0
        self.speed = 1.0
        self.estop = False
        self.fire = False
        
        # Timing
        self.last_cmd_time = 0.0
        self.last_input_time = 0.0
        self.in_standby = False
        
        # Network
        self.laptop_sock = None
        
        # Initialize all systems
        self.initialize_systems()
    
    def init_pigpio(self):
        """Initialize pigpio daemon connection"""
        print("\n[System] Connecting to pigpiod...")
        self.pi = pigpio.pi()
        
        if not self.pi.connected:
            print("FATAL: pigpiod not running!")
            print("Run: sudo pigpiod")
            sys.exit(1)
        
        print("[System] ✅ Connected to pigpiod")
    
    def initialize_systems(self):
        """Initialize all robot subsystems"""
        print("\n[System] Initializing subsystems...")
        
        # Motor controller
        self.motor_controller = MotorController(self.pi, self.config)
        
        # IR controller
        gv_ip = self.config['network']['game_viewer_ip']
        gv_port = self.config['network']['game_viewer_control_port']
        team_id = self.config['team']['team_id']
        
        self.ir_controller = IRController(self.pi, self.config, team_id, gv_ip, gv_port)
        self.ir_controller.on_hit_callback = self.on_robot_hit
        
        # Servo controller
        self.servo_controller = ServoController(self.pi, self.config)
        
        # GPIO controller
        self.gpio_controller = GPIOController(self.pi, self.config)
        
        # Camera streamer
        self.camera_streamer = CameraStreamer(self.config)
        
        # Game client
        self.game_client = GameClient(self.config)
        self.game_client.on_game_start = self.on_game_start
        self.game_client.on_game_end = self.on_game_end
        self.game_client.on_ready_check = self.on_ready_check
        self.game_client.on_points_update = self.on_points_update
        
        # Start game client
        self.game_client.start()
        
        # Setup laptop UDP listener
        self.setup_laptop_communication()
        
        print("[System] ✅ All subsystems initialized")
    
    def setup_laptop_communication(self):
        """Setup UDP socket for laptop communication"""
        import socket
        
        self.laptop_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.laptop_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.laptop_sock.settimeout(0.001)
        
        listen_port = self.config['network']['robot_listen_port']
        self.laptop_sock.bind(('0.0.0.0', listen_port))
        
        print(f"[System] Listening for laptop commands on port {listen_port}")
    
    def on_robot_hit(self):
        """Called when robot is hit"""
        print("[System] 💥 Robot hit - entering disabled state")
        self.motor_controller.stop_all()
        self.motor_controller.enter_standby()
        self.in_standby = True
        
        # Update game client stats
        self.game_client.deaths += 1
        
        # Flash lights if configured
        if 'd1' in self.gpio_controller.lights:
            self.gpio_controller.toggle_light('d1')
    
    def on_game_start(self):
        """Called when game starts"""
        print("[System] 🎮 GAME STARTING!")
        self.ir_controller.start_game()
        self.camera_streamer.start_stream()
        
        # Flash lights
        if 'd1' in self.gpio_controller.lights:
            self.gpio_controller.set_light('d1', True)
        if 'd2' in self.gpio_controller.lights:
            self.gpio_controller.set_light('d2', True)
    
    def on_game_end(self):
        """Called when game ends"""
        print("[System] 🏁 GAME ENDED!")
        self.ir_controller.end_game()
        self.motor_controller.stop_all()
        
        # Print stats
        hit_log = self.ir_controller.get_hit_log()
        print(f"[System] Game Stats:")
        print(f"  - Total Hits Received: {len(hit_log)}")
        print(f"  - Points: {self.game_client.points}")
        print(f"  - K/D: {self.game_client.kills}/{self.game_client.deaths}")
        
        # Turn off lights
        if 'd1' in self.gpio_controller.lights:
            self.gpio_controller.set_light('d1', False)
        if 'd2' in self.gpio_controller.lights:
            self.gpio_controller.set_light('d2', False)
    
    def on_ready_check(self):
        """Called when GV asks if ready"""
        print("[System] 📢 Ready check received - auto-responding ready")
        self.game_client.send_ready(True)
    
    def on_points_update(self, points: int):
        """Called when points are updated"""
        # Could flash lights or do something visual
        pass
    
    def process_laptop_command(self):
        """Process commands from laptop"""
        try:
            data, addr = self.laptop_sock.recvfrom(1024)
            message = json.loads(data.decode('utf-8'))
            
            # Update robot state
            self.vx = float(message.get('vx', 0))
            self.vy = float(message.get('vy', 0))
            self.omega = float(message.get('omega', 0))
            self.speed = max(0.0, min(1.0, float(message.get('speed', 1.0))))
            self.estop = bool(message.get('estop', False))
            self.fire = bool(message.get('fire', False))
            
            self.last_cmd_time = time.time()
            
            if 'last_input_time' in message:
                self.last_input_time = float(message['last_input_time'])
            
            # Handle servo commands
            if 'servo_1' in message:
                self.servo_controller.set_servo_normalized('servo_1', message['servo_1'])
            if 'servo_2' in message:
                self.servo_controller.set_servo_normalized('servo_2', message['servo_2'])
            
            # Handle GPIO commands
            if 'gpio_commands' in message:
                for gpio_name, value in message['gpio_commands'].items():
                    self.gpio_controller.set_gpio(gpio_name, value)
            
            # Handle light commands
            if 'light_commands' in message:
                for light_name, state in message['light_commands'].items():
                    self.gpio_controller.set_light(light_name, state)
            
            # Fire weapon
            if self.fire:
                self.ir_controller.fire()
            
            # Exit standby if movement detected
            if self.in_standby and (abs(self.vx) > 0.05 or abs(self.vy) > 0.05 or 
                                   abs(self.omega) > 0.05 or self.estop):
                if not self.ir_controller.is_hit:
                    self.motor_controller.exit_standby()
                    self.in_standby = False
            
            # Send status back to laptop
            response = {
                "ir_status": self.ir_controller.get_status(),
                "game_status": self.game_client.get_status(),
                "camera_active": self.camera_streamer.is_alive()
            }
            
            self.laptop_sock.sendto(json.dumps(response).encode('utf-8'), addr)
        
        except Exception:
            pass
    
    async def control_loop(self):
        """Main control loop"""
        print("\n[System] 🚀 Starting main control loop")
        
        command_timeout = self.config['safety']['command_timeout_s']
        power_save_timeout = self.config['safety']['power_save_timeout_s']
        
        while True:
            now = time.time()
            
            # Process laptop commands
            self.process_laptop_command()
            
            # Update IR hit timer
            self.ir_controller.update()
            
            # Motor control logic
            if self.ir_controller.is_hit or self.estop or (now - self.last_cmd_time) > command_timeout:
                # Stop motors if hit, estop, or timeout
                self.motor_controller.stop_all()
            
            elif (now - self.last_input_time) > power_save_timeout and not self.in_standby:
                # Enter power save mode
                self.motor_controller.enter_standby()
                self.in_standby = True
            
            elif not self.in_standby and not self.ir_controller.is_hit:
                # Normal driving
                self.motor_controller.drive_mecanum(self.vx, self.vy, self.omega, self.speed)
            
            await asyncio.sleep(0.02)  # 50 Hz
    
    def cleanup(self):
        """Clean up all resources"""
        print("\n[System] 🛑 Shutting down...")
        
        if self.motor_controller:
            self.motor_controller.cleanup()
        
        if self.ir_controller:
            self.ir_controller.cleanup()
        
        if self.servo_controller:
            self.servo_controller.cleanup()
        
        if self.gpio_controller:
            self.gpio_controller.cleanup()
        
        if self.camera_streamer:
            self.camera_streamer.cleanup()
        
        if self.game_client:
            self.game_client.cleanup()
        
        if self.laptop_sock:
            self.laptop_sock.close()
        
        if self.pi:
            self.pi.stop()
        
        print("[System] ✅ Shutdown complete")
    
    async def run(self):
        """Main run function"""
        # Setup signal handlers
        loop = asyncio.get_running_loop()
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
        
        print("\n" + "=" * 60)
        print(f"🎯 {self.config['team']['team_name']} - {self.config['team']['robot_name']}")
        print(f"Team ID: {self.config['team']['team_id']}")
        print("=" * 60)
        print("\n✅ System ready - waiting for commands")
        
        try:
            await self.control_loop()
        except asyncio.CancelledError:
            pass
        finally:
            self.cleanup()
    
    async def shutdown(self):
        """Graceful shutdown"""
        print("\n[System] Shutdown signal received")
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        asyncio.get_event_loop().stop()


def main():
    """Entry point"""
    try:
        robot = RobotSystem()
        asyncio.run(robot.run())
    
    except KeyboardInterrupt:
        print("\n[System] Keyboard interrupt")
    
    except Exception as e:
        print(f"\n[System] FATAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        print("[System] Exiting")


if __name__ == "__main__":
    main()
