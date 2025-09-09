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

# 🎯 Zone-Based Position Management System
from zone_position_manager import ZonePositionManager, create_zone_position_manager

# 🧠 Intelligent Position Management System
from intelligent_position_manager import IntelligentPositionManager, create_intelligent_position_manager
from dynamic_7d_smart_closer import create_dynamic_7d_smart_closer

# 🎯 Position Purpose Tracking System
from position_purpose_tracker import create_position_purpose_tracker

# 📊 Market Analysis Systems
from market_analysis import MultiTimeframeAnalyzer, MarketSessionAnalyzer
from price_action_analyzer import PriceActionAnalyzer

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
logging.getLogger('trading_conditions').setLevel(logging.INFO)
logging.getLogger('portfolio_manager').setLevel(logging.WARNING)
logging.getLogger('calculations').setLevel(logging.WARNING)
logging.getLogger('signal_manager').setLevel(logging.INFO)
logging.getLogger('smart_gap_filler').setLevel(logging.WARNING)
logging.getLogger('force_trading_mode').setLevel(logging.WARNING)
logging.getLogger('advanced_breakout_recovery').setLevel(logging.WARNING)
logging.getLogger('price_zone_analysis').setLevel(logging.WARNING)
logging.getLogger('zone_rebalancer').setLevel(logging.WARNING)
logging.getLogger('market_analysis').setLevel(logging.WARNING)

