#!/usr/bin/env python3
"""
Configuration Manager - Handles loading and validation of team_config.json
"""

import json
import os
import sys
from typing import Dict, Any

class ConfigManager:
    def __init__(self, config_file: str = "team_config.json"):
        self.config_file = config_file
        self.config: Dict[str, Any] = {}
        self.load_config()
    
    def load_config(self) -> bool:
        """Load configuration from JSON file"""
        try:
            if not os.path.exists(self.config_file):
                print(f"ERROR: Config file '{self.config_file}' not found!", file=sys.stderr)
                return False
            
            with open(self.config_file, 'r') as f:
                self.config = json.load(f)
            
            print(f"[Config] Loaded configuration")
            print(f"[Config] Team: {self.config['team']['team_name']} (ID: {self.config['team']['team_id']})")
            
            # Validate critical settings
            if not self.validate_config():
                print("ERROR: Configuration validation failed!", file=sys.stderr)
                return False
            
            return True
        
        except json.JSONDecodeError as e:
            print(f"ERROR: Invalid JSON in config file: {e}", file=sys.stderr)
            return False
        except Exception as e:
            print(f"ERROR: Failed to load config: {e}", file=sys.stderr)
            return False
    
    def validate_config(self) -> bool:
        """Validate configuration"""
        try:
            # Check team ID
            team_id = self.config['team']['team_id']
            if not (1 <= team_id <= 255):
                print("ERROR: Team ID must be between 1 and 255", file=sys.stderr)
                return False
            
            # Check motor pins are not duplicated
            motor_pins = []
            for motor in self.config['motors'].values():
                if isinstance(motor, dict) and 'EN' in motor:
                    motor_pins.extend([motor['EN'], motor['IN1'], motor['IN2']])
            
            if len(motor_pins) != len(set(motor_pins)):
                print("ERROR: Duplicate motor GPIO pins detected", file=sys.stderr)
                return False
            
            # Check IR pins
            ir_tx = self.config['ir_system']['transmitter_gpio']
            ir_rx = self.config['ir_system']['receiver_gpios']
            
            if ir_tx in motor_pins or any(rx in motor_pins for rx in ir_rx):
                print("ERROR: IR pins conflict with motor pins", file=sys.stderr)
                return False
            
            # Validate network settings
            if not self.config['network']['game_viewer_ip']:
                print("WARNING: Game Viewer IP not configured", file=sys.stderr)
            
            print("[Config] Validation passed")
            return True
        
        except KeyError as e:
            print(f"ERROR: Missing required config key: {e}", file=sys.stderr)
            return False
    
    def get(self, *keys):
        """Get nested config value"""
        value = self.config
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        return value
    
    def save_config(self) -> bool:
        """Save current configuration back to file"""
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            print("[Config] Configuration saved")
            return True
        except Exception as e:
            print(f"ERROR: Failed to save config: {e}", file=sys.stderr)
            return False
    
    def update_value(self, value, *keys):
        """Update a nested config value"""
        config = self.config
        for key in keys[:-1]:
            config = config.setdefault(key, {})
        config[keys[-1]] = value
    
    def get_team_id(self) -> int:
        return self.config['team']['team_id']
    
    def get_team_name(self) -> str:
        return self.config['team']['team_name']
    
    def get_motor_config(self) -> dict:
        return self.config['motors']
    
    def get_ir_config(self) -> dict:
        return self.config['ir_system']
    
    def get_network_config(self) -> dict:
        return self.config['network']
    
    def get_servo_config(self) -> dict:
        return self.config['servos']
    
    def get_gpio_config(self) -> dict:
        return self.config['extra_gpios']
    
    def get_lights_config(self) -> dict:
        return self.config['lights']
    
    def get_camera_config(self) -> dict:
        return self.config['camera']
    
    def get_safety_config(self) -> dict:
        return self.config['safety']
