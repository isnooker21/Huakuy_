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
        self.root.title("🚀 Enhanced 7D Smart Trading System")
        self.root.geometry("1200x800")
        self.root.configure(bg='#1a1a1a')
        
        # ตั้งค่า icon และ style
        try:
            self.root.iconbitmap('icon.ico')  # ถ้ามี icon file
        except:
            pass
        
        # ตัวแปรสำหรับ GUI
        self.is_trading = False
        self.update_thread = None
        self.stop_update = False
        self._last_account_update = 0  # เพื่อลดความถี่การอัพเดท
        self._last_market_status_update = 0  # สำหรับ market status
        self._last_7d_analysis_update = 0  # สำหรับ 7D analysis
        
        # สร้าง GUI components
        self.create_widgets()
        self.setup_styles()
        
        # เริ่มต้นการอัพเดทข้อมูลเบาๆ หลังจาก GUI โหลดเสร็จ
        self.root.after(10000, self.start_light_update)  # รอ 10 วินาทีก่อนเริ่มอัพเดท
        
    def create_widgets(self):
        """สร้าง widgets ทั้งหมด"""
        try:
            # สร้าง main frame
            main_frame = tk.Frame(self.root, bg='#1a1a1a')
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
        control_frame = tk.Frame(parent, bg='#1a1a1a')
        control_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Connection Status
        conn_frame = tk.Frame(control_frame, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        conn_frame.pack(side=tk.LEFT, padx=(0, 10), pady=3, fill=tk.Y)
        
        tk.Label(conn_frame, text="🔗 MT5 Connection", bg='#2d2d2d', fg='#00ff88', 
                                                    font=('Segoe UI', 8, 'bold')).pack(pady=4)
        
        self.connection_status = tk.Label(conn_frame, text="Disconnected", 
                                        bg='#2d2d2d', fg='#ff4444', font=('Segoe UI', 9, 'bold'))
        self.connection_status.pack(pady=2)
        
        self.connect_btn = tk.Button(conn_frame, text="Connect MT5", 
                                   command=self.connect_mt5, bg='#4a4a4a', fg='white',
                                   font=('Segoe UI', 9), relief=tk.RAISED, bd=2)
        self.connect_btn.pack(pady=4)
        
        # Trading Controls
        trading_frame = tk.Frame(control_frame, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        trading_frame.pack(side=tk.LEFT, padx=(0, 10), pady=3, fill=tk.Y)
        
        tk.Label(trading_frame, text="🎯 Trading Control", bg='#2d2d2d', fg='#00ff88', 
                                                    font=('Segoe UI', 8, 'bold')).pack(pady=4)
        
        self.trading_status = tk.Label(trading_frame, text="Stopped", 
                                     bg='#2d2d2d', fg='#ff4444', font=('Segoe UI', 9, 'bold'))
        self.trading_status.pack(pady=3)
        
        btn_frame = tk.Frame(trading_frame, bg='#2d2d2d')
        btn_frame.pack(pady=8)
        
        self.start_btn = tk.Button(btn_frame, text="▶️ Start", 
                                 command=self.start_trading, bg='#4CAF50', fg='white',
                                 font=('Segoe UI', 9, 'bold'), relief=tk.RAISED, bd=2)
        self.start_btn.pack(side=tk.LEFT, padx=3)
        
        self.stop_btn = tk.Button(btn_frame, text="⏹️ Stop", 
                                command=self.stop_trading, bg='#f44336', fg='white',
                                font=('Segoe UI', 9, 'bold'), relief=tk.RAISED, bd=2)
        self.stop_btn.pack(side=tk.LEFT, padx=3)
        
        # Emergency Controls
        emergency_frame = tk.Frame(control_frame, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        emergency_frame.pack(side=tk.LEFT, padx=(0, 10), pady=3, fill=tk.Y)
        
        tk.Label(emergency_frame, text="🚨 Emergency", bg='#2d2d2d', fg='#ff4444', 
                                                    font=('Segoe UI', 8, 'bold')).pack(pady=4)
        
        self.close_all_btn = tk.Button(emergency_frame, text="🛑 Close All Positions", 
                                     command=self.close_all_positions, bg='#d32f2f', fg='white',
                                     font=('Segoe UI', 9, 'bold'), relief=tk.RAISED, bd=2)
        self.close_all_btn.pack(pady=8)
    
    def create_market_status_panel(self, parent):
        """สร้างแผงสถานะตลาด"""
        market_frame = tk.Frame(parent, bg='#1a1a1a')
        market_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Market Status Card
        status_card = tk.Frame(market_frame, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        status_card.pack(fill=tk.X, pady=5)
        
        tk.Label(status_card, text="🕐 Market Status", bg='#2d2d2d', fg='#00ff88', 
                font=('Segoe UI', 10, 'bold')).pack(pady=4)
        
        # Market status info
        status_info_frame = tk.Frame(status_card, bg='#2d2d2d')
        status_info_frame.pack(fill=tk.X, padx=10, pady=3)
        
        # Market status labels
        self.market_status_labels = {}
        market_fields = [
            ('status', 'Status', '🔴 CLOSED'),
            ('current_time', 'Current Time', '00:00:00'),
            ('active_sessions', 'Active Sessions', 'None'),
            ('next_session', 'Next Session', 'Unknown'),
            ('london_ny_overlap', 'London-NY Overlap', '❌')
        ]
        
        for i, (key, label, default) in enumerate(market_fields):
            row = i // 3
            col = i % 3
            
            field_frame = tk.Frame(status_info_frame, bg='#2d2d2d')
            field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')
            
            tk.Label(field_frame, text=f"{label}:", bg='#2d2d2d', fg='#cccccc', 
                    font=('Segoe UI', 8)).pack(anchor='w')
            
            self.market_status_labels[key] = tk.Label(field_frame, text=default, 
                                                    bg='#2d2d2d', fg='#00ff88', 
                                                    font=('Segoe UI', 8, 'bold'))
            self.market_status_labels[key].pack(anchor='w')
        
        # Configure grid weights
        for i in range(3):
            status_info_frame.columnconfigure(i, weight=1)
        
    def create_main_info_panel(self, parent):
        """สร้างแผงข้อมูลหลัก"""
        info_frame = tk.Frame(parent, bg='#1a1a1a')
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Account Info (จำเป็น)
        self.create_account_info_card(info_frame)
        
        # Trading Status (สำคัญ)
        self.create_trading_status_card(info_frame)
        
        # 7D Smart Closer Status (สำคัญ)
        self.create_7d_closer_status_card(info_frame)
    
    def create_7d_analysis_panel(self, parent):
        """สร้างแผงวิเคราะห์ 7D"""
        analysis_frame = tk.Frame(parent, bg='#1a1a1a')
        analysis_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 7D Analysis Card
        analysis_card = tk.Frame(analysis_frame, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        analysis_card.pack(fill=tk.X, pady=5)
        
        tk.Label(analysis_card, text="🧠 7D Smart Analysis", bg='#2d2d2d', fg='#00ff88', 
                font=('Segoe UI', 10, 'bold')).pack(pady=4)
        
        # 7D Analysis info
        analysis_info_frame = tk.Frame(analysis_card, bg='#2d2d2d')
        analysis_info_frame.pack(fill=tk.X, padx=10, pady=3)
        
        # 7D Analysis labels
        self.analysis_labels = {}
        analysis_fields = [
            ('portfolio_health', 'Portfolio Health', '🟢 EXCELLENT'),
            ('risk_level', 'Risk Level', '🟢 LOW'),
            ('market_timing', 'Market Timing', '🟢 EXCELLENT'),
            ('closing_recommendation', 'Closing Recommendation', '💤 HOLD'),
            ('active_positions', 'Active Positions', '0'),
            ('closing_confidence', 'Closing Confidence', '0%')
        ]
        
        for i, (key, label, default) in enumerate(analysis_fields):
            row = i // 3
            col = i % 3
            
            field_frame = tk.Frame(analysis_info_frame, bg='#2d2d2d')
            field_frame.grid(row=row, column=col, padx=10, pady=5, sticky='ew')
            
            tk.Label(field_frame, text=f"{label}:", bg='#2d2d2d', fg='#cccccc', 
                    font=('Segoe UI', 8)).pack(anchor='w')
            
            self.analysis_labels[key] = tk.Label(field_frame, text=default, 
                                               bg='#2d2d2d', fg='#00ff88', 
                                               font=('Segoe UI', 8, 'bold'))
            self.analysis_labels[key].pack(anchor='w')
        
        # Configure grid weights
        for i in range(3):
            analysis_info_frame.columnconfigure(i, weight=1)
        
    def create_account_info_card(self, parent):
        """สร้างการ์ดข้อมูลบัญชี"""
        card = tk.Frame(parent, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        card.pack(side=tk.LEFT, padx=(0, 10), pady=3, fill=tk.BOTH, expand=True)
        
        tk.Label(card, text="💰 Account Information", bg='#2d2d2d', fg='#00ff88', 
                font=('Segoe UI', 10, 'bold')).pack(pady=4)
        
        # Account details
        details_frame = tk.Frame(card, bg='#2d2d2d')
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.account_labels = {}
        account_fields = [
            ('Balance', 'balance', '💵'),
            ('Equity', 'equity', '📊'),
            ('Margin', 'margin', '🔒'),
            ('Free Margin', 'margin_free', '🆓'),
            ('Margin Level', 'margin_level', '📈')
        ]
        
        for i, (label, key, icon) in enumerate(account_fields):
            tk.Label(details_frame, text=f"{icon} {label}:", bg='#2d2d2d', fg='#cccccc', 
                    font=('Segoe UI', 8)).grid(row=i, column=0, sticky='w', pady=2)
            
            self.account_labels[key] = tk.Label(details_frame, text="0.00", bg='#2d2d2d', 
                                              fg='#00ff88', font=('Segoe UI', 9, 'bold'))
            self.account_labels[key].grid(row=i, column=1, sticky='e', pady=3)
            
        details_frame.columnconfigure(1, weight=1)
    
    def create_trading_status_card(self, parent):
        """สร้างการ์ดสถานะการเทรด"""
        card = tk.Frame(parent, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        card.pack(side=tk.LEFT, padx=(0, 10), pady=3, fill=tk.BOTH, expand=True)
        
        tk.Label(card, text="📈 Trading Status", bg='#2d2d2d', fg='#00ff88', 
                font=('Segoe UI', 10, 'bold')).pack(pady=4)
        
        # Trading status details
        details_frame = tk.Frame(card, bg='#2d2d2d')
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.trading_status_labels = {}
        trading_fields = [
            ('active_positions', 'Active Positions', '0', '🎯'),
            ('total_pnl', 'Total P&L', '0.00', '💰'),
            ('daily_pnl', 'Daily P&L', '0.00', '📊'),
            ('win_rate', 'Win Rate', '0%', '🎯'),
            ('profit_factor', 'Profit Factor', '0.00', '⚡')
        ]
        
        for i, (key, label, default, icon) in enumerate(trading_fields):
            tk.Label(details_frame, text=f"{icon} {label}:", bg='#2d2d2d', fg='#cccccc', 
                    font=('Segoe UI', 8)).grid(row=i, column=0, sticky='w', pady=2)
            
            self.trading_status_labels[key] = tk.Label(details_frame, text=default, bg='#2d2d2d', 
                                              fg='#00ff88', font=('Segoe UI', 9, 'bold'))
            self.trading_status_labels[key].grid(row=i, column=1, sticky='e', pady=3)
            
        details_frame.columnconfigure(1, weight=1)
    
    def create_7d_closer_status_card(self, parent):
        """สร้างการ์ดสถานะ 7D Smart Closer"""
        card = tk.Frame(parent, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        card.pack(side=tk.LEFT, padx=(0, 10), pady=3, fill=tk.BOTH, expand=True)
        
        tk.Label(card, text="🧠 7D Smart Closer", bg='#2d2d2d', fg='#00ff88', 
                font=('Segoe UI', 10, 'bold')).pack(pady=4)
        
        # 7D Closer status details
        details_frame = tk.Frame(card, bg='#2d2d2d')
        details_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.closer_status_labels = {}
        closer_fields = [
            ('closer_status', 'Closer Status', '💤 IDLE', '🔄'),
            ('last_analysis', 'Last Analysis', 'Never', '⏰'),
            ('closing_confidence', 'Confidence', '0%', '🎯'),
            ('positions_analyzed', 'Positions Analyzed', '0', '📊'),
            ('recommendation', 'Recommendation', 'HOLD', '💡')
        ]
        
        for i, (key, label, default, icon) in enumerate(closer_fields):
            tk.Label(details_frame, text=f"{icon} {label}:", bg='#2d2d2d', fg='#cccccc', 
                    font=('Segoe UI', 8)).grid(row=i, column=0, sticky='w', pady=2)
            
            self.closer_status_labels[key] = tk.Label(details_frame, text=default, bg='#2d2d2d', 
                                              fg='#00ff88', font=('Segoe UI', 9, 'bold'))
            self.closer_status_labels[key].grid(row=i, column=1, sticky='e', pady=3)
            
        details_frame.columnconfigure(1, weight=1)
        
        
    def create_bottom_panel(self, parent):
        """สร้างแผงด้านล่าง"""
        bottom_frame = tk.Frame(parent, bg='#2b2b2b')
        bottom_frame.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
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
                  'Current Price', 'Profit', 'Profit %', 'Swap', 'Comment', 'Hedge Pair')
        
        self.positions_tree = ttk.Treeview(positions_frame, columns=columns, show='headings')
        
        # กำหนดหัวข้อ
        for col in columns:
            self.positions_tree.heading(col, text=col)
            if col == 'Hedge Pair':
                self.positions_tree.column(col, width=150)  # กว้างขึ้นสำหรับแสดงการจับคู่
            else:
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
                                                font=('Consolas', 8), wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=3, pady=3)
        
        # เพิ่ม handler สำหรับ logging
        self.setup_log_handler()
        
    def create_settings_tab(self, notebook):
        """สร้างแท็บ Settings"""
        settings_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(settings_frame, text="Settings")
        
        # Risk Settings
        risk_settings_frame = tk.LabelFrame(settings_frame, text="Risk Settings (%)", 
                                          bg='#3a3a3a', fg='white', font=('Arial', 10, 'bold'))
        risk_settings_frame.pack(fill=tk.X, padx=8, pady=3)
        
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
        balance_settings_frame.pack(fill=tk.X, padx=8, pady=3)
        
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
        style.configure("Treeview", background='#1a1a1a', foreground='white', 
                       fieldbackground='#1a1a1a', font=('Segoe UI', 8))
        style.configure("Treeview.Heading", background='#2d2d2d', foreground='#00ff88',
                                                    font=('Segoe UI', 8, 'bold'))
        
        # กำหนดสีสำหรับ Progressbar
        style.configure("TProgressbar", background='#00ff88', troughcolor='#2d2d2d')
        
        # กำหนดสีสำหรับ Notebook tabs
        style.configure("TNotebook", background='#1a1a1a')
        style.configure("TNotebook.Tab", background='#2d2d2d', foreground='white',
                       padding=[15, 8], font=('Segoe UI', 8))
        style.map("TNotebook.Tab", background=[('selected', '#00ff88'), ('active', '#3d3d3d')],
                 foreground=[('selected', '#1a1a1a'), ('active', 'white')])
        
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
        """Loop อัพเดทแบบเบา - OPTIMIZED"""
        update_counter = 0
        while not self.stop_update:
            try:
                if not self.stop_update:
                    # 🚀 OPTIMIZED: อัพเดท connection status ทุกครั้ง
                    self.root.after_idle(self.update_connection_status_light)
                    
                    # 🚀 OPTIMIZED: อัพเดทข้อมูลอื่นๆ แบบสลับกัน - ลดความถี่
                    if update_counter % 4 == 0:  # ทุก 80 วินาที (เพิ่มมากขึ้น)
                        self.root.after_idle(self.update_account_info)
                        self.root.after_idle(self.update_trading_status_data)
                    
                    if update_counter % 6 == 0:  # ทุก 120 วินาที (เพิ่มมากขึ้น)
                        self.root.after_idle(self.update_positions_display_light)
                    
                    if update_counter % 8 == 0:  # ทุก 160 วินาที (เพิ่มมากขึ้น)
                        self.root.after_idle(self.update_7d_closer_status)
                    
                    update_counter += 1
                time.sleep(20)  # อัพเดททุก 20 วินาที (เพิ่มจาก 15)
            except Exception as e:
                logger.debug(f"Light update error: {str(e)}")
                time.sleep(30)
            
    def update_data_loop(self):
        """Loop สำหรับอัพเดทข้อมูล - OPTIMIZED"""
        while not self.stop_update:
            try:
                # 🚀 OPTIMIZED: อัพเดทข้อมูลใน main thread - ลดความถี่มากขึ้น
                if not self.stop_update:  # ตรวจสอบอีกครั้ง
                    self.root.after_idle(self.safe_update_gui_data)  # ใช้ after_idle แทน after(0)
                time.sleep(30)  # อัพเดททุก 30 วินาที (เพิ่มจาก 15 วินาที เพื่อลด GUI load มากขึ้น)
            except Exception as e:
                logger.error(f"เกิดข้อผิดพลาดในการอัพเดทข้อมูล: {str(e)}")
                time.sleep(20)  # รอนานขึ้นเมื่อเกิดข้อผิดพลาด (เพิ่มจาก 15)
                
    def safe_update_gui_data(self):
        """อัพเดทข้อมูลใน GUI อย่างปลอดภัย - OPTIMIZED"""
        try:
            if self.stop_update:  # หยุดการอัพเดทถ้าได้รับสัญญาณ
                return
                
            # 🚀 OPTIMIZED: อัพเดทสถานะการเชื่อมต่อ (เบาๆ)
            self.update_connection_status_light()
            
            if self.stop_update:
                return
                
            # 🚀 OPTIMIZED: อัพเดทข้อมูลบัญชี (ลดความถี่มากขึ้น)
            if hasattr(self, '_last_account_update'):
                if time.time() - self._last_account_update < 45:  # อัพเดททุก 45 วินาที (เพิ่มจาก 20)
                    return
            
            if self.mt5_connection.is_connected:  # ใช้ตัวแปรแทนการเรียกฟังก์ชัน
                self.update_account_info()
                self._last_account_update = time.time()
                
            if self.stop_update:
                return
                
            # 🚀 OPTIMIZED: อัพเดทข้อมูลพอร์ต (ลดความถี่มากขึ้น)
            if hasattr(self, '_last_portfolio_update'):
                if time.time() - self._last_portfolio_update < 60:  # อัพเดททุก 60 วินาที (เพิ่มจาก 30)
                    return
            else:
                self._last_portfolio_update = 0
                
            self.update_portfolio_info_light()
            self._last_portfolio_update = time.time()
            
            if self.stop_update:
                return
                
            # 🚀 OPTIMIZED: อัพเดท Positions (ลดความถี่มากขึ้น)  
            if hasattr(self, '_last_positions_update'):
                if time.time() - self._last_positions_update < 40:  # อัพเดททุก 40 วินาที (เพิ่มจาก 25)
                    return
            else:
                self._last_positions_update = 0
                
            self.update_positions_display_light()
            self._last_positions_update = time.time()
            
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
            
            
    def update_positions_display_light(self):
        """อัพเดทการแสดง Positions แบบเบา"""
        try:
            # อัพเดทเฉพาะเมื่อจำเป็น
            if not hasattr(self, 'positions_tree'):
                return
                
            # ดึงข้อมูล positions จาก trading system โดยตรง
            if self.trading_system and hasattr(self.trading_system, 'order_manager'):
                positions = self.trading_system.order_manager.active_positions
            else:
                positions = []
                
            current_count = len(self.positions_tree.get_children())
            
            # อัพเดทเฉพาะเมื่อจำนวน position เปลี่ยน
            if len(positions) != current_count:
                self.update_positions_display()
                # อัพเดทสถานะ Hedge ด้วย (ถ้า GUI พร้อมแล้ว)
                if hasattr(self, 'hedge_status_label'):
                    self.update_hedge_status()
                
        except Exception as e:
            logger.debug(f"Position display update error: {str(e)}")
            
            
            
            
            
            
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
            if not hasattr(self, 'account_labels'):
                return
                
            if self.mt5_connection and self.mt5_connection.is_connected:
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
            else:
                # แสดงข้อมูล default เมื่อไม่สามารถดึงข้อมูลได้
                self.account_labels['balance'].config(text="0.00")
                self.account_labels['equity'].config(text="0.00")
                self.account_labels['margin'].config(text="0.00")
                self.account_labels['margin_free'].config(text="0.00")
                self.account_labels['margin_level'].config(text="0.00%")
        except Exception as e:
            logger.debug(f"Account info update error: {str(e)}")
    
    
    def update_trading_status_data(self):
        """อัพเดทข้อมูลสถานะการเทรด"""
        try:
            if not hasattr(self, 'trading_status_labels'):
                return
                
            if self.trading_system and hasattr(self.trading_system, 'order_manager'):
                positions = self.trading_system.order_manager.active_positions
                
                # อัพเดทจำนวน positions
                self.trading_status_labels['active_positions'].config(text=str(len(positions)))
                
                if positions:
                    # คำนวณ Total P&L จาก positions จริง
                    total_pnl = 0
                    profitable_count = 0
                    total_profit = 0
                    total_loss = 0
                    
                    for pos in positions:
                        profit = getattr(pos, 'profit', 0)
                        total_pnl += profit
                        if profit > 0:
                            profitable_count += 1
                            total_profit += profit
                        else:
                            total_loss += abs(profit)
                    
                    # อัพเดท Total P&L
                    self.trading_status_labels['total_pnl'].config(
                        text=f"{total_pnl:.2f}",
                        fg='#00ff88' if total_pnl >= 0 else '#ff4444'
                    )
                    
                    # อัพเดท Daily P&L (ใช้ Total P&L เป็นฐาน)
                    self.trading_status_labels['daily_pnl'].config(
                        text=f"{total_pnl:.2f}",
                        fg='#00ff88' if total_pnl >= 0 else '#ff4444'
                    )
                    
                    # คำนวณ Win Rate
                    win_rate = (profitable_count / len(positions)) * 100 if positions else 0
                    self.trading_status_labels['win_rate'].config(
                        text=f"{win_rate:.1f}%",
                        fg='#00ff88' if win_rate >= 50 else '#ff4444'
                    )
                    
                    # คำนวณ Profit Factor
                    profit_factor = total_profit / total_loss if total_loss > 0 else (total_profit if total_profit > 0 else 0)
                    self.trading_status_labels['profit_factor'].config(
                        text=f"{profit_factor:.2f}",
                        fg='#00ff88' if profit_factor >= 1.0 else '#ff4444'
                    )
                else:
                    # ไม่มี positions
                    self.trading_status_labels['total_pnl'].config(text="0.00", fg='#cccccc')
                    self.trading_status_labels['daily_pnl'].config(text="0.00", fg='#cccccc')
                    self.trading_status_labels['win_rate'].config(text="0%", fg='#cccccc')
                    self.trading_status_labels['profit_factor'].config(text="0.00", fg='#cccccc')
            else:
                # ไม่มี trading system หรือ order manager
                self.trading_status_labels['active_positions'].config(text="0", fg='#cccccc')
                self.trading_status_labels['total_pnl'].config(text="0.00", fg='#cccccc')
                self.trading_status_labels['daily_pnl'].config(text="0.00", fg='#cccccc')
                self.trading_status_labels['win_rate'].config(text="0%", fg='#cccccc')
                self.trading_status_labels['profit_factor'].config(text="0.00", fg='#cccccc')
        except Exception as e:
            logger.debug(f"Trading status update error: {str(e)}")
    
    def update_7d_closer_status(self):
        """อัพเดทสถานะ 7D Smart Closer"""
        try:
            if (self.trading_system and 
                hasattr(self.trading_system, 'dynamic_7d_smart_closer') and 
                self.trading_system.dynamic_7d_smart_closer):
                
                positions = self.trading_system.order_manager.active_positions
                
                # อัพเดทจำนวน positions ที่วิเคราะห์
                self.closer_status_labels['positions_analyzed'].config(text=str(len(positions)))
                
                if positions:
                    # อัพเดทเวลาล่าสุด
                    current_time = datetime.now().strftime('%H:%M:%S')
                    self.closer_status_labels['last_analysis'].config(text=current_time)
                    
                    # ตรวจสอบสถานะ closer แบบง่าย (ไม่เรียก 7D analysis เพื่อลด load)
                    self.closer_status_labels['closer_status'].config(
                        text="🔄 MONITORING",
                        fg='#ffaa00'
                    )
                    
                    # แสดงสถานะพื้นฐาน
                    self.closer_status_labels['recommendation'].config(
                        text="MONITORING",
                        fg='#ffaa00'
                    )
                    self.closer_status_labels['closing_confidence'].config(
                        text="--",
                        fg='#ffaa00'
                    )
                else:
                    # ไม่มี positions
                    self.closer_status_labels['closer_status'].config(
                        text="💤 IDLE",
                        fg='#cccccc'
                    )
                    self.closer_status_labels['recommendation'].config(
                        text="NO POSITIONS",
                        fg='#cccccc'
                    )
                    self.closer_status_labels['closing_confidence'].config(
                        text="0%",
                        fg='#cccccc'
                    )
        except Exception as e:
            logger.debug(f"7D closer status update error: {str(e)}")
            
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
                if self.trading_system and hasattr(self.trading_system, 'order_manager'):
                    positions = self.trading_system.order_manager.active_positions
                else:
                    positions = []
            except Exception as e:
                logger.debug(f"ไม่สามารถดึงข้อมูล positions ได้: {str(e)}")
                return
                
            # ลบข้อมูลเก่า
            for item in self.positions_tree.get_children():
                self.positions_tree.delete(item)
                
            # เพิ่มข้อมูลใหม่
            if positions:
                for pos in positions:
                    try:
                        # คำนวณ Profit %
                        profit_pct = 0.0
                        if hasattr(pos, 'price_open') and pos.price_open != 0:
                            if hasattr(pos, 'price_current'):
                                if pos.type == 0:  # BUY
                                    profit_pct = ((pos.price_current - pos.price_open) / pos.price_open) * 100
                                else:  # SELL
                                    profit_pct = ((pos.price_open - pos.price_current) / pos.price_open) * 100
                        
                        # หาการจับคู่ของไม้นี้
                        hedge_info = self._get_hedge_info(getattr(pos, 'ticket', 'N/A'), positions)
                        
                        # เพิ่มข้อมูลใน Treeview
                        values = (
                            getattr(pos, 'ticket', 'N/A'),
                            getattr(pos, 'symbol', 'N/A'),
                            "BUY" if getattr(pos, 'type', 0) == 0 else "SELL",
                            f"{getattr(pos, 'volume', 0):.2f}",
                            f"{getattr(pos, 'price_open', 0):.5f}",
                            f"{getattr(pos, 'price_current', 0):.5f}",
                            f"{getattr(pos, 'profit', 0):.2f}",
                            f"{profit_pct:.2f}%",
                            f"{getattr(pos, 'swap', 0):.2f}",
                            getattr(pos, 'comment', ''),
                            hedge_info
                    )
                    
                        item = self.positions_tree.insert('', 'end', values=values)
                        
                        # เปลี่ยนสีตามกำไรขาดทุน
                        profit = getattr(pos, 'profit', 0)
                        if profit > 0:
                            self.positions_tree.set(item, 'Profit', f"+{profit:.2f}")
                        elif profit < 0:
                            self.positions_tree.set(item, 'Profit', f"{profit:.2f}")
                            
                    except Exception as pos_error:
                        logger.debug(f"Error processing position: {str(pos_error)}")
                        continue
            else:
                # ไม่มี positions - แสดงข้อความ
                self.positions_tree.insert('', 'end', values=(
                    'No positions', '', '', '', '', '', '', '', '', '', ''
                ))
                    
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการอัพเดท Positions: {str(e)}")
    
    def _analyze_hedge_pairs(self, positions):
        """วิเคราะห์การจับคู่ไม้"""
        try:
            if not positions or len(positions) < 2:
                return []
            
            hedge_pairs = []
            
            # หาการจับคู่แบบง่ายๆ
            for i, pos1 in enumerate(positions):
                for j, pos2 in enumerate(positions[i+1:], i+1):
                    profit1 = getattr(pos1, 'profit', 0)
                    profit2 = getattr(pos2, 'profit', 0)
                    total_profit = profit1 + profit2
                    
                    # ถ้าผลรวมเป็นบวก ให้จับคู่
                    if total_profit > 0.1:
                        hedge_pairs.append({
                            'position1': pos1,
                            'position2': pos2,
                            'total_profit': total_profit,
                            'tickets': [str(getattr(pos1, 'ticket', 'N/A')), str(getattr(pos2, 'ticket', 'N/A'))]
                        })
            
            return hedge_pairs
            
        except Exception as e:
            logger.error(f"Error analyzing hedge pairs: {e}")
            return []
    
    def _get_hedge_info(self, ticket, positions):
        """หาข้อมูลการจับคู่ Hedge ของไม้"""
        try:
            if not positions:
                return "No positions"
            
            # หาไม้ที่ตรงกับ ticket
            current_pos = None
            for pos in positions:
                if getattr(pos, 'ticket', 'N/A') == ticket:
                    current_pos = pos
                    break
            
            if not current_pos:
                return "Position not found"
            
            current_type = getattr(current_pos, 'type', 0)
            current_profit = getattr(current_pos, 'profit', 0)
            
            # หาไม้ตรงข้ามที่จับคู่ได้
            hedge_pairs = []
            
            for pos in positions:
                if pos == current_pos:
                    continue
                
                other_type = getattr(pos, 'type', 0)
                other_profit = getattr(pos, 'profit', 0)
                other_ticket = getattr(pos, 'ticket', 'N/A')
                
                # ตรวจสอบว่าเป็นไม้ตรงข้ามหรือไม่
                if current_type != other_type:
                    # จับคู่ Hedge (ไม่สนใจผลรวม)
                    if (current_type == 0 and current_profit < 0 and other_profit > 0) or \
                       (current_type == 1 and current_profit < 0 and other_profit > 0):
                        # Hedge Pair: ติดลบ + กำไร
                        total_profit = current_profit + other_profit
                        hedge_pairs.append({
                            'ticket': other_ticket,
                            'profit': other_profit,
                            'total_profit': total_profit,
                            'type': 'HEDGE'
                        })
                    elif (current_type == 0 and current_profit > 0 and other_profit < 0) or \
                         (current_type == 1 and current_profit > 0 and other_profit < 0):
                        # Hedge Pair: กำไร + ติดลบ
                        total_profit = current_profit + other_profit
                        hedge_pairs.append({
                            'ticket': other_ticket,
                            'profit': other_profit,
                            'total_profit': total_profit,
                            'type': 'HEDGE'
                        })
            
            # แสดงข้อมูลการจับคู่
            if hedge_pairs:
                # เรียงตามผลรวมกำไร (มากสุดก่อน)
                hedge_pairs.sort(key=lambda x: x['total_profit'], reverse=True)
                
                best_pair = hedge_pairs[0]
                pair_ticket = best_pair['ticket']
                total_profit = best_pair['total_profit']
                
                if total_profit >= 0.1:
                    return f"🔗 Hedge: {pair_ticket} (+${total_profit:.2f})"
                elif total_profit >= -0.1:
                    return f"🔗 Hedge: {pair_ticket} (${total_profit:.2f})"
                else:
                    return f"🔗 Hedge: {pair_ticket} (${total_profit:.2f})"
            else:
                # หาไม้อื่นๆ ที่กำไรและไม่มี Hedge
                additional_positions = []
                for pos in positions:
                    if pos == current_pos:
                        continue
                    
                    other_profit = getattr(pos, 'profit', 0)
                    other_ticket = getattr(pos, 'ticket', 'N/A')
                    
                    if other_profit > 0:
                        # ตรวจสอบว่าไม้นี้ไม่มี Hedge กับคู่อื่น
                        has_hedge = False
                        for other_pos in positions:
                            if other_pos == pos or other_pos == current_pos:
                                continue
                            
                            other_type = getattr(other_pos, 'type', 0)
                            other_profit2 = getattr(other_pos, 'profit', 0)
                            
                            if getattr(pos, 'type', 0) != other_type and other_profit2 > 0:
                                has_hedge = True
                                break
                        
                        if not has_hedge:
                            additional_positions.append({
                                'ticket': other_ticket,
                                'profit': other_profit
                            })
                
                if additional_positions:
                    # แสดงไม้อื่นๆ ที่กำไร
                    additional_tickets = [str(p['ticket']) for p in additional_positions[:2]]  # แสดงแค่ 2 ตัว
                    return f"➕ Additional: {', '.join(additional_tickets)}"
                else:
                    return "💤 No hedge pair"
            
        except Exception as e:
            logger.error(f"Error getting hedge info: {e}")
            return "Error"
    
    def analyze_hedge_pairs(self):
        """วิเคราะห์การจับคู่ไม้"""
        try:
            if not self.trading_system or not hasattr(self.trading_system, 'order_manager'):
                messagebox.showwarning("Warning", "Trading system not available")
                return
            
            positions = self.trading_system.order_manager.active_positions
            if not positions:
                messagebox.showinfo("Info", "No positions to analyze")
                return
            
            # วิเคราะห์การจับคู่
            hedge_pairs = self._analyze_hedge_pairs(positions)
            
            if hedge_pairs:
                message = f"Found {len(hedge_pairs)} hedge pairs:\n\n"
                for i, pair in enumerate(hedge_pairs[:5]):  # แสดงแค่ 5 คู่แรก
                    ticket1 = pair['tickets'][0]
                    ticket2 = pair['tickets'][1]
                    profit = pair['total_profit']
                    message += f"Pair {i+1}: {ticket1} + {ticket2} = +${profit:.2f}\n"
                
                if len(hedge_pairs) > 5:
                    message += f"\n... and {len(hedge_pairs) - 5} more pairs"
                
                messagebox.showinfo("Hedge Analysis", message)
                self.hedge_status_label.config(text=f"✅ Found {len(hedge_pairs)} pairs")
            else:
                messagebox.showinfo("Hedge Analysis", "No profitable hedge pairs found")
                self.hedge_status_label.config(text="❌ No pairs found")
                
        except Exception as e:
            logger.error(f"Error in hedge analysis: {e}")
            messagebox.showerror("Error", f"Error analyzing hedge pairs: {e}")
    
    def refresh_hedge_pairs(self):
        """รีเฟรชการจับคู่ไม้"""
        try:
            self.update_positions_display()
            if hasattr(self, 'hedge_status_label'):
                self.hedge_status_label.config(text="🔄 Refreshed", fg='#00ff88')
        except Exception as e:
            logger.error(f"Error refreshing hedge pairs: {e}")
            if hasattr(self, 'hedge_status_label'):
                self.hedge_status_label.config(text="❌ Error", fg='#ff4444')
    
    def update_hedge_status(self):
        """อัพเดทสถานะการจับคู่ Hedge"""
        try:
            # ตรวจสอบว่า hedge_status_label ถูกสร้างแล้วหรือไม่
            if not hasattr(self, 'hedge_status_label'):
                logger.debug("hedge_status_label not yet created, skipping update")
                return
                
            if not self.trading_system or not hasattr(self.trading_system, 'order_manager'):
                self.hedge_status_label.config(text="❌ No trading system", fg='#ff4444')
                return
            
            positions = self.trading_system.order_manager.active_positions
            if not positions:
                self.hedge_status_label.config(text="💤 No positions", fg='#cccccc')
                return
            
            # วิเคราะห์การจับคู่ Hedge
            hedge_pairs = self._analyze_hedge_pairs(positions)
            
            if hedge_pairs:
                # นับจำนวน Hedge Pairs
                hedge_count = len(hedge_pairs)
                total_profit = sum(pair['total_profit'] for pair in hedge_pairs)
                
                # แสดงสถานะ
                if total_profit >= 0.1:
                    status_text = f"✅ {hedge_count} Hedge Pairs (+${total_profit:.2f})"
                    status_color = '#00ff88'
                elif total_profit >= -0.1:
                    status_text = f"⚠️ {hedge_count} Hedge Pairs (${total_profit:.2f})"
                    status_color = '#ffaa00'
                else:
                    status_text = f"❌ {hedge_count} Hedge Pairs (${total_profit:.2f})"
                    status_color = '#ff4444'
                
                self.hedge_status_label.config(text=status_text, fg=status_color)
                
                # แสดงรายละเอียดใน log
                logger.info(f"🔍 Hedge Status: {hedge_count} pairs, Total P&L: ${total_profit:.2f}")
                for i, pair in enumerate(hedge_pairs[:3]):  # แสดงแค่ 3 คู่แรก
                    ticket1, ticket2 = pair['tickets']
                    profit = pair['total_profit']
                    logger.info(f"   Pair {i+1}: {ticket1} + {ticket2} = ${profit:.2f}")
                
            else:
                self.hedge_status_label.config(text="💤 No hedge pairs found", fg='#cccccc')
                logger.info("🔍 No hedge pairs found")
            
        except Exception as e:
            logger.error(f"Error updating hedge status: {e}")
            self.hedge_status_label.config(text="❌ Error", fg='#ff4444')
            
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
                
            # เริ่มการเทรดผ่าน TradingSystem (ใน background thread)
            def start_trading_async():
                try:
                    success = self.trading_system.start_trading()
                    if success:
                        # อัพเดท GUI ใน main thread
                        self.root.after(0, lambda: self.update_trading_status(True))
                        logger.info("เริ่มการเทรดจาก GUI สำเร็จ")
                except Exception as e:
                    logger.error(f"เกิดข้อผิดพลาดในการเริ่มเทรด: {str(e)}")
                    self.root.after(0, lambda: messagebox.showerror("Error", f"เกิดข้อผิดพลาด: {str(e)}"))
            
            # รัน start_trading ใน background thread
            threading.Thread(target=start_trading_async, daemon=True).start()
            
            # อัพเดท GUI ทันที (แสดงสถานะ "Starting...")
            self.trading_status.config(text="Starting...", fg='orange')
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการเริ่มเทรด: {str(e)}")
            messagebox.showerror("Error", f"เกิดข้อผิดพลาด: {str(e)}")
            
    def update_trading_status(self, is_running):
        """อัพเดทสถานะการเทรด"""
        try:
            if is_running:
                self.is_trading = True
                self.trading_status.config(text="Running", fg='green')
            else:
                self.is_trading = False
                self.trading_status.config(text="Stopped", fg='red')
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการอัพเดทสถานะ: {str(e)}")
    
    def stop_trading(self):
        """หยุดการเทรด"""
        try:
            # หยุดการเทรดผ่าน TradingSystem (ใน background thread)
            def stop_trading_async():
                try:
                    self.trading_system.stop_trading()
                    # อัพเดท GUI ใน main thread
                    self.root.after(0, lambda: self.update_trading_status(False))
                    logger.info("หยุดการเทรดจาก GUI สำเร็จ")
                except Exception as e:
                    logger.error(f"เกิดข้อผิดพลาดในการหยุดเทรด: {str(e)}")
                    self.root.after(0, lambda: messagebox.showerror("Error", f"เกิดข้อผิดพลาด: {str(e)}"))
            
            # รัน stop_trading ใน background thread
            threading.Thread(target=stop_trading_async, daemon=True).start()
            
            # อัพเดท GUI ทันที (แสดงสถานะ "Stopping...")
            self.trading_status.config(text="Stopping...", fg='orange')
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการหยุดเทรด: {str(e)}")
            messagebox.showerror("Error", f"เกิดข้อผิดพลาด: {str(e)}")
            
    def close_all_positions(self):
        """ปิด Position ทั้งหมด - ⚠️ อันตราย: อาจปิดติดลบ"""
        try:
            if messagebox.askyesno("⚠️ อันตราย!", 
                                 "การปิดทั้งหมดอาจทำให้ขาดทุน!\n"
                                 "แนะนำให้ใช้ Smart Profit Taking แทน\n\n"
                                 "ยืนยันที่จะปิดทั้งหมด?"):
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

    def alert(self, message, level='info'):
        """แสดงการแจ้งเตือน"""
        try:
            if level == 'info':
                messagebox.showinfo("Info", message)
            elif level == 'warning':
                messagebox.showwarning("Warning", message)
            elif level == 'error':
                messagebox.showerror("Error", message)
            else:
                messagebox.showinfo("Info", message)
        except Exception as e:
            logger.error(f"Error showing alert: {e}")
