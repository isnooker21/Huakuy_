# -*- coding: utf-8 -*-
"""
🚀 Simple Breakout Trading System with GUI
==========================================
#85726dba89c0b032198ead4b3d0b292f01d7a23d <<< commit file ที่ใช้งานสมบูณ
NEW ENTRY LOGIC:
✅ BUY: current.close > previous.high
✅ SELL: current.close < previous.low
✅ Multi-Timeframe: M5, M15, M30, H1
✅ One Trade Per Candle Per TF
✅ Support/Resistance Override
✅ Dynamic Lot Sizing
✅ Keep Original GUI

AUTHOR: Advanced Trading System
VERSION: 2.0.0
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

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

# 🚀 SIMPLE & CLEAN LOGGING CONFIGURATION
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('simple_breakout_gui.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 🚀 NEW SYSTEM LOGGING - Clean & Simple
logging.getLogger('mt5_connection').setLevel(logging.WARNING)
logging.getLogger('order_management').setLevel(logging.INFO)
logging.getLogger('dynamic_position_modifier').setLevel(logging.INFO)
# 🚫 REMOVED: dynamic_adaptive_closer logging - Replaced by Enhanced 7D Smart Closer
logging.getLogger('calculations').setLevel(logging.ERROR)

logger = logging.getLogger(__name__)

class SimpleBreakoutTradingSystemGUI:
    """
    🚀 Simple Breakout Trading System with GUI
    
    FEATURES:
    ✅ Original GUI Interface
    ✅ Simple Breakout Entry Logic
    ✅ Multi-Timeframe Support
    ✅ Dynamic Lot Sizing
    ✅ Support/Resistance Override
    ✅ Position Management Systems
    """
    
    def __init__(self, initial_balance: float = 10000.0, symbol: str = "XAUUSD"):
        """Initialize Simple Breakout Trading System with GUI"""
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
        # 🚫 REMOVED: dynamic_adaptive_closer - Replaced by Enhanced 7D Smart Closer
        self.hedge_pairing_closer = None
        
        # 🎯 SIMPLE BREAKOUT STATE
        self.last_candle_data = {}  # {timeframe: candle}
        self.timeframes = ['M5', 'M15', 'M30', 'H1']
        self.last_trade_time = {}  # {timeframe: timestamp}
        
        # Initialize last trade times
        for tf in self.timeframes:
            self.last_trade_time[tf] = None
        
        # 🎯 Trading State (Same as original)
        self.is_running = False
        self.trading_thread = None
        self.last_candle_time = None
        
        # ข้อมูลตลาด
        self.current_prices = {}
        self.volume_history = []
        self.price_history = []
        
        # GUI
        self.gui = None
        
        # 🛡️ RANGE-BOUND MARKET PROTECTION (DISABLED - FIGHT MODE!)
        self.price_range_history = []  # เก็บราคา high/low ล่าสุด
        self.range_check_period = 10   # ลดเป็น 10 candles (เร็วสุด)
        self.max_range_points = 50     # ลดเป็น 50 จุด (ต้องติดมากจริงๆ)
        self.min_positions_for_range_check = 20  # เพิ่มเป็น 20 positions (ปิดแทบจะปิด)
        
        logger.info(f"🛡️ Range-bound Protection: Max Range: {self.max_range_points} points, Min Positions: {self.min_positions_for_range_check}")
        
        # 🔒 Position Locking
        self.closing_positions = set()
        self.closing_lock = threading.Lock()
        
        # ⏰ Closing Cooldown
        self.last_closing_time = None
        self.closing_cooldown_seconds = 30
        
        logger.info("🚀 SIMPLE BREAKOUT TRADING SYSTEM WITH GUI initialized")
        logger.info(f"💰 Initial Balance: ${initial_balance:,.2f}")
        logger.info(f"📊 Target Symbol: {symbol}")
        logger.info(f"⏰ Monitoring Timeframes: {self.timeframes}")
    
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
            logger.info(f"พบ Position ที่เปิดอยู่: {len(positions)} ตัว")
            
            # โหลดข้อมูลราคาเริ่มต้น
            self.load_initial_market_data()
            
            # ✅ Initialize Position Management Systems (Keep from original)
            logger.info("✅ Initializing Position Management Systems...")
            
            self.dynamic_position_modifier = create_dynamic_position_modifier(
                mt5_connection=self.mt5_connection,
                symbol=self.actual_symbol,
                hedge_pairing_closer=self.hedge_pairing_closer,
                initial_balance=self.initial_balance
            )
            
            # 🚫 REMOVED: dynamic_adaptive_closer initialization - Replaced by Enhanced 7D Smart Closer
            
            logger.info("✅ SIMPLE BREAKOUT SYSTEM WITH GUI ready!")
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
                logger.info(f"โหลดราคาปัจจุบัน: {current_price}")
            
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
                logger.info(f"โหลดข้อมูลเทียน: {len(candles)} แท่ง")
                
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการโหลดข้อมูลตลาด: {str(e)}")
    
    def start_trading(self):
        """Start trading loop (Same as original structure)"""
        try:
            if self.is_running:
                logger.warning("ระบบเทรดกำลังทำงานอยู่แล้ว")
                return True
            
            # 🚀 Initialize Hedge Pairing Closer
            try:
                from hedge_pairing_closer import create_hedge_pairing_closer
                self.hedge_pairing_closer = create_hedge_pairing_closer(symbol=self.actual_symbol)
                # ตั้งค่า MT5 connection สำหรับ Real-time P&L
                if self.mt5_connection:
                    self.hedge_pairing_closer.set_mt5_connection(self.mt5_connection)
                logger.info("🚀 Hedge Pairing Closer initialized successfully")
            except Exception as e:
                logger.error(f"❌ Failed to initialize Hedge Pairing Closer: {e}")
                self.hedge_pairing_closer = None
            
            self.is_running = True
            self.trading_thread = threading.Thread(target=self._trading_loop, daemon=True)
            self.trading_thread.start()
            
            logger.info("🚀 เริ่มระบบเทรดแล้ว")
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
        if self.trading_thread:
            self.trading_thread.join(timeout=5)
        
        logger.info("🛑 หยุดระบบเทรดแล้ว")
    
    def _trading_loop(self):
        """Main trading loop with Simple Breakout Logic"""
        logger.info("🔄 เริ่มลูปเทรด")
        
        while self.is_running:
            try:
                # ตรวจสอบการรอปิดแท่ง
                if hasattr(self, 'hedge_pairing_closer') and self.hedge_pairing_closer:
                    if self.hedge_pairing_closer._should_wait_for_bar_close('M5'):
                        time.sleep(1)
                        continue
                    
                    # ตรวจสอบการปิดกำไรเร่งด่วน (เร็วขึ้น) - เอาออกเพราะซ้ำซ้อนกับ Close All
                    # if hasattr(self, 'order_manager') and self.order_manager.active_positions:
                    #     total_profit = sum(getattr(pos, 'profit', 0) for pos in self.order_manager.active_positions)
                    #     if total_profit >= 50.0:  # กำไรเร่งด่วน $50
                    #         logger.info(f"🚨 URGENT: Total profit ${total_profit:.2f} - Closing all positions immediately")
                    #         # ปิดไม้ทั้งหมดทันที
                    #         self._handle_dynamic_closing(current_candle)
                    #         time.sleep(1)
                    #         continue
                
                # Get current candle data
                current_candle = self._get_current_candle()
                if not current_candle:
                    time.sleep(1)
                    continue
                
                # 🕐 Log market status (every 5 minutes)
                if not hasattr(self, '_last_market_status_log'):
                    self._last_market_status_log = 0
                
                current_time = time.time()
                if current_time - self._last_market_status_log >= 300:  # 5 minutes
                    self.mt5_connection.log_market_status(self.actual_symbol or "XAUUSD")
                    self._last_market_status_log = current_time
                
                # Process Simple Breakout for all timeframes (ตรวจสอบ Bar Close ก่อน)
                if hasattr(self, 'hedge_pairing_closer') and self.hedge_pairing_closer:
                    if not self.hedge_pairing_closer._should_wait_for_bar_close('M5'):
                        self._process_simple_breakout(current_candle)
                    # else:
                        # logger.info("⏰ Waiting for bar close before opening new positions...")
                else:
                    self._process_simple_breakout(current_candle)
                
                # Position Management (Keep original logic) - Throttle to every 5 seconds
                if not hasattr(self, '_last_position_management_time'):
                    self._last_position_management_time = 0
                
                if current_time - self._last_position_management_time >= 10:  # Every 10 seconds
                    self._handle_position_management(current_candle)
                    self._last_position_management_time = current_time
                
                # Dynamic Closing (Keep original logic) - Throttle to every 8 seconds
                if not hasattr(self, '_last_dynamic_closing_time'):
                    self._last_dynamic_closing_time = 0
                
                if current_time - self._last_dynamic_closing_time >= 8:  # Every 8 seconds
                    self._handle_dynamic_closing(current_candle)
                    self._last_dynamic_closing_time = current_time
                
                # Sleep
                time.sleep(2)  # Increase sleep time
                
            except Exception as e:
                logger.error(f"❌ เกิดข้อผิดพลาดในลูปเทรด: {e}")
                time.sleep(5)
        
        logger.info("🔄 จบลูปเทรด")
    
    def _get_current_candle(self) -> Optional[CandleData]:
        """Get current candle data"""
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
    
    def _process_simple_breakout(self, current_candle: CandleData):
        """
        🚀 NEW SIMPLE BREAKOUT LOGIC
        
        LOGIC:
        ✅ BUY: current.close > previous.high
        ✅ SELL: current.close < previous.low
        ✅ One trade per candle per timeframe
        ✅ Dynamic lot sizing
        """
        try:
            # ตรวจสอบการรอปิดแท่งก่อนออกไม้ใหม่
            if hasattr(self, 'hedge_pairing_closer') and self.hedge_pairing_closer:
                if self.hedge_pairing_closer._should_wait_for_bar_close('M5'):
                    logger.info("⏰ Waiting for bar close before opening new positions...")
                    return
            
            current_price = current_candle.close
            
            # Process each timeframe
            for timeframe in self.timeframes:
                # Check if we can trade this timeframe (one per candle rule) - สอดคล้องกับ Bar Close
                if not self._can_trade_timeframe(timeframe):
                    logger.debug(f"⏰ Cannot trade {timeframe} - waiting for bar close or time interval")
                    continue
                
                # Get previous candle for this timeframe
                previous_candle = self._get_previous_candle(timeframe)
                if not previous_candle:
                    continue
                
                # 🎯 SIMPLE BREAKOUT DETECTION
                breakout_signal = None
                
                if current_candle.close > previous_candle.high:
                    # 🟢 BUY Breakout
                    breakout_signal = "BUY"
                    reason = f"Breakout BUY: {current_candle.close:.2f} > {previous_candle.high:.2f}"
                    
                elif current_candle.close < previous_candle.low:
                    # 🔴 SELL Breakout
                    breakout_signal = "SELL"
                    reason = f"Breakout SELL: {current_candle.close:.2f} < {previous_candle.low:.2f}"
                
                if breakout_signal:
                    # 🛡️ Range-bound protection (DISABLED - FIGHT MODE!)
                    # if self._is_range_bound_market():
                    #     logger.warning(f"⏸️ BREAKOUT SKIPPED: Range-bound market detected for {timeframe}")
                    #     logger.warning(f"   Current positions: {len(self.order_manager.active_positions)}")
                    #     continue
                    # else:
                    logger.debug(f"✅ Market OK for trading: {timeframe} - FIGHT MODE ACTIVE!")
                    
                    # 🚀 Execute breakout trade
                    self._execute_simple_breakout_trade(
                        direction=breakout_signal,
                        timeframe=timeframe,
                        current_candle=current_candle,
                        reason=reason
                    )
            
            # Update candle history
            self._update_candle_history(current_candle)
            
        except Exception as e:
            logger.error(f"❌ Error in simple breakout processing: {e}")
    
    def _can_trade_timeframe(self, timeframe: str) -> bool:
        """Check if we can trade this timeframe (one trade per candle rule) - สอดคล้องกับ Bar Close"""
        last_trade = self.last_trade_time.get(timeframe)
        if last_trade is None:
            return True
        
        # ใช้เวลาเดียวกันกับ Bar Close System
        current_time = datetime.now()
        
        # Simple time-based check (adjust based on timeframe)
        time_intervals = {
            'M5': 300,   # 5 minutes
            'M15': 900,  # 15 minutes  
            'M30': 1800, # 30 minutes
            'H1': 3600   # 1 hour
        }
        
        interval = time_intervals.get(timeframe, 60)
        time_diff = (current_time - last_trade).total_seconds()
        
        # ตรวจสอบว่าแท่งปิดแล้วหรือยัง (สอดคล้องกับ Bar Close) - แยกตาม TF
        if hasattr(self, 'hedge_pairing_closer') and self.hedge_pairing_closer:
            if self.hedge_pairing_closer._should_wait_for_bar_close(timeframe):
                return False  # รอปิดแท่ง
        
        return time_diff > interval
    
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
            
            return CandleData(
                open=prev_candle.get('open', 0),
                high=prev_candle.get('high', 0),
                low=prev_candle.get('low', 0),
                close=prev_candle.get('close', 0),
                volume=prev_candle.get('volume', 100),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"❌ Error getting previous candle for {timeframe}: {e}")
            return None
    
    def _execute_simple_breakout_trade(self, direction: str, timeframe: str, 
                                     current_candle: CandleData, reason: str):
        """Execute simple breakout trade"""
        try:
            # ตรวจสอบการรอปิดแท่งก่อนออกไม้ใหม่
            if hasattr(self, 'hedge_pairing_closer') and self.hedge_pairing_closer:
                if self.hedge_pairing_closer._should_wait_for_bar_close('M5'):
                    logger.info("⏰ Waiting for bar close before opening new positions...")
                    return
            
            # ตรวจสอบ SW Filter ก่อนออกไม้ใหม่
            if hasattr(self, 'hedge_pairing_closer') and self.hedge_pairing_closer:
                # สร้าง mock position สำหรับตรวจสอบ SW Filter
                mock_position = type('MockPosition', (), {
                    'price': current_candle.close,
                    'price_open': current_candle.close,
                    'type': 0 if direction == 'BUY' else 1,
                    'volume': 0.01
                })()
                
                # ตรวจสอบ SW Filter
                existing_positions = self.order_manager.active_positions
                sw_ok, sw_msg = self.hedge_pairing_closer._sw_filter_check(mock_position, existing_positions)
                
                if not sw_ok:
                    logger.info(f"🚫 SW FILTER: {sw_msg}")
                    return
            
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
                # Update last trade time
                self.last_trade_time[timeframe] = datetime.now()
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
        """Update candle history"""
        for tf in self.timeframes:
            self.last_candle_data[tf] = candle
        
        # 🛡️ Update price range history for range-bound detection
        self._update_price_range_history(candle)
    
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
    
    def _handle_dynamic_closing(self, candle: CandleData):
        """Handle dynamic closing using Hedge Pairing Closer"""
        try:
            if not self.hedge_pairing_closer:
                return
            
            # 🕐 Check market status before closing
            market_status = self.mt5_connection.get_market_status(self.actual_symbol or "XAUUSD")
            if not market_status.get('is_market_open', False):
                logger.debug(f"💤 Market is closed - skipping closing analysis")
                return
            
            account_info = self.mt5_connection.get_account_info()
            
            # 🔄 ซิงค์ข้อมูล Position จาก MT5 ก่อนวิเคราะห์
            positions = self.order_manager.sync_positions_from_mt5()
            
            if not positions:
                return
            
            # 🚀 Use Hedge Pairing Closer for comprehensive analysis
            market_conditions = {
                'current_price': candle.close,
                'volatility': 'medium',  # Could be enhanced with real volatility calculation
                'trend': 'neutral',      # Could be enhanced with real trend analysis
                'market_open': market_status.get('is_market_open', False),
                'active_sessions': market_status.get('active_sessions', []),
                'london_ny_overlap': market_status.get('london_ny_overlap', False)
            }
            
            closing_result = self.hedge_pairing_closer.find_optimal_closing(
                positions=positions,
                account_info=account_info or {},
                market_conditions=market_conditions
            )
            
            if closing_result and closing_result.should_close:
                logger.info(f"🚀 HEDGE CLOSING RECOMMENDED: {len(closing_result.positions_to_close)} positions")
                logger.info(f"   Net P&L: ${closing_result.net_pnl:.2f}, Confidence: {closing_result.confidence_score:.1f}%")
                logger.info(f"   Method: {closing_result.method}")
                logger.info(f"   Reason: {closing_result.reason}")
                
                # Execute closing
                result = self.order_manager.close_positions_group(closing_result.positions_to_close)
                if result:
                    logger.info(f"✅ HEDGE GROUP CLOSED successfully")
                else:
                    logger.warning(f"❌ HEDGE GROUP CLOSE FAILED")
            else:
                logger.debug(f"💤 HEDGE No closing recommended - waiting for better opportunity")
                            
        except Exception as e:
            logger.error(f"❌ Error in Hedge dynamic closing: {e}")
    
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

def main():
    """Main function"""
    # Create trading system
    system = SimpleBreakoutTradingSystemGUI(initial_balance=10000.0, symbol="XAUUSD")
    
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
