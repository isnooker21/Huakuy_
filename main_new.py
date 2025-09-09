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

# 🚫 OLD ZONE-BASED SYSTEM REMOVED - Using Dynamic 7D Smart Closer only
# from zone_position_manager import ZonePositionManager, create_zone_position_manager

# 🧠 Intelligent Position Management System
from intelligent_position_manager import IntelligentPositionManager, create_intelligent_position_manager
from dynamic_7d_smart_closer import create_dynamic_7d_smart_closer

# 🎯 Position Purpose Tracking System
from position_purpose_tracker import create_position_purpose_tracker

# 🎯 Smart Entry Timing System
from smart_entry_timing import create_smart_entry_timing
from strategic_position_manager import create_strategic_position_manager

# 🚀 Enhanced 7D Entry + Position Modifier System
from enhanced_7d_entry_system import create_enhanced_7d_entry_system

# 🚀 Dynamic Adaptive Systems - Full Dynamic Trading Ecosystem
from dynamic_adaptive_entry_system import create_dynamic_adaptive_entry_system
from dynamic_position_modifier import create_dynamic_position_modifier
from dynamic_adaptive_closer import create_dynamic_adaptive_closer

# 📊 Market Analysis Systems
from market_analysis import MultiTimeframeAnalyzer, MarketSessionAnalyzer
from price_action_analyzer import PriceActionAnalyzer

