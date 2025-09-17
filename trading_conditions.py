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
# from market_analysis import MarketSessionAnalyzer, MultiTimeframeAnalyzer  # Removed unused dependency

logger = logging.getLogger(__name__)

@dataclass
class Signal:
    """คลาสสำหรับเก็บข้อมูลสัญญาณการเทรด"""
    direction: str = "BUY"  # "BUY" หรือ "SELL"
    symbol: str = "XAUUSD"
    strength: float = 50.0  # แรงของสัญญาณ (0-100)
    confidence: float = 50.0  # ความมั่นใจ (0-100)
    timestamp: datetime = None
    price: float = 0.0
    volume_suggestion: float = 0.01
    stop_loss: float = 0.0
    take_profit: float = 0.0
    comment: str = ""
    # 🧠 7D Intelligence Fields
    entry_7d_score: float = 0.0      # คะแนน 7D สำหรับการเปิดไม้
    portfolio_synergy: float = 0.0    # คะแนนการช่วยเหลือพอร์ต
    recovery_support: float = 0.0     # คะแนนการช่วย recovery
    timing_intelligence: float = 0.0  # คะแนนจังหวะเปิดไม้
    margin_safety: float = 0.0        # คะแนนความปลอดภัย margin
    
    def __post_init__(self):
        """Post-initialization processing"""
        if self.timestamp is None:
            self.timestamp = datetime.now()

