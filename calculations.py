# -*- coding: utf-8 -*-
"""
Calculations Module
โมดูลสำหรับคำนวณ lot, เปอร์เซ็นต์, และค่าต่างๆ ที่เกี่ยวข้องกับการเทรด
"""

import logging
import math
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Position:
    """คลาสสำหรับเก็บข้อมูล Position"""
    ticket: int
    symbol: str
    type: int  # 0=BUY, 1=SELL
    volume: float
    price_open: float
    price_current: float
    profit: float
    swap: float = 0.0
    commission: float = 0.0
    comment: str = ""
    magic: int = 0
    time_open: Optional[Any] = None

class PercentageCalculator:
    """คลาสสำหรับคำนวณเปอร์เซ็นต์ต่างๆ"""
    
    @staticmethod
    def calculate_profit_percentage(position: Position, account_balance: float) -> float:
        """
        คำนวณเปอร์เซ็นต์กำไร/ขาดทุนของ Position
        
        Args:
            position: ข้อมูล Position
            account_balance: ยอดเงินในบัญชี
            
        Returns:
            float: เปอร์เซ็นต์กำไร/ขาดทุน
        """
        if account_balance <= 0:
            return 0.0
            
        total_profit = position.profit + position.swap + position.commission
        return (total_profit / account_balance) * 100
        
    @staticmethod
    def calculate_price_change_percentage(open_price: float, current_price: float) -> float:
        """
        คำนวณเปอร์เซ็นต์การเปลี่ยนแปลงราคา
        
        Args:
            open_price: ราคาเปิด Position
            current_price: ราคาปัจจุบัน
            
        Returns:
            float: เปอร์เซ็นต์การเปลี่ยนแปลงราคา
        """
        if open_price <= 0:
            return 0.0
            
        return ((current_price - open_price) / open_price) * 100
        
    @staticmethod
    def calculate_group_profit_percentage(positions: List[Position], account_balance: float) -> float:
        """
        คำนวณเปอร์เซ็นต์กำไร/ขาดทุนของกลุ่ม Position
        
        Args:
            positions: รายการ Position
            account_balance: ยอดเงินในบัญชี
            
        Returns:
            float: เปอร์เซ็นต์กำไร/ขาดทุนรวม
        """
        if not positions or account_balance <= 0:
            return 0.0
            
        total_profit = sum(pos.profit + pos.swap + pos.commission for pos in positions)
        return (total_profit / account_balance) * 100
        
    @staticmethod
    def calculate_portfolio_exposure_percentage(positions: List[Position], account_balance: float) -> float:
        """
        คำนวณเปอร์เซ็นต์การใช้เงินทุนของพอร์ต
        
        Args:
            positions: รายการ Position
            account_balance: ยอดเงินในบัญชี
            
        Returns:
            float: เปอร์เซ็นต์การใช้เงินทุน
        """
        if not positions or account_balance <= 0:
            return 0.0
            
        # คำนวณมูลค่าการลงทุนรวม (ปรับตามสัญลักษณ์)
        total_exposure = 0.0
        
        for pos in positions:
            if 'XAU' in pos.symbol.upper() or 'GOLD' in pos.symbol.upper():
                # XAUUSD: 1 lot = 100 oz, ใช้ margin requirement จริง (ประมาณ 1-5%)
                position_value = pos.volume * pos.price_open * 100  # 100 oz per lot
                margin_requirement = position_value * 0.02  # 2% margin requirement
                total_exposure += margin_requirement
            else:
                # Forex pairs: ใช้ margin requirement จริง (ประมาณ 1-3%)
                position_value = pos.volume * 100000  # 100,000 units per lot
                margin_requirement = position_value * 0.01  # 1% margin requirement  
                total_exposure += margin_requirement
        
        return (total_exposure / account_balance) * 100
        
    @staticmethod
    def calculate_buy_sell_ratio(positions: List[Position]) -> Dict[str, float]:
        """
        คำนวณสัดส่วน Buy:Sell เป็นเปอร์เซ็นต์
        
        Args:
            positions: รายการ Position
            
        Returns:
            Dict: สัดส่วน Buy และ Sell เป็นเปอร์เซ็นต์
        """
        if not positions:
            return {'buy_percentage': 0.0, 'sell_percentage': 0.0, 'total_positions': 0}
            
        buy_count = sum(1 for pos in positions if pos.type == 0)  # BUY
        sell_count = sum(1 for pos in positions if pos.type == 1)  # SELL
        total_count = len(positions)
        
        buy_percentage = (buy_count / total_count) * 100 if total_count > 0 else 0.0
        sell_percentage = (sell_count / total_count) * 100 if total_count > 0 else 0.0
        
        return {
            'buy_percentage': buy_percentage,
            'sell_percentage': sell_percentage,
            'buy_count': buy_count,
            'sell_count': sell_count,
            'total_positions': total_count
        }

