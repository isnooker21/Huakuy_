# -*- coding: utf-8 -*-
"""
GUI Module
โมดูลสำหรับ Graphical User Interface ของระบบเทรด
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class TradingGUI:
    """คลาสสำหรับ GUI ของระบบเทรด"""
    
    def __init__(self, trading_system):
        """
        Args:
            trading_system: ระบบเทรดหลัก
        """
        self.trading_system = trading_system
        self.portfolio_manager = trading_system.portfolio_manager
        self.mt5_connection = trading_system.mt5_connection
        
        # สร้าง main window
        self.root = tk.Tk()
        self.root.title("Trading System - Percentage Based")
        self.root.geometry("1400x900")
        self.root.configure(bg='#2b2b2b')
        
        # ตัวแปรสำหรับ GUI
        self.is_trading = False
        self.update_thread = None
        self.stop_update = False
        self._last_account_update = 0  # เพื่อลดความถี่การอัพเดท
        
        # สร้าง GUI components
        self.create_widgets()
        self.setup_styles()
        
        # เริ่มต้นการอัพเดทข้อมูลเบาๆ หลังจาก GUI โหลดเสร็จ
        self.root.after(10000, self.start_light_update)  # รอ 10 วินาทีก่อนเริ่มอัพเดท
        
    def create_widgets(self):
        """สร้าง widgets ทั้งหมด"""
        try:
            # สร้าง main frame
            main_frame = tk.Frame(self.root, bg='#2b2b2b')
            main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
            
            # สร้าง top frame สำหรับการเชื่อมต่อและควบคุม
            self.create_control_panel(main_frame)
            
            # สร้าง middle frame สำหรับข้อมูลหลัก
            self.create_main_info_panel(main_frame)
            
            # สร้าง bottom frame สำหรับ positions และ log
            self.create_bottom_panel(main_frame)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการสร้าง widgets: {str(e)}")
            
    def create_control_panel(self, parent):
        """สร้างแผงควบคุม"""
        control_frame = tk.Frame(parent, bg='#2b2b2b')
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Connection Status
        conn_frame = tk.Frame(control_frame, bg='#3a3a3a', relief=tk.RAISED, bd=1)
        conn_frame.pack(side=tk.LEFT, padx=(0, 10), pady=5, fill=tk.Y)
        
        tk.Label(conn_frame, text="MT5 Connection", bg='#3a3a3a', fg='white', 
                font=('Arial', 10, 'bold')).pack(pady=5)
        
        self.connection_status = tk.Label(conn_frame, text="Disconnected", 
                                        bg='#3a3a3a', fg='red', font=('Arial', 9))
        self.connection_status.pack(pady=2)
        
        self.connect_btn = tk.Button(conn_frame, text="Connect MT5", 
                                   command=self.connect_mt5, bg='#4a4a4a', fg='white')
        self.connect_btn.pack(pady=5)
        
        # Trading Controls
        trading_frame = tk.Frame(control_frame, bg='#3a3a3a', relief=tk.RAISED, bd=1)
        trading_frame.pack(side=tk.LEFT, padx=(0, 10), pady=5, fill=tk.Y)
        
        tk.Label(trading_frame, text="Trading Control", bg='#3a3a3a', fg='white', 
                font=('Arial', 10, 'bold')).pack(pady=5)
        
        self.trading_status = tk.Label(trading_frame, text="Stopped", 
                                     bg='#3a3a3a', fg='red', font=('Arial', 9))
        self.trading_status.pack(pady=2)
        
        self.start_btn = tk.Button(trading_frame, text="Start Trading", 
                                 command=self.start_trading, bg='#4a4a4a', fg='white')
        self.start_btn.pack(side=tk.LEFT, padx=2, pady=5)
        
        self.stop_btn = tk.Button(trading_frame, text="Stop Trading", 
                                command=self.stop_trading, bg='#4a4a4a', fg='white')
        self.stop_btn.pack(side=tk.LEFT, padx=2, pady=5)
        
        # Emergency Controls
        emergency_frame = tk.Frame(control_frame, bg='#3a3a3a', relief=tk.RAISED, bd=1)
        emergency_frame.pack(side=tk.LEFT, padx=(0, 10), pady=5, fill=tk.Y)
        
        tk.Label(emergency_frame, text="Emergency", bg='#3a3a3a', fg='white', 
                font=('Arial', 10, 'bold')).pack(pady=5)
        
        self.close_all_btn = tk.Button(emergency_frame, text="Close All Positions", 
                                     command=self.close_all_positions, bg='#d32f2f', fg='white')
        self.close_all_btn.pack(pady=5)
        
    def create_main_info_panel(self, parent):
        """สร้างแผงข้อมูลหลัก"""
        info_frame = tk.Frame(parent, bg='#2b2b2b')
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Account Info
        self.create_account_info_card(info_frame)
        
        # Portfolio Balance
        self.create_portfolio_balance_card(info_frame)
        
        # Performance Metrics
        self.create_performance_card(info_frame)
        
        # Risk Metrics
        self.create_risk_card(info_frame)
        
    def create_account_info_card(self, parent):
        """สร้างการ์ดข้อมูลบัญชี"""
        card = tk.Frame(parent, bg='#3a3a3a', relief=tk.RAISED, bd=1)
        card.pack(side=tk.LEFT, padx=(0, 10), pady=5, fill=tk.BOTH, expand=True)
        
        tk.Label(card, text="Account Information", bg='#3a3a3a', fg='white', 
                font=('Arial', 12, 'bold')).pack(pady=5)
        
        # Account details
        details_frame = tk.Frame(card, bg='#3a3a3a')
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.account_labels = {}
        account_fields = [
            ('Balance', 'balance'),
            ('Equity', 'equity'),
            ('Margin', 'margin'),
            ('Free Margin', 'margin_free'),
            ('Margin Level', 'margin_level')
        ]
        
        for i, (label, key) in enumerate(account_fields):
            tk.Label(details_frame, text=f"{label}:", bg='#3a3a3a', fg='lightgray', 
                    font=('Arial', 9)).grid(row=i, column=0, sticky='w', pady=2)
            
            self.account_labels[key] = tk.Label(details_frame, text="0.00", bg='#3a3a3a', 
                                              fg='white', font=('Arial', 9, 'bold'))
            self.account_labels[key].grid(row=i, column=1, sticky='e', pady=2)
            
        details_frame.columnconfigure(1, weight=1)
        
    def create_portfolio_balance_card(self, parent):
        """สร้างการ์ดสมดุลพอร์ต"""
        card = tk.Frame(parent, bg='#3a3a3a', relief=tk.RAISED, bd=1)
        card.pack(side=tk.LEFT, padx=(0, 10), pady=5, fill=tk.BOTH, expand=True)
        
        tk.Label(card, text="Portfolio Balance (%)", bg='#3a3a3a', fg='white', 
                font=('Arial', 12, 'bold')).pack(pady=5)
        
        balance_frame = tk.Frame(card, bg='#3a3a3a')
        balance_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Buy/Sell Ratio
        tk.Label(balance_frame, text="Buy/Sell Ratio:", bg='#3a3a3a', fg='lightgray', 
                font=('Arial', 10, 'bold')).pack(pady=2)
        
        ratio_frame = tk.Frame(balance_frame, bg='#3a3a3a')
        ratio_frame.pack(fill=tk.X, pady=5)
        
        self.buy_ratio_label = tk.Label(ratio_frame, text="Buy: 0.0%", bg='#3a3a3a', 
                                      fg='#4caf50', font=('Arial', 9, 'bold'))
        self.buy_ratio_label.pack(side=tk.LEFT)
        
        self.sell_ratio_label = tk.Label(ratio_frame, text="Sell: 0.0%", bg='#3a3a3a', 
                                       fg='#f44336', font=('Arial', 9, 'bold'))
        self.sell_ratio_label.pack(side=tk.RIGHT)
        
        # Progress bars for visual representation
        self.buy_progress = ttk.Progressbar(balance_frame, length=200, mode='determinate')
        self.buy_progress.pack(fill=tk.X, pady=2)
        
        self.sell_progress = ttk.Progressbar(balance_frame, length=200, mode='determinate')
        self.sell_progress.pack(fill=tk.X, pady=2)
        
        # Balance warning
        self.balance_warning = tk.Label(balance_frame, text="", bg='#3a3a3a', 
                                      fg='orange', font=('Arial', 8))
        self.balance_warning.pack(pady=5)
        
    def create_performance_card(self, parent):
        """สร้างการ์ดประสิทธิภาพ"""
        card = tk.Frame(parent, bg='#3a3a3a', relief=tk.RAISED, bd=1)
        card.pack(side=tk.LEFT, padx=(0, 10), pady=5, fill=tk.BOTH, expand=True)
        
        tk.Label(card, text="Performance Metrics (%)", bg='#3a3a3a', fg='white', 
                font=('Arial', 12, 'bold')).pack(pady=5)
        
        perf_frame = tk.Frame(card, bg='#3a3a3a')
        perf_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.performance_labels = {}
        performance_fields = [
            ('Total P&L', 'total_pnl_pct'),
            ('Daily P&L', 'daily_pnl_pct'),
            ('Win Rate', 'win_rate_pct'),
            ('Max Drawdown', 'max_drawdown_pct'),
            ('Profit Factor', 'profit_factor')
        ]
        
        for i, (label, key) in enumerate(performance_fields):
            tk.Label(perf_frame, text=f"{label}:", bg='#3a3a3a', fg='lightgray', 
                    font=('Arial', 9)).grid(row=i, column=0, sticky='w', pady=2)
            
            self.performance_labels[key] = tk.Label(perf_frame, text="0.00%", bg='#3a3a3a', 
                                                  fg='white', font=('Arial', 9, 'bold'))
            self.performance_labels[key].grid(row=i, column=1, sticky='e', pady=2)
            
        perf_frame.columnconfigure(1, weight=1)
        
    def create_risk_card(self, parent):
        """สร้างการ์ดความเสี่ยง"""
        card = tk.Frame(parent, bg='#3a3a3a', relief=tk.RAISED, bd=1)
        card.pack(side=tk.LEFT, pady=5, fill=tk.BOTH, expand=True)
        
        tk.Label(card, text="Risk Management (%)", bg='#3a3a3a', fg='white', 
                font=('Arial', 12, 'bold')).pack(pady=5)
        
        risk_frame = tk.Frame(card, bg='#3a3a3a')
        risk_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.risk_labels = {}
        risk_fields = [
            ('Portfolio Risk', 'portfolio_risk_pct'),
            ('Exposure', 'exposure_pct'),
            ('Losing Positions', 'losing_count'),
            ('Risk per Trade', 'risk_per_trade_pct'),
            ('Daily Loss Limit', 'daily_loss_limit_pct')
        ]
        
        for i, (label, key) in enumerate(risk_fields):
            tk.Label(risk_frame, text=f"{label}:", bg='#3a3a3a', fg='lightgray', 
                    font=('Arial', 9)).grid(row=i, column=0, sticky='w', pady=2)
            
            self.risk_labels[key] = tk.Label(risk_frame, text="0.00%", bg='#3a3a3a', 
                                           fg='white', font=('Arial', 9, 'bold'))
            self.risk_labels[key].grid(row=i, column=1, sticky='e', pady=2)
            
        risk_frame.columnconfigure(1, weight=1)
        
    def create_bottom_panel(self, parent):
        """สร้างแผงด้านล่าง"""
        bottom_frame = tk.Frame(parent, bg='#2b2b2b')
        bottom_frame.pack(fill=tk.BOTH, expand=True)
        
        # สร้าง notebook สำหรับแท็บ
        notebook = ttk.Notebook(bottom_frame)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # แท็บ Positions
        self.create_positions_tab(notebook)
        
        # แท็บ Trading Log
        self.create_log_tab(notebook)
        
        # แท็บ Settings
        self.create_settings_tab(notebook)
        
    def create_positions_tab(self, notebook):
        """สร้างแท็บ Positions"""
        positions_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(positions_frame, text="Positions")
        
        # สร้าง Treeview สำหรับแสดง Positions
        columns = ('Ticket', 'Symbol', 'Type', 'Volume', 'Open Price', 
                  'Current Price', 'Profit', 'Profit %', 'Swap', 'Comment')
        
        self.positions_tree = ttk.Treeview(positions_frame, columns=columns, show='headings')
        
        # กำหนดหัวข้อ
        for col in columns:
            self.positions_tree.heading(col, text=col)
            self.positions_tree.column(col, width=100)
            
        # เพิ่ม scrollbar
        positions_scroll = ttk.Scrollbar(positions_frame, orient=tk.VERTICAL, 
                                       command=self.positions_tree.yview)
        self.positions_tree.configure(yscrollcommand=positions_scroll.set)
        
        # จัดวาง
        self.positions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        positions_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # เพิ่มเมนูคลิกขวา
        self.create_positions_context_menu()
        
    def create_positions_context_menu(self):
        """สร้างเมนูคลิกขวาสำหรับ Positions"""
        self.positions_menu = tk.Menu(self.root, tearoff=0)
        self.positions_menu.add_command(label="Close Position", command=self.close_selected_position)
        self.positions_menu.add_separator()
        self.positions_menu.add_command(label="Close All Profitable", command=self.close_profitable_positions)
        self.positions_menu.add_command(label="Close All Losing", command=self.close_losing_positions)
        self.positions_menu.add_separator()
        self.positions_menu.add_command(label="Scale Close 1:1", command=lambda: self.scale_close("1:1"))
        self.positions_menu.add_command(label="Scale Close 1:2", command=lambda: self.scale_close("1:2"))
        
        # ผูกเมนูกับ Treeview
        self.positions_tree.bind("<Button-3>", self.show_positions_menu)  # Right click
        
    def show_positions_menu(self, event):
        """แสดงเมนูคลิกขวา"""
        try:
            self.positions_menu.post(event.x_root, event.y_root)
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการแสดงเมนู: {str(e)}")
            
    def create_log_tab(self, notebook):
        """สร้างแท็บ Log"""
        log_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(log_frame, text="Trading Log")
        
        # สร้าง ScrolledText สำหรับ log
        self.log_text = scrolledtext.ScrolledText(log_frame, bg='#1a1a1a', fg='lightgreen', 
                                                font=('Consolas', 9), wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # เพิ่ม handler สำหรับ logging
        self.setup_log_handler()
        
    def create_settings_tab(self, notebook):
        """สร้างแท็บ Settings"""
        settings_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(settings_frame, text="Settings")
        
        # Risk Settings
        risk_settings_frame = tk.LabelFrame(settings_frame, text="Risk Settings (%)", 
                                          bg='#3a3a3a', fg='white', font=('Arial', 10, 'bold'))
        risk_settings_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.risk_settings = {}
        risk_settings_fields = [
            ('Max Risk per Trade (%)', 'max_risk_per_trade', 2.0),
            ('Max Portfolio Exposure (%)', 'max_portfolio_exposure', 80.0),
            ('Max Daily Loss (%)', 'max_daily_loss', 10.0),
            ('Profit Target (%)', 'profit_target', 2.0),
            ('Max Drawdown Limit (%)', 'max_drawdown_limit', 15.0)
        ]
        
        for i, (label, key, default_value) in enumerate(risk_settings_fields):
            tk.Label(risk_settings_frame, text=label, bg='#3a3a3a', fg='lightgray', 
                    font=('Arial', 9)).grid(row=i, column=0, sticky='w', padx=5, pady=2)
            
            var = tk.DoubleVar(value=default_value)
            entry = tk.Entry(risk_settings_frame, textvariable=var, width=10)
            entry.grid(row=i, column=1, padx=5, pady=2)
            
            self.risk_settings[key] = var
            
        # Balance Settings
        balance_settings_frame = tk.LabelFrame(settings_frame, text="Balance Settings (%)", 
                                             bg='#3a3a3a', fg='white', font=('Arial', 10, 'bold'))
        balance_settings_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.balance_settings = {}
        balance_settings_fields = [
            ('Balance Warning Threshold (%)', 'balance_warning_threshold', 70.0),
            ('Balance Stop Threshold (%)', 'balance_stop_threshold', 80.0),
            ('Min Market Strength (%)', 'min_market_strength', 0.5),
            ('Min Volume Percentage (%)', 'min_volume_percentage', 120.0)
        ]
        
        for i, (label, key, default_value) in enumerate(balance_settings_fields):
            tk.Label(balance_settings_frame, text=label, bg='#3a3a3a', fg='lightgray', 
                    font=('Arial', 9)).grid(row=i, column=0, sticky='w', padx=5, pady=2)
            
            var = tk.DoubleVar(value=default_value)
            entry = tk.Entry(balance_settings_frame, textvariable=var, width=10)
            entry.grid(row=i, column=1, padx=5, pady=2)
            
            self.balance_settings[key] = var
            
        # Save Settings Button
        save_btn = tk.Button(settings_frame, text="Save Settings", command=self.save_settings, 
                           bg='#4caf50', fg='white', font=('Arial', 10, 'bold'))
        save_btn.pack(pady=10)
        
    def setup_styles(self):
        """ตั้งค่า styles สำหรับ ttk widgets"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # กำหนดสีสำหรับ Treeview
        style.configure("Treeview", background='#2b2b2b', foreground='white', 
                       fieldbackground='#2b2b2b')
        style.configure("Treeview.Heading", background='#3a3a3a', foreground='white')
        
        # กำหนดสีสำหรับ Progressbar
        style.configure("TProgressbar", background='#4caf50')
        
    def setup_log_handler(self):
        """ตั้งค่า log handler สำหรับแสดงใน GUI"""
        class GUILogHandler(logging.Handler):
            def __init__(self, text_widget):
                super().__init__()
                self.text_widget = text_widget
                
            def emit(self, record):
                try:
                    msg = self.format(record)
                    timestamp = datetime.now().strftime("%H:%M:%S")
                    
                    # กำหนดสีตาม level
                    if record.levelno >= logging.ERROR:
                        color = 'red'
                    elif record.levelno >= logging.WARNING:
                        color = 'orange'
                    elif record.levelno >= logging.INFO:
                        color = 'lightgreen'
                    else:
                        color = 'lightgray'
                        
                    # แสดงใน GUI (thread-safe)
                    self.text_widget.after(0, lambda: self._append_log(f"[{timestamp}] {msg}\n", color))
                except:
                    pass
                    
            def _append_log(self, message, color):
                try:
                    self.text_widget.insert(tk.END, message)
                    self.text_widget.see(tk.END)
                    
                    # จำกัดจำนวนบรรทัด
                    lines = int(self.text_widget.index('end-1c').split('.')[0])
                    if lines > 1000:
                        self.text_widget.delete('1.0', '100.0')
                except:
                    pass
                    
        # เพิ่ม handler ให้กับ logger
        gui_handler = GUILogHandler(self.log_text)
        gui_handler.setFormatter(logging.Formatter('%(name)s - %(levelname)s - %(message)s'))
        logging.getLogger().addHandler(gui_handler)
        
    def start_light_update(self):
        """เริ่มต้นการอัพเดทข้อมูลแบบเบา"""
        if not self.update_thread or not self.update_thread.is_alive():
            self.stop_update = False
            self.update_thread = threading.Thread(target=self.light_update_loop, daemon=True)
            self.update_thread.start()
            
    def start_data_update(self):
        """เริ่มต้นการอัพเดทข้อมูล (ใช้เมื่อจำเป็น)"""
        if not self.update_thread or not self.update_thread.is_alive():
            self.stop_update = False
            self.update_thread = threading.Thread(target=self.update_data_loop, daemon=True)
            self.update_thread.start()
            
    def light_update_loop(self):
        """Loop อัพเดทแบบเบา"""
        while not self.stop_update:
            try:
                if not self.stop_update:
                    self.root.after_idle(self.update_connection_status_light)
                time.sleep(10)  # อัพเดททุก 10 วินาที
            except Exception as e:
                logger.debug(f"Light update error: {str(e)}")
                time.sleep(20)
            
    def update_data_loop(self):
        """Loop สำหรับอัพเดทข้อมูล"""
        while not self.stop_update:
            try:
                # อัพเดทข้อมูลใน main thread (ลดความถี่มากขึ้น)
                if not self.stop_update:  # ตรวจสอบอีกครั้ง
                    self.root.after_idle(self.safe_update_gui_data)  # ใช้ after_idle แทน after(0)
                time.sleep(5)  # อัพเดททุก 5 วินาที (เพิ่มจาก 3 วินาที)
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการอัพเดทข้อมูล: {str(e)}")
                time.sleep(15)  # รอนานขึ้นเมื่อเกิดข้อผิดพลาด
                
    def safe_update_gui_data(self):
        """อัพเดทข้อมูลใน GUI อย่างปลอดภัย"""
        try:
            if self.stop_update:  # หยุดการอัพเดทถ้าได้รับสัญญาณ
                return
                
            # อัพเดทสถานะการเชื่อมต่อ (เบาๆ)
            self.update_connection_status_light()
            
            if self.stop_update:
                return
                
            # อัพเดทข้อมูลบัญชี (ลดความถี่)
            if hasattr(self, '_last_account_update'):
                if time.time() - self._last_account_update < 10:  # อัพเดททุก 10 วินาที
                    return
            
            if self.mt5_connection.is_connected:  # ใช้ตัวแปรแทนการเรียกฟังก์ชัน
                self.update_account_info()
                self._last_account_update = time.time()
                
            if self.stop_update:
                return
                
            # อัพเดทข้อมูลพอร์ต (ลดความถี่)
            self.update_portfolio_info_light()
            
            if self.stop_update:
                return
                
            # อัพเดท Positions (ลดความถี่)
            self.update_positions_display_light()
            
        except Exception as e:
            logger.debug(f"GUI update error: {str(e)}")  # ใช้ debug แทน error
            
    def update_gui_data(self):
        """อัพเดทข้อมูลใน GUI (เรียกจาก safe_update_gui_data)"""
        self.safe_update_gui_data()
        
    def update_connection_status_light(self):
        """อัพเดทสถานะการเชื่อมต่อแบบเบา"""
        try:
            # ใช้ตัวแปรแทนการเรียกฟังก์ชัน
            if self.mt5_connection.is_connected:
                self.connection_status.config(text="Connected", fg='green')
                self.connect_btn.config(text="Disconnect", command=self.disconnect_mt5)
            else:
                self.connection_status.config(text="Disconnected", fg='red')
                self.connect_btn.config(text="Connect MT5", command=self.connect_mt5)
                
            # อัพเดทสถานะการเทรด
            if hasattr(self.trading_system, 'is_running') and self.trading_system.is_running:
                self.trading_status.config(text="Running", fg='green')
            else:
                self.trading_status.config(text="Stopped", fg='red')
                
        except Exception as e:
            pass  # ไม่ log error เพื่อลด overhead
            
    def update_portfolio_info_light(self):
        """อัพเดทข้อมูลพอร์ตแบบเบา"""
        try:
            # อัพเดทเฉพาะข้อมูลสำคัญ
            if hasattr(self.portfolio_manager.order_manager, 'active_positions'):
                positions = self.portfolio_manager.order_manager.active_positions or []
                
                if positions:
                    from calculations import PercentageCalculator
                    balance_ratio = PercentageCalculator.calculate_buy_sell_ratio(positions)
                    
                    buy_pct = balance_ratio.get('buy_percentage', 0)
                    sell_pct = balance_ratio.get('sell_percentage', 0)
                    
                    self.buy_ratio_label.config(text=f"Buy: {buy_pct:.1f}%")
                    self.sell_ratio_label.config(text=f"Sell: {sell_pct:.1f}%")
                    
                    self.buy_progress['value'] = buy_pct
                    self.sell_progress['value'] = sell_pct
                    
        except Exception as e:
            pass  # ไม่ log error
            
    def update_positions_display_light(self):
        """อัพเดทการแสดง Positions แบบเบา"""
        try:
            # อัพเดทเฉพาะเมื่อจำเป็น
            if not hasattr(self, 'positions_tree'):
                return
                
            positions = getattr(self.portfolio_manager.order_manager, 'active_positions', [])
            current_count = len(self.positions_tree.get_children())
            
            # อัพเดทเฉพาะเมื่อจำนวน position เปลี่ยน
            if len(positions) != current_count:
                self.update_positions_display()
                
        except Exception as e:
            pass  # ไม่ log error
            
    def update_connection_status(self):
        """อัพเดทสถานะการเชื่อมต่อ"""
        try:
            if self.mt5_connection.check_connection_health():
                self.connection_status.config(text="Connected", fg='green')
                self.connect_btn.config(text="Disconnect", command=self.disconnect_mt5)
            else:
                self.connection_status.config(text="Disconnected", fg='red')
                self.connect_btn.config(text="Connect MT5", command=self.connect_mt5)
                
            # อัพเดทสถานะการเทรด
            if self.trading_system.is_running:
                self.trading_status.config(text="Running", fg='green')
            else:
                self.trading_status.config(text="Stopped", fg='red')
                
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการอัพเดทสถานะการเชื่อมต่อ: {str(e)}")
            
    def update_account_info(self):
        """อัพเดทข้อมูลบัญชี"""
        try:
            account_info = self.mt5_connection.get_account_info()
            if account_info:
                self.account_labels['balance'].config(text=f"{account_info['balance']:.2f}")
                self.account_labels['equity'].config(text=f"{account_info['equity']:.2f}")
                self.account_labels['margin'].config(text=f"{account_info['margin']:.2f}")
                self.account_labels['margin_free'].config(text=f"{account_info['margin_free']:.2f}")
                
                margin_level = account_info['margin_level']
                self.account_labels['margin_level'].config(text=f"{margin_level:.2f}%")
                
                # เปลี่ยนสีตาม Margin Level
                if margin_level < 100:
                    self.account_labels['margin_level'].config(fg='red')
                elif margin_level < 200:
                    self.account_labels['margin_level'].config(fg='orange')
                else:
                    self.account_labels['margin_level'].config(fg='green')
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการอัพเดทข้อมูลบัญชี: {str(e)}")
            
    def update_portfolio_info(self):
        """อัพเดทข้อมูลพอร์ต"""
        try:
            # ตรวจสอบว่ามี positions หรือไม่ก่อน
            if not hasattr(self.portfolio_manager.order_manager, 'active_positions'):
                return
                
            # ดึงข้อมูลสรุปพอร์ต (ถ้าไม่มี error)
            try:
                portfolio_summary = self.portfolio_manager.get_portfolio_summary()
            except Exception as e:
                logger.debug(f"ไม่สามารถดึงข้อมูลพอร์ตได้: {str(e)}")
                return
            
            if portfolio_summary and 'error' not in portfolio_summary:
                # อัพเดทข้อมูล Performance
                perf_metrics = portfolio_summary.get('performance_metrics', {})
                
                total_pnl_pct = portfolio_summary.get('total_profit_percentage', 0.0)
                self.performance_labels['total_pnl_pct'].config(text=f"{total_pnl_pct:.2f}%")
                self.performance_labels['total_pnl_pct'].config(
                    fg='green' if total_pnl_pct >= 0 else 'red'
                )
                
                daily_pnl_pct = perf_metrics.get('daily_pnl_percentage', 0.0)
                self.performance_labels['daily_pnl_pct'].config(text=f"{daily_pnl_pct:.2f}%")
                self.performance_labels['daily_pnl_pct'].config(
                    fg='green' if daily_pnl_pct >= 0 else 'red'
                )
                
                win_rate = perf_metrics.get('win_rate_percentage', 0.0)
                self.performance_labels['win_rate_pct'].config(text=f"{win_rate:.1f}%")
                
                max_dd = perf_metrics.get('max_drawdown_percentage', 0.0)
                self.performance_labels['max_drawdown_pct'].config(text=f"{max_dd:.2f}%")
                self.performance_labels['max_drawdown_pct'].config(
                    fg='red' if max_dd > 10 else 'orange' if max_dd > 5 else 'green'
                )
                
                profit_factor = perf_metrics.get('profit_factor', 0.0)
                self.performance_labels['profit_factor'].config(text=f"{profit_factor:.2f}")
                
                # อัพเดทข้อมูล Balance
                positions = self.portfolio_manager.order_manager.active_positions
                if positions:
                    from calculations import PercentageCalculator
                    balance_ratio = PercentageCalculator.calculate_buy_sell_ratio(positions)
                    
                    buy_pct = balance_ratio['buy_percentage']
                    sell_pct = balance_ratio['sell_percentage']
                    
                    self.buy_ratio_label.config(text=f"Buy: {buy_pct:.1f}%")
                    self.sell_ratio_label.config(text=f"Sell: {sell_pct:.1f}%")
                    
                    self.buy_progress['value'] = buy_pct
                    self.sell_progress['value'] = sell_pct
                    
                    # เตือนความไม่สมดุล
                    if buy_pct >= 70 or sell_pct >= 70:
                        self.balance_warning.config(text="⚠️ Portfolio Imbalance Warning!", fg='orange')
                    elif buy_pct >= 80 or sell_pct >= 80:
                        self.balance_warning.config(text="🚨 Critical Imbalance!", fg='red')
                    else:
                        self.balance_warning.config(text="✅ Portfolio Balanced", fg='green')
                        
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการอัพเดทข้อมูลพอร์ต: {str(e)}")
            
    def update_positions_display(self):
        """อัพเดทการแสดง Positions"""
        try:
            # ตรวจสอบว่ามี positions tree หรือไม่
            if not hasattr(self, 'positions_tree'):
                return
                
            # ดึงข้อมูล positions อย่างปลอดภัย
            try:
                positions = self.portfolio_manager.order_manager.active_positions
            except Exception as e:
                logger.debug(f"ไม่สามารถดึงข้อมูล positions ได้: {str(e)}")
                return
                
            # ลบข้อมูลเก่า
            for item in self.positions_tree.get_children():
                self.positions_tree.delete(item)
                
            # เพิ่มข้อมูลใหม่
            if positions:
                for pos in positions:
                    # คำนวณ Profit %
                    profit_pct = 0.0
                    if pos.price_open != 0:
                        if pos.type == 0:  # BUY
                            profit_pct = ((pos.price_current - pos.price_open) / pos.price_open) * 100
                        else:  # SELL
                            profit_pct = ((pos.price_open - pos.price_current) / pos.price_open) * 100
                        
                    # เพิ่มข้อมูลใน Treeview
                    values = (
                        pos.ticket,
                        pos.symbol,
                        "BUY" if pos.type == 0 else "SELL",
                        f"{pos.volume:.2f}",
                        f"{pos.price_open:.5f}",
                        f"{pos.price_current:.5f}",
                        f"{pos.profit:.2f}",
                        f"{profit_pct:.2f}%",
                        f"{pos.swap:.2f}",
                        pos.comment
                    )
                    
                    item = self.positions_tree.insert('', 'end', values=values)
                    
                    # เปลี่ยนสีตามกำไรขาดทุน
                    if pos.profit > 0:
                        self.positions_tree.set(item, 'Profit', f"+{pos.profit:.2f}")
                        # สีเขียวสำหรับกำไร (ต้องใช้ tag)
                    elif pos.profit < 0:
                        # สีแดงสำหรับขาดทุน (ต้องใช้ tag)
                        pass
                    
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการอัพเดท Positions: {str(e)}")
            
    # Event handlers
    def connect_mt5(self):
        """เชื่อมต่อ MT5"""
        try:
            success = self.mt5_connection.connect_mt5()
            if success:
                logger.info("เชื่อมต่อ MT5 สำเร็จ")
                messagebox.showinfo("Success", "เชื่อมต่อ MT5 สำเร็จ")
                # อัพเดท GUI ทันทีหลังเชื่อมต่อ
                self.root.after(100, self.update_connection_status_light)
            else:
                logger.error("ไม่สามารถเชื่อมต่อ MT5 ได้")
                messagebox.showerror("Error", "ไม่สามารถเชื่อมต่อ MT5 ได้")
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ MT5: {str(e)}")
            messagebox.showerror("Error", f"เกิดข้อผิดพลาด: {str(e)}")
            
    def disconnect_mt5(self):
        """ตัดการเชื่อมต่อ MT5"""
        try:
            self.mt5_connection.disconnect_mt5()
            logger.info("ตัดการเชื่อมต่อ MT5 แล้ว")
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการตัดการเชื่อมต่อ MT5: {str(e)}")
            
    def start_trading(self):
        """เริ่มการเทรด"""
        try:
            if not self.mt5_connection.is_connected:
                messagebox.showerror("Error", "กรุณาเชื่อมต่อ MT5 ก่อน")
                return
                
            # เริ่มการเทรดผ่าน TradingSystem
            self.trading_system.start_trading()
            self.is_trading = True
            self.trading_status.config(text="Running", fg='green')
            logger.info("เริ่มการเทรดจาก GUI")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการเริ่มเทรด: {str(e)}")
            messagebox.showerror("Error", f"เกิดข้อผิดพลาด: {str(e)}")
            
    def stop_trading(self):
        """หยุดการเทรด"""
        try:
            # หยุดการเทรดผ่าน TradingSystem
            self.trading_system.stop_trading()
            self.is_trading = False
            self.trading_status.config(text="Stopped", fg='red')
            logger.info("หยุดการเทรดจาก GUI")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการหยุดเทรด: {str(e)}")
            
    def close_all_positions(self):
        """ปิด Position ทั้งหมด"""
        try:
            if messagebox.askyesno("Confirm", "คุณต้องการปิด Position ทั้งหมดหรือไม่?"):
                result = self.portfolio_manager.order_manager.emergency_close_all("Manual close all")
                if result.success:
                    logger.info(f"ปิด Position ทั้งหมดสำเร็จ - จำนวน: {len(result.closed_tickets)}")
                    messagebox.showinfo("Success", f"ปิด Position สำเร็จ {len(result.closed_tickets)} ตัว")
                else:
                    logger.error(f"ไม่สามารถปิด Position ได้: {result.error_message}")
                    messagebox.showerror("Error", result.error_message)
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการปิด Position ทั้งหมด: {str(e)}")
            messagebox.showerror("Error", f"เกิดข้อผิดพลาด: {str(e)}")
            
    def close_selected_position(self):
        """ปิด Position ที่เลือก"""
        # Implementation for closing selected position
        pass
        
    def close_profitable_positions(self):
        """ปิด Position ที่กำไร"""
        # Implementation for closing profitable positions
        pass
        
    def close_losing_positions(self):
        """ปิด Position ที่ขาดทุน"""
        # Implementation for closing losing positions
        pass
        
    def scale_close(self, scaling_type):
        """ปิด Position แบบ Scaling"""
        # Implementation for scaling close
        pass
        
    def save_settings(self):
        """บันทึกการตั้งค่า"""
        try:
            # อัพเดทการตั้งค่าใน portfolio manager
            pm = self.portfolio_manager
            
            pm.max_risk_per_trade = self.risk_settings['max_risk_per_trade'].get()
            pm.max_portfolio_exposure = self.risk_settings['max_portfolio_exposure'].get()
            pm.max_daily_loss = self.risk_settings['max_daily_loss'].get()
            pm.profit_target = self.risk_settings['profit_target'].get()
            pm.max_drawdown_limit = self.risk_settings['max_drawdown_limit'].get()
            
            pm.balance_warning_threshold = self.balance_settings['balance_warning_threshold'].get()
            pm.balance_stop_threshold = self.balance_settings['balance_stop_threshold'].get()
            
            logger.info("บันทึกการตั้งค่าสำเร็จ")
            messagebox.showinfo("Success", "บันทึกการตั้งค่าสำเร็จ")
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการบันทึกการตั้งค่า: {str(e)}")
            messagebox.showerror("Error", f"เกิดข้อผิดพลาด: {str(e)}")
            
    def run(self):
        """เริ่มต้น GUI"""
        try:
            logger.info("เริ่มต้น Trading System GUI")
            self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
            self.root.mainloop()
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดใน GUI: {str(e)}")
            
    def on_closing(self):
        """จัดการเมื่อปิด GUI"""
        try:
            logger.info("กำลังปิด GUI...")
            
            # หยุด update thread
            self.stop_update = True
            
            # หยุดการเทรดก่อน
            if hasattr(self, 'trading_system') and self.trading_system.is_running:
                self.trading_system.stop_trading()
            
            # รอ update thread ให้หยุด
            if self.update_thread and self.update_thread.is_alive():
                self.update_thread.join(timeout=2)  # เพิ่มเวลารอ
                
            # ตัดการเชื่อมต่อ MT5
            try:
                self.mt5_connection.disconnect_mt5()
            except:
                pass  # ไม่สำคัญถ้า disconnect ไม่ได้
                
            logger.info("ปิด Trading System สำเร็จ")
            self.root.quit()  # ใช้ quit แทน destroy
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการปิด GUI: {str(e)}")
            try:
                self.root.quit()
            except:
                pass
