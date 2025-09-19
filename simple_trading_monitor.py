# -*- coding: utf-8 -*-
"""
🎯 Simple Trading Monitor
========================
แสดงข้อมูลการเข้าไม้และราคาปัจจุบันแบบง่ายๆ ไม่มีกราฟซับซ้อน

AUTHOR: Advanced Trading System
VERSION: 1.0.0 - Simple Edition
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import logging
from datetime import datetime
from typing import Dict, List, Optional
import queue

# Import modules from original system
from mt5_connection import MT5Connection
from order_management import OrderManager
from trading_conditions import Signal, CandleData

logger = logging.getLogger(__name__)

class SimpleTradingMonitor:
    """🎯 Simple Trading Monitor - แสดงข้อมูลการเทรดแบบง่ายๆ"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎯 Simple Trading Monitor - Real-time Trading Info")
        self.root.geometry("800x600")
        self.root.configure(bg='#1e1e1e')
        
        # ข้อมูล
        self.current_price = 0.0
        self.symbol = "XAUUSD"
        self.positions = []
        self.orders = []
        
        # Threading
        self.update_queue = queue.Queue()
        self.is_running = False
        self.update_thread = None
        
        # MT5 Connection
        self.mt5_connection = None
        self.order_manager = None
        
        # สี
        self.colors = {
            'background': '#1e1e1e',
            'foreground': '#ffffff',
            'buy': '#00ff00',
            'sell': '#ff0000',
            'price': '#00bfff',
            'profit': '#00ff00',
            'loss': '#ff0000'
        }
        
        self.setup_gui()
        self.start_update_loop()
        
    def setup_gui(self):
        """ตั้งค่าหน้าต่าง GUI"""
        # Main frame
        main_frame = tk.Frame(self.root, bg=self.colors['background'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Title
        title_frame = tk.Frame(main_frame, bg=self.colors['background'])
        title_frame.pack(fill=tk.X, pady=(0, 20))
        
        title_label = tk.Label(title_frame, text="🎯 Simple Trading Monitor", 
                              bg=self.colors['background'], fg=self.colors['foreground'],
                              font=('Arial', 16, 'bold'))
        title_label.pack()
        
        # Control panel
        control_frame = tk.Frame(main_frame, bg=self.colors['background'])
        control_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Symbol selection
        symbol_frame = tk.Frame(control_frame, bg=self.colors['background'])
        symbol_frame.pack(side=tk.LEFT, padx=(0, 20))
        
        tk.Label(symbol_frame, text="Symbol:", bg=self.colors['background'], 
                fg=self.colors['foreground'], font=('Arial', 10, 'bold')).pack(side=tk.LEFT)
        
        self.symbol_var = tk.StringVar(value="XAUUSD")
        symbol_combo = ttk.Combobox(symbol_frame, textvariable=self.symbol_var, 
                                   values=["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"], 
                                   width=10, state="readonly")
        symbol_combo.pack(side=tk.LEFT, padx=(5, 0))
        symbol_combo.bind('<<ComboboxSelected>>', self.on_symbol_change)
        
        # Control buttons
        button_frame = tk.Frame(control_frame, bg=self.colors['background'])
        button_frame.pack(side=tk.RIGHT)
        
        self.start_btn = tk.Button(button_frame, text="▶️ Start Monitor", 
                                  command=self.start_monitor, bg='#00aa00', fg='white',
                                  font=('Arial', 10, 'bold'), padx=10)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_btn = tk.Button(button_frame, text="⏹️ Stop Monitor", 
                                 command=self.stop_monitor, bg='#aa0000', fg='white',
                                 font=('Arial', 10, 'bold'), padx=10, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.clear_btn = tk.Button(button_frame, text="🗑️ Clear All", 
                                  command=self.clear_all, bg='#666666', fg='white',
                                  font=('Arial', 10, 'bold'), padx=10)
        self.clear_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Status bar
        status_frame = tk.Frame(main_frame, bg=self.colors['background'])
        status_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.status_label = tk.Label(status_frame, text="Status: Ready", 
                                    bg=self.colors['background'], fg=self.colors['foreground'],
                                    font=('Arial', 10))
        self.status_label.pack(side=tk.LEFT)
        
        self.price_label = tk.Label(status_frame, text="Price: 0.00000", 
                                   bg=self.colors['background'], fg=self.colors['price'],
                                   font=('Arial', 14, 'bold'))
        self.price_label.pack(side=tk.RIGHT)
        
        # Main content area
        content_frame = tk.Frame(main_frame, bg=self.colors['background'])
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Current Price & Recent Trades
        left_frame = tk.Frame(content_frame, bg=self.colors['background'])
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Current price display
        price_frame = tk.LabelFrame(left_frame, text="💰 Current Price", 
                                   bg=self.colors['background'], fg=self.colors['foreground'],
                                   font=('Arial', 12, 'bold'))
        price_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.price_display = tk.Label(price_frame, text="0.00000", 
                                     bg=self.colors['background'], fg=self.colors['price'],
                                     font=('Arial', 24, 'bold'))
        self.price_display.pack(pady=10)
        
        # Recent trades
        trades_frame = tk.LabelFrame(left_frame, text="📈 Recent Trades", 
                                    bg=self.colors['background'], fg=self.colors['foreground'],
                                    font=('Arial', 12, 'bold'))
        trades_frame.pack(fill=tk.BOTH, expand=True)
        
        self.trades_text = tk.Text(trades_frame, height=15, bg='#2d2d2d', fg='#ffffff',
                                  font=('Consolas', 10), state=tk.DISABLED)
        self.trades_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Right panel - Positions & Statistics
        right_frame = tk.Frame(content_frame, bg=self.colors['background'], width=300)
        right_frame.pack(side=tk.RIGHT, fill=tk.Y)
        right_frame.pack_propagate(False)
        
        # Positions
        positions_frame = tk.LabelFrame(right_frame, text="📊 Open Positions", 
                                       bg=self.colors['background'], fg=self.colors['foreground'],
                                       font=('Arial', 12, 'bold'))
        positions_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.positions_tree = ttk.Treeview(positions_frame, columns=('Type', 'Volume', 'Price', 'Profit'), 
                                          show='headings', height=8)
        self.positions_tree.heading('#0', text='Ticket')
        self.positions_tree.heading('Type', text='Type')
        self.positions_tree.heading('Volume', text='Volume')
        self.positions_tree.heading('Price', text='Price')
        self.positions_tree.heading('Profit', text='Profit')
        
        self.positions_tree.column('#0', width=60)
        self.positions_tree.column('Type', width=60)
        self.positions_tree.column('Volume', width=60)
        self.positions_tree.column('Price', width=80)
        self.positions_tree.column('Profit', width=80)
        
        self.positions_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Statistics
        stats_frame = tk.LabelFrame(right_frame, text="📈 Statistics", 
                                   bg=self.colors['background'], fg=self.colors['foreground'],
                                   font=('Arial', 12, 'bold'))
        stats_frame.pack(fill=tk.X)
        
        self.stats_text = tk.Text(stats_frame, height=8, bg='#2d2d2d', fg='#ffffff',
                                 font=('Consolas', 9), state=tk.DISABLED)
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
    def start_monitor(self):
        """เริ่มการตรวจสอบ"""
        if not self.is_running:
            self.is_running = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.status_label.config(text="Status: Running")
            
            # Start update thread
            self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
            self.update_thread.start()
            
            logger.info("🎯 Simple Trading Monitor started")
    
    def stop_monitor(self):
        """หยุดการตรวจสอบ"""
        if self.is_running:
            self.is_running = False
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.status_label.config(text="Status: Stopped")
            
            logger.info("🎯 Simple Trading Monitor stopped")
    
    def clear_all(self):
        """ล้างข้อมูลทั้งหมด"""
        self.positions.clear()
        self.orders.clear()
        
        # Clear trees
        for item in self.positions_tree.get_children():
            self.positions_tree.delete(item)
        
        # Clear text
        self.trades_text.config(state=tk.NORMAL)
        self.trades_text.delete(1.0, tk.END)
        self.trades_text.config(state=tk.DISABLED)
        
        logger.info("🎯 Simple Trading Monitor cleared")
    
    def start_update_loop(self):
        """เริ่มลูปการอัพเดท"""
        self.root.after(100, self.process_queue)
    
    def process_queue(self):
        """ประมวลผลคิวการอัพเดท"""
        try:
            while not self.update_queue.empty():
                update_type, data = self.update_queue.get_nowait()
                self.handle_update(update_type, data)
        except queue.Empty:
            pass
        
        # Schedule next update
        self.root.after(100, self.process_queue)
    
    def handle_update(self, update_type: str, data):
        """จัดการการอัพเดท"""
        if update_type == "price":
            self.update_price_display(data)
        elif update_type == "position":
            self.update_position_display(data)
        elif update_type == "trade":
            self.update_trade_display(data)
    
    def update_loop(self):
        """ลูปการอัพเดทหลัก"""
        while self.is_running:
            try:
                # ดึงข้อมูลราคา
                self.fetch_price_data()
                
                # ดึงข้อมูล Position
                self.fetch_position_data()
                
                # อัพเดทสถิติ
                self.update_statistics()
                
                time.sleep(1)  # อัพเดททุก 1 วินาที
                
            except Exception as e:
                logger.error(f"❌ Error in update loop: {e}")
                time.sleep(5)
    
    def fetch_price_data(self):
        """ดึงข้อมูลราคา"""
        try:
            if self.mt5_connection and self.mt5_connection.check_connection_health():
                # ดึงราคาจาก MT5
                tick = self.mt5_connection.get_tick(self.symbol)
                if tick:
                    self.current_price = tick['bid']
                    self.update_queue.put(("price", self.current_price))
            else:
                # สร้างราคาจำลอง
                if not hasattr(self, '_last_price'):
                    self._last_price = 2000.0
                
                # Random walk
                import random
                change = random.uniform(-0.5, 0.5)
                self._last_price += change
                self.current_price = self._last_price
                self.update_queue.put(("price", self.current_price))
                
        except Exception as e:
            logger.error(f"❌ Error fetching price data: {e}")
    
    def fetch_position_data(self):
        """ดึงข้อมูล Position"""
        try:
            if self.order_manager:
                current_positions = self.order_manager.active_positions
                
                # ตรวจสอบ Position ใหม่
                for pos in current_positions:
                    if not any(p.ticket == pos.ticket for p in self.positions):
                        # Position ใหม่
                        self.positions.append(pos)
                        self.update_queue.put(("position", pos))
                        
                        # แสดงการเข้าไม้
                        direction = "BUY" if pos.type == 0 else "SELL"
                        trade_info = f"[{datetime.now().strftime('%H:%M:%S')}] {direction} {pos.volume:.2f} lots at {pos.price_open:.5f}"
                        self.update_queue.put(("trade", trade_info))
                
                # ตรวจสอบ Position ที่ปิดแล้ว
                for pos in self.positions[:]:
                    if not any(p.ticket == pos.ticket for p in current_positions):
                        # Position ปิดแล้ว
                        self.positions.remove(pos)
                        
                        # แสดงการปิดไม้
                        direction = "BUY" if pos.type == 0 else "SELL"
                        profit = pos.profit + pos.swap + pos.commission
                        close_info = f"[{datetime.now().strftime('%H:%M:%S')}] CLOSE {direction} {pos.volume:.2f} lots - Profit: ${profit:.2f}"
                        self.update_queue.put(("trade", close_info))
                
        except Exception as e:
            logger.error(f"❌ Error fetching position data: {e}")
    
    def update_price_display(self, price: float):
        """อัพเดทการแสดงราคา"""
        self.price_label.config(text=f"Price: {price:.5f}")
        self.price_display.config(text=f"{price:.5f}")
    
    def update_position_display(self, position):
        """อัพเดทการแสดง Position"""
        # เพิ่มใน TreeView
        direction = "BUY" if position.type == 0 else "SELL"
        profit = position.profit + position.swap + position.commission
        
        item = self.positions_tree.insert('', 'end', text=str(position.ticket),
                                        values=(direction, f"{position.volume:.2f}",
                                               f"{position.price_open:.5f}",
                                               f"${profit:.2f}"))
        
        # ตั้งสีตามกำไร/ขาดทุน
        if profit > 0:
            self.positions_tree.set(item, 'Profit', f"${profit:.2f}")
        else:
            self.positions_tree.set(item, 'Profit', f"${profit:.2f}")
    
    def update_trade_display(self, trade_info: str):
        """อัพเดทการแสดงการเทรด"""
        self.trades_text.config(state=tk.NORMAL)
        self.trades_text.insert(tk.END, trade_info + "\n")
        self.trades_text.see(tk.END)
        self.trades_text.config(state=tk.DISABLED)
        
        # จำกัดจำนวนบรรทัด
        lines = self.trades_text.get(1.0, tk.END).split('\n')
        if len(lines) > 50:
            self.trades_text.config(state=tk.NORMAL)
            self.trades_text.delete(1.0, f"{len(lines)-50}.0")
            self.trades_text.config(state=tk.DISABLED)
    
    def update_statistics(self):
        """อัพเดทสถิติ"""
        try:
            self.stats_text.config(state=tk.NORMAL)
            self.stats_text.delete(1.0, tk.END)
            
            # คำนวณสถิติ
            total_positions = len(self.positions)
            buy_positions = len([p for p in self.positions if p.type == 0])
            sell_positions = len([p for p in self.positions if p.type == 1])
            
            total_profit = sum(p.profit + p.swap + p.commission for p in self.positions)
            total_volume = sum(p.volume for p in self.positions)
            
            # แสดงสถิติ
            stats = f"""📊 Trading Statistics
{'='*30}

💰 Current Price: {self.current_price:.5f}
📈 Open Positions: {total_positions}
🟢 BUY Positions: {buy_positions}
🔴 SELL Positions: {sell_positions}
📦 Total Volume: {total_volume:.2f}
💵 Total Profit: ${total_profit:.2f}

⏰ Last Update: {datetime.now().strftime('%H:%M:%S')}
"""
            
            self.stats_text.insert(tk.END, stats)
            self.stats_text.config(state=tk.DISABLED)
            
        except Exception as e:
            logger.error(f"❌ Error updating statistics: {e}")
    
    def on_symbol_change(self, event):
        """เมื่อเปลี่ยน Symbol"""
        self.symbol = self.symbol_var.get()
        logger.info(f"🎯 Symbol changed to: {self.symbol}")
    
    def connect_to_mt5(self, order_manager: OrderManager):
        """เชื่อมต่อกับ MT5 Order Manager"""
        self.order_manager = order_manager
        self.mt5_connection = order_manager.mt5
        logger.info("🎯 Connected to MT5 Order Manager")
    
    def run(self):
        """รัน GUI"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.stop_monitor()
            logger.info("🎯 Simple Trading Monitor stopped by user")

def main():
    """ฟังก์ชันหลัก"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run monitor
    monitor = SimpleTradingMonitor()
    
    # Connect to MT5 if available
    try:
        from order_management import OrderManager
        from mt5_connection import MT5Connection
        
        mt5_connection = MT5Connection()
        order_manager = OrderManager(mt5_connection)
        monitor.connect_to_mt5(order_manager)
        
    except Exception as e:
        logger.warning(f"⚠️ Could not connect to MT5: {e}")
        logger.info("🎯 Running in simulation mode only")
    
    # Run monitor
    monitor.run()

if __name__ == "__main__":
    main()
