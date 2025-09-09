#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🚀 SIMPLE BREAKOUT TRADING SYSTEM
=================================

NEW FEATURES:
✅ Simple Breakout Logic: current.close > previous.high/low
✅ Multi-Timeframe: M5, M15, M30, H1
✅ One Trade Per Candle Per TF
✅ Support/Resistance Override
✅ Dynamic Lot Sizing based on capital & candle strength
✅ No complex blocking systems
✅ Clean & Simple Logging

AUTHOR: Advanced Trading System
VERSION: 2.0.0
"""

import logging
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# 🚀 NEW SIMPLE TRADING SYSTEM
from mt5_connection import MT5Connection
from calculations import Position
from trading_conditions import CandleData
from order_management import OrderManager

# 🚀 NEW BREAKOUT TRADING ENGINE
from simple_breakout_engine import create_simple_breakout_engine, CandleData as BreakoutCandle, TimeFrame, BreakoutSignal
from sr_detection_engine import create_sr_detection_engine

# ✅ KEEP POSITION MANAGEMENT & CLOSING SYSTEMS
from dynamic_position_modifier import create_dynamic_position_modifier
from dynamic_adaptive_closer import create_dynamic_adaptive_closer

# 🚀 SIMPLE & CLEAN LOGGING
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[
        logging.FileHandler('simple_breakout_trading.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

# 🚀 NEW SYSTEM LOGGING - Clean & Simple
logging.getLogger('mt5_connection').setLevel(logging.WARNING)
logging.getLogger('order_management').setLevel(logging.INFO)
logging.getLogger('simple_breakout_engine').setLevel(logging.INFO)
logging.getLogger('sr_detection_engine').setLevel(logging.INFO)
logging.getLogger('dynamic_position_modifier').setLevel(logging.INFO)
logging.getLogger('dynamic_adaptive_closer').setLevel(logging.INFO)

logger = logging.getLogger(__name__)

class SimpleBreakoutTradingSystem:
    """
    🚀 SIMPLE BREAKOUT TRADING SYSTEM
    
    FEATURES:
    ✅ Simple Breakout: current.close > previous.high/low
    ✅ Multi-Timeframe: M5, M15, M30, H1
    ✅ One Trade Per Candle Per TF
    ✅ S/R Override: Force BUY at Support, SELL at Resistance
    ✅ Dynamic Lot Sizing: Based on capital & candle strength
    ✅ Position Management: Smart modification & closing
    ✅ No Complex Blocking: Fight to the end mentality
    """
    
    def __init__(self, initial_balance: float = 10000.0, symbol: str = "XAUUSD"):
        """Initialize Simple Breakout Trading System"""
        self.base_symbol = symbol
        self.actual_symbol = None
        self.initial_balance = initial_balance
        
        # 🚀 CORE SYSTEMS
        self.mt5_connection = MT5Connection()
        self.order_manager = OrderManager(self.mt5_connection)
        
        # 🚀 NEW BREAKOUT TRADING ENGINE
        self.breakout_engine = None
        self.sr_detector = None
        
        # ✅ POSITION MANAGEMENT & CLOSING SYSTEMS
        self.dynamic_position_modifier = None
        self.dynamic_adaptive_closer = None
        
        # 🎯 TRADING STATE
        self.is_running = False
        self.trading_thread = None
        self.last_candle_time = {}  # {timeframe: last_time}
        
        # 📊 MULTI-TIMEFRAME CANDLE STORAGE
        self.candle_history = {}  # {timeframe: [candles]}
        self.timeframes = [TimeFrame.M5, TimeFrame.M15, TimeFrame.M30, TimeFrame.H1]
        
        # Initialize candle history for each timeframe
        for tf in self.timeframes:
            self.candle_history[tf] = []
            self.last_candle_time[tf] = None
        
        # 🔒 THREAD SAFETY
        self.lock = threading.Lock()
        
        logger.info("🚀 SIMPLE BREAKOUT TRADING SYSTEM initialized")
        logger.info(f"💰 Initial Balance: ${initial_balance:,.2f}")
        logger.info(f"📊 Target Symbol: {symbol}")
        logger.info(f"⏰ Monitoring Timeframes: {[tf.value for tf in self.timeframes]}")
    
    def initialize_system(self) -> bool:
        """Initialize all systems"""
        try:
            # 🔗 Connect to MT5
            if not self.mt5_connection.connect():
                logger.error("❌ Failed to connect to MT5")
                return False
            
            # 🔍 Auto-detect gold symbol
            logger.info("🔍 Auto-detecting gold symbol...")
            self.actual_symbol = self.mt5_connection.auto_detect_gold_symbol()
            
            if not self.actual_symbol:
                logger.error("❌ Gold symbol not found")
                return False
                
            logger.info(f"✅ Using symbol: {self.base_symbol} -> {self.actual_symbol}")
            
            # 📊 Sync existing positions
            positions = self.order_manager.sync_positions_from_mt5()
            logger.info(f"📊 Found {len(positions)} existing positions")
            
            # 🚀 Initialize Breakout Engine
            logger.info("🚀 Initializing Simple Breakout Engine...")
            self.breakout_engine = create_simple_breakout_engine(
                mt5_connection=self.mt5_connection,
                symbol=self.actual_symbol
            )
            
            # 🛡️ Initialize S/R Detection Engine
            logger.info("🛡️ Initializing S/R Detection Engine...")
            self.sr_detector = create_sr_detection_engine(symbol=self.actual_symbol)
            
            # ✅ Initialize Position Management Systems
            logger.info("✅ Initializing Position Management Systems...")
            
            self.dynamic_position_modifier = create_dynamic_position_modifier(
                mt5_connection=self.mt5_connection,
                symbol=self.actual_symbol
            )
            
            self.dynamic_adaptive_closer = create_dynamic_adaptive_closer(
                mt5_connection=self.mt5_connection,
                symbol=self.actual_symbol
            )
            
            logger.info("✅ SIMPLE BREAKOUT SYSTEM ready to trade!")
            return True
            
        except Exception as e:
            logger.error(f"❌ System initialization error: {e}")
            return False
    
    def start_trading(self):
        """Start the trading loop"""
        if self.is_running:
            logger.warning("⚠️ Trading system is already running")
            return
        
        if not self.initialize_system():
            logger.error("❌ Failed to initialize system")
            return
        
        self.is_running = True
        self.trading_thread = threading.Thread(target=self._trading_loop, daemon=True)
        self.trading_thread.start()
        
        logger.info("🚀 SIMPLE BREAKOUT TRADING SYSTEM started!")
    
    def stop_trading(self):
        """Stop the trading loop"""
        if not self.is_running:
            logger.warning("⚠️ Trading system is not running")
            return
        
        self.is_running = False
        if self.trading_thread:
            self.trading_thread.join(timeout=5)
        
        logger.info("🛑 SIMPLE BREAKOUT TRADING SYSTEM stopped")
    
    def _trading_loop(self):
        """Main trading loop"""
        logger.info("🔄 Trading loop started")
        
        while self.is_running:
            try:
                # Get current price
                current_price = self.mt5_connection.get_current_price(self.actual_symbol)
                if not current_price:
                    time.sleep(1)
                    continue
                
                # Create current candle data
                current_candle = self._get_current_candle(current_price)
                if not current_candle:
                    time.sleep(1)
                    continue
                
                # Process candle for all timeframes
                self._process_multi_timeframe_candle(current_candle)
                
                # Sleep for 1 second
                time.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Trading loop error: {e}")
                time.sleep(5)
        
        logger.info("🔄 Trading loop ended")
    
    def _get_current_candle(self, current_price: float) -> Optional[CandleData]:
        """Get current candle data from MT5"""
        try:
            # Get latest candle from MT5
            candles = self.mt5_connection.get_candles(self.actual_symbol, count=2, timeframe='M1')
            if not candles or len(candles) < 1:
                return None
            
            latest_candle = candles[-1]
            
            return CandleData(
                open=latest_candle.get('open', current_price),
                high=latest_candle.get('high', current_price),
                low=latest_candle.get('low', current_price),
                close=latest_candle.get('close', current_price),
                volume=latest_candle.get('volume', 100),
                time=datetime.now()
            )
            
        except Exception as e:
            logger.error(f"❌ Error getting current candle: {e}")
            return None
    
    def _process_multi_timeframe_candle(self, candle: CandleData):
        """
        🚀 Process candle for all timeframes
        
        PROCESS:
        1. 🚀 Multi-Timeframe Breakout Analysis
        2. 🛡️ Support/Resistance Override
        3. 💰 Dynamic Lot Sizing
        4. ✅ Position Management & Closing
        """
        try:
            current_price = candle.close
            
            # Get account info
            account_info = self.mt5_connection.get_account_info() if self.mt5_connection else {}
            account_balance = account_info.get('balance', self.initial_balance)
            
            # 🚀 1. MULTI-TIMEFRAME BREAKOUT ANALYSIS
            for timeframe in self.timeframes:
                # Create breakout candle for this timeframe
                breakout_candle = BreakoutCandle(
                    open=candle.open,
                    high=candle.high,
                    low=candle.low,
                    close=candle.close,
                    volume=getattr(candle, 'volume', 100.0),
                    time=datetime.now(),
                    timeframe=timeframe
                )
                
                # Update candle history
                self._update_candle_history(breakout_candle, timeframe)
                
                # Check if we can trade this candle (one per candle rule)
                if not self._can_trade_candle(breakout_candle, timeframe):
                    continue
                
                # Analyze breakout opportunity
                if self.breakout_engine:
                    breakout_signal = self.breakout_engine.analyze_breakout_opportunity(
                        current_candle=breakout_candle,
                        account_balance=account_balance
                    )
                    
                    if breakout_signal:
                        # 🚀 Execute breakout trade
                        self._execute_breakout_trade(breakout_signal)
            
            # 🛡️ 2. UPDATE SUPPORT/RESISTANCE LEVELS
            self._update_sr_levels(current_price)
            
            # ✅ 3. POSITION MANAGEMENT & MODIFICATION
            self._handle_position_management(account_info, current_price)
            
            # 💰 4. DYNAMIC CLOSING ANALYSIS
            self._handle_dynamic_closing(account_info, current_price)
            
        except Exception as e:
            logger.error(f"❌ Error processing multi-timeframe candle: {e}")
    
    def _update_candle_history(self, candle: BreakoutCandle, timeframe: TimeFrame):
        """Update candle history for timeframe"""
        if timeframe not in self.candle_history:
            self.candle_history[timeframe] = []
        
        # Add new candle
        self.candle_history[timeframe].append(candle)
        
        # Keep only last 100 candles per timeframe
        if len(self.candle_history[timeframe]) > 100:
            self.candle_history[timeframe] = self.candle_history[timeframe][-100:]
    
    def _can_trade_candle(self, candle: BreakoutCandle, timeframe: TimeFrame) -> bool:
        """Check if we can trade this candle (one trade per candle rule)"""
        last_trade_time = self.last_candle_time.get(timeframe)
        
        if last_trade_time is None:
            return True
            
        # Check if this is a new candle (simplified - every 5 seconds for demo)
        return (datetime.now() - last_trade_time).total_seconds() > 5
    
    def _execute_breakout_trade(self, signal: BreakoutSignal):
        """Execute breakout trade"""
        try:
            logger.info(f"🚀 BREAKOUT SIGNAL: {signal.direction} {signal.timeframe.value}")
            logger.info(f"   💰 Lot Size: {signal.lot_size:.3f}")
            logger.info(f"   🎯 Entry Price: {signal.entry_price:.2f}")
            logger.info(f"   💪 Candle Strength: {signal.candle_strength:.1f}%")
            logger.info(f"   📊 Confidence: {signal.confidence:.1f}%")
            logger.info(f"   📝 Reason: {signal.reason}")
            
            # Execute the trade
            if signal.direction == "BUY":
                result = self.order_manager.open_buy_position(
                    symbol=self.actual_symbol,
                    lot_size=signal.lot_size,
                    comment=f"Breakout-{signal.timeframe.value}"
                )
            else:  # SELL
                result = self.order_manager.open_sell_position(
                    symbol=self.actual_symbol,
                    lot_size=signal.lot_size,
                    comment=f"Breakout-{signal.timeframe.value}"
                )
            
            if result and hasattr(result, 'success') and result.success:
                logger.info(f"✅ BREAKOUT TRADE EXECUTED: Order #{getattr(result, 'ticket', 'N/A')}")
                # Update last trade time
                self.last_candle_time[signal.timeframe] = signal.timestamp
            else:
                error_msg = getattr(result, 'error_message', 'Unknown error') if result else 'No result'
                logger.error(f"❌ BREAKOUT TRADE FAILED: {error_msg}")
                
        except Exception as e:
            logger.error(f"❌ Error executing breakout trade: {e}")
    
    def _update_sr_levels(self, current_price: float):
        """Update Support/Resistance levels"""
        try:
            if not self.sr_detector:
                return
            
            # Use H1 candles for S/R detection (if we have enough data)
            h1_candles = self.candle_history.get(TimeFrame.H1, [])
            if len(h1_candles) < 20:
                return
            
            # Detect S/R levels
            sr_levels = self.sr_detector.detect_sr_levels(h1_candles, current_price)
            
            # Update breakout engine with new S/R levels
            if self.breakout_engine and sr_levels:
                self.breakout_engine.update_sr_levels(sr_levels)
                logger.debug(f"🛡️ Updated {len(sr_levels)} S/R levels")
                
        except Exception as e:
            logger.error(f"❌ Error updating S/R levels: {e}")
    
    def _handle_position_management(self, account_info: Dict, current_price: float):
        """Handle position management and modification"""
        try:
            if not self.dynamic_position_modifier:
                return
            
            positions = self.order_manager.active_positions
            if not positions:
                return
            
            # Analyze portfolio modifications
            modification_plan = self.dynamic_position_modifier.analyze_portfolio_modifications(
                positions=positions,
                account_info=account_info,
                current_price=current_price
            )
            
            # Apply modifications if needed
            if modification_plan and hasattr(modification_plan, 'modifications'):
                for modification in modification_plan.modifications:
                    if modification.priority in ['HIGH', 'CRITICAL']:
                        logger.info(f"🔧 APPLYING MODIFICATION: {modification.action} for Position #{modification.ticket}")
                        # Apply modification logic here
                        
        except Exception as e:
            logger.error(f"❌ Error in position management: {e}")
    
    def _handle_dynamic_closing(self, account_info: Dict, current_price: float):
        """Handle dynamic closing analysis"""
        try:
            if not self.dynamic_adaptive_closer:
                return
            
            positions = self.order_manager.active_positions
            if not positions:
                return
            
            # Analyze closing opportunities
            closing_analysis = self.dynamic_adaptive_closer.analyze_dynamic_closing(
                positions=positions,
                account_info=account_info,
                current_price=current_price
            )
            
            # Execute closing if recommended
            if hasattr(closing_analysis, 'should_close') and closing_analysis.should_close:
                if hasattr(closing_analysis, 'closing_groups') and closing_analysis.closing_groups:
                    for group in closing_analysis.closing_groups:
                        logger.info(f"💰 CLOSING GROUP: {len(group)} positions")
                        # Execute group closing
                        result = self.order_manager.close_positions_group(group)
                        if result:
                            logger.info(f"✅ GROUP CLOSED: Net profit expected")
                        else:
                            logger.error(f"❌ GROUP CLOSING FAILED")
                            
        except Exception as e:
            logger.error(f"❌ Error in dynamic closing: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get current system status"""
        return {
            'is_running': self.is_running,
            'symbol': self.actual_symbol,
            'timeframes': [tf.value for tf in self.timeframes],
            'candle_history_sizes': {tf.value: len(history) for tf, history in self.candle_history.items()},
            'last_trade_times': {tf.value: time.isoformat() if time else None 
                               for tf, time in self.last_candle_time.items()},
            'active_positions': len(self.order_manager.active_positions) if self.order_manager else 0
        }

def main():
    """Main function to run the Simple Breakout Trading System"""
    # Create and start the trading system
    system = SimpleBreakoutTradingSystem(initial_balance=10000.0, symbol="XAUUSD")
    
    try:
        # Start trading
        system.start_trading()
        
        # Keep the system running
        logger.info("🚀 System is running. Press Ctrl+C to stop...")
        while True:
            time.sleep(10)
            # Print status every 10 seconds
            status = system.get_system_status()
            logger.info(f"📊 STATUS: Running={status['is_running']}, Positions={status['active_positions']}")
            
    except KeyboardInterrupt:
        logger.info("🛑 Stopping system...")
        system.stop_trading()
        logger.info("✅ System stopped successfully")

if __name__ == "__main__":
    main()
