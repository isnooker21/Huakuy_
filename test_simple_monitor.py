# -*- coding: utf-8 -*-
"""
🎯 Test Simple Trading Monitor
=============================
ทดสอบ Simple Trading Monitor แบบง่าย

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

def test_simple_monitor():
    """ทดสอบ Simple Trading Monitor"""
    try:
        print("🎯 Testing Simple Trading Monitor...")
        
        # Import monitor
        from simple_trading_monitor import SimpleTradingMonitor
        
        # สร้าง Monitor
        monitor = SimpleTradingMonitor()
        
        print("✅ Simple Trading Monitor created successfully")
        print("🎮 Starting GUI...")
        
        # รัน Monitor
        monitor.run()
        
    except ImportError as e:
        print(f"❌ Import Error: {e}")
        print("💡 Please install required dependencies:")
        print("   pip install tkinter")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        logger.error(f"❌ Error in test_simple_monitor: {e}")

def main():
    """ฟังก์ชันหลัก"""
    try:
        print("=" * 60)
        print("🎯 Simple Trading Monitor Test")
        print("=" * 60)
        print(f"📅 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("📊 Testing Simple Monitor GUI...")
        print("=" * 60)
        
        test_simple_monitor()
        
    except Exception as e:
        print(f"❌ Error in main: {e}")

if __name__ == "__main__":
    main()
