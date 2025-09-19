# -*- coding: utf-8 -*-
"""
🎯 MT5 Simulator Integration
===========================
เชื่อมต่อ MT5 Simulator กับระบบหลัก
แสดงการเข้าออกไม้แบบ Real-time

AUTHOR: Advanced Trading System
VERSION: 1.0.0 - Integration Edition
"""

import logging
import threading
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

# Import modules from original system
from mt5_connection import MT5Connection
from order_management import OrderManager
from trading_conditions import Signal, CandleData
from calculations import Position

logger = logging.getLogger(__name__)

@dataclass
class SimulatorEvent:
    """ข้อมูล Event สำหรับ Simulator"""
    event_type: str  # 'position_open', 'position_close', 'order_place', 'price_update'
    data: Dict
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()

class MT5SimulatorIntegration:
    """🎯 MT5 Simulator Integration - เชื่อมต่อกับระบบหลัก"""
    
    def __init__(self, simulator_gui, order_manager: OrderManager = None):
        self.simulator_gui = simulator_gui
        self.order_manager = order_manager
        self.is_running = False
        self.integration_thread = None
        
        # Event tracking
        self.last_positions = []
        self.last_orders = []
        self.last_price = 0.0
        
        # Statistics
        self.total_trades = 0
        self.total_profit = 0.0
        self.win_trades = 0
        self.loss_trades = 0
        
        logger.info("🎯 MT5 Simulator Integration initialized")
    
    def start_integration(self):
        """เริ่มการเชื่อมต่อ"""
        if not self.is_running:
            self.is_running = True
            self.integration_thread = threading.Thread(target=self.integration_loop, daemon=True)
            self.integration_thread.start()
            logger.info("🎯 MT5 Simulator Integration started")
    
    def stop_integration(self):
        """หยุดการเชื่อมต่อ"""
        if self.is_running:
            self.is_running = False
            if self.integration_thread:
                self.integration_thread.join(timeout=5)
            logger.info("🎯 MT5 Simulator Integration stopped")
    
    def integration_loop(self):
        """ลูปการเชื่อมต่อหลัก"""
        while self.is_running:
            try:
                # ตรวจสอบการเปลี่ยนแปลงใน Position
                self.check_position_changes()
                
                # ตรวจสอบการเปลี่ยนแปลงใน Order
                self.check_order_changes()
                
                # ตรวจสอบการเปลี่ยนแปลงในราคา
                self.check_price_changes()
                
                time.sleep(0.5)  # ตรวจสอบทุก 0.5 วินาที
                
            except Exception as e:
                logger.error(f"❌ Error in integration loop: {e}")
                time.sleep(5)
    
    def check_position_changes(self):
        """ตรวจสอบการเปลี่ยนแปลงใน Position"""
        try:
            if not self.order_manager:
                return
            
            current_positions = self.order_manager.active_positions
            
            # ตรวจสอบ Position ใหม่
            for pos in current_positions:
                if not any(p.ticket == pos.ticket for p in self.last_positions):
                    # Position ใหม่
                    self.handle_position_open(pos)
                    self.last_positions.append(pos)
            
            # ตรวจสอบ Position ที่ปิดแล้ว
            for last_pos in self.last_positions:
                if not any(p.ticket == last_pos.ticket for p in current_positions):
                    # Position ปิดแล้ว
                    self.handle_position_close(last_pos)
                    self.last_positions.remove(last_pos)
            
            # อัพเดท Position ที่มีอยู่
            for i, pos in enumerate(current_positions):
                if i < len(self.last_positions):
                    if (pos.ticket == self.last_positions[i].ticket and 
                        pos.profit != self.last_positions[i].profit):
                        # กำไรเปลี่ยนแปลง
                        self.handle_position_update(pos)
                        self.last_positions[i] = pos
            
        except Exception as e:
            logger.error(f"❌ Error checking position changes: {e}")
    
    def check_order_changes(self):
        """ตรวจสอบการเปลี่ยนแปลงใน Order"""
        try:
            # TODO: ตรวจสอบ Order changes เมื่อมี Order Management
            pass
            
        except Exception as e:
            logger.error(f"❌ Error checking order changes: {e}")
    
    def check_price_changes(self):
        """ตรวจสอบการเปลี่ยนแปลงในราคา"""
        try:
            if not self.order_manager or not self.order_manager.mt5:
                return
            
            # ดึงราคาปัจจุบัน
            tick = self.order_manager.mt5.get_tick(self.simulator_gui.symbol)
            if tick:
                current_price = tick['bid']
                
                if current_price != self.last_price:
                    self.handle_price_update(current_price)
                    self.last_price = current_price
                    
        except Exception as e:
            logger.error(f"❌ Error checking price changes: {e}")
    
    def handle_position_open(self, position: Position):
        """จัดการการเปิด Position"""
        try:
            # สร้างข้อมูลสำหรับ Simulator
            pos_data = {
                'ticket': position.ticket,
                'symbol': position.symbol,
                'type': position.type,
                'volume': position.volume,
                'price_open': position.price_open,
                'price_current': position.price_current,
                'profit': position.profit,
                'swap': position.swap,
                'commission': position.commission,
                'comment': position.comment,
                'magic': position.magic,
                'time_open': position.time_open
            }
            
            # ส่งไปยัง Simulator
            self.simulator_gui.update_queue.put(("position", pos_data))
            
            # อัพเดทสถิติ
            self.total_trades += 1
            
            # Log
            direction = "BUY" if position.type == 0 else "SELL"
            logger.info(f"🎯 Position Opened: {direction} {position.volume:.2f} lots at {position.price_open:.5f}")
            
        except Exception as e:
            logger.error(f"❌ Error handling position open: {e}")
    
    def handle_position_close(self, position: Position):
        """จัดการการปิด Position"""
        try:
            # สร้างข้อมูลสำหรับ Simulator
            pos_data = {
                'ticket': position.ticket,
                'symbol': position.symbol,
                'type': position.type,
                'volume': position.volume,
                'price_open': position.price_open,
                'price_current': position.price_current,
                'profit': position.profit,
                'swap': position.swap,
                'commission': position.commission,
                'comment': position.comment,
                'magic': position.magic,
                'time_open': position.time_open
            }
            
            # ส่งไปยัง Simulator
            self.simulator_gui.update_queue.put(("close", pos_data))
            
            # อัพเดทสถิติ
            net_profit = position.profit + position.swap + position.commission
            self.total_profit += net_profit
            
            if net_profit > 0:
                self.win_trades += 1
            else:
                self.loss_trades += 1
            
            # Log
            direction = "BUY" if position.type == 0 else "SELL"
            logger.info(f"🎯 Position Closed: {direction} {position.volume:.2f} lots - Profit: ${net_profit:.2f}")
            
        except Exception as e:
            logger.error(f"❌ Error handling position close: {e}")
    
    def handle_position_update(self, position: Position):
        """จัดการการอัพเดท Position"""
        try:
            # สร้างข้อมูลสำหรับ Simulator
            pos_data = {
                'ticket': position.ticket,
                'symbol': position.symbol,
                'type': position.type,
                'volume': position.volume,
                'price_open': position.price_open,
                'price_current': position.price_current,
                'profit': position.profit,
                'swap': position.swap,
                'commission': position.commission,
                'comment': position.comment,
                'magic': position.magic,
                'time_open': position.time_open
            }
            
            # ส่งไปยัง Simulator
            self.simulator_gui.update_queue.put(("position", pos_data))
            
        except Exception as e:
            logger.error(f"❌ Error handling position update: {e}")
    
    def handle_price_update(self, price: float):
        """จัดการการอัพเดทราคา"""
        try:
            # ส่งไปยัง Simulator
            self.simulator_gui.update_queue.put(("price", price))
            
        except Exception as e:
            logger.error(f"❌ Error handling price update: {e}")
    
    def get_statistics(self) -> Dict:
        """ดึงสถิติการเทรด"""
        try:
            win_rate = (self.win_trades / self.total_trades * 100) if self.total_trades > 0 else 0
            
            return {
                'total_trades': self.total_trades,
                'total_profit': self.total_profit,
                'win_trades': self.win_trades,
                'loss_trades': self.loss_trades,
                'win_rate': win_rate,
                'current_positions': len(self.last_positions)
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting statistics: {e}")
            return {}
    
    def simulate_trade_from_signal(self, signal: Signal, lot_size: float):
        """จำลองการเทรดจาก Signal"""
        try:
            # สร้าง Position จำลอง
            simulated_pos = {
                'ticket': len(self.last_positions) + 1,
                'symbol': signal.symbol,
                'type': 0 if signal.direction == "BUY" else 1,
                'volume': lot_size,
                'price_open': signal.price,
                'price_current': signal.price,
                'profit': 0.0,
                'swap': 0.0,
                'commission': 0.0,
                'comment': signal.comment,
                'magic': 123456,
                'time_open': signal.timestamp
            }
            
            # ส่งไปยัง Simulator
            self.simulator_gui.update_queue.put(("position", simulated_pos))
            
            # Log
            logger.info(f"🎯 Simulated Trade: {signal.direction} {lot_size:.2f} lots at {signal.price:.5f}")
            
        except Exception as e:
            logger.error(f"❌ Error simulating trade from signal: {e}")

def create_simulator_with_integration(order_manager: OrderManager = None):
    """สร้าง Simulator พร้อม Integration"""
    try:
        from mt5_simulator_gui import MT5SimulatorGUI
        
        # สร้าง Simulator GUI
        simulator_gui = MT5SimulatorGUI()
        
        # สร้าง Integration
        integration = MT5SimulatorIntegration(simulator_gui, order_manager)
        
        # เชื่อมต่อ
        simulator_gui.integration = integration
        
        return simulator_gui, integration
        
    except Exception as e:
        logger.error(f"❌ Error creating simulator with integration: {e}")
        return None, None

def main():
    """ฟังก์ชันหลัก"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    try:
        # สร้าง Simulator
        simulator_gui, integration = create_simulator_with_integration()
        
        if simulator_gui and integration:
            # เริ่ม Integration
            integration.start_integration()
            
            # รัน Simulator
            simulator_gui.run()
            
            # หยุด Integration
            integration.stop_integration()
        else:
            logger.error("❌ Failed to create simulator")
            
    except Exception as e:
        logger.error(f"❌ Error in main: {e}")

if __name__ == "__main__":
    main()
