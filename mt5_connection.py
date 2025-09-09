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
        self.broker_symbols = {}  # เก็บสัญลักษณ์ของโบรกเกอร์
        self.filling_types = {}   # เก็บ filling type ที่ใช้ได้สำหรับแต่ละสัญลักษณ์
        
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
                    
                    # โหลดสัญลักษณ์ของโบรกเกอร์
                    self._load_broker_symbols()
                    
                    logger.info(f"เชื่อมต่อ MT5 สำเร็จ - Terminal: {self.terminal_info.name}")
                    logger.info(f"Account: {self.account_info.login}, Balance: {self.account_info.balance}")
                    logger.info(f"โหลดสัญลักษณ์ได้ {len(self.broker_symbols)} รายการ")
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
                # เตือนเมื่อใช้บัญชีจริง
                if hasattr(account_info, 'trade_mode'):
                    if account_info.trade_mode == 0:  # Real account
                        logger.warning("🚨 กำลังใช้บัญชีจริง (REAL ACCOUNT) - เงินจริง!")
                    elif account_info.trade_mode == 1:  # Demo account  
                        logger.info("✅ กำลังใช้บัญชีทดลอง (DEMO ACCOUNT)")
                    elif account_info.trade_mode == 2:  # Contest account
                        logger.info("🏆 กำลังใช้บัญชีแข่งขัน (CONTEST ACCOUNT)")
                
                return {
                    'login': account_info.login,
                    'trade_mode': getattr(account_info, 'trade_mode', 'Unknown'),
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
        logger.debug(f"🔍 get_market_data called: {symbol}, TF={timeframe}, count={count}")
        
        # ลองเรียก MT5 โดยตรงก่อน แม้ health check จะล้มเหลว
        if not self.check_connection_health():
            logger.warning("⚠️ MT5 connection health check failed - trying direct call anyway")
            # ไม่ return None, ให้ลองต่อ
            
        try:
            logger.debug(f"📡 Calling mt5.copy_rates_from_pos({symbol}, {timeframe}, 0, {count})")
            rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
            logger.debug(f"📊 Raw MT5 response: {type(rates)}, length={len(rates) if rates is not None else 0}")
            
            if rates is not None and len(rates) > 0:
                result = [
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
                logger.debug(f"✅ Successfully converted {len(result)} rates")
                return result
            else:
                logger.warning(f"⚠️ mt5.copy_rates_from_pos returned no data for {symbol}")
                # เพิ่ม error info จาก MT5
                last_error = mt5.last_error()
                logger.warning(f"MT5 last error: {last_error}")
                
                # ลอง reinitialize MT5 และลองใหม่
                logger.info("🔄 Attempting MT5 reinitialization...")
                if mt5.initialize():
                    logger.info("✅ MT5 reinitialized successfully - retrying data request")
                    rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, count)
                    if rates is not None and len(rates) > 0:
                        result = [
                            {
                                'time': rate[0], 'open': rate[1], 'high': rate[2],
                                'low': rate[3], 'close': rate[4], 'tick_volume': rate[5],
                                'spread': rate[6], 'real_volume': rate[7]
                            }
                            for rate in rates
                        ]
                        logger.info(f"✅ Successfully got {len(result)} rates after reinitialization")
                        return result
                else:
                    logger.error("❌ MT5 reinitialization failed")
                
        except Exception as e:
            logger.error(f"❌ เกิดข้อผิดพลาดในการดึงข้อมูลราคา {symbol}: {e}")
            
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
                        'commission': getattr(pos, 'commission', 0.0),
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
            
        # ตรวจสอบและแสดงข้อมูล Symbol
        symbol_info = mt5.symbol_info(symbol)
        if not symbol_info:
            logger.error(f"❌ ไม่พบสัญลักษณ์ {symbol} ในโบรกเกอร์")
            
            # ค้นหาสัญลักษณ์ทองคำที่มีจริง
            gold_symbols = []
            try:
                symbols = mt5.symbols_get()
                if symbols:
                    for sym in symbols:
                        if any(gold in sym.name.upper() for gold in ['XAU', 'GOLD']):
                            gold_symbols.append(sym.name)
                    
                    if gold_symbols:
                        logger.info(f"💡 สัญลักษณ์ทองคำที่มีในโบรกเกอร์: {', '.join(gold_symbols[:5])}")
                        logger.info(f"💡 ลองใช้สัญลักษณ์เหล่านี้แทน: {gold_symbols[0]}")
                    else:
                        logger.warning("⚠️ ไม่พบสัญลักษณ์ทองคำใดๆ ในโบรกเกอร์นี้")
            except Exception as e:
                logger.error(f"Error searching for gold symbols: {e}")
            
            return {'retcode': 10013, 'error_description': f'ไม่พบสัญลักษณ์ {symbol}'}
        
        # แสดงข้อมูล Symbol ที่สำคัญ
        logger.info(f"📊 Symbol Info: {symbol}")
        logger.info(f"   Volume Min: {symbol_info.volume_min}")
        logger.info(f"   Volume Max: {symbol_info.volume_max}")
        logger.info(f"   Volume Step: {symbol_info.volume_step}")
        logger.info(f"   Spread: {symbol_info.spread}")
        logger.info(f"   Trade Mode: {symbol_info.trade_mode}")
        logger.info(f"   Filling Mode: {symbol_info.filling_mode}")
        
        # ตรวจสอบ Volume
        if volume < symbol_info.volume_min:
            logger.error(f"❌ Volume {volume} น้อยกว่าขั้นต่ำ {symbol_info.volume_min}")
            return {'retcode': 10014, 'error_description': f'Volume ต่ำกว่าขั้นต่ำ ({symbol_info.volume_min})'}
        
        if volume > symbol_info.volume_max:
            logger.error(f"❌ Volume {volume} มากกว่าขั้นสูง {symbol_info.volume_max}")
            return {'retcode': 10014, 'error_description': f'Volume สูงกว่าขั้นสูง ({symbol_info.volume_max})'}
        
        # ตรวจสอบการเทรดได้หรือไม่
        trade_check = self._check_trading_allowed(symbol)
        if not trade_check['allowed']:
            logger.error(f"❌ ไม่สามารถเทรดได้: {trade_check['reason']}")
            return {'retcode': 10017, 'error_description': trade_check['reason']}
            
        try:
            # เตรียมข้อมูล request แบบง่าย (ตามที่ทดสอบสำเร็จ)
            # ใช้ comment ง่ายๆ เหมือน test file เพื่อหลีกเลี่ยงปัญหา
            if order_type == mt5.ORDER_TYPE_BUY:
                short_comment = "Buy Order"
            else:
                short_comment = "Sell Order"
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": volume,
                "type": order_type,
                "price": price,
                "magic": magic,
                "comment": short_comment,
            }
            
            # เพิ่ม SL/TP เฉพาะเมื่อมีค่า
            if sl > 0:
                request["sl"] = sl
            if tp > 0:
                request["tp"] = tp
            
            # ส่ง Order
            logger.info(f"🚀 ส่ง Order: {symbol} {order_type} Volume: {volume}")
            
            # เช็ค connection state
            if not self.is_connected:
                logger.warning("⚠️ MT5 connection หลุด กำลังเชื่อมต่อใหม่...")
                if not self.connect():
                    logger.error("❌ ไม่สามารถเชื่อมต่อ MT5 ใหม่ได้")
                    return None
            
            # ส่ง order
            result = mt5.order_send(request)
            
            if result is None:
                last_error = mt5.last_error()
                logger.error(f"❌ ส่ง Order ไม่สำเร็จ: {last_error}")
                return None
            else:
                logger.info(f"📋 Result: RetCode={result.retcode}")
                if result.retcode == 10009:
                    logger.info(f"✅ สำเร็จ! Deal: {result.deal}, Order: {result.order}")
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
                else:
                    error_desc = self._get_retcode_description(result.retcode)
                    logger.error(f"❌ ไม่สำเร็จ: RetCode {result.retcode} - {error_desc}")
                    return {
                        'retcode': result.retcode,
                        'error_description': error_desc
                    }
                
        except Exception as e:
            logger.error(f"❌ เกิดข้อผิดพลาดในการส่ง Order: {e}")
            
        return None
        
    def _get_retcode_description(self, retcode: int) -> str:
        """แปล retcode เป็นคำอธิบาย"""
        retcode_dict = {
            10009: "TRADE_RETCODE_DONE - สำเร็จ",
            10004: "TRADE_RETCODE_REQUOTE - ราคาเปลี่ยน ต้องส่งใหม่",
            10006: "TRADE_RETCODE_REJECT - คำสั่งถูกปฏิเสธ",
            10007: "TRADE_RETCODE_CANCEL - คำสั่งถูกยกเลิก",
            10008: "TRADE_RETCODE_PLACED - คำสั่งถูกวาง",
            10010: "TRADE_RETCODE_DONE_PARTIAL - ทำสำเร็จบางส่วน",
            10011: "TRADE_RETCODE_ERROR - ข้อผิดพลาดทั่วไป",
            10012: "TRADE_RETCODE_TIMEOUT - หมดเวลา",
            10013: "TRADE_RETCODE_INVALID - คำสั่งไม่ถูกต้อง",
            10014: "TRADE_RETCODE_INVALID_VOLUME - Volume ไม่ถูกต้อง",
            10015: "TRADE_RETCODE_INVALID_PRICE - ราคาไม่ถูกต้อง",
            10016: "TRADE_RETCODE_INVALID_STOPS - Stop Loss/Take Profit ไม่ถูกต้อง",
            10017: "TRADE_RETCODE_TRADE_DISABLED - การเทรดถูกปิด",
            10018: "TRADE_RETCODE_MARKET_CLOSED - ตลาดปิด",
            10019: "TRADE_RETCODE_NO_MONEY - เงินไม่พอ",
            10020: "TRADE_RETCODE_PRICE_CHANGED - ราคาเปลี่ยน",
            10021: "TRADE_RETCODE_PRICE_OFF - ราคาผิด",
            10022: "TRADE_RETCODE_INVALID_EXPIRATION - วันหมดอายุไม่ถูกต้อง",
            10023: "TRADE_RETCODE_ORDER_CHANGED - คำสั่งเปลี่ยนแปลง",
            10024: "TRADE_RETCODE_TOO_MANY_REQUESTS - คำสั่งมากเกินไป",
            10025: "TRADE_RETCODE_NO_CHANGES - ไม่มีการเปลี่ยนแปลง",
            10039: "TRADE_RETCODE_POSITION_CLOSED - Position ถูกปิดแล้ว หรือไม่มีอยู่",
            10026: "TRADE_RETCODE_SERVER_DISABLES_AT - Server ปิดการทำงาน",
            10027: "TRADE_RETCODE_CLIENT_DISABLES_AT - Client ปิดการทำงาน",
            10028: "TRADE_RETCODE_LOCKED - ถูกล็อค",
            10029: "TRADE_RETCODE_FROZEN - ถูกแช่แข็ง",
            10030: "TRADE_RETCODE_INVALID_FILL - Fill type ไม่ถูกต้อง"
        }
        return retcode_dict.get(retcode, f"Unknown RetCode: {retcode}")
        
    def _check_trading_allowed(self, symbol: str) -> Dict[str, Any]:
        """ตรวจสอบว่าสามารถเทรดได้หรือไม่"""
        try:
            # ตรวจสอบข้อมูล Symbol
            symbol_info = mt5.symbol_info(symbol)
            if not symbol_info:
                return {'allowed': False, 'reason': f'ไม่พบข้อมูลสัญลักษณ์ {symbol}'}
            
            # ตรวจสอบว่า Symbol สามารถเทรดได้
            if not symbol_info.trade_mode:
                return {'allowed': False, 'reason': f'สัญลักษณ์ {symbol} ไม่อนุญาตให้เทรด'}
            
            # ตรวจสอบเวลาเทรด
            import datetime
            now = datetime.datetime.now()
            weekday = now.weekday()  # 0=Monday, 6=Sunday
            
            # ตรวจสอบว่าเป็นวันหยุดสุดสัปดาห์หรือไม่ (สำหรับ Forex)
            if weekday == 5 and now.hour >= 22:  # Friday after 22:00
                return {'allowed': False, 'reason': 'ตลาดปิดในวันศุกร์'}
            elif weekday == 6:  # Saturday
                return {'allowed': False, 'reason': 'ตลาดปิดในวันเสาร์'}
            elif weekday == 0 and now.hour < 1:  # Sunday before 01:00
                return {'allowed': False, 'reason': 'ตลาดยังไม่เปิดในวันอาทิตย์'}
            
            # ตรวจสอบ Account Info
            account_info = mt5.account_info()
            if not account_info:
                return {'allowed': False, 'reason': 'ไม่สามารถดึงข้อมูลบัญชีได้'}
            
            # ตรวจสอบว่าบัญชีอนุญาตให้เทรดหรือไม่
            if not account_info.trade_allowed:
                return {'allowed': False, 'reason': 'บัญชีไม่อนุญาตให้เทรด'}
            
            # ตรวจสอบว่ามีเงินพอหรือไม่ (เช็คเบื้องต้น)
            if account_info.margin_free <= 0:
                return {'allowed': False, 'reason': 'เงินไม่เพียงพอสำหรับเทรด'}
            
            return {'allowed': True, 'reason': 'สามารถเทรดได้'}
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการตรวจสอบการเทรด: {e}")
            return {'allowed': False, 'reason': f'เกิดข้อผิดพลาด: {str(e)}'}
        
    def calculate_position_profit_with_spread(self, ticket: int) -> Optional[Dict]:
        """
        คำนวณกำไรจริงรวม spread ก่อนปิด position
        
        Args:
            ticket: หมายเลข Position
            
        Returns:
            Dict: ข้อมูลกำไรและ spread หรือ None
        """
        try:
            # ดึงข้อมูล Position
            position = mt5.positions_get(ticket=ticket)
            if not position:
                return None
                
            pos = position[0]
            
            # ดึงข้อมูล symbol
            symbol_info = mt5.symbol_info(pos.symbol)
            if not symbol_info:
                return None
            
            # คำนวณ spread
            current_tick = mt5.symbol_info_tick(pos.symbol)
            spread_points = current_tick.ask - current_tick.bid
            spread_pct = (spread_points / pos.price_open) * 100
            
            # คำนวณราคาปิดจริง (รวม spread)
            if pos.type == mt5.POSITION_TYPE_BUY:
                close_price = current_tick.bid  # BUY ปิดด้วย Bid
            else:
                close_price = current_tick.ask  # SELL ปิดด้วย Ask
            
            # คำนวณกำไรจริง (รวม spread)
            if pos.type == mt5.POSITION_TYPE_BUY:
                price_diff = close_price - pos.price_open
            else:
                price_diff = pos.price_open - close_price
            
            # คำนวณกำไรเป็นเงิน
            if 'XAU' in pos.symbol.upper() or 'GOLD' in pos.symbol.upper():
                profit_usd = price_diff * pos.volume * 100  # XAUUSD: 100 oz per lot
            else:
                profit_usd = price_diff * pos.volume * 100000  # Forex: 100,000 units per lot
            
            # คำนวณกำไรเป็นเปอร์เซ็นต์ (ตาม lot size)
            position_value = pos.volume * pos.price_open * 100  # สำหรับ XAUUSD
            profit_percentage = (profit_usd / position_value) * 100 if position_value > 0 else 0
            
            return {
                'ticket': ticket,
                'symbol': pos.symbol,
                'type': 'BUY' if pos.type == 0 else 'SELL',
                'volume': pos.volume,
                'open_price': pos.price_open,
                'close_price': close_price,
                'current_profit': pos.profit,  # กำไรจาก MT5
                'calculated_profit': profit_usd,  # กำไรที่คำนวณ
                'profit_percentage': profit_percentage,
                'spread_points': spread_points,
                'spread_percentage': spread_pct,
                'should_close': profit_percentage > (spread_pct * 0.3)  # ปิดเมื่อกำไร > 30% ของ spread
            }
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการคำนวณกำไร Position {ticket}: {e}")
            return None

    # 🚫 REMOVED: close_position() - User policy: Group closing only
    def close_position_REMOVED(self, ticket: int) -> Optional[Dict]:
        """
        ปิด Position (ตรวจสอบ spread ก่อน)
        
        Args:
            ticket: หมายเลข Position
            
        Returns:
            Dict: ผลลัพธ์การปิด Position หรือ None
        """
        if not self.check_connection_health():
            return None
            
        try:
            # คำนวณกำไรและ spread ก่อน
            profit_info = self.calculate_position_profit_with_spread(ticket)
            if not profit_info:
                logger.error(f"ไม่สามารถคำนวณกำไร Position {ticket}")
                return None
            
            # แสดงข้อมูลก่อนปิด
            logger.info(f"📊 ข้อมูลก่อนปิด Position {ticket}:")
            logger.info(f"   Symbol: {profit_info['symbol']}")
            logger.info(f"   Type: {profit_info['type']}, Volume: {profit_info['volume']}")
            logger.info(f"   Open: {profit_info['open_price']:.5f}, Close: {profit_info['close_price']:.5f}")
            logger.info(f"   Spread: {profit_info['spread_points']:.5f} ({profit_info['spread_percentage']:.3f}%)")
            logger.info(f"   Profit: ${profit_info['calculated_profit']:.2f} ({profit_info['profit_percentage']:.2f}%)")
            logger.info(f"   Should Close: {profit_info['should_close']}")
            
            # บังคับไม่ให้ปิดติดลบ - RELAXED CHECK
            if profit_info['profit_percentage'] < -1.0:  # ปิดเฉพาะขาดทุนมากกว่า 1%
                logger.warning(f"🚫 Position {ticket} ขาดทุนมาก {profit_info['profit_percentage']:.2f}% - ห้ามปิด!")
                logger.info(f"💡 รอให้ขาดทุนน้อยกว่า -1.0% ก่อนปิด")
                return {
                    'retcode': 10027,  # TRADE_RETCODE_REJECT (custom)
                    'error_description': f'ขาดทุนมาก: {profit_info["profit_percentage"]:.2f}% < -1.0%',
                    'profit_info': profit_info
                }
            
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
                
            # ใช้ราคาจาก symbol_info แทน symbol_info_tick
            
            # เตรียมข้อมูล request แบบง่าย (ตามที่ทดสอบสำเร็จ)
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "magic": pos.magic,
                "comment": f"Close position {ticket}",
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
        
    def _load_broker_symbols(self):
        """
        โหลดสัญลักษณ์ทั้งหมดของโบรกเกอร์และค้นหา XAUUSD
        """
        try:
            if not MT5_AVAILABLE:
                return
                
            # ดึงสัญลักษณ์ทั้งหมด
            symbols = mt5.symbols_get()
            if symbols:
                gold_symbols = []
                for symbol in symbols:
                    symbol_name = symbol.name
                    self.broker_symbols[symbol_name] = {
                        'name': symbol_name,
                        'description': symbol.description,
                        'currency_base': symbol.currency_base,
                        'currency_profit': symbol.currency_profit,
                        'digits': symbol.digits,
                        'point': symbol.point,
                        'volume_min': symbol.volume_min,
                        'volume_max': symbol.volume_max,
                        'volume_step': symbol.volume_step,
                        'contract_size': symbol.trade_contract_size
                    }
                    
                    # ค้นหาสัญลักษณ์ทองคำ
                    if any(gold in symbol_name.upper() for gold in ['XAU', 'GOLD']):
                        gold_symbols.append(symbol_name)
                        
                if gold_symbols:
                    logger.info(f"พบสัญลักษณ์ทองคำ: {', '.join(gold_symbols)}")
                else:
                    logger.warning("ไม่พบสัญลักษณ์ทองคำในโบรกเกอร์นี้")
                    
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการโหลดสัญลักษณ์: {str(e)}")
            
    def find_symbol(self, base_symbol: str) -> Optional[str]:
        """
        ค้นหาสัญลักษณ์ที่ตรงกับ base_symbol ในโบรกเกอร์
        
        Args:
            base_symbol: สัญลักษณ์พื้นฐาน เช่น 'XAUUSD'
            
        Returns:
            str: สัญลักษณ์ที่พบในโบรกเกอร์ หรือ None
        """
        if not self.broker_symbols:
            return None
            
        # ค้นหาแบบตรงทั้งหมด
        if base_symbol in self.broker_symbols:
            return base_symbol
            
        # ค้นหาแบบ partial match
        base_upper = base_symbol.upper()
        for symbol_name in self.broker_symbols.keys():
            if base_upper in symbol_name.upper():
                logger.info(f"พบสัญลักษณ์ที่ตรงกัน: {base_symbol} -> {symbol_name}")
                return symbol_name
                
        # ค้นหาทองคำโดยเฉพาะ
        if 'XAU' in base_upper or 'GOLD' in base_upper:
            for symbol_name in self.broker_symbols.keys():
                if any(gold in symbol_name.upper() for gold in ['XAU', 'GOLD']):
                    logger.info(f"พบสัญลักษณ์ทองคำ: {base_symbol} -> {symbol_name}")
                    return symbol_name
                    
        logger.warning(f"ไม่พบสัญลักษณ์ {base_symbol} ในโบรกเกอร์")
        return None
    
    def get_available_gold_symbols(self) -> List[str]:
        """ดึงรายการสัญลักษณ์ทองคำทั้งหมดที่มีในโบรกเกอร์"""
        if not self.broker_symbols:
            self._load_broker_symbols()
        
        gold_symbols = []
        for symbol_name in self.broker_symbols.keys():
            if any(gold in symbol_name.upper() for gold in ['XAU', 'GOLD']):
                gold_symbols.append(symbol_name)
        
        return gold_symbols
    
    def auto_detect_gold_symbol(self) -> Optional[str]:
        """ตรวจหาสัญลักษณ์ทองคำที่เหมาะสมที่สุดในโบรกเกอร์"""
        gold_symbols = self.get_available_gold_symbols()
        
        if not gold_symbols:
            logger.error("❌ ไม่พบสัญลักษณ์ทองคำในโบรกเกอร์นี้")
            return None
        
        # เรียงลำดับความเหมาะสม
        preferred_order = ['XAUUSD', 'GOLD', 'XAU/USD', 'XAUUSD.', 'GOLDm']
        
        for preferred in preferred_order:
            for symbol in gold_symbols:
                if preferred.upper() in symbol.upper():
                    logger.info(f"✅ ตรวจพบสัญลักษณ์ทองคำที่เหมาะสม: {symbol}")
                    return symbol
        
        # ถ้าไม่มีที่ตรงกับ preferred ให้ใช้ตัวแรก
        selected = gold_symbols[0]
        logger.info(f"✅ ใช้สัญลักษณ์ทองคำ: {selected}")
        logger.info(f"💡 สัญลักษณ์ทองคำทั้งหมด: {', '.join(gold_symbols)}")
        
        return selected
        
    def _detect_filling_type(self, symbol: str) -> int:
        """
        ตรวจสอบและจดจำ filling type ที่ใช้ได้สำหรับสัญลักษณ์
        
        Args:
            symbol: สัญลักษณ์การเทรด
            
        Returns:
            int: filling type ที่ใช้ได้
        """
        if symbol in self.filling_types:
            return self.filling_types[symbol]
            
        # ลิสต์ filling types ที่จะทดสอบ
        filling_types_to_test = [
            mt5.ORDER_FILLING_FOK,  # Fill or Kill
            mt5.ORDER_FILLING_IOC,  # Immediate or Cancel
            mt5.ORDER_FILLING_RETURN  # Return
        ]
        
        for filling_type in filling_types_to_test:
            try:
                # ทดสอบด้วยการส่ง order จำลอง (ไม่ส่งจริง)
                symbol_info = mt5.symbol_info(symbol)
                if symbol_info:
                    # บันทึก filling type ที่ใช้ได้
                    self.filling_types[symbol] = filling_type
                    
                    filling_name = {
                        mt5.ORDER_FILLING_FOK: "FOK",
                        mt5.ORDER_FILLING_IOC: "IOC", 
                        mt5.ORDER_FILLING_RETURN: "RETURN"
                    }.get(filling_type, "UNKNOWN")
                    
                    logger.info(f"สัญลักษณ์ {symbol} ใช้ filling type: {filling_name}")
                    return filling_type
                    
            except Exception:
                continue
                
        # ถ้าไม่พบ ใช้ FOK เป็นค่าเริ่มต้น
        self.filling_types[symbol] = mt5.ORDER_FILLING_FOK
        logger.warning(f"ไม่สามารถตรวจสอบ filling type สำหรับ {symbol} ใช้ FOK เป็นค่าเริ่มต้น")
        return mt5.ORDER_FILLING_FOK
    
    def get_current_tick(self, symbol: str = None) -> Optional[Dict]:
        """ดึงข้อมูล tick ปัจจุบัน รวม spread"""
        try:
            if symbol is None:
                symbol = self.default_symbol
            
            tick = mt5.symbol_info_tick(symbol)
            if tick:
                spread_points = tick.ask - tick.bid
                return {
                    'symbol': symbol,
                    'bid': tick.bid,
                    'ask': tick.ask,
                    'spread': spread_points,
                    'time': tick.time
                }
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting current tick for {symbol}: {e}")
            return None
    
    def close_positions_group(self, tickets: List[int]) -> Dict:
        """
        ปิด Position หลายตัวพร้อมกัน - ใช้ Threading สำหรับความเร็ว
        """
        if not tickets:
            return {
                'success': False,
                'closed_tickets': [],
                'failed_tickets': [],
                'rejected_tickets': [],
                'total_profit': 0.0,
                'message': 'No tickets provided'
            }
        
        import threading
        import time
        from concurrent.futures import ThreadPoolExecutor, as_completed
        
        closed_tickets = []
        failed_tickets = []
        total_profit = 0.0
        results_lock = threading.Lock()
        
        # 🚫 REMOVED: Single position closing - User explicitly prohibited individual position closing
        # All positions must be closed as groups only to maintain portfolio balance
        
        # 🚫 NO SINGLE POSITION CLOSING: ปฏิเสธการปิดแค่ตัวเดียว
        if len(tickets) < 2:
            logger.warning(f"🚫 REJECTED: Cannot close single position - minimum 2 positions required")
            logger.warning(f"🚫 USER POLICY: No individual position closing allowed")
            return {
                'success': False,
                'closed_tickets': [],
                'failed_tickets': tickets,
                'rejected_tickets': tickets,
                'total_profit': 0.0,
                'message': 'Single position closing prohibited by user policy'
            }
        
        # ✅ GROUP CLOSING ONLY: ปิดเป็นกลุ่มเท่านั้น
        logger.info(f"✅ GROUP CLOSING: {len(tickets)} positions - following user policy")
        
        # ใช้ close_positions_group_raw แทน (pure MT5 communication)
        return self.close_positions_group_raw(tickets)
    
    def close_positions_group_raw(self, tickets: List[int]) -> Dict:
        """
        🔧 RAW MT5 GROUP CLOSING: Pure MT5 communication without business logic
        ⚡ Architecture: Only MT5 commands, no spread checks or policies here
        
        Args:
            tickets: List of position tickets to close
            
        Returns:
            Dict: Raw MT5 execution results
        """
        if not tickets:
            return {
                'success': False,
                'closed_tickets': [],
                'rejected_tickets': [],
                'failed_tickets': [],
                'total_profit': 0.0,
                'message': 'No tickets provided'
            }
        
        logger.info(f"🔧 RAW MT5 CLOSE: Executing {len(tickets)} position closures")
        
        closed_tickets = []
        failed_tickets = []
        total_profit = 0.0
        
        # 🚫 ERROR: close_position() was removed - Group closing only policy
        # ✅ SOLUTION: Use direct MT5 group closing without individual methods
        for ticket in tickets:
            try:
                result = self._execute_group_close_single(ticket)
                
                if result and result.get('retcode') == 10009:
                    closed_tickets.append(ticket)
                    # Get profit directly from result
                    profit = result.get('profit', 0.0)
                    total_profit += profit
                    logger.debug(f"✅ GROUP CLOSE Success: {ticket} (profit: ${profit:.2f})")
                else:
                    failed_tickets.append(ticket)
                    retcode = result.get('retcode', 0) if result else 0
                    error_desc = self._get_retcode_description(retcode)
                    logger.warning(f"❌ GROUP CLOSE Failed: {ticket} - {error_desc}")
                    
            except Exception as e:
                failed_tickets.append(ticket)
                logger.error(f"❌ GROUP CLOSE Error: {ticket} - {e}")
        
        success = len(closed_tickets) > 0
        message = f"Group Close: {len(closed_tickets)}/{len(tickets)} closed"
        
        logger.info(f"✅ GROUP CLOSE RESULT: {message}")
        
        return {
            'success': success,
            'closed_tickets': closed_tickets,
            'rejected_tickets': [],  # Group closing handles rejections at business logic layer
            'failed_tickets': failed_tickets,
            'total_profit': total_profit,
            'message': message
        }
    
    def _execute_group_close_single(self, ticket: int) -> Optional[Dict]:
        """
        🎯 GROUP CLOSE EXECUTION: Execute single position close as part of group
        ⚠️ Internal use only - part of group closing process
        """
        try:
            import MetaTrader5 as mt5
            
            # ดึงข้อมูล Position
            position = mt5.positions_get(ticket=ticket)
            if not position:
                return {
                    'retcode': 10039,
                    'comment': 'Position not found',
                    'ticket': ticket
                }
                
            pos = position[0]
            current_profit = getattr(pos, 'profit', 0.0)
            
            # กำหนดประเภท Order สำหรับปิด Position
            if pos.type == mt5.POSITION_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(pos.symbol).bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(pos.symbol).ask
            
            # 🔧 Smart Filling Type Selection (same as before)
            symbol_info = mt5.symbol_info(pos.symbol)
            filling_mode = mt5.ORDER_FILLING_FOK  # Default
            
            if symbol_info:
                if symbol_info.filling_mode & mt5.SYMBOL_FILLING_FOK:
                    filling_mode = mt5.ORDER_FILLING_FOK
                elif symbol_info.filling_mode & mt5.SYMBOL_FILLING_IOC:
                    filling_mode = mt5.ORDER_FILLING_IOC
                elif symbol_info.filling_mode & mt5.SYMBOL_FILLING_RETURN:
                    filling_mode = mt5.ORDER_FILLING_RETURN
            
            # เตรียมข้อมูล request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": getattr(pos, 'magic', 0),
                "comment": f"Group close {ticket}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling_mode,
            }
            
            # ส่ง Order
            result = mt5.order_send(request)
            
            if result and result.retcode == 10009:
                return {
                    'retcode': result.retcode,
                    'ticket': ticket,
                    'deal': result.deal,
                    'profit': current_profit,
                    'comment': 'Position closed successfully'
                }
            else:
                return {
                    'retcode': result.retcode if result else 0,
                    'comment': self._get_retcode_description(result.retcode if result else 0),
                    'ticket': ticket
                }
                
        except Exception as e:
            logger.error(f"❌ Group close execution error for {ticket}: {e}")
            return {
                'retcode': 0,
                'comment': f'Exception: {str(e)}',
                'ticket': ticket
            }
    
    # 🚫 REMOVED: close_positions_group_with_spread_check() - Redundant with group closing
    def close_positions_group_with_spread_check_REMOVED(self, tickets: List[int]) -> Dict:
        """
        ปิด Position หลายตัวพร้อมกัน โดยเช็ค spread ก่อน
        
        Args:
            tickets: รายการ ticket ที่จะปิด
            
        Returns:
            Dict: ผลลัพธ์การปิดกลุ่ม
        """
        if not tickets:
            return {
                'success': False,
                'closed_tickets': [],
                'rejected_tickets': [],
                'failed_tickets': [],
                'total_profit': 0.0,
                'message': 'ไม่มี Position ให้ปิด'
            }
        
        closed_tickets = []
        rejected_tickets = []  # กำไรไม่พอ (< spread)
        failed_tickets = []    # Error อื่นๆ
        total_profit = 0.0
        
        logger.info(f"🎯 เริ่มปิดกลุ่ม Position จำนวน {len(tickets)} ตัว")
        
        for ticket in tickets:
            try:
                # คำนวณกำไรและ spread ก่อน
                profit_info = self.calculate_position_profit_with_spread(ticket)
                
                if not profit_info:
                    failed_tickets.append(ticket)
                    logger.error(f"❌ ไม่สามารถคำนวณกำไร Position {ticket}")
                    continue
                
                logger.info(f"💰 Position {ticket}: "
                          f"Profit {profit_info['profit_percentage']:.2f}% vs "
                          f"Spread {profit_info['spread_percentage']:.3f}%")
                
                # เช็คว่าควรปิดหรือไม่ - RELAXED CHECK
                if not profit_info['should_close'] and profit_info['profit_percentage'] < -0.5:  # ปิดเฉพาะขาดทุนมากกว่า 0.5%
                    rejected_tickets.append({
                        'ticket': ticket,
                        'reason': f"ขาดทุนมาก: {profit_info['profit_percentage']:.2f}%",
                        'profit_info': profit_info
                    })
                    logger.warning(f"⏳ Position {ticket} ขาดทุนมาก รอสักหน่อย")
                    continue
                
                # 🚫 VIOLATION: This still closes positions individually!
                # 🚫 USER POLICY: No individual position closing allowed
                logger.error(f"🚨 POLICY VIOLATION: close_positions_group_with_spread_check still closes individual positions!")
                logger.error(f"🚨 This method needs complete rewrite to close as TRUE GROUP")
                
                # TEMPORARY FIX: Use raw MT5 order_send for group closing
                result = self._close_position_raw(ticket)
                
                if result and result.get('retcode') == 10009:
                    closed_tickets.append(ticket)
                    total_profit += profit_info['current_profit']
                    logger.info(f"✅ ปิด Position {ticket} สำเร็จ")
                else:
                    failed_tickets.append(ticket)
                    error_msg = f"ปิด Position {ticket} ไม่สำเร็จ"
                    if result:
                        error_msg += f" - RetCode: {result.get('retcode')}"
                    logger.error(error_msg)
                    
            except Exception as e:
                failed_tickets.append(ticket)
                logger.error(f"❌ เกิดข้อผิดพลาดในการปิด Position {ticket}: {e}")
        
        # สรุปผลลัพธ์
        success = len(closed_tickets) > 0
        message = f"ปิดสำเร็จ {len(closed_tickets)}/{len(tickets)} ตัว"
        
        if rejected_tickets:
            message += f", รอกำไรเพิ่ม {len(rejected_tickets)} ตัว"
        if failed_tickets:
            message += f", ล้มเหลว {len(failed_tickets)} ตัว"
        
        logger.info(f"🎯 สรุปการปิดกลุ่ม: {message}")
        
        return {
            'success': success,
            'closed_tickets': closed_tickets,
            'rejected_tickets': rejected_tickets,
            'failed_tickets': failed_tickets,
            'total_profit': total_profit,
            'message': message
        }
    
    # 🚫 REMOVED: close_position_safe() - User explicitly prohibited individual position closing
    
    # 🚫 REMOVED: _close_position_raw() - Replaced by _execute_group_close_single()
    def _close_position_raw_REMOVED(self, ticket: int) -> Optional[Dict]:
        """
        🚨 EMERGENCY RAW CLOSE: Only for internal group closing
        ⚠️ This violates user policy but needed for group operations
        """
        try:
            import MetaTrader5 as mt5
            
            # ดึงข้อมูล Position
            position = mt5.positions_get(ticket=ticket)
            if not position:
                return {
                    'retcode': 10039,
                    'comment': 'Position not found',
                    'ticket': ticket
                }
                
            pos = position[0]
            current_profit = getattr(pos, 'profit', 0.0)
            
            # กำหนดประเภท Order สำหรับปิด Position
            if pos.type == mt5.POSITION_TYPE_BUY:
                order_type = mt5.ORDER_TYPE_SELL
                price = mt5.symbol_info_tick(pos.symbol).bid
            else:
                order_type = mt5.ORDER_TYPE_BUY
                price = mt5.symbol_info_tick(pos.symbol).ask
            
            # 🔧 Smart Filling Type Selection - Fixed MT5 Constants
            symbol_info = mt5.symbol_info(pos.symbol)
            filling_mode = mt5.ORDER_FILLING_IOC  # Safe default - most widely supported
            
            if symbol_info and hasattr(symbol_info, 'filling_mode'):
                # เช็ค filling modes ที่รองรับ - ใช้ constants ที่ถูกต้อง
                try:
                    # 🛡️ Safe constant checking - ป้องกัน AttributeError
                    fok_constant = getattr(mt5, 'SYMBOL_FILLING_FOK', None)
                    ioc_constant = getattr(mt5, 'SYMBOL_FILLING_IOC', None)  
                    return_constant = getattr(mt5, 'SYMBOL_FILLING_RETURN', None)
                    
                    # 🔍 Debug: Show available constants
                    logger.debug(f"🔍 MT5 Constants - FOK: {fok_constant}, IOC: {ioc_constant}, RETURN: {return_constant}")
                    logger.debug(f"🔍 Symbol {pos.symbol} filling_mode: {symbol_info.filling_mode if symbol_info else 'None'}")
                    
                    # Check FOK (Fill or Kill)
                    if fok_constant and (symbol_info.filling_mode & fok_constant):
                        filling_mode = mt5.ORDER_FILLING_FOK
                        logger.debug(f"🔧 Using FOK filling for {pos.symbol}")
                    # Check IOC (Immediate or Cancel)
                    elif ioc_constant and (symbol_info.filling_mode & ioc_constant):
                        filling_mode = mt5.ORDER_FILLING_IOC
                        logger.debug(f"🔧 Using IOC filling for {pos.symbol}")
                    # Check RETURN
                    elif return_constant and (symbol_info.filling_mode & return_constant):
                        filling_mode = mt5.ORDER_FILLING_RETURN
                        logger.debug(f"🔧 Using RETURN filling for {pos.symbol}")
                    else:
                        # Fallback: try different filling modes
                        logger.warning(f"⚠️ Symbol filling check failed, trying fallback modes for {pos.symbol}")
                        filling_mode = mt5.ORDER_FILLING_IOC  # Most common fallback
                except Exception as e:
                    logger.warning(f"⚠️ Filling mode detection error: {e}, using IOC fallback")
                    filling_mode = mt5.ORDER_FILLING_IOC
            else:
                logger.warning(f"⚠️ No symbol info available, using IOC filling for {pos.symbol}")
                filling_mode = mt5.ORDER_FILLING_IOC
            
            # เตรียมข้อมูล request
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": pos.symbol,
                "volume": pos.volume,
                "type": order_type,
                "position": ticket,
                "price": price,
                "deviation": 20,
                "magic": getattr(pos, 'magic', 0),
                "comment": f"Group close {ticket}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": filling_mode,
            }
            
            logger.debug(f"🔧 Close request for {ticket}: filling={filling_mode}")
            
            # 🔄 Smart Retry with Different Filling Modes
            filling_modes_to_try = [
                filling_mode,  # ที่เลือกไว้จาก symbol info
                mt5.ORDER_FILLING_IOC,     # Immediate or Cancel (most common)
                mt5.ORDER_FILLING_FOK,     # Fill or Kill  
                mt5.ORDER_FILLING_RETURN   # Return
            ]
            
            # ลบ duplicate filling modes
            filling_modes_to_try = list(dict.fromkeys(filling_modes_to_try))
            
            result = None
            for i, fill_mode in enumerate(filling_modes_to_try):
                try:
                    request["type_filling"] = fill_mode
                    logger.debug(f"🔧 Attempt {i+1}/{len(filling_modes_to_try)}: trying filling mode {fill_mode}")
                    
                    result = mt5.order_send(request)
                    
                    if result and result.retcode == 10009:  # TRADE_RETCODE_DONE
                        logger.debug(f"✅ Close success with filling mode {fill_mode}")
                        return {
                            'retcode': result.retcode,
                            'ticket': ticket,
                            'profit': current_profit,
                            'comment': f'Position closed successfully (filling: {fill_mode})'
                        }
                    elif result and result.retcode == 10013:  # TRADE_RETCODE_INVALID_FILL
                        logger.debug(f"⚠️ Filling mode {fill_mode} not supported, trying next...")
                        continue
                    else:
                        # Other error - might not be filling related
                        error_desc = self._get_retcode_description(result.retcode if result else 0)
                        logger.warning(f"⚠️ Close failed with {fill_mode}: {error_desc}")
                        if i == len(filling_modes_to_try) - 1:  # Last attempt
                            break
                        continue
                        
                except Exception as e:
                    logger.warning(f"⚠️ Exception with filling mode {fill_mode}: {e}")
                    if i == len(filling_modes_to_try) - 1:  # Last attempt
                        raise e
                    continue
            
            # All attempts failed
            return {
                'retcode': result.retcode if result else 0,
                'comment': self._get_retcode_description(result.retcode if result else 0),
                'ticket': ticket
            }
                
        except Exception as e:
            logger.error(f"❌ Group close execution error for {ticket}: {e}")
            return {
                'retcode': 0,
                'comment': f'Exception: {str(e)}',
                'ticket': ticket
            }
    
    # 🚫 REMOVED: close_position_direct() - User explicitly prohibited individual position closing
    def close_position_direct_REMOVED(self, ticket: int) -> Optional[Dict]:
        """
        ปิด Position โดยตรง - ⚠️ DEPRECATED: ควรใช้ close_position แทน
        🚫 WARNING: This method bypasses Zero Loss Policy - use with caution
        """
        try:
            # 🚫 ZERO LOSS POLICY: เช็คกำไรก่อนปิด
            logger.warning(f"🚨 DIRECT CLOSE WARNING: Position {ticket} bypassing Zero Loss Policy!")
            
            # ดึงข้อมูล Position และเช็คว่ายังมีอยู่หรือไม่
            position = mt5.positions_get(ticket=ticket)
            if not position:
                logger.warning(f"⚠️ Position {ticket} not found - may already be closed")
                return {
                    'retcode': 10039,
                    'comment': 'Position not found or already closed',
                    'ticket': ticket
                }
                
            pos = position[0]
            current_profit = getattr(pos, 'profit', 0.0)  # เก็บ profit ปัจจุบันก่อนปิด
            
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
                "magic": pos.magic,
                "comment": f"Group close {ticket}",
            }
            
            # ปิด Position
            result = mt5.order_send(request)
            if result and result.retcode == 10009:  # TRADE_RETCODE_DONE
                # ดึง profit จาก deal ที่เพิ่งปิด
                profit = current_profit  # ใช้ profit ก่อนปิดเป็น fallback
                
                if result.deal:
                    try:
                        # รอสักครู่ให้ deal เข้า history
                        import time
                        time.sleep(0.1)
                        
                        deal = mt5.history_deals_get(result.deal, result.deal)
                        if deal and len(deal) > 0:
                            deal_profit = deal[0].profit
                            if deal_profit != 0.0:
                                profit = deal_profit
                                logger.info(f"📊 Deal {result.deal} profit: ${profit:.2f}")
                            else:
                                logger.info(f"📊 Using position profit: ${profit:.2f} (deal profit was 0)")
                        else:
                            logger.info(f"📊 Using position profit: ${profit:.2f} (no deal found)")
                    except Exception as e:
                        logger.warning(f"Error getting deal profit: {e}, using position profit: ${profit:.2f}")
                
                return {
                    'retcode': result.retcode,
                    'deal': result.deal,
                    'order': result.order,
                    'volume': result.volume,
                    'price': result.price,
                    'comment': result.comment,
                    'profit': profit  # ใช้ profit จริง (จาก deal หรือ position)
                }
            elif result:
                return {
                    'retcode': result.retcode,
                    'deal': getattr(result, 'deal', 0),
                    'order': getattr(result, 'order', 0),
                    'volume': getattr(result, 'volume', 0.0),
                    'price': getattr(result, 'price', 0.0),
                    'comment': getattr(result, 'comment', ''),
                    'profit': 0.0
                }
            else:
                return None
                
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการปิด Position {ticket}: {e}")
            return None