class LotSizeCalculator:
    """คลาสสำหรับคำนวณขนาด Lot"""
    
    def __init__(self, account_balance: float, risk_percentage: float = 2.0):
        """
        Args:
            account_balance: ยอดเงินในบัญชี
            risk_percentage: เปอร์เซ็นต์ความเสี่ยงต่อ Trade
        """
        self.account_balance = account_balance
        self.risk_percentage = risk_percentage
        
    def calculate_lot_by_risk_percentage(self, stop_loss_pips: float, pip_value: float = 10.0, symbol: str = "EURUSD") -> float:
        """
        คำนวณขนาด Lot ตามเปอร์เซ็นต์ความเสี่ยง
        
        Args:
            stop_loss_pips: จำนวน pips ของ Stop Loss
            pip_value: มูลค่าต่อ pip (default 10 สำหรับ EURUSD, 1000 สำหรับ XAUUSD)
            symbol: สัญลักษณ์การเทรด
            
        Returns:
            float: ขนาด Lot ที่แนะนำ
        """
        # ปรับ pip value สำหรับสัญลักษณ์ต่างๆ
        if 'XAU' in symbol.upper() or 'GOLD' in symbol.upper():
            pip_value = 1000.0  # XAUUSD มีมูลค่าต่อ pip สูงกว่า
        elif 'JPY' in symbol.upper():
            pip_value = 100.0   # JPY pairs
        else:
            pip_value = 10.0    # Major pairs
        if stop_loss_pips <= 0 or pip_value <= 0:
            return 0.01  # ขั้นต่ำ
            
        risk_amount = self.account_balance * (self.risk_percentage / 100)
        lot_size = risk_amount / (stop_loss_pips * pip_value)
        
        # ปรับให้อยู่ในช่วงที่เหมาะสม
        lot_size = max(0.01, min(lot_size, 10.0))
        
        # ปรับให้เป็นทศนิยม 2 ตำแหน่ง
        return round(lot_size, 2)
        
    def calculate_lot_by_balance_percentage(self, balance_percentage: float = 1.0, symbol: str = "EURUSD") -> float:
        """
        คำนวณขนาด Lot ตามเปอร์เซ็นต์ของยอดเงิน
        
        Args:
            balance_percentage: เปอร์เซ็นต์ของยอดเงินที่จะใช้
            symbol: สัญลักษณ์การเทรด
            
        Returns:
            float: ขนาด Lot ที่แนะนำ
        """
        if balance_percentage <= 0:
            return 0.01
            
        available_amount = self.account_balance * (balance_percentage / 100)
        
        # คำนวณขนาด lot ตามสัญลักษณ์
        if 'XAU' in symbol.upper() or 'GOLD' in symbol.upper():
            # XAUUSD: 1 lot = 100 oz, ราคาประมาณ $2000/oz
            lot_size = available_amount / 200000  # ประมาณการ margin requirement
        else:
            # Forex pairs: 1 lot = 100,000 units
            lot_size = available_amount / 100000
        
        # ปรับให้อยู่ในช่วงที่เหมาะสม
        lot_size = max(0.01, min(lot_size, 10.0))
        
        return round(lot_size, 2)
        
    def calculate_dynamic_lot_size(self, market_strength: float, volatility: float, 
                                  volume_factor: float = 1.0, balance_factor: float = 1.0) -> float:
        """
        คำนวณขนาด Lot แบบไดนามิกตามแรงตลาด ความผันผวน Volume และทุน
        
        Args:
            market_strength: แรงตลาดเป็นเปอร์เซ็นต์ (0-100)
            volatility: ความผันผวนเป็นเปอร์เซ็นต์
            volume_factor: ปัจจัย Volume ตลาด (1.0 = ปกติ, >1.0 = Volume สูง)
            balance_factor: ปัจจัยทุน (1.0 = ปกติ, >1.0 = ทุนเยอะ)
            
        Returns:
            float: ขนาด Lot ที่แนะนำ
        """
        base_lot = self.calculate_lot_by_balance_percentage(1.0)
        
        # ปรับตามแรงตลาด
        strength_multiplier = 1.0 + (market_strength / 100)
        
        # ปรับตามความผันผวน (ลดขนาดเมื่อผันผวนสูง)
        volatility_multiplier = 1.0 - (volatility / 200)  # ลดสูงสุด 50%
        volatility_multiplier = max(0.5, volatility_multiplier)
        
        # ปรับตาม Volume ตลาด
        volume_multiplier = min(2.0, max(0.5, volume_factor))  # จำกัด 0.5-2.0
        
        # ปรับตามทุนที่มี  
        balance_multiplier = min(3.0, max(0.3, balance_factor))  # จำกัด 0.3-3.0
        
        # คำนวณ lot size รวมทุกปัจจัย
        dynamic_lot = (base_lot * strength_multiplier * volatility_multiplier * 
                      volume_multiplier * balance_multiplier)
        
        # Debug logging
        logger.info(f"📊 Lot Calculation Details:")
        logger.info(f"   Base Lot: {base_lot:.4f}")
        logger.info(f"   Strength Multiplier: {strength_multiplier:.2f}")
        logger.info(f"   Volatility Multiplier: {volatility_multiplier:.2f}")
        logger.info(f"   Volume Multiplier: {volume_multiplier:.2f}")
        logger.info(f"   Balance Multiplier: {balance_multiplier:.2f}")
        logger.info(f"   Raw Dynamic Lot: {dynamic_lot:.4f}")
        
        # ปรับให้อยู่ในช่วงที่เหมาะสม
        dynamic_lot = max(0.01, min(dynamic_lot, 10.0))
        logger.info(f"   After Min/Max: {dynamic_lot:.4f}")
        
        # ปัดเศษตาม volume step (0.01)
        final_lot = LotSizeCalculator.round_to_volume_step(dynamic_lot, 0.01)
        logger.info(f"   Final Lot: {final_lot:.2f}")
        
        return final_lot
    
    def calculate_portfolio_risk_lot(self, positions_count: int, market_volatility: float, 
                                   account_balance: float = None) -> float:
        """
        คำนวณ Lot Size จากขนาด Portfolio และความผันผวนตลาด
        
        Args:
            positions_count: จำนวน positions ปัจจุบัน
            market_volatility: ความผันผวนตลาดเป็นเปอร์เซ็นต์ (ATR/Price * 100)
            account_balance: ยอดเงินในบัญชี (optional)
            
        Returns:
            float: ขนาด Lot ที่เหมาะสม (0.01 step)
        """
        try:
            # Base risk ตามจำนวนไม้ในพอร์ต
            if positions_count <= 5:       base_risk_pct = 15.0    # 15% - พอร์ตเล็ก เสี่ยงได้มาก
            elif positions_count <= 15:    base_risk_pct = 12.0    # 12% - พอร์ตปานกลาง
            elif positions_count <= 25:    base_risk_pct = 10.0    # 10% - พอร์ตใหญ่
            else:                          base_risk_pct = 8.0     # 8% - พอร์ตใหญ่มาก ระวัง
            
            # ปรับตามความผันผวนตลาด
            if market_volatility > 20.0:     volatility_multiplier = 1.3    # ตลาดผันผวนมาก เพิ่ม lot
            elif market_volatility > 10.0:   volatility_multiplier = 1.0    # ตลาดปกติ
            elif market_volatility > 5.0:    volatility_multiplier = 0.9    # ตลาดเงียบ ลด lot เล็กน้อย
            else:                            volatility_multiplier = 0.8    # ตลาดเงียบมาก ลด lot
            
            # คำนวณ risk percentage สุดท้าย
            final_risk_pct = base_risk_pct * volatility_multiplier
            final_risk_pct = max(8.0, min(20.0, final_risk_pct))  # จำกัด 8-20%
            
            # แปลงเป็น lot size
            balance = account_balance or self.account_balance
            risk_amount = balance * (final_risk_pct / 100)
            
            # ✅ ไม่มี SL - ใช้วิธีคำนวณแบบ Direct Risk Allocation
            # คำนวณ lot โดยตรงจาก risk percentage และ portfolio size
            
            # Base lot calculation จาก risk amount (เพิ่มขึ้นเพื่อ lot หลากหลาย)
            if positions_count <= 5:
                # Portfolio เล็ก - เสี่ยงได้มาก
                base_multiplier = 0.0012  # เพิ่มจาก 0.0008 → ~0.04-0.06 lot
            elif positions_count <= 15:
                # Portfolio ปานกลาง - เสี่ยงปานกลาง
                base_multiplier = 0.0010  # เพิ่มจาก 0.0006 → ~0.03-0.05 lot
            else:
                # Portfolio ใหญ่ - เสี่ยงน้อย
                base_multiplier = 0.0008  # เพิ่มจาก 0.0004 → ~0.02-0.04 lot
                
            # คำนวณ lot จาก risk amount โดยตรง
            base_lot = risk_amount * base_multiplier
            
            # 🎯 ปรับตามความผันผวนตลาด (Market Volatility Adjustment)
            if market_volatility > 20.0:
                volatility_adj = 1.3  # ตลาดผันผวนมาก → เพิ่ม lot
            elif market_volatility > 15.0:
                volatility_adj = 1.2  # ตลาดผันผวนปานกลางสูง
            elif market_volatility > 10.0:
                volatility_adj = 1.0  # ตลาดปกติ
            elif market_volatility > 5.0:
                volatility_adj = 0.9  # ตลาดเงียบ
            else:
                volatility_adj = 0.8  # ตลาดเงียบมาก
                
            calculated_lot = base_lot * volatility_adj
            
            # ปรับให้เป็น 0.01 step และจำกัดขอบเขต
            portfolio_lot = max(0.01, min(0.10, calculated_lot))
            portfolio_lot = round(portfolio_lot, 2)
            
            logger.info(f"📊 Portfolio Risk Lot Calculation (No SL):")
            logger.info(f"   Positions Count: {positions_count}")
            logger.info(f"   Market Volatility: {market_volatility:.1f}% → {volatility_adj:.1f}x")
            logger.info(f"   Base Risk: {base_risk_pct:.1f}%")
            logger.info(f"   Volatility Multiplier: {volatility_multiplier:.1f}x")
            logger.info(f"   Final Risk: {final_risk_pct:.1f}%")
            logger.info(f"   Risk Amount: ${risk_amount:.2f}")
            logger.info(f"   Base Multiplier: {base_multiplier:.6f}")
            logger.info(f"   Base Lot: {base_lot:.4f}")
            logger.info(f"   After Volatility: {calculated_lot:.4f}")
            logger.info(f"   Final Portfolio Lot: {portfolio_lot:.2f}")
            
            return portfolio_lot
            
        except Exception as e:
            logger.error(f"Error calculating portfolio risk lot: {e}")
            return 0.01  # fallback
    
    @staticmethod
    def calculate_market_volatility(candle_data: List[Any], atr_period: int = 14) -> float:
        """
        คำนวณความผันผวนตลาดจาก ATR และ Price Movement
        
        Args:
            candle_data: รายการข้อมูลแท่งเทียน (ต้องมี high, low, close)
            atr_period: ช่วงเวลาสำหรับคำนวณ ATR
            
        Returns:
            float: ความผันผวนเป็นเปอร์เซ็นต์
        """
        try:
            if not candle_data or len(candle_data) < atr_period:
                return 10.0  # default volatility
                
            # คำนวณ True Range สำหรับแต่ละแท่ง
            true_ranges = []
            
            for i in range(1, len(candle_data)):
                current = candle_data[i]
                previous = candle_data[i-1]
                
                # True Range = max(high-low, |high-prev_close|, |low-prev_close|)
                tr1 = current.high - current.low
                tr2 = abs(current.high - previous.close)
                tr3 = abs(current.low - previous.close)
                
                true_range = max(tr1, tr2, tr3)
                true_ranges.append(true_range)
            
            # คำนวณ ATR (Average True Range)
            if len(true_ranges) >= atr_period:
                recent_tr = true_ranges[-atr_period:]  # ใช้ข้อมูลล่าสุด
                atr = sum(recent_tr) / len(recent_tr)
                
                # แปลง ATR เป็นเปอร์เซ็นต์ของราคา
                current_price = candle_data[-1].close
                volatility_percentage = (atr / current_price) * 100
                
                # จำกัดให้อยู่ในช่วงสมเหตุสมผล
                volatility_percentage = max(1.0, min(50.0, volatility_percentage))
                
                logger.info(f"📊 Market Volatility Calculation:")
                logger.info(f"   ATR ({atr_period} periods): {atr:.4f}")
                logger.info(f"   Current Price: {current_price:.2f}")
                logger.info(f"   Volatility: {volatility_percentage:.2f}%")
                
                return volatility_percentage
            else:
                return 10.0  # default
                
        except Exception as e:
            logger.error(f"Error calculating market volatility: {e}")
            return 10.0  # default volatility
    
    @staticmethod
    def assess_volatility_level(volatility_pct: float) -> Dict[str, Any]:
        """
        ประเมินระดับความผันผวนและแนะนำ Risk Level
        
        Args:
            volatility_pct: ความผันผวนเป็นเปอร์เซ็นต์
            
        Returns:
            Dict: ข้อมูลระดับความผันผวนและคำแนะนำ
        """
        if volatility_pct > 25.0:
            level = "EXTREME"
            risk_suggestion = 20.0  # 20% risk
            description = "ตลาดผันผวนสุดขั้ว - เสี่ยงสูง แต่โอกาสมาก"
        elif volatility_pct > 20.0:
            level = "VERY_HIGH"  
            risk_suggestion = 18.0  # 18% risk
            description = "ตลาดผันผวนมากมาย - เสี่ยงสูง"
        elif volatility_pct > 15.0:
            level = "HIGH"
            risk_suggestion = 15.0  # 15% risk  
            description = "ตลาดผันผวนสูง - เสี่ยงปานกลางสูง"
        elif volatility_pct > 10.0:
            level = "MODERATE"
            risk_suggestion = 12.0  # 12% risk
            description = "ตลาดผันผวนปานกลาง - เสี่ยงปกติ"
        elif volatility_pct > 5.0:
            level = "LOW"
            risk_suggestion = 10.0  # 10% risk
            description = "ตลาดผันผวนต่ำ - เสี่ยงน้อย"
        else:
            level = "VERY_LOW"
            risk_suggestion = 8.0   # 8% risk
            description = "ตลาดเงียบมาก - เสี่ยงน้อยมาก"
        
        return {
            'level': level,
            'volatility_pct': volatility_pct,
            'risk_suggestion': risk_suggestion,
            'description': description,
            'lot_multiplier': risk_suggestion / 12.0  # normalize to 12% base
        }
        
    @staticmethod
    def round_to_volume_step(lot_size: float, volume_step: float = 0.01) -> float:
        """
        ปัดเศษ lot size ตาม volume step ของโบรกเกอร์
        
        Args:
            lot_size: ขนาด lot ที่คำนวณได้
            volume_step: ขั้นต่ำของ volume (เช่น 0.01)
            
        Returns:
            float: lot size ที่ปัดแล้ว
        """
        if volume_step <= 0:
            return round(lot_size, 2)
        
        # คำนวณจำนวนขั้นที่ใกล้เคียงที่สุด
        steps = lot_size / volume_step
        
        # ปัดเศษ: 0.016 -> 0.02, 0.015 -> 0.01
        if steps - int(steps) >= 0.6:
            rounded_steps = int(steps) + 1  # ปัดขึ้น
        elif steps - int(steps) <= 0.4:
            rounded_steps = int(steps)      # ปัดลง
        else:
            # 0.015 (steps = 1.5) -> ปัดลงเป็น 1 (0.01)
            rounded_steps = int(steps)
        
        result = rounded_steps * volume_step
        return max(volume_step, round(result, 2))  # ขั้นต่ำคือ volume_step
        
    @staticmethod
    def calculate_volume_factor(current_volume: float, volume_history: List[float]) -> float:
        """
        คำนวณปัจจัย Volume ตลาด
        
        Args:
            current_volume: Volume ปัจจุบัน
            volume_history: ประวัติ Volume
            
        Returns:
            float: ปัจจัย Volume (1.0 = ปกติ, >1.0 = สูง, <1.0 = ต่ำ)
        """
        if not volume_history or len(volume_history) < 5:
            return 1.0
        
        # คำนวณ Volume เฉลี่ย
        avg_volume = sum(volume_history[-20:]) / min(20, len(volume_history))
        
        if avg_volume <= 0:
            return 1.0
        
        # อัตราส่วน Volume ปัจจุบันต่อเฉลี่ย
        volume_ratio = current_volume / avg_volume
        
        # แปลงเป็นปัจจัย (1.0 = ปกติ)
        if volume_ratio >= 2.0:
            return 2.0  # Volume สูงมาก
        elif volume_ratio >= 1.5:
            return 1.5  # Volume สูง
        elif volume_ratio >= 1.2:
            return 1.2  # Volume ปานกลาง
        elif volume_ratio <= 0.5:
            return 0.5  # Volume ต่ำมาก
        elif volume_ratio <= 0.8:
            return 0.8  # Volume ต่ำ
        else:
            return 1.0  # Volume ปกติ
    
    @staticmethod
    def calculate_balance_factor(current_balance: float, initial_balance: float = 10000.0) -> float:
        """
        คำนวณปัจจัยทุน
        
        Args:
            current_balance: ทุนปัจจุบัน
            initial_balance: ทุนเริ่มต้น
            
        Returns:
            float: ปัจจัยทุน (1.0 = ปกติ, >1.0 = ทุนเพิ่ม, <1.0 = ทุนลด)
        """
        if initial_balance <= 0:
            return 1.0
        
        # อัตราส่วนทุนปัจจุบันต่อเริ่มต้น
        balance_ratio = current_balance / initial_balance
        
        # แปลงเป็นปัจจัย
        if balance_ratio >= 3.0:
            return 3.0  # ทุนเพิ่มมาก (300%+)
        elif balance_ratio >= 2.0:
            return 2.0  # ทุนเพิ่ม (200%+)
        elif balance_ratio >= 1.5:
            return 1.5  # ทุนเพิ่มเล็กน้อย (150%+)
        elif balance_ratio <= 0.3:
            return 0.3  # ทุนลดมาก (30%-)
        elif balance_ratio <= 0.5:
            return 0.5  # ทุนลด (50%-)
        elif balance_ratio <= 0.8:
            return 0.8  # ทุนลดเล็กน้อย (80%-)
        else:
            return balance_ratio  # ใช้อัตราส่วนจริง

