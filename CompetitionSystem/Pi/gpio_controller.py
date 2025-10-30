#!/usr/bin/env python3
"""
GPIO Controller - Manages extra GPIOs and status lights
"""

import pigpio
from typing import Dict

class GPIOController:
    def __init__(self, pi: pigpio.pi, config: Dict):
        self.pi = pi
        self.gpio_config = config.get('extra_gpios', {})
        self.lights_config = config.get('lights', {})
        
        self.gpios = {}
        self.lights = {}
        
        self.setup_gpios()
        self.setup_lights()
    
    def setup_gpios(self):
        """Initialize extra GPIO pins"""
        print("[GPIO] Initializing extra GPIOs...")
        
        for name, gpio_cfg in self.gpio_config.items():
            # Skip comment fields
            if name.startswith('_'):
                continue
            
            # Ensure gpio_cfg is a dict
            if not isinstance(gpio_cfg, dict):
                print(f"[GPIO] Skipping {name} - invalid config type")
                continue
            
            if not gpio_cfg.get('enabled', False):
                continue
            
            gpio = gpio_cfg['gpio']
            if gpio == 0:
                continue
            
            mode = gpio_cfg.get('mode', 'output').lower()
            pull = gpio_cfg.get('pull', 'none').lower()
            initial_state = gpio_cfg.get('initial_state', 0)
            
            # Set mode
            if mode == 'input':
                self.pi.set_mode(gpio, pigpio.INPUT)
                
                # Set pull resistor
                if pull == 'up':
                    self.pi.set_pull_up_down(gpio, pigpio.PUD_UP)
                elif pull == 'down':
                    self.pi.set_pull_up_down(gpio, pigpio.PUD_DOWN)
                else:
                    self.pi.set_pull_up_down(gpio, pigpio.PUD_OFF)
            else:
                self.pi.set_mode(gpio, pigpio.OUTPUT)
                self.pi.write(gpio, initial_state)
            
            self.gpios[name] = {
                'gpio': gpio,
                'mode': mode,
                'description': gpio_cfg.get('description', name)
            }
            
            print(f"[GPIO] {name} ({gpio_cfg.get('description', '')}) on GPIO {gpio} [{mode}]")
        
        if not self.gpios:
            print("[GPIO] No extra GPIOs configured")
    
    def setup_lights(self):
        """Initialize status lights"""
        print("[GPIO] Initializing status lights...")
        
        for name, light_cfg in self.lights_config.items():
            # Skip comment fields
            if name.startswith('_'):
                continue
            
            # Ensure light_cfg is a dict
            if not isinstance(light_cfg, dict):
                print(f"[GPIO] Skipping {name} - invalid config type")
                continue
            
            if not light_cfg.get('enabled', False):
                continue
            
            gpio = light_cfg['gpio']
            if gpio == 0:
                continue
            
            initial_state = light_cfg.get('initial_state', 0)
            
            self.pi.set_mode(gpio, pigpio.OUTPUT)
            self.pi.write(gpio, initial_state)
            
            self.lights[name] = {
                'gpio': gpio,
                'state': initial_state
            }
            
            print(f"[GPIO] Light {name} on GPIO {gpio}")
        
        if not self.lights:
            print("[GPIO] No lights configured")
    
    def set_gpio(self, name: str, value: int) -> bool:
        """Set GPIO output value"""
        if name not in self.gpios:
            return False
        
        gpio_info = self.gpios[name]
        if gpio_info['mode'] != 'output':
            return False
        
        self.pi.write(gpio_info['gpio'], 1 if value else 0)
        return True
    
    def get_gpio(self, name: str) -> int:
        """Read GPIO value"""
        if name not in self.gpios:
            return -1
        
        return self.pi.read(self.gpios[name]['gpio'])
    
    def set_light(self, name: str, state: bool) -> bool:
        """Set light on/off (INVERTED - Active LOW for ground-connected LEDs)"""
        if name not in self.lights:
            return False
        
        light = self.lights[name]
        # Invert: LOW (0) = ON, HIGH (1) = OFF
        inverted_state = 0 if state else 1
        self.pi.write(light['gpio'], inverted_state)
        light['state'] = 1 if state else 0  # Store logical state
        return True
    
    def toggle_light(self, name: str) -> bool:
        """Toggle light state"""
        if name not in self.lights:
            return False
        
        light = self.lights[name]
        new_state = 1 - light['state']
        return self.set_light(name, new_state)
    
    def get_light_state(self, name: str) -> int:
        """Get current light state"""
        if name not in self.lights:
            return -1
        return self.lights[name]['state']
    
    def set_pwm(self, name: str, duty_cycle: int) -> bool:
        """Set PWM duty cycle (0-255) on a GPIO"""
        if name not in self.gpios:
            return False
        
        gpio_info = self.gpios[name]
        if gpio_info['mode'] != 'output':
            return False
        
        duty_cycle = max(0, min(255, duty_cycle))
        self.pi.set_PWM_dutycycle(gpio_info['gpio'], duty_cycle)
        return True
    
    def cleanup(self):
        """Clean up GPIO resources"""
        print("[GPIO] Cleaning up...")
        
        # Turn off all lights
        for name in self.lights.keys():
            self.set_light(name, False)
        
        # Set all output GPIOs to 0
        for name, gpio_info in self.gpios.items():
            if gpio_info['mode'] == 'output':
                self.pi.write(gpio_info['gpio'], 0)
