# -*- coding: utf-8 -*-
"""
🎯 MT5 Trading Simulator GUI
==========================
หน้าต่างการจำลองการเข้าไม้แบบ MT5 แบบ Real-time
แสดงกราฟและแสดงการเข้าออกไม้แบบ Visual

AUTHOR: Advanced Trading System
VERSION: 1.0.0 - MT5 Simulator Edition
"""

import tkinter as tk
from tkinter import ttk, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import threading
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import queue

# Import modules from original system
from mt5_connection import MT5Connection
from order_management import OrderManager
from trading_conditions import CandleData

logger = logging.getLogger(__name__)

@dataclass
class SimulatedPosition:
    """ข้อมูล Position จำลอง"""
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
    magic: int = 123456
    time_open: datetime = None
    
    def __post_init__(self):
        if self.time_open is None:
            self.time_open = datetime.now()

@dataclass
class SimulatedOrder:
    """ข้อมูล Order จำลอง"""
    ticket: int
    symbol: str
    type: int
    volume: float
    price: float
    sl: float = 0.0
    tp: float = 0.0
    comment: str = ""
    magic: int = 123456
    time: datetime = None
    
    def __post_init__(self):
        if self.time is None:
            self.time = datetime.now()

class MT5SimulatorGUI:
    """🎯 MT5 Trading Simulator GUI - หน้าต่างการจำลองการเข้าไม้แบบ MT5"""
    
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("🎯 MT5 Trading Simulator - Real-time Visual Trading")
        self.root.geometry("1400x900")
        self.root.configure(bg='#1e1e1e')
        
        # ข้อมูลจำลอง
        self.simulated_positions = []
        self.simulated_orders = []
        self.price_history = []
        self.candle_data = []
        self.current_price = 0.0
        self.symbol = "XAUUSD"
        
        # ข้อมูลกราฟ
        self.fig = None
        self.ax = None
        self.canvas = None
        self.price_line = None
        self.buy_markers = []
        self.sell_markers = []
        self.close_markers = []
        
        # Threading
        self.update_queue = queue.Queue()
        self.is_running = False
        self.update_thread = None
        
        # MT5 Connection (สำหรับดึงข้อมูลจริง)
        self.mt5_connection = MT5Connection()
        self.order_manager = None
        
        # สี
        self.colors = {
            'background': '#1e1e1e',
            'foreground': '#ffffff',
            'buy': '#00ff00',
            'sell': '#ff0000',
            'close': '#ffff00',
            'price': '#00bfff',
            'grid': '#333333'
        }
        
        self.setup_gui()
        self.setup_chart()
        self.start_update_loop()
        
    def setup_gui(self):
        """ตั้งค่าหน้าต่าง GUI"""
        # Main frame
        main_frame = tk.Frame(self.root, bg=self.colors['background'])
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Top control panel
        control_frame = tk.Frame(main_frame, bg=self.colors['background'])
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
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
        
        self.start_btn = tk.Button(button_frame, text="▶️ Start Simulation", 
                                  command=self.start_simulation, bg='#00aa00', fg='white',
                                  font=('Arial', 10, 'bold'), padx=10)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.stop_btn = tk.Button(button_frame, text="⏹️ Stop Simulation", 
                                 command=self.stop_simulation, bg='#aa0000', fg='white',
                                 font=('Arial', 10, 'bold'), padx=10, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        self.clear_btn = tk.Button(button_frame, text="🗑️ Clear All", 
                                  command=self.clear_all, bg='#666666', fg='white',
                                  font=('Arial', 10, 'bold'), padx=10)
        self.clear_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        # Status bar
        status_frame = tk.Frame(main_frame, bg=self.colors['background'])
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.status_label = tk.Label(status_frame, text="Status: Ready", 
                                    bg=self.colors['background'], fg=self.colors['foreground'],
                                    font=('Arial', 10))
        self.status_label.pack(side=tk.LEFT)
        
        self.price_label = tk.Label(status_frame, text="Price: 0.00000", 
                                   bg=self.colors['background'], fg=self.colors['price'],
                                   font=('Arial', 12, 'bold'))
        self.price_label.pack(side=tk.RIGHT)
        
        # Main content area
        content_frame = tk.Frame(main_frame, bg=self.colors['background'])
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left panel - Chart
        chart_frame = tk.Frame(content_frame, bg=self.colors['background'])
        chart_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        # Chart title
        chart_title = tk.Label(chart_frame, text="📈 Price Chart & Trading Activity", 
                              bg=self.colors['background'], fg=self.colors['foreground'],
                              font=('Arial', 14, 'bold'))
        chart_title.pack(pady=(0, 10))
        
        # Chart canvas (will be created in setup_chart)
        self.chart_frame = chart_frame
        
        # Right panel - Trading info
        info_frame = tk.Frame(content_frame, bg=self.colors['background'], width=300)
        info_frame.pack(side=tk.RIGHT, fill=tk.Y)
        info_frame.pack_propagate(False)
        
        # Positions info
        positions_frame = tk.LabelFrame(info_frame, text="📊 Open Positions", 
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
        self.positions_tree.column('Type', width=50)
        self.positions_tree.column('Volume', width=60)
        self.positions_tree.column('Price', width=80)
        self.positions_tree.column('Profit', width=80)
        
        self.positions_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Orders info
        orders_frame = tk.LabelFrame(info_frame, text="📋 Pending Orders", 
                                    bg=self.colors['background'], fg=self.colors['foreground'],
                                    font=('Arial', 12, 'bold'))
        orders_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.orders_tree = ttk.Treeview(orders_frame, columns=('Type', 'Volume', 'Price'), 
                                       show='headings', height=6)
        self.orders_tree.heading('#0', text='Ticket')
        self.orders_tree.heading('Type', text='Type')
        self.orders_tree.heading('Volume', text='Volume')
        self.orders_tree.heading('Price', text='Price')
        
        self.orders_tree.column('#0', width=60)
        self.orders_tree.column('Type', width=50)
        self.orders_tree.column('Volume', width=60)
        self.orders_tree.column('Price', width=80)
        
        self.orders_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Trading controls
        trading_frame = tk.LabelFrame(info_frame, text="🎮 Trading Controls", 
                                     bg=self.colors['background'], fg=self.colors['foreground'],
                                     font=('Arial', 12, 'bold'))
        trading_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Manual trade buttons
        manual_frame = tk.Frame(trading_frame, bg=self.colors['background'])
        manual_frame.pack(fill=tk.X, padx=5, pady=5)
        
        tk.Label(manual_frame, text="Volume:", bg=self.colors['background'], 
                fg=self.colors['foreground']).pack(side=tk.LEFT)
        
        self.volume_var = tk.StringVar(value="0.01")
        volume_entry = tk.Entry(manual_frame, textvariable=self.volume_var, width=10)
        volume_entry.pack(side=tk.LEFT, padx=(5, 10))
        
        buy_btn = tk.Button(manual_frame, text="🟢 BUY", command=self.manual_buy, 
                           bg='#00aa00', fg='white', font=('Arial', 10, 'bold'))
        buy_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        sell_btn = tk.Button(manual_frame, text="🔴 SELL", command=self.manual_sell, 
                            bg='#aa0000', fg='white', font=('Arial', 10, 'bold'))
        sell_btn.pack(side=tk.LEFT)
        
        # Statistics
        stats_frame = tk.LabelFrame(info_frame, text="📈 Statistics", 
                                   bg=self.colors['background'], fg=self.colors['foreground'],
                                   font=('Arial', 12, 'bold'))
        stats_frame.pack(fill=tk.X)
        
        self.stats_text = tk.Text(stats_frame, height=8, bg='#2d2d2d', fg='#ffffff',
                                 font=('Consolas', 9), state=tk.DISABLED)
        self.stats_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
    def setup_chart(self):
        """ตั้งค่ากราฟ"""
        # Create matplotlib figure
        self.fig = Figure(figsize=(12, 8), facecolor=self.colors['background'])
        self.ax = self.fig.add_subplot(111, facecolor=self.colors['background'])
        
        # Configure chart
        self.ax.set_facecolor(self.colors['background'])
        self.ax.tick_params(colors=self.colors['foreground'])
        self.ax.spines['bottom'].set_color(self.colors['foreground'])
        self.ax.spines['top'].set_color(self.colors['foreground'])
        self.ax.spines['right'].set_color(self.colors['foreground'])
        self.ax.spines['left'].set_color(self.colors['foreground'])
        self.ax.grid(True, color=self.colors['grid'], alpha=0.3)
        
        # Create canvas
        self.canvas = FigureCanvasTkAgg(self.fig, self.chart_frame)
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Initialize empty chart
        self.ax.set_title(f"{self.symbol} - Price Chart", color=self.colors['foreground'], fontsize=14)
        self.ax.set_xlabel("Time", color=self.colors['foreground'])
        self.ax.set_ylabel("Price", color=self.colors['foreground'])
        
        # Initialize price line
        self.price_line, = self.ax.plot([], [], color=self.colors['price'], linewidth=2, label='Price')
        
        self.canvas.draw()
        
    def start_simulation(self):
        """เริ่มการจำลอง"""
        if not self.is_running:
            self.is_running = True
            self.start_btn.config(state=tk.DISABLED)
            self.stop_btn.config(state=tk.NORMAL)
            self.status_label.config(text="Status: Running")
            
            # Start update thread
            self.update_thread = threading.Thread(target=self.update_loop, daemon=True)
            self.update_thread.start()
            
            logger.info("🎯 MT5 Simulator started")
    
    def stop_simulation(self):
        """หยุดการจำลอง"""
        if self.is_running:
            self.is_running = False
            self.start_btn.config(state=tk.NORMAL)
            self.stop_btn.config(state=tk.DISABLED)
            self.status_label.config(text="Status: Stopped")
            
            logger.info("🎯 MT5 Simulator stopped")
    
    def clear_all(self):
        """ล้างข้อมูลทั้งหมด"""
        self.simulated_positions.clear()
        self.simulated_orders.clear()
        self.price_history.clear()
        self.candle_data.clear()
        
        # Clear chart
        self.ax.clear()
        self.setup_chart()
        
        # Clear trees
        for item in self.positions_tree.get_children():
            self.positions_tree.delete(item)
        for item in self.orders_tree.get_children():
            self.orders_tree.delete(item)
        
        # Clear statistics
        self.stats_text.config(state=tk.NORMAL)
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.config(state=tk.DISABLED)
        
        logger.info("🎯 MT5 Simulator cleared")
    
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
        elif update_type == "order":
            self.update_order_display(data)
        elif update_type == "close":
            self.update_close_display(data)
    
    def update_loop(self):
        """ลูปการอัพเดทหลัก"""
        while self.is_running:
            try:
                # ดึงข้อมูลราคาจาก MT5
                if self.mt5_connection and self.mt5_connection.check_connection_health():
                    self.fetch_real_data()
                else:
                    self.generate_simulated_data()
                
                # อัพเดทกราฟ
                self.update_chart()
                
                # อัพเดทสถิติ
                self.update_statistics()
                
                time.sleep(1)  # อัพเดททุก 1 วินาที
                
            except Exception as e:
                logger.error(f"❌ Error in update loop: {e}")
                time.sleep(5)
    
    def fetch_real_data(self):
        """ดึงข้อมูลจริงจาก MT5"""
        try:
            # ดึงราคาปัจจุบัน
            tick = self.mt5_connection.get_tick(self.symbol)
            if tick:
                self.current_price = tick['bid']
                self.update_queue.put(("price", self.current_price))
                
                # เพิ่มข้อมูลราคา
                self.price_history.append({
                    'time': datetime.now(),
                    'price': self.current_price
                })
                
                # จำกัดข้อมูลราคา (เก็บ 1000 จุดล่าสุด)
                if len(self.price_history) > 1000:
                    self.price_history = self.price_history[-1000:]
                
                # ดึงข้อมูล Position จริง
                if self.order_manager:
                    positions = self.order_manager.active_positions
                    for pos in positions:
                        # ตรวจสอบว่าเป็น Position ใหม่หรือไม่
                        if not any(p.ticket == pos.ticket for p in self.simulated_positions):
                            simulated_pos = SimulatedPosition(
                                ticket=pos.ticket,
                                symbol=pos.symbol,
                                type=pos.type,
                                volume=pos.volume,
                                price_open=pos.price_open,
                                price_current=pos.price_current,
                                profit=pos.profit,
                                swap=pos.swap,
                                commission=pos.commission,
                                comment=pos.comment,
                                magic=pos.magic,
                                time_open=pos.time_open
                            )
                            self.simulated_positions.append(simulated_pos)
                            self.update_queue.put(("position", simulated_pos))
                
        except Exception as e:
            logger.error(f"❌ Error fetching real data: {e}")
    
    def generate_simulated_data(self):
        """สร้างข้อมูลจำลอง"""
        try:
            # สร้างราคาจำลอง (Random Walk)
            if not self.price_history:
                base_price = 2000.0  # ราคาเริ่มต้นสำหรับ XAUUSD
            else:
                base_price = self.price_history[-1]['price']
            
            # Random walk with slight upward bias
            change = np.random.normal(0, 0.5)
            new_price = base_price + change
            
            self.current_price = new_price
            self.update_queue.put(("price", self.current_price))
            
            # เพิ่มข้อมูลราคา
            self.price_history.append({
                'time': datetime.now(),
                'price': self.current_price
            })
            
            # จำกัดข้อมูลราคา
            if len(self.price_history) > 1000:
                self.price_history = self.price_history[-1000:]
            
            # สร้าง Position จำลองเป็นครั้งคราว
            if np.random.random() < 0.01:  # 1% โอกาส
                self.create_simulated_position()
                
        except Exception as e:
            logger.error(f"❌ Error generating simulated data: {e}")
    
    def create_simulated_position(self):
        """สร้าง Position จำลอง"""
        try:
            # สร้าง Position ใหม่
            position_type = np.random.choice([0, 1])  # 0=BUY, 1=SELL
            volume = np.random.choice([0.01, 0.02, 0.05, 0.1])
            
            simulated_pos = SimulatedPosition(
                ticket=len(self.simulated_positions) + 1,
                symbol=self.symbol,
                type=position_type,
                volume=volume,
                price_open=self.current_price,
                price_current=self.current_price,
                profit=0.0,
                comment=f"Simulated {['BUY', 'SELL'][position_type]}"
            )
            
            self.simulated_positions.append(simulated_pos)
            self.update_queue.put(("position", simulated_pos))
            
            # สร้าง Order จำลองด้วย
            simulated_order = SimulatedOrder(
                ticket=len(self.simulated_orders) + 1,
                symbol=self.symbol,
                type=position_type,
                volume=volume,
                price=self.current_price,
                comment=f"Simulated Order {['BUY', 'SELL'][position_type]}"
            )
            
            self.simulated_orders.append(simulated_order)
            self.update_queue.put(("order", simulated_order))
            
        except Exception as e:
            logger.error(f"❌ Error creating simulated position: {e}")
    
    def update_price_display(self, price: float):
        """อัพเดทการแสดงราคา"""
        self.price_label.config(text=f"Price: {price:.5f}")
    
    def update_position_display(self, position: SimulatedPosition):
        """อัพเดทการแสดง Position"""
        # เพิ่มใน TreeView
        item = self.positions_tree.insert('', 'end', text=str(position.ticket),
                                        values=(['BUY', 'SELL'][position.type],
                                               f"{position.volume:.2f}",
                                               f"{position.price_open:.5f}",
                                               f"${position.profit:.2f}"))
        
        # ตั้งสีตามประเภท
        if position.type == 0:  # BUY
            self.positions_tree.set(item, 'Type', '🟢 BUY')
        else:  # SELL
            self.positions_tree.set(item, 'Type', '🔴 SELL')
    
    def update_order_display(self, order: SimulatedOrder):
        """อัพเดทการแสดง Order"""
        # เพิ่มใน TreeView
        item = self.orders_tree.insert('', 'end', text=str(order.ticket),
                                     values=(['BUY', 'SELL'][order.type],
                                            f"{order.volume:.2f}",
                                            f"{order.price:.5f}"))
        
        # ตั้งสีตามประเภท
        if order.type == 0:  # BUY
            self.orders_tree.set(item, 'Type', '🟢 BUY')
        else:  # SELL
            self.orders_tree.set(item, 'Type', '🔴 SELL')
    
    def update_close_display(self, position: SimulatedPosition):
        """อัพเดทการแสดงการปิด Position"""
        # ลบจาก TreeView
        for item in self.positions_tree.get_children():
            if self.positions_tree.item(item, 'text') == str(position.ticket):
                self.positions_tree.delete(item)
                break
    
    def update_chart(self):
        """อัพเดทกราฟ"""
        try:
            if not self.price_history:
                return
            
            # เตรียมข้อมูล
            times = [d['time'] for d in self.price_history]
            prices = [d['price'] for d in self.price_history]
            
            # อัพเดทเส้นราคา
            self.price_line.set_data(times, prices)
            
            # อัพเดท Position markers
            self.update_position_markers()
            
            # อัพเดทขอบเขตกราฟ
            if times and prices:
                self.ax.set_xlim(min(times), max(times))
                self.ax.set_ylim(min(prices) * 0.999, max(prices) * 1.001)
            
            # อัพเดทกราฟ
            self.canvas.draw()
            
        except Exception as e:
            logger.error(f"❌ Error updating chart: {e}")
    
    def update_position_markers(self):
        """อัพเดท markers ของ Position"""
        try:
            # ลบ markers เก่า
            for marker in self.buy_markers + self.sell_markers + self.close_markers:
                marker.remove()
            self.buy_markers.clear()
            self.sell_markers.clear()
            self.close_markers.clear()
            
            # เพิ่ม markers ใหม่
            for pos in self.simulated_positions:
                if pos.time_open in [d['time'] for d in self.price_history]:
                    if pos.type == 0:  # BUY
                        marker = self.ax.scatter(pos.time_open, pos.price_open, 
                                               color=self.colors['buy'], marker='^', 
                                               s=100, alpha=0.8, label='BUY')
                        self.buy_markers.append(marker)
                    else:  # SELL
                        marker = self.ax.scatter(pos.time_open, pos.price_open, 
                                               color=self.colors['sell'], marker='v', 
                                               s=100, alpha=0.8, label='SELL')
                        self.sell_markers.append(marker)
            
        except Exception as e:
            logger.error(f"❌ Error updating position markers: {e}")
    
    def update_statistics(self):
        """อัพเดทสถิติ"""
        try:
            self.stats_text.config(state=tk.NORMAL)
            self.stats_text.delete(1.0, tk.END)
            
            # คำนวณสถิติ
            total_positions = len(self.simulated_positions)
            buy_positions = len([p for p in self.simulated_positions if p.type == 0])
            sell_positions = len([p for p in self.simulated_positions if p.type == 1])
            
            total_profit = sum(p.profit for p in self.simulated_positions)
            total_volume = sum(p.volume for p in self.simulated_positions)
            
            # แสดงสถิติ
            stats = f"""📊 Trading Statistics
{'='*30}

💰 Total Profit: ${total_profit:.2f}
📈 Total Positions: {total_positions}
🟢 BUY Positions: {buy_positions}
🔴 SELL Positions: {sell_positions}
📦 Total Volume: {total_volume:.2f}

📋 Pending Orders: {len(self.simulated_orders)}
📊 Price Points: {len(self.price_history)}

⏰ Last Update: {datetime.now().strftime('%H:%M:%S')}
"""
            
            self.stats_text.insert(tk.END, stats)
            self.stats_text.config(state=tk.DISABLED)
            
        except Exception as e:
            logger.error(f"❌ Error updating statistics: {e}")
    
    def manual_buy(self):
        """เปิด Position BUY ด้วยตนเอง"""
        try:
            volume = float(self.volume_var.get())
            
            simulated_pos = SimulatedPosition(
                ticket=len(self.simulated_positions) + 1,
                symbol=self.symbol,
                type=0,  # BUY
                volume=volume,
                price_open=self.current_price,
                price_current=self.current_price,
                profit=0.0,
                comment="Manual BUY"
            )
            
            self.simulated_positions.append(simulated_pos)
            self.update_queue.put(("position", simulated_pos))
            
            logger.info(f"🎯 Manual BUY: {volume} lots at {self.current_price:.5f}")
            
        except Exception as e:
            logger.error(f"❌ Error in manual buy: {e}")
            messagebox.showerror("Error", f"Error in manual buy: {e}")
    
    def manual_sell(self):
        """เปิด Position SELL ด้วยตนเอง"""
        try:
            volume = float(self.volume_var.get())
            
            simulated_pos = SimulatedPosition(
                ticket=len(self.simulated_positions) + 1,
                symbol=self.symbol,
                type=1,  # SELL
                volume=volume,
                price_open=self.current_price,
                price_current=self.current_price,
                profit=0.0,
                comment="Manual SELL"
            )
            
            self.simulated_positions.append(simulated_pos)
            self.update_queue.put(("position", simulated_pos))
            
            logger.info(f"🎯 Manual SELL: {volume} lots at {self.current_price:.5f}")
            
        except Exception as e:
            logger.error(f"❌ Error in manual sell: {e}")
            messagebox.showerror("Error", f"Error in manual sell: {e}")
    
    def on_symbol_change(self, event):
        """เมื่อเปลี่ยน Symbol"""
        self.symbol = self.symbol_var.get()
        self.ax.set_title(f"{self.symbol} - Price Chart", color=self.colors['foreground'])
        self.canvas.draw()
        
        logger.info(f"🎯 Symbol changed to: {self.symbol}")
    
    def connect_to_mt5(self, order_manager: OrderManager):
        """เชื่อมต่อกับ MT5 Order Manager"""
        self.order_manager = order_manager
        logger.info("🎯 Connected to MT5 Order Manager")
    
    def run(self):
        """รัน GUI"""
        try:
            self.root.mainloop()
        except KeyboardInterrupt:
            self.stop_simulation()
            logger.info("🎯 MT5 Simulator stopped by user")

def main():
    """ฟังก์ชันหลัก"""
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and run simulator
    simulator = MT5SimulatorGUI()
    
    # Connect to MT5 if available
    try:
        from order_management import OrderManager
        from mt5_connection import MT5Connection
        
        mt5_connection = MT5Connection()
        order_manager = OrderManager(mt5_connection)
        simulator.connect_to_mt5(order_manager)
        
    except Exception as e:
        logger.warning(f"⚠️ Could not connect to MT5: {e}")
        logger.info("🎯 Running in simulation mode only")
    
    # Run simulator
    simulator.run()

if __name__ == "__main__":
    main()
