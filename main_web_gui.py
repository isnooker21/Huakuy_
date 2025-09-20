# -*- coding: utf-8 -*-
"""
Main Web GUI Application
แอปพลิเคชันหลักสำหรับ Web-based GUI
"""

import logging
import sys
from main_simple_gui import AdaptiveTradingSystemGUI

# 🚀 Simple & Clean Logging Configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('web_gui.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 🚀 Reduce logging noise
logging.getLogger('mt5_connection').setLevel(logging.WARNING)
logging.getLogger('order_management').setLevel(logging.WARNING)
logging.getLogger('dynamic_position_modifier').setLevel(logging.WARNING)
logging.getLogger('calculations').setLevel(logging.ERROR)
logging.getLogger('zone_analyzer').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

def main():
    """Main function for Web GUI"""
    logger.info("🚀 Starting Enhanced 7D Smart Trading System - Web GUI")
    
    # Create trading system
    system = AdaptiveTradingSystemGUI(initial_balance=10000.0, symbol="XAUUSD")
    
    try:
        # Initialize system
        logger.info("🔧 Initializing trading system...")
        if system.initialize_system():
            logger.info("✅ System initialized successfully")
            
            # Start Web GUI
            logger.info("🌐 Starting Web GUI...")
            logger.info("📱 Open your browser and go to: http://localhost:8080")
            logger.info("📱 Or use your IP address: http://[your-ip]:8080")
            logger.info("🛑 Press Ctrl+C to stop the system")
            
            system.start_gui(use_web_gui=True)  # ใช้ Web GUI
            
        else:
            logger.error("❌ Failed to initialize system")
            return 1
            
    except KeyboardInterrupt:
        logger.info("🛑 Stopping system...")
        system.shutdown()
        return 0
    except Exception as e:
        logger.error(f"❌ System error: {e}")
        system.shutdown()
        return 1

if __name__ == "__main__":
    sys.exit(main())
