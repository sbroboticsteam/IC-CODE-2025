#!/usr/bin/env python3
"""
Quick UDP test script
"""
import socket
import json
import time
import sys

PI_IP = "192.168.50.147"
PI_PORT = 5005

print("=" * 50)
print("UDP CONNECTION TEST")
print("=" * 50)
print(f"Target: {PI_IP}:{PI_PORT}")
print()

# Get local IP
hostname = socket.gethostname()
local_ip = socket.gethostbyname(hostname)
print(f"Source: {local_ip}")
print()

# Create socket
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# Test 1: Send heartbeat
print("Test 1: Sending HEARTBEAT...")
message = {'type': 'HEARTBEAT'}
data = json.dumps(message).encode('utf-8')
try:
    sock.sendto(data, (PI_IP, PI_PORT))
    print(f"✅ Sent {len(data)} bytes")
except Exception as e:
    print(f"❌ Failed: {e}")

time.sleep(0.5)

# Test 2: Send control command
print("\nTest 2: Sending CONTROL command...")
message = {
    'type': 'CONTROL',
    'vx': 0.5,
    'vy': 0.5,
    'vr': 0.0,
    'servo1': 0.5,
    'servo2': 0.5,
    'gpio': [False, False, False, False],
    'lights': False
}
data = json.dumps(message).encode('utf-8')
try:
    sock.sendto(data, (PI_IP, PI_PORT))
    print(f"✅ Sent {len(data)} bytes")
except Exception as e:
    print(f"❌ Failed: {e}")

time.sleep(0.5)

# Test 3: Send fire command
print("\nTest 3: Sending FIRE command...")
message = {
    'type': 'CONTROL',
    'vx': 0.0,
    'vy': 0.0,
    'vr': 0.0,
    'fire': True,
    'servo1': 0.5,
    'servo2': 0.5,
    'gpio': [False, False, False, False],
    'lights': False
}
data = json.dumps(message).encode('utf-8')
try:
    sock.sendto(data, (PI_IP, PI_PORT))
    print(f"✅ Sent {len(data)} bytes")
except Exception as e:
    print(f"❌ Failed: {e}")

sock.close()

print()
print("=" * 50)
print("Check Pi terminal for received messages")
print("If nothing appears, there's a network issue")
print("=" * 50)
