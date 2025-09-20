# -*- coding: utf-8 -*-
"""
Install Web GUI Dependencies
สคริปต์ติดตั้ง dependencies สำหรับ Web GUI
"""

import subprocess
import sys
import os

def install_requirements():
    """ติดตั้ง requirements สำหรับ Web GUI"""
    try:
        print("🚀 Installing Web GUI dependencies...")
        
        # ติดตั้ง aiohttp และ dependencies
        packages = [
            "aiohttp>=3.8.0",
            "aiohttp-cors>=0.7.0",
            "psutil>=5.9.0"
        ]
        
        for package in packages:
            print(f"📦 Installing {package}...")
            result = subprocess.run([
                sys.executable, "-m", "pip", "install", package
            ], capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ {package} installed successfully")
            else:
                print(f"❌ Failed to install {package}")
                print(f"Error: {result.stderr}")
                return False
        
        print("🎉 All dependencies installed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Error installing dependencies: {e}")
        return False

def check_dependencies():
    """ตรวจสอบ dependencies"""
    try:
        print("🔍 Checking dependencies...")
        
        # ตรวจสอบ aiohttp
        import aiohttp
        print(f"✅ aiohttp {aiohttp.__version__} is installed")
        
        # ตรวจสอบ aiohttp_cors
        import aiohttp_cors
        print(f"✅ aiohttp-cors is installed")
        
        # ตรวจสอบ psutil
        import psutil
        print(f"✅ psutil {psutil.__version__} is installed")
        
        return True
        
    except ImportError as e:
        print(f"❌ Missing dependency: {e}")
        return False

def main():
    """Main function"""
    print("🌐 Web GUI Setup")
    print("=" * 50)
    
    # ตรวจสอบ dependencies
    if check_dependencies():
        print("✅ All dependencies are already installed!")
        print("🚀 You can now run: python main_web_gui.py")
        return True
    
    # ติดตั้ง dependencies
    print("📦 Installing missing dependencies...")
    if install_requirements():
        print("\n🎉 Setup completed successfully!")
        print("🚀 You can now run: python main_web_gui.py")
        print("📱 Open your browser and go to: http://localhost:8080")
        return True
    else:
        print("\n❌ Setup failed!")
        print("💡 Try running manually: pip install aiohttp aiohttp-cors psutil")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
