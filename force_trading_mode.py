"""
Force Trading Mode - บังคับเทรดเมื่อระบบหยุดนิ่งนานเกินไป
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import MetaTrader5 as mt5
from calculations import Position
from trading_conditions import Signal

logger = logging.getLogger(__name__)

@dataclass
class MarketMomentum:
    """ข้อมูลแรงโมเมนตัมของตลาด"""
    price_change: float      # การเปลี่ยนแปลงราคา (pips)
    volume_ratio: float      # อัตราส่วน volume เทียบเฉลี่ย
    volatility: float        # ความผันผวน (ATR)
    trend_direction: str     # 'UP', 'DOWN', 'SIDEWAYS'
    momentum_strength: float # แรงโมเมนตัม 0-100%

class ForceTradingMode:
    """ระบบบังคับเทรดเมื่อหยุดนิ่งนานเกินไป"""
    
    def __init__(self, mt5_connection):
        self.mt5 = mt5_connection
        
        # การตั้งค่า
        self.activation_timeout = 1200     # 20 นาที เปิดใช้
        self.emergency_timeout = 1800      # 30 นาที บังคับเทรด
        self.min_volatility = 0.5          # ATR ขั้นต่ำ (pips)
        self.min_volume_ratio = 0.8        # Volume ratio ขั้นต่ำ
        self.force_signal_strength = 20.0  # แรงสัญญาณบังคับ
        
        # สถิติ
        self.last_activation_time: Optional[datetime] = None
        self.forced_trades_today = 0
        self.max_forced_trades = 6         # สูงสุด 6 ครั้งต่อวัน
        self.success_rate = 0.0
        
        # Cache
        self.last_momentum_analysis: Optional[MarketMomentum] = None
        self.last_momentum_time: Optional[datetime] = None
        
    def analyze_market_momentum(self, symbol: str = "XAUUSD", timeframe=mt5.TIMEFRAME_M5) -> Optional[MarketMomentum]:
        """วิเคราะห์แรงโมเมนตัมของตลาด"""
        try:
            # ใช้ cache ถ้าข้อมูลยังใหม่ (< 2 นาที)
            now = datetime.now()
            if (self.last_momentum_analysis and self.last_momentum_time and 
                (now - self.last_momentum_time).total_seconds() < 120):
                return self.last_momentum_analysis
            
            # ดึงข้อมูล candle ย้อนหลัง 20 แท่ง
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 20)
            if rates is None or len(rates) < 10:
                logger.warning("ไม่สามารถดึงข้อมูลราคาสำหรับ momentum analysis")
                return None
            
            # คำนวณการเปลี่ยนแปลงราคา
            current_price = rates[-1]['close']
            prev_price = rates[-5]['close']  # 5 แท่งก่อน
            price_change = (current_price - prev_price) * 10  # แปลงเป็น pips
            
            # คำนวณ volume ratio
            recent_volumes = [r['tick_volume'] for r in rates[-5:]]
            older_volumes = [r['tick_volume'] for r in rates[-15:-5]]
            
            avg_recent_volume = sum(recent_volumes) / len(recent_volumes)
            avg_older_volume = sum(older_volumes) / len(older_volumes)
            volume_ratio = avg_recent_volume / avg_older_volume if avg_older_volume > 0 else 1.0
            
            # คำนวณ ATR (Average True Range)
            atr_values = []
            for i in range(1, len(rates)):
                high_low = rates[i]['high'] - rates[i]['low']
                high_close_prev = abs(rates[i]['high'] - rates[i-1]['close'])
                low_close_prev = abs(rates[i]['low'] - rates[i-1]['close'])
                true_range = max(high_low, high_close_prev, low_close_prev)
                atr_values.append(true_range * 10)  # แปลงเป็น pips
            
            volatility = sum(atr_values[-10:]) / 10 if atr_values else 0.0
            
            # กำหนดทิศทาง trend
            if price_change > 2.0:
                trend_direction = 'UP'
            elif price_change < -2.0:
                trend_direction = 'DOWN'
            else:
                trend_direction = 'SIDEWAYS'
            
            # คำนวณแรงโมเมนตัม
            momentum_strength = min(100.0, abs(price_change) * 5 + volume_ratio * 20 + volatility * 2)
            
            momentum = MarketMomentum(
                price_change=price_change,
                volume_ratio=volume_ratio,
                volatility=volatility,
                trend_direction=trend_direction,
                momentum_strength=momentum_strength
            )
            
            # อัพเดท cache
            self.last_momentum_analysis = momentum
            self.last_momentum_time = now
            
            logger.info(f"📊 Market Momentum: Price={price_change:.1f}p, Vol={volume_ratio:.2f}x, "
                       f"ATR={volatility:.1f}p, Trend={trend_direction}, Strength={momentum_strength:.1f}%")
            
            return momentum
            
        except Exception as e:
            logger.error(f"Error analyzing market momentum: {e}")
            return None
    
    def should_activate_force_mode(self, last_trade_time: Optional[datetime], 
                                 positions: List[Position]) -> Dict[str, Any]:
        """ตัดสินใจว่าควรเปิด Force Trading Mode หรือไม่"""
        try:
            now = datetime.now()
            
            result = {
                'should_activate': False,
                'activation_level': 'NONE',  # 'NORMAL', 'EMERGENCY'
                'reason': '',
                'time_since_trade': 0,
                'momentum_analysis': None,
                'recommended_action': {}
            }
            
            # เช็คขีดจำกัดการบังคับเทรดต่อวัน
            if self.forced_trades_today >= self.max_forced_trades:
                result['reason'] = f'Daily limit reached ({self.forced_trades_today}/{self.max_forced_trades})'
                return result
            
            # คำนวณเวลาที่ไม่ได้เทรด
            if last_trade_time:
                time_since_trade = (now - last_trade_time).total_seconds()
                result['time_since_trade'] = time_since_trade
                
                # เช็คเงื่อนไขเปิดใช้
                if time_since_trade > self.activation_timeout:
                    # วิเคราะห์ momentum
                    momentum = self.analyze_market_momentum()
                    result['momentum_analysis'] = momentum
                    
                    if momentum and self._is_market_suitable_for_force_trade(momentum):
                        activation_level = 'EMERGENCY' if time_since_trade > self.emergency_timeout else 'NORMAL'
                        
                        result.update({
                            'should_activate': True,
                            'activation_level': activation_level,
                            'reason': f'No trades for {time_since_trade/60:.1f} minutes with suitable market conditions',
                            'recommended_action': self._create_force_trade_recommendation(momentum, positions, activation_level)
                        })
                        
                        logger.info(f"🚨 Force Trading Mode Activated: {activation_level} - {result['reason']}")
                        return result
                    else:
                        result['reason'] = 'Market conditions not suitable for forced trading'
                else:
                    result['reason'] = f'Time threshold not reached: {time_since_trade/60:.1f}/{self.activation_timeout/60:.1f} minutes'
            else:
                result['reason'] = 'No previous trade time available'
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking force mode activation: {e}")
            return {'should_activate': False, 'activation_level': 'NONE', 'reason': f'Error: {e}', 
                   'time_since_trade': 0, 'momentum_analysis': None, 'recommended_action': {}}
    
    def _is_market_suitable_for_force_trade(self, momentum: MarketMomentum) -> bool:
        """ตรวจสอบว่าสภาพตลาดเหมาะสำหรับการบังคับเทรดหรือไม่"""
        try:
            # เช็คความผันผวนขั้นต่ำ
            if momentum.volatility < self.min_volatility:
                logger.debug(f"Volatility too low: {momentum.volatility:.2f} < {self.min_volatility}")
                return False
            
            # เช็ค volume ratio
            if momentum.volume_ratio < self.min_volume_ratio:
                logger.debug(f"Volume ratio too low: {momentum.volume_ratio:.2f} < {self.min_volume_ratio}")
                return False
            
            # เช็คแรงโมเมนตัม
            if momentum.momentum_strength < 15.0:
                logger.debug(f"Momentum too weak: {momentum.momentum_strength:.1f}% < 15%")
                return False
            
            logger.info(f"✅ Market suitable for force trade: Vol={momentum.volatility:.1f}p, "
                       f"VolRatio={momentum.volume_ratio:.2f}x, Momentum={momentum.momentum_strength:.1f}%")
            return True
            
        except Exception as e:
            logger.error(f"Error checking market suitability: {e}")
            return False
    
    def _create_force_trade_recommendation(self, momentum: MarketMomentum, positions: List[Position], 
                                         activation_level: str) -> Dict[str, Any]:
        """สร้างคำแนะนำการเทรดบังคับ"""
        try:
            # เลือกทิศทางตาม momentum และ position imbalance
            buy_count = len([pos for pos in positions if pos.type == 0])
            sell_count = len([pos for pos in positions if pos.type == 1])
            
            # กำหนดทิศทางตาม momentum
            if momentum.trend_direction == 'UP' and momentum.price_change > 1.0:
                primary_direction = 'BUY'
            elif momentum.trend_direction == 'DOWN' and momentum.price_change < -1.0:
                primary_direction = 'SELL'
            else:
                # ถ้าไม่มี trend ชัด ให้เลือกตามความไม่สมดุล
                if buy_count < sell_count:
                    primary_direction = 'BUY'
                elif sell_count < buy_count:
                    primary_direction = 'SELL'
                else:
                    # สุ่มตาม momentum
                    primary_direction = 'BUY' if momentum.price_change >= 0 else 'SELL'
            
            # กำหนด lot size ตาม activation level
            if activation_level == 'EMERGENCY':
                lot_size = 0.02  # เพิ่ม lot ในกรณีฉุกเฉิน
                signal_strength = self.force_signal_strength + 5.0
            else:
                lot_size = 0.01
                signal_strength = self.force_signal_strength
            
            # ปรับ signal strength ตาม momentum
            adjusted_strength = min(50.0, signal_strength + momentum.momentum_strength * 0.3)
            
            recommendation = {
                'action': 'FORCE_TRADE',
                'direction': primary_direction,
                'lot_size': lot_size,
                'signal_strength': adjusted_strength,
                'confidence': 0.5 if activation_level == 'NORMAL' else 0.7,
                'reason': f'Force trade - {activation_level} level',
                'momentum_data': {
                    'price_change': momentum.price_change,
                    'trend': momentum.trend_direction,
                    'volatility': momentum.volatility,
                    'volume_ratio': momentum.volume_ratio
                },
                'priority': 'HIGH' if activation_level == 'EMERGENCY' else 'MEDIUM',
                'timeout': 600  # 10 นาที timeout
            }
            
            logger.info(f"🎯 Force Trade Recommendation: {primary_direction} (Lot: {lot_size}, "
                       f"Strength: {adjusted_strength:.1f}%, Level: {activation_level})")
            
            return recommendation
            
        except Exception as e:
            logger.error(f"Error creating force trade recommendation: {e}")
            return {}
    
    def create_force_signal(self, recommendation: Dict[str, Any], current_price: float, 
                          symbol: str = "XAUUSD") -> Optional[Signal]:
        """สร้างสัญญาณบังคับเทรด"""
        try:
            if not recommendation or recommendation.get('action') != 'FORCE_TRADE':
                return None
            
            direction = recommendation['direction']
            strength = recommendation['signal_strength']
            confidence = recommendation['confidence']
            
            # ปรับราคา entry เล็กน้อย
            price_adjustment = 0.1 if direction == 'BUY' else -0.1  # 1 pip
            entry_price = current_price + price_adjustment
            
            signal = Signal(
                direction=direction,
                symbol=symbol,
                strength=strength,
                confidence=confidence,
                price=entry_price,
                timestamp=datetime.now(),
                comment=f"Force Trade: {direction} at {entry_price}")
            
            # เพิ่ม indicators แบบ manual
            signal.indicators = {
                'source': 'FORCE_TRADING',
                'forced': True,
                'activation_level': recommendation.get('priority', 'MEDIUM'),
                'momentum_data': recommendation.get('momentum_data', {}),
                'reason': recommendation.get('reason', 'Force trade')
            }
            
            logger.info(f"🚨 Force Signal Created: {direction} at {entry_price:.2f} "
                       f"(Strength: {strength:.1f}%, Confidence: {confidence:.1f})")
            
            # อัพเดทสถิติ
            self.last_activation_time = datetime.now()
            self.forced_trades_today += 1
            
            return signal
            
        except Exception as e:
            logger.error(f"Error creating force signal: {e}")
            return None
    
    def get_force_statistics(self) -> Dict[str, Any]:
        """ดึงสถิติการบังคับเทรด"""
        return {
            'forced_trades_today': self.forced_trades_today,
            'max_forced_trades': self.max_forced_trades,
            'success_rate': self.success_rate,
            'last_activation_time': self.last_activation_time,
            'activation_timeout_minutes': self.activation_timeout / 60,
            'emergency_timeout_minutes': self.emergency_timeout / 60,
            'last_momentum': self.last_momentum_analysis
        }
    
    def update_success_rate(self, trade_result: bool):
        """อัพเดทอัตราความสำเร็จ"""
        try:
            if not hasattr(self, '_force_trade_results'):
                self._force_trade_results = []
            
            self._force_trade_results.append(trade_result)
            
            # เก็บแค่ 20 ผลลัพธ์ล่าสุด
            if len(self._force_trade_results) > 20:
                self._force_trade_results = self._force_trade_results[-20:]
            
            # คำนวณอัตราความสำเร็จ
            successful_trades = sum(self._force_trade_results)
            total_trades = len(self._force_trade_results)
            self.success_rate = (successful_trades / total_trades) * 100 if total_trades > 0 else 0.0
            
            logger.info(f"📊 Force Trading Success Rate Updated: {self.success_rate:.1f}% "
                       f"({successful_trades}/{total_trades})")
            
        except Exception as e:
            logger.error(f"Error updating success rate: {e}")
