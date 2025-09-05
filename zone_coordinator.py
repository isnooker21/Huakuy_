# -*- coding: utf-8 -*-
"""
Zone Coordinator - ประสานงาน Inter-Zone Support และ Actions
จัดการความร่วมมือระหว่าง Zones เพื่อแก้ปัญหาและเพิ่มประสิทธิภาพ

🎯 หลักการ Inter-Zone Coordination:
1. วิเคราะห์โอกาสความร่วมมือระหว่าง Zones
2. วางแผน Cross-Zone Actions (Support, Balance, Recovery)
3. ดำเนินการ Zone-to-Zone Operations
4. ติดตาม Results และปรับปรุง

✅ ความร่วมมือ ✅ แก้ปัญหาเฉพาะจุด ✅ เพิ่มประสิทธิภาพ
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

from zone_manager import Zone, ZoneManager, ZonePosition
from zone_analyzer import (
    ZoneAnalyzer, ZoneAnalysis, ZoneComparison,
    BalanceRecoveryAnalysis, CrossZoneBalancePlan
)

logger = logging.getLogger(__name__)

@dataclass
class SupportPlan:
    """แผนการช่วยเหลือระหว่าง Zones"""
    plan_id: str
    helper_zones: List[int]
    troubled_zones: List[int]
    
    # Financial Planning
    total_help_available: float
    total_help_needed: float
    support_ratio: float  # available/needed
    
    # Action Plan
    actions: List[Dict[str, Any]]
    execution_order: List[str]
    expected_outcome: Dict[str, float]
    
    # Execution Info
    status: str = 'PLANNED'  # PLANNED, EXECUTING, COMPLETED, FAILED
    created_time: datetime = field(default_factory=datetime.now)
    confidence: float = 0.0

@dataclass
class CrossZoneAction:
    """การกระทำข้าม Zones"""
    action_id: str
    action_type: str  # SUPPORT, BALANCE, CLOSE, RECOVER
    source_zones: List[int]
    target_zones: List[int]
    
    # Position Details
    positions_involved: List[int]  # ticket numbers
    expected_pnl: float
    risk_level: str
    
    # Execution
    priority: str = 'MEDIUM'  # LOW, MEDIUM, HIGH, URGENT
    status: str = 'PENDING'   # PENDING, EXECUTING, COMPLETED, FAILED
    result: Optional[Dict[str, Any]] = None

class ZoneCoordinator:
    """🤝 Zone Coordinator - ประสานงาน Inter-Zone Support และ Actions"""
    
    def __init__(self, zone_manager: ZoneManager, zone_analyzer: ZoneAnalyzer):
        """
        เริ่มต้น Zone Coordinator
        
        Args:
            zone_manager: Zone Manager instance
            zone_analyzer: Zone Analyzer instance
        """
        self.zone_manager = zone_manager
        self.zone_analyzer = zone_analyzer
        
        # Support Planning
        self.active_plans: Dict[str, SupportPlan] = {}
        self.pending_actions: List[CrossZoneAction] = []
        self.completed_actions: List[CrossZoneAction] = []
        
        # Configuration
        self.min_support_ratio = 1.0  # ต้องมีเงินช่วยเหลือเพียงพอ 100%
        self.max_concurrent_plans = 3
        self.max_actions_per_plan = 5
        
        # Distance Penalties (Zone ไกลกัน = ประสิทธิภาพลด)
        self.distance_penalties = {
            0: 1.0,    # Same zone (impossible but just in case)
            1: 1.0,    # Adjacent zones
            2: 0.9,    # 1 zone apart
            3: 0.8,    # 2 zones apart
            4: 0.7,    # 3 zones apart
        }
        
        logger.info("🤝 Zone Coordinator initialized")
    
    def analyze_support_opportunities(self, current_price: float) -> List[SupportPlan]:
        """
        วิเคราะห์โอกาสการช่วยเหลือระหว่าง Zones
        
        Args:
            current_price: ราคาปัจจุบัน
            
        Returns:
            List[SupportPlan]: รายการแผนการช่วยเหลือ
        """
        try:
            # วิเคราะห์ Zones ทั้งหมด
            analyses = self.zone_analyzer.analyze_all_zones(current_price)
            
            if not analyses:
                return []
            
            # หา Helper และ Troubled Zones
            helper_zones = []
            troubled_zones = []
            
            for zone_id, analysis in analyses.items():
                if analysis.total_pnl > 0 and analysis.risk_level in ['LOW', 'MEDIUM']:
                    helper_zones.append((zone_id, analysis))
                elif analysis.total_pnl < 0 or analysis.risk_level in ['HIGH', 'CRITICAL']:
                    troubled_zones.append((zone_id, analysis))
            
            if not helper_zones or not troubled_zones:
                logger.debug("No support opportunities found")
                return []
            
            # สร้างแผนการช่วยเหลือ
            support_plans = []
            
            # Single Helper → Single Troubled
            for helper_id, helper_analysis in helper_zones:
                for troubled_id, troubled_analysis in troubled_zones:
                    plan = self._create_single_support_plan(
                        helper_id, helper_analysis, troubled_id, troubled_analysis, current_price
                    )
                    if plan and plan.support_ratio >= self.min_support_ratio:
                        support_plans.append(plan)
            
            # Multiple Helpers → Single Troubled (สำหรับปัญหาใหญ่)
            for troubled_id, troubled_analysis in troubled_zones:
                if abs(troubled_analysis.total_pnl) > 100:  # ปัญหาใหญ่
                    multi_plan = self._create_multi_helper_plan(
                        helper_zones, troubled_id, troubled_analysis, current_price
                    )
                    if multi_plan and multi_plan.support_ratio >= self.min_support_ratio:
                        support_plans.append(multi_plan)
            
            # เรียงตาม Priority
            support_plans.sort(key=lambda x: (x.confidence, x.support_ratio), reverse=True)
            
            return support_plans[:self.max_concurrent_plans]
            
        except Exception as e:
            logger.error(f"❌ Error analyzing support opportunities: {e}")
            return []
    
    def _create_single_support_plan(self, helper_id: int, helper_analysis: ZoneAnalysis, 
                                   troubled_id: int, troubled_analysis: ZoneAnalysis, 
                                   current_price: float) -> Optional[SupportPlan]:
        """สร้างแผนการช่วยเหลือแบบ 1:1"""
        try:
            # คำนวณระยะห่างระหว่าง Zones
            distance = abs(helper_id - troubled_id)
            efficiency = self.distance_penalties.get(distance, 0.5)
            
            # คำนวณความสามารถในการช่วยเหลือ
            available_help = helper_analysis.total_pnl * 0.8 * efficiency  # เก็บ 20% ไว้
            needed_help = abs(troubled_analysis.total_pnl)
            
            if available_help <= 0 or needed_help <= 0:
                return None
                
            support_ratio = available_help / needed_help
            
            # สร้างแผนการดำเนินงาน
            actions = []
            
            # Action 1: Close profitable positions in helper zone
            helper_zone = self.zone_manager.zones[helper_id]
            profitable_positions = [pos for pos in helper_zone.positions if pos.profit > 0]
            
            if profitable_positions:
                actions.append({
                    'type': 'CLOSE_PROFITABLE',
                    'zone_id': helper_id,
                    'positions': [pos.ticket for pos in profitable_positions[:3]],  # Top 3
                    'expected_profit': sum(pos.profit for pos in profitable_positions[:3])
                })
            
            # Action 2: Use profit to support troubled zone
            troubled_zone = self.zone_manager.zones[troubled_id]
            losing_positions = [pos for pos in troubled_zone.positions if pos.profit < 0]
            
            if losing_positions:
                # เลือกไม้ที่ขาดทุนน้อยที่สุดก่อน (ง่ายกว่า)
                losing_positions.sort(key=lambda x: x.profit, reverse=True)
                
                actions.append({
                    'type': 'SUPPORT_RECOVERY',
                    'zone_id': troubled_id,
                    'positions': [pos.ticket for pos in losing_positions[:2]],  # Top 2
                    'recovery_method': 'CROSS_ZONE_BALANCE'
                })
            
            # คำนวณผลลัพธ์ที่คาดหวัง
            expected_outcome = {
                'total_profit': available_help * 0.7,  # ประมาณ 70% ของความช่วยเหลือ
                'risk_reduction': troubled_analysis.total_pnl * 0.5,
                'zones_improved': 2
            }
            
            plan_id = f"SP_{helper_id}to{troubled_id}_{int(datetime.now().timestamp())}"
            
            plan = SupportPlan(
                plan_id=plan_id,
                helper_zones=[helper_id],
                troubled_zones=[troubled_id],
                total_help_available=available_help,
                total_help_needed=needed_help,
                support_ratio=support_ratio,
                actions=actions,
                execution_order=[action['type'] for action in actions],
                expected_outcome=expected_outcome,
                confidence=min(0.9, efficiency * support_ratio * 0.8)
            )
            
            return plan
            
        except Exception as e:
            logger.error(f"❌ Error creating support plan: {e}")
            return None
    
    def _create_multi_helper_plan(self, helper_zones: List[Tuple[int, ZoneAnalysis]], 
                                 troubled_id: int, troubled_analysis: ZoneAnalysis,
                                 current_price: float) -> Optional[SupportPlan]:
        """สร้างแผนการช่วยเหลือแบบหลาย Helper"""
        try:
            needed_help = abs(troubled_analysis.total_pnl)
            total_available = 0.0
            selected_helpers = []
            
            # เลือก Helpers ที่ดีที่สุด
            helper_candidates = [(hid, ha) for hid, ha in helper_zones if ha.total_pnl > 20]
            helper_candidates.sort(key=lambda x: x[1].total_pnl, reverse=True)
            
            for helper_id, helper_analysis in helper_candidates[:3]:  # สูงสุด 3 helpers
                distance = abs(helper_id - troubled_id)
                efficiency = self.distance_penalties.get(distance, 0.5)
                
                available = helper_analysis.total_pnl * 0.6 * efficiency  # เก็บ 40% ไว้
                
                if available > 10:  # มีประโยชน์
                    selected_helpers.append((helper_id, helper_analysis, available))
                    total_available += available
                    
                    if total_available >= needed_help:
                        break
            
            if not selected_helpers or total_available < needed_help * 0.7:
                return None
                
            support_ratio = total_available / needed_help
            
            # สร้าง Actions
            actions = []
            
            for helper_id, helper_analysis, available in selected_helpers:
                helper_zone = self.zone_manager.zones[helper_id]
                profitable_positions = [pos for pos in helper_zone.positions if pos.profit > 0]
                
                if profitable_positions:
                    actions.append({
                        'type': 'CLOSE_PROFITABLE',
                        'zone_id': helper_id,
                        'positions': [pos.ticket for pos in profitable_positions[:2]],
                        'expected_profit': sum(pos.profit for pos in profitable_positions[:2])
                    })
            
            # Support Action สำหรับ Troubled Zone
            troubled_zone = self.zone_manager.zones[troubled_id]
            losing_positions = [pos for pos in troubled_zone.positions if pos.profit < 0]
            
            if losing_positions:
                actions.append({
                    'type': 'MULTI_ZONE_RECOVERY',
                    'zone_id': troubled_id,
                    'positions': [pos.ticket for pos in losing_positions],
                    'recovery_method': 'COORDINATED_SUPPORT',
                    'helper_zones': [h[0] for h in selected_helpers]
                })
            
            expected_outcome = {
                'total_profit': total_available * 0.6,
                'risk_reduction': troubled_analysis.total_pnl * 0.7,
                'zones_improved': len(selected_helpers) + 1
            }
            
            plan_id = f"MP_{troubled_id}_{int(datetime.now().timestamp())}"
            
            plan = SupportPlan(
                plan_id=plan_id,
                helper_zones=[h[0] for h in selected_helpers],
                troubled_zones=[troubled_id],
                total_help_available=total_available,
                total_help_needed=needed_help,
                support_ratio=support_ratio,
                actions=actions,
                execution_order=[action['type'] for action in actions],
                expected_outcome=expected_outcome,
                confidence=min(0.85, support_ratio * 0.7)
            )
            
            return plan
            
        except Exception as e:
            logger.error(f"❌ Error creating multi-helper plan: {e}")
            return None
    
    def execute_support_plan(self, plan: SupportPlan, current_price: float) -> Dict[str, Any]:
        """
        ดำเนินการตามแผนการช่วยเหลือ
        
        Args:
            plan: แผนการช่วยเหลือ
            current_price: ราคาปัจจุบัน
            
        Returns:
            Dict: ผลการดำเนินงาน
        """
        try:
            logger.info(f"🚀 Executing support plan: {plan.plan_id}")
            
            plan.status = 'EXECUTING'
            results = {
                'plan_id': plan.plan_id,
                'success': False,
                'actions_completed': 0,
                'total_profit': 0.0,
                'errors': []
            }
            
            # ดำเนินการตาม Actions
            for i, action in enumerate(plan.actions):
                try:
                    action_result = self._execute_action(action, current_price)
                    
                    if action_result['success']:
                        results['actions_completed'] += 1
                        results['total_profit'] += action_result.get('profit', 0.0)
                        logger.info(f"✅ Action {i+1}/{len(plan.actions)} completed: {action['type']}")
                    else:
                        results['errors'].append(f"Action {i+1} failed: {action_result.get('error', 'Unknown')}")
                        logger.warning(f"❌ Action {i+1} failed: {action['type']}")
                        
                except Exception as e:
                    error_msg = f"Action {i+1} error: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)
            
            # ประเมินผลรวม
            if results['actions_completed'] >= len(plan.actions) * 0.7:  # 70% success rate
                results['success'] = True
                plan.status = 'COMPLETED'
                logger.info(f"✅ Support plan completed successfully: ${results['total_profit']:.2f} profit")
            else:
                plan.status = 'FAILED'
                logger.warning(f"❌ Support plan failed: {len(results['errors'])} errors")
            
            # เก็บผลลัพธ์
            self.active_plans[plan.plan_id] = plan
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error executing support plan: {e}")
            plan.status = 'FAILED'
            return {
                'plan_id': plan.plan_id,
                'success': False,
                'actions_completed': 0,
                'total_profit': 0.0,
                'errors': [str(e)]
            }
    
    def _execute_action(self, action: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        """
        ดำเนินการ Action เดี่ยว
        
        Args:
            action: Action ที่ต้องการดำเนินการ
            current_price: ราคาปัจจุบัน
            
        Returns:
            Dict: ผลการดำเนินงาน
        """
        try:
            action_type = action['type']
            zone_id = action['zone_id']
            
            if action_type == 'CLOSE_PROFITABLE':
                return self._close_profitable_positions(zone_id, action['positions'], current_price)
                
            elif action_type == 'SUPPORT_RECOVERY':
                return self._create_support_recovery(zone_id, action['positions'], current_price)
                
            elif action_type == 'MULTI_ZONE_RECOVERY':
                return self._create_multi_zone_recovery(action, current_price)
                
            else:
                return {
                    'success': False,
                    'error': f'Unknown action type: {action_type}'
                }
                
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def _close_profitable_positions(self, zone_id: int, position_tickets: List[int], 
                                   current_price: float) -> Dict[str, Any]:
        """ปิด Positions ที่มีกำไรใน Zone"""
        try:
            zone = self.zone_manager.zones.get(zone_id)
            if not zone:
                return {'success': False, 'error': 'Zone not found'}
            
            # หา Positions ที่ต้องปิด
            positions_to_close = []
            total_profit = 0.0
            
            for pos in zone.positions:
                if pos.ticket in position_tickets and pos.profit > 0:
                    positions_to_close.append(pos)
                    total_profit += pos.profit
            
            if not positions_to_close:
                return {'success': False, 'error': 'No profitable positions found'}
            
            # สำหรับ Demo - จำลองการปิด
            logger.info(f"💰 Closing {len(positions_to_close)} profitable positions in Zone {zone_id}")
            
            # ในระบบจริงจะเรียก MT5 API
            # close_result = self.order_manager.close_positions(positions_to_close)
            
            return {
                'success': True,
                'positions_closed': len(positions_to_close),
                'profit': total_profit
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _create_support_recovery(self, zone_id: int, position_tickets: List[int], 
                                current_price: float) -> Dict[str, Any]:
        """สร้าง Recovery Support สำหรับ Zone"""
        try:
            zone = self.zone_manager.zones.get(zone_id)
            if not zone:
                return {'success': False, 'error': 'Zone not found'}
            
            # หา Positions ที่ต้องการ Recovery
            positions_to_recover = []
            for pos in zone.positions:
                if pos.ticket in position_tickets and pos.profit < 0:
                    positions_to_recover.append(pos)
            
            if not positions_to_recover:
                return {'success': False, 'error': 'No positions need recovery'}
            
            # สำหรับ Demo - จำลองการสร้าง Recovery
            logger.info(f"🚀 Creating recovery support for {len(positions_to_recover)} positions in Zone {zone_id}")
            
            # ในระบบจริงจะสร้าง Recovery Orders
            # recovery_result = self.recovery_manager.create_recovery_orders(positions_to_recover)
            
            return {
                'success': True,
                'recovery_orders_created': len(positions_to_recover),
                'expected_recovery': sum(abs(pos.profit) for pos in positions_to_recover) * 0.6
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def _create_multi_zone_recovery(self, action: Dict[str, Any], current_price: float) -> Dict[str, Any]:
        """สร้าง Multi-Zone Recovery"""
        try:
            zone_id = action['zone_id']
            helper_zones = action.get('helper_zones', [])
            
            logger.info(f"🤝 Creating multi-zone recovery: Zone {zone_id} supported by Zones {helper_zones}")
            
            # ในระบบจริงจะประสานงานระหว่าง Zones
            # multi_recovery_result = self.create_coordinated_recovery(zone_id, helper_zones)
            
            return {
                'success': True,
                'coordinated_recovery': True,
                'zones_involved': len(helper_zones) + 1,
                'expected_success_rate': 0.8
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
    
    def get_coordination_summary(self) -> Dict[str, Any]:
        """ดึงสรุปการประสานงาน"""
        active_plans = len(self.active_plans)
        completed_plans = len([p for p in self.active_plans.values() if p.status == 'COMPLETED'])
        failed_plans = len([p for p in self.active_plans.values() if p.status == 'FAILED'])
        
        return {
            'active_plans': active_plans,
            'completed_plans': completed_plans,
            'failed_plans': failed_plans,
            'success_rate': completed_plans / max(1, active_plans),
            'pending_actions': len(self.pending_actions),
            'completed_actions': len(self.completed_actions)
        }
    
    def log_coordination_status(self):
        """แสดงสถานะการประสานงาน"""
        summary = self.get_coordination_summary()
        
        logger.info("🤝 ZONE COORDINATION STATUS")
        logger.info(f"📊 Plans: {summary['active_plans']} active, "
                   f"{summary['completed_plans']} completed, "
                   f"{summary['failed_plans']} failed")
        logger.info(f"📈 Success Rate: {summary['success_rate']:.1%}")
        logger.info(f"⚡ Actions: {summary['pending_actions']} pending, "
                   f"{summary['completed_actions']} completed")
    
    def analyze_balance_recovery_opportunities(self, current_price: float) -> List[CrossZoneBalancePlan]:
        """
        🎯 วิเคราะห์โอกาส Cross-Zone Balance Recovery
        
        Args:
            current_price: ราคาปัจจุบัน
            
        Returns:
            List[CrossZoneBalancePlan]: รายการแผน Balance Recovery
        """
        try:
            # ใช้ Zone Analyzer หา Balance Recovery Opportunities
            balance_analyses = self.zone_analyzer.detect_balance_recovery_opportunities(current_price)
            
            if not balance_analyses:
                logger.debug("No balance recovery opportunities found")
                return []
            
            # สร้างแผน Cross-Zone Balance Recovery
            balance_plans = self.zone_analyzer.find_cross_zone_balance_pairs(balance_analyses)
            
            # เพิ่มข้อมูลการประสานงาน
            for plan in balance_plans:
                plan = self._enhance_balance_plan_with_coordination(plan, current_price)
            
            logger.info(f"🎯 Found {len(balance_plans)} cross-zone balance recovery opportunities")
            return balance_plans
            
        except Exception as e:
            logger.error(f"❌ Error analyzing balance recovery opportunities: {e}")
            return []
    
    def _enhance_balance_plan_with_coordination(self, plan: CrossZoneBalancePlan, current_price: float) -> CrossZoneBalancePlan:
        """
        เพิ่มข้อมูลการประสานงานให้กับ Balance Plan
        
        Args:
            plan: แผน Balance Recovery
            current_price: ราคาปัจจุบัน
            
        Returns:
            CrossZoneBalancePlan: แผนที่ปรับปรุงแล้ว
        """
        try:
            # คำนวณระยะห่างระหว่าง Zones
            distance = abs(plan.primary_zone - plan.partner_zone)
            efficiency = self.distance_penalties.get(distance, 0.5)
            
            # ปรับ Expected Profit ตามประสิทธิภาพ
            plan.expected_profit *= efficiency
            
            # ปรับ Confidence Score
            plan.confidence_score *= efficiency
            
            # ปรับ Priority ตามระยะห่าง
            if distance <= 1 and plan.execution_priority == 'HIGH':
                plan.execution_priority = 'URGENT'
            elif distance >= 3 and plan.execution_priority == 'URGENT':
                plan.execution_priority = 'HIGH'
            
            return plan
            
        except Exception as e:
            logger.error(f"❌ Error enhancing balance plan: {e}")
            return plan
    
    def execute_balance_recovery_plan(self, plan: CrossZoneBalancePlan, current_price: float) -> Dict[str, Any]:
        """
        🚀 ดำเนินการ Cross-Zone Balance Recovery
        
        Args:
            plan: แผน Balance Recovery
            current_price: ราคาปัจจุบัน
            
        Returns:
            Dict: ผลการดำเนินงาน
        """
        try:
            logger.info(f"🚀 Executing Balance Recovery: Zone {plan.primary_zone} ↔ Zone {plan.partner_zone}")
            
            results = {
                'success': False,
                'primary_zone': plan.primary_zone,
                'partner_zone': plan.partner_zone,
                'positions_closed': 0,
                'total_profit': 0.0,
                'balance_improvement': {},
                'errors': []
            }
            
            # ดำเนินการปิดไม้ตามแผน
            for zone_id, position in plan.positions_to_close:
                try:
                    # สำหรับ Demo - จำลองการปิดไม้
                    close_result = self._execute_balance_position_close(zone_id, position, current_price)
                    
                    if close_result['success']:
                        results['positions_closed'] += 1
                        results['total_profit'] += close_result.get('profit', 0.0)
                        logger.info(f"✅ Closed position {position.ticket} in Zone {zone_id}: ${close_result.get('profit', 0):.2f}")
                    else:
                        error_msg = f"Failed to close position {position.ticket} in Zone {zone_id}"
                        results['errors'].append(error_msg)
                        logger.warning(f"❌ {error_msg}")
                        
                except Exception as e:
                    error_msg = f"Error closing position {position.ticket}: {str(e)}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)
            
            # ประเมินผลลัพธ์
            expected_closes = len(plan.positions_to_close)
            success_rate = results['positions_closed'] / max(1, expected_closes)
            
            if success_rate >= 0.7:  # 70% success rate
                results['success'] = True
                results['balance_improvement'] = plan.health_improvement
                
                logger.info(f"✅ Balance Recovery completed successfully!")
                logger.info(f"💰 Total Profit: ${results['total_profit']:.2f}")
                logger.info(f"⚖️ Zones improved: {list(plan.health_improvement.keys())}")
            else:
                logger.warning(f"❌ Balance Recovery partially failed: {len(results['errors'])} errors")
            
            return results
            
        except Exception as e:
            logger.error(f"❌ Error executing balance recovery plan: {e}")
            return {
                'success': False,
                'primary_zone': plan.primary_zone,
                'partner_zone': plan.partner_zone,
                'positions_closed': 0,
                'total_profit': 0.0,
                'balance_improvement': {},
                'errors': [str(e)]
            }
    
    def _execute_balance_position_close(self, zone_id: int, position: Any, current_price: float) -> Dict[str, Any]:
        """
        ปิดไม้สำหรับ Balance Recovery
        
        Args:
            zone_id: Zone ID
            position: Position ที่จะปิด
            current_price: ราคาปัจจุบัน
            
        Returns:
            Dict: ผลการปิดไม้
        """
        try:
            # ในระบบจริงจะเรียก Order Manager
            # close_result = self.order_manager.close_position(position)
            
            # สำหรับ Demo - จำลองการปิด
            profit = getattr(position, 'profit', 0.0)
            
            logger.debug(f"🎯 Closing balance position: Zone {zone_id}, Ticket {position.ticket}, Profit: ${profit:.2f}")
            
            return {
                'success': True,
                'ticket': position.ticket,
                'profit': profit,
                'zone_id': zone_id
            }
            
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'ticket': getattr(position, 'ticket', 'unknown'),
                'zone_id': zone_id
            }
    
    def log_balance_recovery_opportunities(self, current_price: float, detailed: bool = False):
        """
        📊 แสดงโอกาส Balance Recovery ใน Log
        
        Args:
            current_price: ราคาปัจจุบัน
            detailed: แสดงรายละเอียดหรือไม่
        """
        try:
            balance_plans = self.analyze_balance_recovery_opportunities(current_price)
            
            if not balance_plans:
                logger.info("🎯 No balance recovery opportunities found")
                return
            
            logger.info("=" * 60)
            logger.info("🎯 CROSS-ZONE BALANCE RECOVERY OPPORTUNITIES")
            logger.info("=" * 60)
            
            for i, plan in enumerate(balance_plans[:5], 1):  # Top 5
                logger.info(f"{i}. Zone {plan.primary_zone} ↔ Zone {plan.partner_zone}")
                logger.info(f"   💰 Expected Profit: ${plan.expected_profit:.2f}")
                logger.info(f"   ⚖️ Positions to Close: {len(plan.positions_to_close)}")
                logger.info(f"   📈 Priority: {plan.execution_priority}")
                logger.info(f"   🎯 Confidence: {plan.confidence_score:.2f}")
                
                if detailed:
                    logger.info(f"   🔄 Health Improvement:")
                    for zone_id, improvement in plan.health_improvement.items():
                        logger.info(f"      Zone {zone_id}: +{improvement:.1f}")
                
                logger.info("")
            
            # สรุปโอกาส
            total_profit = sum(plan.expected_profit for plan in balance_plans)
            urgent_plans = len([p for p in balance_plans if p.execution_priority == 'URGENT'])
            high_plans = len([p for p in balance_plans if p.execution_priority == 'HIGH'])
            
            logger.info(f"📊 Summary: {len(balance_plans)} opportunities, ${total_profit:.2f} total potential")
            logger.info(f"🚨 Urgent: {urgent_plans}, High Priority: {high_plans}")
            logger.info("=" * 60)
            
        except Exception as e:
            logger.error(f"❌ Error logging balance recovery opportunities: {e}")


# ==========================================
# 🎯 HELPER FUNCTIONS
# ==========================================

def create_zone_coordinator(zone_manager: ZoneManager, zone_analyzer: ZoneAnalyzer) -> ZoneCoordinator:
    """
    สร้าง Zone Coordinator instance
    
    Args:
        zone_manager: Zone Manager instance
        zone_analyzer: Zone Analyzer instance
        
    Returns:
        ZoneCoordinator: Zone Coordinator instance
    """
    return ZoneCoordinator(zone_manager, zone_analyzer)

if __name__ == "__main__":
    # Demo Zone Coordination
    from zone_manager import create_zone_manager
    from zone_analyzer import create_zone_analyzer
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    logger.info("🤝 Zone Coordinator Demo")
    
    # สร้าง Components
    zm = create_zone_manager()
    za = create_zone_analyzer(zm)
    zc = create_zone_coordinator(zm, za)
    
    # Demo จะต้องมีข้อมูล Zones ก่อน
    logger.info("Demo requires zone data - please run with actual position data")
