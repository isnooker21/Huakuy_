# -*- coding: utf-8 -*-
"""
Test Market Status Detection
ทดสอบฟังก์ชันตรวจจับตลาดปิดเปิด
"""

import logging
from datetime import datetime
from mt5_connection import MT5Connection

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_market_status():
    """ทดสอบฟังก์ชันตรวจจับตลาดปิดเปิด"""
    try:
        # สร้าง MT5Connection
        mt5_conn = MT5Connection()
        
        # เชื่อมต่อ MT5
        if not mt5_conn.connect_mt5():
            logger.error("❌ ไม่สามารถเชื่อมต่อ MT5 ได้")
            return
        
        logger.info("✅ เชื่อมต่อ MT5 สำเร็จ")
        
        # ทดสอบฟังก์ชันต่างๆ
        symbol = "XAUUSD"
        
        # 1. ทดสอบ get_market_status()
        logger.info(f"\n🔍 ทดสอบ get_market_status() สำหรับ {symbol}")
        market_status = mt5_conn.get_market_status(symbol)
        
        logger.info(f"📊 Market Status:")
        logger.info(f"   Status: {'🟢 OPEN' if market_status['is_market_open'] else '🔴 CLOSED'}")
        logger.info(f"   Reason: {market_status['reason']}")
        logger.info(f"   Current Time: {market_status['current_time']} (UTC: {market_status['current_utc']})")
        
        if market_status['active_sessions']:
            logger.info(f"   Active Sessions: {len(market_status['active_sessions'])}")
            for session in market_status['active_sessions']:
                logger.info(f"     • {session['name'].upper()}: {session['open']}-{session['close']} ({session['timezone']})")
        else:
            logger.info(f"   Active Sessions: None")
        
        if market_status['next_session']:
            next_session = market_status['next_session']
            logger.info(f"   Next Session: {next_session['name'].upper()} at {next_session['open']} ({next_session['timezone']})")
            logger.info(f"   Time to Next: {next_session['time_to_open']:.1f} hours")
        
        if market_status.get('london_ny_overlap'):
            logger.info(f"   🚀 London-NY Overlap: ACTIVE (High Volume Period)")
        
        # 2. ทดสอบ is_market_open()
        logger.info(f"\n🔍 ทดสอบ is_market_open() สำหรับ {symbol}")
        is_open = mt5_conn.is_market_open(symbol)
        logger.info(f"   Market Open: {'🟢 YES' if is_open else '🔴 NO'}")
        
        # 3. ทดสอบ get_next_market_open()
        logger.info(f"\n🔍 ทดสอบ get_next_market_open() สำหรับ {symbol}")
        next_open = mt5_conn.get_next_market_open(symbol)
        logger.info(f"   Next Session: {next_open['session_name'].upper()}")
        logger.info(f"   Open Time: {next_open['open_time']} ({next_open['timezone']})")
        if next_open['hours_until_open']:
            logger.info(f"   Hours Until Open: {next_open['hours_until_open']:.1f}")
            logger.info(f"   Minutes Until Open: {next_open['minutes_until_open']:.0f}")
        
        # 4. ทดสอบ log_market_status()
        logger.info(f"\n🔍 ทดสอบ log_market_status() สำหรับ {symbol}")
        mt5_conn.log_market_status(symbol)
        
        # 5. ทดสอบกับสัญลักษณ์อื่น
        other_symbols = ["EURUSD", "GBPUSD", "USDJPY"]
        for other_symbol in other_symbols:
            logger.info(f"\n🔍 ทดสอบ {other_symbol}")
            try:
                is_open = mt5_conn.is_market_open(other_symbol)
                logger.info(f"   Market Open: {'🟢 YES' if is_open else '🔴 NO'}")
            except Exception as e:
                logger.warning(f"   ⚠️ Error testing {other_symbol}: {e}")
        
        logger.info("\n✅ ทดสอบเสร็จสิ้น")
        
    except Exception as e:
        logger.error(f"❌ เกิดข้อผิดพลาดในการทดสอบ: {e}")

if __name__ == "__main__":
    test_market_status()
