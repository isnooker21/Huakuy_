# Standard library imports
import json
import logging
import os
import pickle
import platform
import queue
import subprocess
import threading
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, TYPE_CHECKING

# GUI imports
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox

# Safe imports with fallback for missing dependencies
try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    print("WARNING: MetaTrader5 not available - running in simulation mode")
    mt5 = None
    MT5_AVAILABLE = True

try:
    import pandas as pd
except ImportError:
    print("WARNING: pandas not available - using basic data structures")
    pd = None

try:
    import numpy as np
except ImportError:
    print("WARNING: numpy not available - using basic math operations")
    np = None

# TYPE_CHECKING imports for proper type annotations
if TYPE_CHECKING:
    from pandas import DataFrame
else:
    # Runtime fallback to avoid import errors
    DataFrame = Any

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def serialize_datetime_objects(data):
    """Convert datetime objects to ISO strings for JSON serialization (supports nested structures)"""
    if isinstance(data, dict):
        return {k: serialize_datetime_objects(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [serialize_datetime_objects(item) for item in data]
    elif isinstance(data, datetime):
        return data.isoformat()
    return data

def safe_parse_datetime(date_value):
    """Safely parse datetime value from string or datetime object"""
    try:
        if isinstance(date_value, datetime):
            return date_value
        elif isinstance(date_value, str):
            return datetime.fromisoformat(date_value)
        else:
            logger.warning(f"Invalid datetime type: {type(date_value)}, returning current time")
            return datetime.now()
    except (ValueError, TypeError) as e:
        logger.error(f"Error parsing datetime '{date_value}': {e}, returning current time")
        return datetime.now()

class ValidationError(Exception):
    """Custom validation error"""
    pass

class InputValidator:
    """Input validation utility class"""
    
    @staticmethod
    def _validate_numeric(value, name: str, allow_types=(int, float)):
        """Common numeric validation helper"""
        if not isinstance(value, allow_types):
            raise ValidationError(f"{name} must be numeric, got {type(value)}")
        return float(value)
    
    @staticmethod
    def _validate_positive(value: float, name: str):
        """Common positive number validation helper"""
        if value <= 0:
            raise ValidationError(f"{name} must be positive, got {value}")
    
    @staticmethod
    def validate_volume(volume: float, min_volume: float = 0.01, max_volume: float = 100.0) -> float:
        """Validate trading volume with MT5 compatibility"""
        volume = InputValidator._validate_numeric(volume, "Volume")
        InputValidator._validate_positive(volume, "Volume")
        
        # Apply limits with auto-correction
        if volume < min_volume:
            volume = min_volume
        if volume > max_volume:
            volume = max_volume
        
        # Round to 2 decimal places for MT5 compatibility
        volume = round(volume, 2)
        
        # Ensure minimum step compliance (most brokers use 0.01 step)
        volume_steps = round(volume / 0.01) * 0.01
        volume = round(volume_steps, 2)
        
        return volume
    
    @staticmethod
    def validate_symbol(symbol: str) -> str:
        """Validate trading symbol"""
        if not isinstance(symbol, str):
            raise ValidationError(f"Symbol must be string, got {type(symbol)}")
        
        symbol = symbol.strip().upper()
        if not symbol:
            raise ValidationError("Symbol cannot be empty")
        if len(symbol) < 3 or len(symbol) > 20:
            raise ValidationError(f"Symbol length must be 3-20 characters, got {len(symbol)}")
        
        return symbol
    
    @staticmethod
    def validate_price(price: float, min_price: float = 0.0001) -> float:
        """Validate price values"""
        price = InputValidator._validate_numeric(price, "Price")
        InputValidator._validate_positive(price, "Price")
        
        if price < min_price:
            raise ValidationError(f"Price {price} below minimum {min_price}")
        
        return price
    
    @staticmethod
    def validate_signal_direction(direction: str) -> str:
        """Validate signal direction"""
        if not isinstance(direction, str):
            raise ValidationError(f"Direction must be string, got {type(direction)}")
        
        direction = direction.strip().upper()
        if direction not in ['BUY', 'SELL']:
            raise ValidationError(f"Direction must be 'BUY' or 'SELL', got '{direction}'")
        
        return direction

@dataclass
class Signal:
    """Signal data structure"""
    timestamp: datetime
    symbol: str
    direction: str  # 'BUY' or 'SELL'
    strength: float  # 0.5 - 3.0
    reason: str
    price: float

@dataclass
class Position:
    """Position data structure"""
    ticket: int
    symbol: str
    type: str
    volume: float
    open_price: float
    current_price: float
    profit: float
    profit_per_lot: float
    role: str = "UNKNOWN"  # MAIN, HG, SUPPORT, SACRIFICE
    efficiency: str = "fair"  # excellent, good, fair, poor

class OrderRole(Enum):
    MAIN = "MAIN"
    HEDGE_GUARD = "HG"
    SUPPORT = "SUPPORT"
    SACRIFICE = "SACRIFICE"

class TradingSystem:
    def __init__(self):
        self.mt5_connected = False
        self.trading_active = False
        self.symbol = "XAUUSD.v"  # เปลี่ยนจาก "XAUUSD" เป็น "XAUUSD.v"
        self.base_lot = 0.01
        self.max_positions = 50
        self.min_margin_level = 200.0
        self.signal_cooldown = 60  # seconds
        self.max_signals_per_hour = 40
        
        # Trading statistics
        self.total_signals = 0
        self.successful_signals = 0
        self.last_signal_time = None
        self.hourly_signals = []
        
        # Portfolio tracking
        self.positions: List[Position] = []
        self.buy_volume = 0.0
        self.sell_volume = 0.0
        self.portfolio_health = 100.0
        
        # GUI components
        self.root = None
        self.log_queue = queue.Queue()
        
        # 🧠 Smart Signal Router & Position Management
        self.position_tracker = {}
        self.smart_router_enabled = True
        self.balance_target_ratio = 0.5
        self.balance_tolerance = 0.15  # ยอมรับ 35:65 - 65:35
        self.redirect_threshold = 0.65  # redirect เมื่อ balance เกิน 65:35
        self.max_redirect_ratio = 0.4   # redirect ได้สูงสุด 40% ของ signals
        
        # Adaptive profit management
        self.profit_harvest_threshold = 50.0
        self.adaptive_profit_targets = True
        self.min_profit_for_redirect_close = 25.0
        self.position_efficiency_check_interval = 30
        self.last_efficiency_check = None
        
        # Smart routing statistics
        self.total_redirects = 0
        self.successful_redirects = 0
        self.redirect_profit_captured = 0.0
        self.last_redirect_time = None
        self.redirect_cooldown = 30  # วินาที
        
        # Position hold scoring
        self.max_hold_hours = 48
        self.gentle_management = True
        self.emergency_mode_threshold = 25  # portfolio health

        # 🎯 Zone-Based Trading System Configuration
        self.zone_size_pips = 25  # ขนาด zone (pips)
        
        # 🎯 Smart Position Management (ป้องกันการออกไม้มั่วซั่ว)
        self.debug_distance_calculation = False  # เปิดเพื่อ debug การคำนวณระยะ
        self.debug_position_tracking = False  # เปิดเพื่อ debug การ track positions
        self.max_positions_per_zone = 5  # จำกัดไม้ต่อ zone (ป้องกันการกระจุกตัว)
        self.min_position_distance_pips = 8   # ระยะห่างขั้นต่ำ 8 pips (ป้องกันการใกล้กันเกินไป)
        self.force_zone_diversification = True  # เปิดการบังคับกระจาย (ป้องกันการกระจุกตัว)
        
        # 🧠 Smart Opening Rules (ยืดหยุ่นขึ้น)
        self.max_total_positions = 50  # เพิ่มจาก 20 เป็น 50 (ยืดหยุ่นขึ้น)
        self.max_daily_positions = 25  # เพิ่มจาก 10 เป็น 25 (ยืดหยุ่นขึ้น)
        self.position_opening_cooldown = 15  # ลดจาก 30 เป็น 15 วินาที (เร็วขึ้น)
        self.last_position_opened = None  # เวลาที่เปิดไม้ล่าสุด
        
        # 🆕 Dynamic Position Limits (ปรับตามตลาด)
        self.dynamic_position_limits = True  # เปิดใช้งาน dynamic limits
        self.market_opportunity_multiplier = 2.0  # คูณ 2 เมื่อมีโอกาสดี
        self.continuous_movement_bonus = 5  # เพิ่ม 5 ไม้เมื่อกราฟวิ่งต่อเนื่อง
        
        # 📊 Dynamic Lot Sizing Configuration
        self.base_lot_size = 0.01  # lot พื้นฐาน
        
        # 🚀 Performance Optimization - Zone Analysis Caching
        self.zone_analysis_cache = None
        self.zone_analysis_cache_time = None
        self.zone_analysis_cache_positions_hash = None
        self.zone_cache_ttl = 30  # seconds - cache for 30 seconds
        self.zone_recalc_threshold = 0.1  # recalculate if positions change by 10%
        self.max_lot_size = 0.10   # lot สูงสุด
        self.lot_multiplier_range = (0.5, 3.0)  # ช่วงการคูณ lot
        self.equity_based_sizing = True  # ปรับตาม equity
        self.signal_strength_multiplier = True  # ปรับตาม signal strength

        # Auto-detect filling type
        self.filling_type = None
        if MT5_AVAILABLE:
            self.filling_types_priority = [
                mt5.ORDER_FILLING_IOC,  # Immediate or Cancel
                mt5.ORDER_FILLING_FOK,  # Fill or Kill  
                mt5.ORDER_FILLING_RETURN  # Return (default)
            ]
        else:
            # Fallback values when MT5 is not available
            self.filling_types_priority = [0, 1, 2]  # Mock values
        
        # 🔗 Connection Health Monitoring & Circuit Breakers
        self.last_mt5_ping = None
        self.connection_failures = 0
        self.max_connection_failures = 5
        self.connection_check_interval = 30  # seconds
        self.circuit_breaker_enabled = True
        
        # 🚀 พยายามเชื่อมต่อ MT5 ทันที
        self._try_connect_mt5()
        
        # Circuit breaker settings
        self.circuit_breaker_threshold = 3  # failures before breaking
        self.circuit_breaker_timeout = 300  # 5 minutes before retry
        
        # 🚀 AI Margin Intelligence System
        self.ai_margin_intelligence = True
        self.dynamic_profit_targets = True
        self.margin_priority_mode = True
        self.ai_confidence_threshold = 0.7
        self.market_intelligence_enabled = True
        self.portfolio_optimization_enabled = True
        
        # AI Decision History
        self.ai_decision_history = []
        self.market_reversal_history = []
        self.portfolio_performance_history = []
        
        # AI Configuration
        self.ai_margin_warning_threshold = 0.75  # ยืดหยุ่นขึ้น
        self.ai_margin_caution_threshold = 0.85  # ยืดหยุ่นขึ้น
        self.ai_margin_danger_threshold = 0.60   # ยืดหยุ่นขึ้น
        self.ai_margin_emergency_threshold = 0.40  # ยืดหยุ่นขึ้น
        
        # Circuit breaker state
        self.circuit_breaker_open = False
        self.circuit_breaker_last_failure = None

        # 🖥️ Terminal Selection System
        self.available_terminals = []
        self.selected_terminal = None
        self.terminal_scan_in_progress = False

        # 🛡️ Anti-Exposure Protection System (IMPROVED)
        self.anti_exposure_enabled = True
        self.max_exposure_distance = 150  # pips (1.5 points for XAUUSD)
        self.exposure_warning_distance = 50   # ลดจาก 100 → 50 pips
        self.auto_hedge_enabled = True
        self.hedge_trigger_distance = 30     # ลดจาก 120 → 30 pips (ทำงานเร็วขึ้นมาก!)
        
        # 🎯 Support/Resistance Detection
        self.sr_detection_enabled = True
        self.sr_lookback_periods = 50  # candles to analyze
        self.sr_strength_threshold = 3  # minimum touches to confirm S/R
        self.sr_proximity_pips = 20  # pips distance to consider "at" S/R
        
        # 🔄 Auto-Hedge System - ENHANCED
        self.hedge_system_enabled = True
        self.hedge_calculation_method = "LOSS_COVERAGE"  # VOLUME_MATCH, LOSS_COVERAGE, DISTANCE_BASED
        self.hedge_coverage_ratio = 1.2  # 120% loss coverage
        self.min_hedge_volume = 0.01
        self.max_hedge_volume = 5.0
        self.hedge_distance_multiplier = 1.5
        
        # 🛠️ Advanced Drawdown Management (IMPROVED)
        self.drawdown_management_enabled = True
        self.drawdown_trigger_pips = 50   # ลดจาก 150 → 50 pips (ทำงานเร็วขึ้น)
        self.critical_drawdown_pips = 100 # ลดจาก 250 → 100 pips  
        self.emergency_drawdown_pips = 150 # ลดจาก 350 → 150 pips
        
        # 🔄 Portfolio Balance Protection
        self.balance_protection_enabled = True
        self.min_balance_ratio = 0.2  # อย่างน้อย 20:80 หรือ 80:20
        self.balance_preference_when_stuck = "HEDGE_SUPPORT"  # สร้าง hedge เพื่อช่วยไม้ที่ติด
        
        # 🤖 AI Margin Intelligence System (NEW!)
        self.ai_margin_intelligence = True
        self.dynamic_profit_targets = True
        self.margin_priority_mode = True  # Margin เป็นความสำคัญอันดับ 1
        
        # 📊 AI Priority Weights (Margin-First)
        self.margin_priority_weight = 0.40    # 40% - สำคัญสุด!
        self.profit_priority_weight = 0.25    # 25%
        self.balance_priority_weight = 0.20   # 20%
        self.risk_priority_weight = 0.15      # 15%
        
        # 🎯 Dynamic Profit Targets (% per lot)
        self.profit_target_emergency = 0.001  # 0.1% per lot (ปิดง่ายมาก!)
        self.profit_target_danger = 0.003     # 0.3% per lot
        self.profit_target_caution = 0.005    # 0.5% per lot
        self.profit_target_safe = 0.005       # 0.5% per lot (ลดลงจาก 1.0% เพื่อให้ปิดง่ายขึ้น)
        
        # 🧠 AI Margin Risk Factors
        self.margin_risk_factors = {
            'position_count_weight': 0.25,
            'volatility_weight': 0.20,
            'account_health_weight': 0.30,
            'market_session_weight': 0.15,
            'broker_buffer_weight': 0.10
        }
        
        # 📈 AI Learning & History
        self.ai_decision_history = []
        self.margin_call_history = []
        self.ai_confidence_threshold = 0.50  # 50% confidence minimum (ลดลงเพื่อให้ AI ทำงานง่ายขึ้น)
        
        # 🆕 Market Intelligence Enhancement System
        self.market_intelligence_enabled = True
        self.real_time_market_analysis = True
        self.market_reversal_detection = True
        self.volume_momentum_analysis = True
        
        # 📊 Market Intelligence Configuration
        self.market_analysis_interval = 15  # seconds
        self.reversal_detection_periods = 20  # candles for reversal detection
        self.volume_threshold_multiplier = 1.5  # volume spike detection
        self.momentum_lookback_periods = 10  # periods for momentum calculation
        
        # 🎯 Smart Threshold Adjustment
        self.dynamic_threshold_adjustment = True
        self.market_condition_adaptation = True
        self.session_based_optimization = True
        
        # 🆕 Portfolio Optimization Engine
        self.portfolio_optimization_enabled = True
        self.real_time_performance_analysis = True
        self.dynamic_risk_adjustment = True
        self.smart_position_rebalancing = True
        
        # 📈 Portfolio Optimization Configuration
        self.performance_analysis_interval = 30  # seconds
        self.risk_adjustment_threshold = 0.1  # 10% change triggers adjustment
        self.rebalancing_trigger_ratio = 0.15  # 15% imbalance triggers rebalancing
        self.max_rebalancing_frequency = 300  # 5 minutes between rebalancing
        
        # 🆕 Market Intelligence History
        self.market_reversal_history = []
        self.volume_spike_history = []
        self.momentum_trend_history = []
        self.threshold_adjustment_history = []
        
        # 🆕 Portfolio Performance History
        self.portfolio_performance_history = []
        self.risk_adjustment_history = []
        self.rebalancing_history = []
        self.performance_metrics = {
            'win_rate': 0.0,
            'avg_profit': 0.0,
            'avg_loss': 0.0,
            'profit_factor': 0.0,
            'max_drawdown': 0.0,
            'sharpe_ratio': 0.0,
            'cycles_completed': 0,           # 🆕 เพิ่ม key ที่ขาดหายไป
            'error_rate': 0.0,               # 🆕 เพิ่ม key ที่ขาดหายไป
            'total_trades': 0,               # 🆕 เพิ่ม key ที่ขาดหายไป
            'successful_trades': 0,          # 🆕 เพิ่ม key ที่ขาดหายไป
            'uptime_start': datetime.now(),  # 🆕 เพิ่ม key ที่ขาดหายไป
            'successful_operations': 0,      # 🆕 เพิ่ม key ที่ขาดหายไป
            'failed_operations': 0,          # 🆕 เพิ่ม key ที่ขาดหายไป
            'recent_errors': [],             # 🆕 เพิ่ม key ที่ขาดหายไป
            'execution_times': [],           # 🆕 เพิ่ม key ที่ขาดหายไป
            'average_execution_time': 0.0    # 🆕 เพิ่ม key ที่ขาดหายไป
        }
        
        # 🎯 Dynamic Hedge Strategy
        self.hedge_strategy = "SMART_RECOVERY"  # IMMEDIATE, SMART_RECOVERY, AVERAGING, HYBRID
        self.hedge_volume_calculation = "DYNAMIC_RATIO"  # FIXED_RATIO, DYNAMIC_RATIO, LOSS_BASED
        self.hedge_min_profit_to_close = 0.5  # 0.5% profit ถึงจะปิด hedge
        self.hedge_recovery_target = 2.0  # เป้า 2% กำไรรวม
        
        # 🔄 Multi-Level Hedge System
        self.max_hedge_levels = 3  # สูงสุด 3 ระดับ hedge
        self.hedge_distance_increment = 50  # เพิ่มระยะห่าง 50 pips ต่อ level
        self.hedge_volume_multiplier = 1.3  # เพิ่ม volume 1.3 เท่าต่อ level
        
        # 📊 Hedge Tracking & Analytics
        self.active_hedges = {}  # {original_ticket: [hedge_tickets]}
        self.hedge_pairs = {}    # {hedge_ticket: original_ticket}
        self.hedge_analytics = {
            'total_hedges_created': 0,
            'successful_recoveries': 0,
            'total_recovery_profit': 0.0,
            'avg_recovery_time_hours': 0.0,
            'hedge_effectiveness': 0.0,
            'active_hedge_pairs': 0
        }
    
    def _try_connect_mt5(self):
        """🚀 พยายามเชื่อมต่อ MT5 ทันที"""
        try:
            if MT5_AVAILABLE and mt5:
                # พยายามเชื่อมต่อ
                if mt5.initialize():
                    self.mt5_connected = True
                    self.log("✅ MT5 Connected successfully!", "INFO")
                    
                    # ตรวจสอบ account info
                    account_info = mt5.account_info()
                    if account_info:
                        self.log(f"💰 Account: {account_info.login} | Balance: ${account_info.balance:.2f}", "INFO")
                        self.log(f"📊 Equity: ${account_info.equity:.2f} | Margin: ${account_info.margin:.2f}", "INFO")
                    else:
                        self.log("⚠️ Connected to MT5 but cannot get account info", "WARNING")
                else:
                    self.mt5_connected = False
                    self.log("❌ Failed to initialize MT5", "ERROR")
            else:
                self.mt5_connected = False
                self.log("⚠️ MT5 not available - running in simulation mode", "WARNING")
                
        except Exception as e:
            self.mt5_connected = False
            self.log(f"❌ Error connecting to MT5: {str(e)}", "ERROR")

        # 🎯 Smart Pair/Group Closing System (เปลี่ยนเป็น %)
        self.pair_closing_enabled = True
        self.min_pair_profit_percent = 2.0  # กำไรรวมขั้นต่ำ 2%
        self.group_closing_enabled = True
        self.min_group_profit_percent = 3.0  # กำไรรวมขั้นต่ำ 3%
        self.max_loss_percent = -15.0  # ขาดทุนสูงสุด -15% ต่อไม้ที่ยอมให้จับคู่
        self.portfolio_recovery_mode = True
        self.recovery_target_percent = 5.0  # เป้ากำไร 5% สำหรับโหมดฟื้นฟู
        
        # เปลี่ยน profit targets เป็น %
        self.profit_harvest_threshold_percent = 8.0  # 8% กำไรต่อ lot
        self.min_profit_for_redirect_close_percent = 3.0  # 3% ขั้นต่ำสำหรับ redirect
        self.emergency_profit_threshold_percent = 4.0  # 4% ขั้นต่ำสำหรับ emergency close
        
        # Statistics
        self.total_pair_closes = 0
        self.successful_pair_closes = 0
        self.pair_profit_captured = 0.0
        self.total_group_closes = 0
        self.group_profit_captured = 0.0

        # เพิ่มชื่อไฟล์สำหรับ save/load
        self.state_file = "trading_state.json"
        self.positions_file = "positions_backup.pkl"
        
        # โหลดสถานะเมื่อเริ่มโปรแกรม - with safe loading
        try:
            self.load_trading_state()
            print("✅ Trading state loaded successfully")
        except Exception as e:
            print(f"⚠️ State loading failed: {e}")
            # Continue with default values instead of crashing
            self.log(f"Warning: Using default state due to loading error: {e}", "WARNING")
        
        # 🛠️ Smart HG System - เพิ่มส่วนนี้
        self.smart_hg_enabled = True
        self.hg_intelligence_level = "ADVANCED"
        self.hg_decision_threshold = 75
        self.hg_max_concurrent = 3
        self.hg_cooldown_minutes = 15
        
        # 📊 HG Decision Parameters
        self.market_context_weight = 0.3
        self.position_cluster_analysis = True
        self.dynamic_risk_assessment = True
        self.partial_hedge_enabled = True
        self.hedge_timing_optimization = True
        
        # 🎯 Advanced HG Strategies
        self.hg_strategy_selection = "AUTO_ADAPTIVE"
        self.min_loss_threshold_for_hg = 100
        self.max_portfolio_hg_ratio = 0.4
        
        # 💡 Pattern Recognition
        self.hg_pattern_learning = True
        self.avoid_bad_timing = True
        self.market_reversal_detection = True
        self.hg_performance_history = []
        
        # 📊 System Health Monitoring & Enhanced Debugging
        self.system_health_enabled = True
        self.health_check_interval = 300  # 5 minutes
        self.last_health_check = None
        self.system_alerts = []
        self.max_alerts = 50  # Keep last 50 alerts
        
        # Performance metrics
        self.performance_metrics = {
            'average_execution_time': 0.0,
            'execution_times': [],
            'error_rate': 0.0,
            'recent_errors': [],
            'uptime_start': datetime.now(),
            'cycles_completed': 0,
            'successful_operations': 0,
            'failed_operations': 0
        }
        
        # Debug settings
        self.debug_mode = False
        self.verbose_logging = False
        self.log_market_data = False
        self.log_memory_usage = False
        self.hg_performance_history = []
        self.hg_success_patterns = {}
        self.hg_failure_analysis = {}
        
        # 🔧 Missing Variables - Added for complete initialization
        self.last_hedge_time = None  # Track last hedge execution time
        self.recent_volatility = 1.0  # Default volatility level

    def log(self, message: str, level: str = "INFO"):
        """🎨 Enhanced thread-safe logging with beautiful formatting"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # 🎨 Enhanced formatting with smart emojis and colors
        level_icons = {
            "INFO": "ℹ️",
            "WARNING": "⚠️", 
            "ERROR": "❌",
            "SUCCESS": "✅",
            "DEBUG": "🐛"
        }
        
        # 🧠 Smart category detection with enhanced emojis
        category_icons = {
            "TRADE": "💰",
            "SIGNAL": "📡", 
            "POSITION": "📊",
            "CLOSING": "🎯",
            "HEDGE": "🔄",
            "AI": "🤖",
            "MARGIN": "🏦",
            "RECOVERY": "🧠",
            "BASKET": "🧮",
            "BALANCE": "⚖️",
            "PROFIT": "💵",
            "SYSTEM": "⚙️",
            "CONNECTION": "🔗",
            "ZONE": "🗺️"
        }
        
        # 🎯 Auto-detect category from message content
        clean_message = message.strip()
        message_lower = clean_message.lower()
        
        # Smart category detection
        if any(keyword in message_lower for keyword in ["buy", "sell", "order", "execute", "trade"]):
            category = "TRADE"
        elif any(keyword in message_lower for keyword in ["signal", "zone", "analysis", "strength"]):
            category = "SIGNAL"
        elif any(keyword in message_lower for keyword in ["position", "ticket", "close", "tracking"]):
            category = "POSITION"
        elif any(keyword in message_lower for keyword in ["hedge", "balance", "support", "volume"]):
            category = "HEDGE"
        elif any(keyword in message_lower for keyword in ["ai", "margin", "risk", "assessment"]):
            category = "AI"
        elif any(keyword in message_lower for keyword in ["basket", "optimal", "score", "combination"]):
            category = "BASKET"
        elif any(keyword in message_lower for keyword in ["recovery", "smart", "emergency"]):
            category = "RECOVERY"
        elif any(keyword in message_lower for keyword in ["profit", "loss", "p&l", "equity"]):
            category = "PROFIT"
        elif any(keyword in message_lower for keyword in ["connect", "mt5", "terminal", "broker"]):
            category = "CONNECTION"
        elif any(keyword in message_lower for keyword in ["system", "start", "stop", "status"]):
            category = "SYSTEM"
        else:
            category = "INFO"
        
        # 🎨 Get appropriate icons
        level_icon = level_icons.get(level, "📝")
        category_icon = category_icons.get(category, "ℹ️")
        
        # 🎯 Create beautiful formatted message
        if level == "ERROR":
            log_message = f"{timestamp} {level_icon} {category_icon} ERROR: {clean_message}"
        elif level == "WARNING":
            log_message = f"{timestamp} {level_icon} {category_icon} WARN: {clean_message}"
        elif level == "SUCCESS":
            log_message = f"{timestamp} {level_icon} {category_icon} {clean_message}"
        elif level == "DEBUG":
            log_message = f"{timestamp} {level_icon} {category_icon} DEBUG: {clean_message}"
        else:
            # 🎨 Special formatting for different categories
            if category == "AI":
                log_message = f"{timestamp} {category_icon} {clean_message}"
            elif category == "BASKET":
                log_message = f"{timestamp} {category_icon} {clean_message}"
            elif category == "RECOVERY":
                log_message = f"{timestamp} {category_icon} {clean_message}"
            elif category == "TRADE":
                log_message = f"{timestamp} {category_icon} {clean_message}"
            else:
                log_message = f"{timestamp} {category_icon} {clean_message}"
        
        # 📤 Add to queue for GUI update
        self.log_queue.put(log_message)
        
        # 🖥️ Console output
        print(log_message)

    def detect_broker_filling_type(self) -> int:
        """Auto-detect broker's supported filling type"""
        if not MT5_AVAILABLE:
            self.log("MT5 not available - using mock filling type", "WARNING")
            return 0  # Mock value
            
        if not self.mt5_connected:
            return mt5.ORDER_FILLING_IOC
            
        try:
            # Get symbol info to check filling modes
            symbol_info = mt5.symbol_info(self.symbol)
            if symbol_info is None:
                self.log(f"Cannot get symbol info for {self.symbol}", "WARNING")
                return mt5.ORDER_FILLING_IOC
            
            filling_modes = symbol_info.filling_mode
            
            # Check each filling type in priority order
            for filling_type in self.filling_types_priority:
                if filling_modes & filling_type:
                    filling_name = {
                        mt5.ORDER_FILLING_IOC: "IOC (Immediate or Cancel)",
                        mt5.ORDER_FILLING_FOK: "FOK (Fill or Kill)",
                        mt5.ORDER_FILLING_RETURN: "RETURN (Default)"
                    }.get(filling_type, f"Unknown ({filling_type})")
                    
                    self.log(f"✅ Detected broker filling type: {filling_name}")
                    return filling_type
            
            # Fallback to RETURN if nothing else works
            self.log("⚠️ Using fallback filling type: RETURN", "WARNING")
            return mt5.ORDER_FILLING_RETURN
            
        except Exception as e:
            self.log(f"Error detecting filling type: {str(e)}", "ERROR")
            return mt5.ORDER_FILLING_IOC

    def connect_mt5(self, max_retries: int = 3, retry_delay: float = 2.0) -> bool:
        """Connect to MetaTrader 5 with retry mechanism and validation"""
        if not MT5_AVAILABLE:
            self.log("MT5 not available - running in simulation mode", "WARNING")
            self.mt5_connected = False
            return False
            
        for attempt in range(max_retries):
            try:
                # Validate inputs
                if max_retries < 1:
                    raise ValidationError("max_retries must be at least 1")
                if retry_delay < 0:
                    raise ValidationError("retry_delay cannot be negative")
                
                self.log(f"MT5 connection attempt {attempt + 1}/{max_retries}")
                
                # Initialize MT5
                if not mt5.initialize():
                    error_code = mt5.last_error()
                    self.log(f"MT5 initialization failed: {error_code}", "ERROR")
                    if attempt < max_retries - 1:
                        self.log(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 1.5  # Exponential backoff
                        continue
                    return False
                
                # Validate connection with account info
                account_info = mt5.account_info()
                if account_info is None:
                    error_code = mt5.last_error()
                    self.log(f"Failed to get account info: {error_code}", "ERROR")
                    mt5.shutdown()
                    if attempt < max_retries - 1:
                        self.log(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 1.5
                        continue
                    return False
                
                # Validate account state
                if account_info.trade_allowed is False:
                    self.log("Trading is not allowed on this account", "ERROR")
                    mt5.shutdown()
                    return False
                
                # Connection successful
                self.mt5_connected = True
                
                # Auto-detect filling type after connection
                try:
                    self.filling_type = self.detect_broker_filling_type()
                except Exception as e:
                    self.log(f"Warning: Could not detect filling type: {e}", "WARNING")
                    self.filling_type = mt5.ORDER_FILLING_IOC  # Safe default
                
                self.log(f"✅ Connected to MT5 - Account: {account_info.login}")
                self.log(f"Balance: ${account_info.balance:.2f}, Equity: ${account_info.equity:.2f}")
                self.log(f"Trade allowed: {account_info.trade_allowed}")
                
                # Initialize connection health tracking
                self.last_mt5_ping = datetime.now()
                self.connection_failures = 0
                
                return True
                
            except ValidationError as e:
                self.log(f"Validation error in MT5 connection: {e}", "ERROR")
                return False
            except Exception as e:
                self.log(f"MT5 connection error (attempt {attempt + 1}): {str(e)}", "ERROR")
                if attempt < max_retries - 1:
                    self.log(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5
                    continue
                
        self.log("All MT5 connection attempts failed", "ERROR")
        return False
    
    def scan_available_terminals(self) -> List[Dict]:
        """Scan for available MT5 terminals across different platforms with timeout protection"""
        terminals = []
        try:
            import os
            import subprocess
            import platform
            import signal
            
            self.log("🔍 Scanning for available MT5 terminals...")
            system = platform.system()
            self.log(f"📊 Detected platform: {system}")
            
            # Set a timeout handler for the entire scan operation
            def timeout_handler(signum, frame):
                raise TimeoutError("Terminal scan operation timed out")
            
            # Only set alarm on Unix-like systems
            if hasattr(signal, 'SIGALRM'):
                signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(15)  # 15 second timeout for entire scan
            
            try:
                if system == "Windows":
                    terminals = self._scan_windows_terminals()
                elif system == "Linux":
                    terminals = self._scan_linux_terminals()
                elif system == "Darwin":  # macOS
                    terminals = self._scan_macos_terminals()
                else:
                    self.log(f"⚠️ Unsupported platform: {system}", "WARNING")
                    terminals = self._get_default_terminal()
            finally:
                # Cancel the alarm
                if hasattr(signal, 'SIGALRM'):
                    signal.alarm(0)
            
            # If no terminals found, provide default option
            if not terminals:
                self.log("📋 No running terminals found, adding default option")
                terminals = self._get_default_terminal()
            
            self.log(f"📊 Terminal scan completed: {len(terminals)} terminal(s) found")
            return terminals
            
        except TimeoutError:
            self.log("⏰ Terminal scan operation timed out", "WARNING")
            return self._get_default_terminal()
        except Exception as e:
            self.log(f"❌ Error scanning terminals: {str(e)}", "ERROR")
            return self._get_default_terminal()
    
    def _scan_windows_terminals(self) -> List[Dict]:
        """Scan for MT5 terminals on Windows"""
        terminals = []
        try:
            # Use tasklist to find running MT5 processes
            result = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq terminal64.exe', '/FO', 'CSV'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and 'terminal64.exe' in result.stdout:
                self.log("✅ Found running MT5 terminal process")
                lines = result.stdout.strip().split('\n')[1:]  # Skip header
                
                for line in lines:
                    if 'terminal64.exe' in line:
                        # Try to get terminal info by connecting
                        terminal_data = self._get_running_terminal_info()
                        if terminal_data:
                            terminals.append(terminal_data)
                            break
                            
        except subprocess.TimeoutExpired:
            self.log("⏰ Terminal scan timeout", "WARNING")
        except FileNotFoundError:
            self.log("⚠️ tasklist command not found (not Windows?)", "WARNING")
        except Exception as e:
            self.log(f"❌ Windows terminal scan error: {e}", "ERROR")
            
        return terminals
    
    def _scan_linux_terminals(self) -> List[Dict]:
        """Scan for MT5 terminals on Linux (Wine)"""
        terminals = []
        try:
            # Look for wine processes running MT5
            result = subprocess.run(['pgrep', '-f', 'terminal64.exe'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                self.log("✅ Found MT5 terminal process under Wine")
                terminal_data = self._get_running_terminal_info()
                if terminal_data:
                    terminals.append(terminal_data)
                    
        except subprocess.TimeoutExpired:
            self.log("⏰ Linux terminal scan timeout", "WARNING")
        except FileNotFoundError:
            self.log("⚠️ pgrep command not found", "WARNING")
        except Exception as e:
            self.log(f"❌ Linux terminal scan error: {e}", "ERROR")
            
        return terminals
    
    def _scan_macos_terminals(self) -> List[Dict]:
        """Scan for MT5 terminals on macOS (Wine)"""
        terminals = []
        try:
            # Similar to Linux, look for wine processes
            result = subprocess.run(['pgrep', '-f', 'terminal64.exe'], 
                                  capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0 and result.stdout.strip():
                self.log("✅ Found MT5 terminal process under Wine")
                terminal_data = self._get_running_terminal_info()
                if terminal_data:
                    terminals.append(terminal_data)
                    
        except Exception as e:
            self.log(f"❌ macOS terminal scan error: {e}", "ERROR")
            
        return terminals
    
    def _get_running_terminal_info(self) -> Dict:
        """Try to connect to running terminal and get info"""
        try:
            # Temporarily connect to get terminal info
            if mt5.initialize():
                terminal_info = mt5.terminal_info()
                account_info = mt5.account_info()
                
                terminal_data = {
                    'path': 'default',  # Running terminal
                    'login': account_info.login if account_info else 'Unknown',
                    'server': account_info.server if account_info else 'Unknown',
                    'company': terminal_info.company if terminal_info else 'Unknown',
                    'name': terminal_info.name if terminal_info else 'MetaTrader 5',
                    'build': terminal_info.build if terminal_info else 'Unknown',
                    'connected': terminal_info.connected if terminal_info else False,
                    'display_name': f"MT5 - {account_info.login}@{account_info.server}" if account_info else "MT5 Terminal"
                }
                
                mt5.shutdown()
                self.log(f"✅ Retrieved terminal info: {terminal_data['display_name']}")
                return terminal_data
                
        except Exception as e:
            self.log(f"⚠️ Could not get running terminal info: {e}", "WARNING")
            try:
                mt5.shutdown()  # Ensure cleanup
            except:
                pass
                
        return None
    
    def _get_default_terminal(self) -> List[Dict]:
        """Get default terminal option when no terminals are found"""
        return [{
            'path': 'default',
            'login': 'Not Connected',
            'server': 'Not Connected', 
            'company': 'Unknown',
            'name': 'MetaTrader 5',
            'build': 'Unknown',
            'connected': False,
            'display_name': 'Default MT5 Terminal'
        }]
    
    def get_terminal_info(self, terminal_path: str) -> Dict:
        """Get detailed information about a specific terminal"""
        try:
            if terminal_path == 'default':
                # Try to connect and get info
                if mt5.initialize():
                    terminal_info = mt5.terminal_info()
                    account_info = mt5.account_info()
                    
                    info = {
                        'terminal_info': {
                            'company': terminal_info.company if terminal_info else 'Unknown',
                            'name': terminal_info.name if terminal_info else 'MetaTrader 5',
                            'path': terminal_info.path if terminal_info else 'Unknown',
                            'build': terminal_info.build if terminal_info else 'Unknown',
                            'connected': terminal_info.connected if terminal_info else False
                        },
                        'account_info': {
                            'login': account_info.login if account_info else 'Unknown',
                            'server': account_info.server if account_info else 'Unknown',
                            'trade_allowed': account_info.trade_allowed if account_info else False,
                            'balance': account_info.balance if account_info else 0.0,
                            'equity': account_info.equity if account_info else 0.0
                        }
                    }
                    mt5.shutdown()
                    return info
            
            return {
                'terminal_info': {
                    'company': 'Unknown',
                    'name': 'MetaTrader 5', 
                    'path': terminal_path,
                    'build': 'Unknown',
                    'connected': False
                },
                'account_info': {
                    'login': 'Unknown',
                    'server': 'Unknown',
                    'trade_allowed': False,
                    'balance': 0.0,
                    'equity': 0.0
                }
            }
            
        except Exception as e:
            self.log(f"Error getting terminal info for {terminal_path}: {str(e)}", "ERROR")
            return {
                'terminal_info': {'company': 'Error', 'name': 'Error', 'path': terminal_path, 'build': 'Error', 'connected': False},
                'account_info': {'login': 'Error', 'server': 'Error', 'trade_allowed': False, 'balance': 0.0, 'equity': 0.0}
            }
    
    def connect_to_specific_terminal(self, terminal_path: str, max_retries: int = 3, retry_delay: float = 2.0) -> bool:
        """Connect to a specific MT5 terminal"""
        for attempt in range(max_retries):
            try:
                # Validate inputs
                if max_retries < 1:
                    raise ValidationError("max_retries must be at least 1")
                if retry_delay < 0:
                    raise ValidationError("retry_delay cannot be negative")
                
                self.log(f"Connecting to terminal: {terminal_path} (attempt {attempt + 1}/{max_retries})")
                
                # Initialize MT5 with specific terminal path if provided
                if terminal_path and terminal_path != 'default':
                    if not mt5.initialize(path=terminal_path):
                        error_code = mt5.last_error()
                        self.log(f"MT5 initialization failed for {terminal_path}: {error_code}", "ERROR")
                        if attempt < max_retries - 1:
                            self.log(f"Retrying in {retry_delay} seconds...")
                            time.sleep(retry_delay)
                            retry_delay *= 1.5
                            continue
                        return False
                else:
                    # Use default initialization
                    if not mt5.initialize():
                        error_code = mt5.last_error()
                        self.log(f"MT5 initialization failed: {error_code}", "ERROR")
                        if attempt < max_retries - 1:
                            self.log(f"Retrying in {retry_delay} seconds...")
                            time.sleep(retry_delay)
                            retry_delay *= 1.5
                            continue
                        return False
                
                # Validate connection with account info
                account_info = mt5.account_info()
                if account_info is None:
                    error_code = mt5.last_error()
                    self.log(f"Failed to get account info: {error_code}", "ERROR")
                    mt5.shutdown()
                    if attempt < max_retries - 1:
                        self.log(f"Retrying in {retry_delay} seconds...")
                        time.sleep(retry_delay)
                        retry_delay *= 1.5
                        continue
                    return False
                
                # Validate account state
                if account_info.trade_allowed is False:
                    self.log("Trading is not allowed on this account", "ERROR")
                    mt5.shutdown()
                    return False
                
                # Connection successful
                self.mt5_connected = True
                
                # Auto-detect filling type after connection
                try:
                    self.filling_type = self.detect_broker_filling_type()
                except Exception as e:
                    self.log(f"Warning: Could not detect filling type: {e}", "WARNING")
                    self.filling_type = mt5.ORDER_FILLING_IOC  # Safe default
                
                # Get terminal info for logging
                terminal_info = mt5.terminal_info()
                self.log(f"✅ Connected to MT5 Terminal - {terminal_info.name if terminal_info else 'Unknown'}")
                self.log(f"Account: {account_info.login}@{account_info.server}")
                self.log(f"Balance: ${account_info.balance:.2f}, Equity: ${account_info.equity:.2f}")
                self.log(f"Trade allowed: {account_info.trade_allowed}")
                
                # Initialize connection health tracking
                self.last_mt5_ping = datetime.now()
                self.connection_failures = 0
                
                return True
                
            except ValidationError as e:
                self.log(f"Validation error in MT5 connection: {e}", "ERROR")
                return False
            except Exception as e:
                self.log(f"MT5 connection error (attempt {attempt + 1}): {str(e)}", "ERROR")
                if attempt < max_retries - 1:
                    self.log(f"Retrying in {retry_delay} seconds...")
                    time.sleep(retry_delay)
                    retry_delay *= 1.5
                    continue
                
        self.log("All MT5 connection attempts failed", "ERROR")
        return False
    
    def check_mt5_connection_health(self) -> bool:
        """Check MT5 connection health with circuit breaker logic"""
        try:
            # If circuit breaker is open, check if timeout has passed
            if self.circuit_breaker_open:
                if (self.circuit_breaker_last_failure and 
                    (datetime.now() - self.circuit_breaker_last_failure).seconds >= self.circuit_breaker_timeout):
                    self.log("🔄 Circuit breaker timeout elapsed, attempting to close", "INFO")
                    self.circuit_breaker_open = False
                    self.connection_failures = 0
                else:
                    return False
            
            # Quick connection health check
            if not self.mt5_connected:
                return False
            
            # Ping MT5 by getting basic info
            account_info = mt5.account_info()
            if account_info is None:
                self.log("MT5 health check failed - no account info", "WARNING")
                self._handle_connection_failure()
                return False
            
            # Additional health checks
            terminal_info = mt5.terminal_info()
            if terminal_info is None:
                self.log("MT5 health check failed - no terminal info", "WARNING")
                self._handle_connection_failure()
                return False
            
            if not terminal_info.connected:
                self.log("MT5 terminal not connected to trade server", "WARNING")
                self._handle_connection_failure()
                return False
            
            # Health check passed
            self.last_mt5_ping = datetime.now()
            self.connection_failures = 0
            return True
            
        except Exception as e:
            self.log(f"MT5 health check error: {str(e)}", "ERROR")
            self._handle_connection_failure()
            return False
    
    def _handle_connection_failure(self):
        """Handle connection failure with circuit breaker logic"""
        self.connection_failures += 1
        self.log(f"Connection failure #{self.connection_failures}", "WARNING")
        
        if self.circuit_breaker_enabled and self.connection_failures >= self.circuit_breaker_threshold:
            self.circuit_breaker_open = True
            self.circuit_breaker_last_failure = datetime.now()
            self.mt5_connected = False
            self.log(f"🚨 Circuit breaker OPEN - too many failures ({self.connection_failures})", "ERROR")
            self.log(f"Will retry after {self.circuit_breaker_timeout} seconds")
    
    def attempt_mt5_reconnection(self) -> bool:
        """Attempt to reconnect to MT5 with circuit breaker protection"""
        if self.circuit_breaker_open:
            self.log("Circuit breaker is open, cannot reconnect yet", "WARNING")
            return False
        
        self.log("🔄 Attempting MT5 reconnection...")
        self.mt5_connected = False
        
        # Try to shutdown first in case of partial connection
        try:
            mt5.shutdown()
        except:
            pass
        
        success = self.connect_mt5()
        if success:
            self.log("✅ MT5 reconnection successful")
            self.connection_failures = 0
        else:
            self.log("❌ MT5 reconnection failed")
            self._handle_connection_failure()
        
        return success

    def disconnect_mt5(self):
        """Disconnect from MetaTrader 5 and save state"""
        if self.trading_active:
            self.trading_active = False
            time.sleep(2)  # รอให้ loop หยุด
        
        if self.mt5_connected:
            # Save state ก่อนปิด
            self.save_trading_state()
            mt5.shutdown()
            self.mt5_connected = False
            self.log("💾 State saved and disconnected from MT5")

    def optimize_trading_parameters(self):
        """ปรับพารามิเตอร์แบบ adaptive"""
        try:
            # วิเคราะห์ performance ล่าสุด
            if self.total_signals >= 20:  # มีข้อมูลพอ
                success_rate = self.successful_signals / self.total_signals
                
                # ปรับ signal cooldown
                if success_rate > 0.8:
                    self.signal_cooldown = max(30, self.signal_cooldown - 5)  # เร็วขึ้น
                elif success_rate < 0.5:
                    self.signal_cooldown = min(120, self.signal_cooldown + 10)  # ช้าลง
                
                # ปรับ profit targets
                avg_profit = self.redirect_profit_captured / max(1, self.successful_redirects)
                if avg_profit > 50:
                    self.profit_harvest_threshold_percent *= 1.1  # เป้าสูงขึ้น
                elif avg_profit < 20:
                    self.profit_harvest_threshold_percent *= 0.9  # เป้าต่ำลง
                
                self.log(f"🎛️ Parameters optimized: Success rate {success_rate:.1%}")
                
        except Exception as e:
            self.log(f"Error optimizing parameters: {str(e)}", "ERROR")

    def enhanced_risk_management(self):
        """การจัดการความเสี่ยงขั้นสูง - Enhanced with Position Risk Monitoring"""
        try:
            account_info = mt5.account_info()
            if not account_info:
                return
            
            # 1. Dynamic position size based on account equity (ใช้ %)
            equity = account_info.equity
            equity_percentage = equity / 10000  # Normalize to 10k base
            
            if equity_percentage < 0.1:  # < 1k
                self.base_lot = 0.01
            elif equity_percentage < 0.5:  # < 5k
                self.base_lot = 0.02
            elif equity_percentage < 1.0:  # < 10k
                self.base_lot = 0.03
            else:
                self.base_lot = min(0.05, equity_percentage * 0.05)  # Max 0.05 lots
            
            # 2. Drawdown protection (ใช้ %)
            balance = account_info.balance
            current_drawdown = (balance - equity) / balance * 100 if balance > 0 else 0
            
            if current_drawdown > 20:  # 20% drawdown
                self.trading_active = False
                self.log("🚨 EMERGENCY STOP: 20% drawdown reached", "ERROR")
            elif current_drawdown > 10:  # 10% drawdown - reduce activity
                self.max_signals_per_hour = 20
                self.signal_cooldown = 120
                self.log("⚠️ Risk mode: Reduced trading activity", "WARNING")
            
            # 3. Margin level protection (ใช้ %)
            if account_info.margin > 0:
                margin_level = (equity / account_info.margin) * 100
                if margin_level < 150:
                    self.gentle_management = False  # Aggressive closing
                    self.log("⚠️ Low margin: Activating aggressive management", "WARNING")
            
            # 🆕 4. Position Risk Monitoring (ใหม่)
            if self.positions:
                position_risk_analysis = self.monitor_position_risk()
                if position_risk_analysis.get('high_risk_count', 0) > 0:
                    self.log(f"⚠️ Position Risk Alert: {position_risk_analysis['high_risk_count']} high-risk positions detected", "WARNING")
                    
                    # ตรวจสอบว่าต้องการ immediate action หรือไม่
                    if position_risk_analysis.get('total_risk_score', 0) > 70:
                        self.log("🚨 HIGH RISK: Activating emergency position management", "ERROR")
                        self.activate_emergency_position_management()
                
        except Exception as e:
            self.log(f"Error in enhanced risk management: {str(e)}", "ERROR")

    def monitor_position_risk(self) -> dict:
        """🎯 ติดตามความเสี่ยงของ positions แบบ real-time ใช้ %"""
        try:
            risk_analysis = {
                'high_risk_positions': [],
                'medium_risk_positions': [],
                'low_risk_positions': [],
                'total_risk_score': 0.0,
                'high_risk_count': 0,
                'medium_risk_count': 0,
                'low_risk_count': 0,
                'recommendations': []
            }
            
            if not self.positions:
                return risk_analysis
            
            current_price = self.get_current_price()
            total_portfolio_value = self.get_portfolio_value()
            
            if current_price <= 0 or total_portfolio_value <= 0:
                return risk_analysis
            
            for position in self.positions:
                # 1. คำนวณ % loss จาก entry price
                if position.open_price > 0:
                    price_loss_percentage = ((current_price - position.open_price) / position.open_price) * 100
                    if position.type == 'SELL':
                        price_loss_percentage = -price_loss_percentage  # SELL = ราคาลง = loss
                else:
                    price_loss_percentage = 0
                
                # 2. คำนวณ % loss จาก portfolio value
                portfolio_loss_percentage = (position.profit / total_portfolio_value) * 100
                
                # 3. คำนวณระยะห่างจากตลาด (%)
                distance_percentage = abs(current_price - position.open_price) / current_price * 100
                
                # 4. วิเคราะห์ความเสี่ยง
                risk_level = self._analyze_position_risk_level(
                    position, price_loss_percentage, portfolio_loss_percentage, distance_percentage
                )
                
                # 5. คำนวณ risk score
                risk_score = self._calculate_position_risk_score(
                    position, portfolio_loss_percentage, price_loss_percentage
                )
                
                risk_item = {
                    'position': position,
                    'price_loss_percentage': price_loss_percentage,
                    'portfolio_loss_percentage': portfolio_loss_percentage,
                    'distance_percentage': distance_percentage,
                    'risk_score': risk_score,
                    'risk_level': risk_level
                }
                
                if risk_level == 'HIGH':
                    risk_analysis['high_risk_positions'].append(risk_item)
                    risk_analysis['high_risk_count'] += 1
                elif risk_level == 'MEDIUM':
                    risk_analysis['medium_risk_positions'].append(risk_item)
                    risk_analysis['medium_risk_count'] += 1
                else:
                    risk_analysis['low_risk_positions'].append(risk_item)
                    risk_analysis['low_risk_count'] += 1
            
            # 6. คำนวณ total risk score
            risk_analysis['total_risk_score'] = self._calculate_total_risk_score(risk_analysis)
            
            # 7. สร้าง recommendations
            risk_analysis['recommendations'] = self._generate_risk_recommendations(risk_analysis)
            
            return risk_analysis
            
        except Exception as e:
            self.log(f"Error in position risk monitoring: {str(e)}", "ERROR")
            return {'error': str(e)}

    def _analyze_position_risk_level(self, position, price_loss_percentage: float, portfolio_loss_percentage: float, distance_percentage: float) -> str:
        """🧠 วิเคราะห์ระดับความเสี่ยงของ position แบบ %"""
        
        # 1. Loss Percentage Thresholds (ใช้ % แทน fix values)
        high_loss_threshold = -3.0      # ติดลบมากกว่า 3%
        medium_loss_threshold = -1.5    # ติดลบมากกว่า 1.5%
        
        # 2. Portfolio Loss Percentage Thresholds
        high_portfolio_loss_threshold = -2.0    # ติดลบมากกว่า 2% ของ portfolio
        medium_portfolio_loss_threshold = -1.0  # ติดลบมากกว่า 1% ของ portfolio
        
        # 3. Distance from Market Thresholds (ใช้ % แทน fix points)
        high_distance_threshold = 2.0   # ห่างจากตลาดมากกว่า 2%
        medium_distance_threshold = 1.0 # ห่างจากตลาดมากกว่า 1%
        
        # 4. วิเคราะห์ความเสี่ยง
        risk_factors = 0
        
        # Loss percentage
        if price_loss_percentage < high_loss_threshold:
            risk_factors += 3
        elif price_loss_percentage < medium_loss_threshold:
            risk_factors += 2
        elif price_loss_percentage < 0:
            risk_factors += 1
        
        # Portfolio loss percentage
        if portfolio_loss_percentage < high_portfolio_loss_threshold:
            risk_factors += 3
        elif portfolio_loss_percentage < medium_portfolio_loss_threshold:
            risk_factors += 2
        elif portfolio_loss_percentage < 0:
            risk_factors += 1
        
        # Distance from market
        if distance_percentage > high_distance_threshold:
            risk_factors += 2
        elif distance_percentage > medium_distance_threshold:
            risk_factors += 1
        
        # Position age (ไม้ใหม่ไม่เสี่ยง)
        if hasattr(position, 'open_time'):
            position_age = (datetime.now() - position.open_time).total_seconds() / 60  # นาที
            if position_age < 5:  # ไม้ใหม่ (น้อยกว่า 5 นาที)
                risk_factors = max(0, risk_factors - 2)  # ลดความเสี่ยง
        
        # ตัดสินใจความเสี่ยง
        if risk_factors >= 6:
            return 'HIGH'
        elif risk_factors >= 3:
            return 'MEDIUM'
        else:
            return 'LOW'

    def _calculate_position_risk_score(self, position, portfolio_loss_percentage: float, price_loss_percentage: float) -> float:
        """📊 คำนวณ risk score ของ position (0-100)"""
        
        try:
            score = 0.0
            
            # 1. Portfolio Loss Score (40 points)
            if portfolio_loss_percentage < 0:
                score += min(40, abs(portfolio_loss_percentage) * 20)  # 1% = 20 points
            
            # 2. Price Loss Score (30 points)
            if price_loss_percentage < 0:
                score += min(30, abs(price_loss_percentage) * 10)  # 1% = 10 points
            
            # 3. Position Age Score (20 points)
            if hasattr(position, 'open_time'):
                position_age = (datetime.now() - position.open_time).total_seconds() / 60  # นาที
                if position_age > 60:  # ไม้เก่า (มากกว่า 1 ชั่วโมง)
                    score += 20
                elif position_age > 30:  # ไม้ปานกลาง (มากกว่า 30 นาที)
                    score += 10
                # ไม้ใหม่ (น้อยกว่า 30 นาที) = 0 points
            
            # 4. Volume Score (10 points)
            if hasattr(position, 'volume'):
                if position.volume > 0.05:  # ไม้ใหญ่
                    score += 10
                elif position.volume > 0.02:  # ไม้ปานกลาง
                    score += 5
                # ไม้เล็ก = 0 points
            
            return min(100.0, max(0.0, score))
            
        except Exception as e:
            self.log(f"Error calculating position risk score: {str(e)}", "ERROR")
            return 50.0

    def _calculate_total_risk_score(self, risk_analysis: dict) -> float:
        """📊 คำนวณ total risk score ของ portfolio"""
        
        try:
            high_risk_count = risk_analysis.get('high_risk_count', 0)
            medium_risk_count = risk_analysis.get('medium_risk_count', 0)
            low_risk_count = risk_analysis.get('low_risk_count', 0)
            
            # คำนวณ weighted risk score
            high_risk_weight = 3.0    # High risk = 3x
            medium_risk_weight = 1.5  # Medium risk = 1.5x
            low_risk_weight = 0.5     # Low risk = 0.5x
            
            total_positions = high_risk_count + medium_risk_count + low_risk_count
            if total_positions == 0:
                return 0.0
            
            weighted_score = (
                (high_risk_count * high_risk_weight) +
                (medium_risk_count * medium_risk_weight) +
                (low_risk_count * low_risk_weight)
            ) / total_positions
            
            # แปลงเป็น 0-100 scale
            normalized_score = min(100.0, weighted_score * 20)
            
            return normalized_score
            
        except Exception as e:
            self.log(f"Error calculating total risk score: {str(e)}", "ERROR")
            return 50.0

    def _generate_risk_recommendations(self, risk_analysis: dict) -> list:
        """💡 สร้างคำแนะนำตาม risk analysis"""
        
        recommendations = []
        total_risk_score = risk_analysis.get('total_risk_score', 0)
        high_risk_count = risk_analysis.get('high_risk_count', 0)
        
        if total_risk_score > 80:
            recommendations.append("🚨 EMERGENCY: Portfolio at extreme risk - immediate action required")
            recommendations.append("🛡️ Close high-risk positions immediately")
            recommendations.append("⏸️ Stop opening new positions")
        elif total_risk_score > 60:
            recommendations.append("⚠️ HIGH RISK: Portfolio needs immediate attention")
            recommendations.append("🎯 Focus on closing high-risk positions")
            recommendations.append("📊 Review position sizing strategy")
        elif total_risk_score > 40:
            recommendations.append("🟡 MEDIUM RISK: Monitor closely")
            recommendations.append("🔍 Watch for worsening conditions")
            recommendations.append("📈 Consider reducing exposure")
        elif total_risk_score > 20:
            recommendations.append("🟢 LOW RISK: Portfolio is healthy")
            recommendations.append("✅ Continue normal operations")
            recommendations.append("📊 Regular monitoring recommended")
        else:
            recommendations.append("🟢 VERY LOW RISK: Portfolio is excellent")
            recommendations.append("✅ Optimal conditions")
            recommendations.append("🚀 Consider increasing exposure")
        
        if high_risk_count > 0:
            recommendations.append(f"🎯 Priority: Close {high_risk_count} high-risk positions")
        
        return recommendations

    def activate_emergency_position_management(self):
        """🚨 เปิดใช้งาน Emergency Position Management"""
        try:
            self.log("🚨 ACTIVATING EMERGENCY POSITION MANAGEMENT", "ERROR")
            
            # 1. หาไม้ที่เสี่ยงมากที่สุด
            risk_analysis = self.monitor_position_risk()
            high_risk_positions = risk_analysis.get('high_risk_positions', [])
            
            if not high_risk_positions:
                self.log("✅ No high-risk positions found", "INFO")
                return
            
            # 2. เรียงตาม risk score (เสี่ยงมากที่สุดก่อน)
            high_risk_positions.sort(key=lambda x: x['risk_score'], reverse=True)
            
            # 3. ปิดไม้ที่เสี่ยงมากที่สุด 3 ตัวแรก
            positions_to_close = high_risk_positions[:3]
            
            self.log(f"🚨 Emergency Closing: {len(positions_to_close)} high-risk positions", "ERROR")
            
            for risk_item in positions_to_close:
                position = risk_item['position']
                risk_score = risk_item['risk_score']
                
                self.log(f"🚨 Emergency Closing Position {position.ticket}: Risk Score {risk_score:.1f}", "ERROR")
                
                # ปิด position
                if hasattr(self, 'close_position_smart'):
                    close_result = self.close_position_smart(position.ticket)
                    if close_result.get('success'):
                        self.log(f"✅ Emergency Closed Position {position.ticket}", "SUCCESS")
                    else:
                        self.log(f"❌ Failed to Emergency Close Position {position.ticket}", "ERROR")
            
            # 4. ปรับ trading parameters
            self.max_signals_per_hour = 5  # ลดการเปิดไม้ใหม่
            self.signal_cooldown = 300     # เพิ่ม cooldown
            
            self.log("🚨 Emergency Position Management: Trading parameters adjusted", "WARNING")
            
        except Exception as e:
            self.log(f"Error in emergency position management: {str(e)}", "ERROR")

    def get_portfolio_value(self) -> float:
        """💰 คำนวณ portfolio value รวม"""
        try:
            if not self.positions:
                return 0.0
            
            # ใช้ balance + total profit/loss
            if hasattr(self, 'get_account_info'):
                account_info = self.get_account_info()
                balance = account_info.get('balance', 0.0)
                total_profit = sum(p.profit for p in self.positions)
                return balance + total_profit
            else:
                # Fallback: ใช้ total profit/loss เท่านั้น
                total_profit = sum(p.profit for p in self.positions)
                return max(1000.0, abs(total_profit) * 10)  # Estimate
            
        except Exception as e:
            self.log(f"Error calculating portfolio value: {str(e)}", "ERROR")
            return 1000.0  # Default value

    def get_current_price(self) -> float:
        """📊 รับราคาปัจจุบันของ market"""
        try:
            if MT5_AVAILABLE and mt5 and self.mt5_connected:
                tick = mt5.symbol_info_tick(self.symbol)
                if tick:
                    return (tick.bid + tick.ask) / 2  # Average price
            
            # Fallback: ใช้ราคาเฉลี่ยของ positions
            if self.positions:
                return sum(p.current_price for p in self.positions) / len(self.positions)
            
            return 3500.0  # Default price for XAUUSD
            
        except Exception as e:
            self.log(f"Error getting current price: {str(e)}", "ERROR")
            return 3500.0  # Default price

    def calculate_market_volatility(self, df: DataFrame) -> float:
        """Calculate recent market volatility"""
        if df is None or len(df) < 5:
            return 1.0
            
        try:
            # คำนวณ ATR (Average True Range) แบบง่าย
            df['tr1'] = df['high'] - df['low']
            df['tr2'] = abs(df['high'] - df['close'].shift(1))
            df['tr3'] = abs(df['low'] - df['close'].shift(1))
            df['true_range'] = df[['tr1', 'tr2', 'tr3']].max(axis=1)
            
            # ATR ช่วง 5 periods
            atr = df['true_range'].tail(5).mean()
            
            # Normalize ATR (สำหรับ XAUUSD)
            volatility = atr / 10.0  # ปรับค่าให้เหมาะสม
            
            return max(0.2, min(5.0, volatility))
            
        except Exception as e:
            self.log(f"Error calculating volatility: {str(e)}", "ERROR")
            return 1.0

    def get_market_data(self) -> Optional[DataFrame]:
        """Get recent market data for analysis"""
        if not self.mt5_connected:
            return None
            
        try:
            # Get last 15 M5 candles (เพิ่มจาก 10)
            rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M5, 0, 15)
            if rates is None or len(rates) < 5:
                return None
                
            df = pd.DataFrame(rates)
            df['time'] = pd.to_datetime(df['time'], unit='s')
            
            # Calculate candle properties
            df['body'] = abs(df['close'] - df['open'])
            df['total_range'] = df['high'] - df['low']
            df['body_ratio'] = df['body'] / df['total_range'] * 100
            df['is_green'] = df['close'] > df['open']
            df['movement'] = abs(df['close'] - df['open'])
            
            # คำนวณและเก็บ volatility
            self.recent_volatility = self.calculate_market_volatility(df)
            
            return df
            
        except Exception as e:
            self.log(f"Error getting market data: {str(e)}", "ERROR")
            return None

    def analyze_volume_pattern(self, df: DataFrame) -> Dict[str, Any]:
        """📊 วิเคราะห์รูปแบบปริมาณการซื้อขาย"""
        try:
            if df is None or len(df) < 5:
                return {'pattern': 'INSUFFICIENT_DATA', 'strength': 0.0, 'trend': 'NEUTRAL'}
            
            # คำนวณ volume indicators
            recent_volume = df['tick_volume'].tail(5).mean()
            avg_volume = df['tick_volume'].mean() if len(df) > 10 else recent_volume
            
            # วิเคราะห์รูปแบบ volume
            volume_trend = 'INCREASING' if recent_volume > avg_volume * 1.2 else 'DECREASING' if recent_volume < avg_volume * 0.8 else 'STABLE'
            
            # คำนวณความแรงของ pattern
            strength = min(1.0, abs(recent_volume - avg_volume) / avg_volume)
            
            return {
                'pattern': f'VOLUME_{volume_trend}',
                'strength': strength,
                'trend': volume_trend,
                'recent_avg': recent_volume,
                'historical_avg': avg_volume
            }
            
        except Exception as e:
            self.log(f"Error analyzing volume pattern: {str(e)}", "ERROR")
            return {'pattern': 'ERROR', 'strength': 0.0, 'trend': 'NEUTRAL'}

    def detect_sr_levels(self, df: DataFrame) -> Dict[str, Any]:
        """🎯 ตรวจหา Support/Resistance levels"""
        try:
            if df is None or len(df) < 10:
                return {'support_levels': [], 'resistance_levels': [], 'current_bias': 'NEUTRAL'}
            
            # หา local highs และ lows
            highs = []
            lows = []
            
            for i in range(2, len(df) - 2):
                # Local high
                if (df.iloc[i]['high'] > df.iloc[i-1]['high'] and 
                    df.iloc[i]['high'] > df.iloc[i+1]['high'] and
                    df.iloc[i]['high'] > df.iloc[i-2]['high'] and 
                    df.iloc[i]['high'] > df.iloc[i+2]['high']):
                    highs.append(df.iloc[i]['high'])
                
                # Local low
                if (df.iloc[i]['low'] < df.iloc[i-1]['low'] and 
                    df.iloc[i]['low'] < df.iloc[i+1]['low'] and
                    df.iloc[i]['low'] < df.iloc[i-2]['low'] and 
                    df.iloc[i]['low'] < df.iloc[i+2]['low']):
                    lows.append(df.iloc[i]['low'])
            
            # กรอง levels ที่ใกล้เคียงกัน
            current_price = df.iloc[-1]['close']
            proximity_threshold = 0.5  # 0.5 points for XAUUSD
            
            resistance_levels = []
            support_levels = []
            
            for high in highs:
                if high > current_price and not any(abs(high - r) < proximity_threshold for r in resistance_levels):
                    resistance_levels.append(high)
                    
            for low in lows:
                if low < current_price and not any(abs(low - s) < proximity_threshold for s in support_levels):
                    support_levels.append(low)
            
            # จำกัดจำนวน levels
            resistance_levels = sorted(resistance_levels)[:3]
            support_levels = sorted(support_levels, reverse=True)[:3]
            
            # กำหนด bias
            bias = 'NEUTRAL'
            if resistance_levels and support_levels:
                if len(resistance_levels) > len(support_levels):
                    bias = 'BEARISH'
                elif len(support_levels) > len(resistance_levels):
                    bias = 'BULLISH'
            
            return {
                'support_levels': support_levels,
                'resistance_levels': resistance_levels,
                'current_bias': bias,
                'current_price': current_price
            }
            
        except Exception as e:
            self.log(f"Error detecting S/R levels: {str(e)}", "ERROR")
            return {'support_levels': [], 'resistance_levels': [], 'current_bias': 'NEUTRAL'}

    def calculate_market_sentiment(self, df: DataFrame) -> float:
        """🧠 คำนวณ sentiment ของตลาด (0.0-1.0)"""
        try:
            if df is None or len(df) < 5:
                return 0.5  # Neutral sentiment
            
            sentiment_score = 0.5  # เริ่มต้นที่ neutral
            
            # 1. Price momentum (30% weight)
            recent_close = df.iloc[-1]['close']
            previous_close = df.iloc[-5]['close'] if len(df) >= 5 else df.iloc[0]['close']
            price_change = (recent_close - previous_close) / previous_close
            momentum_score = 0.5 + (price_change * 10)  # Scale to 0-1
            momentum_score = max(0.0, min(1.0, momentum_score))
            
            # 2. Candle patterns (25% weight)
            green_count = df.tail(5)['is_green'].sum()
            pattern_score = green_count / 5.0
            
            # 3. Volume confirmation (20% weight)
            volume_data = self.analyze_volume_pattern(df)
            volume_score = 0.5
            if volume_data['trend'] == 'INCREASING':
                volume_score = 0.7
            elif volume_data['trend'] == 'DECREASING':
                volume_score = 0.3
            
            # 4. Volatility factor (15% weight)
            volatility = self.calculate_market_volatility(df)
            volatility_score = min(1.0, volatility / 2.0)  # Higher volatility = more bullish potential
            
            # 5. Recent body strength (10% weight)
            avg_body_ratio = df.tail(3)['body_ratio'].mean()
            body_score = min(1.0, avg_body_ratio / 10.0)  # Strong bodies = more directional
            
            # Weighted combination
            sentiment_score = (
                momentum_score * 0.30 +
                pattern_score * 0.25 +
                volume_score * 0.20 +
                volatility_score * 0.15 +
                body_score * 0.10
            )
            
            return max(0.0, min(1.0, sentiment_score))
            
        except Exception as e:
            self.log(f"Error calculating market sentiment: {str(e)}", "ERROR")
            return 0.5  # Return neutral on error

    def analyze_real_time_sentiment(self) -> Dict[str, Any]:
        """วิเคราะห์ sentiment แบบ real-time"""
        try:
            sentiment = {
                'direction': 'NEUTRAL',
                'strength': 0.5,
                'confidence': 0.5,
                'recommendation': 'HOLD',
                'factors': []
            }
            
            market_data = self.get_market_data()
            if market_data is None:
                return sentiment
            
            # Multi-timeframe analysis
            short_term = market_data.tail(3)  # Last 3 candles
            medium_term = market_data.tail(7)  # Last 7 candles
            
            # Factor 1: Short-term momentum
            short_green_ratio = short_term['is_green'].sum() / 3
            if short_green_ratio >= 0.67:
                sentiment['factors'].append("Short-term bullish momentum")
                sentiment['strength'] += 0.2
            elif short_green_ratio <= 0.33:
                sentiment['factors'].append("Short-term bearish momentum")
                sentiment['strength'] += 0.2
            
            # Factor 2: Medium-term trend
            medium_green_ratio = medium_term['is_green'].sum() / 7
            if medium_green_ratio >= 0.6:
                sentiment['factors'].append("Medium-term uptrend")
                sentiment['strength'] += 0.15
            elif medium_green_ratio <= 0.4:
                sentiment['factors'].append("Medium-term downtrend")
                sentiment['strength'] += 0.15
            
            # Factor 3: Volume/Body analysis
            avg_body_ratio = short_term['body_ratio'].mean()
            if avg_body_ratio > 15:
                sentiment['factors'].append("Strong candle bodies")
                sentiment['confidence'] += 0.2
            
            # Factor 4: Price movement
            avg_movement = short_term['movement'].mean()
            if avg_movement > 0.5:
                sentiment['factors'].append("High price movement")
                sentiment['confidence'] += 0.15
            
            # Determine final direction
            if short_green_ratio > 0.6 and medium_green_ratio > 0.5:
                sentiment['direction'] = 'BULLISH'
                sentiment['recommendation'] = 'BUY_BIAS'
            elif short_green_ratio < 0.4 and medium_green_ratio < 0.5:
                sentiment['direction'] = 'BEARISH'
                sentiment['recommendation'] = 'SELL_BIAS'
            
            # Limit values
            sentiment['strength'] = min(1.0, sentiment['strength'])
            sentiment['confidence'] = min(1.0, sentiment['confidence'])
            
            return sentiment
            
        except Exception as e:
            self.log(f"Error analyzing sentiment: {str(e)}", "ERROR")
            return sentiment

    def analyze_portfolio_exposure(self) -> Dict:
        """🛡️ วิเคราะห์ระดับ exposure ของ portfolio"""
        try:
            analysis = {
                'total_exposure_pips': 0,
                'max_distance_buy': 0,
                'max_distance_sell': 0,
                'exposure_level': 'LOW',
                'needs_hedge': False,
                'recommended_hedge': None,
                'risk_score': 0
            }
            
            if not self.positions:
                return analysis
            
            # ดึงราคาปัจจุบัน
            current_tick = mt5.symbol_info_tick(self.symbol)
            if not current_tick:
                return analysis
            
            current_price = (current_tick.bid + current_tick.ask) / 2
            
            buy_positions = [p for p in self.positions if p.type == "BUY"]
            sell_positions = [p for p in self.positions if p.type == "SELL"]
            
            # คำนวณระยะห่างของ BUY positions
            buy_distances = []
            for pos in buy_positions:
                distance_pips = (current_price - pos.open_price) * 100
                buy_distances.append(distance_pips)
            
            # คำนวณระยะห่างของ SELL positions
            sell_distances = []
            for pos in sell_positions:
                distance_pips = (pos.open_price - current_price) * 100
                sell_distances.append(distance_pips)
            
            # คำนวณค่าต่างๆ
            if buy_distances:
                analysis['max_distance_buy'] = max(buy_distances)
            
            if sell_distances:
                analysis['max_distance_sell'] = max(sell_distances)
            
            # คำนวณ total exposure
            max_buy_distance = abs(analysis['max_distance_buy'])
            max_sell_distance = abs(analysis['max_distance_sell'])
            analysis['total_exposure_pips'] = max_buy_distance + max_sell_distance
            
            # ประเมิน exposure level
            if analysis['total_exposure_pips'] > 300:
                analysis['exposure_level'] = 'CRITICAL'
                analysis['risk_score'] = 90
            elif analysis['total_exposure_pips'] > 200:
                analysis['exposure_level'] = 'HIGH'
                analysis['risk_score'] = 70
            elif analysis['total_exposure_pips'] > 100:
                analysis['exposure_level'] = 'MEDIUM'
                analysis['risk_score'] = 40
            else:
                analysis['exposure_level'] = 'LOW'
                analysis['risk_score'] = 20
            
            # ตรวจสอบว่าต้องการ hedge หรือไม่
            analysis['needs_hedge'] = (
                analysis['total_exposure_pips'] > self.hedge_trigger_distance or
                max_buy_distance > self.max_exposure_distance or
                max_sell_distance > self.max_exposure_distance
            )
            
            return analysis
            
        except Exception as e:
            self.log(f"Error analyzing portfolio exposure: {str(e)}", "ERROR")
            return analysis

    def analyze_mini_trend(self, df: DataFrame) -> Optional[Signal]:
        """Analyze mini trend and generate signals with new conditions"""
        if df is None or len(df) < 3:
            return None
            
        try:
            # Get last 3 candles
            last_3 = df.tail(3)
            current_candle = last_3.iloc[-1]  # แท่งปัจจุบัน
            current_price = current_candle['close']
            
            # Count green/red candles
            green_count = last_3['is_green'].sum()
            red_count = 3 - green_count
            
            # Check minimum requirements
            min_body_ratio = 5.0  # 5%
            min_movement = 0.2    # 0.2 points (20 pips)
            
            # Calculate signal strength based on various factors
            avg_body_ratio = last_3['body_ratio'].mean()
            avg_movement = last_3['movement'].mean()
            
            strength = 1.0
            if avg_body_ratio > 10:
                strength += 0.3
            if avg_movement > 0.5:
                strength += 0.4
            if avg_movement > 1.0:
                strength += 0.3
                
            strength = min(3.0, max(0.5, strength))
            
            # 🟢 BUY signal conditions - NEW LOGIC
            if (green_count >= 2 and 
                avg_body_ratio >= min_body_ratio and 
                avg_movement >= min_movement and
                current_candle['is_green']):  # แท่งปัจจุบันต้องเป็นสีเขียว
                
                return Signal(
                    timestamp=datetime.now(),
                    symbol=self.symbol,
                    direction='BUY',
                    strength=strength,
                    reason=f"🟢 Green {green_count}/3 + Current Green, Body: {avg_body_ratio:.1f}%, Move: {avg_movement:.2f}",
                    price=current_price
                )
            
            # 🔴 SELL signal conditions - NEW LOGIC
            elif (red_count >= 2 and 
                  avg_body_ratio >= min_body_ratio and 
                  avg_movement >= min_movement and
                  not current_candle['is_green']):  # แท่งปัจจุบันต้องเป็นสีแดง
                
                return Signal(
                    timestamp=datetime.now(),
                    symbol=self.symbol,
                    direction='SELL',
                    strength=strength,
                    reason=f"🔴 Red {red_count}/3 + Current Red, Body: {avg_body_ratio:.1f}%, Move: {avg_movement:.2f}",
                    price=current_price
                )
            
            return None
            
        except Exception as e:
            self.log(f"Error analyzing trend: {str(e)}", "ERROR")
            return None

    def analyze_advanced_market_patterns(self, df: DataFrame) -> Optional[Signal]:
        """วิเคราะห์ pattern ขั้นสูงด้วย AI-inspired techniques"""
        if df is None or len(df) < 10:
            return None
        
        try:
            # เพิ่มตัววิเคราะห์ขั้นสูง
            patterns = {
                'trend_strength': self.calculate_trend_strength(df),
                'momentum_score': self.calculate_momentum_score(df),
                'volume_pattern': self.analyze_volume_pattern(df),
                'support_resistance': self.detect_sr_levels(df),
                'market_sentiment': self.calculate_market_sentiment(df)
            }
            
            # AI-inspired scoring
            signal_confidence = self.calculate_ai_confidence(patterns)
            
            if signal_confidence['should_trade']:
                return Signal(
                    timestamp=datetime.now(),
                    symbol=self.symbol,
                    direction=signal_confidence['direction'],
                    strength=signal_confidence['strength'],
                    reason=f"🤖 AI Pattern: {signal_confidence['pattern_name']} (Conf: {signal_confidence['confidence']:.1%})",
                    price=df.iloc[-1]['close']
                )
            
            return None
            
        except Exception as e:
            self.log(f"Error in advanced analysis: {str(e)}", "ERROR")
            return None

    def calculate_trend_strength(self, df: DataFrame) -> float:
        """คำนวณความแรงของ trend"""
        try:
            last_10 = df.tail(10)
            
            # Linear regression slope
            x = np.arange(len(last_10))
            y = last_10['close'].values
            slope = np.polyfit(x, y, 1)[0]
            
            # Normalize slope to 0-1 scale
            price_range = last_10['close'].max() - last_10['close'].min()
            trend_strength = abs(slope) / (price_range / len(last_10)) if price_range > 0 else 0
            
            return min(1.0, trend_strength)
            
        except Exception as e:
            return 0.5

    def calculate_momentum_score(self, df: DataFrame) -> float:
        """คำนวณ momentum ด้วย RSI-inspired method"""
        try:
            last_10 = df.tail(10)
            
            # Calculate price changes
            price_changes = last_10['close'].diff().dropna()
            
            # Separate gains and losses
            gains = price_changes.where(price_changes > 0, 0)
            losses = -price_changes.where(price_changes < 0, 0)
            
            # Calculate average gains and losses
            avg_gain = gains.mean()
            avg_loss = losses.mean()
            
            # RSI-like calculation
            if avg_loss == 0:
                return 1.0
            
            rs = avg_gain / avg_loss
            momentum = rs / (1 + rs)
            
            return momentum
            
        except Exception as e:
            return 0.5

    def calculate_ai_confidence(self, patterns: dict) -> dict:
        """คำนวณความเชื่อมั่นแบบ AI"""
        try:
            confidence_score = 0.0
            direction_votes = {'BUY': 0, 'SELL': 0}
            
            # Trend analysis
            trend_strength = patterns['trend_strength']
            if trend_strength > 0.7:
                confidence_score += 0.3
                direction_votes['BUY'] += trend_strength
            elif trend_strength < 0.3:
                confidence_score += 0.3
                direction_votes['SELL'] += (1 - trend_strength)
            
            # Momentum analysis
            momentum = patterns['momentum_score']
            if momentum > 0.6:
                confidence_score += 0.25
                direction_votes['BUY'] += momentum
            elif momentum < 0.4:
                confidence_score += 0.25
                direction_votes['SELL'] += (1 - momentum)
            
            # Market sentiment
            sentiment = patterns['market_sentiment']
            if abs(sentiment - 0.5) > 0.2:
                confidence_score += 0.2
                if sentiment > 0.5:
                    direction_votes['BUY'] += sentiment
                else:
                    direction_votes['SELL'] += (1 - sentiment)
            
            # Pattern recognition bonus
            if confidence_score > 0.6:
                confidence_score += 0.15
            
            # Determine direction
            direction = 'BUY' if direction_votes['BUY'] > direction_votes['SELL'] else 'SELL'
            
            return {
                'should_trade': confidence_score > 0.65,
                'confidence': confidence_score,
                'direction': direction,
                'strength': min(3.0, max(0.5, confidence_score * 4)),
                'pattern_name': f"Multi-Pattern-{confidence_score:.2f}"
            }
            
        except Exception as e:
            return {'should_trade': False, 'confidence': 0.0}

    def calculate_dynamic_lot_size(self, signal: Signal) -> float:
        """Calculate enhanced dynamic lot size with zone-based risk management"""
        try:
            # 1. Base lot จาก signal strength
            base_lot = self.base_lot_size * signal.strength if hasattr(signal, 'strength') else self.base_lot_size
            
            # 2. Account equity adjustment (if MT5 available)
            if MT5_AVAILABLE and mt5 and self.mt5_connected:
                account_info = mt5.account_info()
                if account_info and self.equity_based_sizing:
                    equity = account_info.equity
                    
                    # Risk per trade = 1-3% ของ equity ตาม signal strength
                    signal_strength = getattr(signal, 'strength', 1.0)
                    risk_percent = 0.01 + (signal_strength - 0.5) * 0.008  # 1%-3%
                    risk_amount = equity * risk_percent
                    
                    # คำนวณ lot จาก risk amount (สมมติ stop loss 50 pips)
                    pip_value = 1.0  # XAUUSD 1 pip = $1 per 0.01 lot
                    stop_loss_pips = 50
                    lot_from_risk = risk_amount / (stop_loss_pips * pip_value * 100)
                    
                    base_lot = min(base_lot, lot_from_risk)
            
            # 🎯 3. Zone-Based Risk Adjustment
            zone_risk_factor = self.calculate_zone_risk_factor(signal)
            base_lot *= zone_risk_factor
            
            # 4. Portfolio balance adjustment (ปรับสมดุล BUY/SELL)
            total_volume = self.buy_volume + self.sell_volume
            if total_volume > 0:
                buy_ratio = self.buy_volume / total_volume
                sell_ratio = self.sell_volume / total_volume
                
                # เป้าหมาย 50:50 balance
                if signal.direction == 'BUY':
                    if buy_ratio > 0.65:  # BUY มากเกินไป
                        base_lot *= 0.5  # ลด lot
                    elif buy_ratio < 0.35:  # BUY น้อยเกินไป
                        base_lot *= 1.5  # เพิ่ม lot
                else:  # SELL
                    if sell_ratio > 0.65:  # SELL มากเกินไป
                        base_lot *= 0.5  # ลด lot
                    elif sell_ratio < 0.35:  # SELL น้อยเกินไป
                        base_lot *= 1.5  # เพิ่ม lot
            
            # 5. Market volatility adjustment
            if hasattr(self, 'recent_volatility'):
                if self.recent_volatility > 2.0:  # ตลาดผันผวนสูง
                    base_lot *= 0.7  # ลด lot
                elif self.recent_volatility < 0.5:  # ตลาดเงียบ
                    base_lot *= 1.3  # เพิ่ม lot
            
            # 6. Position count adjustment
            position_count = len(self.positions)
            if position_count > 30:
                base_lot *= 0.8  # มี position เยอะแล้ว ลด lot
            elif position_count < 10:
                base_lot *= 1.2  # มี position น้อย เพิ่ม lot
            
            # 7. Time-based adjustment (ตามเวลาเทรด)
            current_hour = datetime.now().hour
            if 22 <= current_hour or current_hour <= 2:  # เวลาเทรดหลัก
                base_lot *= 1.2
            elif 7 <= current_hour <= 9:  # เวลาเปิดตลาดเอเชีย
                base_lot *= 1.1
            elif 14 <= current_hour <= 16:  # เวลาเปิดตลาดอเมริกา
                base_lot *= 1.1
            else:  # เวลาเทรดเงียบ
                base_lot *= 0.8
            
            # 8. Portfolio health adjustment
            if self.portfolio_health < 50:
                base_lot *= 0.6  # Portfolio ไม่ดี ลด lot
            elif self.portfolio_health > 80:
                base_lot *= 1.3  # Portfolio ดี เพิ่ม lot
            
            # 9. Signal strength multiplier (if enabled)
            if self.signal_strength_multiplier and hasattr(signal, 'strength'):
                multiplier = max(self.lot_multiplier_range[0], 
                               min(self.lot_multiplier_range[1], signal.strength))
                base_lot *= multiplier
            
            # 10. Final validation and rounding
            lot_size = round(base_lot, 2)
            lot_size = max(self.base_lot_size, min(self.max_lot_size, lot_size))
            
            return lot_size
            
        except Exception as e:
            self.log(f"Error calculating enhanced dynamic lot size: {str(e)}", "ERROR")
            return self.base_lot_size

    def calculate_zone_risk_factor(self, signal: Signal) -> float:
        """คำนวณ risk factor ตาม zone analysis"""
        try:
            if not self.positions:
                return 1.0  # No positions, normal risk
            
            zone_analysis = self.analyze_position_zones()
            
            # Base risk factor
            risk_factor = 1.0
            
            # 1. Zone distribution score impact
            distribution_score = zone_analysis.get('distribution_score', 100.0)
            if distribution_score < 50:
                risk_factor *= 0.7  # Poor distribution, reduce lot size
            elif distribution_score > 80:
                risk_factor *= 1.2  # Good distribution, allow larger lots
            
            # 2. Check for signal price clustering
            if hasattr(signal, 'price') and signal.price:
                if self.check_position_clustering(signal.price):
                    risk_factor *= 0.3  # Severe clustering risk, drastically reduce lot
            
            # 3. Congested zones impact
            congested_zones = zone_analysis.get('clustered_zones', [])
            if len(congested_zones) > 2:  # More than 2 congested zones
                risk_factor *= 0.8  # Multiple congested zones, reduce risk
            
            # 4. Empty zones opportunity
            empty_zones = zone_analysis.get('empty_zones', [])
            total_zones_used = zone_analysis.get('total_zones_used', 1)
            
            if len(empty_zones) > total_zones_used:  # More empty than used zones
                risk_factor *= 1.1  # Good diversification opportunity
            
            # Ensure risk factor stays within reasonable bounds
            return max(0.2, min(2.0, risk_factor))
            
        except Exception as e:
            self.log(f"Error calculating zone risk factor: {str(e)}", "ERROR")
            return 1.0

    def calculate_risk_based_volume(self, signal: Signal, zone_risk: float) -> float:
        """ปรับ volume ตาม risk level ของแต่ละ zone"""
        try:
            base_volume = self.calculate_dynamic_lot_size(signal)
            
            # Apply zone risk adjustment
            adjusted_volume = base_volume * zone_risk
            
            # Additional validation
            if zone_risk < 0.5:  # High risk zone
                adjusted_volume = min(adjusted_volume, self.base_lot_size * 1.5)
            elif zone_risk > 1.5:  # Low risk zone
                adjusted_volume = min(adjusted_volume, self.max_lot_size * 0.8)
            
            return max(self.base_lot_size, min(self.max_lot_size, adjusted_volume))
            
        except Exception as e:
            self.log(f"Error calculating risk-based volume: {str(e)}", "ERROR")
            return self.base_lot_size

    # 🎯 Zone-Based Trading System Methods
    
    def _get_positions_hash(self) -> str:
        """Calculate a hash of current positions for cache invalidation"""
        try:
            if not self.positions:
                return "empty"
            
            # Create a simple hash based on position count, total volume, and key prices
            position_data = []
            for pos in self.positions:
                position_data.append(f"{pos.ticket}:{pos.open_price}:{pos.volume}:{pos.type}")
            
            position_string = "|".join(sorted(position_data))
            import hashlib
            return hashlib.md5(position_string.encode()).hexdigest()[:8]
        except Exception:
            return str(len(self.positions) if self.positions else 0)

    def analyze_position_zones(self) -> dict:
        """แบ่ง positions ตาม price zones และวิเคราะห์การกระจาย - with caching"""
        try:
            # Check cache validity first
            current_time = datetime.now()
            current_positions_hash = self._get_positions_hash()
            
            if (self.zone_analysis_cache and 
                self.zone_analysis_cache_time and 
                self.zone_analysis_cache_positions_hash == current_positions_hash and
                (current_time - self.zone_analysis_cache_time).seconds < self.zone_cache_ttl):
                # Return cached result with flag
                cached_result = self.zone_analysis_cache.copy()
                cached_result['cached'] = True
                return cached_result
            
            if not self.positions:
                empty_result = {
                    'zones': {}, 
                    'distribution_score': 100.0, 
                    'clustered_zones': [], 
                    'empty_zones': [],
                    'total_zones_used': 0,
                    'current_price': 0.0,
                    'cached': False
                }
                # Cache empty result too
                self.zone_analysis_cache = empty_result
                self.zone_analysis_cache_time = current_time
                self.zone_analysis_cache_positions_hash = current_positions_hash
                return empty_result
            
            # Get current market price for reference
            current_price = 0
            if MT5_AVAILABLE and mt5 and self.mt5_connected:
                tick = mt5.symbol_info_tick(self.symbol)
                if tick:
                    current_price = tick.bid
            
            if current_price == 0:
                # Fallback to average of position prices
                current_price = sum(p.current_price for p in self.positions) / len(self.positions)
            
            # Group positions by zones
            zones = {}
            # For XAUUSD: 1 pip = 0.1 point, so 25 pips = 2.5 points
            zone_size = self.zone_size_pips * 0.1  # Convert pips to price units for XAUUSD
            
            for position in self.positions:
                # Calculate zone index based on price difference from current price
                price_diff = position.open_price - current_price
                zone_index = int(price_diff / zone_size)
                
                if zone_index not in zones:
                    zones[zone_index] = {
                        'positions': [],
                        'buy_count': 0,
                        'sell_count': 0,
                        'total_volume': 0.0,
                        'avg_price': 0.0,
                        'zone_range': (
                            current_price + (zone_index * zone_size),
                            current_price + ((zone_index + 1) * zone_size)
                        )
                    }
                
                zones[zone_index]['positions'].append(position)
                zones[zone_index]['total_volume'] += position.volume
                
                if position.type == 'BUY':
                    zones[zone_index]['buy_count'] += 1
                else:
                    zones[zone_index]['sell_count'] += 1
            
            # Calculate average price for each zone
            for zone_data in zones.values():
                if zone_data['positions']:
                    zone_data['avg_price'] = sum(p.open_price for p in zone_data['positions']) / len(zone_data['positions'])
            
            # Calculate distribution score and identify issues
            distribution_score = self.calculate_zone_distribution_score(zones)
            clustered_zones = self.get_congested_zones(zones)
            empty_zones = self.get_empty_zones(zones, current_price)
            
            result = {
                'zones': zones,
                'distribution_score': distribution_score,
                'clustered_zones': clustered_zones,
                'empty_zones': empty_zones,
                'total_zones_used': len(zones),
                'current_price': current_price,
                'cached': False
            }
            
            # Cache the result
            self.zone_analysis_cache = result
            self.zone_analysis_cache_time = current_time
            self.zone_analysis_cache_positions_hash = current_positions_hash
            
            # 🆕 Advanced Distribution Analysis
            advanced_distribution = self._analyze_advanced_distribution(zones)
            result['advanced_distribution'] = advanced_distribution
            
            return result
            
        except Exception as e:
            self.log(f"Error analyzing position zones: {str(e)}", "ERROR")
            return {'zones': {}, 'distribution_score': 0.0, 'clustered_zones': [], 'empty_zones': [], 'cached': False}

    def _analyze_advanced_distribution(self, zones: dict) -> dict:
        """🧠 Advanced Distribution Analysis สำหรับ Smart Distribution"""
        try:
            advanced_analysis = {
                'price_gaps': [],
                'distribution_quality': 'UNKNOWN',
                'needs_distribution_improvement': False,
                'optimal_distribution_actions': [],
                'profit_distribution': {},
                'risk_distribution': {},
                'message': ''
            }
            
            # 1. 📏 Price Gap Analysis
            all_positions = []
            for zone in zones.values():
                all_positions.extend(zone['positions'])
            
            if len(all_positions) < 2:
                advanced_analysis['message'] = 'Insufficient positions for distribution analysis'
                return advanced_analysis
            
            # เรียงตาม entry price
            all_positions.sort(key=lambda x: x.open_price)
            
            # คำนวณ price gaps (ปรับให้ยืดหยุ่นขึ้น)
            for i in range(len(all_positions) - 1):
                gap = abs(all_positions[i+1].open_price - all_positions[i].open_price) * 10000  # Convert to points
                
                # ปรับ threshold ให้ยืดหยุ่นขึ้น
                if gap > 300:  # ลดจาก 500 เป็น 300
                    gap_quality = 'GOOD'
                elif gap > 100:  # ลดจาก 200 เป็น 100
                    gap_quality = 'MEDIUM'
                else:
                    gap_quality = 'POOR'
                
                advanced_analysis['price_gaps'].append({
                    'position1': all_positions[i].ticket,
                    'position1_price': all_positions[i].open_price,
                    'position2': all_positions[i+1].ticket,
                    'position2_price': all_positions[i+1].open_price,
                    'gap_points': gap,
                    'gap_quality': gap_quality
                })
            
            # 2. 🎯 Distribution Quality Assessment (ปรับให้ยืดหยุ่นขึ้น)
            poor_gaps = [g for g in advanced_analysis['price_gaps'] if g['gap_quality'] == 'POOR']
            medium_gaps = [g for g in advanced_analysis['price_gaps'] if g['gap_quality'] == 'MEDIUM']
            good_gaps = [g for g in advanced_analysis['price_gaps'] if g['gap_quality'] == 'GOOD']
            
            # 🆕 ปรับ Price Gap Analysis ให้รวม Buy/Sell Separation
            if 'buy_sell_separation' in advanced_analysis:
                separation_quality = advanced_analysis['buy_sell_separation']['separation_quality']
                if separation_quality in ['EMERGENCY', 'POOR']:
                    # ถ้า Buy/Sell separation แย่ ให้ปรับ Price Gap quality
                    for gap in advanced_analysis['price_gaps']:
                        if gap['gap_quality'] == 'GOOD':
                            # ลด quality ของ gaps ที่อยู่ห่างกันมาก
                            if gap['gap_points'] > 1000:  # 1000 points = 100 pips
                                gap['gap_quality'] = 'MEDIUM'
                            if gap['gap_points'] > 2000:  # 2000 points = 200 pips
                                gap['gap_quality'] = 'POOR'
                    
                    # คำนวณ Price Gap quality ใหม่
                    poor_gaps = [g for g in advanced_analysis['price_gaps'] if g['gap_quality'] == 'POOR']
                    medium_gaps = [g for g in advanced_analysis['price_gaps'] if g['gap_quality'] == 'MEDIUM']
                    good_gaps = [g for g in advanced_analysis['price_gaps'] if g['gap_quality'] == 'GOOD']
            
            # 🆕 เพิ่ม BUY/SELL Balance Check
            buy_positions = [p for p in all_positions if p.type == 'BUY']
            sell_positions = [p for p in all_positions if p.type == 'SELL']
            buy_ratio = len(buy_positions) / len(all_positions) if all_positions else 0
            sell_ratio = len(sell_positions) / len(all_positions) if all_positions else 0
            
            # 🆕 เพิ่ม Buy/Sell Separation Analysis (สำคัญมาก!)
            buy_sell_separation = 0
            if buy_positions and sell_positions:
                # หา Buy ที่ต่ำสุด และ Sell ที่สูงสุด
                min_buy_price = min(p.open_price for p in buy_positions)
                max_sell_price = max(p.open_price for p in sell_positions)
                buy_sell_separation = (min_buy_price - max_sell_price) * 1000  # Convert to points (1000 not 10000!)
                
                # วิเคราะห์ Buy/Sell separation (ปรับให้สมเหตุสมผล)
                if buy_sell_separation > 500:  # 500 points = 50 pips
                    separation_quality = 'EMERGENCY'
                    separation_message = f'CRITICAL: Buy/Sell separation {buy_sell_separation:.0f} points - Immediate action needed!'
                elif buy_sell_separation > 300:  # 300 points = 30 pips
                    separation_quality = 'POOR'
                    separation_message = f'POOR: Buy/Sell separation {buy_sell_separation:.0f} points - Action needed'
                elif buy_sell_separation > 100:  # 100 points = 10 pips
                    separation_quality = 'MEDIUM'
                    separation_message = f'MEDIUM: Buy/Sell separation {buy_sell_separation:.0f} points - Monitor closely'
                else:
                    separation_quality = 'GOOD'
                    separation_message = f'GOOD: Buy/Sell separation {buy_sell_separation:.0f} points'
                
                # เพิ่มข้อมูล separation ใน advanced_analysis
                advanced_analysis['buy_sell_separation'] = {
                    'separation_points': buy_sell_separation,
                    'separation_quality': separation_quality,
                    'min_buy_price': min_buy_price,
                    'max_sell_price': max_sell_price,
                    'message': separation_message
                }
                
                # 🆕 เพิ่ม Debug Log สำหรับ Buy/Sell Separation
                self.log(f"🔍 Buy/Sell Separation Analysis: {buy_sell_separation:.0f} points | Quality: {separation_quality} | Min BUY: {min_buy_price:.2f} | Max SELL: {max_sell_price:.2f}", "INFO")
            
            # ตรวจสอบ BUY/SELL imbalance (ปรับให้ยืดหยุ่นขึ้น)
            imbalance_threshold = 0.55  # ลดจาก 0.6 เป็น 0.55
            slight_imbalance_threshold = 0.52  # เพิ่มใหม่
            is_imbalanced = buy_ratio > imbalance_threshold or sell_ratio > imbalance_threshold
            is_slightly_imbalanced = buy_ratio > slight_imbalance_threshold or sell_ratio > slight_imbalance_threshold
            
            # 🆕 ปรับ distribution quality assessment ให้ใช้ Buy/Sell Separation (สำคัญมาก!)
            if 'buy_sell_separation' in advanced_analysis:
                separation_quality = advanced_analysis['buy_sell_separation']['separation_quality']
                separation_points = advanced_analysis['buy_sell_separation']['separation_points']
                
                if separation_quality == 'EMERGENCY':
                    advanced_analysis['distribution_quality'] = 'EMERGENCY'
                    advanced_analysis['needs_distribution_improvement'] = True
                    advanced_analysis['message'] = f'EMERGENCY: Buy/Sell separation {separation_points:.0f} points - Immediate action needed!'
                elif separation_quality == 'POOR':
                    advanced_analysis['distribution_quality'] = 'POOR'
                    advanced_analysis['needs_distribution_improvement'] = True
                    advanced_analysis['message'] = f'POOR: Buy/Sell separation {separation_points:.0f} points - Action needed'
                elif separation_quality == 'MEDIUM':
                    advanced_analysis['distribution_quality'] = 'MEDIUM'
                    advanced_analysis['needs_distribution_improvement'] = True
                    advanced_analysis['message'] = f'MEDIUM: Buy/Sell separation {separation_points:.0f} points - Monitor closely'
                else:
                    # ใช้ logic เดิมถ้า separation ดี
                    if len(poor_gaps) > len(good_gaps) or is_imbalanced:
                        advanced_analysis['distribution_quality'] = 'POOR'
                        advanced_analysis['needs_distribution_improvement'] = True
                        if len(poor_gaps) > len(good_gaps):
                            advanced_analysis['message'] = f'Poor distribution: {len(poor_gaps)} poor gaps vs {len(good_gaps)} good gaps'
                        else:
                            advanced_analysis['message'] = f'BUY/SELL imbalance: BUY {buy_ratio:.1%} vs SELL {sell_ratio:.1%}'
                    elif len(medium_gaps) > len(good_gaps) or is_slightly_imbalanced:
                        advanced_analysis['distribution_quality'] = 'MEDIUM'
                        advanced_analysis['needs_distribution_improvement'] = True
                        if len(medium_gaps) > len(good_gaps):
                            advanced_analysis['message'] = f'Medium distribution: {len(medium_gaps)} medium gaps vs {len(good_gaps)} good gaps'
                        else:
                            advanced_analysis['message'] = f'BUY/SELL slight imbalance: BUY {buy_ratio:.1%} vs SELL {sell_ratio:.1%}'
                    else:
                        advanced_analysis['distribution_quality'] = 'GOOD'
                        advanced_analysis['needs_distribution_improvement'] = False
                        advanced_analysis['message'] = f'Good distribution: {len(good_gaps)} good gaps | BUY {buy_ratio:.1%} vs SELL {sell_ratio:.1%}'
            else:
                # Fallback: ใช้ logic เดิมถ้าไม่มี separation data
                if len(poor_gaps) > len(good_gaps) or is_imbalanced:
                    advanced_analysis['distribution_quality'] = 'POOR'
                    advanced_analysis['needs_distribution_improvement'] = True
                    if len(poor_gaps) > len(good_gaps):
                        advanced_analysis['message'] = f'Poor distribution: {len(poor_gaps)} poor gaps vs {len(good_gaps)} good gaps'
                    else:
                        advanced_analysis['message'] = f'BUY/SELL imbalance: BUY {buy_ratio:.1%} vs SELL {sell_ratio:.1%}'
                elif len(medium_gaps) > len(good_gaps) or is_slightly_imbalanced:
                    advanced_analysis['distribution_quality'] = 'MEDIUM'
                    advanced_analysis['needs_distribution_improvement'] = True
                    if len(medium_gaps) > len(good_gaps):
                        advanced_analysis['message'] = f'Medium distribution: {len(medium_gaps)} medium gaps vs {len(good_gaps)} good gaps'
                    else:
                        advanced_analysis['message'] = f'BUY/SELL slight imbalance: BUY {buy_ratio:.1%} vs SELL {sell_ratio:.1%}'
                else:
                    advanced_analysis['distribution_quality'] = 'GOOD'
                    advanced_analysis['needs_distribution_improvement'] = False
                    advanced_analysis['message'] = f'Good distribution: {len(good_gaps)} good gaps | BUY {buy_ratio:.1%} vs SELL {sell_ratio:.1%}'
            
            # 3. 💰 Profit Distribution Analysis
            profitable_positions = [p for p in all_positions if hasattr(p, 'profit') and p.profit > 0]
            losing_positions = [p for p in all_positions if hasattr(p, 'profit') and p.profit < 0]
            
            if profitable_positions:
                profit_prices = [p.open_price for p in profitable_positions]
                advanced_analysis['profit_distribution'] = {
                    'count': len(profitable_positions),
                    'price_range': max(profit_prices) - min(profit_prices) if len(profit_prices) > 1 else 0,
                    'price_spread': 'GOOD' if len(profit_prices) > 1 and (max(profit_prices) - min(profit_prices)) > 500 else 'POOR'
                }
            
            if losing_positions:
                loss_prices = [p.open_price for p in losing_positions]
                advanced_analysis['risk_distribution'] = {
                    'count': len(losing_positions),
                    'price_range': max(loss_prices) - min(loss_prices) if len(loss_prices) > 1 else 0,
                    'price_spread': 'GOOD' if len(loss_prices) > 1 and (max(loss_prices) - min(loss_prices)) > 500 else 'POOR'
                }
            
            # 4. 🎯 Optimal Distribution Actions (ปรับให้ยืดหยุ่นขึ้น)
            if advanced_analysis['needs_distribution_improvement']:
                # 🆕 เพิ่ม Buy/Sell Separation Actions (สำคัญมาก!)
                if 'buy_sell_separation' in advanced_analysis:
                    separation_quality = advanced_analysis['buy_sell_separation']['separation_quality']
                    separation_points = advanced_analysis['buy_sell_separation']['separation_points']
                    
                    if separation_quality == 'EMERGENCY':
                        # 🚨 EMERGENCY: ระยะห่าง Buy/Sell เกิน 500 points
                        advanced_analysis['optimal_distribution_actions'].append({
                            'action': 'EMERGENCY_BUY_SELL_BALANCE',
                            'reason': f'CRITICAL: Buy/Sell separation {separation_points:.0f} points - Immediate action needed!',
                            'priority': 'EMERGENCY',
                            'separation_points': separation_points,
                            'target_reduction': 300  # ลดลงเหลือ 300 points
                        })
                        
                        # เพิ่ม actions เฉพาะเจาะจง (แก้ไขให้ถูกต้อง)
                        if buy_ratio > sell_ratio:
                            # BUY heavy - เปิด SELL ใหม่เพื่อลดระยะห่าง
                            advanced_analysis['optimal_distribution_actions'].append({
                                'action': 'OPEN_SELL_TO_REDUCE_SEPARATION',
                                'reason': f'BUY heavy - Open SELL to reduce {separation_points:.0f} points separation',
                                'priority': 'EMERGENCY',
                                'target_price_range': 'Near lowest BUY positions'
                            })
                        else:
                            # SELL heavy - เปิด BUY ใหม่เพื่อลดระยะห่าง
                            advanced_analysis['optimal_distribution_actions'].append({
                                'action': 'OPEN_BUY_TO_REDUCE_SEPARATION',
                                'reason': f'SELL heavy - Open BUY to reduce {separation_points:.0f} points separation',
                                'priority': 'EMERGENCY',
                                'target_price_range': 'Near highest SELL positions'
                            })
                        
                        # 🆕 เพิ่ม EMERGENCY_BUY_SELL_BALANCE Action (สำคัญมาก!)
                        advanced_analysis['optimal_distribution_actions'].append({
                            'action': 'EMERGENCY_BUY_SELL_BALANCE',
                            'reason': f'CRITICAL: Buy/Sell separation {separation_points:.0f} points - Immediate action needed!',
                            'priority': 'EMERGENCY',
                            'separation_points': separation_points,
                            'target_reduction': 300  # ลดลงเหลือ 300 points
                        })
                        
                        # 🆕 เพิ่ม Debug Log สำหรับ Action Logic
                        self.log(f"🔍 Action Logic Debug: BUY ratio {buy_ratio:.1%} vs SELL ratio {sell_ratio:.1%} | Action: {'OPEN_SELL' if buy_ratio > sell_ratio else 'OPEN_BUY'}", "INFO")
                        
                    elif separation_quality == 'POOR':
                        # ⚠️ POOR: ระยะห่าง Buy/Sell เกิน 300 points
                        advanced_analysis['optimal_distribution_actions'].append({
                            'action': 'REDUCE_BUY_SELL_SEPARATION',
                            'reason': f'POOR: Buy/Sell separation {separation_points:.0f} points - Action needed',
                            'priority': 'HIGH',
                            'separation_points': separation_points,
                            'target_reduction': 200  # ลดลงเหลือ 200 points
                        })
                        
                        # เพิ่ม actions เฉพาะเจาะจง
                        if buy_ratio > sell_ratio:
                            advanced_analysis['optimal_distribution_actions'].append({
                                'action': 'OPEN_SELL_TO_REDUCE_SEPARATION',
                                'reason': f'BUY heavy - Open SELL to reduce separation',
                                'priority': 'HIGH',
                                'target_price_range': 'Near lowest BUY positions'
                            })
                        else:
                            advanced_analysis['optimal_distribution_actions'].append({
                                'action': 'OPEN_BUY_TO_REDUCE_SEPARATION',
                                'reason': f'SELL heavy - Open BUY to reduce separation',
                                'priority': 'HIGH',
                                'target_price_range': 'Near highest SELL positions'
                            })
                        
                    elif separation_quality == 'MEDIUM':
                        # 📊 MEDIUM: ระยะห่าง Buy/Sell เกิน 100 points
                        advanced_analysis['optimal_distribution_actions'].append({
                            'action': 'MONITOR_BUY_SELL_SEPARATION',
                            'reason': f'MEDIUM: Buy/Sell separation {separation_points:.0f} points - Monitor closely',
                            'priority': 'MEDIUM',
                            'separation_points': separation_points
                        })
                
                # 🆕 เพิ่ม BUY/SELL Balance Actions (เดิม)
                if is_imbalanced:
                    if buy_ratio > imbalance_threshold:
                        advanced_analysis['optimal_distribution_actions'].append({
                            'action': 'BALANCE_BUY_HEAVY',
                            'reason': f'BUY heavy ({buy_ratio:.1%}) - need to balance portfolio',
                            'priority': 'HIGH'
                        })
                    elif sell_ratio > imbalance_threshold:
                        advanced_analysis['optimal_distribution_actions'].append({
                            'action': 'BALANCE_SELL_HEAVY',
                            'reason': f'SELL heavy ({sell_ratio:.1%}) - need to balance portfolio',
                            'priority': 'HIGH'
                        })
                
                # 🆕 เพิ่ม Gap Management Actions
                if len(poor_gaps) > 0:
                    advanced_analysis['optimal_distribution_actions'].append({
                        'action': 'CLOSE_CLUSTERED',
                        'reason': f'Close {len(poor_gaps)} clustered positions to improve distribution',
                        'priority': 'HIGH'
                    })
                
                # 🆕 เพิ่ม Price Spread Actions
                if advanced_analysis['profit_distribution'].get('price_spread') == 'POOR':
                    advanced_analysis['optimal_distribution_actions'].append({
                        'action': 'REDISTRIBUTE_PROFITS',
                        'reason': 'Redistribute profitable positions for better price spread',
                        'priority': 'MEDIUM'
                    })
                
                if advanced_analysis['risk_distribution'].get('price_spread') == 'POOR':
                    advanced_analysis['optimal_distribution_actions'].append({
                        'action': 'REDISTRIBUTE_RISKS',
                        'reason': 'Redistribute losing positions for better price spread',
                        'priority': 'MEDIUM'
                    })
                
                # 🆕 เพิ่ม Portfolio Balance Actions
                if buy_ratio > 0.55 or sell_ratio > 0.55:
                    advanced_analysis['optimal_distribution_actions'].append({
                        'action': 'IMPROVE_PORTFOLIO_BALANCE',
                        'reason': f'Improve BUY/SELL balance (BUY {buy_ratio:.1%} vs SELL {sell_ratio:.1%})',
                        'priority': 'MEDIUM',
                        'action_type': 'OPEN_POSITIONS'
                    })
            
            return advanced_analysis
            
        except Exception as e:
            self.log(f"Error in advanced distribution analysis: {str(e)}", "ERROR")
            return {'error': str(e)}

    def calculate_zone_distribution_score(self, zones: dict) -> float:
        """คำนวณคะแนนการกระจายตัวของ zones (0-100)"""
        try:
            if not zones:
                return 100.0
            
            total_positions = sum(len(zone['positions']) for zone in zones.values())
            if total_positions == 0:
                return 100.0
            
            score = 100.0
            
            # 1. Penalize overcrowded zones (40 points)
            overcrowded_penalty = 0
            for zone_data in zones.values():
                position_count = len(zone_data['positions'])
                if position_count > self.max_positions_per_zone:
                    overcrowded_penalty += (position_count - self.max_positions_per_zone) * 10
            
            score -= min(40, overcrowded_penalty)
            
            # 2. Reward even distribution (30 points)
            zone_counts = [len(zone['positions']) for zone in zones.values()]
            avg_per_zone = sum(zone_counts) / len(zone_counts)
            variance = sum((count - avg_per_zone) ** 2 for count in zone_counts) / len(zone_counts)
            distribution_score = max(0, 30 - (variance * 5))
            score = score - 30 + distribution_score
            
            # 3. Penalize clustering (30 points)
            clustering_penalty = 0
            zone_indices = sorted(zones.keys())
            consecutive_zones = 0
            for i in range(len(zone_indices) - 1):
                if zone_indices[i+1] - zone_indices[i] == 1:  # Adjacent zones
                    consecutive_zones += 1
            
            if consecutive_zones > 2:  # More than 2 consecutive zones
                clustering_penalty = (consecutive_zones - 2) * 10
            
            score -= min(30, clustering_penalty)
            
            return max(0.0, min(100.0, score))
            
        except Exception as e:
            self.log(f"Error calculating zone distribution score: {str(e)}", "ERROR")
            return 50.0

    def get_empty_zones(self, zones: dict, current_price: float) -> List[int]:
        """หา zones ที่ว่างเปล่าใกล้ราคาปัจจุบัน"""
        try:
            if not zones:
                return list(range(-2, 3))  # Return zones around current price
            
            used_zone_indices = set(zones.keys())
            min_zone = min(used_zone_indices)
            max_zone = max(used_zone_indices)
            
            # Check for gaps in the range
            empty_zones = []
            for zone_idx in range(min_zone - 2, max_zone + 3):
                if zone_idx not in used_zone_indices:
                    empty_zones.append(zone_idx)
            
            return empty_zones
            
        except Exception as e:
            self.log(f"Error finding empty zones: {str(e)}", "ERROR")
            return []

    def get_congested_zones(self, zones: dict) -> List[dict]:
        """หา zones ที่มี positions เกินขีดจำกัด"""
        try:
            congested = []
            for zone_idx, zone_data in zones.items():
                position_count = len(zone_data['positions'])
                if position_count > self.max_positions_per_zone:
                    congested.append({
                        'zone_index': zone_idx,
                        'position_count': position_count,
                        'excess_positions': position_count - self.max_positions_per_zone,
                        'zone_range': zone_data['zone_range']
                    })
            
            return sorted(congested, key=lambda x: x['excess_positions'], reverse=True)
            
        except Exception as e:
            self.log(f"Error finding congested zones: {str(e)}", "ERROR")
            return []

    def check_position_clustering(self, target_price: float) -> bool:
        """ตรวจสอบว่าจะเกิด clustering หรือไม่ถ้าเปิด position ที่ราคานี้"""
        try:
            if not self.positions:
                return False
            
            min_distance = self.min_position_distance_pips * 0.1  # Convert pips to price units for XAUUSD
            
            # Check distance to all existing positions
            for position in self.positions:
                distance = abs(target_price - position.open_price)
                if distance < min_distance:
                    self.log(f"🚫 Position clustering detected: {distance*10:.1f} pips < {self.min_position_distance_pips} pips minimum")
                    return True
            
            return False
            
        except Exception as e:
            self.log(f"Error checking position clustering: {str(e)}", "ERROR")
            return False

    def calculate_advanced_position_score(self, position: Position) -> dict:
        """คำนวณคะแนน position แบบขั้นสูง"""
        try:
            score_details = {
                'profit_score': 0,          # 0-25
                'age_score': 0,             # 0-15  
                'market_alignment': 0,      # 0-20
                'risk_reward_ratio': 0,     # 0-15
                'portfolio_contribution': 0, # 0-15
                'technical_position': 0,    # 0-10
                'total_score': 0
            }
            
            # 1. Profit Performance (25 points)
            profit_pct = self.calculate_profit_percent(position)
            if profit_pct >= 10:
                score_details['profit_score'] = 25
            elif profit_pct >= 5:
                score_details['profit_score'] = 20
            elif profit_pct >= 2:
                score_details['profit_score'] = 15
            elif profit_pct >= 0:
                score_details['profit_score'] = 10
            else:
                # Penalty for losses, but not too harsh
                score_details['profit_score'] = max(0, 10 + profit_pct)
            
            # 2. Age Factor (15 points)
            if position.ticket in self.position_tracker:
                try:
                    birth_time = safe_parse_datetime(self.position_tracker[position.ticket]['birth_time'])
                    age_hours = (datetime.now() - birth_time).total_seconds() / 3600
                    if age_hours < 2:
                        score_details['age_score'] = 5  # Too young
                    elif age_hours < 12:
                        score_details['age_score'] = 15  # Perfect age
                    elif age_hours < 24:
                        score_details['age_score'] = 10  # Getting old
                    else:
                        score_details['age_score'] = 5   # Too old
                except Exception as age_error:
                    self.log(f"Warning: Could not calculate age factor for position {position.ticket}: {age_error}", "WARNING")
                    score_details['age_score'] = 5  # Default score
            
            # 3. Market Alignment (20 points)
            market_data = self.get_market_data()
            if market_data is not None:
                trend_strength = self.calculate_trend_strength(market_data)
                momentum = self.calculate_momentum_score(market_data)
                
                if position.type == "BUY":
                    if trend_strength > 0.6 and momentum > 0.6:
                        score_details['market_alignment'] = 20
                    elif trend_strength > 0.4 and momentum > 0.4:
                        score_details['market_alignment'] = 10
                else:  # SELL
                    if trend_strength < 0.4 and momentum < 0.4:
                        score_details['market_alignment'] = 20
                    elif trend_strength < 0.6 and momentum < 0.6:
                        score_details['market_alignment'] = 10
            
            # 4. Risk-Reward Ratio (15 points)
            if position.profit > 0:
                # Good profit deserves points
                score_details['risk_reward_ratio'] = min(15, (profit_pct / 5) * 15)
            else:
                # Manage risk for losing positions
                if profit_pct > -10:  # Acceptable loss
                    score_details['risk_reward_ratio'] = 10
                elif profit_pct > -20:  # High risk
                    score_details['risk_reward_ratio'] = 5
                else:  # Very high risk
                    score_details['risk_reward_ratio'] = 0
            
            # 5. Portfolio Contribution (15 points)
            if self.will_improve_balance_by_closing(position):
                score_details['portfolio_contribution'] = 15
            elif self.portfolio_health < 50 and position.profit > 0:
                score_details['portfolio_contribution'] = 10
            
            # 6. Technical Position (10 points)
            if hasattr(self, 'recent_volatility'):
                if self.recent_volatility < 1.0 and position.profit > 0:
                    score_details['technical_position'] = 10  # Good timing in low volatility
                elif self.recent_volatility > 2.0 and position.profit < 0:
                    score_details['technical_position'] = 0   # Bad timing in high volatility
                else:
                    score_details['technical_position'] = 5
            
            # Calculate total
            score_details['total_score'] = sum(v for k, v in score_details.items() if k != 'total_score')
            
            return score_details
            
        except Exception as e:
            self.log(f"Error calculating advanced score: {str(e)}", "ERROR")
            return {'total_score': 50}

    def will_improve_balance_by_closing(self, position: Position) -> bool:
        """ปรับปรุงการตรวจสอบ balance"""
        try:
            if len(self.positions) <= 1:
                return False
            
            total_volume = self.buy_volume + self.sell_volume
            if total_volume <= position.volume:
                return False
            
            current_buy_ratio = self.buy_volume / total_volume
            
            # คำนวณ balance หลังปิด
            if position.type == "BUY":
                new_buy_volume = self.buy_volume - position.volume
                new_sell_volume = self.sell_volume
            else:
                new_buy_volume = self.buy_volume
                new_sell_volume = self.sell_volume - position.volume
            
            new_total = new_buy_volume + new_sell_volume
            if new_total <= 0:
                return False
            
            new_buy_ratio = new_buy_volume / new_total
            
            # เช็คว่าใกล้ 50:50 มากขึ้นหรือไม่
            current_distance = abs(current_buy_ratio - 0.5)
            new_distance = abs(new_buy_ratio - 0.5)
            
            return new_distance < current_distance - 0.05  # ต้องดีขึ้นอย่างน้อย 5%
            
        except Exception as e:
            return False

    def can_trade(self) -> bool:
        """Check if trading is allowed based on various conditions"""
        try:
            # Check basic conditions
            if not self.mt5_connected or not self.trading_active:
                return False
            
            # Check position limit
            if len(self.positions) >= self.max_positions:
                self.log("Max positions reached", "WARNING")
                return False
            
            # Check signal cooldown
            if (self.last_signal_time and 
                (datetime.now() - self.last_signal_time).seconds < self.signal_cooldown):
                return False
            
            # Check hourly signal limit
            now = datetime.now()
            hour_ago = now - timedelta(hours=1)
            recent_signals = [s for s in self.hourly_signals if s > hour_ago]
            if len(recent_signals) >= self.max_signals_per_hour:
                self.log("Hourly signal limit reached", "WARNING")
                return False
            
            # 🆕 Enhanced Portfolio Health Check
            portfolio_health = self.check_portfolio_health()
            if not portfolio_health['can_trade']:
                self.log(f"❌ Portfolio Health Check Failed: {portfolio_health['reason']}", "WARNING")
                return False
            
            return True
            
        except Exception as e:
            self.log(f"Error checking trade conditions: {str(e)}", "ERROR")
            return False

    def execute_order(self, signal: Signal) -> bool:
        """Execute order with smart routing and comprehensive validation"""
        try:
            # Input validation
            if not isinstance(signal, Signal):
                raise ValidationError(f"Signal must be Signal object, got {type(signal)}")
            
            # Validate signal properties
            signal.direction = InputValidator.validate_signal_direction(signal.direction)
            signal.price = InputValidator.validate_price(signal.price)
            
            if not hasattr(signal, 'strength') or signal.strength is None:
                signal.strength = 1.0
            else:
                signal.strength = self._validate_float(signal.strength, min_val=0.1, max_val=5.0, default=1.0)
            
            if not hasattr(signal, 'symbol') or not signal.symbol:
                signal.symbol = self.symbol
            else:
                signal.symbol = InputValidator.validate_symbol(signal.symbol)
            
            # 🆕 Enhanced Order Opening Conditions Check
            order_opening_check = self.check_order_opening_conditions(signal)
            if not order_opening_check['can_open']:
                self.log(f"❌ Order Opening Conditions Not Met: {order_opening_check['reason']}", "WARNING")
                return False
            
            # System state validation
            if not self.can_trade():
                self.log("❌ Trading conditions not met", "WARNING")
                return False
            
            if not self.mt5_connected:
                self.log("❌ MT5 not connected", "ERROR")
                return False
            
            # Circuit breaker check
            if self.circuit_breaker_open:
                self.log("❌ Circuit breaker is open, cannot execute orders", "WARNING")
                return False
                
            # ใช้ Enhanced Smart Signal Router with Zone Analysis
            router_result = self.smart_signal_router(signal)
            
            # 🎯 Log zone analysis if available
            if 'zone_analysis' in router_result['details'] and router_result['details']['zone_analysis']:
                zone_data = router_result['details']['zone_analysis']
                cache_status = "📋 CACHED" if zone_data.get('cached', False) else "🔄 CALCULATED"
                self.log(f"🗺️ Zone Analysis ({cache_status}): {zone_data['total_zones_used']} zones, score: {zone_data['distribution_score']:.1f}")
                if zone_data['clustered_zones']:
                    self.log(f"   ⚠️ Congested zones: {len(zone_data['clustered_zones'])}")
                if zone_data['empty_zones']:
                    self.log(f"   📍 Empty zones available: {len(zone_data['empty_zones'])}")
            
            if router_result['action'] == 'skip':
                self.log(f"⏭️ Signal SKIPPED: {signal.direction} - {router_result['details']['reason']}")
                return False
            
            elif router_result['action'] == 'redirect':
                # ดำเนินการ redirect
                details = router_result['details']
                target_position = details['target_position']
                
                success = self.execute_redirect_close(target_position, signal, details['reason'])
                if success:
                    self.log(f"🎯 REDIRECT SUCCESS: ${details['profit_captured']:.2f} captured")
                    return True
                else:
                    # ถ้า redirect ล้มเหลว ให้ execute ปกติ
                    self.log("🔄 Redirect failed, executing normal order")
            
            # Execute ปกติ (หรือ fallback จาก redirect ที่ล้มเหลว)
            return self.execute_normal_order(signal)
            
        except ValidationError as e:
            self.log(f"Validation error in execute_order: {str(e)}", "ERROR")
            return False
        except Exception as e:
            self.log(f"Error in execute_order: {str(e)}", "ERROR")
            return False

    def execute_normal_order(self, signal: Signal) -> bool:
        """Execute normal market order with comprehensive validation"""
        try:
            # Input validation
            if not isinstance(signal, Signal):
                raise ValidationError(f"Signal must be Signal object, got {type(signal)}")
            
            # Connection validation
            if not self.mt5_connected:
                raise ValidationError("MT5 not connected")
                
            if self.circuit_breaker_open:
                raise ValidationError("Circuit breaker is open")
            
            # Calculate and validate lot size
            lot_size = self.calculate_dynamic_lot_size(signal)
            lot_size = InputValidator.validate_volume(lot_size)
            
            # Validate order type
            if signal.direction not in ['BUY', 'SELL']:
                raise ValidationError(f"Invalid signal direction: {signal.direction}")
                
            order_type = mt5.ORDER_TYPE_BUY if signal.direction == 'BUY' else mt5.ORDER_TYPE_SELL
            
            # Ensure we have a valid filling type
            if self.filling_type is None:
                self.filling_type = self.detect_broker_filling_type()
            
            # Validate symbol
            symbol_info = mt5.symbol_info(self.symbol)
            if symbol_info is None:
                raise ValidationError(f"Symbol {self.symbol} not available")
            
            if not symbol_info.visible:
                self.log(f"Making symbol {self.symbol} visible", "INFO")
                if not mt5.symbol_select(self.symbol, True):
                    raise ValidationError(f"Could not select symbol {self.symbol}")
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": lot_size,
                "type": order_type,
                "deviation": 20,
                "magic": 123456,
                "comment": f"AI_Smart_{signal.strength:.1f}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self.filling_type,
            }
            
            # Retry mechanism with different filling types if needed
            for attempt in range(3):
                try:
                    result = mt5.order_send(request)
                    
                    if result is None:
                        self.log(f"❌ Order send returned None (attempt {attempt + 1})", "WARNING")
                        time.sleep(1)
                        continue
                    
                    if result.retcode == mt5.TRADE_RETCODE_DONE:
                        self.last_signal_time = datetime.now()
                        self.hourly_signals.append(datetime.now())
                        self.total_signals += 1
                        
                        self.log(f"✅ Order executed: {signal.direction} {lot_size} lots")
                        self.log(f"   Ticket: {result.order}")
                        self.log(f"   Reason: {signal.reason}")
                        return True
                        
                    elif result.retcode == mt5.TRADE_RETCODE_INVALID_FILL:
                        # Try next filling type
                        try:
                            current_index = self.filling_types_priority.index(self.filling_type)
                            if current_index < len(self.filling_types_priority) - 1:
                                self.filling_type = self.filling_types_priority[current_index + 1]
                                request["type_filling"] = self.filling_type
                                self.log(f"🔄 Retrying with different filling type: {self.filling_type}")
                                continue
                            else:
                                self.log(f"❌ All filling types failed: {result.retcode}", "ERROR")
                                break
                        except ValueError:
                            # filling_type not in priority list, use default
                            self.filling_type = mt5.ORDER_FILLING_IOC
                            request["type_filling"] = self.filling_type
                            continue
                    else:
                        error_description = self._get_trade_error_description(result.retcode)
                        self.log(f"❌ Order failed (attempt {attempt + 1}): {result.retcode} - {error_description}", "WARNING")
                        
                        # Check if error suggests connection issue
                        if result.retcode in [mt5.TRADE_RETCODE_CONNECTION, 
                                            mt5.TRADE_RETCODE_TIMEOUT, 
                                            mt5.TRADE_RETCODE_TRADE_DISABLED]:
                            self._handle_connection_failure()
                            break
                            
                        time.sleep(1)
                        
                except Exception as inner_e:
                    self.log(f"Exception during order send (attempt {attempt + 1}): {str(inner_e)}", "ERROR")
                    time.sleep(1)
            
            self.log("❌ Order execution failed after all attempts", "ERROR")
            return False
            
        except ValidationError as e:
            self.log(f"Validation error in execute_normal_order: {str(e)}", "ERROR")
            return False
        except Exception as e:
            self.log(f"Error executing normal order: {str(e)}", "ERROR")
            return False
    
    def _get_trade_error_description(self, retcode: int) -> str:
        """Get human-readable description of trade error code"""
        error_descriptions = {
            mt5.TRADE_RETCODE_REQUOTE: "Requote",
            mt5.TRADE_RETCODE_REJECT: "Request rejected",
            mt5.TRADE_RETCODE_CANCEL: "Request canceled",
            mt5.TRADE_RETCODE_PLACED: "Order placed",
            mt5.TRADE_RETCODE_DONE: "Request completed",
            mt5.TRADE_RETCODE_DONE_PARTIAL: "Request partially completed",
            mt5.TRADE_RETCODE_ERROR: "Common error",
            mt5.TRADE_RETCODE_TIMEOUT: "Request timeout",
            mt5.TRADE_RETCODE_INVALID: "Invalid request",
            mt5.TRADE_RETCODE_INVALID_VOLUME: "Invalid volume",
            mt5.TRADE_RETCODE_INVALID_PRICE: "Invalid price",
            mt5.TRADE_RETCODE_INVALID_STOPS: "Invalid stops",
            mt5.TRADE_RETCODE_TRADE_DISABLED: "Trade disabled",
            mt5.TRADE_RETCODE_MARKET_CLOSED: "Market closed",
            mt5.TRADE_RETCODE_NO_MONEY: "No money",
            mt5.TRADE_RETCODE_PRICE_CHANGED: "Price changed",
            mt5.TRADE_RETCODE_PRICE_OFF: "Off quotes",
            mt5.TRADE_RETCODE_INVALID_EXPIRATION: "Invalid expiration",
            mt5.TRADE_RETCODE_ORDER_CHANGED: "Order changed",
            mt5.TRADE_RETCODE_TOO_MANY_REQUESTS: "Too many requests",
            mt5.TRADE_RETCODE_NO_CHANGES: "No changes",
            mt5.TRADE_RETCODE_SERVER_DISABLES_AT: "Server disables autotrading",
            mt5.TRADE_RETCODE_CLIENT_DISABLES_AT: "Client disables autotrading",
            mt5.TRADE_RETCODE_LOCKED: "Request locked",
            mt5.TRADE_RETCODE_FROZEN: "Order frozen",
            mt5.TRADE_RETCODE_INVALID_FILL: "Invalid fill",
            mt5.TRADE_RETCODE_CONNECTION: "No connection",
            mt5.TRADE_RETCODE_ONLY_REAL: "Only real accounts allowed",
            mt5.TRADE_RETCODE_LIMIT_ORDERS: "Order limit reached",
            mt5.TRADE_RETCODE_LIMIT_VOLUME: "Volume limit reached",
            mt5.TRADE_RETCODE_INVALID_ORDER: "Invalid order",
            mt5.TRADE_RETCODE_POSITION_CLOSED: "Position closed",
        }
        
        return error_descriptions.get(retcode, f"Unknown error code: {retcode}")

    def update_positions(self):
        """Update position data and calculate metrics"""
        if not self.mt5_connected or not MT5_AVAILABLE or not mt5:
            return
            
        try:
            positions = mt5.positions_get(symbol=self.symbol)
            if positions is None:
                positions = []
            
            self.positions.clear()
            self.buy_volume = 0.0
            self.sell_volume = 0.0
            
            for pos in positions:
                try:
                    # Get current price with error handling
                    tick_info = mt5.symbol_info_tick(self.symbol)
                    if tick_info is None:
                        self.log(f"Warning: Could not get tick info for {self.symbol}", "WARNING")
                        current_price = pos.price_open  # Fallback to open price
                    else:
                        current_price = tick_info.bid if pos.type == 1 else tick_info.ask
                    
                    # Calculate profit per lot with validation
                    if pos.volume > 0:
                        profit_per_lot = pos.profit / pos.volume
                        # Round to 2 decimal places for currency consistency
                        profit_per_lot = round(profit_per_lot, 2)
                    else:
                        self.log(f"Warning: Position {pos.ticket} has zero volume", "WARNING")
                        profit_per_lot = 0
                    
                    # Add debugging log for profit per lot calculation
                    if self.verbose_logging:
                        self.log(f"Position {pos.ticket}: Profit=${pos.profit:.2f}, Volume={pos.volume:.2f}, $/Lot=${profit_per_lot:.2f}", "DEBUG")
                        
                except Exception as calc_error:
                    self.log(f"Error calculating profit per lot for position {pos.ticket}: {calc_error}", "ERROR")
                    current_price = pos.price_open
                    profit_per_lot = 0
                
                # Classify efficiency with error handling (ใช้เปอร์เซ็นต์)
                try:
                    profit_percent = (profit_per_lot / pos.price_open) * 100 if pos.price_open > 0 else 0
                    if profit_percent > 8.0:
                        efficiency = "excellent"
                    elif profit_percent > 4.0:
                        efficiency = "good"
                    elif profit_percent > 0:
                        efficiency = "fair"
                    else:
                        efficiency = "poor"
                except Exception as efficiency_error:
                    self.log(f"Error classifying efficiency for position {pos.ticket}: {efficiency_error}", "ERROR")
                    efficiency = "poor"
                
                # Assign role (simplified logic) with error handling
                try:
                    role = self.assign_position_role(pos, profit_per_lot)
                except Exception as role_error:
                    self.log(f"Error assigning role for position {pos.ticket}: {role_error}", "ERROR")
                    role = "UNKNOWN"
                
                try:
                    position = Position(
                        ticket=pos.ticket,
                        symbol=pos.symbol,
                        type="BUY" if pos.type == 0 else "SELL",
                        volume=pos.volume,
                        open_price=pos.price_open,
                        current_price=current_price,
                        profit=pos.profit,
                        profit_per_lot=profit_per_lot,
                        role=role,
                        efficiency=efficiency
                    )
                    
                    self.positions.append(position)
                    
                    # Update volume counters
                    if pos.type == 0:  # BUY
                        self.buy_volume += pos.volume
                    else:  # SELL
                        self.sell_volume += pos.volume
                        
                except Exception as position_error:
                    self.log(f"Error creating position object for {pos.ticket}: {position_error}", "ERROR")
                    continue
            
            # Calculate portfolio health
            self.calculate_portfolio_health()
            
            # 🚀 Performance: Invalidate zone analysis cache when positions update
            if hasattr(self, 'zone_analysis_cache') and self.zone_analysis_cache:
                # Clear cache to ensure fresh analysis after position changes
                self.zone_analysis_cache = None
                self.zone_analysis_cache_time = None
                self.zone_analysis_cache_positions_hash = None
            
        except Exception as e:
            self.log(f"Error updating positions: {str(e)}", "ERROR")

    def assign_position_role(self, position, profit_per_lot: float) -> str:
        """Assign role to position based on performance (ใช้เปอร์เซ็นต์)"""
        try:
            # Validate profit_per_lot is a valid number
            if not isinstance(profit_per_lot, (int, float)) or profit_per_lot != profit_per_lot:  # Check for NaN
                self.log(f"Warning: Invalid profit_per_lot {profit_per_lot} for position {getattr(position, 'ticket', 'unknown')}", "WARNING")
                return OrderRole.SUPPORT.value
            
            # คำนวณเป็นเปอร์เซ็นต์
            profit_percent = (profit_per_lot / position.price_open) * 100 if position.price_open > 0 else 0
            
            if profit_percent > 8.0:
                return OrderRole.MAIN.value
            elif profit_percent > 0:
                return OrderRole.SUPPORT.value
            elif profit_percent > -4.0:
                return OrderRole.HEDGE_GUARD.value
            else:
                return OrderRole.SACRIFICE.value
        except Exception as e:
            self.log(f"Error assigning position role: {e}", "ERROR")
            return OrderRole.SUPPORT.value

    def calculate_portfolio_health(self):
        """Calculate overall portfolio health score"""
        if not self.positions:
            self.portfolio_health = 100.0
            return
            
        try:
            total_profit = sum(pos.profit for pos in self.positions)
            total_volume = sum(pos.volume for pos in self.positions)
            
            # Volume balance factor
            total_vol = self.buy_volume + self.sell_volume
            balance_factor = 1.0
            if total_vol > 0:
                buy_ratio = self.buy_volume / total_vol
                imbalance = abs(buy_ratio - 0.5)
                balance_factor = 1.0 - (imbalance * 0.5)  # Max 25% penalty
            
            # Efficiency distribution
            excellent_count = len([p for p in self.positions if p.efficiency == "excellent"])
            good_count = len([p for p in self.positions if p.efficiency == "good"])
            poor_count = len([p for p in self.positions if p.efficiency == "poor"])
            
            efficiency_score = (excellent_count * 100 + good_count * 70 - poor_count * 30) / len(self.positions)
            efficiency_score = max(0, min(100, efficiency_score))
            
            # Position count factor
            position_factor = max(0.5, 1.0 - (len(self.positions) / self.max_positions) * 0.3)
            
            # Calculate final health score
            self.portfolio_health = efficiency_score * balance_factor * position_factor
            self.portfolio_health = max(0, min(100, self.portfolio_health))
            
        except Exception as e:
            self.log(f"Error calculating portfolio health: {str(e)}", "ERROR")
            self.portfolio_health = 50.0

    def get_smart_close_recommendations(self) -> List[str]:
        """Generate smart close recommendations"""
        recommendations = []
        
        try:
            if not self.positions:
                return recommendations
            
            # Find sacrifice candidates
            sacrifice_positions = [p for p in self.positions if p.role == OrderRole.SACRIFICE.value]
            if sacrifice_positions:
                total_sacrifice_loss = sum(p.profit for p in sacrifice_positions)
                main_positions = [p for p in self.positions if p.role == OrderRole.MAIN.value]
                total_main_profit = sum(p.profit for p in main_positions)
                
                if total_main_profit > abs(total_sacrifice_loss) * 1.2:
                    recommendations.append(f"Consider closing {len(sacrifice_positions)} sacrifice positions for net gain")
            
            # Volume imbalance recommendations
            total_vol = self.buy_volume + self.sell_volume
            if total_vol > 0:
                buy_ratio = self.buy_volume / total_vol
                if buy_ratio > 0.7:
                    recommendations.append("High BUY volume imbalance - consider closing some BUY positions")
                elif buy_ratio < 0.3:
                    recommendations.append("High SELL volume imbalance - consider closing some SELL positions")
            
            # Margin optimization
            account_info = mt5.account_info()
            if account_info and account_info.margin > 0:
                margin_level = (account_info.equity / account_info.margin) * 100
                if margin_level < 300:
                    poor_positions = [p for p in self.positions if p.efficiency == "poor"]
                    if poor_positions:
                        recommendations.append(f"Low margin warning - consider closing {len(poor_positions)} poor positions")
            
        except Exception as e:
            self.log(f"Error generating recommendations: {str(e)}", "ERROR")
        
        return recommendations

    def smart_signal_router(self, signal: Signal) -> Dict[str, Any]:
        """
        Enhanced Smart Signal Router with Zone-Based Analysis
        ตัดสินใจว่าจะ execute, redirect หรือ skip signal โดยพิจารณา zone distribution
        Returns: {'action': 'execute'/'redirect'/'skip', 'details': {...}}
        """
        try:
            result = {
                'action': 'execute',
                'details': {
                    'original_signal': signal,
                    'reason': 'Normal execution',
                    'redirect_target': None,
                    'profit_captured': 0.0,
                    'zone_analysis': None
                }
            }
            
            if not self.smart_router_enabled or not self.positions:
                return result
            
            # 🎯 PHASE 1: Zone-Based Analysis
            zone_analysis = self.analyze_position_zones()
            result['details']['zone_analysis'] = zone_analysis
            
            # 🆕 PHASE 1.5: AI Market Prediction Integration
            try:
                market_prediction = self.ai_market_prediction_system()
                if market_prediction and market_prediction.get('prediction') != 'ERROR':
                    prediction = market_prediction.get('prediction', 'UNKNOWN')
                    confidence = market_prediction.get('confidence', 0.0)
                    
                    # ปรับ signal ตามการทำนาย
                    if prediction == 'BULLISH_REVERSAL':
                        if signal.direction == 'SELL':
                            signal.direction = 'BUY'
                            signal.reason = f"{signal.reason} + AI Prediction: {prediction}"
                            self.log(f"🔮 AI Signal Adjustment: SELL → BUY (BULLISH_REVERSAL)", "INFO")
                            self.log(f"   Confidence: {confidence:.1%}", "INFO")
                            
                    elif prediction == 'BEARISH_REVERSAL':
                        if signal.direction == 'BUY':
                            signal.direction = 'SELL'
                            signal.reason = f"{signal.reason} + AI Prediction: {prediction}"
                            self.log(f"🔮 AI Signal Adjustment: BUY → SELL (BEARISH_REVERSAL)", "INFO")
                            self.log(f"   Confidence: {confidence:.1%}", "INFO")
                            
                    elif prediction == 'BULLISH_TREND':
                        if signal.direction == 'BUY':
                            self.log(f"🔮 AI Prediction: {prediction} - Increased confidence for BUY", "INFO")
                        elif signal.direction == 'SELL':
                            self.log(f"🔮 AI Prediction: {prediction} - Decreased confidence for SELL", "INFO")
                            
                    elif prediction == 'BEARISH_TREND':
                        if signal.direction == 'SELL':
                            self.log(f"🔮 AI Prediction: {prediction} - Increased confidence for SELL", "INFO")
                        elif signal.direction == 'BUY':
                            self.log(f"🔮 AI Prediction: {prediction} - Decreased confidence for BUY", "INFO")
                    
                    # แสดงคำแนะนำจาก AI
                    recommendations = market_prediction.get('recommendations', [])
                    if recommendations:
                        self.log(f"💡 AI Recommendations:", "INFO")
                        for rec in recommendations:
                            self.log(f"   {rec}", "INFO")
                            
            except Exception as e:
                self.log(f"Warning: AI Market Prediction integration failed: {str(e)}", "WARNING")
            
            # 🆕 PHASE 1.6: Market Intelligence Integration (เดิม)
            if self.market_intelligence_enabled:
                try:
                    market_integration = self.integrate_market_intelligence_with_trading(signal)
                    if market_integration and market_integration.get('signal_enhanced'):
                        self.log(f"🔗 Market Intelligence: Signal enhanced with {len(market_integration.get('recommendations', []))} adjustments", "INFO")
                        # ปรับ signal confidence ตาม market intelligence
                        if hasattr(signal, 'confidence'):
                            original_confidence = signal.confidence
                            signal.confidence = market_integration.get('final_confidence', original_confidence)
                            self.log(f"📊 Signal confidence adjusted: {original_confidence:.2f} → {signal.confidence:.2f}", "INFO")
                except Exception as e:
                    self.log(f"Warning: Market intelligence integration failed: {str(e)}", "WARNING")
            
            # 🎯 PHASE 1.6: Simple Balance Management (Distribution handled separately)
            if self.balance_protection_enabled:
                balance_status = self._check_simple_portfolio_balance()
                if balance_status['needs_attention']:
                    self.log(f"⚠️ Balance Alert: {balance_status['message']}", "WARNING")
                    
                    # Simple Signal Redirection (without distribution logic)
                    if balance_status['imbalance_type'] == 'BUY_HEAVY' and signal.direction == 'BUY':
                        signal.direction = 'SELL'
                        signal.reason = f"Balance Protection: {balance_status['message']}"
                        self.log(f"🔄 Balance Redirect: BUY → SELL | {balance_status['message']}", "INFO")
                        
                    elif balance_status['imbalance_type'] == 'SELL_HEAVY' and signal.direction == 'SELL':
                        signal.direction = 'BUY'
                        signal.reason = f"Balance Protection: {balance_status['message']}"
                        self.log(f"🔄 Balance Redirect: SELL → BUY | {balance_status['message']}", "INFO")
            
            # 🎯 Simple Zone Analysis (Distribution handled separately)
            if zone_analysis.get('distribution_score', 100) < 20:
                self.log(f"⚠️ Zone Warning: Poor zone distribution (score: {zone_analysis['distribution_score']:.1f})", "WARNING")
                signal.reason = f"{signal.reason} + Zone Warning: Poor distribution detected"
            
            # Check position clustering first
            if self.force_zone_diversification and hasattr(signal, 'price') and signal.price:
                if self.check_position_clustering(signal.price):
                    # Try to find alternative zone for signal
                    alternative_zone = self.find_best_zone_for_signal(signal, zone_analysis)
                    if alternative_zone['should_redirect']:
                        result['action'] = 'redirect'
                        result['details'].update(alternative_zone)
                        result['details']['reason'] = f"Zone diversification: {alternative_zone['reason']}"
                        return result
                    else:
                        result['action'] = 'skip'
                        result['details']['reason'] = 'Position clustering prevention - no suitable alternative'
                        self.log(f"🚫 Signal SKIPPED: {signal.direction} - Position clustering prevented")
                        return result
            
            # 1. Check redirect cooldown
            if (self.last_redirect_time and 
                (datetime.now() - self.last_redirect_time).seconds < self.redirect_cooldown):
                return result
            
            # 2. Check redirect ratio limit
            if self.total_signals > 0:
                current_redirect_ratio = self.total_redirects / self.total_signals
                if current_redirect_ratio >= self.max_redirect_ratio:
                    result['details']['reason'] = 'Redirect ratio limit reached'
                    return result
            
            # 3. Analyze current balance
            total_volume = self.buy_volume + self.sell_volume
            if total_volume <= 0:
                return result
            
            buy_ratio = self.buy_volume / total_volume
            
            # 🎯 PHASE 2: Zone-Based Redirect Analysis
            zone_redirect_analysis = self.should_redirect_for_zone_balance(signal, zone_analysis, buy_ratio)
            
            if zone_redirect_analysis['should_redirect']:
                result['action'] = 'redirect'
                result['details'].update(zone_redirect_analysis)
                self.log(f"🔄 Zone-Based REDIRECT: {signal.direction} → {zone_redirect_analysis['reason']}")
                return result
            
            # 4. Check traditional volume-based redirect
            redirect_analysis = self.analyze_redirect_opportunity(signal, buy_ratio)
            
            if redirect_analysis['should_redirect']:
                result['action'] = 'redirect'
                result['details'].update(redirect_analysis)
                self.log(f"🔄 Volume-Based REDIRECT: {signal.direction} → Close {redirect_analysis['target_type']}")
                self.log(f"   Reason: {redirect_analysis['reason']}")
                return result
            
            # 5. Check if should skip (extreme cases)
            if self.should_skip_signal(signal, buy_ratio):
                result['action'] = 'skip'
                result['details']['reason'] = 'Signal skipped for portfolio protection'
                return result
            
            # 🎯 Simple Signal Processing (Distribution handled separately)
            self.log(f"🎯 Signal processed: {signal.direction} - {signal.reason}", "INFO")
            
            # 6. Final zone distribution check (relaxed threshold)
            if zone_analysis['distribution_score'] < 20:  # Only skip if very poor distribution (was 30)
                self.log(f"⚠️ Very poor zone distribution (score: {zone_analysis['distribution_score']:.1f}) - allowing signal")
                result['details']['reason'] += ' - Poor zone distribution warning'
            
            return result
            
        except Exception as e:
            self.log(f"Error in enhanced smart signal router: {str(e)}", "ERROR")
            return {'action': 'execute', 'details': {'reason': 'Router error - default execute'}}

    def _check_simple_portfolio_balance(self) -> dict:
        """🎯 ตรวจสอบ portfolio balance แบบเรียบง่าย (Distribution handled separately)"""
        try:
            if not self.positions:
                return {'needs_attention': False, 'message': 'No positions available'}
            
            # คำนวณ volume balance
            buy_volume = sum(p.volume for p in self.positions if p.type == 'BUY')
            sell_volume = sum(p.volume for p in self.positions if p.type == 'SELL')
            total_volume = buy_volume + sell_volume
            
            if total_volume <= 0:
                return {'needs_attention': False, 'message': 'No volume available'}
            
            buy_ratio = buy_volume / total_volume
            sell_ratio = sell_volume / total_volume
            
            # ตรวจสอบ imbalance (ปรับให้เหมาะสม)
            imbalance_threshold = 0.6  # 60% เป็นขีดจำกัด (ลดลง)
            
            # 🆕 Debug: แสดง balance check
            self.log(f"🔍 Balance Check: BUY {buy_ratio:.1%} vs SELL {sell_ratio:.1%} | Threshold: {imbalance_threshold:.1%}", "INFO")
            
            if buy_ratio > imbalance_threshold:
                self.log(f"⚠️ BUY Heavy Detected: {buy_ratio:.1%} > {imbalance_threshold:.1%}", "WARNING")
                return {
                    'needs_attention': True,
                    'imbalance_type': 'BUY_HEAVY',
                    'message': f'BUY heavy: {buy_ratio:.1%} vs {sell_ratio:.1%}',
                    'buy_ratio': buy_ratio,
                    'sell_ratio': sell_ratio
                }
            elif sell_ratio > imbalance_threshold:
                return {
                    'needs_attention': True,
                    'imbalance_type': 'SELL_HEAVY',
                    'message': f'SELL heavy: {sell_ratio:.1%} vs {buy_ratio:.1%}',
                    'buy_ratio': buy_ratio,
                    'sell_ratio': sell_ratio
                }
            else:
                return {
                    'needs_attention': False,
                    'message': f'Portfolio balanced: BUY {buy_ratio:.1%} vs SELL {sell_ratio:.1%}',
                    'buy_ratio': buy_ratio,
                    'sell_ratio': sell_ratio
                }
                
        except Exception as e:
            self.log(f"Error in simple portfolio balance check: {str(e)}", "ERROR")
            return {'needs_attention': False, 'error': str(e)}

    def independent_portfolio_distribution_system(self):
        """🔄 Independent Portfolio Distribution System - ทำงานแยกจาก Signal System"""
        try:
            # 🆕 Debug: แสดงการเริ่มทำงานของ Independent Distribution System
            self.log(f"🔄 Independent Distribution System: Starting analysis", "INFO")
            
            if not self.positions or len(self.positions) < 2:
                self.log(f"🔄 Independent Distribution System: Insufficient positions ({len(self.positions) if self.positions else 0})", "INFO")
                return {'success': True, 'message': 'Insufficient positions for distribution analysis'}
            
            # 🆕 Debug: แสดงข้อมูล portfolio
            buy_positions = [p for p in self.positions if p.type == 'BUY']
            sell_positions = [p for p in self.positions if p.type == 'SELL']
            buy_ratio = len(buy_positions) / len(self.positions) if self.positions else 0
            sell_ratio = len(sell_positions) / len(self.positions) if self.positions else 0
            
            self.log(f"🔍 Distribution Debug: BUY {len(buy_positions)} ({buy_ratio:.1%}) vs SELL {len(sell_positions)} ({sell_ratio:.1%})", "INFO")
            
            # 1. 📊 วิเคราะห์ portfolio distribution ปัจจุบัน
            zone_analysis = self.analyze_position_zones()
            if 'error' in zone_analysis:
                return {'success': False, 'error': zone_analysis['error']}
            
            advanced_distribution = zone_analysis.get('advanced_distribution', {})
            if 'error' in advanced_distribution:
                return {'success': False, 'error': advanced_distribution['error']}
            
            # 🆕 Debug: แสดง advanced distribution results
            self.log(f"🔍 Advanced Distribution: {advanced_distribution.get('distribution_quality', 'UNKNOWN')} | Needs Improvement: {advanced_distribution.get('needs_distribution_improvement', False)}", "INFO")
            
            # 🆕 Debug: แสดง BUY/SELL balance
            buy_sell_balance = advanced_distribution.get('buy_sell_balance', {})
            if buy_sell_balance:
                buy_count = buy_sell_balance.get('buy_count', 0)
                sell_count = buy_sell_balance.get('sell_count', 0)
                buy_ratio = buy_sell_balance.get('buy_ratio', 0)
                sell_ratio = buy_sell_balance.get('sell_ratio', 0)
                self.log(f"🔍 BUY/SELL Balance: BUY {buy_count} ({buy_ratio:.1%}) vs SELL {sell_count} ({sell_ratio:.1%})", "INFO")
            
            if advanced_distribution.get('price_gaps'):
                gap_count = len(advanced_distribution['price_gaps'])
                poor_gaps = len([g for g in advanced_distribution['price_gaps'] if g.get('gap_quality') == 'POOR'])
                medium_gaps = len([g for g in advanced_distribution['price_gaps'] if g.get('gap_quality') == 'MEDIUM'])
                good_gaps = len([g for g in advanced_distribution['price_gaps'] if g.get('gap_quality') == 'GOOD'])
                
                self.log(f"🔍 Price Gaps: Total {gap_count} | POOR: {poor_gaps} | MEDIUM: {medium_gaps} | GOOD: {good_gaps}", "INFO")
            
            # 2. 🎯 ตรวจสอบ distribution quality
            distribution_quality = advanced_distribution.get('distribution_quality', 'UNKNOWN')
            needs_improvement = advanced_distribution.get('needs_distribution_improvement', False)
            
            if not needs_improvement:
                self.log(f"🔍 Distribution Analysis: No improvement needed - Quality: {distribution_quality}", "INFO")
                return {'success': True, 'message': 'Portfolio distribution is already good'}
            
            # 3. 🧠 AI Optimization Actions
            optimization_result = {
                'success': True,
                'actions_taken': [],
                'improvements_made': [],
                'recommendations': [],
                'optimization_score': 0.0,
                'distribution_quality': distribution_quality
            }
            
            # 🆕 4. Recovery Mode - ตรวจสอบและฟื้นฟูไม้ที่ติดลบ
            recovery_mode_result = self._execute_portfolio_recovery_mode()
            if recovery_mode_result['success']:
                optimization_result['actions_taken'].append({
                    'action': 'RECOVERY_MODE',
                    'result': recovery_mode_result['message'],
                    'priority': 'HIGH'
                })
                optimization_result['improvements_made'].append('Executed portfolio recovery mode')
                optimization_result['optimization_score'] += 20.0
            
            if needs_improvement:
                distribution_actions = advanced_distribution.get('optimal_distribution_actions', [])
                
                # 🆕 Debug: แสดง actions ที่จะ execute
                if distribution_actions:
                    self.log(f"🚀 Portfolio Distribution Actions: {len(distribution_actions)} actions to execute", "INFO")
                    for i, action in enumerate(distribution_actions):
                        self.log(f"  {i+1}. {action.get('action', 'UNKNOWN')} - {action.get('reason', 'No reason')} (Priority: {action.get('priority', 'UNKNOWN')})", "INFO")
                
                for action in distribution_actions:
                    if action.get('priority') == 'HIGH':
                        # Execute high priority actions
                        if action['action'] == 'CLOSE_CLUSTERED':
                            close_result = self._execute_clustered_position_closure()
                            if close_result['success']:
                                optimization_result['actions_taken'].append({
                                    'action': 'CLOSE_CLUSTERED',
                                    'result': close_result['message'],
                                    'priority': 'HIGH'
                                })
                                optimization_result['improvements_made'].append('Closed clustered positions for better distribution')
                                optimization_result['optimization_score'] += 15.0
                        
                        elif action['action'] == 'REDISTRIBUTE_PROFITS':
                            redistribute_result = self._execute_profit_redistribution()
                            if redistribute_result['success']:
                                optimization_result['actions_taken'].append({
                                    'action': 'REDISTRIBUTE_PROFITS',
                                    'result': redistribute_result['message'],
                                    'priority': 'HIGH'
                                })
                                optimization_result['improvements_made'].append('Redistributed profits for better spread')
                                optimization_result['optimization_score'] += 10.0
                        
                        elif action['action'] == 'REDISTRIBUTE_RISKS':
                            risk_redistribute_result = self._execute_risk_redistribution()
                            if risk_redistribute_result['success']:
                                optimization_result['actions_taken'].append({
                                    'action': 'REDISTRIBUTE_RISKS',
                                    'result': risk_redistribute_result['message'],
                                    'priority': 'HIGH'
                                })
                                optimization_result['improvements_made'].append('Redistributed risks for better spread')
                                optimization_result['optimization_score'] += 10.0
                        
                        # 🆕 เพิ่ม Portfolio Balance Actions
                        elif action['action'] in ['BALANCE_BUY_HEAVY', 'BALANCE_SELL_HEAVY', 'IMPROVE_BUY_BALANCE', 'IMPROVE_SELL_BALANCE']:
                            self.log(f"🚀 Executing HIGH Priority Portfolio Balance Action: {action['action']}", "INFO")
                            balance_result = self._execute_portfolio_balance_improvement(action)
                            if balance_result['success']:
                                optimization_result['actions_taken'].append({
                                    'action': action['action'],
                                    'result': balance_result['message'],
                                    'priority': 'HIGH'
                                })
                                optimization_result['improvements_made'].append(f'Portfolio balance improved: {action["action"]}')
                                optimization_result['optimization_score'] += 20.0
                                self.log(f"✅ Successfully executed portfolio balance action: {action['action']}", "INFO")
                            else:
                                self.log(f"⚠️ Failed to execute portfolio balance action {action['action']}: {balance_result.get('error', 'Unknown error')}", "WARNING")
                        
                        # 🆕 เพิ่ม EMERGENCY Buy/Sell Balance Actions
                        elif action['action'] == 'EMERGENCY_BUY_SELL_BALANCE':
                            self.log(f"🚨 Executing EMERGENCY Buy/Sell Balance: {action['reason']}", "INFO")
                            emergency_result = self._execute_emergency_buy_sell_balance(action)
                            if emergency_result['success']:
                                optimization_result['actions_taken'].append({
                                    'action': action['action'],
                                    'result': emergency_result['message'],
                                    'priority': 'EMERGENCY'
                                })
                                optimization_result['improvements_made'].append(f'Emergency separation reduction: {action["action"]}')
                                optimization_result['optimization_score'] += 30.0
                                self.log(f"✅ Successfully executed emergency action: {action['action']}", "INFO")
                            else:
                                self.log(f"⚠️ Failed to execute emergency action {action['action']}: {emergency_result.get('error', 'Unknown error')}", "WARNING")
                        
                        # 🆕 เพิ่ม Separation Reduction Actions
                        elif action['action'] == 'OPEN_SELL_TO_REDUCE_SEPARATION':
                            self.log(f"📉 Executing Open SELL to Reduce Separation: {action['reason']}", "INFO")
                            separation_result = self._execute_open_sell_to_reduce_separation(action)
                            if separation_result['success']:
                                optimization_result['actions_taken'].append({
                                    'action': action['action'],
                                    'result': separation_result['message'],
                                    'priority': 'HIGH'
                                })
                                optimization_result['improvements_made'].append(f'Separation reduction: {action["action"]}')
                                optimization_result['optimization_score'] += 25.0
                                self.log(f"✅ Successfully executed separation action: {action['action']}", "INFO")
                            else:
                                self.log(f"⚠️ Failed to execute separation action {action['action']}: {separation_result.get('error', 'Unknown error')}", "WARNING")
                        
                        elif action['action'] == 'OPEN_BUY_TO_REDUCE_SEPARATION':
                            self.log(f"📈 Executing Open BUY to Reduce Separation: {action['reason']}", "INFO")
                            separation_result = self._execute_open_buy_to_reduce_separation(action)
                            if separation_result['success']:
                                optimization_result['actions_taken'].append({
                                    'action': action['action'],
                                    'result': separation_result['message'],
                                    'priority': 'HIGH'
                                })
                                optimization_result['improvements_made'].append(f'Separation reduction: {action["action"]}')
                                optimization_result['optimization_score'] += 25.0
                                self.log(f"✅ Successfully executed separation action: {action['action']}", "INFO")
                            else:
                                self.log(f"⚠️ Failed to execute separation action {action['action']}: {separation_result.get('error', 'Unknown error')}", "WARNING")
                    
                    elif action.get('priority') == 'MEDIUM':
                        # Execute medium priority actions
                        if action['action'] == 'IMPROVE_PORTFOLIO_BALANCE':
                            self.log(f"🚀 Executing MEDIUM Priority Portfolio Balance Action: {action['action']}", "INFO")
                            balance_result = self._execute_portfolio_balance_improvement(action)
                            if balance_result['success']:
                                optimization_result['actions_taken'].append({
                                    'action': action['action'],
                                    'result': balance_result['message'],
                                    'priority': 'MEDIUM'
                                })
                                optimization_result['improvements_made'].append(f'Portfolio balance improved: {action["action"]}')
                                optimization_result['optimization_score'] += 15.0
                                self.log(f"✅ Successfully executed portfolio balance action: {action['action']}", "INFO")
                            else:
                                self.log(f"⚠️ Failed to execute portfolio balance action {action['action']}: {balance_result.get('error', 'Unknown error')}", "WARNING")
                
                # 4. 📈 คำนวณ final optimization score
                optimization_result['optimization_score'] = min(100.0, optimization_result['optimization_score'])
                
                if optimization_result['actions_taken']:
                    optimization_result['recommendations'].append(f"Distribution optimization completed: {len(optimization_result['actions_taken'])} actions taken")
                    optimization_result['recommendations'].append(f"Final score: {optimization_result['optimization_score']:.1f}/100")
                else:
                    optimization_result['recommendations'].append("No immediate distribution actions needed")
            
            return optimization_result
            
        except Exception as e:
            self.log(f"Error in independent portfolio distribution system: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}

    def _execute_portfolio_recovery_mode(self) -> dict:
        """🚀 Portfolio Recovery Mode: ฟื้นฟูไม้ที่ติดลบโดยไม่คัท loss"""
        try:
            recovery_result = {
                'success': False,
                'message': '',
                'actions_taken': [],
                'positions_recovered': 0,
                'total_profit_generated': 0.0
            }
            
            if not self.positions:
                recovery_result['message'] = 'No positions to recover'
                return recovery_result
            
            # 1. ตรวจสอบไม้ที่ติดลบ
            losing_positions = [p for p in self.positions if p.profit < 0]
            profitable_positions = [p for p in self.positions if p.profit > 0]
            
            if not losing_positions:
                recovery_result['message'] = 'No losing positions to recover'
                return recovery_result
            
            if not profitable_positions:
                recovery_result['message'] = 'No profitable positions for recovery'
                return recovery_result
            
            self.log(f"🚀 Portfolio Recovery Mode: {len(losing_positions)} losing, {len(profitable_positions)} profitable", "INFO")
            
            # 2. วิเคราะห์ไม้ที่ติดลบมากที่สุด
            sorted_losses = sorted(losing_positions, key=lambda x: abs(x.profit), reverse=True)
            
            for loss_pos in sorted_losses[:3]:  # Top 3 biggest losses
                loss_amount = abs(loss_pos.profit)
                
                # ตรวจสอบว่ามี profit buffer เพียงพอหรือไม่
                if hasattr(self, 'hedge_profit_buffer_tracker'):
                    if loss_pos.ticket in self.hedge_profit_buffer_tracker:
                        hedge_info = self.hedge_profit_buffer_tracker[loss_pos.ticket]
                        current_buffer = hedge_info.get('current_profit_buffer', 0)
                        target_buffer = hedge_info.get('target_profit_buffer', 0)
                        
                        if current_buffer >= target_buffer:
                            self.log(f"🎯 Position {loss_pos.ticket} ready for recovery: Buffer ${current_buffer:.2f} >= Target ${target_buffer:.2f}", "INFO")
                            continue  # ไม้นี้พร้อมฟื้นฟูแล้ว
                
                # 3. สร้าง profit buffer สำหรับไม้ที่ติดลบ
                buffer_created = self._create_profit_buffer_for_position(loss_pos)
                if buffer_created:
                    recovery_result['actions_taken'].append(f"Created profit buffer for position {loss_pos.ticket}")
                    recovery_result['positions_recovered'] += 1
                    recovery_result['total_profit_generated'] += buffer_created
                    
                    self.log(f"✅ Created profit buffer ${buffer_created:.2f} for position {loss_pos.ticket}", "SUCCESS")
            
            # 4. สรุปผลลัพธ์
            if recovery_result['positions_recovered'] > 0:
                recovery_result['success'] = True
                recovery_result['message'] = f"Recovered {recovery_result['positions_recovered']} positions with ${recovery_result['total_profit_generated']:.2f} profit buffer"
                self.log(f"🚀 Portfolio Recovery Mode: {recovery_result['message']}", "SUCCESS")
            else:
                recovery_result['message'] = 'No positions recovered - waiting for profit buffer to build'
                self.log(f"⏳ Portfolio Recovery Mode: {recovery_result['message']}", "INFO")
            
            return recovery_result
            
        except Exception as e:
            self.log(f"Error in portfolio recovery mode: {str(e)}", "ERROR")
            return {
                'success': False,
                'message': f'Error: {str(e)}',
                'actions_taken': [],
                'positions_recovered': 0,
                'total_profit_generated': 0.0
            }

    def _create_profit_buffer_for_position(self, loss_position: Position) -> float:
        """🎯 สร้าง profit buffer สำหรับไม้ที่ติดลบ"""
        try:
            if not self.positions:
                return 0.0
            
            # 1. ตรวจสอบ margin และ portfolio health
            portfolio_health = self.check_portfolio_health()
            if not portfolio_health['can_trade']:
                self.log(f"⚠️ Cannot create profit buffer: Portfolio health check failed", "WARNING")
                return 0.0
            
            # 2. คำนวณ lot size ที่เหมาะสม
            loss_amount = abs(loss_position.profit)
            target_buffer = loss_amount * 1.2  # ต้องการ profit buffer 120% ของ loss
            
            # 3. ตรวจสอบ margin ที่จะใช้
            if MT5_AVAILABLE and mt5:
                account_info = mt5.account_info()
                if account_info and account_info.margin > 0:
                    current_margin_level = (account_info.equity / account_info.margin) * 100
                    
                    # คำนวณ lot size ที่เหมาะสมกับ margin
                    max_lot_size = min(0.05, (account_info.margin_free / 100000) * 0.01)  # จำกัด lot size
                    if max_lot_size < 0.01:
                        self.log(f"⚠️ Cannot create profit buffer: Insufficient free margin", "WARNING")
                        return 0.0
                    
                    # 4. สร้าง hedge position เพื่อสร้าง profit buffer
                    hedge_type = "SELL" if loss_position.type == "BUY" else "BUY"
                    hedge_volume = min(max_lot_size, 0.03)  # จำกัด lot size ไม่เกิน 0.03
                    
                    # 5. เปิด hedge position
                    success = self.execute_auto_hedge(loss_position, "PROFIT_BUFFER_CREATION")
                    if success:
                        # บันทึก hedge info สำหรับ profit buffer tracking
                        if not hasattr(self, 'hedge_profit_buffer_tracker'):
                            self.hedge_profit_buffer_tracker = {}
                        
                        hedge_info = {
                            'stuck_position_ticket': loss_position.ticket,
                            'stuck_position_type': loss_position.type,
                            'hedge_type': hedge_type,
                            'hedge_volume': hedge_volume,
                            'created_time': datetime.now(),
                            'target_profit_buffer': target_buffer,
                            'current_profit_buffer': 0.0,
                            'status': 'ACTIVE'
                        }
                        
                        self.hedge_profit_buffer_tracker[loss_position.ticket] = hedge_info
                        
                        self.log(f"✅ Created profit buffer hedge: {hedge_type} {hedge_volume:.2f} lots", "SUCCESS")
                        self.log(f"   Target Profit Buffer: ${target_buffer:.2f}", "INFO")
                        
                        return target_buffer * 0.8  # Return 80% ของ target เป็น estimated profit
                    else:
                        self.log(f"❌ Failed to create profit buffer hedge", "ERROR")
                        return 0.0
            
            return 0.0
            
        except Exception as e:
            self.log(f"Error creating profit buffer for position: {str(e)}", "ERROR")
            return 0.0

    def _ai_distribution_engine(self, signal: 'Signal') -> dict:
        """🧠 AI Distribution Engine: ตัดสินใจการกระจายตัวแบบฉลาด"""
        try:
            ai_result = {
                'success': False,
                'signal': signal,
                'reason': 'No AI distribution action needed',
                'distribution_actions': [],
                'confidence': 0.7
            }
            
            # 1. 📊 วิเคราะห์ portfolio distribution
            zone_analysis = self.analyze_position_zones()
            if 'error' in zone_analysis:
                return ai_result
            
            advanced_distribution = zone_analysis.get('advanced_distribution', {})
            if 'error' in advanced_distribution:
                return ai_result
            
            # 2. 🎯 ตรวจสอบว่าต้องการ distribution improvement หรือไม่
            if not advanced_distribution.get('needs_distribution_improvement', False):
                return ai_result
            
            # 3. 🧠 AI ตัดสินใจการกระจายตัว
            distribution_actions = advanced_distribution.get('optimal_distribution_actions', [])
            
            if distribution_actions:
                ai_result['success'] = True
                ai_result['distribution_actions'] = distribution_actions
                ai_result['confidence'] = 0.8
                
                # เลือก action ที่สำคัญที่สุด
                high_priority_actions = [a for a in distribution_actions if a.get('priority') == 'HIGH']
                if high_priority_actions:
                    primary_action = high_priority_actions[0]
                    ai_result['reason'] = f"AI Distribution: {primary_action['action']} - {primary_action['reason']}"
                else:
                    medium_priority_actions = [a for a in distribution_actions if a.get('priority') == 'MEDIUM']
                    if medium_priority_actions:
                        primary_action = medium_priority_actions[0]
                        ai_result['reason'] = f"AI Distribution: {primary_action['action']} - {primary_action['reason']}"
                    else:
                        ai_result['reason'] = f"AI Distribution: {len(distribution_actions)} actions recommended"
                
                # ปรับ signal ตาม AI recommendation
                if 'CLOSE_CLUSTERED' in [a['action'] for a in distribution_actions]:
                    signal.reason = f"{signal.reason} + AI: Close clustered positions for better distribution"
                    ai_result['confidence'] = 0.9
                
                elif 'REDISTRIBUTE_PROFITS' in [a['action'] for a in distribution_actions]:
                    signal.reason = f"{signal.reason} + AI: Redistribute profits for better spread"
                    ai_result['reason'] = f"AI Distribution: {primary_action['action']} - {primary_action['reason']}"
                    ai_result['confidence'] = 0.8
                
                elif 'REDISTRIBUTE_RISKS' in [a['action'] for a in distribution_actions]:
                    signal.reason = f"{signal.reason} + AI: Redistribute risks for better spread"
                    ai_result['reason'] = f"AI Distribution: {primary_action['action']} - {primary_action['reason']}"
                    ai_result['confidence'] = 0.8
            
            return ai_result
            
        except Exception as e:
            self.log(f"Error in AI distribution engine: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}

    def continuous_portfolio_optimization(self):
        """🔄 Continuous Portfolio Optimization: ปรับ portfolio อย่างต่อเนื่อง"""
        try:
            if not self.positions or len(self.positions) < 2:
                return {'success': False, 'message': 'Insufficient positions for optimization'}
            
            optimization_result = {
                'success': True,
                'actions_taken': [],
                'improvements_made': [],
                'recommendations': [],
                'optimization_score': 0.0
            }
            
            # 1. 📊 วิเคราะห์ portfolio distribution ปัจจุบัน
            zone_analysis = self.analyze_position_zones()
            if 'error' in zone_analysis:
                return {'success': False, 'error': zone_analysis['error']}
            
            advanced_distribution = zone_analysis.get('advanced_distribution', {})
            if 'error' in advanced_distribution:
                return {'success': False, 'error': advanced_distribution['error']}
            
            # 2. 🎯 ตรวจสอบ distribution quality
            distribution_quality = advanced_distribution.get('distribution_quality', 'UNKNOWN')
            needs_improvement = advanced_distribution.get('needs_distribution_improvement', False)
            
            if distribution_quality == 'GOOD':
                optimization_result['optimization_score'] = 85.0
                optimization_result['recommendations'].append('Portfolio distribution is already good - maintain current structure')
                return optimization_result
            
            # 3. 🧠 AI Optimization Actions
            if needs_improvement:
                distribution_actions = advanced_distribution.get('optimal_distribution_actions', [])
                
                for action in distribution_actions:
                    if action.get('priority') == 'HIGH':
                        # Execute high priority actions
                        if action['action'] == 'CLOSE_CLUSTERED':
                            close_result = self._execute_clustered_position_closure()
                            if close_result['success']:
                                optimization_result['actions_taken'].append({
                                    'action': 'CLOSE_CLUSTERED',
                                    'result': close_result['message'],
                                    'priority': 'HIGH'
                                })
                                optimization_result['improvements_made'].append('Closed clustered positions for better distribution')
                                optimization_result['optimization_score'] += 15.0
                        
                        elif action['action'] == 'REDISTRIBUTE_PROFITS':
                            redistribute_result = self._execute_profit_redistribution()
                            if redistribute_result['success']:
                                optimization_result['actions_taken'].append({
                                    'action': 'REDISTRIBUTE_PROFITS',
                                    'result': redistribute_result['message'],
                                    'priority': 'HIGH'
                                })
                                optimization_result['improvements_made'].append('Redistributed profits for better spread')
                                optimization_result['optimization_score'] += 10.0
                        
                        elif action['action'] == 'REDISTRIBUTE_RISKS':
                            risk_redistribute_result = self._execute_risk_redistribution()
                            if risk_redistribute_result['success']:
                                optimization_result['actions_taken'].append({
                                    'action': 'REDISTRIBUTE_RISKS',
                                    'result': risk_redistribute_result['message'],
                                    'priority': 'HIGH'
                                })
                                optimization_result['improvements_made'].append('Redistributed risks for better spread')
                                optimization_result['optimization_score'] += 10.0
                
                # 4. 📈 คำนวณ final optimization score
                optimization_result['optimization_score'] = min(100.0, optimization_result['optimization_score'])
                
                if optimization_result['actions_taken']:
                    optimization_result['recommendations'].append(f"Optimization completed: {len(optimization_result['actions_taken'])} actions taken")
                    optimization_result['recommendations'].append(f"Final score: {optimization_result['optimization_score']:.1f}/100")
                else:
                    optimization_result['recommendations'].append("No immediate optimization actions needed")
            
            return optimization_result
            
        except Exception as e:
            self.log(f"Error in continuous portfolio optimization: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}

    def _execute_clustered_position_closure(self) -> dict:
        """🔒 ปิด clustered positions เพื่อปรับปรุง distribution"""
        try:
            # หา positions ที่ clustered กัน
            zone_analysis = self.analyze_position_zones()
            if 'error' in zone_analysis:
                return {'success': False, 'error': zone_analysis['error']}
            
            advanced_distribution = zone_analysis.get('advanced_distribution', {})
            if 'error' in advanced_distribution:
                return {'success': False, 'error': advanced_distribution['error']}
            
            poor_gaps = advanced_distribution.get('price_gaps', [])
            poor_gaps = [g for g in poor_gaps if g.get('gap_quality') == 'POOR']
            
            if not poor_gaps:
                return {'success': False, 'message': 'No clustered positions found'}
            
            # เลือก position ที่ควรปิด (profit ที่น้อยที่สุด)
            positions_to_close = []
            for gap in poor_gaps[:2]:  # ปิดแค่ 2 positions ก่อน
                pos1_ticket = gap.get('position1')
                pos2_ticket = gap.get('position2')
                
                pos1 = next((p for p in self.positions if p.ticket == pos1_ticket), None)
                pos2 = next((p for p in self.positions if p.ticket == pos2_ticket), None)
                
                if pos1 and pos2:
                    # เลือก position ที่ profit น้อยกว่า
                    if pos1.profit < pos2.profit:
                        positions_to_close.append(pos1)
                    else:
                        positions_to_close.append(pos2)
            
            # ปิด positions
            closed_count = 0
            for position in positions_to_close:
                if hasattr(self, 'close_position_smart'):
                    close_result = self.close_position_smart(position.ticket)
                    if close_result.get('success'):
                        closed_count += 1
                        self.log(f"🔒 Closed clustered position {position.ticket} for distribution improvement", "INFO")
            
            return {
                'success': True,
                'message': f'Closed {closed_count} clustered positions',
                'closed_count': closed_count
            }
            
        except Exception as e:
            self.log(f"Error executing clustered position closure: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}

    def _execute_profit_redistribution(self) -> dict:
        """💰 ปิดและเปิดใหม่ profitable positions เพื่อปรับปรุง distribution"""
        try:
            # หา profitable positions ที่ clustered กัน
            zone_analysis = self.analyze_position_zones()
            if 'error' in zone_analysis:
                return {'success': False, 'error': zone_analysis['error']}
            
            advanced_distribution = zone_analysis.get('advanced_distribution', {})
            if 'error' in advanced_distribution:
                return {'success': False, 'error': advanced_distribution['error']}
            
            profit_distribution = advanced_distribution.get('profit_distribution', {})
            if profit_distribution.get('price_spread') == 'GOOD':
                return {'success': False, 'message': 'Profit distribution is already good'}
            
            # หา profitable positions ที่ clustered กัน
            profitable_positions = [p for p in self.positions if hasattr(p, 'profit') and p.profit > 0]
            if len(profitable_positions) < 2:
                return {'success': False, 'message': 'Insufficient profitable positions for redistribution'}
            
            # เรียงตาม profit และเลือกตัวที่ profit น้อยที่สุด
            profitable_positions.sort(key=lambda x: x.profit)
            positions_to_close = profitable_positions[:2]  # ปิด 2 ตัวที่ profit น้อยที่สุด
            
            # ปิด positions
            closed_count = 0
            total_profit_closed = 0.0
            for position in positions_to_close:
                if hasattr(self, 'close_position_smart'):
                    close_result = self.close_position_smart(position.ticket)
                    if close_result.get('success'):
                        closed_count += 1
                        total_profit_closed += position.profit
                        self.log(f"💰 Closed profitable position {position.ticket} (profit: {position.profit:.2f}) for redistribution", "INFO")
            
            return {
                'success': True,
                'message': f'Closed {closed_count} profitable positions (total profit: {total_profit_closed:.2f})',
                'closed_count': closed_count,
                'total_profit_closed': total_profit_closed
            }
            
        except Exception as e:
            self.log(f"Error executing profit redistribution: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}

    def _execute_risk_redistribution(self) -> dict:
        """⚠️ ปิดและเปิดใหม่ risky positions เพื่อปรับปรุง distribution"""
        
        try:
            # หา losing positions ที่ clustered กัน
            zone_analysis = self.analyze_position_zones()
            if 'error' in zone_analysis:
                return {'success': False, 'error': zone_analysis['error']}
            
            advanced_distribution = zone_analysis.get('advanced_distribution', {})
            if 'error' in advanced_distribution:
                return {'success': False, 'error': advanced_distribution['error']}
            
            risk_distribution = advanced_distribution.get('risk_distribution', {})
            if risk_distribution.get('price_spread') == 'GOOD':
                return {'success': False, 'message': 'Risk distribution is already good'}
            
            # หา losing positions ที่ clustered กัน
            losing_positions = [p for p in self.positions if hasattr(p, 'profit') and p.profit < 0]
            if len(losing_positions) < 2:
                return {'success': False, 'message': 'Insufficient losing positions for redistribution'}
            
            # เรียงตาม loss และเลือกตัวที่ loss มากที่สุด
            losing_positions.sort(key=lambda x: x.profit)  # profit ติดลบ = loss
            positions_to_close = losing_positions[:2]  # ปิด 2 ตัวที่ loss มากที่สุด
            
            # ปิด positions
            closed_count = 0
            total_loss_closed = 0.0
            for position in positions_to_close:
                if hasattr(self, 'close_position_smart'):
                    close_result = self.close_position_smart(position.ticket)
                    if close_result.get('success'):
                        closed_count += 1
                        total_loss_closed += abs(position.profit)
                        self.log(f"⚠️ Closed losing position {position.ticket} (loss: {abs(position.profit):.2f}) for redistribution", "INFO")
            
            return {
                'success': True,
                'message': f'Closed {closed_count} losing positions (total loss: {total_loss_closed:.2f})',
                'closed_count': closed_count,
                'total_loss_closed': total_loss_closed
            }
            
        except Exception as e:
            self.log(f"Error executing risk redistribution: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}

    def _execute_portfolio_balance_improvement(self, action: dict) -> dict:
        """🚀 Execute Portfolio Balance Improvement Actions"""
        try:
            action_name = action.get('action', '')
            action_type = action.get('action_type', '')
            reason = action.get('reason', '')
            
            self.log(f"🚀 Executing Portfolio Balance Action: {action_name} - {reason}", "INFO")
            
            if action_type == 'OPEN_SELL':
                return self._execute_buy_heavy_balance(action)
            elif action_type == 'OPEN_BUY':
                return self._execute_sell_heavy_balance(action)
            elif action_type == 'OPEN_POSITIONS':
                return self._execute_general_balance_improvement(action)
            elif action_type == '':  # ถ้าไม่มี action_type ให้ใช้ general improvement
                return self._execute_general_balance_improvement(action)
            else:
                return {'success': False, 'error': f'Unknown action type: {action_type}'}
                
        except Exception as e:
            self.log(f"Error executing portfolio balance improvement: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}
    
    def _execute_emergency_buy_sell_balance(self, action: dict) -> dict:
        """🚨 Execute EMERGENCY Buy/Sell Balance Action"""
        try:
            separation_points = action.get('separation_points', 0)
            target_reduction = action.get('target_reduction', 300)
            
            self.log(f"🚨 EMERGENCY: Reducing Buy/Sell separation from {separation_points:.0f} to {target_reduction} points", "WARNING")
            
            # วิเคราะห์ positions ปัจจุบัน
            buy_positions = [p for p in self.positions if p.order_type == 'BUY']
            sell_positions = [p for p in self.positions if p.order_type == 'SELL']
            
            if not buy_positions or not sell_positions:
                return {'success': False, 'error': 'Need both BUY and SELL positions for balance'}
            
            # คำนวณ target price สำหรับไม้ใหม่
            avg_buy_price = sum(p.open_price for p in buy_positions) / len(buy_positions)
            avg_sell_price = sum(p.open_price for p in sell_positions) / len(sell_positions)
            
            # เปิดไม้ใหม่เพื่อลดระยะห่าง
            if len(buy_positions) > len(sell_positions):
                # BUY heavy - เปิด SELL ใหม่
                target_price = avg_buy_price - (target_reduction / 1000)  # แปลง points เป็น price
                result = self._open_emergency_sell_position(target_price, action)
            else:
                # SELL heavy - เปิด BUY ใหม่
                target_price = avg_sell_price + (target_reduction / 1000)  # แปลง points เป็น price
                result = self._open_emergency_buy_position(target_price, action)
            
            return result
            
        except Exception as e:
            self.log(f"Error executing emergency buy/sell balance: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}
    
    def _execute_open_sell_to_reduce_separation(self, action: dict) -> dict:
        """📉 Execute Open SELL to Reduce Separation"""
        try:
            target_price_range = action.get('target_price_range', 'Near lowest BUY positions')
            
            # หา BUY positions ที่ต่ำสุด
            buy_positions = [p for p in self.positions if p.order_type == 'BUY']
            if not buy_positions:
                return {'success': False, 'error': 'No BUY positions found'}
            
            lowest_buy = min(buy_positions, key=lambda x: x.open_price)
            target_price = lowest_buy.open_price - 0.001  # เปิด SELL ต่ำกว่า BUY เล็กน้อย
            
            return self._open_emergency_sell_position(target_price, action)
            
        except Exception as e:
            self.log(f"Error executing open SELL to reduce separation: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}
    
    def _execute_open_buy_to_reduce_separation(self, action: dict) -> dict:
        """📈 Execute Open BUY to Reduce Separation"""
        try:
            target_price_range = action.get('target_price_range', 'Near highest SELL positions')
            
            # หา SELL positions ที่สูงสุด
            sell_positions = [p for p in self.positions if p.order_type == 'SELL']
            if not sell_positions:
                return {'success': False, 'error': 'No SELL positions found'}
            
            highest_sell = max(sell_positions, key=lambda x: x.open_price)
            target_price = highest_sell.open_price + 0.001  # เปิด BUY สูงกว่า SELL เล็กน้อย
            
            return self._open_emergency_buy_position(target_price, action)
            
        except Exception as e:
            self.log(f"Error executing open BUY to reduce separation: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}
    
    def _open_emergency_sell_position(self, target_price: float, action: dict) -> dict:
        """📉 เปิด SELL Position ฉุกเฉินเพื่อลดระยะห่างและกระจายตัวแบบสลับกัน"""
        try:
            # ตรวจสอบ portfolio health ก่อนเปิดไม้
            health_check = self.check_portfolio_health()
            if health_check['status'] == 'FAILED':
                return {'success': False, 'error': f'Portfolio health check failed: {health_check["warnings"]}'}
            
            # ตรวจสอบ order opening conditions
            order_check = self.check_order_opening_conditions(None)  # ไม่มี signal
            if order_check['status'] == 'FAILED':
                return {'success': False, 'error': f'Order opening check failed: {order_check["warnings"]}'}
            
            # 🆕 คำนวณตำแหน่งที่ดีที่สุดสำหรับ SELL แบบกระจายตัว
            optimal_price = self._find_optimal_sell_distribution_price()
            if optimal_price:
                target_price = optimal_price
                self.log(f"🎯 Found optimal SELL distribution price: {target_price:.5f}", "INFO")
            
            # คำนวณ volume ที่เหมาะสม
            emergency_volume = min(0.01, self.base_volume * 0.5)  # ใช้ volume เล็ก
            
            # 🆕 เปิดไม้ใหม่โดยตรงผ่าน MT5 (ไม่ผ่านระบบหลัก)
            order_result = self._open_direct_mt5_order('SELL', target_price, emergency_volume, action.get('reason', 'Smart distribution - SELL'))
            
            if order_result.get('success'):
                self.log(f"✅ Smart Distribution SELL opened: {target_price:.5f}, Volume: {emergency_volume}", "INFO")
                return {
                    'success': True,
                    'message': f'Smart Distribution SELL opened at {target_price:.5f}',
                    'volume': emergency_volume
                }
            else:
                return {'success': False, 'error': f'Failed to open smart distribution SELL: {order_result.get("error")}'}
            
        except Exception as e:
            self.log(f"Error opening smart distribution SELL position: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}
    
    def _open_emergency_buy_position(self, target_price: float, action: dict) -> dict:
        """📈 เปิด BUY Position ฉุกเฉินเพื่อลดระยะห่างและกระจายตัวแบบสลับกัน"""
        try:
            # 🆕 คำนวณตำแหน่งที่ดีที่สุดสำหรับ BUY แบบกระจายตัว
            optimal_price = self._find_optimal_buy_distribution_price()
            if optimal_price:
                target_price = optimal_price
                self.log(f"🎯 Found optimal BUY distribution price: {target_price:.5f}", "INFO")
            
            # คำนวณ volume ที่เหมาะสม
            emergency_volume = min(0.01, self.base_volume * 0.5)  # ใช้ volume เล็ก
            
            # 🆕 เปิดไม้ใหม่โดยตรงผ่าน MT5 (ไม่ผ่านระบบหลัก)
            order_result = self._open_direct_mt5_order('BUY', target_price, emergency_volume, action.get('reason', 'Smart distribution - BUY'))
            
            if order_result.get('success'):
                self.log(f"✅ Smart Distribution BUY opened: {target_price:.5f}, Volume: {emergency_volume}", "INFO")
                return {
                    'success': True,
                    'message': f'Smart Distribution BUY opened at {target_price:.5f}',
                    'volume': emergency_volume,
                    'ticket': order_result.get('ticket')
                }
            else:
                return {'success': False, 'error': f'Failed to open smart distribution BUY: {order_result.get("error")}'}
            
        except Exception as e:
            self.log(f"Error opening smart distribution BUY position: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}
    
    def _open_direct_mt5_order(self, order_type: str, price: float, volume: float, reason: str) -> dict:
        """🚀 เปิดไม้ใหม่โดยตรงผ่าน MT5 (ไม่ผ่านระบบหลัก) - ฉลาดขึ้น"""
        try:
            # 🧠 Smart Position Opening Check (ป้องกันการออกไม้มั่วซั่ว)
            smart_check = self._smart_position_opening_check(order_type, price, volume)
            if not smart_check['can_open']:
                self.log(f"🚫 Smart check failed: {smart_check['reason']}", "WARNING")
                for warning in smart_check['warnings']:
                    self.log(warning, "WARNING")
                return {'success': False, 'error': smart_check['reason']}
            
            # ตรวจสอบว่า MT5 พร้อมใช้งาน
            if not hasattr(self, 'mt5') or not self.mt5:
                return {'success': False, 'error': 'MT5 not available'}
            
            # สร้าง order request
            request = {
                "action": self.mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": volume,
                "type": self.mt5.ORDER_TYPE_BUY if order_type == 'BUY' else self.mt5.ORDER_TYPE_SELL,
                "price": price,
                "deviation": 20,
                "magic": 234000,
                "comment": f"Smart Distribution: {reason}",
                "type_time": self.mt5.ORDER_TIME_GTC,
                "type_filling": self.mt5.ORDER_FILLING_IOC,
            }
            
            # ส่ง order
            result = self.mt5.order_send(request)
            
            if result.retcode == self.mt5.TRADE_RETCODE_DONE:
                # 🆕 อัปเดตเวลาที่เปิดไม้ล่าสุด
                self.last_position_opened = datetime.now()
                
                self.log(f"✅ Smart Distribution {order_type} opened: {price:.5f}, Volume: {volume}, Ticket: {result.order}", "INFO")
                return {
                    'success': True,
                    'ticket': result.order,
                    'price': price,
                    'volume': volume,
                    'message': f'Smart Distribution {order_type} opened successfully'
                }
            else:
                error_msg = f"MT5 order failed: {result.retcode} - {result.comment}"
                self.log(f"❌ {error_msg}", "ERROR")
                return {'success': False, 'error': error_msg}
                
        except Exception as e:
            self.log(f"Error opening direct MT5 order: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}
    
    def _find_optimal_sell_distribution_price(self) -> float:
        """🎯 หาตำแหน่งที่ดีที่สุดสำหรับ SELL แบบกระจายตัวสลับกัน - ฉลาดขึ้น"""
        try:
            if not self.positions:
                return None
            
            # แยก BUY และ SELL positions
            buy_positions = [p for p in self.positions if p.order_type == 'BUY']
            sell_positions = [p for p in self.positions if p.order_type == 'SELL']
            
            if not buy_positions:
                return None
            
            # 🆕 ตรวจจับการกระจุกตัวของ BUY
            buy_clustering = self._detect_buy_clustering()
            if buy_clustering['is_clustered']:
                self.log(f"🚨 BUY Clustering Detected: {buy_clustering['cluster_count']} positions in {buy_clustering['cluster_range']:.3f} range", "WARNING")
                
                # หาตำแหน่งที่ดีที่สุดสำหรับ SELL ใหม่
                optimal_price = self._find_best_sell_position_for_buy_clustering(buy_clustering)
                if optimal_price:
                    self.log(f"🎯 Found optimal SELL position for BUY clustering: {optimal_price:.5f}", "INFO")
                    return optimal_price
            
            # 🆕 ตรวจจับ gaps ที่เหมาะสม
            optimal_price = self._find_best_gap_for_sell()
            if optimal_price:
                return optimal_price
            
            # 🆕 Fallback: วางใกล้ BUY ต่ำสุด
            lowest_buy = min(buy_positions, key=lambda x: x.open_price)
            fallback_price = lowest_buy.open_price - 0.008  # 8 pips ใต้ BUY ต่ำสุด
            self.log(f"📍 Fallback SELL position: {fallback_price:.5f} (near lowest BUY)", "INFO")
            return fallback_price
            
        except Exception as e:
            self.log(f"Error finding optimal SELL distribution price: {str(e)}", "ERROR")
            return None
    
    def _find_optimal_buy_distribution_price(self) -> float:
        """🎯 หาตำแหน่งที่ดีที่สุดสำหรับ BUY แบบกระจายตัวสลับกัน - ฉลาดขึ้น"""
        try:
            if not self.positions:
                return None
            
            # แยก BUY และ SELL positions
            buy_positions = [p for p in self.positions if p.order_type == 'BUY']
            sell_positions = [p for p in self.positions if p.order_type == 'SELL']
            
            if not sell_positions:
                return None
            
            # 🆕 ตรวจจับการกระจุกตัวของ SELL
            sell_clustering = self._detect_sell_clustering()
            if sell_clustering['is_clustered']:
                self.log(f"🚨 SELL Clustering Detected: {sell_clustering['cluster_count']} positions in {sell_clustering['cluster_range']:.3f} range", "WARNING")
                
                # หาตำแหน่งที่ดีที่สุดสำหรับ BUY ใหม่
                optimal_price = self._find_best_buy_position_for_sell_clustering(sell_clustering)
                if optimal_price:
                    self.log(f"🎯 Found optimal BUY position for SELL clustering: {optimal_price:.5f}", "INFO")
                    return optimal_price
            
            # 🆕 ตรวจจับ gaps ที่เหมาะสม
            optimal_price = self._find_best_gap_for_buy()
            if optimal_price:
                return optimal_price
            
            # 🆕 Fallback: วางใกล้ SELL สูงสุด
            highest_sell = max(sell_positions, key=lambda x: x.open_price)
            fallback_price = highest_sell.open_price + 0.008  # 8 pips เหนือ SELL สูงสุด
            self.log(f"📍 Fallback BUY position: {fallback_price:.5f} (near highest SELL)", "INFO")
            return fallback_price
            
        except Exception as e:
            self.log(f"Error finding optimal BUY distribution price: {str(e)}", "ERROR")
            return None
    
    def _detect_buy_clustering(self) -> dict:
        """🔍 ตรวจจับการกระจุกตัวของ BUY positions"""
        try:
            buy_positions = [p for p in self.positions if p.order_type == 'BUY']
            if len(buy_positions) < 3:
                return {'is_clustered': False, 'cluster_count': 0, 'cluster_range': 0}
            
            # เรียงตามราคา
            buy_prices = sorted([p.open_price for p in buy_positions])
            
            # ตรวจสอบการกระจุกตัว (3 ไม้ขึ้นไปในระยะ 20 pips)
            cluster_threshold = 0.020  # 20 pips
            
            for i in range(len(buy_prices) - 2):
                price_range = buy_prices[i+2] - buy_prices[i]
                if price_range <= cluster_threshold:
                    cluster_count = 3
                    # นับไม้ที่กระจุกกัน
                    for j in range(i+3, len(buy_prices)):
                        if buy_prices[j] - buy_prices[i] <= cluster_threshold:
                            cluster_count += 1
                        else:
                            break
                    
                    return {
                        'is_clustered': True,
                        'cluster_count': cluster_count,
                        'cluster_range': price_range,
                        'cluster_start': buy_prices[i],
                        'cluster_end': buy_prices[i+cluster_count-1],
                        'cluster_center': (buy_prices[i] + buy_prices[i+cluster_count-1]) / 2
                    }
            
            return {'is_clustered': False, 'cluster_count': 0, 'cluster_range': 0}
            
        except Exception as e:
            self.log(f"Error detecting BUY clustering: {str(e)}", "ERROR")
            return {'is_clustered': False, 'cluster_count': 0, 'cluster_range': 0}
    
    def _detect_sell_clustering(self) -> dict:
        """🔍 ตรวจจับการกระจุกตัวของ SELL positions"""
        try:
            sell_positions = [p for p in self.positions if p.order_type == 'SELL']
            if len(sell_positions) < 3:
                return {'is_clustered': False, 'cluster_count': 0, 'cluster_range': 0}
            
            # เรียงตามราคา
            sell_prices = sorted([p.open_price for p in sell_positions])
            
            # ตรวจสอบการกระจุกตัว (3 ไม้ขึ้นไปในระยะ 20 pips)
            cluster_threshold = 0.020  # 20 pips
            
            for i in range(len(sell_prices) - 2):
                price_range = sell_prices[i+2] - sell_prices[i]
                if price_range <= cluster_threshold:
                    cluster_count = 3
                    # นับไม้ที่กระจุกกัน
                    for j in range(i+3, len(sell_prices)):
                        if sell_prices[j] - sell_prices[i] <= cluster_threshold:
                            cluster_count += 1
                        else:
                            break
                    
                    return {
                        'is_clustered': True,
                        'cluster_count': cluster_count,
                        'cluster_range': price_range,
                        'cluster_start': sell_prices[i],
                        'cluster_end': sell_prices[i+cluster_count-1],
                        'cluster_center': (sell_prices[i] + sell_prices[i+cluster_count-1]) / 2
                    }
            
            return {'is_clustered': False, 'cluster_count': 0, 'cluster_range': 0}
            
        except Exception as e:
            self.log(f"Error detecting BUY clustering: {str(e)}", "ERROR")
            return {'is_clustered': False, 'cluster_count': 0, 'cluster_range': 0}
    
    def _find_best_sell_position_for_buy_clustering(self, buy_clustering: dict) -> float:
        """🎯 หาตำแหน่งที่ดีที่สุดสำหรับ SELL เมื่อ BUY กระจุกตัว"""
        try:
            if not buy_clustering['is_clustered']:
                return None
            
            # วาง SELL ตรงกลางของ BUY cluster
            cluster_center = buy_clustering['cluster_center']
            
            # ตรวจสอบว่าไม่ชนกับไม้ที่มีอยู่
            safe_distance = 0.005  # 5 pips
            
            # ลองตำแหน่งต่างๆ
            candidate_positions = [
                cluster_center - 0.010,  # 10 pips ใต้ cluster center
                cluster_center - 0.015,  # 15 pips ใต้ cluster center
                cluster_center - 0.020   # 20 pips ใต้ cluster center
            ]
            
            for pos in candidate_positions:
                if self._is_position_safe(pos, 'SELL', safe_distance):
                    return pos
            
            # ถ้าไม่มีตำแหน่งที่ปลอดภัย ให้ใช้ตำแหน่งที่ไกลที่สุด
            return candidate_positions[-1]
            
        except Exception as e:
            self.log(f"Error finding best SELL position for BUY clustering: {str(e)}", "ERROR")
            return None
    
    def _find_best_buy_position_for_sell_clustering(self, sell_clustering: dict) -> float:
        """🎯 หาตำแหน่งที่ดีที่สุดสำหรับ BUY เมื่อ SELL กระจุกตัว"""
        try:
            if not sell_clustering['is_clustered']:
                return None
            
            # วาง BUY ตรงกลางของ SELL cluster
            cluster_center = sell_clustering['cluster_center']
            
            # ตรวจสอบว่าไม่ชนกับไม้ที่มีอยู่
            safe_distance = 0.005  # 5 pips
            
            # ลองตำแหน่งต่างๆ
            candidate_positions = [
                cluster_center + 0.010,  # 10 pips เหนือ cluster center
                cluster_center + 0.015,  # 15 pips เหนือ cluster center
                cluster_center + 0.020   # 20 pips เหนือ cluster center
            ]
            
            for pos in candidate_positions:
                if self._is_position_safe(pos, 'BUY', safe_distance):
                    return pos
            
            # ถ้าไม่มีตำแหน่งที่ปลอดภัย ให้ใช้ตำแหน่งที่ไกลที่สุด
            return candidate_positions[-1]
            
        except Exception as e:
            self.log(f"Error finding best BUY position for SELL clustering: {str(e)}", "ERROR")
            return None
    
    def _is_position_safe(self, price: float, order_type: str, min_distance: float) -> bool:
        """🔒 ตรวจสอบว่าตำแหน่งปลอดภัยหรือไม่"""
        try:
            for pos in self.positions:
                distance = abs(pos.open_price - price)
                if distance < min_distance:
                    return False
            return True
        except Exception as e:
            self.log(f"Error checking position safety: {str(e)}", "ERROR")
            return False
    
    def _smart_position_opening_check(self, order_type: str, price: float, volume: float) -> dict:
        """🧠 ตรวจสอบการเปิดไม้แบบฉลาด (ป้องกันการออกไม้มั่วซั่ว)"""
        try:
            check_result = {
                'can_open': True,
                'reason': '',
                'warnings': [],
                'recommendations': []
            }
            
            # 1. ตรวจสอบจำนวนไม้รวม (ยืดหยุ่นขึ้น)
            current_limit = self._get_dynamic_position_limit()
            if len(self.positions) >= current_limit:
                check_result['can_open'] = False
                check_result['reason'] = f'Dynamic position limit reached: {len(self.positions)}/{current_limit}'
                check_result['warnings'].append(f"🚫 Dynamic limit: {len(self.positions)}/{current_limit}")
                return check_result
            
            # 2. ตรวจสอบจำนวนไม้ต่อ zone
            zone_positions = self._count_positions_in_zone(price)
            if zone_positions >= self.max_positions_per_zone:
                check_result['can_open'] = False
                check_result['reason'] = f'Zone position limit reached: {zone_positions}/{self.max_positions_per_zone}'
                check_result['warnings'].append(f"🚫 Zone limit: {zone_positions}/{self.max_positions_per_zone}")
                return check_result
            
            # 3. ตรวจสอบระยะห่างขั้นต่ำ
            if not self._is_position_safe(price, order_type, self.min_position_distance_pips * 0.001):
                check_result['can_open'] = False
                check_result['reason'] = f'Position too close to existing positions (min: {self.min_position_distance_pips} pips)'
                check_result['warnings'].append(f"🚫 Too close: min {self.min_position_distance_pips} pips required")
                return check_result
            
            # 4. ตรวจสอบ cooldown
            if self.last_position_opened:
                time_since_last = (datetime.now() - self.last_position_opened).total_seconds()
                if time_since_last < self.position_opening_cooldown:
                    check_result['can_open'] = False
                    check_result['reason'] = f'Opening cooldown active: {self.position_opening_cooldown - time_since_last:.1f}s remaining'
                    check_result['warnings'].append(f"⏰ Cooldown: {self.position_opening_cooldown - time_since_last:.1f}s remaining")
                    return check_result
            
            # 5. ตรวจสอบ portfolio balance
            if not self._check_portfolio_balance_for_new_position(order_type, volume):
                check_result['can_open'] = False
                check_result['reason'] = 'Portfolio balance check failed'
                check_result['warnings'].append("🚫 Portfolio balance check failed")
                return check_result
            
            # ✅ ผ่านการตรวจสอบทั้งหมด
            check_result['recommendations'].append("✅ Position opening check passed")
            return check_result
            
        except Exception as e:
            self.log(f"Error in smart position opening check: {str(e)}", "ERROR")
            return {'can_open': False, 'reason': f'Error: {str(e)}', 'warnings': [], 'recommendations': []}
    
    def _count_positions_in_zone(self, price: float) -> int:
        """🔢 นับจำนวนไม้ใน zone เดียวกัน"""
        try:
            zone_size = self.zone_size_pips * 0.001  # แปลง pips เป็น price
            count = 0
            
            for pos in self.positions:
                distance = abs(pos.open_price - price)
                if distance <= zone_size:
                    count += 1
            
            return count
            
        except Exception as e:
            self.log(f"Error counting positions in zone: {str(e)}", "ERROR")
            return 0
    
    def _check_portfolio_balance_for_new_position(self, order_type: str, volume: float) -> bool:
        """⚖️ ตรวจสอบ portfolio balance สำหรับไม้ใหม่"""
        try:
            # ตรวจสอบว่าการเปิดไม้ใหม่จะทำให้ balance แย่ลงหรือไม่
            if order_type == 'BUY':
                new_buy_volume = self.buy_volume + volume
                new_sell_volume = self.sell_volume
            else:  # SELL
                new_buy_volume = self.buy_volume
                new_sell_volume = self.sell_volume + volume
            
            total_volume = new_buy_volume + new_sell_volume
            if total_volume > 0:
                new_buy_ratio = new_buy_volume / total_volume
                imbalance = abs(new_buy_ratio - 0.5)
                
                # ถ้า imbalance เกิน 0.3 (30%) ให้บล็อก
                if imbalance > 0.3:
                    self.log(f"🚫 Portfolio balance would be too imbalanced: {imbalance:.1%}", "WARNING")
                    return False
            
            return True
            
        except Exception as e:
            self.log(f"Error checking portfolio balance: {str(e)}", "ERROR")
            return True  # ถ้าเกิด error ให้ผ่านไปก่อน
    
    def _get_dynamic_position_limit(self) -> int:
        """🎯 คำนวณ Dynamic Position Limit ตามตลาด"""
        try:
            base_limit = self.max_total_positions  # 50 ไม้
            
            # 1. ตรวจสอบ Market Opportunity
            if self._is_market_opportunity_good():
                base_limit = int(base_limit * self.market_opportunity_multiplier)  # 50 * 2 = 100 ไม้
                self.log(f"🎯 Market opportunity detected - Limit increased to {base_limit}", "INFO")
            
            # 2. ตรวจสอบ Continuous Movement
            if self._is_continuous_movement_detected():
                base_limit += self.continuous_movement_bonus  # +5 ไม้
                self.log(f"📈 Continuous movement detected - Bonus +5 positions", "INFO")
            
            # 3. ตรวจสอบ Portfolio Health
            if hasattr(self, 'portfolio_health') and self.portfolio_health > 80:
                base_limit += 10  # +10 ไม้เมื่อ portfolio สุขภาพดี
                self.log(f"💚 Portfolio health good - Bonus +10 positions", "INFO")
            
            # 4. ตรวจสอบ Market Volatility
            if self._is_high_volatility():
                base_limit += 15  # +15 ไม้เมื่อตลาดผันผวน
                self.log(f"🌊 High volatility detected - Bonus +15 positions", "INFO")
            
            self.log(f"🎯 Dynamic Position Limit: {base_limit} positions", "INFO")
            return base_limit
            
        except Exception as e:
            self.log(f"Error calculating dynamic position limit: {str(e)}", "ERROR")
            return self.max_total_positions  # ใช้ค่าเริ่มต้นถ้าเกิด error
    
    def _is_market_opportunity_good(self) -> bool:
        """🎯 ตรวจสอบว่าตลาดมีโอกาสดีหรือไม่"""
        try:
            if not self.positions:
                return False
            
            # ตรวจสอบจาก profit ของไม้ที่มีอยู่
            profitable_positions = [p for p in self.positions if p.profit > 0]
            total_positions = len(self.positions)
            
            if total_positions > 0:
                profit_ratio = len(profitable_positions) / total_positions
                
                # ถ้า profit ratio > 60% และมีไม้อย่างน้อย 5 ไม้
                if profit_ratio > 0.6 and total_positions >= 5:
                    return True
            
            return False
            
        except Exception as e:
            self.log(f"Error checking market opportunity: {str(e)}", "ERROR")
            return False
    
    def _is_continuous_movement_detected(self) -> bool:
        """📈 ตรวจสอบว่ากราฟวิ่งต่อเนื่องหรือไม่"""
        try:
            if len(self.positions) < 3:
                return False
            
            # ตรวจสอบจาก profit trend ของไม้ล่าสุด
            recent_positions = self.positions[-3:]  # ไม้ 3 ตัวล่าสุด
            profit_trend = []
            
            for i, pos in enumerate(recent_positions):
                if i > 0:
                    prev_pos = recent_positions[i-1]
                    profit_change = pos.profit - prev_pos.profit
                    profit_trend.append(profit_change > 0)  # True = profit เพิ่ม
            
            # ถ้า profit เพิ่มขึ้นต่อเนื่อง 2 ครั้ง
            if len(profit_trend) >= 2 and all(profit_trend):
                return True
            
            return False
            
        except Exception as e:
            self.log(f"Error checking continuous movement: {str(e)}", "ERROR")
            return False
    
    def _is_high_volatility(self) -> bool:
        """🌊 ตรวจสอบว่าตลาดผันผวนสูงหรือไม่"""
        try:
            if len(self.positions) < 5:
                return False
            
            # คำนวณ standard deviation ของ profit
            profits = [p.profit for p in self.positions]
            if len(profits) > 1:
                mean_profit = sum(profits) / len(profits)
                variance = sum((p - mean_profit) ** 2 for p in profits) / len(profits)
                std_dev = variance ** 0.5
                
                # ถ้า standard deviation > 50% ของ mean profit
                if mean_profit != 0 and abs(std_dev / mean_profit) > 0.5:
                    return True
            
            return False
            
        except Exception as e:
            self.log(f"Error checking volatility: {str(e)}", "ERROR")
            return False
    
    def _find_best_gap_for_sell(self) -> float:
        """🎯 หา gap ที่ดีที่สุดสำหรับ SELL"""
        try:
            all_prices = sorted([p.open_price for p in self.positions])
            min_gap = 0.015  # 15 pips
            
            best_gap_start = None
            best_gap_size = 0
            
            for i in range(len(all_prices) - 1):
                gap_size = all_prices[i+1] - all_prices[i]
                if gap_size > min_gap and gap_size > best_gap_size:
                    best_gap_size = gap_size
                    best_gap_start = all_prices[i]
            
            if best_gap_start:
                optimal_price = best_gap_start + (best_gap_size / 2)
                self.log(f"🎯 Found gap for SELL: {best_gap_size:.5f} at {optimal_price:.5f}", "INFO")
                return optimal_price
            
            return None
            
        except Exception as e:
            self.log(f"Error finding best gap for SELL: {str(e)}", "ERROR")
            return None
    
    def _find_best_gap_for_buy(self) -> float:
        """🎯 หา gap ที่ดีที่สุดสำหรับ BUY"""
        try:
            all_prices = sorted([p.open_price for p in self.positions])
            min_gap = 0.015  # 15 pips
            
            best_gap_start = None
            best_gap_size = 0
            
            for i in range(len(all_prices) - 1):
                gap_size = all_prices[i+1] - all_prices[i]
                if gap_size > min_gap and gap_size > best_gap_size:
                    best_gap_size = gap_size
                    best_gap_start = all_prices[i]
            
            if best_gap_start:
                optimal_price = best_gap_start + (best_gap_size / 2)
                self.log(f"🎯 Found gap for BUY: {best_gap_size:.5f} at {optimal_price:.5f}", "INFO")
                return optimal_price
            
            return None
            
        except Exception as e:
            self.log(f"Error finding best gap for BUY: {str(e)}", "ERROR")
            return None

    def _execute_buy_heavy_balance(self, action: dict) -> dict:
        """🟢 เปิด SELL ใหม่เมื่อ BUY heavy"""
        try:
            self.log(f"🟢 Executing BUY Heavy Balance: {action.get('reason', '')}", "INFO")
            
            # 1. วิเคราะห์ portfolio ปัจจุบัน
            buy_positions = [p for p in self.positions if p.type == 'BUY']
            sell_positions = [p for p in self.positions if p.type == 'SELL']
            
            if not buy_positions:
                return {'success': False, 'error': 'No BUY positions found'}
            
            # 2. หาตำแหน่งที่ดีที่สุดสำหรับ SELL ใหม่
            buy_prices = [p.open_price for p in buy_positions]
            min_buy_price = min(buy_prices)
            max_buy_price = max(buy_prices)
            
            # เปิด SELL ที่ราคาต่ำกว่า BUY ต่ำสุดเล็กน้อย
            target_price = min_buy_price - (self.min_position_distance_pips * 0.1)
            
            # 3. ตรวจสอบว่าไม่เกิด clustering
            if self.check_position_clustering(target_price):
                # ลองราคาอื่น
                target_price = min_buy_price - (self.min_position_distance_pips * 0.2)
                if self.check_position_clustering(target_price):
                    return {'success': False, 'error': 'Cannot find suitable price without clustering'}
            
            # 4. คำนวณ lot size (ครึ่งหนึ่งของ BUY total volume)
            total_buy_volume = sum(p.volume for p in buy_positions)
            target_lot_size = total_buy_volume * 0.5
            
            # ปรับ lot size ให้อยู่ในขอบเขตที่อนุญาต
            min_lot = 0.01
            max_lot = 1.0
            target_lot_size = max(min_lot, min(max_lot, target_lot_size))
            
            # 5. เปิด SELL order
            if hasattr(self, 'execute_order'):
                # สร้าง Signal object สำหรับ portfolio balance
                balance_signal = Signal(
                    timestamp=datetime.now(),
                    symbol=self.symbol,
                    direction='SELL',
                    strength=1.0,
                    reason=f"Portfolio Balance: {action.get('reason', '')}",
                    price=target_price
                )
                
                # เปิด order
                order_success = self.execute_order(balance_signal)
                
                if order_success:
                    self.log(f"✅ Successfully opened SELL {target_lot_size} at {target_price} for portfolio balance", "INFO")
                    return {
                        'success': True,
                        'message': f'Opened SELL {target_lot_size} at {target_price}',
                        'action': 'BALANCE_BUY_HEAVY',
                        'order_details': {'success': True, 'volume': target_lot_size, 'price': target_price}
                    }
                else:
                    return {'success': False, 'error': 'Failed to open SELL order'}
            else:
                return {'success': False, 'error': 'execute_order method not available'}
                
        except Exception as e:
            self.log(f"Error executing BUY heavy balance: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}

    def _execute_sell_heavy_balance(self, action: dict) -> dict:
        """🔴 เปิด BUY ใหม่เมื่อ SELL heavy"""
        try:
            self.log(f"🔴 Executing SELL Heavy Balance: {action.get('reason', '')}", "INFO")
            
            # 1. วิเคราะห์ portfolio ปัจจุบัน
            buy_positions = [p for p in self.positions if p.type == 'BUY']
            sell_positions = [p for p in self.positions if p.type == 'SELL']
            
            if not sell_positions:
                return {'success': False, 'error': 'No SELL positions found'}
            
            # 2. หาตำแหน่งที่ดีที่สุดสำหรับ BUY ใหม่
            sell_prices = [p.open_price for p in sell_positions]
            min_sell_price = min(sell_prices)
            max_sell_price = max(sell_prices)
            
            # เปิด BUY ที่ราคาสูงกว่า SELL สูงสุดเล็กน้อย
            target_price = max_sell_price + (self.min_position_distance_pips * 0.1)
            
            # 3. ตรวจสอบว่าไม่เกิด clustering
            if self.check_position_clustering(target_price):
                # ลองราคาอื่น
                target_price = max_sell_price + (self.min_position_distance_pips * 0.2)
                if self.check_position_clustering(target_price):
                    return {'success': False, 'error': 'Cannot find suitable price without clustering'}
            
            # 4. คำนวณ lot size (ครึ่งหนึ่งของ SELL total volume)
            total_sell_volume = sum(p.volume for p in sell_positions)
            target_lot_size = total_sell_volume * 0.5
            
            # ปรับ lot size ให้อยู่ในขอบเขตที่อนุญาต
            min_lot = 0.01
            max_lot = 1.0
            target_lot_size = max(min_lot, min(max_lot, target_lot_size))
            
            # 5. เปิด BUY order
            if hasattr(self, 'execute_order'):
                # สร้าง Signal object สำหรับ portfolio balance
                balance_signal = Signal(
                    timestamp=datetime.now(),
                    symbol=self.symbol,
                    direction='BUY',
                    strength=1.0,
                    reason=f"Portfolio Balance: {action.get('reason', '')}",
                    price=target_price
                )
                
                # เปิด order
                order_success = self.execute_order(balance_signal)
                
                if order_success:
                    self.log(f"✅ Successfully opened BUY {target_lot_size} at {target_price} for portfolio balance", "INFO")
                    return {
                        'success': True,
                        'message': f'Opened BUY {target_lot_size} at {target_price}',
                        'action': 'BALANCE_SELL_HEAVY',
                        'order_details': {'success': True, 'volume': target_lot_size, 'price': target_price}
                    }
                else:
                    return {'success': False, 'error': 'Failed to open BUY order'}
            else:
                return {'success': False, 'error': 'execute_order method not available'}
                
        except Exception as e:
            self.log(f"Error executing SELL heavy balance: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}

    def _execute_general_balance_improvement(self, action: dict) -> dict:
        """🔄 Execute General Portfolio Balance Improvement"""
        try:
            self.log(f"🔄 Executing General Balance Improvement: {action.get('reason', '')}", "INFO")
            
            # 1. วิเคราะห์ portfolio ปัจจุบัน
            buy_positions = [p for p in self.positions if p.type == 'BUY']
            sell_positions = [p for p in self.positions if p.type == 'SELL']
            
            buy_ratio = len(buy_positions) / len(self.positions) if self.positions else 0
            sell_ratio = len(sell_positions) / len(self.positions) if self.positions else 0
            
            # 2. ตัดสินใจว่าจะเปิด BUY หรือ SELL
            if buy_ratio > sell_ratio:
                # BUY heavy - เปิด SELL
                self.log(f"🟢 Portfolio Analysis: BUY heavy ({buy_ratio:.1%}) - will open SELL", "INFO")
                return self._execute_buy_heavy_balance(action)
            else:
                # SELL heavy - เปิด BUY
                self.log(f"🔴 Portfolio Analysis: SELL heavy ({sell_ratio:.1%}) - will open BUY", "INFO")
                return self._execute_sell_heavy_balance(action)
                
        except Exception as e:
            self.log(f"Error executing general balance improvement: {str(e)}", "ERROR")
            return {'success': False, 'error': str(e)}

    def should_redirect_for_zone_balance(self, signal: Signal, zone_analysis: dict, buy_ratio: float) -> dict:
        """ตรวจสอบว่าควร redirect เพื่อ zone balance หรือไม่"""
        try:
            result = {
                'should_redirect': False,
                'reason': '',
                'target_position': None,
                'profit_captured': 0.0,
                'zone_improvement': 0.0
            }
            
            zones = zone_analysis.get('zones', {})
            congested_zones = zone_analysis.get('clustered_zones', [])
            
            if not zones or not congested_zones:
                return result
            
            # Find positions in congested zones that could be closed
            candidates = []
            for congested_zone in congested_zones:
                zone_idx = congested_zone['zone_index']
                if zone_idx in zones:
                    zone_positions = zones[zone_idx]['positions']
                    for pos in zone_positions:
                        # Only consider profitable positions (ใช้เปอร์เซ็นต์)
                        profit_percent = (pos.profit_per_lot / pos.open_price) * 100 if pos.open_price > 0 else 0
                        if profit_percent > self.min_profit_for_redirect_close_percent:
                            candidates.append({
                                'position': pos,
                                'zone_index': zone_idx,
                                'profit': pos.profit,
                                'zone_congestion': congested_zone['excess_positions']
                            })
            
            if not candidates:
                return result
            
            # Score candidates based on zone improvement and profit
            best_candidate = None
            best_score = 0
            
            for candidate in candidates:
                pos = candidate['position']
                
                # Calculate score based on profit and zone improvement
                profit_score = min(40, pos.profit / 2)  # Max 40 points
                congestion_score = candidate['zone_congestion'] * 10  # 10 points per excess position
                
                # Volume match with signal
                signal_volume = self.calculate_dynamic_lot_size(signal)
                volume_diff = abs(signal_volume - pos.volume)
                volume_score = max(0, 20 - (volume_diff * 100))  # Max 20 points
                
                total_score = profit_score + congestion_score + volume_score
                
                if total_score > best_score and total_score > 50:
                    best_score = total_score
                    best_candidate = candidate
            
            if best_candidate:
                pos = best_candidate['position']
                result.update({
                    'should_redirect': True,
                    'reason': f"Zone decongestion - close {pos.type} from overcrowded zone {best_candidate['zone_index']}",
                    'target_position': pos,
                    'profit_captured': pos.profit,
                    'zone_improvement': best_candidate['zone_congestion']
                })
            
            return result
            
        except Exception as e:
            self.log(f"Error in zone balance redirect analysis: {str(e)}", "ERROR")
            return {'should_redirect': False}

    def find_best_zone_for_signal(self, signal: Signal, zone_analysis: dict) -> dict:
        """หา zone ที่เหมาะสมที่สุดสำหรับ signal ถ้าไม่สามารถเปิดที่ราคาปัจจุบันได้"""
        try:
            result = {
                'should_redirect': False,
                'reason': '',
                'target_position': None,
                'alternative_action': 'skip'
            }
            
            empty_zones = zone_analysis.get('empty_zones', [])
            current_price = zone_analysis.get('current_price', 0)
            
            if not empty_zones or current_price == 0:
                return result
            
            # Look for profitable positions in congested zones that could be closed
            zones = zone_analysis.get('zones', {})
            congested_zones = zone_analysis.get('clustered_zones', [])
            
            for congested_zone in congested_zones:
                zone_idx = congested_zone['zone_index']
                if zone_idx in zones:
                    zone_positions = zones[zone_idx]['positions']
                    
                    # Find a profitable position of opposite type
                    for pos in zone_positions:
                        profit_percent = (pos.profit_per_lot / pos.open_price) * 100 if pos.open_price > 0 else 0
                        if (pos.type != signal.direction and 
                            profit_percent > self.min_profit_for_redirect_close_percent):
                            
                            result.update({
                                'should_redirect': True,
                                'reason': f"Close profitable {pos.type} from congested zone to make room for {signal.direction}",
                                'target_position': pos,
                                'profit_captured': pos.profit,
                                'alternative_action': 'redirect_and_execute'
                            })
                            return result
            
            return result
            
        except Exception as e:
            self.log(f"Error finding best zone for signal: {str(e)}", "ERROR")
            return {'should_redirect': False}

    def analyze_redirect_opportunity(self, signal: Signal, buy_ratio: float) -> dict:
        """วิเคราะห์โอกาสในการ redirect signal"""
        try:
            analysis = {
                'should_redirect': False,
                'target_type': None,
                'target_position': None,
                'reason': '',
                'profit_captured': 0.0,
                'balance_improvement': 0.0,
                'redirect_target': None
            }
            
            # Determine which type to close based on signal direction and balance
            if signal.direction == 'BUY' and buy_ratio > self.redirect_threshold:
                target_type = 'SELL'
                analysis['reason'] = f'BUY signal with high BUY ratio ({buy_ratio:.1%})'
            elif signal.direction == 'SELL' and (1 - buy_ratio) > self.redirect_threshold:
                target_type = 'BUY'
                analysis['reason'] = f'SELL signal with high SELL ratio ({1-buy_ratio:.1%})'
            else:
                return analysis
            
            # Find best candidate to close
            candidates = [p for p in self.positions if p.type == target_type]
            if not candidates:
                return analysis
            
            # Score each candidate
            best_candidate = None
            best_score = 0
            
            for pos in candidates:
                score = self.calculate_redirect_score(pos, signal)
                if score > best_score and score > 50:  # minimum score threshold
                    best_score = score
                    best_candidate = pos
            
            if best_candidate:
                # Calculate benefits
                volume_difference = abs(signal.strength * self.base_lot - best_candidate.volume)
                volume_match_score = max(0, 1 - (volume_difference / best_candidate.volume))
                
                # Calculate balance improvement
                new_buy_ratio = self.calculate_balance_after_close(best_candidate, buy_ratio)
                balance_improvement = abs(buy_ratio - 0.5) - abs(new_buy_ratio - 0.5)
                
                analysis.update({
                    'should_redirect': True,
                    'target_type': target_type,
                    'target_position': best_candidate,
                    'profit_captured': best_candidate.profit,
                    'balance_improvement': balance_improvement,
                    'redirect_target': best_candidate.ticket,
                    'volume_match_score': volume_match_score,
                    'redirect_score': best_score
                })
            
            return analysis
            
        except Exception as e:
            self.log(f"Error analyzing redirect opportunity: {str(e)}", "ERROR")
            return {'should_redirect': False}

    def calculate_redirect_score(self, position: Position, signal: Signal) -> float:
        """คำนวณคะแนนความเหมาะสมในการปิด position เพื่อ redirect (ใช้ %)"""
        try:
            score = 0.0
            profit_pct = self.calculate_profit_percent(position)
            
            # 1. Profit score (40 points) - ใช้ %
            if profit_pct >= self.min_profit_for_redirect_close_percent:
                profit_ratio = profit_pct / self.profit_harvest_threshold_percent
                score += min(40, profit_ratio * 30)
            else:
                return 0  # ไม่ปิดถ้ากำไรต่ำเกินไป
            
            # 2. Volume match score (20 points)
            signal_volume = self.calculate_dynamic_lot_size(signal)
            volume_diff = abs(signal_volume - position.volume)
            volume_match = max(0, 1 - (volume_diff / max(signal_volume, position.volume)))
            score += volume_match * 20
            
            # 3. Age score (15 points)
            if position.ticket in self.position_tracker:
                try:
                    birth_time = safe_parse_datetime(self.position_tracker[position.ticket]['birth_time'])
                    age_hours = (datetime.now() - birth_time).total_seconds() / 3600
                    if age_hours > 12:
                        score += min(15, age_hours / 2)
                except Exception as age_error:
                    self.log(f"Warning: Could not calculate age score for position {position.ticket}: {age_error}", "WARNING")
            
            # 4. Portfolio health bonus (15 points)
            if self.portfolio_health < 50 and profit_pct > 0:
                score += 15
            
            # 5. Efficiency score (10 points)
            if profit_pct > 10:
                score += 10
            elif profit_pct > 5:
                score += 7
            elif profit_pct > 2:
                score += 4
            
            return score
            
        except Exception as e:
            self.log(f"Error calculating redirect score: {str(e)}", "ERROR")
            return 0

    def calculate_adaptive_profit_target(self, position: Position) -> float:
        """คำนวณเป้าหมายกำไรแบบปรับตัว (เป็น %)"""
        try:
            base_target_pct = getattr(self, 'profit_harvest_threshold_percent', 8.0)
            
            # ปรับตาม portfolio health
            if self.portfolio_health < 40:
                base_target_pct *= 0.6
            elif self.portfolio_health > 80:
                base_target_pct *= 1.3
            
            # ปรับตาม balance
            try:
                if self.will_improve_balance_by_closing(position):
                    base_target_pct *= 0.75
            except Exception:
                pass  # ไม่ต้องปรับถ้า error
            
            # ปรับตาม volatility
            if hasattr(self, 'recent_volatility'):
                if self.recent_volatility > 2.0:
                    base_target_pct *= 0.8
                elif self.recent_volatility < 0.5:
                    base_target_pct *= 1.2
            
            return max(2.0, min(20.0, base_target_pct))
            
        except Exception as e:
            return getattr(self, 'profit_harvest_threshold_percent', 8.0)

    def calculate_balance_after_close(self, position: Position, current_buy_ratio: float) -> float:
        """คำนวณ balance หลังจากปิด position"""
        try:
            new_buy_volume = self.buy_volume - (position.volume if position.type == "BUY" else 0)
            new_sell_volume = self.sell_volume - (position.volume if position.type == "SELL" else 0)
            new_total = new_buy_volume + new_sell_volume
            
            if new_total <= 0:
                return 0.5
            
            return new_buy_volume / new_total
            
        except:
            return current_buy_ratio

    def should_skip_signal(self, signal: Signal, buy_ratio: float) -> bool:
        """ตรวจสอบว่าควร skip signal หรือไม่ - optimized for better signal acceptance"""
        try:
            # Relaxed skip conditions - only skip in truly extreme cases
            # Changed from 0.8/0.2 to 0.85/0.15 to allow more signals through
            if signal.direction == 'BUY' and buy_ratio > 0.85:
                sell_positions = [p for p in self.positions if p.type == "SELL"]
                profitable_sells = [p for p in sell_positions if (p.profit_per_lot / p.open_price) * 100 > self.min_profit_for_redirect_close_percent]
                if not profitable_sells:
                    self.log(f"⏭️ Skipping BUY signal - extreme imbalance and no profitable SELLs")
                    return True
            
            elif signal.direction == 'SELL' and buy_ratio < 0.15:
                buy_positions = [p for p in self.positions if p.type == "BUY"]
                profitable_buys = [p for p in buy_positions if (p.profit_per_lot / p.open_price) * 100 > self.min_profit_for_redirect_close_percent]
                if not profitable_buys:
                    self.log(f"⏭️ Skipping SELL signal - extreme imbalance and no profitable BUYs")
                    return True
            
            # 🆕 Portfolio Recovery Strategy - ไม่ข้ามสัญญาณ แต่คิดกลยุทธ์ฟื้นฟูพอร์ต
            if len(self.positions) > self.max_positions * 0.95:
                if MT5_AVAILABLE and mt5 and self.mt5_connected:
                    account_info = mt5.account_info()
                    if account_info and account_info.margin > 0:
                        margin_level = (account_info.equity / account_info.margin) * 100
                        if margin_level < self.min_margin_level * 1.2:
                            # 🚀 ไม่ข้ามสัญญาณ แต่คิดกลยุทธ์ฟื้นฟูพอร์ต
                            recovery_strategy = self._analyze_portfolio_recovery_strategy(signal, margin_level)
                            
                            if recovery_strategy['action'] == 'OPEN_WITH_RECOVERY':
                                self.log(f"🚀 Portfolio Recovery: Opening {signal.direction} with recovery strategy", "INFO")
                                self.log(f"   📊 Strategy: {recovery_strategy['strategy_name']}", "INFO")
                                self.log(f"   🎯 Target: {recovery_strategy['target']}", "INFO")
                                return False  # เปิดออเดอร์พร้อมกลยุทธ์ฟื้นฟู
                            
                            elif recovery_strategy['action'] == 'OPEN_AND_CLOSE_RISKY':
                                self.log(f"🚀 Portfolio Recovery: Opening {signal.direction} and closing risky positions", "INFO")
                                self.log(f"   📊 Strategy: {recovery_strategy['strategy_name']}", "INFO")
                                self.log(f"   🎯 Target: {recovery_strategy['target']}", "INFO")
                                
                                # ปิดไม้ที่เสี่ยงก่อนเปิดไม้ใหม่
                                self._execute_recovery_position_closing(recovery_strategy['positions_to_close'])
                                return False  # เปิดออเดอร์หลังจากปิดไม้เสี่ยง
                            
                            else:
                                self.log(f"⚠️ Portfolio Recovery: Signal allowed but monitor closely", "WARNING")
                                return False  # เปิดออเดอร์แต่ติดตามใกล้ชิด
            
            return False
            
        except Exception as e:
            self.log(f"Error checking skip conditions: {str(e)}", "ERROR")
            return False

    def check_portfolio_health(self) -> dict:
        """🏥 ตรวจสอบสุขภาพของ Portfolio แบบครบถ้วน"""
        try:
            health_status = {
                'can_trade': True,
                'reason': '',
                'balance': 0.0,
                'equity': 0.0,
                'margin': 0.0,
                'free_margin': 0.0,
                'margin_level': 0.0,
                'total_profit_loss': 0.0,
                'portfolio_health_score': 0.0,
                'warnings': [],
                'recommendations': []
            }
            
            if not MT5_AVAILABLE or not mt5 or not self.mt5_connected:
                health_status['can_trade'] = False
                health_status['reason'] = 'MT5 not available or connected'
                return health_status
            
            # 1. รับข้อมูล Account
            account_info = mt5.account_info()
            if not account_info:
                health_status['can_trade'] = False
                health_status['reason'] = 'Cannot get account info'
                return health_status
            
            # 2. เก็บข้อมูลพื้นฐาน
            health_status['balance'] = account_info.balance
            health_status['equity'] = account_info.equity
            health_status['margin'] = account_info.margin
            health_status['free_margin'] = account_info.margin_free
            health_status['margin_level'] = (account_info.equity / account_info.margin * 100) if account_info.margin > 0 else 1000
            
            # 3. คำนวณ Total Profit/Loss
            if self.positions:
                health_status['total_profit_loss'] = sum(p.profit for p in self.positions)
            else:
                health_status['total_profit_loss'] = 0.0
            
            # 4. ตรวจสอบเงื่อนไขการเทรด
            
            # 4.1 Balance Check - ปิดการบล็อกชั่วคราว
            if health_status['balance'] < 100:  # ลดลงมากเพื่อให้ผ่าน
                health_status['can_trade'] = False
                health_status['reason'] = f'Balance too low: ${health_status["balance"]:.2f}'
                health_status['warnings'].append(f"⚠️ Balance: ${health_status['balance']:.2f} (Min: $100)")
            
            # 4.2 Equity Check - ปิดการบล็อกชั่วคราว
            if health_status['equity'] < 50:  # ลดลงมากเพื่อให้ผ่าน
                health_status['can_trade'] = False
                health_status['reason'] = f'Equity too low: ${health_status["equity"]:.2f}'
                health_status['warnings'].append(f"⚠️ Equity: ${health_status['equity']:.2f} (Min: $50)")
            
            # 4.3 Margin Level Check - ปิดการบล็อกชั่วคราว
            min_margin = getattr(self, 'min_margin_level', 50)  # ลดลงมากเพื่อให้ผ่าน
            if health_status['margin_level'] < min_margin:
                health_status['can_trade'] = False
                health_status['reason'] = f'Margin level too low: {health_status["margin_level"]:.1f}%'
                health_status['warnings'].append(f"⚠️ Margin Level: {health_status['margin_level']:.1f}% (Min: {min_margin}%)")
            
            # 4.4 Free Margin Check - ปิดการบล็อกชั่วคราว
            if health_status['free_margin'] < 10:  # ลดลงมากเพื่อให้ผ่าน
                health_status['can_trade'] = False
                health_status['reason'] = f'Free margin too low: ${health_status["free_margin"]:.2f}'
                health_status['warnings'].append(f"⚠️ Free Margin: ${health_status['free_margin']:.2f} (Min: $10)")
            
            # 4.5 Portfolio Loss Check - ยืดหยุ่นตาม Balance (ปรับให้ยืดหยุ่นขึ้น)
            current_balance = health_status['balance']
            if current_balance > 0:
                # 🆕 คำนวณ threshold แบบยืดหยุ่น (เพิ่มจาก 20% เป็น 35% ของ balance)
                balance_based_threshold = current_balance * 0.35
                
                if health_status['total_profit_loss'] < -balance_based_threshold:
                    health_status['can_trade'] = False
                    health_status['reason'] = f'Portfolio loss too high: ${health_status["total_profit_loss"]:.2f} (Threshold: ${balance_based_threshold:.2f})'
                    health_status['warnings'].append(f"⚠️ Portfolio Loss: ${health_status['total_profit_loss']:.2f} (Max: ${balance_based_threshold:.2f} - 35% of Balance)")
                else:
                    # 🆕 แสดงข้อมูล balance และ threshold
                    health_status['warnings'].append(f"ℹ️ Portfolio Loss: ${health_status['total_profit_loss']:.2f} (Safe within ${balance_based_threshold:.2f} threshold)")
            else:
                # Fallback: ใช้ค่าเดิมถ้าไม่มี balance
                if health_status['total_profit_loss'] < -500:
                    health_status['can_trade'] = False
                    health_status['reason'] = f'Portfolio loss too high: ${health_status["total_profit_loss"]:.2f}'
                    health_status['warnings'].append(f"⚠️ Portfolio Loss: ${health_status['total_profit_loss']:.2f} (Max: -$500)")
            
            # 4.6 Drawdown Check
            if health_status['balance'] > 0:
                drawdown_percentage = ((health_status['balance'] - health_status['equity']) / health_status['balance']) * 100
                if drawdown_percentage > 25:
                    health_status['can_trade'] = False
                    health_status['reason'] = f'Drawdown too high: {drawdown_percentage:.1f}%'
                    health_status['warnings'].append(f"⚠️ Drawdown: {drawdown_percentage:.1f}% (Max: 25%)")
            
            # 5. คำนวณ Portfolio Health Score
            health_status['portfolio_health_score'] = self._calculate_portfolio_health_score(health_status)
            
            # 6. สร้างคำแนะนำ
            health_status['recommendations'] = self._generate_portfolio_health_recommendations(health_status)
            
            # 7. Log ผลลัพธ์
            if health_status['can_trade']:
                self.log(f"✅ Portfolio Health Check: PASSED (Score: {health_status['portfolio_health_score']:.1f})", "INFO")
            else:
                self.log(f"❌ Portfolio Health Check: FAILED - {health_status['reason']}", "WARNING")
                for warning in health_status['warnings']:
                    self.log(warning, "WARNING")
            
            return health_status
            
        except Exception as e:
            self.log(f"Error in portfolio health check: {str(e)}", "ERROR")
            return {
                'can_trade': False,
                'reason': f'Error: {str(e)}',
                'portfolio_health_score': 0
            }

    def _calculate_portfolio_health_score(self, health_status: dict) -> float:
        """📊 คำนวณ Portfolio Health Score (0-100)"""
        try:
            score = 0.0
            
            # 1. Balance Score (25 points)
            balance = health_status.get('balance', 0)
            if balance >= 5000:
                score += 25
            elif balance >= 3000:
                score += 20
            elif balance >= 2000:
                score += 15
            elif balance >= 1000:
                score += 10
            else:
                score += 0
            
            # 2. Equity Score (25 points)
            equity = health_status.get('equity', 0)
            if equity >= 5000:
                score += 25
            elif equity >= 3000:
                score += 20
            elif equity >= 2000:
                score += 15
            elif equity >= 800:
                score += 10
            else:
                score += 0
            
            # 3. Margin Level Score (25 points)
            margin_level = health_status.get('margin_level', 0)
            if margin_level >= 500:
                score += 25
            elif margin_level >= 300:
                score += 20
            elif margin_level >= 200:
                score += 15
            elif margin_level >= 150:
                score += 10
            else:
                score += 0
            
            # 4. Free Margin Score (15 points)
            free_margin = health_status.get('free_margin', 0)
            if free_margin >= 1000:
                score += 15
            elif free_margin >= 500:
                score += 12
            elif free_margin >= 200:
                score += 8
            elif free_margin >= 100:
                score += 5
            else:
                score += 0
            
            # 5. Portfolio Loss Score (10 points)
            total_profit_loss = health_status.get('total_profit_loss', 0)
            if total_profit_loss >= 0:
                score += 10
            elif total_profit_loss >= -100:
                score += 8
            elif total_profit_loss >= -200:
                score += 5
            elif total_profit_loss >= -300:
                score += 2
            else:
                score += 0
            
            return min(100.0, max(0.0, score))
            
        except Exception as e:
            self.log(f"Error calculating portfolio health score: {str(e)}", "ERROR")
            return 50.0

    def _generate_portfolio_health_recommendations(self, health_status: dict) -> list:
        """💡 สร้างคำแนะนำตาม Portfolio Health"""
        recommendations = []
        score = health_status.get('portfolio_health_score', 0)
        
        if score >= 90:
            recommendations.append("🟢 EXCELLENT: Portfolio is in excellent condition")
            recommendations.append("✅ Continue normal trading operations")
            recommendations.append("🚀 Consider increasing position sizes")
        elif score >= 80:
            recommendations.append("🟢 VERY GOOD: Portfolio is very healthy")
            recommendations.append("✅ Continue normal trading operations")
            recommendations.append("📊 Monitor for any changes")
        elif score >= 70:
            recommendations.append("🟡 GOOD: Portfolio is in good condition")
            recommendations.append("✅ Continue trading but monitor closely")
            recommendations.append("📊 Watch for any deterioration")
        elif score >= 60:
            recommendations.append("🟡 FAIR: Portfolio needs attention")
            recommendations.append("⚠️ Reduce position sizes")
            recommendations.append("📊 Focus on risk management")
        elif score >= 50:
            recommendations.append("🟠 POOR: Portfolio needs immediate attention")
            recommendations.append("🚨 Reduce exposure significantly")
            recommendations.append("📊 Focus on loss reduction")
        else:
            recommendations.append("🔴 CRITICAL: Portfolio is in critical condition")
            recommendations.append("🚨 Stop trading immediately")
            recommendations.append("📊 Emergency recovery needed")
        
        # เพิ่มคำแนะนำเฉพาะตาม warnings
        warnings = health_status.get('warnings', [])
        for warning in warnings:
            if "Balance" in warning:
                recommendations.append("💰 Consider depositing more funds")
            elif "Equity" in warning:
                recommendations.append("📉 Focus on profitable trades")
            elif "Margin" in warning:
                recommendations.append("🛡️ Close some positions to free margin")
            elif "Portfolio Loss" in warning:
                recommendations.append("📊 Focus on risk management and loss reduction")
            elif "Drawdown" in warning:
                recommendations.append("📉 Implement strict risk controls")
        
        return recommendations

    def check_order_opening_conditions(self, signal: Signal) -> dict:
        """🔍 ตรวจสอบเงื่อนไขก่อนเปิดออเดอร์ - Balance, Equity, Margin, Free Margin, Portfolio Loss"""
        try:
            check_result = {
                'can_open': True,
                'reason': '',
                'balance_check': True,
                'equity_check': True,
                'margin_check': True,
                'free_margin_check': True,
                'portfolio_loss_check': True,
                'warnings': [],
                'recommendations': []
            }
            
            if not MT5_AVAILABLE or not mt5 or not self.mt5_connected:
                check_result['can_open'] = False
                check_result['reason'] = 'MT5 not available or connected'
                return check_result
            
            # 1. รับข้อมูล Account
            account_info = mt5.account_info()
            if not account_info:
                check_result['can_open'] = False
                check_result['reason'] = 'Cannot get account info'
                return check_result
            
            # 2. Balance Check - ปิดการบล็อกชั่วคราว
            balance = account_info.balance
            if balance < 50:  # ลดลงมากเพื่อให้ผ่าน
                check_result['balance_check'] = False
                check_result['can_open'] = False
                check_result['reason'] = f'Balance too low: ${balance:.2f}'
                check_result['warnings'].append(f"⚠️ Balance: ${balance:.2f} (Min: $50)")
                check_result['recommendations'].append("💰 Consider depositing more funds")
            
            # 3. Equity Check - ปิดการบล็อกชั่วคราว
            equity = account_info.equity
            if equity < 25:  # ลดลงมากเพื่อให้ผ่าน
                check_result['equity_check'] = False
                check_result['can_open'] = False
                check_result['reason'] = f'Equity too low: ${equity:.2f}'
                check_result['warnings'].append(f"⚠️ Equity: ${equity:.2f} (Min: $25)")
                check_result['recommendations'].append("📉 Focus on profitable trades")
            
            # 4. Margin Level Check - ปิดการบล็อกชั่วคราว
            min_margin = getattr(self, 'min_margin_level', 25)  # ลดลงมากเพื่อให้ผ่าน
            if account_info.margin > 0:
                margin_level = (equity / account_info.margin) * 100
                if margin_level < min_margin:
                    check_result['margin_check'] = False
                    check_result['can_open'] = False
                    check_result['reason'] = f'Margin level too low: {margin_level:.1f}%'
                    check_result['warnings'].append(f"⚠️ Margin Level: {margin_level:.1f}% (Min: {min_margin}%)")
                    check_result['recommendations'].append("🛡️ Close some positions to free margin")
            
            # 5. Free Margin Check - ปิดการบล็อกชั่วคราว
            free_margin = account_info.margin_free
            if free_margin < 5:  # ลดลงมากเพื่อให้ผ่าน
                check_result['free_margin_check'] = False
                check_result['can_open'] = False
                check_result['reason'] = f'Free margin too low: ${free_margin:.2f}'
                check_result['warnings'].append(f"⚠️ Free Margin: ${free_margin:.2f} (Min: $5)")
                check_result['recommendations'].append("🛡️ Close some positions to free margin")
            
            # 6. Portfolio Loss Check - ยืดหยุ่นตาม Balance
            if self.positions:
                total_profit_loss = sum(p.profit for p in self.positions)
                
                # 🆕 คำนวณ threshold แบบยืดหยุ่นตาม balance (ปรับให้ยืดหยุ่นขึ้น)
                if balance > 0:
                    balance_based_threshold = balance * 0.40  # เพิ่มจาก 25% เป็น 40% ของ balance
                    
                    if total_profit_loss < -balance_based_threshold:
                        check_result['portfolio_loss_check'] = False
                        check_result['can_open'] = False
                        check_result['reason'] = f'Portfolio loss too high: ${total_profit_loss:.2f} (Threshold: ${balance_based_threshold:.2f})'
                        check_result['warnings'].append(f"⚠️ Portfolio Loss: ${total_profit_loss:.2f} (Max: ${balance_based_threshold:.2f} - 40% of Balance)")
                        check_result['recommendations'].append("📊 Focus on risk management and loss reduction")
                    else:
                        # 🆕 แสดงข้อมูล balance และ threshold
                        check_result['warnings'].append(f"ℹ️ Portfolio Loss: ${total_profit_loss:.2f} (Safe within ${balance_based_threshold:.2f} threshold)")
                        check_result['recommendations'].append(f"💰 Current Balance: ${balance:.2f} | Safe to open orders")
                else:
                    # Fallback: ใช้ค่าเดิมถ้าไม่มี balance
                    if total_profit_loss < -500:
                        check_result['portfolio_loss_check'] = False
                        check_result['can_open'] = False
                        check_result['reason'] = f'Portfolio loss too high: ${total_profit_loss:.2f}'
                        check_result['warnings'].append(f"⚠️ Portfolio Loss: ${total_profit_loss:.2f} (Max: -$500)")
                        check_result['recommendations'].append("📊 Focus on risk management and loss reduction")
            
            # 7. Log ผลลัพธ์
            if check_result['can_open']:
                self.log(f"✅ Order Opening Check: PASSED - All conditions met", "INFO")
            else:
                self.log(f"❌ Order Opening Check: FAILED - {check_result['reason']}", "WARNING")
                for warning in check_result['warnings']:
                    self.log(warning, "WARNING")
                for recommendation in check_result['recommendations']:
                    self.log(recommendation, "INFO")
            
            return check_result
            
        except Exception as e:
            self.log(f"Error in order opening conditions check: {str(e)}", "ERROR")
            return {
                'can_open': False,
                'reason': f'Error: {str(e)}',
                'balance_check': False,
                'equity_check': False,
                'margin_check': False,
                'free_margin_check': False,
                'portfolio_loss_check': False,
                'warnings': [],
                'recommendations': []
            }

    def ai_market_prediction_system(self) -> dict:
        """🔮 AI Market Prediction System: ทำนายอนาคตของราคาแบบเทคนิคอล"""
        try:
            prediction_result = {
                'timestamp': datetime.now(),
                'prediction': 'UNKNOWN',
                'confidence': 0.0,
                'trend_direction': 'UNKNOWN',
                'trend_strength': 0.0,
                'reversal_probability': 0.0,
                'volatility_level': 'UNKNOWN',
                'support_levels': [],
                'resistance_levels': [],
                'key_indicators': {},
                'recommendations': [],
                'risk_level': 'UNKNOWN'
            }
            
            if not self.positions or not MT5_AVAILABLE or not mt5:
                return prediction_result
            
            # 1. 📊 วิเคราะห์ราคาปัจจุบัน
            current_price_analysis = self._analyze_current_price()
            if current_price_analysis:
                prediction_result.update(current_price_analysis)
            
            # 2. 📈 วิเคราะห์เทรนด์
            trend_analysis = self._analyze_trend_analysis()
            if trend_analysis:
                prediction_result.update(trend_analysis)
            
            # 3. 🔄 วิเคราะห์การกลับตัว
            reversal_analysis = self._analyze_reversal_signals()
            if reversal_analysis:
                prediction_result.update(reversal_analysis)
            
            # 4. 📊 วิเคราะห์ Indicators
            indicators_analysis = self._analyze_technical_indicators()
            if indicators_analysis:
                prediction_result.update(indicators_analysis)
            
            # 5. 🎯 สรุปการทำนาย
            final_prediction = self._generate_final_prediction(prediction_result)
            prediction_result.update(final_prediction)
            
            # 6. 📝 แสดงผลการทำนาย
            self._display_prediction_results(prediction_result)
            
            return prediction_result
            
        except Exception as e:
            self.log(f"Error in AI market prediction system: {str(e)}", "ERROR")
            return {
                'timestamp': datetime.now(),
                'prediction': 'ERROR',
                'confidence': 0.0,
                'trend_direction': 'UNKNOWN',
                'trend_strength': 0.0,
                'reversal_probability': 0.0,
                'volatility_level': 'UNKNOWN',
                'support_levels': [],
                'resistance_levels': [],
                'key_indicators': {},
                'recommendations': [],
                'risk_level': 'UNKNOWN'
            }

    def _analyze_current_price(self) -> dict:
        """📊 วิเคราะห์ราคาปัจจุบัน"""
        try:
            if not self.positions:
                return {}
            
            # หาราคาปัจจุบันจาก positions
            current_prices = [p.current_price for p in self.positions if hasattr(p, 'current_price')]
            if not current_prices:
                return {}
            
            avg_current_price = sum(current_prices) / len(current_prices)
            
            # หาราคา entry จาก positions
            entry_prices = [p.open_price for p in self.positions if hasattr(p, 'open_price')]
            if not entry_prices:
                return {}
            
            avg_entry_price = sum(entry_prices) / len(entry_prices)
            
            # คำนวณการเปลี่ยนแปลง
            price_change = avg_current_price - avg_entry_price
            price_change_percent = (price_change / avg_entry_price) * 100 if avg_entry_price > 0 else 0
            
            # วิเคราะห์ volatility
            price_variance = sum((p - avg_current_price) ** 2 for p in current_prices) / len(current_prices)
            volatility = price_variance ** 0.5
            
            return {
                'current_price': avg_current_price,
                'entry_price': avg_entry_price,
                'price_change': price_change,
                'price_change_percent': price_change_percent,
                'volatility': volatility,
                'volatility_level': 'HIGH' if volatility > 0.001 else 'MEDIUM' if volatility > 0.0005 else 'LOW'
            }
            
        except Exception as e:
            self.log(f"Error analyzing current price: {str(e)}", "ERROR")
            return {}

    def _analyze_trend_analysis(self) -> dict:
        """📈 วิเคราะห์เทรนด์"""
        try:
            if not self.positions:
                return {}
            
            # วิเคราะห์จาก positions ที่มีอยู่
            buy_positions = [p for p in self.positions if p.type == 'BUY']
            sell_positions = [p for p in self.positions if p.type == 'SELL']
            
            # คำนวณ average price ของ BUY และ SELL
            if buy_positions:
                avg_buy_price = sum(p.open_price for p in buy_positions) / len(buy_positions)
            else:
                avg_buy_price = 0
            
            if sell_positions:
                avg_sell_price = sum(p.open_price for p in sell_positions) / len(sell_positions)
            else:
                avg_sell_price = 0
            
            # วิเคราะห์เทรนด์จาก price distribution
            if avg_buy_price > 0 and avg_sell_price > 0:
                if avg_buy_price > avg_sell_price:
                    trend_direction = 'BULLISH'
                    trend_strength = min(0.9, (avg_buy_price - avg_sell_price) / avg_sell_price)
                else:
                    trend_direction = 'BEARISH'
                    trend_strength = min(0.9, (avg_sell_price - avg_buy_price) / avg_buy_price)
            else:
                trend_direction = 'NEUTRAL'
                trend_strength = 0.0
            
            return {
                'trend_direction': trend_direction,
                'trend_strength': trend_strength,
                'avg_buy_price': avg_buy_price,
                'avg_sell_price': avg_sell_price
            }
            
        except Exception as e:
            self.log(f"Error analyzing trend: {str(e)}", "ERROR")
            return {}

    def _analyze_reversal_signals(self) -> dict:
        """🔄 วิเคราะห์สัญญาณการกลับตัว"""
        try:
            if not self.positions:
                return {}
            
            # วิเคราะห์จาก profit/loss ของ positions
            profitable_positions = [p for p in self.positions if p.profit > 0]
            losing_positions = [p for p in self.positions if p.profit < 0]
            
            # คำนวณ reversal probability
            total_positions = len(self.positions)
            if total_positions > 0:
                profitable_ratio = len(profitable_positions) / total_positions
                losing_ratio = len(losing_positions) / total_positions
                
                # ถ้า profitable positions มากเกินไป อาจมีการกลับตัว
                if profitable_ratio > 0.7:
                    reversal_probability = 0.8
                    reversal_signal = 'BEARISH_REVERSAL'
                elif losing_ratio > 0.7:
                    reversal_probability = 0.8
                    reversal_signal = 'BULLISH_REVERSAL'
                else:
                    reversal_probability = 0.3
                    reversal_signal = 'NO_REVERSAL'
            else:
                reversal_probability = 0.0
                reversal_signal = 'NO_REVERSAL'
            
            return {
                'reversal_probability': reversal_probability,
                'reversal_signal': reversal_signal,
                'profitable_ratio': profitable_ratio if 'profitable_ratio' in locals() else 0.0,
                'losing_ratio': losing_ratio if 'losing_ratio' in locals() else 0.0
            }
            
        except Exception as e:
            self.log(f"Error analyzing reversal signals: {str(e)}", "ERROR")
            return {}

    def _analyze_technical_indicators(self) -> dict:
        """📊 วิเคราะห์ Technical Indicators"""
        try:
            if not self.positions:
                return {}
            
            # วิเคราะห์จาก positions ที่มีอยู่
            key_indicators = {}
            
            # 1. RSI-like indicator (จาก profit/loss ratio)
            if self.positions:
                total_profit = sum(p.profit for p in self.positions)
                total_volume = sum(p.volume for p in self.positions)
                
                if total_volume > 0:
                    # คำนวณ RSI-like indicator
                    avg_profit_per_lot = total_profit / total_volume
                    if avg_profit_per_lot > 0:
                        rsi_like = min(100, 50 + (avg_profit_per_lot * 1000))  # Normalize
                    else:
                        rsi_like = max(0, 50 + (avg_profit_per_lot * 1000))
                    
                    key_indicators['rsi_like'] = rsi_like
                    
                    # วิเคราะห์ RSI
                    if rsi_like > 70:
                        key_indicators['rsi_signal'] = 'OVERBOUGHT'
                    elif rsi_like < 30:
                        key_indicators['rsi_signal'] = 'OVERSOLD'
                    else:
                        key_indicators['rsi_signal'] = 'NEUTRAL'
            
            # 2. MACD-like indicator (จาก price momentum)
            if len(self.positions) >= 2:
                # คำนวณ momentum จาก profit changes
                recent_profits = [p.profit for p in self.positions[-2:]]
                if len(recent_profits) == 2:
                    momentum = recent_profits[1] - recent_profits[0]
                    key_indicators['momentum'] = momentum
                    
                    if momentum > 0:
                        key_indicators['momentum_signal'] = 'BULLISH'
                    else:
                        key_indicators['momentum_signal'] = 'BEARISH'
            
            # 3. Volume analysis (จาก lot sizes)
            if self.positions:
                total_volume = sum(p.volume for p in self.positions)
                avg_volume = total_volume / len(self.positions)
                key_indicators['total_volume'] = total_volume
                key_indicators['avg_volume'] = avg_volume
                
                # วิเคราะห์ volume trend
                if total_volume > 0.5:  # High volume
                    key_indicators['volume_signal'] = 'HIGH_VOLUME'
                elif total_volume > 0.2:  # Medium volume
                    key_indicators['volume_signal'] = 'MEDIUM_VOLUME'
                else:
                    key_indicators['volume_signal'] = 'LOW_VOLUME'
            
            return {
                'key_indicators': key_indicators
            }
            
        except Exception as e:
            self.log(f"Error analyzing technical indicators: {str(e)}", "ERROR")
            return {}

    def _generate_final_prediction(self, analysis_data: dict) -> dict:
        """🎯 สรุปการทำนายสุดท้าย"""
        try:
            # 1. วิเคราะห์ trend direction
            trend_direction = analysis_data.get('trend_direction', 'NEUTRAL')
            trend_strength = analysis_data.get('trend_strength', 0.0)
            
            # 2. วิเคราะห์ reversal signals
            reversal_probability = analysis_data.get('reversal_probability', 0.0)
            reversal_signal = analysis_data.get('reversal_signal', 'NO_REVERSAL')
            
            # 3. วิเคราะห์ technical indicators
            key_indicators = analysis_data.get('key_indicators', {})
            rsi_signal = key_indicators.get('rsi_signal', 'NEUTRAL')
            momentum_signal = key_indicators.get('momentum_signal', 'NEUTRAL')
            
            # 4. สรุปการทำนาย
            if reversal_probability > 0.7:
                if reversal_signal == 'BULLISH_REVERSAL':
                    prediction = 'BULLISH_REVERSAL'
                    confidence = 0.8
                elif reversal_signal == 'BEARISH_REVERSAL':
                    prediction = 'BEARISH_REVERSAL'
                    confidence = 0.8
                else:
                    prediction = 'NEUTRAL'
                    confidence = 0.5
            elif trend_strength > 0.6:
                if trend_direction == 'BULLISH':
                    prediction = 'BULLISH_TREND'
                    confidence = 0.7
                elif trend_direction == 'BEARISH':
                    prediction = 'BEARISH_TREND'
                    confidence = 0.7
                else:
                    prediction = 'NEUTRAL'
                    confidence = 0.5
            else:
                prediction = 'NEUTRAL'
                confidence = 0.5
            
            # 5. กำหนด risk level
            if confidence > 0.7:
                risk_level = 'LOW'
            elif confidence > 0.5:
                risk_level = 'MEDIUM'
            else:
                risk_level = 'HIGH'
            
            # 6. สร้างคำแนะนำ
            recommendations = []
            if prediction == 'BULLISH_REVERSAL':
                recommendations.append("🟢 ราคาอาจกลับตัวขึ้น - เก็บ BUY positions ไว้")
                recommendations.append("🔴 ปิด SELL positions ที่ติดลบก่อน")
            elif prediction == 'BEARISH_REVERSAL':
                recommendations.append("🔴 ราคาอาจกลับตัวลง - เก็บ SELL positions ไว้")
                recommendations.append("🟢 ปิด BUY positions ที่ติดลบก่อน")
            elif prediction == 'BULLISH_TREND':
                recommendations.append("🟢 ราคามีเทรนด์ขึ้น - เพิ่ม BUY positions")
                recommendations.append("🔴 ลด SELL positions")
            elif prediction == 'BEARISH_TREND':
                recommendations.append("🔴 ราคามีเทรนด์ลง - เพิ่ม SELL positions")
                recommendations.append("🟢 ลด BUY positions")
            else:
                recommendations.append("⚪ ราคานิ่ง - รอสัญญาณที่ชัดเจน")
            
            return {
                'prediction': prediction,
                'confidence': confidence,
                'risk_level': risk_level,
                'recommendations': recommendations
            }
            
        except Exception as e:
            self.log(f"Error generating final prediction: {str(e)}", "ERROR")
            return {
                'prediction': 'ERROR',
                'confidence': 0.0,
                'risk_level': 'UNKNOWN',
                'recommendations': []
            }

    def _display_prediction_results(self, prediction_result: dict):
        """📝 แสดงผลการทำนาย"""
        try:
            prediction = prediction_result.get('prediction', 'UNKNOWN')
            confidence = prediction_result.get('confidence', 0.0)
            risk_level = prediction_result.get('risk_level', 'UNKNOWN')
            
            # แสดงผลการทำนายหลัก
            self.log(f"🔮 AI Market Prediction: {prediction} (Confidence: {confidence:.1%})", "INFO")
            self.log(f"   Risk Level: {risk_level}", "INFO")
            
            # แสดงคำแนะนำ
            recommendations = prediction_result.get('recommendations', [])
            if recommendations:
                self.log(f"💡 Recommendations:", "INFO")
                for rec in recommendations:
                    self.log(f"   {rec}", "INFO")
            
            # แสดงข้อมูลเพิ่มเติม
            if prediction_result.get('trend_direction'):
                self.log(f"📈 Trend: {prediction_result['trend_direction']} (Strength: {prediction_result.get('trend_strength', 0):.1%})", "INFO")
            
            if prediction_result.get('reversal_probability'):
                self.log(f"🔄 Reversal Probability: {prediction_result['reversal_probability']:.1%}", "INFO")
            
            if prediction_result.get('volatility_level'):
                self.log(f"📊 Volatility: {prediction_result['volatility_level']}", "INFO")
            
        except Exception as e:
            self.log(f"Error displaying prediction results: {str(e)}", "ERROR")

    def display_balance_status(self) -> dict:
        """💰 แสดงสถานะ Balance และ Portfolio แบบ Real-time"""
        try:
            balance_status = {
                'timestamp': datetime.now(),
                'balance': 0.0,
                'equity': 0.0,
                'margin': 0.0,
                'free_margin': 0.0,
                'margin_level': 0.0,
                'total_profit_loss': 0.0,
                'portfolio_health': 'UNKNOWN',
                'can_trade': False,
                'balance_threshold': 0.0,
                'portfolio_threshold': 0.0
            }
            
            if MT5_AVAILABLE and mt5 and self.mt5_connected:
                account_info = mt5.account_info()
                if account_info:
                    balance_status['balance'] = account_info.balance
                    balance_status['equity'] = account_info.equity
                    balance_status['margin'] = account_info.margin
                    balance_status['free_margin'] = account_info.margin_free
                    balance_status['margin_level'] = (account_info.equity / account_info.margin * 100) if account_info.margin > 0 else 1000
                    
                    # คำนวณ portfolio loss
                    if self.positions:
                        balance_status['total_profit_loss'] = sum(p.profit for p in self.positions)
                    
                    # คำนวณ thresholds แบบยืดหยุ่น
                    if balance_status['balance'] > 0:
                        balance_status['balance_threshold'] = balance_status['balance'] * 0.15  # 15% สำหรับ hedge
                        balance_status['portfolio_threshold'] = balance_status['balance'] * 0.20  # 20% สำหรับ portfolio health
                        
                        # ตรวจสอบสถานะ
                        if balance_status['total_profit_loss'] >= -balance_status['portfolio_threshold']:
                            balance_status['portfolio_health'] = 'HEALTHY'
                            balance_status['can_trade'] = True
                        else:
                            balance_status['portfolio_health'] = 'AT_RISK'
                            balance_status['can_trade'] = False
                    
                    # แสดงสถานะแบบ real-time
                    self.log(f"💰 Balance Status: ${balance_status['balance']:.2f} | Equity: ${balance_status['equity']:.2f}", "INFO")
                    self.log(f"   Portfolio Loss: ${balance_status['total_profit_loss']:.2f} | Health: {balance_status['portfolio_health']}", "INFO")
                    self.log(f"   Hedge Threshold: ${balance_status['balance_threshold']:.2f} | Portfolio Threshold: ${balance_status['portfolio_threshold']:.2f}", "INFO")
                    
                    if balance_status['can_trade']:
                        self.log(f"✅ Portfolio is healthy - Safe to trade", "SUCCESS")
                    else:
                        self.log(f"⚠️ Portfolio needs attention - Trading restricted", "WARNING")
            
            return balance_status
            
        except Exception as e:
            self.log(f"Error displaying balance status: {str(e)}", "ERROR")
            return {
                'timestamp': datetime.now(),
                'balance': 0.0,
                'equity': 0.0,
                'margin': 0.0,
                'free_margin': 0.0,
                'margin_level': 0.0,
                'total_profit_loss': 0.0,
                'portfolio_health': 'ERROR',
                'can_trade': False,
                'balance_threshold': 0.0,
                'portfolio_threshold': 0.0
            }

    def check_order_closing_conditions(self, position: Position) -> dict:
        """🔍 ตรวจสอบเงื่อนไขก่อนปิดออเดอร์ - Margin, Portfolio Impact"""
        try:
            check_result = {
                'can_close': True,
                'reason': '',
                'margin_check': True,
                'portfolio_impact_check': True,
                'warnings': [],
                'recommendations': []
            }
            
            if not MT5_AVAILABLE or not mt5 or not self.mt5_connected:
                check_result['can_close'] = False
                check_result['reason'] = 'MT5 not available or connected'
                return check_result
            
            # 1. รับข้อมูล Account
            account_info = mt5.account_info()
            if not account_info:
                check_result['can_close'] = False
                check_result['reason'] = 'Cannot get account info'
                return check_result
            
            # 2. Margin Level Check
            if account_info.margin > 0:
                current_margin_level = (account_info.equity / account_info.margin) * 100
                
                # คำนวณ margin level หลังจากปิด position
                position_margin = position.volume * 100000 * 0.01  # ประมาณการ margin ที่ใช้
                new_margin_level = (account_info.equity / (account_info.margin - position_margin)) * 100 if (account_info.margin - position_margin) > 0 else 1000
                
                # ตรวจสอบว่าการปิดจะทำให้ margin level ดีขึ้นหรือไม่
                if new_margin_level < self.min_margin_level:
                    check_result['margin_check'] = False
                    check_result['can_close'] = False
                    check_result['reason'] = f'Closing would make margin level too low: {new_margin_level:.1f}%'
                    check_result['warnings'].append(f"⚠️ New Margin Level: {new_margin_level:.1f}% (Min: {self.min_margin_level}%)")
                    check_result['recommendations'].append("🛡️ Keep position to maintain margin level")
                elif new_margin_level < current_margin_level:
                    check_result['warnings'].append(f"⚠️ Closing will reduce margin level from {current_margin_level:.1f}% to {new_margin_level:.1f}%")
                    check_result['recommendations'].append("📊 Consider if closing is necessary")
            
            # 3. Portfolio Impact Check
            if self.positions:
                total_profit_loss = sum(p.profit for p in self.positions)
                position_profit = position.profit
                
                # คำนวณ portfolio impact หลังจากปิด
                new_total_profit_loss = total_profit_loss - position_profit
                
                # ตรวจสอบว่าการปิดจะทำให้ portfolio ดีขึ้นหรือไม่
                if position_profit > 0 and new_total_profit_loss < total_profit_loss:
                    # ปิดไม้กำไรจะทำให้ portfolio แย่ลง
                    check_result['portfolio_impact_check'] = False
                    check_result['warnings'].append(f"⚠️ Closing profitable position will reduce portfolio profit")
                    check_result['recommendations'].append("📊 Consider keeping profitable position")
                
                elif position_profit < 0 and new_total_profit_loss > total_profit_loss:
                    # ปิดไม้ขาดทุนจะทำให้ portfolio ดีขึ้น
                    check_result['recommendations'].append("✅ Closing losing position will improve portfolio")
            
            # 4. Log ผลลัพธ์
            if check_result['can_close']:
                self.log(f"✅ Order Closing Check: PASSED - Position {position.ticket} can be closed", "INFO")
            else:
                self.log(f"❌ Order Closing Check: FAILED - {check_result['reason']}", "WARNING")
                for warning in check_result['warnings']:
                    self.log(warning, "WARNING")
                for recommendation in check_result['recommendations']:
                    self.log(recommendation, "INFO")
            
            return check_result
            
        except Exception as e:
            self.log(f"Error in order closing conditions check: {str(e)}", "ERROR")
            return {
                'can_close': False,
                'reason': f'Error: {str(e)}',
                'margin_check': False,
                'portfolio_impact_check': False,
                'warnings': [],
                'recommendations': []
            }

    def _analyze_portfolio_recovery_strategy(self, signal: Signal, margin_level: float) -> dict:
        """🧠 วิเคราะห์กลยุทธ์การฟื้นฟูพอร์ตเมื่อ margin ต่ำ"""
        try:
            recovery_strategy = {
                'action': 'OPEN_WITH_RECOVERY',
                'strategy_name': '',
                'target': '',
                'positions_to_close': [],
                'reason': '',
                'risk_level': 'MEDIUM'
            }
            
            # 1. วิเคราะห์สถานการณ์ปัจจุบัน
            current_price = self.get_current_price()
            total_profit_loss = sum(p.profit for p in self.positions) if self.positions else 0
            
            # 2. วิเคราะห์ BUY/SELL ratio
            buy_positions = [p for p in self.positions if p.type == "BUY"]
            sell_positions = [p for p in self.positions if p.type == "SELL"]
            buy_ratio = len(buy_positions) / len(self.positions) if self.positions else 0.5
            
            # 3. วิเคราะห์กลยุทธ์ตาม signal direction
            if signal.direction == 'BUY':
                if buy_ratio > 0.7:  # BUY heavy
                    # กลยุทธ์: เปิด BUY เพื่อสร้าง hedge และลดความเสี่ยง
                    recovery_strategy.update({
                        'strategy_name': 'HEDGE_AND_RECOVER',
                        'target': 'Create BUY hedge to reduce SELL risk exposure',
                        'reason': 'BUY heavy portfolio - need hedge protection',
                        'risk_level': 'HIGH'
                    })
                    
                    # หาไม้ที่เสี่ยงมากที่สุดเพื่อปิด
                    risky_positions = self._find_risky_positions_for_recovery()
                    if risky_positions:
                        recovery_strategy.update({
                            'action': 'OPEN_AND_CLOSE_RISKY',
                            'positions_to_close': risky_positions
                        })
                
                else:  # BUY balanced
                    # กลยุทธ์: เปิด BUY ปกติเพื่อสร้าง profit
                    recovery_strategy.update({
                        'strategy_name': 'PROFIT_RECOVERY',
                        'target': 'Open BUY to generate profit and improve portfolio',
                        'reason': 'BUY balanced - can add profitable position',
                        'risk_level': 'MEDIUM'
                    })
            
            elif signal.direction == 'SELL':
                if buy_ratio < 0.3:  # SELL heavy
                    # กลยุทธ์: เปิด SELL เพื่อสร้าง hedge และลดความเสี่ยง
                    recovery_strategy.update({
                        'strategy_name': 'HEDGE_AND_RECOVER',
                        'target': 'Create SELL hedge to reduce BUY risk exposure',
                        'reason': 'SELL heavy portfolio - need hedge protection',
                        'risk_level': 'HIGH'
                    })
                    
                    # หาไม้ที่เสี่ยงมากที่สุดเพื่อปิด
                    risky_positions = self._find_risky_positions_for_recovery()
                    if risky_positions:
                        recovery_strategy.update({
                            'action': 'OPEN_AND_CLOSE_RISKY',
                            'positions_to_close': risky_positions
                        })
                
                else:  # SELL balanced
                    # กลยุทธ์: เปิด SELL ปกติเพื่อสร้าง profit
                    recovery_strategy.update({
                        'strategy_name': 'PROFIT_RECOVERY',
                        'target': 'Open SELL to generate profit and improve portfolio',
                        'reason': 'SELL balanced - can add profitable position',
                        'risk_level': 'MEDIUM'
                    })
            
            # 4. ปรับกลยุทธ์ตาม margin level
            if margin_level < self.min_margin_level * 0.8:  # Margin ต่ำมาก
                recovery_strategy['risk_level'] = 'HIGH'
                recovery_strategy['strategy_name'] += '_EMERGENCY'
                recovery_strategy['target'] += ' (Emergency Mode)'
            
            # 5. ปรับกลยุทธ์ตาม portfolio loss
            if total_profit_loss < -300:  # ติดลบมาก
                recovery_strategy['strategy_name'] += '_LOSS_RECOVERY'
                recovery_strategy['target'] += ' - Focus on loss reduction'
            
            return recovery_strategy
            
        except Exception as e:
            self.log(f"Error analyzing portfolio recovery strategy: {str(e)}", "ERROR")
            return {
                'action': 'OPEN_WITH_RECOVERY',
                'strategy_name': 'DEFAULT_RECOVERY',
                'target': 'Default recovery strategy',
                'reason': 'Error in analysis',
                'risk_level': 'MEDIUM'
            }

    def _find_risky_positions_for_recovery(self) -> list:
        """🎯 หาไม้ที่เสี่ยงมากที่สุดสำหรับการฟื้นฟูพอร์ต"""
        try:
            if not self.positions:
                return []
            
            current_price = self.get_current_price()
            risky_positions = []
            
            for position in self.positions:
                # 1. คำนวณ % loss จาก entry price
                if position.open_price > 0:
                    price_loss_percentage = ((current_price - position.open_price) / position.open_price) * 100
                    if position.type == 'SELL':
                        price_loss_percentage = -price_loss_percentage  # SELL = ราคาลง = loss
                else:
                    price_loss_percentage = 0
                
                # 2. คำนวณ % loss จาก portfolio value
                total_portfolio_value = self.get_portfolio_value()
                if total_portfolio_value > 0:
                    portfolio_loss_percentage = (position.profit / total_portfolio_value) * 100
                else:
                    portfolio_loss_percentage = 0
                
                # 3. คำนวณระยะห่างจากตลาด (%)
                distance_percentage = abs(current_price - position.open_price) / current_price * 100
                
                # 4. คำนวณ risk score
                risk_score = self._calculate_position_risk_score(
                    position, portfolio_loss_percentage, price_loss_percentage
                )
                
                # 5. เพิ่มไม้ที่เสี่ยงมากที่สุด (risk score > 70)
                if risk_score > 70:
                    risky_positions.append({
                        'position': position,
                        'risk_score': risk_score,
                        'price_loss_percentage': price_loss_percentage,
                        'portfolio_loss_percentage': portfolio_loss_percentage,
                        'distance_percentage': distance_percentage
                    })
            
            # 6. เรียงตาม risk score (เสี่ยงมากที่สุดก่อน)
            risky_positions.sort(key=lambda x: x['risk_score'], reverse=True)
            
            # 7. เลือกไม้ที่เสี่ยงมากที่สุด 2-3 ตัว
            return risky_positions[:3]
            
        except Exception as e:
            self.log(f"Error finding risky positions for recovery: {str(e)}", "ERROR")
            return []

    def _execute_recovery_position_closing(self, positions_to_close: list):
        """🚀 ปิดไม้ที่เสี่ยงเพื่อการฟื้นฟูพอร์ต"""
        try:
            if not positions_to_close:
                return
            
            self.log(f"🚀 Portfolio Recovery: Closing {len(positions_to_close)} risky positions", "INFO")
            
            for risk_item in positions_to_close:
                position = risk_item['position']
                risk_score = risk_item['risk_score']
                
                self.log(f"🚀 Recovery Closing: Position {position.ticket} (Risk Score: {risk_score:.1f})", "INFO")
                
                # ปิด position
                if hasattr(self, 'close_position_smart'):
                    close_result = self.close_position_smart(position.ticket)
                    if close_result.get('success'):
                        self.log(f"✅ Recovery Closed Position {position.ticket}", "SUCCESS")
                    else:
                        self.log(f"❌ Failed to Recovery Close Position {position.ticket}", "ERROR")
            
            self.log(f"🚀 Portfolio Recovery: Completed closing {len(positions_to_close)} risky positions", "INFO")
            
        except Exception as e:
            self.log(f"Error in recovery position closing: {str(e)}", "ERROR")

    def execute_redirect_close(self, position: Position, original_signal: Signal, reason: str) -> bool:
        """ดำเนินการปิด position สำหรับ redirect"""
        try:
            close_type = mt5.ORDER_TYPE_SELL if position.type == "BUY" else mt5.ORDER_TYPE_BUY
            
            # Ensure we have a valid filling type
            if self.filling_type is None:
                self.filling_type = self.detect_broker_filling_type()
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": position.volume,
                "type": close_type,
                "position": position.ticket,
                "deviation": 20,
                "magic": 123456,
                "comment": f"Smart_Redirect_{original_signal.direction[:1]}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self.filling_type,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                # Update statistics
                self.total_redirects += 1
                self.successful_redirects += 1
                self.redirect_profit_captured += position.profit
                self.last_redirect_time = datetime.now()
                
                self.log(f"✅ Redirect successful: Closed {position.type} {position.volume} lots")
                self.log(f"   Profit captured: ${position.profit:.2f} (${position.profit_per_lot:.2f}/lot)")
                self.log(f"   Reason: {reason}")
                
                # Update position tracker
                if position.ticket in self.position_tracker:
                    del self.position_tracker[position.ticket]
                
                return True
                
            elif result.retcode == mt5.TRADE_RETCODE_INVALID_FILL:
                # Try with different filling type for close orders
                for filling_type in self.filling_types_priority:
                    if filling_type != self.filling_type:
                        request["type_filling"] = filling_type
                        result = mt5.order_send(request)
                        if result.retcode == mt5.TRADE_RETCODE_DONE:
                            self.log(f"✅ Redirect close successful with {filling_type}")
                            return True
                        
                self.log(f"❌ Redirect close failed with all filling types", "ERROR")
                return False
            else:
                self.log(f"❌ Redirect close failed: {result.retcode}", "WARNING")
                return False
                
        except Exception as e:
            self.log(f"Error executing redirect close: {str(e)}", "ERROR")
            return False

    def track_position_lifecycle(self, position: Position):
        """ติดตามวงจรชีวิตของแต่ละ position"""
        try:
            # Debug logging
            if self.debug_position_tracking:
                self.log(f"🐛 Tracking position: {position}", "DEBUG")
                self.log(f"🐛 Current tracker keys: {list(self.position_tracker.keys())}", "DEBUG")
                
            # ตรวจสอบว่า position เป็น object ที่ถูกต้อง
            if position is None:
                self.log("Position is None", "ERROR")
                return
                
            if not isinstance(position, Position):
                self.log(f"Invalid position type: {type(position)}", "ERROR")
                return
            
            # ตรวจสอบ required attributes
            required_attrs = ['ticket', 'open_price', 'profit', 'profit_per_lot']
            for attr in required_attrs:
                if not hasattr(position, attr):
                    self.log(f"Position missing required attribute: {attr}", "ERROR")
                    return
                if getattr(position, attr) is None:
                    self.log(f"Position {attr} is None", "ERROR")
                    return
            
            ticket = position.ticket
            
            # ตรวจสอบ ticket validity
            if not isinstance(ticket, (int, str)) or ticket == 0:
                self.log(f"Invalid ticket format: {ticket} (type: {type(ticket)})", "ERROR")
                return
                
            if not hasattr(position, 'role') or position.role is None:
                position.role = "UNKNOWN"
                
            if not hasattr(position, 'efficiency') or position.efficiency is None:
                position.efficiency = "fair"
            
            # สร้างหรือดึง tracker (ใช้ get() เพื่อความปลอดภัย)
            if ticket not in self.position_tracker:
                if self.debug_position_tracking:
                    self.log(f"🐛 Creating new tracker for ticket {ticket}", "DEBUG")
                    
                self.position_tracker[ticket] = {
                    'birth_time': datetime.now().isoformat(),
                    'initial_price': position.open_price,
                    'max_profit': position.profit,
                    'min_profit': position.profit,
                    'role_history': [position.role],
                    'efficiency_history': [position.efficiency],
                    'peak_profit_per_lot': position.profit_per_lot,
                    'contribution_score': 0.0,
                    'hold_score': 50,
                    'adaptive_target': getattr(self, 'profit_harvest_threshold_percent', 8.0)
                }
                
                if self.debug_position_tracking:
                    self.log(f"🐛 Tracker created successfully for {ticket}", "DEBUG")
            
            # ใช้ get() เพื่อป้องกัน KeyError
            tracker = self.position_tracker.get(ticket)
            if tracker is None:
                self.log(f"ERROR: Tracker for {ticket} is None after creation!", "ERROR")
                self.log(f"ERROR: Available keys: {list(self.position_tracker.keys())}", "ERROR")
                # สร้างใหม่อีกครั้งเป็น fallback
                self.position_tracker[ticket] = {
                    'birth_time': datetime.now().isoformat(),
                    'initial_price': position.open_price,
                    'max_profit': position.profit,
                    'min_profit': position.profit,
                    'role_history': [position.role],
                    'efficiency_history': [position.efficiency],
                    'peak_profit_per_lot': position.profit_per_lot,
                    'contribution_score': 0.0,
                    'hold_score': 50,
                    'adaptive_target': 8.0
                }
                tracker = self.position_tracker[ticket]
                self.log(f"WARNING: Created emergency fallback tracker for {ticket}", "WARNING")
            
            # อัพเดทข้อมูล (ป้องกัน None values)
            if position.profit is not None:
                tracker['max_profit'] = max(tracker.get('max_profit', 0), position.profit)
                tracker['min_profit'] = min(tracker.get('min_profit', 0), position.profit)
            
            if position.profit_per_lot is not None:
                tracker['peak_profit_per_lot'] = max(tracker.get('peak_profit_per_lot', 0), position.profit_per_lot)
            
            # คำนวณ adaptive target (ป้องกัน error)
            try:
                tracker['adaptive_target'] = self.calculate_adaptive_profit_target(position)
            except Exception as target_error:
                self.log(f"Error calculating adaptive target for {ticket}: {target_error}", "WARNING")
                tracker['adaptive_target'] = getattr(self, 'profit_harvest_threshold_percent', 8.0)
            
            # คำนวณ hold score (ป้องกัน error)
            try:
                tracker['hold_score'] = self.calculate_hold_score(position, tracker)
            except Exception as score_error:
                self.log(f"Error calculating hold score for {ticket}: {score_error}", "WARNING")
                tracker['hold_score'] = 50
            
            # อัพเดทประวัติ (ป้องกัน empty list)
            if tracker.get('role_history') and len(tracker['role_history']) > 0:
                if tracker['role_history'][-1] != position.role:
                    tracker['role_history'].append(position.role)
            else:
                tracker['role_history'] = [position.role]
                
            if tracker.get('efficiency_history') and len(tracker['efficiency_history']) > 0:
                if tracker['efficiency_history'][-1] != position.efficiency:
                    tracker['efficiency_history'].append(position.efficiency)
            else:
                tracker['efficiency_history'] = [position.efficiency]
                
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            self.log(f"Error tracking position {position.ticket}: {type(e).__name__}: {str(e)}", "ERROR")
            self.log(f"Full traceback: {error_details}", "DEBUG")



    def calculate_hold_score(self, position: Position, tracker: dict) -> int:
        """คำนวณคะแนนการถือ position (ใช้เปอร์เซ็นต์)"""
        try:
            score = 50
            adaptive_target_pct = tracker.get('adaptive_target', getattr(self, 'profit_harvest_threshold_percent', 8.0))
            
            # 1. Profit factor (ใช้เปอร์เซ็นต์)
            profit_percent = (position.profit_per_lot / position.open_price) * 100 if position.open_price > 0 else 0
            profit_ratio = profit_percent / adaptive_target_pct if adaptive_target_pct > 0 else 0
            
            if profit_ratio >= 1.2:
                score -= 35
            elif profit_ratio >= 1.0:
                score -= 25
            elif profit_ratio >= 0.5:
                score += 10
            elif profit_ratio > 0:
                score += 20
            else:
                score += 30
            
            # 2. Portfolio health factor
            if self.portfolio_health < self.emergency_mode_threshold:
                if position.profit > 0:
                    score -= 25
            elif self.portfolio_health > 80:
                score += 15
            
            # 3. Balance factor
            try:
                if self.will_improve_balance_by_closing(position):
                    score -= 10
            except Exception as balance_error:
                self.log(f"Warning: Could not calculate balance factor for hold score: {balance_error}", "WARNING")
            
            # 4. Age factor
            try:
                birth_time = safe_parse_datetime(tracker['birth_time'])
                age_hours = (datetime.now() - birth_time).total_seconds() / 3600
                if age_hours > self.max_hold_hours:
                    score -= 20
                elif age_hours > 24:
                    score -= 10
            except Exception as age_error:
                self.log(f"Warning: Could not calculate age factor for hold score: {age_error}", "WARNING")
            
            return max(0, min(100, score))
            
        except Exception as e:
            return 50


    def smart_position_management(self):
        """🤖 ระบบจัดการ position อัจฉริยะ (AI-Enhanced with Balance Protection)"""
        if not self.mt5_connected or not self.positions:
            return
        
        # 🆕 Debug: แสดงการทำงานของ smart_position_management
        self.log(f"🔄 Smart Position Management: Starting with {len(self.positions)} positions", "INFO")
        
        try:
            # ติดตามทุก position
            for position in self.positions:
                self.track_position_lifecycle(position)
            
            # 🤖 AI Step 0: Margin Risk Assessment
            if self.ai_margin_intelligence:
                margin_risk = self.ai_assess_margin_risk()
                if margin_risk['risk_level'] in ['EMERGENCY', 'DANGER']:
                    self.log(f"🚨 AI Alert: {margin_risk['risk_level']} margin situation detected!", "WARNING")
                
                # 🆕 AI Step 0.5: Market Intelligence Analysis
                if self.market_intelligence_enabled:
                    market_analysis = self.analyze_market_intelligence()
                    if market_analysis.get('reversal_detected'):
                        self.log(f"🔍 Market Intelligence: {market_analysis.get('reversal_type', 'Unknown')} reversal detected", "INFO")
                    
                    portfolio_optimization = self.optimize_portfolio_performance()
                    if portfolio_optimization.get('optimization_needed'):
                        self.log(f"🚀 Portfolio Optimization: {len(portfolio_optimization.get('recommendations', []))} recommendations", "INFO")
                    
                    # 🎯 Adaptive Threshold Adjustment
                    threshold_adjustment = self.adaptive_threshold_adjustment()
                    if threshold_adjustment.get('adjustments_made'):
                        self.log(f"🎯 Adaptive Thresholds: {len(threshold_adjustment.get('recommendations', []))} adjustments applied", "INFO")
                        for rec in threshold_adjustment.get('recommendations', []):
                            self.log(f"💡 {rec}", "INFO")
            
            # 🔄 Step 1: ตรวจสอบและสร้าง Balance Support ก่อน
            if self.balance_protection_enabled:
                # 🆕 แสดงสถานะ Balance แบบ Real-time
                balance_status = self.display_balance_status()
                
                # ตรวจสอบ balance status ก่อนสร้าง hedge
                if balance_status.get('can_trade', False):
                    self.smart_balance_management()
                else:
                    self.log(f"⚠️ Balance protection disabled: Portfolio health check failed", "WARNING")
            
            # 📈 Step 2: ระบบจัดการ drawdown & hedge ก่อน
            self.drawdown_management_system()
            
            # 🚫 Step 3: ลบระบบเก่าทิ้ง (ไม่ใช้ smart_pair_group_management อีกต่อไป)
            # ใช้แค่ AI system เท่านั้น
            
            # 🧠 Step 4: AI Smart Recovery (อัจฉริยะสำหรับไม้ติดลบเยอะ) + AI Market Prediction
            if self.ai_margin_intelligence:
                self.log("🧠 Starting AI Smart Recovery...", "INFO")
                
                # 🆕 ใช้ AI Market Prediction ในการตัดสินใจปิดไม้
                market_prediction = self.ai_market_prediction_system()
                if market_prediction and market_prediction.get('prediction') != 'ERROR':
                    prediction = market_prediction.get('prediction', 'UNKNOWN')
                    confidence = market_prediction.get('confidence', 0.0)
                    
                    self.log(f"🔮 AI Market Prediction for Recovery: {prediction} (Confidence: {confidence:.1%})", "INFO")
                    
                    # ปรับ recovery strategy ตามการทำนาย
                    if prediction in ['BULLISH_REVERSAL', 'BULLISH_TREND']:
                        self.log(f"🟢 AI Recovery Strategy: Bullish market - Keep BUY positions, close SELL losses", "INFO")
                    elif prediction in ['BEARISH_REVERSAL', 'BEARISH_TREND']:
                        self.log(f"🔴 AI Recovery Strategy: Bearish market - Keep SELL positions, close BUY losses", "INFO")
                    else:
                        self.log(f"⚪ AI Recovery Strategy: Neutral market - Standard recovery approach", "INFO")
                
                recovery_executed = self.execute_smart_recovery_closes()
                if recovery_executed:
                    self.log("🧠 AI Smart Recovery completed, traditional closing may be skipped", "INFO")
                else:
                    self.log("🧠 AI Smart Recovery: No actions taken", "INFO")
            
            # 🎯 Step 5: ปิดแบบยืดหยุ่น (AI-Enhanced หรือ Traditional)
            self.execute_flexible_closes()
            
            # 🆕 Step 5.5: Independent Portfolio Distribution System + AI Market Prediction
            if self.ai_margin_intelligence:
                try:
                    # 🆕 ใช้ AI Market Prediction ในการตัดสินใจ distribution
                    market_prediction = self.ai_market_prediction_system()
                    if market_prediction and market_prediction.get('prediction') != 'ERROR':
                        prediction = market_prediction.get('prediction', 'UNKNOWN')
                        confidence = market_prediction.get('confidence', 0.0)
                        
                        self.log(f"🔮 AI Market Prediction for Distribution: {prediction} (Confidence: {confidence:.1%})", "INFO")
                        
                        # ปรับ distribution strategy ตามการทำนาย
                        if prediction in ['BULLISH_REVERSAL', 'BULLISH_TREND']:
                            self.log(f"🟢 AI Distribution Strategy: Bullish market - Optimize for BUY positions", "INFO")
                        elif prediction in ['BEARISH_REVERSAL', 'BEARISH_TREND']:
                            self.log(f"🔴 AI Distribution Strategy: Bearish market - Optimize for SELL positions", "INFO")
                        else:
                            self.log(f"⚪ AI Distribution Strategy: Neutral market - Standard distribution approach", "INFO")
                    
                    distribution_result = self.independent_portfolio_distribution_system()
                    if distribution_result.get('success') and distribution_result.get('actions_taken'):
                        self.log(f"🔄 Independent Distribution: {len(distribution_result['actions_taken'])} actions taken", "INFO")
                        for action in distribution_result['actions_taken']:
                            self.log(f"✅ {action['action']}: {action['result']}", "INFO")
                        
                        if distribution_result.get('improvements_made'):
                            for improvement in distribution_result['improvements_made']:
                                self.log(f"📈 Improvement: {improvement}", "INFO")
                        
                        self.log(f"🎯 Distribution Score: {distribution_result.get('optimization_score', 0):.1f}/100", "INFO")
                        self.log(f"📊 Distribution Quality: {distribution_result.get('distribution_quality', 'UNKNOWN')}", "INFO")
                    elif distribution_result.get('success'):
                        self.log(f"🔄 Independent Distribution: {distribution_result.get('message', 'No actions needed')}", "INFO")
                except Exception as e:
                    self.log(f"Warning: Independent distribution system failed: {str(e)}", "WARNING")
            
            # 🧹 Step 6: ทำความสะอาด tracker
            self.cleanup_closed_positions()
            
        except Exception as e:
            self.log(f"❌ Error in AI smart position management: {str(e)}", "ERROR")

    def smart_balance_management(self):
        """🔄 ระบบจัดการสมดุลอัจฉริยะ - สร้าง hedge เพื่อช่วยไม้ที่ติด"""
        try:
            # คำนวณ balance ปัจจุบัน
            total_volume = self.buy_volume + self.sell_volume
            if total_volume <= 0:
                return
                
            buy_ratio = self.buy_volume / total_volume
            
            # หาไม้ที่ติดมากที่สุด
            stuck_positions = []
            for pos in self.positions:
                if pos.profit < -20:  # ขาดทุนเกิน $20
                    distance = self.calculate_position_distance_from_market(pos)
                    stuck_positions.append((pos, distance))
            
            if not stuck_positions:
                return
                
            # เรียงตาม distance (ไกลสุดก่อน)
            stuck_positions.sort(key=lambda x: x[1], reverse=True)
            most_stuck_pos, max_distance = stuck_positions[0]
            
            # ตรวจสอบว่า imbalance หรือไม่
            is_imbalanced = buy_ratio < self.min_balance_ratio or buy_ratio > (1 - self.min_balance_ratio)
            
            # ถ้า imbalance และมีไม้ติดเยอะ
            if is_imbalanced and max_distance > 30:
                # สร้าง support hedge เพื่อช่วยไม้ที่ติด
                self.create_balance_support_hedge(most_stuck_pos, buy_ratio)
                
        except Exception as e:
            self.log(f"Error in smart balance management: {str(e)}", "ERROR")

    def create_balance_support_hedge(self, stuck_position: Position, current_buy_ratio: float):
        """🛡️ สร้าง hedge เพื่อช่วยไม้ที่ติดและสร้างสมดุล - Enhanced with Balance Check"""
        try:
            # 🆕 ตรวจสอบ balance ปัจจุบันก่อนสร้าง hedge
            current_balance = self._get_current_balance()
            if current_balance <= 0:
                self.log(f"⚠️ Cannot create hedge: Invalid balance ${current_balance:.2f}", "WARNING")
                return False
            
            # 🆕 ตรวจสอบ portfolio loss แบบยืดหยุ่นตาม balance
            if self.positions:
                total_profit_loss = sum(p.profit for p in self.positions)
                
                # 🆕 คำนวณ threshold แบบยืดหยุ่น (15% ของ balance)
                balance_threshold = current_balance * 0.15
                
                # 🆕 ใช้ balance ปัจจุบันในการตัดสินใจ
                if total_profit_loss < -balance_threshold:
                    self.log(f"⚠️ Cannot create hedge: Portfolio loss ${total_profit_loss:.2f} > Balance threshold ${balance_threshold:.2f}", "WARNING")
                    self.log(f"   Current Balance: ${current_balance:.2f} | Loss: ${total_profit_loss:.2f} | Threshold: ${balance_threshold:.2f}", "INFO")
                    return False
                else:
                    self.log(f"✅ Portfolio loss ${total_profit_loss:.2f} within balance threshold ${balance_threshold:.2f}", "INFO")
                    self.log(f"   Current Balance: ${current_balance:.2f} | Safe to create hedge", "INFO")
            
            # 🎯 Logic เดิม + ปรับให้ยืดหยุ่นขึ้น
            if stuck_position.type == "BUY" and current_buy_ratio > 0.65:  # ลดจาก 0.7 เป็น 0.65
                hedge_volume = min(stuck_position.volume * 0.7, 0.05)  # ลดจาก 0.8 เป็น 0.7 และจำกัด max 0.05
                hedge_type = "SELL"
                self.log(f"🔄 Creating ENHANCED BALANCE SUPPORT: SELL hedge {hedge_volume:.2f} lots for stuck BUY #{stuck_position.ticket}", "INFO")
                
            elif stuck_position.type == "SELL" and current_buy_ratio < 0.35:  # เพิ่มจาก 0.3 เป็น 0.35
                hedge_volume = min(stuck_position.volume * 0.7, 0.05)  # ลดจาก 0.8 เป็น 0.7 และจำกัด max 0.05
                hedge_type = "BUY"
                self.log(f"🔄 Creating ENHANCED BALANCE SUPPORT: BUY hedge {hedge_volume:.2f} lots for stuck SELL #{stuck_position.ticket}", "INFO")
                
            else:
                self.log(f"ℹ️ No hedge needed: BUY ratio {current_buy_ratio:.1%} is balanced", "INFO")
                return False  # ไม่ต้องสร้าง hedge
            
            # 🆕 สร้าง hedge โดยใช้ระบบ auto hedge พร้อม balance tracking
            success = self.execute_auto_hedge(stuck_position, "ENHANCED_BALANCE_SUPPORT")
            if success:
                self.log(f"✅ Enhanced balance support hedge created successfully", "SUCCESS")
                self.log(f"   Hedge Type: {hedge_type} | Volume: {hedge_volume:.2f} | Balance: ${current_balance:.2f}", "INFO")
                return True
            else:
                self.log(f"❌ Failed to create enhanced balance support hedge", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Error creating enhanced balance support hedge: {str(e)}", "ERROR")
            return False

    def _get_current_balance(self) -> float:
        """💰 ดึง balance ปัจจุบันจาก MT5"""
        try:
            if MT5_AVAILABLE and mt5 and self.mt5_connected:
                account_info = mt5.account_info()
                if account_info and account_info.balance > 0:
                    return float(account_info.balance)
            
            # Fallback: ใช้ balance จาก positions หรือค่าเริ่มต้น
            if hasattr(self, 'initial_balance') and self.initial_balance > 0:
                return self.initial_balance
            
            # ค่าเริ่มต้นถ้าไม่มีข้อมูล
            return 1000.0
            
        except Exception as e:
            self.log(f"Error getting current balance: {str(e)}", "ERROR")
            return 1000.0

    def execute_smart_recovery_closes(self) -> bool:
        """🧠 AI Smart Recovery: ระบบปิดไม้อัจฉริยะเพื่อฟื้นฟู portfolio"""
        try:
            if not self.ai_margin_intelligence:
                return False
            
            # 📊 ประเมินสถานการณ์
            margin_risk = self.ai_assess_margin_risk()
            losing_positions = [p for p in self.positions if p.profit < 0]
            profitable_positions = [p for p in self.positions if p.profit > 0]
            
            if not profitable_positions:
                self.log("🔍 Smart Recovery: No profitable positions for recovery", "INFO")
                return False
            
            self.log(f"🧠 Smart Recovery Analysis: {margin_risk['risk_level']} risk, "
                   f"{len(losing_positions)} losing, {len(profitable_positions)} profitable", "INFO")
            
            recovery_success = False
            
            # 🎯 Strategy 1: Emergency Net Profit Baskets
            if margin_risk['risk_level'] in ['EMERGENCY', 'DANGER']:
                optimal_baskets = self.find_optimal_closing_baskets()
                
                for basket in optimal_baskets[:3]:  # Top 3 baskets
                    if basket['total_profit'] > 0 and basket['confidence'] >= 0.6:  # Lower confidence threshold
                        self.log(f"🚨 Emergency Recovery: Executing basket with ${basket['total_profit']:.2f} profit", "INFO")
                        
                        # ปิดทั้ง basket
                        for position in basket['positions']:
                            try:
                                success = self.close_position_smart(position, 
                                    f"Emergency Recovery: {basket['strategy']}")
                                if success:
                                    recovery_success = True
                                    time.sleep(0.5)  # Quick succession
                            except Exception as pos_error:
                                self.log(f"❌ Recovery error on {position.ticket}: {pos_error}", "ERROR")
                        
                        if recovery_success:
                            break
            
            # 🎯 Strategy 2: Intelligent Pair Closing
            if not recovery_success and len(losing_positions) >= 2:
                # หาไม้ขาดทุนที่น้อยที่สุด + ไม้กำไรที่เหมาะสม
                sorted_losses = sorted(losing_positions, key=lambda x: abs(x.profit))
                sorted_profits = sorted(profitable_positions, key=lambda x: x.profit, reverse=True)
                
                for loss_pos in sorted_losses[:3]:  # Top 3 smallest losses
                    for profit_pos in sorted_profits:
                        net_profit = profit_pos.profit + loss_pos.profit
                        
                        if net_profit > 5:  # Net positive > $5
                            # ตรวจสอบ balance impact
                            pair = [loss_pos, profit_pos]
                            target_analysis = self.calculate_dynamic_profit_target(pair)
                            
                            if target_analysis['meets_target']:
                                self.log(f"🎯 Smart Pair Recovery: Net ${net_profit:.2f} "
                                       f"({loss_pos.ticket} + {profit_pos.ticket})", "INFO")
                                
                                # ปิดทั้งคู่
                                pair_success = 0
                                for pos in pair:
                                    success = self.close_position_smart(pos, 
                                        f"Smart Pair Recovery: Net ${net_profit:.2f}")
                                    if success:
                                        pair_success += 1
                                        time.sleep(1)
                                
                                if pair_success >= 1:
                                    recovery_success = True
                                    break
                    
                    if recovery_success:
                        break
            
            # 🎯 Strategy 3: Margin Relief Priority
            if not recovery_success and margin_risk['risk_score'] >= 60:
                # ปิดไม้กำไรที่ให้ margin relief สูงสุด
                high_volume_profits = [p for p in profitable_positions if p.volume >= 0.02]  # >= 0.02 lots
                
                if high_volume_profits:
                    # เรียงตาม margin relief potential
                    sorted_by_margin = sorted(high_volume_profits, 
                                            key=lambda x: x.volume * x.profit, reverse=True)
                    
                    for position in sorted_by_margin[:2]:  # Top 2
                        if position.profit > 10:  # At least $10 profit
                            self.log(f"💰 Margin Relief Recovery: ${position.profit:.2f} "
                                   f"({position.volume} lots)", "INFO")
                            
                            success = self.close_position_smart(position, 
                                f"Margin Relief Recovery: {position.volume} lots")
                            if success:
                                recovery_success = True
                                time.sleep(1)
            
            # 🆕 Strategy 4: No Cut Loss - Profit Buffer Recovery
            if not recovery_success and hasattr(self, 'hedge_profit_buffer_tracker'):
                recovery_success = self._execute_profit_buffer_recovery()
            
            # 📊 Recovery Summary
            if recovery_success:
                self.log("✅ Smart Recovery executed successfully", "SUCCESS")
                
                # Update AI decision history
                self.ai_decision_history.append({
                    'timestamp': datetime.now(),
                    'action': 'smart_recovery',
                    'risk_level': margin_risk['risk_level'],
                    'success': True
                })
            else:
                self.log("⚠️ Smart Recovery: No suitable recovery actions found", "WARNING")
            
            return recovery_success
            
        except Exception as e:
            self.log(f"❌ Error in smart recovery closes: {str(e)}", "ERROR")
            return False

    def _execute_profit_buffer_recovery(self) -> bool:
        """🎯 No Cut Loss Recovery: ใช้ profit buffer แทนการคัท loss"""
        try:
            if not hasattr(self, 'hedge_profit_buffer_tracker') or not self.hedge_profit_buffer_tracker:
                return False
            
            recovery_success = False
            current_time = datetime.now()
            
            # ตรวจสอบ hedge profit buffer tracker
            for stuck_ticket, hedge_info in list(self.hedge_profit_buffer_tracker.items()):
                if hedge_info['status'] != 'ACTIVE':
                    continue
                
                # หา stuck position
                stuck_position = None
                for pos in self.positions:
                    if pos.ticket == stuck_ticket:
                        stuck_position = pos
                        break
                
                if not stuck_position:
                    # Stuck position ถูกปิดแล้ว
                    hedge_info['status'] = 'COMPLETED'
                    continue
                
                # คำนวณ profit buffer ปัจจุบัน
                current_profit_buffer = self._calculate_current_profit_buffer(stuck_position)
                hedge_info['current_profit_buffer'] = current_profit_buffer
                
                # ตรวจสอบว่าถึง target profit buffer หรือยัง
                target_buffer = hedge_info['target_profit_buffer']
                
                if current_profit_buffer >= target_buffer:
                    # 🎯 ถึง target profit buffer แล้ว - ปิด stuck position
                    self.log(f"🎯 Profit Buffer Target Reached: Position {stuck_ticket}", "INFO")
                    self.log(f"   Current Buffer: ${current_profit_buffer:.2f} | Target: ${target_buffer:.2f}", "INFO")
                    
                    # ปิด stuck position
                    success = self.close_position_smart(stuck_position, 
                        f"Profit Buffer Recovery: Buffer ${current_profit_buffer:.2f} >= Target ${target_buffer:.2f}")
                    
                    if success:
                        hedge_info['status'] = 'COMPLETED'
                        recovery_success = True
                        self.log(f"✅ Successfully closed stuck position {stuck_ticket} using profit buffer", "SUCCESS")
                    else:
                        self.log(f"❌ Failed to close stuck position {stuck_ticket}", "ERROR")
                
                else:
                    # ยังไม่ถึง target - แสดงสถานการณ์
                    buffer_percentage = (current_profit_buffer / target_buffer) * 100
                    self.log(f"📊 Profit Buffer Progress: Position {stuck_ticket} - {buffer_percentage:.1f}%", "INFO")
                    self.log(f"   Current: ${current_profit_buffer:.2f} | Target: ${target_buffer:.2f} | Remaining: ${target_buffer - current_profit_buffer:.2f}", "INFO")
            
            return recovery_success
            
        except Exception as e:
            self.log(f"Error in profit buffer recovery: {str(e)}", "ERROR")
            return False

    def _calculate_current_profit_buffer(self, stuck_position: Position) -> float:
        """📊 คำนวณ profit buffer ปัจจุบันสำหรับ stuck position"""
        try:
            if not self.positions:
                return 0.0
            
            current_profit_buffer = 0.0
            
            # 1. คำนวณ profit จาก hedge positions ที่เกี่ยวข้อง
            if hasattr(self, 'hedge_profit_buffer_tracker'):
                stuck_ticket = stuck_position.ticket
                if stuck_ticket in self.hedge_profit_buffer_tracker:
                    hedge_info = self.hedge_profit_buffer_tracker[stuck_ticket]
                    hedge_type = hedge_info['hedge_type']
                    
                    # หา hedge positions ที่เกี่ยวข้อง
                    for pos in self.positions:
                        if pos.ticket != stuck_ticket:  # ไม่ใช่ stuck position เดียวกัน
                            # ตรวจสอบว่าเป็น hedge position หรือไม่
                            if self._is_hedge_position(pos, stuck_position, hedge_type):
                                if pos.profit > 0:  # เฉพาะไม้กำไร
                                    current_profit_buffer += pos.profit
            
            # 2. คำนวณ profit จากไม้อื่นๆ ที่ช่วยได้
            for pos in self.positions:
                if pos.ticket != stuck_position.ticket:  # ไม่ใช่ stuck position เดียวกัน
                    if pos.profit > 0:  # เฉพาะไม้กำไร
                        # เพิ่ม profit จากไม้ที่ช่วยได้ (ไม่ใช่ hedge)
                        if not self._is_hedge_position(pos, stuck_position, hedge_type if 'hedge_type' in locals() else None):
                            current_profit_buffer += pos.profit * 0.3  # เพิ่ม 30% ของ profit
            
            return max(0.0, current_profit_buffer)
            
        except Exception as e:
            self.log(f"Error calculating current profit buffer: {str(e)}", "ERROR")
            return 0.0

    def _is_hedge_position(self, position: Position, stuck_position: Position, hedge_type: str) -> bool:
        """🔍 ตรวจสอบว่า position เป็น hedge position หรือไม่"""
        try:
            if not hedge_type:
                return False
            
            # ตรวจสอบว่าเป็น hedge position หรือไม่
            if hedge_type == "SELL" and position.type == "SELL":
                # SELL hedge สำหรับ BUY stuck position
                return True
            elif hedge_type == "BUY" and position.type == "BUY":
                # BUY hedge สำหรับ SELL stuck position
                return True
            
            return False
            
        except Exception as e:
            self.log(f"Error checking hedge position: {str(e)}", "ERROR")
            return False

    def ai_assess_margin_risk(self) -> dict:
        """🤖 AI ประเมินความเสี่ยงของ margin แบบอัจฉริยะ"""
        try:
            if not self.ai_margin_intelligence:
                return {"risk_level": "SAFE", "risk_score": 0, "confidence": 0.5}
            
            risk_factors = {}
            total_score = 0
            
            # 1. 📊 Current Margin Level (ปัจจัยหลัก)
            try:
                if self.mt5_connected and MT5_AVAILABLE:
                    account_info = mt5.account_info()
                    if account_info:
                        margin_level = account_info.margin_level if account_info.margin_level else 1000
                        margin_used_pct = (account_info.margin / account_info.balance) * 100 if account_info.balance > 0 else 0
                        
                        # 🆕 เพิ่ม Equity monitoring
                        equity = account_info.equity if account_info.equity else account_info.balance
                        balance = account_info.balance if account_info.balance > 0 else 1
                        equity_ratio = equity / balance
                        
                        # 🆕 Smart Equity Monitoring - ยืดหยุ่นและฉลาดขึ้น
                        current_time = time.time()
                        
                        # ตรวจสอบการเปลี่ยนแปลงแบบ dynamic
                        if not hasattr(self, '_equity_history'):
                            self._equity_history = []
                            self._last_equity_check = current_time
                        
                        # เพิ่มข้อมูลปัจจุบันเข้า history (เก็บ 10 ค่าล่าสุด)
                        self._equity_history.append({
                            'ratio': equity_ratio,
                            'equity': equity,
                            'timestamp': current_time
                        })
                        
                        # เก็บแค่ 10 ค่าล่าสุด
                        if len(self._equity_history) > 10:
                            self._equity_history.pop(0)
                        
                        # คำนวณการเปลี่ยนแปลง
                        if len(self._equity_history) >= 2:
                            recent_change = self._equity_history[-1]['ratio'] - self._equity_history[-2]['ratio']
                            change_percent = abs(recent_change) * 100
                            
                            # ตรวจสอบการเปลี่ยนแปลงแบบฉับพลัน (มากกว่า 1% ในครั้งเดียว)
                            sudden_drop = recent_change < -0.01
                            sudden_recovery = recent_change > 0.01
                            
                            # Smart thresholds ตามการเปลี่ยนแปลง - ยืดหยุ่นขึ้น
                            if sudden_drop:
                                # ถ้าตกลงฉับพลัน ให้ปรับ threshold ให้ยืดหยุ่นขึ้นมาก
                                warning_threshold = 0.75  # จาก 0.85 เป็น 0.75
                                caution_threshold = 0.85   # จาก 0.90 เป็น 0.85
                                self.log(f"🚨 SUDDEN EQUITY DROP: {change_percent:.2f}% in one check!", "WARNING")
                            elif sudden_recovery:
                                # ถ้าฟื้นตัวขึ้น ให้กลับไปใช้ threshold ปกติ
                                warning_threshold = 0.80
                                caution_threshold = 0.90
                                self.log(f"📈 EQUITY RECOVERY: +{change_percent:.2f}% - Back to normal thresholds", "INFO")
                            else:
                                # การเปลี่ยนแปลงปกติ - ยืดหยุ่นขึ้น
                                warning_threshold = 0.80  # จาก 0.90 เป็น 0.80
                                caution_threshold = 0.90  # จาก 0.95 เป็น 0.90
                        else:
                            # ยังไม่มีข้อมูลเพียงพอ ใช้ค่าเริ่มต้น - ยืดหยุ่นขึ้น
                            warning_threshold = 0.80  # จาก 0.90 เป็น 0.80
                            caution_threshold = 0.90  # จาก 0.95 เป็น 0.90
                            recent_change = 0
                        
                        # Smart Logging ตาม thresholds ที่ปรับแล้ว
                        if equity_ratio < warning_threshold:
                            if not hasattr(self, '_last_equity_warning') or self._last_equity_warning != 'WARNING':
                                self.log(f"⚠️ EQUITY WARNING: {equity_ratio:.1%} (${equity:.2f} / ${balance:.2f}) - Threshold: {warning_threshold:.1%}", "WARNING")
                                self._last_equity_warning = 'WARNING'
                        elif equity_ratio < caution_threshold:
                            if not hasattr(self, '_last_equity_warning') or self._last_equity_warning != 'CAUTION':
                                self.log(f"📊 EQUITY CAUTION: {equity_ratio:.1%} (${equity:.2f} / ${balance:.2f}) - Threshold: {caution_threshold:.1%}", "INFO")
                                self._last_equity_warning = 'CAUTION'
                        else:
                            # Reset warning flag เมื่อ Equity กลับมาปกติ
                            if hasattr(self, '_last_equity_warning'):
                                delattr(self, '_last_equity_warning')
                        
                        # ตรวจสอบการเปลี่ยนแปลงแบบต่อเนื่อง (ทุก 30 วินาที)
                        if current_time - self._last_equity_check > 30:
                            self._last_equity_check = current_time
                            
                            # คำนวณ trend จาก 5 ค่าล่าสุด
                            if len(self._equity_history) >= 5:
                                recent_5 = [h['ratio'] for h in self._equity_history[-5:]]
                                trend = sum(recent_5[i] - recent_5[i-1] for i in range(1, len(recent_5))) / (len(recent_5) - 1)
                                
                                if trend < -0.005:  # ตกลงต่อเนื่อง
                                    self.log(f"📉 EQUITY TREND: Declining trend detected (-{abs(trend)*100:.2f}% per check)", "WARNING")
                                elif trend > 0.005:  # ฟื้นตัวต่อเนื่อง
                                    self.log(f"📈 EQUITY TREND: Recovery trend detected (+{trend*100:.2f}% per check)", "INFO")
                    else:
                        margin_level = 1000
                        margin_used_pct = 50  # Default assumption
                        equity_ratio = 0.95  # Default assumption
                else:
                    # Fallback calculation
                    margin_used_pct = min(len(self.positions) * 2, 90)  # Rough estimate
                    margin_level = max(1000 - margin_used_pct * 10, 100)
                    equity_ratio = 0.95  # Default assumption
                
                # Convert to risk score (0-100) - ปรับให้เข้มงวดขึ้น
                if margin_used_pct >= 95:
                    margin_risk = 95
                elif margin_used_pct >= 85:
                    margin_risk = 70 + (margin_used_pct - 85) * 2.5
                elif margin_used_pct >= 70:
                    margin_risk = 40 + (margin_used_pct - 70) * 2
                elif margin_used_pct >= 50:  # เพิ่มเงื่อนไขใหม่
                    margin_risk = 20 + (margin_used_pct - 50) * 1.5
                else:
                    margin_risk = max(0, margin_used_pct * 0.4)  # ลด scale ลง
                
                risk_factors['margin_level'] = margin_risk
                total_score += margin_risk * self.margin_risk_factors['account_health_weight']
                
            except Exception as margin_error:
                self.log(f"Warning: Could not assess margin level: {margin_error}", "WARNING")
                risk_factors['margin_level'] = 50  # Default medium risk
                total_score += 50 * self.margin_risk_factors['account_health_weight']
            
            # 2. 📈 Position Count Risk
            position_count = len(self.positions)
            max_safe_positions = self.max_positions * 0.7  # 70% of max is considered safe
            
            if position_count >= self.max_positions * 0.95:
                position_risk = 90
            elif position_count >= max_safe_positions:
                excess = position_count - max_safe_positions
                max_excess = self.max_positions * 0.25
                position_risk = 40 + (excess / max_excess) * 50
            else:
                position_risk = (position_count / max_safe_positions) * 40
            
            risk_factors['position_count'] = position_risk
            total_score += position_risk * self.margin_risk_factors['position_count_weight']
            
            # 3. 📊 Market Volatility Risk
            try:
                volatility_risk = 30  # Default medium
                if hasattr(self, 'recent_volatility') and self.recent_volatility:
                    if self.recent_volatility > 2.0:
                        volatility_risk = 80
                    elif self.recent_volatility > 1.5:
                        volatility_risk = 60
                    elif self.recent_volatility > 1.0:
                        volatility_risk = 40
                    else:
                        volatility_risk = 20
                
                risk_factors['volatility'] = volatility_risk
                total_score += volatility_risk * self.margin_risk_factors['volatility_weight']
                
            except:
                risk_factors['volatility'] = 30
                total_score += 30 * self.margin_risk_factors['volatility_weight']
            
            # 4. 🕐 Market Session Risk
            current_hour = datetime.now().hour
            if 0 <= current_hour <= 6:  # Asian session - higher volatility
                session_risk = 60
            elif 7 <= current_hour <= 15:  # European session - medium
                session_risk = 40
            elif 16 <= current_hour <= 20:  # US session - high volatility
                session_risk = 70
            else:  # Overlap periods - highest risk
                session_risk = 80
            
            risk_factors['market_session'] = session_risk
            total_score += session_risk * self.margin_risk_factors['market_session_weight']
            
            # 5. 🛡️ Broker Buffer Assessment
            losing_positions = [p for p in self.positions if p.profit < 0]
            total_loss = sum(abs(p.profit) for p in losing_positions)
            
            if total_loss > 500:  # High total loss
                buffer_risk = 80
            elif total_loss > 200:
                buffer_risk = 60
            elif total_loss > 50:
                buffer_risk = 40
            else:
                buffer_risk = 20
            
            risk_factors['broker_buffer'] = buffer_risk
            total_score += buffer_risk * self.margin_risk_factors['broker_buffer_weight']
            
            # 📊 Final Risk Assessment
            total_score = min(100, max(0, total_score))
            
            if total_score >= 85:
                risk_level = "EMERGENCY"
                confidence = 0.95
            elif total_score >= 70:
                risk_level = "DANGER"
                confidence = 0.85
            elif total_score >= 50:
                risk_level = "CAUTION"
                confidence = 0.75
            else:
                risk_level = "SAFE"
                confidence = 0.65
            
            result = {
                'risk_level': risk_level,
                'risk_score': total_score,
                'confidence': confidence,
                'factors': risk_factors,
                'recommendation': self._get_margin_recommendation(risk_level, total_score)
            }
            
            # 📝 Log significant risk changes
            if hasattr(self, '_last_margin_risk_level'):
                if self._last_margin_risk_level != risk_level:
                    self.log(f"🤖 AI Margin Risk: {self._last_margin_risk_level} → {risk_level} (Score: {total_score:.1f})", "INFO")
            
            self._last_margin_risk_level = risk_level
            return result
            
        except Exception as e:
            self.log(f"Error in AI margin risk assessment: {str(e)}", "ERROR")
            return {"risk_level": "CAUTION", "risk_score": 50, "confidence": 0.5}

    def analyze_market_intelligence(self) -> dict:
        """🧠 Market Intelligence: วิเคราะห์ตลาดแบบ real-time เพื่อเพิ่มความแม่นยำ"""
        try:
            if not self.market_intelligence_enabled:
                return {'enabled': False}
            
            current_time = time.time()
            market_analysis = {
                'timestamp': current_time,
                'reversal_detected': False,
                'volume_spike': False,
                'momentum_trend': 'NEUTRAL',
                'market_condition': 'NORMAL',
                'recommendation': 'CONTINUE_NORMAL',
                'confidence': 0.7
            }
            
            # 1. 📊 Market Reversal Detection
            if self.market_reversal_detection and MT5_AVAILABLE:
                try:
                    # ดึงข้อมูล candlestick ล่าสุด
                    rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M5, 0, self.reversal_detection_periods)
                    if rates is not None and len(rates) >= 10:
                        df = pd.DataFrame(rates) if pd else None
                        if df is not None:
                            # ตรวจสอบ reversal pattern
                            recent_highs = df['high'].tail(5).values
                            recent_lows = df['low'].tail(5).values
                            
                            # Higher Highs + Higher Lows = Uptrend
                            # Lower Highs + Lower Lows = Downtrend
                            # Break of pattern = Potential Reversal
                            
                            if (recent_highs[-1] < recent_highs[-2] and 
                                recent_lows[-1] < recent_lows[-2]):
                                market_analysis['reversal_detected'] = True
                                market_analysis['reversal_type'] = 'BEARISH'
                                market_analysis['market_condition'] = 'REVERSAL'
                                market_analysis['confidence'] += 0.1
                                
                                # ป้องกัน log spam - log เฉพาะเมื่อเปลี่ยนแปลง
                                if not hasattr(self, '_last_market_condition') or \
                                   self._last_market_condition != 'BEARISH_REVERSAL' or \
                                   (current_time - getattr(self, '_last_market_log_time', 0)) > 30:  # 30 วินาที
                                    self.log("🐻 Market Intelligence: Bearish reversal pattern detected", "INFO")
                                    self._last_market_condition = 'BEARISH_REVERSAL'
                                    self._last_market_log_time = current_time
                                
                            elif (recent_highs[-1] > recent_highs[-2] and 
                                  recent_lows[-1] > recent_lows[-2]):
                                market_analysis['reversal_detected'] = True
                                market_analysis['reversal_type'] = 'BULLISH'
                                market_analysis['market_condition'] = 'REVERSAL'
                                market_analysis['confidence'] += 0.1
                                
                                # ป้องกัน log spam - log เฉพาะเมื่อเปลี่ยนแปลง
                                if not hasattr(self, '_last_market_condition') or \
                                   self._last_market_condition != 'BULLISH_REVERSAL' or \
                                   (current_time - getattr(self, '_last_market_log_time', 0)) > 30:  # 30 วินาที
                                    self.log("🐂 Market Intelligence: Bullish reversal pattern detected", "INFO")
                                    self._last_market_condition = 'BULLISH_REVERSAL'
                                    self._last_market_log_time = current_time
                            
                            # ตรวจสอบ market condition เพิ่มเติม
                            if not market_analysis['reversal_detected']:
                                # ตรวจสอบ volatility
                                price_changes = []
                                for i in range(1, len(df)):
                                    change = abs(df['close'].iloc[i] - df['close'].iloc[i-1]) / df['close'].iloc[i-1] * 100
                                    price_changes.append(change)
                                
                                avg_change = sum(price_changes) / len(price_changes) if price_changes else 0
                                
                                if avg_change > 0.5:  # 0.5% change per candle
                                    market_analysis['market_condition'] = 'VOLATILE'
                                    # ป้องกัน log spam
                                    if not hasattr(self, '_last_market_condition') or \
                                       self._last_market_condition != 'VOLATILE' or \
                                       (current_time - getattr(self, '_last_market_log_time', 0)) > 30:
                                        self.log(f"📊 Market Intelligence: High volatility detected ({avg_change:.2f}% avg change)", "INFO")
                                        self._last_market_condition = 'VOLATILE'
                                        self._last_market_log_time = current_time
                                elif avg_change < 0.1:  # 0.1% change per candle
                                    market_analysis['market_condition'] = 'SIDEWAYS'
                                    # ป้องกัน log spam
                                    if not hasattr(self, '_last_market_condition') or \
                                       self._last_market_condition != 'SIDEWAYS' or \
                                       (current_time - getattr(self, '_last_market_log_time', 0)) > 30:
                                        self.log(f"📊 Market Intelligence: Low volatility - sideways market detected", "INFO")
                                        self._last_market_condition = 'SIDEWAYS'
                                        self._last_market_log_time = current_time
                                else:
                                    # ตรวจสอบ trend strength
                                    trend_strength = 0
                                    if len(df) >= 20:
                                        # คำนวณ trend จาก 20 candles
                                        first_half = df['close'].iloc[:10].mean()
                                        second_half = df['close'].iloc[10:].mean()
                                        trend_change = (second_half - first_half) / first_half * 100
                                        
                                        if abs(trend_change) > 1.0:  # 1% trend change
                                            if trend_change > 0:
                                                market_analysis['market_condition'] = 'TRENDING'
                                                market_analysis['momentum_trend'] = 'BULLISH'
                                                # ป้องกัน log spam
                                                if not hasattr(self, '_last_market_condition') or \
                                                   self._last_market_condition != 'BULLISH_TREND' or \
                                                   (current_time - getattr(self, '_last_market_log_time', 0)) > 30:
                                                    self.log(f"📈 Market Intelligence: Strong bullish trend detected ({trend_change:.2f}%)", "INFO")
                                                    self._last_market_condition = 'BULLISH_TREND'
                                                    self._last_market_log_time = current_time
                                            else:
                                                market_analysis['market_condition'] = 'TRENDING'
                                                market_analysis['momentum_trend'] = 'BEARISH'
                                                # ป้องกัน log spam
                                                if not hasattr(self, '_last_market_condition') or \
                                                   self._last_market_condition != 'BEARISH_TREND' or \
                                                   (current_time - getattr(self, '_last_market_log_time', 0)) > 30:
                                                    self.log(f"📉 Market Intelligence: Strong bearish trend detected ({trend_change:.2f}%)", "INFO")
                                                    self._last_market_condition = 'BEARISH_TREND'
                                                    self._last_market_log_time = current_time
                                        else:
                                            market_analysis['market_condition'] = 'NORMAL'
                                            # ป้องกัน log spam
                                            if not hasattr(self, '_last_market_condition') or \
                                               self._last_market_condition != 'NORMAL' or \
                                               (current_time - getattr(self, '_last_market_log_time', 0)) > 60:  # 60 วินาทีสำหรับ NORMAL
                                                self.log("📊 Market Intelligence: Normal market condition detected", "INFO")
                                                self._last_market_condition = 'NORMAL'
                                                self._last_market_log_time = current_time
                                    else:
                                        market_analysis['market_condition'] = 'NORMAL'
                                        # ป้องกัน log spam
                                        if not hasattr(self, '_last_market_condition') or \
                                           self._last_market_condition != 'NORMAL' or \
                                           (current_time - getattr(self, '_last_market_log_time', 0)) > 60:  # 60 วินาทีสำหรับ NORMAL
                                            self.log("📊 Market Intelligence: Normal market condition detected", "INFO")
                                            self._last_market_condition = 'NORMAL'
                                            self._last_market_log_time = current_time
                            
                            # เก็บประวัติ
                            if not hasattr(self, 'market_reversal_history'):
                                self.market_reversal_history = []
                            
                            self.market_reversal_history.append({
                                'timestamp': current_time,
                                'type': market_analysis.get('reversal_type', 'NONE'),
                                'confidence': market_analysis['confidence']
                            })
                            
                            # เก็บแค่ 50 รายการล่าสุด
                            if len(self.market_reversal_history) > 50:
                                self.market_reversal_history.pop(0)
                                
                except Exception as e:
                    self.log(f"Error in reversal detection: {str(e)}", "WARNING")
            
            # 2. 📈 Volume & Momentum Analysis
            if self.volume_momentum_analysis and MT5_AVAILABLE:
                try:
                    # ดึงข้อมูล volume และ price
                    rates = mt5.copy_rates_from_pos(self.symbol, mt5.TIMEFRAME_M1, 0, self.momentum_lookback_periods)
                    if rates is not None and len(rates) >= 5:
                        df = pd.DataFrame(rates) if pd else None
                        if df is not None:
                            # คำนวณ momentum (price change rate)
                            price_changes = df['close'].pct_change().dropna()
                            momentum = price_changes.mean() * 100  # เป็นเปอร์เซ็นต์
                            
                            # กำหนด momentum trend
                            if momentum > 0.1:  # ขึ้นมากกว่า 0.1% ต่อ minute
                                market_analysis['momentum_trend'] = 'BULLISH'
                                market_analysis['confidence'] += 0.05
                            elif momentum < -0.1:  # ลงมากกว่า 0.1% ต่อ minute
                                market_analysis['momentum_trend'] = 'BEARISH'
                                market_analysis['confidence'] -= 0.05
                            
                            # เก็บประวัติ
                            if not hasattr(self, 'momentum_trend_history'):
                                self.momentum_trend_history = []
                            
                            self.momentum_trend_history.append({
                                'timestamp': current_time,
                                'momentum': momentum,
                                'trend': market_analysis['momentum_trend']
                            })
                            
                            if len(self.momentum_trend_history) > 100:
                                self.momentum_trend_history.pop(0)
                                
                except Exception as e:
                    self.log(f"Error in momentum analysis: {str(e)}", "WARNING")
            
            # 3. 🎯 Smart Threshold Adjustment
            if self.dynamic_threshold_adjustment:
                # ปรับ thresholds ตาม market condition
                if market_analysis['reversal_detected']:
                    # เมื่อมี reversal ให้ปรับ thresholds ให้ยืดหยุ่นขึ้น
                    adjustment_factor = 0.8  # ลด thresholds ลง 20%
                    market_analysis['threshold_adjustment'] = adjustment_factor
                    market_analysis['recommendation'] = 'ADJUST_THRESHOLDS'
                    
                    # เก็บประวัติการปรับ
                    if not hasattr(self, 'threshold_adjustment_history'):
                        self.threshold_adjustment_history = []
                    
                    self.threshold_adjustment_history.append({
                        'timestamp': current_time,
                        'factor': adjustment_factor,
                        'reason': 'reversal_detected'
                    })
                    
                    if len(self.threshold_adjustment_history) > 50:
                        self.threshold_adjustment_history.pop(0)
                
                elif market_analysis['momentum_trend'] == 'NEUTRAL':
                    # เมื่อ momentum เป็นกลาง ให้ใช้ thresholds ปกติ
                    market_analysis['threshold_adjustment'] = 1.0
                    market_analysis['recommendation'] = 'USE_NORMAL_THRESHOLDS'
            
            # 4. 🕐 Market Session Optimization
            if self.session_based_optimization:
                current_hour = datetime.now().hour
                
                # ปรับตาม market session
                if 0 <= current_hour <= 6:  # Asian session
                    market_analysis['session_factor'] = 1.2  # เพิ่ม thresholds 20%
                    market_analysis['recommendation'] = 'ASIAN_SESSION_ADJUSTMENT'
                elif 16 <= current_hour <= 20:  # US session
                    market_analysis['session_factor'] = 0.9  # ลด thresholds 10%
                    market_analysis['recommendation'] = 'US_SESSION_ADJUSTMENT'
                else:
                    market_analysis['session_factor'] = 1.0  # ปกติ
            
            # จำกัด confidence ไม่เกิน 0.95
            try:
                market_analysis['confidence'] = min(0.95, max(0.3, market_analysis['confidence']))
            except Exception as e:
                self.log(f"Warning: Error adjusting confidence: {str(e)}", "WARNING")
                market_analysis['confidence'] = 0.7  # Default confidence
            
            return market_analysis
            
        except Exception as e:
            self.log(f"Error in market intelligence analysis: {str(e)}", "ERROR")
            return {'enabled': False, 'error': str(e)}

    def optimize_portfolio_performance(self) -> dict:
        """🚀 Portfolio Optimization Engine: ปรับปรุงการจัดการ portfolio แบบ real-time"""
        try:
            if not self.portfolio_optimization_enabled:
                return {'enabled': False}
            
            current_time = time.time()
            optimization_result = {
                'timestamp': current_time,
                'optimization_needed': False,
                'risk_adjustment': False,
                'rebalancing_needed': False,
                'recommendations': [],
                'confidence': 0.7
            }
            
            # 1. 📊 Real-Time Performance Analysis
            if self.real_time_performance_analysis:
                try:
                    # คำนวณ performance metrics
                    if self.positions:
                        profitable_positions = [p for p in self.positions if p.profit > 0]
                        losing_positions = [p for p in self.positions if p.profit < 0]
                        
                        total_profit = sum(p.profit for p in profitable_positions)
                        total_loss = abs(sum(p.profit for p in losing_positions))
                        
                        # Win Rate
                        win_rate = len(profitable_positions) / len(self.positions) if self.positions else 0
                        
                        # Profit Factor
                        profit_factor = total_profit / total_loss if total_loss > 0 else float('inf')
                        
                        # Average Profit/Loss
                        avg_profit = total_profit / len(profitable_positions) if profitable_positions else 0
                        avg_loss = total_loss / len(losing_positions) if losing_positions else 0
                        
                        # อัพเดท performance metrics
                        self.performance_metrics.update({
                            'win_rate': win_rate,
                            'avg_profit': avg_profit,
                            'avg_loss': avg_loss,
                            'profit_factor': profit_factor
                        })
                        
                        # เก็บประวัติ
                        if not hasattr(self, 'portfolio_performance_history'):
                            self.portfolio_performance_history = []
                        
                        self.portfolio_performance_history.append({
                            'timestamp': current_time,
                            'win_rate': win_rate,
                            'profit_factor': profit_factor,
                            'total_positions': len(self.positions),
                            'portfolio_health': self.portfolio_health
                        })
                        
                        if len(self.portfolio_performance_history) > 200:
                            self.portfolio_performance_history.pop(0)
                        
                        # วิเคราะห์ performance
                        if win_rate < 0.4:  # Win rate ต่ำกว่า 40%
                            optimization_result['recommendations'].append("Low win rate - consider reducing position size")
                            optimization_result['optimization_needed'] = True
                        
                        if profit_factor < 1.2:  # Profit factor ต่ำกว่า 1.2
                            optimization_result['recommendations'].append("Low profit factor - review strategy")
                            optimization_result['optimization_needed'] = True
                        
                        if avg_loss > abs(avg_profit) * 1.5:  # Loss มากกว่า profit 1.5 เท่า
                            optimization_result['recommendations'].append("High loss ratio - implement stop loss")
                            optimization_result['optimization_needed'] = True
                            
                except Exception as e:
                    self.log(f"Error in performance analysis: {str(e)}", "WARNING")
            
            # 2. 🎯 Dynamic Risk Adjustment
            if self.dynamic_risk_adjustment:
                try:
                    # ตรวจสอบการเปลี่ยนแปลงของ portfolio health
                    if hasattr(self, '_last_portfolio_health'):
                        health_change = abs(self.portfolio_health - self._last_portfolio_health) / 100
                        
                        if health_change > self.risk_adjustment_threshold:
                            optimization_result['risk_adjustment'] = True
                            optimization_result['recommendations'].append(f"Portfolio health changed {health_change:.1%} - adjusting risk parameters")
                            
                            # ปรับ risk parameters
                            if self.portfolio_health < 50:  # Health ต่ำ
                                # ลด risk
                                self.max_positions = max(10, int(self.max_positions * 0.8))
                                self.base_lot = max(0.01, self.base_lot * 0.8)
                                optimization_result['recommendations'].append("Reduced max positions and lot size due to low health")
                            elif self.portfolio_health > 80:  # Health สูง
                                # เพิ่ม risk
                                self.max_positions = min(50, int(self.max_positions * 1.1))
                                self.base_lot = min(0.10, self.base_lot * 1.1)
                                optimization_result['recommendations'].append("Increased max positions and lot size due to high health")
                            
                            # ปรับ risk parameters ตาม market condition
                            try:
                                market_analysis = self.analyze_market_intelligence()
                                market_condition = market_analysis.get('market_condition', 'NORMAL')
                                
                                if market_condition == 'VOLATILE':
                                    # ตลาดผันผวน - ลด risk
                                    self.max_positions = max(5, int(self.max_positions * 0.9))
                                    self.base_lot = max(0.01, self.base_lot * 0.9)
                                    optimization_result['recommendations'].append("Market volatility detected - reducing risk parameters")
                                    
                                elif market_condition == 'REVERSAL':
                                    # ตลาดกลับตัว - ปรับ risk ตามทิศทาง
                                    if market_analysis.get('reversal_type') == 'BEARISH':
                                        # Bearish reversal - ลด BUY exposure
                                        optimization_result['recommendations'].append("Bearish reversal - reducing BUY exposure")
                                    else:
                                        # Bullish reversal - ลด SELL exposure
                                        optimization_result['recommendations'].append("Bullish reversal - reducing SELL exposure")
                                        
                                elif market_condition == 'TRENDING':
                                    # ตลาดมี trend ชัดเจน - เพิ่ม confidence
                                    if market_analysis.get('momentum_trend') == 'BULLISH':
                                        optimization_result['recommendations'].append("Strong bullish trend - maintaining BUY positions")
                                    else:
                                        optimization_result['recommendations'].append("Strong bearish trend - maintaining SELL positions")
                                        
                                elif market_condition == 'SIDEWAYS':
                                    # ตลาด sideways - ลด risk
                                    self.max_positions = max(8, int(self.max_positions * 0.95))
                                    self.base_lot = max(0.01, self.base_lot * 0.95)
                                    optimization_result['recommendations'].append("Sideways market - reducing risk parameters")
                                    
                            except Exception as market_error:
                                self.log(f"Warning: Error in market-based risk adjustment: {str(market_error)}", "WARNING")
                            
                            # เก็บประวัติ
                            if not hasattr(self, 'risk_adjustment_history'):
                                self.risk_adjustment_history = []
                            
                            self.risk_adjustment_history.append({
                                'timestamp': current_time,
                                'health_change': health_change,
                                'new_max_positions': self.max_positions,
                                'new_base_lot': self.base_lot
                            })
                            
                            if len(self.risk_adjustment_history) > 100:
                                self.risk_adjustment_history.pop(0)
                    
                    # อัพเดท last health
                    self._last_portfolio_health = self.portfolio_health
                    
                except Exception as e:
                    self.log(f"Error in risk adjustment: {str(e)}", "WARNING")
            
            # 3. 🔄 Smart Position Rebalancing
            if self.smart_position_rebalancing:
                try:
                    # ตรวจสอบความสมดุลของ portfolio
                    if self.positions:
                        buy_volume = sum(p.volume for p in self.positions if p.type == "BUY")
                        sell_volume = sum(p.volume for p in self.positions if p.type == "SELL")
                        total_volume = buy_volume + sell_volume
                        
                        if total_volume > 0:
                            buy_ratio = buy_volume / total_volume
                            imbalance = abs(buy_ratio - 0.5)
                            
                            if imbalance > self.rebalancing_trigger_ratio:
                                # มีความไม่สมดุล
                                optimization_result['rebalancing_needed'] = True
                                
                                if buy_ratio > 0.65:  # BUY มากเกินไป
                                    optimization_result['recommendations'].append("BUY heavy portfolio - consider closing some BUY positions")
                                elif buy_ratio < 0.35:  # SELL มากเกินไป
                                    optimization_result['recommendations'].append("SELL heavy portfolio - consider closing some SELL positions")
                                
                                # เก็บประวัติ
                                if not hasattr(self, 'rebalancing_history'):
                                    self.rebalancing_history = []
                                
                                self.rebalancing_history.append({
                                    'timestamp': current_time,
                                    'buy_ratio': buy_ratio,
                                    'imbalance': imbalance,
                                    'action': 'rebalancing_triggered'
                                })
                                
                                if len(self.rebalancing_history) > 100:
                                    self.rebalancing_history.pop(0)
                    
                except Exception as e:
                    self.log(f"Error in position rebalancing: {str(e)}", "WARNING")
            
            # 4. 📈 Performance Trend Analysis
            if hasattr(self, 'portfolio_performance_history') and len(self.portfolio_performance_history) >= 10:
                try:
                    # วิเคราะห์ trend ของ performance
                    recent_performance = self.portfolio_performance_history[-10:]
                    win_rate_trend = [p['win_rate'] for p in recent_performance]
                    
                    # คำนวณ trend (positive = improving, negative = declining)
                    if len(win_rate_trend) >= 2:
                        trend = sum(win_rate_trend[i] - win_rate_trend[i-1] for i in range(1, len(win_rate_trend))) / (len(win_rate_trend) - 1)
                        
                        if trend > 0.02:  # ดีขึ้นมากกว่า 2% ต่อครั้ง
                            optimization_result['recommendations'].append("Performance improving - maintain current strategy")
                            optimization_result['confidence'] += 0.1
                        elif trend < -0.02:  # แย่ลงมากกว่า 2% ต่อครั้ง
                            optimization_result['recommendations'].append("Performance declining - review and adjust strategy")
                            optimization_result['confidence'] -= 0.1
                            
                except Exception as e:
                    self.log(f"Error in trend analysis: {str(e)}", "WARNING")
            
            # จำกัด confidence
            try:
                optimization_result['confidence'] = min(0.95, max(0.3, optimization_result['confidence']))
            except Exception as e:
                self.log(f"Warning: Error adjusting confidence: {str(e)}", "WARNING")
                optimization_result['confidence'] = 0.7  # Default confidence
            
            # Log ถ้ามี optimization ที่สำคัญ
            try:
                if optimization_result['optimization_needed'] or optimization_result['risk_adjustment']:
                    self.log(f"🚀 Portfolio Optimization: {len(optimization_result['recommendations'])} recommendations", "INFO")
                    for rec in optimization_result['recommendations']:
                        self.log(f"💡 {rec}", "INFO")
            except Exception as log_error:
                self.log(f"Warning: Error logging optimization results: {str(log_error)}", "WARNING")
            
            return optimization_result
            
        except Exception as e:
            self.log(f"Error in portfolio optimization: {str(e)}", "ERROR")
            return {'enabled': False, 'error': str(e)}

    def analyze_individual_position(self, position: 'Position') -> dict:
        """🧠 Individual Position Analysis: วิเคราะห์ไม้แต่ละตัวแบบละเอียด"""
        try:
            if not position:
                return {'error': 'No position provided'}
            
            current_time = time.time()
            analysis_result = {
                'ticket': position.ticket,
                'symbol': position.symbol,
                'type': position.type,
                'volume': position.volume,
                'quality_score': 0.0,
                'recovery_potential': 0.0,
                'risk_level': 'MEDIUM',
                'portfolio_impact': 'NEUTRAL',
                'future_outlook': 'NEUTRAL',
                'category': 'UNKNOWN',
                'recommendation': 'HOLD',
                'confidence': 0.7,
                'timestamp': current_time
            }
            
            # 1. 📊 Position Quality Score (0-100)
            try:
                # Profit Factor (30%)
                profit_factor = 0.0
                if hasattr(position, 'profit') and hasattr(position, 'price_open'):
                    if position.price_open > 0:
                        profit_pct = (position.profit / (position.price_open * position.volume)) * 100
                        profit_factor = max(0, min(100, 50 + profit_pct * 10))  # -5% = 0, +5% = 100
                
                # Distance Factor (25%)
                distance_factor = 0.0
                if hasattr(position, 'current_price') and hasattr(position, 'price_open'):
                    distance_pips = abs(position.current_price - position.price_open) * 10000  # Convert to pips
                    if distance_pips <= 10:
                        distance_factor = 100  # ใกล้ entry
                    elif distance_pips <= 25:
                        distance_factor = 75   # ปานกลาง
                    elif distance_pips <= 50:
                        distance_factor = 50   # ไกล
                    else:
                        distance_factor = 25   # ไกลมาก
                
                # Time Factor (20%)
                time_factor = 0.0
                if hasattr(position, 'open_time'):
                    try:
                        open_time = position.open_time if isinstance(position.open_time, datetime) else datetime.fromisoformat(str(position.open_time))
                        hours_in_market = (datetime.now() - open_time).total_seconds() / 3600
                        if hours_in_market <= 1:
                            time_factor = 100  # เปิดใหม่
                        elif hours_in_market <= 6:
                            time_factor = 80   # เปิดไม่นาน
                        elif hours_in_market <= 24:
                            time_factor = 60   # เปิด 1 วัน
                        else:
                            time_factor = max(20, 100 - (hours_in_market - 24) * 2)  # ลดลงตามเวลา
                    except:
                        time_factor = 50  # Default
                
                # Volume Factor (15%)
                volume_factor = 0.0
                if hasattr(self, 'positions') and self.positions:
                    total_volume = sum(p.volume for p in self.positions)
                    if total_volume > 0:
                        volume_ratio = position.volume / total_volume
                        if volume_ratio <= 0.1:
                            volume_factor = 100  # Volume น้อย
                        elif volume_ratio <= 0.25:
                            volume_factor = 80   # Volume ปานกลาง
                        else:
                            volume_factor = 60   # Volume มาก
                
                # Market Trend Alignment (10%)
                trend_factor = 50.0  # Default neutral
                try:
                    market_analysis = self.analyze_market_intelligence()
                    if market_analysis and market_analysis.get('momentum_trend'):
                        if (position.type == 'BUY' and market_analysis['momentum_trend'] == 'BULLISH') or \
                           (position.type == 'SELL' and market_analysis['momentum_trend'] == 'BEARISH'):
                            trend_factor = 100  # Trend เอื้ออำนวย
                        elif (position.type == 'BUY' and market_analysis['momentum_trend'] == 'BEARISH') or \
                             (position.type == 'SELL' and market_analysis['momentum_trend'] == 'BULLISH'):
                            trend_factor = 0    # Trend ไม่เอื้ออำนวย
                except:
                    trend_factor = 50.0  # Default
                
                # คำนวณ Quality Score รวม
                analysis_result['quality_score'] = (
                    profit_factor * 0.3 +
                    distance_factor * 0.25 +
                    time_factor * 0.2 +
                    volume_factor * 0.15 +
                    trend_factor * 0.1
                )
                
            except Exception as e:
                self.log(f"Error calculating quality score: {str(e)}", "WARNING")
                analysis_result['quality_score'] = 50.0  # Default
            
            # 2. 🎯 Recovery Potential (0-100)
            try:
                # Market Reversal Signals (35%)
                reversal_factor = 0.0
                try:
                    market_analysis = self.analyze_market_intelligence()
                    if market_analysis and market_analysis.get('reversal_detected'):
                        if (position.type == 'BUY' and market_analysis.get('reversal_type') == 'BULLISH') or \
                           (position.type == 'SELL' and market_analysis.get('reversal_type') == 'BEARISH'):
                            reversal_factor = 100  # Reversal เอื้ออำนวย
                        else:
                            reversal_factor = 0    # Reversal ไม่เอื้ออำนวย
                except:
                    reversal_factor = 50.0  # Default
                
                # Support/Resistance Levels (25%)
                sr_factor = 50.0  # Default
                try:
                    if hasattr(position, 'current_price') and hasattr(position, 'price_open'):
                        # คำนวณระยะห่างจาก entry price
                        distance_pips = abs(position.current_price - position.price_open) * 10000
                        if distance_pips <= 15:
                            sr_factor = 80   # ใกล้ entry (อาจฟื้นตัวได้)
                        elif distance_pips <= 30:
                            sr_factor = 60   # ปานกลาง
                        else:
                            sr_factor = 30   # ไกล (ยากที่จะฟื้นตัว)
                except:
                    sr_factor = 50.0  # Default
                
                # Volume Analysis (20%)
                volume_analysis = 50.0  # Default
                try:
                    if hasattr(position, 'volume'):
                        if position.volume <= 0.01:
                            volume_analysis = 80   # Volume น้อย (ฟื้นตัวง่าย)
                        elif position.volume <= 0.05:
                            volume_analysis = 60   # Volume ปานกลาง
                        else:
                            volume_analysis = 40   # Volume มาก (ฟื้นตัวยาก)
                except:
                    volume_analysis = 50.0  # Default
                
                # Technical Indicators (15%)
                technical_factor = 50.0  # Default
                
                # Historical Pattern (5%)
                pattern_factor = 50.0  # Default
                
                # คำนวณ Recovery Potential รวม
                analysis_result['recovery_potential'] = (
                    reversal_factor * 0.35 +
                    sr_factor * 0.25 +
                    volume_analysis * 0.2 +
                    technical_factor * 0.15 +
                    pattern_factor * 0.05
                )
                
            except Exception as e:
                self.log(f"Error calculating recovery potential: {str(e)}", "WARNING")
                analysis_result['recovery_potential'] = 50.0  # Default
            
            # 3. ⚠️ Risk Level Assessment
            try:
                # Margin Usage (40%)
                margin_factor = 0.0
                try:
                    if hasattr(self, 'positions') and self.positions:
                        total_volume = sum(p.volume for p in self.positions)
                        if total_volume > 0:
                            volume_ratio = position.volume / total_volume
                            if volume_ratio <= 0.1:
                                margin_factor = 20   # Risk ต่ำ
                            elif volume_ratio <= 0.25:
                                margin_factor = 50   # Risk ปานกลาง
                            else:
                                margin_factor = 80   # Risk สูง
                except:
                    margin_factor = 50.0  # Default
                
                # Distance Risk (30%)
                distance_risk = 0.0
                try:
                    if hasattr(position, 'current_price') and hasattr(position, 'price_open'):
                        distance_pips = abs(position.current_price - position.price_open) * 10000
                        if distance_pips <= 10:
                            distance_risk = 20   # Risk ต่ำ
                        elif distance_pips <= 25:
                            distance_risk = 50   # Risk ปานกลาง
                        elif distance_pips <= 50:
                            distance_risk = 70   # Risk สูง
                        else:
                            distance_risk = 90   # Risk สูงมาก
                except:
                    distance_risk = 50.0  # Default
                
                # Concentration Risk (20%)
                concentration_risk = 50.0  # Default
                
                # Volatility Risk (10%)
                volatility_risk = 50.0  # Default
                
                # คำนวณ Risk Level รวม
                total_risk = (
                    margin_factor * 0.4 +
                    distance_risk * 0.3 +
                    concentration_risk * 0.2 +
                    volatility_risk * 0.1
                )
                
                # กำหนด Risk Level
                if total_risk <= 30:
                    analysis_result['risk_level'] = 'LOW'
                elif total_risk <= 60:
                    analysis_result['risk_level'] = 'MEDIUM'
                else:
                    analysis_result['risk_level'] = 'HIGH'
                
            except Exception as e:
                self.log(f"Error calculating risk level: {str(e)}", "WARNING")
                analysis_result['risk_level'] = 'MEDIUM'  # Default
            
            # 4. 📊 Portfolio Impact Assessment
            try:
                if analysis_result['quality_score'] >= 80 and analysis_result['risk_level'] == 'LOW':
                    analysis_result['portfolio_impact'] = 'POSITIVE'
                elif analysis_result['quality_score'] <= 30 and analysis_result['risk_level'] == 'HIGH':
                    analysis_result['portfolio_impact'] = 'NEGATIVE'
                else:
                    analysis_result['portfolio_impact'] = 'NEUTRAL'
            except:
                analysis_result['portfolio_impact'] = 'NEUTRAL'
            
            # 5. 🔮 Future Outlook
            try:
                if analysis_result['recovery_potential'] >= 70 and analysis_result['quality_score'] >= 60:
                    analysis_result['future_outlook'] = 'BULLISH'
                elif analysis_result['recovery_potential'] <= 30 and analysis_result['quality_score'] <= 40:
                    analysis_result['future_outlook'] = 'BEARISH'
                else:
                    analysis_result['future_outlook'] = 'NEUTRAL'
            except:
                analysis_result['future_outlook'] = 'NEUTRAL'
            
            # 6. 🏷️ Position Categorization
            try:
                if analysis_result['quality_score'] >= 80 and analysis_result['risk_level'] == 'LOW':
                    analysis_result['category'] = 'KEEPER'
                    analysis_result['recommendation'] = 'HOLD'
                elif analysis_result['quality_score'] >= 60 and analysis_result['recovery_potential'] >= 50:
                    analysis_result['category'] = 'RECOVERABLE'
                    analysis_result['recommendation'] = 'WAIT'
                elif analysis_result['quality_score'] <= 40 and analysis_result['risk_level'] == 'HIGH':
                    analysis_result['category'] = 'TROUBLEMAKER'
                    analysis_result['recommendation'] = 'CLOSE'
                elif analysis_result['portfolio_impact'] == 'POSITIVE':
                    analysis_result['category'] = 'SUPPORT'
                    analysis_result['recommendation'] = 'HOLD'
                else:
                    analysis_result['category'] = 'NEUTRAL'
                    analysis_result['recommendation'] = 'MONITOR'
            except:
                analysis_result['category'] = 'NEUTRAL'
                analysis_result['recommendation'] = 'MONITOR'
            
            # 7. 📊 Confidence Calculation
            try:
                # ปรับ confidence ตามความแม่นยำของข้อมูล
                confidence_factors = []
                
                if analysis_result['quality_score'] > 0:
                    confidence_factors.append(0.8)
                if analysis_result['recovery_potential'] > 0:
                    confidence_factors.append(0.7)
                if analysis_result['risk_level'] != 'UNKNOWN':
                    confidence_factors.append(0.9)
                
                if confidence_factors:
                    analysis_result['confidence'] = sum(confidence_factors) / len(confidence_factors)
                else:
                    analysis_result['confidence'] = 0.7
                
                # จำกัด confidence
                analysis_result['confidence'] = min(0.95, max(0.3, analysis_result['confidence']))
                
            except Exception as e:
                self.log(f"Error calculating confidence: {str(e)}", "WARNING")
                analysis_result['confidence'] = 0.7  # Default
            
            return analysis_result
            
        except Exception as e:
            self.log(f"Error in individual position analysis: {str(e)}", "ERROR")
            return {
                'error': str(e),
                'quality_score': 50.0,
                'recovery_potential': 50.0,
                'risk_level': 'MEDIUM',
                'category': 'UNKNOWN',
                'recommendation': 'MONITOR',
                'confidence': 0.5
            }

    def analyze_portfolio_positions(self) -> dict:
        """📊 Portfolio Position Analysis: วิเคราะห์ไม้ทั้งหมดใน portfolio"""
        try:
            if not self.positions:
                return {'error': 'No positions available'}
            
            portfolio_analysis = {
                'total_positions': len(self.positions),
                'position_categories': {},
                'risk_distribution': {},
                'market_alignment': {},
                'closing_recommendations': [],
                'priority_actions': [],
                'confidence': 0.7,
                'timestamp': time.time()
            }
            
            # วิเคราะห์ไม้แต่ละตัว
            position_analyses = []
            for position in self.positions:
                try:
                    analysis = self.analyze_individual_position(position)
                    if analysis and 'error' not in analysis:
                        position_analyses.append(analysis)
                except Exception as e:
                    self.log(f"Error analyzing position {getattr(position, 'ticket', 'unknown')}: {str(e)}", "WARNING")
            
            if not position_analyses:
                return {'error': 'No valid position analyses'}
            
            # จัดหมวดหมู่ไม้
            categories = {}
            risk_levels = {}
            market_alignments = {}
            
            for analysis in position_analyses:
                # Category distribution
                category = analysis.get('category', 'UNKNOWN')
                if category not in categories:
                    categories[category] = []
                categories[category].append(analysis)
                
                # Risk level distribution
                risk_level = analysis.get('risk_level', 'MEDIUM')
                if risk_level not in risk_levels:
                    risk_levels[risk_level] = []
                risk_levels[risk_level].append(analysis)
                
                # Market alignment
                future_outlook = analysis.get('future_outlook', 'NEUTRAL')
                if future_outlook not in market_alignments:
                    market_alignments[future_outlook] = []
                market_alignments[future_outlook].append(analysis)
            
            portfolio_analysis['position_categories'] = categories
            portfolio_analysis['risk_distribution'] = risk_levels
            portfolio_analysis['market_alignment'] = market_alignments
            
            # สร้าง closing recommendations
            recommendations = []
            priority_actions = []
            
            # 1. TROUBLEMAKERS - ต้องจัดการก่อน
            if 'TROUBLEMAKER' in categories:
                trouble_positions = categories['TROUBLEMAKER']
                recommendations.append(f"🚨 {len(trouble_positions)} TROUBLEMAKER positions need immediate attention")
                
                for pos in trouble_positions:
                    priority_actions.append({
                        'action': 'CLOSE',
                        'position': pos,
                        'priority': 'HIGH',
                        'reason': f"High risk ({pos.get('risk_level', 'UNKNOWN')}) with low quality ({pos.get('quality_score', 0):.1f})"
                    })
            
            # 2. RECOVERABLE - อาจฟื้นตัวได้
            if 'RECOVERABLE' in categories:
                recoverable_positions = categories['RECOVERABLE']
                recommendations.append(f"🔄 {len(recoverable_positions)} RECOVERABLE positions - monitor for recovery")
                
                for pos in recoverable_positions:
                    if pos.get('recovery_potential', 0) >= 60:
                        priority_actions.append({
                            'action': 'WAIT',
                            'position': pos,
                            'priority': 'MEDIUM',
                            'reason': f"High recovery potential ({pos.get('recovery_potential', 0):.1f})"
                        })
                    else:
                        priority_actions.append({
                            'action': 'CONSIDER_CLOSE',
                            'position': pos,
                            'priority': 'MEDIUM',
                            'reason': f"Low recovery potential ({pos.get('recovery_potential', 0):.1f})"
                        })
            
            # 3. KEEPERS - เก็บไว้
            if 'KEEPER' in categories:
                keeper_positions = categories['KEEPER']
                recommendations.append(f"✅ {len(keeper_positions)} KEEPER positions - maintain these")
            
            # 4. SUPPORT - ช่วย balance portfolio
            if 'SUPPORT' in categories:
                support_positions = categories['SUPPORT']
                recommendations.append(f"🛡️ {len(support_positions)} SUPPORT positions - help balance portfolio")
            
            # 5. Market alignment analysis
            if 'BEARISH' in market_alignments and 'BULLISH' in market_alignments:
                bearish_count = len(market_alignments['BEARISH'])
                bullish_count = len(market_alignments['BULLISH'])
                recommendations.append(f"📊 Market alignment: {bearish_count} bearish vs {bullish_count} bullish positions")
            
            portfolio_analysis['closing_recommendations'] = recommendations
            portfolio_analysis['priority_actions'] = priority_actions
            
            # คำนวณ confidence
            if position_analyses:
                avg_confidence = sum(pos.get('confidence', 0.7) for pos in position_analyses) / len(position_analyses)
                portfolio_analysis['confidence'] = min(0.95, max(0.3, avg_confidence))
            
            return portfolio_analysis
            
        except Exception as e:
            self.log(f"Error in portfolio position analysis: {str(e)}", "ERROR")
            return {'error': str(e)}

    def find_smart_closing_pairs(self) -> list:
        """🔗 Smart Closing Pairs: หาคู่ไม้ที่เหมาะสมสำหรับการปิด"""
        try:
            if not self.positions:
                return []
            
            # วิเคราะห์ portfolio
            portfolio_analysis = self.analyze_portfolio_positions()
            if 'error' in portfolio_analysis:
                return []
            
            # หาไม้ที่ควรปิด
            positions_to_close = []
            profitable_positions = []
            
            for action in portfolio_analysis.get('priority_actions', []):
                if action['action'] in ['CLOSE', 'CONSIDER_CLOSE']:
                    positions_to_close.append(action['position'])
                elif action['action'] == 'WAIT':
                    # ไม้ที่รอฟื้นตัว
                    pass
            
            # หาไม้กำไร
            for position in self.positions:
                if hasattr(position, 'profit') and position.profit > 0:
                    profitable_positions.append(position)
            
            if not positions_to_close or not profitable_positions:
                return []
            
            # สร้าง smart pairs
            smart_pairs = []
            
            for loss_pos in positions_to_close:
                best_pair = None
                best_score = -1
                
                for profit_pos in profitable_positions:
                    # คำนวณ pair score
                    pair_score = self._calculate_pair_score(loss_pos, profit_pos)
                    
                    if pair_score > best_score:
                        best_score = pair_score
                        best_pair = profit_pos
                
                if best_pair and best_score > 0:
                    smart_pairs.append({
                        'loss_position': loss_pos,
                        'profit_position': best_pair,
                        'pair_score': best_score,
                        'net_impact': self._calculate_net_impact(loss_pos, best_pair),
                        'recommendation': self._generate_pair_recommendation(loss_pos, best_pair)
                    })
            
            # เรียงตาม pair score
            smart_pairs.sort(key=lambda x: x['pair_score'], reverse=True)
            
            return smart_pairs
            
        except Exception as e:
            self.log(f"Error finding smart closing pairs: {str(e)}", "ERROR")
            return []

    def _calculate_pair_score(self, loss_pos: 'Position', profit_pos: 'Position') -> float:
        """🧮 คำนวณ pair score สำหรับการปิดไม้"""
        try:
            score = 0.0
            
            # 1. Risk reduction score (40%)
            loss_analysis = self.analyze_individual_position(loss_pos)
            risk_reduction = 0.0
            
            if loss_analysis.get('risk_level') == 'HIGH':
                risk_reduction = 100  # ลด risk สูงสุด
            elif loss_analysis.get('risk_level') == 'MEDIUM':
                risk_reduction = 70   # ลด risk ปานกลาง
            else:
                risk_reduction = 40   # ลด risk น้อย
            
            score += risk_reduction * 0.4
            
            # 2. Portfolio balance score (30%)
            balance_score = 0.0
            try:
                if hasattr(self, 'buy_volume') and hasattr(self, 'sell_volume'):
                    total_volume = self.buy_volume + self.sell_volume
                    if total_volume > 0:
                        if loss_pos.type == 'BUY' and profit_pos.type == 'SELL':
                            # ปิด BUY + SELL = ลด BUY exposure
                            buy_ratio = self.buy_volume / total_volume
                            if buy_ratio > 0.6:  # BUY heavy
                                balance_score = 100
                            elif buy_ratio > 0.5:
                                balance_score = 70
                            else:
                                balance_score = 40
                        elif loss_pos.type == 'SELL' and profit_pos.type == 'BUY':
                            # ปิด SELL + BUY = ลด SELL exposure
                            sell_ratio = self.sell_volume / total_volume
                            if sell_ratio > 0.6:  # SELL heavy
                                balance_score = 100
                            elif sell_ratio > 0.5:
                                balance_score = 70
                            else:
                                balance_score = 40
            except:
                balance_score = 50  # Default
            
            score += balance_score * 0.3
            
            # 3. Market trend alignment score (20%)
            trend_score = 0.0
            try:
                market_analysis = self.analyze_market_intelligence()
                if market_analysis and market_analysis.get('momentum_trend'):
                    if (loss_pos.type == 'BUY' and market_analysis['momentum_trend'] == 'BEARISH') or \
                       (loss_pos.type == 'SELL' and market_analysis['momentum_trend'] == 'BULLISH'):
                        trend_score = 100  # ปิดไม้ที่เสียหายจาก market trend
                    else:
                        trend_score = 50   # Market trend ไม่เอื้ออำนวย
            except:
                trend_score = 50  # Default
            
            score += trend_score * 0.2
            
            # 4. Volume optimization score (10%)
            volume_score = 0.0
            try:
                if hasattr(loss_pos, 'volume') and hasattr(profit_pos, 'volume'):
                    volume_ratio = loss_pos.volume / profit_pos.volume
                    if 0.5 <= volume_ratio <= 2.0:
                        volume_score = 100  # Volume ratio ที่เหมาะสม
                    elif 0.25 <= volume_ratio <= 4.0:
                        volume_score = 70   # Volume ratio ที่ยอมรับได้
                    else:
                        volume_score = 40   # Volume ratio ที่ไม่เหมาะสม
            except:
                volume_score = 50  # Default
            
            score += volume_score * 0.1
            
            return max(0, min(100, score))
            
        except Exception as e:
            self.log(f"Error calculating pair score: {str(e)}", "WARNING")
            return 0.0

    def _calculate_net_impact(self, loss_pos: 'Position', profit_pos: 'Position') -> dict:
        """📊 คำนวณผลกระทบสุทธิของการปิดคู่ไม้"""
        try:
            loss_amount = abs(loss_pos.profit) if hasattr(loss_pos, 'profit') and loss_pos.profit < 0 else 0
            profit_amount = profit_pos.profit if hasattr(profit_pos, 'profit') and profit_pos.profit > 0 else 0
            
            net_loss = loss_amount - profit_amount
            net_impact = {
                'loss_reduction': loss_amount,
                'profit_capture': profit_amount,
                'net_result': net_loss,
                'portfolio_improvement': net_loss < 0,  # True if portfolio improves
                'risk_reduction': True if loss_amount > profit_amount else False
            }
            
            return net_impact
            
        except Exception as e:
            self.log(f"Error calculating net impact: {str(e)}", "WARNING")
            return {
                'loss_reduction': 0,
                'profit_capture': 0,
                'net_result': 0,
                'portfolio_improvement': False,
                'risk_reduction': False
            }

    def _generate_pair_recommendation(self, loss_pos: 'Position', profit_pos: 'Position') -> str:
        """💡 สร้างคำแนะนำสำหรับคู่ไม้"""
        try:
            loss_analysis = self.analyze_individual_position(loss_pos)
            profit_analysis = self.analyze_individual_position(profit_pos)
            
            recommendation = f"Close {loss_pos.type} #{loss_pos.ticket} ({loss_analysis.get('category', 'UNKNOWN')}) "
            recommendation += f"+ {profit_pos.type} #{profit_pos.ticket} ({profit_analysis.get('category', 'UNKNOWN')})"
            
            if loss_analysis.get('risk_level') == 'HIGH':
                recommendation += " - High risk reduction"
            elif loss_analysis.get('recovery_potential', 0) < 40:
                recommendation += " - Low recovery potential"
            
            return recommendation
            
        except Exception as e:
            self.log(f"Error generating pair recommendation: {str(e)}", "WARNING")
            return "Close position pair"

    # 🚨 DEPRECATED: ระบบเดิมถูกแทนที่ด้วย Smart Flexible Closing System
    # def execute_market_aware_closing(self) -> dict:
    #     """🚀 Market-Aware Closing: ปิดไม้ตาม market condition และ portfolio health"""
    #     # ระบบนี้ถูกแทนที่ด้วย execute_smart_flexible_closing() แล้ว
    #     self.log("⚠️ DEPRECATED: execute_market_aware_closing() is deprecated. Use execute_smart_flexible_closing() instead.", "WARNING")
    #     return self.execute_smart_flexible_closing()

    def integrate_market_intelligence_with_trading(self, signal: 'Signal') -> dict:
        """🔗 Integrate Market Intelligence กับ Trading Decisions"""
        try:
            if not self.market_intelligence_enabled:
                return {'integration': False, 'reason': 'Market intelligence disabled'}
            
            # วิเคราะห์ market intelligence
            try:
                market_analysis = self.analyze_market_intelligence()
            except Exception as e:
                self.log(f"Warning: Market intelligence analysis failed: {str(e)}", "WARNING")
                market_analysis = {'enabled': False}
            
            try:
                portfolio_optimization = self.optimize_portfolio_performance()
            except Exception as e:
                self.log(f"Warning: Portfolio optimization failed: {str(e)}", "WARNING")
                portfolio_optimization = {'enabled': False}
            
            integration_result = {
                'signal_enhanced': False,
                'risk_adjusted': False,
                'threshold_modified': False,
                'recommendations': [],
                'final_confidence': signal.confidence if hasattr(signal, 'confidence') else 0.7
            }
            
            # 1. 🎯 Signal Enhancement
            if market_analysis and market_analysis.get('reversal_detected'):
                if market_analysis.get('reversal_type') == 'BEARISH' and hasattr(signal, 'direction') and signal.direction == 'BUY':
                    # สัญญาณ BUY แต่ตลาดมี bearish reversal
                    integration_result['signal_enhanced'] = True
                    if 'recommendations' not in integration_result:
                        integration_result['recommendations'] = []
                    integration_result['recommendations'].append("BEARISH reversal detected - consider reducing BUY signal strength")
                    integration_result['final_confidence'] *= 0.8  # ลดความเชื่อมั่น 20%
                    
                elif market_analysis.get('reversal_type') == 'BULLISH' and hasattr(signal, 'direction') and signal.direction == 'SELL':
                    # สัญญาณ SELL แต่ตลาดมี bullish reversal
                    integration_result['signal_enhanced'] = True
                    if 'recommendations' not in integration_result:
                        integration_result['recommendations'] = []
                    integration_result['recommendations'].append("BULLISH reversal detected - consider reducing SELL signal strength")
                    integration_result['final_confidence'] *= 0.8  # ลดความเชื่อมั่น 20%
            
            # 2. 🎯 Risk Adjustment
            if portfolio_optimization and portfolio_optimization.get('risk_adjustment'):
                integration_result['risk_adjustment'] = True
                if 'recommendations' not in integration_result:
                    integration_result['recommendations'] = []
                integration_result['recommendations'].append("Portfolio risk parameters adjusted based on health")
                
                # ปรับ lot size ตาม risk
                if hasattr(self, 'portfolio_health') and self.portfolio_health < 50:
                    integration_result['recommendations'].append("Low portfolio health - consider reducing position size")
                    integration_result['final_confidence'] *= 0.9  # ลดความเชื่อมั่น 10%
            
            # 3. 🎯 Threshold Modification
            if market_analysis and market_analysis.get('threshold_adjustment'):
                integration_result['threshold_modified'] = True
                adjustment_factor = market_analysis.get('threshold_adjustment', 1.0)
                if 'recommendations' not in integration_result:
                    integration_result['recommendations'] = []
                integration_result['recommendations'].append(f"Thresholds adjusted by factor: {adjustment_factor}")
                
                # ปรับ profit targets ตาม market condition
                if adjustment_factor < 1.0:
                    integration_result['recommendations'].append("Market volatility detected - profit targets reduced")
                elif adjustment_factor > 1.0:
                    integration_result['recommendations'].append("Market stability detected - profit targets increased")
            
            # 4. 🎯 Session-Based Optimization
            if market_analysis and market_analysis.get('session_factor'):
                session_factor = market_analysis.get('session_factor', 1.0)
                if session_factor != 1.0:
                    if 'recommendations' not in integration_result:
                        integration_result['recommendations'] = []
                    integration_result['recommendations'].append(f"Session-based adjustment: {session_factor:.1f}x")
                    
                    if session_factor > 1.0:
                        integration_result['final_confidence'] *= 1.05  # เพิ่มความเชื่อมั่น 5%
                    else:
                        integration_result['final_confidence'] *= 0.95  # ลดความเชื่อมั่น 5%
            
            # จำกัด final confidence
            try:
                integration_result['final_confidence'] = min(0.95, max(0.3, integration_result['final_confidence']))
            except Exception as e:
                self.log(f"Warning: Error adjusting final confidence: {str(e)}", "WARNING")
                integration_result['final_confidence'] = 0.7  # Default confidence
            
            # Log integration results
            try:
                # ตรวจสอบว่ามี key ที่ต้องการหรือไม่
                signal_enhanced = integration_result.get('signal_enhanced', False)
                risk_adjustment = integration_result.get('risk_adjustment', False)
                
                if signal_enhanced or risk_adjustment:
                    self.log(f"🔗 Market Intelligence Integration: Signal enhanced with {len(integration_result.get('recommendations', []))} adjustments", "INFO")
                    for rec in integration_result.get('recommendations', []):
                        self.log(f"💡 {rec}", "INFO")
                    self.log(f"📊 Final Confidence: {integration_result.get('final_confidence', 0.7):.2f}", "INFO")
            except Exception as log_error:
                self.log(f"Warning: Error logging integration results: {str(log_error)}", "WARNING")
            
            return integration_result
            
        except Exception as e:
            self.log(f"Error in market intelligence integration: {str(e)}", "ERROR")
            return {
                'integration': False, 
                'error': str(e),
                'signal_enhanced': False,
                'risk_adjustment': False,
                'threshold_modified': False,
                'recommendations': [],
                'final_confidence': 0.7
            }

    def _get_margin_recommendation(self, risk_level: str, score: float) -> str:
        """📋 แนะนำการดำเนินการตาม margin risk"""
        if risk_level == "EMERGENCY":
            return f"URGENT: Close positions immediately! (Score: {score:.1f}/100)"
        elif risk_level == "DANGER":
            return f"HIGH PRIORITY: Reduce positions soon (Score: {score:.1f}/100)"
        elif risk_level == "CAUTION":
            return f"MONITOR: Watch margin carefully (Score: {score:.1f}/100)"
        else:
            return f"SAFE: Normal operations (Score: {score:.1f}/100)"

    def calculate_dynamic_profit_target(self, positions_basket: List[Position]) -> dict:
        """🎯 คำนวณเป้าหมายกำไรแบบ dynamic ตาม lot และ margin risk"""
        try:
            if not self.dynamic_profit_targets or not positions_basket:
                return {"target_amount": 50.0, "target_percent": 1.0, "confidence": 0.5}
            
            # 1. 📊 คำนวณ total lots และ average price
            total_lots = sum(pos.volume for pos in positions_basket)
            if total_lots <= 0:
                return {"target_amount": 50.0, "target_percent": 1.0, "confidence": 0.5}
            
            # คำนวณ weighted average price
            total_value = sum(pos.open_price * pos.volume for pos in positions_basket)
            avg_price = total_value / total_lots
            
            # 2. 🤖 ประเมิน margin risk
            margin_assessment = self.ai_assess_margin_risk()
            risk_level = margin_assessment['risk_level']
            risk_score = margin_assessment['risk_score']
            
            # 3. 🎯 เลือก profit target rate ตาม risk level
            if risk_level == "EMERGENCY":
                target_rate = self.profit_target_emergency  # 0.1%
                urgency_multiplier = 0.5  # ลดเป้าหมายลง 50%
                confidence = 0.95
            elif risk_level == "DANGER":
                target_rate = self.profit_target_danger      # 0.3%
                urgency_multiplier = 0.7  # ลดเป้าหมายลง 30%
                confidence = 0.85
            elif risk_level == "CAUTION":
                target_rate = self.profit_target_caution     # 0.5%
                urgency_multiplier = 0.9  # ลดเป้าหมายลง 10%
                confidence = 0.75
            else:  # SAFE
                target_rate = self.profit_target_safe        # 1.0%
                urgency_multiplier = 1.0  # เป้าหมายเต็ม
                confidence = 0.65
            
            # 4. 💰 คำนวณ target amount
            base_target = avg_price * total_lots * target_rate * 100  # Convert to dollar amount
            final_target = base_target * urgency_multiplier
            
            # 5. 📊 ปรับแต่งตามสถานการณ์พิเศษ
            adjustments = []
            
            # มีไม้ขาดทุนเยอะ → ลด target
            losing_positions = [p for p in positions_basket if p.profit < 0]
            if len(losing_positions) >= len(positions_basket) * 0.7:  # 70% ขาดทุน
                final_target *= 0.8
                adjustments.append("High loss ratio: -20%")
            
            # Portfolio health แย่ → ลด target
            if self.portfolio_health < 40:
                final_target *= 0.7
                adjustments.append("Poor portfolio health: -30%")
            
            # จำนวนไม้เยอะมาก → ลด target เพื่อลดไม้
            if len(positions_basket) >= 5:
                final_target *= 0.85
                adjustments.append("Large basket size: -15%")
            
            # 6. 🎯 คำนวณ profit percentage
            current_total_profit = sum(pos.profit for pos in positions_basket)
            target_percent = (final_target / (avg_price * total_lots * 100)) * 100 if avg_price > 0 else 1.0
            
            # 7. 📋 สร้างผลลัพธ์
            result = {
                'target_amount': max(1.0, final_target),  # อย่างน้อย $1
                'target_percent': max(0.05, target_percent),  # อย่างน้อย 0.05%
                'current_profit': current_total_profit,
                'total_lots': total_lots,
                'avg_price': avg_price,
                'risk_level': risk_level,
                'risk_score': risk_score,
                'urgency_multiplier': urgency_multiplier,
                'adjustments': adjustments,
                'confidence': confidence,
                'meets_target': current_total_profit >= final_target,
                'reasoning': self._get_profit_target_reasoning(risk_level, final_target, current_total_profit)
            }
            
            return result
            
        except Exception as e:
            self.log(f"Error calculating dynamic profit target: {str(e)}", "ERROR")
            return {"target_amount": 50.0, "target_percent": 1.0, "confidence": 0.5}

    def _get_profit_target_reasoning(self, risk_level: str, target: float, current: float) -> str:
        """💭 อธิบายเหตุผลการตั้งเป้าหมาย"""
        status = "✅ MEETS TARGET" if current >= target else "❌ BELOW TARGET"
        gap = current - target
        
        if risk_level == "EMERGENCY":
            return f"🚨 EMERGENCY: Accept any profit! Target: ${target:.2f}, Current: ${current:.2f} ({status})"
        elif risk_level == "DANGER":
            return f"⚠️ DANGER: Low target for quick margin relief. Gap: ${gap:.2f} ({status})"
        elif risk_level == "CAUTION":
            return f"📊 CAUTION: Moderate target with safety margin. Gap: ${gap:.2f} ({status})"
        else:
            return f"✅ SAFE: Normal profit target maintained. Gap: ${gap:.2f} ({status})"

    def adaptive_threshold_adjustment(self) -> dict:
        """🎯 Adaptive Threshold Adjustment: ปรับ profit targets ตาม market condition แบบ real-time"""
        try:
            current_time = time.time()
            adjustment_result = {
                'timestamp': current_time,
                'adjustments_made': False,
                'profit_targets_modified': False,
                'confidence_thresholds_modified': False,
                'recommendations': [],
                'confidence': 0.7
            }
            
            # 1. 📊 Market Condition Analysis
            market_analysis = self.analyze_market_intelligence()
            market_condition = market_analysis.get('market_condition', 'NORMAL')
            volatility_level = market_analysis.get('volatility_level', 'MEDIUM')
            
            # 2. 🎯 Profit Target Adjustment
            original_targets = {
                'emergency': self.profit_target_emergency,
                'danger': self.profit_target_danger,
                'caution': self.profit_target_caution,
                'safe': self.profit_target_safe
            }
            
            adjustment_factor = 1.0
            
            if market_condition == 'VOLATILE':
                # ตลาดผันผวน - ลด profit targets
                adjustment_factor = 0.7
                adjustment_result['recommendations'].append("High volatility - reducing profit targets by 30%")
                
            elif market_condition == 'REVERSAL':
                # ตลาดกลับตัว - ลด profit targets
                adjustment_factor = 0.8
                adjustment_result['recommendations'].append("Market reversal - reducing profit targets by 20%")
                
            elif market_condition == 'TRENDING':
                # ตลาดมี trend - เพิ่ม profit targets
                adjustment_factor = 1.2
                adjustment_result['recommendations'].append("Strong trend - increasing profit targets by 20%")
                
            elif market_condition == 'SIDEWAYS':
                # ตลาด sideways - ลด profit targets เล็กน้อย
                adjustment_factor = 0.9
                adjustment_result['recommendations'].append("Sideways market - reducing profit targets by 10%")
                
            else:  # NORMAL
                adjustment_factor = 1.0
                adjustment_result['recommendations'].append("Normal market - maintaining standard profit targets")
            
            # 3. 🎯 ปรับ profit targets
            if adjustment_factor != 1.0:
                self.profit_target_emergency = max(0.0005, self.profit_target_emergency * adjustment_factor)
                self.profit_target_danger = max(0.001, self.profit_target_danger * adjustment_factor)
                self.profit_target_caution = max(0.002, self.profit_target_caution * adjustment_factor)
                self.profit_target_safe = max(0.003, self.profit_target_safe * adjustment_factor)
                
                adjustment_result['profit_targets_modified'] = True
                adjustment_result['adjustments_made'] = True
                
                self.log(f"🎯 Adaptive Threshold Adjustment: Profit targets adjusted by factor {adjustment_factor:.2f}", "INFO")
            
            # 4. 🎯 Confidence Threshold Adjustment
            if market_condition in ['VOLATILE', 'REVERSAL']:
                # ตลาดไม่แน่นอน - ลด confidence threshold
                new_confidence = max(0.3, self.ai_confidence_threshold * 0.8)
                if new_confidence != self.ai_confidence_threshold:
                    self.ai_confidence_threshold = new_confidence
                    adjustment_result['confidence_thresholds_modified'] = True
                    adjustment_result['adjustments_made'] = True
                    adjustment_result['recommendations'].append(f"Reduced AI confidence threshold to {new_confidence:.2f}")
                    
            elif market_condition in ['TRENDING', 'NORMAL']:
                # ตลาดปกติ - เพิ่ม confidence threshold
                new_confidence = min(0.9, self.ai_confidence_threshold * 1.1)
                if new_confidence != self.ai_confidence_threshold:
                    self.ai_confidence_threshold = new_confidence
                    adjustment_result['confidence_thresholds_modified'] = True
                    adjustment_result['adjustments_made'] = True
                    adjustment_result['recommendations'].append(f"Increased AI confidence threshold to {new_confidence:.2f}")
            
            # 5. 📊 Portfolio Health Consideration
            if hasattr(self, 'portfolio_health'):
                if self.portfolio_health < 30:  # Emergency
                    # Portfolio เสี่ยง - ลด profit targets เพิ่มเติม
                    emergency_factor = 0.6
                    self.profit_target_emergency *= emergency_factor
                    self.profit_target_danger *= emergency_factor
                    adjustment_result['recommendations'].append("Emergency portfolio health - further reducing profit targets")
                    adjustment_result['adjustments_made'] = True
                    
                elif self.portfolio_health > 80:  # Safe
                    # Portfolio ปลอดภัย - เพิ่ม profit targets
                    safe_factor = 1.15
                    self.profit_target_safe *= safe_factor
                    adjustment_result['recommendations'].append("Safe portfolio health - increasing profit targets")
                    adjustment_result['adjustments_made'] = True
            
            # 6. 📝 Log และเก็บประวัติ
            if adjustment_result['adjustments_made']:
                self.log(f"🎯 Adaptive Threshold Adjustment: {len(adjustment_result['recommendations'])} adjustments applied", "INFO")
                for rec in adjustment_result['recommendations']:
                    self.log(f"💡 {rec}", "INFO")
                
                # เก็บประวัติ
                if not hasattr(self, 'threshold_adjustment_history'):
                    self.threshold_adjustment_history = []
                
                self.threshold_adjustment_history.append({
                    'timestamp': current_time,
                    'market_condition': market_condition,
                    'adjustment_factor': adjustment_factor,
                    'profit_targets_modified': adjustment_result['profit_targets_modified'],
                    'confidence_thresholds_modified': adjustment_result['confidence_thresholds_modified'],
                    'recommendations': adjustment_result['recommendations']
                })
                
                if len(self.threshold_adjustment_history) > 100:
                    self.threshold_adjustment_history.pop(0)
            
            return adjustment_result
            
        except Exception as e:
            self.log(f"Error in adaptive threshold adjustment: {str(e)}", "ERROR")
            return {'error': str(e)}

    def find_optimal_closing_baskets(self) -> List[dict]:
        """🧮 หา basket ของไม้ที่เหมาะสมที่สุดสำหรับปิด (AI-powered)"""
        try:
            if len(self.positions) < 2:
                return []
            
            profitable_positions = [p for p in self.positions if p.profit > 0]
            losing_positions = [p for p in self.positions if p.profit < 0]
            
            if not profitable_positions:
                return []  # ไม่มีไม้กำไรให้รองรับ
            
            baskets = []
            
            # 🎯 Strategy 1: Profit + Loss Combinations (Primary)
            for profit_pos in profitable_positions:
                for loss_count in range(1, min(4, len(losing_positions) + 1)):  # 1-3 ไม้ขาดทุน
                    # เรียงไม้ขาดทุนตาม loss น้อยสุดก่อน (ง่ายต่อการปิด)
                    sorted_losses = sorted(losing_positions, key=lambda x: abs(x.profit))
                    
                    for loss_combo in self._get_combinations(sorted_losses, loss_count):
                        basket_positions = [profit_pos] + list(loss_combo)
                        basket_score = self._evaluate_basket_score(basket_positions)
                        
                        if basket_score['meets_criteria']:
                            baskets.append(basket_score)
            
            # 🎯 Strategy 2: Multiple Profits + Multiple Losses
            if len(profitable_positions) >= 2:
                for profit_count in range(2, min(4, len(profitable_positions) + 1)):
                    for profit_combo in self._get_combinations(profitable_positions, profit_count):
                        for loss_count in range(1, min(3, len(losing_positions) + 1)):
                            for loss_combo in self._get_combinations(losing_positions, loss_count):
                                basket_positions = list(profit_combo) + list(loss_combo)
                                if len(basket_positions) <= 6:  # จำกัดขนาด basket
                                    basket_score = self._evaluate_basket_score(basket_positions)
                                    
                                    if basket_score['meets_criteria']:
                                        baskets.append(basket_score)
            
            # 🎯 Strategy 3: Emergency Mode - Pure Profit Baskets
            margin_risk = self.ai_assess_margin_risk()
            if margin_risk['risk_level'] in ['EMERGENCY', 'DANGER']:
                for profit_count in range(2, min(5, len(profitable_positions) + 1)):
                    for profit_combo in self._get_combinations(profitable_positions, profit_count):
                        basket_positions = list(profit_combo)
                        basket_score = self._evaluate_basket_score(basket_positions)
                        
                        # ใน emergency mode ยอมรับ profit น้อยกว่า
                        if basket_score['total_profit'] > 0:
                            basket_score['meets_criteria'] = True
                            basket_score['strategy'] = "EMERGENCY_PROFIT_ONLY"
                            baskets.append(basket_score)
            
            # 🎯 Strategy 4: SAFE Mode - Smart Profit Baskets (NEW!)
            if margin_risk['risk_level'] == "SAFE" and len(profitable_positions) >= 2:
                # สร้าง baskets แม้ใน SAFE mode เพื่อเพิ่มประสิทธิภาพ
                for profit_count in range(2, min(4, len(profitable_positions) + 1)):
                    for profit_combo in self._get_combinations(profitable_positions, profit_count):
                        basket_positions = list(profit_combo)
                        basket_score = self._evaluate_basket_score(basket_positions)
                        
                        # ใน SAFE mode ใช้ profit target ปกติ
                        if basket_score['total_profit'] > 5:  # ลดลงเหลือ $5 profit (ง่ายขึ้นมาก!)
                            basket_score['meets_criteria'] = True
                            basket_score['strategy'] = "SAFE_PROFIT_BASKET"
                            baskets.append(basket_score)
            
            # 🎯 Strategy 5: Micro Profit Baskets (NEW!)
            if len(profitable_positions) >= 3:  # ต้องมีไม้กำไรอย่างน้อย 3 ตัว
                # สร้าง baskets จากไม้กำไรน้อยๆ เพื่อลดจำนวนไม้
                for profit_count in range(3, min(6, len(profitable_positions) + 1)):
                    for profit_combo in self._get_combinations(profitable_positions, profit_count):
                        basket_positions = list(profit_combo)
                        total_profit = sum(pos.profit for pos in basket_positions)
                        
                        # ยอมรับ profit รวมน้อยๆ เพื่อลดจำนวนไม้
                        if total_profit > 2:  # อย่างน้อย $2 profit รวม
                            basket_score = {
                                'positions': basket_positions,
                                'total_profit': total_profit,
                                'total_lots': sum(pos.volume for pos in basket_positions),
                                'meets_criteria': True,
                                'final_score': 60 + (total_profit * 2),  # คะแนนตาม profit
                                'strategy': "MICRO_PROFIT_BASKET",
                                'confidence': 0.6
                            }
                            baskets.append(basket_score)
            
            # 📊 เรียงลำดับตามคะแนน
            baskets.sort(key=lambda x: x['final_score'], reverse=True)
            
            # 🏆 คืนค่า top 5 baskets
            return baskets[:5]
            
        except Exception as e:
            self.log(f"Error finding optimal closing baskets: {str(e)}", "ERROR")
            return []

    def _get_combinations(self, items: List, r: int):
        """🔄 สร้าง combinations (helper function)"""
        from itertools import combinations
        return combinations(items, r)

    def _evaluate_basket_score(self, positions: List[Position]) -> dict:
        """🎯 ประเมินคะแนน basket"""
        try:
            total_profit = sum(pos.profit for pos in positions)
            total_lots = sum(pos.volume for pos in positions)
            
            # คำนวณ dynamic target
            target_analysis = self.calculate_dynamic_profit_target(positions)
            meets_target = target_analysis['meets_target']
            
            # 📊 คำนวณคะแนนต่างๆ
            scores = {}
            
            # 1. Profit Score (40% - สำคัญสุด!)
            if total_profit > 0:
                profit_ratio = total_profit / target_analysis['target_amount']
                scores['profit'] = min(100, max(0, profit_ratio * 100))
            else:
                scores['profit'] = 0
            
            # 2. Margin Relief Score (30%)
            margin_relief = self._calculate_margin_relief(positions)
            scores['margin'] = margin_relief
            
            # 3. Balance Impact Score (20%)
            balance_impact = self._calculate_balance_impact(positions)
            scores['balance'] = balance_impact
            
            # 4. Risk Reduction Score (10%)
            risk_reduction = self._calculate_risk_reduction(positions)
            scores['risk'] = risk_reduction
            
            # 🎯 คำนวณคะแนนรวม
            final_score = (
                scores['profit'] * self.margin_priority_weight +      # 40%
                scores['margin'] * self.profit_priority_weight +     # 25%  
                scores['balance'] * self.balance_priority_weight +   # 20%
                scores['risk'] * self.risk_priority_weight           # 15%
            )
            
            # 📋 สร้างผลลัพธ์
            result = {
                'positions': positions,
                'total_profit': total_profit,
                'total_lots': total_lots,
                'target_analysis': target_analysis,
                'meets_target': meets_target,
                'meets_criteria': meets_target and total_profit > 0,
                'scores': scores,
                'final_score': final_score,
                'confidence': target_analysis['confidence'],
                'strategy': 'MIXED_BASKET',
                'recommendation': self._get_basket_recommendation(total_profit, meets_target, final_score)
            }
            
            return result
            
        except Exception as e:
            self.log(f"Error evaluating basket score: {str(e)}", "ERROR")
            return {'meets_criteria': False, 'final_score': 0}

    def _calculate_margin_relief(self, positions: List[Position]) -> float:
        """💰 คำนวณการประหยัด margin (0-100)"""
        try:
            # ประมาณการ margin ที่จะประหยัดได้
            total_lots = sum(pos.volume for pos in positions)
            estimated_margin_relief = total_lots * 1000  # Rough estimate per lot
            
            # สเกลเป็น 0-100
            if estimated_margin_relief >= 5000:  # $5000+ relief = excellent
                return 100
            elif estimated_margin_relief >= 2000:  # $2000+ = good
                return 70
            elif estimated_margin_relief >= 500:   # $500+ = fair
                return 40
            else:
                return 20
                
        except:
            return 30

    def _calculate_balance_impact(self, positions: List[Position]) -> float:
        """⚖️ คำนวณผลกระทบต่อ balance (0-100)"""
        try:
            buy_lots = sum(pos.volume for pos in positions if pos.type == "BUY")
            sell_lots = sum(pos.volume for pos in positions if pos.type == "SELL")
            
            # ถ้าปิดทั้ง BUY และ SELL = ดีมาก
            if buy_lots > 0 and sell_lots > 0:
                ratio_diff = abs(buy_lots - sell_lots) / (buy_lots + sell_lots)
                return 100 - (ratio_diff * 50)  # ยิ่งใกล้เคียงกัน ยิ่งดี
            else:
                return 50  # ปิดฝั่งเดียว = ปานกลาง
                
        except:
            return 50

    def _calculate_risk_reduction(self, positions: List[Position]) -> float:
        """📉 คำนวณการลดความเสี่ยง (0-100) - Enhanced with % calculation"""
        try:
            if not positions:
                return 0.0
            
            # 1. จำนวนไม้ที่จะลดได้
            position_count = len(positions)
            
            # 2. วิเคราะห์ % loss ของแต่ละไม้
            total_portfolio_value = self.get_portfolio_value()
            if total_portfolio_value <= 0:
                return 30.0
            
            risk_scores = []
            for position in positions:
                # คำนวณ % loss จาก portfolio value
                portfolio_loss_percentage = abs(position.profit) / total_portfolio_value * 100
                
                # คำนวณ % loss จาก entry price
                if position.open_price > 0:
                    price_loss_percentage = abs(position.current_price - position.open_price) / position.open_price * 100
                else:
                    price_loss_percentage = 0
                
                # คำนวณ risk score สำหรับไม้นี้
                position_risk_score = self._calculate_position_risk_score(
                    position, portfolio_loss_percentage, price_loss_percentage
                )
                risk_scores.append(position_risk_score)
            
            # 3. คำนวณ total risk reduction score
            if risk_scores:
                avg_risk_score = sum(risk_scores) / len(risk_scores)
                position_bonus = min(30, position_count * 5)  # 5 points per position, max 30
                total_score = avg_risk_score + position_bonus
                
                return min(100.0, max(0.0, total_score))
            else:
                return 30.0
            
        except Exception as e:
            self.log(f"Error calculating risk reduction: {str(e)}", "ERROR")
            return 30.0

    def _get_basket_recommendation(self, profit: float, meets_target: bool, score: float) -> str:
        """📋 แนะนำการดำเนินการ"""
        if score >= 80:
            return f"🏆 EXCELLENT: Close immediately! Profit: ${profit:.2f}, Score: {score:.1f}"
        elif score >= 60:
            return f"✅ GOOD: Recommended close. Profit: ${profit:.2f}, Score: {score:.1f}"
        elif score >= 40:
            return f"⚠️ FAIR: Consider closing. Profit: ${profit:.2f}, Score: {score:.1f}"
        else:
            return f"❌ POOR: Not recommended. Profit: ${profit:.2f}, Score: {score:.1f}"

    def execute_flexible_closes(self):
        """🤖 AI-Enhanced Flexible Closing: ปิดไม้แบบฉลาดตาม AI margin risk assessment และ Market Intelligence"""
        try:
            if not self.positions:
                return
            
            # 🤖 AI Step 1: Market Intelligence Analysis
            market_analysis = self.analyze_market_intelligence()
            market_condition = market_analysis.get('market_condition', 'NORMAL')
            reversal_detected = market_analysis.get('reversal_detected', False)
            momentum_trend = market_analysis.get('momentum_trend', 'NEUTRAL')
            
            self.log(f"🤖 Market Intelligence: {market_condition} | Reversal: {reversal_detected} | Trend: {momentum_trend}", "AI")
            
            # 🤖 AI Step 2: Margin Risk Assessment
            margin_risk = self.ai_assess_margin_risk()
            risk_level = margin_risk.get('risk_level', 'SAFE')
            confidence = margin_risk.get('confidence', 0.7)
            
            self.log(f"🤖 AI Margin Risk Assessment: {risk_level} (Score: {margin_risk.get('risk_score', 0):.1f})", "AI")
            self.log(f"💡 {margin_risk.get('recommendation', 'No recommendation')}", "AI")
            
            # 🤖 AI Step 3: Portfolio Position Analysis
            portfolio_analysis = self.analyze_portfolio_positions()
            if 'error' not in portfolio_analysis:
                total_positions = portfolio_analysis.get('total_positions', 0)
                trouble_count = len(portfolio_analysis.get('position_categories', {}).get('TROUBLEMAKER', []))
                recoverable_count = len(portfolio_analysis.get('position_categories', {}).get('RECOVERABLE', []))
                
                self.log(f"🤖 Portfolio Analysis: {total_positions} positions | {trouble_count} TROUBLEMAKERS | {recoverable_count} RECOVERABLE", "AI")
            
            # 🤖 AI Step 4: Smart Closing Strategy Selection
            closing_strategy = self._select_closing_strategy(market_condition, risk_level, portfolio_analysis)
            self.log(f"🤖 Selected Closing Strategy: {closing_strategy['name']} - {closing_strategy['description']}", "AI")
            
            # 🤖 AI Step 5: Execute Selected Strategy (ปรับปรุงให้ใช้ระบบใหม่)
            if closing_strategy['name'] == 'MARKET_AWARE_CLOSING':
                # ใช้ Smart Flexible Closing แทน (ระบบใหม่)
                self.log("🚀 Upgrading to Smart Flexible Closing System", "AI")
                self.execute_smart_flexible_closing()
                    
            elif closing_strategy['name'] == 'TRADITIONAL_BASKET_CLOSING':
                # ใช้ Smart Flexible Closing แทน (ระบบใหม่)
                self.log("🚀 Upgrading to Smart Flexible Closing System", "AI")
                self.execute_smart_flexible_closing()
                    
            elif closing_strategy['name'] == 'DEFENSIVE_CLOSING':
                # ใช้ Smart Flexible Closing แทน (ระบบใหม่)
                self.log("🚀 Upgrading to Smart Flexible Closing System", "AI")
                self.execute_smart_flexible_closing()
                    
            elif closing_strategy['name'] == 'WAIT_AND_MONITOR':
                # รอและติดตาม
                self.log("🤖 Strategy: Wait and Monitor - No immediate action needed", "AI")
            
            # 🤖 AI Step 6: Update Decision History
            self._update_ai_decision_history(closing_strategy, market_analysis, margin_risk)
                
        except Exception as e:
            self.log(f"❌ Error in AI-enhanced flexible closing: {str(e)}", "ERROR")

    def _select_closing_strategy(self, market_condition: str, risk_level: str, portfolio_analysis: dict) -> dict:
        """🎯 เลือก closing strategy ที่เหมาะสมตาม market condition และ portfolio health"""
        try:
            # ตรวจสอบ market condition
            if market_condition == 'VOLATILE':
                if risk_level in ['DANGER', 'EMERGENCY']:
                    return {
                        'name': 'DEFENSIVE_CLOSING',
                        'description': 'High volatility + High risk = Defensive closing only',
                        'priority': 'HIGH'
                    }
                else:
                    return {
                        'name': 'MARKET_AWARE_CLOSING',
                        'description': 'High volatility + Safe risk = Market-aware closing',
                        'priority': 'MEDIUM'
                    }
            
            elif market_condition == 'REVERSAL':
                if risk_level in ['DANGER', 'EMERGENCY']:
                    return {
                        'name': 'MARKET_AWARE_CLOSING',
                        'description': 'Market reversal + High risk = Market-aware closing',
                        'priority': 'HIGH'
                    }
                else:
                    return {
                        'name': 'MARKET_AWARE_CLOSING',
                        'description': 'Market reversal + Safe risk = Market-aware closing',
                        'priority': 'MEDIUM'
                    }
            
            elif market_condition == 'TRENDING':
                if risk_level in ['DANGER', 'EMERGENCY']:
                    return {
                        'name': 'TRADITIONAL_BASKET_CLOSING',
                        'description': 'Strong trend + High risk = Traditional basket closing',
                        'priority': 'HIGH'
                    }
                else:
                    return {
                        'name': 'MARKET_AWARE_CLOSING',
                        'description': 'Strong trend + Safe risk = Market-aware closing',
                        'priority': 'MEDIUM'
                    }
            
            elif market_condition == 'SIDEWAYS':
                if risk_level in ['DANGER', 'EMERGENCY']:
                    return {
                        'name': 'TRADITIONAL_BASKET_CLOSING',
                        'description': 'Sideways market + High risk = Traditional basket closing',
                        'priority': 'HIGH'
                    }
                else:
                    return {
                        'name': 'WAIT_AND_MONITOR',
                        'description': 'Sideways market + Safe risk = Wait for better opportunity',
                        'priority': 'LOW'
                    }
            
            else:  # NORMAL market condition
                if risk_level in ['DANGER', 'EMERGENCY']:
                    return {
                        'name': 'TRADITIONAL_BASKET_CLOSING',
                        'description': 'Normal market + High risk = Traditional basket closing',
                        'priority': 'HIGH'
                    }
                else:
                    return {
                        'name': 'MARKET_AWARE_CLOSING',
                        'description': 'Normal market + Safe risk = Market-aware closing',
                        'priority': 'MEDIUM'
                    }
                    
        except Exception as e:
            self.log(f"Error selecting closing strategy: {str(e)}", "WARNING")
            return {
                'name': 'TRADITIONAL_BASKET_CLOSING',
                'description': 'Fallback to traditional method',
                'priority': 'MEDIUM'
            }

    # 🚨 DEPRECATED: ระบบเดิมถูกแทนที่ด้วย Smart Flexible Closing System
    # def _execute_traditional_baskets(self, optimal_baskets: list, confidence: float, risk_level: str):
    #     """🤖 ปิดไม้แบบ traditional basket closing"""
    #     # ระบบนี้ถูกแทนที่ด้วย execute_smart_flexible_closing() แล้ว
    #     self.log("⚠️ DEPRECATED: _execute_traditional_baskets() is deprecated. Use execute_smart_flexible_closing() instead.", "WARNING")
    #     return self.execute_smart_flexible_closing()

    # 🚨 DEPRECATED: ระบบเดิมถูกแทนที่ด้วย Smart Flexible Closing System
    # def _execute_defensive_closing(self, portfolio_analysis: dict):
    #     """🛡️ ปิดไม้แบบ defensive (เฉพาะไม้ที่เสี่ยงมาก)"""
    #     # ระบบนี้ถูกแทนที่ด้วย execute_smart_flexible_closing() แล้ว
    #     self.log("⚠️ DEPRECATED: _execute_defensive_closing() is deprecated. Use execute_smart_flexible_closing() instead.", "WARNING")
    #     return self.execute_smart_flexible_closing()

    def _update_ai_decision_history(self, closing_strategy: dict, market_analysis: dict, margin_risk: dict):
        """📊 อัพเดท AI decision history"""
        try:
            self.ai_decision_history.append({
                'timestamp': time.time(),
                'action': 'strategy_selection',
                'strategy': closing_strategy['name'],
                'strategy_description': closing_strategy['description'],
                'market_condition': market_analysis.get('market_condition', 'UNKNOWN'),
                'risk_level': margin_risk.get('risk_level', 'UNKNOWN'),
                'confidence': margin_risk.get('confidence', 0.7)
            })
            
            # เก็บแค่ 100 รายการล่าสุด
            if len(self.ai_decision_history) > 100:
                self.ai_decision_history = self.ai_decision_history[-100:]
                
        except Exception as e:
            self.log(f"Warning: Error updating AI decision history: {str(e)}", "WARNING")

    def will_hurt_portfolio_balance(self, position: Position) -> bool:
        """🔄 ตรวจสอบว่าการปิด position นี้จะทำลายสมดุลพอร์ตไหม"""
        try:
            # คำนวณ volume หลังปิด position นี้
            remaining_buy_volume = self.buy_volume
            remaining_sell_volume = self.sell_volume
            
            if position.type == "BUY":
                remaining_buy_volume -= position.volume
            else:
                remaining_sell_volume -= position.volume
            
            total_remaining = remaining_buy_volume + remaining_sell_volume
            
            # ถ้าไม่มีไม้เหลือเลย ให้ปิดได้
            if total_remaining <= 0:
                return False
            
            # คำนวณ ratio หลังปิด
            remaining_buy_ratio = remaining_buy_volume / total_remaining
            
            # ตรวจสอบว่าจะทำให้ imbalance มากเกินไปไหม
            imbalance_threshold = 0.8  # 80:20 เป็นขีดจำกัด
            
            # ถ้าปิด BUY แล้วเหลือ BUY น้อยเกินไป
            if position.type == "BUY" and remaining_buy_ratio < (1 - imbalance_threshold):
                # แต่ถ้ามี BUY ที่ขาดทุนเยอะ ให้ปิด SELL ได้เพื่อสร้างสมดุล
                losing_buy_positions = [p for p in self.positions if p.type == "BUY" and p.profit < -50]
                if len(losing_buy_positions) >= 3:  # มี BUY ขาดทุนเยอะ
                    return False  # ให้ปิด SELL ได้
                return True
            
            # ถ้าปิด SELL แล้วเหลือ SELL น้อยเกินไป
            if position.type == "SELL" and remaining_buy_ratio > imbalance_threshold:
                # แต่ถ้ามี SELL ที่ขาดทุนเยอะ ให้ปิด BUY ได้เพื่อสร้างสมดุล
                losing_sell_positions = [p for p in self.positions if p.type == "SELL" and p.profit < -50]
                if len(losing_sell_positions) >= 3:  # มี SELL ขาดทุนเยอะ
                    return False  # ให้ปิด BUY ได้
                return True
                
            return False  # ปิดได้ปกติ
            
        except Exception as e:
            self.log(f"Error checking portfolio balance impact: {str(e)}", "ERROR")
            return False  # ถ้า error ให้ปิดได้

    def close_position_smart(self, position: Position, reason: str) -> bool:
        """ปิด position อย่างชาญฉลาด - Enhanced with Order Closing Check"""
        try:
            # 🆕 Enhanced Order Closing Conditions Check
            order_closing_check = self.check_order_closing_conditions(position)
            if not order_closing_check['can_close']:
                self.log(f"❌ Order Closing Conditions Not Met: {order_closing_check['reason']}", "WARNING")
                return False
            
            close_type = mt5.ORDER_TYPE_SELL if position.type == "BUY" else mt5.ORDER_TYPE_BUY
            
            # Ensure we have a valid filling type
            if self.filling_type is None:
                self.filling_type = self.detect_broker_filling_type()
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": position.volume,
                "type": close_type,
                "position": position.ticket,
                "deviation": 20,
                "magic": 123456,
                "comment": f"Smart_{reason[:12]}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self.filling_type,
            }
            
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                self.log(f"✅ Smart close: {position.ticket} - {reason}")
                self.log(f"   Profit: ${position.profit:.2f} (${position.profit_per_lot:.2f}/lot)")
                return True
            elif result.retcode == mt5.TRADE_RETCODE_INVALID_FILL:
                # Try with different filling types
                for filling_type in self.filling_types_priority:
                    if filling_type != self.filling_type:
                        request["type_filling"] = filling_type
                        result = mt5.order_send(request)
                        if result.retcode == mt5.TRADE_RETCODE_DONE:
                            self.log(f"✅ Smart close successful with {filling_type}")
                            return True
                            
                self.log(f"❌ Smart close failed with all filling types", "ERROR")
                return False
            else:
                self.log(f"❌ Smart close failed: {result.retcode}", "WARNING")
                return False
                
        except Exception as e:
            self.log(f"Error in smart close: {str(e)}", "ERROR")
            return False

    def cleanup_closed_positions(self):
        """ทำความสะอาด tracker with enhanced memory management"""
        try:
            active_tickets = {pos.ticket for pos in self.positions}
            
            # Convert all tracker keys to consistent format for comparison
            normalized_tracker = {}
            closed_tickets = []
            
            for ticket in list(self.position_tracker.keys()):
                try:
                    # Convert ticket to int for comparison
                    ticket_int = int(ticket)
                    if ticket_int not in active_tickets:
                        closed_tickets.append(ticket)
                    else:
                        normalized_tracker[ticket_int] = self.position_tracker[ticket]
                except (ValueError, TypeError):
                    # Remove invalid ticket entries
                    closed_tickets.append(ticket)
                    self.log(f"Removing invalid tracker ticket: {ticket}", "WARNING")
            
            # Remove closed position trackers
            for ticket in closed_tickets:
                try:
                    del self.position_tracker[ticket]
                except KeyError:
                    pass  # Already removed
            
            # Update tracker with normalized keys
            if len(normalized_tracker) != len(self.position_tracker):
                self.position_tracker = normalized_tracker
                
            if closed_tickets:
                self.log(f"🧹 Cleaned up {len(closed_tickets)} closed position trackers")
                
            # Additional memory cleanup
            self._cleanup_memory_intensive_data()
                
        except Exception as e:
            self.log(f"Error cleaning up: {str(e)}", "ERROR")
    
    def _cleanup_memory_intensive_data(self):
        """Clean up memory-intensive data structures"""
        try:
            # Limit hourly signals to prevent memory bloat
            max_hourly_signals = 1000
            if len(self.hourly_signals) > max_hourly_signals:
                # Keep only the most recent signals
                self.hourly_signals = self.hourly_signals[-max_hourly_signals:]
                self.log(f"🧹 Trimmed hourly signals to {max_hourly_signals} entries")
            
            # Clean up old hedge analytics
            if hasattr(self, 'hedge_analytics') and isinstance(self.hedge_analytics, dict):
                # Keep only recent hedge analytics (last 24 hours)
                current_time = datetime.now()
                old_keys = []
                
                for key, analytics in self.hedge_analytics.items():
                    if isinstance(analytics, dict) and 'timestamp' in analytics:
                        try:
                            analytics_time = datetime.fromisoformat(analytics['timestamp'])
                            if (current_time - analytics_time).days > 1:
                                old_keys.append(key)
                        except:
                            old_keys.append(key)  # Remove invalid entries
                
                for key in old_keys:
                    del self.hedge_analytics[key]
                
                if old_keys:
                    self.log(f"🧹 Cleaned up {len(old_keys)} old hedge analytics")
            
            # Clean up position tracker of very old entries
            if hasattr(self, 'position_tracker'):
                current_time = datetime.now()
                old_trackers = []
                
                for ticket, tracker in self.position_tracker.items():
                    if isinstance(tracker, dict) and 'birth_time' in tracker:
                        try:
                            birth_time = tracker['birth_time']
                            if isinstance(birth_time, str):
                                birth_time = datetime.fromisoformat(birth_time)
                            
                            # Remove trackers older than 7 days
                            if (current_time - birth_time).days > 7:
                                old_trackers.append(ticket)
                        except:
                            # Remove invalid tracker entries
                            old_trackers.append(ticket)
                
                for ticket in old_trackers:
                    try:
                        del self.position_tracker[ticket]
                    except KeyError:
                        pass
                
                if old_trackers:
                    self.log(f"🧹 Cleaned up {len(old_trackers)} old position trackers")
                    
        except Exception as e:
            self.log(f"Error in memory cleanup: {str(e)}", "ERROR")

    def get_smart_management_stats(self) -> dict:
        """สถิติการจัดการแบบชาญฉลาด"""
        try:
            stats = {
                'total_redirects': self.total_redirects,
                'successful_redirects': self.successful_redirects,
                'redirect_success_rate': (self.successful_redirects / max(1, self.total_redirects)) * 100,
                'redirect_profit_captured': self.redirect_profit_captured,
                'avg_profit_per_redirect': self.redirect_profit_captured / max(1, self.successful_redirects),
                'redirect_ratio': (self.total_redirects / max(1, self.total_signals)) * 100,
                'active_trackers': len(self.position_tracker),
                'positions_ready_to_close': 0,
                'avg_hold_score': 0
            }
            
            if self.positions:
                total_hold_score = 0
                ready_count = 0
                
                for position in self.positions:
                    tracker = self.position_tracker.get(position.ticket, {})
                    hold_score = tracker.get('hold_score', 50)
                    total_hold_score += hold_score
                    
                    if hold_score <= 25:
                        ready_count += 1
                
                stats['avg_hold_score'] = total_hold_score / len(self.positions)
                stats['positions_ready_to_close'] = ready_count
            
            return stats
            
        except Exception as e:
            self.log(f"Error getting smart stats: {str(e)}", "ERROR")
            return {}

    def trading_loop(self):
        """Main trading loop with comprehensive monitoring and health checks"""
        self.log("🧠 Smart Trading System Started with Enhanced Monitoring")
        last_save_time = datetime.now()
        last_connection_check = datetime.now()
        last_memory_management = datetime.now()
        last_health_check = datetime.now()
        cycle_start_time = datetime.now()
        
        while self.trading_active:
            cycle_start = datetime.now()
            cycle_success = True
            
            try:
                # 🏥 System Health Check (every 5 minutes)
                if (datetime.now() - last_health_check).seconds >= self.health_check_interval:
                    try:
                        if self.system_health_enabled:
                            health_report = self.perform_system_health_check()
                            if health_report['overall_status'] == 'CRITICAL':
                                self.log("🚨 Critical system health issues detected", "ERROR")
                            last_health_check = datetime.now()
                    except Exception as health_error:
                        self.log(f"Health check error: {str(health_error)}", "ERROR")
                

                # 🔗 Connection Health Check
                if (datetime.now() - last_connection_check).seconds >= self.connection_check_interval:
                    if not self.check_mt5_connection_health():
                        if not self.attempt_mt5_reconnection():
                            self.log("⚠️ MT5 connection unhealthy, skipping cycle", "WARNING")
                            cycle_success = False
                            time.sleep(10)
                            continue
                    last_connection_check = datetime.now()
                
                if not self.mt5_connected:
                    self.log("⚠️ MT5 not connected, attempting reconnection...", "WARNING")
                    if not self.attempt_mt5_reconnection():
                        cycle_success = False
                        time.sleep(5)
                        continue
                
                # 🧹 Memory Management (every 30 minutes)
                if (datetime.now() - last_memory_management).seconds >= 1800:  # 30 minutes
                    try:
                        if self.log_memory_usage:
                            memory_before = self.get_memory_status()
                            self.log(f"Memory before cleanup: {memory_before.get('memory_health', {}).get('process_memory_mb', 'N/A')}MB")
                        
                        self.perform_memory_management()
                        last_memory_management = datetime.now()
                        
                        if self.log_memory_usage:
                            memory_after = self.get_memory_status()
                            self.log(f"Memory after cleanup: {memory_after.get('memory_health', {}).get('process_memory_mb', 'N/A')}MB")
                    except Exception as mem_error:
                        self.log(f"Memory management error: {str(mem_error)}", "ERROR")
                        cycle_success = False
                
                # Update positions with error handling
                try:
                    self.update_positions()
                    if self.verbose_logging:
                        self.log(f"📊 Updated positions: {len(self.positions)} active")
                except Exception as e:
                    self.log(f"Error updating positions: {str(e)}", "ERROR")
                    cycle_success = False
                    continue
                
                # Smart Position Management (ทุก 30 วินาที)
                if (not self.last_efficiency_check or 
                    (datetime.now() - self.last_efficiency_check).seconds >= self.position_efficiency_check_interval):
                    try:
                        self.smart_position_management()
                        self.last_efficiency_check = datetime.now()
                        if self.verbose_logging:
                            self.log("🧠 Smart position management executed")
                    except Exception as e:
                        self.log(f"Error in position management: {str(e)}", "ERROR")
                        cycle_success = False
                
                # Market analysis and signal processing
                if self.verbose_logging:
                    self.log("📈 Getting market data...")
                market_data = self.get_market_data()
                
                if (market_data is not None):
                    if self.log_market_data:
                        self.log(f"✅ Market data received: {len(market_data)} candles")
                    
                    try:
                        signal = self.analyze_mini_trend(market_data)
                        
                        if signal:
                            self.log(f"🚨 SIGNAL FOUND: {signal.direction} strength {signal.strength:.1f}")
                            if self.debug_mode:
                                self.log(f"   Reason: {signal.reason}")
                                self.log(f"   Price: {signal.price}")
                            
                            if self.can_trade():
                                if self.verbose_logging:
                                    self.log(f"✅ Trade conditions OK, executing order...")
                                    
                                order_start_time = datetime.now()
                                success = self.execute_order(signal)  # ใช้ smart router
                                order_execution_time = (datetime.now() - order_start_time).total_seconds()
                                
                                if success:
                                    self.successful_signals += 1
                                    self.log(f"🎯 Order execution successful! (took {order_execution_time:.2f}s)")
                                    if self.debug_mode:
                                        self.log(f"   Signal processed: {signal.direction} at {signal.price}")
                                else:
                                    self.log(f"❌ Order execution failed (took {order_execution_time:.2f}s)")
                                    cycle_success = False
                            else:
                                if self.debug_mode:
                                    self.log(f"⏸️ Cannot trade - checking conditions...")
                                    # Debug why can't trade
                                    self.debug_trade_conditions()
                        else:
                            if self.verbose_logging:
                                self.log("📊 No signal detected in current market data")
                            # Debug market conditions only in debug mode
                            if self.debug_mode:
                                self.debug_market_conditions(market_data)
                    except Exception as e:
                        self.log(f"Error in signal analysis: {str(e)}", "ERROR")
                        cycle_success = False
                else:
                    self.log("❌ No market data received", "WARNING")
                    cycle_success = False
                
                # Memory management - cleanup old signals
                try:
                    hour_ago = datetime.now() - timedelta(hours=1)
                    old_count = len(self.hourly_signals)
                    self.hourly_signals = [s for s in self.hourly_signals if s > hour_ago]
                    if old_count != len(self.hourly_signals) and self.verbose_logging:
                        self.log(f"🧹 Cleaned up {old_count - len(self.hourly_signals)} old signals")
                except Exception as e:
                    self.log(f"Error cleaning signals: {str(e)}", "ERROR")
                    cycle_success = False
                
                # Auto-save ทุก 5 นาที
                if (datetime.now() - last_save_time).seconds >= 300:  # 5 minutes
                    try:
                        self.auto_save_state()
                        last_save_time = datetime.now()
                    except Exception as e:
                        self.log(f"Error in auto-save: {str(e)}", "ERROR")
                        cycle_success = False
                
                time.sleep(5)  # 5-second cycle
                
            except Exception as e:
                self.log(f"Error in trading loop: {str(e)}", "ERROR")
                cycle_success = False
                
                # Emergency recovery
                try:
                    self.emergency_state_recovery()
                except Exception as recovery_error:
                    self.log(f"Emergency recovery failed: {str(recovery_error)}", "ERROR")
                time.sleep(10)
            
            finally:
                # Update performance metrics
                cycle_time = (datetime.now() - cycle_start).total_seconds()
                self.update_performance_metrics(cycle_success, cycle_time)
        
        # Save state เมื่อหยุด trading
        try:
            self.save_trading_state()
            final_uptime = (datetime.now() - cycle_start_time).total_seconds()
            self.log(f"🛑 Smart Trading System Stopped - Uptime: {final_uptime/3600:.1f} hours")
            self.log(f"📊 Final Stats: {self.performance_metrics['cycles_completed']} cycles, {self.performance_metrics['error_rate']:.1f}% error rate")
        except Exception as e:
            self.log(f"Error saving final state: {str(e)}", "ERROR")

    def debug_trade_conditions(self):
        """Debug why trading is not allowed"""
        try:
            conditions = []
            
            if not self.mt5_connected:
                conditions.append("❌ MT5 not connected")
            else:
                conditions.append("✅ MT5 connected")
                
            if not self.trading_active:
                conditions.append("❌ Trading not active")
            else:
                conditions.append("✅ Trading active")
                
            if len(self.positions) >= self.max_positions:
                conditions.append(f"❌ Max positions reached: {len(self.positions)}/{self.max_positions}")
            else:
                conditions.append(f"✅ Position count OK: {len(self.positions)}/{self.max_positions}")
                
            # Signal cooldown
            if self.last_signal_time:
                seconds_since = (datetime.now() - self.last_signal_time).seconds
                if seconds_since < self.signal_cooldown:
                    conditions.append(f"❌ Signal cooldown: {seconds_since}/{self.signal_cooldown}s")
                else:
                    conditions.append(f"✅ Signal cooldown OK: {seconds_since}s ago")
            else:
                conditions.append("✅ No previous signals")
                
            # Hourly limit
            recent_count = len(self.hourly_signals)
            if recent_count >= self.max_signals_per_hour:
                conditions.append(f"❌ Hourly limit: {recent_count}/{self.max_signals_per_hour}")
            else:
                conditions.append(f"✅ Hourly signals OK: {recent_count}/{self.max_signals_per_hour}")
                
            # Margin check (only if MT5 is available)
            if MT5_AVAILABLE and mt5:
                account_info = mt5.account_info()
                if account_info and account_info.margin > 0:
                    margin_level = (account_info.equity / account_info.margin) * 100
                    if margin_level < self.min_margin_level:
                        conditions.append(f"❌ Low margin: {margin_level:.1f}%")
                    else:
                        conditions.append(f"✅ Margin OK: {margin_level:.1f}%")
                else:
                    conditions.append("✅ No margin used")
            else:
                conditions.append("✅ MT5 not available - margin check skipped")
                
            self.log("🔍 TRADE CONDITIONS DEBUG:")
            for condition in conditions:
                self.log(f"   {condition}")
                
        except Exception as e:
            self.log(f"Error debugging trade conditions: {str(e)}", "ERROR")

    def debug_market_conditions(self, df):
        """Debug market analysis conditions"""
        try:
            if df is None or len(df) < 3:
                self.log("🔍 MARKET DEBUG: Insufficient data")
                return
                
            last_3 = df.tail(3)
            current_candle = last_3.iloc[-1]
            
            # Count conditions
            green_count = last_3['is_green'].sum()
            red_count = 3 - green_count
            avg_body_ratio = last_3['body_ratio'].mean()
            avg_movement = last_3['movement'].mean()
            current_is_green = current_candle['is_green']
            
            self.log("🔍 MARKET CONDITIONS DEBUG:")
            self.log(f"   Green candles: {green_count}/3")
            self.log(f"   Red candles: {red_count}/3")
            self.log(f"   Avg body ratio: {avg_body_ratio:.2f}% (need ≥5%)")
            self.log(f"   Avg movement: {avg_movement:.4f} points (need ≥0.2)")
            self.log(f"   Current candle: {'Green' if current_is_green else 'Red'}")
            
            # Check BUY conditions
            buy_possible = (green_count >= 2 and 
                           avg_body_ratio >= 5.0 and 
                           avg_movement >= 0.2 and
                           current_is_green)
            
            # Check SELL conditions  
            sell_possible = (red_count >= 2 and 
                            avg_body_ratio >= 5.0 and 
                            avg_movement >= 0.2 and
                            not current_is_green)
            
            if buy_possible:
                self.log("   ✅ BUY signal conditions MET")
            elif sell_possible:
                self.log("   ✅ SELL signal conditions MET")
            else:
                self.log("   ❌ No signal conditions met")
                
            # Detailed breakdown
            if green_count >= 2 and current_is_green:
                self.log("   ✅ BUY trend OK")
            elif red_count >= 2 and not current_is_green:
                self.log("   ✅ SELL trend OK")
            else:
                self.log("   ❌ Trend conditions not met")
                
            if avg_body_ratio < 5.0:
                self.log(f"   ❌ Body ratio too small: {avg_body_ratio:.2f}%")
            else:
                self.log(f"   ✅ Body ratio OK: {avg_body_ratio:.2f}%")
                
            if avg_movement < 0.2:
                self.log(f"   ❌ Movement too small: {avg_movement:.4f}")
            else:
                self.log(f"   ✅ Movement OK: {avg_movement:.4f}")
                
        except Exception as e:
            self.log(f"Error debugging market conditions: {str(e)}", "ERROR")

    def calculate_position_distance_from_market(self, position):
        """คำนวณระยะห่างเป็น pips จาก market price ล่าสุด"""
        try:
            # ตรวจสอบ MT5 connection
            if not self.mt5_connected or not MT5_AVAILABLE:
                return 0
                
            current_tick = mt5.symbol_info_tick(self.symbol)
            if not current_tick:
                self.log(f"Warning: Cannot get current tick for {self.symbol}", "WARNING")
                return 0
            
            # เลือก price ที่เหมาะสมตามประเภท position
            if position.type == "BUY":
                # BUY positions ปิดที่ bid price
                current_price = current_tick.bid
            else:
                # SELL positions ปิดที่ ask price  
                current_price = current_tick.ask
            
            # คำนวณระยะห่างเป็น pips
            # สำหรับ XAUUSD: 1 pip = 0.1, ดังนั้นคูณ 10
            if "XAU" in self.symbol or "GOLD" in self.symbol.upper():
                distance_pips = abs(position.open_price - current_price) * 10
            else:
                # สำหรับ major pairs อื่นๆ
                distance_pips = abs(position.open_price - current_price) * 10000
            
            # Debug log สำหรับตรวจสอบการคำนวณ
            if hasattr(self, 'debug_distance_calculation') and self.debug_distance_calculation:
                self.log(f"🔍 Distance calc: Ticket #{position.ticket}, "
                        f"Open: {position.open_price}, Current: {current_price}, "
                        f"Distance: {distance_pips:.2f} pips", "DEBUG")
            
            return round(distance_pips, 2)
            
        except Exception as e:
            self.log(f"Error calculating position distance: {str(e)}", "ERROR")
            return 0

    def calculate_profit_percent(self, position: Position) -> float:
        """คำนวณกำไรเป็น % ต่อ lot"""
        try:
            if position.volume <= 0:
                return 0.0
            
            # คำนวณ profit per lot as percentage
            # สมมติ 1 lot XAUUSD = $1000 margin requirement
            margin_per_lot = 1000.0  # ปรับตามโบรกเกอร์
            profit_percent = (position.profit_per_lot / margin_per_lot) * 100
            
            return profit_percent
            
        except Exception as e:
            self.log(f"Error calculating profit percent: {str(e)}", "ERROR")
            return 0.0

    # 🚫 ลบระบบเก่าทิ้ง - ใช้แค่ AI system เท่านั้น
    # def find_profitable_pairs(self) -> List[dict]:
    #     """หาคู่ไม้ที่กำไร + ขาดทุน = กำไรรวม (เป็น %) - ลบแล้ว"""
    #     pass

    def calculate_pair_score_percent(self, profit_pos: Position, loss_pos: Position, net_profit_pct: float) -> float:
        """คำนวณคะแนนคู่ไม้ (ใช้ %)"""
        try:
            score = 0.0
            
            # 1. Net profit percentage score (40 points)
            profit_ratio = net_profit_pct / self.min_pair_profit_percent
            score += min(40, profit_ratio * 20)
            
            # 2. Volume balance score (20 points)
            volume_diff = abs(profit_pos.volume - loss_pos.volume)
            avg_volume = (profit_pos.volume + loss_pos.volume) / 2
            volume_balance = max(0, 1 - (volume_diff / avg_volume)) if avg_volume > 0 else 0
            score += volume_balance * 20
            
            # 3. Age factor (15 points)
            if (profit_pos.ticket in self.position_tracker and 
                loss_pos.ticket in self.position_tracker):
                try:
                    profit_birth_time = safe_parse_datetime(self.position_tracker[profit_pos.ticket]['birth_time'])
                    loss_birth_time = safe_parse_datetime(self.position_tracker[loss_pos.ticket]['birth_time'])
                    
                    profit_age = (datetime.now() - profit_birth_time).total_seconds() / 3600
                    loss_age = (datetime.now() - loss_birth_time).total_seconds() / 3600
                    avg_age = (profit_age + loss_age) / 2
                    if avg_age > 6:  # หลัง 6 ชั่วโมง
                        score += min(15, avg_age / 2)
                except Exception as age_error:
                    self.log(f"Warning: Could not calculate age factor in pair score: {age_error}", "WARNING")
            
            # 4. Portfolio health bonus (15 points)
            if self.portfolio_health < 50:
                score += 15
            elif self.portfolio_health < 30:
                score += 25  # Emergency bonus
            
            # 5. Balance improvement (10 points)
            if self.will_improve_balance_by_closing_pair(profit_pos, loss_pos):
                score += 10
            
            return score
            
        except Exception as e:
            self.log(f"Error calculating pair score: {str(e)}", "ERROR")
            return 0

    def find_profitable_groups(self) -> List[dict]:
        """หากลุ่มไม้ที่รวมกันได้กำไร (ใช้ %)"""
        groups = []
        
        try:
            if not self.group_closing_enabled or len(self.positions) < 3:
                return groups
            
            # แยกตามประเภท
            buy_positions = [p for p in self.positions if p.type == "BUY"]
            sell_positions = [p for p in self.positions if p.type == "SELL"]
            
            # หากลุ่ม BUY ที่ได้กำไรรวม
            if len(buy_positions) >= 2:
                buy_group = self.analyze_group_profitability(buy_positions, "BUY")
                if buy_group:
                    groups.append(buy_group)
            
            # หากลุ่ม SELL ที่ได้กำไรรวม
            if len(sell_positions) >= 2:
                sell_group = self.analyze_group_profitability(sell_positions, "SELL")
                if sell_group:
                    groups.append(sell_group)
            
            # หากลุ่มผสม (BUY + SELL)
            mixed_group = self.analyze_mixed_group_profitability(buy_positions, sell_positions)
            if mixed_group:
                groups.append(mixed_group)
            
            # เรียงตามคะแนน
            groups.sort(key=lambda x: x['score'], reverse=True)
            return groups[:3]  # ส่งคืนแค่ 3 กลุ่มที่ดีที่สุด
            
        except Exception as e:
            self.log(f"Error finding profitable groups: {str(e)}", "ERROR")
            return []

    def analyze_group_profitability(self, positions: List[Position], group_type: str) -> Optional[dict]:
        """วิเคราะห์กำไรของกลุ่ม positions"""
        try:
            if len(positions) < 2:
                return None
            
            # คำนวณกำไรรวมเป็น %
            total_profit = sum(p.profit for p in positions)
            total_volume = sum(p.volume for p in positions)
            avg_profit_percent = sum(self.calculate_profit_percent(p) for p in positions) / len(positions)
            
            if avg_profit_percent >= self.min_group_profit_percent:
                score = self.calculate_group_score(positions, avg_profit_percent, group_type)
                
                return {
                    'type': 'group',
                    'group_type': group_type,
                    'positions': positions,
                    'net_profit': total_profit,
                    'avg_profit_percent': avg_profit_percent,
                    'score': score,
                    'total_volume': total_volume,
                    'reason': f'{group_type} group close: {avg_profit_percent:.1f}% avg profit ({len(positions)} positions)'
                }
            
            return None
            
        except Exception as e:
            self.log(f"Error analyzing group profitability: {str(e)}", "ERROR")
            return None

    def analyze_mixed_group_profitability(self, buy_positions: List[Position], sell_positions: List[Position]) -> Optional[dict]:
        """วิเคราะห์กลุ่มผสม BUY+SELL"""
        try:
            if len(buy_positions) < 1 or len(sell_positions) < 1:
                return None
            
            # หาชุดคู่ที่ดีที่สุด
            best_combination = None
            best_score = 0
            
            # ลองรวม 1-2 BUY + 1-2 SELL
            for buy_count in range(1, min(3, len(buy_positions) + 1)):
                for sell_count in range(1, min(3, len(sell_positions) + 1)):
                    if buy_count + sell_count < 3:  # ต้องมีอย่างน้อย 3 ตัว
                        continue
                    
                    # เลือก positions ที่ดีที่สุด
                    selected_buys = sorted(buy_positions, key=lambda p: self.calculate_profit_percent(p), reverse=True)[:buy_count]
                    selected_sells = sorted(sell_positions, key=lambda p: self.calculate_profit_percent(p), reverse=True)[:sell_count]
                    
                    combined_positions = selected_buys + selected_sells
                    total_profit = sum(p.profit for p in combined_positions)
                    avg_profit_pct = sum(self.calculate_profit_percent(p) for p in combined_positions) / len(combined_positions)
                    
                    if avg_profit_pct >= self.min_group_profit_percent:
                        score = self.calculate_group_score(combined_positions, avg_profit_pct, "MIXED")
                        
                        if score > best_score:
                            best_score = score
                            best_combination = {
                                'type': 'mixed_group',
                                'group_type': 'MIXED',
                                'positions': combined_positions,
                                'net_profit': total_profit,
                                'avg_profit_percent': avg_profit_pct,
                                'score': score,
                                'buy_count': buy_count,
                                'sell_count': sell_count,
                                'reason': f'Mixed group: {buy_count}BUY+{sell_count}SELL, {avg_profit_pct:.1f}% avg'
                            }
            
            return best_combination
            
        except Exception as e:
            self.log(f"Error analyzing mixed group: {str(e)}", "ERROR")
            return None

    def calculate_group_score(self, positions: List[Position], avg_profit_pct: float, group_type: str) -> float:
        """คำนวณคะแนนกลุ่ม"""
        try:
            score = 0.0
            
            # 1. Average profit percentage score (35 points)
            profit_ratio = avg_profit_pct / self.min_group_profit_percent
            score += min(35, profit_ratio * 25)
            
            # 2. Group size bonus (20 points)
            group_size = len(positions)
            if group_size >= 5:
                score += 20
            elif group_size >= 3:
                score += 15
            else:
                score += 10
            
            # 3. Balance factor (20 points)
            if group_type == "MIXED":
                score += 20  # Mixed groups help balance
            elif self.portfolio_needs_rebalancing():
                buy_volume = sum(p.volume for p in positions if p.type == "BUY")
                sell_volume = sum(p.volume for p in positions if p.type == "SELL")
                
                if self.buy_volume > self.sell_volume and sell_volume > buy_volume:
                    score += 15  # ปิด SELL เมื่อ BUY มากกว่า
                elif self.sell_volume > self.buy_volume and buy_volume > sell_volume:
                    score += 15  # ปิด BUY เมื่อ SELL มากกว่า
            
            # 4. Portfolio health bonus (15 points)
            if self.portfolio_health < 40:
                score += 15
            
            # 5. Age factor (10 points)
            avg_age = 0
            valid_ages = 0
            for pos in positions:
                if pos.ticket in self.position_tracker:
                    try:
                        birth_time = safe_parse_datetime(self.position_tracker[pos.ticket]['birth_time'])
                        age_hours = (datetime.now() - birth_time).total_seconds() / 3600
                        avg_age += age_hours
                        valid_ages += 1
                    except Exception as age_error:
                        self.log(f"Warning: Could not calculate age for position {pos.ticket}: {age_error}", "WARNING")
            
            if valid_ages > 0:
                avg_age /= valid_ages
                if avg_age > 12:
                    score += min(10, avg_age / 2)
            
            return score
            
        except Exception as e:
            self.log(f"Error calculating group score: {str(e)}", "ERROR")
            return 0

    def will_improve_balance_by_closing_pair(self, pos1: Position, pos2: Position) -> bool:
        """ตรวจสอบว่าการปิดคู่จะช่วย balance ได้หรือไม่"""
        try:
            if len(self.positions) <= 2:
                return False
            
            total_volume = self.buy_volume + self.sell_volume
            if total_volume <= 0:
                return False
            
            current_buy_ratio = self.buy_volume / total_volume
            
            # คำนวณ balance หลังปิด
            new_buy_volume = self.buy_volume - (pos1.volume if pos1.type == "BUY" else 0) - (pos2.volume if pos1.type == "BUY" else 0)
            new_sell_volume = self.sell_volume - (pos1.volume if pos1.type == "SELL" else 0) - (pos2.volume if pos1.type == "SELL" else 0)
            new_total = new_buy_volume + new_sell_volume
            
            if new_total <= 0:
                return False
            
            new_buy_ratio = new_buy_volume / new_total
            
            # เช็คว่าใกล้ 50:50 มากขึ้นหรือไม่
            current_distance = abs(current_buy_ratio - 0.5)
            new_distance = abs(new_buy_ratio - 0.5)
            
            return new_distance < current_distance
            
        except:
            return False

    def portfolio_needs_rebalancing(self) -> bool:
        """ตรวจสอบว่า portfolio ต้องการ rebalance หรือไม่"""
        try:
            total_volume = self.buy_volume + self.sell_volume
            if total_volume <= 0:
                return False
            
            buy_ratio = self.buy_volume / total_volume
            return abs(buy_ratio - 0.5) > self.balance_tolerance
            
        except:
            return False

    def execute_pair_close(self, pair_data: dict) -> bool:
        """ปิดคู่ positions"""
        try:
            positions = pair_data['positions']
            
            # กรองเฉพาะ positions ที่ไม่ขาดทุน
            profitable_positions = [pos for pos in positions if pos.profit > 0]
            
            if len(profitable_positions) != len(positions):
                self.log(f"⚠️ Pair close: Skipping {len(positions) - len(profitable_positions)} losing positions")
                if len(profitable_positions) == 0:
                    self.log("❌ Pair close CANCELLED: All positions are losing")
                    return False
            
            success_count = 0
            for position in profitable_positions:
                if self.close_position_smart(position, f"Pair close: {pair_data['net_profit_percent']:.1f}%"):
                    success_count += 1
                    time.sleep(0.5)  # หน่วงเล็กน้อย
            
            if success_count == len(profitable_positions):
                self.total_pair_closes += 1
                self.successful_pair_closes += 1
                self.pair_profit_captured += pair_data['net_profit']
                
                self.log(f"✅ Pair close SUCCESS: {pair_data['reason']}")
                self.log(f"   Net profit: ${pair_data['net_profit']:.2f} ({pair_data['net_profit_percent']:.1f}%)")
                return True
            else:
                self.log(f"❌ Pair close PARTIAL: {success_count}/{len(profitable_positions)} positions closed")
                return False
                
        except Exception as e:
            self.log(f"Error executing pair close: {str(e)}", "ERROR")
            return False

    def execute_group_close(self, group_data: dict) -> bool:
        """ปิดกลุ่ม positions"""
        try:
            positions = group_data['positions']
            
            # กรองเฉพาะ positions ที่ไม่ขาดทุน
            profitable_positions = [pos for pos in positions if pos.profit > 0]
            
            if len(profitable_positions) != len(positions):
                self.log(f"⚠️ Group close: Skipping {len(positions) - len(profitable_positions)} losing positions")
                if len(profitable_positions) == 0:
                    self.log("❌ Group close CANCELLED: All positions are losing")
                    return False
            
            success_count = 0
            for position in profitable_positions:
                if self.close_position_smart(position, f"Group close: {group_data['avg_profit_percent']:.1f}%"):
                    success_count += 1
                    time.sleep(0.5)  # หน่วงเล็กน้อย
            
            if success_count >= len(profitable_positions) * 0.8:  # 80% สำเร็จถือว่าโอเค
                self.total_group_closes += 1
                self.group_profit_captured += group_data['net_profit']
                
                self.log(f"✅ Group close SUCCESS: {group_data['reason']}")
                self.log(f"   Net profit: ${group_data['net_profit']:.2f} ({group_data['avg_profit_percent']:.1f}%)")
                self.log(f"   Positions closed: {success_count}/{len(profitable_positions)}")
                return True
            else:
                self.log(f"❌ Group close FAILED: {success_count}/{len(profitable_positions)} positions closed")
                return False
                
        except Exception as e:
            self.log(f"Error executing group close: {str(e)}", "ERROR")
            return False

    # 🚫 ลบระบบเก่าทิ้ง - ใช้แค่ AI system เท่านั้น
    # def smart_pair_group_management(self):
    #     """ระบบจัดการแบบคู่และกลุ่ม - ลบแล้ว"""
    #     pass

    def get_pair_group_stats(self) -> dict:
        """สถิติการปิดแบบคู่และกลุ่ม"""
        try:
            stats = {
                'total_pair_closes': self.total_pair_closes,
                'successful_pair_closes': self.successful_pair_closes,
                'pair_success_rate': (self.successful_pair_closes / max(1, self.total_pair_closes)) * 100,
                'pair_profit_captured': self.pair_profit_captured,
                'total_group_closes': self.total_group_closes,
                'group_profit_captured': self.group_profit_captured,
                'total_smart_profit': self.pair_profit_captured + self.group_profit_captured,
                'available_pairs': 0,
                'available_groups': 0
            }
            
            # นับโอกาสปัจจุบัน
            pairs = self.find_profitable_pairs()
            groups = self.find_profitable_groups()
            
            stats['available_pairs'] = len([p for p in pairs if p['score'] > 50])
            stats['available_groups'] = len([g for g in groups if g['score'] > 60])
            
            return stats
            
        except Exception as e:
            self.log(f"Error getting pair/group stats: {str(e)}", "ERROR")
            return {}

    def analyze_position_drawdown(self, position: Position) -> dict:
        """วิเคราะห์ระดับ drawdown ของ position"""
        try:
            analysis = {
                'position': position,
                'current_drawdown_pips': 0,
                'drawdown_level': 'SAFE',
                'recommended_action': 'HOLD',
                'distance_from_entry': 0,
                'risk_score': 0,
                'needs_hedge': False,
                'hedge_suggestions': []
            }
            
            # ดึงราคาปัจจุบัน
            current_tick = mt5.symbol_info_tick(self.symbol)
            if not current_tick:
                return analysis
            
            current_price = current_tick.ask if position.type == "BUY" else current_tick.bid
            
            # คำนวณระยะห่างเป็น pips
            if position.type == "BUY":
                distance_pips = (position.open_price - current_price) * 100  # ติดลบถ้าราคาตก
            else:  # SELL
                distance_pips = (current_price - position.open_price) * 100  # ติดลบถ้าราคาขึ้น
            
            analysis['current_drawdown_pips'] = distance_pips
            analysis['distance_from_entry'] = abs(distance_pips)
            
            # ประเมินระดับ drawdown
            if analysis['distance_from_entry'] >= self.emergency_drawdown_pips:
                analysis['drawdown_level'] = 'EMERGENCY'
                analysis['risk_score'] = 95
                analysis['recommended_action'] = 'IMMEDIATE_HEDGE'
                analysis['needs_hedge'] = True
            elif analysis['distance_from_entry'] >= self.critical_drawdown_pips:
                analysis['drawdown_level'] = 'CRITICAL'
                analysis['risk_score'] = 80
                analysis['recommended_action'] = 'URGENT_HEDGE'
                analysis['needs_hedge'] = True
            elif analysis['distance_from_entry'] >= self.drawdown_trigger_pips:
                analysis['drawdown_level'] = 'HIGH'
                analysis['risk_score'] = 60
                analysis['recommended_action'] = 'CONSIDER_HEDGE'
                analysis['needs_hedge'] = True
            else:
                analysis['drawdown_level'] = 'SAFE'
                analysis['risk_score'] = 20
                analysis['recommended_action'] = 'MONITOR'
            
            # สร้างคำแนะนำ hedge
            if analysis['needs_hedge']:
                analysis['hedge_suggestions'] = self.generate_hedge_suggestions(position, analysis)
            
            return analysis
            
        except Exception as e:
            self.log(f"Error analyzing drawdown: {str(e)}", "ERROR")
            return analysis

    def generate_hedge_suggestions(self, position: Position, analysis: dict) -> List[dict]:
        """สร้างคำแนะนำการ hedge"""
        suggestions = []
        
        try:
            distance = analysis['distance_from_entry']
            drawdown_level = analysis['drawdown_level']
            
            # Strategy 1: Immediate Hedge
            hedge_volume = self.calculate_hedge_volume(position, "IMMEDIATE")
            suggestions.append({
                'strategy': 'IMMEDIATE_HEDGE',
                'description': f'Hedge {hedge_volume:.2f} lots opposite direction immediately',
                'volume': hedge_volume,
                'expected_coverage': self.hedge_coverage_ratio,
                'recovery_potential': 'Medium',
                'risk_level': 'Low'
            })
            
            # Strategy 2: Smart Recovery (รอจังหวะ)
            if drawdown_level in ['HIGH', 'CRITICAL']:
                smart_volume = self.calculate_hedge_volume(position, "SMART_RECOVERY")
                suggestions.append({
                    'strategy': 'SMART_RECOVERY',
                    'description': f'Wait for reversal signal, then hedge {smart_volume:.2f} lots',
                    'volume': smart_volume,
                    'expected_coverage': self.hedge_coverage_ratio * 0.8,
                    'recovery_potential': 'High',
                    'risk_level': 'Medium'
                })
            
            # Strategy 3: Multi-Level Hedge
            if drawdown_level == 'EMERGENCY':
                level1_volume = position.volume * 0.6
                level2_volume = position.volume * 0.8
                suggestions.append({
                    'strategy': 'MULTI_LEVEL',
                    'description': f'Level 1: {level1_volume:.2f} lots now, Level 2: {level2_volume:.2f} lots at +50 pips',
                    'volume': level1_volume,
                    'expected_coverage': 1.4,
                    'recovery_potential': 'Very High',
                    'risk_level': 'High'
                })
            
            return suggestions
            
        except Exception as e:
            self.log(f"Error generating hedge suggestions: {str(e)}", "ERROR")
            return []

    def calculate_hedge_volume(self, position: Position, strategy: str) -> float:
        """คำนวณ volume สำหรับ hedge"""
        try:
            base_volume = position.volume
            
            if self.hedge_volume_calculation == "FIXED_RATIO":
                hedge_volume = base_volume * self.hedge_coverage_ratio
                
            elif self.hedge_volume_calculation == "DYNAMIC_RATIO":
                # ปรับ ratio ตามระยะห่างและสถานการณ์ - แก้ไข recursion
                # ดึงราคาปัจจุบันโดยตรงแทนการเรียก analyze_position_drawdown
                current_tick = mt5.symbol_info_tick(self.symbol)
                if current_tick:
                    current_price = current_tick.ask if position.type == "BUY" else current_tick.bid
                    
                    # คำนวณระยะห่างโดยตรง
                    if position.type == "BUY":
                        distance_pips = (position.open_price - current_price) * 100
                    else:  # SELL
                        distance_pips = (current_price - position.open_price) * 100
                    
                    distance = abs(distance_pips)
                    
                    # ปรับ ratio ตามระยะห่าง
                    if distance >= self.emergency_drawdown_pips:
                        ratio = self.hedge_coverage_ratio * 1.3  # เพิ่มมากขึ้น
                    elif distance >= self.critical_drawdown_pips:
                        ratio = self.hedge_coverage_ratio * 1.1
                    else:
                        ratio = self.hedge_coverage_ratio * 0.9
                else:
                    ratio = self.hedge_coverage_ratio
                
                hedge_volume = base_volume * ratio
                
            elif self.hedge_volume_calculation == "LOSS_BASED":
                # คำนวณจาก loss amount
                loss_amount = abs(position.profit)
                if loss_amount > 0:
                    # สมมติต้องการ hedge ให้ครอบคลุม 120% ของ loss
                    target_coverage = loss_amount * self.hedge_coverage_ratio
                    # ประมาณ pip value (ปรับตามโบรกเกอร์)
                    pip_value_per_lot = 100  # XAUUSD โดยประมาณ
                    hedge_volume = target_coverage / pip_value_per_lot
                else:
                    hedge_volume = base_volume * self.hedge_coverage_ratio
            else:
                # Default fallback
                hedge_volume = base_volume * self.hedge_coverage_ratio
            
            # ปรับตาม strategy
            if strategy == "SMART_RECOVERY":
                hedge_volume *= 0.8  # ลดลงเพราะรอจังหวะดี
            elif strategy == "MULTI_LEVEL":
                hedge_volume *= 0.6  # level แรก ใช้น้อยกว่า
            
            # จำกัดขอบเขต
            hedge_volume = max(self.min_hedge_volume, min(self.max_hedge_volume, hedge_volume))
            hedge_volume = round(hedge_volume, 2)
            
            return hedge_volume
            
        except Exception as e:
            self.log(f"Error calculating hedge volume: {str(e)}", "ERROR")
            return self.min_hedge_volume

    def execute_auto_hedge(self, position: Position, strategy: str = "IMMEDIATE") -> bool:
        """ดำเนินการ hedge อัตโนมัติ"""
        try:
            if not self.hedge_system_enabled:
                return False
            
            # ตรวจสอบว่ามี hedge อยู่แล้วหรือไม่
            if position.ticket in self.active_hedges:
                current_hedges = len(self.active_hedges[position.ticket])
                if current_hedges >= self.max_hedge_levels:
                    self.log(f"⚠️ Max hedge levels reached for position {position.ticket}")
                    return False
            
            # คำนวณ hedge volume
            hedge_volume = self.calculate_hedge_volume(position, strategy)
            
            # กำหนดทิศทางตรงข้าม
            hedge_type = mt5.ORDER_TYPE_SELL if position.type == "BUY" else mt5.ORDER_TYPE_BUY
            hedge_direction = "SELL" if position.type == "BUY" else "BUY"
            
            # สร้าง order request
            if self.filling_type is None:
                self.filling_type = self.detect_broker_filling_type()
            
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": self.symbol,
                "volume": hedge_volume,
                "type": hedge_type,
                "deviation": 20,
                "magic": 123457,  # ใช้ magic number ต่างจาก trade ปกติ
                "comment": f"HG_{position.ticket}_{strategy[:4]}",
                "type_time": mt5.ORDER_TIME_GTC,
                "type_filling": self.filling_type,
            }
            
            # ส่ง order
            result = mt5.order_send(request)
            
            if result.retcode == mt5.TRADE_RETCODE_DONE:
                hedge_ticket = result.order
                
                # บันทึกการ hedge
                if position.ticket not in self.active_hedges:
                    self.active_hedges[position.ticket] = []
                
                self.active_hedges[position.ticket].append({
                    'hedge_ticket': hedge_ticket,
                    'hedge_volume': hedge_volume,
                    'hedge_type': hedge_direction,
                    'creation_time': datetime.now(),
                    'creation_price': result.price,
                    'strategy': strategy,
                    'level': len(self.active_hedges[position.ticket]) + 1
                })
                
                self.hedge_pairs[hedge_ticket] = position.ticket
                
                # อัพเดท statistics
                self.hedge_analytics['total_hedges_created'] += 1
                self.hedge_analytics['active_hedge_pairs'] += 1
                
                self.log(f"✅ Hedge created: {hedge_direction} {hedge_volume} lots for position {position.ticket}")
                self.log(f"   Strategy: {strategy}, Ticket: {hedge_ticket}")
                self.log(f"   Original: {position.type} {position.volume} lots @ {position.open_price}")
                
                return True
                
            else:
                self.log(f"❌ Hedge creation failed: {result.retcode}", "ERROR")
                return False
                
        except Exception as e:
            self.log(f"Error executing auto hedge: {str(e)}", "ERROR")
            return False

    def manage_existing_hedges(self):
        """จัดการ hedge pairs ที่มีอยู่"""
        if not self.active_hedges:
            return
        
        try:
            for original_ticket, hedge_list in list(self.active_hedges.items()):
                # หา original position
                original_pos = None
                for pos in self.positions:
                    if pos.ticket == original_ticket:
                        original_pos = pos
                        break
                
                if not original_pos:
                    # Original position ถูกปิดแล้ว ให้ปิด hedge ด้วย
                    self.close_orphaned_hedges(original_ticket, hedge_list)
                    continue
                
                # จัดการแต่ละ hedge
                for hedge_info in hedge_list[:]:  # ใช้ slice เพื่อป้องกัน modification error
                    hedge_ticket = hedge_info['hedge_ticket']
                    
                    # หา hedge position
                    hedge_pos = None
                    for pos in self.positions:
                        if pos.ticket == hedge_ticket:
                            hedge_pos = pos
                            break
                    
                    if not hedge_pos:
                        # Hedge ถูกปิดแล้ว ลบออกจาก tracking
                        hedge_list.remove(hedge_info)
                        if hedge_ticket in self.hedge_pairs:
                            del self.hedge_pairs[hedge_ticket]
                        continue
                    
                    # วิเคราะห์ว่าควรปิด hedge pair หรือไม่
                    should_close, reason = self.should_close_hedge_pair(original_pos, hedge_pos, hedge_info)
                    
                    if should_close:
                        success = self.close_hedge_pair(original_pos, hedge_pos, reason)
                        if success:
                            hedge_list.remove(hedge_info)
                            if hedge_ticket in self.hedge_pairs:
                                del self.hedge_pairs[hedge_ticket]
                
                # ลบ original ticket ถ้าไม่มี hedge เหลือ
                if not hedge_list:
                    del self.active_hedges[original_ticket]
                    
        except Exception as e:
            self.log(f"Error managing existing hedges: {str(e)}", "ERROR")

    def should_close_hedge_pair(self, original_pos: Position, hedge_pos: Position, hedge_info: dict) -> Tuple[bool, str]:
        """ตัดสินใจว่าควรปิด hedge pair หรือไม่"""
        try:
            # คำนวณกำไรรวม
            total_profit = original_pos.profit + hedge_pos.profit
            combined_volume = original_pos.volume + hedge_pos.volume
            avg_profit_per_lot = total_profit / combined_volume if combined_volume > 0 else 0
            
            # เงื่อนไข 1: กำไรรวมเกินเป้า
            target_profit = self.hedge_recovery_target / 100 * 1000 * combined_volume  # 2% of margin
            if total_profit >= target_profit:
                return True, f"Recovery target reached: ${total_profit:.2f} (target: ${target_profit:.2f})"
            
            # เงื่อนไข 2: Hedge กำไรดีพอและ original กลับมาใกล้เคียง
            hedge_profit_pct = (hedge_pos.profit_per_lot / 1000) * 100  # สมมติ margin 1000/lot
            original_loss_pct = (original_pos.profit_per_lot / 1000) * 100
            
            if (hedge_profit_pct >= self.hedge_min_profit_to_close and 
                original_loss_pct >= -5.0):  # original ขาดทุนไม่เกิน 5%
                return True, f"Hedge profitable & original recovered: HG +{hedge_profit_pct:.1f}%, Orig {original_loss_pct:.1f}%"
            
            # เงื่อนไข 3: Portfolio health ต่ำ และมีกำไรรวม
            if (self.portfolio_health < 40 and 
                total_profit > combined_volume * 20):  # กำไรรวม > $20/lot
                return True, f"Portfolio health emergency: ${total_profit:.2f} profit captured"
            
            # เงื่อนไข 4: เวลานานเกินไป และมีกำไรบ้าง
            hedge_age_hours = (datetime.now() - hedge_info['creation_time']).total_seconds() / 3600
            if (hedge_age_hours > 24 and total_profit > 0):
                return True, f"Long duration + positive: {hedge_age_hours:.1f}h, ${total_profit:.2f}"
            
            # เงื่อนไข 5: Market reversal แรง (เทคนิคขั้นสูง)
            if self.detect_market_reversal(original_pos, hedge_pos):
                return True, "Strong market reversal detected"
            
            return False, "Continue monitoring"
            
        except Exception as e:
            self.log(f"Error evaluating hedge pair: {str(e)}", "ERROR")
            return False, "Error in evaluation"

    
    def detect_market_reversal(self, original_pos: Position, hedge_pos: Position) -> bool:
        """ตรวจจับการเปลี่ยนทิศทางของตลาด"""
        try:
            # ดึงข้อมูลตลาดล่าสุด
            market_data = self.get_market_data()
            if market_data is None or len(market_data) < 5:
                return False
            
            # วิเคราะห์ momentum ล่าสุด
            last_5 = market_data.tail(5)
            
            # ตรวจสอบการเปลี่ยนทิศทาง
            if original_pos.type == "BUY":  # Original เป็น BUY ที่ติดลบ
                # ถ้าตลาดเริ่มขึ้นแรง (3/5 candles เป็นสีเขียว)
                green_count = last_5['is_green'].sum()
                avg_movement = last_5['movement'].mean()
                
                if green_count >= 3 and avg_movement > 0.5:  # เพิ่ม 'and'
                    return True
                    
            else:  # Original เป็น SELL ที่ติดลบ
                # ถ้าตลาดเริ่มลงแรง (3/5 candles เป็นสีแดง)
                red_count = 5 - last_5['is_green'].sum()
                avg_movement = last_5['movement'].mean()
                
                if red_count >= 3 and avg_movement > 0.5:  # เพิ่ม 'and'
                    return True
            
            return False
            
        except Exception as e:
            self.log(f"Error detecting reversal: {str(e)}", "ERROR")
            return False
    
    def close_hedge_pair(self, original_pos: Position, hedge_pos: Position, reason: str) -> bool:
        """ปิด hedge pair"""
        try:
            success_count = 0
            total_profit = original_pos.profit + hedge_pos.profit
            
            # ปิด original position ก่อน
            if self.close_position_smart(original_pos, f"Hedge pair close: {reason}"):
                success_count += 1
                time.sleep(0.5)
            
            # ปิด hedge position
            if self.close_position_smart(hedge_pos, f"Hedge pair close: {reason}"):
                success_count += 1
            
            if success_count == 2:
                # อัพเดท statistics
                self.hedge_analytics['successful_recoveries'] += 1
                self.hedge_analytics['total_recovery_profit'] += total_profit
                self.hedge_analytics['active_hedge_pairs'] -= 1
                
                self.log(f"✅ Hedge pair closed successfully!")
                self.log(f"   Original: {original_pos.ticket} ({original_pos.type} {original_pos.volume})")
                self.log(f"   Hedge: {hedge_pos.ticket} ({hedge_pos.type} {hedge_pos.volume})")
                self.log(f"   Total profit: ${total_profit:.2f}")
                self.log(f"   Reason: {reason}")
                
                return True
            else:
                self.log(f"❌ Partial hedge pair close: {success_count}/2 positions closed")
                return False
                
        except Exception as e:
            self.log(f"Error closing hedge pair: {str(e)}", "ERROR")
            return False

    def close_orphaned_hedges(self, original_ticket: int, hedge_list: List[dict]):
        """ปิด hedge ที่ original position หายไป"""
        try:
            for hedge_info in hedge_list:
                hedge_ticket = hedge_info['hedge_ticket']
                
                # หา hedge position
                hedge_pos = None
                for pos in self.positions:
                    if pos.ticket == hedge_ticket:
                        hedge_pos = pos
                        break
                
                if hedge_pos:
                    if self.close_position_smart(hedge_pos, f"Orphaned hedge (original {original_ticket} closed)"):
                        self.log(f"✅ Closed orphaned hedge {hedge_ticket}")
                        if hedge_ticket in self.hedge_pairs:
                            del self.hedge_pairs[hedge_ticket]
            
            # ลบออกจาก tracking
            if original_ticket in self.active_hedges:
                del self.active_hedges[original_ticket]
                
        except Exception as e:
            self.log(f"Error closing orphaned hedges: {str(e)}", "ERROR")

    def drawdown_management_system(self):
        """ระบบจัดการ drawdown หลัก - อัปเดตให้ใช้ Smart HG"""
        if not self.drawdown_management_enabled or not self.positions:
            return
        
        try:
            # 1. รัน Smart HG Management Cycle
            if self.smart_hg_enabled:
                self.smart_hg_management_cycle()
            else:
                # ใช้ระบบเก่าถ้า Smart HG ปิดอยู่
                for position in self.positions:
                    if position.ticket in self.hedge_pairs:
                        continue
                    
                    analysis = self.analyze_position_drawdown(position)
                    
                    if analysis['needs_hedge']:
                        self.log(f"⚠️ Drawdown detected: Position {position.ticket}")
                        self.log(f"   Distance: {analysis['distance_from_entry']:.0f} pips")
                        self.log(f"   Level: {analysis['drawdown_level']}")
                        
                        if analysis['drawdown_level'] in ['EMERGENCY', 'CRITICAL']:
                            self.execute_auto_hedge(position, "IMMEDIATE")
                        elif analysis['drawdown_level'] == 'HIGH':
                            if self.hedge_strategy == "SMART_RECOVERY":
                                if self.detect_market_reversal_opportunity(position):
                                    self.execute_auto_hedge(position, "SMART_RECOVERY")
                            else:
                                self.execute_auto_hedge(position, "IMMEDIATE")
            
            # 2. จัดการ hedge pairs ที่มีอยู่
            self.manage_existing_hedges()
            
        except Exception as e:
            self.log(f"Error in drawdown management: {str(e)}", "ERROR")

    def detect_market_reversal_opportunity(self, position: Position) -> bool:
        """ตรวจหาโอกาส reversal สำหรับ smart hedge"""
        try:
            market_data = self.get_market_data()
            if market_data is None or len(market_data) < 3:
                return False
            
            last_3 = market_data.tail(3)
            
            if position.type == "BUY":
                # ตลาดเริ่มกลับขึ้น
                green_count = last_3['is_green'].sum()
                if green_count >= 2:
                    return True
            else:
                # ตลาดเริ่มกลับลง
                red_count = 3 - last_3['is_green'].sum()
                if red_count >= 2:
                    return True
            
            return False
            
        except Exception as e:
            return False

    def get_hedge_analytics(self) -> dict:
        """สถิติระบบ hedge"""
        try:
            analytics = self.hedge_analytics.copy()
            
            # คำนวณประสิทธิภาพ
            total_hedges = analytics['total_hedges_created']
            successful_recoveries = analytics['successful_recoveries']
            
            if total_hedges > 0:
                analytics['hedge_effectiveness'] = (successful_recoveries / total_hedges) * 100
            
            if successful_recoveries > 0:
                analytics['avg_recovery_profit'] = analytics['total_recovery_profit'] / successful_recoveries
            else:
                analytics['avg_recovery_profit'] = 0.0
            
            # ข้อมูลปัจจุบัน
            analytics['positions_with_drawdown'] = 0
            analytics['positions_needing_hedge'] = 0
            
            for position in self.positions:
                if position.ticket not in self.hedge_pairs:  # ไม่นับ hedge positions
                    analysis = self.analyze_position_drawdown(position)
                    if analysis['distance_from_entry'] > 100:
                        analytics['positions_with_drawdown'] += 1
                    if analysis['needs_hedge']:
                        analytics['positions_needing_hedge'] += 1
            
            return analytics
            
        except Exception as e:
            self.log(f"Error getting hedge analytics: {str(e)}", "ERROR")
            return self.hedge_analytics

    def save_trading_state(self):
        """💾 บันทึกสถานะสำคัญของระบบ with atomic writes and backup"""
        temp_file = None
        backup_file = None
        
        try:
            # Validate critical data before saving
            if not hasattr(self, 'position_tracker'):
                self.position_tracker = {}
            if not hasattr(self, 'active_hedges'):
                self.active_hedges = {}
            if not hasattr(self, 'hedge_pairs'):
                self.hedge_pairs = {}
            
            # ข้อมูลที่จะบันทึก
            state_data = {
                "timestamp": datetime.now().isoformat(),
                "version": "3.1",  # Updated version for robustness
                "checksum": None,  # Will be calculated
                
                # Position tracking (with validation and datetime serialization)
                "position_tracker": serialize_datetime_objects(self.position_tracker if isinstance(self.position_tracker, dict) else {}),
                "active_hedges": serialize_datetime_objects(self.active_hedges if isinstance(self.active_hedges, dict) else {}),
                "hedge_pairs": serialize_datetime_objects(self.hedge_pairs if isinstance(self.hedge_pairs, dict) else {}),
                
                # Statistics (with defaults)
                "total_signals": getattr(self, 'total_signals', 0),
                "successful_signals": getattr(self, 'successful_signals', 0),
                "last_signal_time": self.last_signal_time.isoformat() if getattr(self, 'last_signal_time', None) else None,
                
                # Smart router stats
                "total_redirects": getattr(self, 'total_redirects', 0),
                "successful_redirects": getattr(self, 'successful_redirects', 0),
                "redirect_profit_captured": getattr(self, 'redirect_profit_captured', 0.0),
                "last_redirect_time": self.last_redirect_time.isoformat() if getattr(self, 'last_redirect_time', None) else None,
                
                # Pair/Group closing stats
                "total_pair_closes": getattr(self, 'total_pair_closes', 0),
                "successful_pair_closes": getattr(self, 'successful_pair_closes', 0),
                "pair_profit_captured": getattr(self, 'pair_profit_captured', 0.0),
                "total_group_closes": getattr(self, 'total_group_closes', 0),
                "group_profit_captured": getattr(self, 'group_profit_captured', 0.0),
                
                # Hedge analytics
                "hedge_analytics": serialize_datetime_objects(getattr(self, 'hedge_analytics', {})),
                
                # Portfolio info
                "portfolio_health": getattr(self, 'portfolio_health', 100.0),
                
                # Settings (สำคัญ)
                "base_lot": getattr(self, 'base_lot', 0.01),
                "smart_router_enabled": getattr(self, 'smart_router_enabled', True),
                "pair_closing_enabled": getattr(self, 'pair_closing_enabled', True),
                "hedge_system_enabled": getattr(self, 'hedge_system_enabled', True),
                "drawdown_management_enabled": getattr(self, 'drawdown_management_enabled', True)
            }
            
            # Calculate checksum for data integrity
            import hashlib
            state_json = json.dumps(state_data, sort_keys=True, ensure_ascii=False)
            state_data["checksum"] = hashlib.md5(state_json.encode()).hexdigest()
            
            # Create backup of existing file
            if os.path.exists(self.state_file):
                backup_file = f"{self.state_file}.backup"
                try:
                    import shutil
                    shutil.copy2(self.state_file, backup_file)
                except Exception as backup_error:
                    self.log(f"Warning: Could not create backup: {backup_error}", "WARNING")
            
            # Atomic write using temporary file
            temp_file = f"{self.state_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(state_data, f, ensure_ascii=False, indent=2)
                f.flush()  # Ensure data is written to disk
                os.fsync(f.fileno())  # Force write to disk
            
            # Atomic rename (most filesystems guarantee this is atomic)
            if os.path.exists(temp_file):
                if os.name == 'nt':  # Windows
                    if os.path.exists(self.state_file):
                        os.remove(self.state_file)
                os.rename(temp_file, self.state_file)
            
            self.log(f"✅ Trading state saved to {self.state_file}")
            
            # Clean up old backup
            if backup_file and os.path.exists(backup_file):
                try:
                    # Keep only the most recent backup
                    old_backup = f"{backup_file}.old"
                    if os.path.exists(old_backup):
                        os.remove(old_backup)
                    os.rename(backup_file, old_backup)
                except:
                    pass
            
            return True
            
        except Exception as e:
            self.log(f"❌ Error saving state: {str(e)}", "ERROR")
            
            # Cleanup on error
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass
            
            # Restore from backup if available
            if backup_file and os.path.exists(backup_file):
                try:
                    import shutil
                    shutil.copy2(backup_file, self.state_file)
                    self.log("Restored from backup after save failure", "WARNING")
                except Exception as restore_error:
                    self.log(f"Failed to restore from backup: {restore_error}", "ERROR")
            
            return False
            
        except Exception as e:
            self.log(f"❌ Error saving state: {str(e)}", "ERROR")
            return False

    def load_trading_state(self):
        """📂 โหลดสถานะที่บันทึกไว้ with validation and recovery"""
        backup_loaded = False
        
        try:
            # Check if main state file exists
            if not os.path.exists(self.state_file):
                # Try to load from backup
                backup_file = f"{self.state_file}.backup"
                old_backup = f"{backup_file}.old"
                
                if os.path.exists(backup_file):
                    self.log(f"📝 Main state file not found, trying backup: {backup_file}")
                    success = self._load_state_from_file(backup_file)
                    return success
                elif os.path.exists(old_backup):
                    self.log(f"📝 Trying old backup: {old_backup}")
                    success = self._load_state_from_file(old_backup)
                    return success
                else:
                    self.log(f"📝 No previous state found ({self.state_file})")
                    return False
            
            success = self._load_state_from_file(self.state_file)
            return success
            
        except Exception as e:
            self.log(f"❌ Error loading state: {str(e)}", "ERROR")
            
            # Try backup files as fallback
            for backup_file in [f"{self.state_file}.backup", f"{self.state_file}.backup.old"]:
                if os.path.exists(backup_file):
                    try:
                        self.log(f"🔄 Attempting recovery from {backup_file}")
                        success = self._load_state_from_file(backup_file)
                        return success
                    except Exception as backup_error:
                        self.log(f"❌ Backup recovery failed: {backup_error}", "ERROR")
                        continue
            
            self.log("❌ All recovery attempts failed", "ERROR")
            return False
    
    def _load_state_from_file(self, filename: str) -> bool:
        """Load state from a specific file with validation"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                state_data = json.load(f)
            
            # Validate basic structure
            if not isinstance(state_data, dict):
                raise ValidationError("State data is not a dictionary")
            
            # Check version compatibility
            version = state_data.get("version", "3.0")
            if version not in ["3.0", "3.1"]:
                self.log(f"⚠️ Unsupported version {version}, loading with compatibility mode", "WARNING")
            
            # Validate checksum if available (version 3.1+)
            if version == "3.1" and "checksum" in state_data:
                saved_checksum = state_data.pop("checksum")
                import hashlib
                current_json = json.dumps(state_data, sort_keys=True, ensure_ascii=False)
                current_checksum = hashlib.md5(current_json.encode()).hexdigest()
                
                if saved_checksum != current_checksum:
                    self.log("⚠️ Checksum mismatch - data may be corrupted", "WARNING")
                    # Continue loading but with caution
            
            # Restore data with validation
            self.position_tracker = self._validate_dict(state_data.get("position_tracker", {}))
            self.active_hedges = self._validate_dict(state_data.get("active_hedges", {}))
            self.hedge_pairs = self._validate_dict(state_data.get("hedge_pairs", {}))
            
            # Statistics with validation
            self.total_signals = self._validate_int(state_data.get("total_signals", 0), min_val=0)
            self.successful_signals = self._validate_int(state_data.get("successful_signals", 0), min_val=0)
            
            # Parse datetime strings with validation
            if state_data.get("last_signal_time"):
                try:
                    self.last_signal_time = datetime.fromisoformat(state_data["last_signal_time"])
                except ValueError as e:
                    self.log(f"Invalid last_signal_time format: {e}", "WARNING")
                    self.last_signal_time = None
            
            # Smart router stats with validation
            self.total_redirects = self._validate_int(state_data.get("total_redirects", 0), min_val=0)
            self.successful_redirects = self._validate_int(state_data.get("successful_redirects", 0), min_val=0)
            self.redirect_profit_captured = self._validate_float(state_data.get("redirect_profit_captured", 0.0))
            
            if state_data.get("last_redirect_time"):
                try:
                    self.last_redirect_time = datetime.fromisoformat(state_data["last_redirect_time"])
                except ValueError as e:
                    self.log(f"Invalid last_redirect_time format: {e}", "WARNING")
                    self.last_redirect_time = None
            
            # Pair/Group stats with validation
            self.total_pair_closes = self._validate_int(state_data.get("total_pair_closes", 0), min_val=0)
            self.successful_pair_closes = self._validate_int(state_data.get("successful_pair_closes", 0), min_val=0)
            self.pair_profit_captured = self._validate_float(state_data.get("pair_profit_captured", 0.0))
            self.total_group_closes = self._validate_int(state_data.get("total_group_closes", 0), min_val=0)
            self.group_profit_captured = self._validate_float(state_data.get("group_profit_captured", 0.0))
            
            # Hedge analytics with validation
            hedge_analytics = state_data.get("hedge_analytics", {})
            if isinstance(hedge_analytics, dict):
                if hasattr(self, 'hedge_analytics'):
                    self.hedge_analytics.update(hedge_analytics)
                else:
                    self.hedge_analytics = hedge_analytics
            
            # Portfolio with validation
            self.portfolio_health = self._validate_float(
                state_data.get("portfolio_health", 100.0), 
                min_val=0.0, 
                max_val=200.0
            )
            
            # Settings with validation
            self.base_lot = self._validate_float(
                state_data.get("base_lot", self.base_lot),
                min_val=0.01,
                max_val=100.0
            )
            
            self.smart_router_enabled = bool(state_data.get("smart_router_enabled", True))
            self.pair_closing_enabled = bool(state_data.get("pair_closing_enabled", True))
            self.hedge_system_enabled = bool(state_data.get("hedge_system_enabled", True))
            self.drawdown_management_enabled = bool(state_data.get("drawdown_management_enabled", True))
            
            # Restore datetime objects in nested structures
            self.restore_position_tracker_datetime()
            
            saved_time = state_data.get("timestamp", "Unknown")
            self.log(f"✅ Trading state loaded from {saved_time} (file: {filename})")
            self.log(f"📊 Restored: {len(self.position_tracker)} position trackers")
            self.log(f"📊 Restored: {len(self.active_hedges)} hedge groups")
            self.log(f"📊 Stats: {self.total_signals} signals, {self.total_redirects} redirects")
            
            return True
            
        except Exception as e:
            self.log(f"❌ Error loading from {filename}: {str(e)}", "ERROR")
            raise
    
    def _validate_dict(self, value, default=None):
        """Validate that value is a dictionary"""
        if default is None:
            default = {}
        return value if isinstance(value, dict) else default
    
    def _validate_int(self, value, min_val=None, max_val=None, default=0):
        """Validate integer values with optional bounds"""
        try:
            val = int(value)
            if min_val is not None and val < min_val:
                return min_val
            if max_val is not None and val > max_val:
                return max_val
            return val
        except (ValueError, TypeError):
            return default
    
    def _validate_float(self, value, min_val=None, max_val=None, default=0.0):
        """Validate float values with optional bounds"""
        try:
            val = float(value)
            if min_val is not None and val < min_val:
                return min_val
            if max_val is not None and val > max_val:
                return max_val
            return val
        except (ValueError, TypeError):
            return default

    def restore_position_tracker_datetime(self):
        """แปลง datetime strings ใน position_tracker กลับเป็น datetime objects"""
        try:
            for ticket, tracker in self.position_tracker.items():
                if isinstance(tracker.get('birth_time'), str):
                    tracker['birth_time'] = datetime.fromisoformat(tracker['birth_time'])
                    
            # ทำเช่นเดียวกันกับ active_hedges
            for original_ticket, hedge_list in self.active_hedges.items():
                for hedge_info in hedge_list:
                    if isinstance(hedge_info.get('creation_time'), str):
                        hedge_info['creation_time'] = datetime.fromisoformat(hedge_info['creation_time'])
                        
        except Exception as e:
            self.log(f"Error restoring datetime objects: {str(e)}", "ERROR")

    def backup_positions_data(self):
        """💾 Backup positions data (เป็น binary เพื่อความเร็ว)"""
        try:
            if not self.positions:
                return
            
            positions_data = {
                'positions': [pos.__dict__ for pos in self.positions],
                'buy_volume': self.buy_volume,
                'sell_volume': self.sell_volume,
                'timestamp': datetime.now(),
                'total_positions': len(self.positions)
            }
            
            with open(self.positions_file, 'wb') as f:
                pickle.dump(positions_data, f)
                
            self.log(f"📦 Positions backup: {len(self.positions)} positions saved")
            
        except Exception as e:
            self.log(f"Error backing up positions: {str(e)}", "ERROR")

    def restore_positions_reference(self):
        """📂 โหลดข้อมูล positions สำหรับอ้างอิง (ไม่ใช่การเทรดจริง)"""
        try:
            if not os.path.exists(self.positions_file):
                return None
            
            with open(self.positions_file, 'rb') as f:
                positions_data = pickle.load(f)
            
            backup_time = positions_data.get('timestamp', 'Unknown')
            total_positions = positions_data.get('total_positions', 0)
            
            self.log(f"📋 Reference positions available: {total_positions} from {backup_time}")
            return positions_data
            
        except Exception as e:
            self.log(f"Error loading positions reference: {str(e)}", "ERROR")
            return None

    def auto_save_state(self):
        """🔄 Auto-save ทุก 5 นาที"""
        try:
            # Save trading state
            self.save_trading_state()
            
            # Backup positions
            self.backup_positions_data()
            
            # Clean up old files (เก็บแค่ 7 วัน)
            self.cleanup_old_files()
            
        except Exception as e:
            self.log(f"Error in auto-save: {str(e)}", "ERROR")

    def cleanup_old_files(self):
        """🧹 ทำความสะอาดไฟล์เก่า"""
        try:
            # สร้างชื่อไฟล์แบบมี timestamp
            timestamp = datetime.now().strftime("%Y%m%d")
            
            # Archive ไฟล์ปัจจุบัน
            if os.path.exists(self.state_file):
                archive_name = f"trading_state_{timestamp}.json"
                if not os.path.exists(archive_name):
                    os.rename(self.state_file, archive_name)
                    self.log(f"📁 State archived as {archive_name}")
            
            # ลบไฟล์เก่าที่เก็บเกิน 7 วัน
            current_time = datetime.now()
            for filename in os.listdir('.'):
                if filename.startswith('trading_state_') and filename.endswith('.json'):
                    try:
                        file_date = datetime.strptime(filename[14:22], "%Y%m%d")
                        if (current_time - file_date).days > 7:
                            os.remove(filename)
                            self.log(f"🗑️ Removed old file: {filename}")
                    except:
                        continue
                        
        except Exception as e:
            self.log(f"Error cleaning up files: {str(e)}", "ERROR")

    def get_memory_status(self) -> dict:
        """📊 สถานะหน่วยความจำ with detailed monitoring"""
        try:
            import psutil
            import sys
            import gc
            
            # Get system memory info
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            system_memory = psutil.virtual_memory()
            
            # Calculate object counts
            object_counts = {
                'position_trackers': len(getattr(self, 'position_tracker', {})),
                'active_hedges': len(getattr(self, 'active_hedges', {})),
                'hedge_pairs': len(getattr(self, 'hedge_pairs', {})),
                'hourly_signals': len(getattr(self, 'hourly_signals', [])),
                'active_positions': len(getattr(self, 'positions', [])),
                'hedge_analytics_entries': len(getattr(self, 'hedge_analytics', {}))
            }
            
            # Calculate memory usage of key data structures
            memory_usage = {
                'position_tracker_size': sys.getsizeof(getattr(self, 'position_tracker', {})),
                'hourly_signals_size': sys.getsizeof(getattr(self, 'hourly_signals', [])),
                'hedge_analytics_size': sys.getsizeof(getattr(self, 'hedge_analytics', {}))
            }
            
            # File status
            file_status = {
                'has_saved_state': os.path.exists(self.state_file),
                'has_positions_backup': os.path.exists(getattr(self, 'positions_file', '')),
                'state_file_size': 0,
                'backup_file_size': 0,
                'last_save': 'Never'
            }
            
            if file_status['has_saved_state']:
                try:
                    file_status['state_file_size'] = os.path.getsize(self.state_file)
                    mod_time = os.path.getmtime(self.state_file)
                    file_status['last_save'] = datetime.fromtimestamp(mod_time).strftime("%H:%M:%S")
                except:
                    pass
            
            if file_status['has_positions_backup']:
                try:
                    file_status['backup_file_size'] = os.path.getsize(getattr(self, 'positions_file', ''))
                except:
                    pass
            
            # Memory health assessment
            memory_health = {
                'process_memory_mb': memory_info.rss / 1024 / 1024,
                'system_memory_percent': system_memory.percent,
                'memory_available_mb': system_memory.available / 1024 / 1024,
                'gc_objects': len(gc.get_objects()),
                'memory_pressure': 'LOW'
            }
            
            # Assess memory pressure
            if memory_health['process_memory_mb'] > 500:  # 500MB
                memory_health['memory_pressure'] = 'HIGH'
            elif memory_health['process_memory_mb'] > 200:  # 200MB
                memory_health['memory_pressure'] = 'MEDIUM'
            
            # Connection health
            connection_health = {
                'mt5_connected': getattr(self, 'mt5_connected', False),
                'circuit_breaker_open': getattr(self, 'circuit_breaker_open', False),
                'connection_failures': getattr(self, 'connection_failures', 0),
                'last_connection_check': 'Never'
            }
            
            if hasattr(self, 'last_mt5_ping') and self.last_mt5_ping:
                connection_health['last_connection_check'] = self.last_mt5_ping.strftime("%H:%M:%S")
            
            status = {
                'timestamp': datetime.now().isoformat(),
                'object_counts': object_counts,
                'memory_usage': memory_usage,
                'file_status': file_status,
                'memory_health': memory_health,
                'connection_health': connection_health
            }
            
            return status
            
        except ImportError:
            # Fallback if psutil is not available
            return self._get_basic_memory_status()
        except Exception as e:
            self.log(f"Error getting memory status: {str(e)}", "ERROR")
            return self._get_basic_memory_status()
    
    def _get_basic_memory_status(self) -> dict:
        """Basic memory status without psutil dependency"""
        try:
            status = {
                'timestamp': datetime.now().isoformat(),
                'object_counts': {
                    'position_trackers': len(getattr(self, 'position_tracker', {})),
                    'active_hedges': len(getattr(self, 'active_hedges', {})),
                    'hedge_pairs': len(getattr(self, 'hedge_pairs', {})),
                    'hourly_signals': len(getattr(self, 'hourly_signals', [])),
                    'active_positions': len(getattr(self, 'positions', []))
                },
                'file_status': {
                    'has_saved_state': os.path.exists(self.state_file),
                    'has_positions_backup': os.path.exists(getattr(self, 'positions_file', '')),
                    'last_save': 'Never'
                },
                'connection_health': {
                    'mt5_connected': getattr(self, 'mt5_connected', False),
                    'circuit_breaker_open': getattr(self, 'circuit_breaker_open', False),
                    'connection_failures': getattr(self, 'connection_failures', 0)
                }
            }
            
            if os.path.exists(self.state_file):
                try:
                    mod_time = os.path.getmtime(self.state_file)
                    status['file_status']['last_save'] = datetime.fromtimestamp(mod_time).strftime("%H:%M:%S")
                except:
                    pass
            
            return status
            
        except Exception as e:
            self.log(f"Error getting basic memory status: {str(e)}", "ERROR")
            return {'error': str(e), 'timestamp': datetime.now().isoformat()}
    
    def perform_memory_management(self):
        """🧹 Comprehensive memory management and cleanup"""
        try:
            self.log("🧹 Starting comprehensive memory management", "INFO")
            
            # Get initial memory status
            initial_status = self.get_memory_status()
            
            # 1. Clean up closed positions
            self.cleanup_closed_positions()
            
            # 2. Clean up old files
            self.cleanup_old_files()
            
            # 3. Garbage collection
            import gc
            initial_objects = len(gc.get_objects())
            collected = gc.collect()
            final_objects = len(gc.get_objects())
            
            if collected > 0:
                self.log(f"🗑️ Garbage collected: {collected} objects freed")
                self.log(f"📊 Objects: {initial_objects} → {final_objects}")
            
            # 4. Validate and clean up data structures
            self._validate_and_clean_data_structures()
            
            # 5. Force save state to ensure data persistence
            self.save_trading_state()
            
            # Get final memory status
            final_status = self.get_memory_status()
            
            # Report memory management results
            if 'object_counts' in initial_status and 'object_counts' in final_status:
                self.log("📊 Memory Management Results:")
                for key in initial_status['object_counts']:
                    initial_count = initial_status['object_counts'].get(key, 0)
                    final_count = final_status['object_counts'].get(key, 0)
                    if initial_count != final_count:
                        self.log(f"   {key}: {initial_count} → {final_count}")
            
            self.log("✅ Memory management completed", "INFO")
            
        except Exception as e:
            self.log(f"❌ Error in memory management: {str(e)}", "ERROR")
    
    def _validate_and_clean_data_structures(self):
        """Validate and clean up data structures"""
        try:
            # Validate position_tracker
            if hasattr(self, 'position_tracker') and isinstance(self.position_tracker, dict):
                invalid_trackers = []
                for ticket, tracker in self.position_tracker.items():
                    if not isinstance(tracker, dict):
                        invalid_trackers.append(ticket)
                        continue
                    
                    # Ensure required fields exist
                    required_fields = ['birth_time', 'initial_price', 'max_profit', 'min_profit']
                    for field in required_fields:
                        if field not in tracker:
                            if field == 'birth_time':
                                tracker[field] = datetime.now()
                            elif field in ['initial_price', 'max_profit', 'min_profit']:
                                tracker[field] = 0.0
                
                for ticket in invalid_trackers:
                    del self.position_tracker[ticket]
                    
                if invalid_trackers:
                    self.log(f"🧹 Removed {len(invalid_trackers)} invalid position trackers")
            
            # Validate active_hedges
            if hasattr(self, 'active_hedges') and isinstance(self.active_hedges, dict):
                invalid_hedges = []
                for key, hedge_list in self.active_hedges.items():
                    if not isinstance(hedge_list, list):
                        invalid_hedges.append(key)
                
                for key in invalid_hedges:
                    del self.active_hedges[key]
                    
                if invalid_hedges:
                    self.log(f"🧹 Removed {len(invalid_hedges)} invalid hedge entries")
            
            # Validate hedge_pairs
            if hasattr(self, 'hedge_pairs') and isinstance(self.hedge_pairs, dict):
                invalid_pairs = []
                for key, pair_data in self.hedge_pairs.items():
                    if not isinstance(pair_data, dict):
                        invalid_pairs.append(key)
                
                for key in invalid_pairs:
                    del self.hedge_pairs[key]
                    
                if invalid_pairs:
                    self.log(f"🧹 Removed {len(invalid_pairs)} invalid hedge pairs")
            
            # Validate numeric fields
            numeric_fields = [
                'total_signals', 'successful_signals',
                'total_redirects', 'successful_redirects', 'redirect_profit_captured',
                'total_pair_closes', 'successful_pair_closes', 'pair_profit_captured',
                'total_group_closes', 'group_profit_captured', 'portfolio_health',
                'base_lot', 'connection_failures'
            ]
            
            for field in numeric_fields:
                if hasattr(self, field):
                    value = getattr(self, field)
                    if not isinstance(value, (int, float)):
                        try:
                            setattr(self, field, float(value) if '.' in str(value) else int(value))
                        except (ValueError, TypeError):
                            # Set to safe default
                            if 'ratio' in field or 'percent' in field or field == 'portfolio_health':
                                setattr(self, field, 100.0)
                            elif 'lot' in field:
                                setattr(self, field, 0.01)
                            else:
                                setattr(self, field, 0)
                            self.log(f"Reset invalid {field} to default", "WARNING")
            
        except Exception as e:
            self.log(f"Error validating data structures: {str(e)}", "ERROR")
    
    def perform_system_health_check(self) -> dict:
        """🏥 Comprehensive system health monitoring"""
        try:
            health_report = {
                'timestamp': datetime.now().isoformat(),
                'overall_status': 'HEALTHY',
                'alerts': [],
                'warnings': [],
                'metrics': {}
            }
            
            # 1. Connection Health
            connection_health = {
                'mt5_connected': self.mt5_connected,
                'circuit_breaker_open': self.circuit_breaker_open,
                'connection_failures': self.connection_failures,
                'last_ping_success': self.last_mt5_ping is not None
            }
            
            if not self.mt5_connected:
                health_report['alerts'].append("MT5 not connected")
                health_report['overall_status'] = 'CRITICAL'
            elif self.circuit_breaker_open:
                health_report['alerts'].append("Circuit breaker is open")
                health_report['overall_status'] = 'WARNING'
            elif self.connection_failures > 0:
                health_report['warnings'].append(f"Recent connection failures: {self.connection_failures}")
            
            # 2. Memory Health
            memory_status = self.get_memory_status()
            if 'memory_health' in memory_status:
                memory_health = memory_status['memory_health']
                if memory_health.get('memory_pressure') == 'HIGH':
                    health_report['alerts'].append("High memory usage detected")
                    if health_report['overall_status'] == 'HEALTHY':
                        health_report['overall_status'] = 'WARNING'
                elif memory_health.get('memory_pressure') == 'MEDIUM':
                    health_report['warnings'].append("Medium memory usage")
            
            # 3. Performance Metrics
            uptime_seconds = (datetime.now() - self.performance_metrics['uptime_start']).total_seconds()
            cycles_per_hour = (self.performance_metrics['cycles_completed'] / max(1, uptime_seconds)) * 3600
            
            error_rate = 0
            if self.performance_metrics['successful_operations'] + self.performance_metrics['failed_operations'] > 0:
                total_ops = self.performance_metrics['successful_operations'] + self.performance_metrics['failed_operations']
                error_rate = (self.performance_metrics['failed_operations'] / total_ops) * 100
            
            performance_health = {
                'uptime_hours': uptime_seconds / 3600,
                'cycles_completed': self.performance_metrics['cycles_completed'],
                'cycles_per_hour': cycles_per_hour,
                'error_rate_percent': error_rate,
                'avg_execution_time': self.performance_metrics.get('average_execution_time', 0)
            }
            
            if error_rate > 20:  # More than 20% error rate
                health_report['alerts'].append(f"High error rate: {error_rate:.1f}%")
                health_report['overall_status'] = 'CRITICAL'
            elif error_rate > 10:  # More than 10% error rate
                health_report['warnings'].append(f"Elevated error rate: {error_rate:.1f}%")
                if health_report['overall_status'] == 'HEALTHY':
                    health_report['overall_status'] = 'WARNING'
            
            # 4. Trading Health
            trading_health = {
                'trading_active': self.trading_active,
                'active_positions': len(self.positions) if hasattr(self, 'positions') else 0,
                'success_rate': 0
            }
            
            if self.total_signals > 0:
                trading_health['success_rate'] = (self.successful_signals / self.total_signals) * 100
            
            if self.trading_active and trading_health['success_rate'] < 30:  # Less than 30% success
                health_report['warnings'].append(f"Low trading success rate: {trading_health['success_rate']:.1f}%")
                if health_report['overall_status'] == 'HEALTHY':
                    health_report['overall_status'] = 'WARNING'
            
            # 5. Data Integrity Health
            data_health = {
                'position_trackers': len(self.position_tracker) if hasattr(self, 'position_tracker') else 0,
                'state_file_exists': os.path.exists(self.state_file),
                'backup_file_exists': os.path.exists(getattr(self, 'positions_file', '')),
                'recent_save_success': True  # We'll track this
            }
            
            if not data_health['state_file_exists']:
                health_report['warnings'].append("No state file found")
            
            # Compile final report
            health_report['metrics'] = {
                'connection': connection_health,
                'performance': performance_health,
                'trading': trading_health,
                'data': data_health
            }
            
            # Add to alerts history
            if health_report['alerts'] or health_report['warnings']:
                alert_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'status': health_report['overall_status'],
                    'alerts': health_report['alerts'].copy(),
                    'warnings': health_report['warnings'].copy()
                }
                self.system_alerts.append(alert_entry)
                
                # Keep only recent alerts
                if len(self.system_alerts) > self.max_alerts:
                    self.system_alerts = self.system_alerts[-self.max_alerts:]
            
            # Log health status
            if health_report['overall_status'] == 'CRITICAL':
                self.log(f"🚨 SYSTEM HEALTH: CRITICAL - {', '.join(health_report['alerts'])}", "ERROR")
            elif health_report['overall_status'] == 'WARNING':
                self.log(f"⚠️ SYSTEM HEALTH: WARNING - {', '.join(health_report['warnings'])}", "WARNING")
            elif self.verbose_logging:
                self.log("✅ System health check: All systems normal", "INFO")
            
            self.last_health_check = datetime.now()
            return health_report
            
        except Exception as e:
            self.log(f"Error in system health check: {str(e)}", "ERROR")
            return {
                'timestamp': datetime.now().isoformat(),
                'overall_status': 'ERROR',
                'alerts': [f"Health check failed: {str(e)}"],
                'metrics': {}
            }
    
    def update_performance_metrics(self, operation_success: bool, execution_time: float = None):
        """Update performance tracking metrics"""
        try:
            self.performance_metrics['cycles_completed'] += 1
            
            if operation_success:
                self.performance_metrics['successful_operations'] += 1
            else:
                self.performance_metrics['failed_operations'] += 1
                # Track recent errors
                error_entry = {
                    'timestamp': datetime.now().isoformat(),
                    'cycle': self.performance_metrics['cycles_completed']
                }
                self.performance_metrics['recent_errors'].append(error_entry)
                
                # Keep only last 100 errors
                if len(self.performance_metrics['recent_errors']) > 100:
                    self.performance_metrics['recent_errors'] = self.performance_metrics['recent_errors'][-100:]
            
            # Track execution times
            if execution_time is not None:
                self.performance_metrics['execution_times'].append(execution_time)
                
                # Keep only last 1000 execution times
                if len(self.performance_metrics['execution_times']) > 1000:
                    self.performance_metrics['execution_times'] = self.performance_metrics['execution_times'][-1000:]
                
                # Update average
                if self.performance_metrics['execution_times']:
                    self.performance_metrics['average_execution_time'] = sum(self.performance_metrics['execution_times']) / len(self.performance_metrics['execution_times'])
            
            # Update error rate
            total_ops = self.performance_metrics['successful_operations'] + self.performance_metrics['failed_operations']
            if total_ops > 0:
                self.performance_metrics['error_rate'] = (self.performance_metrics['failed_operations'] / total_ops) * 100
            
        except Exception as e:
            self.log(f"Error updating performance metrics: {str(e)}", "ERROR")
    
    def get_system_diagnostics(self) -> dict:
        """🔍 Get comprehensive system diagnostics"""
        try:
            diagnostics = {
                'timestamp': datetime.now().isoformat(),
                'system_info': {},
                'trading_info': {},
                'memory_info': {},
                'connection_info': {},
                'recent_alerts': self.system_alerts[-10:] if self.system_alerts else [],
                'performance_summary': {}
            }
            
            # System information
            try:
                import platform
                diagnostics['system_info'] = {
                    'platform': platform.platform(),
                    'python_version': platform.python_version(),
                    'architecture': platform.architecture()[0]
                }
            except:
                diagnostics['system_info'] = {'error': 'Could not retrieve system info'}
            
            # Trading information
            diagnostics['trading_info'] = {
                'trading_active': self.trading_active,
                'mt5_connected': self.mt5_connected,
                'symbol': self.symbol,
                'base_lot': self.base_lot,
                'active_positions': len(self.positions) if hasattr(self, 'positions') else 0,
                'total_signals': self.total_signals,
                'successful_signals': self.successful_signals,
                'success_rate': (self.successful_signals / max(1, self.total_signals)) * 100
            }
            
            # Memory information
            diagnostics['memory_info'] = self.get_memory_status()
            
            # Connection information
            diagnostics['connection_info'] = {
                'mt5_connected': self.mt5_connected,
                'circuit_breaker_open': self.circuit_breaker_open,
                'connection_failures': self.connection_failures,
                'last_ping': self.last_mt5_ping.isoformat() if self.last_mt5_ping else None,
                'last_health_check': self.last_health_check.isoformat() if self.last_health_check else None
            }
            
            # Performance summary
            uptime_seconds = (datetime.now() - self.performance_metrics['uptime_start']).total_seconds()
            diagnostics['performance_summary'] = {
                'uptime_hours': uptime_seconds / 3600,
                'cycles_completed': self.performance_metrics['cycles_completed'],
                'error_rate': self.performance_metrics['error_rate'],
                'average_execution_time': self.performance_metrics['average_execution_time'],
                'successful_operations': self.performance_metrics['successful_operations'],
                'failed_operations': self.performance_metrics['failed_operations']
            }
            
            return diagnostics
            
        except Exception as e:
            self.log(f"Error getting diagnostics: {str(e)}", "ERROR")
            return {
                'timestamp': datetime.now().isoformat(),
                'error': str(e)
            }

    def emergency_state_recovery(self):
        """🚨 กู้คืนสถานะฉุกเฉิน"""
        try:
            self.log("🚨 EMERGENCY RECOVERY MODE", "WARNING")
            
            # พยายามโหลดจากไฟล์ backup
            success = self.load_trading_state()
            
            if success:
                self.log("✅ Emergency recovery successful")
                
                # ตรวจสอบและซิงค์กับ MT5
                if self.mt5_connected:
                    self.sync_with_mt5_positions()
                    
            else:
                self.log("❌ Emergency recovery failed - starting fresh", "ERROR")
                self.reset_to_defaults()
                
        except Exception as e:
            self.log(f"❌ Critical error in emergency recovery: {str(e)}", "ERROR")
            self.reset_to_defaults()

    def sync_with_mt5_positions(self):
        """🔄 ซิงค์ข้อมูลกับ positions จริงใน MT5"""
        try:
            if not self.mt5_connected or not MT5_AVAILABLE or not mt5:
                return
            
            # ดึง positions จริงจาก MT5
            mt5_positions = mt5.positions_get(symbol=self.symbol)
            if mt5_positions is None:
                mt5_positions = []
            
            mt5_tickets = {pos.ticket for pos in mt5_positions}
            tracked_tickets = set(self.position_tracker.keys())
            
            # ลบ tracker ที่ไม่มี position จริงแล้ว
            closed_tickets = tracked_tickets - mt5_tickets
            for ticket in closed_tickets:
                if str(ticket) in self.position_tracker:
                    del self.position_tracker[str(ticket)]
                elif int(ticket) in self.position_tracker:
                    del self.position_tracker[int(ticket)]
            
            # เพิ่ม tracker สำหรับ positions ใหม่
            new_tickets = mt5_tickets - tracked_tickets
            for pos in mt5_positions:
                if pos.ticket in new_tickets:
                    self.position_tracker[pos.ticket] = {
                        'birth_time': datetime.now(),
                        'initial_price': pos.price_open,
                        'max_profit': pos.profit,
                        'min_profit': pos.profit,
                        'role_history': ["UNKNOWN"],
                        'efficiency_history': ["fair"],
                        'peak_profit_per_lot': pos.profit / pos.volume if pos.volume > 0 else 0,
                        'contribution_score': 0.0,
                        'hold_score': 50,
                        'adaptive_target': self.profit_harvest_threshold
                    }
            
            self.log(f"🔄 Synced with MT5: {len(closed_tickets)} removed, {len(new_tickets)} added")
            
        except Exception as e:
            self.log(f"Error syncing with MT5: {str(e)}", "ERROR")

    def reset_to_defaults(self):
        """🔄 รีเซ็ตเป็นค่าเริ่มต้น"""
        try:
            self.position_tracker = {}
            self.active_hedges = {}
            self.hedge_pairs = {}
            self.hourly_signals = []
            
            # รีเซ็ต stats (เก็บแค่วันนี้)
            self.total_redirects = 0
            self.successful_redirects = 0
            self.redirect_profit_captured = 0.0
            self.last_redirect_time = None
            
            self.total_pair_closes = 0
            self.successful_pair_closes = 0
            self.pair_profit_captured = 0.0
            self.total_group_closes = 0
            self.group_profit_captured = 0.0
            
            self.portfolio_health = 100.0
            
            self.log("🔄 System reset to defaults")
            
        except Exception as e:
            self.log(f"Error resetting to defaults: {str(e)}", "ERROR")

    def analyze_hg_necessity(self, position: Position) -> dict:
        """🧠 วิเคราะห์ความจำเป็นในการออก HG แบบฉลาด"""
        try:
            analysis = {
                'should_hedge': False,
                'confidence_score': 0,
                'strategy': None,
                'volume_recommendation': 0.0,
                'timing_recommendation': 'IMMEDIATE',
                'risk_factors': [],
                'opportunity_factors': [],
                'decision_reasoning': []
            }
            
            # 1. Basic Loss Analysis
            loss_analysis = self.analyze_position_loss_severity(position)
            analysis['risk_factors'].extend(loss_analysis['factors'])
            
            # 2. Market Context Analysis
            market_context = self.analyze_market_context_for_hg(position)
            analysis['opportunity_factors'].extend(market_context['factors'])
            
            # 3. Portfolio Impact Analysis
            portfolio_impact = self.analyze_portfolio_impact_of_hg(position)
            
            # 4. Timing Analysis
            timing_analysis = self.analyze_hg_timing_opportunity(position)
            
            # 5. Pattern Recognition
            pattern_analysis = self.analyze_historical_hg_patterns(position)
            
            # 6. Calculate Composite Score
            composite_score = self.calculate_hg_composite_score(
                loss_analysis, market_context, portfolio_impact, 
                timing_analysis, pattern_analysis
            )
            
            analysis['confidence_score'] = composite_score['total_score']
            analysis['decision_reasoning'] = composite_score['reasoning']
            
            # 7. Final Decision
            if composite_score['total_score'] >= self.hg_decision_threshold:
                analysis['should_hedge'] = True
                analysis['strategy'] = self.select_optimal_hg_strategy(position, composite_score)
                analysis['volume_recommendation'] = self.calculate_smart_hg_volume(position, composite_score)
                analysis['timing_recommendation'] = timing_analysis.get('best_timing', 'IMMEDIATE')
            
            return analysis
            
        except Exception as e:
            self.log(f"Error analyzing HG necessity: {str(e)}", "ERROR")
            return analysis

    def analyze_position_loss_severity(self, position: Position) -> dict:
        """📉 วิเคราะห์ความรุนแรงของการขาดทุน"""
        try:
            analysis = {
                'severity_level': 'LOW',
                'loss_amount': abs(position.profit),
                'loss_percentage': 0,
                'time_in_loss': 0,
                'factors': [],
                'score': 0
            }
            
            loss_amount = abs(position.profit)
            
            # คำนวณ % loss
            if position.volume > 0:
                estimated_margin = position.volume * 1000
                analysis['loss_percentage'] = (loss_amount / estimated_margin) * 100
            
            # วิเคราะห์เวลาที่ติดลบ
            if position.ticket in self.position_tracker:
                try:
                    birth_time = safe_parse_datetime(self.position_tracker[position.ticket]['birth_time'])
                    loss_duration = (datetime.now() - birth_time).total_seconds() / 3600
                    analysis['time_in_loss'] = loss_duration
                except Exception as time_error:
                    self.log(f"Warning: Could not calculate loss duration for position {position.ticket}: {time_error}", "WARNING")
                    analysis['time_in_loss'] = 0
            
            # ประเมินความรุนแรง
            if loss_amount >= 500:
                analysis['severity_level'] = 'CRITICAL'
                analysis['score'] += 40
                analysis['factors'].append(f"Critical loss: ${loss_amount:.0f}")
            elif loss_amount >= 250:
                analysis['severity_level'] = 'HIGH'
                analysis['score'] += 30
                analysis['factors'].append(f"High loss: ${loss_amount:.0f}")
            elif loss_amount >= 100:
                analysis['severity_level'] = 'MEDIUM'
                analysis['score'] += 20
                analysis['factors'].append(f"Medium loss: ${loss_amount:.0f}")
            else:
                analysis['severity_level'] = 'LOW'
                analysis['score'] += 5
            
            # Bonus สำหรับ loss % สูง
            if analysis['loss_percentage'] > 20:
                analysis['score'] += 25
                analysis['factors'].append(f"High loss %: {analysis['loss_percentage']:.1f}%")
            elif analysis['loss_percentage'] > 10:
                analysis['score'] += 15
                analysis['factors'].append(f"Moderate loss %: {analysis['loss_percentage']:.1f}%")
            
            # Penalty สำหรับ loss เล็กน้อย
            if loss_amount < self.min_loss_threshold_for_hg:
                analysis['score'] = max(0, analysis['score'] - 20)
                analysis['factors'].append("Loss too small for HG")
            
            return analysis
            
        except Exception as e:
            self.log(f"Error analyzing loss severity: {str(e)}", "ERROR")
            return {'severity_level': 'LOW', 'score': 0, 'factors': []}

    def analyze_market_context_for_hg(self, position: Position) -> dict:
        """🌍 วิเคราะห์บริบทตลาดสำหรับการตัดสินใจ HG"""
        try:
            context = {
                'market_trend': 'NEUTRAL',
                'volatility_level': 'NORMAL',
                'momentum_strength': 0.5,
                'reversal_probability': 0.5,
                'factors': [],
                'score': 0
            }
            
            market_data = self.get_market_data()
            if market_data is None:
                return context
            
            # 1. Trend Analysis
            trend_strength = self.calculate_trend_strength(market_data)
            if trend_strength > 0.7:
                context['market_trend'] = 'STRONG_UP'
                context['score'] += 15
                context['factors'].append("Strong uptrend detected")
            elif trend_strength < 0.3:
                context['market_trend'] = 'STRONG_DOWN'
                context['score'] += 15
                context['factors'].append("Strong downtrend detected")
            else:
                context['market_trend'] = 'SIDEWAYS'
                context['score'] += 25  # Sideways ดีสำหรับ HG
                context['factors'].append("Sideways market - good for HG")
            
            # 2. Volatility Analysis
            if hasattr(self, 'recent_volatility'):
                if self.recent_volatility > 2.0:
                    context['volatility_level'] = 'HIGH'
                    context['score'] += 20
                    context['factors'].append("High volatility - HG opportunity")
                elif self.recent_volatility < 0.5:
                    context['volatility_level'] = 'LOW'
                    context['score'] += 5
                    context['factors'].append("Low volatility - limited HG benefit")
                else:
                    context['volatility_level'] = 'NORMAL'
                    context['score'] += 10
            
            # 3. Momentum vs Position Direction
            momentum = self.calculate_momentum_score(market_data)
            context['momentum_strength'] = momentum
            
            if position.type == "BUY" and momentum < 0.3:
                context['score'] += 20
                context['factors'].append("BUY against bearish momentum - HG recommended")
            elif position.type == "SELL" and momentum > 0.7:
                context['score'] += 20
                context['factors'].append("SELL against bullish momentum - HG recommended")
            
            # 4. Reversal Pattern Detection
            reversal_score = self.detect_reversal_patterns(market_data, position)
            context['reversal_probability'] = reversal_score
            if reversal_score > 0.7:
                context['score'] += 15
                context['factors'].append("High reversal probability detected")
            
            return context
            
        except Exception as e:
            self.log(f"Error analyzing market context for HG: {str(e)}", "ERROR")
            return context

    def analyze_portfolio_impact_of_hg(self, position: Position) -> dict:
        """💼 วิเคราะห์ผลกระทบต่อ portfolio จากการทำ HG"""
        try:
            impact = {
                'margin_impact': 'LOW',
                'balance_impact': 'NEUTRAL',
                'risk_reduction': 0,
                'recovery_potential': 0,
                'score': 0,
                'factors': []
            }
            
            # 1. Margin Usage Analysis
            account_info = mt5.account_info()
            if account_info and account_info.margin > 0:
                current_margin_level = (account_info.equity / account_info.margin) * 100
                
                # Estimate margin after HG
                hedge_volume = self.calculate_hedge_volume(position, "IMMEDIATE")
                estimated_additional_margin = hedge_volume * 1000  # ประมาณการ
                new_margin_level = (account_info.equity / (account_info.margin + estimated_additional_margin)) * 100
                
                if new_margin_level > 200:
                    impact['margin_impact'] = 'LOW'
                    impact['score'] += 15
                elif new_margin_level > 150:
                    impact['margin_impact'] = 'MEDIUM'
                    impact['score'] += 10
                else:
                    impact['margin_impact'] = 'HIGH'
                    impact['score'] += 0
                    impact['factors'].append(f"High margin impact: {new_margin_level:.0f}%")
            
            # 2. Portfolio Balance Impact
            total_volume = self.buy_volume + self.sell_volume
            if total_volume > 0:
                current_buy_ratio = self.buy_volume / total_volume
                
                # 🆕 กำหนด hedge_volume ก่อนใช้งาน
                hedge_volume = self.calculate_hedge_volume(position, "IMMEDIATE")
                
                # Calculate balance after HG
                if position.type == "BUY":
                    new_sell_volume = self.sell_volume + hedge_volume
                    new_buy_ratio = self.buy_volume / (total_volume + hedge_volume)
                else:
                    new_buy_volume = self.buy_volume + hedge_volume
                    new_buy_ratio = new_buy_volume / (total_volume + hedge_volume)
                
                current_imbalance = abs(current_buy_ratio - 0.5)
                new_imbalance = abs(new_buy_ratio - 0.5)
                
                if new_imbalance < current_imbalance:
                    impact['balance_impact'] = 'POSITIVE'
                    impact['score'] += 15
                    impact['factors'].append("HG improves portfolio balance")
                elif new_imbalance == current_imbalance:
                    impact['balance_impact'] = 'NEUTRAL'
                    impact['score'] += 5
                else:
                    impact['balance_impact'] = 'NEGATIVE'
                    impact['score'] -= 10
                    impact['factors'].append("HG worsens portfolio balance")
            
            # 3. Risk Reduction Calculation
            position_risk = abs(position.profit) / max(1, position.volume * 1000) * 100
            if position_risk > 15:
                impact['risk_reduction'] = 80
                impact['score'] += 25
                impact['factors'].append(f"High risk reduction: {position_risk:.1f}%")
            elif position_risk > 10:
                impact['risk_reduction'] = 60
                impact['score'] += 15
            else:
                impact['risk_reduction'] = 30
                impact['score'] += 5
            
            # 4. Recovery Potential
            if self.portfolio_health < 50:
                impact['recovery_potential'] = 80
                impact['score'] += 20
                impact['factors'].append("High recovery potential in weak portfolio")
            elif self.portfolio_health < 70:
                impact['recovery_potential'] = 60
                impact['score'] += 10
            else:
                impact['recovery_potential'] = 40
                impact['score'] += 5
            
            return impact
            
        except Exception as e:
            self.log(f"Error analyzing portfolio impact: {str(e)}", "ERROR")
            return impact

    def analyze_hg_timing_opportunity(self, position: Position) -> dict:
        """⏰ วิเคราะห์จังหวะเวลาที่เหมาะสมสำหรับ HG"""
        try:
            timing = {
                'best_timing': 'IMMEDIATE',
                'confidence': 0.5,
                'wait_recommendation': False,
                'optimal_delay_minutes': 0,
                'score': 0,
                'factors': []
            }
            
            # 1. Position Age Analysis
            age_hours = 0
            if position.ticket in self.position_tracker:
                try:
                    birth_time = safe_parse_datetime(self.position_tracker[position.ticket]['birth_time'])
                    age_hours = (datetime.now() - birth_time).total_seconds() / 3600
                except Exception as age_error:
                    self.log(f"Warning: Could not calculate position age for timing analysis: {age_error}", "WARNING")
                    age_hours = 0
            
            if age_hours < 1:
                timing['best_timing'] = 'WAIT'
                timing['wait_recommendation'] = True
                timing['optimal_delay_minutes'] = 30
                timing['score'] += 5
                timing['factors'].append("Position too young - wait for development")
            elif age_hours > 12:
                timing['best_timing'] = 'IMMEDIATE'
                timing['score'] += 20
                timing['factors'].append("Position mature - immediate HG recommended")
            else:
                timing['best_timing'] = 'IMMEDIATE'
                timing['score'] += 15
            
            # 2. Market Session Analysis
            current_hour = datetime.now().hour
            if 22 <= current_hour or current_hour <= 2:  # ตลาดหลัก
                timing['score'] += 15
                timing['factors'].append("Major market session - optimal HG timing")
            elif 7 <= current_hour <= 9 or 14 <= current_hour <= 16:  # ตลาดรอง
                timing['score'] += 10
                timing['factors'].append("Active market session - good HG timing")
            else:
                timing['score'] += 5
                timing['factors'].append("Quiet session - limited HG effectiveness")
            
            # 3. Recent HG Activity
            if hasattr(self, 'last_hedge_time'):
                if self.last_hedge_time:
                    minutes_since = (datetime.now() - self.last_hedge_time).total_seconds() / 60
                    if minutes_since < self.hg_cooldown_minutes:
                        timing['best_timing'] = 'WAIT'
                        timing['wait_recommendation'] = True
                        timing['optimal_delay_minutes'] = self.hg_cooldown_minutes - int(minutes_since)
                        timing['score'] -= 15
                        timing['factors'].append(f"HG cooldown: wait {timing['optimal_delay_minutes']} minutes")
            
            # 4. Market Volatility Timing
            if hasattr(self, 'recent_volatility'):
                if self.recent_volatility > 2.5:
                    timing['confidence'] = 0.8
                    timing['score'] += 10
                    timing['factors'].append("High volatility - excellent HG timing")
                elif self.recent_volatility < 0.3:
                    timing['confidence'] = 0.3
                    timing['score'] -= 5
                    timing['factors'].append("Low volatility - poor HG timing")
            
            # 5. Concurrent HG Limit Check
            active_hg_count = len(self.active_hedges)
            if active_hg_count >= self.hg_max_concurrent:
                timing['best_timing'] = 'WAIT'
                timing['wait_recommendation'] = True
                timing['score'] -= 20
                timing['factors'].append(f"Max concurrent HG reached: {active_hg_count}/{self.hg_max_concurrent}")
            
            timing['confidence'] = max(0.1, min(1.0, timing['score'] / 50))
            
            return timing
            
        except Exception as e:
            self.log(f"Error analyzing HG timing: {str(e)}", "ERROR")
            return timing

    def analyze_historical_hg_patterns(self, position: Position) -> dict:
        """📚 วิเคราะห์รูปแบบประสบการณ์ HG ในอดีต"""
        try:
            patterns = {
                'similar_situation_success_rate': 0.5,
                'recommended_strategy': 'IMMEDIATE',
                'confidence_from_history': 0.5,
                'score': 0,
                'factors': []
            }
            
            if not self.hg_pattern_learning:
                patterns['score'] = 10  # Base score
                return patterns
            
            # 1. Analyze similar positions from history
            similar_successes = 0
            similar_total = 0
            
            for record in self.hg_performance_history:
                # Check if similar situation
                if (record.get('original_type') == position.type and
                    abs(record.get('loss_amount', 0) - abs(position.profit)) < 100):
                    similar_total += 1
                    if record.get('final_result') == 'SUCCESS':
                        similar_successes += 1
            
            if similar_total > 0:
                patterns['similar_situation_success_rate'] = similar_successes / similar_total
                patterns['confidence_from_history'] = min(1.0, similar_total / 10)  # More confident with more data
                
                if patterns['similar_situation_success_rate'] > 0.7:
                    patterns['score'] += 20
                    patterns['factors'].append(f"High historical success: {patterns['similar_situation_success_rate']:.1%}")
                elif patterns['similar_situation_success_rate'] > 0.5:
                    patterns['score'] += 10
                    patterns['factors'].append(f"Moderate historical success: {patterns['similar_situation_success_rate']:.1%}")
                else:
                    patterns['score'] += 0
                    patterns['factors'].append(f"Low historical success: {patterns['similar_situation_success_rate']:.1%}")
            
            # 2. Strategy recommendation based on patterns
            if patterns['similar_situation_success_rate'] > 0.6:
                patterns['recommended_strategy'] = 'IMMEDIATE'
            else:
                patterns['recommended_strategy'] = 'SMART_RECOVERY'
            
            # 3. Check for known failure patterns
            current_market_data = self.get_market_data()
            if current_market_data is not None and self.avoid_bad_timing:
                if self.matches_failure_pattern(position, current_market_data):
                    patterns['score'] -= 15
                    patterns['factors'].append("Matches historical failure pattern")
            
            return patterns
            
        except Exception as e:
            self.log(f"Error analyzing HG patterns: {str(e)}", "ERROR")
            return patterns

    def calculate_hg_composite_score(self, loss_analysis: dict, market_context: dict, 
                                   portfolio_impact: dict, timing_analysis: dict, 
                                   pattern_analysis: dict) -> dict:
        """🧮 คำนวณคะแนนรวมสำหรับการตัดสินใจ HG"""
        try:
            composite = {
                'total_score': 0,
                'reasoning': [],
                'confidence_level': 'LOW',
                'risk_assessment': 'MEDIUM'
            }
            
            # Weight factors
            weights = {
                'loss_severity': 0.3,
                'market_context': self.market_context_weight,
                'portfolio_impact': 0.25,
                'timing': 0.15,
                'historical_patterns': 0.1
            }
            
            # Calculate weighted score
            scores = {
                'loss_severity': loss_analysis.get('score', 0),
                'market_context': market_context.get('score', 0),
                'portfolio_impact': portfolio_impact.get('score', 0),
                'timing': timing_analysis.get('score', 0),
                'historical_patterns': pattern_analysis.get('score', 0)
            }
            
            weighted_total = 0
            for factor, score in scores.items():
                weighted_score = score * weights[factor]
                weighted_total += weighted_score
                composite['reasoning'].append(f"{factor}: {score:.0f} pts (weight: {weights[factor]:.1%}) = {weighted_score:.1f}")
            
            composite['total_score'] = weighted_total
            
            # Determine confidence level
            if weighted_total >= 80:
                composite['confidence_level'] = 'VERY_HIGH'
                composite['risk_assessment'] = 'LOW'
            elif weighted_total >= 70:
                composite['confidence_level'] = 'HIGH'
                composite['risk_assessment'] = 'LOW'
            elif weighted_total >= 60:
                composite['confidence_level'] = 'MEDIUM'
                composite['risk_assessment'] = 'MEDIUM'
            elif weighted_total >= 40:
                composite['confidence_level'] = 'LOW'
                composite['risk_assessment'] = 'HIGH'
            else:
                composite['confidence_level'] = 'VERY_LOW'
                composite['risk_assessment'] = 'VERY_HIGH'
            
            # Add bonus/penalty factors
            if self.dynamic_risk_assessment:
                self.apply_dynamic_risk_adjustments(composite, portfolio_impact)
            
            return composite
            
        except Exception as e:
            self.log(f"Error calculating HG composite score: {str(e)}", "ERROR")
            return {'total_score': 0, 'reasoning': ['Error in calculation'], 'confidence_level': 'LOW'}

    def select_optimal_hg_strategy(self, position: Position, composite_score: dict) -> str:
        """🎯 เลือกกลยุทธ์ HG ที่เหมาะสมที่สุด"""
        try:
            if self.hg_strategy_selection == "AUTO_ADAPTIVE":
                score = composite_score['total_score']
                confidence = composite_score['confidence_level']
                
                if score >= 85 and confidence in ['HIGH', 'VERY_HIGH']:
                    return "IMMEDIATE_FULL"
                elif score >= 75:
                    return "IMMEDIATE"
                elif score >= 65:
                    return "SMART_RECOVERY"
                elif score >= 55:
                    return "PARTIAL_HEDGE"
                else:
                    return "WAIT_AND_MONITOR"
            
            else:
                # Use predefined strategy
                return self.hg_strategy_selection
                
        except Exception as e:
            self.log(f"Error selecting HG strategy: {str(e)}", "ERROR")
            return "IMMEDIATE"

    def calculate_smart_hg_volume(self, position: Position, composite_score: dict) -> float:
        """📐 คำนวณ volume HG อย่างชาญฉลาด"""
        try:
            base_volume = position.volume
            score = composite_score['total_score']
            confidence = composite_score['confidence_level']
            
            # Base ratio calculation
            if confidence == 'VERY_HIGH':
                ratio = 1.3  # 130% coverage
            elif confidence == 'HIGH':
                ratio = 1.2  # 120% coverage
            elif confidence == 'MEDIUM':
                ratio = 1.0  # 100% coverage
            else:
                ratio = 0.8  # 80% coverage
            
            # Adjust based on score
            if score >= 90:
                ratio *= 1.1
            elif score <= 60:
                ratio *= 0.9
            
            # Portfolio health adjustment
            if self.portfolio_health < 30:
                ratio *= 1.2  # More aggressive in crisis
            elif self.portfolio_health > 80:
                ratio *= 0.9  # More conservative when healthy
            
            # Calculate final volume
            hg_volume = base_volume * ratio
            
            # Apply limits
            hg_volume = max(self.min_hedge_volume, min(self.max_hedge_volume, hg_volume))
            hg_volume = round(hg_volume, 2)
            
            return hg_volume
            
        except Exception as e:
            self.log(f"Error calculating smart HG volume: {str(e)}", "ERROR")
            return self.min_hedge_volume

    def detect_reversal_patterns(self, market_data: DataFrame, position: Position) -> float:
        """🔄 ตรวจจับรูปแบบการเปลี่ยนทิศทางของตลาด"""
        try:
            if market_data is None or len(market_data) < 5:
                return 0.5
            
            reversal_score = 0.0
            
            last_5 = market_data.tail(5)
            
            # 1. Candlestick pattern analysis
            if position.type == "BUY":
                # Look for bullish reversal patterns
                red_count = (last_5['is_green'] == False).sum()
                if red_count >= 3:  # Many red candles, potential reversal
                    reversal_score += 0.3
                
                # Check for hammer/doji patterns
                for idx, row in last_5.iterrows():
                    if row['body_ratio'] < 3 and row['total_range'] > 0.3:  # Small body, long wicks
                        reversal_score += 0.1
            
            else:  # SELL position
                # Look for bearish reversal patterns
                green_count = last_5['is_green'].sum()
                if green_count >= 3:  # Many green candles, potential reversal
                    reversal_score += 0.3
                
                # Check for shooting star/doji patterns
                for idx, row in last_5.iterrows():
                    if row['body_ratio'] < 3 and row['total_range'] > 0.3:
                        reversal_score += 0.1
            
            # 2. Momentum divergence
            momentum = self.calculate_momentum_score(market_data)
            if position.type == "BUY" and momentum > 0.6:
                reversal_score += 0.2
            elif position.type == "SELL" and momentum < 0.4:
                reversal_score += 0.2
            
            # 3. Volatility spike (often precedes reversal)
            if hasattr(self, 'recent_volatility') and self.recent_volatility > 2.0:
                reversal_score += 0.2
            
            return min(1.0, reversal_score)
            
        except Exception as e:
            self.log(f"Error detecting reversal patterns: {str(e)}", "ERROR")
            return 0.5

    def matches_failure_pattern(self, position: Position, market_data: DataFrame) -> bool:
        """❌ ตรวจสอบว่าตรงกับรูปแบบที่เคยล้มเหลว"""
        try:
            if not self.hg_failure_analysis:
                return False
            
            current_conditions = {
                'position_type': position.type,
                'loss_range': self.categorize_loss_amount(abs(position.profit)),
                'market_trend': self.get_current_trend_category(market_data),
                'volatility_level': self.get_volatility_category()
            }
            
            # Check against known failure patterns
            for failure_pattern in self.hg_failure_analysis.get('patterns', []):
                match_count = 0
                total_factors = len(failure_pattern)
                
                for factor, value in failure_pattern.items():
                    if current_conditions.get(factor) == value:
                        match_count += 1
                
                # If 75% match, consider it a risky pattern
                if match_count / total_factors >= 0.75:
                    return True
            
            return False
            
        except Exception as e:
            self.log(f"Error checking failure patterns: {str(e)}", "ERROR")
            return False

    def apply_dynamic_risk_adjustments(self, composite: dict, portfolio_impact: dict):
        """⚖️ ปรับคะแนนตามความเสี่ยงแบบไดนามิก"""
        try:
            # Portfolio health penalty/bonus
            if self.portfolio_health < 30:
                composite['total_score'] += 10  # More aggressive when desperate
                composite['reasoning'].append("Emergency portfolio bonus: +10 pts")
            elif self.portfolio_health > 85:
                composite['total_score'] -= 5  # More conservative when healthy
                composite['reasoning'].append("Conservative health penalty: -5 pts")
            
            # Margin impact adjustment
            if portfolio_impact['margin_impact'] == 'HIGH':
                composite['total_score'] -= 15
                composite['reasoning'].append("High margin impact penalty: -15 pts")
            
            # Balance improvement bonus
            if portfolio_impact['balance_impact'] == 'POSITIVE':
                composite['total_score'] += 8
                composite['reasoning'].append("Balance improvement bonus: +8 pts")
            
            # Concurrent HG penalty
            active_hg_count = len(self.active_hedges)
            if active_hg_count > 2:
                penalty = (active_hg_count - 2) * 5
                composite['total_score'] -= penalty
                composite['reasoning'].append(f"Multiple HG penalty: -{penalty} pts")
                
        except Exception as e:
            self.log(f"Error applying risk adjustments: {str(e)}", "ERROR")

    def execute_smart_hg_decision(self, position: Position) -> bool:
        """🎯 ตัดสินใจและดำเนินการ HG อย่างชาญฉลาด"""
        try:
            if not self.smart_hg_enabled:
                return False
            
            # Analyze HG necessity
            hg_analysis = self.analyze_hg_necessity(position)
            
            if not hg_analysis['should_hedge']:
                self.log(f"🤔 HG Analysis: Not recommended for {position.ticket}")
                self.log(f"   Score: {hg_analysis['confidence_score']:.1f}/{self.hg_decision_threshold}")
                return False
            
            # Log decision reasoning
            self.log(f"🧠 SMART HG DECISION for Position {position.ticket}:")
            self.log(f"   Strategy: {hg_analysis['strategy']}")
            self.log(f"   Volume: {hg_analysis['volume_recommendation']:.2f} lots")
            self.log(f"   Timing: {hg_analysis['timing_recommendation']}")
            self.log(f"   Confidence: {hg_analysis['confidence_score']:.1f}/{self.hg_decision_threshold}")
            
            for reason in hg_analysis['decision_reasoning']:
                self.log(f"   • {reason}")
            
            # Execute based on timing recommendation
            if hg_analysis['timing_recommendation'] == 'IMMEDIATE':
                success = self.execute_auto_hedge(position, hg_analysis['strategy'])
                
                if success:
                    # Record success pattern
                    self.record_hg_decision(position, hg_analysis, 'EXECUTED')
                    self.last_hedge_time = datetime.now()
                    return True
                else:
                    # Record failure
                    self.record_hg_decision(position, hg_analysis, 'FAILED')
                    return False
            
            else:  # WAIT
                self.log(f"⏰ HG Decision: WAIT - {hg_analysis['timing_recommendation']}")
                self.record_hg_decision(position, hg_analysis, 'DELAYED')
                return False
                
        except Exception as e:
            self.log(f"Error in smart HG decision: {str(e)}", "ERROR")
            return False

    def record_hg_decision(self, position: Position, analysis: dict, outcome: str):
        """📝 บันทึกการตัดสินใจ HG เพื่อการเรียนรู้"""
        try:
            record = {
                'timestamp': datetime.now().isoformat(),
                'position_ticket': position.ticket,
                'position_type': position.type,
                'position_volume': position.volume,
                'loss_amount': abs(position.profit),
                'analysis_score': analysis['confidence_score'],
                'strategy_used': analysis.get('strategy'),
                'volume_used': analysis.get('volume_recommendation'),
                'outcome': outcome,
                'portfolio_health_at_time': self.portfolio_health,
                'market_conditions': self.get_current_market_snapshot()
            }
            
            self.hg_performance_history.append(record)
            
            # Keep only last 100 records
            if len(self.hg_performance_history) > 100:
                self.hg_performance_history = self.hg_performance_history[-100:]
                
        except Exception as e:
            self.log(f"Error recording HG decision: {str(e)}", "ERROR")

    def get_current_market_snapshot(self) -> Dict[str, Any]:
        """📸 ถ่ายภาพสถานการณ์ตลาดปัจจุบัน"""
        try:
            market_data = self.get_market_data()
            
            if market_data is None:
                return {'trend': 'UNKNOWN', 'volatility': 'UNKNOWN'}
            
            return {
                'trend': self.get_current_trend_category(market_data),
                'volatility': self.get_volatility_category(),
                'momentum': self.calculate_momentum_score(market_data),
                'session': self.get_trading_session()
            }
            
        except Exception as e:
            return {'error': str(e)}

    def get_current_trend_category(self, market_data: DataFrame) -> str:
        """📈 หาประเภทของเทรนด์ปัจจุบัน"""
        try:
            trend_strength = self.calculate_trend_strength(market_data)
            
            if trend_strength > 0.7:
                return 'STRONG_UP'
            elif trend_strength > 0.6:
                return 'MODERATE_UP'
            elif trend_strength < 0.3:
                return 'STRONG_DOWN'
            elif trend_strength < 0.4:
                return 'MODERATE_DOWN'
            else:
                return 'SIDEWAYS'
                
        except:
            return 'UNKNOWN'

    def get_volatility_category(self) -> str:
        """📊 หาประเภทของความผันผวน"""
        try:
            if hasattr(self, 'recent_volatility'):
                if self.recent_volatility > 2.5:
                    return 'VERY_HIGH'
                elif self.recent_volatility > 1.5:
                    return 'HIGH'
                elif self.recent_volatility < 0.5:
                    return 'LOW'
                else:
                    return 'NORMAL'
            return 'UNKNOWN'
        except:
            return 'UNKNOWN'

    def get_trading_session(self) -> str:
        """🕐 หาช่วงเวลาเทรดปัจจุบัน"""
        try:
            hour = datetime.now().hour
            
            if 22 <= hour or hour <= 2:
                return 'MAJOR'
            elif 7 <= hour <= 9:
                return 'ASIAN'
            elif 14 <= hour <= 16:
                return 'US'
            else:
                return 'QUIET'
                
        except:
            return 'UNKNOWN'

    def categorize_loss_amount(self, loss_amount: float) -> str:
        """💰 จัดหมวดหมู่จำนวนการขาดทุน"""
        if loss_amount < 50:
            return 'SMALL'
        elif loss_amount < 150:
            return 'MEDIUM'
        elif loss_amount < 300:
            return 'LARGE'
        else:
            return 'CRITICAL'

    def smart_hg_management_cycle(self):
        """🔄 รอบการจัดการ HG อัจฉริยะ"""
        if not self.smart_hg_enabled or not self.positions:
            return
        
        try:
            for position in self.positions:
                # ข้าม hedge positions
                if position.ticket in self.hedge_pairs:
                    continue
                
                # ข้ามถ้ามี HG อยู่แล้ว (ตรวจสอบขีดจำกัด)
                if position.ticket in self.active_hedges:
                    current_hedges = len(self.active_hedges[position.ticket])
                    if current_hedges >= self.max_hedge_levels:
                        continue
                
                # วิเคราะห์และตัดสินใจ
                if abs(position.profit) >= self.min_loss_threshold_for_hg:
                    self.execute_smart_hg_decision(position)
            
            # จัดการ HG ที่มีอยู่
            self.manage_existing_hedges()
            
        except Exception as e:
            self.log(f"Error in smart HG management cycle: {str(e)}", "ERROR")

    def get_smart_hg_analytics(self) -> dict:
        """📊 สถิติระบบ HG อัจฉริยะ"""
        try:
            analytics = {
                'smart_hg_enabled': self.smart_hg_enabled,
                'intelligence_level': self.hg_intelligence_level,
                'decision_threshold': self.hg_decision_threshold,
                'max_concurrent': self.hg_max_concurrent,
                'cooldown_minutes': self.hg_cooldown_minutes,
                
                'current_status': {
                    'active_hedges': len(self.active_hedges),
                    'total_hedge_pairs': sum(len(hedges) for hedges in self.active_hedges.values()),
                    'positions_eligible_for_hg': 0,
                    'positions_above_loss_threshold': 0
                },
                
                'performance_metrics': {
                    'total_decisions_made': len(self.hg_performance_history),
                    'successful_executions': 0,
                    'failed_executions': 0,
                    'delayed_decisions': 0,
                    'avg_decision_score': 0
                },
                
                'learning_data': {
                    'pattern_learning_enabled': self.hg_pattern_learning,
                    'success_patterns_identified': len(self.hg_success_patterns),
                    'failure_patterns_identified': len(self.hg_failure_analysis),
                    'market_reversal_detection': self.market_reversal_detection
                }
            }
            
            # นับ positions ที่เข้าเกณฑ์
            for position in self.positions:
                if position.ticket not in self.hedge_pairs:  # ไม่ใช่ hedge position
                    analytics['current_status']['positions_eligible_for_hg'] += 1
                    
                    if abs(position.profit) >= self.min_loss_threshold_for_hg:
                        analytics['current_status']['positions_above_loss_threshold'] += 1
            
            # คำนวณ performance metrics
            if self.hg_performance_history:
                executed = len([r for r in self.hg_performance_history if r['outcome'] == 'EXECUTED'])
                failed = len([r for r in self.hg_performance_history if r['outcome'] == 'FAILED'])
                delayed = len([r for r in self.hg_performance_history if r['outcome'] == 'DELAYED'])
                
                analytics['performance_metrics'].update({
                    'successful_executions': executed,
                    'failed_executions': failed,
                    'delayed_decisions': delayed,
                    'avg_decision_score': sum(r['analysis_score'] for r in self.hg_performance_history) / len(self.hg_performance_history)
                })
            
            return analytics
            
        except Exception as e:
            self.log(f"Error getting smart HG analytics: {str(e)}", "ERROR")
            return {}

    def create_smart_flexible_basket(self) -> dict:
        """🧠 Smart Flexible Basket Creation: สร้าง basket ที่ยืดหยุ่นที่สุด"""
        try:
            if len(self.positions) < 2:
                return None
            
            # 1. วิเคราะห์ไม้ที่ควรปิด
            positions_to_close = self._analyze_positions_to_close()
            if not positions_to_close:
                return None
            
            # 2. สร้าง flexible baskets แบบยืดหยุ่น
            flexible_baskets = self._create_flexible_baskets(positions_to_close)
            if not flexible_baskets:
                return None
            
            # 3. เลือก basket ที่ดีที่สุด
            best_basket = self._select_best_flexible_basket(flexible_baskets)
            
            return best_basket
            
        except Exception as e:
            self.log(f"Error creating smart flexible basket: {str(e)}", "ERROR")
            return None

    def _analyze_positions_to_close(self) -> List[dict]:
        """🔍 วิเคราะห์ไม้ที่ควรปิด"""
        try:
            positions_to_close = []
            
            for position in self.positions:
                # วิเคราะห์ไม้แต่ละตัว
                analysis = self.analyze_individual_position(position)
                if analysis and 'error' not in analysis:
                    # เพิ่มข้อมูลเพิ่มเติม
                    position_info = {
                        'position': position,
                        'analysis': analysis,
                        'priority_score': self._calculate_position_priority(position, analysis),
                        'market_distance': self._calculate_market_distance(position)
                    }
                    positions_to_close.append(position_info)
            
            # เรียงตาม priority score
            positions_to_close.sort(key=lambda x: x['priority_score'], reverse=True)
            
            return positions_to_close
            
        except Exception as e:
            self.log(f"Error analyzing positions to close: {str(e)}", "ERROR")
            return []

    def _create_flexible_baskets(self, positions_to_close: List[dict]) -> List[dict]:
        """🔄 สร้าง flexible baskets แบบยืดหยุ่น"""
        try:
            baskets = []
            
            # 1. สร้าง baskets ขนาด 2-6 ไม้
            for basket_size in range(2, min(7, len(positions_to_close) + 1)):
                # สร้าง combinations ทุกแบบ
                for combo in self._get_combinations(positions_to_close, basket_size):
                    basket_positions = [item['position'] for item in combo]
                    
                    # ตรวจสอบว่าไม้ไม่ห่างจากราคาปัจจุบันเกินไป
                    if self._validate_basket_market_distance(basket_positions):
                        # สร้าง basket
                        basket = self._create_flexible_basket(basket_positions)
                        if basket:
                            baskets.append(basket)
            
            return baskets
            
        except Exception as e:
            self.log(f"Error creating flexible baskets: {str(e)}", "ERROR")
            return []

    def _create_flexible_basket(self, positions: List[Position]) -> dict:
        """🎯 สร้าง flexible basket เดี่ยว"""
        try:
            # ใช้ฟีเจอร์เดิมที่มีอยู่แล้ว
            basket_score = self._evaluate_basket_score(positions)
            
            if basket_score and basket_score.get('meets_criteria', False):
                # เพิ่มข้อมูลเพิ่มเติม
                basket_score['flexibility_score'] = self._calculate_flexibility_score(positions)
                basket_score['market_alignment'] = self._calculate_market_alignment(positions)
                basket_score['portfolio_impact'] = self._calculate_portfolio_impact(positions)
                
                return basket_score
            
            return None
            
        except Exception as e:
            self.log(f"Error creating flexible basket: {str(e)}", "ERROR")
            return None

    def _calculate_position_priority(self, position: Position, analysis: dict) -> float:
        """🎯 คำนวณ priority score ของไม้"""
        try:
            priority_score = 0.0
            
            # 1. Risk Level (40%)
            risk_level = analysis.get('risk_level', 'MEDIUM')
            if risk_level == 'HIGH':
                priority_score += 40
            elif risk_level == 'MEDIUM':
                priority_score += 25
            else:
                priority_score += 10
            
            # 2. Quality Score (30%)
            quality_score = analysis.get('quality_score', 0)
            priority_score += (quality_score / 100) * 30
            
            # 3. Recovery Potential (20%)
            recovery_potential = analysis.get('recovery_potential', 0)
            priority_score += (recovery_potential / 100) * 20
            
            # 4. Portfolio Impact (10%)
            portfolio_impact = analysis.get('portfolio_impact', 'NEUTRAL')
            if portfolio_impact == 'NEGATIVE':
                priority_score += 10
            elif portfolio_impact == 'NEUTRAL':
                priority_score += 5
            
            return priority_score
            
        except Exception as e:
            self.log(f"Error calculating position priority: {str(e)}", "ERROR")
            return 0.0

    def _calculate_market_distance(self, position: Position) -> float:
        """📏 คำนวณระยะห่างจากราคาปัจจุบัน"""
        try:
            current_price = self.get_current_price()
            if hasattr(position, 'open_price') and current_price:
                distance_pips = abs(current_price - position.open_price) * 10000
                return distance_pips
            return 0.0
        except:
            return 0.0

    def _validate_basket_market_distance(self, positions: List[Position]) -> bool:
        """✅ ตรวจสอบว่าไม้ใน basket ไม่ห่างจากราคาปัจจุบันเกินไป"""
        try:
            max_allowed_distance = 100  # 100 pips
            
            for position in positions:
                distance = self._calculate_market_distance(position)
                if distance > max_allowed_distance:
                    return False
            
            return True
            
        except Exception as e:
            self.log(f"Error validating basket market distance: {str(e)}", "ERROR")
            return False

    def _calculate_flexibility_score(self, positions: List[Position]) -> float:
        """🔄 คำนวณความยืดหยุ่นของ basket"""
        try:
            # 1. ความหลากหลายของประเภทไม้
            buy_count = len([p for p in positions if p.type == "BUY"])
            sell_count = len([p for p in positions if p.type == "SELL"])
            
            # ยิ่งหลากหลาย ยิ่งยืดหยุ่น
            diversity_score = min(100, abs(buy_count - sell_count) * 20)
            
            # 2. ความสมดุลของ volume
            total_volume = sum(p.volume for p in positions)
            if total_volume > 0:
                volume_balance = min(100, (1 - abs(buy_count - sell_count) / len(positions)) * 100)
            else:
                volume_balance = 50
            
            # คำนวณ flexibility score รวม
            flexibility_score = (diversity_score * 0.6) + (volume_balance * 0.4)
            
            return max(0, min(100, flexibility_score))
            
        except Exception as e:
            self.log(f"Error calculating flexibility score: {str(e)}", "ERROR")
            return 50.0

    def _calculate_market_alignment(self, positions: List[Position]) -> float:
        """📊 คำนวณการจัดเรียงตามตลาด"""
        try:
            # วิเคราะห์ market trend
            market_analysis = self.analyze_market_intelligence()
            market_trend = market_analysis.get('momentum_trend', 'NEUTRAL')
            
            alignment_score = 0.0
            
            for position in positions:
                if market_trend == 'BULLISH' and position.type == 'BUY':
                    alignment_score += 20
                elif market_trend == 'BEARISH' and position.type == 'SELL':
                    alignment_score += 20
                elif market_trend == 'NEUTRAL':
                    alignment_score += 10
            
            # สเกลเป็น 0-100
            final_score = min(100, alignment_score)
            return final_score
            
        except Exception as e:
            self.log(f"Error calculating market alignment: {str(e)}", "ERROR")
            return 50.0

    def _calculate_portfolio_impact(self, positions: List[Position]) -> float:
        """⚖️ คำนวณผลกระทบต่อ portfolio"""
        try:
            # ใช้ฟีเจอร์เดิมที่มีอยู่แล้ว
            margin_relief = self._calculate_margin_relief(positions)
            balance_impact = self._calculate_balance_impact(positions)
            risk_reduction = self._calculate_risk_reduction(positions)
            
            # คำนวณ portfolio impact score
            portfolio_impact = (margin_relief * 0.4) + (balance_impact * 0.4) + (risk_reduction * 0.2)
            
            return max(0, min(100, portfolio_impact))
            
        except Exception as e:
            self.log(f"Error calculating portfolio impact: {str(e)}", "ERROR")
            return 50.0

    def _select_best_flexible_basket(self, baskets: List[dict]) -> dict:
        """🏆 เลือก basket ที่ดีที่สุด"""
        try:
            if not baskets:
                return None
            
            # คำนวณ final score ที่รวมความยืดหยุ่น
            for basket in baskets:
                # ใช้ฟีเจอร์เดิมที่มีอยู่แล้ว
                base_score = basket.get('final_score', 0)
                
                # เพิ่มคะแนนความยืดหยุ่น
                flexibility_bonus = basket.get('flexibility_score', 50) * 0.2
                market_alignment_bonus = basket.get('market_alignment', 50) * 0.15
                portfolio_impact_bonus = basket.get('portfolio_impact', 50) * 0.15
                
                # คำนวณ final score ใหม่
                enhanced_score = base_score + flexibility_bonus + market_alignment_bonus + portfolio_impact_bonus
                basket['enhanced_final_score'] = enhanced_score
            
            # เรียงตาม enhanced final score
            baskets.sort(key=lambda x: x.get('enhanced_final_score', 0), reverse=True)
            
            # คืนค่า basket ที่ดีที่สุด
            return baskets[0] if baskets else None
            
        except Exception as e:
            self.log(f"Error selecting best flexible basket: {str(e)}", "ERROR")
            return None

    def execute_smart_flexible_closing(self):
        """🚀 Smart Flexible Closing: ปิดไม้แบบยืดหยุ่นและฉลาด"""
        try:
            if not self.positions:
                return
            
            self.log("🧠 Starting Smart Flexible Closing System", "AI")
            
            # 1. สร้าง smart flexible basket
            best_basket = self.create_smart_flexible_basket()
            
            if best_basket:
                # 2. แสดงข้อมูล basket
                self._log_basket_details(best_basket)
                
                # 3. ปิดไม้ทั้งหมดใน basket พร้อมกัน
                success = self._execute_batch_closing(best_basket['positions'])
                
                if success:
                    self.log(f"✅ Smart Flexible Closing: {len(best_basket['positions'])} positions closed successfully", "SUCCESS")
                    self.log(f"💰 Net Profit: ${best_basket['total_profit']:.2f}", "SUCCESS")
                    self.log(f"🎯 Enhanced Score: {best_basket.get('enhanced_final_score', 0):.1f}", "SUCCESS")
                else:
                    self.log(f"❌ Smart Flexible Closing: Failed to close positions", "ERROR")
            else:
                self.log("🤖 Smart Flexible Closing: No suitable basket found", "AI")
                
        except Exception as e:
            self.log(f"❌ Error in smart flexible closing: {str(e)}", "ERROR")

    def _log_basket_details(self, basket: dict):
        """📋 แสดงรายละเอียด basket"""
        try:
            positions = basket.get('positions', [])
            total_profit = basket.get('total_profit', 0)
            enhanced_score = basket.get('enhanced_final_score', 0)
            
            self.log(f"🎯 Smart Basket Details:", "AI")
            self.log(f"   📊 Total Positions: {len(positions)}", "AI")
            self.log(f"   💰 Total Profit: ${total_profit:.2f}", "AI")
            self.log(f"   🏆 Enhanced Score: {enhanced_score:.1f}", "AI")
            
            # แสดงไม้แต่ละตัว
            for i, position in enumerate(positions, 1):
                pos_type = position.type
                pos_profit = position.profit
                pos_volume = position.volume
                self.log(f"   {i}. {pos_type} {pos_volume} lots - ${pos_profit:.2f}", "AI")
                
        except Exception as e:
            self.log(f"Error logging basket details: {str(e)}", "ERROR")

    def _execute_batch_closing(self, positions: List[Position]) -> bool:
        """⚡ ปิดไม้เป็นกลุ่มพร้อมกัน (ไม้ไม่กระโดด)"""
        try:
            if not positions:
                return False
            
            self.log(f"⚡ Executing batch closing for {len(positions)} positions", "INFO")
            
            # 1. ล็อคไม้ที่จะปิด
            for position in positions:
                position.locked_for_closing = True
                position.lock_timestamp = time.time()
            
            # 2. ส่งคำสั่งปิดไม้ทั้งหมดพร้อมกัน
            close_orders = []
            for position in positions:
                try:
                    # ใช้ฟีเจอร์เดิมที่มีอยู่แล้ว
                    close_success = self.close_position_smart(
                        position, 
                        f"Smart Flexible Closing - Batch Mode"
                    )
                    
                    if close_success:
                        close_orders.append({
                            'position': position,
                            'success': True,
                            'timestamp': time.time()
                        })
                    else:
                        close_orders.append({
                            'position': position,
                            'success': False,
                            'timestamp': time.time()
                        })
                        
                except Exception as e:
                    self.log(f"Error closing position {position.ticket}: {str(e)}", "ERROR")
                    close_orders.append({
                        'position': position,
                        'success': False,
                        'error': str(e),
                        'timestamp': time.time()
                    })
            
            # 3. รอให้ไม้ปิดเสร็จ
            time.sleep(2)  # รอ 2 วินาที
            
            # 4. ตรวจสอบผลลัพธ์
            successful_closes = [order for order in close_orders if order['success']]
            failed_closes = [order for order in close_orders if not order['success']]
            
            if successful_closes:
                self.log(f"✅ Batch Closing: {len(successful_closes)} positions closed successfully", "SUCCESS")
            
            if failed_closes:
                self.log(f"⚠️ Batch Closing: {len(failed_closes)} positions failed to close", "WARNING")
                for failed in failed_closes:
                    self.log(f"   Failed: {failed['position'].ticket} - {failed.get('error', 'Unknown error')}", "WARNING")
            
            # 5. อัพเดท last batch closing time
            self.last_batch_closing = time.time()
            
            # 6. คืนค่า success rate
            success_rate = len(successful_closes) / len(positions)
            return success_rate >= 0.8  # 80% success rate
            
        except Exception as e:
            self.log(f"Error in batch closing: {str(e)}", "ERROR")
            return False

    def _emergency_close_high_risk_positions(self) -> dict:
        """🚨 ปิดไม้ที่เสี่ยงที่สุดในภาวะฉุกเฉิน"""
        try:
            self.log("🚨 Emergency Closing High Risk Positions", "AI")
            
            # หาไม้ที่เสี่ยงที่สุด
            high_risk_positions = []
            for position in self.positions:
                risk_score = self._calculate_position_risk_score(position)
                if risk_score > 80:  # เสี่ยงมากกว่า 80%
                    high_risk_positions.append((position, risk_score))
            
            # เรียงตามความเสี่ยง
            high_risk_positions.sort(key=lambda x: x[1], reverse=True)
            
            # ปิดไม้ที่เสี่ยงที่สุด 3 ตัวแรก
            positions_closed = 0
            for position, risk_score in high_risk_positions[:3]:
                try:
                    if self.close_position_smart(position, f"Emergency: High Risk (Score: {risk_score:.1f})"):
                        positions_closed += 1
                        self.log(f"🚨 Emergency Closed: {position.ticket} (Risk: {risk_score:.1f})", "AI")
                except Exception as e:
                    self.log(f"Error emergency closing position {position.ticket}: {str(e)}", "ERROR")
            
            return {
                'success': positions_closed > 0,
                'positions_closed': positions_closed,
                'total_high_risk': len(high_risk_positions)
            }
            
        except Exception as e:
            self.log(f"Error in emergency closing high risk positions: {str(e)}", "ERROR")
            return {'success': False, 'positions_closed': 0, 'total_high_risk': 0}

    def _emergency_close_high_loss_positions(self) -> dict:
        """📉 ปิดไม้ที่ขาดทุนมากที่สุดในภาวะฉุกเฉิน"""
        try:
            self.log("📉 Emergency Closing High Loss Positions", "AI")
            
            # หาไม้ที่ขาดทุนมากที่สุด
            high_loss_positions = [p for p in self.positions if p.profit < -100]
            high_loss_positions.sort(key=lambda x: x.profit)  # เรียงจากขาดทุนมากไปน้อย
            
            # ปิดไม้ที่ขาดทุนมากที่สุด 3 ตัวแรก
            positions_closed = 0
            total_loss_reduced = 0
            
            for position in high_loss_positions[:3]:
                try:
                    if self.close_position_smart(position, f"Emergency: High Loss (${position.profit:.2f})"):
                        positions_closed += 1
                        total_loss_reduced += abs(position.profit)
                        self.log(f"📉 Emergency Closed: {position.ticket} (Loss: ${position.profit:.2f})", "AI")
                except Exception as e:
                    self.log(f"Error emergency closing position {position.ticket}: {str(e)}", "ERROR")
            
            return {
                'success': positions_closed > 0,
                'positions_closed': positions_closed,
                'total_loss_reduced': total_loss_reduced
            }
            
        except Exception as e:
            self.log(f"Error in emergency closing high loss positions: {str(e)}", "ERROR")
            return {'success': False, 'positions_closed': 0, 'total_loss_reduced': 0}

    def _emergency_close_imbalanced_positions(self) -> dict:
        """⚖️ ปิดไม้ที่ไม่สมดุลในภาวะฉุกเฉิน"""
        try:
            self.log("⚖️ Emergency Closing Imbalanced Positions", "AI")
            
            # วิเคราะห์ความไม่สมดุล
            buy_positions = [p for p in self.positions if p.type == "BUY"]
            sell_positions = [p for p in self.positions if p.type == "SELL"]
            
            buy_volume = sum(p.volume for p in buy_positions)
            sell_volume = sum(p.volume for p in sell_positions)
            
            positions_closed = 0
            
            if buy_volume > sell_volume * 1.5:  # BUY มากกว่า SELL 50%
                # ปิด BUY ที่ขาดทุนมากที่สุด
                buy_loss_positions = [p for p in buy_positions if p.profit < 0]
                buy_loss_positions.sort(key=lambda x: x.profit)
                
                for position in buy_loss_positions[:2]:  # ปิด 2 ตัวแรก
                    if self.close_position_smart(position, "Emergency: BUY Imbalance"):
                        positions_closed += 1
                        self.log(f"⚖️ Emergency Closed BUY: {position.ticket}", "AI")
                        
            elif sell_volume > buy_volume * 1.5:  # SELL มากกว่า BUY 50%
                # ปิด SELL ที่ขาดทุนมากที่สุด
                sell_loss_positions = [p for p in sell_positions if p.profit < 0]
                sell_loss_positions.sort(key=lambda x: x.profit)
                
                for position in sell_loss_positions[:2]:  # ปิด 2 ตัวแรก
                    if self.close_position_smart(position, "Emergency: SELL Imbalance"):
                        positions_closed += 1
                        self.log(f"📉 Emergency Closed SELL: {position.ticket}", "AI")
            
            return {
                'success': positions_closed > 0,
                'positions_closed': positions_closed,
                'buy_volume': buy_volume,
                'sell_volume': sell_volume
            }
            
        except Exception as e:
            self.log(f"Error in emergency closing imbalanced positions: {str(e)}", "ERROR")
            return {'success': False, 'positions_closed': 0}

    def _ai_create_balancing_positions(self) -> dict:
        """🎯 AI สร้างไม้เพื่อสมดุล Portfolio"""
        try:
            self.log("🎯 AI Creating Balancing Positions", "AI")
            
            # วิเคราะห์ความไม่สมดุล
            buy_positions = [p for p in self.positions if p.type == "BUY"]
            sell_positions = [p for p in self.positions if p.type == "SELL"]
            
            buy_volume = sum(p.volume for p in buy_positions)
            sell_volume = sum(p.volume for p in sell_positions)
            
            positions_created = 0
            
            if buy_volume > sell_volume * 1.3:  # BUY มากกว่า SELL 30%
                # สร้าง SELL เพื่อสมดุล
                current_price = self.get_current_price()
                if current_price:
                    # สร้าง SELL ที่ราคาปัจจุบัน
                    result = self._open_direct_mt5_order(
                        "SELL", 
                        current_price, 
                        0.1,  # 0.1 lots
                        "AI Balancing: SELL to reduce BUY imbalance"
                    )
                    if result.get('success'):
                        positions_created += 1
                        self.log(f"🎯 AI Created Balancing SELL: {result.get('ticket', 'Unknown')}", "AI")
                        
            elif sell_volume > buy_volume * 1.3:  # SELL มากกว่า BUY 30%
                # สร้าง BUY เพื่อสมดุล
                current_price = self.get_current_price()
                if current_price:
                    # สร้าง BUY ที่ราคาปัจจุบัน
                    result = self._open_direct_mt5_order(
                        "BUY", 
                        current_price, 
                        0.1,  # 0.1 lots
                        "AI Balancing: BUY to reduce SELL imbalance"
                    )
                    if result.get('success'):
                        positions_created += 1
                        self.log(f"🎯 AI Created Balancing BUY: {result.get('ticket', 'Unknown')}", "AI")
            
            return {
                'success': positions_created > 0,
                'positions_created': positions_created,
                'buy_volume': buy_volume,
                'sell_volume': sell_volume
            }
            
        except Exception as e:
            self.log(f"Error in AI creating balancing positions: {str(e)}", "ERROR")
            return {'success': False, 'positions_created': 0}

    def _close_high_margin_positions(self) -> dict:
        """💰 ปิดไม้ที่ใช้ margin มากที่สุด"""
        try:
            self.log("💰 Closing High Margin Positions", "AI")
            
            # หาไม้ที่ใช้ margin มากที่สุด
            high_margin_positions = []
            for position in self.positions:
                margin_used = position.volume * 1000  # ประมาณการ margin ที่ใช้
                high_margin_positions.append((position, margin_used))
            
            # เรียงตาม margin ที่ใช้
            high_margin_positions.sort(key=lambda x: x[1], reverse=True)
            
            # ปิดไม้ที่ใช้ margin มากที่สุด 2 ตัวแรก
            positions_closed = 0
            margin_relieved = 0
            
            for position, margin_used in high_margin_positions[:2]:
                try:
                    if self.close_position_smart(position, f"Margin Management: High Margin (${margin_used:.0f})"):
                        positions_closed += 1
                        margin_relieved += margin_used
                        self.log(f"💰 Closed High Margin: {position.ticket} (Margin: ${margin_used:.0f})", "AI")
                except Exception as e:
                    self.log(f"Error closing high margin position {position.ticket}: {str(e)}", "ERROR")
            
            return {
                'success': positions_closed > 0,
                'positions_closed': positions_closed,
                'margin_relieved': margin_relieved
            }
            
        except Exception as e:
            self.log(f"Error in closing high margin positions: {str(e)}", "ERROR")
            return {'success': False, 'positions_closed': 0, 'margin_relieved': 0}

    def _close_unnecessary_positions(self) -> dict:
        """🗑️ ปิดไม้ที่ไม่จำเป็น"""
        try:
            self.log("🗑️ Closing Unnecessary Positions", "AI")
            
            # หาไม้ที่ไม่จำเป็น (ไม้ที่เปิดมานานและไม่กำไร)
            unnecessary_positions = []
            current_time = time.time()
            
            for position in self.positions:
                # ไม้ที่เปิดมานาน (มากกว่า 24 ชั่วโมง) และไม่กำไร
                if hasattr(position, 'open_time'):
                    try:
                        open_time = position.open_time if isinstance(position.open_time, datetime) else datetime.fromisoformat(str(position.open_time))
                        hours_open = (datetime.now() - open_time).total_seconds() / 3600
                        
                        if hours_open > 24 and position.profit < 0:
                            unnecessary_positions.append((position, hours_open))
                    except:
                        pass
            
            # เรียงตามเวลาที่เปิด
            unnecessary_positions.sort(key=lambda x: x[1], reverse=True)
            
            # ปิดไม้ที่ไม่จำเป็น 2 ตัวแรก
            positions_closed = 0
            
            for position, hours_open in unnecessary_positions[:2]:
                try:
                    if self.close_position_smart(position, f"Unnecessary: Open for {hours_open:.1f} hours"):
                        positions_closed += 1
                        self.log(f"🗑️ Closed Unnecessary: {position.ticket} (Hours: {hours_open:.1f})", "AI")
                except Exception as e:
                    self.log(f"Error closing unnecessary position {position.ticket}: {str(e)}", "ERROR")
            
            return {
                'success': positions_closed > 0,
                'positions_closed': positions_closed,
                'total_unnecessary': len(unnecessary_positions)
            }
            
        except Exception as e:
            self.log(f"Error in closing unnecessary positions: {str(e)}", "ERROR")
            return {'success': False, 'positions_closed': 0, 'total_unnecessary': 0}

    def _rebalance_buy_heavy_portfolio(self) -> dict:
        """📈 สร้างสมดุล Portfolio ที่ BUY หนัก"""
        try:
            self.log("📈 Rebalancing BUY Heavy Portfolio", "AI")
            
            # หาไม้ BUY ที่ควรปิด
            buy_positions = [p for p in self.positions if p.type == "BUY"]
            buy_positions.sort(key=lambda x: x.profit)  # เรียงจากขาดทุนมากไปน้อย
            
            # ปิด BUY ที่ขาดทุนมากที่สุด 2 ตัวแรก
            positions_closed = 0
            
            for position in buy_positions[:2]:
                try:
                    if self.close_position_smart(position, "Rebalancing: BUY Heavy Portfolio"):
                        positions_closed += 1
                        self.log(f"📈 Rebalancing Closed BUY: {position.ticket}", "AI")
                except Exception as e:
                    self.log(f"Error rebalancing BUY position {position.ticket}: {str(e)}", "ERROR")
            
            return {
                'success': positions_closed > 0,
                'positions_closed': positions_closed,
                'strategy': 'BUY_HEAVY_REBALANCING'
            }
            
        except Exception as e:
            self.log(f"Error in rebalancing BUY heavy portfolio: {str(e)}", "ERROR")
            return {'success': False, 'positions_closed': 0, 'strategy': 'ERROR'}

    def _rebalance_sell_heavy_portfolio(self) -> dict:
        """📉 สร้างสมดุล Portfolio ที่ SELL หนัก"""
        try:
            self.log("📉 Rebalancing SELL Heavy Portfolio", "AI")
            
            # หาไม้ SELL ที่ควรปิด
            sell_positions = [p for p in self.positions if p.type == "SELL"]
            sell_positions.sort(key=lambda x: x.profit)  # เรียงจากขาดทุนมากไปน้อย
            
            # ปิดไม้ที่ขาดทุนมากที่สุด 2 ตัวแรก
            positions_closed = 0
            
            for position in sell_positions[:2]:
                try:
                    if self.close_position_smart(position, "Rebalancing: SELL Heavy Portfolio"):
                        positions_closed += 1
                        self.log(f"📉 Rebalancing Closed SELL: {position.ticket}", "AI")
                except Exception as e:
                    self.log(f"Error rebalancing SELL position {position.ticket}: {str(e)}", "ERROR")
            
            return {
                'success': positions_closed > 0,
                'positions_closed': positions_closed,
                'strategy': 'SELL_HEAVY_REBALANCING'
            }
            
        except Exception as e:
            self.log(f"Error in rebalancing SELL heavy portfolio: {str(e)}", "ERROR")
            return {'success': False, 'positions_closed': 0, 'strategy': 'ERROR'}

    def _rebalance_mixed_portfolio(self) -> dict:
        """🔄 สร้างสมดุล Portfolio แบบผสม"""
        try:
            self.log("🔄 Rebalancing Mixed Portfolio", "AI")
            
            # วิเคราะห์ Portfolio
            buy_positions = [p for p in self.positions if p.type == "BUY"]
            sell_positions = [p for p in self.positions if p.type == "SELL"]
            
            # ปิดไม้ที่ขาดทุนมากที่สุดจากทั้งสองฝั่ง
            positions_closed = 0
            
            # ปิด BUY ที่ขาดทุนมากที่สุด 1 ตัว
            if buy_positions:
                worst_buy = min(buy_positions, key=lambda x: x.profit)
                if worst_buy.profit < 0:
                    if self.close_position_smart(worst_buy, "Rebalancing: Mixed Portfolio BUY"):
                        positions_closed += 1
                        self.log(f"🔄 Rebalancing Closed BUY: {worst_buy.ticket}", "AI")
            
            # ปิด SELL ที่ขาดทุนมากที่สุด 1 ตัว
            if sell_positions:
                worst_sell = min(sell_positions, key=lambda x: x.profit)
                if worst_sell.profit < 0:
                    if self.close_position_smart(worst_sell, "Rebalancing: Mixed Portfolio SELL"):
                        positions_closed += 1
                        self.log(f"📉 Rebalancing Closed SELL: {worst_sell.ticket}", "AI")
            
            return {
                'success': positions_closed > 0,
                'positions_closed': positions_closed,
                'strategy': 'MIXED_PORTFOLIO_REBALANCING'
            }
            
        except Exception as e:
            self.log(f"Error in rebalancing mixed portfolio: {str(e)}", "ERROR")
            return {'success': False, 'positions_closed': 0, 'strategy': 'ERROR'}

    def _create_hedging_positions(self) -> dict:
        """🛡️ สร้างไม้ค้ำไม้ที่ขาดทุน"""
        try:
            self.log("🛡️ Creating Hedging Positions", "AI")
            
            # หาไม้ที่ขาดทุนมากที่สุด
            losing_positions = [p for p in self.positions if p.profit < -50]
            if not losing_positions:
                return {'success': False, 'reason': 'No losing positions to hedge'}
            
            # เรียงตามการขาดทุน
            losing_positions.sort(key=lambda x: x.profit)
            worst_position = losing_positions[0]
            
            # สร้างไม้ค้ำ
            current_price = self.get_current_price()
            if not current_price:
                return {'success': False, 'reason': 'Cannot get current price'}
            
            hedge_type = "SELL" if worst_position.type == "BUY" else "BUY"
            hedge_volume = worst_position.volume * 0.5  # ครึ่งหนึ่งของไม้ที่ขาดทุน
            
            result = self._open_direct_mt5_order(
                hedge_type,
                current_price,
                hedge_volume,
                f"AI Hedging: {hedge_type} to hedge {worst_position.type} position"
            )
            
            if result.get('success'):
                self.log(f"🛡️ Created Hedging {hedge_type}: {result.get('ticket', 'Unknown')}", "AI")
                return {
                    'success': True,
                    'hedge_type': hedge_type,
                    'hedge_volume': hedge_volume,
                    'hedged_position': worst_position.ticket
                }
            else:
                return {
                    'success': False,
                    'reason': f'Failed to create hedging position: {result.get("error", "Unknown error")}'
                }
                
        except Exception as e:
            self.log(f"Error in creating hedging positions: {str(e)}", "ERROR")
            return {'success': False, 'reason': f'Error: {str(e)}'}

    def _adjust_stop_loss_take_profit(self) -> dict:
        """🎯 ปรับ Stop Loss และ Take Profit"""
        try:
            self.log("🎯 Adjusting Stop Loss and Take Profit", "AI")
            
            # หาไม้ที่ไม่มี Stop Loss หรือ Take Profit
            positions_adjusted = 0
            
            for position in self.positions:
                try:
                    # ตรวจสอบว่ามี Stop Loss หรือไม่
                    has_sl = hasattr(position, 'sl') and position.sl > 0
                    has_tp = hasattr(position, 'tp') and position.tp > 0
                    
                    if not has_sl or not has_tp:
                        # ปรับ Stop Loss และ Take Profit
                        current_price = self.get_current_price()
                        if current_price:
                            if position.type == "BUY":
                                # BUY: SL ต่ำกว่า entry, TP สูงกว่า entry
                                new_sl = position.open_price * 0.995  # -0.5%
                                new_tp = position.open_price * 1.01   # +1.0%
                            else:
                                # SELL: SL สูงกว่า entry, TP ต่ำกว่า entry
                                new_sl = position.open_price * 1.005  # +0.5%
                                new_tp = position.open_price * 0.99   # -1.0%
                            
                            # ปรับ Stop Loss และ Take Profit (จำลอง)
                            self.log(f"🎯 Adjusted {position.type} {position.ticket}: SL={new_sl:.5f}, TP={new_tp:.5f}", "AI")
                            positions_adjusted += 1
                            
                except Exception as e:
                    self.log(f"Error adjusting SL/TP for position {position.ticket}: {str(e)}", "ERROR")
                    continue
            
            return {
                'success': positions_adjusted > 0,
                'positions_adjusted': positions_adjusted
            }
            
        except Exception as e:
            self.log(f"Error in adjusting stop loss and take profit: {str(e)}", "ERROR")
            return {'success': False, 'positions_adjusted': 0}

    def _calculate_position_risk_score(self, position: Position) -> float:
        """⚠️ คำนวณความเสี่ยงของไม้"""
        try:
            risk_score = 0.0
            
            # 1. Loss Factor (40%)
            if position.profit < 0:
                loss_percent = abs(position.profit) / (position.open_price * position.volume) * 100
                risk_score += min(40, loss_percent * 2)  # ขาดทุน 20% = 20 points
            
            # 2. Volume Factor (30%)
            total_volume = sum(p.volume for p in self.positions)
            if total_volume > 0:
                volume_ratio = position.volume / total_volume
                risk_score += min(30, volume_ratio * 100)  # Volume 30% = 30 points
            
            # 3. Time Factor (20%)
            if hasattr(position, 'open_time'):
                try:
                    open_time = position.open_time if isinstance(position.open_time, datetime) else datetime.fromisoformat(str(position.open_time))
                    hours_open = (datetime.now() - open_time).total_seconds() / 3600
                    risk_score += min(20, hours_open / 2)  # เปิด 40 ชั่วโมง = 20 points
                except:
                    pass
            
            # 4. Market Distance Factor (10%)
            current_price = self.get_current_price()
            if current_price and hasattr(position, 'open_price'):
                distance_pips = abs(current_price - position.open_price) * 10000
                risk_score += min(10, distance_pips / 10)  # 100 pips = 10 points
            
            return min(100, risk_score)
            
        except Exception as e:
            self.log(f"Error calculating position risk score: {str(e)}", "ERROR")
            return 50.0

class TradingGUI:
    def __init__(self):
        # Initialize logging and error tracking
        self.startup_errors = []
        self.gui_components_loaded = False
        self.fallback_mode = False
        
        try:
            self.trading_system = TradingSystem()
            print("✅ Trading system initialized successfully")
        except Exception as e:
            print(f"⚠️ Trading system initialization failed: {e}")
            self.startup_errors.append(f"Trading system: {e}")
            # Create minimal trading system fallback
            self.trading_system = self.create_fallback_trading_system()
        
        # Enhanced Modern Professional Color Scheme
        self.COLORS = {
            'bg_primary': '#1a1a1a',     # Main background
            'bg_secondary': '#2d2d2d',   # Card backgrounds
            'bg_accent': '#3a3a3a',      # Button/component backgrounds
            'bg_highlight': '#404040',   # Highlighted elements
            'accent_blue': '#0078d4',    # Primary action color
            'accent_green': '#107c10',   # Success/profit color
            'accent_red': '#d13438',     # Error/loss color
            'accent_orange': '#ff8c00',  # Warning color
            'accent_purple': '#8b5cf6',  # Monitor/analysis color
            'accent_cyan': '#06b6d4',    # Info/data color
            'text_primary': '#ffffff',   # Primary text
            'text_secondary': '#cccccc', # Secondary text
            'text_muted': '#999999',     # Muted text
            'border': '#404040',         # Borders and separators
            'hover': '#4a4a4a',          # Hover states
            'card_shadow': '#0f0f0f',    # Card shadow effect
            'gradient_start': '#2d2d2d', # Gradient start
            'gradient_end': '#1a1a1a'    # Gradient end
        }
        
        # Animation and status tracking
        self.connection_animation_state = 0
        self.hover_states = {}
        
        # Setup GUI with comprehensive error handling
        try:
            self.setup_gui()
            self.gui_components_loaded = True
            print("✅ GUI setup completed successfully")
        except Exception as e:
            print(f"❌ GUI setup failed: {e}")
            self.startup_errors.append(f"GUI setup: {e}")
            try:
                self.setup_fallback_gui()
                print("✅ Fallback GUI loaded")
            except Exception as fallback_error:
                print(f"❌ Fallback GUI also failed: {fallback_error}")
                raise Exception(f"Complete GUI failure: {e}")
        
        # Start update loop only if GUI was created successfully
        if self.gui_components_loaded or self.fallback_mode:
            self.update_loop()

    def create_fallback_trading_system(self):
        """Create a minimal trading system fallback"""
        class FallbackTradingSystem:
            def __init__(self):
                self.mt5_connected = False
                self.buy_volume = 0.0
                self.sell_volume = 0.0
                self.net_profit = 0.0
                self.total_trades = 0
                self.root = None
                
            def log(self, message, level="INFO"):
                print(f"[{level}] {message}")
                
            def update_positions(self):
                pass
                
        return FallbackTradingSystem()

    def setup_gui(self):
        """Setup the modern professional GUI with comprehensive error handling"""
        try:
            print("🔄 Starting GUI initialization...")
            
            # Create main window with more compact size
            self.root = tk.Tk()
            self.root.title("🏆 Modern AI Gold Grid Trading System v3.0")
            self.root.geometry("1200x800")
            self.root.configure(bg=self.COLORS['bg_primary'])
            self.root.minsize(1000, 600)  # Responsive minimum size
            print("✅ Main window created")
            
            # Modern Style Configuration
            try:
                self.setup_modern_styles()
                print("✅ Modern styles configured")
            except Exception as e:
                print(f"⚠️ Style configuration failed: {e}")
                self.startup_errors.append(f"Styles: {e}")
            
            # Create modern layout with cards - each with individual error handling
            component_success = 0
            total_components = 5
            
            try:
                self.create_modern_header()
                component_success += 1
                print("✅ Header created and packed")
            except Exception as e:
                print(f"⚠️ Header creation failed: {e}")
                self.startup_errors.append(f"Header: {e}")
                
            try:
                self.create_control_cards()
                component_success += 1
                print("✅ Control cards created and packed")
            except Exception as e:
                print(f"⚠️ Control cards creation failed: {e}")
                self.startup_errors.append(f"Control cards: {e}")
                
            try:
                self.create_data_section()
                component_success += 1
                print("✅ Data section created and packed")
            except Exception as e:
                print(f"⚠️ Data section creation failed: {e}")
                self.startup_errors.append(f"Data section: {e}")
                
            try:
                self.create_analytics_dashboard()
                component_success += 1
                print("✅ Analytics dashboard created and packed")
            except Exception as e:
                print(f"⚠️ Analytics dashboard creation failed: {e}")
                self.startup_errors.append(f"Analytics: {e}")
                
            try:
                self.create_log_panel()
                component_success += 1
                print("✅ Log panel created and packed")
            except Exception as e:
                print(f"⚠️ Log panel creation failed: {e}")
                self.startup_errors.append(f"Log panel: {e}")
            
            print(f"📊 GUI Components loaded: {component_success}/{total_components}")
            
            # Add debug output for widget hierarchy
            self.debug_widget_hierarchy()
            
            # Connect trading system to root
            if hasattr(self.trading_system, 'root'):
                self.trading_system.root = self.root
            
            # Show startup status
            if self.startup_errors:
                self.show_startup_status()
            
            # Auto-scan for terminals after GUI is fully loaded (increased delay)
            self.root.after(5000, self.safe_auto_scan_terminals)
            
            # Start animation timers with reduced frequency
            try:
                self.start_status_animations()
                print("✅ Status animations started")
            except Exception as e:
                print(f"⚠️ Animation startup failed: {e}")
                
        except Exception as e:
            print(f"❌ Critical GUI setup failure: {e}")
            raise

    def setup_fallback_gui(self):
        """Setup a basic fallback GUI when modern GUI fails"""
        print("🔄 Setting up fallback GUI...")
        self.fallback_mode = True
        
        self.root = tk.Tk()
        self.root.title("Trading System - Basic Mode")
        self.root.geometry("800x600")
        self.root.configure(bg='#f0f0f0')
        
        # Simple header
        header = tk.Label(self.root, text="Trading System - Basic Mode", 
                         font=('Arial', 16, 'bold'), bg='#f0f0f0')
        header.pack(pady=20)
        
        # Status display
        status_frame = tk.Frame(self.root, bg='#f0f0f0')
        status_frame.pack(fill='x', padx=20, pady=10)
        
        self.fallback_status = tk.Label(status_frame, text="System Status: Basic Mode Active", 
                                       font=('Arial', 12), bg='#f0f0f0')
        self.fallback_status.pack()
        
        # Error display
        if self.startup_errors:
            error_frame = tk.LabelFrame(self.root, text="Startup Issues", bg='#f0f0f0')
            error_frame.pack(fill='both', expand=True, padx=20, pady=10)
            
            error_text = scrolledtext.ScrolledText(error_frame, height=15)
            error_text.pack(fill='both', expand=True, padx=10, pady=10)
            
            for error in self.startup_errors:
                error_text.insert(tk.END, f"• {error}\n")
            
            error_text.config(state='disabled')
        
        # Basic controls
        control_frame = tk.Frame(self.root, bg='#f0f0f0')
        control_frame.pack(fill='x', padx=20, pady=10)
        
        tk.Button(control_frame, text="Retry Full GUI", 
                 command=self.retry_full_gui).pack(side='left', padx=5)
        tk.Button(control_frame, text="Exit", 
                 command=self.root.quit).pack(side='right', padx=5)

    def setup_modern_styles(self):
        """Configure modern professional styles"""
        style = ttk.Style()
        style.theme_use('clam')
        
        # Configure modern button styles
        style.configure('Modern.TButton', 
                       font=('Segoe UI', 9, 'bold'),
                       borderwidth=0,
                       focuscolor='none',
                       background=self.COLORS['accent_blue'],
                       foreground=self.COLORS['text_primary'])
        
        style.map('Modern.TButton',
                 background=[('active', '#106ebe'),
                           ('pressed', '#005a9e')])
        
        # Success button style
        style.configure('Success.TButton',
                       font=('Segoe UI', 9, 'bold'),
                       borderwidth=0,
                       focuscolor='none',
                       background=self.COLORS['accent_green'],
                       foreground=self.COLORS['text_primary'])
        
        style.map('Success.TButton',
                 background=[('active', '#0e6e0e'),
                           ('pressed', '#0c5a0c')])
        
        # Danger button style
        style.configure('Danger.TButton',
                       font=('Segoe UI', 9, 'bold'),
                       borderwidth=0,
                       focuscolor='none',
                       background=self.COLORS['accent_red'],
                       foreground=self.COLORS['text_primary'])
        
        style.map('Danger.TButton',
                 background=[('active', '#b82d32'),
                           ('pressed', '#9e262a')])
        
        # Emergency button style (bright red with blink effect)
        style.configure('Emergency.TButton',
                       font=('Segoe UI', 9, 'bold'),
                       borderwidth=2,
                       focuscolor='none',
                       background='#ff0000',
                       foreground='#ffffff')
        
        style.map('Emergency.TButton',
                 background=[('active', '#cc0000'),
                           ('pressed', '#990000')])
        
        # Monitor button style (special purple theme)
        style.configure('Monitor.TButton',
                       font=('Segoe UI', 10, 'bold'),
                       borderwidth=0,
                       focuscolor='none',
                       background=self.COLORS['accent_purple'],
                       foreground=self.COLORS['text_primary'])
        
        style.map('Monitor.TButton',
                 background=[('active', '#7c3aed'),
                           ('pressed', '#6d28d9')])
        
        # Monitor hover button style
        style.configure('MonitorHover.TButton',
                       font=('Segoe UI', 10, 'bold'),
                       borderwidth=1,
                       focuscolor='none',
                       relief='solid',
                       background='#7c3aed',
                       foreground='#ffffff')
        
        # Modern Entry style
        style.configure('Modern.TEntry',
                       font=('Segoe UI', 9),
                       borderwidth=1,
                       relief='solid',
                       insertcolor=self.COLORS['text_primary'],
                       background=self.COLORS['bg_accent'],
                       foreground=self.COLORS['text_primary'])
        
        # Modern labels
        style.configure('ModernTitle.TLabel',
                       font=('Segoe UI', 18, 'bold'),
                       background=self.COLORS['bg_primary'],
                       foreground=self.COLORS['text_primary'])
        
        style.configure('CardTitle.TLabel',
                       font=('Segoe UI', 12, 'bold'),
                       background=self.COLORS['bg_secondary'],
                       foreground=self.COLORS['text_primary'])
        
        style.configure('Status.TLabel',
                       font=('Segoe UI', 10),
                       background=self.COLORS['bg_secondary'],
                       foreground=self.COLORS['text_secondary'])
        
        style.configure('Success.TLabel',
                       font=('Segoe UI', 10, 'bold'),
                       background=self.COLORS['bg_secondary'],
                       foreground=self.COLORS['accent_green'])
        
        style.configure('Error.TLabel',
                       font=('Segoe UI', 10, 'bold'),
                       background=self.COLORS['bg_secondary'],
                       foreground=self.COLORS['accent_red'])
        
        # Modern combobox
        style.configure('Modern.TCombobox',
                       font=('Segoe UI', 9),
                       borderwidth=1,
                       relief='solid',
                       background=self.COLORS['bg_accent'],
                       foreground=self.COLORS['text_primary'])
        
        # Modern treeview
        style.configure('Modern.Treeview',
                       font=('Segoe UI', 9),
                       background=self.COLORS['bg_secondary'],
                       foreground=self.COLORS['text_primary'],
                       fieldbackground=self.COLORS['bg_secondary'],
                       borderwidth=0)
        
        style.configure('Modern.Treeview.Heading',
                       font=('Segoe UI', 10, 'bold'),
                       background=self.COLORS['bg_accent'],
                       foreground=self.COLORS['text_primary'],
                       borderwidth=1,
                       relief='solid')
        
        # Modern Notebook (for tabs)
        style.configure('Modern.TNotebook',
                       background=self.COLORS['bg_primary'],
                       borderwidth=0)
        
        style.configure('Modern.TNotebook.Tab',
                       background=self.COLORS['bg_accent'],
                       foreground=self.COLORS['text_secondary'],
                       padding=[20, 8],
                       font=('Segoe UI', 10, 'bold'))
        
        style.map('Modern.TNotebook.Tab',
                 background=[('selected', self.COLORS['accent_purple']),
                           ('active', self.COLORS['bg_highlight'])],
                 foreground=[('selected', self.COLORS['text_primary']),
                           ('active', self.COLORS['text_primary'])])
        
        # Value labels (for important numbers)
        style.configure('Value.TLabel',
                       font=('Segoe UI', 9, 'bold'),
                       background=self.COLORS['bg_secondary'],
                       foreground=self.COLORS['accent_cyan'])
        
        # Modern checkbutton
        style.configure('Modern.TCheckbutton',
                       font=('Segoe UI', 9),
                       background=self.COLORS['bg_secondary'],
                       foreground=self.COLORS['text_secondary'],
                       focuscolor='none')
        
        # Modern LabelFrame
        style.configure('Modern.TLabelframe',
                       background=self.COLORS['bg_secondary'],
                       foreground=self.COLORS['text_primary'],
                       borderwidth=1,
                       relief='solid')
        
        style.configure('Modern.TLabelframe.Label',
                       background=self.COLORS['bg_secondary'],
                       foreground=self.COLORS['text_primary'],
                       font=('Segoe UI', 9, 'bold'))

    def create_modern_header(self):
        """Create modern header with app title, version, and animated connection status"""
        # Header card container with reduced padding
        header_container = tk.Frame(self.root, bg=self.COLORS['bg_primary'])
        header_container.pack(fill='x', padx=15, pady=(15, 8))
        
        # Main header card (pack first)
        header_card = tk.Frame(header_container, bg=self.COLORS['bg_secondary'], 
                              relief='flat', bd=0)
        header_card.pack(fill='x', pady=(0, 2))
        
        # Add shadow effect (pack after main card)
        shadow_frame = tk.Frame(header_container, bg=self.COLORS['card_shadow'], height=2)
        shadow_frame.pack(fill='x')
        
        # Header content with reduced padding
        header_content = tk.Frame(header_card, bg=self.COLORS['bg_secondary'])
        header_content.pack(fill='x', padx=20, pady=15)
        
        # Left side - Title and version
        title_frame = tk.Frame(header_content, bg=self.COLORS['bg_secondary'])
        title_frame.pack(side='left')
        
        title_label = ttk.Label(title_frame, text="🏆 Modern AI Gold Grid Trading System", 
                               style='ModernTitle.TLabel')
        title_label.pack(anchor='w')
        
        version_label = ttk.Label(title_frame, text="v3.0 Professional Edition", 
                                style='Status.TLabel')
        version_label.pack(anchor='w', pady=(5, 0))
        
        # Right side - Connection status with animated indicator
        status_frame = tk.Frame(header_content, bg=self.COLORS['bg_secondary'])
        status_frame.pack(side='right')
        
        # Animated connection indicator
        self.connection_indicator = tk.Canvas(status_frame, width=20, height=20, 
                                            bg=self.COLORS['bg_secondary'], 
                                            highlightthickness=0)
        self.connection_indicator.pack(side='left', padx=(0, 10))
        
        self.connection_status = ttk.Label(status_frame, text="Disconnected", 
                                         style='Error.TLabel', font=('Segoe UI', 12, 'bold'))
        self.connection_status.pack(side='left')
        
        # Initialize connection indicator
        self.update_connection_indicator(False)

    def create_control_cards(self):
        """Create modern control panel with card-based layout"""
        # Control cards container with reduced padding
        control_container = tk.Frame(self.root, bg=self.COLORS['bg_primary'])
        control_container.pack(fill='x', padx=15, pady=8)
        
        # First row of cards with reduced spacing
        cards_row1 = tk.Frame(control_container, bg=self.COLORS['bg_primary'])
        cards_row1.pack(fill='x', pady=(0, 8))
        
        # Connection Control Card
        self.create_connection_card(cards_row1)
        
        # Terminal Selection Card
        self.create_terminal_card(cards_row1)
        
        # Trading Control Card
        self.create_trading_card(cards_row1)
        
        # Live Stats Card
        self.create_live_stats_card(cards_row1)

    def create_connection_card(self, parent):
        """Create connection control card"""
        card_content = self.create_card(parent, "🔌 Connection", width=280, height=140)
        # Pack the card container properly
        card_content.card_container.pack(side='left', padx=(0, 12), fill='y')
        
        # Connection buttons with modern styling
        btn_frame = tk.Frame(card_content, bg=self.COLORS['bg_secondary'])
        btn_frame.pack(fill='x', pady=(0, 8))
        
        self.connect_btn = ttk.Button(btn_frame, text="🔌 Connect MT5", 
                                     command=self.connect_mt5, style='Modern.TButton')
        self.connect_btn.pack(side='left', padx=(0, 6), fill='x', expand=True)
        
        self.disconnect_btn = ttk.Button(btn_frame, text="🔌 Disconnect", 
                                        command=self.disconnect_mt5, style='Danger.TButton')
        self.disconnect_btn.pack(side='right', fill='x', expand=True)
        
        # Connection status display
        status_frame = tk.Frame(card_content, bg=self.COLORS['bg_secondary'])
        status_frame.pack(fill='x', pady=(0, 6))
        
        status_label = ttk.Label(status_frame, text="Status:", style='Status.TLabel')
        status_label.pack(side='left')
        
        self.connection_status_label = ttk.Label(status_frame, text="Disconnected", 
                                               style='Error.TLabel')
        self.connection_status_label.pack(side='right')
        
        # Terminal path display
        path_frame = tk.Frame(card_content, bg=self.COLORS['bg_secondary'])
        path_frame.pack(fill='x')
        
        path_label = ttk.Label(path_frame, text="Terminal Path:", style='Status.TLabel')
        path_label.pack(anchor='w')
        
        self.terminal_path_label = ttk.Label(path_frame, text="Not selected", 
                                           style='Status.TLabel', font=('Segoe UI', 8))
        self.terminal_path_label.pack(anchor='w', pady=(2, 0))

    def create_terminal_card(self, parent):
        """Create terminal selection card"""
        card_content = self.create_card(parent, "🖥️ Terminal Selection", width=280, height=140)
        card_content.card_container.pack(side='left', padx=(0, 12), fill='y')
        
        # Scan buttons
        btn_frame = tk.Frame(card_content, bg=self.COLORS['bg_secondary'])
        btn_frame.pack(fill='x', pady=(0, 8))
        
        self.scan_btn = ttk.Button(btn_frame, text="🔍 Scan", 
                                  command=self.scan_terminals, style='Modern.TButton')
        self.scan_btn.pack(side='left', padx=(0, 6), fill='x', expand=True)
        
        self.refresh_btn = ttk.Button(btn_frame, text="🔄 Refresh", 
                                     command=self.refresh_terminals, style='Modern.TButton')
        self.refresh_btn.pack(side='right', fill='x', expand=True)
        
        # Terminal selection dropdown
        self.terminal_var = tk.StringVar()
        self.terminal_combobox = ttk.Combobox(card_content, textvariable=self.terminal_var, 
                                            state='readonly', style='Modern.TCombobox',
                                            font=('Segoe UI', 8))
        self.terminal_combobox.pack(fill='x', pady=(0, 6))
        self.terminal_combobox.bind('<<ComboboxSelected>>', self.on_terminal_selected)
        
        # Terminal info with modern styling
        self.terminal_info_label = ttk.Label(card_content, text="Click 'Scan' to find terminals", 
                                           style='Status.TLabel', font=('Segoe UI', 8))
        self.terminal_info_label.pack(fill='x')

    def create_trading_card(self, parent):
        """Create enhanced trading control card"""
        card_content = self.create_card(parent, "⚡ Trading Control", width=320, height=280)
        card_content.card_container.pack(side='left', padx=(0, 12), fill='y')
        
        # === MAIN TRADING CONTROLS ===
        main_controls_frame = ttk.LabelFrame(card_content, text="🎮 Main Controls", style='Modern.TLabelframe')
        main_controls_frame.pack(fill='x', pady=(0, 8))
        
        # Trading buttons - improved layout
        btn_frame = tk.Frame(main_controls_frame, bg=self.COLORS['bg_secondary'])
        btn_frame.pack(fill='x', pady=5)
        
        self.start_btn = ttk.Button(btn_frame, text="▶️ Start Trading", 
                                   command=self.start_trading, style='Success.TButton')
        self.start_btn.pack(side='left', padx=(0, 6), fill='x', expand=True)
        
        self.stop_btn = ttk.Button(btn_frame, text="⏹️ Stop Trading", 
                                  command=self.stop_trading, style='Danger.TButton')
        self.stop_btn.pack(side='right', fill='x', expand=True)
        
        # Settings in a grid layout
        settings_frame = tk.Frame(main_controls_frame, bg=self.COLORS['bg_secondary'])
        settings_frame.pack(fill='x', pady=(0, 5))
        
        # Base lot size
        ttk.Label(settings_frame, text="Base Lot:", style='Status.TLabel').grid(row=0, column=0, sticky='w', padx=(5,0))
        self.lot_size_var = tk.StringVar(value="0.01")
        self.lot_size_entry = ttk.Entry(settings_frame, textvariable=self.lot_size_var, 
                                       width=10, style='Modern.TEntry')
        self.lot_size_entry.grid(row=0, column=1, sticky='e', padx=(0,5))
        self.lot_size_entry.bind('<Return>', self.update_lot_size)
        
        # Max positions
        ttk.Label(settings_frame, text="Max Positions:", style='Status.TLabel').grid(row=1, column=0, sticky='w', padx=(5,0))
        self.max_pos_var = tk.StringVar(value="50")
        self.max_pos_entry = ttk.Entry(settings_frame, textvariable=self.max_pos_var, 
                                      width=10, style='Modern.TEntry')
        self.max_pos_entry.grid(row=1, column=1, sticky='e', padx=(0,5))
        self.max_pos_entry.bind('<Return>', self.update_max_positions)
        
        # Configure grid weights
        settings_frame.columnconfigure(0, weight=1)
        settings_frame.columnconfigure(1, weight=0)
        
        # === DEBUG TOOLS ===
        debug_frame = ttk.LabelFrame(card_content, text="🔧 Debug Tools", style='Modern.TLabelframe')
        debug_frame.pack(fill='x', pady=(0, 8))
        
        # Debug controls in a compact layout
        debug_controls = tk.Frame(debug_frame, bg=self.COLORS['bg_secondary'])
        debug_controls.pack(fill='x', pady=5)
        
        self.debug_distance_var = tk.BooleanVar(value=False)
        self.debug_distance_check = ttk.Checkbutton(debug_controls, text="🐛 Distance Debug", 
                                                   variable=self.debug_distance_var,
                                                   command=self.toggle_debug_distance,
                                                   style='Modern.TCheckbutton')
        self.debug_distance_check.pack(side='left', padx=(5, 15))
        
        self.debug_tracking_var = tk.BooleanVar(value=False)
        self.debug_tracking_check = ttk.Checkbutton(debug_controls, text="🐛 Tracking Debug", 
                                                   variable=self.debug_tracking_var,
                                                   command=self.toggle_debug_tracking,
                                                   style='Modern.TCheckbutton')
        self.debug_tracking_check.pack(side='left')
        
        # === EMERGENCY CONTROLS ===
        emergency_frame = ttk.LabelFrame(card_content, text="🚨 Emergency", style='Modern.TLabelframe')
        emergency_frame.pack(fill='x')
        
        self.emergency_btn = ttk.Button(emergency_frame, text="🚨 EMERGENCY STOP", 
                                       command=self.emergency_stop, style='Emergency.TButton')
        self.emergency_btn.pack(fill='x', pady=5)

    def create_live_stats_card(self, parent):
        """Create live statistics card"""
        card_content = self.create_card(parent, "📊 Live Stats", width=300, height=200)
        card_content.card_container.pack(side='right', fill='y')
        
        # Current P&L display
        pnl_frame = tk.Frame(card_content, bg=self.COLORS['bg_secondary'])
        pnl_frame.pack(fill='x', pady=(0, 6))
        
        pnl_label = ttk.Label(pnl_frame, text="💰 Current P&L:", style='Status.TLabel')
        pnl_label.pack(side='left')
        
        self.pnl_value_label = ttk.Label(pnl_frame, text="$0.00", style='Success.TLabel')
        self.pnl_value_label.pack(side='right')
        
        # Active positions count
        positions_frame = tk.Frame(card_content, bg=self.COLORS['bg_secondary'])
        positions_frame.pack(fill='x', pady=(0, 6))
        
        pos_count_label = ttk.Label(positions_frame, text="📊 Active Pos:", style='Status.TLabel')
        pos_count_label.pack(side='left')
        
        self.active_pos_label = ttk.Label(positions_frame, text="0/50", style='Status.TLabel')
        self.active_pos_label.pack(side='right')
        
        # Portfolio health with progress indicator
        health_frame = tk.Frame(card_content, bg=self.COLORS['bg_secondary'])
        health_frame.pack(fill='x', pady=(0, 6))
        
        self.portfolio_label = ttk.Label(health_frame, text="💼 Portfolio Health", 
                                        style='Status.TLabel')
        self.portfolio_label.pack(anchor='w')
        
        # Health progress bar (smaller)
        self.health_canvas = tk.Canvas(health_frame, width=260, height=6,
                                     bg=self.COLORS['bg_accent'], highlightthickness=0)
        self.health_canvas.pack(fill='x', pady=(4, 0))
        
        # Volume balance with visual indicator
        volume_frame = tk.Frame(card_content, bg=self.COLORS['bg_secondary'])
        volume_frame.pack(fill='x')
        
        self.volume_label = ttk.Label(volume_frame, text="⚖️ Volume Balance", 
                                     style='Status.TLabel')
        self.volume_label.pack(anchor='w')
        
        # Volume visualization (smaller)
        self.volume_canvas = tk.Canvas(volume_frame, width=260, height=25,
                                     bg=self.COLORS['bg_accent'], highlightthickness=0)
        self.volume_canvas.pack(fill='x', pady=(4, 0))

    def create_card(self, parent, title, width=None, height=None):
        """Create a modern card container with shadow effect"""
        # Card container with shadow
        card_container = tk.Frame(parent, bg=self.COLORS['bg_primary'])
        if width:
            card_container.configure(width=width)
            card_container.pack_propagate(False)  # Maintain fixed width
        if height:
            card_container.configure(height=height)
            card_container.pack_propagate(False)  # Maintain fixed height
        
        # Main card (pack first to ensure proper layout)
        card = tk.Frame(card_container, bg=self.COLORS['bg_secondary'], 
                       relief='flat', bd=0)
        card.pack(fill='both', expand=True, padx=0, pady=(0, 2))
        
        # Shadow effect (pack after main card)
        shadow = tk.Frame(card_container, bg=self.COLORS['card_shadow'], height=2)
        shadow.pack(side='bottom', fill='x')
        
        # Card header
        header = tk.Frame(card, bg=self.COLORS['bg_accent'])
        header.pack(fill='x')
        
        title_label = ttk.Label(header, text=title, style='CardTitle.TLabel')
        title_label.pack(side='left', padx=12, pady=8)
        
        # Card content area with reduced padding
        content = tk.Frame(card, bg=self.COLORS['bg_secondary'])
        content.pack(fill='both', expand=True, padx=12, pady=12)
        
        # Return both container and content for proper layout management
        content.card_container = card_container
        return content

    def create_data_section(self):
        """Create modern data section with enhanced positions table"""
        # Data section container with reduced padding
        data_container = tk.Frame(self.root, bg=self.COLORS['bg_primary'])
        data_container.pack(fill='both', expand=True, padx=15, pady=8)
        
        # Positions card
        positions_card_content = self.create_large_card(data_container, "📊 Active Positions")
        positions_card_content.card_container.pack(fill='both', expand=True)
        
        # Positions toolbar
        toolbar = tk.Frame(positions_card_content, bg=self.COLORS['bg_secondary'])
        toolbar.pack(fill='x', pady=(0, 8))
        
        # Position count indicator
        self.pos_count_label = ttk.Label(toolbar, text="Positions: 0/50", 
                                        style='Status.TLabel')
        self.pos_count_label.pack(side='left')
        
        # Filter buttons
        filter_frame = tk.Frame(toolbar, bg=self.COLORS['bg_secondary'])
        filter_frame.pack(side='right')
        
        # Create modern treeview for positions
        tree_frame = tk.Frame(positions_card_content, bg=self.COLORS['bg_secondary'])
        tree_frame.pack(fill='both', expand=True)
        
        # Enhanced columns with better organization
        columns = ('Ticket', 'Type', 'Volume', 'Open Price', 'Current Price', 
                  'Profit $', '$/Lot', 'Role', 'Efficiency', 'Status')
        
        # More compact treeview
        self.positions_tree = ttk.Treeview(tree_frame, columns=columns, show='headings', 
                                         style='Modern.Treeview', height=8)
        
        # Configure columns with smaller widths
        column_configs = {
            'Ticket': {'width': 70, 'anchor': 'center'},
            'Type': {'width': 50, 'anchor': 'center'},
            'Volume': {'width': 70, 'anchor': 'center'},
            'Open Price': {'width': 80, 'anchor': 'e'},
            'Current Price': {'width': 80, 'anchor': 'e'},
            'Profit $': {'width': 80, 'anchor': 'e'},
            '$/Lot': {'width': 70, 'anchor': 'e'},
            'Role': {'width': 70, 'anchor': 'center'},
            'Efficiency': {'width': 80, 'anchor': 'center'},
            'Status': {'width': 70, 'anchor': 'center'}
        }
        
        for col in columns:
            config = column_configs[col]
            self.positions_tree.heading(col, text=col, anchor='center')
            self.positions_tree.column(col, width=config['width'], 
                                     anchor=config['anchor'], minwidth=60)
        
        # Modern scrollbars
        v_scrollbar = ttk.Scrollbar(tree_frame, orient='vertical', 
                                   command=self.positions_tree.yview)
        h_scrollbar = ttk.Scrollbar(tree_frame, orient='horizontal', 
                                   command=self.positions_tree.xview)
        
        self.positions_tree.configure(yscrollcommand=v_scrollbar.set, 
                                    xscrollcommand=h_scrollbar.set)
        
        # Pack treeview and scrollbars
        self.positions_tree.grid(row=0, column=0, sticky='nsew')
        v_scrollbar.grid(row=0, column=1, sticky='ns')
        h_scrollbar.grid(row=1, column=0, sticky='ew')
        
        tree_frame.grid_rowconfigure(0, weight=1)
        tree_frame.grid_columnconfigure(0, weight=1)
        
        # Configure alternating row colors
        self.positions_tree.tag_configure("oddrow", background=self.COLORS['bg_secondary'])
        self.positions_tree.tag_configure("evenrow", background=self.COLORS['bg_accent'])
        
        # Configure efficiency tags with modern colors
        self.positions_tree.tag_configure("excellent", 
                                        background=self.COLORS['accent_green'], 
                                        foreground=self.COLORS['text_primary'])
        self.positions_tree.tag_configure("good", 
                                        background='#2d5a2d', 
                                        foreground=self.COLORS['text_primary'])
        self.positions_tree.tag_configure("fair", 
                                        background='#5a5a2d', 
                                        foreground=self.COLORS['text_primary'])
        self.positions_tree.tag_configure("poor", 
                                        background=self.COLORS['accent_red'], 
                                        foreground=self.COLORS['text_primary'])

    def create_large_card(self, parent, title):
        """Create a large card for major sections"""
        # Card container
        card_container = tk.Frame(parent, bg=self.COLORS['bg_primary'])
        
        # Main card (pack first to ensure proper layout)
        card = tk.Frame(card_container, bg=self.COLORS['bg_secondary'], 
                       relief='flat', bd=0)
        card.pack(fill='both', expand=True, padx=0, pady=(0, 2))
        
        # Shadow effect (pack after main card)
        shadow = tk.Frame(card_container, bg=self.COLORS['card_shadow'], height=2)
        shadow.pack(side='bottom', fill='x')
        
        # Card header with modern styling (reduced padding)
        header = tk.Frame(card, bg=self.COLORS['bg_accent'])
        header.pack(fill='x')
        
        title_label = ttk.Label(header, text=title, style='CardTitle.TLabel',
                               font=('Segoe UI', 12, 'bold'))
        title_label.pack(side='left', padx=15, pady=10)
        
        # Card content area with reduced padding
        content = tk.Frame(card, bg=self.COLORS['bg_secondary'])
        content.pack(fill='both', expand=True, padx=15, pady=15)
        
        # Return both container and content for proper layout management
        content.card_container = card_container
        return content

    def create_analytics_dashboard(self):
        """Create modern analytics dashboard with cards and visualizations"""
        # Analytics container with reduced padding
        analytics_container = tk.Frame(self.root, bg=self.COLORS['bg_primary'])
        analytics_container.pack(fill='x', padx=15, pady=8)
        
        # Analytics cards row
        cards_row = tk.Frame(analytics_container, bg=self.COLORS['bg_primary'])
        cards_row.pack(fill='x')
        
        # Performance Metrics Card
        performance_card_content = self.create_card(cards_row, "📊 Performance Metrics", width=300, height=140)
        performance_card_content.card_container.pack(side='left', padx=(0, 12), fill='y')
        
        # Success rate display
        success_frame = tk.Frame(performance_card_content, bg=self.COLORS['bg_secondary'])
        success_frame.pack(fill='x', pady=(0, 4))
        
        success_label = ttk.Label(success_frame, text="Success Rate:", style='Status.TLabel')
        success_label.pack(side='left')
        
        self.success_rate_label = ttk.Label(success_frame, text="0%", style='Success.TLabel')
        self.success_rate_label.pack(side='right')
        
        # Win/Loss ratio
        winloss_frame = tk.Frame(performance_card_content, bg=self.COLORS['bg_secondary'])
        winloss_frame.pack(fill='x', pady=(0, 4))
        
        winloss_label = ttk.Label(winloss_frame, text="Win/Loss:", style='Status.TLabel')
        winloss_label.pack(side='left')
        
        self.winloss_label = ttk.Label(winloss_frame, text="0/0", style='Status.TLabel')
        self.winloss_label.pack(side='right')
        
        # Average profit per trade
        avg_profit_frame = tk.Frame(performance_card_content, bg=self.COLORS['bg_secondary'])
        avg_profit_frame.pack(fill='x', pady=(0, 4))
        
        avg_profit_label = ttk.Label(avg_profit_frame, text="Avg Profit:", style='Status.TLabel')
        avg_profit_label.pack(side='left')
        
        self.avg_profit_label = ttk.Label(avg_profit_frame, text="$0.00", style='Status.TLabel')
        self.avg_profit_label.pack(side='right')
        
        # Risk level indicator
        risk_frame = tk.Frame(performance_card_content, bg=self.COLORS['bg_secondary'])
        risk_frame.pack(fill='x')
        
        risk_label = ttk.Label(risk_frame, text="Risk Level:", style='Status.TLabel')
        risk_label.pack(side='left')
        
        self.risk_level_label = ttk.Label(risk_frame, text="Low", style='Success.TLabel')
        self.risk_level_label.pack(side='right')
        
        # Portfolio Visualization Card
        portfolio_card_content = self.create_card(cards_row, "💼 Portfolio Overview", width=280, height=140)
        portfolio_card_content.card_container.pack(side='left', padx=(0, 12), fill='y')
        
        # Mini donut chart for portfolio balance
        self.portfolio_canvas = tk.Canvas(portfolio_card_content, width=250, height=100,
                                        bg=self.COLORS['bg_secondary'], highlightthickness=0)
        self.portfolio_canvas.pack(pady=8)
        
        # Portfolio metrics
        metrics_frame = tk.Frame(portfolio_card_content, bg=self.COLORS['bg_secondary'])
        metrics_frame.pack(fill='x')
        
        self.buy_volume_label = ttk.Label(metrics_frame, text="BUY: 0.00", 
                                        style='Success.TLabel')
        self.buy_volume_label.pack(side='left')
        
        self.sell_volume_label = ttk.Label(metrics_frame, text="SELL: 0.00", 
                                         style='Error.TLabel')
        self.sell_volume_label.pack(side='right')
        
        # Smart Insights Card
        insights_card_content = self.create_card(cards_row, "🧠 Smart Insights", width=380, height=140)
        insights_card_content.card_container.pack(side='right', fill='y')
        
        self.recommendations_text = tk.Text(insights_card_content, height=5, 
                                          bg=self.COLORS['bg_accent'], 
                                          fg=self.COLORS['accent_orange'], 
                                          font=('Consolas', 8),
                                          relief='flat', bd=0, wrap='word')
        self.recommendations_text.pack(fill='both', expand=True)

    def create_log_panel(self):
        """Create modern log panel with syntax highlighting"""
        # Log container with reduced padding
        log_container = tk.Frame(self.root, bg=self.COLORS['bg_primary'])
        log_container.pack(fill='x', padx=15, pady=(8, 15))
        
        # Log card
        log_card_content = self.create_large_card(log_container, "📝 System Log")
        log_card_content.card_container.pack(fill='x')
        
        # Log controls
        controls_frame = tk.Frame(log_card_content, bg=self.COLORS['bg_secondary'])
        controls_frame.pack(fill='x', pady=(0, 8))
        
        # Log level indicator
        self.log_level_label = ttk.Label(controls_frame, text="Log Level: INFO", 
                                       style='Status.TLabel')
        self.log_level_label.pack(side='left')
        
        # Clear log button
        clear_btn = ttk.Button(controls_frame, text="🗑️ Clear Log", 
                              command=self.clear_log, style='Modern.TButton')
        clear_btn.pack(side='right')
        
        # Enhanced log text with modern styling (reduced height)
        log_frame = tk.Frame(log_card_content, bg=self.COLORS['bg_secondary'])
        log_frame.pack(fill='both', expand=True)
        
        self.log_text = scrolledtext.ScrolledText(log_frame, height=6, 
                                                bg=self.COLORS['bg_accent'], 
                                                fg=self.COLORS['text_primary'],
                                                font=('Consolas', 8),
                                                relief='flat', bd=0,
                                                wrap='word')
        self.log_text.pack(fill='both', expand=True)
        
        # Configure log text tags for syntax highlighting
        self.setup_log_highlighting()

    def setup_log_highlighting(self):
        """Setup syntax highlighting for log messages"""
        # Configure tags for different log levels and content
        self.log_text.tag_configure("ERROR", foreground=self.COLORS['accent_red'], 
                                  font=('Consolas', 9, 'bold'))
        self.log_text.tag_configure("WARNING", foreground=self.COLORS['accent_orange'])
        self.log_text.tag_configure("SUCCESS", foreground=self.COLORS['accent_green'])
        self.log_text.tag_configure("INFO", foreground=self.COLORS['text_secondary'])
        self.log_text.tag_configure("DEBUG", foreground=self.COLORS['text_muted'])
        self.log_text.tag_configure("TIMESTAMP", foreground=self.COLORS['accent_blue'])

    def debug_widget_hierarchy(self):
        """Debug widget hierarchy and visibility"""
        try:
            print("\n🔍 DEBUG: Widget hierarchy check:")
            
            # Check main window children
            root_children = self.root.winfo_children()
            print(f"   Root has {len(root_children)} children")
            
            for i, child in enumerate(root_children):
                widget_name = child.__class__.__name__
                is_mapped = child.winfo_ismapped()
                width = child.winfo_reqwidth()
                height = child.winfo_reqheight()
                print(f"   [{i}] {widget_name}: mapped={is_mapped}, size={width}x{height}")
                
                # Check if widget has children
                grandchildren = child.winfo_children()
                if grandchildren:
                    print(f"       Has {len(grandchildren)} children")
                    for j, grandchild in enumerate(grandchildren[:3]):  # Show first 3
                        gc_name = grandchild.__class__.__name__
                        gc_mapped = grandchild.winfo_ismapped()
                        print(f"         [{j}] {gc_name}: mapped={gc_mapped}")
                        
            print("🔍 DEBUG: Widget hierarchy check complete\n")
            
        except Exception as e:
            print(f"❌ Debug hierarchy failed: {e}")

    def clear_log(self):
        """Clear the log display"""
        self.log_text.delete(1.0, tk.END)
        self.trading_system.log("Log cleared by user", "INFO")

    def start_status_animations(self):
        """Start status animations and indicators"""
        self.animate_connection_indicator()
        self.update_portfolio_visualization()

    def animate_connection_indicator(self):
        """Animate connection status indicator"""
        if not hasattr(self, 'connection_indicator'):
            return
            
        # Clear canvas
        self.connection_indicator.delete("all")
        
        # Draw animated indicator based on connection status
        if self.trading_system.mt5_connected:
            # Connected - solid green circle with pulse effect
            size = 8 + (self.connection_animation_state % 3)
            self.connection_indicator.create_oval(10-size//2, 10-size//2, 
                                                10+size//2, 10+size//2,
                                                fill=self.COLORS['accent_green'], 
                                                outline=self.COLORS['accent_green'])
        else:
            # Disconnected - red circle
            self.connection_indicator.create_oval(6, 6, 14, 14,
                                                fill=self.COLORS['accent_red'], 
                                                outline=self.COLORS['accent_red'])
        
        self.connection_animation_state = (self.connection_animation_state + 1) % 10
        
        # Schedule next animation frame with reduced frequency to prevent GUI blocking
        self.root.after(1000, self.animate_connection_indicator)

    def update_connection_indicator(self, connected):
        """Update connection status display"""
        if connected:
            self.connection_status.configure(text="Connected", style='Success.TLabel')
        else:
            self.connection_status.configure(text="Disconnected", style='Error.TLabel')

    def update_portfolio_visualization(self):
        """Update portfolio donut chart visualization"""
        if not hasattr(self, 'portfolio_canvas'):
            return
            
        try:
            canvas = self.portfolio_canvas
            canvas.delete("all")
            
            # Get portfolio data
            total_volume = self.trading_system.buy_volume + self.trading_system.sell_volume
            if total_volume == 0:
                # No positions - draw empty state
                canvas.create_text(125, 60, text="No Active Positions", 
                                 fill=self.COLORS['text_muted'], 
                                 font=('Segoe UI', 11))
                return
            
            # Calculate percentages
            buy_pct = self.trading_system.buy_volume / total_volume
            sell_pct = self.trading_system.sell_volume / total_volume
            
            # Draw donut chart
            center_x, center_y = 125, 60
            radius = 35
            inner_radius = 20
            
            # Draw arcs
            if buy_pct > 0:
                extent = int(360 * buy_pct)
                canvas.create_arc(center_x-radius, center_y-radius, 
                                center_x+radius, center_y+radius,
                                start=0, extent=extent, fill=self.COLORS['accent_green'],
                                outline=self.COLORS['accent_green'], width=2)
            
            if sell_pct > 0:
                start_angle = int(360 * buy_pct)
                extent = int(360 * sell_pct)
                canvas.create_arc(center_x-radius, center_y-radius, 
                                center_x+radius, center_y+radius,
                                start=start_angle, extent=extent, 
                                fill=self.COLORS['accent_red'],
                                outline=self.COLORS['accent_red'], width=2)
            
            # Draw inner circle to create donut effect
            canvas.create_oval(center_x-inner_radius, center_y-inner_radius,
                             center_x+inner_radius, center_y+inner_radius,
                             fill=self.COLORS['bg_secondary'], 
                             outline=self.COLORS['bg_secondary'])
            
            # Draw center text
            canvas.create_text(center_x, center_y-8, text=f"{buy_pct*100:.1f}%", 
                             fill=self.COLORS['accent_green'], 
                             font=('Segoe UI', 10, 'bold'))
            canvas.create_text(center_x, center_y+8, text="BUY", 
                             fill=self.COLORS['text_secondary'], 
                             font=('Segoe UI', 8))
            
        except Exception as e:
            print(f"Error updating portfolio visualization: {str(e)}")
        
        # Schedule next update with reduced frequency to prevent GUI overload
        self.root.after(5000, self.update_portfolio_visualization)

    def update_health_progress(self):
        """Update health progress bar"""
        if not hasattr(self, 'health_canvas'):
            return
            
        canvas = self.health_canvas
        canvas.delete("all")
        
        # Get health percentage
        health = self.trading_system.portfolio_health
        
        # Draw background
        canvas.create_rectangle(0, 0, 250, 8, fill=self.COLORS['bg_accent'], 
                              outline=self.COLORS['border'])
        
        # Draw progress
        progress_width = int(250 * (health / 100))
        
        # Color based on health level
        if health >= 80:
            color = self.COLORS['accent_green']
        elif health >= 60:
            color = self.COLORS['accent_orange']
        else:
            color = self.COLORS['accent_red']
        
        if progress_width > 0:
            canvas.create_rectangle(0, 0, progress_width, 8, fill=color, outline=color)

    def update_volume_balance_visualization(self):
        """Update volume balance visualization"""
        if not hasattr(self, 'volume_canvas'):
            return
            
        canvas = self.volume_canvas
        canvas.delete("all")
        
        total_volume = self.trading_system.buy_volume + self.trading_system.sell_volume
        if total_volume == 0:
            canvas.create_text(125, 15, text="No Volume", 
                             fill=self.COLORS['text_muted'], 
                             font=('Segoe UI', 9))
            return
        
        # Calculate positions
        buy_width = int(250 * (self.trading_system.buy_volume / total_volume))
        sell_width = 250 - buy_width
        
        # Draw volume bars
        if buy_width > 0:
            canvas.create_rectangle(0, 5, buy_width, 25, 
                                  fill=self.COLORS['accent_green'], 
                                  outline=self.COLORS['accent_green'])
            canvas.create_text(buy_width//2, 15, 
                             text=f"{self.trading_system.buy_volume:.2f}", 
                             fill=self.COLORS['text_primary'], 
                             font=('Segoe UI', 8, 'bold'))
        
        if sell_width > 0:
            canvas.create_rectangle(buy_width, 5, 250, 25, 
                                  fill=self.COLORS['accent_red'], 
                                  outline=self.COLORS['accent_red'])
            canvas.create_text(buy_width + sell_width//2, 15, 
                             text=f"{self.trading_system.sell_volume:.2f}", 
                             fill=self.COLORS['text_primary'], 
                             font=('Segoe UI', 8, 'bold'))

    def scan_terminals(self):
        """Scan for available MT5 terminals"""
        try:
            self.scan_btn.config(state='disabled', text='🔍 Scanning...')
            self.refresh_btn.config(state='disabled')
            self.terminal_combobox.set('')
            self.terminal_info_label.config(text="Scanning terminals...")
            
            # Update UI to show scanning state
            self.root.update()
            
            # Scan terminals in a separate thread to prevent UI blocking
            def scan_thread():
                try:
                    terminals = self.trading_system.scan_available_terminals()
                    
                    # Update UI in main thread
                    self.root.after(0, self.update_terminal_list, terminals)
                except Exception as e:
                    self.root.after(0, self.scan_error, str(e))
            
            threading.Thread(target=scan_thread, daemon=True).start()
            
        except Exception as e:
            self.scan_btn.config(state='normal', text='🔍 Scan')
            self.refresh_btn.config(state='normal')
            messagebox.showerror("Error", f"Failed to scan terminals: {str(e)}")
    
    def update_terminal_list(self, terminals):
        """Update terminal list from scan results"""
        try:
            self.trading_system.available_terminals = terminals
            
            # Update combobox
            terminal_names = [terminal['display_name'] for terminal in terminals]
            self.terminal_combobox['values'] = terminal_names
            
            if terminals:
                self.terminal_combobox.set(terminal_names[0])  # Select first terminal
                self.on_terminal_selected()  # Update info display
                self.terminal_info_label.config(text=f"Found {len(terminals)} terminal(s)")
            else:
                self.terminal_info_label.config(text="No terminals found")
            
            self.scan_btn.config(state='normal', text='🔍 Scan')
            self.refresh_btn.config(state='normal')
            
        except Exception as e:
            self.scan_error(str(e))
    
    def scan_error(self, error_msg):
        """Handle scan error"""
        self.scan_btn.config(state='normal', text='🔍 Scan')
        self.refresh_btn.config(state='normal')
        self.terminal_info_label.config(text="Scan failed")
        messagebox.showerror("Scan Error", f"Failed to scan terminals: {error_msg}")
    
    def on_terminal_selected(self, event=None):
        """Handle terminal selection"""
        try:
            selected_name = self.terminal_var.get()
            if not selected_name or not self.trading_system.available_terminals:
                return
            
            # Find selected terminal
            selected_terminal = None
            for terminal in self.trading_system.available_terminals:
                if terminal['display_name'] == selected_name:
                    selected_terminal = terminal
                    break
            
            if selected_terminal:
                self.trading_system.selected_terminal = selected_terminal
                
                # Update info display
                info_text = f"Login: {selected_terminal['login']} | Server: {selected_terminal['server']}"
                if len(info_text) > 35:
                    info_text = info_text[:32] + "..."
                
                self.terminal_info_label.config(text=info_text)
                
        except Exception as e:
            self.terminal_info_label.config(text="Selection error")
            self.trading_system.log(f"Terminal selection error: {str(e)}", "ERROR")

    def connect_mt5(self):
        """Connect to selected MT5 terminal"""
        try:
            # Check if a terminal is selected
            if not self.trading_system.selected_terminal:
                # Show dialog to scan first
                result = messagebox.askyesno("No Terminal Selected", 
                                           "No MT5 terminal selected. Would you like to scan for terminals first?")
                if result:
                    self.scan_terminals()
                    return
                else:
                    # Try default connection
                    if self.trading_system.connect_mt5():
                        self.update_connection_indicator(True)
                        messagebox.showinfo("Success", "Connected to MetaTrader 5 (Default)")
                    else:
                        messagebox.showerror("Error", "Failed to connect to MetaTrader 5")
                    return
            
            # Connect to selected terminal
            terminal_path = self.trading_system.selected_terminal.get('path', 'default')
            display_name = self.trading_system.selected_terminal.get('display_name', 'Unknown')
            
            self.connect_btn.config(state='disabled', text='🔌 Connecting...')
            self.root.update()
            
            # Connect in separate thread to prevent UI blocking
            def connect_thread():
                try:
                    success = self.trading_system.connect_to_specific_terminal(terminal_path)
                    self.root.after(0, self.connection_complete, success, display_name)
                except Exception as e:
                    self.root.after(0, self.connection_error, str(e))
            
            threading.Thread(target=connect_thread, daemon=True).start()
            
        except Exception as e:
            self.connect_btn.config(state='normal', text='🔌 Connect MT5')
            messagebox.showerror("Error", f"Connection error: {str(e)}")
    
    def connection_complete(self, success, terminal_name):
        """Handle connection completion"""
        self.connect_btn.config(state='normal', text='🔌 Connect MT5')
        
        if success:
            self.update_connection_indicator(True)
            messagebox.showinfo("Success", f"Connected to {terminal_name}")
        else:
            messagebox.showerror("Error", f"Failed to connect to {terminal_name}")
    
    def connection_error(self, error_msg):
        """Handle connection error"""
        self.connect_btn.config(state='normal', text='🔌 Connect MT5')
        messagebox.showerror("Connection Error", f"Failed to connect: {error_msg}")

    def auto_scan_terminals(self):
        """Automatically scan for terminals on startup with timeout protection"""
        try:
            # Check if GUI is ready and scanning is not already in progress
            if not hasattr(self, 'scan_btn') or self.scan_btn.cget('state') == 'disabled':
                # GUI not ready or scan in progress, skip this auto-scan
                self.terminal_info_label.config(text="Auto-scan skipped (GUI loading...)")
                return
                
            self.terminal_info_label.config(text="Auto-scanning terminals...")
            
            # Use a separate thread for auto-scan to prevent blocking
            def auto_scan_thread():
                try:
                    terminals = self.trading_system.scan_available_terminals()
                    # Update UI in main thread
                    self.root.after(0, self.update_terminal_list, terminals)
                except Exception as e:
                    self.root.after(0, lambda: self.terminal_info_label.config(text="Auto-scan failed"))
                    self.trading_system.log(f"Auto-scan error: {str(e)}", "WARNING")
            
            threading.Thread(target=auto_scan_thread, daemon=True).start()
            
        except Exception as e:
            self.trading_system.log(f"Auto-scan error: {str(e)}", "ERROR")
            self.terminal_info_label.config(text="Auto-scan failed")

    def refresh_terminals(self):
        """Refresh the terminal list"""
        try:
            if self.scan_btn.cget('state') == 'disabled':
                # Scan already in progress
                return
                
            self.terminal_info_label.config(text="Refreshing terminals...")
            self.scan_terminals()
        except Exception as e:
            self.trading_system.log(f"Refresh error: {str(e)}", "ERROR")
            self.terminal_info_label.config(text="Refresh failed")

    def disconnect_mt5(self):
        """Disconnect from MT5"""
        self.stop_trading()
        self.trading_system.disconnect_mt5()
        self.update_connection_indicator(False)

    def start_trading(self):
        """Start automated trading"""
        if not self.trading_system.mt5_connected:
            messagebox.showerror("Error", "Please connect to MT5 first")
            return
        
        if not self.trading_system.trading_active:
            self.trading_system.trading_active = True
            self.trading_thread = threading.Thread(target=self.trading_system.trading_loop, daemon=True)
            self.trading_thread.start()
            
            self.start_btn.config(state='disabled')
            self.stop_btn.config(state='normal')
            messagebox.showinfo("Success", "Trading started")

    def stop_trading(self):
        """Stop automated trading"""
        if self.trading_system.trading_active:
            self.trading_system.trading_active = False
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            messagebox.showinfo("Success", "Trading stopped")
    
    def update_lot_size(self, event=None):
        """Update base lot size"""
        try:
            lot_size = float(self.lot_size_var.get())
            if 0.01 <= lot_size <= 100.0:
                self.trading_system.base_lot = lot_size
                self.trading_system.log(f"Base lot size updated to {lot_size}", "INFO")
            else:
                messagebox.showerror("Error", "Lot size must be between 0.01 and 100.0")
                self.lot_size_var.set(str(self.trading_system.base_lot))
        except ValueError:
            messagebox.showerror("Error", "Invalid lot size value")
            self.lot_size_var.set(str(self.trading_system.base_lot))
    
    def update_max_positions(self, event=None):
        """Update maximum positions"""
        try:
            max_pos = int(self.max_pos_var.get())
            if 1 <= max_pos <= 500:
                self.trading_system.max_positions = max_pos
                self.trading_system.log(f"Maximum positions updated to {max_pos}", "INFO")
            else:
                messagebox.showerror("Error", "Max positions must be between 1 and 500")
                self.max_pos_var.set(str(self.trading_system.max_positions))
        except ValueError:
            messagebox.showerror("Error", "Invalid max positions value")
            self.max_pos_var.set(str(self.trading_system.max_positions))
    
    def toggle_debug_distance(self):
        """Toggle debug mode for distance calculation"""
        try:
            debug_enabled = self.debug_distance_var.get()
            self.trading_system.debug_distance_calculation = debug_enabled
            
            if debug_enabled:
                self.trading_system.log("🐛 Debug distance calculation ENABLED", "INFO")
            else:
                self.trading_system.log("🐛 Debug distance calculation DISABLED", "INFO")
                
        except Exception as e:
            self.trading_system.log(f"Error toggling debug mode: {str(e)}", "ERROR")
    
    def toggle_debug_tracking(self):
        """Toggle debug mode for position tracking"""
        try:
            debug_enabled = self.debug_tracking_var.get()
            self.trading_system.debug_position_tracking = debug_enabled
            
            if debug_enabled:
                self.trading_system.log("🐛 Debug position tracking ENABLED", "INFO")
            else:
                self.trading_system.log("🐛 Debug position tracking DISABLED", "INFO")
                
        except Exception as e:
            self.trading_system.log(f"Error toggling debug tracking: {str(e)}", "ERROR")







    def emergency_stop(self):
        """Emergency stop - immediately halt all trading and close positions"""
        try:
            # Stop trading immediately
            self.trading_system.trading_active = False
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            
            # Log emergency stop
            self.trading_system.log("🚨 EMERGENCY STOP ACTIVATED", "WARNING")
            
            # Show confirmation dialog
            result = messagebox.askyesno("Emergency Stop", 
                                       "Emergency stop activated!\n\nDo you want to close all open positions?")
            
            if result and self.trading_system.mt5_connected:
                # Close all positions (this would need MT5 implementation)
                self.trading_system.log("Attempting to close all positions...", "WARNING")
                # Note: Actual position closing would require MT5 implementation
                
            messagebox.showwarning("Emergency Stop", "All trading activities have been halted!")
            
        except Exception as e:
            self.trading_system.log(f"Error during emergency stop: {str(e)}", "ERROR")
            messagebox.showerror("Error", f"Emergency stop failed: {str(e)}")

    def update_positions_display(self):
        """Update positions in the modern treeview"""
        try:
            # Clear existing items
            if hasattr(self, 'positions_tree'):
                for item in self.positions_tree.get_children():
                    self.positions_tree.delete(item)
                    
                # Get current positions from trading system
                positions = self.trading_system.positions
                
                # Add positions to tree
                for pos in positions:
                    profit_color = 'green' if pos.profit > 0 else 'red' if pos.profit < 0 else 'black'
                    self.positions_tree.insert('', 'end', values=(
                        pos.ticket,
                        pos.type,
                        pos.volume,
                        f"{pos.open_price:.5f}",
                        f"{pos.current_price:.5f}",
                        f"${pos.profit:.2f}",
                        f"{(pos.profit / abs(pos.open_price * pos.volume * 100000)) * 100:.2f}%" if pos.open_price != 0 else "0%",
                        pos.role,
                        pos.efficiency
                    ), tags=(profit_color,))
                    
        except Exception as e:
            self.trading_system.log(f"Error updating positions display: {str(e)}", "ERROR")

    def update_status_display(self):
        """Update status labels with current trading information"""
        try:
            # Update account info if available
            if hasattr(self, 'account_balance_label') and self.trading_system.mt5_connected:
                if hasattr(self.trading_system, 'get_account_info'):
                    account_info = self.trading_system.get_account_info()
                    if account_info:
                        self.account_balance_label.config(text=f"${account_info.get('balance', 0):.2f}")
                else:
                    # Fallback display
                    self.account_balance_label.config(text="Connected")
                    
        except Exception as e:
            self.trading_system.log(f"Error updating status display: {str(e)}", "ERROR")

    def auto_scan_symbols(self):
        """Auto scan for available symbols"""
        try:
            if self.trading_system.mt5_connected:
                if hasattr(self.trading_system, 'get_available_symbols'):
                    symbols = self.trading_system.get_available_symbols()
                    self.trading_system.log(f"Found {len(symbols)} available symbols", "INFO")
                else:
                    # Fallback - just log that MT5 is connected
                    self.trading_system.log("MT5 connected - symbol scanning not implemented", "INFO")
            else:
                self.trading_system.log("MT5 not connected for symbol scanning", "WARNING")
        except Exception as e:
            self.trading_system.log(f"Auto-scan error: {e}", "ERROR")

    def safe_auto_scan_terminals(self):
        """Safely auto-scan terminals without blocking GUI"""
        try:
            if hasattr(self, 'auto_scan_terminals'):
                # Run in a separate thread to avoid blocking
                import threading
                scan_thread = threading.Thread(target=self.auto_scan_terminals, daemon=True)
                scan_thread.start()
                self.trading_system.log("Auto-scan started in background thread", "INFO")
            else:
                self.trading_system.log("Auto-scan method not available", "WARNING")
        except Exception as e:
            self.trading_system.log(f"Auto-scan error: {e}", "ERROR")

    def update_loop(self):
        """Enhanced GUI update loop with better error handling"""
        try:
            # Skip updates if MT5 is not connected to reduce CPU load
            if hasattr(self.trading_system, 'mt5_connected') and not self.trading_system.mt5_connected:
                # Only update log display when not connected
                self.update_log_display()
            else:
                # Full update when connected
                if hasattr(self.trading_system, 'update_positions'):
                    self.trading_system.update_positions()
                if hasattr(self, 'update_positions_display'):
                    self.update_positions_display()
                if hasattr(self, 'update_log_display'):
                    self.update_log_display()
            
            # 🆕 Independent Portfolio Distribution System (every 30 seconds)
            if (hasattr(self.trading_system, 'ai_margin_intelligence') and 
                self.trading_system.ai_margin_intelligence):
                
                # 🆕 Debug: แสดงการตรวจสอบ GUI Update Loop
                if not hasattr(self, '_debug_distribution_check'):
                    self._debug_distribution_check = True
                    self.trading_system.log(f"🔄 GUI Update Loop: Independent Distribution System check enabled", "INFO")
                
                current_time = time.time()
                if not hasattr(self, '_last_distribution_time'):
                    self._last_distribution_time = 0
                
                if current_time - self._last_distribution_time > 30:  # 30 seconds interval
                    try:
                        distribution_result = self.trading_system.independent_portfolio_distribution_system()
                        if distribution_result.get('success'):
                            if distribution_result.get('actions_taken'):
                                self.trading_system.log(f"🔄 Independent Distribution: {len(distribution_result['actions_taken'])} actions taken", "INFO")
                                for action in distribution_result['actions_taken']:
                                    self.trading_system.log(f"✅ {action['action']}: {action['result']}", "INFO")
                                
                                if distribution_result.get('improvements_made'):
                                    for improvement in distribution_result['improvements_made']:
                                        self.trading_system.log(f"📈 Improvement: {improvement}", "INFO")
                                
                                self.trading_system.log(f"🎯 Distribution Score: {distribution_result.get('optimization_score', 0):.1f}/100", "INFO")
                            else:
                                self.trading_system.log(f"🔄 Independent Distribution: {distribution_result.get('message', 'No actions needed')}", "INFO")
                        
                        self._last_distribution_time = current_time
                    except Exception as e:
                        self.trading_system.log(f"Warning: Independent distribution system failed: {str(e)}", "WARNING")
            
        except Exception as e:
            # Use trading system logger if available, fallback to print
            if hasattr(self, 'trading_system'):
                self.trading_system.log(f"GUI update error: {str(e)}", "ERROR")
            else:
                print(f"GUI update error: {str(e)}")
        
        # Schedule next update (reduced frequency for better stability)
        if hasattr(self, 'root') and self.root:
            self.root.after(2500, self.update_loop)

    def update_log_display(self):
        """Update log display with enhanced formatting"""
        try:
            if not hasattr(self, 'log_text'):
                return
                
            while True:
                message = self.trading_system.log_queue.get_nowait()
                
                # Insert message with appropriate styling
                self.log_text.insert(tk.END, message + "\n")
                
                # Apply syntax highlighting
                lines = self.log_text.get("1.0", tk.END).split('\n')
                current_line = len(lines) - 2  # -2 because of the trailing newline
                
                if current_line > 0:
                    line_start = f"{current_line}.0"
                    line_end = f"{current_line}.end"
                    
                    # Apply tags based on content
                    if "ERROR" in message:
                        self.log_text.tag_add("ERROR", line_start, line_end)
                    elif "WARNING" in message or "WARN" in message:
                        self.log_text.tag_add("WARNING", line_start, line_end)
                    elif "✅" in message or "SUCCESS" in message:
                        self.log_text.tag_add("SUCCESS", line_start, line_end)
                    elif any(icon in message for icon in ["🎯", "📡", "💰", "ℹ️"]):
                        self.log_text.tag_add("INFO", line_start, line_end)
                
                self.log_text.see(tk.END)
                
        except queue.Empty:
            pass
        except Exception as e:
            print(f"Error updating log display: {str(e)}")

    def retry_full_gui(self):
        """Retry loading the full GUI from fallback mode"""
        try:
            self.root.destroy()
            self.setup_gui()
            self.gui_components_loaded = True
            messagebox.showinfo("Success", "Full GUI loaded successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load full GUI: {e}")
            self.setup_fallback_gui()

    def run(self):
        """Start the modern GUI application"""
        self.trading_system.log("🏆 Modern AI Gold Grid Trading System v3.0 Started")
        self.trading_system.log("🎨 Professional GUI Interface Loaded")
        self.trading_system.log("🔌 Ready for MT5 connection")
        self.root.mainloop()

def main():
    """Main application entry point with comprehensive error handling"""
    print("🚀 Starting Huakuy Trading System...")
    print(f"📦 MT5 Available: {MT5_AVAILABLE}")
    print(f"📦 Pandas Available: {pd is not None}")
    print(f"📦 NumPy Available: {np is not None}")
    
    try:
        print("🔄 Creating GUI application...")
        app = TradingGUI()
        
        print("🎯 Starting application main loop...")
        
        # 🆕 Start Independent Portfolio Distribution System in background
        if hasattr(app, 'trading_system') and app.trading_system.ai_margin_intelligence:
            print("🔄 Starting Independent Portfolio Distribution System...")
            try:
                # Run initial distribution analysis
                initial_distribution = app.trading_system.independent_portfolio_distribution_system()
                if initial_distribution.get('success'):
                    print(f"✅ Initial Distribution Analysis: {initial_distribution.get('message', 'Completed')}")
                    if initial_distribution.get('optimization_score'):
                        print(f"🎯 Initial Distribution Score: {initial_distribution['optimization_score']:.1f}/100")
                    if initial_distribution.get('distribution_quality'):
                        print(f"📊 Distribution Quality: {initial_distribution['distribution_quality']}")
                else:
                    print(f"⚠️ Initial Distribution Analysis: {initial_distribution.get('message', 'No actions needed')}")
            except Exception as e:
                print(f"Warning: Initial distribution analysis failed: {str(e)}")
        
        app.run()
        
    except ImportError as e:
        error_msg = f"Missing required dependency: {str(e)}"
        print(f"❌ {error_msg}")
        try:
            messagebox.showerror("Dependency Error", error_msg)
        except:
            print("Could not show error dialog - tkinter may not be available")
            
    except Exception as e:
        error_msg = f"Application failed to start: {str(e)}"
        print(f"❌ {error_msg}")
        print("📊 Error details:")
        import traceback
        traceback.print_exc()
        
        try:
            messagebox.showerror("Critical Error", error_msg)
        except:
            print("Could not show error dialog")
    
    print("🏁 Application terminated")

if __name__ == "__main__":
    main()

    def update_monitor_data(self):
        """Update all monitor data"""
        try:
            if not hasattr(self, 'monitor_window') or not self.monitor_window.winfo_exists():
                return
                
            # Update overview tab
            self.update_overview_data()
            
            # Update closing analysis
            self.update_closing_analysis()
            
            # Update smart routing
            self.update_routing_data()
            
            # Update live monitoring
            self.update_live_activity()
            
            # Schedule next update
            self.monitor_update_job = self.monitor_window.after(2000, self.update_monitor_data)
            
        except Exception as e:
            self.trading_system.log(f"Error updating monitor data: {str(e)}", "ERROR")

    def update_overview_data(self):
        """Update overview tab data"""
        try:
            positions = self.trading_system.positions
            
            # Update summary
            buy_positions = [p for p in positions if p.type == "BUY"]
            sell_positions = [p for p in positions if p.type == "SELL"]
            total_profit = sum(p.profit for p in positions)
            
            buy_volume = sum(p.volume for p in buy_positions)
            sell_volume = sum(p.volume for p in sell_positions)
            total_volume = buy_volume + sell_volume
            buy_ratio = (buy_volume / total_volume * 100) if total_volume > 0 else 50
            sell_ratio = 100 - buy_ratio
            
            # Update summary labels
            self.summary_labels['total_positions'].config(text=str(len(positions)))
            self.summary_labels['buy_positions'].config(text=str(len(buy_positions)))
            self.summary_labels['sell_positions'].config(text=str(len(sell_positions)))
            self.summary_labels['total_profit'].config(text=f"${total_profit:.2f}")
            self.summary_labels['portfolio_health'].config(text=f"{self.trading_system.portfolio_health:.1f}%")
            self.summary_labels['balance_ratio'].config(text=f"{buy_ratio:.0f}:{sell_ratio:.0f}")
            
            # Update positions table
            # Clear existing items
            for item in self.positions_tree.get_children():
                self.positions_tree.delete(item)
            
            # Add current positions
            for position in positions:
                # Calculate additional data
                profit_percent = (position.profit_per_lot / position.open_price) * 100 if position.open_price > 0 else 0
                distance = self.trading_system.calculate_position_distance_from_market(position)
                
                # Get hold score from tracker
                tracker = self.trading_system.position_tracker.get(position.ticket, {})
                hold_score = tracker.get('hold_score', 50)
                
                # Format values
                values = (
                    str(position.ticket),
                    position.type,
                    f"{position.volume:.2f}",
                    f"{position.open_price:.2f}",
                    f"{position.current_price:.2f}",
                    f"${position.profit:.2f}",
                    f"{profit_percent:.2f}%",
                    f"{distance:.1f}",
                    position.role,
                    f"{hold_score}/100"
                )
                
                # Color coding based on profit
                tags = ()
                if position.profit > 0:
                    tags = ('profit',)
                elif position.profit < 0:
                    tags = ('loss',)
                
                self.positions_tree.insert('', 'end', values=values, tags=tags)
            
            # Configure tags for colors
            self.positions_tree.tag_configure('profit', foreground='#107c10')
            self.positions_tree.tag_configure('loss', foreground='#d13438')
            
        except Exception as e:
            self.trading_system.log(f"Error updating overview data: {str(e)}", "ERROR")

    def update_closing_analysis(self):
        """Update closing analysis tab"""
        try:
            # Clear previous analysis
            self.closing_analysis_text.delete(1.0, tk.END)
            
            # Analyze closing candidates
            positions = self.trading_system.positions
            profitable_positions = [p for p in positions if p.profit > 0]
            
            if not profitable_positions:
                self.closing_analysis_text.insert(tk.END, "📊 No profitable positions available for closing analysis.\n\n")
                return
            
            # Sort by distance (farthest first) - same as system logic
            positions_with_distance = []
            for pos in profitable_positions:
                distance = self.trading_system.calculate_position_distance_from_market(pos)
                positions_with_distance.append((pos, distance))
            
            sorted_positions = sorted(positions_with_distance, key=lambda x: x[1], reverse=True)
            
            self.closing_analysis_text.insert(tk.END, "🎯 CLOSING ANALYSIS - Current Candidates\n")
            self.closing_analysis_text.insert(tk.END, "=" * 60 + "\n\n")
            
            for i, (position, distance) in enumerate(sorted_positions[:10]):  # Top 10 candidates
                profit_percent = (position.profit_per_lot / position.open_price) * 100 if position.open_price > 0 else 0
                tracker = self.trading_system.position_tracker.get(position.ticket, {})
                hold_score = tracker.get('hold_score', 50)
                
                # Determine closing likelihood
                likelihood = "LOW"
                reason = "Below thresholds"
                
                if profit_percent >= 8.0:
                    likelihood = "HIGH"
                    reason = "Target reached (8%+)"
                elif profit_percent >= 6.0 and hold_score <= 25 and self.trading_system.portfolio_health < 60:
                    likelihood = "HIGH"
                    reason = "Portfolio concern"
                elif self.trading_system.portfolio_health < 25 and profit_percent > 4.0 and hold_score <= 30:
                    likelihood = "VERY HIGH"
                    reason = "Emergency mode"
                elif len(positions) > self.trading_system.max_positions * 0.9 and profit_percent > 5.0 and hold_score <= 20:
                    likelihood = "MEDIUM"
                    reason = "Position optimization"
                
                self.closing_analysis_text.insert(tk.END, f"#{i+1} Ticket {position.ticket} ({position.type})\n")
                self.closing_analysis_text.insert(tk.END, f"   💰 Profit: ${position.profit:.2f} ({profit_percent:.2f}%)\n")
                self.closing_analysis_text.insert(tk.END, f"   📏 Distance: {distance:.1f} pips\n")
                self.closing_analysis_text.insert(tk.END, f"   🎯 Hold Score: {hold_score}/100\n")
                self.closing_analysis_text.insert(tk.END, f"   📊 Role: {position.role} | Efficiency: {position.efficiency}\n")
                self.closing_analysis_text.insert(tk.END, f"   🚦 Close Likelihood: {likelihood}\n")
                self.closing_analysis_text.insert(tk.END, f"   💭 Reason: {reason}\n")
                self.closing_analysis_text.insert(tk.END, "\n")
            
            # Update statistics
            closes_today = getattr(self.trading_system, 'closes_today', 0)
            self.closing_stats_labels['closes_today'].config(text=str(closes_today))
            
        except Exception as e:
            self.trading_system.log(f"Error updating closing analysis: {str(e)}", "ERROR")

    def update_routing_data(self):
        """Update smart routing tab"""
        try:
            # Update routing status
            router_enabled = "Yes" if self.trading_system.smart_router_enabled else "No"
            self.routing_status_labels['router_enabled'].config(text=router_enabled)
            
            # Update balance ratio
            total_volume = self.trading_system.buy_volume + self.trading_system.sell_volume
            if total_volume > 0:
                buy_ratio = self.trading_system.buy_volume / total_volume * 100
                sell_ratio = 100 - buy_ratio
                balance_text = f"{buy_ratio:.0f}:{sell_ratio:.0f}"
            else:
                balance_text = "50:50"
            self.routing_status_labels['balance_ratio'].config(text=balance_text)
            
            # Update redirect mode
            if hasattr(self.trading_system, 'last_redirect_time') and self.trading_system.last_redirect_time:
                redirect_mode = "Active"
            else:
                redirect_mode = "Normal"
            self.routing_status_labels['redirect_mode'].config(text=redirect_mode)
            
            # Last redirect time
            if hasattr(self.trading_system, 'last_redirect_time') and self.trading_system.last_redirect_time:
                last_redirect = self.trading_system.last_redirect_time.strftime("%H:%M:%S")
            else:
                last_redirect = "Never"
            self.routing_status_labels['last_redirect'].config(text=last_redirect)
            
        except Exception as e:
            self.trading_system.log(f"Error updating routing data: {str(e)}", "ERROR")

    def update_live_activity(self):
        """Update live activity feed"""
        try:
            # Add current activity
            current_time = datetime.now().strftime("%H:%M:%S")
            
            # Check for recent activities
            positions_count = len(self.trading_system.positions)
            portfolio_health = self.trading_system.portfolio_health
            
            activity_msg = f"[{current_time}] 📊 Portfolio Status: {positions_count} positions, Health: {portfolio_health:.1f}%\n"
            
            # Add to activity log
            self.activity_text.insert(tk.END, activity_msg)
            
            # Auto-scroll if enabled
            if self.auto_scroll_var.get():
                self.activity_text.see(tk.END)
            
            # Limit text size (keep last 1000 lines)
            lines = self.activity_text.get(1.0, tk.END).split('\n')
            if len(lines) > 1000:
                self.activity_text.delete(1.0, f"{len(lines)-1000}.0")
            
        except Exception as e:
            self.trading_system.log(f"Error updating live activity: {str(e)}", "ERROR")

    def refresh_monitor_data(self):
        """Manually refresh monitor data"""
        try:
            self.update_monitor_data()
            self.trading_system.log("📊 Monitor data refreshed", "INFO")
        except Exception as e:
            self.trading_system.log(f"Error refreshing monitor data: {str(e)}", "ERROR")

    def clear_activity_log(self):
        """Clear activity log"""
        try:
            self.activity_text.delete(1.0, tk.END)
            self.activity_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] 📋 Activity log cleared\n")
        except Exception as e:
            self.trading_system.log(f"Error clearing activity log: {str(e)}", "ERROR")

    def export_monitor_data(self):
        """Export monitor data to file"""
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if filename:
                with open(filename, 'w') as f:
                    f.write("Position Monitor Data Export\n")
                    f.write(f"Exported at: {datetime.now()}\n")
                    f.write("=" * 50 + "\n\n")
                    
                    # Export positions data
                    for position in self.trading_system.positions:
                        f.write(f"Ticket: {position.ticket}\n")
                        f.write(f"Type: {position.type}\n")
                        f.write(f"Volume: {position.volume}\n")
                        f.write(f"Profit: ${position.profit:.2f}\n")
                        f.write(f"Role: {position.role}\n")
                        f.write("-" * 30 + "\n")
                
                self.trading_system.log(f"📊 Monitor data exported to {filename}", "INFO")
        except Exception as e:
            self.trading_system.log(f"Error exporting monitor data: {str(e)}", "ERROR")

    def close_position_monitor(self):
        """Close position monitor window"""
        try:
            if hasattr(self, 'monitor_update_job') and self.monitor_update_job:
                self.monitor_window.after_cancel(self.monitor_update_job)
            self.monitor_window.destroy()
            self.trading_system.log("📊 Position Monitor closed", "INFO")
        except Exception as e:
            self.trading_system.log(f"Error closing position monitor: {str(e)}", "ERROR")

    def emergency_stop(self):
        """Emergency stop - immediately halt all trading and close positions"""
        try:
            # Stop trading immediately
            self.trading_system.trading_active = False
            self.start_btn.config(state='normal')
            self.stop_btn.config(state='disabled')
            
            # Log emergency stop
            self.trading_system.log("🚨 EMERGENCY STOP ACTIVATED", "WARNING")
            
            # Show confirmation dialog
            result = messagebox.askyesno("Emergency Stop", 
                                       "Emergency stop activated!\n\nDo you want to close all open positions?")
            
            if result and self.trading_system.mt5_connected:
                # Close all positions (this would need MT5 implementation)
                self.trading_system.log("Attempting to close all positions...", "WARNING")
                # Note: Actual position closing would require MT5 implementation
                
            messagebox.showwarning("Emergency Stop", "All trading activities have been halted!")
            
        except Exception as e:
            self.trading_system.log(f"Error during emergency stop: {str(e)}", "ERROR")
            messagebox.showerror("Error", f"Emergency stop failed: {str(e)}")

    def update_positions_display(self):
        """Update positions in the modern treeview"""
        try:
            # Clear existing items
            for item in self.positions_tree.get_children():
                self.positions_tree.delete(item)
            
            # Update position count
            if hasattr(self, 'pos_count_label'):
                pos_count = len(self.trading_system.positions)
                max_positions = self.trading_system.max_positions
                self.pos_count_label.config(text=f"Positions: {pos_count}/{max_positions}")
            
            # Add current positions with enhanced styling
            for i, pos in enumerate(self.trading_system.positions):
                values = (
                    pos.ticket,
                    pos.type,
                    f"{pos.volume:.2f}",
                    f"{pos.open_price:.5f}",
                    f"{pos.current_price:.5f}",
                    f"${pos.profit:.2f}",
                    f"${pos.profit_per_lot:.2f}",
                    pos.role,
                    pos.efficiency,
                    "🟢 Active" if pos.profit >= 0 else "🔴 Loss"
                )
                
                # Determine tags for styling
                tags = []
                
                # Alternating row colors
                if i % 2 == 0:
                    tags.append("evenrow")
                else:
                    tags.append("oddrow")
                
                # Efficiency color coding
                if pos.efficiency == "excellent":
                    tags.append("excellent")
                elif pos.efficiency == "good":
                    tags.append("good")
                elif pos.efficiency == "fair":
                    tags.append("fair")
                else:
                    tags.append("poor")
                
                self.positions_tree.insert('', 'end', values=values, tags=tuple(tags))
            
        except Exception as e:
            print(f"Error updating positions display: {str(e)}")

    def update_analytics_display(self):
        """Update analytics with modern styling and enhanced information"""
        try:
            # Update recommendations (keep the smart insights)
            self.recommendations_text.delete(1.0, tk.END)
            smart_stats = self.trading_system.get_smart_management_stats()
            current_time = datetime.now().strftime("%H:%M:%S")
            recommendations = self.get_smart_router_recommendations(smart_stats)
            
            if recommendations:
                rec_text = f"🧠 SMART INSIGHTS [{current_time}]\n\n"
                for i, rec in enumerate(recommendations, 1):
                    rec_text += f"• {rec}\n\n"
            else:
                rec_text = f"🧠 SYSTEM STATUS [{current_time}]\n\n"
                if self.trading_system.trading_active:
                    rec_text += "✅ System running and monitoring\n"
                    rec_text += "⏳ Waiting for signal conditions\n"
                    rec_text += "📊 Analyzing M5 XAUUSD candles\n"
                else:
                    rec_text += "⏹️ Trading system stopped\n"
                    rec_text += "🔌 Connect to MT5 to begin\n"
            
            self.recommendations_text.insert(tk.END, rec_text)
            
            # Update volume labels
            if hasattr(self, 'buy_volume_label'):
                self.buy_volume_label.config(text=f"BUY: {self.trading_system.buy_volume:.2f}")
            if hasattr(self, 'sell_volume_label'):
                self.sell_volume_label.config(text=f"SELL: {self.trading_system.sell_volume:.2f}")
            
            # Update visual indicators
            self.update_health_progress()
            self.update_volume_balance_visualization()
            
        except Exception as e:
            print(f"Error updating analytics display: {str(e)}")

    def get_smart_router_recommendations(self, smart_stats: dict) -> List[str]:
        """Generate modern smart router recommendations"""
        recommendations = []
        
        try:
            # Router performance analysis
            redirect_ratio = smart_stats.get('redirect_ratio', 0)
            redirect_success_rate = smart_stats.get('redirect_success_rate', 0)
            avg_hold_score = smart_stats.get('avg_hold_score', 50)
            
            if redirect_ratio > 30:
                recommendations.append(f"🔄 High redirect activity ({redirect_ratio:.1f}%) - Smart balance management active")
            
            if redirect_success_rate > 80 and smart_stats.get('total_redirects', 0) > 5:
                recommendations.append(f"✅ Excellent redirect success rate ({redirect_success_rate:.1f}%)")
            
            # Portfolio insights
            if avg_hold_score < 30:
                recommendations.append("📈 Low average hold score - Multiple positions ready for profit-taking")
            elif avg_hold_score > 70:
                recommendations.append("💪 High hold score - Portfolio in strong holding position")
            
            # Balance analysis
            total_volume = self.trading_system.buy_volume + self.trading_system.sell_volume
            if total_volume > 0:
                buy_ratio = self.trading_system.buy_volume / total_volume
                if abs(buy_ratio - 0.5) > 0.2:
                    recommendations.append(f"⚖️ Balance monitoring: {buy_ratio*100:.1f}% BUY - Router optimizing")
            
            # Profit capture insights
            profit_captured = smart_stats.get('redirect_profit_captured', 0)
            if profit_captured > 100:
                recommendations.append(f"💰 Router captured ${profit_captured:.2f} through smart redirects")
            
            # System health
            if self.trading_system.portfolio_health < 40:
                recommendations.append("🚨 Portfolio health low - Smart system in protective mode")
            elif self.trading_system.portfolio_health > 80:
                recommendations.append("🌟 Excellent portfolio health - System optimizing growth")
            
        except Exception as e:
            self.trading_system.log(f"Error generating router recommendations: {str(e)}", "ERROR")
        
        return recommendations

    def update_status_labels(self):
        """Update status labels with modern formatting"""
        try:
            # Update portfolio label if it exists (old style support)
            if hasattr(self, 'portfolio_label') and hasattr(self.portfolio_label, 'config'):
                try:
                    self.portfolio_label.config(text=f"💼 Portfolio Health: {self.trading_system.portfolio_health:.1f}%")
                except:
                    pass
            
            # Update volume label if it exists (old style support)  
            if hasattr(self, 'volume_label') and hasattr(self.volume_label, 'config'):
                try:
                    self.volume_label.config(text=f"⚖️ Volume Balance: {self.trading_system.buy_volume:.2f}/{self.trading_system.sell_volume:.2f}")
                except:
                    pass
                    
        except Exception as e:
            print(f"Error updating status labels: {str(e)}")

    def update_live_stats_display(self):
        """Update live statistics display with enhanced metrics"""
        try:
            # Update current P&L display
            if hasattr(self, 'pnl_value_label'):
                total_profit = sum(pos.profit for pos in self.trading_system.positions)
                if total_profit >= 0:
                    self.pnl_value_label.config(text=f"${total_profit:.2f}", style='Success.TLabel')
                else:
                    self.pnl_value_label.config(text=f"${total_profit:.2f}", style='Error.TLabel')
            
            # Update active positions count
            if hasattr(self, 'active_pos_label'):
                pos_count = len(self.trading_system.positions)
                self.active_pos_label.config(
                    text=f"{pos_count}/{self.trading_system.max_positions}"
                )
            
            # Update analytics dashboard metrics
            if hasattr(self, 'success_rate_label'):
                success_rate = 0
                if self.trading_system.total_signals > 0:
                    success_rate = (self.trading_system.successful_signals / self.trading_system.total_signals) * 100
                self.success_rate_label.config(text=f"{success_rate:.1f}%")
            
            # Update win/loss ratio
            if hasattr(self, 'winloss_label'):
                wins = self.trading_system.successful_signals
                losses = self.trading_system.total_signals - self.trading_system.successful_signals
                self.winloss_label.config(text=f"{wins}/{losses}")
            
            # Update average profit per trade
            if hasattr(self, 'avg_profit_label'):
                avg_profit = 0
                if self.trading_system.total_signals > 0:
                    total_profit = sum(pos.profit for pos in self.trading_system.positions)
                    avg_profit = total_profit / max(1, self.trading_system.total_signals)
                self.avg_profit_label.config(text=f"${avg_profit:.2f}")
            
            # Update risk level indicator
            if hasattr(self, 'risk_level_label'):
                # Calculate risk level based on portfolio health and position count
                risk_level = "Low"
                risk_style = 'Success.TLabel'
                
                pos_count = len(self.trading_system.positions)
                health = self.trading_system.portfolio_health
                
                if pos_count > 40 or health < 30:
                    risk_level = "High"
                    risk_style = 'Error.TLabel'
                elif pos_count > 25 or health < 60:
                    risk_level = "Medium"
                    risk_style = 'Status.TLabel'
                
                self.risk_level_label.config(text=risk_level, style=risk_style)
            
            # Update connection status in connection card
            if hasattr(self, 'connection_status_label'):
                if self.trading_system.mt5_connected:
                    self.connection_status_label.config(text="Connected", style='Success.TLabel')
                else:
                    self.connection_status_label.config(text="Disconnected", style='Error.TLabel')
            
            # Update terminal path display
            if hasattr(self, 'terminal_path_label'):
                if hasattr(self.trading_system, 'selected_terminal') and self.trading_system.selected_terminal:
                    path = self.trading_system.selected_terminal.get('path', 'Not selected')
                    if len(path) > 40:
                        path = "..." + path[-37:]  # Truncate long paths
                    self.terminal_path_label.config(text=path)
                else:
                    self.terminal_path_label.config(text="Not selected")
            
            # Update input field values to match system state
            if hasattr(self, 'lot_size_var'):
                current_lot = self.lot_size_var.get()
                system_lot = str(self.trading_system.base_lot)
                if current_lot != system_lot:
                    self.lot_size_var.set(system_lot)
            
            if hasattr(self, 'max_pos_var'):
                current_max = self.max_pos_var.get()
                system_max = str(self.trading_system.max_positions)
                if current_max != system_max:
                    self.max_pos_var.set(system_max)
                    
        except Exception as e:
            print(f"Error updating live stats display: {str(e)}")

    def update_log_display(self):
        """Update log display with syntax highlighting"""
        try:
            while True:
                message = self.trading_system.log_queue.get_nowait()
                
                # Insert message with appropriate styling
                self.log_text.insert(tk.END, message + "\n")
                
                # Apply syntax highlighting
                lines = self.log_text.get("1.0", tk.END).split('\n')
                current_line = len(lines) - 2  # -2 because of the trailing newline
                
                if current_line > 0:
                    line_start = f"{current_line}.0"
                    line_end = f"{current_line}.end"
                    
                    # Apply tags based on content
                    if "ERROR" in message:
                        self.log_text.tag_add("ERROR", line_start, line_end)
                    elif "WARNING" in message:
                        self.log_text.tag_add("WARNING", line_start, line_end)
                    elif "✅" in message or "SUCCESS" in message:
                        self.log_text.tag_add("SUCCESS", line_start, line_end)
                    elif message.strip().startswith(("🔍", "📊", "⏰")):
                        self.log_text.tag_add("INFO", line_start, line_end)
                
                self.log_text.see(tk.END)
                
        except queue.Empty:
            pass

    def update_loop(self):
        """Enhanced GUI update loop with modern features and smart updating"""
        try:
            # Skip updates if MT5 is not connected to reduce CPU load
            if hasattr(self.trading_system, 'mt5_connected') and not self.trading_system.mt5_connected:
                # Only update log display when not connected
                self.update_log_display()
            else:
                # Full update when connected
                self.trading_system.update_positions()
                self.update_positions_display()
                self.update_analytics_display()
                self.update_live_stats_display()
                self.update_status_labels()
                self.update_log_display()
            
        except Exception as e:
            # Use trading system logger if available, fallback to print
            if hasattr(self, 'trading_system'):
                self.trading_system.log(f"GUI update error: {str(e)}", "ERROR")
            else:
                print(f"GUI update error: {str(e)}")
        
        # Schedule next update (reduced frequency for better stability)
        self.root.after(2500, self.update_loop)

    def show_startup_status(self):
        """Show startup status and errors to user"""
        try:
            # Create a status message
            error_count = len(self.startup_errors)
            if error_count > 0:
                status_msg = f"⚠️ GUI loaded with {error_count} warning(s). Check logs for details."
                if hasattr(self, 'trading_system') and hasattr(self.trading_system, 'log'):
                    self.trading_system.log(status_msg, "WARNING")
                    for error in self.startup_errors:
                        self.trading_system.log(f"Startup warning: {error}", "WARNING")
        except Exception as e:
            print(f"Error showing startup status: {e}")

    def safe_auto_scan_terminals(self):
        """Safely auto-scan terminals without blocking GUI"""
        try:
            print("🔄 Starting safe auto-scan for terminals...")
            if hasattr(self, 'auto_scan_terminals'):
                # Run in a separate thread to avoid blocking
                import threading
                scan_thread = threading.Thread(target=self.auto_scan_terminals, daemon=True)
                scan_thread.start()
                print("✅ Auto-scan started in background thread")
            else:
                print("⚠️ Auto-scan method not available")
        except Exception as e:
            print(f"⚠️ Auto-scan failed: {e}")
            if hasattr(self, 'trading_system') and hasattr(self.trading_system, 'log'):
                self.trading_system.log(f"Auto-scan error: {e}", "ERROR")

    def retry_full_gui(self):
        """Retry loading the full GUI from fallback mode"""
        try:
            self.root.destroy()
            self.startup_errors = []
            self.gui_components_loaded = False
            self.fallback_mode = False
            
            # Reinitialize
            self.setup_gui()
            self.gui_components_loaded = True
            messagebox.showinfo("Success", "Full GUI loaded successfully!")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load full GUI: {e}")
            self.setup_fallback_gui()

    def run(self):
        """Start the modern GUI application"""
        self.trading_system.log("🏆 Modern AI Gold Grid Trading System v3.0 Started")
        self.trading_system.log("🎨 Professional GUI Interface Loaded")
        self.trading_system.log("🔌 Ready for MT5 connection")
        self.root.mainloop()

def main():
    """Main application entry point with comprehensive error handling"""
    print("🚀 Starting Huakuy Trading System...")
    print(f"📦 MT5 Available: {MT5_AVAILABLE}")
    print(f"📦 Pandas Available: {pd is not None}")
    print(f"📦 NumPy Available: {np is not None}")
    
    try:
        print("🔄 Creating GUI application...")
        app = TradingGUI()
        
        print("🎯 Starting application main loop...")
        app.run()
        
    except ImportError as e:
        error_msg = f"Missing required dependency: {str(e)}"
        print(f"❌ {error_msg}")
        try:
            messagebox.showerror("Dependency Error", error_msg)
        except:
            print("Could not show error dialog - tkinter may not be available")
            
    except Exception as e:
        error_msg = f"Application failed to start: {str(e)}"
        print(f"❌ {error_msg}")
        print("📊 Error details:")
        import traceback
        traceback.print_exc()
        
        try:
            messagebox.showerror("Critical Error", error_msg)
        except:
            print("Could not show error dialog")
    
    print("🏁 Application terminated")

if __name__ == "__main__":
    main()