# -*- coding: utf-8 -*-
"""
🎯 Test MT5 Simulator
====================
ทดสอบ MT5 Simulator แบบง่าย

AUTHOR: Advanced Trading System
VERSION: 1.0.0 - Test Edition
"""

import logging
import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_simulator():
    """ทดสอบ Simulator"""
    try:
        print("🎯 Testing MT5 Simulator...")
        
        # Import simulator
        from mt5_simulator_gui import MT5SimulatorGUI
        
        # สร้าง Simulator
        simulator = MT5SimulatorGUI()
        
        print("✅ Simulator created successfully")
        print("🎮 Starting GUI...")
        
        # รัน Simulator
        simulator.run()
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Please install required dependencies:")
        print("   pip install matplotlib numpy pandas")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"❌ Error in test_simulator: {e}")

def main():
    """ฟังก์ชันหลัก"""
    try:
        print("=" * 60)
        print("🎯 MT5 Simulator Test")
        print("=" * 60)
        print(f"📅 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("📊 Testing Simulator GUI...")
        print("=" * 60)
        
        test_simulator()
        
    except Exception as e:
        print(f"❌ Error in main: {e}")

if __name__ == "__main__":
    main()
