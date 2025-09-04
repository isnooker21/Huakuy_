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
                
            # คำนวณขนาด Lot
            lot_calculator = LotSizeCalculator(current_state.account_balance, self.max_risk_per_trade)
            
            # คำนวณปัจจัยต่างๆ
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
            
            # ใช้ Dynamic Lot Size ตามแรงตลาด Volume และทุน
            lot_size = lot_calculator.calculate_dynamic_lot_size(
                market_strength, volatility, volume_factor, balance_factor
            )
            
            logger.info(f"📊 Lot Size Calculation:")
            logger.info(f"   Market Strength: {market_strength:.1f}%")
            logger.info(f"   Volatility: {volatility:.1f}%")
            logger.info(f"   Volume Factor: {volume_factor:.2f}x")
            logger.info(f"   Balance Factor: {balance_factor:.2f}x")
            logger.info(f"   Final Lot Size: {lot_size:.2f}")
            
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
