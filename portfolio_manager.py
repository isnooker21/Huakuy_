# -*- coding: utf-8 -*-
"""
Portfolio Manager Module
โมดูลสำหรับบริหารพอร์ตและการตัดสินใจการเทรด
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from calculations import (
    Position, PercentageCalculator, LotSizeCalculator, 
    RiskCalculator, MarketAnalysisCalculator, ProfitTargetCalculator
)
from trading_conditions import Signal, TradingConditions, CandleData
# Smart Recovery System removed - replaced by Smart Profit Taking System
from price_zone_analysis import PriceZoneAnalyzer
from zone_rebalancer import ZoneRebalancer
# from advanced_breakout_recovery import AdvancedBreakoutRecovery  # DISABLED - ใช้ Simple Position Manager
from smart_gap_filler import SmartGapFiller
from force_trading_mode import ForceTradingMode
from zone_position_manager import ZonePositionManager, create_zone_position_manager
from signal_manager import SignalManager, RankedSignal
from order_management import OrderManager, OrderResult, CloseResult

logger = logging.getLogger(__name__)

@dataclass
class PortfolioState:
    """คลาสสำหรับเก็บสถานะพอร์ต"""
    account_balance: float
    equity: float
    margin: float
    margin_level: float
    total_positions: int
    buy_positions: int
    sell_positions: int
    total_profit: float
    total_profit_percentage: float
    exposure_percentage: float
    risk_percentage: float
    buy_sell_ratio: Dict[str, float]
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class PerformanceMetrics:
    """คลาสสำหรับเก็บเมตริกการทำงาน"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate_percentage: float = 0.0
    total_profit: float = 0.0
    total_loss: float = 0.0
    max_drawdown_percentage: float = 0.0
    profit_factor: float = 0.0
    daily_pnl_percentage: float = 0.0
    equity_history: List[float] = field(default_factory=list)

