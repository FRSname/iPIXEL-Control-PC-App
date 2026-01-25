#!/usr/bin/env python3
"""
iPixel LED Panel Controller Launcher
Simple Python launcher that replaces run.bat to avoid Smart App Control issues
"""

import sys
import subprocess
import os

def main():
    """Launch the iPixel Controller"""
    print("=" * 60)
    print("  iPixel LED Panel Controller")
    print("=" * 60)
    print()
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("ERROR: Python 3.8 or higher is required!")
        print(f"You are using Python {sys.version_info.major}.{sys.version_info.minor}")
        input("Press Enter to exit...")
        sys.exit(1)
    
    print(f"✓ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Check if in correct directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    controller_file = os.path.join(script_dir, "ipixel_controller.py")
    
    if not os.path.exists(controller_file):
        print(f"ERROR: Cannot find ipixel_controller.py in {script_dir}")
        input("Press Enter to exit...")
        sys.exit(1)
    
    print(f"✓ Found controller at {controller_file}")
    print()
    
    # Check dependencies
    print("Checking dependencies...")
    required_packages = [
        'pypixelcolor',
        'bleak', 
        'PIL',
        'yfinance',
        'googleapiclient',
        'requests',
        'numpy'
    ]
    
    missing = []
    for package in required_packages:
        try:
            if package == 'PIL':
                __import__('PIL')
            elif package == 'googleapiclient':
                __import__('googleapiclient')
            else:
                __import__(package)
            print(f"  ✓ {package}")
        except ImportError:
            print(f"  ✗ {package} - MISSING")
            missing.append(package)
    
    if missing:
        print()
        print("=" * 60)
        print("MISSING DEPENDENCIES!")
        print("=" * 60)
        print()
        print("Please install missing packages by running:")
        print()
        print("  python -m pip install -r requirements.txt")
        print()
        print("Or install individually:")
        for pkg in missing:
            if pkg == 'PIL':
                print(f"  python -m pip install Pillow")
            elif pkg == 'googleapiclient':
                print(f"  python -m pip install google-api-python-client")
            else:
                print(f"  python -m pip install {pkg}")
        print()
        input("Press Enter to exit...")
        sys.exit(1)
    
    print()
    print("✓ All dependencies installed")
    print()
    print("=" * 60)
    print("Launching iPixel Controller...")
    print("=" * 60)
    print()
    
    # Change to script directory
    os.chdir(script_dir)
    
    # Launch the controller
    try:
        # Use pythonw on Windows to hide console, or python for debugging
        python_exe = sys.executable
        subprocess.run([python_exe, controller_file])
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"\nERROR: {e}")
        input("Press Enter to exit...")
        sys.exit(1)

if __name__ == "__main__":
    main()
