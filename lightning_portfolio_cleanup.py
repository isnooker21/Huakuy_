# -*- coding: utf-8 -*-
"""
Lightning Portfolio Cleanup System
ระบบปิดไม้แบบฟ้าผ่า - เร็ว ปลอดภัย ลดไม้ค้าง

🎯 เป้าหมาย:
- ปิดเร็ว: 30 วินาที - 2 นาที
- ไม่ติดลบเด็ดขาด: ทุกการปิดต้องเป็นบวก
- ลดไม้ค้าง: ทุกครั้งที่ปิดเอาไม้เสียออกด้วย
- กำไรขั้นต่ำ: คำนวณจาก % ตาม lot size
- พอร์ตดีขึ้น: ลดยอดติดลบสะสม
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class CleanupPriority(Enum):
    """ลำดับความสำคัญในการปิดไม้"""
    LIGHTNING = "lightning"    # ปิดทันที (30 วินาที)
    SMART = "smart"           # ปิดเร็ว (30วิ - 2นาที)
    MAXIMUM = "maximum"       # ปิดช้า (2+ นาที) - สำหรับกำไรสูง

@dataclass
class CleanupGroup:
    """กลุ่มไม้สำหรับปิด"""
    profit_positions: List[Any]
    loss_positions: List[Any]
    total_pnl: float
    total_lots: float
    total_positions: int
    priority: CleanupPriority
    cleanup_score: float
    estimated_execution_time: float  # วินาที

class LightningPortfolioCleanup:
    """ระบบปิดไม้แบบฟ้าผ่า"""
    
    def __init__(self, mt5_connection, order_manager):
        self.mt5 = mt5_connection
        self.order_manager = order_manager
        
        # 🎯 Core Settings - ปรับได้ตามต้องการ
        self.min_profit_percentage = 0.5  # กำไรขั้นต่ำ 0.5% ของ lot value
        self.max_loss_ratio = 0.4          # ไม้เสียไม่เกิน 40% ของกำไร
        self.max_positions_per_round = 8   # ปิดสูงสุด 8 ไม้ต่อรอบ
        
        # ⚡ Lightning Level Settings (30 วินาที)
        self.lightning_min_profit_per_lot = 0.20    # $0.20 ต่อ 0.01 lot
        self.lightning_max_positions = 5            # สูงสุด 5 ไม้
        
        # 💰 Smart Level Settings (30วิ - 2นาที)  
        self.smart_min_profit_per_lot = 0.50        # $0.50 ต่อ 0.01 lot
        self.smart_max_positions = 8                # สูงสุด 8 ไม้
        
        # 🎯 Maximum Level Settings (2+ นาที)
        self.maximum_min_profit_per_lot = 1.00      # $1.00 ต่อ 0.01 lot
        self.maximum_max_positions = 12             # สูงสุด 12 ไม้
        
        # 📊 Performance Tracking
        self.cleanup_history = []
        self.total_cleanups = 0
        self.successful_cleanups = 0
        self.total_positions_cleaned = 0
        self.total_profit_realized = 0.0
        
    def should_execute_cleanup(self, positions: List[Any], current_price: float, 
                              account_balance: float) -> Dict[str, Any]:
        """
        🔍 ตรวจสอบว่าควรปิดไม้หรือไม่
        
        Returns:
            Dict: ผลการตรวจสอบพร้อมกลุ่มที่เหมาะสม
        """
        try:
            if not positions:
                return {
                    'should_execute': False,
                    'reason': 'No positions to clean up',
                    'cleanup_groups': [],
                    'priority': None
                }
            
            # 1. 🔍 ประเมินคุณภาพพอร์ต
            portfolio_quality = self._assess_portfolio_quality(positions, current_price)
            
            # 2. 🎯 หากลุ่มที่เหมาะสมทั้ง 3 ระดับ
            cleanup_groups = self._find_optimal_cleanup_groups(positions, current_price, account_balance)
            
            if not cleanup_groups:
                return {
                    'should_execute': False,
                    'reason': 'No suitable cleanup groups found',
                    'portfolio_quality': portfolio_quality,
                    'cleanup_groups': [],
                    'priority': None
                }
            
            # 3. ⚡ เลือกกลุ่มที่ดีที่สุด (ลำดับความสำคัญ)
            best_group = self._select_best_cleanup_group(cleanup_groups)
            
            return {
                'should_execute': True,
                'reason': f'{best_group.priority.value.upper()} cleanup ready',
                'portfolio_quality': portfolio_quality,
                'best_group': best_group,
                'cleanup_groups': cleanup_groups,
                'priority': best_group.priority
            }
            
        except Exception as e:
            logger.error(f"Error checking cleanup conditions: {e}")
            return {
                'should_execute': False,
                'reason': f'Error: {e}',
                'cleanup_groups': [],
                'priority': None
            }
    
    def execute_lightning_cleanup(self, cleanup_group: CleanupGroup) -> Dict[str, Any]:
        """
        ⚡ ดำเนินการปิดไม้แบบฟ้าผ่า
        
        Args:
            cleanup_group: กลุ่มไม้ที่จะปิด
            
        Returns:
            Dict: ผลการปิดไม้
        """
        try:
            start_time = datetime.now()
            
            # 1. 🛡️ Final Safety Check - ป้องกันการติดลบ
            safety_check = self._final_safety_check(cleanup_group)
            if not safety_check['safe']:
                return {
                    'success': False,
                    'message': f'Safety check failed: {safety_check["reason"]}',
                    'positions_closed': 0,
                    'profit_realized': 0.0
                }
            
            # 2. 📝 เตรียมรายการไม้ที่จะปิด
            positions_to_close = cleanup_group.profit_positions + cleanup_group.loss_positions
            
            # 3. 🔥 ปิดไม้ทั้งหมดในกลุ่ม
            close_results = []
            successful_closes = 0
            total_profit = 0.0
            
            for position in positions_to_close:
                try:
                    close_result = self.order_manager.close_position(position.ticket)
                    close_results.append(close_result)
                    
                    if close_result.success:
                        successful_closes += 1
                        total_profit += close_result.profit if hasattr(close_result, 'profit') else 0.0
                        logger.info(f"⚡ Closed position #{position.ticket}: ${close_result.profit:.2f}")
                    else:
                        logger.warning(f"❌ Failed to close position #{position.ticket}: {close_result.error_message}")
                        
                except Exception as e:
                    logger.error(f"Error closing position #{position.ticket}: {e}")
            
            # 4. 📊 บันทึกผลลัพธ์
            execution_time = (datetime.now() - start_time).total_seconds()
            
            self._record_cleanup_history(cleanup_group, {
                'successful_closes': successful_closes,
                'total_closes_attempted': len(positions_to_close),
                'total_profit': total_profit,
                'execution_time': execution_time
            })
            
            # 5. 🎉 สรุปผลลัพธ์
            if successful_closes > 0:
                self.successful_cleanups += 1
                self.total_positions_cleaned += successful_closes
                self.total_profit_realized += total_profit
                
                return {
                    'success': True,
                    'message': f'Lightning cleanup success: {successful_closes}/{len(positions_to_close)} positions closed',
                    'positions_closed': successful_closes,
                    'profit_realized': total_profit,
                    'execution_time': execution_time,
                    'priority': cleanup_group.priority.value
                }
            else:
                return {
                    'success': False,
                    'message': 'No positions were successfully closed',
                    'positions_closed': 0,
                    'profit_realized': 0.0,
                    'execution_time': execution_time
                }
                
        except Exception as e:
            logger.error(f"Error executing lightning cleanup: {e}")
            return {
                'success': False,
                'message': f'Execution error: {e}',
                'positions_closed': 0,
                'profit_realized': 0.0
            }
    
    def _assess_portfolio_quality(self, positions: List[Any], current_price: float) -> Dict[str, Any]:
        """🔍 ประเมินคุณภาพพอร์ต"""
        try:
            if not positions:
                return {
                    'total_positions': 0,
                    'profitable_positions': 0,
                    'losing_positions': 0,
                    'profit_ratio': 1.0,
                    'quality_score': 100.0,
                    'total_unrealized_pnl': 0.0
                }
            
            profitable_positions = 0
            losing_positions = 0
            total_unrealized_pnl = 0.0
            
            for pos in positions:
                # คำนวณ P&L โดยประมาณ
                if hasattr(pos, 'type') and hasattr(pos, 'price_open') and hasattr(pos, 'volume'):
                    pos_type = pos.type.upper() if isinstance(pos.type, str) else ("BUY" if pos.type == 0 else "SELL")
                    
                    if pos_type == "BUY":
                        pnl = (current_price - pos.price_open) * pos.volume * 100
                    else:  # SELL
                        pnl = (pos.price_open - current_price) * pos.volume * 100
                    
                    total_unrealized_pnl += pnl
                    
                    if pnl > 0:
                        profitable_positions += 1
                    else:
                        losing_positions += 1
            
            total_positions = len(positions)
            profit_ratio = profitable_positions / total_positions if total_positions > 0 else 0
            quality_score = profit_ratio * 100
            
            return {
                'total_positions': total_positions,
                'profitable_positions': profitable_positions,
                'losing_positions': losing_positions,
                'profit_ratio': profit_ratio,
                'quality_score': quality_score,
                'total_unrealized_pnl': total_unrealized_pnl
            }
            
        except Exception as e:
            logger.error(f"Error assessing portfolio quality: {e}")
            return {
                'total_positions': len(positions) if positions else 0,
                'quality_score': 0.0,
                'total_unrealized_pnl': 0.0
            }
    
    def _find_optimal_cleanup_groups(self, positions: List[Any], current_price: float, 
                                   account_balance: float) -> List[CleanupGroup]:
        """🎯 หากลุ่มที่เหมาะสมสำหรับปิด"""
        try:
            cleanup_groups = []
            
            # แยกไม้กำไรและไม้เสีย
            profitable_positions = []
            losing_positions = []
            
            for pos in positions:
                if hasattr(pos, 'type') and hasattr(pos, 'price_open') and hasattr(pos, 'volume'):
                    pos_type = pos.type.upper() if isinstance(pos.type, str) else ("BUY" if pos.type == 0 else "SELL")
                    
                    if pos_type == "BUY":
                        pnl = (current_price - pos.price_open) * pos.volume * 100
                    else:  # SELL
                        pnl = (pos.price_open - current_price) * pos.volume * 100
                    
                    # เพิ่ม pnl attribute เพื่อใช้ในการคำนวณ
                    pos.calculated_pnl = pnl
                    
                    if pnl > 0:
                        profitable_positions.append(pos)
                    else:
                        losing_positions.append(pos)
            
            if not profitable_positions:
                return []
            
            # เรียงลำดับ
            profitable_positions.sort(key=lambda x: x.calculated_pnl, reverse=True)  # กำไรมาก -> น้อย
            losing_positions.sort(key=lambda x: abs(x.calculated_pnl))  # เสียน้อย -> มาก
            
            # สร้างกลุ่มทั้ง 3 ระดับ
            cleanup_groups.extend(self._create_lightning_groups(profitable_positions, losing_positions))
            cleanup_groups.extend(self._create_smart_groups(profitable_positions, losing_positions))
            cleanup_groups.extend(self._create_maximum_groups(profitable_positions, losing_positions))
            
            # กรองเฉพาะกลุ่มที่ผ่านเงื่อนไข
            valid_groups = []
            for group in cleanup_groups:
                if self._validate_cleanup_group(group):
                    valid_groups.append(group)
            
            # เรียงตามลำดับความสำคัญและคะแนน
            valid_groups.sort(key=lambda x: (x.priority.value, -x.cleanup_score))
            
            return valid_groups
            
        except Exception as e:
            logger.error(f"Error finding optimal cleanup groups: {e}")
            return []
    
    def _create_lightning_groups(self, profitable_positions: List[Any], 
                               losing_positions: List[Any]) -> List[CleanupGroup]:
        """⚡ สร้างกลุ่ม Lightning (ปิดทันที)"""
        groups = []
        
        try:
            for profit_pos in profitable_positions[:3]:  # เลือกไม้กำไรสูงสุด 3 ไม้
                if profit_pos.calculated_pnl < self.lightning_min_profit_per_lot * (profit_pos.volume / 0.01):
                    continue
                
                # หาไม้เสียที่เหมาะสม
                suitable_losses = []
                remaining_profit = profit_pos.calculated_pnl * self.max_loss_ratio
                
                for loss_pos in losing_positions:
                    if len(suitable_losses) >= 3:  # สูงสุด 3 ไม้เสีย
                        break
                    if abs(loss_pos.calculated_pnl) <= remaining_profit:
                        suitable_losses.append(loss_pos)
                        remaining_profit -= abs(loss_pos.calculated_pnl)
                
                if suitable_losses:
                    total_pnl = profit_pos.calculated_pnl + sum(pos.calculated_pnl for pos in suitable_losses)
                    total_lots = profit_pos.volume + sum(pos.volume for pos in suitable_losses)
                    
                    if total_pnl > 0:  # ต้องเป็นบวก
                        group = CleanupGroup(
                            profit_positions=[profit_pos],
                            loss_positions=suitable_losses,
                            total_pnl=total_pnl,
                            total_lots=total_lots,
                            total_positions=1 + len(suitable_losses),
                            priority=CleanupPriority.LIGHTNING,
                            cleanup_score=self._calculate_cleanup_score(total_pnl, total_lots, 1 + len(suitable_losses)),
                            estimated_execution_time=30.0
                        )
                        groups.append(group)
            
        except Exception as e:
            logger.error(f"Error creating lightning groups: {e}")
        
        return groups
    
    def _create_smart_groups(self, profitable_positions: List[Any], 
                           losing_positions: List[Any]) -> List[CleanupGroup]:
        """💰 สร้างกลุ่ม Smart (30วิ - 2นาที)"""
        groups = []
        
        try:
            for profit_pos in profitable_positions[:5]:  # เลือกไม้กำไรสูงสุด 5 ไม้
                if profit_pos.calculated_pnl < self.smart_min_profit_per_lot * (profit_pos.volume / 0.01):
                    continue
                
                # หาไม้เสียที่เหมาะสม
                suitable_losses = []
                remaining_profit = profit_pos.calculated_pnl * self.max_loss_ratio
                
                for loss_pos in losing_positions:
                    if len(suitable_losses) >= 5:  # สูงสุด 5 ไม้เสีย
                        break
                    if abs(loss_pos.calculated_pnl) <= remaining_profit:
                        suitable_losses.append(loss_pos)
                        remaining_profit -= abs(loss_pos.calculated_pnl)
                
                if suitable_losses:
                    total_pnl = profit_pos.calculated_pnl + sum(pos.calculated_pnl for pos in suitable_losses)
                    total_lots = profit_pos.volume + sum(pos.volume for pos in suitable_losses)
                    
                    if total_pnl > 0:  # ต้องเป็นบวก
                        group = CleanupGroup(
                            profit_positions=[profit_pos],
                            loss_positions=suitable_losses,
                            total_pnl=total_pnl,
                            total_lots=total_lots,
                            total_positions=1 + len(suitable_losses),
                            priority=CleanupPriority.SMART,
                            cleanup_score=self._calculate_cleanup_score(total_pnl, total_lots, 1 + len(suitable_losses)),
                            estimated_execution_time=90.0
                        )
                        groups.append(group)
            
        except Exception as e:
            logger.error(f"Error creating smart groups: {e}")
        
        return groups
    
    def _create_maximum_groups(self, profitable_positions: List[Any], 
                             losing_positions: List[Any]) -> List[CleanupGroup]:
        """🎯 สร้างกลุ่ม Maximum (2+ นาที)"""
        groups = []
        
        try:
            # รวมไม้กำไรหลายไม้เพื่อปิดไม้เสียมากขึ้น
            for i in range(min(3, len(profitable_positions))):
                profit_group = profitable_positions[i:i+2]  # เลือก 1-2 ไม้กำไร
                total_profit = sum(pos.calculated_pnl for pos in profit_group)
                
                if total_profit < self.maximum_min_profit_per_lot * sum(pos.volume / 0.01 for pos in profit_group):
                    continue
                
                # หาไม้เสียที่เหมาะสม
                suitable_losses = []
                remaining_profit = total_profit * self.max_loss_ratio
                
                for loss_pos in losing_positions:
                    if len(suitable_losses) >= 8:  # สูงสุด 8 ไม้เสีย
                        break
                    if abs(loss_pos.calculated_pnl) <= remaining_profit:
                        suitable_losses.append(loss_pos)
                        remaining_profit -= abs(loss_pos.calculated_pnl)
                
                if suitable_losses:
                    total_pnl = total_profit + sum(pos.calculated_pnl for pos in suitable_losses)
                    total_lots = sum(pos.volume for pos in profit_group) + sum(pos.volume for pos in suitable_losses)
                    
                    if total_pnl > 0:  # ต้องเป็นบวก
                        group = CleanupGroup(
                            profit_positions=profit_group,
                            loss_positions=suitable_losses,
                            total_pnl=total_pnl,
                            total_lots=total_lots,
                            total_positions=len(profit_group) + len(suitable_losses),
                            priority=CleanupPriority.MAXIMUM,
                            cleanup_score=self._calculate_cleanup_score(total_pnl, total_lots, len(profit_group) + len(suitable_losses)),
                            estimated_execution_time=180.0
                        )
                        groups.append(group)
            
        except Exception as e:
            logger.error(f"Error creating maximum groups: {e}")
        
        return groups
    
    def _calculate_cleanup_score(self, total_pnl: float, total_lots: float, total_positions: int) -> float:
        """📊 คำนวณคะแนนของกลุ่ม"""
        try:
            # คะแนนพื้นฐานจากกำไร
            profit_score = min(total_pnl * 10, 100)  # สูงสุด 100
            
            # คะแนนจากการลดจำนวนไม้
            position_reduction_score = min(total_positions * 5, 50)  # สูงสุด 50
            
            # คะแนนจาก lot size
            lot_score = min(total_lots * 100, 30)  # สูงสุด 30
            
            total_score = profit_score + position_reduction_score + lot_score
            return min(total_score, 180)  # สูงสุด 180
            
        except Exception as e:
            logger.error(f"Error calculating cleanup score: {e}")
            return 0.0
    
    def _validate_cleanup_group(self, group: CleanupGroup) -> bool:
        """🛡️ ตรวจสอบความถูกต้องของกลุ่ม"""
        try:
            # 1. ต้องมีกำไรเป็นบวก
            if group.total_pnl <= 0:
                return False
            
            # 2. ต้องมีไม้เสียด้วย (เพื่อลดจำนวนไม้)
            if not group.loss_positions:
                return False
            
            # 3. จำนวนไม้ไม่เกินขีดจำกัด
            if group.total_positions > self.max_positions_per_round:
                return False
            
            # 4. กำไรต้องมากกว่าขั้นต่ำ
            min_profit_required = group.total_lots * 100 * (self.min_profit_percentage / 100)
            if group.total_pnl < min_profit_required:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating cleanup group: {e}")
            return False
    
    def _select_best_cleanup_group(self, cleanup_groups: List[CleanupGroup]) -> Optional[CleanupGroup]:
        """🎯 เลือกกลุ่มที่ดีที่สุด"""
        try:
            if not cleanup_groups:
                return None
            
            # เรียงตามลำดับความสำคัญ: Lightning > Smart > Maximum
            # และคะแนนสูงสุดในแต่ละระดับ
            priority_order = {
                CleanupPriority.LIGHTNING: 1,
                CleanupPriority.SMART: 2,
                CleanupPriority.MAXIMUM: 3
            }
            
            cleanup_groups.sort(key=lambda x: (priority_order[x.priority], -x.cleanup_score))
            return cleanup_groups[0]
            
        except Exception as e:
            logger.error(f"Error selecting best cleanup group: {e}")
            return None
    
    def _final_safety_check(self, cleanup_group: CleanupGroup) -> Dict[str, Any]:
        """🛡️ ตรวจสอบความปลอดภัยครั้งสุดท้าย"""
        try:
            # คำนวณ P&L จริงอีกครั้ง
            total_pnl = 0.0
            for pos in cleanup_group.profit_positions + cleanup_group.loss_positions:
                if hasattr(pos, 'calculated_pnl'):
                    total_pnl += pos.calculated_pnl
            
            if total_pnl <= 0:
                return {
                    'safe': False,
                    'reason': f'Final P&L check failed: ${total_pnl:.2f} (would lose money)'
                }
            
            return {
                'safe': True,
                'reason': f'Final safety check passed: ${total_pnl:.2f} profit expected'
            }
            
        except Exception as e:
            return {
                'safe': False,
                'reason': f'Safety check error: {e}'
            }
    
    def _record_cleanup_history(self, cleanup_group: CleanupGroup, execution_result: Dict):
        """📝 บันทึกประวัติการทำงาน"""
        try:
            history_entry = {
                'timestamp': datetime.now(),
                'priority': cleanup_group.priority.value,
                'total_positions': cleanup_group.total_positions,
                'total_lots': cleanup_group.total_lots,
                'expected_pnl': cleanup_group.total_pnl,
                'actual_profit': execution_result.get('total_profit', 0.0),
                'successful_closes': execution_result.get('successful_closes', 0),
                'execution_time': execution_result.get('execution_time', 0.0)
            }
            
            self.cleanup_history.append(history_entry)
            self.total_cleanups += 1
            
            # เก็บประวัติแค่ 100 รายการล่าสุด
            if len(self.cleanup_history) > 100:
                self.cleanup_history = self.cleanup_history[-100:]
                
        except Exception as e:
            logger.error(f"Error recording cleanup history: {e}")
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """📊 ดึงข้อมูลประสิทธิภาพ"""
        try:
            if self.total_cleanups == 0:
                return {
                    'total_cleanups': 0,
                    'success_rate': 0.0,
                    'avg_positions_per_cleanup': 0.0,
                    'total_profit_realized': 0.0,
                    'avg_execution_time': 0.0
                }
            
            success_rate = (self.successful_cleanups / self.total_cleanups) * 100
            avg_positions = self.total_positions_cleaned / self.successful_cleanups if self.successful_cleanups > 0 else 0
            
            recent_executions = [h for h in self.cleanup_history if h['execution_time'] > 0]
            avg_execution_time = sum(h['execution_time'] for h in recent_executions) / len(recent_executions) if recent_executions else 0
            
            return {
                'total_cleanups': self.total_cleanups,
                'successful_cleanups': self.successful_cleanups,
                'success_rate': success_rate,
                'total_positions_cleaned': self.total_positions_cleaned,
                'avg_positions_per_cleanup': avg_positions,
                'total_profit_realized': self.total_profit_realized,
                'avg_execution_time': avg_execution_time,
                'recent_cleanup_count': len([h for h in self.cleanup_history if (datetime.now() - h['timestamp']).total_seconds() < 3600])
            }
            
        except Exception as e:
            logger.error(f"Error getting performance metrics: {e}")
            return {}
    
    def configure_settings(self, **settings):
        """⚙️ ปรับแต่งการตั้งค่า"""
        try:
            if 'min_profit_percentage' in settings:
                self.min_profit_percentage = settings['min_profit_percentage']
            if 'max_loss_ratio' in settings:
                self.max_loss_ratio = settings['max_loss_ratio']
            if 'lightning_min_profit_per_lot' in settings:
                self.lightning_min_profit_per_lot = settings['lightning_min_profit_per_lot']
            if 'smart_min_profit_per_lot' in settings:
                self.smart_min_profit_per_lot = settings['smart_min_profit_per_lot']
                
            logger.info("⚙️ Lightning Portfolio Cleanup settings updated")
            
        except Exception as e:
            logger.error(f"Error configuring settings: {e}")