class PortfolioManager:
    """คลาสสำหรับบริหารพอร์ตและการตัดสินใจการเทรด"""
    
    def __init__(self, order_manager: OrderManager, initial_balance: float):
        """
        Args:
            order_manager: ตัวจัดการ Order
            initial_balance: เงินทุนเริ่มต้น
        """
        self.order_manager = order_manager
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.current_symbol = None  # จะถูกตั้งค่าจาก main system
        self.trading_conditions = TradingConditions()
        # Smart Recovery System removed - functionality moved to Smart Profit Taking System
        
        # เพิ่ม Zone Analysis System (จะถูกตั้งค่าภายหลัง)
        self.zone_analyzer = None
        self.zone_rebalancer = None
        
        # Advanced Breakout Recovery System DISABLED - ใช้ Simple Position Manager แทน
        # self.advanced_recovery = AdvancedBreakoutRecovery(order_manager.mt5)
        self.advanced_recovery = None
        
        # เพิ่ม Continuous Trading Systems
        self.gap_filler = SmartGapFiller(order_manager.mt5)
        self.force_trading = ForceTradingMode(order_manager.mt5)
        
        # 🎯 Zone Position Manager - ระบบจัดการไม้แบบ Zone-Based
        self.position_manager = create_zone_position_manager(
            mt5_connection=order_manager.mt5,
            order_manager=order_manager,
            zone_size_pips=30.0
        )
        
        # 🎯 Zone-Based System ได้ถูก integrate ใน position_manager แล้ว
        # ไม่จำเป็นต้องมี separate recovery manager
        
        # 🎯 Signal Manager - จัดการสัญญาณจากทุกระบบในจุดเดียว
        self.signal_manager = SignalManager(order_manager.mt5)
        
        # การตั้งค่าความเสี่ยง
        self.max_risk_per_trade = 2.0  # เปอร์เซ็นต์ความเสี่ยงต่อ Trade
        self.max_portfolio_exposure = 80.0  # เปอร์เซ็นต์การใช้เงินทุนสูงสุด
        self.max_daily_loss = 10.0  # ขาดทุนสูงสุดต่อวัน
        self.profit_target = 2.0  # เป้าหมายกำไร
        self.max_drawdown_limit = 15.0  # Drawdown สูงสุดที่ยอมรับ
        
        # การตั้งค่าสมดุลพอร์ต
        self.balance_warning_threshold = 70.0  # เตือนเมื่อฝั่งใดเกิน 70%
        self.balance_stop_threshold = 80.0  # หยุดเทรดเมื่อฝั่งใดเกิน 80%
        
        # ข้อมูลประสิทธิภาพ
        self.performance_metrics = PerformanceMetrics()
        self.daily_start_balance = initial_balance
        self.daily_start_time = datetime.now().date()
        
        # ประวัติการทำงาน
        self.portfolio_history = []
        self.trade_history = []
        
        # ติดตามเวลาเทรดล่าสุด สำหรับ Continuous Trading
        self.last_trade_time: Optional[datetime] = None
        self.last_signal_time: Optional[datetime] = None
        
    def analyze_portfolio_state(self, account_info: Dict) -> PortfolioState:
        """
        วิเคราะห์สถานะพอร์ตปัจจุบัน
        
        Args:
            account_info: ข้อมูลบัญชีจาก MT5
            
        Returns:
            PortfolioState: สถานะพอร์ต
        """
        try:
            # อัพเดทข้อมูลบัญชี
            self.current_balance = account_info.get('balance', self.current_balance)
            
            # ซิงค์ข้อมูล Position
            positions = self.order_manager.sync_positions_from_mt5()
            
            # คำนวณสถิติต่างๆ
            stats = self.order_manager.get_position_statistics(self.current_balance)
            
            # สร้างสถานะพอร์ต
            state = PortfolioState(
                account_balance=self.current_balance,
                equity=account_info.get('equity', self.current_balance),
                margin=account_info.get('margin', 0.0),
                margin_level=account_info.get('margin_level', 0.0),
                total_positions=stats['total_positions'],
                buy_positions=stats['buy_sell_ratio']['buy_count'],
                sell_positions=stats['buy_sell_ratio']['sell_count'],
                total_profit=sum(pos.profit + pos.swap + pos.commission for pos in positions),
                total_profit_percentage=stats['total_profit_percentage'],
                exposure_percentage=stats['exposure_percentage'],
                risk_percentage=stats['risk_percentage'],
                buy_sell_ratio=stats['buy_sell_ratio']
            )
            
            # บันทึกประวัติ
            self.portfolio_history.append(state)
            
            return state
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการวิเคราะห์สถานะพอร์ต: {str(e)}")
            return PortfolioState(
                account_balance=self.current_balance,
                equity=self.current_balance,
                margin=0.0,
                margin_level=0.0,
                total_positions=0,
                buy_positions=0,
                sell_positions=0,
                total_profit=0.0,
                total_profit_percentage=0.0,
                exposure_percentage=0.0,
                risk_percentage=0.0,
                buy_sell_ratio={'buy_percentage': 0, 'sell_percentage': 0}
            )
            
    def should_enter_trade(self, signal: Signal, candle: CandleData, 
                          current_state: PortfolioState, volume_history: List[float] = None) -> Dict[str, Any]:
        """
        ตัดสินใจว่าควรเข้าเทรดหรือไม่
        
        Args:
            signal: สัญญาณการเทรด
            candle: ข้อมูลแท่งเทียน
            current_state: สถานะพอร์ตปัจจุบัน
            volume_history: ประวัติ Volume
            
        Returns:
            Dict: ผลการตัดสินใจ
        """
        try:
            # ตรวจสอบเงื่อนไขพื้นฐาน
            basic_conditions = self.trading_conditions.check_entry_conditions(
                candle, self.order_manager.active_positions, 

                current_state.account_balance, volume_history, signal.symbol
            )
            
            if not basic_conditions['can_enter']:
                return {
                    'should_enter': False,
                    'reasons': basic_conditions['reasons'],
                    'signal': None,
                    'lot_size': 0.0
                }
                
            # 🚀 ADAPTIVE ENTRY: ปิดการตรวจสอบ Portfolio Limits เพื่อ Unlimited Entry
            # portfolio_checks = self._check_portfolio_limits(current_state, signal.direction)
            # if not portfolio_checks['can_enter']:
            #     return {
            #         'should_enter': False,
            #         'reasons': portfolio_checks['reasons'],
            #         'signal': None,
            #         'lot_size': 0.0
            #     }
            logger.info(f"🚀 ADAPTIVE: Portfolio limits disabled - Unlimited Entry enabled")
            
            # 🎯 Zone-Based Entry Analysis (NEW) - แทนที่ระบบเก่า
            zone_recommendation = self._get_zone_based_entry_analysis(signal, candle.close)
                
            # คำนวณขนาด Lot พร้อม Zone Multiplier
            lot_calculator = LotSizeCalculator(current_state.account_balance, self.max_risk_per_trade)
            
            # คำนวณปัจจัยต่างๆ รวม Zone Analysis
            market_strength = signal.strength
            volatility = self._estimate_market_volatility()
            
            # คำนวณปัจจัย Volume ตลาด
            volume_factor = lot_calculator.calculate_volume_factor(
                candle.volume, volume_history or []
            )
            
            # คำนวณปัจจัยทุน
            balance_factor = lot_calculator.calculate_balance_factor(
                current_state.account_balance, self.initial_balance
            )
            
            # 🆕 Portfolio-Based Risk Lot Sizing (ใหม่!)
            # ใช้ active_positions จาก order_manager
            positions_count = len(self.order_manager.active_positions) if self.order_manager.active_positions else 0
            
            # คำนวณ market volatility จาก candle data (ถ้ามี)
            market_volatility = volatility  # ใช้ volatility ที่คำนวณแล้ว
            
            # ใช้ Portfolio Risk Calculator แทนระบบเดิม
            portfolio_lot = lot_calculator.calculate_portfolio_risk_lot(
                positions_count, market_volatility, current_state.account_balance
            )
            
            # รวมกับ Dynamic Lot Size เดิม (เป็น fallback)
            traditional_lot = lot_calculator.calculate_dynamic_lot_size(
                market_strength, volatility, volume_factor, balance_factor
            )
            
            # เลือกใช้ Portfolio Lot เป็นหลัก แต่ไม่ต่ำกว่า Traditional Lot
            base_lot_size = max(portfolio_lot, traditional_lot * 0.6)  # ลดจาก 0.8 เป็น 0.6 เพื่อความยืดหยุ่น
            
            # 🎯 ปรับตามแรงแท่งเทียน (Candle Strength Adjustment)
            candle_strength_adj = self._calculate_candle_strength_multiplier(signal.strength, candle)
            
            # ปรับ lot size ตาม Zone Recommendation
            if zone_recommendation:
                if zone_recommendation.get('should_enter', True):
                    zone_multiplier = zone_recommendation.get('lot_multiplier', 1.0)
                else:
                    # ถ้า Zone Analysis แนะนำไม่ให้เข้า
                    logger.warning(f"🚫 Zone Analysis blocks entry: {zone_recommendation.get('reason', 'Unknown')}")
                    return {
                        'should_enter': False,
                        'reasons': [f"Zone Analysis: {zone_recommendation.get('reason', 'Not suitable for zone distribution')}"],
                        'signal': None,
                        'lot_size': 0.0
                    }
            else:
                zone_multiplier = 1.0
            
            # รวมทุกปัจจัย (เพิ่มการจำกัดขนาด)
            multiplier_total = zone_multiplier * candle_strength_adj
            # จำกัด Total Multiplier ไม่ให้เกิน 1.5x
            multiplier_total = min(multiplier_total, 1.5)
            lot_size = base_lot_size * multiplier_total
            
            logger.info(f"📊 Enhanced Lot Size Calculation:")
            logger.info(f"   Positions Count: {positions_count}")
            logger.info(f"   Market Volatility: {market_volatility:.1f}%")
            logger.info(f"   Portfolio Risk Lot: {portfolio_lot:.3f}")
            logger.info(f"   Traditional Lot: {traditional_lot:.3f}")
            logger.info(f"   Selected Base Lot: {base_lot_size:.3f}")
            logger.info(f"   Candle Strength Adj: {candle_strength_adj:.2f}x (Strength: {signal.strength:.1f}%)")
            if zone_recommendation:
                logger.info(f"   Zone Multiplier: {zone_multiplier:.2f}x ({zone_recommendation.get('reason', 'N/A')})")
            logger.info(f"   Total Multiplier: {multiplier_total:.2f}x (capped at 1.5x)")
            logger.info(f"   Final Lot Size: {lot_size:.3f}")
            
            # ปรับขนาด lot สำหรับสัญลักษณ์ทองคำ (ลดการลดขนาดอีก)
            if 'XAU' in signal.symbol.upper() or 'GOLD' in signal.symbol.upper():
                # ทองคำมีความผันผวนสูง แต่ไม่ลดมากเกินไปเพื่อให้ได้ lot หลากหลาย
                lot_size = lot_size * 0.9  # เปลี่ยนจาก 0.8 เป็น 0.9
                logger.info(f"   XAUUSD Adjustment: ×0.9 (was {lot_size/0.9:.3f})")
            
            # ปรับขนาด Lot ตามสถานะพอร์ต
            adjusted_lot = self._adjust_lot_size_by_portfolio_state(lot_size, current_state)
            
            return {
                'should_enter': True,
                'reasons': ['ผ่านเงื่อนไขการเข้าทั้งหมด'],
                'signal': signal,
                'lot_size': adjusted_lot,
                'market_strength': market_strength,
                'volatility': volatility
            }
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการตัดสินใจเข้าเทรด: {str(e)}")
            return {
                'should_enter': False,
                'reasons': [f'เกิดข้อผิดพลาด: {str(e)}'],
                'signal': None,
                'lot_size': 0.0
            }
            
    # 🗑️ EMERGENCY EXIT SYSTEM REMOVED
    # All exit logic handled by Smart Profit Taking System only
    
    def should_exit_positions(self, current_state: PortfolioState, 
                            current_prices: Dict[str, float]) -> Dict[str, Any]:
        """🗑️ REMOVED - All exit logic handled by Smart Profit Taking System"""
        logger.debug("🗑️ Emergency Exit removed - all exits handled by Smart Profit Taking System")
        return {'should_exit': False, 'reason': 'Emergency Exit removed - using Smart Profit Taking System only'}
            
    def execute_trade_decision(self, decision: Dict[str, Any]) -> OrderResult:
        """
        ดำเนินการตามการตัดสินใจเทรด
        
        Args:
            decision: ผลการตัดสินใจจาก should_enter_trade
            
        Returns:
            OrderResult: ผลลัพธ์การส่ง Order
        """
        try:
            if not decision.get('should_enter', False):
                return OrderResult(
                    success=False,
                    error_message=f"ไม่ควรเข้าเทรด: {'; '.join(decision.get('reasons', []))}"
                )
                
            signal = decision['signal']
            lot_size = decision['lot_size']
            
            # ส่ง Order
            result = self.order_manager.place_order_from_signal(
                signal, lot_size, self.current_balance
            )
            
            if result.success:
                # บันทึกการเทรด
                self.trading_conditions.register_order_for_candle(signal.timestamp)
                
                # อัพเดทสถิติ
                self.performance_metrics.total_trades += 1
                
                logger.info(f"ส่ง Order สำเร็จ - Ticket: {result.ticket}, "
                           f"Direction: {signal.direction}, Lot: {lot_size}")
                           
            return result
            
        except Exception as e:
            error_msg = f"เกิดข้อผิดพลาดในการดำเนินการเทรด: {str(e)}"
            logger.error(error_msg)
            return OrderResult(success=False, error_message=error_msg)
            
    def execute_exit_decision(self, decision: Dict[str, Any]) -> CloseResult:
        """
        ดำเนินการตามการตัดสินใจปิด Position
        
        Args:
            decision: ผลการตัดสินใจจาก should_exit_positions
            
        Returns:
            CloseResult: ผลลัพธ์การปิด Position
        """
        try:
            if not decision.get('should_exit', False):
                return CloseResult(
                    success=False,
                    closed_tickets=[],
                    error_message=f"ไม่ควรปิด Position: {decision.get('reason', '')}"
                )
                
            positions_to_close = decision.get('positions_to_close', self.order_manager.active_positions)
            exit_type = decision.get('exit_type', 'manual')
            reason = decision.get('reason', 'Portfolio decision')
            
            # ปิด Position
            if exit_type == 'scaling':
                scaling_type = decision.get('scaling_type', '1:1')
                result = self.order_manager.close_positions_by_scaling_ratio(
                    positions_to_close, scaling_type, reason
                )
            else:
                result = self.order_manager.close_positions_group(positions_to_close, reason)
                
            if result.success:
                # อัพเดทสถิติ
                self._update_performance_metrics(result)
                
                logger.info(f"ปิด Position สำเร็จ - จำนวน: {len(result.closed_tickets)}, "
                           f"Profit: {result.total_profit:.2f}")
                           
            return result
            
        except Exception as e:
            error_msg = f"เกิดข้อผิดพลาดในการปิด Position: {str(e)}"
            logger.error(error_msg)
            return CloseResult(
                success=False,
                closed_tickets=[],
                error_message=error_msg
            )
            
    def _check_portfolio_limits(self, current_state: PortfolioState, direction: str) -> Dict[str, Any]:
        """
        ตรวจสอบข้อจำกัดของพอร์ต
        
        Args:
            current_state: สถานะพอร์ตปัจจุบัน
            direction: ทิศทางที่จะเทรด
            
        Returns:
            Dict: ผลการตรวจสอบ
        """
        result = {'can_enter': True, 'reasons': []}
        
        # ตรวจสอบการใช้เงินทุน (ปิดใช้งาน - เพื่อ Recovery Systems)
        # if current_state.exposure_percentage >= self.max_portfolio_exposure:
        #     result['can_enter'] = False
        #     result['reasons'].append(
        #         f"การใช้เงินทุนเกิน {self.max_portfolio_exposure}% ({current_state.exposure_percentage:.1f}%)"
        #     )
            
        # ตรวจสอบสมดุล Buy:Sell (ยืดหยุ่นกว่าเดิม)
        total_positions = current_state.buy_sell_ratio.get('total_positions', 0)
        
        # 🚀 ADAPTIVE BALANCE MANAGEMENT - ให้ Adaptive Entry Control จัดการแทน
        # ปิดการใช้ balance_stop_threshold เพราะ Adaptive System จัดการแล้ว
        # if total_positions < 3:
        #     logger.info(f"💡 Portfolio มี Position {total_positions} ตัว - ข้ามการเช็คสมดุล")
        # else:
        #     # เช็คสมดุลเมื่อมี position หลายตัว
        #     if direction == "BUY":
        #         buy_pct = current_state.buy_sell_ratio['buy_percentage']
        #         if buy_pct >= self.balance_stop_threshold:
        #             result['can_enter'] = False
        #             result['reasons'].append(f"Buy positions เกิน {self.balance_stop_threshold}% ({buy_pct:.1f}%)")
        #     else:  # SELL
        #         sell_pct = current_state.buy_sell_ratio['sell_percentage']
        #         if sell_pct >= self.balance_stop_threshold:
        #             result['can_enter'] = False
        #             result['reasons'].append(f"Sell positions เกิน {self.balance_stop_threshold}% ({sell_pct:.1f}%)")
        
        logger.info(f"🚀 ADAPTIVE: Balance management handled by Adaptive Entry Control")
                
        # 🚀 ADAPTIVE RISK MANAGEMENT - ไม่บล็อค Risk % เพื่อให้ระบบปิดทำงาน
        # ปิดการตรวจสอบ Risk % เพื่อรองรับ Unlimited Entry Strategy
        # if current_state.risk_percentage >= 20.0:  # ความเสี่ยงสูงสุด 20%
        #     result['can_enter'] = False
        #     result['reasons'].append(f"ความเสี่ยงรวมเกิน 20% ({current_state.risk_percentage:.1f}%)")
        logger.info(f"🚀 ADAPTIVE: Risk {current_state.risk_percentage:.1f}% - Allow entry for portfolio management")
            
        return result
        
    def _check_portfolio_exit_conditions(self, current_state: PortfolioState) -> Dict[str, Any]:
        """
        ตรวจสอบเงื่อนไขการปิดของพอร์ต
        
        Args:
            current_state: สถานะพอร์ตปัจจุบัน
            
        Returns:
            Dict: ผลการตรวจสอบ
        """
        # ตรวจสอบเป้าหมายกำไร
        if current_state.total_profit_percentage >= self.profit_target:
            return {
                'should_exit': True,
                'exit_type': 'profit_target',
                'positions_to_close': self.order_manager.active_positions,
                'reason': f'ถึงเป้าหมายกำไร {self.profit_target}% ({current_state.total_profit_percentage:.2f}%)'
            }
            
        # ตรวจสอบความไม่สมดุลรุนแรง
        buy_pct = current_state.buy_sell_ratio['buy_percentage']
        sell_pct = current_state.buy_sell_ratio['sell_percentage']
        
        if buy_pct >= 85.0 or sell_pct >= 85.0:
            # ปิดแบบ Scaling เพื่อปรับสมดุล
            return {
                'should_exit': True,
                'exit_type': 'scaling',
                'scaling_type': '1:2',
                'reason': f'ปรับสมดุลพอร์ต (Buy: {buy_pct:.1f}%, Sell: {sell_pct:.1f}%)'
            }
            
        return {'should_exit': False}
        
    def _check_daily_loss_limit(self, current_state: PortfolioState) -> Dict[str, Any]:
        """
        ตรวจสอบขาดทุนต่อวัน
        
        Args:
            current_state: สถานะพอร์ตปัจจุบัน
            
        Returns:
            Dict: ผลการตรวจสอบ
        """
        # คำนวณ P&L ต่อวัน
        daily_pnl = current_state.account_balance - self.daily_start_balance
        daily_pnl_percentage = (daily_pnl / self.daily_start_balance) * 100
        
        if daily_pnl_percentage <= -self.max_daily_loss:
            return {
                'should_exit': True,
                'exit_type': 'daily_loss_limit',
                'positions_to_close': self.order_manager.active_positions,
                'reason': f'ถึงขาดทุนต่อวันสูงสุด {self.max_daily_loss}% ({daily_pnl_percentage:.2f}%)'
            }
            
        return {'should_exit': False}
        
    def _check_maximum_drawdown(self) -> Dict[str, Any]:
        """
        ตรวจสอบ Maximum Drawdown
        
        Returns:
            Dict: ผลการตรวจสอบ
        """
        if len(self.performance_metrics.equity_history) < 2:
            return {'should_exit': False}
            
        max_drawdown = RiskCalculator.calculate_maximum_drawdown_percentage(
            self.performance_metrics.equity_history
        )
        
        if max_drawdown >= self.max_drawdown_limit:
            return {
                'should_exit': True,
                'exit_type': 'max_drawdown',
                'positions_to_close': self.order_manager.active_positions,
                'reason': f'ถึง Maximum Drawdown {self.max_drawdown_limit}% ({max_drawdown:.2f}%)'
            }
            
        return {'should_exit': False}
        
    def _adjust_lot_size_by_portfolio_state(self, base_lot: float, 
                                          current_state: PortfolioState) -> float:
        """
        ปรับขนาด Lot ตามสถานะพอร์ต (ปรับให้ยืดหยุ่นมากขึ้น)
        
        Args:
            base_lot: ขนาด Lot พื้นฐาน
            current_state: สถานะพอร์ตปัจจุบัน
            
        Returns:
            float: ขนาด Lot ที่ปรับแล้ว
        """
        adjusted_lot = base_lot
        adjustment_reasons = []
        
        # ลดขนาดเมื่อมี Position เยอะมากเกินไป (เกณฑ์สูงขึ้น)
        if current_state.total_positions >= 25:  # เพิ่มเกณฑ์จาก 15 เป็น 25
            adjusted_lot *= 0.95  # ลดน้อยลง จาก 0.9 เป็น 0.95
            adjustment_reasons.append(f"High positions ({current_state.total_positions}): ×0.95")
            
        # ลดขนาดเมื่อความเสี่ยงสูงมาก (เกณฑ์สูงขึ้น)
        if current_state.risk_percentage >= 30.0:  # เพิ่มเกณฑ์จาก 25 เป็น 30
            adjusted_lot *= 0.9  # ลดน้อยลง จาก 0.8 เป็น 0.9
            adjustment_reasons.append(f"High risk ({current_state.risk_percentage:.1f}%): ×0.9")
            
        # ลดขนาดเมื่อใช้เงินทุนเกือบหมด (เกณฑ์สูงขึ้น)
        if current_state.exposure_percentage >= 90.0:  # เพิ่มเกณฑ์จาก 80 เป็น 90
            adjusted_lot *= 0.98  # ลดน้อยลง จาก 0.95 เป็น 0.98
            adjustment_reasons.append(f"High exposure ({current_state.exposure_percentage:.1f}%): ×0.98")
            
        # ปรับให้อยู่ในช่วงที่เหมาะสม
        adjusted_lot = max(0.01, min(adjusted_lot, 2.0))
        
        if adjustment_reasons:
            logger.info(f"📉 Portfolio Adjustments: {', '.join(adjustment_reasons)}")
            logger.info(f"   Base → Adjusted: {base_lot:.3f} → {adjusted_lot:.3f}")
        
        return round(adjusted_lot, 2)
    
    def _calculate_candle_strength_multiplier(self, signal_strength: float, candle: CandleData) -> float:
        """
        🎯 คำนวณตัวคูณ lot ตามแรงแท่งเทียนและแรงสัญญาณ
        
        Args:
            signal_strength: แรงสัญญาณ (0-100)
            candle: ข้อมูลแท่งเทียน
            
        Returns:
            float: ตัวคูณ lot (0.7-1.5x)
        """
        try:
            # 1. แรงสัญญาณ (Signal Strength)
            if signal_strength >= 80.0:
                signal_multiplier = 1.4  # แรงมาก
            elif signal_strength >= 60.0:
                signal_multiplier = 1.2  # แรงปานกลางสูง
            elif signal_strength >= 40.0:
                signal_multiplier = 1.0  # แรงปานกลาง
            elif signal_strength >= 20.0:
                signal_multiplier = 0.9  # แรงน้อย
            else:
                signal_multiplier = 0.8  # แรงน้อยมาก
                
            # 2. แรงแท่งเทียน (Candle Body Strength)
            if hasattr(candle, 'body_size_percentage'):
                body_strength = candle.body_size_percentage
            else:
                # คำนวณ body strength
                body_strength = abs((candle.close - candle.open) / candle.open) * 100 if candle.open != 0 else 0
                
            if body_strength >= 0.3:  # แท่งแรงมาก (>0.3%)
                candle_multiplier = 1.3
            elif body_strength >= 0.2:  # แท่งแรงปานกลาง (>0.2%)
                candle_multiplier = 1.1
            elif body_strength >= 0.1:  # แท่งแรงน้อย (>0.1%)
                candle_multiplier = 1.0
            else:  # แท่งอ่อน (<0.1%)
                candle_multiplier = 0.9
                
            # 3. รวมและจำกัดขอบเขต
            combined_multiplier = (signal_multiplier + candle_multiplier) / 2
            final_multiplier = max(0.7, min(1.5, combined_multiplier))
            
            logger.info(f"🎯 Candle Strength Analysis:")
            logger.info(f"   Signal Strength: {signal_strength:.1f}% → {signal_multiplier:.1f}x")
            logger.info(f"   Body Strength: {body_strength:.3f}% → {candle_multiplier:.1f}x")
            logger.info(f"   Combined: {final_multiplier:.2f}x")
            
            return final_multiplier
            
        except Exception as e:
            logger.error(f"Error calculating candle strength multiplier: {e}")
            return 1.0  # fallback
        
    def _estimate_market_volatility(self) -> float:
        """
        ประมาณการความผันผวนของตลาด
        
        Returns:
            float: ความผันผวนเป็นเปอร์เซ็นต์
        """
        # ใช้ข้อมูลจากประวัติราคาหรือสถิติที่มี
        # สำหรับตัวอย่างนี้ใช้ค่าคงที่
        return 1.5  # 1.5% volatility
        
    def _update_performance_metrics(self, close_result: CloseResult):
        """
        อัพเดทเมตริกการทำงาน
        
        Args:
            close_result: ผลลัพธ์การปิด Position
        """
        try:
            if close_result.total_profit > 0:
                self.performance_metrics.winning_trades += len(close_result.closed_tickets)
                self.performance_metrics.total_profit += close_result.total_profit
            else:
                self.performance_metrics.losing_trades += len(close_result.closed_tickets)
                self.performance_metrics.total_loss += abs(close_result.total_profit)
                
            # คำนวณ Win Rate
            total_closed = self.performance_metrics.winning_trades + self.performance_metrics.losing_trades
            if total_closed > 0:
                self.performance_metrics.win_rate_percentage = (
                    self.performance_metrics.winning_trades / total_closed
                ) * 100
                
            # คำนวณ Profit Factor
            if self.performance_metrics.total_loss > 0:
                self.performance_metrics.profit_factor = (
                    self.performance_metrics.total_profit / self.performance_metrics.total_loss
                )
                
            # อัพเดท Equity History
            self.performance_metrics.equity_history.append(self.current_balance)
            
            # คำนวณ Max Drawdown
            if len(self.performance_metrics.equity_history) > 1:
                self.performance_metrics.max_drawdown_percentage = (
                    RiskCalculator.calculate_maximum_drawdown_percentage(
                        self.performance_metrics.equity_history
                    )
                )
                
            # คำนวณ Daily P&L
            daily_pnl = self.current_balance - self.daily_start_balance
            self.performance_metrics.daily_pnl_percentage = (
                daily_pnl / self.daily_start_balance
            ) * 100
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการอัพเดทเมตริก: {str(e)}")
            
    def get_portfolio_summary(self) -> Dict[str, Any]:
        """
        ดึงสรุปข้อมูลพอร์ต
        
        Returns:
            Dict: ข้อมูลสรุปพอร์ต
        """
        try:
            # ตรวจสอบว่ามี order_manager หรือไม่
            if not hasattr(self.order_manager, 'active_positions'):
                return {'error': 'No order manager available'}
                
            positions = self.order_manager.active_positions or []
            
            # ตรวจสอบว่ามี positions หรือไม่
            if not positions:
                return {
                    'account_balance': self.current_balance,
                    'initial_balance': self.initial_balance,
                    'total_profit_loss': 0.0,
                    'total_profit_percentage': 0.0,
                    'total_positions': 0,
                    'profitable_positions': 0,
                    'losing_positions': 0,
                    'performance_metrics': {
                        'total_trades': 0,
                        'win_rate_percentage': 0.0,
                        'profit_factor': 0.0,
                        'max_drawdown_percentage': 0.0,
                        'daily_pnl_percentage': 0.0
                    }
                }
                
            profit_loss = self.order_manager.calculate_total_profit_loss()
            
            return {
                'account_balance': self.current_balance,
                'initial_balance': self.initial_balance,
                'total_profit_loss': profit_loss['net_profit'],
                'total_profit_percentage': (profit_loss['net_profit'] / self.initial_balance) * 100,
                'total_positions': len(positions),
                'profitable_positions': profit_loss['profitable_count'],
                'losing_positions': profit_loss['losing_count'],
                'performance_metrics': {
                    'total_trades': self.performance_metrics.total_trades,
                    'win_rate_percentage': self.performance_metrics.win_rate_percentage,
                    'profit_factor': self.performance_metrics.profit_factor,
                    'max_drawdown_percentage': self.performance_metrics.max_drawdown_percentage,
                    'daily_pnl_percentage': self.performance_metrics.daily_pnl_percentage
                },
                'risk_settings': {
                    'max_risk_per_trade': self.max_risk_per_trade,
                    'max_portfolio_exposure': self.max_portfolio_exposure,
                    'max_daily_loss': self.max_daily_loss,
                    'profit_target': self.profit_target
                }
            }
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการสรุปพอร์ต: {str(e)}")
            return {'error': str(e)}
            
    def reset_daily_metrics(self):
        """รีเซ็ตเมตริกรายวัน"""
        try:
            current_date = datetime.now().date()
            
            # ตรวจสอบว่าเป็นวันใหม่หรือไม่
            if current_date > self.daily_start_time:
                self.daily_start_balance = self.current_balance
                self.daily_start_time = current_date
                self.performance_metrics.daily_pnl_percentage = 0.0
                
                # ทำความสะอาดข้อมูลเก่า
                self.trading_conditions.cleanup_old_candle_records()
                
                logger.info(f"รีเซ็ตเมตริกรายวันสำหรับวันที่ {current_date}")
                
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการรีเซ็ตเมตริกรายวัน: {str(e)}")
    
    # 🗑️ SMART RECOVERY SYSTEM REMOVED - Replaced by Smart Profit Taking System
    def check_and_execute_smart_recovery(self, current_price: float, 
                                         block_recovery: bool = False) -> Dict[str, Any]:
        """🗑️ REMOVED - Smart Recovery replaced by Smart Profit Taking System"""
        logger.debug("🗑️ Smart Recovery removed - functionality moved to Smart Profit Taking System")
        return {'executed': False, 'reason': 'Smart Recovery removed - using Smart Profit Taking System instead'}
    
    def _get_zone_smart_entry(self, signal: Signal, current_price: float) -> Optional[Dict[str, Any]]:
        """ดึงคำแนะนำการเข้าจาก Zone Analysis"""
        try:
            # Initialize zone analyzer if not done
            if self.zone_analyzer is None:
                from price_zone_analysis import PriceZoneAnalyzer
                from zone_rebalancer import ZoneRebalancer
                self.zone_analyzer = PriceZoneAnalyzer(signal.symbol, num_zones=10)
                self.zone_rebalancer = ZoneRebalancer(self.zone_analyzer)
            
            # อัพเดทราคาปัจจุบัน
            self.zone_analyzer.update_price_history(current_price)
            
            # ถ้ายังไม่มีโซน ให้สร้างขึ้นมา
            if not self.zone_analyzer.zones:
                self.zone_analyzer.initialize_zones(current_price)
            
            # ดึงคำแนะนำ
            recommendation = self.zone_analyzer.get_smart_entry_recommendation(
                signal.direction, current_price, self.order_manager.active_positions
            )
            
            if recommendation.recommended_action == "WAIT":
                logger.info(f"🚫 Zone Analysis: {recommendation.reason}")
                return None
            
            logger.info(f"🎯 Zone Analysis Recommendation:")
            logger.info(f"   Action: {recommendation.recommended_action}")
            logger.info(f"   Target Zone: {recommendation.target_zone_id}")
            logger.info(f"   Price Range: {recommendation.target_price_range[0]:.2f} - {recommendation.target_price_range[1]:.2f}")
            logger.info(f"   Confidence: {recommendation.confidence_score:.1f}%")
            logger.info(f"   Lot Multiplier: {recommendation.lot_size_multiplier:.2f}x")
            logger.info(f"   Reason: {recommendation.reason}")
            
            return {
                'action': recommendation.recommended_action,
                'zone_id': recommendation.target_zone_id,
                'price_range': recommendation.target_price_range,
                'confidence': recommendation.confidence_score,
                'lot_multiplier': recommendation.lot_size_multiplier,
                'reason': recommendation.reason,
                'alternatives': recommendation.alternative_zones
            }
            
        except Exception as e:
            logger.error(f"Error getting zone smart entry: {e}")
            return None
    
    def _get_zone_based_entry_analysis(self, signal: Signal, current_price: float) -> Optional[Dict[str, Any]]:
        """
        🎯 ใหม่! วิเคราะห์การเข้าไม้แบบ Zone-Based ที่เข้ากับระบบปิดไม้
        
        Args:
            signal: สัญญาณการเทรด
            current_price: ราคาปัจจุบัน
            
        Returns:
            Dict: คำแนะนำการเข้าไม้แบบ Zone-Based
        """
        try:
            if not self.position_manager:
                return None
            
            # ดึงข้อมูล Positions ปัจจุบัน
            positions = self.order_manager.active_positions or []
            
            # อัพเดท Zones จาก Positions ปัจจุบัน
            zones_updated = self.position_manager.zone_manager.update_zones_from_positions(positions, current_price)
            if not zones_updated:
                # ถ้าไม่มี Zones ให้สร้างใหม่
                logger.info("🎯 Creating initial zones for entry analysis")
                return self._create_initial_zone_recommendation(signal, current_price)
            
            # วิเคราะห์ Zone Distribution ปัจจุบัน
            zone_analysis = self._analyze_current_zone_distribution(current_price)
            
            # ตรวจสอบว่าการเข้าไม้นี้จะช่วย Zone Balance ไหม
            entry_impact = self._evaluate_entry_impact_on_zones(signal.direction, current_price, zone_analysis)
            
            # ตัดสินใจแนะนำ
            if entry_impact['should_enter']:
                logger.info(f"🎯 Zone-Based Entry Recommendation:")
                logger.info(f"   Direction: {signal.direction}")
                logger.info(f"   Target Zone: {entry_impact['target_zone_id']}")
                logger.info(f"   Zone Health Impact: +{entry_impact['health_improvement']:.1f}")
                logger.info(f"   Portfolio Balance Impact: {entry_impact['balance_impact']}")
                logger.info(f"   Reason: {entry_impact['reason']}")
                
                return {
                    'should_enter': True,
                    'target_zone': entry_impact['target_zone_id'],
                    'lot_multiplier': entry_impact['lot_multiplier'],
                    'confidence': entry_impact['confidence'],
                    'reason': entry_impact['reason'],
                    'zone_health_impact': entry_impact['health_improvement'],
                    'balance_impact': entry_impact['balance_impact']
                }
            else:
                logger.info(f"🚫 Zone-Based Entry Block: {entry_impact['reason']}")
                return {
                    'should_enter': False,
                    'reason': entry_impact['reason'],
                    'lot_multiplier': 0.5,  # ลด lot ถ้าไม่เหมาะสม
                    'confidence': 0.3
                }
                
        except Exception as e:
            logger.error(f"❌ Error in zone-based entry analysis: {e}")
            return None
    
    def _create_initial_zone_recommendation(self, signal: Signal, current_price: float) -> Dict[str, Any]:
        """สร้างคำแนะนำสำหรับการเข้าไม้ครั้งแรก"""
        return {
            'should_enter': True,
            'target_zone': 0,
            'lot_multiplier': 1.0,
            'confidence': 0.8,
            'reason': 'Initial position - creating first zone',
            'zone_health_impact': 0.0,
            'balance_impact': 'NEUTRAL'
        }
    
    def _analyze_current_zone_distribution(self, current_price: float) -> Dict[str, Any]:
        """วิเคราะห์การกระจาย Zones ปัจจุบัน"""
        try:
            zones = self.position_manager.zone_manager.zones
            
            if not zones:
                return {'total_zones': 0, 'buy_heavy_zones': 0, 'sell_heavy_zones': 0, 'balanced_zones': 0}
            
            buy_heavy_count = 0
            sell_heavy_count = 0
            balanced_count = 0
            
            for zone in zones.values():
                if zone.total_positions > 0:
                    if zone.balance_ratio >= 0.7:  # BUY-heavy
                        buy_heavy_count += 1
                    elif zone.balance_ratio <= 0.3:  # SELL-heavy
                        sell_heavy_count += 1
                    else:
                        balanced_count += 1
            
            return {
                'total_zones': len([z for z in zones.values() if z.total_positions > 0]),
                'buy_heavy_zones': buy_heavy_count,
                'sell_heavy_zones': sell_heavy_count,
                'balanced_zones': balanced_count,
                'current_price': current_price
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing zone distribution: {e}")
            return {'total_zones': 0, 'buy_heavy_zones': 0, 'sell_heavy_zones': 0, 'balanced_zones': 0}
    
    def _evaluate_entry_impact_on_zones(self, direction: str, current_price: float, zone_analysis: Dict) -> Dict[str, Any]:
        """ประเมินผลกระทบของการเข้าไม้ต่อ Zone System"""
        try:
            # คำนวณ Zone ที่ราคาปัจจุบันจะเข้าไป
            target_zone_id = self.position_manager.zone_manager.calculate_zone_id(current_price)
            target_zone = self.position_manager.zone_manager.zones.get(target_zone_id)
            
            # วิเคราะห์ผลกระทบ
            should_enter = True
            confidence = 0.7
            lot_multiplier = 1.0
            health_improvement = 0.0
            balance_impact = 'NEUTRAL'
            reason = f"Enter {direction} in Zone {target_zone_id}"
            
            # ถ้ามี Zone อยู่แล้ว
            if target_zone and target_zone.total_positions > 0:
                current_balance = target_zone.balance_ratio
                
                # 🚫 ตรวจสอบการกระจุกของ Position (ป้องกันการมี Position มากเกินไปใน Zone เดียว)
                if target_zone.total_positions >= 25:  # ถ้ามี Position เกิน 25 ตัวใน Zone เดียว
                    should_enter = False
                    confidence = 0.2
                    lot_multiplier = 0.5
                    balance_impact = 'NEGATIVE'
                    reason = f"Block entry: Zone {target_zone_id} overcrowded ({target_zone.total_positions} positions)"
                    
                    return {
                        'should_enter': should_enter,
                        'target_zone_id': target_zone_id,
                        'lot_multiplier': lot_multiplier,
                        'confidence': confidence,
                        'health_improvement': -20.0,
                        'balance_impact': balance_impact,
                        'reason': reason
                    }
                
                if direction == "BUY":
                    # ถ้า Zone นี้ SELL-heavy อยู่ → BUY จะช่วยสมดุล
                    if current_balance <= 0.3:  # SELL-heavy
                        health_improvement = 30.0
                        confidence = 0.9
                        lot_multiplier = 1.2
                        balance_impact = 'POSITIVE'
                        reason = f"BUY helps balance SELL-heavy Zone {target_zone_id}"
                    
                    # ถ้า Zone นี้ BUY-heavy อยู่แล้ว → BUY จะทำให้เสียสมดุลมากขึ้น
                    elif current_balance >= 0.7:  # BUY-heavy
                        health_improvement = -10.0
                        confidence = 0.4
                        lot_multiplier = 0.7
                        balance_impact = 'NEGATIVE'
                        
                        # เช็คว่ามี SELL-heavy zones อื่นไหม ถ้าไม่มีก็ยังให้เข้าได้
                        if zone_analysis['sell_heavy_zones'] == 0:
                            should_enter = True
                            reason = f"BUY in BUY-heavy Zone {target_zone_id} - but no SELL-heavy zones to balance"
                        else:
                            should_enter = False
                            reason = f"Block BUY in BUY-heavy Zone {target_zone_id} - prefer SELL-heavy zones"
                
                else:  # SELL
                    # ถ้า Zone นี้ BUY-heavy อยู่ → SELL จะช่วยสมดุล
                    if current_balance >= 0.7:  # BUY-heavy
                        health_improvement = 30.0
                        confidence = 0.9
                        lot_multiplier = 1.2
                        balance_impact = 'POSITIVE'
                        reason = f"SELL helps balance BUY-heavy Zone {target_zone_id}"
                    
                    # ถ้า Zone นี้ SELL-heavy อยู่แล้ว → SELL จะทำให้เสียสมดุลมากขึ้น
                    elif current_balance <= 0.3:  # SELL-heavy
                        health_improvement = -10.0
                        confidence = 0.4
                        lot_multiplier = 0.7
                        balance_impact = 'NEGATIVE'
                        
                        # เช็คว่ามี BUY-heavy zones อื่นไหม
                        if zone_analysis['buy_heavy_zones'] == 0:
                            should_enter = True
                            reason = f"SELL in SELL-heavy Zone {target_zone_id} - but no BUY-heavy zones to balance"
                        else:
                            should_enter = False
                            reason = f"Block SELL in SELL-heavy Zone {target_zone_id} - prefer BUY-heavy zones"
            
            # ถ้าเป็น Zone ใหม่ → อนุญาตเสมอ
            else:
                health_improvement = 10.0
                confidence = 0.8
                reason = f"Create new Zone {target_zone_id} with {direction}"
            
            return {
                'should_enter': should_enter,
                'target_zone_id': target_zone_id,
                'lot_multiplier': lot_multiplier,
                'confidence': confidence,
                'health_improvement': health_improvement,
                'balance_impact': balance_impact,
                'reason': reason
            }
            
        except Exception as e:
            logger.error(f"❌ Error evaluating entry impact: {e}")
            return {
                'should_enter': True,
                'target_zone_id': 0,
                'lot_multiplier': 1.0,
                'confidence': 0.5,
                'health_improvement': 0.0,
                'balance_impact': 'UNKNOWN',
                'reason': f'Error in analysis: {str(e)}'
            }
    
    def check_and_execute_zone_rebalance(self, current_price: float) -> Dict[str, Any]:
        """ตรวจสอบและดำเนินการปรับสมดุลโซน"""
        try:
            # Initialize zone analyzer if not done
            if self.zone_analyzer is None:
                from price_zone_analysis import PriceZoneAnalyzer
                from zone_rebalancer import ZoneRebalancer
                # Use a default symbol if we don't have one
                symbol = getattr(self, 'current_symbol', 'XAUUSD')
                self.zone_analyzer = PriceZoneAnalyzer(symbol, num_zones=10)
                self.zone_rebalancer = ZoneRebalancer(self.zone_analyzer)
            
            # อัพเดทราคา
            self.zone_analyzer.update_price_history(current_price)
            
            # วิเคราะห์การกระจายปัจจุบัน
            positions = self.order_manager.active_positions
            analysis = self.zone_analyzer.analyze_position_distribution(positions)
            
            # ตรวจสอบว่าควร rebalance หรือไม่
            should_rebalance = self.zone_rebalancer.should_trigger_rebalance(analysis)
            
            if not should_rebalance:
                return {
                    'executed': False,
                    'reason': 'ยังไม่ถึงเงื่อนไข Rebalance',
                    'zone_score': analysis.overall_health_score,
                    'zone_quality': analysis.distribution_quality
                }
            
            # วิเคราะห์ความต้องการ rebalance
            rebalance_result = self.zone_rebalancer.analyze_rebalance_needs(positions, current_price)
            
            logger.info(f"📊 Zone Analysis Result:")
            logger.info(f"   Overall Score: {analysis.overall_health_score:.1f}/100")
            logger.info(f"   Quality: {analysis.distribution_quality}")
            logger.info(f"   Active Zones: {analysis.active_zones}/{analysis.total_zones}")
            logger.info(f"   Balanced Zones: {analysis.balanced_zones}")
            logger.info(f"   Critical Zones: {analysis.critical_zones}")
            
            # แสดงคำแนะนำ
            summary = self.zone_rebalancer.get_rebalance_summary(rebalance_result)
            logger.info(summary)
            
            # แสดง Zone Map
            zone_map = self.zone_analyzer.get_zone_map_display(current_price)
            logger.info(f"\n{zone_map}")
            
            return {
                'executed': True,
                'analysis': analysis,
                'rebalance_result': rebalance_result,
                'recommendations': rebalance_result.recommendations,
                'zone_score': analysis.overall_health_score,
                'zone_quality': analysis.distribution_quality,
                'summary': summary
            }
            
        except Exception as e:
            logger.error(f"Error in zone rebalance check: {e}")
            return {
                'executed': False,
                'error': str(e),
                'reason': f'เกิดข้อผิดพลาด: {str(e)}'
            }
    
    def check_advanced_breakout_recovery(self, current_price: float) -> Dict[str, Any]:
        """Advanced Breakout Recovery Strategy DISABLED - ใช้ Simple Position Manager แทน"""
        return {
            'should_block_recovery': False,
            'reason': 'Advanced Breakout Recovery disabled - using Simple Position Manager',
            'is_breakout_pending': False,
            'recovery_results': []
        }
        
        # ORIGINAL CODE DISABLED
        """
        try:
            positions = self.order_manager.active_positions
            
            # 1. วิเคราะห์ระดับ breakout
            breakout_analysis = self.advanced_recovery.analyze_breakout_levels(positions, current_price)
            
            # Log ข้อมูลการวิเคราะห์
            if breakout_analysis.get('has_levels'):
                analysis_info = breakout_analysis.get('breakout_analysis', {})
                potential = analysis_info.get('potential', 'NONE')
                max_buy = breakout_analysis.get('max_buy', 0)
                min_sell = breakout_analysis.get('min_sell', 0)
                logger.info(f"🔍 Advanced Breakout Analysis: {potential}")
                logger.info(f"   Current: {breakout_analysis.get('current_price', 0):.2f}, BUY: {max_buy:.2f}, SELL: {min_sell:.2f}")
            else:
                logger.info(f"🔍 Advanced Breakout Analysis: {breakout_analysis.get('reason', 'No analysis available')}")
            
            if not breakout_analysis.get('has_levels'):
                logger.info(f"📊 No breakout levels detected - Total positions: {len(positions)}")
                return {
                    'is_breakout_pending': False,
                    'should_block_recovery': False,
                    'breakout_direction': None,
                    'reason': breakout_analysis.get('reason', 'ไม่มีระดับ breakout'),
                    'recovery_groups': 0
                }
            
            # 2. ตรวจสอบการ breakout และสร้าง recovery group
            potential = breakout_analysis['breakout_analysis']['potential']
            
            if potential in ['BULLISH_BREAKOUT', 'BEARISH_BREAKOUT']:
                # สร้าง recovery group ใหม่
                group_id = self.advanced_recovery.create_recovery_group(breakout_analysis['breakout_analysis'], current_price)
                if group_id:
                    logger.info(f"🎯 สร้าง Recovery Group ใหม่: {group_id}")
            
            # 3. อัพเดทสถานะ recovery groups ที่มีอยู่
            update_results = self.advanced_recovery.update_recovery_groups(current_price, positions)
            
            # 4. เช็คการกระทำที่ต้องทำ
            actions_needed = update_results.get('actions_needed', [])
            ready_for_recovery = update_results.get('ready_for_recovery', [])
            
            # 5. ดำเนินการ Triple Recovery ถ้าพร้อม
            recovery_results = []
            # ดึงข้อมูล current_state สำหรับ validator
            account_info = self.order_manager.mt5.get_account_info()
            if account_info:
                current_state = self.analyze_portfolio_state(account_info)
                
                for group_id in ready_for_recovery:
                    # ส่ง Portfolio Health Validator ไปให้ Advanced Recovery ใช้ร่วมกัน
                    recovery_result = self.advanced_recovery.execute_triple_recovery(
                        group_id,
                        portfolio_validator=lambda candidate, state: self._validate_portfolio_improvement(candidate, current_state)
                    )
                    recovery_results.append(recovery_result)
                    
                    if recovery_result['success']:
                        logger.info(f"✅ Triple Recovery สำเร็จ: {group_id}")
                        logger.info(f"   กำไรสุทธิ: ${recovery_result['net_profit']:.2f}")
            
            # 6. ตัดสินใจการบล็อค Recovery
            should_block_recovery = self._should_block_traditional_recovery(breakout_analysis, update_results)
            
            # 7. สร้างผลลัพธ์
            result = {
                'is_breakout_pending': breakout_analysis.get('is_overlapping', False),
                'should_block_recovery': should_block_recovery,
                'breakout_direction': potential,
                'reason': breakout_analysis['breakout_analysis'].get('recommended_action', 'N/A'),
                'recovery_groups': len(self.advanced_recovery.active_recoveries),
                'actions_needed': actions_needed,
                'recovery_results': recovery_results,
                'breakout_levels': {
                    'max_buy': breakout_analysis.get('max_buy'),
                    'min_sell': breakout_analysis.get('min_sell'),
                    'current_price': current_price
                }
            }
            
            # Log สรุป
            logger.info(f"🎯 Advanced Breakout Recovery Analysis:")
            logger.info(f"   Current Price: {current_price}")
            logger.info(f"   Potential: {potential}")
            logger.info(f"   Active Recovery Groups: {result['recovery_groups']}")
            logger.info(f"   Block Traditional Recovery: {should_block_recovery}")
            logger.info(f"   Actions Needed: {len(actions_needed)}")
            logger.info(f"   Recovery Results: {len(recovery_results)}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error in advanced breakout recovery check: {e}")
            return {
                'is_breakout_pending': False,
                'should_block_recovery': False,
                'breakout_direction': None,
                'reason': f'เกิดข้อผิดพลาด: {str(e)}',
                'recovery_groups': 0
            }
    
    def _should_block_traditional_recovery(self, breakout_analysis: Dict, update_results: Dict) -> bool:
        # Traditional Recovery Blocking DISABLED - use Simple Position Manager instead
        # Do not block anything, let Simple Position Manager handle it
        return False
        
        # ORIGINAL CODE DISABLED
        """
        try:
            now = datetime.now()
            
            # เช็ค Advanced Recovery groups (ยืดหยุ่นมาก)
            active_groups = len(self.advanced_recovery.active_recoveries) if self.advanced_recovery else 0
            
            if active_groups > 0:
                # ตรวจสอบว่า groups ค้างนานเกินไปหรือไม่
                oldest_group_age = 0
                for group_id, group in self.advanced_recovery.active_recoveries.items():
                    age_minutes = (now - group.created_time).total_seconds() / 60
                    oldest_group_age = max(oldest_group_age, age_minutes)
                
                # ยืดหยุ่นมาก: ถ้า groups ค้างเกิน 3 นาที → ไม่บล็อค (ลดจาก 10 นาที)
                if oldest_group_age > 3:
                    logger.info(f"🔄 Advanced Recovery Timeout: Groups active for {oldest_group_age:.1f} minutes - Allow Smart Recovery")
                    return False
                
                # ถ้ามี groups เยอะเกิน 1 → ไม่บล็อค (ลดจาก 2 เป็น 1)
                if active_groups > 1:
                    logger.info(f"🔄 Advanced Recovery Overload: {active_groups} groups active - Allow Smart Recovery")
                    return False
                
                # บล็อคเฉพาะ 1 group แรกๆ เท่านั้น (ภายใน 3 นาที)
                logger.info(f"🔒 Temporary Block: {active_groups} Advanced Recovery group active ({oldest_group_age:.1f} min)")
                return True
            
            # บล็อคถ้าใกล้ breakout (ยืดหยุ่นมาก - ลดเวลารอ)
            potential = breakout_analysis.get('breakout_analysis', {}).get('potential', 'NONE')
            if potential in ['APPROACHING_BULLISH', 'APPROACHING_BEARISH']:
                logger.info(f"🔒 Near Breakout Detected: {potential}")
                # ตรวจสอบว่าใกล้ breakout มานานแล้วหรือยัง
                if hasattr(self, 'last_approaching_time'):
                    approaching_duration = (now - self.last_approaching_time).total_seconds() / 60
                    if approaching_duration > 2:  # ลดจาก 5 นาที เป็น 2 นาที
                        logger.info(f"🔄 Breakout Timeout: {approaching_duration:.1f} minutes - Allow Smart Recovery")
                        return False
                else:
                    self.last_approaching_time = now
                
                logger.info(f"🔒 Brief Breakout Wait: {potential} (max 2 min)")
                return True
            
            # ไม่บล็อคถ้าไม่มีเงื่อนไขพิเศษ
            logger.debug(f"🔓 No blocking conditions - Smart Recovery allowed")
            return False
            
        except Exception as e:
            logger.error(f"Error deciding recovery block: {e}")
            return False
    
    def get_unified_signal(self, candle: CandleData, current_price: float,
                          account_balance: float, volume_history: List[float] = None) -> Optional[RankedSignal]:
        """ดึงสัญญาณแบบรวมจาก Signal Manager (Single Entry Point)"""
        try:
            positions = self.order_manager.active_positions
            
            # ใช้ SignalManager เพื่อหาสัญญาณที่ดีที่สุด
            best_signal = self.signal_manager.get_best_signal(
                candle=candle,
                positions=positions,
                account_balance=account_balance,
                volume_history=volume_history,
                current_price=current_price,
                last_trade_time=self.last_trade_time
            )
            
            if best_signal:
                logger.info(f"🎯 Unified Signal: {best_signal.source} - {best_signal.signal.direction}")
                logger.info(f"   Priority: {best_signal.priority.name}, Score: {best_signal.confidence_score:.1f}")
                logger.info(f"   Reason: {best_signal.reason}")
            
            return best_signal
            
        except Exception as e:
            logger.error(f"Error getting unified signal: {e}")
            return None
    
    # 🗑️ DEPRECATED - ใช้ get_unified_signal() แทน
    def check_continuous_trading_opportunities(self, current_price: float, 
                                             current_candle: Optional[CandleData] = None) -> Dict[str, Any]:
        """ตรวจสอบโอกาสการเทรดแบบต่เนื่อง"""
        try:
            positions = self.order_manager.active_positions
            now = datetime.now()
            
            result = {
                'gap_filler_active': False,
                'force_trading_active': False,
                'recommended_signal': None,
                'activation_reason': '',
                'continuous_stats': {}
            }
            
            # 1. ตรวจสอบ Smart Gap Filler
            gap_result = self.gap_filler.should_activate_gap_filling(
                positions, current_price, self.last_trade_time
            )
            
            if gap_result['should_activate']:
                gap_signal = self.gap_filler.create_synthetic_signal(
                    gap_result['recommended_action']
                )
                
                if gap_signal:
                    result.update({
                        'gap_filler_active': True,
                        'recommended_signal': gap_signal,
                        'activation_reason': f"Gap Filling: {gap_result['activation_reason']}",
                        'gap_analysis': gap_result['gap_analysis']
                    })
                    
                    logger.info(f"🔧 Gap Filler Activated: {result['activation_reason']}")
                    return result
            
            # 2. ตรวจสอบ Force Trading Mode (ถ้า Gap Filler ไม่ทำงาน)
            force_result = self.force_trading.should_activate_force_mode(
                self.last_trade_time, positions
            )
            
            if force_result['should_activate']:
                force_signal = self.force_trading.create_force_signal(
                    force_result['recommended_action'], current_price
                )
                
                if force_signal:
                    result.update({
                        'force_trading_active': True,
                        'recommended_signal': force_signal,
                        'activation_reason': f"Force Trading: {force_result['reason']}",
                        'momentum_analysis': force_result['momentum_analysis']
                    })
                    
                    logger.info(f"🚨 Force Trading Activated: {result['activation_reason']}")
                    return result
            
            # 3. รวบรวมสถิติ
            result['continuous_stats'] = {
                'gap_filler_stats': self.gap_filler.get_fill_statistics(),
                'force_trading_stats': self.force_trading.get_force_statistics(),
                'last_trade_time': self.last_trade_time,
                'time_since_last_trade': (now - self.last_trade_time).total_seconds() / 60 if self.last_trade_time else None
            }
            
            return result
            
        except Exception as e:
            logger.error(f"Error checking continuous trading opportunities: {e}")
            return {
                'gap_filler_active': False,
                'force_trading_active': False,
                'recommended_signal': None,
                'activation_reason': f'Error: {e}',
                'continuous_stats': {}
            }
    
    def update_trade_timing(self, trade_executed: bool = False, signal_generated: bool = False):
        """อัพเดทเวลาการเทรดและสัญญาณ"""
        try:
            now = datetime.now()
            
            if trade_executed:
                self.last_trade_time = now
                logger.debug(f"📊 Trade timing updated: {now}")
            
            if signal_generated:
                self.last_signal_time = now
                logger.debug(f"📡 Signal timing updated: {now}")
                
        except Exception as e:
            logger.error(f"Error updating trade timing: {e}")
    
    def _validate_portfolio_improvement(self, recovery_candidate: Dict, current_state: PortfolioState) -> Dict[str, Any]:
        """ตรวจสอบว่าการปิดไม้จะทำให้พอร์ตดีขึ้นหรือไม่"""
        try:
            positions_to_close = recovery_candidate.get('positions', [])
            if not positions_to_close:
                return {'valid': False, 'reason': 'ไม่มีไม้ที่จะปิด'}
            
            # คำนวณ Net Profit ของไม้ที่จะปิด
            total_profit = 0
            profitable_count = 0
            losing_count = 0
            
            for pos in positions_to_close:
                total_profit += pos.profit
                if pos.profit > 0:
                    profitable_count += 1
                else:
                    losing_count += 1
            
            # เงื่อนไข 1: Net Profit ต้องเป็นบวก
            if total_profit <= 0:
                return {'valid': False, 'reason': f'Net profit เป็นลบ: ${total_profit:.2f}'}
            
            # เงื่อนไข 2: กำไรต้องมากกว่า % ของจำนวนไม้ (ใช้เกณฑ์ตาม lot size เหมือน Smart Recovery)
            position_count = len(positions_to_close)
            
            # คำนวณ total lots ของไม้ที่จะปิด
            total_lots = sum(pos.volume for pos in positions_to_close)
            
            # ใช้เกณฑ์เดียวกับ Smart Recovery - ตาม lot size
            if total_lots <= 0.02:  # รวมกัน <= 0.02 lot
                min_required_profit = 0.001  # แค่ $0.001 เท่านั้น!
            elif total_lots <= 0.05:  # รวมกัน <= 0.05 lot  
                min_required_profit = 0.005  # แค่ $0.005
            elif total_lots <= 0.1:   # รวมกัน <= 0.1 lot
                min_required_profit = 0.01   # แค่ $0.01
            elif current_state.account_balance <= 0 or position_count > 10:
                min_required_profit = 0.1    # กำไรขั้นต่ำ $0.1 สำหรับกรณีพิเศษ
            else:
                # สำหรับ lot ใหญ่ใช้เกณฑ์ยืดหยุ่น
                min_profit_percentage = min(position_count * 0.05, 0.5)  # ลดเหลือ 0.05% และไม่เกิน 0.5%
                min_required_profit = abs(current_state.account_balance) * (min_profit_percentage / 100)
                min_required_profit = min(min_required_profit, 5.0)  # จำกัดไม่เกิน $5
            
            logger.info(f"🎯 Portfolio Health: {total_lots} lots → ต้องการ ${min_required_profit:.3f}, ได้ ${total_profit:.3f}")
            
            if total_profit < min_required_profit:
                return {
                    'valid': False, 
                    'reason': f'กำไรไม่ถึงเกณฑ์: ${total_profit:.3f} < ${min_required_profit:.3f} (lots: {total_lots})'
                }
            
            # เงื่อนไข 3: ต้องมีไม้กำไรและขาดทุนปะปนกัน (ไม่ปิดแค่ฝั่งเดียว)
            if profitable_count == 0:
                return {'valid': False, 'reason': 'ไม่มีไม้กำไรในกลุ่ม'}
            
            if losing_count == 0:
                return {'valid': False, 'reason': 'ไม่มีไม้ขาดทุนในกลุ่ม - ไม่จำเป็นต้อง Recovery'}
            
            # เงื่อนไข 4: สมดุลของไม้ (ยืดหยุ่นสำหรับไม้เยอะ)
            balance_ratio = abs(profitable_count - losing_count) / position_count
            max_imbalance = 0.9 if position_count > 30 else 0.8  # ยืดหยุ่นมากขึ้นถ้ามีไม้เยอะ
            
            if balance_ratio > max_imbalance:
                return {'valid': False, 'reason': f'ไม้ไม่สมดุลเกินไป: กำไร {profitable_count} vs ขาดทุน {losing_count} ({balance_ratio:.1%})'}
            
            # เงื่อนไข 5: คำนวณผลกระทบต่อ Equity และ Free Margin
            estimated_new_balance = current_state.account_balance + total_profit
            margin_freed = sum(abs(pos.profit) * 0.01 for pos in positions_to_close)  # ประมาณการ
            estimated_new_free_margin = current_state.margin + margin_freed
            
            improvement_metrics = {
                'balance_improvement': total_profit,
                'balance_improvement_pct': (total_profit / current_state.account_balance) * 100,
                'estimated_new_balance': estimated_new_balance,
                'estimated_margin_freed': margin_freed,
                'estimated_new_free_margin': estimated_new_free_margin,
                'positions_closed': position_count,
                'profitable_positions': profitable_count,
                'losing_positions': losing_count
            }
            
            return {
                'valid': True,
                'reason': f'Portfolio improvement validated: +${total_profit:.2f} ({improvement_metrics["balance_improvement_pct"]:.2f}%)',
                'metrics': improvement_metrics
            }
            
        except Exception as e:
            logger.error(f"Error validating portfolio improvement: {e}")
            return {'valid': False, 'reason': f'Validation error: {str(e)}'}
    
    def _check_and_create_recovery_orders(self, positions: List[Any], current_price: float) -> Dict[str, Any]:
        """
        🎯 REPLACED: Recovery Orders now handled by Zone-Based System
        
        Args:
            positions: รายการ positions ทั้งหมด
            current_price: ราคาปัจจุบัน
            
        Returns:
            Dict: ผลการสร้าง Recovery Orders (Zone-based)
        """
        
        try:
            # Zone-Based System handles recovery automatically through zone coordination
            logger.debug("🎯 Recovery Orders handled by Zone-Based Position Management System")
            
            return {
                'recovery_created': False,
                'recovery_orders': [],
                'balance_orders': [],
                'dragged_positions': 0,
                'total_drag_loss': 0,
                'note': 'Recovery handled by Zone-Based System'
            }
            
        except Exception as e:
            logger.error(f"Error in recovery orders check: {e}")
            return {
                'recovery_created': False,
                'recovery_orders': [],
                'balance_orders': [],
                'dragged_positions': 0,
                'total_drag_loss': 0,
                'error': str(e)
            }
    
    def _calculate_balance_lot_size(self, positions: List[Any], direction: str) -> float:
        """คำนวณ Lot Size สำหรับ Balance Position"""
        
        try:
            # คำนวณ Lot เฉลี่ยของไม้ที่มีอยู่
            total_lot = sum(pos.volume for pos in positions)
            avg_lot = total_lot / len(positions) if positions else 0.01
            
            # ปรับ Lot ตามทิศทาง
            if direction == 'BUY':
                # BUY ใช้ Lot น้อยกว่าเฉลี่ยเล็กน้อย
                balance_lot = avg_lot * 0.8
            else:  # SELL
                # SELL ใช้ Lot น้อยกว่าเฉลี่ยเล็กน้อย
                balance_lot = avg_lot * 0.8
            
            # จำกัด Lot Size
            balance_lot = max(0.01, min(balance_lot, 0.1))
            
            # ปรับให้เป็น Step ที่ถูกต้อง (0.01)
            balance_lot = round(balance_lot, 2)
            
            return balance_lot
            
        except Exception as e:
            logger.error(f"Error calculating balance lot size: {e}")
            return 0.01  # Default lot size
    
    def _analyze_portfolio_balance(self, positions: List[Any], current_price: float) -> Dict[str, Any]:
        """วิเคราะห์สมดุลของ Portfolio"""
        
        try:
            if not positions:
                return {'imbalance_percentage': 0, 'imbalance_side': 'BALANCED'}
            
            buy_positions = [pos for pos in positions if pos.type == 0]
            sell_positions = [pos for pos in positions if pos.type == 1]
            
            total_positions = len(positions)
            buy_count = len(buy_positions)
            sell_count = len(sell_positions)
            
            buy_percentage = (buy_count / total_positions) * 100
            sell_percentage = (sell_count / total_positions) * 100
            
            imbalance_percentage = max(buy_percentage, sell_percentage)
            
            if buy_percentage > sell_percentage:
                imbalance_side = 'BUY'
            elif sell_percentage > buy_percentage:
                imbalance_side = 'SELL'
            else:
                imbalance_side = 'BALANCED'
            
            return {
                'total_positions': total_positions,
                'buy_count': buy_count,
                'sell_count': sell_count,
                'buy_percentage': buy_percentage,
                'sell_percentage': sell_percentage,
                'imbalance_percentage': imbalance_percentage,
                'imbalance_side': imbalance_side
            }
            
        except Exception as e:
            logger.error(f"Error analyzing portfolio balance: {e}")
            return {'imbalance_percentage': 0, 'imbalance_side': 'ERROR'}
    
    # 🗑️ Portfolio Health Check and Entry Quality Validation REMOVED
    # 
    # Reasoning: Let the Lightning Portfolio Cleanup System handle all risk management
    # - It's designed to close positions fast and safely
    # - Never closes at a loss (100% profit guarantee)  
    # - Always reduces position count by closing losing positions
    # - More positions = more opportunities for profitable cleanup
    # 
    # Blocking entries prevents the cleanup system from working optimally
