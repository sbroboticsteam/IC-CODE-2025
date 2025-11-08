#!/usr/bin/env python3
"""
Servo Controller - Controls two servo channels with 1000-2000us pulses
"""

import pigpio
import time
from typing import Dict

class ServoController:
    def __init__(self, pi: pigpio.pi, config: Dict):
        self.pi = pi
        self.config = config['servos']
        self.servos = {}
        
        self.setup_servos()
    
    def setup_servos(self):
        """Initialize servo channels"""
        print("[Servo] Initializing servo controller...")
        
        for name, servo_config in self.config.items():
            # Skip comment fields
            if name.startswith('_'):
                continue
            
            # Ensure servo_config is a dict
            if not isinstance(servo_config, dict):
                print(f"[Servo] Skipping {name} - invalid config type")
                continue
            
            if not servo_config.get('enabled', False):
                print(f"[Servo] {name} disabled in config")
                continue
            
            gpio = servo_config['gpio']
            if gpio == 0:
                print(f"[Servo] {name} not configured (GPIO = 0)")
                continue
            
            # Setup GPIO for servo - CRITICAL: Set mode first!
            self.pi.set_mode(gpio, pigpio.OUTPUT)
            
            # IMPORTANT: Stop any existing servo signal first
            self.pi.set_servo_pulsewidth(gpio, 0)
            time.sleep(0.1)
            
            # Set to default position
            default_pulse = servo_config.get('default_position', 1500)
            self.pi.set_servo_pulsewidth(gpio, default_pulse)
            
            # Verify it's working
            actual_pulse = self.pi.get_servo_pulsewidth(gpio)
            if actual_pulse == 0:
                print(f"[Servo] ⚠️ {name} - Failed to set pulse! Check GPIO {gpio}")
            else:
                print(f"[Servo] {name} initialized on GPIO {gpio} - pulse: {actual_pulse}us")
            
            self.servos[name] = {
                'gpio': gpio,
                'min_pulse': servo_config.get('min_pulse_us', 1000),
                'max_pulse': servo_config.get('max_pulse_us', 2000),
                'current_pulse': default_pulse
            }
            
            print(f"[Servo] {name} initialized on GPIO {gpio}")
        
        if not self.servos:
            print("[Servo] No servos configured")
    
    def set_servo_pulse(self, name: str, pulse_width_us: int):
        """Set servo pulse width directly (1000-2000us)"""
        if name not in self.servos:
            return False
        
        servo = self.servos[name]
        
        # Clamp to valid range
        pulse_width_us = max(servo['min_pulse'], min(servo['max_pulse'], pulse_width_us))
        
        self.pi.set_servo_pulsewidth(servo['gpio'], pulse_width_us)
        servo['current_pulse'] = pulse_width_us
        
        # Debug: Print first time servo moves
        if not hasattr(self, f'_debug_{name}_moved'):
            setattr(self, f'_debug_{name}_moved', True)
            print(f"[Servo] {name} moved to {pulse_width_us}us")
        
        return True
    
    def set_servo_normalized(self, name: str, value: float):
        """
        Set servo position with normalized value (-1.0 to 1.0)
        -1.0 = min pulse (1000us)
        0.0 = center (1500us)
        1.0 = max pulse (2000us)
        """
        if name not in self.servos:
            return False
        
        servo = self.servos[name]
        
        # Clamp value
        value = max(-1.0, min(1.0, value))
        
        # Map to pulse width
        center = (servo['min_pulse'] + servo['max_pulse']) / 2
        half_range = (servo['max_pulse'] - servo['min_pulse']) / 2
        pulse_width = int(center + (value * half_range))
        
        return self.set_servo_pulse(name, pulse_width)
    
    def set_servo_percent(self, name: str, percent: float):
        """
        Set servo position with percentage (0-100)
        0% = min pulse, 100% = max pulse
        """
        if name not in self.servos:
            return False
        
        servo = self.servos[name]
        
        # Clamp percent
        percent = max(0, min(100, percent))
        
        # Map to pulse width
        pulse_range = servo['max_pulse'] - servo['min_pulse']
        pulse_width = int(servo['min_pulse'] + (pulse_range * percent / 100))
        
        return self.set_servo_pulse(name, pulse_width)
    
    def get_servo_pulse(self, name: str) -> int:
        """Get current pulse width"""
        if name not in self.servos:
            return 0
        return self.servos[name]['current_pulse']
    
    def disable_servo(self, name: str):
        """Disable servo (stop sending pulses)"""
        if name not in self.servos:
            return False
        
        servo = self.servos[name]
        self.pi.set_servo_pulsewidth(servo['gpio'], 0)
        return True
    
    def cleanup(self):
        """Clean up servo resources"""
        print("[Servo] Cleaning up...")
        for name, servo in self.servos.items():
            self.pi.set_servo_pulsewidth(servo['gpio'], 0)
