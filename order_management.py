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
        self.magic_number = 123456  # Magic Number สำหรับระบุ Orders ของระบบ (เหมือน test file)
        
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
            logger.info(f"📥 OrderManager รับคำสั่งจาก SmartEntrySystem")
            logger.info(f"   Signal: {signal.direction} {signal.symbol} at {signal.price}")
            logger.info(f"   Lot Size: {lot_size}, Account Balance: {account_balance}")
            logger.info(f"   Comment: {signal.comment} (Type: {type(signal.comment)})")
            
            # ตรวจสอบการเชื่อมต่อ
            if not self.mt5.check_connection_health():
                logger.error(f"❌ OrderManager: ไม่สามารถเชื่อมต่อ MT5 ได้")
                return OrderResult(
                    success=False,
                    error_message="ไม่สามารถเชื่อมต่อ MT5 ได้"
                )
                
            # ตรวจสอบและปรับ lot size ให้ตรงกับ symbol
            import MetaTrader5 as mt5
            mt5_symbol_info = mt5.symbol_info(signal.symbol)
            if mt5_symbol_info:
                # ปรับ lot size ให้ตรงกับ volume_step
                volume_step = mt5_symbol_info.volume_step
                adjusted_lot = round(lot_size / volume_step) * volume_step
                
                # ตรวจสอบขั้นต่ำและขั้นสูง
                if adjusted_lot < mt5_symbol_info.volume_min:
                    adjusted_lot = mt5_symbol_info.volume_min
                elif adjusted_lot > mt5_symbol_info.volume_max:
                    adjusted_lot = mt5_symbol_info.volume_max
                
                if adjusted_lot != lot_size:
                    logger.info(f"🔧 ปรับ Lot Size จาก {lot_size} เป็น {adjusted_lot}")
                    lot_size = adjusted_lot
            
            # กำหนดประเภท Order
            if signal.direction == "BUY":
                order_type = 0  # mt5.ORDER_TYPE_BUY
                price = signal.price
            else:  # SELL
                order_type = 1  # mt5.ORDER_TYPE_SELL
                price = signal.price
                
            # ส่ง Order
            # ปรับปรุง comment ให้ชัดเจน - ตรวจสอบอย่างปลอดภัย
            try:
                if signal.comment is not None and str(signal.comment).strip():
                    order_comment = str(signal.comment).strip()
                else:
                    order_comment = f"SmartEntry_{signal.direction}"
            except Exception as e:
                logger.warning(f"⚠️ Error processing comment: {e}")
                order_comment = f"SmartEntry_{signal.direction}"
            
            logger.info(f"📝 Final Order Comment: {order_comment}")
            
            result = self.mt5.place_order(
                symbol=signal.symbol,
                order_type=order_type,
                volume=lot_size,
                price=price,
                sl=signal.stop_loss,
                tp=signal.take_profit,
                comment=order_comment,
                magic=self.magic_number
            )
            
            # ตรวจสอบผลลัพธ์อย่างละเอียด
            if result is None:
                error_msg = "ส่ง Order ไม่สำเร็จ - mt5.order_send() ส่งคืน None"
                logger.error(f"❌ {error_msg}")
                return OrderResult(success=False, error_message=error_msg)
                
            retcode = result.get('retcode')
            logger.info(f"📋 Order Response: RetCode={retcode}")
            
            if retcode == 10009:  # TRADE_RETCODE_DONE
                # บันทึกข้อมูล Order
                deal_id = result.get('deal', 0)
                order_id = result.get('order', 0)
                
                # ใช้ deal_id เป็น ticket หลัก
                ticket = deal_id if deal_id > 0 else order_id
                
                position = Position(
                    ticket=ticket,
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
                
                logger.info(f"✅ OrderManager: Order sent successfully - Ticket: {ticket}")
                logger.info(f"   📤 ส่งคำสั่งไปยัง MT5 ผ่าน mt5_connection.py")
                logger.info(f"   📝 Comment sent to MT5: {order_comment}")
                
                return OrderResult(
                    success=True,
                    ticket=ticket,
                    order_details={
                        'signal': signal,
                        'lot_size': lot_size,
                        'price': result.get('price', price),
                        'deal_id': deal_id,
                        'order_id': order_id
                    }
                )
            else:
                # แสดง error พร้อมคำอธิบาย
                error_desc = result.get('error_description', f'RetCode: {retcode}')
                error_msg = f"ส่ง Order ไม่สำเร็จ - {error_desc}"
                logger.error(f"❌ {error_msg}")
                
                # แสดงข้อมูล request ที่ส่งไป
                logger.error(f"   Request: Symbol={signal.symbol}, Direction={signal.direction}, Volume={lot_size}")
                logger.error(f"   Price={price}, Account Balance={account_balance:,.2f}")
                
                return OrderResult(success=False, error_message=error_msg)
                
        except Exception as e:
            error_msg = f"เกิดข้อผิดพลาดในการส่ง Order: {str(e)}"
            logger.error(error_msg)
            return OrderResult(success=False, error_message=error_msg)
            
    def close_positions_group_raw(self, positions: List[Position], reason: str = "") -> CloseResult:
        """
        ส่งคำสั่งปิด Positions ไปยัง MT5 โดยตรง (Raw MT5 Command)
        
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
            
            # ดึง tickets จาก positions
            tickets = []
            for pos in positions:
                if isinstance(pos, dict):
                    ticket = pos.get('ticket')
                else:
                    ticket = getattr(pos, 'ticket', None)
                
                if ticket:
                    tickets.append(ticket)
            
            if not tickets:
                return CloseResult(
                    success=False,
                    closed_tickets=[],
                    error_message="ไม่พบ Ticket ที่ถูกต้อง"
                )
            
            # ส่งคำสั่งปิดไปยัง MT5
            logger.info(f"📤 ส่งคำสั่งปิด {len(tickets)} positions ไปยัง MT5")
            group_result = self.mt5.close_positions_group_raw(tickets)
            
            # ประมวลผลลัพธ์
            closed_tickets = group_result.get('closed_tickets', [])
            total_profit = group_result.get('total_profit', 0.0)
            
            # อัพเดท active positions
            self.active_positions = [
                pos for pos in self.active_positions 
                if (pos['ticket'] if isinstance(pos, dict) else getattr(pos, 'ticket', None)) not in closed_tickets
            ]
            
            if closed_tickets:
                logger.info(f"✅ ปิด Position สำเร็จ: {len(closed_tickets)} ตัว - กำไร: ${total_profit:.2f}")
                return CloseResult(
                    success=True,
                    closed_tickets=closed_tickets,
                    total_profit=total_profit,
                    close_details={
                        'reason': reason,
                        'positions_count': len(closed_tickets)
                    }
                )
            else:
                error_msg = group_result.get('error_message', 'ไม่สามารถปิด Position ได้')
                return CloseResult(
                    success=False,
                    closed_tickets=[],
                    error_message=error_msg
                )
                
        except Exception as e:
            error_msg = f"เกิดข้อผิดพลาดในการปิด Position: {str(e)}"
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
            position = next((pos for pos in self.active_positions if (pos['ticket'] if isinstance(pos, dict) else getattr(pos, 'ticket', None)) == ticket), None)
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
            
            # 🔍 DEBUG: Show all MT5 positions with magic numbers
            logger.info(f"🔍 MT5 RAW POSITIONS: {len(mt5_positions)} total positions")
            if mt5_positions:
                magic_numbers = {}
                for pos in mt5_positions[:5]:  # Show first 5
                    magic = pos.get('magic', 'NO_MAGIC')
                    ticket = pos.get('ticket', 'NO_TICKET')
                    magic_numbers[magic] = magic_numbers.get(magic, 0) + 1
                    logger.info(f"   Ticket {ticket}: Magic={magic}")
                
                logger.info(f"🔍 Magic Number Summary: {magic_numbers}")
                logger.info(f"🔍 System Magic Number: {self.magic_number}")
            
            # 🚨 DIRECT BROKER ACCESS: ใช้ positions ทั้งหมดจากโบรกเกอร์
            logger.info(f"💎 DIRECT BROKER ACCESS: Using ALL {len(mt5_positions)} positions from broker")
            system_positions = mt5_positions  # ใช้ทั้งหมดโดยไม่กรอง Magic Number
            
            # # เดิม: กรองเฉพาะ Position ของระบบ (ตาม Magic Number) - DISABLED
            # system_positions = [
            #     pos for pos in mt5_positions 
            #     if pos.get('magic') == self.magic_number
            # ]
            
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
            
            logger.info(f"📊 ซิงค์ข้อมูล Position สำเร็จ - จำนวน: {len(synced_positions)}")
            
            # แสดงจำนวนสุทธิ
            if synced_positions:
                logger.info(f"📊 Synced positions: {len(synced_positions)}")
            else:
                logger.info("ℹ️ ไม่พบ Position เก่าของระบบ (Magic Number: {})".format(self.magic_number))
            return synced_positions
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการซิงค์ข้อมูล Position: {str(e)}")
            return self.active_positions
            
    def get_positions(self) -> List[Position]:
        """
        ดึง Position ทั้งหมด
        
        Returns:
            List[Position]: รายการ Position ทั้งหมด
        """
        return self.active_positions.copy()
        
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
                'buy_sell_ratio': {
                    'buy_percentage': 0, 
                    'sell_percentage': 0,
                    'buy_count': 0,
                    'sell_count': 0,
                    'total_positions': 0
                },
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
    