@dataclass
class Smart7DEntryAnalysis:
    """🧠 7D Intelligence Analysis สำหรับการเปิดไม้"""
    portfolio_synergy: float         # 0-100: การช่วยสมดุลพอร์ต
    recovery_support: float          # 0-100: การช่วย recovery positions เก่า
    timing_intelligence: float       # 0-100: จังหวะเปิดไม้ที่เหมาะสม
    margin_safety: float            # 0-100: ความปลอดภัยต่อ margin
    correlation_score: float        # 0-100: ความสัมพันธ์กับ positions เดิม
    market_condition_score: float   # 0-100: สภาพตลาดเหมาะสมหรือไม่
    position_spacing_score: float   # 0-100: ระยะห่างจาก positions เดิม
    total_7d_score: float          # คะแนนรวม 7 มิติ
    recommended_lot_size: str       # MINIMAL, SMALL, NORMAL, LARGE
    confidence_level: str           # LOW, FAIR, GOOD, HIGH
    entry_reasoning: str            # เหตุผลการตัดสินใจ

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
                           min_volume_percentage: float = 80.0) -> bool:
        """
        ตรวจสอบ Volume Filter (ปรับให้ยืดหยุ่นมากขึ้น)
        
        Args:
            current_volume: Volume ปัจจุบัน
            volume_history: ประวัติ Volume
            min_volume_percentage: เกณฑ์ขั้นต่ำของ Volume เป็นเปอร์เซ็นต์ (ลดจาก 120% เป็น 80%)
            
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
        
        # เพิ่ม Market Analysis - Disabled (no market_analysis module)
        # self.session_analyzer = MarketSessionAnalyzer()  # Disabled - no market_analysis
        self.session_analyzer = None
        self.mtf_analyzer = None  # จะถูกตั้งค่าเมื่อใช้งาน
        
        # 🧠 7D Entry Intelligence System
        self.enable_7d_entry_intelligence = True
        self.intelligent_position_manager = None  # จะถูกตั้งค่าจาก main_new.py
        
        # 🎯 Smart Entry Timing System - Disabled (no smart_entry_timing module)
        # try:
        #     from smart_entry_timing import create_smart_entry_timing
        #     self.smart_entry_timing = create_smart_entry_timing(symbol="XAUUSD")
        #     logger.info("✅ Smart Entry Timing initialized in TradingConditions")
        # except Exception as e:
        #     logger.error(f"❌ Failed to initialize Smart Entry Timing: {e}")
        #     self.smart_entry_timing = None
        self.smart_entry_timing = None
        logger.info("✅ Smart Entry Timing disabled - no module available")
            
        self.strategic_position_manager = None  # จะถูกตั้งค่าจาก main_new.py
        
    def check_smart_entry_timing(self, signal_direction: str, current_price: float, 
                                positions: List[Position]) -> Dict[str, Any]:
        """🎯 เช็คเวลาเข้าที่ฉลาด - ป้องกัน BUY สูง SELL ต่ำ"""
        try:
            if not self.smart_entry_timing:
                # Smart Entry Timing disabled - allow all entries (ปรับให้เทรดได้ทุกสภาวะ)
                logger.debug(f"🎯 SMART ENTRY: Disabled - allowing {signal_direction} at {current_price:.2f}")
                return {'approved': True, 'reason': 'Smart Entry Timing disabled - All market conditions allowed'}
            
            logger.info(f"🎯 SMART ENTRY CHECK: {signal_direction} at {current_price:.2f}")
            
            # วิเคราะห์จุดเข้า
            entry_analysis = self.smart_entry_timing.analyze_entry_opportunity(
                signal_direction=signal_direction,
                current_price=current_price,
                existing_positions=positions
            )
            
            # ตัดสินใจ
            if entry_analysis.timing.value == "ENTER_NOW":
                logger.info(f"✅ SMART ENTRY APPROVED: {entry_analysis.quality.value}")
                logger.info(f"   Score: {entry_analysis.score:.1f}, Hierarchy OK: {entry_analysis.price_hierarchy_ok}")
                
                # 🚨 CRITICAL CHECK: Price Hierarchy must be OK
                if not entry_analysis.price_hierarchy_ok:
                    logger.error(f"🚨 CRITICAL ERROR: Entry approved but Price Hierarchy violated!")
                    logger.error(f"   This should never happen - blocking entry for safety")
                    return {
                        'approved': False,
                        'reason': 'CRITICAL: Price hierarchy violated despite approval',
                        'hierarchy_ok': False
                    }
                
                return {
                    'approved': True,
                    'quality': entry_analysis.quality.value,
                    'score': entry_analysis.score,
                    'confidence': entry_analysis.confidence,
                    'strategic_value': entry_analysis.strategic_value,
                    'entry_analysis': entry_analysis,
                    'reason': f'Smart entry approved: {entry_analysis.quality.value}'
                }
            
            elif entry_analysis.timing.value in ["WAIT_PULLBACK", "WAIT_BREAKOUT"]:
                logger.info(f"⏳ SMART ENTRY WAIT: {entry_analysis.wait_reason}")
                logger.info(f"   Current: {current_price:.2f}, Suggested: {entry_analysis.suggested_price:.2f}")
                
                return {
                    'approved': False,
                    'reason': f'Wait for better price: {entry_analysis.wait_reason}',
                    'suggested_price': entry_analysis.suggested_price,
                    'current_price': current_price,
                    'wait_type': entry_analysis.timing.value
                }
            
            else:  # SKIP_SIGNAL
                logger.warning(f"🚫 SMART ENTRY REJECTED: {entry_analysis.wait_reason}")
                
                return {
                    'approved': False,
                    'reason': f'Entry rejected: {entry_analysis.wait_reason}',
                    'quality': entry_analysis.quality.value,
                    'hierarchy_ok': entry_analysis.price_hierarchy_ok
                }
                
        except Exception as e:
            logger.error(f"❌ Error in smart entry timing check: {e}")
            logger.error(f"🚫 BLOCKING ENTRY due to Smart Entry Timing error - Safety First!")
            return {'approved': False, 'reason': f'Smart entry check failed: {str(e)} - BLOCKED for safety'}
        
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
        
        # 🧠 Adaptive Entry Limits ตามสภาพตลาด (ปรับให้ยืดหยุ่นมากขึ้น)
        volatility_factor = self._calculate_market_volatility(candle)
        max_entries_per_minute = self._get_adaptive_entry_limit(volatility_factor, len(positions))
        
        # เพิ่ม entry limit เพื่อให้เทรดได้บ่อยขึ้น
        max_entries_per_minute = max_entries_per_minute * 2  # เพิ่มเป็น 2 เท่า
        
        if orders_this_minute >= max_entries_per_minute:
            result['reasons'].append(f"Entry limit reached: {orders_this_minute}/{max_entries_per_minute} per minute")
            logger.info(f"⚠️ Entry limit: {orders_this_minute}/{max_entries_per_minute} entries this minute")
            return result
        
        logger.info(f"✅ High-Frequency OK: {orders_this_minute}/{max_entries_per_minute} entries this minute")
            
        # 2. Market Session Analysis - Disabled (no market_analysis module)
        # session_params = self.session_analyzer.adjust_trading_parameters({
        #     'base_strength_threshold': 20.0,
        #     'base_max_positions': 4,
        session_params = {
            'base_strength_threshold': 20.0,
            'base_max_positions': 4,
            'base_lot_multiplier': 1.0
        }
        
        # 3. Multi-Timeframe Confirmation  
        # 🎯 FIXED: Counter-trend logic - ซื้อถูก ขายแพง
        if candle.close > candle.open:  # แท่งเขียว = ราคาขึ้น
            direction = "SELL"  # ขายตอนราคาสูง (ขายแพง)
        else:  # แท่งแดง = ราคาลง
            direction = "BUY"   # ซื้อตอนราคาต่ำ (ซื้อถูก)
        
        # Initialize mtf_analyzer with actual symbol if not done
        if self.mtf_analyzer is None and symbol:
            # from market_analysis import MultiTimeframeAnalyzer  # Removed unused dependency
            # self.mtf_analyzer = MultiTimeframeAnalyzer(symbol)  # Disabled - no market_analysis
            self.mtf_analyzer = None
        
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
            # 🔴 STRICT ENTRY: ต้องมีแรงตลาดเพียงพอถึงจะเทรด
            can_enter_analysis = False
            if session_params['current_session'] in ['OVERLAP_LONDON_NY', 'LONDON'] and strength_analysis['total_strength'] >= 15.0:
                can_enter_analysis = True
                entry_reason = f"Session สูง + แรงตลาดพอ ({strength_analysis['total_strength']:.2f}%)"
            else:
                # ลดเกณฑ์แรงตลาดเพื่อให้เทรดได้ทุกสภาวะ
                if strength_analysis['total_strength'] >= 5.0:  # ลดจาก 15% เป็น 5%
                    can_enter_analysis = True
                    entry_reason = f"แรงตลาดพอสำหรับทุกสภาวะ ({strength_analysis['total_strength']:.2f}% >= 5%)"
                else:
                    entry_reason = f"❌ BLOCKED: แรงตลาดไม่เพียงพอ ({strength_analysis['total_strength']:.2f}% < 5%)"
                    result['reasons'].append(entry_reason)
                    logger.warning(f"❌ เงื่อนไข 2: {entry_reason}")
                    return result
        
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
        # เพื่อไม่ให้พอร์ตแย่ยิ่งแย่หนัก จากการไม่ออกไม้

        # 🚀 Adaptive Entry Control - ENHANCED for Balance Enforcement
        adaptive_control = self._check_adaptive_entry_control(positions, candle.close, strength_analysis['direction'], strength_analysis)
        
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

        # 🧠 7D ENTRY INTELLIGENCE ANALYSIS
        entry_7d_analysis = None
        if self.enable_7d_entry_intelligence and self.intelligent_position_manager:
            try:
                entry_7d_analysis = self._analyze_7d_entry_intelligence(
                    strength_analysis['direction'], candle, positions, account_balance, entry_price
                )
                logger.info(f"🧠 7D Entry Analysis: Score={entry_7d_analysis.total_7d_score:.1f}, "
                           f"Confidence={entry_7d_analysis.confidence_level}, "
                           f"Lot={entry_7d_analysis.recommended_lot_size}")
                logger.info(f"   📊 Synergy={entry_7d_analysis.portfolio_synergy:.1f}, "
                           f"Recovery={entry_7d_analysis.recovery_support:.1f}, "
                           f"Timing={entry_7d_analysis.timing_intelligence:.1f}")
            except Exception as e:
                logger.warning(f"⚠️ 7D Entry Analysis failed: {e} - Using traditional analysis")

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
        
        # 🧠 เพิ่ม 7D Intelligence ลงใน Signal
        if entry_7d_analysis:
            signal.entry_7d_score = entry_7d_analysis.total_7d_score
            signal.portfolio_synergy = entry_7d_analysis.portfolio_synergy
            signal.recovery_support = entry_7d_analysis.recovery_support
            signal.timing_intelligence = entry_7d_analysis.timing_intelligence
            signal.margin_safety = entry_7d_analysis.margin_safety
            
            # ปรับ volume_suggestion ตาม 7D analysis
            signal.volume_suggestion = self._calculate_smart_lot_size(entry_7d_analysis)
            signal.comment += f" | 7D Score: {entry_7d_analysis.total_7d_score:.1f}"
        
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
            gap_pips = (max_buy_price - min_sell_price) * 0.1  # XAUUSD: 1 point = 0.1 pip
            
            # 🎯 STRICTER RULES: ลด exception cases ให้เข้มงวดขึ้น
            
            # อนุญาตเฉพาะ gap เล็กมาก (< 50 pips สำหรับ Recovery System) - ลดจาก 200 เป็น 50
            if gap_pips < 50.0:
                logger.info(f"⚡ Price Hierarchy Override: Small gap {gap_pips:.1f} pips - Recovery System")
                return {'valid': True, 'reason': f'Small gap {gap_pips:.1f} pips < 50 pips'}
            
            # อนุญาตถ้ามี positions น้อยมาก (< 5 ไม้) - ลดจาก 10 เป็น 5
            if len(positions) < 5:
                logger.info(f"⚡ Price Hierarchy Override: Very few positions ({len(positions)}) - Allow flexibility")
                return {'valid': True, 'reason': f'Very few positions ({len(positions)}) - Allow flexibility'}
            
            # อนุญาตถ้ามี positions เยอะมาก (> 15 ไม้) - เพิ่มจาก 8 เป็น 15 เพื่อเข้มงวดขึ้น
            if len(positions) > 15:
                logger.info(f"⚡ Price Hierarchy Override: Emergency recovery mode ({len(positions)} positions)")
                return {'valid': True, 'reason': f'Emergency recovery mode ({len(positions)} positions) - Hierarchy relaxed'}
            
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
        """⚡ ตรวจสอบว่าต้อง Force Trade หรือไม่ - Enhanced with Extreme Zone Logic"""
        result = {
            'should_force': False,
            'forced_direction': '',
            'reason': ''
        }
        
        if not positions:
            return result
        
        # 🎯 NEW: Extreme Zone Detection - ไม้บนสุด/ล่างสุดต้องมี SELL/BUY
        buy_prices = [pos.price_open for pos in positions if pos.type == 0]
        sell_prices = [pos.price_open for pos in positions if pos.type == 1]
        
        if buy_prices and sell_prices:
            max_position_price = max(max(buy_prices), max(sell_prices))  # ไม้บนสุด
            min_position_price = min(min(buy_prices), min(sell_prices))  # ไม้ล่างสุด
            
            # 🔝 ตรวจสอบไม้บนสุด - ต้องมี SELL
            top_sells = [pos for pos in positions if pos.type == 1 and pos.price_open >= max_position_price - 5.0]  # ใกล้บนสุด 5 จุด
            
            # 🚀 BREAKOUT LOGIC: ราคาทะลุขึ้นบนสุด → ออก SELL
            if current_price > max_position_price + 5.0:  # ทะลุขึ้นเหนือไม้บนสุด 5 จุด
                result['should_force'] = True
                result['forced_direction'] = 'SELL'
                result['reason'] = f"BREAKOUT SELL: Price broke above top positions (Max: {max_position_price:.2f}, Current: {current_price:.2f})"
                logger.info(f"🚀 BREAKOUT FORCE SELL: {result['reason']}")
                return result
            # 🔝 ZONE LOGIC: ใกล้บนสุดแต่ไม่มี SELL
            elif not top_sells and current_price >= max_position_price - 10.0:  # ราคาใกล้บนสุด
                result['should_force'] = True
                result['forced_direction'] = 'SELL'
                result['reason'] = f"Force SELL: No SELL at top zone (Max: {max_position_price:.2f}, Current: {current_price:.2f})"
                logger.info(f"🔝 EXTREME ZONE FORCE: {result['reason']}")
                return result
            
            # 🔻 ตรวจสอบไม้ล่างสุด - ต้องมี BUY  
            bottom_buys = [pos for pos in positions if pos.type == 0 and pos.price_open <= min_position_price + 5.0]  # ใกล้ล่างสุด 5 จุด
            
            # 🚀 BREAKOUT LOGIC: ราคาทะลุลงล่างสุด → ออก BUY
            if current_price < min_position_price - 5.0:  # ทะลุลงใต้ไม้ล่างสุด 5 จุด
                result['should_force'] = True
                result['forced_direction'] = 'BUY'
                result['reason'] = f"BREAKOUT BUY: Price broke below bottom positions (Min: {min_position_price:.2f}, Current: {current_price:.2f})"
                logger.info(f"🚀 BREAKOUT FORCE BUY: {result['reason']}")
                return result
            # 🔻 ZONE LOGIC: ใกล้ล่างสุดแต่ไม่มี BUY
            elif not bottom_buys and current_price <= min_position_price + 10.0:  # ราคาใกล้ล่างสุด
                result['should_force'] = True
                result['forced_direction'] = 'BUY'
                result['reason'] = f"Force BUY: No BUY at bottom zone (Min: {min_position_price:.2f}, Current: {current_price:.2f})"
                logger.info(f"🔻 EXTREME ZONE FORCE: {result['reason']}")
                return result
        
        # 🎯 ORIGINAL: Zone Boundary Logic (Keep as backup)
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
    
    def _check_adaptive_entry_control(self, positions: List[Position], current_price: float, direction: str, strength_analysis: Dict) -> Dict[str, Any]:
        """
        🚀 Adaptive Entry Control - รองรับ Unlimited Entry + Smart Management
        
        Args:
            positions: รายการ positions
            current_price: ราคาปัจจุบัน
            direction: ทิศทางที่จะเข้า
            strength_analysis: ข้อมูลแรงตลาด
            
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
            
        # 🚫 OLD BALANCE CONTROL SYSTEM REMOVED
        # ✅ Smart Entry Timing System now handles all entry logic
        # ✅ Price Hierarchy Rules prevent bad entries
        # ✅ Zone-Aware Reversal Logic manages balance
        
        result['reason'] = 'Entry control handled by Smart Entry Timing System'
        return result
    
    # 🚫 REMOVED: _calculate_dynamic_balance_threshold - Not needed with Smart Entry Timing System
    
    # 🧠 ===== 7D ENTRY INTELLIGENCE SYSTEM =====
    
    def _analyze_7d_entry_intelligence(self, direction: str, candle: CandleData, 
                                     positions: List[Position], account_balance: float,
                                     entry_price: float) -> Smart7DEntryAnalysis:
        """
        🧠 7D Entry Intelligence Analysis
        วิเคราะห์ 7 มิติสำหรับการเปิดไม้ที่ฉลาดและปลอดภัย
        """
        try:
            logger.debug(f"🧠 Starting 7D Entry Analysis for {direction}")
            
            # 1. 📊 Portfolio Synergy Analysis
            portfolio_synergy = self._calculate_portfolio_synergy(direction, positions)
            
            # 2. 🔄 Recovery Support Analysis  
            recovery_support = self._calculate_recovery_support(direction, positions, entry_price)
            
            # 3. ⏰ Market Timing Intelligence
            timing_intelligence = self._calculate_timing_intelligence(candle, positions)
            
            # 4. 💊 Margin Safety Analysis
            margin_safety = self._calculate_margin_safety(account_balance, positions)
            
            # 5. 🔗 Position Correlation Analysis
            correlation_score = self._calculate_position_correlation(direction, positions, entry_price)
            
            # 6. 🌊 Market Condition Analysis
            market_condition_score = self._calculate_market_condition_score(candle)
            
            # 7. 📏 Position Spacing Analysis
            position_spacing_score = self._calculate_position_spacing(direction, positions, entry_price)
            
            # 🧮 Calculate Total 7D Score (Weighted)
            total_7d_score = (
                (portfolio_synergy * 0.25) +      # 25% - สำคัญที่สุด
                (recovery_support * 0.20) +       # 20% - ช่วย recovery
                (timing_intelligence * 0.15) +    # 15% - จังหวะ
                (margin_safety * 0.15) +          # 15% - ปลอดภัย
                (correlation_score * 0.10) +      # 10% - ความสัมพันธ์
                (market_condition_score * 0.10) + # 10% - สภาพตลาด
                (position_spacing_score * 0.05)   # 5% - ระยะห่าง
            )
            
            # 🎯 Determine Confidence Level & Lot Size
            if total_7d_score >= 80:
                confidence_level = "HIGH"
                recommended_lot_size = "LARGE"
                reasoning = "7D Score ดีเยี่ยม - เปิดไม้ใหญ่"
            elif total_7d_score >= 65:
                confidence_level = "GOOD"  
                recommended_lot_size = "NORMAL"
                reasoning = "7D Score ดี - เปิดไม้ปกติ"
            elif total_7d_score >= 45:
                confidence_level = "FAIR"
                recommended_lot_size = "SMALL"
                reasoning = "7D Score พอใช้ - เปิดไม้เล็ก"
            else:
                confidence_level = "LOW"
                recommended_lot_size = "MINIMAL"
                reasoning = "7D Score ต่ำ - เปิดไม้น้อย"
            
            logger.debug(f"🧠 7D Analysis Complete: Total Score = {total_7d_score:.1f}")
            
            return Smart7DEntryAnalysis(
                portfolio_synergy=portfolio_synergy,
                recovery_support=recovery_support,
                timing_intelligence=timing_intelligence,
                margin_safety=margin_safety,
                correlation_score=correlation_score,
                market_condition_score=market_condition_score,
                position_spacing_score=position_spacing_score,
                total_7d_score=total_7d_score,
                recommended_lot_size=recommended_lot_size,
                confidence_level=confidence_level,
                entry_reasoning=reasoning
            )
            
        except Exception as e:
            logger.error(f"❌ Error in 7D Entry Analysis: {e}")
            # Return safe defaults
            return Smart7DEntryAnalysis(
                portfolio_synergy=50.0,
                recovery_support=50.0,
                timing_intelligence=50.0,
                margin_safety=50.0,
                correlation_score=50.0,
                market_condition_score=50.0,
                position_spacing_score=50.0,
                total_7d_score=50.0,
                recommended_lot_size="SMALL",
                confidence_level="FAIR",
                entry_reasoning="7D Analysis failed - using safe defaults"
            )
    
    def _calculate_portfolio_synergy(self, direction: str, positions: List[Position]) -> float:
        """📊 Portfolio Synergy: การช่วยสมดุลพอร์ต"""
        try:
            if not positions:
                return 85.0  # ไม่มี positions = เปิดได้เต็มที่
            
            buy_count = sum(1 for pos in positions if getattr(pos, 'type', 0) == 0)
            sell_count = sum(1 for pos in positions if getattr(pos, 'type', 0) == 1)
            total_positions = len(positions)
            
            if total_positions == 0:
                return 85.0
            
            buy_ratio = buy_count / total_positions
            sell_ratio = sell_count / total_positions
            
            # คำนวณ synergy score
            if direction == "BUY":
                if sell_ratio > 0.6:  # SELL เยอะ → BUY ช่วยสมดุล
                    synergy_score = 95.0
                elif sell_ratio > 0.5:  # SELL เล็กน้อย → BUY ช่วยได้
                    synergy_score = 80.0
                elif buy_ratio > 0.7:  # BUY เยอะแล้ว → BUY เพิ่มไม่ดี
                    synergy_score = 30.0
                else:
                    synergy_score = 60.0  # สมดุลปกติ
            else:  # SELL
                if buy_ratio > 0.6:  # BUY เยอะ → SELL ช่วยสมดุล
                    synergy_score = 95.0
                elif buy_ratio > 0.5:  # BUY เล็กน้อย → SELL ช่วยได้
                    synergy_score = 80.0
                elif sell_ratio > 0.7:  # SELL เยอะแล้ว → SELL เพิ่มไม่ดี
                    synergy_score = 30.0
                else:
                    synergy_score = 60.0  # สมดุลปกติ
            
            logger.debug(f"📊 Portfolio Synergy: {direction} = {synergy_score:.1f} "
                        f"(BUY: {buy_count}, SELL: {sell_count})")
            return synergy_score
            
        except Exception as e:
            logger.error(f"❌ Error calculating portfolio synergy: {e}")
            return 50.0
    
    def _calculate_recovery_support(self, direction: str, positions: List[Position], entry_price: float) -> float:
        """🔄 Recovery Support: การช่วย recovery positions เก่า"""
        try:
            if not positions:
                return 70.0  # ไม่มี positions = ไม่ต้องช่วย recovery
            
            losing_positions = [pos for pos in positions if getattr(pos, 'profit', 0) < -5.0]
            if not losing_positions:
                return 70.0  # ไม่มี losing positions
            
            # หา losing positions ที่ตรงข้ามกับ direction ใหม่
            opposite_losing = []
            for pos in losing_positions:
                pos_type = getattr(pos, 'type', 0)
                if (direction == "BUY" and pos_type == 1) or (direction == "SELL" and pos_type == 0):
                    opposite_losing.append(pos)
            
            if not opposite_losing:
                return 40.0  # ไม่ช่วย recovery
            
            # คำนวณ recovery potential
            total_loss = sum(abs(getattr(pos, 'profit', 0)) for pos in opposite_losing)
            avg_loss_per_position = total_loss / len(opposite_losing) if opposite_losing else 0
            
            # ยิ่ง loss เยอะ ยิ่งต้องการ recovery
            if avg_loss_per_position > 20.0:
                recovery_score = 90.0  # ต้องการ recovery มาก
            elif avg_loss_per_position > 10.0:
                recovery_score = 75.0  # ต้องการ recovery ปานกลาง
            elif avg_loss_per_position > 5.0:
                recovery_score = 60.0  # ต้องการ recovery เล็กน้อย
            else:
                recovery_score = 45.0  # loss น้อย
            
            logger.debug(f"🔄 Recovery Support: {direction} = {recovery_score:.1f} "
                        f"(Opposite losing: {len(opposite_losing)}, Avg loss: ${avg_loss_per_position:.2f})")
            return recovery_score
            
        except Exception as e:
            logger.error(f"❌ Error calculating recovery support: {e}")
            return 50.0
    
    def _calculate_timing_intelligence(self, candle: CandleData, positions: List[Position]) -> float:
        """⏰ Market Timing Intelligence: จังหวะเปิดไม้"""
        try:
            timing_score = 60.0  # Base score
            
            # 1. Candle strength analysis
            candle_range = abs(candle.high - candle.low)
            candle_body = abs(candle.close - candle.open)
            
            if candle_range > 0:
                body_ratio = candle_body / candle_range
                if body_ratio > 0.7:  # Strong candle
                    timing_score += 15.0
                elif body_ratio > 0.5:  # Moderate candle  
                    timing_score += 10.0
                elif body_ratio < 0.3:  # Weak/doji candle
                    timing_score -= 10.0
            
            # 2. Position age analysis
            if positions:
                current_time = datetime.now().timestamp()
                avg_age_hours = 0
                valid_positions = 0
                
                for pos in positions:
                    pos_time = getattr(pos, 'time', 0)
                    if pos_time > 0:
                        age_hours = (current_time - pos_time) / 3600
                        avg_age_hours += age_hours
                        valid_positions += 1
                
                if valid_positions > 0:
                    avg_age_hours /= valid_positions
                    
                    # ถ้า positions เก่ามาก = เวลาเปิดใหม่
                    if avg_age_hours > 24:  # > 1 day
                        timing_score += 10.0
                    elif avg_age_hours > 12:  # > 12 hours
                        timing_score += 5.0
                    elif avg_age_hours < 1:  # < 1 hour (เพิ่งเปิด)
                        timing_score -= 5.0
            
            # 3. Volume analysis
            if hasattr(candle, 'volume') and candle.volume > 0:
                # Assume average volume = 1000 (placeholder)
                volume_ratio = candle.volume / 1000.0
                if volume_ratio > 1.5:  # High volume
                    timing_score += 10.0
                elif volume_ratio < 0.5:  # Low volume
                    timing_score -= 5.0
            
            timing_score = max(0, min(100, timing_score))
            logger.debug(f"⏰ Timing Intelligence: {timing_score:.1f}")
            return timing_score
            
        except Exception as e:
            logger.error(f"❌ Error calculating timing intelligence: {e}")
            return 50.0
    
    def _calculate_margin_safety(self, account_balance: float, positions: List[Position]) -> float:
        """💊 Margin Safety: ความปลอดภัยต่อ margin"""
        try:
            if account_balance <= 0:
                return 20.0  # Unsafe
            
            # Estimate margin usage (simplified)
            total_volume = sum(getattr(pos, 'volume', 0.01) for pos in positions)
            estimated_margin_per_lot = account_balance * 0.001  # Rough estimate
            used_margin = total_volume * estimated_margin_per_lot
            
            if used_margin <= 0:
                return 90.0  # No positions = very safe
            
            margin_ratio = used_margin / account_balance
            
            # Calculate safety score
            if margin_ratio < 0.1:  # < 10% margin usage
                safety_score = 95.0
            elif margin_ratio < 0.2:  # < 20% margin usage
                safety_score = 85.0
            elif margin_ratio < 0.4:  # < 40% margin usage
                safety_score = 70.0
            elif margin_ratio < 0.6:  # < 60% margin usage
                safety_score = 50.0
            elif margin_ratio < 0.8:  # < 80% margin usage
                safety_score = 30.0
            else:  # > 80% margin usage
                safety_score = 10.0
            
            logger.debug(f"💊 Margin Safety: {safety_score:.1f} "
                        f"(Usage: {margin_ratio*100:.1f}%)")
            return safety_score
            
        except Exception as e:
            logger.error(f"❌ Error calculating margin safety: {e}")
            return 50.0
    
    def _calculate_position_correlation(self, direction: str, positions: List[Position], entry_price: float) -> float:
        """🔗 Position Correlation: ความสัมพันธ์กับ positions เดิม"""
        try:
            if not positions:
                return 70.0  # No correlation issues
            
            correlation_score = 70.0  # Base score
            same_direction_count = 0
            opposite_direction_count = 0
            
            for pos in positions:
                pos_type = getattr(pos, 'type', 0)
                pos_price = getattr(pos, 'price_open', entry_price)
                
                # Count same/opposite direction
                if (direction == "BUY" and pos_type == 0) or (direction == "SELL" and pos_type == 1):
                    same_direction_count += 1
                    # Check price correlation
                    price_diff = abs(pos_price - entry_price)
                    if price_diff < 10.0:  # Too close
                        correlation_score -= 5.0
                else:
                    opposite_direction_count += 1
                    # Opposite direction is good for hedging
                    correlation_score += 2.0
            
            # Penalize too many same direction
            total_positions = len(positions)
            same_ratio = same_direction_count / total_positions if total_positions > 0 else 0
            
            if same_ratio > 0.8:  # Too many same direction
                correlation_score -= 20.0
            elif same_ratio < 0.3:  # Good diversity
                correlation_score += 10.0
            
            correlation_score = max(0, min(100, correlation_score))
            logger.debug(f"🔗 Position Correlation: {correlation_score:.1f} "
                        f"(Same: {same_direction_count}, Opposite: {opposite_direction_count})")
            return correlation_score
            
        except Exception as e:
            logger.error(f"❌ Error calculating position correlation: {e}")
            return 50.0
    
    def _calculate_market_condition_score(self, candle: CandleData) -> float:
        """🌊 Market Condition: สภาพตลาดเหมาะสมหรือไม่"""
        try:
            condition_score = 60.0  # Base score
            
            # 1. Volatility analysis
            candle_range = abs(candle.high - candle.low)
            candle_body = abs(candle.close - candle.open)
            
            if candle_range > 0:
                volatility_ratio = candle_range / candle.close if candle.close > 0 else 0
                
                # Optimal volatility range
                if 0.001 < volatility_ratio < 0.005:  # 0.1% - 0.5%
                    condition_score += 15.0
                elif volatility_ratio > 0.01:  # > 1% (too volatile)
                    condition_score -= 10.0
                elif volatility_ratio < 0.0005:  # < 0.05% (too quiet)
                    condition_score -= 5.0
            
            # 2. Candle pattern analysis
            if candle.is_green:
                if candle_body > candle_range * 0.6:  # Strong green
                    condition_score += 10.0
                else:  # Weak green
                    condition_score += 5.0
            elif candle.is_red:
                if candle_body > candle_range * 0.6:  # Strong red
                    condition_score += 10.0
                else:  # Weak red
                    condition_score += 5.0
            else:  # Doji
                condition_score -= 5.0
            
            # 3. Time-based analysis (simplified)
            current_hour = datetime.now().hour
            if 8 <= current_hour <= 17:  # Active trading hours
                condition_score += 5.0
            elif 22 <= current_hour or current_hour <= 2:  # Low activity
                condition_score -= 5.0
            
            condition_score = max(0, min(100, condition_score))
            logger.debug(f"🌊 Market Condition: {condition_score:.1f}")
            return condition_score
            
        except Exception as e:
            logger.error(f"❌ Error calculating market condition: {e}")
            return 50.0
    
    def _calculate_position_spacing(self, direction: str, positions: List[Position], entry_price: float) -> float:
        """📏 Position Spacing: ระยะห่างจาก positions เดิม"""
        try:
            if not positions:
                return 80.0  # No spacing issues
            
            spacing_score = 80.0  # Base score
            min_distance = float('inf')
            same_direction_positions = []
            
            for pos in positions:
                pos_type = getattr(pos, 'type', 0)
                pos_price = getattr(pos, 'price_open', entry_price)
                
                # Check same direction positions
                if (direction == "BUY" and pos_type == 0) or (direction == "SELL" and pos_type == 1):
                    same_direction_positions.append(pos_price)
                    distance = abs(pos_price - entry_price)
                    min_distance = min(min_distance, distance)
            
            if same_direction_positions:
                # Penalize too close positions
                if min_distance < 5.0:  # < 5 pips
                    spacing_score -= 30.0
                elif min_distance < 10.0:  # < 10 pips
                    spacing_score -= 15.0
                elif min_distance < 20.0:  # < 20 pips
                    spacing_score -= 5.0
                else:  # Good spacing
                    spacing_score += 5.0
            
            spacing_score = max(0, min(100, spacing_score))
            logger.debug(f"📏 Position Spacing: {spacing_score:.1f} "
                        f"(Min distance: {min_distance:.1f} pips)")
            return spacing_score
            
        except Exception as e:
            logger.error(f"❌ Error calculating position spacing: {e}")
            return 50.0
    
    def _calculate_smart_lot_size(self, analysis: Smart7DEntryAnalysis) -> float:
        """🎯 Smart Lot Sizing ตาม 7D Analysis"""
        try:
            base_lot = 0.02  # Base lot size
            
            # Adjust based on 7D score and confidence
            if analysis.recommended_lot_size == "LARGE":
                multiplier = 1.5  # 0.03
            elif analysis.recommended_lot_size == "NORMAL":
                multiplier = 1.0  # 0.02
            elif analysis.recommended_lot_size == "SMALL":
                multiplier = 0.5  # 0.01
            else:  # MINIMAL
                multiplier = 0.25  # 0.005
            
            # Additional adjustments
            if analysis.margin_safety > 90:
                multiplier *= 1.2  # Extra safe = bigger lot
            elif analysis.margin_safety < 30:
                multiplier *= 0.5  # Risky = smaller lot
            
            if analysis.portfolio_synergy > 90:
                multiplier *= 1.1  # Great synergy = slightly bigger
            elif analysis.portfolio_synergy < 40:
                multiplier *= 0.8  # Poor synergy = smaller
            
            smart_lot = base_lot * multiplier
            smart_lot = max(0.01, min(0.1, smart_lot))  # Limit 0.01 - 0.1
            
            logger.debug(f"🎯 Smart Lot Size: {smart_lot:.3f} "
                        f"(Base: {base_lot}, Multiplier: {multiplier:.2f})")
            return smart_lot
            
        except Exception as e:
            logger.error(f"❌ Error calculating smart lot size: {e}")
            return 0.02  # Safe default
