# fix_opencv.py
# Script to fix OpenCV installation issues on Windows

import subprocess
import sys
import os

def run_command(cmd):
    """Run a command and return success status"""
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        print(f"Command: {cmd}")
        if result.returncode == 0:
            print("✅ Success")
            if result.stdout:
                print(result.stdout)
        else:
            print("❌ Failed")
            if result.stderr:
                print(result.stderr)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Error running command: {e}")
        return False

def main():
    print("🔧 OpenCV Fix Tool for Windows")
    print("=" * 40)
    
    print("\n1. Uninstalling existing OpenCV packages...")
    packages_to_remove = [
        "opencv-python",
        "opencv-contrib-python",
        "opencv-python-headless",
        "opencv-contrib-python-headless"
    ]
    
    for package in packages_to_remove:
        run_command(f"{sys.executable} -m pip uninstall -y {package}")
    
    print("\n2. Updating pip...")
    run_command(f"{sys.executable} -m pip install --upgrade pip")
    
    print("\n3. Installing OpenCV with specific version...")
    # Try different approaches
    approaches = [
        f"{sys.executable} -m pip install opencv-python==4.8.1.78",
        f"{sys.executable} -m pip install opencv-python --no-cache-dir",
        f"{sys.executable} -m pip install opencv-python-headless"
    ]
    
    success = False
    for approach in approaches:
        print(f"\nTrying: {approach}")
        if run_command(approach):
            success = True
            break
        print("Failed, trying next approach...")
    
    print("\n4. Testing OpenCV installation...")
    test_code = """
import cv2
print(f"OpenCV version: {cv2.__version__}")
print("✅ OpenCV is working correctly!")
"""
    
    try:
        exec(test_code)
        print("🎉 OpenCV installation successful!")
        return True
    except ImportError as e:
        print(f"❌ OpenCV still not working: {e}")
        print("\n🔧 Alternative Solutions:")
        print("1. Try: pip install opencv-python-headless (no GUI features)")
        print("2. Use xbox_control_simple.py instead (no OpenCV required)")
        print("3. Install Visual C++ Redistributables from Microsoft")
        print("4. Restart your command prompt/IDE")
        return False

if __name__ == "__main__":
    main()
    input("\nPress Enter to exit...")
