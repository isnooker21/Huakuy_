"""
Signal Manager - จัดการสัญญาณจากทุกระบบในจุดเดียว
ป้องกันความซับซ้อนและการตีกันระหว่างระบบต่างๆ
"""

import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from trading_conditions import Signal, CandleData, TradingConditions
from smart_gap_filler import SmartGapFiller
from force_trading_mode import ForceTradingMode

logger = logging.getLogger(__name__)

class SignalPriority(Enum):
    """ลำดับความสำคัญของสัญญาณ"""
    MAIN = 1        # สัญญาณหลักจาก candle analysis
    GAP_FILLER = 2  # สัญญาณเติม gap
    FORCE_TRADE = 3 # สัญญาณบังคับเทรด
    
@dataclass
class RankedSignal:
    """สัญญาณพร้อมลำดับความสำคัญ"""
    signal: Signal
    priority: SignalPriority
    source: str
    confidence_score: float
    reason: str

class SignalManager:
    """จัดการสัญญาณจากทุกระบบในจุดเดียว"""
    
    def __init__(self, mt5_connection):
        self.mt5 = mt5_connection
        
        # ระบบย่อยต่างๆ
        self.trading_conditions = TradingConditions()
        self.gap_filler = SmartGapFiller(mt5_connection)
        self.force_trading = ForceTradingMode(mt5_connection)
        
        # การตั้งค่า
        self.enable_main_signals = True
        self.enable_gap_filler = True
        self.enable_force_trading = True
        
        # สถิติ
        self.signal_history = []
        self.last_signal_time = None
        self.signals_generated_today = 0
        
    def get_best_signal(self, candle: CandleData, positions: List[Any], 
                       account_balance: float, volume_history: List[float] = None,
                       current_price: float = None, last_trade_time: datetime = None) -> Optional[RankedSignal]:
        """หาสัญญาณที่ดีที่สุดจากทุกระบบ"""
        try:
            logger.debug("🎯 Signal Manager: กำลังหาสัญญาณที่ดีที่สุด...")
            
            all_signals = []
            current_price = current_price or candle.close
            
            # 1. 🎯 Main Signal System (Priority 1 - สูงสุด)
            if self.enable_main_signals:
                main_signal = self._get_main_signal(candle, positions, account_balance, volume_history)
                if main_signal:
                    all_signals.append(main_signal)
                    logger.info(f"📊 Main Signal: {main_signal.signal.direction} (Strength: {main_signal.signal.strength:.1f}%)")
            
            # 2. 🔧 Gap Filler (Priority 2 - เฉพาะเมื่อไม่มี main signal)
            if self.enable_gap_filler and not all_signals:
                gap_signal = self._get_gap_filler_signal(positions, current_price, last_trade_time)
                if gap_signal:
                    all_signals.append(gap_signal)
                    logger.info(f"🔧 Gap Filler Signal: {gap_signal.signal.direction} (Gap Fill)")
            
            # 3. 🚨 Force Trading (Priority 3 - เฉพาะเมื่อไม่มีสัญญาณอื่น)
            if self.enable_force_trading and not all_signals:
                force_signal = self._get_force_trading_signal(positions, last_trade_time, current_price)
                if force_signal:
                    all_signals.append(force_signal)
                    logger.info(f"🚨 Force Trading Signal: {force_signal.signal.direction} (Forced)")
            
            # เลือกสัญญาณที่ดีที่สุด
            best_signal = self._select_best_signal(all_signals)
            
            if best_signal:
                logger.info(f"✅ Selected Signal: {best_signal.source} - {best_signal.signal.direction} "
                           f"(Priority: {best_signal.priority.name}, Score: {best_signal.confidence_score:.1f})")
                
                # บันทึกประวัติ
                self._record_signal_history(best_signal)
                
            else:
                logger.debug("⏸️ No suitable signals found")
            
            return best_signal
            
        except Exception as e:
            logger.error(f"Error in signal manager: {e}")
            return None
    
    def _get_main_signal(self, candle: CandleData, positions: List[Any], 
                        account_balance: float, volume_history: List[float]) -> Optional[RankedSignal]:
        """ดึงสัญญาณหลักจาก TradingConditions"""
        try:
            entry_result = self.trading_conditions.check_entry_conditions(
                candle, positions, account_balance, volume_history, candle.symbol
            )
            
            if entry_result['can_enter'] and entry_result['signal']:
                signal = entry_result['signal']
                
                # คำนวณ confidence score
                confidence_score = self._calculate_main_signal_confidence(signal, candle)
                
                return RankedSignal(
                    signal=signal,
                    priority=SignalPriority.MAIN,
                    source="Main Trading System",
                    confidence_score=confidence_score,
                    reason=f"Candle analysis: {signal.direction} with {signal.strength:.1f}% strength"
                )
                
        except Exception as e:
            logger.error(f"Error getting main signal: {e}")
            
        return None
    
    def _get_gap_filler_signal(self, positions: List[Any], current_price: float, 
                              last_trade_time: datetime) -> Optional[RankedSignal]:
        """ดึงสัญญาณจาก Gap Filler"""
        try:
            gap_result = self.gap_filler.should_activate_gap_filling(
                positions, current_price, last_trade_time
            )
            
            if gap_result['should_activate']:
                gap_signal = self.gap_filler.create_synthetic_signal(
                    gap_result['recommended_action']
                )
                
                if gap_signal:
                    # คำนวณ confidence score
                    confidence_score = self._calculate_gap_filler_confidence(gap_result)
                    
                    return RankedSignal(
                        signal=gap_signal,
                        priority=SignalPriority.GAP_FILLER,
                        source="Smart Gap Filler",
                        confidence_score=confidence_score,
                        reason=gap_result['activation_reason']
                    )
                    
        except Exception as e:
            logger.error(f"Error getting gap filler signal: {e}")
            
        return None
    
    def _get_force_trading_signal(self, positions: List[Any], last_trade_time: datetime,
                                 current_price: float) -> Optional[RankedSignal]:
        """ดึงสัญญาณจาก Force Trading"""
        try:
            force_result = self.force_trading.should_activate_force_mode(
                last_trade_time, positions
            )
            
            if force_result['should_activate']:
                force_signal = self.force_trading.create_force_signal(
                    force_result['recommended_action'], current_price
                )
                
                if force_signal:
                    # คำนวณ confidence score
                    confidence_score = self._calculate_force_trading_confidence(force_result)
                    
                    return RankedSignal(
                        signal=force_signal,
                        priority=SignalPriority.FORCE_TRADE,
                        source="Force Trading Mode",
                        confidence_score=confidence_score,
                        reason=force_result['activation_reason']
                    )
                    
        except Exception as e:
            logger.error(f"Error getting force trading signal: {e}")
            
        return None
    
    def _select_best_signal(self, signals: List[RankedSignal]) -> Optional[RankedSignal]:
        """เลือกสัญญาณที่ดีที่สุด"""
        if not signals:
            return None
        
        # เรียงตามลำดับความสำคัญ แล้วตาม confidence score
        signals.sort(key=lambda x: (x.priority.value, -x.confidence_score))
        
        return signals[0]
    
    def _calculate_main_signal_confidence(self, signal: Signal, candle: CandleData) -> float:
        """คำนวณ confidence score สำหรับ main signal"""
        try:
            base_score = signal.confidence
            
            # เพิ่มคะแนนจากแรงของแท่งเทียน
            candle_strength = abs(candle.close - candle.open) / candle.open * 100
            strength_bonus = min(candle_strength * 10, 20)  # สูงสุด 20 คะแนน
            
            # เพิ่มคะแนนจาก signal strength
            signal_bonus = signal.strength * 0.3
            
            total_score = min(base_score + strength_bonus + signal_bonus, 100)
            return total_score
            
        except Exception as e:
            logger.error(f"Error calculating main signal confidence: {e}")
            return signal.confidence
    
    def _calculate_gap_filler_confidence(self, gap_result: Dict) -> float:
        """คำนวณ confidence score สำหรับ gap filler"""
        try:
            base_score = 40.0  # ค่าเริ่มต้นต่ำกว่า main signal
            
            # เพิ่มคะแนนจากขนาด gap
            gap_analysis = gap_result.get('gap_analysis')
            if gap_analysis and hasattr(gap_analysis, 'gap_size'):
                gap_bonus = min(gap_analysis.gap_size / 10, 30)  # สูงสุด 30 คะแนน
                base_score += gap_bonus
            
            return min(base_score, 80)  # สูงสุด 80% สำหรับ synthetic signal
            
        except Exception as e:
            logger.error(f"Error calculating gap filler confidence: {e}")
            return 40.0
    
    def _calculate_force_trading_confidence(self, force_result: Dict) -> float:
        """คำนวณ confidence score สำหรับ force trading"""
        try:
            base_score = 30.0  # ค่าเริ่มต้นต่ำสุด
            
            # เพิ่มคะแนนจาก activation level
            activation_level = force_result.get('activation_level', 'LOW')
            if activation_level == 'HIGH':
                base_score += 20
            elif activation_level == 'MEDIUM':
                base_score += 10
            
            return min(base_score, 60)  # สูงสุด 60% สำหรับ forced signal
            
        except Exception as e:
            logger.error(f"Error calculating force trading confidence: {e}")
            return 30.0
    
    def _record_signal_history(self, ranked_signal: RankedSignal):
        """บันทึกประวัติสัญญาณ"""
        try:
            record = {
                'timestamp': datetime.now(),
                'source': ranked_signal.source,
                'priority': ranked_signal.priority.name,
                'direction': ranked_signal.signal.direction,
                'strength': ranked_signal.signal.strength,
                'confidence_score': ranked_signal.confidence_score,
                'reason': ranked_signal.reason
            }
            
            self.signal_history.append(record)
            
            # เก็บแค่ 100 records ล่าสุด
            if len(self.signal_history) > 100:
                self.signal_history = self.signal_history[-100:]
                
            self.last_signal_time = datetime.now()
            self.signals_generated_today += 1
            
        except Exception as e:
            logger.error(f"Error recording signal history: {e}")
    
    
