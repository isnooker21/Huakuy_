# -*- coding: utf-8 -*-
"""
MT5 Connection Module
โมดูลสำหรับการเชื่อมต่อและจัดการ MetaTrader 5
"""

import logging
import time
from typing import Optional, Dict, List, Any
from datetime import datetime

# Safe import for MT5
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    print("WARNING: MetaTrader5 not available - running in simulation mode")
    mt5 = None
    MT5_AVAILABLE = False

logger = logging.getLogger(__name__)

class MT5Connection:
    """คลาสสำหรับจัดการการเชื่อมต่อ MT5"""
    
    def __init__(self):
        self.is_connected = False
        self.terminal_info = None
        self.account_info = None
        self.last_connection_check = None
        
    def connect_mt5(self, max_retries: int = 3, retry_delay: float = 2.0) -> bool:
        """
        เชื่อมต่อ MT5 Terminal
        
        Args:
            max_retries: จำนวนครั้งที่พยายามเชื่อมต่อ
            retry_delay: ระยะเวลารอระหว่างการพยายาม
            
        Returns:
            bool: สถานะการเชื่อมต่อ
        """
        if not MT5_AVAILABLE:
            logger.error("MT5 module not available")
            return False
            
        for attempt in range(max_retries):
            try:
                logger.info(f"กำลังพยายามเชื่อมต่อ MT5 ครั้งที่ {attempt + 1}")
                
                # พยายามเชื่อมต่อ
                if mt5.initialize():
                    self.is_connected = True
                    self.terminal_info = mt5.terminal_info()
                    self.account_info = mt5.account_info()
                    self.last_connection_check = datetime.now()
                    
                    logger.info(f"เชื่อมต่อ MT5 สำเร็จ - Terminal: {self.terminal_info.name}")
                    logger.info(f"Account: {self.account_info.login}, Balance: {self.account_info.balance}")
                    return True
                    
                else:
                    error = mt5.last_error()
                    logger.error(f"ไม่สามารถเชื่อมต่อ MT5 ได้: {error}")
                    
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ MT5: {e}")
                
            if attempt < max_retries - 1:
                logger.info(f"รอ {retry_delay} วินาที ก่อนพยายามใหม่...")
                time.sleep(retry_delay)
                
        logger.error("ไม่สามารถเชื่อมต่อ MT5 ได้หลังจากพยายาม")
        return False
        
    def connect_to_specific_terminal(self, terminal_path: str, max_retries: int = 3, retry_delay: float = 2.0) -> bool:
        """
        เชื่อมต่อ MT5 Terminal ที่ระบุ path
        
        Args:
            terminal_path: path ของ MT5 Terminal
            max_retries: จำนวนครั้งที่พยายามเชื่อมต่อ
            retry_delay: ระยะเวลารอระหว่างการพยายาม
            
        Returns:
            bool: สถานะการเชื่อมต่อ
        """
        if not MT5_AVAILABLE:
            logger.error("MT5 module not available")
            return False
            
        for attempt in range(max_retries):
            try:
                logger.info(f"กำลังพยายามเชื่อมต่อ MT5 ที่ {terminal_path} ครั้งที่ {attempt + 1}")
                
                # พยายามเชื่อมต่อกับ terminal ที่ระบุ
                if mt5.initialize(path=terminal_path):
                    self.is_connected = True
                    self.terminal_info = mt5.terminal_info()
                    self.account_info = mt5.account_info()
                    self.last_connection_check = datetime.now()
                    
                    logger.info(f"เชื่อมต่อ MT5 สำเร็จ - Terminal: {self.terminal_info.name}")
                    logger.info(f"Path: {terminal_path}")
                    logger.info(f"Account: {self.account_info.login}, Balance: {self.account_info.balance}")
                    return True
                    
                else:
                    error = mt5.last_error()
                    logger.error(f"ไม่สามารถเชื่อมต่อ MT5 ได้: {error}")
                    
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ MT5: {e}")
                
            if attempt < max_retries - 1:
                logger.info(f"รอ {retry_delay} วินาที ก่อนพยายามใหม่...")
                time.sleep(retry_delay)
                
        logger.error("ไม่สามารถเชื่อมต่อ MT5 ได้หลังจากพยายาม")
        return False
        
    def check_connection_health(self) -> bool:
        """
        ตรวจสอบสุขภาพการเชื่อมต่อ MT5
        
        Returns:
            bool: สถานะการเชื่อมต่อ
        """
        if not MT5_AVAILABLE or not self.is_connected:
            return False
            
        try:
            # ตรวจสอบด้วยการเรียก terminal info
            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                logger.warning("การเชื่อมต่อ MT5 หลุด")
                self.is_connected = False
                return False
                
            # อัพเดท account info
            self.account_info = mt5.account_info()
            self.last_connection_check = datetime.now()
            return True
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการตรวจสอบการเชื่อมต่อ: {e}")
            self.is_connected = False
            return False
            
    def attempt_reconnection(self) -> bool:
        """
        พยายามเชื่อมต่อใหม่
        
        Returns:
            bool: สถานะการเชื่อมต่อ
        """
        logger.info("กำลังพยายามเชื่อมต่อ MT5 ใหม่...")
        
        # ปิดการเชื่อมต่อเก่าก่อน
        self.disconnect_mt5()
        
        # พยายามเชื่อมต่อใหม่
        return self.connect_mt5()
        
    def disconnect_mt5(self):
        """ปิดการเชื่อมต่อ MT5"""
        if MT5_AVAILABLE and self.is_connected:
            try:
                mt5.shutdown()
                logger.info("ปิดการเชื่อมต่อ MT5 แล้ว")
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการปิดการเชื่อมต่อ MT5: {e}")
                
        self.is_connected = False
        self.terminal_info = None
        self.account_info = None
        self.last_connection_check = None
        
    def get_account_info(self) -> Optional[Dict]:
        """
        ดึงข้อมูล Account
        
        Returns:
            Dict: ข้อมูล Account หรือ None
        """
        if not self.check_connection_health():
            return None
            
        try:
            account_info = mt5.account_info()
            if account_info:
                return {
                    'login': account_info.login,
                    'balance': account_info.balance,
                    'equity': account_info.equity,
                    'margin': account_info.margin,
                    'margin_free': account_info.margin_free,
                    'margin_level': account_info.margin_level,
                    'profit': account_info.profit,
                    'currency': account_info.currency,
                    'leverage': account_info.leverage
                }
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูล Account: {e}")
            
        return None
        
    def get_terminal_info(self) -> Optional[Dict]:
        """
        ดึงข้อมูล Terminal
        
        Returns:
            Dict: ข้อมูล Terminal หรือ None
        """
        if not self.check_connection_health():
            return None
            
        try:
            terminal_info = mt5.terminal_info()
            if terminal_info:
                return {
                    'name': terminal_info.name,
                    'path': terminal_info.path,
                    'data_path': terminal_info.data_path,
                    'commondata_path': terminal_info.commondata_path,
                    'build': terminal_info.build,
                    'connected': terminal_info.connected,
                    'trade_allowed': terminal_info.trade_allowed,
                    'tradeapi_disabled': terminal_info.tradeapi_disabled,
                    'x64': terminal_info.x64
                }
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูล Terminal: {e}")
            
        return None
        
    def get_symbol_info(self, symbol: str) -> Optional[Dict]:
        """
        ดึงข้อมูลของสัญลักษณ์การเทรด
        
        Args:
            symbol: สัญลักษณ์การเทรด (เช่น EURUSD)
            
        Returns:
            Dict: ข้อมูลสัญลักษณ์ หรือ None
        """
        if not self.check_connection_health():
            return None
            
        try:
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info:
                return {
                    'name': symbol_info.name,
                    'currency_base': symbol_info.currency_base,
                    'currency_profit': symbol_info.currency_profit,
                    'currency_margin': symbol_info.currency_margin,
                    'digits': symbol_info.digits,
                    'point': symbol_info.point,
                    'spread': symbol_info.spread,
                    'volume_min': symbol_info.volume_min,
                    'volume_max': symbol_info.volume_max,
                    'volume_step': symbol_info.volume_step,
                    'trade_contract_size': symbol_info.trade_contract_size,
                    'trade_tick_value': symbol_info.trade_tick_value,
                    'trade_tick_size': symbol_info.trade_tick_size,
                    'margin_initial': symbol_info.margin_initial,
                    'margin_maintenance': symbol_info.margin_maintenance,
                    'bid': symbol_info.bid,
                    'ask': symbol_info.ask,
                    'last': symbol_info.last,
                    'time': symbol_info.time
                }
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลสัญลักษณ์ {symbol}: {e}")
            
        return None
        
    def get_market_data(self, symbol: str, timeframe: int, count: int = 100) -> Optional[List[Dict]]:
        """
        ดึงข้อมูลราคา (OHLC)
        
        Args:
            symbol: สัญลักษณ์การเทรด
            timeframe: กรอบเวลา (mt5.TIMEFRAME_*)
            count: จำนวนแท่งเทียน
            
        Returns:
            List[Dict]: ข้อมูลราคา หรือ None
        """
        if not self.check_connection_health():
            return None
            
        try:
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            if rates is not None and len(rates) > 0:
                return [
                    {
                        'time': rate[0],
                        'open': rate[1],
                        'high': rate[2],
                        'low': rate[3],
                        'close': rate[4],
                        'tick_volume': rate[5],
                        'spread': rate[6],
                        'real_volume': rate[7]
                    }
                    for rate in rates
                ]
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดึงข้อมูลราคา {symbol}: {e}")
            
        return None
        
    def get_positions(self) -> List[Dict]:
        """
        ดึงรายการ Position ที่เปิดอยู่
        
        Returns:
            List[Dict]: รายการ Position
        """
        if not self.check_connection_health():
            return []
            
        try:
            positions = mt5.positions_get()
            if positions:
                return [
                    {
                        'ticket': pos.ticket,
                        'symbol': pos.symbol,
                        'type': pos.type,
                        'volume': pos.volume,
                        'price_open': pos.price_open,
                        'price_current': pos.price_current,
                        'profit': pos.profit,
                        'swap': pos.swap,
                        'commission': pos.commission,
                        'time': pos.time,
                        'comment': pos.comment,
                        'magic': pos.magic
                    }
                    for pos in positions
                ]
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการดึงรายการ Position: {e}")
            
        return []
        
    def place_order(self, symbol: str, order_type: int, volume: float, 
                   price: float = 0, sl: float = 0, tp: float = 0, 
                   comment: str = "", magic: int = 0) -> Optional[Dict]:
        """
        ส่ง Order
        
        Args:
            symbol: สัญลักษณ์การเทรด
            order_type: ประเภท Order (mt5.ORDER_TYPE_*)
            volume: ขนาด lot
            price: ราคา (สำหรับ pending order)
            sl: Stop Loss
            tp: Take Profit
            comment: หมายเหตุ
            magic: Magic Number
            
        Returns:
            Dict: ผลลัพธ์การส่ง Order หรือ None
        """
        if not self.check_connection_health():
            return None
            
        try:
            # เตรียมข้อมูล request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "sl": sl,
                "tp": tp,
                "comment": comment,
                "magic": magic,
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            
            # ส่ง Order
            result = mt5.order_send(request)
            if result:
                return {
                    'retcode': result.retcode,
                    'deal': result.deal,
                    'order': result.order,
                    'volume': result.volume,
                    'price': result.price,
                    'bid': result.bid,
                    'ask': result.ask,
                    'comment': result.comment,
                    'request_id': result.request_id,
                    'retcode_external': result.retcode_external
                }
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการส่ง Order: {e}")
            
        return None
        
    def close_position(self, ticket: int) -> Optional[Dict]:
        """
        ปิด Position
        
        Args:
            ticket: หมายเลข Position
            
        Returns:
            Dict: ผลลัพธ์การปิด Position หรือ None
        """
        if not self.check_connection_health():
            return None
            
        try:
            # ดึงข้อมูล Position
            position = mt5.positions_get(ticket=ticket)
            if not position:
                logger.error(f"ไม่พบ Position ticket {ticket}")
                return None
                
            pos = position[0]
            
            # กำหนดประเภท Order สำหรับปิด Position
            if pos.type == mt5.POSITION_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(pos.symbol).bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(pos.symbol).ask
                
            # เตรียมข้อมูล request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "comment": f"Close position {ticket}",
                "type_filling": mt5.ORDER_FILLING_FOK,
            }
            
            # ปิด Position
            result = mt5.order_send(request)
            if result:
                return {
                    'retcode': result.retcode,
                    'deal': result.deal,
                    'order': result.order,
                    'volume': result.volume,
                    'price': result.price,
                    'comment': result.comment
                }
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการปิด Position {ticket}: {e}")
            
        return None
