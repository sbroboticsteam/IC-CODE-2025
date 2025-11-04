#!/usr/bin/env python3
"""
Motor Controller - Mecanum drive control with PWM
"""

import pigpio
from typing import Dict

class MotorController:
    def __init__(self, pi: pigpio.pi, config: Dict):
        self.pi = pi
        self.motors = config['motors']
        self.standby_pins = self.motors.get('standby_pins', [])
        self.pwm_freq = self.motors.get('pwm_frequency', 10000)
        self.min_duty = self.motors.get('min_duty_cycle', 30)
        self.pure_dc_threshold = self.motors.get('pure_dc_threshold', 80)
        
        self.setup_motors()
    
    def setup_motors(self):
        """Initialize motor GPIO pins"""
        print("[Motors] Initializing motor controller...")
        
        # Setup standby pins
        for pin in self.standby_pins:
            self.pi.set_mode(pin, pigpio.OUTPUT)
            self.pi.write(pin, 1)  # Enable motors
        
        # Setup motor pins
        for name, motor in self.motors.items():
            if not isinstance(motor, dict) or 'EN' not in motor:
                continue
            
            for pin_type in ('EN', 'IN1', 'IN2'):
                pin = motor[pin_type]
                self.pi.set_mode(pin, pigpio.OUTPUT)
                self.pi.write(pin, 0)
            
            # Set PWM frequency on enable pin
            self.pi.set_PWM_frequency(motor['EN'], self.pwm_freq)
        
        print(f"[Motors] Initialized {len([m for m in self.motors.values() if isinstance(m, dict) and 'EN' in m])} motors")
    
    def clamp(self, value: float, min_val: float = -1.0, max_val: float = 1.0) -> float:
        """Clamp value between min and max"""
        return max(min_val, min(max_val, value))
    
    def apply_motor(self, motor_name: str, normalized_speed: float):
        """Apply speed to a single motor"""
        if motor_name not in self.motors or not isinstance(self.motors[motor_name], dict):
            return
        
        motor = self.motors[motor_name]
        direction_offset = motor.get('direction_offset', 1)
        normalized_speed = self.clamp(normalized_speed) * direction_offset
        
        pins = motor
        
        # Stop motor if speed is near zero
        if abs(normalized_speed) < 1e-3:
            self.pi.set_PWM_dutycycle(pins['EN'], 0)
            self.pi.write(pins['IN1'], 0)
            self.pi.write(pins['IN2'], 0)
            return
        
        # Set direction
        forward = normalized_speed > 0
        self.pi.write(pins['IN1'], 1 if forward else 0)
        self.pi.write(pins['IN2'], 0 if forward else 1)
        
        # Set speed
        percent = int(abs(normalized_speed) * 100)
        
        if percent >= self.pure_dc_threshold:
            # Use pure DC for high speeds
            self.pi.write(pins['EN'], 1)
        else:
            # Use PWM for lower speeds
            percent = max(self.min_duty, percent)
            duty = percent * 255 // 100
            self.pi.set_PWM_dutycycle(pins['EN'], duty)
    
    def drive_mecanum( self,
    vx: float,           # strafe: left(-) / right(+)
    vy: float,           # forward(+)/ backward(-)
    omega: float,        # rotation: CCW(-) / CW(+)
    max_speed: float=1.0,
    wheelbase: float=1.0,   # front-back distance (m, arbitrary scale)
    track: float=1.0,       # left-right distance (m, arbitrary scale)
    field_centric: bool=False,
    yaw_rad: float=0.0,     # robot yaw for field-centric
    invert=(False, False, False, False) # (FL, FR, RL, RR) motor invert flags
    ):
        """
        Proper mecanum inverse kinematics.
        Conventions (matches your docstring):
        vx: +right, vy: +forward, omega: +CW (note: CW positive)
        """

        # Optional: rotate command from field frame into robot frame
        if field_centric:
            import math
            cy, sy = math.cos(yaw_rad), math.sin(yaw_rad)
            # field -> robot (x right, y forward)
            vx, vy =  cy*vx + sy*vy, -sy*vx + cy*vy

        # Geometry term (half perimeter from center to wheel contact)
        k = 0.5*(wheelbase + track)

        # Wheel speeds (unnormalized)
        fl =  vy + vx + omega * k   # Front-Left
        fr =  vy - vx - omega * k   # Front-Right
        rl =  vy - vx + omega * k   # Rear-Left
        rr =  vy + vx - omega * k   # Rear-Right

        # Normalize to keep |speed| <= 1
        max_mag = max(1.0, abs(fl), abs(fr), abs(rl), abs(rr))
        fl, fr, rl, rr = fl/max_mag, fr/max_mag, rl/max_mag, rr/max_mag

        # Scale by requested speed (0..1)
        fl *= -max_speed
        fr *= max_speed
        rl *= -max_speed
        rr *= max_speed

        # Per-wheel inversion for wiring differences
        if invert[0]: fl = -fl
        if invert[1]: fr = -fr
        if invert[2]: rl = -rl
        if invert[3]: rr = -rr

        # Optional tiny deadband to kill motor buzz
        def deadband(x, eps=0.02): return 0.0 if abs(x) < eps else x
        fl, fr, rl, rr = map(deadband, (fl, fr, rl, rr))

        # Apply to motors (A=FL, B=FR, C=RL, D=RR per your mapping)
        self.apply_motor('A', fl)
        self.apply_motor('B', fr)
        self.apply_motor('C', rl)
        self.apply_motor('D', rr)

    
    def stop_all(self):
        """Stop all motors immediately"""
        for name in ['A', 'B', 'C', 'D']:
            if name in self.motors:
                motor = self.motors[name]
                if isinstance(motor, dict) and 'EN' in motor:
                    self.pi.set_PWM_dutycycle(motor['EN'], 0)
                    self.pi.write(motor['IN1'], 0)
                    self.pi.write(motor['IN2'], 0)
    
    def enter_standby(self):
        """Enter low power standby mode"""
        print("[Motors] Entering standby mode")
        self.stop_all()
        for pin in self.standby_pins:
            self.pi.write(pin, 0)
    
    def exit_standby(self):
        """Exit standby mode"""
        print("[Motors] Exiting standby mode")
        for pin in self.standby_pins:
            self.pi.write(pin, 1)
    
    def cleanup(self):
        """Clean up motor resources"""
        print("[Motors] Cleaning up...")
        self.stop_all()
        for pin in self.standby_pins:
            self.pi.write(pin, 0)