# 🚀 PERFORMANCE-OPTIMIZED LOGGING
logging.getLogger('zone_position_manager').setLevel(logging.INFO)  # เปิด Zone Analysis logs
logging.getLogger('zone_manager').setLevel(logging.INFO)  # เปิด Zone Health calculation logs
logging.getLogger('zone_analyzer').setLevel(logging.WARNING)  # ปิด INFO logs
logging.getLogger('zone_coordinator').setLevel(logging.WARNING)  # ปิด INFO logs
logging.getLogger('intelligent_position_manager').setLevel(logging.WARNING)  # ปิด DEBUG logs ที่เยอะมาก
logging.getLogger('position_purpose_tracker').setLevel(logging.INFO)  # เปิด Purpose Analysis logs
logging.getLogger('dynamic_7d_smart_closer').setLevel(logging.INFO)  # เปิด Purpose-Aware Closing logs
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
        
        # 🎯 Zone-Based Position Management System (จะถูก initialize หลังจาก MT5 connect)
        self.zone_position_manager = None
        
        # 🧠 Intelligent Systems (จะถูก initialize หลังจาก MT5 connect)
        self.intelligent_position_manager = None
        self.dynamic_7d_smart_closer = None
        
        # 🎯 Purpose Tracking System
        self.position_purpose_tracker = None
        
        # 📊 Market Analysis Systems
        self.market_analyzer = None
        self.price_action_analyzer = None
        
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
        
        # 🔒 Position Locking - ป้องกันการปิดซ้ำ
        self.closing_positions = set()  # เก็บ tickets ที่กำลังปิดอยู่
        self.closing_lock = threading.Lock()
        
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
            
            # 📊 Initialize Market Analysis Systems
            logger.info("📊 Initializing Market Analysis Systems...")
            self.market_analyzer = MultiTimeframeAnalyzer(symbol=self.actual_symbol)
            self.price_action_analyzer = PriceActionAnalyzer(
                mt5_connection=self.mt5_connection,
                symbol=self.actual_symbol
            )
            
            # 🎯 Initialize Position Purpose Tracking System
            logger.info("🎯 Initializing Position Purpose Tracking System...")
            self.position_purpose_tracker = create_position_purpose_tracker(
                market_analyzer=self.market_analyzer,
                price_action_analyzer=self.price_action_analyzer
            )
            
            # 🧠 Initialize Intelligent Position Management System
            logger.info("🧠 Initializing Intelligent Position Management System...")
            self.intelligent_position_manager = create_intelligent_position_manager(
                mt5_connection=self.mt5_connection,
                order_manager=self.order_manager,
                symbol=self.actual_symbol
            )
            
            # 🚀 Initialize Dynamic 7D Smart Closer with Purpose Intelligence
            logger.info("🚀 Initializing Dynamic 7D Smart Closer...")
            self.dynamic_7d_smart_closer = create_dynamic_7d_smart_closer(
                intelligent_manager=self.intelligent_position_manager,
                purpose_tracker=self.position_purpose_tracker,
                market_analyzer=self.market_analyzer,
                price_action_analyzer=self.price_action_analyzer
            )
            
            # 🎯 Initialize Zone-Based Position Management System
            logger.info("🎯 Initializing Zone-Based Position Management System...")
            self.zone_position_manager = create_zone_position_manager(
                mt5_connection=self.mt5_connection,
                order_manager=self.order_manager,
                zone_size_pips=30.0,  # 30 pips per zone
                symbol=self.actual_symbol  # ใช้ symbol ที่ auto-detect ได้
            )
            
            # 🔗 เชื่อมต่อ Purpose-Aware Systems กับ Trading Conditions
            logger.info("🔗 Connecting Purpose-Aware Intelligence to Trading Conditions...")
            self.trading_conditions.intelligent_position_manager = self.intelligent_position_manager
            self.trading_conditions.position_purpose_tracker = self.position_purpose_tracker
            
            # เชื่อมต่อกับ Portfolio Manager
            if hasattr(self.portfolio_manager, 'position_manager'):
                self.portfolio_manager.position_manager = self.zone_position_manager
                logger.info("✅ Zone-Based System integrated with Portfolio Manager")
            else:
                logger.warning("⚠️ Portfolio Manager doesn't support Zone integration - using direct integration")
            
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
                
                # 🚀 HIGH-PERFORMANCE TRADING LOOP - Optimized Intervals
                account_info = self.mt5_connection.get_account_info()
                if not account_info:
                    logger.warning("ไม่สามารถดึงข้อมูลบัญชีได้")
                    time.sleep(5)  # ลดจาก 10 เป็น 5 วินาที
                    continue
                    
                portfolio_state = self.portfolio_manager.analyze_portfolio_state(account_info)
                
                # ✅ ตรวจสอบเงื่อนไขการปิด Position (ทุกรอบ - 1 วินาที)
                self.check_exit_conditions(portfolio_state)
                
                # 🎯 ตรวจสอบเงื่อนไขการเข้าเทรดใหม่ (ทุก 3 รอบ - 3 วินาที)
                if loop_count % 3 == 0:
                    self.check_entry_conditions(portfolio_state)
                
                # ⚡ รอ 1 วินาที (เร็วขึ้นแต่เสถียร)
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดใน Trading Loop: {str(e)}")
                
                # 🛡️ SMART ERROR RECOVERY
                if "connection" in str(e).lower() or "timeout" in str(e).lower():
                    logger.warning("🔄 ตรวจพบปัญหาการเชื่อมต่อ - กำลังพยายามเชื่อมต่อใหม่...")
                    if self.mt5_connection.attempt_reconnection():
                        logger.info("✅ เชื่อมต่อใหม่สำเร็จ")
                        time.sleep(2)  # รอสั้นๆ หลังเชื่อมต่อใหม่
                    else:
                        logger.error("❌ เชื่อมต่อใหม่ไม่สำเร็จ - รอ 30 วินาที")
                        time.sleep(30)
                else:
                    time.sleep(10)  # รอปกติเมื่อ error อื่นๆ
                
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
            else:
                # 🚫 แสดงสาเหตุที่ไม่เข้าไม้ (สั้นๆ)
                reasons = decision.get('reasons', ['Unknown reason'])
                if reasons and len(reasons) > 0:
                    # เอาแค่เหตุผลแรก และทำให้สั้น
                    main_reason = reasons[0] if isinstance(reasons, list) else str(reasons)
                    # ทำให้เหตุผลสั้นลง
                    short_reason = self._simplify_reason(main_reason)
                    logger.info(f"⏸️ NO ENTRY: {short_reason}")
                else:
                    logger.info(f"⏸️ NO ENTRY: No specific reason provided")
                    
            # ล้าง signal หลังจากประมวลผล
            self.last_signal = None
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการตรวจสอบเงื่อนไขการเข้าเทรด: {str(e)}")
    
    def _simplify_reason(self, reason: str) -> str:
        """ทำให้เหตุผลสั้นลงเพื่อ log ที่อ่านง่าย"""
        # แปลงข้อความยาวๆ ให้สั้น
        simplifications = {
            "มี Order ในแท่งเทียนนี้แล้ว": "Already ordered this candle",
            "แรงตลาดไม่เพียงพอ": "Market strength insufficient", 
            "Volume ต่ำกว่าเกณฑ์": "Volume too low",
            "Entry price invalid": "Price invalid",
            "Too many bad positions": "Too many losing positions",
            "Buy positions เกิน 80%": "Too many BUY positions",
            "Sell positions เกิน 80%": "Too many SELL positions",
            "การใช้เงินทุนเกิน": "Capital exposure exceeded"
        }
        
        # หาคำที่ตรงกัน
        for long_phrase, short_phrase in simplifications.items():
            if long_phrase in reason:
                return short_phrase
        
        # ถ้าไม่เจอ ตัดให้สั้น
        if len(reason) > 50:
            return reason[:47] + "..."
        
        return reason
    
    # 🗑️ REMOVED: _aggressive_balance_recovery - replaced by Dynamic 7D Smart Closer
    def _aggressive_balance_recovery_REMOVED(self, positions, current_price):
        """🚀 เร่งหาคู่ปิดเมื่อ positions เยอะ - ไม่สนวิธีการแต่ต้องปิดบวกเสมอ"""
        try:
            logger.info(f"🚀 Aggressive Balance Recovery: {len(positions)} positions")
            
            # แยก BUY และ SELL
            buy_positions = [pos for pos in positions if pos.type == 0]  # BUY
            sell_positions = [pos for pos in positions if pos.type == 1]  # SELL
            
            # แยกเป็น กำไร และ ขาดทุน
            profitable_buys = [pos for pos in buy_positions if pos.profit > 0]
            losing_buys = [pos for pos in buy_positions if pos.profit <= 0]
            profitable_sells = [pos for pos in sell_positions if pos.profit > 0]
            losing_sells = [pos for pos in sell_positions if pos.profit <= 0]
            
            # เรียงตาม P&L
            profitable_buys.sort(key=lambda x: x.profit, reverse=True)  # กำไรมากก่อน
            losing_buys.sort(key=lambda x: x.profit)  # ขาดทุนน้อยก่อน (แย่ที่สุดท้าย)
            profitable_sells.sort(key=lambda x: x.profit, reverse=True)  # กำไรมากก่อน
            losing_sells.sort(key=lambda x: x.profit)  # ขาดทุนน้อยก่อน (แย่ที่สุดท้าย)
            
            # หาคู่ที่ดีที่สุด (BUY + SELL = กำไรรวม)
            best_combinations = []
            
            # 🎯 SMART PAIRING: จับคู่ positions ดี กับ positions แย่
            logger.info(f"🎯 Smart Pairing: Profitable BUY={len(profitable_buys)}, Losing BUY={len(losing_buys)}")
            logger.info(f"🎯 Smart Pairing: Profitable SELL={len(profitable_sells)}, Losing SELL={len(losing_sells)}")
            
            # ลอง combination ขนาดต่างๆ (2-12 positions) - เพิ่มขึ้นเพื่อปิดได้มากขึ้น
            for combo_size in range(2, min(13, len(positions) + 1)):
                # ลอง ratio ต่างๆ ระหว่าง profitable และ losing
                for profitable_ratio in [0.3, 0.4, 0.5, 0.6, 0.7]:  # 30%-70% เป็น profitable
                    profitable_count = max(1, int(combo_size * profitable_ratio))
                    losing_count = combo_size - profitable_count
                    
                    if losing_count < 1:  # ต้องมี losing positions ด้วย
                        continue
                    
                    # แบ่ง profitable และ losing ระหว่าง BUY/SELL
                    for buy_profitable in range(max(0, profitable_count - len(profitable_sells)), 
                                              min(profitable_count + 1, len(profitable_buys) + 1)):
                        sell_profitable = profitable_count - buy_profitable
                        
                        for buy_losing in range(max(0, losing_count - len(losing_sells)), 
                                              min(losing_count + 1, len(losing_buys) + 1)):
                            sell_losing = losing_count - buy_losing
                            
                            # เช็คว่ามี positions เพียงพอไหม
                            if (buy_profitable > len(profitable_buys) or 
                                sell_profitable > len(profitable_sells) or
                                buy_losing > len(losing_buys) or 
                                sell_losing > len(losing_sells)):
                                continue
                            
                            # เลือก positions
                            selected_positions = []
                            selected_positions.extend(profitable_buys[:buy_profitable])
                            selected_positions.extend(profitable_sells[:sell_profitable])
                            selected_positions.extend(losing_buys[-buy_losing:] if buy_losing > 0 else [])  # แย่ที่สุด
                            selected_positions.extend(losing_sells[-sell_losing:] if sell_losing > 0 else [])  # แย่ที่สุด
                            
                            if len(selected_positions) != combo_size:
                                continue
                            
                            # คำนวณ P&L รวม
                            total_pnl = sum([pos.profit for pos in selected_positions])
                            
                            # ต้องเป็นบวกเสมอ (ไม่ปิดติดลบ)
                            if total_pnl > 3.0:  # กำไรขั้นต่ำ $3
                                buy_total = buy_profitable + buy_losing
                                sell_total = sell_profitable + sell_losing
                                balance_score = abs(buy_total - sell_total) * -5  # ยิ่งสมดุลยิ่งดี
                                
                                # 🎯 HEAVY LOSS BONUS - เหมือนระบบอื่น
                                heavy_loss_bonus = 0
                                # นับ losing positions ที่ขาดทุนหนัก
                                losing_positions_selected = []
                                if buy_losing > 0:
                                    losing_positions_selected.extend(losing_buys[-buy_losing:])
                                if sell_losing > 0:
                                    losing_positions_selected.extend(losing_sells[-sell_losing:])
                                
                                logger.debug(f"🔍 Losing positions selected: {len(losing_positions_selected)} (BUY:{buy_losing}, SELL:{sell_losing})")
                                
                                for pos in losing_positions_selected:
                                    if pos.profit < -10:  # ขาดทุน > $10
                                        heavy_loss_bonus += abs(pos.profit) * 2  # Bonus = 2x ขาดทุน
                                        logger.debug(f"💥 Heavy Loss >$10: {pos.profit:.2f} → Bonus +{abs(pos.profit)*2:.1f}")
                                    elif pos.profit < -5:  # ขาดทุน > $5
                                        heavy_loss_bonus += abs(pos.profit) * 1  # Bonus = 1x ขาดทุน
                                        logger.debug(f"💥 Heavy Loss >$5: {pos.profit:.2f} → Bonus +{abs(pos.profit):.1f}")
                                    elif pos.profit < 0:
                                        logger.debug(f"📊 Small Loss: {pos.profit:.2f} → No bonus")
                                
                                losing_bonus = (buy_losing + sell_losing) * 1 + heavy_loss_bonus  # รวม bonus
                                total_score = total_pnl + balance_score + losing_bonus
                                
                                best_combinations.append({
                                    'positions': selected_positions,
                                    'total_pnl': total_pnl,
                                    'balance_score': balance_score,
                                    'losing_bonus': losing_bonus,
                                    'heavy_loss_bonus': heavy_loss_bonus,
                                    'total_score': total_score,
                                    'profitable_count': profitable_count,
                                    'losing_count': losing_count,
                                    'buy_count': buy_total,
                                    'sell_count': sell_total
                                })
            
            if best_combinations:
                # เลือกชุดที่ดีที่สุด
                best_combinations.sort(key=lambda x: x['total_score'], reverse=True)
                best = best_combinations[0]
                
                # 🔍 DEBUG: แสดงรายละเอียด losing positions
                losing_details = []
                losing_positions_in_best = []
                
                # หา losing positions ใน best combination
                for pos in best['positions']:
                    if pos.profit < 0:
                        losing_positions_in_best.append(pos)
                        if pos.profit < -10:
                            losing_details.append(f"{pos.profit:.2f}(>$10)")
                        elif pos.profit < -5:
                            losing_details.append(f"{pos.profit:.2f}(>$5)")
                        else:
                            losing_details.append(f"{pos.profit:.2f}(<$5)")
                
                logger.info(f"🎯 Found SMART aggressive combination: {best['profitable_count']}P+{best['losing_count']}L "
                           f"({best['buy_count']}B+{best['sell_count']}S) = ${best['total_pnl']:.2f}")
                logger.info(f"💥 Heavy Loss Bonus: +{best['heavy_loss_bonus']:.1f}, Total Bonus: +{best['losing_bonus']:.1f}")
                logger.info(f"📊 Losing Details: {', '.join(losing_details) if losing_details else 'No losing positions'}")
                
                return {
                    'should_close': True,
                    'positions_to_close': best['positions'],
                    'expected_pnl': best['total_pnl'],
                    'reason': f"Smart Aggressive: {best['profitable_count']}P+{best['losing_count']}L pairs"
                }
            else:
                logger.info(f"❌ No profitable aggressive combinations found")
                return {'should_close': False}
                
        except Exception as e:
            logger.error(f"❌ Error in aggressive balance recovery: {e}")
            return {'should_close': False}
    
    def _unified_closing_decision(self, positions: List[Any], current_price: float, 
                                 position_scores: List[Any], margin_health: Any, account_info: Dict) -> Dict[str, Any]:
        """
        🤝 Unified Closing Decision System - Enhanced with Dynamic 7D Smart Closer
        ระบบปิดไม้อัจฉริยะที่ใช้ Dynamic 7D Analysis
        """
        try:
            logger.info(f"🤝 UNIFIED ANALYSIS: {len(positions)} positions, Margin: {margin_health.risk_level if margin_health else 'UNKNOWN'}")
            
            # 🚀 Priority 1: Purpose-Aware Dynamic 7D Smart Closer (Primary System)
            if hasattr(self, 'dynamic_7d_smart_closer') and self.dynamic_7d_smart_closer:
                logger.info(f"🧠 PURPOSE-AWARE 7D MODE: Using intelligent purpose-based closing system")
                dynamic_result = self.dynamic_7d_smart_closer.find_optimal_closing(positions, account_info)
                
                if dynamic_result and dynamic_result.should_close:
                    # Convert to unified format
                    return {
                        'should_close': True,
                        'positions_to_close': dynamic_result.positions_to_close,
                        'method': f'purpose_aware_{dynamic_result.method}',
                        'expected_pnl': dynamic_result.expected_pnl,
                        'positions_count': dynamic_result.position_count,
                        'reason': dynamic_result.reason,
                        'confidence_score': dynamic_result.confidence_score,
                        'portfolio_improvement': dynamic_result.portfolio_improvement
                    }
            
            # 🧠 Priority 2: Intelligent Manager (Fallback)
            if hasattr(self, 'intelligent_position_manager') and self.intelligent_position_manager and position_scores:
                logger.info(f"🧠 INTELLIGENT FALLBACK: Using 7D intelligent manager")
                intelligent_decision = self.intelligent_position_manager.analyze_closing_decision(positions, account_info)
                if intelligent_decision.get('should_close', False):
                    intelligent_decision['method'] = 'intelligent_7d_fallback'
                    logger.info(f"✅ INTELLIGENT DECISION: {intelligent_decision.get('positions_count', 0)} positions selected")
                    return intelligent_decision
            
            # 🎯 Priority 3: Zone-Based (Last Resort)
            if self.zone_position_manager:
                logger.info(f"🎯 ZONE FALLBACK: Using zone-based analysis")
                close_decision = self.zone_position_manager.should_close_positions(positions, current_price)
                
                if close_decision.get('should_close', False):
                    close_decision['method'] = 'zone_fallback'
                    logger.info(f"✅ ZONE DECISION: {len(close_decision.get('positions_to_close', []))} positions selected")
                    return close_decision
            
            # 📊 No closing decision made
            logger.info(f"⏸️ NO CLOSING: No system found suitable positions to close")
            return {'should_close': False, 'reason': 'No suitable closing opportunities found', 'method': 'none'}
            
        except Exception as e:
            logger.error(f"❌ Error in unified closing decision: {e}")
            return {'should_close': False, 'reason': f'Unified system error: {str(e)}', 'method': 'error'}
    
    def _filter_locked_positions(self, positions: List[Any]) -> List[Any]:
        """🔒 กรองไม้ที่ไม่ได้ถูก lock ออกมา"""
        with self.closing_lock:
            filtered = []
            for pos in positions:
                ticket = getattr(pos, 'ticket', None)
                if ticket and ticket not in self.closing_positions:
                    filtered.append(pos)
                else:
                    logger.info(f"🔒 Position {ticket} is already being closed - skipping")
            return filtered
    
    def _lock_positions(self, positions: List[Any]):
        """🔒 ล็อคไม้ก่อนปิด"""
        with self.closing_lock:
            for pos in positions:
                ticket = getattr(pos, 'ticket', None)
                if ticket:
                    self.closing_positions.add(ticket)
                    logger.info(f"🔒 Locked position {ticket}")
    
    def _unlock_positions(self, positions: List[Any]):
        """🔓 ปลดล็อคไม้หลังปิดเสร็จ"""
        with self.closing_lock:
            for pos in positions:
                ticket = getattr(pos, 'ticket', None)
                if ticket and ticket in self.closing_positions:
                    self.closing_positions.remove(ticket)
                    logger.info(f"🔓 Unlocked position {ticket}")
            
    def check_exit_conditions(self, portfolio_state):
        """ตรวจสอบเงื่อนไขการปิด Position"""
        try:
            # 🎯 CRITICAL FIX: Sync positions from MT5 FIRST
            logger.debug(f"🔄 Syncing positions from MT5 before closing analysis...")
            synced_positions = self.portfolio_manager.order_manager.sync_positions_from_mt5()
            positions = self.portfolio_manager.order_manager.active_positions
            logger.info(f"🔄 SYNC COMPLETE: {len(positions)} positions active (synced: {len(synced_positions)})")
            
            # 1. ตรวจสอบ Breakout Strategy ก่อน
            breakout_info = None
            should_block_recovery = False
            
            if self.current_prices:
                current_price = self.current_prices.get('close', 0)
                
                # Advanced Breakout Recovery DISABLED - ใช้ Simple Position Manager แทน
                # breakout_info = self.portfolio_manager.check_advanced_breakout_recovery(current_price)
                # should_block_recovery = breakout_info.get('should_block_recovery', False)
                breakout_info = {'should_block_recovery': False, 'reason': 'Advanced Breakout Recovery disabled'}
                should_block_recovery = False
                
                if breakout_info.get('is_breakout_pending'):
                    # Show only successful recovery results
                    for result in breakout_info.get('recovery_results', []):
                        if result['success']:
                            logger.info(f"✅ RECOVERY SUCCESS: ${result['net_profit']:.2f} profit")
                
                # 2. 🗑️ Smart Recovery REMOVED - functionality moved to Smart Profit Taking System
                
                # 🤝 UNIFIED CLOSING SYSTEM - ระบบปิดไม้แบบประสานงาน
                logger.info(f"🤝 UNIFIED CLOSING: Analyzing {len(positions)} positions...")
                
                # 1. 🧠 Get 7D Analysis (คำนวณครั้งเดียว)
                account_info = self.mt5_connection.get_account_info()
                margin_health = None
                position_scores = None
                
                if hasattr(self, 'intelligent_position_manager') and self.intelligent_position_manager:
                    margin_health = self.intelligent_position_manager._analyze_margin_health(account_info)
                    position_scores = self.intelligent_position_manager._score_all_positions(positions, account_info, margin_health)
                    logger.info(f"🧠 7D Analysis Complete: {len(position_scores)} positions scored")
                    logger.info(f"💊 Margin Health: {margin_health.risk_level} - {margin_health.recommendation}")
                
                # 2. 🎯 Unified Decision Making
                closing_result = self._unified_closing_decision(positions, current_price, position_scores, margin_health, account_info)
                
                if closing_result.get('should_close', False):
                    positions_to_close = closing_result.get('positions_to_close', [])
                    if positions_to_close:
                        # 🔒 Check for position locking conflicts
                        filtered_positions = self._filter_locked_positions(positions_to_close)
                        
                        if not filtered_positions:
                            logger.info("🔒 All selected positions are already being closed - skipping")
                            return
                        
                        # 📊 Log unified decision
                        method = closing_result.get('method', 'unified')
                        count = len(filtered_positions)
                        expected_pnl = closing_result.get('expected_pnl', 0.0)
                        reason = closing_result.get('reason', '')
                        
                        logger.info(f"🤝 UNIFIED DECISION ({method.upper()}): {count} positions")
                        logger.info(f"💰 Expected P&L: ${expected_pnl:.2f} - {reason}")
                        
                        # 🔒 Lock positions before closing
                        self._lock_positions(filtered_positions)
                        
                        try:
                            # 3. 🎯 Execute closing
                            close_result = self.zone_position_manager.close_positions(filtered_positions)
                            if close_result.get('success', False):
                                closed_count = close_result.get('closed_count', 0)
                                total_profit = close_result.get('total_profit', 0.0)
                                logger.info(f"✅ UNIFIED SUCCESS: {closed_count} positions closed, ${total_profit:.2f} profit")
                            else:
                                logger.warning(f"❌ UNIFIED FAILED: {close_result.get('message', 'Unknown error')}")
                        finally:
                            # 🔓 Always unlock positions after attempt
                            self._unlock_positions(filtered_positions)
                        return
                
                # 🧠 OLD SYSTEMS REMOVED - ใช้ Unified System แทน
                
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
