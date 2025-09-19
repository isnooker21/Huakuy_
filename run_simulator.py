# -*- coding: utf-8 -*-
"""
🎯 MT5 Simulator Runner
=======================
รัน MT5 Simulator พร้อมเชื่อมต่อกับระบบหลัก

AUTHOR: Advanced Trading System
VERSION: 1.0.0 - Runner Edition
"""

import logging
import sys
import os
from datetime import datetime

# Add current directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import modules from original system
from mt5_connection import MT5Connection
from order_management import OrderManager
from portfolio_manager import PortfolioManager
from trading_conditions import TradingConditions

# Import simulator
from mt5_simulator_gui import MT5SimulatorGUI
from mt5_simulator_integration import MT5SimulatorIntegration

logger = logging.getLogger(__name__)

def setup_logging():
    """ตั้งค่า Logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('mt5_simulator.log', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

def create_trading_system():
    """สร้างระบบเทรดหลัก"""
    try:
        # สร้าง MT5 Connection
        mt5_connection = MT5Connection()
        
        # สร้าง Order Manager
        order_manager = OrderManager(mt5_connection)
        
        # สร้าง Portfolio Manager
        portfolio_manager = PortfolioManager(order_manager, 10000.0)
        
        # สร้าง Trading Conditions
        trading_conditions = TradingConditions()
        
        logger.info("✅ Trading system created successfully")
        return mt5_connection, order_manager, portfolio_manager, trading_conditions
        
    except Exception as e:
        logger.error(f"❌ Error creating trading system: {e}")
        return None, None, None, None

def create_simulator_with_system():
    """สร้าง Simulator พร้อมระบบเทรด"""
    try:
        # สร้างระบบเทรด
        mt5_connection, order_manager, portfolio_manager, trading_conditions = create_trading_system()
        
        if not order_manager:
            logger.warning("⚠️ Could not create trading system, running in simulation mode")
            return None, None
        
        # สร้าง Simulator GUI
        simulator_gui = MT5SimulatorGUI()
        
        # สร้าง Integration
        integration = MT5SimulatorIntegration(simulator_gui, order_manager)
        
        # เชื่อมต่อ
        simulator_gui.integration = integration
        simulator_gui.order_manager = order_manager
        simulator_gui.mt5_connection = mt5_connection
        
        logger.info("✅ Simulator with trading system created successfully")
        return simulator_gui, integration
        
    except Exception as e:
        logger.error(f"❌ Error creating simulator with system: {e}")
        return None, None

def run_simulator():
    """รัน Simulator"""
    try:
        logger.info("🎯 Starting MT5 Simulator...")
        
        # สร้าง Simulator
        simulator_gui, integration = create_simulator_with_system()
        
        if not simulator_gui:
            logger.error("❌ Failed to create simulator")
            return
        
        # เริ่ม Integration
        if integration:
            integration.start_integration()
            logger.info("✅ Integration started")
        
        # รัน Simulator
        logger.info("✅ Simulator GUI started")
        simulator_gui.run()
        
        # หยุด Integration
        if integration:
            integration.stop_integration()
            logger.info("✅ Integration stopped")
        
        logger.info("🎯 MT5 Simulator stopped")
        
    except KeyboardInterrupt:
        logger.info("🎯 Simulator stopped by user")
    except Exception as e:
        logger.error(f"❌ Error running simulator: {e}")

def main():
    """ฟังก์ชันหลัก"""
    try:
        # ตั้งค่า Logging
        setup_logging()
        
        # แสดงข้อมูลเริ่มต้น
        print("=" * 60)
        print("🎯 MT5 Trading Simulator")
        print("=" * 60)
        print(f"📅 Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("📊 Features:")
        print("   • Real-time Price Chart")
        print("   • Live Position Tracking")
        print("   • Visual Trade Markers")
        print("   • Trading Statistics")
        print("   • Manual Trading Controls")
        print("=" * 60)
        
        # รัน Simulator
        run_simulator()
        
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
