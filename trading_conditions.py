# -*- coding: utf-8 -*-
"""
Trading Conditions Module
โมดูลสำหรับเงื่อนไขการเทรดและการวิเคราะห์สัญญาณ
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
from calculations import Position, PercentageCalculator, MarketAnalysisCalculator
from market_analysis import MarketSessionAnalyzer, MultiTimeframeAnalyzer

logger = logging.getLogger(__name__)

@dataclass
class Signal:
    """คลาสสำหรับเก็บข้อมูลสัญญาณการเทรด"""
    direction: str  # "BUY" หรือ "SELL"
    symbol: str
    strength: float  # แรงของสัญญาณ (0-100)
    confidence: float  # ความมั่นใจ (0-100)
    timestamp: datetime
    price: float
    volume_suggestion: float = 0.01
    stop_loss: float = 0.0
    take_profit: float = 0.0
    comment: str = ""

@dataclass
class CandleData:
    """คลาสสำหรับเก็บข้อมูลแท่งเทียน"""
    open: float
    high: float
    low: float
    close: float
    volume: float
    timestamp: datetime
    symbol: str = "UNKNOWN"  # เพิ่ม symbol field
    
    @property
    def is_green(self) -> bool:
        """ตรวจสอบว่าเป็นแท่งเทียนเขียว (ราคาปิดสูงกว่าราคาเปิด)"""
        return self.close > self.open
        
    @property
    def is_red(self) -> bool:
        """ตรวจสอบว่าเป็นแท่งเทียนแดง (ราคาปิดต่ำกว่าราคาเปิด)"""
        return self.close < self.open
        
    @property
    def body_size_percentage(self) -> float:
        """คำนวณขนาดตัวเทียนเป็นเปอร์เซ็นต์"""
        if self.open == 0:
            return 0.0
        return abs((self.close - self.open) / self.open) * 100
        
    @property
    def range_percentage(self) -> float:
        """คำนวณช่วงราคาของแท่งเทียนเป็นเปอร์เซ็นต์"""
        if self.low == 0:
            return 0.0
        return ((self.high - self.low) / self.low) * 100

class CandleAnalyzer:
    """คลาสสำหรับวิเคราะห์แท่งเทียน"""
    
    def __init__(self, min_strength_percentage: float = 20.0):
        """
        Args:
            min_strength_percentage: เกณฑ์ขั้นต่ำของแรงตลาดเป็นเปอร์เซ็นต์ (ลดจาก 50% เป็น 20%)
        """
        self.min_strength_percentage = min_strength_percentage
        
    def analyze_candle_strength(self, candle: CandleData, volume_avg: float = 0) -> Dict[str, Any]:
        """
        วิเคราะห์แรงของแท่งเทียน
        
        Args:
            candle: ข้อมูลแท่งเทียน
            volume_avg: Volume เฉลี่ย
            
        Returns:
            Dict: ข้อมูลการวิเคราะห์แรง
        """
        # คำนวณแรงจากขนาดตัวเทียน
        body_strength = candle.body_size_percentage
        
        # คำนวณแรงจาก Volume
        volume_strength = 0.0
        if volume_avg > 0:
            volume_ratio = candle.volume / volume_avg
            volume_strength = min(100, volume_ratio * 50)  # แปลงเป็น 0-100
            
        # คำนวณแรงจากช่วงราคา
        range_strength = min(100, candle.range_percentage * 10)
        
        # รวมแรงทั้งหมด
        total_strength = (body_strength * 0.4 + volume_strength * 0.4 + range_strength * 0.2)
        
        return {
            'body_strength': body_strength,
            'volume_strength': volume_strength,
            'range_strength': range_strength,
            'total_strength': total_strength,
            'is_strong': total_strength >= self.min_strength_percentage,
            'direction': self._determine_smart_direction(candle, total_strength)  # HYBRID: Trend + Counter-trend
        }
    
    def _determine_smart_direction(self, candle: CandleData, strength: float) -> str:
        """🎯 HYBRID SIGNAL: Trend + Counter-trend Smart Direction"""
        try:
            # 📊 ตัวชี้วัด Trend
            is_green = candle.is_green
            body_size = candle.body_size_percentage
            range_size = candle.range_percentage
            
            # 🚀 HYBRID LOGIC
            if strength > 70:  # แรงมาก
                if body_size > 60 and range_size > 5:
                    # Trend Following สำหรับสัญญาณแรงมาก
                    return 'BUY' if is_green else 'SELL'
                else:
                    # Counter-trend สำหรับแรงมากแต่ไม่มี momentum
                    return 'SELL' if is_green else 'BUY'
            elif strength > 40:  # แรงปานกลาง
                # Counter-trend เป็นหลัก (กลยุทธ์เดิม)
                return 'SELL' if is_green else 'BUY'
            else:  # แรงน้อย
                if body_size > 40:
                    # Trend Following สำหรับ momentum เล็กๆ
                    return 'BUY' if is_green else 'SELL'
                else:
                    # Counter-trend ปกติ
                    return 'SELL' if is_green else 'BUY'
                    
        except Exception as e:
            logger.error(f"Error determining direction: {e}")
            return 'SELL' if candle.is_green else 'BUY'  # Fallback to counter-trend
        
    def check_volume_filter(self, current_volume: float, volume_history: List[float], 
                           min_volume_percentage: float = 120.0) -> bool:
        """
        ตรวจสอบ Volume Filter
        
        Args:
            current_volume: Volume ปัจจุบัน
            volume_history: ประวัติ Volume
            min_volume_percentage: เกณฑ์ขั้นต่ำของ Volume เป็นเปอร์เซ็นต์
            
        Returns:
            bool: ผ่านเกณฑ์ Volume หรือไม่
        """
        if not volume_history:
            return True  # ไม่มีข้อมูลเปรียบเทียบ
            
        avg_volume = sum(volume_history) / len(volume_history)
        if avg_volume == 0:
            return True
            
        volume_percentage = (current_volume / avg_volume) * 100
        return volume_percentage >= min_volume_percentage

class TradingConditions:
    """คลาสสำหรับตรวจสอบเงื่อนไขการเทรด"""
    
    def __init__(self):
        self.candle_analyzer = CandleAnalyzer()
        self.last_candle_time = None
        self.orders_per_candle = {}  # เก็บจำนวน order ต่อแท่งเทียน
        self.previous_candle_close = None  # เก็บราคาปิดแท่งก่อนหน้า
        
        # เพิ่ม Market Analysis
        self.session_analyzer = MarketSessionAnalyzer()
        self.mtf_analyzer = None  # จะถูกตั้งค่าเมื่อใช้งาน
        
    def check_entry_conditions(self, candle: CandleData, positions: List[Position], 
                             account_balance: float, volume_history: List[float] = None, 
                             symbol: str = None) -> Dict[str, Any]:
        """
        ตรวจสอบเงื่อนไขการเข้า Order
        
        Args:
            candle: ข้อมูลแท่งเทียนปัจจุบัน
            positions: รายการ Position ปัจจุบัน
            account_balance: ยอดเงินในบัญชี
            volume_history: ประวัติ Volume
            
        Returns:
            Dict: ผลการตรวจสอบเงื่อนไข
        """
        result = {
            'can_enter': False,
            'signal': None,
            'reasons': []
        }
        
        # 🚀 Initialize Force Balance Mode (ต้องอยู่ก่อนการใช้งาน)
        force_balance_mode = False
        
        logger.info(f"🔍 ตรวจสอบเงื่อนไขการเข้าเทรด - Symbol: {symbol}")
        logger.info(f"   Candle: O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}")
        logger.info(f"   Volume: {candle.volume}, Balance: {account_balance:,.2f}")
        
        # 🚀 HIGH-FREQUENCY ENTRY: Smart Entry Control แทน One Order per Candle
        candle_time_key = candle.timestamp.strftime("%Y%m%d%H%M")
        minute_key = candle.timestamp.strftime("%Y%m%d%H%M")
        
        # ตรวจสอบจำนวน orders ต่อนาที (แทน per candle)
        orders_this_minute = self.orders_per_candle.get(minute_key, 0)
        
        # 🧠 Adaptive Entry Limits ตามสภาพตลาด
        volatility_factor = self._calculate_market_volatility(candle)
        max_entries_per_minute = self._get_adaptive_entry_limit(volatility_factor, len(positions))
        
        if orders_this_minute >= max_entries_per_minute:
            result['reasons'].append(f"Entry limit reached: {orders_this_minute}/{max_entries_per_minute} per minute")
            logger.info(f"⚠️ Entry limit: {orders_this_minute}/{max_entries_per_minute} entries this minute")
            return result
        
        logger.info(f"✅ High-Frequency OK: {orders_this_minute}/{max_entries_per_minute} entries this minute")
            
        # 2. Market Session Analysis
        session_params = self.session_analyzer.adjust_trading_parameters({
            'base_strength_threshold': 20.0,
            'base_max_positions': 4,
            'base_lot_multiplier': 1.0
        })
        
        # 3. Multi-Timeframe Confirmation  
        # 🎯 FIXED: Counter-trend logic - ซื้อถูก ขายแพง
        if candle.close > candle.open:  # แท่งเขียว = ราคาขึ้น
            direction = "SELL"  # ขายตอนราคาสูง (ขายแพง)
        else:  # แท่งแดง = ราคาลง
            direction = "BUY"   # ซื้อตอนราคาต่ำ (ซื้อถูก)
        
        # Initialize mtf_analyzer with actual symbol if not done
        if self.mtf_analyzer is None and symbol:
            from market_analysis import MultiTimeframeAnalyzer
            self.mtf_analyzer = MultiTimeframeAnalyzer(symbol)
        
        mtf_result = self.mtf_analyzer.get_multi_timeframe_confirmation(direction) if self.mtf_analyzer else {'decision': 'WEAK'}
        mtf_decision = mtf_result['decision']
        
        # 4. ตรวจสอบแรงตลาดแบบยืดหยุ่น
        volume_avg = sum(volume_history) / len(volume_history) if volume_history else 0
        strength_analysis = self.candle_analyzer.analyze_candle_strength(candle, volume_avg)
        
        logger.info(f"   Session: {session_params['current_session']} (Threshold: {session_params['entry_threshold']}%)")
        logger.info(f"   Multi-TF Score: {mtf_result['confidence_score']}/100 ({mtf_decision['confidence']})")
        logger.info(f"   แรงตลาด: {strength_analysis['total_strength']:.2f}%")
        logger.info(f"   ทิศทาง: {strength_analysis['direction']}")
        
        # เงื่อนไขยืดหยุ่น: ตรวจสอบแท่งเทียนเต็มแท่งหรือปิดสูงกว่าแท่งก่อนหน้า
        flexible_conditions = self._check_flexible_entry_conditions(candle, positions)
        
        # ตัดสินใจเข้าเทรดแบบยืดหยุ่น
        can_enter_analysis = False
        entry_reason = ""
        
        if flexible_conditions['can_enter']:
            can_enter_analysis = True
            entry_reason = f"เงื่อนไขยืดหยุ่น - {flexible_conditions['reason']}"
            strength_analysis['direction'] = flexible_conditions['direction']
            strength_analysis['is_strong'] = True
            strength_analysis['total_strength'] = 30.0
        elif mtf_decision['action'] != 'WAIT':
            can_enter_analysis = True
            entry_reason = f"Multi-Timeframe ยืนยัน ({mtf_decision['confidence']}, Score: {mtf_result['confidence_score']})"
            strength_analysis['is_strong'] = True
            strength_analysis['total_strength'] = max(30.0, mtf_result['confidence_score'] / 2)
        elif strength_analysis['is_strong'] or strength_analysis['total_strength'] >= session_params['entry_threshold']:
            can_enter_analysis = True
            entry_reason = f"แรงตลาดเพียงพอ ({strength_analysis['total_strength']:.2f}% >= {session_params['entry_threshold']}%)"
        else:
            # 🚀 UNLIMITED ENTRY: ผ่อนปรนเงื่อนไขให้เทรดได้ต่อ
            can_enter_analysis = True
            if session_params['current_session'] in ['OVERLAP_LONDON_NY', 'LONDON'] and strength_analysis['total_strength'] >= 10.0:
                entry_reason = f"Session สูง + แรงตลาดพอใช้ ({strength_analysis['total_strength']:.2f}%)"
                strength_analysis['total_strength'] = 15.0  # ให้คะแนนขั้นต่ำ
            else:
                entry_reason = f"🚀 UNLIMITED ENTRY: ยอมรับแรงตลาดต่ำ ({strength_analysis['total_strength']:.2f}%) เพื่อเทรดต่อเนื่อง"
                strength_analysis['total_strength'] = 10.0  # ให้คะแนนขั้นต่ำ
                logger.info(f"🚀 เงื่อนไข 2: {entry_reason}")
        
        logger.info(f"✅ เงื่อนไข 2: {entry_reason}")
            
        # 3. ตรวจสอบ Volume Filter (ปิดชั่วคราว)
        # if volume_history and not self.candle_analyzer.check_volume_filter(candle.volume, volume_history):
        #     result['reasons'].append("Volume ต่ำกว่าเกณฑ์")
        #     logger.info(f"❌ เงื่อนไข 3: {result['reasons'][-1]}")
        #     return result
        # else:
        logger.info(f"✅ เงื่อนไข 3: Volume เพียงพอ (ข้าม Volume Filter)")
            
        # 4. ตรวจสอบสมดุลพอร์ต
        balance_check = self._check_portfolio_balance(positions, strength_analysis['direction'], force_balance_mode)
        if not balance_check['can_enter']:
            result['reasons'].extend(balance_check['reasons'])
            logger.info(f"❌ เงื่อนไข 4: {'; '.join(balance_check['reasons'])}")
            return result
        else:
            logger.info(f"✅ เงื่อนไข 4: สมดุลพอร์ตเหมาะสม")
            
        # 5. ตรวจสอบการใช้เงินทุน (ปิดใช้งาน - ขัดกับ Recovery Systems)
        # exposure_check = self._check_capital_exposure(positions, account_balance)
        # if not exposure_check['can_enter']:
        #     result['reasons'].extend(exposure_check['reasons'])
        #     logger.info(f"❌ เงื่อนไข 5: {'; '.join(exposure_check['reasons'])}")
        #     return result
        # else:
        logger.info(f"✅ เงื่อนไข 5: การใช้เงินทุน (ปิดการตรวจสอบ - เพื่อ Recovery Systems)")
            
        # 🛡️ Entry Price Validation - ป้องกันการเข้าไม้ในราคาผิด
        entry_price = candle.close
        price_validation = self._validate_entry_price(strength_analysis['direction'], entry_price, candle.close)
        if not price_validation['valid']:
            result['can_enter'] = False
            result['reasons'].append(f"Entry price invalid: {price_validation['reason']}")
            result['signal'] = None
            return result
        
        # 🗑️ Portfolio Quality Check REMOVED - ให้ระบบเข้าไม้ได้เสมอ
        # เพื่อไม่ให้พอร์ตแย่ยิ่งแย่หนัก จากการไม่ออกไม้

        # 🚀 Adaptive Entry Control - ENHANCED for Balance Enforcement
        adaptive_control = self._check_adaptive_entry_control(positions, candle.close, strength_analysis['direction'])
        
        if adaptive_control['force_trade']:
            # บังคับ Counter-Trade เพื่อแก้สมดุล Portfolio
            strength_analysis['direction'] = adaptive_control['forced_direction']
            force_balance_mode = True  # เปิดโหมดบังคับ Balance
            logger.info(f"🚀 Adaptive Force Trade: {adaptive_control['reason']}")
            logger.info(f"🛡️ FORCE BALANCE MODE: ข้ามเงื่อนไขบางข้อเพื่อแก้สมดุล")
        elif adaptive_control['should_block']:
            # บล็อคการเข้าที่ทำให้ไม่ Balance มากขึ้น
            result['can_enter'] = False
            result['reasons'].append(adaptive_control['reason'])
            result['signal'] = None
            logger.warning(f"❌ BLOCKED: {adaptive_control['reason']}")
            return result

        # 🛡️ Dynamic Zone Protection - DISABLED for Zone-Based System
        # เดิมจะบล็อคการเข้าไม้ ตอนนี้ให้ Zone System จัดการแทน
        dynamic_zone_check = self._check_dynamic_zone_protection(positions, candle.close, strength_analysis['direction'])
        if dynamic_zone_check['force_counter_trade'] and not adaptive_control['force_trade']:
            # แสดงคำเตือนแต่ไม่บังคับเปลี่ยนทิศทาง
            logger.info(f"🛡️ Dynamic Zone Info: Would suggest {dynamic_zone_check['forced_direction']} - {dynamic_zone_check['reason']}")
            # ไม่เปลี่ยน direction ให้ Zone System ตัดสินใจ
        elif not dynamic_zone_check['can_enter'] and not adaptive_control['force_trade']:
            # แสดงคำเตือนแต่ไม่บล็อค
            logger.warning(f"⚠️ Dynamic Zone Warning: {dynamic_zone_check['reason']} - Let Zone System decide")
            # ไม่ return ให้ดำเนินการต่อ

        # สร้างสัญญาณการเทรด
        signal = Signal(
            direction=strength_analysis['direction'],
            symbol=symbol,  # ใช้ symbol ที่ส่งมา
            strength=strength_analysis['total_strength'],
            confidence=self._calculate_signal_confidence(strength_analysis, balance_check),
            timestamp=candle.timestamp,
            price=entry_price,
            comment=f"Validated signal: {strength_analysis['direction']} at {entry_price}"
        )
        
        # ผ่านทุกเงื่อนไข
        logger.info(f"🎉 ผ่านทุกเงื่อนไขการเข้าเทรด!")
        logger.info(f"   Signal: {signal.direction} {signal.symbol} @ {signal.price:.2f}")
        logger.info(f"   Strength: {signal.strength:.2f}%, Confidence: {signal.confidence:.2f}%")
        
        result['can_enter'] = True
        result['signal'] = signal
        result['reasons'].append("ผ่านเงื่อนไขการเข้าทั้งหมด")
        
        return result
        
    def _check_flexible_entry_conditions(self, candle: CandleData, positions: List[Position]) -> Dict[str, Any]:
        """
        ตรวจสอบเงื่อนไขการเข้าแบบยืดหยุ่น
        
        Args:
            candle: ข้อมูลแท่งเทียนปัจจุบัน
            positions: รายการ Position ปัจจุบัน
            
        Returns:
            Dict: ผลการตรวจสอบเงื่อนไขยืดหยุ่น
        """
        result = {
            'can_enter': False,
            'direction': None,
            'reason': ''
        }
        
        # เงื่อนไข 1: แท่งเทียนเต็มแท่ง (body ≥ 70% ของ range)
        candle_range = candle.high - candle.low
        candle_body = abs(candle.close - candle.open)
        
        if candle_range > 0:
            body_ratio = candle_body / candle_range
            if body_ratio >= 0.7:  # body ≥ 70% ของ range
                result['can_enter'] = True
                # 🎯 FIXED: Counter-trend logic - ซื้อถูก ขายแพง
                if candle.is_green:  # แท่งเขียว = ราคาขึ้น
                    result['direction'] = 'SELL'  # ขายตอนราคาสูง
                else:  # แท่งแดง = ราคาลง
                    result['direction'] = 'BUY'   # ซื้อตอนราคาต่ำ
                result['reason'] = f"แท่งเทียนเต็มแท่ง (body {body_ratio*100:.1f}% ของ range)"
                logger.info(f"🎯 เงื่อนไขยืดหยุ่น: {result['reason']}")
                return result
        
        # เงื่อนไข 2: ปิดสูงกว่าหรือต่ำกว่าแท่งก่อนหน้า (ต้องมีข้อมูลเปรียบเทียบ)
        # สำหรับตอนนี้ใช้การเปรียบเทียบแบบง่าย
        if hasattr(self, 'previous_candle_close') and self.previous_candle_close:
            price_change_pct = ((candle.close - self.previous_candle_close) / self.previous_candle_close) * 100
            
            # ถ้าราคาเปลี่ยนแปลง ≥ 0.02% (สำหรับทองคำ)
            if abs(price_change_pct) >= 0.02:
                result['can_enter'] = True
                # 🎯 FIXED: Counter-trend logic - ซื้อถูก ขายแพง
                if price_change_pct > 0:  # ราคาขึ้น
                    result['direction'] = 'SELL'  # ขายตอนราคาสูง
                else:  # ราคาลง
                    result['direction'] = 'BUY'   # ซื้อตอนราคาต่ำ
                result['reason'] = f"ปิด{'สูงกว่า' if price_change_pct > 0 else 'ต่ำกว่า'}แท่งก่อนหน้า ({price_change_pct:+.3f}%)"
                logger.info(f"🎯 เงื่อนไขยืดหยุ่น: {result['reason']}")
                
        # บันทึกราคาปิดสำหรับแท่งถัดไป
        self.previous_candle_close = candle.close
        
        if not result['can_enter']:
            logger.info(f"⏸️ ไม่ผ่านเงื่อนไขยืดหยุ่น")
            
        return result
        
    def _check_portfolio_balance(self, positions: List[Position], direction: str, force_balance_mode: bool = False) -> Dict[str, Any]:
        """
        ตรวจสอบสมดุลพอร์ตแบบ Zone-Based (100 จุด = 10 pips)
        
        Args:
            positions: รายการ Position
            direction: ทิศทางที่จะเทรด
            
        Returns:
            Dict: ผลการตรวจสอบสมดุล
        """
        result = {
            'can_enter': True,
            'reasons': []
        }
        
        if not positions:
            return result
            
        # 🎯 Zone-Based Balance Check (100 points = 10 pips per zone)
        zone_balance = self._analyze_zone_balance(positions, direction)
        
        # ถ้ามี position น้อยกว่า 5 ตัว ไม่เช็คสมดุล zone
        if len(positions) < 5:
            logger.info(f"💡 มี Position {len(positions)} ตัว - ข้ามการเช็ค Zone Balance")
        else:
            # เช็คสมดุล zone เมื่อมี position หลายตัว
            current_zone = zone_balance['current_zone']
            zone_imbalance = zone_balance['zone_imbalance']
            
            # ถ้า zone ปัจจุบันไม่สมดุล (เกิน 3 zones)
            if zone_imbalance > 3:
                if direction == "BUY" and zone_balance['buy_heavy']:
                    result['can_enter'] = False
                    result['reasons'].append(f"Zone {current_zone} BUY heavy: {zone_imbalance} zones imbalance")
                elif direction == "SELL" and zone_balance['sell_heavy']:
                    result['can_enter'] = False
                    result['reasons'].append(f"Zone {current_zone} SELL heavy: {zone_imbalance} zones imbalance")
                    
        # ตรวจสอบ Price Hierarchy Rule (ซื้อถูกขายแพง) - ข้ามเมื่อ Force Balance
        if not force_balance_mode:  # เช็คเฉพาะเมื่อไม่ใช่โหมดบังคับ Balance
            hierarchy_check = self._check_price_hierarchy(positions, direction)
            if not hierarchy_check['valid']:
                result['can_enter'] = False
                result['reasons'].append(hierarchy_check['reason'])
        else:
            logger.info(f"🛡️ FORCE BALANCE: ข้าม Price Hierarchy check เพื่อแก้สมดุล")
            
        return result
    
    def _analyze_zone_balance(self, positions: List[Position], direction: str) -> Dict[str, Any]:
        """
        🎯 วิเคราะห์สมดุลแบบ Zone-Based (100 จุด = 10 pips ต่อ zone)
        
        Args:
            positions: รายการ positions
            direction: ทิศทางที่จะเทรด
            
        Returns:
            Dict: ผลการวิเคราะห์ zone balance
        """
        if not positions:
            return {'current_zone': 0, 'zone_imbalance': 0, 'buy_heavy': False, 'sell_heavy': False}
        
        # หาราคาปัจจุบัน (ใช้ราคาเฉลี่ยจาก positions)
        current_price = sum(pos.price_open for pos in positions) / len(positions)
        
        # แบ่ง positions เป็น zones (100 points = 10 pips per zone)
        zone_size = 1.0  # 100 points = 1.0 price units สำหรับ XAUUSD
        zones = {}
        
        for pos in positions:
            # คำนวณ zone number จากราคา
            zone_num = int(pos.price_open / zone_size)
            
            if zone_num not in zones:
                zones[zone_num] = {'BUY': 0, 'SELL': 0, 'total': 0}
            
            pos_type = "BUY" if pos.type == 0 else "SELL"
            zones[zone_num][pos_type] += 1
            zones[zone_num]['total'] += 1
        
        # หา zone ปัจจุบัน
        current_zone = int(current_price / zone_size)
        
        # วิเคราะห์ความไม่สมดุล
        max_imbalance = 0
        buy_heavy = False
        sell_heavy = False
        
        for zone_num, counts in zones.items():
            if counts['total'] >= 3:  # เช็คเฉพาะ zone ที่มี positions >= 3 ตัว
                buy_ratio = counts['BUY'] / counts['total']
                sell_ratio = counts['SELL'] / counts['total']
                
                # คำนวณความไม่สมดุล (0.8 = 80%)
                if buy_ratio >= 0.8:
                    imbalance = abs(zone_num - current_zone)
                    if imbalance > max_imbalance:
                        max_imbalance = imbalance
                        buy_heavy = True
                        sell_heavy = False
                elif sell_ratio >= 0.8:
                    imbalance = abs(zone_num - current_zone)
                    if imbalance > max_imbalance:
                        max_imbalance = imbalance
                        buy_heavy = False
                        sell_heavy = True
        
        return {
            'current_zone': current_zone,
            'zone_imbalance': max_imbalance,
            'buy_heavy': buy_heavy,
            'sell_heavy': sell_heavy,
            'total_zones': len(zones)
        }
    
    def _check_price_hierarchy(self, positions: List[Position], direction: str) -> Dict[str, Any]:
        """
        ตรวจสอบ Price Hierarchy Rule
        Buy Orders ต้องอยู่ต่ำกว่า Sell Orders เสมอ
        แต่อนุญาตเมื่อเกิด Breakout หรือมี Continuous Trading
        
        Args:
            positions: รายการ Position
            direction: ทิศทางที่จะเทรด
            
        Returns:
            Dict: ผลการตรวจสอบ
        """
        if not positions:
            return {'valid': True, 'reason': ''}
            
        buy_prices = [pos.price_open for pos in positions if pos.type == 0]  # BUY
        sell_prices = [pos.price_open for pos in positions if pos.type == 1]  # SELL
        
        if not buy_prices or not sell_prices:
            return {'valid': True, 'reason': ''}
            
        max_buy_price = max(buy_prices)
        min_sell_price = min(sell_prices)
        
        if max_buy_price >= min_sell_price:
            # ตรวจสอบว่าเป็น Breakout Scenario หรือไม่
            gap_pips = (max_buy_price - min_sell_price) * 10  # แปลงเป็น pips
            
            # เข้มงวดกว่า: อนุญาตถ้า gap ไม่ใหญ่มาก (< 50 pips = 500 จุด)
            if gap_pips < 50.0:  # ลดจาก 150 เป็น 50 pips เพื่อให้เหมาะกับ 10 pips spacing
                logger.info(f"⚡ Price Hierarchy Override: Gap={gap_pips:.1f} pips ({gap_pips*10:.0f} จุด) - Normal Trading")
                return {'valid': True, 'reason': f'Acceptable gap - {gap_pips:.1f} pips < 50 pips'}
            
            # อนุญาตถ้ามี positions น้อย (< 10 ไม้) - เพิ่มจาก 5 เป็น 10
            if len(positions) < 10:
                logger.info(f"⚡ Price Hierarchy Override: Only {len(positions)} positions (Allow flexibility)")
                return {'valid': True, 'reason': f'Few positions ({len(positions)}) - Allow flexibility'}
            
            # อนุญาตถ้ามี positions เยอะมาก (> 15 ไม้) - เพื่อ recovery
            if len(positions) > 15:
                logger.info(f"⚡ Price Hierarchy Override: Many positions ({len(positions)}) - Recovery mode")
                return {'valid': True, 'reason': f'Many positions ({len(positions)}) - Recovery priority'}
            
            return {
                'valid': False,
                'reason': f'Price hierarchy violated: Max BUY ({max_buy_price}) >= Min SELL ({min_sell_price}) - Gap: {gap_pips:.1f} pips'
            }
            
        return {'valid': True, 'reason': ''}
    
    def _check_dynamic_zone_protection(self, positions: List[Position], current_price: float, direction: str) -> Dict[str, Any]:
        """
        🛡️ ระบบป้องกัน Price Inversion แบบ Dynamic Zone
        
        Args:
            positions: รายการ positions ปัจจุบัน
            current_price: ราคาปัจจุบัน
            direction: ทิศทางที่ต้องการเทรด
            
        Returns:
            Dict: ผลการตรวจสอบ Dynamic Zone
        """
        result = {
            'can_enter': True,
            'force_counter_trade': False,
            'forced_direction': direction,
            'reason': ''
        }
        
        if not positions or len(positions) < 3:
            return result
            
        # คำนวณขอบเขต zones
        zone_boundaries = self._calculate_zone_boundaries(positions)
        
        # ตรวจสอบ Force Counter Trade
        force_check = self._should_force_counter_trade(positions, current_price, zone_boundaries)
        
        if force_check['should_force']:
            result['force_counter_trade'] = True
            result['forced_direction'] = force_check['forced_direction']
            result['reason'] = force_check['reason']
            return result
            
        # ตรวจสอบการบล็อคการเทรดในโซนอันตราย
        if self._is_in_danger_zone(current_price, zone_boundaries, direction):
            result['can_enter'] = False
            result['reason'] = f"Price in danger zone for {direction} at {current_price:.2f}"
            
        return result
    
    def _calculate_zone_boundaries(self, positions: List[Position]) -> Dict[str, float]:
        """📊 คำนวณขอบเขต Upper/Lower Zone"""
        buy_positions = [pos for pos in positions if pos.type == 0]  # BUY
        sell_positions = [pos for pos in positions if pos.type == 1]  # SELL
        
        zone_buffer = 20.0  # 200 pips = 20.0 points สำหรับ XAUUSD
        
        boundaries = {
            'upper_zone_start': 0.0,
            'lower_zone_start': 0.0,
            'safe_range_top': 0.0,
            'safe_range_bottom': 0.0
        }
        
        if sell_positions:
            max_sell_price = max(pos.price_open for pos in sell_positions)
            boundaries['upper_zone_start'] = max_sell_price + zone_buffer
            boundaries['safe_range_top'] = max_sell_price + (zone_buffer * 0.5)
            
        if buy_positions:
            min_buy_price = min(pos.price_open for pos in buy_positions)
            boundaries['lower_zone_start'] = min_buy_price - zone_buffer
            boundaries['safe_range_bottom'] = min_buy_price - (zone_buffer * 0.5)
            
        return boundaries
    
    def _should_force_counter_trade(self, positions: List[Position], current_price: float, boundaries: Dict[str, float]) -> Dict[str, Any]:
        """⚡ ตรวจสอบว่าต้อง Force Trade หรือไม่"""
        result = {
            'should_force': False,
            'forced_direction': '',
            'reason': ''
        }
        
        # ตรวจสอบ Upper Zone (ราคาสูงเกินไป → บังคับ SELL)
        if boundaries['upper_zone_start'] > 0 and current_price >= boundaries['upper_zone_start']:
            # เช็คว่ามี SELL ในโซนนี้หรือไม่
            sell_positions = [pos for pos in positions if pos.type == 1 and pos.price_open >= boundaries['upper_zone_start']]
            
            if not sell_positions:  # ไม่มี SELL ในโซนบน → บังคับ SELL
                result['should_force'] = True
                result['forced_direction'] = 'SELL'
                result['reason'] = f"Force SELL: Price {current_price:.2f} above upper zone {boundaries['upper_zone_start']:.2f}, no SELL positions in zone"
                
        # ตรวจสอบ Lower Zone (ราคาต่ำเกินไป → บังคับ BUY)
        elif boundaries['lower_zone_start'] > 0 and current_price <= boundaries['lower_zone_start']:
            # เช็คว่ามี BUY ในโซนนี้หรือไม่
            buy_positions = [pos for pos in positions if pos.type == 0 and pos.price_open <= boundaries['lower_zone_start']]
            
            if not buy_positions:  # ไม่มี BUY ในโซนล่าง → บังคับ BUY
                result['should_force'] = True
                result['forced_direction'] = 'BUY'
                result['reason'] = f"Force BUY: Price {current_price:.2f} below lower zone {boundaries['lower_zone_start']:.2f}, no BUY positions in zone"
                
        return result
    
    def _is_in_danger_zone(self, current_price: float, boundaries: Dict[str, float], direction: str) -> bool:
        """🚨 ตรวจสอบว่าอยู่ในโซนอันตรายหรือไม่"""
        # สำหรับตอนนี้ไม่บล็อค เพื่อให้ระบบยืดหยุ่น
        # สามารถเพิ่มเงื่อนไขเพิ่มเติมได้ในอนาคต
        return False
        
    def _check_capital_exposure(self, positions: List[Position], account_balance: float, 
                               max_exposure_percentage: float = 65.0) -> Dict[str, Any]:
        """
        ตรวจสอบการใช้เงินทุน
        
        Args:
            positions: รายการ Position
            account_balance: ยอดเงินในบัญชี
            max_exposure_percentage: เปอร์เซ็นต์การใช้เงินทุนสูงสุด
            
        Returns:
            Dict: ผลการตรวจสอบ
        """
        result = {
            'can_enter': True,
            'reasons': []
        }
        
        if not positions:
            return result
            
        exposure_percentage = PercentageCalculator.calculate_portfolio_exposure_percentage(
            positions, account_balance
        )
        
        # ยืดหยุ่นขึ้น: อนุญาตให้เกิน 5% ถ้ามี positions น้อย
        total_positions = len(positions)
        flexible_limit = max_exposure_percentage
        
        # ถ้ามี positions น้อย ให้ยืดหยุ่นขึ้น
        if total_positions <= 3:
            flexible_limit = max_exposure_percentage + 10  # เพิ่ม 10%
        elif total_positions <= 5:
            flexible_limit = max_exposure_percentage + 5   # เพิ่ม 5%
        
        if exposure_percentage >= flexible_limit:
            result['can_enter'] = False
            result['reasons'].append(
                f"การใช้เงินทุนเกิน {flexible_limit}% ({exposure_percentage:.1f}%) - Positions: {total_positions}"
            )
        elif exposure_percentage >= max_exposure_percentage:
            # แจ้งเตือนแต่ยังอนุญาต
            logger.warning(f"⚠️ การใช้เงินทุนใกล้เกิน: {exposure_percentage:.1f}% (ขีดจำกัด {max_exposure_percentage}%)")
        
        return result
        
    def _calculate_signal_confidence(self, strength_analysis: Dict, balance_check: Dict) -> float:
        """
        คำนวณความมั่นใจของสัญญาณ
        
        Args:
            strength_analysis: ข้อมูลการวิเคราะห์แรง
            balance_check: ข้อมูลการตรวจสอบสมดุล
            
        Returns:
            float: ความมั่นใจ (0-100)
        """
        base_confidence = strength_analysis['total_strength']
        
        # ปรับตามสมดุลพอร์ต
        if balance_check['can_enter']:
            balance_bonus = 20.0
        else:
            balance_bonus = 0.0
            
        # ปรับตาม Volume
        volume_bonus = strength_analysis['volume_strength'] * 0.2
        
        total_confidence = min(100, base_confidence + balance_bonus + volume_bonus)
        return total_confidence
        
    def check_exit_conditions(self, positions: List[Position], account_balance: float,
                            current_prices: Dict[str, float]) -> Dict[str, Any]:
        """
        ตรวจสอบเงื่อนไขการปิด Orders
        
        Args:
            positions: รายการ Position
            account_balance: ยอดเงินในบัญชี
            current_prices: ราคาปัจจุบันของสัญลักษณ์ต่างๆ
            
        Returns:
            Dict: ผลการตรวจสอบเงื่อนไขการปิด
        """
        result = {
            'should_exit': False,
            'exit_type': '',
            'positions_to_close': [],
            'reasons': []
        }
        
        if not positions:
            return result
            
        # 🗑️ ALL EXIT LOGIC REMOVED - Now handled by Smart Profit Taking System
        logger.debug("🗑️ Exit conditions removed - all exits handled by Smart Profit Taking System")
        return {
            'should_exit': False,
            'reason': 'Exit conditions removed - using Smart Profit Taking System only',
            'exit_type': None
        }
        
    def _validate_entry_price(self, direction: str, entry_price: float, current_price: float) -> Dict[str, Any]:
        """
        🛡️ ตรวจสอบราคาเข้าไม้ให้ถูกต้อง - ป้องกันการซื้อแพงขายถูก
        
        Args:
            direction: ทิศทางการเทรด BUY/SELL
            entry_price: ราคาที่จะเข้าไม้
            current_price: ราคาปัจจุบัน
            
        Returns:
            Dict: ผลการตรวจสอบ
        """
        result = {'valid': True, 'reason': 'Price validation passed'}
        
        try:
            if direction == "BUY":
                # BUY ต้องซื้อถูกกว่าราคาปัจจุบัน (หรือเท่ากัน)
                if entry_price > current_price:
                    result['valid'] = False
                    result['reason'] = f"BUY price {entry_price:.2f} > current {current_price:.2f} (would buy expensive)"
                    
            elif direction == "SELL":
                # SELL ต้องขายแพงกว่าราคาปัจจุบัน (หรือเท่ากัน)
                if entry_price < current_price:
                    result['valid'] = False
                    result['reason'] = f"SELL price {entry_price:.2f} < current {current_price:.2f} (would sell cheap)"
                    
        except Exception as e:
            result['valid'] = False
            result['reason'] = f"Price validation error: {e}"
            
        return result
    
    def _assess_portfolio_quality(self, positions: List[Position], current_price: float) -> Dict[str, Any]:
        """
        🔍 ประเมินคุณภาพไม้ในพอร์ต - ดูว่าไม้อยู่ในตำแหน่งที่ดีหรือไม่
        
        Args:
            positions: รายการ positions
            current_price: ราคาปัจจุบัน
            
        Returns:
            Dict: ผลการประเมิน
        """
        result = {
            'total_positions': 0,
            'good_positions': 0,
            'bad_positions': 0,
            'good_position_ratio': 0.0,
            'bad_position_ratio': 0.0,
            'quality_score': 0.0
        }
        
        try:
            if not positions:
                result['quality_score'] = 100.0  # พอร์ตว่าง = คุณภาพดี
                return result
                
            total_positions = len(positions)
            good_positions = 0
            bad_positions = 0
            
            for pos in positions:
                if hasattr(pos, 'type') and hasattr(pos, 'price_open'):
                    pos_type = pos.type.upper() if isinstance(pos.type, str) else ("BUY" if pos.type == 0 else "SELL")
                    
                    # ประเมินคุณภาพตำแหน่ง
                    if pos_type == "BUY" and pos.price_open < current_price:
                        good_positions += 1  # ซื้อถูก - อยู่ในกำไร
                    elif pos_type == "SELL" and pos.price_open > current_price:
                        good_positions += 1  # ขายแพง - อยู่ในกำไร
                    else:
                        bad_positions += 1   # อยู่ผิดตำแหน่ง - ติดลบ
            
            result['total_positions'] = total_positions
            result['good_positions'] = good_positions
            result['bad_positions'] = bad_positions
            result['good_position_ratio'] = good_positions / total_positions
            result['bad_position_ratio'] = bad_positions / total_positions
            result['quality_score'] = (good_positions / total_positions) * 100
            
        except Exception as e:
            logger.error(f"Error assessing portfolio quality: {e}")
            result['quality_score'] = 0.0
            
        return result
    
    # 🗑️ OLD PROFIT/STOP LOSS METHODS REMOVED
    # Replaced by Lightning Portfolio Cleanup System
        
    def _check_pullback_conditions(self, positions: List[Position], current_prices: Dict[str, float],
                                  min_pullback_percentage: float = 0.3) -> Dict[str, Any]:
        """
        ตรวจสอบเงื่อนไข Pullback Wait Strategy
        
        Args:
            positions: รายการ Position
            current_prices: ราคาปัจจุบัน
            min_pullback_percentage: เกณฑ์ Pullback ขั้นต่ำ
            
        Returns:
            Dict: ผลการตรวจสอบ
        """
        # หาราคาสูงสุดและต่ำสุดของ positions
        if not positions:
            return {'should_wait': False}
            
        highest_price = max(pos.price_open for pos in positions)
        lowest_price = min(pos.price_open for pos in positions)
        
        # ตรวจสอบแต่ละสัญลักษณ์
        for symbol, current_price in current_prices.items():
            # ถ้าราคาวิ่งเกิน highest position
            if current_price > highest_price:
                # คำนวณ pullback
                pullback_pct = MarketAnalysisCalculator.calculate_pullback_percentage(
                    current_price, current_price, lowest_price
                )
                
                if pullback_pct < min_pullback_percentage:
                    return {
                        'should_wait': True,
                        'reason': f'รอ Pullback {min_pullback_percentage}% (ปัจจุบัน {pullback_pct:.2f}%)'
                    }
                    
        return {'should_wait': False}
        
    def _check_group_pnl(self, positions: List[Position], account_balance: float) -> Dict[str, Any]:
        """
        ตรวจสอบกำไรขาดทุนของกลุ่ม
        
        Args:
            positions: รายการ Position
            account_balance: ยอดเงินในบัญชี
            
        Returns:
            Dict: ผลการตรวจสอบ
        """
        group_profit_pct = PercentageCalculator.calculate_group_profit_percentage(
            positions, account_balance
        )
        
        # ปิดเมื่อกลุ่มกำไรรวมเป็นบวก
        if group_profit_pct > 0:
            return {
                'should_exit': True,
                'exit_type': 'group_profit',
                'positions_to_close': positions,
                'reasons': [f'กลุ่มมีกำไรรวม {group_profit_pct:.2f}%']
            }
            
        return {'should_exit': False}
        
    def register_order_for_candle(self, candle_time: datetime):
        """
        ลงทะเบียน Order สำหรับแท่งเทียน
        
        Args:
            candle_time: เวลาของแท่งเทียน
        """
        candle_time_key = candle_time.strftime("%Y%m%d%H%M")
        if candle_time_key not in self.orders_per_candle:
            self.orders_per_candle[candle_time_key] = 0
        self.orders_per_candle[candle_time_key] += 1
        
    def cleanup_old_candle_records(self, hours_to_keep: int = 24):
        """
        ลบข้อมูล Order ของแท่งเทียนเก่า
        
        Args:
            hours_to_keep: จำนวนชั่วโมงที่จะเก็บข้อมูล
        """
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(hours=hours_to_keep)
        
        keys_to_remove = []
        for key in self.orders_per_candle.keys():
            try:
                candle_time = datetime.strptime(key, "%Y%m%d%H%M")
                if candle_time < cutoff_time:
                    keys_to_remove.append(key)
            except ValueError:
                keys_to_remove.append(key)  # ลบ key ที่ format ผิด
                
        for key in keys_to_remove:
            del self.orders_per_candle[key]
    
    def _calculate_market_volatility(self, candle: CandleData) -> float:
        """🧠 คำนวณความผันผวนของตลาด"""
        try:
            # คำนวณ ATR-like volatility
            candle_range = candle.high - candle.low
            price_avg = (candle.high + candle.low) / 2
            volatility_pct = (candle_range / price_avg) * 100 if price_avg > 0 else 0
            
            # ปรับค่าให้อยู่ในช่วง 0.1 - 3.0
            volatility_factor = max(0.1, min(3.0, volatility_pct / 0.1))
            
            logger.debug(f"📊 Market Volatility: {volatility_pct:.3f}% → Factor: {volatility_factor:.2f}")
            return volatility_factor
            
        except Exception as e:
            logger.error(f"❌ Error calculating volatility: {e}")
            return 1.0  # Default volatility
    
    def _get_adaptive_entry_limit(self, volatility_factor: float, position_count: int) -> int:
        """🚀 คำนวณขด Entry Limit แบบ Adaptive"""
        try:
            # Base limit ตามความผันผวน
            if volatility_factor > 2.0:
                base_limit = 8  # ผันผวนสูง = เข้าได้บ่อย
            elif volatility_factor > 1.5:
                base_limit = 6  # ผันผวนปานกลาง
            elif volatility_factor > 1.0:
                base_limit = 4  # ผันผวนต่ำ
            else:
                base_limit = 2  # ผันผวนต่ำมาก
            
            # ปรับตามจำนวน positions
            if position_count > 200:
                adjustment = 0.5  # มีไม้เยอะ → ลดการเข้า
            elif position_count > 100:
                adjustment = 0.7
            elif position_count > 50:
                adjustment = 0.9
            else:
                adjustment = 1.2  # มีไม้น้อย → เพิ่มการเข้า
            
            final_limit = max(1, int(base_limit * adjustment))
            
            logger.debug(f"🚀 Entry Limit: Base:{base_limit} × Adj:{adjustment:.2f} = {final_limit} entries/min")
            return final_limit
            
        except Exception as e:
            logger.error(f"❌ Error calculating entry limit: {e}")
            return 3  # Safe default
    
    def _check_adaptive_entry_control(self, positions: List[Position], current_price: float, direction: str) -> Dict[str, Any]:
        """
        🚀 Adaptive Entry Control - รองรับ Unlimited Entry + Smart Management
        
        Args:
            positions: รายการ positions
            current_price: ราคาปัจจุบัน
            direction: ทิศทางที่จะเข้า
            
        Returns:
            Dict: ผลการตรวจสอบ
        """
        result = {
            'should_block': False,
            'force_trade': False,
            'reason': '',
            'forced_direction': direction
        }
        
        if not positions:
            return result
            
        # 🏥 วิเคราะห์สุขภาพ Portfolio
        wrong_buys = sum(1 for pos in positions if pos.type == 0 and pos.price_open > current_price)
        wrong_sells = sum(1 for pos in positions if pos.type == 1 and pos.price_open < current_price)
        total_positions = len(positions)
        wrong_percentage = ((wrong_buys + wrong_sells) / total_positions) * 100 if total_positions > 0 else 0
        
        # 🎯 Smart Imbalance Detection & Counter-Trade Logic
        buy_count = sum(1 for pos in positions if pos.type == 0)
        sell_count = sum(1 for pos in positions if pos.type == 1)
        buy_percentage = (buy_count / total_positions) * 100 if total_positions > 0 else 0
        sell_percentage = (sell_count / total_positions) * 100 if total_positions > 0 else 0
        
        # 🚀 SMART LOGIC: เมื่อเสียสมดุล → Force Counter-Trade (เข้มงวดขึ้น)
        if sell_percentage > 65.0:  # ลดจาก 80% เป็น 65%
            # Portfolio เอียงไป SELL มาก → ต้อง BUY เพื่อแก้สมดุล
            if direction == "BUY":
                result['force_trade'] = True
                result['reason'] = f'🚀 SMART: Force BUY to balance (SELL: {sell_percentage:.1f}%)'
                logger.info(f"🚀 FORCE BUY: Portfolio เอียง SELL {sell_percentage:.1f}% → ซื้อถูกแก้สมดุล")
                return result
            else:  # direction == "SELL"
                result['should_block'] = True
                result['reason'] = f'❌ BLOCK: Too many SELL already ({sell_percentage:.1f}%)'
                return result
                
        elif buy_percentage > 65.0:  # ลดจาก 80% เป็น 65%
            # Portfolio เอียงไป BUY มาก → บังคับ SELL เพื่อแก้สมดุล
            result['force_trade'] = True
            result['forced_direction'] = "SELL"  # บังคับ SELL ไม่ว่า signal จะเป็นอะไร
            result['reason'] = f'🚀 FORCE SELL: Too many BUY ({buy_percentage:.1f}%) - Must balance!'
            logger.info(f"🚀 FORCE SELL: Portfolio เอียง BUY {buy_percentage:.1f}% → บังคับขายเพื่อแก้สมดุล")
            return result
        
        elif total_positions > 50:
            # 🟡 High Volume Mode: ระมัดระวังแต่ไม่บล็อค
            logger.info(f"🟡 High Volume Mode: {total_positions} positions, Wrong: {wrong_percentage:.1f}%")
            result['reason'] = f'High Volume Mode: Proceed with caution'
            return result
        
        # 🟢 Normal Mode: อนุญาตทุกการเข้า (Unlimited Entry)
        result['reason'] = f'Normal Mode: Unlimited entry allowed (Wrong: {wrong_percentage:.1f}%)'
        return result
