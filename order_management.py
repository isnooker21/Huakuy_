# -*- coding: utf-8 -*-
"""
Order Management Module
โมดูลสำหรับจัดการและแก้ไข Orders/Positions
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from dataclasses import dataclass
from mt5_connection import MT5Connection
from calculations import Position, PercentageCalculator, LotSizeCalculator, ProfitTargetCalculator
from trading_conditions import Signal

logger = logging.getLogger(__name__)

@dataclass
class OrderResult:
    """คลาสสำหรับเก็บผลลัพธ์การส่ง Order"""
    success: bool
    ticket: Optional[int] = None
    error_message: str = ""
    order_details: Optional[Dict] = None

@dataclass
class CloseResult:
    """คลาสสำหรับเก็บผลลัพธ์การปิด Position"""
    success: bool
    closed_tickets: List[int]
    total_profit: float = 0.0
    error_message: str = ""
    close_details: Optional[Dict] = None

class OrderManager:
    """คลาสสำหรับจัดการ Orders และ Positions"""
    
    def __init__(self, mt5_connection: MT5Connection):
        """
        Args:
            mt5_connection: การเชื่อมต่อ MT5
        """
        self.mt5 = mt5_connection
        self.active_positions = []
        self.order_history = []
        self.magic_number = 12345  # Magic Number สำหรับระบุ Orders ของระบบ
        
    def place_order_from_signal(self, signal: Signal, lot_size: float, 
                               account_balance: float) -> OrderResult:
        """
        ส่ง Order จาก Signal
        
        Args:
            signal: สัญญาณการเทรด
            lot_size: ขนาด Lot
            account_balance: ยอดเงินในบัญชี
            
        Returns:
            OrderResult: ผลลัพธ์การส่ง Order
        """
        try:
            # ตรวจสอบการเชื่อมต่อ
            if not self.mt5.check_connection_health():
                return OrderResult(
                    success=False,
                    error_message="ไม่สามารถเชื่อมต่อ MT5 ได้"
                )
                
            # กำหนดประเภท Order
            if signal.direction == "BUY":
                order_type = 0  # mt5.ORDER_TYPE_BUY
                price = signal.price
            else:  # SELL
                order_type = 1  # mt5.ORDER_TYPE_SELL
                price = signal.price
                
            # ส่ง Order
            result = self.mt5.place_order(
                symbol=signal.symbol,
                order_type=order_type,
                volume=lot_size,
                price=price,
                sl=signal.stop_loss,
                tp=signal.take_profit,
                comment=f"Signal: {signal.comment}",
                magic=self.magic_number
            )
            
            if result and result.get('retcode') == 10009:  # TRADE_RETCODE_DONE
                # บันทึกข้อมูล Order
                position = Position(
                    ticket=result.get('order', 0),
                    symbol=signal.symbol,
                    type=order_type,
                    volume=lot_size,
                    price_open=result.get('price', price),
                    price_current=result.get('price', price),
                    profit=0.0,
                    comment=signal.comment,
                    magic=self.magic_number,
                    time_open=signal.timestamp
                )
                
                self.active_positions.append(position)
                
                logger.info(f"ส่ง Order สำเร็จ - Ticket: {position.ticket}, "
                           f"Direction: {signal.direction}, Volume: {lot_size}")
                
                return OrderResult(
                    success=True,
                    ticket=position.ticket,
                    order_details={
                        'signal': signal,
                        'lot_size': lot_size,
                        'price': result.get('price', price)
                    }
                )
            else:
                error_msg = f"ส่ง Order ไม่สำเร็จ - RetCode: {result.get('retcode') if result else 'None'}"
                logger.error(error_msg)
                return OrderResult(success=False, error_message=error_msg)
                
        except Exception as e:
            error_msg = f"เกิดข้อผิดพลาดในการส่ง Order: {str(e)}"
            logger.error(error_msg)
            return OrderResult(success=False, error_message=error_msg)
            
    def close_positions_group(self, positions: List[Position], reason: str = "") -> CloseResult:
        """
        ปิด Positions เป็นกลุ่ม (Group Close Only)
        
        Args:
            positions: รายการ Position ที่จะปิด
            reason: เหตุผลในการปิด
            
        Returns:
            CloseResult: ผลลัพธ์การปิด
        """
        try:
            if not positions:
                return CloseResult(
                    success=False,
                    closed_tickets=[],
                    error_message="ไม่มี Position ให้ปิด"
                )
                
            # ตรวจสอบการเชื่อมต่อ
            if not self.mt5.check_connection_health():
                return CloseResult(
                    success=False,
                    closed_tickets=[],
                    error_message="ไม่สามารถเชื่อมต่อ MT5 ได้"
                )
                
            closed_tickets = []
            total_profit = 0.0
            errors = []
            
            # ปิด Position ทีละตัว
            for position in positions:
                try:
                    result = self.mt5.close_position(position.ticket)
                    
                    if result and result.get('retcode') == 10009:  # TRADE_RETCODE_DONE
                        closed_tickets.append(position.ticket)
                        total_profit += position.profit + position.swap + position.commission
                        
                        # ลบจากรายการ active positions
                        self.active_positions = [
                            pos for pos in self.active_positions 
                            if pos.ticket != position.ticket
                        ]
                        
                        logger.info(f"ปิด Position สำเร็จ - Ticket: {position.ticket}")
                        
                    else:
                        error_msg = f"ปิด Position {position.ticket} ไม่สำเร็จ - RetCode: {result.get('retcode') if result else 'None'}"
                        errors.append(error_msg)
                        logger.error(error_msg)
                        
                except Exception as e:
                    error_msg = f"เกิดข้อผิดพลาดในการปิด Position {position.ticket}: {str(e)}"
                    errors.append(error_msg)
                    logger.error(error_msg)
                    
            # สรุปผลลัพธ์
            if closed_tickets:
                success_msg = f"ปิด {len(closed_tickets)} Positions สำเร็จ - Profit: {total_profit:.2f}, Reason: {reason}"
                logger.info(success_msg)
                
                return CloseResult(
                    success=True,
                    closed_tickets=closed_tickets,
                    total_profit=total_profit,
                    close_details={
                        'reason': reason,
                        'positions_count': len(closed_tickets),
                        'errors': errors
                    }
                )
            else:
                error_msg = f"ไม่สามารถปิด Position ใดได้ - Errors: {'; '.join(errors)}"
                return CloseResult(
                    success=False,
                    closed_tickets=[],
                    error_message=error_msg
                )
                
        except Exception as e:
            error_msg = f"เกิดข้อผิดพลาดในการปิดกลุ่ม Position: {str(e)}"
            logger.error(error_msg)
            return CloseResult(
                success=False,
                closed_tickets=[],
                error_message=error_msg
            )
            
    def close_positions_by_scaling_ratio(self, positions: List[Position], scaling_type: str = "1:1",
                                       reason: str = "") -> CloseResult:
        """
        ปิด Positions ตามสัดส่วน Scaling (1:1, 1:2, 1:3, 2:3)
        
        Args:
            positions: รายการ Position ทั้งหมด
            scaling_type: ประเภทการ Scaling
            reason: เหตุผลในการปิด
            
        Returns:
            CloseResult: ผลลัพธ์การปิด
        """
        try:
            # คำนวณสัดส่วนการปิด
            scaling_result = ProfitTargetCalculator.calculate_scaling_ratios(positions, scaling_type)
            positions_to_close = scaling_result['positions_to_close']
            
            if not positions_to_close:
                return CloseResult(
                    success=False,
                    closed_tickets=[],
                    error_message=f"ไม่มี Position ให้ปิดตามสัดส่วน {scaling_type}"
                )
                
            # ปิด Positions ที่เลือก
            close_reason = f"{reason} (Scaling: {scaling_type})"
            return self.close_positions_group(positions_to_close, close_reason)
            
        except Exception as e:
            error_msg = f"เกิดข้อผิดพลาดในการปิดตามสัดส่วน {scaling_type}: {str(e)}"
            logger.error(error_msg)
            return CloseResult(
                success=False,
                closed_tickets=[],
                error_message=error_msg
            )
            
    def modify_position_sl_tp(self, ticket: int, new_sl: float = 0, new_tp: float = 0) -> bool:
        """
        แก้ไข Stop Loss และ Take Profit ของ Position
        
        Args:
            ticket: หมายเลข Position
            new_sl: Stop Loss ใหม่
            new_tp: Take Profit ใหม่
            
        Returns:
            bool: สำเร็จหรือไม่
        """
        try:
            # หาข้อมูล Position
            position = next((pos for pos in self.active_positions if pos.ticket == ticket), None)
            if not position:
                logger.error(f"ไม่พบ Position ticket {ticket}")
                return False
                
            # ใช้ MT5 API สำหรับแก้ไข (ถ้ามี)
            # สำหรับตอนนี้จะอัพเดทใน local data เท่านั้น
            logger.info(f"แก้ไข Position {ticket} - SL: {new_sl}, TP: {new_tp}")
            return True
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการแก้ไข Position {ticket}: {str(e)}")
            return False
            
    def sync_positions_from_mt5(self) -> List[Position]:
        """
        ซิงค์ข้อมูล Position จาก MT5
        
        Returns:
            List[Position]: รายการ Position ปัจจุบัน
        """
        try:
            if not self.mt5.check_connection_health():
                logger.error("ไม่สามารถเชื่อมต่อ MT5 เพื่อซิงค์ข้อมูล")
                return self.active_positions
                
            # ดึงข้อมูล Position จาก MT5
            mt5_positions = self.mt5.get_positions()
            
            # กรองเฉพาะ Position ของระบบ (ตาม Magic Number)
            system_positions = [
                pos for pos in mt5_positions 
                if pos.get('magic') == self.magic_number
            ]
            
            # แปลงเป็น Position objects
            synced_positions = []
            for pos_data in system_positions:
                position = Position(
                    ticket=pos_data['ticket'],
                    symbol=pos_data['symbol'],
                    type=pos_data['type'],
                    volume=pos_data['volume'],
                    price_open=pos_data['price_open'],
                    price_current=pos_data['price_current'],
                    profit=pos_data['profit'],
                    swap=pos_data.get('swap', 0.0),
                    commission=pos_data.get('commission', 0.0),
                    comment=pos_data.get('comment', ''),
                    magic=pos_data.get('magic', 0),
                    time_open=pos_data.get('time')
                )
                synced_positions.append(position)
                
            # อัพเดท active positions
            self.active_positions = synced_positions
            
            logger.info(f"ซิงค์ข้อมูล Position สำเร็จ - จำนวน: {len(synced_positions)}")
            return synced_positions
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการซิงค์ข้อมูล Position: {str(e)}")
            return self.active_positions
            
    def get_positions_by_symbol(self, symbol: str) -> List[Position]:
        """
        ดึง Position ตามสัญลักษณ์
        
        Args:
            symbol: สัญลักษณ์การเทรด
            
        Returns:
            List[Position]: รายการ Position ของสัญลักษณ์นั้น
        """
        return [pos for pos in self.active_positions if pos.symbol == symbol]
        
    def get_positions_by_type(self, position_type: int) -> List[Position]:
        """
        ดึง Position ตามประเภท (BUY/SELL)
        
        Args:
            position_type: ประเภท Position (0=BUY, 1=SELL)
            
        Returns:
            List[Position]: รายการ Position ตามประเภท
        """
        return [pos for pos in self.active_positions if pos.type == position_type]
        
    def get_profitable_positions(self) -> List[Position]:
        """
        ดึง Position ที่กำไร
        
        Returns:
            List[Position]: รายการ Position ที่กำไร
        """
        return [
            pos for pos in self.active_positions 
            if (pos.profit + pos.swap + pos.commission) > 0
        ]
        
    def get_losing_positions(self) -> List[Position]:
        """
        ดึง Position ที่ขาดทุน
        
        Returns:
            List[Position]: รายการ Position ที่ขาดทุน
        """
        return [
            pos for pos in self.active_positions 
            if (pos.profit + pos.swap + pos.commission) < 0
        ]
        
    def calculate_total_profit_loss(self) -> Dict[str, float]:
        """
        คำนวณกำไรขาดทุนรวม
        
        Returns:
            Dict: ข้อมูลกำไรขาดทุนรวม
        """
        if not self.active_positions:
            return {
                'total_profit': 0.0,
                'total_swap': 0.0,
                'total_commission': 0.0,
                'net_profit': 0.0,
                'profitable_count': 0,
                'losing_count': 0
            }
            
        total_profit = sum(pos.profit for pos in self.active_positions)
        total_swap = sum(pos.swap for pos in self.active_positions)
        total_commission = sum(pos.commission for pos in self.active_positions)
        net_profit = total_profit + total_swap + total_commission
        
        profitable_count = len(self.get_profitable_positions())
        losing_count = len(self.get_losing_positions())
        
        return {
            'total_profit': total_profit,
            'total_swap': total_swap,
            'total_commission': total_commission,
            'net_profit': net_profit,
            'profitable_count': profitable_count,
            'losing_count': losing_count
        }
        
    def emergency_close_all(self, reason: str = "Emergency Close") -> CloseResult:
        """
        ปิด Position ทั้งหมดในกรณีฉุกเฉิน
        
        Args:
            reason: เหตุผลในการปิด
            
        Returns:
            CloseResult: ผลลัพธ์การปิด
        """
        logger.warning(f"เริ่มปิด Position ทั้งหมดในกรณีฉุกเฉิน - เหตุผล: {reason}")
        
        if not self.active_positions:
            return CloseResult(
                success=True,
                closed_tickets=[],
                error_message="ไม่มี Position ให้ปิด"
            )
            
        return self.close_positions_group(self.active_positions, reason)
        
    def get_position_statistics(self, account_balance: float) -> Dict[str, Any]:
        """
        คำนวณสถิติของ Position
        
        Args:
            account_balance: ยอดเงินในบัญชี
            
        Returns:
            Dict: สถิติต่างๆ
        """
        if not self.active_positions:
            return {
                'total_positions': 0,
                'buy_sell_ratio': {'buy_percentage': 0, 'sell_percentage': 0},
                'total_profit_percentage': 0.0,
                'exposure_percentage': 0.0,
                'risk_percentage': 0.0
            }
            
        # คำนวณสัดส่วน Buy:Sell
        buy_sell_ratio = PercentageCalculator.calculate_buy_sell_ratio(self.active_positions)
        
        # คำนวณกำไรขาดทุนเป็นเปอร์เซ็นต์
        profit_percentage = PercentageCalculator.calculate_group_profit_percentage(
            self.active_positions, account_balance
        )
        
        # คำนวณการใช้เงินทุน
        exposure_percentage = PercentageCalculator.calculate_portfolio_exposure_percentage(
            self.active_positions, account_balance
        )
        
        # คำนวณความเสี่ยง
        from calculations import RiskCalculator
        risk_info = RiskCalculator.calculate_portfolio_risk_percentage(
            self.active_positions, account_balance
        )
        
        return {
            'total_positions': len(self.active_positions),
            'buy_sell_ratio': buy_sell_ratio,
            'total_profit_percentage': profit_percentage,
            'exposure_percentage': exposure_percentage,
            'risk_percentage': risk_info['total_risk_percentage'],
            'losing_positions_count': risk_info['losing_positions_count'],
            'max_position_risk': risk_info['max_position_risk']
        }
