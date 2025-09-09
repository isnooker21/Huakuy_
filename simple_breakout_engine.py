"""
🚀 Simple Breakout Trading Engine
================================

BREAKOUT LOGIC:
✅ BUY: current_candle.close > previous_candle.high
✅ SELL: current_candle.close < previous_candle.low
✅ One trade per candle per timeframe
✅ Multi-timeframe: M5, M15, M30, H1
✅ Support/Resistance Override
✅ Dynamic Lot Sizing

AUTHOR: Advanced Trading System
VERSION: 1.0.0
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, NamedTuple
from dataclasses import dataclass
from enum import Enum
import numpy as np

logger = logging.getLogger(__name__)

class TimeFrame(Enum):
    M5 = "M5"
    M15 = "M15" 
    M30 = "M30"
    H1 = "H1"

@dataclass
class CandleData:
    """Candle data structure"""
    open: float
    high: float
    low: float
    close: float
    volume: float
    time: datetime
    timeframe: TimeFrame

@dataclass
class BreakoutSignal:
    """Breakout signal data"""
    direction: str  # "BUY" or "SELL"
    timeframe: TimeFrame
    entry_price: float
    candle_strength: float
    lot_size: float
    confidence: float
    reason: str
    timestamp: datetime

@dataclass
class SRLevel:
    """Support/Resistance level"""
    price: float
    strength: float
    level_type: str  # "SUPPORT" or "RESISTANCE"
    touches: int
    last_touch: datetime

class SimpleBreakoutEngine:
    """
    🚀 Simple Breakout Trading Engine
    
    FEATURES:
    ✅ Simple Breakout Detection
    ✅ Multi-Timeframe Analysis
    ✅ One Trade Per Candle Per TF
    ✅ Support/Resistance Override
    ✅ Dynamic Lot Sizing
    """
    
    def __init__(self, mt5_connection, symbol: str, base_lot_size: float = 0.01):
        self.mt5_connection = mt5_connection
        self.symbol = symbol
        self.base_lot_size = base_lot_size
        
        # Trading state tracking
        self.last_trade_candle = {}  # {timeframe: candle_time}
        self.candle_history = {}     # {timeframe: [candles]}
        self.sr_levels = []          # Support/Resistance levels
        
        # Timeframes to monitor
        self.timeframes = [TimeFrame.M5, TimeFrame.M15, TimeFrame.M30, TimeFrame.H1]
        
        # Initialize candle history
        for tf in self.timeframes:
            self.candle_history[tf] = []
            self.last_trade_candle[tf] = None
            
        logger.info("🚀 Simple Breakout Engine initialized")
        logger.info(f"📊 Monitoring TFs: {[tf.value for tf in self.timeframes]}")
    
    def analyze_breakout_opportunity(self, current_candle: CandleData, 
                                   account_balance: float = 10000.0) -> Optional[BreakoutSignal]:
        """
        🎯 Analyze breakout opportunity for current candle
        
        LOGIC:
        ✅ BUY: current.close > previous.high
        ✅ SELL: current.close < previous.low
        ✅ One trade per candle per TF
        ✅ S/R Override check
        ✅ Dynamic lot sizing
        """
        try:
            tf = current_candle.timeframe
            
            # 1. ✅ Check if we can trade this candle (one per candle rule)
            if not self._can_trade_candle(current_candle):
                logger.debug(f"🚫 Cannot trade {tf.value} - Already traded this candle")
                return None
            
            # 2. 📊 Get previous candle for comparison
            previous_candle = self._get_previous_candle(tf)
            if not previous_candle:
                logger.debug(f"🚫 No previous candle for {tf.value}")
                return None
            
            # 3. 🎯 Basic Breakout Analysis
            breakout_signal = self._analyze_basic_breakout(current_candle, previous_candle)
            if not breakout_signal:
                return None
            
            # 4. 🛡️ Support/Resistance Override Check
            sr_override = self._check_sr_override(current_candle.close)
            if sr_override:
                breakout_signal.direction = sr_override
                breakout_signal.reason = f"S/R Override: {sr_override}"
                logger.info(f"🔄 S/R OVERRIDE: {breakout_signal.direction} @ {current_candle.close:.2f}")
            
            # 5. 💰 Dynamic Lot Sizing
            breakout_signal.lot_size = self._calculate_dynamic_lot_size(
                candle_strength=breakout_signal.candle_strength,
                account_balance=account_balance,
                timeframe=tf
            )
            
            # 6. 📝 Update trading state
            self._update_candle_history(current_candle)
            self.last_trade_candle[tf] = current_candle.time
            
            logger.info(f"✅ BREAKOUT SIGNAL: {breakout_signal.direction} {tf.value} "
                       f"Lot:{breakout_signal.lot_size:.3f} Strength:{breakout_signal.candle_strength:.1f}%")
            
            return breakout_signal
            
        except Exception as e:
            logger.error(f"❌ Breakout analysis error: {e}")
            return None
    
    def _can_trade_candle(self, candle: CandleData) -> bool:
        """Check if we can trade this candle (one trade per candle rule)"""
        tf = candle.timeframe
        last_trade_time = self.last_trade_candle.get(tf)
        
        if last_trade_time is None:
            return True
            
        # Check if this is a new candle
        return candle.time > last_trade_time
    
    def _get_previous_candle(self, timeframe: TimeFrame) -> Optional[CandleData]:
        """Get previous candle for comparison"""
        history = self.candle_history.get(timeframe, [])
        if len(history) < 1:
            return None
        return history[-1]  # Most recent previous candle
    
    def _analyze_basic_breakout(self, current: CandleData, previous: CandleData) -> Optional[BreakoutSignal]:
        """
        🎯 Basic Breakout Analysis
        
        BUY: current.close > previous.high
        SELL: current.close < previous.low
        """
        # Calculate candle strength
        candle_body = abs(current.close - current.open)
        candle_range = current.high - current.low
        candle_strength = (candle_body / candle_range * 100) if candle_range > 0 else 0
        
        # Breakout detection
        if current.close > previous.high:
            # 🟢 BUY Breakout
            return BreakoutSignal(
                direction="BUY",
                timeframe=current.timeframe,
                entry_price=current.close,
                candle_strength=candle_strength,
                lot_size=self.base_lot_size,  # Will be recalculated
                confidence=min(95.0, 50.0 + candle_strength),
                reason=f"Breakout: {current.close:.2f} > {previous.high:.2f}",
                timestamp=current.time
            )
            
        elif current.close < previous.low:
            # 🔴 SELL Breakout
            return BreakoutSignal(
                direction="SELL", 
                timeframe=current.timeframe,
                entry_price=current.close,
                candle_strength=candle_strength,
                lot_size=self.base_lot_size,  # Will be recalculated
                confidence=min(95.0, 50.0 + candle_strength),
                reason=f"Breakout: {current.close:.2f} < {previous.low:.2f}",
                timestamp=current.time
            )
        
        return None
    
    def _check_sr_override(self, current_price: float) -> Optional[str]:
        """
        🛡️ Support/Resistance Override
        
        If price hits Support -> Force BUY
        If price hits Resistance -> Force SELL
        """
        tolerance = 5.0  # 5 points tolerance for XAUUSD
        
        for sr_level in self.sr_levels:
            if abs(current_price - sr_level.price) <= tolerance:
                if sr_level.level_type == "SUPPORT":
                    logger.info(f"🛡️ SUPPORT HIT: {current_price:.2f} ≈ {sr_level.price:.2f} -> FORCE BUY")
                    return "BUY"
                elif sr_level.level_type == "RESISTANCE":
                    logger.info(f"🛡️ RESISTANCE HIT: {current_price:.2f} ≈ {sr_level.price:.2f} -> FORCE SELL")
                    return "SELL"
        
        return None
    
    def _calculate_dynamic_lot_size(self, candle_strength: float, account_balance: float, 
                                   timeframe: TimeFrame) -> float:
        """
        💰 Dynamic Lot Sizing
        
        FACTORS:
        ✅ Account Balance (Risk %)
        ✅ Candle Strength (Confidence)
        ✅ Timeframe Weight
        ✅ Min/Max Limits
        """
        # Base risk percentage
        risk_percent = 0.02  # 2% of account
        
        # Timeframe multipliers
        tf_multipliers = {
            TimeFrame.M5: 0.5,   # Lower risk for scalping
            TimeFrame.M15: 0.75,
            TimeFrame.M30: 1.0,  # Base multiplier
            TimeFrame.H1: 1.5    # Higher risk for swing
        }
        
        # Calculate base lot size from account balance
        base_lot_from_balance = (account_balance * risk_percent) / 1000  # Rough calculation
        
        # Apply candle strength multiplier (50-150%)
        strength_multiplier = 0.5 + (candle_strength / 100.0)
        
        # Apply timeframe multiplier
        tf_multiplier = tf_multipliers.get(timeframe, 1.0)
        
        # Calculate final lot size
        dynamic_lot = base_lot_from_balance * strength_multiplier * tf_multiplier
        
        # Apply limits
        min_lot = 0.01
        max_lot = min(1.0, account_balance / 5000)  # Max 1 lot or balance/5000
        
        final_lot = max(min_lot, min(max_lot, dynamic_lot))
        
        logger.debug(f"💰 Dynamic Lot: Balance:{account_balance} Strength:{candle_strength:.1f}% "
                    f"TF:{timeframe.value} -> {final_lot:.3f}")
        
        return round(final_lot, 2)
    
    def _update_candle_history(self, candle: CandleData):
        """Update candle history for timeframe"""
        tf = candle.timeframe
        if tf not in self.candle_history:
            self.candle_history[tf] = []
        
        # Add new candle
        self.candle_history[tf].append(candle)
        
        # Keep only last 100 candles per timeframe
        if len(self.candle_history[tf]) > 100:
            self.candle_history[tf] = self.candle_history[tf][-100:]
    
    def update_sr_levels(self, new_levels: List[SRLevel]):
        """Update Support/Resistance levels"""
        self.sr_levels = new_levels
        logger.info(f"🛡️ Updated S/R Levels: {len(new_levels)} levels")
        
        for level in new_levels:
            logger.debug(f"   {level.level_type}: {level.price:.2f} (Strength: {level.strength:.1f})")
    
    def get_trading_status(self) -> Dict:
        """Get current trading status"""
        return {
            'timeframes_monitored': [tf.value for tf in self.timeframes],
            'last_trades': {tf.value: time.isoformat() if time else None 
                           for tf, time in self.last_trade_candle.items()},
            'candle_history_size': {tf.value: len(history) 
                                  for tf, history in self.candle_history.items()},
            'sr_levels_count': len(self.sr_levels)
        }

def create_simple_breakout_engine(mt5_connection, symbol: str) -> SimpleBreakoutEngine:
    """Factory function to create Simple Breakout Engine"""
    return SimpleBreakoutEngine(mt5_connection, symbol)
