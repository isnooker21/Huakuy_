# -*- coding: utf-8 -*-
"""
🚀 Adaptive Multi-Method Zone Detection Trading System
=====================================================
🎯 NEW ADAPTIVE FEATURES:
✅ Multi-Method Zone Detection: Pivot Points, Fibonacci, Volume Profile, Price Levels, Swing Levels
✅ Adaptive Market Detection: Trending, Sideways, Volatile
✅ Dynamic Parameter Adjustment: ปรับพารามิเตอร์ตามสภาวะตลาด
✅ Multi-Timeframe Analysis: M1, M5, M15, H1
✅ Smart Entry Logic: Support/Resistance + Market Condition
✅ Recovery System: แก้ไม้ที่ขาดทุน
✅ 3 Second Loop: เข้าไม้ทุก 3 วินาที
✅ Market-Adaptive Trading

AUTHOR: Advanced Trading System
VERSION: 3.0.0 - Adaptive Edition
"""

import logging
import time
import threading
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any

import requests

# Import modules from original system
from mt5_connection import MT5Connection
from calculations import Position, PercentageCalculator, LotSizeCalculator
from trading_conditions import TradingConditions, Signal, CandleData
from order_management import OrderManager
from portfolio_manager import PortfolioManager, PortfolioState
from gui import TradingGUI

# ✅ KEEP POSITION MANAGEMENT & CLOSING SYSTEMS
from dynamic_position_modifier import create_dynamic_position_modifier
# 🚫 REMOVED: dynamic_adaptive_closer - Replaced by Enhanced 7D Smart Closer

# 🎯 NEW SMART TRADING SYSTEMS
from zone_analyzer import ZoneAnalyzer
from smart_entry_system import SmartEntrySystem
# 🚫 REMOVED: from portfolio_anchor import PortfolioAnchor

# 🚀 REAL-TIME STATUS TRACKING SYSTEMS
from position_status_manager import PositionStatusManager
from real_time_tracker import RealTimeTracker
from market_condition_detector import MarketConditionDetector

