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
        self.root.geometry("1600x1000")
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
            main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
            
            # สร้าง top frame สำหรับการเชื่อมต่อและควบคุม
            self.create_control_panel(main_frame)
            
            # สร้าง market status panel
            self.create_market_status_panel(main_frame)
            
            # สร้าง middle frame สำหรับข้อมูลหลัก
            self.create_main_info_panel(main_frame)
            
            # สร้าง 7D analysis panel
            self.create_7d_analysis_panel(main_frame)
            
            # สร้าง bottom frame สำหรับ positions และ log
            self.create_bottom_panel(main_frame)
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการสร้าง widgets: {str(e)}")
            
    def create_control_panel(self, parent):
        """สร้างแผงควบคุม"""
        control_frame = tk.Frame(parent, bg='#1a1a1a')
        control_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Connection Status
        conn_frame = tk.Frame(control_frame, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        conn_frame.pack(side=tk.LEFT, padx=(0, 15), pady=5, fill=tk.Y)
        
        tk.Label(conn_frame, text="🔗 MT5 Connection", bg='#2d2d2d', fg='#00ff88', 
                font=('Segoe UI', 11, 'bold')).pack(pady=8)
        
        self.connection_status = tk.Label(conn_frame, text="Disconnected", 
                                        bg='#2d2d2d', fg='#ff4444', font=('Segoe UI', 10, 'bold'))
        self.connection_status.pack(pady=3)
        
        self.connect_btn = tk.Button(conn_frame, text="Connect MT5", 
                                   command=self.connect_mt5, bg='#4a4a4a', fg='white',
                                   font=('Segoe UI', 9), relief=tk.RAISED, bd=2)
        self.connect_btn.pack(pady=8)
        
        # Trading Controls
        trading_frame = tk.Frame(control_frame, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        trading_frame.pack(side=tk.LEFT, padx=(0, 15), pady=5, fill=tk.Y)
        
        tk.Label(trading_frame, text="🎯 Trading Control", bg='#2d2d2d', fg='#00ff88', 
                font=('Segoe UI', 11, 'bold')).pack(pady=8)
        
        self.trading_status = tk.Label(trading_frame, text="Stopped", 
                                     bg='#2d2d2d', fg='#ff4444', font=('Segoe UI', 10, 'bold'))
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
        emergency_frame.pack(side=tk.LEFT, padx=(0, 15), pady=5, fill=tk.Y)
        
        tk.Label(emergency_frame, text="🚨 Emergency", bg='#2d2d2d', fg='#ff4444', 
                font=('Segoe UI', 11, 'bold')).pack(pady=8)
        
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
                font=('Segoe UI', 12, 'bold')).pack(pady=8)
        
        # Market status info
        status_info_frame = tk.Frame(status_card, bg='#2d2d2d')
        status_info_frame.pack(fill=tk.X, padx=15, pady=5)
        
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
                    font=('Segoe UI', 9)).pack(anchor='w')
            
            self.market_status_labels[key] = tk.Label(field_frame, text=default, 
                                                    bg='#2d2d2d', fg='#00ff88', 
                                                    font=('Segoe UI', 9, 'bold'))
            self.market_status_labels[key].pack(anchor='w')
        
        # Configure grid weights
        for i in range(3):
            status_info_frame.columnconfigure(i, weight=1)
        
    def create_main_info_panel(self, parent):
        """สร้างแผงข้อมูลหลัก"""
        info_frame = tk.Frame(parent, bg='#1a1a1a')
        info_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Account Info
        self.create_account_info_card(info_frame)
        
        # Portfolio Balance
        self.create_portfolio_balance_card(info_frame)
        
        # Performance Metrics
        self.create_performance_card(info_frame)
        
        # Risk Metrics
        self.create_risk_card(info_frame)
    
    def create_7d_analysis_panel(self, parent):
        """สร้างแผงวิเคราะห์ 7D"""
        analysis_frame = tk.Frame(parent, bg='#1a1a1a')
        analysis_frame.pack(fill=tk.X, pady=(0, 15))
        
        # 7D Analysis Card
        analysis_card = tk.Frame(analysis_frame, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        analysis_card.pack(fill=tk.X, pady=5)
        
        tk.Label(analysis_card, text="🧠 7D Smart Analysis", bg='#2d2d2d', fg='#00ff88', 
                font=('Segoe UI', 12, 'bold')).pack(pady=8)
        
        # 7D Analysis info
        analysis_info_frame = tk.Frame(analysis_card, bg='#2d2d2d')
        analysis_info_frame.pack(fill=tk.X, padx=15, pady=5)
        
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
                    font=('Segoe UI', 9)).pack(anchor='w')
            
            self.analysis_labels[key] = tk.Label(field_frame, text=default, 
                                               bg='#2d2d2d', fg='#00ff88', 
                                               font=('Segoe UI', 9, 'bold'))
            self.analysis_labels[key].pack(anchor='w')
        
        # Configure grid weights
        for i in range(3):
            analysis_info_frame.columnconfigure(i, weight=1)
        
    def create_account_info_card(self, parent):
        """สร้างการ์ดข้อมูลบัญชี"""
        card = tk.Frame(parent, bg='#2d2d2d', relief=tk.RAISED, bd=2)
        card.pack(side=tk.LEFT, padx=(0, 15), pady=5, fill=tk.BOTH, expand=True)
        
        tk.Label(card, text="💰 Account Information", bg='#2d2d2d', fg='#00ff88', 
                font=('Segoe UI', 12, 'bold')).pack(pady=8)
        
        # Account details
        details_frame = tk.Frame(card, bg='#2d2d2d')
        details_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=8)
        
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
                    font=('Segoe UI', 9)).grid(row=i, column=0, sticky='w', pady=3)
            
            self.account_labels[key] = tk.Label(details_frame, text="0.00", bg='#2d2d2d', 
                                              fg='#00ff88', font=('Segoe UI', 10, 'bold'))
            self.account_labels[key].grid(row=i, column=1, sticky='e', pady=3)
            
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
        
        # แท็บ Recovery Systems
        self.create_recovery_tab(notebook)
        
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
        
    def create_recovery_tab(self, notebook):
        """สร้างแท็บ Recovery Systems Dashboard"""
        recovery_frame = tk.Frame(notebook, bg='#2b2b2b')
        notebook.add(recovery_frame, text="Recovery Systems")
        
        # Main container
        main_container = tk.Frame(recovery_frame, bg='#2b2b2b')
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Top section - System Status
        self.create_system_status_section(main_container)
        
        # Middle section - Active Recovery Groups
        self.create_recovery_groups_section(main_container)
        
        # Bottom section - Recovery Candidates
        self.create_recovery_candidates_section(main_container)
        
    def create_system_status_section(self, parent):
        """สร้างส่วนแสดงสถานะระบบ"""
        status_frame = tk.LabelFrame(parent, text="System Status", bg='#2b2b2b', fg='white', font=('Arial', 10, 'bold'))
        status_frame.pack(fill=tk.X, pady=(0, 5))
        
        # Grid layout for status items
        status_grid = tk.Frame(status_frame, bg='#2b2b2b')
        status_grid.pack(fill=tk.X, padx=5, pady=5)
        
        # Smart Recovery Status
        tk.Label(status_grid, text="Smart Recovery:", bg='#2b2b2b', fg='white', font=('Arial', 9)).grid(row=0, column=0, sticky='w', padx=(0, 10))
        self.smart_recovery_status = tk.Label(status_grid, text="Checking...", bg='#2b2b2b', fg='yellow', font=('Arial', 9, 'bold'))
        self.smart_recovery_status.grid(row=0, column=1, sticky='w')
        
        # Advanced Recovery Status
        tk.Label(status_grid, text="Advanced Recovery:", bg='#2b2b2b', fg='white', font=('Arial', 9)).grid(row=0, column=2, sticky='w', padx=(20, 10))
        self.advanced_recovery_status = tk.Label(status_grid, text="Checking...", bg='#2b2b2b', fg='yellow', font=('Arial', 9, 'bold'))
        self.advanced_recovery_status.grid(row=0, column=3, sticky='w')
        
        # Zone Analysis Status
        tk.Label(status_grid, text="Zone Analysis:", bg='#2b2b2b', fg='white', font=('Arial', 9)).grid(row=1, column=0, sticky='w', padx=(0, 10))
        self.zone_analysis_status = tk.Label(status_grid, text="Checking...", bg='#2b2b2b', fg='yellow', font=('Arial', 9, 'bold'))
        self.zone_analysis_status.grid(row=1, column=1, sticky='w')
        
        # Portfolio Balance Status
        tk.Label(status_grid, text="Portfolio Balance:", bg='#2b2b2b', fg='white', font=('Arial', 9)).grid(row=1, column=2, sticky='w', padx=(20, 10))
        self.portfolio_balance_status = tk.Label(status_grid, text="Checking...", bg='#2b2b2b', fg='yellow', font=('Arial', 9, 'bold'))
        self.portfolio_balance_status.grid(row=1, column=3, sticky='w')
        
        # Next Action
        tk.Label(status_grid, text="Next Action:", bg='#2b2b2b', fg='white', font=('Arial', 10, 'bold')).grid(row=2, column=0, sticky='w', padx=(0, 10), pady=(10, 0))
        self.next_action_label = tk.Label(status_grid, text="Analyzing...", bg='#2b2b2b', fg='cyan', font=('Arial', 10, 'bold'), wraplength=600)
        self.next_action_label.grid(row=2, column=1, columnspan=3, sticky='w', pady=(10, 0))
        
    def create_recovery_groups_section(self, parent):
        """สร้างส่วนแสดง Active Recovery Groups"""
        groups_frame = tk.LabelFrame(parent, text="Active Recovery Groups", bg='#2b2b2b', fg='white', font=('Arial', 10, 'bold'))
        groups_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 5))
        
        # Treeview for recovery groups
        columns = ('Group ID', 'Type', 'Phase', 'Age', 'Positions', 'Net P&L', 'Status')
        self.recovery_groups_tree = ttk.Treeview(groups_frame, columns=columns, show='headings', height=8)
        
        # Configure columns
        self.recovery_groups_tree.heading('Group ID', text='Group ID')
        self.recovery_groups_tree.heading('Type', text='Type')
        self.recovery_groups_tree.heading('Phase', text='Phase')
        self.recovery_groups_tree.heading('Age', text='Age (min)')
        self.recovery_groups_tree.heading('Positions', text='Positions')
        self.recovery_groups_tree.heading('Net P&L', text='Net P&L')
        self.recovery_groups_tree.heading('Status', text='Status')
        
        # Configure column widths
        self.recovery_groups_tree.column('Group ID', width=120)
        self.recovery_groups_tree.column('Type', width=120)
        self.recovery_groups_tree.column('Phase', width=120)
        self.recovery_groups_tree.column('Age', width=80)
        self.recovery_groups_tree.column('Positions', width=80)
        self.recovery_groups_tree.column('Net P&L', width=100)
        self.recovery_groups_tree.column('Status', width=200)
        
        # Scrollbar for recovery groups
        groups_scrollbar = ttk.Scrollbar(groups_frame, orient=tk.VERTICAL, command=self.recovery_groups_tree.yview)
        self.recovery_groups_tree.configure(yscrollcommand=groups_scrollbar.set)
        
        # Pack recovery groups treeview and scrollbar
        self.recovery_groups_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        groups_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
    def create_recovery_candidates_section(self, parent):
        """สร้างส่วนแสดง Recovery Candidates"""
        candidates_frame = tk.LabelFrame(parent, text="Recovery Candidates (Ready to Close)", bg='#2b2b2b', fg='white', font=('Arial', 10, 'bold'))
        candidates_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
        
        # Treeview for recovery candidates
        columns = ('Profit Ticket', 'Profit', 'Loss Ticket', 'Loss', 'Net Profit', 'Score', 'Reason')
        self.recovery_candidates_tree = ttk.Treeview(candidates_frame, columns=columns, show='headings', height=6)
        
        # Configure columns
        self.recovery_candidates_tree.heading('Profit Ticket', text='Profit Ticket')
        self.recovery_candidates_tree.heading('Profit', text='Profit')
        self.recovery_candidates_tree.heading('Loss Ticket', text='Loss Ticket')
        self.recovery_candidates_tree.heading('Loss', text='Loss')
        self.recovery_candidates_tree.heading('Net Profit', text='Net Profit')
        self.recovery_candidates_tree.heading('Score', text='Score')
        self.recovery_candidates_tree.heading('Reason', text='Reason')
        
        # Configure column widths
        self.recovery_candidates_tree.column('Profit Ticket', width=100)
        self.recovery_candidates_tree.column('Profit', width=80)
        self.recovery_candidates_tree.column('Loss Ticket', width=100)
        self.recovery_candidates_tree.column('Loss', width=80)
        self.recovery_candidates_tree.column('Net Profit', width=80)
        self.recovery_candidates_tree.column('Score', width=60)
        self.recovery_candidates_tree.column('Reason', width=200)
        
        # Scrollbar for recovery candidates
        candidates_scrollbar = ttk.Scrollbar(candidates_frame, orient=tk.VERTICAL, command=self.recovery_candidates_tree.yview)
        self.recovery_candidates_tree.configure(yscrollcommand=candidates_scrollbar.set)
        
        # Pack recovery candidates treeview and scrollbar
        self.recovery_candidates_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        candidates_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
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
        style.configure("Treeview", background='#1a1a1a', foreground='white', 
                       fieldbackground='#1a1a1a', font=('Segoe UI', 9))
        style.configure("Treeview.Heading", background='#2d2d2d', foreground='#00ff88',
                       font=('Segoe UI', 9, 'bold'))
        
        # กำหนดสีสำหรับ Progressbar
        style.configure("TProgressbar", background='#00ff88', troughcolor='#2d2d2d')
        
        # กำหนดสีสำหรับ Notebook tabs
        style.configure("TNotebook", background='#1a1a1a')
        style.configure("TNotebook.Tab", background='#2d2d2d', foreground='white',
                       padding=[20, 10], font=('Segoe UI', 9))
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
        """Loop อัพเดทแบบเบา"""
        while not self.stop_update:
            try:
                if not self.stop_update:
                    self.root.after_idle(self.update_connection_status_light)
                    self.root.after_idle(self.update_market_status)
                    self.root.after_idle(self.update_7d_analysis)
                time.sleep(5)  # อัพเดททุก 5 วินาที
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
            
            # อัพเดท Recovery Systems Dashboard
            self.update_recovery_systems_display()
            
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
            
    def update_recovery_systems_display(self):
        """อัพเดท Recovery Systems Dashboard"""
        try:
            if not hasattr(self, 'smart_recovery_status'):
                return  # ยังไม่ได้สร้าง recovery tab
                
            # อัพเดทสถานะระบบต่างๆ
            self.update_system_status()
            self.update_recovery_groups()
            self.update_recovery_candidates()
            
        except Exception as e:
            pass  # ไม่ log error เพื่อไม่ให้รบกวน
            
    def update_system_status(self):
        """อัพเดทสถานะของระบบต่างๆ"""
        try:
            # ซิงค์ positions ก่อน
            self.portfolio_manager.order_manager.sync_positions_from_mt5()
            positions = self.portfolio_manager.order_manager.active_positions
            
            if not positions:
                self.smart_recovery_status.config(text="NO POSITIONS", fg='gray')
                self.advanced_recovery_status.config(text="IDLE", fg='gray')
                self.zone_analysis_status.config(text="IDLE", fg='gray')
                self.portfolio_balance_status.config(text="EMPTY", fg='gray')
                self.next_action_label.config(text="Waiting for positions...")
                return
                
            # ดึงข้อมูล account จริง
            account_info = self.mt5_connection.get_account_info()
            if account_info:
                current_balance = account_info['balance']
                current_equity = account_info['equity']
            else:
                current_balance = 2500  # fallback
                current_equity = 2500
            
            # Smart Recovery Status
            smart_recovery_result = self.portfolio_manager.smart_recovery.should_trigger_recovery(
                positions, current_balance, current_equity
            )
            
            if smart_recovery_result:
                self.smart_recovery_status.config(text="READY", fg='green')
            else:
                self.smart_recovery_status.config(text="WAITING", fg='orange')
                
            # Advanced Recovery Status  
            if hasattr(self.portfolio_manager, 'advanced_recovery'):
                active_groups = len(self.portfolio_manager.advanced_recovery.active_recoveries)
                if active_groups > 0:
                    self.advanced_recovery_status.config(text=f"ACTIVE ({active_groups})", fg='green')
                else:
                    self.advanced_recovery_status.config(text="MONITORING", fg='orange')
            
            # Zone Analysis Status
            if len(positions) > 5:
                self.zone_analysis_status.config(text="ANALYZING", fg='cyan')
            else:
                self.zone_analysis_status.config(text="IDLE", fg='gray')
                
            # Portfolio Balance Status
            buy_count = len([p for p in positions if p.type == 0])
            sell_count = len([p for p in positions if p.type == 1])
            total = len(positions)
            
            if total > 0:
                buy_pct = (buy_count / total) * 100
                if 40 <= buy_pct <= 60:
                    self.portfolio_balance_status.config(text="BALANCED", fg='green')
                elif buy_pct > 70 or buy_pct < 30:
                    self.portfolio_balance_status.config(text="IMBALANCED", fg='red')
                else:
                    self.portfolio_balance_status.config(text="MODERATE", fg='yellow')
            
            # Next Action
            next_action = self.determine_next_action(positions)
            self.next_action_label.config(text=next_action)
            
        except Exception as e:
            logger.debug(f"Error in update_system_status: {e}")
            # ตั้งค่าเป็น error state
            self.smart_recovery_status.config(text="ERROR", fg='red')
            self.advanced_recovery_status.config(text="ERROR", fg='red')
            self.zone_analysis_status.config(text="ERROR", fg='red')
            self.portfolio_balance_status.config(text="ERROR", fg='red')
            self.next_action_label.config(text=f"Error: {str(e)[:50]}...")
            
    def determine_next_action(self, positions):
        """กำหนดการกระทำถัดไป"""
        try:
            if not positions:
                return "Waiting for positions..."
                
            # ตรวจสอบ Smart Recovery
            account_info = self.mt5_connection.get_account_info()
            if account_info:
                current_balance = account_info['balance']
                current_equity = account_info['equity']
            else:
                current_balance = 2500
                current_equity = 2500
                
            smart_ready = self.portfolio_manager.smart_recovery.should_trigger_recovery(
                positions, current_balance, current_equity
            )
            
            if smart_ready:
                profitable = [p for p in positions if p.profit > 0]
                losing = [p for p in positions if p.profit < 0]
                if profitable and losing:
                    return f"🎯 Ready for Smart Recovery: {len(profitable)} profit + {len(losing)} loss positions"
            
            # ตรวจสอบ Portfolio Balance
            buy_count = len([p for p in positions if p.type == 0])
            sell_count = len([p for p in positions if p.type == 1])
            total = len(positions)
            
            if total > 0:
                buy_pct = (buy_count / total) * 100
                if buy_pct > 70:
                    return f"📊 Portfolio imbalanced: {buy_pct:.1f}% BUY - Need more SELL positions"
                elif buy_pct < 30:
                    return f"📊 Portfolio imbalanced: {buy_pct:.1f}% BUY - Need more BUY positions"
            
            # ตรวจสอบ Advanced Recovery
            if hasattr(self.portfolio_manager, 'advanced_recovery'):
                active_groups = len(self.portfolio_manager.advanced_recovery.active_recoveries)
                if active_groups > 0:
                    return f"🚀 Advanced Recovery active: {active_groups} groups in progress"
            
            return "💡 Monitoring market conditions..."
            
        except Exception as e:
            return "Analyzing..."
            
    def update_recovery_groups(self):
        """อัพเดท Active Recovery Groups"""
        try:
            if not hasattr(self, 'recovery_groups_tree'):
                return
                
            # ล้างข้อมูลเก่า
            for item in self.recovery_groups_tree.get_children():
                self.recovery_groups_tree.delete(item)
            
            # เพิ่มข้อมูล Advanced Recovery Groups
            if hasattr(self.portfolio_manager, 'advanced_recovery'):
                for group_id, group in self.portfolio_manager.advanced_recovery.active_recoveries.items():
                    age_minutes = (datetime.now() - group.created_time).total_seconds() / 60
                    
                    # นับ positions ใน group
                    positions_count = 0
                    net_pnl = 0.0
                    
                    if hasattr(group, 'old_position') and group.old_position:
                        positions_count += 1
                        net_pnl += group.old_position.profit
                    if hasattr(group, 'new_position') and group.new_position:
                        positions_count += 1
                        net_pnl += group.new_position.profit
                    if hasattr(group, 'target_recovery') and group.target_recovery:
                        positions_count += 1
                        net_pnl += group.target_recovery.profit
                    
                    status = f"{group.phase.name}" if hasattr(group, 'phase') else "UNKNOWN"
                    
                    self.recovery_groups_tree.insert('', 'end', values=(
                        group_id[:12] + "...",  # ย่อ ID
                        "Triple Recovery",
                        status,
                        f"{age_minutes:.1f}",
                        str(positions_count),
                        f"${net_pnl:.2f}",
                        f"Waiting for phase completion"
                    ))
                    
        except Exception as e:
            pass
            
    def update_recovery_candidates(self):
        """อัพเดท Recovery Candidates"""
        try:
            if not hasattr(self, 'recovery_candidates_tree'):
                return
                
            # ล้างข้อมูลเก่า
            for item in self.recovery_candidates_tree.get_children():
                self.recovery_candidates_tree.delete(item)
            
            positions = self.portfolio_manager.order_manager.active_positions
            if not positions:
                return
                
            # หา Recovery Candidates จาก Smart Recovery
            # ดึงราคาปัจจุบันจาก MT5
            try:
                import MetaTrader5 as mt5
                symbol_info = mt5.symbol_info_tick("XAUUSD")
                current_price = symbol_info.bid if symbol_info else 2540.0
            except:
                current_price = 2540.0  # fallback price
            
            # ดึง account balance จริง
            account_info = self.mt5_connection.get_account_info()
            if account_info:
                current_balance = account_info['balance']
            else:
                current_balance = 2500  # fallback
                
            candidates = self.portfolio_manager.smart_recovery.analyze_recovery_opportunities(
                positions, current_balance, current_price
            )
            
            # แสดง top 10 candidates
            for i, candidate in enumerate(candidates[:10]):
                self.recovery_candidates_tree.insert('', 'end', values=(
                    str(candidate.profit_position.ticket),
                    f"${candidate.profit_position.profit:.2f}",
                    str(candidate.losing_position.ticket),
                    f"${candidate.losing_position.profit:.2f}",
                    f"${candidate.net_profit:.2f}",
                    f"{candidate.recovery_score:.1f}",
                    candidate.reason[:30] + "..." if len(candidate.reason) > 30 else candidate.reason
                ))
                
        except Exception as e:
            pass
            
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
    
    def update_market_status(self):
        """อัพเดทสถานะตลาด"""
        try:
            current_time = time.time()
            if current_time - self._last_market_status_update < 30:  # อัพเดททุก 30 วินาที
                return
            
            self._last_market_status_update = current_time
            
            if self.mt5_connection and self.mt5_connection.is_connected:
                market_status = self.mt5_connection.get_market_status("XAUUSD")
                
                # อัพเดท market status labels
                if market_status:
                    is_open = market_status.get('is_market_open', False)
                    self.market_status_labels['status'].config(
                        text="🟢 OPEN" if is_open else "🔴 CLOSED",
                        fg='#00ff88' if is_open else '#ff4444'
                    )
                    
                    self.market_status_labels['current_time'].config(
                        text=market_status.get('current_time', '00:00:00')
                    )
                    
                    active_sessions = market_status.get('active_sessions', [])
                    if active_sessions:
                        session_names = [s['name'].upper() for s in active_sessions]
                        self.market_status_labels['active_sessions'].config(
                            text=f"{len(active_sessions)} Sessions: {', '.join(session_names)}"
                        )
                    else:
                        self.market_status_labels['active_sessions'].config(text="None")
                    
                    next_session = market_status.get('next_session')
                    if next_session:
                        self.market_status_labels['next_session'].config(
                            text=f"{next_session['name'].upper()} in {next_session['time_to_open']:.1f}h"
                        )
                    else:
                        self.market_status_labels['next_session'].config(text="Unknown")
                    
                    london_ny_overlap = market_status.get('london_ny_overlap', False)
                    self.market_status_labels['london_ny_overlap'].config(
                        text="✅ ACTIVE" if london_ny_overlap else "❌ INACTIVE",
                        fg='#00ff88' if london_ny_overlap else '#ff4444'
                    )
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการอัพเดทสถานะตลาด: {str(e)}")
    
    def update_7d_analysis(self):
        """อัพเดทการวิเคราะห์ 7D"""
        try:
            current_time = time.time()
            if current_time - self._last_7d_analysis_update < 10:  # อัพเดททุก 10 วินาที
                return
            
            self._last_7d_analysis_update = current_time
            
            if (self.trading_system and 
                hasattr(self.trading_system, 'dynamic_7d_smart_closer') and 
                self.trading_system.dynamic_7d_smart_closer):
                
                # ตรวจสอบ positions
                positions = self.trading_system.order_manager.active_positions
                self.analysis_labels['active_positions'].config(text=str(len(positions)))
                
                if positions:
                    # วิเคราะห์ portfolio health
                    account_info = self.mt5_connection.get_account_info() or {}
                    market_conditions = {
                        'current_price': 0,  # จะได้จาก candle data
                        'volatility': 'medium',
                        'trend': 'neutral'
                    }
                    
                    # เรียกใช้ 7D analysis
                    closing_result = self.trading_system.dynamic_7d_smart_closer.find_optimal_closing(
                        positions=positions,
                        account_info=account_info,
                        market_conditions=market_conditions
                    )
                    
                    if closing_result:
                        # อัพเดท closing recommendation
                        if closing_result.should_close:
                            self.analysis_labels['closing_recommendation'].config(
                                text="🚀 CLOSE",
                                fg='#00ff88'
                            )
                            self.analysis_labels['closing_confidence'].config(
                                text=f"{closing_result.confidence_score:.1f}%",
                                fg='#00ff88'
                            )
                        else:
                            self.analysis_labels['closing_recommendation'].config(
                                text="💤 HOLD",
                                fg='#ffaa00'
                            )
                            self.analysis_labels['closing_confidence'].config(
                                text="0%",
                                fg='#ffaa00'
                            )
                        
                        # อัพเดท portfolio health
                        portfolio_health = getattr(closing_result, 'portfolio_health', None)
                        if portfolio_health:
                            health_score = getattr(portfolio_health, 'health_score', 0)
                            if health_score >= 80:
                                health_text = "🟢 EXCELLENT"
                                health_color = '#00ff88'
                            elif health_score >= 60:
                                health_text = "🟡 GOOD"
                                health_color = '#ffaa00'
                            elif health_score >= 40:
                                health_text = "🟠 FAIR"
                                health_color = '#ff8800'
                            else:
                                health_text = "🔴 POOR"
                                health_color = '#ff4444'
                            
                            self.analysis_labels['portfolio_health'].config(
                                text=health_text,
                                fg=health_color
                            )
                        
                        # อัพเดท risk level
                        risk_level = getattr(closing_result, 'risk_level', 'LOW')
                        if risk_level == 'LOW':
                            risk_text = "🟢 LOW"
                            risk_color = '#00ff88'
                        elif risk_level == 'MEDIUM':
                            risk_text = "🟡 MEDIUM"
                            risk_color = '#ffaa00'
                        else:
                            risk_text = "🔴 HIGH"
                            risk_color = '#ff4444'
                        
                        self.analysis_labels['risk_level'].config(
                            text=risk_text,
                            fg=risk_color
                        )
                        
                        # อัพเดท market timing
                        market_timing = getattr(closing_result, 'market_timing', 'NEUTRAL')
                        if market_timing == 'EXCELLENT':
                            timing_text = "🟢 EXCELLENT"
                            timing_color = '#00ff88'
                        elif market_timing == 'GOOD':
                            timing_text = "🟡 GOOD"
                            timing_color = '#ffaa00'
                        elif market_timing == 'POOR':
                            timing_text = "🔴 POOR"
                            timing_color = '#ff4444'
                        else:
                            timing_text = "⚪ NEUTRAL"
                            timing_color = '#cccccc'
                        
                        self.analysis_labels['market_timing'].config(
                            text=timing_text,
                            fg=timing_color
                        )
                else:
                    # ไม่มี positions
                    self.analysis_labels['closing_recommendation'].config(
                        text="💤 NO POSITIONS",
                        fg='#cccccc'
                    )
                    self.analysis_labels['closing_confidence'].config(
                        text="0%",
                        fg='#cccccc'
                    )
                    self.analysis_labels['portfolio_health'].config(
                        text="⚪ NO DATA",
                        fg='#cccccc'
                    )
                    self.analysis_labels['risk_level'].config(
                        text="⚪ NO DATA",
                        fg='#cccccc'
                    )
                    self.analysis_labels['market_timing'].config(
                        text="⚪ NO DATA",
                        fg='#cccccc'
                    )
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการอัพเดทการวิเคราะห์ 7D: {str(e)}")
            
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
                
            # เริ่มการเทรดผ่าน TradingSystem (ใน background thread)
            def start_trading_async():
                try:
                    success = self.trading_system.start_trading()
                    if success:
                        # อัพเดท GUI ใน main thread
                        self.root.after(0, lambda: self.update_trading_status(True))
                        logger.info("เริ่มการเทรดจาก GUI สำเร็จ")
                    else:
                        self.root.after(0, lambda: messagebox.showerror("Error", "ไม่สามารถเริ่มการเทรดได้"))
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
