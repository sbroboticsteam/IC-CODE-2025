#!/usr/bin/env python3
"""
Test script to verify the discovery mechanism works
Run this to test if robots can be rediscovered when Game Viewer restarts
"""

import json
import socket
import time

def test_robot_listener():
    """Simulate a robot listening for discovery messages"""
    print("🤖 Starting test robot listener...")
    
    # Create socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.settimeout(1.0)
    
    try:
        # Bind to port that robots would use
        sock.bind(('0.0.0.0', 6100))
        print("📡 Listening on port 6100 for discovery messages...")
        
        while True:
            try:
                data, addr = sock.recvfrom(4096)
                message = json.loads(data.decode('utf-8'))
                
                print(f"📨 Received message from {addr}: {message}")
                
                if message.get('type') == 'DISCOVERY':
                    print("🔍 Discovery message received! Sending response...")
                    
                    # Send response
                    response = {
                        'type': 'DISCOVERY_RESPONSE',
                        'team_id': 1,
                        'team_name': 'Test Team',
                        'robot_name': 'Test Robot',
                        'listen_port': 6100,
                        'timestamp': time.time()
                    }
                    
                    # Send to Game Viewer
                    gv_addr = (message.get('gv_ip', '192.168.50.67'), message.get('gv_port', 6000))
                    response_data = json.dumps(response).encode('utf-8')
                    sock.sendto(response_data, gv_addr)
                    print(f"✅ Sent discovery response to {gv_addr}")
                    
            except socket.timeout:
                continue
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    finally:
        sock.close()
        print("🛑 Test robot listener stopped")

def test_discovery_broadcast():
    """Send a test discovery broadcast"""
    print("📡 Sending test discovery broadcast...")
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    
    try:
        discovery_message = {
            'type': 'DISCOVERY',
            'gv_ip': '192.168.50.67',
            'gv_port': 6000,
            'timestamp': time.time()
        }
        
        data = json.dumps(discovery_message).encode('utf-8')
        
        # Send to broadcast addresses
        addresses = [
            ('255.255.255.255', 6100),
            ('192.168.50.255', 6100),
            ('127.0.0.1', 6100),  # Localhost for testing
        ]
        
        for addr in addresses:
            try:
                sock.sendto(data, addr)
                print(f"📤 Sent discovery to {addr}")
            except Exception as e:
                print(f"❌ Failed to send to {addr}: {e}")
        
        print("✅ Discovery broadcast complete")
        
    finally:
        sock.close()

def main():
    print("🔧 Discovery Mechanism Test")
    print("=" * 40)
    print()
    print("Choose test mode:")
    print("1. Robot listener (receive discovery)")
    print("2. Send discovery broadcast")
    print("3. Exit")
    print()
    
    choice = input("Enter choice (1-3): ").strip()
    
    if choice == '1':
        test_robot_listener()
    elif choice == '2':
        test_discovery_broadcast()
    elif choice == '3':
        print("👋 Goodbye!")
    else:
        print("❌ Invalid choice")

if __name__ == "__main__":
    main()