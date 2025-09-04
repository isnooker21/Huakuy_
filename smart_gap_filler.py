"""
Smart Gap Filler System - เติมไม้อัตโนมัติเพื่อให้ระบบทำงานต่เนื่อง
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from calculations import Position
from trading_conditions import Signal

logger = logging.getLogger(__name__)

@dataclass
class GapAnalysis:
    """ผลการวิเคราะห์ช่องว่างระหว่างไม้"""
    has_gap: bool
    gap_size: float  # pips
    max_buy_price: float
    min_sell_price: float
    middle_price: float
    missing_side: str  # 'BUY', 'SELL', or 'BALANCED'
    should_fill: bool
    recommended_action: Dict[str, Any]

class SmartGapFiller:
    """ระบบเติมไม้อัตโนมัติในโซนกลาง"""
    
    def __init__(self, mt5_connection):
        self.mt5 = mt5_connection
        
        # การตั้งค่า
        self.min_gap_threshold = 30.0      # 30 pips ขั้นต่ำถึงจะเติม
        self.max_gap_threshold = 150.0     # 150 pips สูงสุดที่เติมได้
        self.fill_timeout = 900            # 15 นาที ก่อนเริ่มเติม
        self.force_fill_timeout = 1500     # 25 นาที บังคับเติม
        self.min_fill_lot = 0.01           # lot ขั้นต่ำสำหรับการเติม
        
        # สถิติ
        self.last_analysis_time: Optional[datetime] = None
        self.last_fill_time: Optional[datetime] = None
        self.total_fills_today = 0
        self.max_fills_per_hour = 4        # สูงสุด 4 ครั้งต่อชั่วโมง
        
    def analyze_price_gap(self, positions: List[Position], current_price: float) -> GapAnalysis:
        """วิเคราะห์ช่องว่างระหว่างไม้ BUY และ SELL"""
        try:
            if not positions or len(positions) < 2:
                return GapAnalysis(
                    has_gap=False,
                    gap_size=0.0,
                    max_buy_price=0.0,
                    min_sell_price=0.0,
                    middle_price=current_price,
                    missing_side='NONE',
                    should_fill=False,
                    recommended_action={}
                )
            
            # แยกไม้ BUY และ SELL
            buy_positions = [pos for pos in positions if pos.type == 0]  # BUY
            sell_positions = [pos for pos in positions if pos.type == 1]  # SELL
            
            if not buy_positions or not sell_positions:
                missing_side = 'SELL' if not sell_positions else 'BUY'
                return GapAnalysis(
                    has_gap=True,
                    gap_size=999.0,  # Gap ใหญ่มาก
                    max_buy_price=max(pos.price_open for pos in buy_positions) if buy_positions else 0.0,
                    min_sell_price=min(pos.price_open for pos in sell_positions) if sell_positions else 0.0,
                    middle_price=current_price,
                    missing_side=missing_side,
                    should_fill=True,
                    recommended_action=self._create_fill_recommendation(missing_side, current_price, positions)
                )
            
            # คำนวณ gap
            max_buy_price = max(pos.price_open for pos in buy_positions)
            min_sell_price = min(pos.price_open for pos in sell_positions)
            
            # สำหรับ XAUUSD: 1 pip = 0.10
            gap_size = abs(max_buy_price - min_sell_price) * 10  # แปลงเป็น pips
            middle_price = (max_buy_price + min_sell_price) / 2
            
            # ตรวจสอบว่าควรเติมหรือไม่
            should_fill = self._should_fill_gap(gap_size, positions)
            
            # หาว่าขาดฝั่งไหน
            buy_count = len(buy_positions)
            sell_count = len(sell_positions)
            
            if buy_count < sell_count - 1:
                missing_side = 'BUY'
            elif sell_count < buy_count - 1:
                missing_side = 'SELL'
            else:
                missing_side = 'BALANCED'
            
            analysis = GapAnalysis(
                has_gap=gap_size > self.min_gap_threshold,
                gap_size=gap_size,
                max_buy_price=max_buy_price,
                min_sell_price=min_sell_price,
                middle_price=middle_price,
                missing_side=missing_side,
                should_fill=should_fill,
                recommended_action=self._create_fill_recommendation(missing_side, middle_price, positions) if should_fill else {}
            )
            
            logger.info(f"🔍 Gap Analysis: Gap={gap_size:.1f} pips, Missing={missing_side}, Should Fill={should_fill}")
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing price gap: {e}")
            return GapAnalysis(False, 0.0, 0.0, 0.0, current_price, 'NONE', False, {})
    
    def _should_fill_gap(self, gap_size: float, positions: List[Position]) -> bool:
        """ตัดสินใจว่าควรเติม gap หรือไม่"""
        try:
            now = datetime.now()
            
            # เช็คขีดจำกัดการเติมต่อชั่วโมง
            if self._is_fill_rate_exceeded():
                logger.info("🚫 Fill rate exceeded - skipping gap fill")
                return False
            
            # เช็คว่า gap อยู่ในช่วงที่เติมได้
            if gap_size < self.min_gap_threshold:
                logger.debug(f"Gap too small: {gap_size:.1f} < {self.min_gap_threshold}")
                return False
                
            if gap_size > self.max_gap_threshold:
                logger.debug(f"Gap too large: {gap_size:.1f} > {self.max_gap_threshold}")
                return False
            
            # เช็คเวลาที่ผ่านมาตั้งแต่การเทรดครั้งล่าสุด
            if self.last_analysis_time:
                time_since_last = (now - self.last_analysis_time).total_seconds()
                
                # เติมปกติหลัง 15 นาที
                if time_since_last > self.fill_timeout:
                    logger.info(f"⏰ Time threshold reached: {time_since_last/60:.1f} minutes")
                    return True
                
                # บังคับเติมหลัง 25 นาที
                if time_since_last > self.force_fill_timeout:
                    logger.info(f"🚨 Force fill activated: {time_since_last/60:.1f} minutes")
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking fill conditions: {e}")
            return False
    
    def _is_fill_rate_exceeded(self) -> bool:
        """เช็คว่าเติมไม้เกินขีดจำกัดต่อชั่วโมงหรือไม่"""
        if not self.last_fill_time:
            return False
            
        now = datetime.now()
        time_diff = (now - self.last_fill_time).total_seconds()
        
        # รีเซ็ตนับทุกชั่วโมง
        if time_diff > 3600:  # 1 ชั่วโมง
            self.total_fills_today = 0
            return False
        
        return self.total_fills_today >= self.max_fills_per_hour
    
    def _create_fill_recommendation(self, missing_side: str, target_price: float, positions: List[Position]) -> Dict[str, Any]:
        """สร้างคำแนะนำการเติมไม้"""
        try:
            if missing_side == 'NONE' or missing_side == 'BALANCED':
                return {}
            
            # คำนวณ lot size สำหรับการเติม
            total_positions = len(positions)
            
            # ใช้ lot เล็กสำหรับการเติม
            fill_lot = self.min_fill_lot
            if total_positions > 5:
                fill_lot = 0.02  # เพิ่ม lot ถ้ามีไม้เยอะ
            
            # ปรับราคาเล็กน้อยเพื่อไม่ให้ติด exact middle
            price_adjustment = 0.2 if missing_side == 'BUY' else -0.2  # 2 pips
            adjusted_price = target_price + price_adjustment
            
            recommendation = {
                'action': 'FILL_GAP',
                'direction': missing_side,
                'price': adjusted_price,
                'lot_size': fill_lot,
                'reason': f'Gap filling - missing {missing_side} positions',
                'priority': 'MEDIUM',
                'timeout': 300,  # 5 นาที timeout
                'signal_strength': 15.0  # กำหนดแรงสัญญาณต่ำ
            }
            
            logger.info(f"💡 Fill Recommendation: {missing_side} at {adjusted_price:.2f} (Lot: {fill_lot})")
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Error creating fill recommendation: {e}")
            return {}
    
    def should_activate_gap_filling(self, positions: List[Position], current_price: float, 
                                  last_trade_time: Optional[datetime] = None) -> Dict[str, Any]:
        """ตัดสินใจว่าควรเปิดใช้ gap filling หรือไม่"""
        try:
            now = datetime.now()
            self.last_analysis_time = now
            
            # วิเคราะห์ gap
            gap_analysis = self.analyze_price_gap(positions, current_price)
            
            result = {
                'should_activate': False,
                'gap_analysis': gap_analysis,
                'activation_reason': '',
                'recommended_action': {}
            }
            
            if not gap_analysis.should_fill:
                result['activation_reason'] = 'Gap conditions not met'
                return result
            
            # เช็คเวลาที่ไม่ได้เทรด
            if last_trade_time:
                time_since_trade = (now - last_trade_time).total_seconds()
                
                if time_since_trade > self.fill_timeout:
                    result.update({
                        'should_activate': True,
                        'activation_reason': f'No trades for {time_since_trade/60:.1f} minutes',
                        'recommended_action': gap_analysis.recommended_action
                    })
                    
                    logger.info(f"🎯 Gap Filling Activated: {result['activation_reason']}")
                    return result
            
            # เช็คความไม่สมดุลของไม้
            if gap_analysis.missing_side in ['BUY', 'SELL']:
                result.update({
                    'should_activate': True,
                    'activation_reason': f'Imbalanced positions - missing {gap_analysis.missing_side}',
                    'recommended_action': gap_analysis.recommended_action
                })
                
                logger.info(f"⚖️ Gap Filling Activated: {result['activation_reason']}")
                return result
            
            return result
            
        except Exception as e:
            logger.error(f"Error in gap filling activation: {e}")
            return {'should_activate': False, 'gap_analysis': None, 'activation_reason': f'Error: {e}', 'recommended_action': {}}
    
    def create_synthetic_signal(self, recommendation: Dict[str, Any], symbol: str = "XAUUSD") -> Optional[Signal]:
        """สร้างสัญญาณเทียมสำหรับการเติม gap"""
        try:
            if not recommendation or recommendation.get('action') != 'FILL_GAP':
                return None
            
            direction = recommendation['direction']
            price = recommendation['price']
            strength = recommendation.get('signal_strength', 15.0)
            
            signal = Signal(
                direction=direction,
                symbol=symbol,
                strength=strength,
                confidence=0.6,  # ความเชื่อมั่นปานกลาง
                entry_price=price,
                timestamp=datetime.now(),
                timeframe='M5',
                indicators={
                    'source': 'GAP_FILLER',
                    'gap_fill': True,
                    'synthetic': True,
                    'reason': recommendation.get('reason', 'Gap filling')
                }
            )
            
            logger.info(f"🤖 Synthetic Signal Created: {direction} at {price:.2f} (Strength: {strength}%)")
            
            # อัพเดทสถิติ
            self.last_fill_time = datetime.now()
            self.total_fills_today += 1
            
            return signal
            
        except Exception as e:
            logger.error(f"Error creating synthetic signal: {e}")
            return None
    
    def get_fill_statistics(self) -> Dict[str, Any]:
        """ดึงสถิติการเติมไม้"""
        return {
            'total_fills_today': self.total_fills_today,
            'max_fills_per_hour': self.max_fills_per_hour,
            'last_fill_time': self.last_fill_time,
            'last_analysis_time': self.last_analysis_time,
            'fill_timeout_minutes': self.fill_timeout / 60,
            'force_fill_timeout_minutes': self.force_fill_timeout / 60
        }
