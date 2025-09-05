"""
Smart Profit Taking System (ระบบปิดกำไรอัจฉริยะ)

ระบบปิดไม้แบบกลุ่มที่ฉลาดและมีประสิทธิภาพสูง
- ห้ามปิด Order เดี่ยว - ต้องปิดเป็นกลุ่มเสมอ
- รอ Pullback ก่อนปิดกำไร
- รองรับ Multi-Ratio (1:1, 1:2, 1:3, 2:3, Custom)
- ปรับตัวตามสภาพตลาด (Trending/Ranging/Volatile)
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum
import statistics

logger = logging.getLogger(__name__)

class MarketCondition(Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    VOLATILE = "volatile"
    UNKNOWN = "unknown"

class PullbackStatus(Enum):
    NO_PULLBACK_NEEDED = "no_pullback_needed"
    WAITING_FOR_PULLBACK = "waiting_for_pullback"
    PULLBACK_DETECTED = "pullback_detected"
    PULLBACK_SUFFICIENT = "pullback_sufficient"

@dataclass
class ProfitGroup:
    """กลุ่มไม้สำหรับปิดกำไร"""
    profit_positions: List[Any]  # Position objects
    loss_positions: List[Any]    # Position objects
    total_pnl: float
    total_lots: float
    profit_ratio: str  # เช่น "1:2", "2:3"
    risk_score: float
    group_quality: float
    estimated_margin_freed: float

@dataclass
class PullbackInfo:
    """ข้อมูล Pullback"""
    peak_price: float
    current_price: float
    pullback_percentage: float
    pullback_pips: float
    time_since_peak: float
    status: PullbackStatus

class SmartProfitTakingSystem:
    """ระบบปิดกำไรอัจฉริยะ"""
    
    def __init__(self, mt5_connection, order_manager):
        self.mt5 = mt5_connection
        self.order_manager = order_manager
        
        # Core Settings
        self.min_profit_per_lot = 0.50           # กำไรขั้นต่ำ $0.50 ต่อ lot
        self.min_profit_per_position = 0.10      # กำไรขั้นต่ำ $0.10 ต่อไม้
        self.pullback_threshold_percentage = 1.0  # รอ Pullback 1%
        self.max_positions_per_group = 10         # สูงสุด 10 ไม้ต่อกลุ่ม
        
        # Pullback Override Settings (ตั้งค่าให้ปิดกำไรได้ง่าย)
        self.enable_pullback_override = True      # เปิดใช้การข้าม pullback เมื่อกำไรดี
        self.pullback_override_multiplier = 1.5  # ปิดทันทีเมื่อกำไร >= 1.5x ขั้นต่ำ (ลดจาก 2.0)
        self.disable_pullback_completely = False # ปิดการรอ pullback ทั้งหมด
        
        logger.info(f"⚙️ Smart Profit Taking Settings:")
        logger.info(f"   💰 ขั้นต่ำ: ${self.min_profit_per_lot}/lot, ${self.min_profit_per_position}/position")
        logger.info(f"   ⚡ Pullback Override: {self.enable_pullback_override} (>= {self.pullback_override_multiplier}x)")
        logger.info(f"   ⏳ Pullback Threshold: {self.pullback_threshold_percentage}%")
        
        # Pullback Detection
        self.price_peaks = {}  # เก็บราคา Peak ของแต่ละ symbol
        self.peak_timestamps = {}  # เก็บเวลาที่เกิด Peak
        
        # Performance Tracking
        self.exit_history = []
        self.success_rate = 0.0
        self.total_exits = 0
        self.successful_exits = 0
        
        # Market Condition Settings
        self.market_condition = MarketCondition.UNKNOWN
        self.trending_pullback_threshold = 1.5  # % สำหรับ Trending Market
        self.ranging_pullback_threshold = 0.8   # % สำหรับ Ranging Market
        self.volatile_pullback_threshold = 2.0  # % สำหรับ Volatile Market
        
    def analyze_market_condition(self, current_price: float, symbol: str = "XAUUSD") -> MarketCondition:
        """วิเคราะห์สภาพตลาด"""
        try:
            # ดึงข้อมูลราคา 50 periods ย้อนหลัง
            import MetaTrader5 as mt5
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 50)
            
            if rates is None or len(rates) < 20:
                return MarketCondition.UNKNOWN
                
            # คำนวณ indicators
            closes = [rate['close'] for rate in rates[-20:]]  # ใช้ 20 periods ล่าสุด
            highs = [rate['high'] for rate in rates[-20:]]
            lows = [rate['low'] for rate in rates[-20:]]
            
            # ATR Calculation
            atr_periods = []
            for i in range(1, len(rates[-20:])):
                high_low = highs[i] - lows[i]
                high_close = abs(highs[i] - closes[i-1])
                low_close = abs(lows[i] - closes[i-1])
                true_range = max(high_low, high_close, low_close)
                atr_periods.append(true_range)
            
            avg_atr = statistics.mean(atr_periods) if atr_periods else 0
            current_atr_ratio = (max(highs[-5:]) - min(lows[-5:])) / avg_atr if avg_atr > 0 else 1
            
            # Price Movement Analysis
            price_range = max(closes) - min(closes)
            price_std = statistics.stdev(closes) if len(closes) > 1 else 0
            
            # Trend Strength
            ma_short = statistics.mean(closes[-5:])  # MA 5
            ma_long = statistics.mean(closes[-15:])   # MA 15
            trend_strength = abs(ma_short - ma_long) / ma_long * 100 if ma_long > 0 else 0
            
            # Market Condition Classification
            if current_atr_ratio > 1.5 and price_std > price_range * 0.3:
                condition = MarketCondition.VOLATILE
            elif trend_strength > 0.5 and closes[-10] > 0 and abs(closes[-1] - closes[-10]) / closes[-10] * 100 > 1.0:
                condition = MarketCondition.TRENDING  
            else:
                condition = MarketCondition.RANGING
                
            logger.info(f"📊 Market Analysis: {condition.value.upper()} (Trend: {trend_strength:.2f}%, ATR: {current_atr_ratio:.2f})")
            
            self.market_condition = condition
            return condition
            
        except Exception as e:
            logger.error(f"Error analyzing market condition: {e}")
            return MarketCondition.UNKNOWN
    
    def detect_pullback(self, current_price: float, positions: List[Any], symbol: str = "XAUUSD") -> PullbackInfo:
        """ตรวจจับ Pullback"""
        try:
            # หา highest และ lowest orders
            if not positions:
                return PullbackInfo(
                    peak_price=current_price,
                    current_price=current_price,
                    pullback_percentage=0.0,
                    pullback_pips=0.0,
                    time_since_peak=0.0,
                    status=PullbackStatus.NO_PULLBACK_NEEDED
                )
            
            buy_positions = [pos for pos in positions if pos.type == 0]  # BUY
            sell_positions = [pos for pos in positions if pos.type == 1]  # SELL
            
            if not buy_positions and not sell_positions:
                return PullbackInfo(
                    peak_price=current_price,
                    current_price=current_price, 
                    pullback_percentage=0.0,
                    pullback_pips=0.0,
                    time_since_peak=0.0,
                    status=PullbackStatus.NO_PULLBACK_NEEDED
                )
            
            # หา extreme prices จาก positions
            highest_buy = max([pos.price_open for pos in buy_positions]) if buy_positions else 0
            lowest_sell = min([pos.price_open for pos in sell_positions]) if sell_positions else float('inf')
            
            # อัพเดท peak tracking (เก็บราคาสูงสุดที่เคยเจอ)
            if symbol not in self.price_peaks:
                # ครั้งแรก - ใช้ราคาสูงสุดระหว่าง current_price, highest_buy, lowest_sell
                initial_peak = current_price
                if buy_positions:
                    initial_peak = max(initial_peak, highest_buy)
                if sell_positions and lowest_sell < float('inf'):
                    initial_peak = max(initial_peak, lowest_sell)
                
                self.price_peaks[symbol] = initial_peak
                self.peak_timestamps[symbol] = datetime.now()
                peak_price = initial_peak
            else:
                # อัพเดท peak ถ้าราคาปัจจุบันสูงกว่า
                if current_price > self.price_peaks[symbol]:
                    self.price_peaks[symbol] = current_price
                    self.peak_timestamps[symbol] = datetime.now()
                
                # ใช้ peak ที่เก็บไว้
                peak_price = self.price_peaks[symbol]
            
            # คำนวณ pullback
            pullback_amount = peak_price - current_price
            pullback_percentage = (pullback_amount / peak_price * 100) if peak_price > 0 else 0
            pullback_pips = pullback_amount * 10  # สำหรับ XAUUSD
            
            # Debug logging
            logger.debug(f"🔍 Pullback Calculation:")
            logger.debug(f"   Peak Price: {peak_price:.2f}")
            logger.debug(f"   Current Price: {current_price:.2f}")
            logger.debug(f"   Pullback Amount: {pullback_amount:.2f}")
            logger.debug(f"   Pullback %: {pullback_percentage:.2f}%")
            
            # คำนวณเวลาที่ผ่านไปจาก peak
            time_since_peak = 0.0
            if symbol in self.peak_timestamps:
                time_since_peak = (datetime.now() - self.peak_timestamps[symbol]).total_seconds() / 60  # นาที
            
            # กำหนด pullback threshold ตาม market condition
            threshold = self.pullback_threshold_percentage
            if self.market_condition == MarketCondition.TRENDING:
                threshold = self.trending_pullback_threshold
            elif self.market_condition == MarketCondition.RANGING:
                threshold = self.ranging_pullback_threshold
            elif self.market_condition == MarketCondition.VOLATILE:
                threshold = self.volatile_pullback_threshold
            
            # กำหนดสถานะ pullback
            if pullback_percentage < 0.1:  # ราคายังวิ่งขึ้นหรือเท่าเดิม
                if current_price >= peak_price:
                    status = PullbackStatus.WAITING_FOR_PULLBACK  # ราคายังแรง
                else:
                    status = PullbackStatus.PULLBACK_DETECTED     # เริ่ม pullback แล้ว
            elif pullback_percentage >= threshold:
                status = PullbackStatus.PULLBACK_SUFFICIENT       # pullback เพียงพอแล้ว
            else:
                status = PullbackStatus.PULLBACK_DETECTED         # pullback แต่ยังไม่พอ
            
            return PullbackInfo(
                peak_price=peak_price,
                current_price=current_price,
                pullback_percentage=pullback_percentage,
                pullback_pips=pullback_pips,
                time_since_peak=time_since_peak,
                status=status
            )
            
        except Exception as e:
            logger.error(f"Error detecting pullback: {e}")
            return PullbackInfo(
                peak_price=current_price,
                current_price=current_price,
                pullback_percentage=0.0,
                pullback_pips=0.0,
                time_since_peak=0.0,
                status=PullbackStatus.NO_PULLBACK_NEEDED
            )
    
    def find_optimal_profit_groups(self, positions: List[Any], current_price: float) -> List[ProfitGroup]:
        """หากลุ่มไม้ที่เหมาะสมสำหรับปิดกำไร"""
        try:
            if not positions or len(positions) < 2:
                return []
            
            profit_positions = [pos for pos in positions if pos.profit > 0]
            loss_positions = [pos for pos in positions if pos.profit < 0]
            
            if not profit_positions or not loss_positions:
                logger.info("💡 ไม่มีโอกาสปิดกลุ่ม - ต้องมีทั้งไม้กำไรและขาดทุน")
                return []
            
            # เรียงไม้ตามคุณภาพ
            profit_positions.sort(key=lambda x: x.profit, reverse=True)  # กำไรมาก → น้อย
            loss_positions.sort(key=lambda x: x.profit)  # ขาดทุนมาก → น้อย
            
            groups = []
            
            # สร้างกลุ่มตาม Multi-Ratio
            ratios = [
                (1, 1, "1:1"),  # 1 กำไร : 1 ขาดทุน
                (1, 2, "1:2"),  # 1 กำไร : 2 ขาดทุน
                (1, 3, "1:3"),  # 1 กำไร : 3 ขาดทุน
                (2, 3, "2:3"),  # 2 กำไร : 3 ขาดทุน
                (3, 2, "3:2"),  # 3 กำไร : 2 ขาดทุน
            ]
            
            for profit_count, loss_count, ratio_name in ratios:
                if len(profit_positions) >= profit_count and len(loss_positions) >= loss_count:
                    group_profit = profit_positions[:profit_count]
                    group_loss = loss_positions[:loss_count]
                    
                    # คำนวณ P&L รวม
                    total_pnl = sum(pos.profit for pos in group_profit + group_loss)
                    total_lots = sum(pos.volume for pos in group_profit + group_loss)
                    
                    # คำนวณคะแนนกลุ่ม
                    risk_score = self._calculate_group_risk_score(group_profit, group_loss, current_price)
                    group_quality = self._calculate_group_quality(group_profit, group_loss, total_pnl)
                    
                    # ประมาณการ margin ที่จะได้คืน
                    estimated_margin = self._estimate_margin_freed(group_profit + group_loss)
                    
                    if total_pnl > 0:  # เฉพาะกลุ่มที่มีกำไรรวม
                        group = ProfitGroup(
                            profit_positions=group_profit,
                            loss_positions=group_loss,
                            total_pnl=total_pnl,
                            total_lots=total_lots,
                            profit_ratio=ratio_name,
                            risk_score=risk_score,
                            group_quality=group_quality,
                            estimated_margin_freed=estimated_margin
                        )
                        groups.append(group)
            
            # เรียงตามคุณภาพกลุ่ม
            groups.sort(key=lambda x: (x.group_quality, x.total_pnl), reverse=True)
            
            logger.info(f"🎯 พบกลุ่มปิดกำไร: {len(groups)} กลุ่ม")
            for i, group in enumerate(groups[:3]):  # แสดง top 3
                logger.info(f"   {i+1}. {group.profit_ratio} - P&L: ${group.total_pnl:.2f}, คุณภาพ: {group.group_quality:.1f}")
            
            return groups
            
        except Exception as e:
            logger.error(f"Error finding optimal profit groups: {e}")
            return []
    
    def _calculate_group_risk_score(self, profit_positions: List[Any], loss_positions: List[Any], current_price: float) -> float:
        """คำนวณคะแนนความเสี่ยงของกลุ่ม"""
        try:
            score = 0.0
            
            # 1. Distance Risk (30%) - ไม้ที่ห่างจากราคาปัจจุบันมีความเสี่ยงน้อย
            total_distance = 0.0
            if current_price > 0:  # ป้องกัน division by zero
                for pos in profit_positions + loss_positions:
                    distance = abs(pos.price_open - current_price) / current_price * 100
                    total_distance += distance
            
            avg_distance = total_distance / len(profit_positions + loss_positions) if profit_positions + loss_positions else 0
            distance_score = min(avg_distance * 2, 30.0)
            score += distance_score
            
            # 2. P&L Balance Risk (40%) - สมดุลระหว่างกำไรและขาดทุน
            total_profit = sum(pos.profit for pos in profit_positions) if profit_positions else 0.0
            total_loss = abs(sum(pos.profit for pos in loss_positions)) if loss_positions else 0.0
            
            if total_loss > 0 and total_profit > 0:  # ป้องกัน division by zero
                balance_ratio = total_profit / total_loss
                if 0.8 <= balance_ratio <= 2.0:  # สมดุลดี
                    balance_score = 40.0
                elif 0.5 <= balance_ratio <= 3.0:  # สมดุลปานกลาง
                    balance_score = 25.0
                else:  # ไม่สมดุล
                    balance_score = 10.0
            elif total_profit > 0:  # มีแต่กำไร
                balance_score = 30.0
            elif total_loss > 0:  # มีแต่ขาดทุน
                balance_score = 5.0
            else:  # ไม่มีทั้งคู่
                balance_score = 20.0
            
            score += balance_score
            
            # 3. Age Risk (30%) - ไม้เก่ามีความเสี่ยงน้อย
            current_time = datetime.now()
            total_age_hours = 0.0
            
            for pos in profit_positions + loss_positions:
                try:
                    if hasattr(pos.time_open, 'timestamp'):
                        pos_time = datetime.fromtimestamp(pos.time_open.timestamp())
                    else:
                        pos_time = datetime.fromtimestamp(pos.time_open)
                    
                    age_hours = (current_time - pos_time).total_seconds() / 3600
                    total_age_hours += age_hours
                except:
                    total_age_hours += 1.0  # default 1 hour
            
            avg_age = total_age_hours / len(profit_positions + loss_positions) if profit_positions + loss_positions else 0
            age_score = min(avg_age / 24 * 30, 30.0)  # Max 30 points for 24+ hours
            score += age_score
            
            return score
            
        except Exception as e:
            logger.error(f"Error calculating group risk score: {e}")
            return 0.0
    
    def _calculate_group_quality(self, profit_positions: List[Any], loss_positions: List[Any], total_pnl: float) -> float:
        """คำนวณคุณภาพของกลุ่ม"""
        try:
            quality = 0.0
            
            # 1. P&L Quality (50%)
            if total_pnl > 0:
                total_exposure = sum(abs(pos.profit) for pos in profit_positions + loss_positions)
                pnl_ratio = total_pnl / total_exposure if total_exposure > 0 else 0
                quality += min(pnl_ratio * 100, 50.0)
            
            # 2. Size Balance (30%)
            profit_lots = sum(pos.volume for pos in profit_positions) if profit_positions else 0.0
            loss_lots = sum(pos.volume for pos in loss_positions) if loss_positions else 0.0
            
            if loss_lots > 0 and profit_lots > 0:  # ป้องกัน division by zero
                size_ratio = profit_lots / loss_lots
                if 0.5 <= size_ratio <= 2.0:  # สมดุลดี
                    quality += 30.0
                elif 0.3 <= size_ratio <= 3.0:  # สมดุลปานกลาง
                    quality += 20.0
                else:
                    quality += 10.0
            elif profit_lots > 0:  # มีแต่กำไร
                quality += 25.0
            elif loss_lots > 0:  # มีแต่ขาดทุน
                quality += 5.0
            else:  # ไม่มีทั้งคู่
                quality += 15.0
            
            # 3. Diversification (20%)
            total_positions = len(profit_positions) + len(loss_positions)
            if total_positions >= 4:
                quality += 20.0
            elif total_positions >= 3:
                quality += 15.0
            else:
                quality += 10.0
            
            return quality
            
        except Exception as e:
            logger.error(f"Error calculating group quality: {e}")
            return 0.0
    
    def _estimate_margin_freed(self, positions: List[Any]) -> float:
        """ประมาณการ margin ที่จะได้คืน"""
        try:
            total_margin = 0.0
            for pos in positions:
                # ประมาณการ margin ต่อ lot สำหรับ XAUUSD
                margin_per_lot = 2000.0  # ประมาณ $2000 ต่อ 1 lot
                position_margin = pos.volume * margin_per_lot
                total_margin += position_margin
            
            return total_margin
            
        except Exception as e:
            logger.error(f"Error estimating margin freed: {e}")
            return 0.0
    
    def _calculate_minimum_profit_required(self, profit_group: ProfitGroup) -> float:
        """คำนวณกำไรขั้นต่ำที่ต้องการตามจำนวนไม้และ lot"""
        try:
            total_positions = len(profit_group.profit_positions) + len(profit_group.loss_positions)
            total_lots = profit_group.total_lots
            
            # คำนวณตาม lot (หลัก)
            lot_based_profit = total_lots * self.min_profit_per_lot
            
            # คำนวณตามจำนวนไม้ (รอง)
            position_based_profit = total_positions * self.min_profit_per_position
            
            # ใช้ค่าที่สูงกว่า แต่มี cap สูงสุด
            min_profit = max(lot_based_profit, position_based_profit)
            
            # กำหนดขีดจำกัดสูงสุด (ไม่ให้สูงเกินไป)
            max_profit_cap = 20.0  # สูงสุด $20
            min_profit = min(min_profit, max_profit_cap)
            
            # ขั้นต่ำสุด $0.50
            min_profit = max(min_profit, 0.50)
            
            logger.debug(f"💰 Min Profit Calculation:")
            logger.debug(f"   Positions: {total_positions}, Lots: {total_lots:.2f}")
            logger.debug(f"   Lot-based: ${lot_based_profit:.2f}")
            logger.debug(f"   Position-based: ${position_based_profit:.2f}")
            logger.debug(f"   Required: ${min_profit:.2f}")
            
            return min_profit
            
        except Exception as e:
            logger.error(f"Error calculating minimum profit required: {e}")
            return 1.0  # fallback
    
    def should_execute_profit_taking(self, positions: List[Any], current_price: float, 
                                   account_balance: float) -> Dict[str, Any]:
        """ตรวจสอบว่าควรปิดกำไรหรือไม่"""
        try:
            # 1. วิเคราะห์สภาพตลาด
            market_condition = self.analyze_market_condition(current_price)
            
            # 2. ตรวจจับ Pullback
            pullback_info = self.detect_pullback(current_price, positions)
            
            # 3. หากลุ่มที่เหมาะสม
            profit_groups = self.find_optimal_profit_groups(positions, current_price)
            
            if not profit_groups:
                return {
                    'should_execute': False,
                    'reason': 'ไม่พบกลุ่มที่เหมาะสมสำหรับปิดกำไร',
                    'pullback_status': pullback_info.status.value,
                    'market_condition': market_condition.value
                }
            
            best_group = profit_groups[0]
            
            # 4. ตรวจสอบเงื่อนไข Pullback (ยืดหยุ่นตามการตั้งค่า)
            min_profit_required = self._calculate_minimum_profit_required(best_group)
            profit_margin = best_group.total_pnl / min_profit_required if min_profit_required > 0 else 1.0
            
            # ตรวจสอบการปิด pullback ทั้งหมด
            if self.disable_pullback_completely:
                logger.info(f"⚡ ปิด Pullback ทั้งหมด - ปิดทันทีเมื่อกำไรเป็นบวก")
            # ตรวจสอบการข้าม pullback เมื่อกำไรดี
            elif self.enable_pullback_override and profit_margin >= self.pullback_override_multiplier:
                logger.info(f"💰 กำไรดีมาก ({profit_margin:.1f}x >= {self.pullback_override_multiplier}x) - ข้าม pullback")
            # รอ pullback ตามปกติ
            elif pullback_info.status == PullbackStatus.WAITING_FOR_PULLBACK:
                return {
                    'should_execute': False,
                    'reason': f'รอ Pullback: ราคาวิ่งขึ้น {pullback_info.pullback_percentage:.2f}% (ต้องการ {self.pullback_threshold_percentage:.1f}%) - กำไร: {profit_margin:.1f}x',
                    'pullback_status': pullback_info.status.value,
                    'market_condition': market_condition.value,
                    'best_group': best_group
                }
            
            # 5. ตรวจสอบกำไรขั้นต่ำ (ตาม lot และจำนวนไม้)
            if best_group.total_pnl < min_profit_required:
                total_positions = len(best_group.profit_positions) + len(best_group.loss_positions)
                return {
                    'should_execute': False,
                    'reason': f'กำไรไม่ถึงเกณฑ์: ${best_group.total_pnl:.2f} < ${min_profit_required:.2f} ({total_positions} ไม้, {best_group.total_lots:.2f} lots)',
                    'pullback_status': pullback_info.status.value,
                    'market_condition': market_condition.value,
                    'best_group': best_group
                }
            
            # 6. ผ่านเงื่อนไขทั้งหมด - พร้อมปิดกำไร
            return {
                'should_execute': True,
                'reason': f'พร้อมปิดกำไร: {best_group.profit_ratio} - P&L ${best_group.total_pnl:.2f}',
                'pullback_status': pullback_info.status.value,
                'market_condition': market_condition.value,
                'best_group': best_group,
                'pullback_info': pullback_info
            }
            
        except Exception as e:
            logger.error(f"Error checking profit taking conditions: {e}")
            return {
                'should_execute': False,
                'reason': f'เกิดข้อผิดพลาด: {str(e)}',
                'pullback_status': 'unknown',
                'market_condition': 'unknown'
            }
    
    def execute_profit_taking(self, profit_group: ProfitGroup) -> Dict[str, Any]:
        """ดำเนินการปิดกำไรกลุ่ม"""
        try:
            all_positions = profit_group.profit_positions + profit_group.loss_positions
            tickets = [pos.ticket for pos in all_positions]
            
            logger.info(f"🎯 เริ่มปิดกำไรกลุ่ม {profit_group.profit_ratio}:")
            logger.info(f"   กำไร: {len(profit_group.profit_positions)} ไม้")
            logger.info(f"   ขาดทุน: {len(profit_group.loss_positions)} ไม้")
            logger.info(f"   P&L รวม: ${profit_group.total_pnl:.2f}")
            logger.info(f"   Lots รวม: {profit_group.total_lots}")
            
            # ปิดไม้ทั้งกลุ่ม
            result = self.mt5.close_positions_group_with_spread_check(tickets)
            
            if result['success']:
                # บันทึกประวัติการปิด
                self._record_exit_history(profit_group, result)
                
                # อัพเดทสถิติ
                self.successful_exits += 1
                self.total_exits += 1
                self.success_rate = (self.successful_exits / self.total_exits * 100) if self.total_exits > 0 else 0.0
                
                logger.info(f"✅ ปิดกำไรกลุ่มสำเร็จ: P&L ${profit_group.total_pnl:.2f}")
                logger.info(f"📊 Success Rate: {self.success_rate:.1f}% ({self.successful_exits}/{self.total_exits})")
                
                return {
                    'success': True,
                    'group_closed': profit_group,
                    'actual_pnl': result.get('total_profit', profit_group.total_pnl),
                    'positions_closed': len(tickets),
                    'message': f"ปิดกำไรกลุ่ม {profit_group.profit_ratio} สำเร็จ"
                }
            else:
                self.total_exits += 1
                self.success_rate = (self.successful_exits / self.total_exits * 100) if self.total_exits > 0 else 0.0
                
                logger.warning(f"❌ ปิดกำไรกลุ่มล้มเหลว: {result.get('reason', 'Unknown error')}")
                
                return {
                    'success': False,
                    'reason': result.get('reason', 'Unknown error'),
                    'group_attempted': profit_group,
                    'message': f"ปิดกำไรกลุ่ม {profit_group.profit_ratio} ล้มเหลว"
                }
                
        except Exception as e:
            logger.error(f"Error executing profit taking: {e}")
            return {
                'success': False,
                'error': str(e),
                'message': f"เกิดข้อผิดพลาดในการปิดกำไร: {str(e)}"
            }
    
    def _record_exit_history(self, profit_group: ProfitGroup, result: Dict):
        """บันทึกประวัติการปิดไม้"""
        try:
            exit_record = {
                'timestamp': datetime.now(),
                'profit_ratio': profit_group.profit_ratio,
                'positions_count': len(profit_group.profit_positions) + len(profit_group.loss_positions),
                'total_lots': profit_group.total_lots,
                'planned_pnl': profit_group.total_pnl,
                'actual_pnl': result.get('total_profit', profit_group.total_pnl),
                'group_quality': profit_group.group_quality,
                'risk_score': profit_group.risk_score,
                'success': result['success']
            }
            
            self.exit_history.append(exit_record)
            
            # เก็บแค่ 100 records ล่าสุด
            if len(self.exit_history) > 100:
                self.exit_history = self.exit_history[-100:]
                
        except Exception as e:
            logger.error(f"Error recording exit history: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """ดึงข้อมูลประสิทธิภาพ"""
        try:
            if not self.exit_history:
                return {
                    'total_exits': 0,
                    'success_rate': 0.0,
                    'avg_pnl': 0.0,
                    'total_pnl': 0.0,
                    'avg_group_quality': 0.0
                }
            
            recent_exits = self.exit_history[-20:]  # 20 ครั้งล่าสุด
            
            total_pnl = sum(record['actual_pnl'] for record in recent_exits)
            avg_pnl = total_pnl / len(recent_exits) if recent_exits else 0
            avg_quality = statistics.mean([record['group_quality'] for record in recent_exits])
            
            return {
                'total_exits': self.total_exits,
                'success_rate': self.success_rate,
                'avg_pnl': avg_pnl,
                'total_pnl': total_pnl,
                'avg_group_quality': avg_quality,
                'recent_exits_count': len(recent_exits)
            }
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}
    
    def configure_pullback_behavior(self, 
                                  disable_completely: bool = False,
                                  enable_override: bool = True, 
                                  override_multiplier: float = 2.0,
                                  threshold_percentage: float = 1.0):
        """
        ปรับแต่งพฤติกรรม Pullback
        
        Args:
            disable_completely: ปิดการรอ pullback ทั้งหมด (ปิดทันทีเมื่อกำไรเป็นบวก)
            enable_override: เปิดใช้การข้าม pullback เมื่อกำไรดี
            override_multiplier: ข้าม pullback เมื่อกำไร >= X เท่าของขั้นต่ำ
            threshold_percentage: เปอร์เซ็นต์ pullback ที่ต้องรอ
        """
        self.disable_pullback_completely = disable_completely
        self.enable_pullback_override = enable_override
        self.pullback_override_multiplier = override_multiplier
        self.pullback_threshold_percentage = threshold_percentage
        
        if disable_completely:
            logger.info("⚡ ปิดการรอ Pullback ทั้งหมด - จะปิดทันทีเมื่อกำไรเป็นบวก")
        elif enable_override:
            logger.info(f"💰 เปิดการข้าม Pullback เมื่อกำไร >= {override_multiplier}x ขั้นต่ำ")
        else:
            logger.info(f"⏳ รอ Pullback {threshold_percentage}% ตามปกติ")
