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
    MT5_AVAILABLE = False

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
    role: str  # MAIN, HG, SUPPORT, SACRIFICE
    efficiency: str  # excellent, good, fair, poor

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
        self.max_positions_per_zone = 3  # จำกัดไม้ต่อ zone
        self.min_position_distance_pips = 15  # ระยะห่างขั้นต่ำระหว่างไม้
        self.force_zone_diversification = True  # บังคับกระจาย
        
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
        self.circuit_breaker_threshold = 3  # failures before breaking
        self.circuit_breaker_timeout = 300  # 5 minutes before retry
        self.circuit_breaker_open = False
        self.circuit_breaker_last_failure = None

        # 🖥️ Terminal Selection System
        self.available_terminals = []
        self.selected_terminal = None
        self.terminal_scan_in_progress = False

        # 🛡️ Anti-Exposure Protection System
        self.anti_exposure_enabled = True
        self.max_exposure_distance = 150  # pips (1.5 points for XAUUSD)
        self.exposure_warning_distance = 100  # pips
        self.auto_hedge_enabled = True
        self.hedge_trigger_distance = 120  # pips
        
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
        
        # 🛠️ Advanced Drawdown Management (NEW)
        self.drawdown_management_enabled = True
        self.drawdown_trigger_pips = 150  # เริ่มคิดหาทางแก้ที่ 150 pips
        self.critical_drawdown_pips = 250  # ถือว่าวิกฤตที่ 250 pips
        self.emergency_drawdown_pips = 350  # ต้องแก้ทันทีที่ 350 pips
        
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
        """Thread-safe logging"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {level}: {message}"
        self.log_queue.put(log_message)
        
        if level == "ERROR":
            logger.error(message)
        elif level == "WARNING":
            logger.warning(message)
        else:
            logger.info(message)

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
        """การจัดการความเสี่ยงขั้นสูง"""
        try:
            account_info = mt5.account_info()
            if not account_info:
                return
            
            # 1. Dynamic position size based on account equity
            equity = account_info.equity
            if equity < 1000:
                self.base_lot = 0.01
            elif equity < 5000:
                self.base_lot = 0.02
            elif equity < 10000:
                self.base_lot = 0.03
            else:
                self.base_lot = min(0.05, equity / 200000)  # Max 0.05 lots
            
            # 2. Drawdown protection
            balance = account_info.balance
            current_drawdown = (balance - equity) / balance * 100 if balance > 0 else 0
            
            if current_drawdown > 20:  # 20% drawdown
                self.trading_active = False
                self.log("🚨 EMERGENCY STOP: 20% drawdown reached", "ERROR")
            elif current_drawdown > 10:  # 10% drawdown - reduce activity
                self.max_signals_per_hour = 20
                self.signal_cooldown = 120
                self.log("⚠️ Risk mode: Reduced trading activity", "WARNING")
            
            # 3. Margin level protection
            if account_info.margin > 0:
                margin_level = (equity / account_info.margin) * 100
                if margin_level < 150:
                    self.gentle_management = False  # Aggressive closing
                    self.log("⚠️ Low margin: Activating aggressive management", "WARNING")
                
        except Exception as e:
            self.log(f"Error in risk management: {str(e)}", "ERROR")

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
            
            return result
            
        except Exception as e:
            self.log(f"Error analyzing position zones: {str(e)}", "ERROR")
            return {'zones': {}, 'distribution_score': 0.0, 'clustered_zones': [], 'empty_zones': [], 'cached': False}

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
            
            # Check margin level (only if MT5 is available)
            if MT5_AVAILABLE and mt5:
                account_info = mt5.account_info()
                if account_info and account_info.margin != 0:
                    margin_level = (account_info.equity / account_info.margin) * 100
                    if margin_level < self.min_margin_level:
                        self.log(f"Low margin level: {margin_level:.1f}%", "WARNING")
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
            
            # 6. Final zone distribution check (relaxed threshold)
            if zone_analysis['distribution_score'] < 20:  # Only skip if very poor distribution (was 30)
                self.log(f"⚠️ Very poor zone distribution (score: {zone_analysis['distribution_score']:.1f}) - allowing signal")
                result['details']['reason'] += ' - Poor zone distribution warning'
            
            return result
            
        except Exception as e:
            self.log(f"Error in enhanced smart signal router: {str(e)}", "ERROR")
            return {'action': 'execute', 'details': {'reason': 'Router error - default execute'}}

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
            base_target_pct = self.profit_harvest_threshold_percent
            
            # ปรับตาม portfolio health
            if self.portfolio_health < 40:
                base_target_pct *= 0.6
            elif self.portfolio_health > 80:
                base_target_pct *= 1.3
            
            # ปรับตาม balance
            if self.will_improve_balance_by_closing(position):
                base_target_pct *= 0.75
            
            # ปรับตาม volatility
            if hasattr(self, 'recent_volatility'):
                if self.recent_volatility > 2.0:
                    base_target_pct *= 0.8
                elif self.recent_volatility < 0.5:
                    base_target_pct *= 1.2
            
            return max(2.0, min(20.0, base_target_pct))
            
        except Exception as e:
            return self.profit_harvest_threshold_percent

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
            
            # Relaxed position count and margin check - only skip if really critical
            # Changed from 0.9 to 0.95 and margin level from 1.5 to 1.2
            if len(self.positions) > self.max_positions * 0.95:
                if MT5_AVAILABLE and mt5 and self.mt5_connected:
                    account_info = mt5.account_info()
                    if account_info and account_info.margin > 0:
                        margin_level = (account_info.equity / account_info.margin) * 100
                        if margin_level < self.min_margin_level * 1.2:
                            self.log(f"⏭️ Skipping signal - critical position count and low margin (ML: {margin_level:.1f})")
                            return True
            
            return False
            
        except Exception as e:
            self.log(f"Error checking skip conditions: {str(e)}", "ERROR")
            return False

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
            ticket = position.ticket
            
            if (ticket not in self.position_tracker) and (str(ticket) not in self.position_tracker):
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
                    'adaptive_target': self.profit_harvest_threshold
                }
            
            tracker = self.position_tracker[ticket]
            
            # อัพเดทข้อมูล
            tracker['max_profit'] = max(tracker['max_profit'], position.profit)
            tracker['min_profit'] = min(tracker['min_profit'], position.profit)
            tracker['peak_profit_per_lot'] = max(tracker['peak_profit_per_lot'], position.profit_per_lot)
            
            # คำนวณ adaptive target
            tracker['adaptive_target'] = self.calculate_adaptive_profit_target(position)
            
            # คำนวณ hold score
            tracker['hold_score'] = self.calculate_hold_score(position, tracker)
            
            # อัพเดทประวัติ
            if tracker['role_history'][-1] != position.role:
                tracker['role_history'].append(position.role)
            if tracker['efficiency_history'][-1] != position.efficiency:
                tracker['efficiency_history'].append(position.efficiency)
                
        except Exception as e:
            self.log(f"Error tracking position {position.ticket}: {str(e)}", "ERROR")



    def calculate_hold_score(self, position: Position, tracker: dict) -> int:
        """คำนวณคะแนนการถือ position (ใช้เปอร์เซ็นต์)"""
        try:
            score = 50
            adaptive_target_pct = tracker.get('adaptive_target', self.profit_harvest_threshold_percent)
            
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
            if self.will_improve_balance_by_closing(position):
                score -= 10
            
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
        """ระบบจัดการ position อัจฉริยะ (เพิ่ม hedge management)"""
        if not self.mt5_connected or not self.positions:
            return
        
        try:
            # ติดตามทุก position
            for position in self.positions:
                self.track_position_lifecycle(position)
            
            # 1. ระบบจัดการ drawdown & hedge ก่อน
            self.drawdown_management_system()
            
            # 2. ลองปิดแบบคู่/กลุ่ม (ประหยัด margin มากกว่า)
            self.smart_pair_group_management()
            
            # 3. ปิดแบบปกติ (ถ้าไม่มีโอกาสคู่/กลุ่มดี)
            self.execute_flexible_closes()
            
            # 4. ทำความสะอาด tracker
            self.cleanup_closed_positions()
            
        except Exception as e:
            self.log(f"Error in smart position management: {str(e)}", "ERROR")

    def execute_flexible_closes(self):
        """ปิด position แบบยืดหยุ่น"""
        try:
            closes_this_cycle = 0
            max_closes = 2 if self.gentle_management else 3
            
            # เรียง positions ตามระยะห่าง (ไกลสุดก่อน)
            positions_with_distance = []
            for pos in self.positions:
                if pos.profit > 0:  # เฉพาะไม้ที่มีกำไร
                    distance = self.calculate_position_distance_from_market(pos)
                    positions_with_distance.append((pos, distance))

            # เรียงจากไกลสุด → ใกล้สุด
            sorted_positions = sorted(positions_with_distance, key=lambda x: x[1], reverse=True)
            
            for position, distance in sorted_positions:
                if closes_this_cycle >= max_closes:
                    break
                
                # ห้ามปิดไม้ที่ขาดทุน
                if position.profit <= 0:
                    continue
                
                tracker = self.position_tracker.get(position.ticket, {})
                hold_score = tracker.get('hold_score', 50)
                
                # คำนวณกำไรเป็นเปอร์เซ็นต์ต่อ lot
                profit_percent = (position.profit_per_lot / position.open_price) * 100
                
                should_close = False
                reason = ""
                
                # เงื่อนไขการปิดแบบยืดหยุ่น (ใช้เปอร์เซ็นต์)
                if profit_percent >= 8.0 and position.profit > 0:  # ไม่ปิดติดลบ
                    should_close = True
                    reason = f"Target reached: {profit_percent:.2f}% (Distance: {distance:.1f} pips)"
                
                elif (profit_percent >= 6.0 and 
                      hold_score <= 25 and 
                      self.portfolio_health < 60):
                    should_close = True
                    reason = f"Portfolio concern: {profit_percent:.2f}%"
                
                elif (self.portfolio_health < self.emergency_mode_threshold and 
                      profit_percent > 4.0 and 
                      hold_score <= 30):
                    should_close = True
                    reason = f"Emergency mode: {profit_percent:.2f}%"
                
                elif (len(self.positions) > self.max_positions * 0.9 and
                      profit_percent > 5.0 and
                      hold_score <= 20):
                    should_close = True
                    reason = f"Position optimization: {profit_percent:.2f}%"
                
                if should_close:
                    success = self.close_position_smart(position, reason)
                    if success:
                        closes_this_cycle += 1
                        time.sleep(1)  # Small delay between closes
                
        except Exception as e:
            self.log(f"Error executing flexible closes: {str(e)}", "ERROR")

    def close_position_smart(self, position: Position, reason: str) -> bool:
        """ปิด position อย่างชาญฉลาด"""
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
            current_tick = mt5.symbol_info_tick(self.symbol)
            if not current_tick:
                return 0
            
            current_price = current_tick.bid
            distance_pips = abs(position.open_price - current_price) * 100
            return distance_pips
        except:
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

    def find_profitable_pairs(self) -> List[dict]:
        """หาคู่ไม้ที่กำไร + ขาดทุน = กำไรรวม (เป็น %)"""
        pairs = []
        
        try:
            if not self.pair_closing_enabled or len(self.positions) < 2:
                return pairs
            
            # แยกไม้กำไรและขาดทุน
            profitable_positions = [p for p in self.positions if self.calculate_profit_percent(p) > 0]
            loss_positions = [p for p in self.positions 
                            if self.calculate_profit_percent(p) < 0 
                            and self.calculate_profit_percent(p) >= self.max_loss_percent]
            
            if not profitable_positions or not loss_positions:
                return pairs
            
            # หาคู่ที่ดีที่สุด
            for profit_pos in profitable_positions:
                for loss_pos in loss_positions:
                    profit_pct = self.calculate_profit_percent(profit_pos)
                    loss_pct = self.calculate_profit_percent(loss_pos)
                    net_profit_pct = profit_pct + loss_pct  # loss_pct เป็นลบอยู่แล้ว
                    
                    if net_profit_pct >= self.min_pair_profit_percent:
                        pair_score = self.calculate_pair_score_percent(profit_pos, loss_pos, net_profit_pct)
                        
                        pairs.append({
                            'type': 'pair',
                            'positions': [profit_pos, loss_pos],
                            'net_profit': profit_pos.profit + loss_pos.profit,
                            'net_profit_percent': net_profit_pct,
                            'score': pair_score,
                            'profit_position': profit_pos,
                            'loss_position': loss_pos,
                            'reason': f'Pair close: {profit_pct:.1f}% + {loss_pct:.1f}% = {net_profit_pct:.1f}%'
                        })
            
            # เรียงตามคะแนน
            pairs.sort(key=lambda x: x['score'], reverse=True)
            return pairs[:5]  # ส่งคืนแค่ 5 คู่ที่ดีที่สุด
            
        except Exception as e:
            self.log(f"Error finding profitable pairs: {str(e)}", "ERROR")
            return []

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

    def smart_pair_group_management(self):
        """ระบบจัดการแบบคู่และกลุ่ม"""
        if not self.mt5_connected or len(self.positions) < 2:
            return
        
        try:
            # 1. หาโอกาสปิดคู่
            profitable_pairs = self.find_profitable_pairs()
            if profitable_pairs:
                best_pair = profitable_pairs[0]
                if best_pair['score'] > 70:  # คะแนนสูงพอ
                    self.execute_pair_close(best_pair)
                    return  # ปิดคู่แล้วพอ cycle นี้
            
            # 2. หาโอกาสปิดกลุ่ม (ถ้าไม่มีคู่ดี)
            profitable_groups = self.find_profitable_groups()
            if profitable_groups:
                best_group = profitable_groups[0]
                if best_group['score'] > 80:  # คะแนนสูงกว่าเพราะปิดหลายตัว
                    self.execute_group_close(best_group)
            
        except Exception as e:
            self.log(f"Error in smart pair/group management: {str(e)}", "ERROR")

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
        
        # Modern Professional Color Scheme
        self.COLORS = {
            'bg_primary': '#1a1a1a',     # Main background
            'bg_secondary': '#2d2d2d',   # Card backgrounds
            'bg_accent': '#3a3a3a',      # Button/component backgrounds
            'accent_blue': '#0078d4',    # Primary action color
            'accent_green': '#107c10',   # Success/profit color
            'accent_red': '#d13438',     # Error/loss color
            'accent_orange': '#ff8c00',  # Warning color
            'text_primary': '#ffffff',   # Primary text
            'text_secondary': '#cccccc', # Secondary text
            'text_muted': '#999999',     # Muted text
            'border': '#404040',         # Borders and separators
            'hover': '#4a4a4a',          # Hover states
            'card_shadow': '#0f0f0f'     # Card shadow effect
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
        """Create trading control card"""
        card_content = self.create_card(parent, "▶️ Trading Control", width=280, height=180)
        card_content.card_container.pack(side='left', padx=(0, 12), fill='y')
        
        # Trading buttons
        btn_frame = tk.Frame(card_content, bg=self.COLORS['bg_secondary'])
        btn_frame.pack(fill='x', pady=(0, 8))
        
        self.start_btn = ttk.Button(btn_frame, text="▶️ Start Trading", 
                                   command=self.start_trading, style='Success.TButton')
        self.start_btn.pack(side='left', padx=(0, 6), fill='x', expand=True)
        
        self.stop_btn = ttk.Button(btn_frame, text="⏹️ Stop Trading", 
                                  command=self.stop_trading, style='Danger.TButton')
        self.stop_btn.pack(side='right', fill='x', expand=True)
        
        # Base lot size input
        lot_frame = tk.Frame(card_content, bg=self.COLORS['bg_secondary'])
        lot_frame.pack(fill='x', pady=(0, 6))
        
        lot_label = ttk.Label(lot_frame, text="Base Lot:", style='Status.TLabel')
        lot_label.pack(side='left')
        
        self.lot_size_var = tk.StringVar(value="0.01")
        self.lot_size_entry = ttk.Entry(lot_frame, textvariable=self.lot_size_var, 
                                       width=8, style='Modern.TEntry')
        self.lot_size_entry.pack(side='right')
        self.lot_size_entry.bind('<Return>', self.update_lot_size)
        
        # Max positions setting
        pos_frame = tk.Frame(card_content, bg=self.COLORS['bg_secondary'])
        pos_frame.pack(fill='x', pady=(0, 6))
        
        pos_label = ttk.Label(pos_frame, text="Max Pos:", style='Status.TLabel')
        pos_label.pack(side='left')
        
        self.max_pos_var = tk.StringVar(value="50")
        self.max_pos_entry = ttk.Entry(pos_frame, textvariable=self.max_pos_var, 
                                      width=8, style='Modern.TEntry')
        self.max_pos_entry.pack(side='right')
        self.max_pos_entry.bind('<Return>', self.update_max_positions)
        
        # Emergency stop button
        emergency_frame = tk.Frame(card_content, bg=self.COLORS['bg_secondary'])
        emergency_frame.pack(fill='x')
        
        self.emergency_btn = ttk.Button(emergency_frame, text="🚨 EMERGENCY STOP", 
                                       command=self.emergency_stop, style='Emergency.TButton')
        self.emergency_btn.pack(fill='x')

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