# 🎯 SIMPLE & CLEAN LOGGING CONFIGURATION
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',  # ลบ levelname เพื่อความสะอาด
    handlers=[
        logging.FileHandler('trading_system.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 🎯 CLEAN LOGGING - แสดงแค่สิ่งสำคัญ
logging.getLogger('mt5_connection').setLevel(logging.ERROR)
logging.getLogger('order_management').setLevel(logging.WARNING)
logging.getLogger('trading_conditions').setLevel(logging.INFO)  # เปิดดู Smart Entry
logging.getLogger('smart_entry_timing').setLevel(logging.INFO)  # เปิดดู Price Hierarchy
logging.getLogger('portfolio_manager').setLevel(logging.INFO)   # เปิดดู Entry decisions
logging.getLogger('calculations').setLevel(logging.ERROR)
logging.getLogger('intelligent_position_manager').setLevel(logging.ERROR)
logging.getLogger('position_purpose_tracker').setLevel(logging.ERROR)
logging.getLogger('dynamic_7d_smart_closer').setLevel(logging.WARNING)
logging.getLogger('market_analysis').setLevel(logging.ERROR)

# ปิด logs ที่ไม่จำเป็น
for module in ['signal_manager', 'smart_gap_filler', 'force_trading_mode', 
               'advanced_breakout_recovery', 'price_zone_analysis', 'zone_rebalancer',
               'zone_position_manager', 'zone_manager', 'zone_analyzer', 'zone_coordinator']:
    logging.getLogger(module).setLevel(logging.ERROR)

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
        
        # 🚀 Enhanced 7D Entry + Position Modifier System
        self.enhanced_7d_entry_system = None
        
        # 🚀 Dynamic Adaptive Systems - Full Dynamic Trading Ecosystem
        self.dynamic_adaptive_entry = None
        self.dynamic_position_modifier = None
        self.dynamic_adaptive_closer = None
        
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
        
        # ⏰ Closing Cooldown - ป้องกันการปิดบ่อยเกินไป
        self.last_closing_time = None
        self.closing_cooldown_seconds = 30  # รอ 30 วินาทีระหว่างการปิด
        
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
            
            # 🚫 REMOVED: Zone-Based Position Management System
            # ✅ REASON: Redundant with Dynamic 7D Smart Closer
            # - Distance-based logic covered by Dynamic 7D
            # - Cross-zone analysis covered by Intelligent Manager
            # - Removing redundant systems improves closing intelligence
            logger.info("🚫 Zone Manager DISABLED - Using Dynamic 7D Smart Closer only")
            self.zone_position_manager = None  # Disabled
            
            # 🎯 Initialize Smart Entry Timing System
            logger.info("🎯 Initializing Smart Entry Timing System...")
            self.smart_entry_timing = create_smart_entry_timing(
                mt5_connection=self.mt5_connection,
                symbol=self.actual_symbol
            )
            logger.info(f"✅ Smart Entry Timing created: {type(self.smart_entry_timing)}")
            
            # 🛡️ Initialize Strategic Position Manager
            logger.info("🛡️ Initializing Strategic Position Manager...")
            self.strategic_position_manager = create_strategic_position_manager(
                smart_entry_timing=self.smart_entry_timing
            )
            
            # 🚀 Initialize Enhanced 7D Entry + Position Modifier System
            logger.info("🚀 Initializing Enhanced 7D Entry + Position Modifier System...")
            self.enhanced_7d_entry_system = create_enhanced_7d_entry_system(
                intelligent_manager=self.intelligent_position_manager,
                purpose_tracker=self.position_purpose_tracker,
                dynamic_7d_closer=self.dynamic_7d_smart_closer,
                mt5_connection=self.mt5_connection
            )
            logger.info(f"✅ Enhanced 7D Entry System created: {type(self.enhanced_7d_entry_system)}")
            
            # 🚀 Initialize Dynamic Adaptive Systems - Full Dynamic Trading Ecosystem
            logger.info("🚀 Initializing Dynamic Adaptive Trading Systems...")
            
            # Dynamic Entry System
            self.dynamic_adaptive_entry = create_dynamic_adaptive_entry_system(
                mt5_connection=self.mt5_connection,
                symbol=self.actual_symbol
            )
            logger.info(f"✅ Dynamic Adaptive Entry created: {type(self.dynamic_adaptive_entry)}")
            
            # Dynamic Position Modifier
            self.dynamic_position_modifier = create_dynamic_position_modifier(
                mt5_connection=self.mt5_connection,
                symbol=self.actual_symbol
            )
            logger.info(f"✅ Dynamic Position Modifier created: {type(self.dynamic_position_modifier)}")
            
            # Dynamic Adaptive Closer
            self.dynamic_adaptive_closer = create_dynamic_adaptive_closer(
                mt5_connection=self.mt5_connection,
                symbol=self.actual_symbol
            )
            logger.info(f"✅ Dynamic Adaptive Closer created: {type(self.dynamic_adaptive_closer)}")
            
            # 🔗 เชื่อมต่อ Smart Systems กับ Trading Conditions
            logger.info("🔗 Connecting Smart Systems to Trading Conditions...")
            self.trading_conditions.intelligent_position_manager = self.intelligent_position_manager
            self.trading_conditions.position_purpose_tracker = self.position_purpose_tracker
            self.trading_conditions.smart_entry_timing = self.smart_entry_timing
            self.trading_conditions.strategic_position_manager = self.strategic_position_manager
            self.trading_conditions.enhanced_7d_entry_system = self.enhanced_7d_entry_system
            
            # Connect Dynamic Adaptive Systems
            self.trading_conditions.dynamic_adaptive_entry = self.dynamic_adaptive_entry
            self.trading_conditions.dynamic_position_modifier = self.dynamic_position_modifier
            self.trading_conditions.dynamic_adaptive_closer = self.dynamic_adaptive_closer
            
            # 🔍 Verify connections
            logger.info(f"🔍 VERIFICATION:")
            logger.info(f"   Smart Entry Timing: {type(self.trading_conditions.smart_entry_timing) if self.trading_conditions.smart_entry_timing else 'NULL'}")
            logger.info(f"   Position Purpose Tracker: {type(self.trading_conditions.position_purpose_tracker) if self.trading_conditions.position_purpose_tracker else 'NULL'}")
            logger.info(f"   Enhanced 7D Entry System: {type(self.trading_conditions.enhanced_7d_entry_system) if self.trading_conditions.enhanced_7d_entry_system else 'NULL'}")
            logger.info(f"   Dynamic Adaptive Entry: {type(self.trading_conditions.dynamic_adaptive_entry) if self.trading_conditions.dynamic_adaptive_entry else 'NULL'}")
            logger.info(f"   Dynamic Position Modifier: {type(self.trading_conditions.dynamic_position_modifier) if self.trading_conditions.dynamic_position_modifier else 'NULL'}")
            logger.info(f"   Dynamic Adaptive Closer: {type(self.trading_conditions.dynamic_adaptive_closer) if self.trading_conditions.dynamic_adaptive_closer else 'NULL'}")
            
            # 🚫 REMOVED: Zone Manager connection to Portfolio Manager
            # ✅ Portfolio Manager now uses only Dynamic 7D Smart Closer
            
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
            
    def process_new_candle(self, candle: CandleData):
        """ประมวลผลแท่งเทียนใหม่ - ใช้ Smart Entry Timing System"""
        try:
            # แสดงราคาแบบเรียบง่าย
            logger.info(f"📊 {candle.close:.2f}")
            
        except Exception as e:
            logger.info(f"❌ Candle processing error: {str(e)}")
            
    # 🚫 REMOVED: calculate_signal_strength - Signal analysis moved to Smart Entry Timing System
            
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
            
            # 🎯 Generate SMART signal with Position-Aware Logic
            # Create a smart signal that considers existing positions
            raw_signal_direction = "BUY" if candle.close > candle.open else "SELL"
            
            # 🧠 Smart Signal Reversal: ดูตำแหน่งที่มีอยู่และปรับ Signal
            smart_signal_direction = self._get_smart_signal_direction(
                raw_signal_direction, current_price, self.order_manager.active_positions
            )
            
            # 🚀 DYNAMIC ADAPTIVE ANALYSIS - Ultimate Trading Intelligence
            account_info = self.mt5_connection.get_account_info() if self.mt5_connection else {}
            
            # 1. 🎯 Dynamic Entry Analysis
            if self.dynamic_adaptive_entry:
                dynamic_entry_analysis = self.dynamic_adaptive_entry.analyze_dynamic_entry(
                    signal_direction=smart_signal_direction,
                    current_price=current_price,
                    positions=self.order_manager.active_positions,
                    account_info=account_info,
                    candle_data=candle
                )
                
                # Override signal based on dynamic analysis
                if not dynamic_entry_analysis.should_enter:
                    logger.info(f"🚫 DYNAMIC ENTRY BLOCKED: {', '.join(dynamic_entry_analysis.entry_reasons)}")
                    return  # Skip this entry
                
                # Use dynamic direction and lot size
                smart_signal_direction = dynamic_entry_analysis.direction
                dynamic_lot_size = dynamic_entry_analysis.lot_size
                logger.info(f"🚀 DYNAMIC ENTRY APPROVED: {smart_signal_direction} {dynamic_lot_size} lot")
            
            # 2. 🔧 Dynamic Position Modification
            if self.dynamic_position_modifier:
                modification_plan = self.dynamic_position_modifier.analyze_portfolio_modifications(
                    positions=self.order_manager.active_positions,
                    account_info=account_info,
                    current_price=current_price
                )
                
                # Apply high-priority modifications
                self._apply_dynamic_modifications(modification_plan)
            
            # 3. 🚀 Enhanced 7D Entry Analysis (Backup/Validation)
            if self.enhanced_7d_entry_system:
                entry_7d_analysis = self.enhanced_7d_entry_system.analyze_entry_opportunity(
                    signal_direction=smart_signal_direction,
                    current_price=current_price,
                    positions=self.order_manager.active_positions,
                    account_info=account_info,
                    candle_data=candle
                )
                
                # 7D Validation
                if entry_7d_analysis.total_7d_score < 20.0:  # Very low 7D score
                    logger.info(f"🚫 7D VALIDATION FAILED: Score {entry_7d_analysis.total_7d_score:.1f}")
                    return  # Skip this entry
            
            basic_signal = Signal(
                direction=smart_signal_direction,
                symbol=self.actual_symbol,
                strength=abs(candle.close - candle.open) / (candle.high - candle.low) * 100 if candle.high != candle.low else 50,
                confidence=70.0,  # Default confidence
                timestamp=datetime.now(),
                price=current_price
            )
            
            # แสดงการปรับ signal
            if raw_signal_direction != smart_signal_direction:
                logger.info(f"🔄 SIGNAL REVERSAL: {raw_signal_direction} → {smart_signal_direction} (Price Hierarchy)")
            
            # ✅ Smart Entry Timing will analyze and approve/reject this signal
            decision = self.portfolio_manager.should_enter_trade(
                signal=basic_signal,
                candle=candle,
                current_state=portfolio_state,
                volume_history=self.volume_history
            )
            
            if decision['should_enter']:
                # 🎯 เข้าไม้
                logger.info(f"🎯 {basic_signal.direction} {decision['lot_size']:.2f} lots @ {basic_signal.price:.2f}")
                
                # ดำเนินการเทรด
                result = self.portfolio_manager.execute_trade_decision(decision)
                
                if result.success:
                    logger.info(f"✅ Order #{result.ticket} opened successfully")
                    self.portfolio_manager.update_trade_timing(trade_executed=True)
                else:
                    logger.info(f"❌ Order failed: {result.error_message}")
            else:
                # 🚫 ไม่เข้าไม้ (แสดงเฉพาะเหตุผลสำคัญ)
                reasons = decision.get('reasons', [])
                if reasons:
                    main_reason = reasons[0] if isinstance(reasons, list) else str(reasons)
                    short_reason = self._simplify_reason(main_reason)
                    if 'Smart Entry' in short_reason or 'Price Hierarchy' in short_reason:
                        logger.info(f"⏸️ {short_reason}")
                    # ไม่แสดง reason ธรรมดาเพื่อลด noise
                    
            # ล้าง signal หลังจากประมวลผล
            self.last_signal = None
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการตรวจสอบเงื่อนไขการเข้าเทรด: {str(e)}")
    
    def _get_smart_signal_direction(self, raw_direction: str, current_price: float, positions: List) -> str:
        """
        🧠 Smart Signal Direction: ปรับ Signal ให้เหมาะกับ Price Hierarchy
        
        Logic:
        - ถ้า BUY แต่มี SELL ต่ำกว่าราคาปัจจุบัน → กลับเป็น SELL (ช่วย SELL)
        - ถ้า SELL แต่มี BUY สูงกว่าราคาปัจจุบัน → กลับเป็น BUY (ช่วย BUY)
        - ถ้าไม่มีปัญหา → ใช้ signal เดิม
        """
        try:
            if not positions:
                return raw_direction
            
            # แยกประเภท positions
            buy_positions = [p for p in positions if getattr(p, 'type', 0) == 0]
            sell_positions = [p for p in positions if getattr(p, 'type', 1) == 1]
            
            # ตรวจสอบ BUY สูง (losing BUYs)
            losing_buys = [p for p in buy_positions if getattr(p, 'price_open', 0) > current_price + 10]
            
            # ตรวจสอบ SELL ต่ำ (losing SELLs)  
            losing_sells = [p for p in sell_positions if getattr(p, 'price_open', 0) < current_price - 10]
            
            # 🎯 Smart Logic: ช่วย positions ที่กำลังขาดทุน
            if raw_direction == "BUY" and losing_buys and len(losing_buys) > len(losing_sells):
                # มี BUY สูงๆ เยอะ → BUY ต่ำกว่าเพื่อ average down
                if current_price < min(getattr(p, 'price_open', current_price) for p in buy_positions) - 5:
                    return "BUY"  # BUY ต่ำกว่า existing BUYs = ดี
                else:
                    return "SELL"  # BUY ใกล้ๆ = ไม่ดี, กลับเป็น SELL
                    
            elif raw_direction == "SELL" and losing_sells and len(losing_sells) > len(losing_buys):
                # มี SELL ต่ำๆ เยอะ → SELL สูงกว่าเพื่อ average down
                if current_price > max(getattr(p, 'price_open', current_price) for p in sell_positions) + 5:
                    return "SELL"  # SELL สูงกว่า existing SELLs = ดี
                else:
                    return "BUY"   # SELL ใกล้ๆ = ไม่ดี, กลับเป็น BUY
            
            # ไม่มีปัญหา → ใช้ signal เดิม
            return raw_direction
            
        except Exception as e:
            logger.error(f"❌ Error in smart signal direction: {e}")
            return raw_direction
    
    def _apply_position_modifications(self, modifications):
        """
        🔧 Apply Position Modifications (Legacy)
        """
        try:
            if not modifications:
                return
            
            logger.info(f"🔧 APPLYING POSITION MODIFICATIONS: {len(modifications)} positions")
            
            for modification in modifications:
                if modification.expected_improvement > 0.4:  # High improvement expected
                    logger.info(f"🔧 High Priority Modification: Ticket {modification.position_ticket}")
                    logger.info(f"   Action: {modification.modifier_action.value}")
                    logger.info(f"   Expected Improvement: {modification.expected_improvement:.1%}")
                    
                    # 📝 Log suggested entry for manual review
                    suggested_entry = modification.suggested_entry
                    logger.info(f"   Suggested Entry: {suggested_entry}")
                    
                    # Note: Actual implementation would execute the modification
                    # For now, we just log the recommendations
                    
        except Exception as e:
            logger.error(f"❌ Error applying position modifications: {e}")
    
    def _apply_dynamic_modifications(self, modification_plan):
        """
        🚀 Apply Dynamic Position Modifications
        """
        try:
            if not modification_plan or not modification_plan.individual_modifications:
                return
            
            logger.info(f"🚀 APPLYING DYNAMIC MODIFICATIONS: {len(modification_plan.individual_modifications)} individual")
            
            # Apply critical and high priority modifications
            critical_mods = [mod for mod in modification_plan.individual_modifications 
                           if mod.priority.value in ['critical', 'high']]
            
            for mod in critical_mods[:3]:  # Limit to top 3 for safety
                logger.info(f"🚨 {mod.priority.value.upper()} MODIFICATION:")
                logger.info(f"   Ticket {mod.position_ticket}: {mod.recommended_action.value}")
                logger.info(f"   Expected Improvement: {mod.expected_improvement:.1%}")
                logger.info(f"   Success Probability: {mod.success_probability:.1%}")
                
                # Log emergency actions
                if modification_plan.emergency_actions:
                    logger.warning(f"🚨 EMERGENCY ACTIONS NEEDED: {', '.join(modification_plan.emergency_actions)}")
                    
        except Exception as e:
            logger.error(f"❌ Error applying dynamic modifications: {e}")
    
    def _execute_dynamic_closing(self, closing_groups, analysis):
        """
        🚀 Execute Dynamic Closing
        """
        try:
            if not closing_groups:
                logger.info("🔄 No closing groups to execute")
                return
            
            logger.info(f"🚀 EXECUTING DYNAMIC CLOSING: {len(closing_groups)} groups")
            
            for group in closing_groups:
                logger.info(f"💰 Closing Group {group.group_id}:")
                logger.info(f"   Positions: {len(group.positions)}")
                logger.info(f"   Total Profit: ${group.total_profit:.2f}")
                logger.info(f"   Reason: {group.closing_reason}")
                
                # Extract position tickets
                tickets = [getattr(pos, 'ticket', 0) for pos in group.positions]
                
                # Execute closing through order manager
                if tickets:
                    close_result = self.order_manager.close_positions_group(tickets)
                    if close_result.success:
                        logger.info(f"✅ Group {group.group_id} closed successfully: ${close_result.total_profit:.2f}")
                    else:
                        logger.error(f"❌ Group {group.group_id} closing failed: {close_result.error}")
                        
        except Exception as e:
            logger.error(f"❌ Error executing dynamic closing: {e}")
    
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
            
            # 🧠 Priority 2: Intelligent Manager (Fallback only if Dynamic 7D fails)
            if hasattr(self, 'intelligent_position_manager') and self.intelligent_position_manager and position_scores:
                logger.info(f"🧠 INTELLIGENT BACKUP: Using 7D intelligent manager")
                intelligent_decision = self.intelligent_position_manager.analyze_closing_decision(positions, account_info)
                if intelligent_decision.get('should_close', False):
                    intelligent_decision['method'] = 'intelligent_7d_backup'
                    logger.info(f"✅ INTELLIGENT DECISION: {intelligent_decision.get('positions_count', 0)} positions selected")
                    return intelligent_decision
            
            # 🚫 REMOVED Priority 3 & 4: Zone Manager and Portfolio Manager 
            # ✅ REASON: Priority 1 & 2 already cover all functionality:
            #    - Dynamic 7D handles distance-based (zone logic)
            #    - Intelligent Manager handles cross-zone analysis
            #    - Portfolio health covered by both systems
            #    - Redundant fallbacks slow down smart closing
            
            # 📊 Only 2 priorities now - cleaner and smarter
            logger.info(f"⏸️ NO CLOSING: Smart systems found no suitable positions to close")
            return {'should_close': False, 'reason': 'Smart analysis found no profitable closing opportunities', 'method': 'none'}
            
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
                
                # 🚀 DYNAMIC ADAPTIVE CLOSING - Ultimate Closing Intelligence
                logger.info(f"🚀 DYNAMIC CLOSING: Analyzing {len(positions)} positions...")
                
                # 1. 🎯 Dynamic Adaptive Closing Analysis
                account_info = self.mt5_connection.get_account_info()
                
                if self.dynamic_adaptive_closer:
                    dynamic_closing_analysis = self.dynamic_adaptive_closer.analyze_dynamic_closing(
                        positions=positions,
                        account_info=account_info,
                        current_price=current_price,
                        market_data={'volatility': 0.5, 'trend_strength': 0.6, 'volume': 0.4}  # Simplified
                    )
                    
                    if dynamic_closing_analysis.should_close:
                        logger.info(f"🚀 DYNAMIC CLOSING APPROVED: {dynamic_closing_analysis.closing_strategy.value}")
                        
                        # Create closing groups
                        closing_groups = self.dynamic_adaptive_closer.create_closing_groups(
                            positions=positions,
                            closing_strategy=dynamic_closing_analysis.closing_strategy,
                            current_price=current_price
                        )
                        
                        # Execute dynamic closing
                        self._execute_dynamic_closing(closing_groups, dynamic_closing_analysis)
                        return
                
                # 2. 🔄 Fallback to Enhanced Unified System
                logger.info(f"🤝 FALLBACK UNIFIED CLOSING: Analyzing {len(positions)} positions...")
                
                # Get 7D Analysis (คำนวณครั้งเดียว)
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
                        
                        # 📊 แสดงการตัดสินใจปิดไม้
                        count = len(filtered_positions)
                        expected_pnl = closing_result.get('expected_pnl', 0.0)
                        method = closing_result.get('method', 'unknown')
                        
                        logger.info(f"💰 Closing {count} positions (Expected: ${expected_pnl:.2f})")
                        
                        # 🔒 Lock positions before closing
                        self._lock_positions(filtered_positions)
                        
                        try:
                            # 3. 🎯 Execute closing via Order Manager (Zero Loss Policy enforced)
                            close_result = self.order_manager.close_positions_group(
                                filtered_positions, 
                                reason=f"Unified Decision: {method}"
                            )
                            if close_result.success:
                                closed_count = len(close_result.closed_tickets)
                                total_profit = close_result.total_profit
                                logger.info(f"✅ Closed {closed_count} positions: ${total_profit:.2f} profit")
                            else:
                                logger.info(f"❌ Close failed: {close_result.error_message}")
                        finally:
                            # 🔓 Always unlock positions after attempt
                            self._unlock_positions(filtered_positions)
                        return
                
                # 🧠 OLD SYSTEMS REMOVED - ใช้ Unified System แทน
                
                # 🚫 OLD ZONE SYSTEM REMOVED - Using Dynamic 7D Smart Closer only
                # ✅ All zone analysis now handled by Dynamic 7D Smart Closer
            
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
        logger.info("🚀 Trading System Starting...")
        
        # สร้างระบบเทรด
        trading_system = TradingSystem(
            initial_balance=10000.0,  # เงินทุนเริ่มต้น
            symbol="XAUUSD"           # สัญลักษณ์การเทรด (ทองคำ)
        )
        
        # เริ่มต้นระบบ
        if not trading_system.initialize_system():
            logger.info("❌ System initialization failed")
            return
            
        # แสดงข้อมูลสำคัญ
        logger.info(f"💰 Balance: ${trading_system.initial_balance:,.2f}")
        logger.info(f"📊 Symbol: {trading_system.actual_symbol}")
        logger.info("✅ System ready - Press 'Start Trading' to begin")
        logger.info("-" * 50)
        
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
