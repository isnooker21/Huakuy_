"""
🚀 Recovery Order Manager
========================

ระบบจัดการ Order สำหรับ Universal Recovery System
- สร้าง Recovery Orders พร้อม Enhanced Comments
- ติดตาม Recovery Pairs และ Balance Positions
- Integration กับ OrderManager เดิม

Author: Huakuy Trading System
Version: 1.0.0
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class RecoveryOrderRequest:
    """Recovery Order Request Data Structure"""
    order_type: str  # 'BUY', 'SELL'
    lot_size: float
    price: float
    comment: str
    recovery_type: str  # 'drag_recovery', 'balance_position', 'group_recovery'
    primary_ticket: Optional[int] = None  # สำหรับ Recovery Pairs
    group_id: Optional[str] = None  # สำหรับ Group Recovery
    priority: int = 3  # 1=highest, 5=lowest

class RecoveryOrderManager:
    """
    🎯 Recovery Order Manager
    
    หน้าที่หลัก:
    1. สร้าง Recovery Orders พร้อม Enhanced Comments
    2. ติดตาม Recovery Pairs และ Relationships
    3. Validate Order Parameters
    4. Integration กับ OrderManager เดิม
    """
    
    def __init__(self, mt5_manager, order_manager, recovery_manager):
        self.mt5 = mt5_manager
        self.order_manager = order_manager
        self.recovery_manager = recovery_manager
        
        # 🎯 Configuration
        self.config = {
            'max_comment_length': 31,  # MT5 limit
            'retry_attempts': 3,
            'retry_delay': 1.0,  # seconds
            'validate_before_send': True,
            'log_all_orders': True
        }
        
        # 📊 Statistics
        self.recovery_orders_created = 0
        self.successful_orders = 0
        self.failed_orders = 0
        
        logger.info("🚀 Recovery Order Manager initialized")
    
    def create_recovery_order(self, recovery_request: RecoveryOrderRequest) -> Dict[str, Any]:
        """
        🎯 สร้าง Recovery Order พร้อม Enhanced Comment System
        
        Args:
            recovery_request: RecoveryOrderRequest object
            
        Returns:
            Dict: ผลการสร้าง Order
        """
        
        try:
            # 1. Validate Request
            validation_result = self._validate_recovery_request(recovery_request)
            if not validation_result['valid']:
                return {
                    'success': False,
                    'error': validation_result['error'],
                    'ticket': None
                }
            
            # 2. Generate Enhanced Comment
            enhanced_comment = self._generate_enhanced_comment(recovery_request)
            
            # 3. Prepare Order Parameters
            order_params = self._prepare_order_parameters(recovery_request, enhanced_comment)
            
            # 4. Execute Order via OrderManager
            order_result = self._execute_recovery_order(order_params)
            
            # 5. Update Tracking Data
            if order_result['success']:
                self._update_recovery_tracking(recovery_request, order_result)
                self.successful_orders += 1
                
                logger.info(f"✅ Recovery Order Created: {order_result['ticket']}")
                logger.info(f"💰 Type: {recovery_request.order_type}, Lot: {recovery_request.lot_size}")
                logger.info(f"🏷️ Comment: {enhanced_comment}")
                
            else:
                self.failed_orders += 1
                logger.error(f"❌ Recovery Order Failed: {order_result.get('error', 'Unknown error')}")
            
            self.recovery_orders_created += 1
            
            return order_result
            
        except Exception as e:
            logger.error(f"🚨 Error creating recovery order: {e}")
            self.failed_orders += 1
            return {
                'success': False,
                'error': f"Recovery order creation failed: {str(e)}",
                'ticket': None
            }
    
    def _validate_recovery_request(self, request: RecoveryOrderRequest) -> Dict[str, Any]:
        """Validate Recovery Order Request"""
        
        # Basic validation
        if request.order_type not in ['BUY', 'SELL']:
            return {'valid': False, 'error': f"Invalid order type: {request.order_type}"}
        
        if request.lot_size <= 0:
            return {'valid': False, 'error': f"Invalid lot size: {request.lot_size}"}
        
        if request.price <= 0:
            return {'valid': False, 'error': f"Invalid price: {request.price}"}
        
        # Recovery-specific validation
        if request.recovery_type == 'drag_recovery' and not request.primary_ticket:
            return {'valid': False, 'error': "Drag recovery requires primary_ticket"}
        
        if request.recovery_type == 'group_recovery' and not request.group_id:
            return {'valid': False, 'error': "Group recovery requires group_id"}
        
        # Comment length validation
        test_comment = self._generate_enhanced_comment(request)
        if len(test_comment) > self.config['max_comment_length']:
            return {'valid': False, 'error': f"Comment too long: {len(test_comment)} > {self.config['max_comment_length']}"}
        
        return {'valid': True, 'error': None}
    
    def _generate_enhanced_comment(self, request: RecoveryOrderRequest) -> str:
        """
        🏷️ Generate Enhanced Comment สำหรับ Recovery Orders
        
        Comment Format Examples:
        - "REC_BUY_12345_20250905194500"  (Drag Recovery)
        - "BAL_SELL_20250905194500"       (Balance Position)
        - "GRP_A_20250905194500"          (Group Recovery)
        """
        
        timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
        
        if request.recovery_type == 'drag_recovery':
            # Drag Recovery Comment
            comment = f"REC_{request.order_type}_{request.primary_ticket}_{timestamp}"
            
        elif request.recovery_type == 'balance_position':
            # Balance Position Comment
            comment = f"BAL_{request.order_type}_{timestamp}"
            
        elif request.recovery_type == 'group_recovery':
            # Group Recovery Comment
            comment = f"GRP_{request.group_id}_{timestamp}"
            
        else:
            # Default Recovery Comment
            comment = f"REC_{request.order_type}_{timestamp}"
        
        # Truncate if too long
        if len(comment) > self.config['max_comment_length']:
            comment = comment[:self.config['max_comment_length']]
        
        return comment
    
    def _prepare_order_parameters(self, request: RecoveryOrderRequest, comment: str) -> Dict[str, Any]:
        """เตรียม Parameters สำหรับส่ง Order"""
        
        return {
            'symbol': 'XAUUSD',  # Default symbol
            'order_type': request.order_type,
            'lot_size': request.lot_size,
            'price': request.price,
            'comment': comment,
            'recovery_order': True,  # Flag สำหรับ OrderManager
            'priority': request.priority
        }
    
    def _execute_recovery_order(self, order_params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Recovery Order ผ่าน OrderManager"""
        
        try:
            # ใช้ OrderManager เดิมในการส่ง Order
            if hasattr(self.order_manager, 'send_order'):
                result = self.order_manager.send_order(
                    symbol=order_params['symbol'],
                    order_type=order_params['order_type'],
                    lot_size=order_params['lot_size'],
                    price=order_params.get('price'),
                    comment=order_params['comment']
                )
            else:
                # Fallback: ใช้ method อื่น
                result = self._fallback_order_execution(order_params)
            
            return result
            
        except Exception as e:
            logger.error(f"🚨 Error executing recovery order: {e}")
            return {
                'success': False,
                'error': f"Order execution failed: {str(e)}",
                'ticket': None
            }
    
    def _fallback_order_execution(self, order_params: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback Order Execution"""
        
        # ใช้ MT5 โดยตรงถ้าไม่มี OrderManager method
        try:
            import MetaTrader5 as mt5
            
            order_type = mt5.ORDER_TYPE_BUY if order_params['order_type'] == 'BUY' else mt5.ORDER_TYPE_SELL
            
            request = {
                'action': mt5.TRADE_ACTION_DEAL,
                'symbol': order_params['symbol'],
                'volume': order_params['lot_size'],
                'type': order_type,
                'price': order_params.get('price', 0),
                'comment': order_params['comment'],
                'type_filling': mt5.ORDER_FILLING_IOC,
                'magic': 12345  # Default magic number
            }
            
            result = mt5.order_send(request)
            
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                return {
                    'success': True,
                    'ticket': result.order,
                    'price': result.price,
                    'volume': result.volume
                }
            else:
                return {
                    'success': False,
                    'error': f"MT5 Error: {result.retcode if result else 'No response'}",
                    'ticket': None
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': f"Fallback execution failed: {str(e)}",
                'ticket': None
            }
    
    def _update_recovery_tracking(self, request: RecoveryOrderRequest, order_result: Dict[str, Any]):
        """Update Recovery Tracking Data"""
        
        try:
            ticket = order_result.get('ticket')
            if not ticket:
                return
            
            # Update Recovery Manager tracking
            if request.recovery_type == 'drag_recovery' and request.primary_ticket:
                # สร้าง Recovery Pair
                pair_key = f"{request.primary_ticket}_{ticket}"
                
                from universal_recovery_manager import RecoveryPair
                recovery_pair = RecoveryPair(
                    primary_ticket=request.primary_ticket,
                    recovery_ticket=ticket,
                    pair_type=f"{request.order_type.lower()}_drag",
                    created_time=datetime.now(),
                    target_profit=0.0,  # จะคำนวณภายหลัง
                    status='active'
                )
                
                self.recovery_manager.recovery_pairs[pair_key] = recovery_pair
                logger.info(f"🔗 Recovery Pair Created: {pair_key}")
                
            elif request.recovery_type == 'balance_position':
                # สร้าง Balance Position
                from universal_recovery_manager import BalancePosition
                balance_position = BalancePosition(
                    ticket=ticket,
                    direction=request.order_type,
                    purpose='balance',
                    created_time=datetime.now(),
                    target_balance=0.0  # จะคำนวณภายหลัง
                )
                
                self.recovery_manager.balance_positions[ticket] = balance_position
                logger.info(f"⚖️ Balance Position Created: {ticket}")
                
            elif request.recovery_type == 'group_recovery' and request.group_id:
                # Update Recovery Group
                if request.group_id in self.recovery_manager.recovery_groups:
                    self.recovery_manager.recovery_groups[request.group_id].positions.append(ticket)
                else:
                    from universal_recovery_manager import RecoveryGroup
                    recovery_group = RecoveryGroup(
                        group_id=request.group_id,
                        positions=[ticket],
                        group_type='recovery',
                        target_profit=0.0,
                        created_time=datetime.now(),
                        priority=request.priority
                    )
                    self.recovery_manager.recovery_groups[request.group_id] = recovery_group
                
                logger.info(f"👥 Group Recovery Updated: {request.group_id}")
            
            # Save updated data
            self.recovery_manager.save_data()
            
        except Exception as e:
            logger.error(f"🚨 Error updating recovery tracking: {e}")
    
    def create_drag_recovery_order(self, dragged_position: Any, recovery_plan: Dict) -> Dict[str, Any]:
        """
        🎯 สร้าง Drag Recovery Order (Shortcut Method)
        
        Args:
            dragged_position: Position ที่โดนลาก
            recovery_plan: แผน Recovery จาก UniversalRecoveryManager
            
        Returns:
            Dict: ผลการสร้าง Order
        """
        
        recovery_request = RecoveryOrderRequest(
            order_type=recovery_plan['recovery_type'],
            lot_size=recovery_plan['recovery_lot'],
            price=recovery_plan['recovery_price'],
            comment=recovery_plan['comment'],
            recovery_type='drag_recovery',
            primary_ticket=recovery_plan['dragged_ticket'],
            priority=recovery_plan.get('priority', 3)
        )
        
        return self.create_recovery_order(recovery_request)
    
    def create_balance_position_order(self, direction: str, lot_size: float, price: float) -> Dict[str, Any]:
        """
        ⚖️ สร้าง Balance Position Order (Shortcut Method)
        
        Args:
            direction: 'BUY' หรือ 'SELL'
            lot_size: ขนาด Lot
            price: ราคา
            
        Returns:
            Dict: ผลการสร้าง Order
        """
        
        recovery_request = RecoveryOrderRequest(
            order_type=direction,
            lot_size=lot_size,
            price=price,
            comment=f"BAL_{direction}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            recovery_type='balance_position',
            priority=4
        )
        
        return self.create_recovery_order(recovery_request)
    
    def get_statistics(self) -> Dict[str, Any]:
        """ดูสถิติการทำงาน Recovery Order Manager"""
        
        success_rate = (self.successful_orders / max(self.recovery_orders_created, 1)) * 100
        
        return {
            'recovery_orders_created': self.recovery_orders_created,
            'successful_orders': self.successful_orders,
            'failed_orders': self.failed_orders,
            'success_rate': round(success_rate, 2),
            'config': self.config
        }
    
    def cleanup_old_tracking_data(self, days_old: int = 7):
        """ทำความสะอาดข้อมูล Tracking เก่า"""
        
        if self.recovery_manager:
            self.recovery_manager.cleanup_old_data(days_old)
            logger.info(f"🧹 Cleaned up recovery tracking data older than {days_old} days")


# ==========================================
# 🔧 INTEGRATION HELPER FUNCTIONS
# ==========================================

def create_recovery_order_manager(mt5_manager, order_manager, recovery_manager) -> RecoveryOrderManager:
    """สร้าง Recovery Order Manager instance"""
    return RecoveryOrderManager(mt5_manager, order_manager, recovery_manager)

def integrate_recovery_orders_with_portfolio_manager(portfolio_manager):
    """เชื่อมต่อ Recovery Order Manager กับ Portfolio Manager"""
    
    # สร้าง Recovery Order Manager
    recovery_order_manager = RecoveryOrderManager(
        portfolio_manager.order_manager.mt5,
        portfolio_manager.order_manager,
        portfolio_manager.recovery_manager
    )
    
    # เพิ่มใน Portfolio Manager
    portfolio_manager.recovery_order_manager = recovery_order_manager
    
    logger.info("🔗 Recovery Order Manager integrated with Portfolio Manager")
    
    return recovery_order_manager
