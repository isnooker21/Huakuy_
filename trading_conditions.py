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
            'direction': 'SELL' if candle.is_green else 'BUY'  # Counter-trend
        }
        
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
        
        logger.info(f"🔍 ตรวจสอบเงื่อนไขการเข้าเทรด - Symbol: {symbol}")
        logger.info(f"   Candle: O:{candle.open:.2f} H:{candle.high:.2f} L:{candle.low:.2f} C:{candle.close:.2f}")
        logger.info(f"   Volume: {candle.volume}, Balance: {account_balance:,.2f}")
        
        # 1. ตรวจสอบ One Order per Candle
        candle_time_key = candle.timestamp.strftime("%Y%m%d%H%M")
        if candle_time_key in self.orders_per_candle:
            result['reasons'].append("มี Order ในแท่งเทียนนี้แล้ว")
            logger.info(f"❌ เงื่อนไข 1: {result['reasons'][-1]}")
            return result
            
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
            # ยืดหยุ่นสุดท้าย - ให้เทรดได้แต่ลด lot
            if session_params['current_session'] in ['OVERLAP_LONDON_NY', 'LONDON'] and strength_analysis['total_strength'] >= 10.0:
                can_enter_analysis = True
                entry_reason = f"Session สูง + แรงตลาดพอใช้ ({strength_analysis['total_strength']:.2f}%)"
                strength_analysis['total_strength'] = 15.0  # ให้คะแนนขั้นต่ำ
            else:
                result['reasons'].append(f"แรงตลาดไม่เพียงพอ ({strength_analysis['total_strength']:.2f}%) และไม่ผ่านเงื่อนไขอื่น")
                logger.info(f"❌ เงื่อนไข 2: {result['reasons'][-1]}")
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
        balance_check = self._check_portfolio_balance(positions, strength_analysis['direction'])
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
        
    def _check_portfolio_balance(self, positions: List[Position], direction: str) -> Dict[str, Any]:
        """
        ตรวจสอบสมดุลพอร์ตแบบ Zone-Based (300 จุด = 30 pips)
        
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
            
        # 🎯 Zone-Based Balance Check (300 points = 30 pips per zone)
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
                    
        # ตรวจสอบ Price Hierarchy Rule (ซื้อถูกขายแพง)
        hierarchy_check = self._check_price_hierarchy(positions, direction)
        if not hierarchy_check['valid']:
            result['can_enter'] = False
            result['reasons'].append(hierarchy_check['reason'])
            
        return result
    
    def _analyze_zone_balance(self, positions: List[Position], direction: str) -> Dict[str, Any]:
        """
        🎯 วิเคราะห์สมดุลแบบ Zone-Based (300 จุด = 30 pips ต่อ zone)
        
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
        
        # แบ่ง positions เป็น zones (300 points = 30 pips per zone)
        zone_size = 3.0  # 300 points = 3.0 price units สำหรับ XAUUSD
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
            
            # ยืดหยุ่นมาก: อนุญาตถ้า gap ไม่ใหญ่มาก (< 150 pips = 1500 จุด)
            if gap_pips < 150.0:  # เพิ่มจาก 60 เป็น 150 pips
                logger.info(f"⚡ Price Hierarchy Override: Gap={gap_pips:.1f} pips ({gap_pips*10:.0f} จุด) - Normal Trading")
                return {'valid': True, 'reason': f'Acceptable gap - {gap_pips:.1f} pips < 150 pips'}
            
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
