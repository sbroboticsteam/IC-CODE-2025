# install_requirements.py
# Run this script to install all required packages for Xbox controller interface

import subprocess
import sys

def install_package(package):
    """Install a package using pip"""
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✓ Successfully installed {package}")
        return True
    except subprocess.CalledProcessError:
        print(f"✗ Failed to install {package}")
        return False

def main():
    print("Installing required packages for Xbox Controller Robot Interface...")
    print("=" * 60)
    
    packages = [
        "pygame",           # Xbox controller input
        "opencv-python",    # Video processing
        "pillow",          # Image processing for GUI
        "pynput",          # Alternative input method (from original)
    ]
    
    failed_packages = []
    
    for package in packages:
        print(f"\nInstalling {package}...")
        if not install_package(package):
            failed_packages.append(package)
    
    print("\n" + "=" * 60)
    if failed_packages:
        print("❌ Installation completed with errors!")
        print("Failed packages:", ", ".join(failed_packages))
        print("\nPlease install these manually:")
        for pkg in failed_packages:
            print(f"  pip install {pkg}")
    else:
        print("✅ All packages installed successfully!")
        print("\nYou can now run:")
        print("  python xbox_control.py")
    
    print("\nNote: Make sure you have:")
    print("1. Xbox controller connected to Windows")
    print("2. Updated the IP addresses in the config section")
    print("3. GStreamer installed (if using video stream)")

if __name__ == "__main__":
    main()