class RiskCalculator:
    """คลาสสำหรับคำนวณความเสี่ยง"""
    
    @staticmethod
    def calculate_position_risk_percentage(position: Position, account_balance: float) -> float:
        """
        คำนวณเปอร์เซ็นต์ความเสี่ยงของ Position
        
        Args:
            position: ข้อมูล Position
            account_balance: ยอดเงินในบัญชี
            
        Returns:
            float: เปอร์เซ็นต์ความเสี่ยง
        """
        if account_balance <= 0:
            return 0.0
            
        # ความเสี่ยงคือขาดทุนปัจจุบัน (ถ้ามี)
        current_loss = min(0, position.profit + position.swap + position.commission)
        return abs(current_loss / account_balance) * 100
        
    @staticmethod
    def calculate_portfolio_risk_percentage(positions: List[Position], account_balance: float) -> Dict[str, float]:
        """
        คำนวณความเสี่ยงของพอร์ตรวม
        
        Args:
            positions: รายการ Position
            account_balance: ยอดเงินในบัญชี
            
        Returns:
            Dict: ข้อมูลความเสี่ยงต่างๆ
        """
        if not positions or account_balance <= 0:
            return {
                'total_risk_percentage': 0.0,
                'max_position_risk': 0.0,
                'losing_positions_count': 0,
                'total_unrealized_loss_percentage': 0.0
            }
            
        # คำนวณความเสี่ยงแต่ละ Position
        position_risks = []
        losing_positions = 0
        total_unrealized_loss = 0.0
        
        for position in positions:
            risk_pct = RiskCalculator.calculate_position_risk_percentage(position, account_balance)
            position_risks.append(risk_pct)
            
            current_profit = position.profit + position.swap + position.commission
            if current_profit < 0:
                losing_positions += 1
                total_unrealized_loss += abs(current_profit)
                
        return {
            'total_risk_percentage': sum(position_risks),
            'max_position_risk': max(position_risks) if position_risks else 0.0,
            'losing_positions_count': losing_positions,
            'total_unrealized_loss_percentage': (total_unrealized_loss / account_balance) * 100
        }
        
    @staticmethod
    def calculate_maximum_drawdown_percentage(equity_history: List[float]) -> float:
        """
        คำนวณ Maximum Drawdown เป็นเปอร์เซ็นต์
        
        Args:
            equity_history: ประวัติ Equity
            
        Returns:
            float: Maximum Drawdown เป็นเปอร์เซ็นต์
        """
        if not equity_history or len(equity_history) < 2:
            return 0.0
            
        max_drawdown = 0.0
        peak = equity_history[0]
        
        for equity in equity_history[1:]:
            if equity > peak:
                peak = equity
            else:
                drawdown = (peak - equity) / peak * 100
                max_drawdown = max(max_drawdown, drawdown)
                
        return max_drawdown

