# -*- coding: utf-8 -*-
"""
Main Trading System
ระบบเทรดหลักที่ใช้การคำนวณเป็นเปอร์เซ็นต์
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# Import modules
from mt5_connection import MT5Connection
from calculations import Position, PercentageCalculator, LotSizeCalculator
from trading_conditions import TradingConditions, Signal, CandleData
from order_management import OrderManager
from portfolio_manager import PortfolioManager
from gui import TradingGUI

# Configure logging - เฉพาะระบบเทรดและปิดกำไร
logging.basicConfig(
    level=logging.INFO,  # ลดเป็น INFO เพื่อลด noise
    format='%(asctime)s - %(levelname)s - %(message)s',  # ลบ module name
    handlers=[
        logging.FileHandler('trading_system.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# ปิด debug logs จากระบบอื่นๆ
logging.getLogger('mt5_connection').setLevel(logging.WARNING)
logging.getLogger('order_management').setLevel(logging.WARNING)
logging.getLogger('trading_conditions').setLevel(logging.WARNING)
logging.getLogger('portfolio_manager').setLevel(logging.WARNING)
logging.getLogger('calculations').setLevel(logging.WARNING)
logging.getLogger('signal_manager').setLevel(logging.WARNING)
logging.getLogger('smart_gap_filler').setLevel(logging.WARNING)
logging.getLogger('force_trading_mode').setLevel(logging.WARNING)
logging.getLogger('advanced_breakout_recovery').setLevel(logging.WARNING)
logging.getLogger('price_zone_analysis').setLevel(logging.WARNING)
logging.getLogger('zone_rebalancer').setLevel(logging.WARNING)
logging.getLogger('market_analysis').setLevel(logging.WARNING)

# เปิดเฉพาะ Simple Position Manager และ Main Trading
logging.getLogger('simple_position_manager').setLevel(logging.INFO)
logging.getLogger('__main__').setLevel(logging.INFO)

logger = logging.getLogger(__name__)

class TradingSystem:
    """ระบบเทรดหลักที่ใช้การคำนวณเป็นเปอร์เซ็นต์"""
    
    def __init__(self, initial_balance: float = 10000.0, symbol: str = "XAUUSD"):
        """
        เริ่มต้นระบบเทรด
        
        Args:
            initial_balance: เงินทุนเริ่มต้น
            symbol: สัญลักษณ์การเทรด (default: XAUUSD สำหรับทองคำ)
        """
        self.base_symbol = symbol
        self.actual_symbol = None  # สัญลักษณ์จริงที่ใช้ในโบรกเกอร์
        self.initial_balance = initial_balance
        
        # เริ่มต้น components
        self.mt5_connection = MT5Connection()
        self.order_manager = OrderManager(self.mt5_connection)
        self.portfolio_manager = PortfolioManager(self.order_manager, initial_balance)
        self.trading_conditions = TradingConditions()
        
        # สถานะการทำงาน
        self.is_running = False
        self.trading_thread = None
        self.last_candle_time = None
        self.is_trading_started_from_gui = False  # ตัวแปรเช็คว่าเริ่มจาก GUI แล้วหรือยัง
        
        # ข้อมูลตลาด
        self.current_prices = {}
        self.volume_history = []
        self.price_history = []
        
        # GUI
        self.gui = None
        
        # Initialize trading system
        
    def initialize_system(self) -> bool:
        """
        เริ่มต้นระบบทั้งหมด
        
        Returns:
            bool: สำเร็จหรือไม่
        """
        try:
            # Starting system initialization
            
            # เชื่อมต่อ MT5
            if not self.mt5_connection.connect_mt5():
                logger.error("ไม่สามารถเชื่อมต่อ MT5 ได้")
                return False
                
            # ตรวจหาสัญลักษณ์ทองคำโดยอัตโนมัติ
            logger.info("🔍 กำลังตรวจหาสัญลักษณ์ทองคำที่เหมาะสม...")
            self.actual_symbol = self.mt5_connection.auto_detect_gold_symbol()
            
            if not self.actual_symbol:
                logger.error("❌ ไม่พบสัญลักษณ์ทองคำในโบรกเกอร์นี้")
                return False
                    
            # ตรวจสอบข้อมูลสัญลักษณ์
            symbol_info = self.mt5_connection.get_symbol_info(self.actual_symbol)
            if not symbol_info:
                logger.error(f"ไม่พบข้อมูลสัญลักษณ์ {self.actual_symbol}")
                return False
                
            logger.info(f"ใช้สัญลักษณ์: {self.base_symbol} -> {self.actual_symbol}")
            logger.info(f"ข้อมูลสัญลักษณ์: {symbol_info}")
            
            # ส่ง symbol ที่ถูกต้องไปยัง portfolio_manager
            self.portfolio_manager.current_symbol = self.actual_symbol
            
            # ซิงค์ข้อมูล Position
            positions = self.order_manager.sync_positions_from_mt5()
            logger.info(f"พบ Position ที่เปิดอยู่: {len(positions)} ตัว")
            
            # โหลดข้อมูลราคาเริ่มต้น
            self.load_initial_market_data()
            
            logger.info("✅ SYSTEM READY")
            return True
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการเริ่มต้นระบบ: {str(e)}")
            return False
            
    def load_initial_market_data(self):
        """โหลดข้อมูลตลาดเริ่มต้น"""
        try:
            # ดึงข้อมูลราคา 100 แท่งล่าสุด
            import MetaTrader5 as mt5
            rates = self.mt5_connection.get_market_data(
                self.actual_symbol, mt5.TIMEFRAME_M1, 100
            )
            
            if rates:
                self.price_history = [rate['close'] for rate in rates]
                self.volume_history = [rate['tick_volume'] for rate in rates]
                
                # อัพเดทราคาปัจจุบัน
                latest_rate = rates[-1]
                self.current_prices[self.actual_symbol] = latest_rate['close']
                
                # Market data loaded successfully
            else:
                logger.warning("ไม่สามารถโหลดข้อมูลตลาดได้")
                
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการโหลดข้อมูลตลาด: {str(e)}")
            
    def start_trading(self):
        """เริ่มการเทรด"""
        try:
            if self.is_running:
                logger.warning("ระบบเทรดกำลังทำงานอยู่แล้ว")
                return
                
            # ตรวจสอบการเชื่อมต่อแบบเบา
            if not self.mt5_connection.is_connected:
                logger.error("ไม่สามารถเชื่อมต่อ MT5 ได้")
                return
                
            self.is_running = True
            self.is_trading_started_from_gui = True
            
            # เริ่ม trading thread ทันที (ไม่ block GUI)
            self.trading_thread = threading.Thread(target=self.trading_loop, daemon=True)
            self.trading_thread.start()
            
            logger.info("🚀 เริ่มการเทรดแล้ว (จาก GUI)")
            return True  # ส่งกลับทันที
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการเริ่มเทรด: {str(e)}")
            self.is_running = False
            return False
            
    def stop_trading(self):
        """หยุดการเทรด"""
        try:
            self.is_running = False
            self.is_trading_started_from_gui = False
            
            if self.trading_thread and self.trading_thread.is_alive():
                self.trading_thread.join(timeout=5)
                
            logger.info("⏹️ หยุดการเทรดแล้ว (จาก GUI)")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการหยุดเทรด: {str(e)}")
            
    def trading_loop(self):
        """Loop หลักของการเทรด"""
        logger.info("เริ่ม Trading Loop")
        
        # ตัวแปรสำหรับลดความถี่
        loop_count = 0
        last_daily_reset = None
        
        while self.is_running:
            try:
                loop_count += 1
                
                # อัพเดทข้อมูลตลาด (ทุกรอบ)
                self.update_market_data()
                
                # รีเซ็ตเมตริกรายวัน (ทุก 1 ชั่วโมง)
                current_hour = datetime.now().hour
                if last_daily_reset is None or last_daily_reset != current_hour:
                    self.portfolio_manager.reset_daily_metrics()
                    last_daily_reset = current_hour
                
                # ดึงข้อมูลบัญชี (ทุก 10 รอบ)
                if loop_count % 10 == 0:
                    account_info = self.mt5_connection.get_account_info()
                    if not account_info:
                        logger.warning("ไม่สามารถดึงข้อมูลบัญชีได้")
                        time.sleep(10)
                        continue
                        
                    portfolio_state = self.portfolio_manager.analyze_portfolio_state(account_info)
                    
                    # ตรวจสอบเงื่อนไขการปิด Position
                    self.check_exit_conditions(portfolio_state)
                    
                    # ตรวจสอบเงื่อนไขการเข้าเทรดใหม่
                    self.check_entry_conditions(portfolio_state)
                
                # รอ 3 วินาที (เพิ่มจาก 1 วินาที)
                time.sleep(3)
                
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดใน Trading Loop: {str(e)}")
                time.sleep(10)  # รอนานขึ้นเมื่อ error
                
        logger.info("จบ Trading Loop")
        
    def update_market_data(self):
        """อัพเดทข้อมูลตลาด"""
        try:
            import MetaTrader5 as mt5
            
            # ดึงข้อมูลแท่งเทียนล่าสุด
            rates = self.mt5_connection.get_market_data(
                self.actual_symbol, mt5.TIMEFRAME_M1, 1
            )
            
            if rates and len(rates) > 0:
                latest_rate = rates[0]
                current_time = datetime.fromtimestamp(latest_rate['time'])
                
                # ตรวจสอบว่าเป็นแท่งเทียนใหม่หรือไม่
                if self.last_candle_time is None or current_time > self.last_candle_time:
                    self.last_candle_time = current_time
                    
                    # สร้าง CandleData
                    candle = CandleData(
                        open=latest_rate['open'],
                        high=latest_rate['high'],
                        low=latest_rate['low'],
                        close=latest_rate['close'],
                        volume=latest_rate['tick_volume'],
                        timestamp=current_time
                    )
                    
                    # อัพเดทข้อมูลประวัติ
                    self.price_history.append(candle.close)
                    self.volume_history.append(candle.volume)
                    
                    # จำกัดขนาดประวัติ
                    if len(self.price_history) > 100:
                        self.price_history = self.price_history[-100:]
                        self.volume_history = self.volume_history[-100:]
                        
                    # อัพเดทราคาปัจจุบัน
                    self.current_prices[self.actual_symbol] = candle.close
                    
                    # ประมวลผลแท่งเทียนใหม่
                    self.process_new_candle(candle)
                    
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการอัพเดทข้อมูลตลาด: {str(e)}")
            
    # 🗑️ DEPRECATED - Signal generation moved to SignalManager
    def process_new_candle(self, candle: CandleData):
        """ประมวลผลแท่งเทียนใหม่ (เหลือไว้เฉพาะ logging)"""
        try:
            # แสดงเฉพาะราคาปิด
            logger.info(f"📊 PRICE: {candle.close}")
                
            # Signal generation ย้ายไป SignalManager แล้ว
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการประมวลผลแท่งเทียน: {str(e)}")
            
    def calculate_signal_strength(self, candle: CandleData) -> float:
        """คำนวณแรงของสัญญาณ"""
        try:
            # คำนวณแรงจากขนาดตัวเทียน
            body_strength = candle.body_size_percentage * 10  # แปลงเป็น 0-100
            
            # คำนวณแรงจาก Volume
            volume_strength = 0.0
            if len(self.volume_history) > 1:
                avg_volume = sum(self.volume_history[:-1]) / len(self.volume_history[:-1])
                if avg_volume > 0:
                    volume_ratio = candle.volume / avg_volume
                    volume_strength = min(100, volume_ratio * 50)
                    
            # คำนวณแรงจากช่วงราคา
            range_strength = min(100, candle.range_percentage * 20)
            
            # รวมแรงทั้งหมด
            total_strength = (body_strength * 0.4 + volume_strength * 0.4 + range_strength * 0.2)
            
            return min(100, total_strength)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการคำนวณแรงสัญญาณ: {str(e)}")
            return 0.0
            
    def check_entry_conditions(self, portfolio_state):
        """🎯 ตรวจสอบเงื่อนไขการเข้าเทรด (Single Entry Point)"""
        try:
            # สร้าง CandleData จากข้อมูลล่าสุด
            if len(self.price_history) < 4:
                return
                
            candle = CandleData(
                open=self.price_history[-2] if len(self.price_history) > 1 else self.price_history[-1],
                high=max(self.price_history[-4:]),
                low=min(self.price_history[-4:]),
                close=self.price_history[-1],
                volume=self.volume_history[-1] if self.volume_history else 1000,
                timestamp=datetime.now(),
                symbol=self.actual_symbol  # ใช้ symbol ที่ถูกต้อง
            )
            
            current_price = candle.close
            
            # 🎯 Single Entry Point - ดึงสัญญาณที่ดีที่สุดจาก SignalManager
            unified_signal = self.portfolio_manager.get_unified_signal(
                candle=candle,
                current_price=current_price,
                account_balance=portfolio_state.account_balance,
                volume_history=self.volume_history
            )
            
            if not unified_signal:
                logger.debug("⏸️ ไม่พบสัญญาณที่เหมาะสม")
                # อัพเดทเวลาสัญญาณ (แม้จะไม่มีสัญญาณ)
                self.portfolio_manager.update_trade_timing(signal_generated=False)
                return
            
            # ตัดสินใจว่าควรเข้าเทรดหรือไม่
            decision = self.portfolio_manager.should_enter_trade(
                unified_signal.signal, candle, portfolio_state, self.volume_history
            )
            
            if decision['should_enter']:
                # 🎯 TRADE ENTRY (Trust the system - let Lightning Cleanup handle risk)
                logger.info(f"🎯 ENTRY: {unified_signal.signal.direction} {decision['lot_size']:.2f} lots @ {unified_signal.signal.price}")
                
                # ดำเนินการเทรด
                result = self.portfolio_manager.execute_trade_decision(decision)
                
                if result.success:
                    logger.info(f"✅ ORDER SUCCESS: Ticket #{result.ticket}")
                    self.portfolio_manager.update_trade_timing(trade_executed=True)
                else:
                    logger.error(f"❌ ORDER FAILED: {result.error_message}")
                    
            # ล้าง signal หลังจากประมวลผล
            self.last_signal = None
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการตรวจสอบเงื่อนไขการเข้าเทรด: {str(e)}")
            
    def check_exit_conditions(self, portfolio_state):
        """ตรวจสอบเงื่อนไขการปิด Position"""
        try:
            positions = self.portfolio_manager.order_manager.active_positions
            logger.debug(f"🔍 Check Exit Conditions: {len(positions)} positions active")
            
            # 1. ตรวจสอบ Breakout Strategy ก่อน
            breakout_info = None
            should_block_recovery = False
            
            if self.current_prices:
                current_price = self.current_prices.get('close', 0)
                
                # ตรวจสอบ Advanced Breakout Recovery Strategy
                breakout_info = self.portfolio_manager.check_advanced_breakout_recovery(current_price)
                should_block_recovery = breakout_info.get('should_block_recovery', False)
                
                if breakout_info.get('is_breakout_pending'):
                    # Show only successful recovery results
                    for result in breakout_info.get('recovery_results', []):
                        if result['success']:
                            logger.info(f"✅ RECOVERY SUCCESS: ${result['net_profit']:.2f} profit")
                
                # 2. 🗑️ Smart Recovery REMOVED - functionality moved to Smart Profit Taking System
                
                # 2. 🎯 Simple Position Manager - ระบบจัดการไม้แบบเรียบง่าย
                if hasattr(self.portfolio_manager, 'position_manager'):
                    close_decision = self.portfolio_manager.position_manager.should_close_positions(
                        positions, current_price
                    )
                    
                    if close_decision.get('should_close', False):
                        positions_to_close = close_decision.get('positions_to_close', [])
                        if positions_to_close:
                            # 🎯 POSITION CLOSING
                            count = close_decision.get('positions_count', 0)
                            expected_pnl = close_decision.get('expected_pnl', 0.0)
                            reason = close_decision.get('reason', '')
                            logger.info(f"🎯 CLOSING: {count} positions, ${expected_pnl:.2f} expected - {reason}")
                            
                            close_result = self.portfolio_manager.position_manager.close_positions(positions_to_close)
                            if close_result.get('success', False):
                                closed_count = close_result.get('closed_count', 0)
                                total_profit = close_result.get('total_profit', 0.0)
                                logger.info(f"✅ CLOSE SUCCESS: {closed_count} positions closed, ${total_profit:.2f} profit")
                            else:
                                logger.warning(f"❌ CLOSE FAILED: {close_result.get('message', 'Unknown error')}")
                    # No suitable positions to close - no logging to reduce noise
                
                # 3. Zone Analysis & Rebalancing (silent)
                zone_result = self.portfolio_manager.check_and_execute_zone_rebalance(current_price)
            
            # 🗑️ Emergency Exit REMOVED - All exits handled by Smart Profit Taking System
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการตรวจสอบเงื่อนไขการปิด: {str(e)}")
            
    def start_gui(self):
        """เริ่ม GUI"""
        try:
            self.gui = TradingGUI(self)
            self.gui.run()
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดใน GUI: {str(e)}")
            
    def shutdown(self):
        """ปิดระบบ"""
        try:
            logger.info("กำลังปิดระบบเทรด...")
            
            # หยุดการเทรด
            self.stop_trading()
            
            # ปิดการเชื่อมต่อ MT5
            self.mt5_connection.disconnect_mt5()
            
            logger.info("ปิดระบบเทรดแล้ว")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการปิดระบบ: {str(e)}")
            
def main():
    """ฟังก์ชันหลัก"""
    try:
        logger.info("🚀 TRADING SYSTEM STARTING")
        
        # สร้างระบบเทรด
        trading_system = TradingSystem(
            initial_balance=10000.0,  # เงินทุนเริ่มต้น
            symbol="XAUUSD"           # สัญลักษณ์การเทรด (ทองคำ)
        )
        
        # เริ่มต้นระบบ
        if not trading_system.initialize_system():
            logger.error("ไม่สามารถเริ่มต้นระบบได้")
            return
            
        # แสดงข้อมูลสำคัญ
        logger.info(f"💰 Balance: ${trading_system.initial_balance:,.2f}")
        logger.info(f"📊 Symbol: {trading_system.actual_symbol}")
        logger.info("")
        logger.info("⚠️  ระบบพร้อมใช้งาน - กดปุ่ม 'Start Trading' ใน GUI เพื่อเริ่มเทรด")
        logger.info("=" * 60)
        
        # เริ่ม GUI (ไม่เริ่มการเทรดอัตโนมัติ)
        trading_system.start_gui()
        
        # ปิดระบบเมื่อ GUI ปิด
        trading_system.shutdown()
        
    except KeyboardInterrupt:
        logger.info("ได้รับสัญญาณหยุดจากผู้ใช้")
    except Exception as e:
        logger.error(f"เกิดข้อผิดพลาดในฟังก์ชันหลัก: {str(e)}")
    finally:
        logger.info("🏁 จบการทำงาน Trading System")

if __name__ == "__main__":
    main()