# 🚀 SIMPLE & CLEAN LOGGING CONFIGURATION
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('smart_entry_gui.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 🚀 NEW SYSTEM LOGGING - Clean & Simple
logging.getLogger('mt5_connection').setLevel(logging.WARNING)
logging.getLogger('order_management').setLevel(logging.WARNING)  # ลด log order management
logging.getLogger('dynamic_position_modifier').setLevel(logging.WARNING)  # ลด log position modifier
# 🚫 REMOVED: dynamic_adaptive_closer logging - Replaced by Enhanced 7D Smart Closer
logging.getLogger('calculations').setLevel(logging.ERROR)
logging.getLogger('zone_analyzer').setLevel(logging.ERROR)  # ลด log zone analyzer มาก

logger = logging.getLogger(__name__)

class AdaptiveTradingSystemGUI:
    """
    🚀 Adaptive Multi-Method Zone Detection Trading System
    
    NEW FEATURES:
    ✅ Multi-Method Zone Detection (5 Methods)
    ✅ Adaptive Market Detection (Trending/Sideways/Volatile)
    ✅ Dynamic Parameter Adjustment
    ✅ Multi-Timeframe Analysis (M1, M5, M15, H1)
    ✅ Smart Entry Logic with Market Condition
    ✅ Recovery System for Losing Positions
    ✅ Dynamic Lot Sizing (based on account balance)
    ✅ 3 Second Trading Loop
    ✅ Position Management Systems
    """
    
    def __init__(self, initial_balance: float = 10000.0, symbol: str = "XAUUSD"):
        """Initialize Smart Entry Trading System with GUI"""
        self.base_symbol = symbol
        self.actual_symbol = None
        self.initial_balance = initial_balance
        
        # 🚀 CORE SYSTEMS (Same as original)
        self.mt5_connection = MT5Connection()
        self.order_manager = OrderManager(self.mt5_connection)
        self.portfolio_manager = PortfolioManager(self.order_manager, initial_balance)
        self.trading_conditions = TradingConditions()
        
        # ✅ KEEP POSITION MANAGEMENT & CLOSING SYSTEMS
        self.dynamic_position_modifier = None
        # 🚫 REMOVED: All old closing systems - Replaced by Edge Priority Closing
        
        # 🎯 ADAPTIVE TRADING STATE
        self.last_candle_data = {}  # {timeframe: candle}
        self.timeframes = ['M1', 'M5', 'M15', 'H1']  # Multi-timeframe analysis
        self.last_trade_time = {}  # {timeframe: timestamp}
        
        # Initialize last trade times
        for tf in self.timeframes:
            self.last_trade_time[tf] = None
        
        # 🎯 Trading State (Same as original)
        self.is_running = False
        self.trading_thread = None
        self.last_candle_time = None
        
        # ข้อมูลตลาด - OPTIMIZED with Memory Management
        self.current_prices = {}
        self.volume_history = []
        self.price_history = []
        self.max_history_size = 100  # จำกัดขนาด history เพื่อประหยัด memory
        
        # GUI
        self.gui = None
        
        # 🎯 ADAPTIVE MARKET DETECTION
        self.market_condition = 'sideways'  # Current market condition
        self.last_market_analysis = 0
        self.market_analysis_interval = 30  # Analyze market every 30 seconds
        
        
        # 🔒 Position Locking
        self.closing_positions = set()
        self.closing_lock = threading.Lock()
        
        # ⏰ Closing Cooldown
        self.last_closing_time = None
        self.closing_cooldown_seconds = 30
        
        # 🎯 ADAPTIVE SMART TRADING SYSTEMS (Initialize later)
        self.zone_analyzer = None
        self.smart_entry_system = None
        self.portfolio_anchor = None
        self.smart_systems_enabled = True
        self.last_zone_analysis = 0
        self.zone_analysis_interval = 3  # ทุก 3 วินาที (ปรับให้เร็วขึ้น)
        self._smart_systems_thread = None  # เพิ่ม thread tracking
        
        # 🚀 REAL-TIME STATUS TRACKING SYSTEMS
        self.status_manager = None
        self.real_time_tracker = None
        self.market_detector = None
        self.status_tracker = None
        self.last_status_update = 0
        self.status_update_interval = 3  # อัพเดทสถานะทุก 3 วินาที
        
        # 🎯 ZONE DETECTION STATS
        self.zone_stats = {
            'pivot_points': {'support': 0, 'resistance': 0},
            'fibonacci': {'support': 0, 'resistance': 0},
            'volume_profile': {'support': 0, 'resistance': 0},
            'price_levels': {'support': 0, 'resistance': 0},
            'swing_levels': {'support': 0, 'resistance': 0}
        }
        self.last_zone_update = 0
        
    
    @property
    def is_trading(self):
        """Property สำหรับ GUI compatibility"""
        return self.is_running
    
    def initialize_system(self) -> bool:
        """Initialize all systems (Same structure as original)"""
        try:
            # 🔗 Connect to MT5
            if not self.mt5_connection.connect_mt5():
                logger.error("❌ ไม่สามารถเชื่อมต่อ MT5 ได้")
                return False
            
            # 🎯 Initialize Smart Trading Systems
            if self.smart_systems_enabled:
                self._initialize_smart_systems()
            
            # 🔍 Auto-detect gold symbol
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
            
            # โหลดข้อมูลราคาเริ่มต้น
            self.load_initial_market_data()
            
            # ✅ Initialize Position Management Systems (Keep from original)
            
            self.dynamic_position_modifier = create_dynamic_position_modifier(
                mt5_connection=self.mt5_connection,
                symbol=self.actual_symbol,
                hedge_pairing_closer=None,  # Disabled - Using Edge Priority Closing
                initial_balance=self.initial_balance
            )
            
            # 🚫 REMOVED: dynamic_adaptive_closer initialization - Replaced by Enhanced 7D Smart Closer
            
            # 🚀 Initialize Real-time Status Tracking Systems
            self._initialize_real_time_systems()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ เกิดข้อผิดพลาดในการเริ่มต้นระบบ: {str(e)}")
            return False
    
    def load_initial_market_data(self):
        """โหลดข้อมูลตลาดเริ่มต้น (Same as original)"""
        try:
            if not self.actual_symbol:
                return
                
            # โหลดราคาปัจจุบัน
            tick_data = self.mt5_connection.get_current_tick(self.actual_symbol)
            if tick_data:
                current_price = tick_data.get('bid', 0)
                self.current_prices[self.actual_symbol] = current_price
            
            # โหลดข้อมูลเทียนเริ่มต้น (ใช้ H1 = 16385)
            try:
                import MetaTrader5 as mt5
                candles = self.mt5_connection.get_market_data(self.actual_symbol, mt5.TIMEFRAME_H1, count=100)
            except:
                # Fallback if MT5 not available (for Mac development)
                candles = self.mt5_connection.get_market_data(self.actual_symbol, 16385, count=100)
            
            if candles:
                self.price_history = [candle.get('close', 0) for candle in candles[-50:]]
                self.volume_history = [candle.get('volume', 0) for candle in candles[-50:]]
                
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการโหลดข้อมูลตลาด: {str(e)}")
    
    def _initialize_real_time_systems(self):
        """🚀 Initialize Real-time Status Tracking Systems"""
        try:
            logger.info("🚀 [INIT] Initializing Real-time Status Tracking Systems...")
            
            # 1. Initialize Position Status Manager
            self.status_manager = PositionStatusManager()
            logger.info("✅ [INIT] Position Status Manager initialized")
            
            # 2. Initialize Market Condition Detector
            self.market_detector = MarketConditionDetector()
            logger.info("✅ [INIT] Market Condition Detector initialized")
            
            # 3. Initialize Real-time Tracker
            self.real_time_tracker = RealTimeTracker(self)
            logger.info("✅ [INIT] Real-time Tracker initialized")
            
            # 4. Initialize Status Tracker (Simple version)
            self.status_tracker = {
                'last_price': 0.0,
                'last_update': 0.0,
                'update_threshold': 3.0,
                'price_change_threshold': 5.0
            }
            logger.info("✅ [INIT] Status Tracker initialized")
            
            # 5. Start Real-time Monitoring
            self.real_time_tracker.start_monitoring()
            logger.info("✅ [INIT] Real-time monitoring started")
            
            logger.info("🎯 [INIT] Real-time Status Tracking Systems ready!")
            
        except Exception as e:
            logger.error(f"❌ [INIT] Error initializing real-time systems: {e}")
    
    def start_trading(self):
        """Start trading loop (Same as original structure)"""
        try:
            if self.is_running:
                logger.warning("ระบบเทรดกำลังทำงานอยู่แล้ว")
                return True
            
            try:
                self.report_status()
            except Exception as e:
                logger.error(f"❌ Status check failed: {e}")
                self.gui.alert(f"{e}", 'error')
                return False
            
            # 🚀 Initialize Edge Priority Closing System
            logger.info("🎯 Initializing Edge Priority Closing System...")
            
            self.is_running = True
            self.trading_thread = threading.Thread(target=self._trading_loop, daemon=True)
            self.trading_thread.start()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting trading: {e}")
            return False
    
    def stop_trading(self):
        """Stop trading loop (Same as original)"""
        if not self.is_running:
            logger.warning("ระบบเทรดไม่ได้ทำงานอยู่")
            return
        
        self.is_running = False
        if self.trading_thread and self.trading_thread != threading.current_thread():
            self.trading_thread.join(timeout=5)
        
        logger.info("🛑 หยุดระบบเทรดแล้ว")
    
    def _trading_loop(self):
        """Main trading loop with Smart Entry Logic"""
        
        # ลบ Performance Optimization Variables ออก - ใช้แบบเดิม
        
        while self.is_running:
            # 🕐 Status Reporting (every 15 minutes)
            if self.should_report_status():
                try:
                    self.report_status()
                except Exception as e:
                    self.stop_trading()
                    self.gui.alert(f"{e}", 'error')

            try:
                current_time = time.time()
                
                # ลบ Bar Close System ออกทั้งหมด - ทำงานทันที
                # if hasattr(self, 'hedge_pairing_closer') and self.hedge_pairing_closer:
                #     if self.hedge_pairing_closer._should_wait_for_bar_close('M5'):
                #         time.sleep(0.5)
                #         continue
                
                # Get current candle data
                current_candle = self._get_current_candle()
                if not current_candle:
                    time.sleep(1)
                    continue
                
                # 🕐 Log market status (every 5 minutes)
                if not hasattr(self, '_last_market_status_log'):
                    self._last_market_status_log = 0
                
                if current_time - self._last_market_status_log >= 300:  # 5 minutes
                    self.mt5_connection.log_market_status(self.actual_symbol or "XAUUSD")
                    self._last_market_status_log = current_time
                
                # Process Simple Breakout for all timeframes - DISABLED (ใช้ Smart Entry System แทน)
                # self._process_simple_breakout(current_candle)
                
                # 🎯 Edge Priority Closing Check (ใหม่) - ตรวจสอบการปิดไม้ขอบ - DISABLED
                # self._check_edge_priority_closing(current_candle)
                
                # 🔗 Hedge Pair Closing Check - ตรวจสอบโอกาสปิด Hedge Pairs - DISABLED
                # self._check_hedge_pair_closing_opportunities(current_candle)
                
                # 🚀 Real-time Status Tracking - ตรวจสอบสถานะไม้แบบ Real-time
                if self._should_update_status(current_candle, current_time):
                    self._update_position_status_realtime(current_candle, current_time)
                
                # Position Management (Keep original logic) - Throttle to every 20 seconds (เพิ่มจาก 10)
                if not hasattr(self, '_last_position_management_time'):
                    self._last_position_management_time = 0
                
                if current_time - self._last_position_management_time >= 20:  # Every 20 seconds (เพิ่มขึ้น)
                    # เรียกใน background thread เพื่อไม่ให้บล็อก main loop
                    def position_mgmt_worker():
                        try:
                            import signal
                            def timeout_handler(signum, frame):
                                raise TimeoutError("Position management timeout")
                            
                            # ตั้ง timeout 8 วินาที
                            try:
                                import platform
                                if platform.system() != 'Windows':  # signal ไม่ทำงานดีใน Windows
                                    signal.signal(signal.SIGALRM, timeout_handler)
                                    signal.alarm(8)
                            except:
                                pass  # ถ้าใช้ signal ไม่ได้ก็ข้าม
                            
                            self._handle_position_management(current_candle)
                            
                            try:
                                if platform.system() != 'Windows':
                                    signal.alarm(0)  # ยกเลิก timeout
                            except:
                                pass
                        except Exception as e:
                            logger.warning(f"⚠️ Position management timeout/error: {e}")
                    
                    # รัน position management ใน background
                    threading.Thread(target=position_mgmt_worker, daemon=True).start()
                    self._last_position_management_time = current_time
                
                # Dynamic Closing (Keep original logic) - Throttle to every 5 seconds (เร็วขึ้น)
                if not hasattr(self, '_last_dynamic_closing_time'):
                    self._last_dynamic_closing_time = 0
                
                if current_time - self._last_dynamic_closing_time >= 5:  # Every 5 seconds (เร็วขึ้น)
                    # เรียกใน background thread เพื่อไม่ให้บล็อก main loop
                    def dynamic_closing_worker():
                        try:
                            import signal
                            def timeout_handler(signum, frame):
                                raise TimeoutError("Dynamic closing timeout")
                            
                            # ตั้ง timeout 10 วินาที
                            try:
                                import platform
                                if platform.system() != 'Windows':  # signal ไม่ทำงานดีใน Windows
                                    signal.signal(signal.SIGALRM, timeout_handler)
                                    signal.alarm(10)
                            except:
                                pass  # ถ้าใช้ signal ไม่ได้ก็ข้าม
                            
                            # 🎯 Edge Priority Closing handled in main loop
                            
                            try:
                                if platform.system() != 'Windows':
                                    signal.alarm(0)  # ยกเลิก timeout
                            except:
                                pass
                        except Exception as e:
                            logger.warning(f"⚠️ Dynamic closing timeout/error: {e}")
                    
                    # รัน dynamic closing ใน background
                    threading.Thread(target=dynamic_closing_worker, daemon=True).start()
                    self._last_dynamic_closing_time = current_time
                
                # 🎯 Smart Trading Systems - Handle every 3 seconds (Smart Entry เป็นหลัก)
                if current_time - getattr(self, '_last_smart_systems_time', 0) >= 3:  # 3 วินาที (Smart Entry เป็นหลัก)
                    # ตรวจสอบว่า Smart Systems ทำงานอยู่หรือไม่ก่อนเริ่มใหม่
                    if not hasattr(self, '_smart_systems_running') or not self._smart_systems_running:
                        logger.info(f"🎯 Starting Smart Systems (interval: {current_time - getattr(self, '_last_smart_systems_time', 0):.1f}s)")
                        self._smart_systems_running = True
                        self._handle_smart_systems()
                        self._last_smart_systems_time = current_time
                    else:
                        logger.debug("🎯 Smart Systems already running, skipping...")
                
                # Sleep - เพิ่มเป็น 5 วินาที เพื่อลด CPU usage มากขึ้น
                time.sleep(5.0)  # ตรวจสอบแท่งเทียนทุก 5 วินาที (ลด GUI freeze มากขึ้น)
                
            except Exception as e:
                logger.error(f"❌ เกิดข้อผิดพลาดในลูปเทรด: {e}")
                time.sleep(5)
        
        logger.info("🔄 จบลูปเทรด")
    
    def should_report_status(self):
        """Check if it's time to report status"""
        if hasattr(self, 'next_report_time') and self.next_report_time:
            current_utc = datetime.now(timezone.utc)
            next_report_utc = self.next_report_time.astimezone(timezone.utc)
            
            return current_utc >= next_report_utc
        return True  # Report if no scheduled time

    def report_status(self):
        """Report the current status to the API"""
        try:
            account_info = self.mt5_connection.account_info
        except Exception as e:
            raise Exception(f"Failed to get account data: {str(e)}")
        
        status_response = requests.post(
            f"http://123.253.62.50:8080/api/customer-clients/status",
            json={
                "tradingAccountId": str(account_info.login),
                "name": account_info.name,
                "brokerName": account_info.company,
                "currentBalance": str(account_info.balance),
                "currentProfit": str(account_info.profit),
                "currency": account_info.currency,
                "botName": "Huakuy",
                "botVersion": "0.0.1"
            },
            timeout=10
        )
        
        if status_response.status_code == 200:
            response_data = status_response.json()
            
            # Check if trading is inactive
            if response_data.get("processedStatus") == "inactive":
                message = response_data.get("message", "Trading is inactive")
                raise Exception(f"Trading is inactive. {message}")
            
            # Store next report time for scheduling
            next_report_time = response_data.get("nextReportTime")
            if next_report_time:
                # Fix microseconds to 6 digits
                if '.' in next_report_time and '+' in next_report_time:
                    parts = next_report_time.split('.')
                    microseconds = parts[1].split('+')[0]
                    timezone_part = '+' + parts[1].split('+')[1]
                    
                    # Truncate microseconds to 6 digits
                    if len(microseconds) > 6:
                        microseconds = microseconds[:6]
                    
                    next_report_time = f"{parts[0]}.{microseconds}{timezone_part}"
                
                self.next_report_time = datetime.fromisoformat(next_report_time)
                logger.info(f"Next report scheduled for: {self.next_report_time}")
                
        else:
            raise Exception(f"Failed to check status: {status_response.status_code}")
    
    def _get_current_candle(self) -> Optional[CandleData]:
        """Get current candle data (M1 for general use)"""
        try:
            tick_data = self.mt5_connection.get_current_tick(self.actual_symbol)
            if not tick_data:
                return None
            
            current_price = tick_data.get('bid', 0)
            
            # Get latest candles (ใช้ M1 = 1)
            try:
                import MetaTrader5 as mt5
                candles = self.mt5_connection.get_market_data(self.actual_symbol, mt5.TIMEFRAME_M1, count=2)
            except:
                # Fallback if MT5 not available (for Mac development)
                candles = self.mt5_connection.get_market_data(self.actual_symbol, 1, count=2)
                
            if not candles or len(candles) < 1:
                return None
            
            latest_candle = candles[-1]
            
            return CandleData(
                open=latest_candle.get('open', current_price),
                high=latest_candle.get('high', current_price),
                low=latest_candle.get('low', current_price),
                close=latest_candle.get('close', current_price),
                volume=latest_candle.get('volume', 100),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"❌ Error getting current candle: {e}")
            return None
    
    def _get_current_candle_for_timeframe(self, timeframe: str) -> Optional[CandleData]:
        """Get current candle data for specific timeframe"""
        try:
            # Get candles from MT5 for specific timeframe
            mt5_timeframe_map = {
                'M5': 5,     # TIMEFRAME_M5
                'M15': 15,   # TIMEFRAME_M15
                'M30': 30,   # TIMEFRAME_M30
                'H1': 16385  # TIMEFRAME_H1
            }
            
            tf_value = mt5_timeframe_map.get(timeframe, 5)
            
            try:
                import MetaTrader5 as mt5
                tf_constants = {
                    'M5': mt5.TIMEFRAME_M5,
                    'M15': mt5.TIMEFRAME_M15,
                    'M30': mt5.TIMEFRAME_M30,
                    'H1': mt5.TIMEFRAME_H1
                }
                candles = self.mt5_connection.get_market_data(
                    self.actual_symbol, 
                    tf_constants.get(timeframe, mt5.TIMEFRAME_M5),
                    count=1
                )
            except:
                # Fallback if MT5 not available
                candles = self.mt5_connection.get_market_data(
                    self.actual_symbol, 
                    tf_value,
                    count=1
                )
            
            if not candles or len(candles) < 1:
                return None
            
            current_candle = candles[-1]
            
            # ใช้เวลาจริงของแท่งเทียนจาก MT5
            candle_time = current_candle.get('time', datetime.now())
            if isinstance(candle_time, (int, float)):
                # Convert timestamp to datetime
                candle_time = datetime.fromtimestamp(candle_time)
            
            return CandleData(
                open=current_candle.get('open', 0),
                high=current_candle.get('high', 0),
                low=current_candle.get('low', 0),
                close=current_candle.get('close', 0),
                volume=current_candle.get('volume', 100),
                timestamp=candle_time
            )
            
        except Exception as e:
            logger.error(f"❌ Error getting current candle for {timeframe}: {e}")
            return None
    
    def _process_simple_breakout(self, current_candle: CandleData):
        """
        🚫 DISABLED: Simple Breakout Logic (ใช้ Smart Entry System แทน)
        
        ระบบเก่านี้ถูกปิดใช้งานแล้ว เนื่องจาก:
        ❌ ขัดแย้งกับ Smart Entry System
        ❌ เข้าไม้ตามเทรนด์ (trend-following) ขณะที่ Smart Entry เข้าไม้ตาม Demand & Supply
        ❌ อาจเข้าไม้ทิศทางตรงข้ามกัน
        
        ใช้ Smart Entry System แทน:
        ✅ เข้าไม้ตาม Support/Resistance + Pivot Point
        ✅ เข้าไม้ทุก 5 วินาที
        ✅ ไม่มีการขัดแย้ง
        """
        # ระบบนี้ถูกปิดใช้งานแล้ว - ใช้ Smart Entry System แทน
        return
        
        try:
            # Process each timeframe
            logger.debug(f"🔍 Processing timeframes: {self.timeframes}")
            for timeframe in self.timeframes:
                logger.debug(f"🔍 Checking timeframe: {timeframe}")
                # Check if we can trade this timeframe (one per candle rule)
                if not self._can_trade_timeframe(timeframe):
                    logger.debug(f"⏰ {timeframe}: Cannot trade - already traded on this candle")
                    continue
                
                # Get current and previous candle for this specific timeframe
                current_tf_candle = self._get_current_candle_for_timeframe(timeframe)
                previous_candle = self._get_previous_candle(timeframe)
                
                if not current_tf_candle or not previous_candle:
                    continue
                
                # ระบบจาก commit 1dd13e0 - ง่ายและทำงานได้ดี
                
                # 🎯 SIMPLE BREAKOUT DETECTION
                breakout_signal = None
                
                if current_tf_candle.close > previous_candle.high:
                    # 🟢 BUY Breakout
                    breakout_signal = "BUY"
                    reason = f"Breakout BUY {timeframe}: {current_tf_candle.close:.2f} > {previous_candle.high:.2f}"
                    
                elif current_tf_candle.close < previous_candle.low:
                    # 🔴 SELL Breakout
                    breakout_signal = "SELL"
                    reason = f"Breakout SELL {timeframe}: {current_tf_candle.close:.2f} < {previous_candle.low:.2f}"
                
                if breakout_signal:
                    logger.info(f"🚀 {timeframe}: {breakout_signal} signal detected - {reason}")
                    
                    # 🚀 Execute breakout trade
                    self._execute_simple_breakout_trade(
                        direction=breakout_signal,
                        timeframe=timeframe,
                        current_candle=current_tf_candle,
                        reason=reason
                    )
                    
                    # อัปเดตเวลาการเทรดล่าสุดเป็นเวลาแท่งเทียนของ timeframe นั้น
                    self.last_trade_time[timeframe] = current_tf_candle.timestamp
                    logger.info(f"✅ {timeframe}: Trade executed, updated last_trade_time to {current_tf_candle.timestamp}")
                else:
                    logger.debug(f"⏰ {timeframe}: No breakout signal - Close: {current_tf_candle.close:.2f}, Prev High: {previous_candle.high:.2f}, Prev Low: {previous_candle.low:.2f}")
            
            # Update candle history
            self._update_candle_history(current_candle)
            
        except Exception as e:
            logger.error(f"❌ Error in simple breakout processing: {e}")
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    def _manage_hedge_group(self, hedge_positions: List, dragged_positions: List, helper_positions: List, current_candle: CandleData):
        """🎯 จัดการกลุ่มไม้ค้ำ + ไม้โดนลาก + ไม้ช่วย"""
        try:
            # จับคู่ไม้ค้ำ + ไม้โดนลาก + ไม้ช่วย
            for hedge in hedge_positions:
                for dragged in dragged_positions:
                    for helper in helper_positions:
                        # ตรวจสอบว่าสามารถจับคู่กันได้
                        if self._can_form_hedge_group(hedge, dragged, helper):
                            # ปิดกลุ่มไม้ค้ำ + ไม้โดนลาก + ไม้ช่วย
                            self._execute_hedge_group_closing(hedge, dragged, helper, current_candle)
                            return  # ปิดกลุ่มเดียวแล้วออก
                            
        except Exception as e:
            logger.error(f"🎯 [HEDGE GROUP] Error: {e}")
    
    def _manage_dragged_with_helper(self, dragged_positions: List, helper_positions: List, current_candle: CandleData):
        """🤝 จัดการไม้โดนลาก + ไม้ช่วย (กรณีไม่มีไม้ค้ำ)"""
        try:
            # จับคู่ไม้โดนลาก + ไม้ช่วย
            for dragged in dragged_positions:
                for helper in helper_positions:
                    # ตรวจสอบว่าสามารถจับคู่กันได้
                    if self._can_form_helper_pair(dragged, helper):
                        # ปิดคู่ไม้โดนลาก + ไม้ช่วย
                        self._execute_helper_pair_closing(dragged, helper, current_candle)
                        return  # ปิดคู่เดียวแล้วออก
                        
        except Exception as e:
            logger.error(f"🤝 [HELPER PAIR] Error: {e}")
    
    def _can_form_hedge_group(self, hedge: Dict, dragged: Dict, helper: Dict) -> bool:
        """🔍 ตรวจสอบว่าสามารถจับคู่กลุ่มไม้ค้ำได้"""
        try:
            # เงื่อนไข: ไม้ค้ำ + ไม้โดนลาก + ไม้ช่วย ต้องเป็นฝั่งเดียวกัน
            if hedge['type'] == dragged['type'] == helper['type']:
                # ตรวจสอบว่าการปิดจะได้กำไร
                total_profit = hedge['profit'] + dragged['profit'] + helper['profit']
                return total_profit > 0
            return False
            
        except Exception as e:
            logger.error(f"🔍 [HEDGE GROUP CHECK] Error: {e}")
            return False
    
    def _can_form_helper_pair(self, dragged: Dict, helper: Dict) -> bool:
        """🔍 ตรวจสอบว่าสามารถจับคู่ไม้ช่วยได้"""
        try:
            # เงื่อนไข: ไม้โดนลาก + ไม้ช่วย ต้องเป็นฝั่งเดียวกัน
            if dragged['type'] == helper['type']:
                # ตรวจสอบว่าการปิดจะได้กำไร
                total_profit = dragged['profit'] + helper['profit']
                return total_profit > 0
            return False
            
        except Exception as e:
            logger.error(f"🔍 [HELPER PAIR CHECK] Error: {e}")
            return False
    
    
    
    def _check_lot_size_balancing(self, classification: Dict):
        """⚖️ ตรวจสอบและปรับ lot size ให้สมดุล"""
        try:
            buy_positions = classification.get('edge_buy', []) + classification.get('middle_buy', []) + classification.get('near_buy', [])
            sell_positions = classification.get('edge_sell', []) + classification.get('middle_sell', []) + classification.get('near_sell', [])
            
            if not buy_positions and not sell_positions:
                return
            
            # วิเคราะห์ lot size ปัจจุบัน
            lot_analysis = self._analyze_lot_sizes(buy_positions, sell_positions)
            
            if lot_analysis['needs_balancing']:
                logger.info(f"⚖️ [LOT BALANCING] Detected lot size imbalance - BUY: {lot_analysis['buy_lots']}, SELL: {lot_analysis['sell_lots']}")
                
                # ปรับ lot size ให้สมดุล
                self._balance_lot_sizes(lot_analysis)
                
        except Exception as e:
            logger.error(f"⚖️ [LOT BALANCING] Error: {e}")
    
    def _analyze_lot_sizes(self, buy_positions: List, sell_positions: List) -> Dict:
        """📊 วิเคราะห์ lot size ปัจจุบัน"""
        try:
            # คำนวณ lot size ของแต่ละฝั่ง
            buy_lots = [getattr(pos, 'volume', 0.01) for pos in buy_positions]
            sell_lots = [getattr(pos, 'volume', 0.01) for pos in sell_positions]
            
            # คำนวณสถิติ
            buy_avg = sum(buy_lots) / len(buy_lots) if buy_lots else 0
            sell_avg = sum(sell_lots) / len(sell_lots) if sell_lots else 0
            
            # คำนวณความแตกต่าง
            buy_variance = max(buy_lots) - min(buy_lots) if buy_lots else 0
            sell_variance = max(sell_lots) - min(sell_lots) if sell_lots else 0
            
            # ตรวจสอบว่าต้องปรับหรือไม่
            needs_balancing = (buy_variance > 0.01 or sell_variance > 0.01) and (len(buy_lots) > 1 or len(sell_lots) > 1)
            
            return {
                'buy_lots': buy_lots,
                'sell_lots': sell_lots,
                'buy_avg': buy_avg,
                'sell_avg': sell_avg,
                'buy_variance': buy_variance,
                'sell_variance': sell_variance,
                'needs_balancing': needs_balancing,
                'buy_positions': buy_positions,
                'sell_positions': sell_positions
            }
            
        except Exception as e:
            logger.error(f"📊 [LOT ANALYSIS] Error: {e}")
            return {'needs_balancing': False}
    
    def _balance_lot_sizes(self, lot_analysis: Dict):
        """⚖️ ปรับ lot size ให้สมดุล"""
        try:
            buy_positions = lot_analysis['buy_positions']
            sell_positions = lot_analysis['sell_positions']
            
            # คำนวณ lot size เป้าหมาย
            target_buy_lot = lot_analysis['buy_avg'] if lot_analysis['buy_avg'] > 0 else 0.05
            target_sell_lot = lot_analysis['sell_avg'] if lot_analysis['sell_avg'] > 0 else 0.05
            
            # ปรับ lot size ของไม้ BUY
            for pos in buy_positions:
                current_lot = getattr(pos, 'volume', 0.01)
                if abs(current_lot - target_buy_lot) > 0.01:  # ต่างกันมากกว่า 0.01
                    self._adjust_position_lot_size(pos, target_buy_lot, "BUY Lot Balancing")
            
            # ปรับ lot size ของไม้ SELL
            for pos in sell_positions:
                current_lot = getattr(pos, 'volume', 0.01)
                if abs(current_lot - target_sell_lot) > 0.01:  # ต่างกันมากกว่า 0.01
                    self._adjust_position_lot_size(pos, target_sell_lot, "SELL Lot Balancing")
                    
        except Exception as e:
            logger.error(f"⚖️ [LOT BALANCING] Error: {e}")
    
    def _adjust_position_lot_size(self, position: Any, target_lot: float, reason: str):
        """🔧 ปรับ lot size ของไม้"""
        try:
            current_lot = getattr(position, 'volume', 0.01)
            ticket = getattr(position, 'ticket', 0)
            
            # คำนวณความแตกต่าง
            lot_diff = target_lot - current_lot
            
            if abs(lot_diff) < 0.01:  # ต่างกันน้อยกว่า 0.01 ไม่ต้องปรับ
                return
            
            # 🚫 REMOVED: Lot adjustment closing - Using new closing system
            logger.info(f"🔧 [LOT ADJUST] Lot size adjustment disabled - Using new closing system")
            
        except Exception as e:
            logger.error(f"🔧 [LOT ADJUST] Error: {e}")
    
    
    def _classify_positions(self, positions: List) -> Dict:
        """🎯 จำแนกไม้ตามสถานะ - ระบบใหม่ที่ฉลาด + เน้นระยะห่าง"""
        try:
            current_time = datetime.now()
            current_price = getattr(positions[0], 'price_current', 0) if positions else 0
            
            classification = {
                'profitable': [],      # ไม้กำไร
                'losing': [],          # ไม้ขาดทุน
                'edge_buy': [],        # ไม้ขอบ BUY (ไกลที่สุด)
                'edge_sell': [],       # ไม้ขอบ SELL (ไกลที่สุด)
                'middle_buy': [],      # ไม้กลาง BUY
                'middle_sell': [],     # ไม้กลาง SELL
                'near_buy': [],        # ไม้ BUY ใกล้ราคาปัจจุบัน
                'near_sell': [],       # ไม้ SELL ใกล้ราคาปัจจุบัน
                'orphan': [],          # ไม้เดี่ยว
                'old_positions': [],   # ไม้เก่า
                'high_risk': []        # ไม้เสี่ยงสูง
            }
            
            # คำนวณระยะห่างและจัดเรียงตามระยะห่าง
            positions_with_distance = []
            for pos in positions:
                price_open = getattr(pos, 'price_open', 0)
                distance = abs(price_open - current_price) if current_price > 0 else 0
                positions_with_distance.append((pos, distance))
            
            # เรียงตามระยะห่าง (ไกลที่สุดก่อน)
            positions_with_distance.sort(key=lambda x: x[1], reverse=True)
            
            for pos, distance in positions_with_distance:
                pos_type = getattr(pos, 'type', 0)
                profit = getattr(pos, 'profit', 0)
                time_open = getattr(pos, 'time', current_time)
                
                # คำนวณเวลาที่เปิด
                time_diff = (current_time - time_open).total_seconds() / 60  # นาที
                
                # จำแนกตามกำไร/ขาดทุน
                if profit > 1.0:
                    classification['profitable'].append(pos)
                elif profit < -1.0:
                    classification['losing'].append(pos)
                
                # จำแนกตามระยะห่าง (ปรับใหม่ให้เน้นไม้ไกล)
                if distance > 3.0:  # ไม้ไกลมาก (Edge) - ปิดก่อน
                    if pos_type == 0:  # BUY
                        classification['edge_buy'].append(pos)
                    else:  # SELL
                        classification['edge_sell'].append(pos)
                elif distance > 1.0:  # ไม้กลาง
                    if pos_type == 0:  # BUY
                        classification['middle_buy'].append(pos)
                    else:  # SELL
                        classification['middle_sell'].append(pos)
                else:  # ไม้ใกล้ราคาปัจจุบัน - เก็บไว้
                    if pos_type == 0:  # BUY
                        classification['near_buy'].append(pos)
                    else:  # SELL
                        classification['near_sell'].append(pos)
                
                # ไม้เก่า (เปิดนานเกิน 1 ชั่วโมง)
                if time_diff > 60:
                    classification['old_positions'].append(pos)
                
                # ไม้เสี่ยงสูง (ขาดทุนมาก + เปิดนาน)
                if profit < -2.0 and time_diff > 30:
                    classification['high_risk'].append(pos)
            
            # หาไม้เดี่ยว (ไม้ที่ไม่มีคู่กำไร)
            classification['orphan'] = self._find_orphan_positions(positions)
            
            # เรียงไม้ขอบตามระยะห่าง (ไกลที่สุดก่อน)
            classification['edge_buy'].sort(key=lambda x: abs(getattr(x, 'price_open', 0) - current_price), reverse=True)
            classification['edge_sell'].sort(key=lambda x: abs(getattr(x, 'price_open', 0) - current_price), reverse=True)
            
            logger.info(f"🎯 [CLASSIFICATION] Profitable: {len(classification['profitable'])}, "
                       f"Losing: {len(classification['losing'])}, "
                       f"Edge: {len(classification['edge_buy']) + len(classification['edge_sell'])}, "
                       f"Near: {len(classification['near_buy']) + len(classification['near_sell'])}, "
                       f"Old: {len(classification['old_positions'])}, "
                       f"Orphan: {len(classification['orphan'])}")
            
            return classification
            
        except Exception as e:
            logger.error(f"🎯 [CLASSIFICATION] Error: {e}")
            return {}
    
    def _find_orphan_positions(self, positions: List) -> List:
        """🔍 หาไม้เดี่ยวที่ไม่มีคู่กำไร"""
        try:
            orphan_positions = []
            
            for pos in positions:
                profit = getattr(pos, 'profit', 0)
                
                # ไม้ขาดทุนที่ไม่มีไม้กำไรมาช่วย
                if profit < -1.0:
                    # ตรวจสอบว่ามีไม้กำไรมาช่วยได้หรือไม่
                    has_helper = False
                    for other_pos in positions:
                        if other_pos != pos and getattr(other_pos, 'profit', 0) > 1.0:
                            # ตรวจสอบว่าสามารถช่วยกันได้หรือไม่
                            if self._can_positions_help_each_other(pos, other_pos):
                                has_helper = True
                                break
                    
                    if not has_helper:
                        orphan_positions.append(pos)
            
            return orphan_positions
            
        except Exception as e:
            logger.error(f"🔍 [ORPHAN] Error: {e}")
            return []
    
    def _can_positions_help_each_other(self, losing_pos: Any, helper_pos: Any) -> bool:
        """🤝 ตรวจสอบว่าไม้สองตัวสามารถช่วยกันได้หรือไม่"""
        try:
            losing_profit = getattr(losing_pos, 'profit', 0)
            helper_profit = getattr(helper_pos, 'profit', 0)
            
            # ตรวจสอบว่ากำไรรวม > 0
            total_profit = losing_profit + helper_profit
            
            # ตรวจสอบระยะห่างจากราคาปัจจุบัน
            current_price = getattr(losing_pos, 'price_current', 0)
            losing_distance = abs(getattr(losing_pos, 'price_open', 0) - current_price)
            helper_distance = abs(getattr(helper_pos, 'price_open', 0) - current_price)
            
            # เงื่อนไข: กำไรรวม > 0 และระยะห่างไม่ไกลเกินไป
            return total_profit > 0 and max(losing_distance, helper_distance) < 5.0
            
        except Exception as e:
            logger.error(f"🤝 [HELPER] Error: {e}")
            return False
    
    
    
    
    
    def _check_hedge_pair_creation(self, classification: Dict):
        """🔗 สร้าง Hedge Pairs สำหรับไม้ที่เหลือ"""
        try:
            buy_positions = classification.get('middle_buy', []) + classification.get('edge_buy', [])
            sell_positions = classification.get('middle_sell', []) + classification.get('edge_sell', [])
            
            if not buy_positions or not sell_positions:
                return
            
            # หาไม้ที่สามารถจับคู่กันได้
            hedge_pairs = []
            
            for buy_pos in buy_positions:
                for sell_pos in sell_positions:
                    # ตรวจสอบว่าสามารถจับคู่กันได้หรือไม่
                    if self._can_create_hedge_pair(buy_pos, sell_pos):
                        total_profit = getattr(buy_pos, 'profit', 0) + getattr(sell_pos, 'profit', 0)
                        hedge_pairs.append({
                            'buy_position': buy_pos,
                            'sell_position': sell_pos,
                            'total_profit': total_profit
                        })
            
            # เรียงตามกำไรรวม (มากที่สุดก่อน)
            hedge_pairs.sort(key=lambda x: x['total_profit'], reverse=True)
            
            # สร้าง Hedge Pairs ที่ดีที่สุด 2 คู่
            for pair in hedge_pairs[:2]:
                self._create_hedge_pair(pair)
                
        except Exception as e:
            logger.error(f"🔗 [HEDGE CREATION] Error: {e}")
    
    def _can_create_hedge_pair(self, buy_pos: Any, sell_pos: Any) -> bool:
        """🤝 ตรวจสอบว่าสามารถสร้าง Hedge Pair ได้หรือไม่"""
        try:
            buy_profit = getattr(buy_pos, 'profit', 0)
            sell_profit = getattr(sell_pos, 'profit', 0)
            
            # เงื่อนไข: กำไรรวม > 0 และไม่ใช่ไม้ที่ขาดทุนมาก
            total_profit = buy_profit + sell_profit
            return total_profit > 0 and buy_profit > -2.0 and sell_profit > -2.0
            
        except Exception as e:
            logger.error(f"🤝 [HEDGE CHECK] Error: {e}")
            return False
    
    def _create_hedge_pair(self, pair: Dict):
        """🔗 สร้าง Hedge Pair"""
        try:
            buy_pos = pair['buy_position']
            sell_pos = pair['sell_position']
            
            # สร้าง Hedge Pair ID
            pair_id = f"HEDGE_{getattr(buy_pos, 'ticket', 0)}_{getattr(sell_pos, 'ticket', 0)}"
            
            # เก็บข้อมูล Hedge Pair
            hedge_pair = {
                'pair_id': pair_id,
                'buy_position': buy_pos,
                'sell_position': sell_pos,
                'buy_ticket': getattr(buy_pos, 'ticket', 0),
                'sell_ticket': getattr(sell_pos, 'ticket', 0),
                'buy_profit': getattr(buy_pos, 'profit', 0),
                'sell_profit': getattr(sell_pos, 'profit', 0),
                'combined_profit': pair['total_profit'],
                'created_time': datetime.now()
            }
            
            # เก็บใน hedge_pairs
            if not hasattr(self, 'hedge_pairs'):
                self.hedge_pairs = []
            
            self.hedge_pairs.append(hedge_pair)
            
            logger.info(f"🔗 [HEDGE CREATED] Pair {pair_id}: BUY ${hedge_pair['buy_profit']:.2f} + "
                       f"SELL ${hedge_pair['sell_profit']:.2f} = ${hedge_pair['combined_profit']:.2f}")
                
        except Exception as e:
            logger.error(f"🔗 [HEDGE CREATION] Error: {e}")
    
    def _should_close_hedge_pair(self, hedge_pair: Dict, current_candle: CandleData) -> bool:
        """✅ ตรวจสอบว่าควรปิด Hedge Pair หรือไม่"""
        try:
            combined_profit = hedge_pair['combined_profit']
            
            # เงื่อนไขการปิด Hedge Pair
            # 1. กำไรรวม ≥ $1.0
            if combined_profit >= 1.0:
                logger.info(f"✅ [HEDGE CLOSE] Pair {hedge_pair['pair_id']} profit ${combined_profit:.2f} ≥ $1.0")
                return True
            
            # 2. ไม้ใดไม้หนึ่งขาดทุนมากเกินไป (≥ -$5.0)
            if hedge_pair['buy_profit'] <= -5.0 or hedge_pair['sell_profit'] <= -5.0:
                logger.info(f"⚠️ [HEDGE CLOSE] Pair {hedge_pair['pair_id']} has heavy loss - closing for safety")
                return True
            
            # 3. ไม้คู่กันมานานเกินไป (≥ 24 ชั่วโมง)
            created_time = hedge_pair['created_time']
            hours_old = (datetime.now() - created_time).total_seconds() / 3600
            if hours_old >= 24:
                logger.info(f"⏰ [HEDGE CLOSE] Pair {hedge_pair['pair_id']} is {hours_old:.1f} hours old - closing")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking hedge pair closing: {e}")
            return False
    
    def _close_hedge_pair(self, hedge_pair: Dict):
        """🚀 ปิด Hedge Pair"""
        try:
            buy_pos = hedge_pair['buy_position']
            sell_pos = hedge_pair['sell_position']
            
            positions_to_close = [buy_pos, sell_pos]
            
            # 🚫 REMOVED: Hedge pair closing - Using new closing system
            logger.info(f"🔧 [HEDGE CLOSE] Hedge pair closing disabled - Using new closing system")
                
        except Exception as e:
            logger.error(f"❌ Error closing hedge pair: {e}")
    
    def _can_trade_timeframe(self, timeframe: str) -> bool:
        """Check if we can trade this timeframe (one trade per candle rule) - ตรวจสอบแท่งเทียนปิดจริง"""
        last_trade = self.last_trade_time.get(timeframe)
        if last_trade is None:
            return True
        
        # ตรวจสอบแท่งเทียนปิดจริงของ timeframe นั้นๆ
        current_tf_candle = self._get_current_candle_for_timeframe(timeframe)
        if not current_tf_candle:
            return False
        
        # ตรวจสอบว่าแท่งเทียนปัจจุบันเป็นแท่งใหม่หรือไม่
        current_candle_time = current_tf_candle.timestamp
        last_trade_time = last_trade
        
        # เปรียบเทียบเวลาแท่งเทียน (ไม่ใช่เวลาปัจจุบัน)
        return current_candle_time > last_trade_time
    
    def _get_previous_candle(self, timeframe: str) -> Optional[CandleData]:
        """Get previous candle for timeframe"""
        try:
            # Get candles from MT5
            mt5_timeframe_map = {
                'M5': 5,     # TIMEFRAME_M5
                'M15': 15,   # TIMEFRAME_M15
                'M30': 30,   # TIMEFRAME_M30
                'H1': 16385  # TIMEFRAME_H1
            }
            
            tf_value = mt5_timeframe_map.get(timeframe, 5)
            
            try:
                import MetaTrader5 as mt5
                tf_constants = {
                    'M5': mt5.TIMEFRAME_M5,
                    'M15': mt5.TIMEFRAME_M15,
                    'M30': mt5.TIMEFRAME_M30,
                    'H1': mt5.TIMEFRAME_H1
                }
                candles = self.mt5_connection.get_market_data(
                    self.actual_symbol, 
                    tf_constants.get(timeframe, mt5.TIMEFRAME_M5),
                    count=2
                )
            except:
                # Fallback if MT5 not available
                candles = self.mt5_connection.get_market_data(
                    self.actual_symbol, 
                    tf_value,
                    count=2
                )
            
            if not candles or len(candles) < 2:
                return None
            
            prev_candle = candles[-2]  # Previous candle
            
            # ใช้เวลาจริงของแท่งเทียนจาก MT5
            candle_time = prev_candle.get('time', datetime.now())
            if isinstance(candle_time, (int, float)):
                # Convert timestamp to datetime
                candle_time = datetime.fromtimestamp(candle_time)
            
            return CandleData(
                open=prev_candle.get('open', 0),
                high=prev_candle.get('high', 0),
                low=prev_candle.get('low', 0),
                close=prev_candle.get('close', 0),
                volume=prev_candle.get('volume', 100),
                timestamp=candle_time
            )
            
        except Exception as e:
            logger.error(f"❌ Error getting previous candle for {timeframe}: {e}")
            return None
    
    def _execute_simple_breakout_trade(self, direction: str, timeframe: str, 
                                     current_candle: CandleData, reason: str):
        """Execute simple breakout trade"""
        try:
            # ลบ Bar Close System ออกทั้งหมด - ทำงานทันที
            
            # 🎯 SW Filter disabled - Using Edge Priority Closing instead
            
            # 💰 Calculate dynamic lot size
            lot_size = self._calculate_dynamic_lot_size(current_candle, timeframe)
            
            logger.info(f"🚀 SIMPLE BREAKOUT: {direction} {timeframe}")
            logger.info(f"   💰 Lot Size: {lot_size:.3f}")
            logger.info(f"   🎯 Price: {current_candle.close:.2f}")
            logger.info(f"   📝 Reason: {reason}")
            
            # Create signal for portfolio manager with detailed comment
            comment = f"SimpleBreakout-{timeframe}-{direction}-{current_candle.close:.2f}"
            
            signal = Signal(
                direction=direction,
                symbol=self.actual_symbol,
                strength=self._calculate_candle_strength(current_candle),
                confidence=80.0,  # High confidence for breakouts
                timestamp=datetime.now(),
                price=current_candle.close,
                comment=comment,  # Add comment to signal
                stop_loss=0.0,   # No stop loss for breakout system
                take_profit=0.0  # No take profit for breakout system
            )
            
            # 🚀 DIRECT ORDER EXECUTION - Bypass all complex blocking systems
            # Get account balance for order placement
            account_info = self.mt5_connection.get_account_info() if self.mt5_connection else {}
            account_balance = account_info.get('balance', self.initial_balance) if account_info else self.initial_balance
            
            # Place order using OrderManager
            result = self.order_manager.place_order_from_signal(
                signal=signal,
                lot_size=lot_size,
                account_balance=account_balance
            )
            
            if result and hasattr(result, 'success') and result.success:
                logger.info(f"✅ BREAKOUT TRADE EXECUTED: Order #{getattr(result, 'ticket', 'N/A')}")
                # Update last trade time to candle timestamp
                self.last_trade_time[timeframe] = current_candle.timestamp
            else:
                error_msg = getattr(result, 'error_message', 'Unknown error') if result else 'No result'
                logger.error(f"❌ BREAKOUT TRADE FAILED: {error_msg}")
                    
        except Exception as e:
            logger.error(f"❌ Error executing breakout trade: {e}")
    
    def _calculate_dynamic_lot_size(self, candle: CandleData, timeframe: str) -> float:
        """Calculate dynamic lot size based on candle strength and timeframe"""
        try:
            # Get account balance
            account_info = self.mt5_connection.get_account_info()
            balance = account_info.get('balance', self.initial_balance) if account_info else self.initial_balance
            
            # Base risk: 2% of balance
            risk_amount = balance * 0.02
            
            # Candle strength factor
            candle_strength = self._calculate_candle_strength(candle)
            strength_multiplier = 0.5 + (candle_strength / 100.0)  # 0.5 to 1.5
            
            # Timeframe multiplier
            tf_multipliers = {
                'M5': 0.5,   # Lower risk for scalping
                'M15': 0.75,
                'M30': 1.0,  # Base
                'H1': 1.5    # Higher risk for swing
            }
            tf_multiplier = tf_multipliers.get(timeframe, 1.0)
            
            # Calculate lot size (rough calculation)
            base_lot = (risk_amount / 1000) * strength_multiplier * tf_multiplier
            
            # Apply limits
            min_lot = 0.01
            max_lot = min(1.0, balance / 5000)
            
            final_lot = max(min_lot, min(max_lot, base_lot))
            
            return round(final_lot, 2)
            
        except Exception as e:
            logger.error(f"❌ Error calculating lot size: {e}")
            return 0.01
    
    def _calculate_candle_strength(self, candle: CandleData) -> float:
        """Calculate candle strength (body/range ratio)"""
        try:
            candle_range = candle.high - candle.low
            candle_body = abs(candle.close - candle.open)
            
            if candle_range > 0:
                strength = (candle_body / candle_range) * 100
            else:
                strength = 50.0
            
            return min(100.0, max(0.0, strength))
            
        except Exception as e:
            logger.error(f"❌ Error calculating candle strength: {e}")
            return 50.0
    
    def _update_candle_history(self, candle: CandleData):
        """Update candle history - OPTIMIZED with Memory Management"""
        for tf in self.timeframes:
            self.last_candle_data[tf] = candle
        
        # 🚀 OPTIMIZED: Update price range history with memory management
        self._update_price_range_history(candle)
        
        # 🚀 OPTIMIZED: Cleanup old data to prevent memory leaks
        self._cleanup_old_data()
    
    def _update_price_range_history(self, candle: CandleData):
        """Update price range history for range-bound market detection"""
        try:
            # เพิ่มข้อมูลราคาใหม่
            price_data = {
                'high': candle.high,
                'low': candle.low,
                'close': candle.close,
                'timestamp': candle.timestamp
            }
            
            self.price_range_history.append(price_data)
            
            # เก็บเฉพาะข้อมูลล่าสุด
            if len(self.price_range_history) > self.range_check_period:
                self.price_range_history = self.price_range_history[-self.range_check_period:]
                
        except Exception as e:
            logger.error(f"❌ Error updating price range history: {e}")
    
    def _cleanup_old_data(self):
        """Cleanup old data to prevent memory leaks - OPTIMIZED"""
        try:
            # 🚀 OPTIMIZED: Limit price history size
            if len(self.price_history) > self.max_history_size:
                self.price_history = self.price_history[-self.max_history_size:]
            
            # 🚀 OPTIMIZED: Limit volume history size
            if len(self.volume_history) > self.max_history_size:
                self.volume_history = self.volume_history[-self.max_history_size:]
            
            # 🚀 OPTIMIZED: Limit price range history size
            if len(self.price_range_history) > self.max_history_size:
                self.price_range_history = self.price_range_history[-self.max_history_size:]
                
        except Exception as e:
            logger.debug(f"Error during data cleanup: {e}")
    
    def _is_range_bound_market(self) -> bool:
        """
        🛡️ ตรวจสอบว่าตลาดอยู่ในสภาพ Range-bound หรือไม่
        
        เงื่อนไข:
        1. มี positions จำนวนมาก (≥ min_positions_for_range_check)
        2. ราคาวิ่งขึ้นลงไม่เกิน max_range_points จุด ใน range_check_period candles
        
        Returns:
            bool: True ถ้าเป็น range-bound market
        """
        try:
            # 1. ตรวจสอบจำนวน positions
            positions = self.order_manager.active_positions
            if len(positions) < self.min_positions_for_range_check:
                return False
            
            # 2. ตรวจสอบข้อมูลราคา
            if len(self.price_range_history) < 10:  # ต้องมีข้อมูลอย่างน้อย 10 candles
                return False
            
            # 3. คำนวณ range ของราคา
            recent_prices = self.price_range_history[-self.range_check_period:]
            
            highest_price = max(price_data['high'] for price_data in recent_prices)
            lowest_price = min(price_data['low'] for price_data in recent_prices)
            
            price_range = highest_price - lowest_price
            
            # 4. ตรวจสอบว่า range น้อยกว่าที่กำหนดหรือไม่
            is_range_bound = price_range <= self.max_range_points
            
            if is_range_bound:
                logger.warning(f"🛡️ RANGE-BOUND MARKET DETECTED:")
                logger.warning(f"   📊 Price Range: {price_range:.1f} points (Max: {self.max_range_points})")
                logger.warning(f"   📈 Highest: {highest_price:.2f}")
                logger.warning(f"   📉 Lowest: {lowest_price:.2f}")
                logger.warning(f"   🎯 Positions: {len(positions)} (Min: {self.min_positions_for_range_check})")
                logger.warning(f"   ⏸️ TRADING PAUSED - Waiting for trend breakout")
            
            return is_range_bound
            
        except Exception as e:
            logger.error(f"❌ Error checking range-bound market: {e}")
            return False
    
    def _get_portfolio_state(self) -> PortfolioState:
        """Get current portfolio state"""
        try:
            positions = self.order_manager.active_positions
            account_info = self.mt5_connection.get_account_info() if self.mt5_connection else {}
            
            # Calculate portfolio metrics
            total_positions = len(positions)
            buy_positions = len([p for p in positions if getattr(p, 'type', 0) == 0])
            sell_positions = len([p for p in positions if getattr(p, 'type', 1) == 1])
            total_profit = sum(getattr(p, 'profit', 0) for p in positions)
            
            # Get account info
            account_balance = account_info.get('balance', self.initial_balance) if account_info else self.initial_balance
            equity = account_info.get('equity', account_balance) if account_info else account_balance
            margin = account_info.get('margin', 0) if account_info else 0
            margin_level = account_info.get('margin_level', 1000) if account_info else 1000
            
            # Calculate percentages
            total_profit_percentage = (total_profit / account_balance * 100) if account_balance > 0 else 0
            exposure_percentage = (margin / account_balance * 100) if account_balance > 0 else 0
            risk_percentage = exposure_percentage  # Simplified
            
            # Buy/sell ratio
            buy_sell_ratio = {
                'buy_ratio': (buy_positions / total_positions * 100) if total_positions > 0 else 50,
                'sell_ratio': (sell_positions / total_positions * 100) if total_positions > 0 else 50
            }
            
            return PortfolioState(
                account_balance=account_balance,
                equity=equity,
                margin=margin,
                margin_level=margin_level,
                total_positions=total_positions,
                buy_positions=buy_positions,
                sell_positions=sell_positions,
                total_profit=total_profit,
                total_profit_percentage=total_profit_percentage,
                exposure_percentage=exposure_percentage,
                risk_percentage=risk_percentage,
                buy_sell_ratio=buy_sell_ratio
            )
            
        except Exception as e:
            logger.error(f"❌ Error getting portfolio state: {e}")
            # Return default PortfolioState
            return PortfolioState(
                account_balance=self.initial_balance,
                equity=self.initial_balance,
                margin=0,
                margin_level=1000,
                total_positions=0,
                buy_positions=0,
                sell_positions=0,
                total_profit=0,
                total_profit_percentage=0,
                exposure_percentage=0,
                risk_percentage=0,
                buy_sell_ratio={'buy_ratio': 50, 'sell_ratio': 50}
            )
    
    def _handle_position_management(self, candle: CandleData):
        """Handle position management (Keep original logic)"""
        try:
            if not self.dynamic_position_modifier:
                return
            
            account_info = self.mt5_connection.get_account_info()
            positions = self.order_manager.active_positions
            
            if not positions:
                return
            
            modification_plan = self.dynamic_position_modifier.analyze_portfolio_modifications(
                positions=positions,
                account_info=account_info or {},
                current_price=candle.close
            )
            
            # Apply modifications if needed
            if modification_plan and hasattr(modification_plan, 'modifications'):
                for modification in modification_plan.modifications:
                    if modification.priority in ['HIGH', 'CRITICAL']:
                        logger.info(f"🔧 APPLYING MODIFICATION: {modification.action}")
                        
        except Exception as e:
            logger.error(f"❌ Error in position management: {e}")
    
    # 🚫 REMOVED: _handle_dynamic_closing - Replaced by Edge Priority Closing
    
    def _initialize_smart_systems(self):
        """🎯 Initialize Smart Trading Systems"""
        try:
            
            # Initialize Zone Analyzer
            self.zone_analyzer = ZoneAnalyzer(self.mt5_connection)
            
            # Initialize Smart Entry System
            self.smart_entry_system = SmartEntrySystem(self.mt5_connection, self.zone_analyzer)
            # ส่ง order_manager ไปยัง SmartEntrySystem
            self.smart_entry_system.order_manager = self.order_manager
            
            # 🚫 Portfolio Anchor REMOVED - Using Edge Priority Closing only
            self.portfolio_anchor = None
            
        except Exception as e:
            logger.error(f"❌ Error initializing smart systems: {e}")
            self.smart_systems_enabled = False
    
    def _handle_smart_systems(self):
        """🎯 Handle Smart Trading Systems"""
        try:
            logger.info("🎯 [SMART SYSTEMS] Starting Smart Systems processing...")
            
            # ตรวจสอบ smart_systems_enabled
            if not self.smart_systems_enabled:
                logger.warning("🚫 Smart Systems disabled - skipping")
                return
            
            # ตรวจสอบ components
            if not self.zone_analyzer:
                logger.warning("🚫 Zone Analyzer not available - skipping")
                return
                
            if not self.smart_entry_system:
                logger.warning("🚫 Smart Entry System not available - skipping")
                return
                
            # 🚫 Portfolio Anchor REMOVED - Using Edge Priority Closing only
            logger.debug("🚫 Portfolio Anchor removed - Using Edge Priority Closing only")
                
            
            current_time = time.time()
            
            # ตรวจสอบเวลาสำหรับ Zone Analysis
            time_since_last_analysis = current_time - self.last_zone_analysis
            
            if time_since_last_analysis < self.zone_analysis_interval:
                return  # ไม่ต้อง log ทุกครั้ง
            
            self.last_zone_analysis = current_time
            logger.info(f"🎯 [SMART SYSTEMS] Starting analysis (interval: {self.zone_analysis_interval}s)")
            
            # ดึงราคาปัจจุบัน (อัปเดตใหม่ทุกครั้ง)
            current_price = self.mt5_connection.get_current_price(self.actual_symbol)
            if not current_price:
                logger.warning("❌ Cannot get current price - skipping")
                return
            
            logger.info(f"💰 [CURRENT PRICE] {self.actual_symbol}: {current_price:.5f}")
            
            # ตรวจสอบว่า Thread เก่าทำงานอยู่หรือไม่ (แก้ไข Thread Overlap)
            if self._smart_systems_thread and self._smart_systems_thread.is_alive():
                logger.debug("🎯 Smart Systems thread still running, skipping...")
                return
            
            # ย้าย Smart Systems ทั้งหมดไป Background Thread (รวม Zone Analysis)
            if hasattr(self, 'zone_analyzer') and self.zone_analyzer:
                try:
                    import threading
                    def smart_systems_worker():
                        try:
                            import time
                            start_time = time.time()
                            
                            # วิเคราะห์ Zones ใน background (ใช้ threading timeout แทน signal)
                            
                            import concurrent.futures
                            with concurrent.futures.ThreadPoolExecutor() as executor:
                                # ส่ง Zone Analysis ไปทำใน thread pool พร้อม timeout
                                future = executor.submit(self.zone_analyzer.analyze_zones, self.actual_symbol, 12)  # ลด lookback เป็น 12 ชั่วโมง
                                try:
                                    zones = future.result(timeout=15)  # ลด timeout เป็น 15 วินาที
                                    zone_time = time.time() - start_time
                                    logger.info(f"🎯 Zone Analysis: {len(zones.get('support', []))} support, {len(zones.get('resistance', []))} resistance ({zone_time:.1f}s)")
                                except concurrent.futures.TimeoutError:
                                    logger.warning("🎯 Zone analysis timeout (15s), skipping...")
                                    self._smart_systems_running = False  # Reset flag
                                    return
                                except Exception as e:
                                    logger.error(f"🎯 Zone analysis error: {e}")
                                    self._smart_systems_running = False  # Reset flag
                                    return
                            
                            if not zones or (not zones['support'] and not zones['resistance']):
                                logger.warning("🎯 NO ZONES FOUND FOR SMART SYSTEMS")
                                logger.warning("   📊 ระบบไม่พบ Support หรือ Resistance zones")
                                logger.warning("   🔧 ปรับแต่ง: ลด zone_tolerance หรือ min_zone_strength ใน Zone Analyzer")
                                return
                            
                            logger.info(f"🎯 Zone Analysis Complete: {len(zones['support'])} support, {len(zones['resistance'])} resistance zones")
                            logger.info(f"📊 Current Price: {current_price:.2f}")
                            
                            # Log current price vs zones
                            if zones['support']:
                                nearest_support = min(zones['support'], key=lambda x: abs(x['price'] - current_price))
                                logger.info(f"📈 Nearest Support: {nearest_support['price']:.2f} (Distance: {abs(current_price - nearest_support['price']):.2f})")
                            
                            if zones['resistance']:
                                nearest_resistance = min(zones['resistance'], key=lambda x: abs(x['price'] - current_price))
                                logger.info(f"📉 Nearest Resistance: {nearest_resistance['price']:.2f} (Distance: {abs(current_price - nearest_resistance['price']):.2f})")
                            
                            # ดึงข้อมูลพอร์ต
                            positions = self.mt5_connection.get_positions()
                            account_info = self.mt5_connection.get_account_info()
                            portfolio_profit = sum(getattr(pos, 'profit', 0) for pos in positions) if positions else 0
                            
                            # 1. Smart Entry System
                            entry_start = time.time()
                            if hasattr(self, 'smart_entry_system') and self.smart_entry_system:
                                try:
                                    # 🎯 SW Filter disabled - Using Edge Priority Closing instead
                                    sw_ok = True  # Always allow entry
                                    sw_reason = "SW Filter disabled - Using Edge Priority Closing"
                                    if sw_ok:
                                            # 1.1 ตรวจสอบโอกาสเข้าไม้ปกติ
                                            logger.info(f"🔍 [SMART ENTRY] Checking entry opportunity for {self.actual_symbol} at {current_price:.5f}")
                                            entry_opportunity = self.smart_entry_system.analyze_entry_opportunity(
                                                self.actual_symbol, current_price, zones, positions
                                            )
                                            if entry_opportunity:
                                                logger.info(f"🎯 Smart Entry Opportunity: {entry_opportunity['direction']} at {current_price}")
                                                logger.info(f"   Zone: {entry_opportunity['zone']['price']:.2f} (Strength: {entry_opportunity['zone']['strength']:.1f})")
                                                logger.info(f"   Lot Size: {entry_opportunity['lot_size']:.2f}")
                                                
                                                # เรียก execute_entry ด้วย entry_opportunity (ไม่ใช่ signal)
                                                ticket = self.smart_entry_system.execute_entry(entry_opportunity)
                                                if ticket:
                                                    logger.info(f"✅ Smart Entry executed: Ticket {ticket}")
                                                else:
                                                    logger.warning("❌ Smart Entry failed to execute")
                                            
                                            # 1.2 ตรวจสอบโอกาสแก้ไม้ (Recovery System)
                                            recovery_opportunities = self.smart_entry_system.find_recovery_opportunity(
                                                self.actual_symbol, current_price, zones, positions
                                            )
                                            if recovery_opportunities:
                                                logger.info(f"🚀 Recovery Opportunities Found: {len(recovery_opportunities)}")
                                                for i, recovery_opp in enumerate(recovery_opportunities[:2]):  # สร้างสูงสุด 2 ตัว
                                                    logger.info(f"   {i+1}. {recovery_opp['reason']}")
                                                    ticket = self.smart_entry_system.execute_entry(recovery_opp)
                                                    if ticket:
                                                        logger.info(f"✅ Recovery Entry executed: Ticket {ticket}")
                                            else:
                                                logger.debug("🚫 No recovery opportunities found")
                                    else:
                                        logger.warning(f"🚫 SW Filter blocked Smart Entry: {sw_reason}")
                                except Exception as e:
                                    logger.error(f"❌ Error in smart entry: {e}")
                            
                            entry_time = time.time() - entry_start
                            logger.debug(f"⏱️ Smart Entry processed in {entry_time:.2f}s")
                            
                            # 🚫 Portfolio Anchor System REMOVED - Using Edge Priority Closing only
                            logger.debug("🚫 Portfolio Anchor removed - Using Edge Priority Closing only")
                                    
                            # Log total processing time
                            total_time = time.time() - start_time
                            logger.info(f"🎯 Smart Systems completed in {total_time:.2f}s")
                            
                        except Exception as e:
                            logger.error(f"❌ Error in smart systems worker: {e}")
                        finally:
                            # Reset flag เสมอ ไม่ว่าจะสำเร็จหรือ error
                            self._smart_systems_running = False
                    
                    # เริ่ม thread และเก็บ reference
                    self._smart_systems_thread = threading.Thread(target=smart_systems_worker, daemon=True)
                    self._smart_systems_thread.start()
                    
                except Exception as e:
                    logger.error(f"❌ Error starting smart systems thread: {e}")
            
            # 🚫 Portfolio Anchor Management REMOVED - Using Edge Priority Closing only
            logger.debug("🚫 Portfolio Anchor management removed - Using Edge Priority Closing only")
            
        except Exception as e:
            logger.error(f"❌ Error in smart systems: {e}")
    
    def start_gui(self):
        """Start GUI (Same as original)"""
        try:
            self.gui = TradingGUI(self)
            self.gui.run()
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดใน GUI: {str(e)}")
    
    def shutdown(self):
        """Shutdown system (Same as original)"""
        try:
            logger.info("กำลังปิดระบบเทรด...")
            self.stop_trading()
            
            if self.mt5_connection:
                self.mt5_connection.disconnect_mt5()
                
            logger.info("✅ ปิดระบบเรียบร้อยแล้ว")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการปิดระบบ: {str(e)}")

    def update_zone_stats(self, zones: Dict[str, List[Dict]]):
        """📊 อัปเดตสถิติการหา zones"""
        try:
            current_time = time.time()
            if current_time - self.last_zone_update < 5:  # อัปเดตทุก 5 วินาที
                return
            
            # รีเซ็ตสถิติ
            for method in self.zone_stats:
                self.zone_stats[method]['support'] = 0
                self.zone_stats[method]['resistance'] = 0
            
            # นับ zones ตาม method
            for zone_type in ['support', 'resistance']:
                for zone in zones.get(zone_type, []):
                    algorithm = zone.get('algorithm', 'unknown')
                    if algorithm in self.zone_stats:
                        self.zone_stats[algorithm][zone_type] += 1
            
            self.last_zone_update = current_time
            
        except Exception as e:
            logger.error(f"❌ Error updating zone stats: {e}")
    
    def _should_update_status(self, current_candle: Dict, current_time: float) -> bool:
        """🚀 ตรวจสอบว่าควรอัพเดทสถานะหรือไม่"""
        try:
            if not self.status_tracker or not self.status_manager:
                return False
            
            # ดึงราคาปัจจุบัน
            current_price = current_candle.get('close', 0.0)
            if current_price == 0:
                return False
            
            # ตรวจสอบการเปลี่ยนแปลงราคา
            price_change = abs(current_price - self.status_tracker['last_price'])
            price_change_pips = price_change * 10000  # แปลงเป็น pips
            
            # ตรวจสอบเวลาที่ผ่านไป
            time_passed = current_time - self.status_tracker['last_update']
            
            # อัพเดทเมื่อ: ราคาเปลี่ยน > 5 pips หรือ เวลาผ่าน > 3 วินาที
            should_update = (
                price_change_pips >= self.status_tracker['price_change_threshold'] or
                time_passed >= self.status_tracker['update_threshold']
            )
            
            if should_update:
                logger.debug(f"🔄 [STATUS UPDATE] Price change: {price_change_pips:.1f} pips, "
                           f"Time passed: {time_passed:.1f}s")
            
            return should_update
            
        except Exception as e:
            logger.error(f"❌ Error checking status update: {e}")
            return False
    
    def _update_position_status_realtime(self, current_candle: Dict, current_time: float):
        """🚀 อัพเดทสถานะไม้แบบ Real-time"""
        try:
            if not self.status_manager or not self.market_detector:
                return
            
            # ดึงราคาปัจจุบัน
            current_price = current_candle.get('close', 0.0)
            if current_price == 0:
                return
            
            # อัพเดทข้อมูลตลาด
            volume = current_candle.get('volume', 0.0)
            self.market_detector.update_price_data(current_price, volume, current_time)
            
            # ดึงสภาวะตลาดปัจจุบัน
            market_condition = self.market_detector.get_current_condition()
            
            # ดึง Position ทั้งหมด
            positions = self.order_manager.get_positions()
            if not positions:
                return
            
            # ดึง Zone ข้อมูล (ถ้ามี)
            zones = []
            if hasattr(self, 'zone_analyzer') and self.zone_analyzer:
                try:
                    zones = self.zone_analyzer.get_zones()
                except:
                    zones = []
            
            # วิเคราะห์สถานะไม้
            status_results = self.status_manager.analyze_all_positions(
                positions=positions,
                current_price=current_price,
                zones=zones,
                market_condition=market_condition.condition
            )
            
            # อัพเดท Status Tracker
            self.status_tracker['last_price'] = current_price
            self.status_tracker['last_update'] = current_time
            
            # Log สถานะพิเศษ
            self._log_special_statuses(status_results)
            
            # อัพเดท GUI (ถ้ามี)
            if hasattr(self, 'gui') and self.gui:
                self._update_gui_with_status(status_results)
            
        except Exception as e:
            logger.error(f"❌ Error updating position status: {e}")
    
    def _log_special_statuses(self, status_results: Dict[int, Any]):
        """📝 Log สถานะพิเศษ"""
        try:
            special_count = 0
            for ticket, status_obj in status_results.items():
                if 'HG' in status_obj.status or 'Support Guard' in status_obj.status:
                    special_count += 1
                    if special_count <= 3:  # Log เฉพาะ 3 ไม้แรก
                        logger.info(f"🎯 [SPECIAL STATUS] #{ticket}: {status_obj.status}")
            
            if special_count > 3:
                logger.info(f"🎯 [SPECIAL STATUS] ... และอีก {special_count - 3} ไม้")
                
        except Exception as e:
            logger.error(f"❌ Error logging special statuses: {e}")
    
    def _update_gui_with_status(self, status_results: Dict[int, Any]):
        """🖥️ อัพเดท GUI ด้วยสถานะ"""
        try:
            if not hasattr(self.gui, 'update_position_status'):
                return
            
            # ส่งข้อมูลสถานะไปยัง GUI
            self.gui.update_position_status(status_results)
            
        except Exception as e:
            logger.error(f"❌ Error updating GUI with status: {e}")
    
    def get_current_position_status(self) -> Dict[int, Any]:
        """📊 ดึงสถานะไม้ปัจจุบัน"""
        try:
            if not self.status_manager:
                return {}
            
            return self.status_manager.get_all_statuses()
            
        except Exception as e:
            logger.error(f"❌ Error getting current position status: {e}")
            return {}
    
    def get_system_status(self) -> Dict[str, Any]:
        """📊 ข้อมูลสถานะระบบสำหรับ GUI"""
        try:
            status = {
                'market_condition': self.market_condition.upper(),
                'zone_analysis_interval': f"{self.zone_analysis_interval}s",
                'smart_systems_enabled': self.smart_systems_enabled,
                'zone_stats': self.zone_stats.copy(),
                'total_support_zones': sum(stats['support'] for stats in self.zone_stats.values()),
                'total_resistance_zones': sum(stats['resistance'] for stats in self.zone_stats.values()),
                'timeframes': self.timeframes,
                'adaptive_mode': getattr(self.zone_analyzer, 'enable_adaptive_mode', False) if self.zone_analyzer else False
            }
            return status
            
        except Exception as e:
            logger.error(f"❌ Error getting system status: {e}")
            return {}

def main():
    """Main function"""
    # Create trading system
    system = AdaptiveTradingSystemGUI(initial_balance=10000.0, symbol="XAUUSD")
    
    try:
        # Initialize system
        if system.initialize_system():
            # Start GUI
            system.start_gui()
        else:
            logger.error("❌ Failed to initialize system")
            
    except KeyboardInterrupt:
        logger.info("🛑 Stopping system...")
        system.shutdown()
    except Exception as e:
        logger.error(f"❌ System error: {e}")
        system.shutdown()

if __name__ == "__main__":
    main()