class MarketAnalysisCalculator:
    """คลาสสำหรับคำนวณการวิเคราะห์ตลาด"""
    
    @staticmethod
    def calculate_market_momentum_percentage(prices: List[float], volume: List[float] = None) -> float:
        """
        คำนวณแรงตลาดเป็นเปอร์เซ็นต์
        
        Args:
            prices: รายการราคา (Close prices)
            volume: รายการ Volume (ถ้ามี)
            
        Returns:
            float: แรงตลาดเป็นเปอร์เซ็นต์
        """
        if not prices or len(prices) < 2:
            return 0.0
            
        # คำนวณการเปลี่ยนแปลงราคา
        price_changes = []
        for i in range(1, len(prices)):
            change_pct = ((prices[i] - prices[i-1]) / prices[i-1]) * 100
            price_changes.append(change_pct)
            
        if not price_changes:
            return 0.0
            
        # คำนวณแรงตลาดโดยใช้ค่าเฉลี่ยของการเปลี่ยนแปลง
        momentum = sum(price_changes) / len(price_changes)
        
        # ปรับตาม Volume ถ้ามี
        if volume and len(volume) >= len(price_changes):
            avg_volume = sum(volume[-len(price_changes):]) / len(price_changes)
            volume_factor = min(2.0, avg_volume / (sum(volume) / len(volume)))  # ปรับสูงสุด 2 เท่า
            momentum *= volume_factor
            
        return abs(momentum)  # ส่งค่าสัมบูรณ์
        
    @staticmethod
    def calculate_pullback_percentage(high_price: float, current_price: float, low_price: float) -> float:
        """
        คำนวณเปอร์เซ็นต์ Pullback
        
        Args:
            high_price: ราคาสูงสุด
            current_price: ราคาปัจจุบัน
            low_price: ราคาต่ำสุด
            
        Returns:
            float: เปอร์เซ็นต์ Pullback
        """
        if high_price <= low_price:
            return 0.0
            
        # คำนวณ Pullback จาก High
        pullback_from_high = ((high_price - current_price) / (high_price - low_price)) * 100
        
        return max(0.0, pullback_from_high)
        
    @staticmethod
    def calculate_volatility_percentage(prices: List[float], period: int = 20) -> float:
        """
        คำนวณความผันผวนเป็นเปอร์เซ็นต์
        
        Args:
            prices: รายการราคา
            period: ระยะเวลาสำหรับคำนวณ
            
        Returns:
            float: ความผันผวนเป็นเปอร์เซ็นต์
        """
        if not prices or len(prices) < period:
            return 0.0
            
        recent_prices = prices[-period:]
        
        # คำนวณการเปลี่ยนแปลงราคารายวัน
        daily_changes = []
        for i in range(1, len(recent_prices)):
            change_pct = ((recent_prices[i] - recent_prices[i-1]) / recent_prices[i-1]) * 100
            daily_changes.append(change_pct)
            
        if not daily_changes:
            return 0.0
            
        # คำนวณ Standard Deviation
        mean_change = sum(daily_changes) / len(daily_changes)
        variance = sum((x - mean_change) ** 2 for x in daily_changes) / len(daily_changes)
        volatility = math.sqrt(variance)
        
        return volatility

