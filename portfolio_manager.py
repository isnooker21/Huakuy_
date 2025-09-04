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
from smart_recovery import SmartRecoverySystem
from price_zone_analysis import PriceZoneAnalyzer
from zone_rebalancer import ZoneRebalancer
from advanced_breakout_recovery import AdvancedBreakoutRecovery
from smart_gap_filler import SmartGapFiller
from force_trading_mode import ForceTradingMode
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
        self.trading_conditions = TradingConditions()
        self.smart_recovery = SmartRecoverySystem(order_manager.mt5)
        
        # เพิ่ม Zone Analysis System
        self.zone_analyzer = PriceZoneAnalyzer("XAUUSD", num_zones=10)
        self.zone_rebalancer = ZoneRebalancer(self.zone_analyzer)
        
        # เพิ่ม Advanced Breakout Recovery System
        self.advanced_recovery = AdvancedBreakoutRecovery(order_manager.mt5)
        
        # เพิ่ม Continuous Trading Systems
        self.gap_filler = SmartGapFiller(order_manager.mt5)
        self.force_trading = ForceTradingMode(order_manager.mt5)
        
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
                
            # ตรวจสอบข้อจำกัดพอร์ต
            portfolio_checks = self._check_portfolio_limits(current_state, signal.direction)
            if not portfolio_checks['can_enter']:
                return {
                    'should_enter': False,
                    'reasons': portfolio_checks['reasons'],
                    'signal': None,
                    'lot_size': 0.0
                }
            
            # Zone Analysis & Smart Entry Recommendation
            zone_recommendation = self._get_zone_smart_entry(signal, candle.close)
                
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
            
            # ใช้ Dynamic Lot Size ตามแรงตลาด Volume และทุน รวม Zone Analysis
            base_lot_size = lot_calculator.calculate_dynamic_lot_size(
                market_strength, volatility, volume_factor, balance_factor
            )
            
            # ปรับ lot size ตาม Zone Recommendation
            zone_multiplier = zone_recommendation.get('lot_multiplier', 1.0) if zone_recommendation else 1.0
            lot_size = base_lot_size * zone_multiplier
            
            logger.info(f"📊 Lot Size Calculation:")
            logger.info(f"   Market Strength: {market_strength:.1f}%")
            logger.info(f"   Volatility: {volatility:.1f}%")
            logger.info(f"   Volume Factor: {volume_factor:.2f}x")
            logger.info(f"   Balance Factor: {balance_factor:.2f}x")
            logger.info(f"   Base Lot Size: {base_lot_size:.3f}")
            if zone_recommendation:
                logger.info(f"   Zone Multiplier: {zone_multiplier:.2f}x ({zone_recommendation.get('reason', 'N/A')})")
            logger.info(f"   Final Lot Size: {lot_size:.3f}")
            
            # ปรับขนาด lot สำหรับสัญลักษณ์ทองคำ
            if 'XAU' in signal.symbol.upper() or 'GOLD' in signal.symbol.upper():
                # ทองคำมีความผันผวนสูง ลดขนาด lot
                lot_size = lot_size * 0.5
            
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
            
    def should_exit_positions(self, current_state: PortfolioState, 
                            current_prices: Dict[str, float]) -> Dict[str, Any]:
        """
        ตัดสินใจว่าควรปิด Position หรือไม่
        
        Args:
            current_state: สถานะพอร์ตปัจจุบัน
            current_prices: ราคาปัจจุบัน
            
        Returns:
            Dict: ผลการตัดสินใจ
        """
        try:
            positions = self.order_manager.active_positions
            if not positions:
                return {'should_exit': False, 'reason': 'ไม่มี Position'}
                
            # ตรวจสอบเงื่อนไขการปิดพื้นฐาน
            exit_conditions = self.trading_conditions.check_exit_conditions(
                positions, current_state.account_balance, current_prices
            )
            
            if exit_conditions['should_exit']:
                return exit_conditions
                
            # ตรวจสอบเงื่อนไขพิเศษของพอร์ต
            portfolio_exit_check = self._check_portfolio_exit_conditions(current_state)
            if portfolio_exit_check['should_exit']:
                return portfolio_exit_check
                
            # ตรวจสอบ Daily Loss Limit
            daily_loss_check = self._check_daily_loss_limit(current_state)
            if daily_loss_check['should_exit']:
                return daily_loss_check
                
            # ตรวจสอบ Maximum Drawdown
            drawdown_check = self._check_maximum_drawdown()
            if drawdown_check['should_exit']:
                return drawdown_check
                
            return {'should_exit': False, 'reason': 'ไม่ถึงเงื่อนไขการปิด'}
            
        except Exception as e:
            logger.error(f"เกิดข้อผิดพลาดในการตัดสินใจปิด Position: {str(e)}")
            return {'should_exit': False, 'reason': f'เกิดข้อผิดพลาด: {str(e)}'}
            
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
        
        # ตรวจสอบการใช้เงินทุน
        if current_state.exposure_percentage >= self.max_portfolio_exposure:
            result['can_enter'] = False
            result['reasons'].append(
                f"การใช้เงินทุนเกิน {self.max_portfolio_exposure}% ({current_state.exposure_percentage:.1f}%)"
            )
            
        # ตรวจสอบสมดุล Buy:Sell (ยืดหยุ่นกว่าเดิม)
        total_positions = current_state.buy_sell_ratio.get('total_positions', 0)
        
        # ถ้ามี position น้อยกว่า 3 ตัว ไม่เช็คสมดุล
        if total_positions < 3:
            logger.info(f"💡 Portfolio มี Position {total_positions} ตัว - ข้ามการเช็คสมดุล")
        else:
            # เช็คสมดุลเมื่อมี position หลายตัว
            if direction == "BUY":
                buy_pct = current_state.buy_sell_ratio['buy_percentage']
                if buy_pct >= self.balance_stop_threshold:
                    result['can_enter'] = False
                    result['reasons'].append(f"Buy positions เกิน {self.balance_stop_threshold}% ({buy_pct:.1f}%)")
            else:  # SELL
                sell_pct = current_state.buy_sell_ratio['sell_percentage']
                if sell_pct >= self.balance_stop_threshold:
                    result['can_enter'] = False
                    result['reasons'].append(f"Sell positions เกิน {self.balance_stop_threshold}% ({sell_pct:.1f}%)")
                
        # ตรวจสอบความเสี่ยงรวม
        if current_state.risk_percentage >= 20.0:  # ความเสี่ยงสูงสุด 20%
            result['can_enter'] = False
            result['reasons'].append(f"ความเสี่ยงรวมเกิน 20% ({current_state.risk_percentage:.1f}%)")
            
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
        ปรับขนาด Lot ตามสถานะพอร์ต
        
        Args:
            base_lot: ขนาด Lot พื้นฐาน
            current_state: สถานะพอร์ตปัจจุบัน
            
        Returns:
            float: ขนาด Lot ที่ปรับแล้ว
        """
        adjusted_lot = base_lot
        
        # ลดขนาดเมื่อมี Position มากเกินไป
        if current_state.total_positions >= 10:
            adjusted_lot *= 0.8
            
        # ลดขนาดเมื่อความเสี่ยงสูง
        if current_state.risk_percentage >= 15.0:
            adjusted_lot *= 0.7
            
        # ลดขนาดเมื่อใช้เงินทุนมาก
        if current_state.exposure_percentage >= 60.0:
            adjusted_lot *= 0.9
            
        # ปรับให้อยู่ในช่วงที่เหมาะสม
        adjusted_lot = max(0.01, min(adjusted_lot, 2.0))
        
        return round(adjusted_lot, 2)
        
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
    
    def check_and_execute_smart_recovery(self, current_price: float, 
                                         block_recovery: bool = False) -> Dict[str, Any]:
        """ตรวจสอบและดำเนินการ Smart Recovery (พร้อม Emergency Override)"""
        try:
            logger.debug(f"🔍 Smart Recovery Check Started - block_recovery: {block_recovery}")
            positions = self.order_manager.active_positions
            logger.debug(f"🔍 Active positions: {len(positions) if positions else 0}")
            # Emergency Override - เฉพาะกรณีที่มั่นใจว่าปิดแล้วพอร์ตดีขึ้น
            positions = self.order_manager.active_positions
            
            # คำนวณกำไรขาดทุนรวม
            profitable_positions = [pos for pos in positions if pos.profit > 0]
            losing_positions = [pos for pos in positions if pos.profit < 0]
            total_profit = sum(pos.profit for pos in profitable_positions)
            total_loss = sum(pos.profit for pos in losing_positions)
            net_profit = total_profit + total_loss
            
            # Emergency Override เฉพาะเมื่อ:
            # 1. มีไม้เยอะมาก (> 8 ไม้) แต่กำไรสุทธิเป็นบวก
            # 2. หรือมีไม้กำไรมากกว่าไม้ขาดทุน และ net profit > $10
            emergency_conditions = []
            
            if len(positions) > 8 and net_profit > 5:
                emergency_conditions.append(f"{len(positions)} positions with net profit ${net_profit:.2f}")
                
            if len(profitable_positions) > len(losing_positions) and net_profit > 10:
                emergency_conditions.append(f"More profitable positions ({len(profitable_positions)} vs {len(losing_positions)}) with net ${net_profit:.2f}")
            
            if emergency_conditions:
                logger.info(f"🚨 Smart Emergency Override: {'; '.join(emergency_conditions)}")
                block_recovery = False
            
            # เช็คว่าถูกบล็อค Recovery หรือไม่ (เช่น ระหว่างรอ Breakout)
            if block_recovery:
                logger.debug(f"🔒 Smart Recovery blocked by Breakout Strategy")
                return {'executed': False, 'reason': 'Recovery ถูกบล็อคชั่วคราว - รอ Breakout Strategy'}
            
            # ดึงข้อมูลปัจจุบัน  
            account_info = self.order_manager.mt5.get_account_info()
            if not account_info:
                return {'executed': False, 'reason': 'ไม่สามารถดึงข้อมูลบัญชีได้'}
                
            current_state = self.analyze_portfolio_state(account_info)
            positions = self.order_manager.active_positions
            
            if not positions or len(positions) < 2:
                logger.debug(f"🔍 Not enough positions for recovery: {len(positions) if positions else 0}")
                return {'executed': False, 'reason': 'ไม่มี positions เพียงพอสำหรับ Recovery'}
            
            # ตรวจสอบว่าควร trigger Recovery หรือไม่
            should_trigger = self.smart_recovery.should_trigger_recovery(
                positions, self.current_balance, current_state.equity
            )
            
            if not should_trigger:
                logger.debug(f"🔍 Recovery conditions not met")
                return {'executed': False, 'reason': 'ยังไม่ถึงเงื่อนไข Recovery'}
            
            # วิเคราะห์โอกาส Recovery
            recovery_candidates = self.smart_recovery.analyze_recovery_opportunities(
                positions, self.current_balance, current_price
            )
            
            if not recovery_candidates:
                logger.debug(f"🔍 No suitable recovery opportunities found")
                return {'executed': False, 'reason': 'ไม่พบโอกาส Recovery ที่เหมาะสม'}
            
            # เลือกและดำเนินการ Recovery ที่ดีที่สุด
            best_candidate = recovery_candidates[0]  # เรียงตาม score แล้ว
            
            # ตรวจสอบ Portfolio Health ก่อนปิด - ต้องมั่นใจว่าปิดแล้วดีขึ้น
            portfolio_health_check = self._validate_portfolio_improvement(best_candidate, current_state)
            if not portfolio_health_check['valid']:
                logger.warning(f"❌ Portfolio Health Check Failed: {portfolio_health_check['reason']}")
                return {'executed': False, 'reason': f"Portfolio Health: {portfolio_health_check['reason']}"}
            
            logger.info(f"🎯 กำลังดำเนินการ Smart Recovery... (Portfolio Health: ✅)")
            
            # ส่ง Portfolio Health Validator ไปให้ Smart Recovery ใช้ร่วมกัน
            recovery_result = self.smart_recovery.execute_recovery(
                best_candidate, 
                portfolio_validator=lambda candidate, state: self._validate_portfolio_improvement(candidate, current_state)
            )
            
            if recovery_result['success']:
                # อัพเดทสถิติ
                if hasattr(self.performance_metrics, 'total_recovery_operations'):
                    self.performance_metrics.total_recovery_operations += 1
                    self.performance_metrics.recovery_profit += recovery_result.get('net_profit', 0)
                
                logger.info(f"✅ Smart Recovery สำเร็จ!")
                logger.info(f"   กำไรสุทธิ: ${recovery_result.get('net_profit', 0):.2f}")
                logger.info(f"   Margin คืน: ${recovery_result.get('margin_freed', 0):.2f}")
                
                return {
                    'executed': True,
                    'success': True,
                    'net_profit': recovery_result.get('net_profit', 0),
                    'margin_freed': recovery_result.get('margin_freed', 0),
                    'closed_tickets': recovery_result.get('closed_tickets', []),
                    'message': recovery_result.get('message', 'Recovery completed')
                }
            else:
                logger.warning(f"⚠️ Smart Recovery ล้มเหลว: {recovery_result.get('message', 'Unknown error')}")
                return {
                    'executed': True,
                    'success': False,
                    'error': recovery_result.get('error', 'Unknown error'),
                    'message': recovery_result.get('message', 'Recovery failed')
                }
                
        except Exception as e:
            logger.error(f"Error in smart recovery: {e}")
            return {'executed': False, 'error': str(e), 'reason': f'เกิดข้อผิดพลาด: {str(e)}'}
    
    def _get_zone_smart_entry(self, signal: Signal, current_price: float) -> Optional[Dict[str, Any]]:
        """ดึงคำแนะนำการเข้าจาก Zone Analysis"""
        try:
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
    
    def check_and_execute_zone_rebalance(self, current_price: float) -> Dict[str, Any]:
        """ตรวจสอบและดำเนินการปรับสมดุลโซน"""
        try:
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
        """ตรวจสอบ Advanced Breakout Recovery Strategy"""
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
        """ตัดสินใจว่าควรบล็อค Traditional Recovery หรือไม่ (ยืดหยุ่นมาก)"""
        try:
            now = datetime.now()
            
            # เช็ค Advanced Recovery groups (ยืดหยุ่นมาก)
            active_groups = len(self.advanced_recovery.active_recoveries)
            
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
            
            # เงื่อนไข 2: กำไรต้องมากกว่า % ของจำนวนไม้
            position_count = len(positions_to_close)
            min_profit_percentage = position_count * 0.5  # 0.5% ต่อไม้
            min_required_profit = current_state.account_balance * (min_profit_percentage / 100)
            
            if total_profit < min_required_profit:
                return {
                    'valid': False, 
                    'reason': f'กำไรไม่ถึงเกณฑ์: ${total_profit:.2f} < ${min_required_profit:.2f} ({min_profit_percentage:.1f}%)'
                }
            
            # เงื่อนไข 3: ต้องมีไม้กำไรและขาดทุนปะปนกัน (ไม่ปิดแค่ฝั่งเดียว)
            if profitable_count == 0:
                return {'valid': False, 'reason': 'ไม่มีไม้กำไรในกลุ่ม'}
            
            if losing_count == 0:
                return {'valid': False, 'reason': 'ไม่มีไม้ขาดทุนในกลุ่ม - ไม่จำเป็นต้อง Recovery'}
            
            # เงื่อนไข 4: สมดุลของไม้ (ไม่เอียงไปฝั่งใดมาก)
            balance_ratio = abs(profitable_count - losing_count) / position_count
            if balance_ratio > 0.7:  # เอียงเกิน 70%
                return {'valid': False, 'reason': f'ไม้ไม่สมดุล: กำไร {profitable_count} vs ขาดทุน {losing_count}'}
            
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