class ProfitTargetCalculator:
    """คลาสสำหรับคำนวณเป้าหมายกำไร"""
    
    @staticmethod
    def calculate_profit_target_percentage(positions: List[Position], target_percentage: float, 
                                         account_balance: float) -> Dict[str, Any]:
        """
        คำนวณเป้าหมายกำไรเป็นเปอร์เซ็นต์
        
        Args:
            positions: รายการ Position
            target_percentage: เป้าหมายกำไรเป็นเปอร์เซ็นต์
            account_balance: ยอดเงินในบัญชี
            
        Returns:
            Dict: ข้อมูลเป้าหมายกำไร
        """
        if not positions or account_balance <= 0:
            return {
                'target_amount': 0.0,
                'current_profit_percentage': 0.0,
                'remaining_percentage': target_percentage,
                'achieved': False
            }
            
        target_amount = account_balance * (target_percentage / 100)
        current_profit = sum(pos.profit + pos.swap + pos.commission for pos in positions)
        current_profit_percentage = (current_profit / account_balance) * 100
        
        return {
            'target_amount': target_amount,
            'current_profit': current_profit,
            'current_profit_percentage': current_profit_percentage,
            'remaining_percentage': target_percentage - current_profit_percentage,
            'achieved': current_profit_percentage >= target_percentage
        }
        
    @staticmethod
    def calculate_scaling_ratios(positions: List[Position], scaling_type: str = "1:1") -> Dict[str, Any]:
        """
        คำนวณสัดส่วนการปิด Position แบบ Scaling
        
        Args:
            positions: รายการ Position
            scaling_type: ประเภทการ Scaling ("1:1", "1:2", "1:3", "2:3")
            
        Returns:
            Dict: ข้อมูลการ Scaling
        """
        if not positions:
            return {'positions_to_close': [], 'remaining_positions': []}
            
        # แยก Position กำไรและขาดทุน
        profit_positions = [pos for pos in positions if (pos.profit + pos.swap + pos.commission) > 0]
        loss_positions = [pos for pos in positions if (pos.profit + pos.swap + pos.commission) < 0]
        
        positions_to_close = []
        
        if scaling_type == "1:1":
            # ปิด 1 กำไร : 1 ขาดทุน
            min_count = min(len(profit_positions), len(loss_positions))
            positions_to_close = profit_positions[:min_count] + loss_positions[:min_count]
            
        elif scaling_type == "1:2":
            # ปิด 1 กำไร : 2 ขาดทุน
            profit_count = len(profit_positions)
            loss_count = min(profit_count * 2, len(loss_positions))
            positions_to_close = profit_positions + loss_positions[:loss_count]
            
        elif scaling_type == "1:3":
            # ปิด 1 กำไร : 3 ขาดทุน
            profit_count = len(profit_positions)
            loss_count = min(profit_count * 3, len(loss_positions))
            positions_to_close = profit_positions + loss_positions[:loss_count]
            
        elif scaling_type == "2:3":
            # ปิด 2 กำไร : 3 ขาดทุน
            max_sets = min(len(profit_positions) // 2, len(loss_positions) // 3)
            positions_to_close = profit_positions[:max_sets * 2] + loss_positions[:max_sets * 3]
            
        remaining_positions = [pos for pos in positions if pos not in positions_to_close]
        
        return {
            'positions_to_close': positions_to_close,
            'remaining_positions': remaining_positions,
            'close_count': len(positions_to_close),
            'remaining_count': len(remaining_positions)
        }
