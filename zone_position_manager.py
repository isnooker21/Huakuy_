# -*- coding: utf-8 -*-
"""
Zone Position Manager - ระบบจัดการ Positions แบบ Zone-Based
แทนที่ Simple Position Manager ด้วยระบบ Zone ที่แม่นยำกว่า

🎯 หลักการ Zone-Based Position Management:
1. แบ่ง Positions เข้า Zones ตามราคา
2. วิเคราะห์ Zone Health และ Inter-Zone Opportunities  
3. ตัดสินใจปิดแบบ Zone-Specific
4. ประสานงาน Cross-Zone Support

✅ แม่นยำกว่า ✅ ประสิทธิภาพดีกว่า ✅ จัดการเฉพาะจุด
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from zone_manager import ZoneManager, Zone, create_zone_manager
from zone_analyzer import ZoneAnalyzer, ZoneAnalysis, create_zone_analyzer  
from zone_coordinator import ZoneCoordinator, SupportPlan, create_zone_coordinator
from calculations import Position

logger = logging.getLogger(__name__)

class ZonePositionManager:
    """🎯 Zone Position Manager - ระบบจัดการ Positions แบบ Zone-Based"""
    
    def __init__(self, mt5_connection, order_manager, zone_size_pips: float = 30.0):
        """
        เริ่มต้น Zone Position Manager
        
        Args:
            mt5_connection: MT5 Connection instance
            order_manager: Order Manager instance
            zone_size_pips: ขนาด Zone ในหน่วย pips
        """
        self.mt5 = mt5_connection
        self.order_manager = order_manager
        
        # Zone System Components
        self.zone_manager = create_zone_manager(zone_size_pips=zone_size_pips, max_zones=15)
        self.zone_analyzer = create_zone_analyzer(self.zone_manager)
        self.zone_coordinator = create_zone_coordinator(self.zone_manager, self.zone_analyzer)
        
        # Configuration
        self.min_profit_threshold = 5.0   # กำไรขั้นต่ำที่ยอมรับ
        self.max_loss_threshold = -200.0  # ขาดทุนสูงสุดต่อ Zone
        self.enable_cross_zone_support = True
        self.enable_auto_recovery = True
        
        # State Tracking
        self.last_analysis_time = None
        self.last_coordination_time = None
        self.active_support_plans = {}
        
        logger.info(f"🎯 Zone Position Manager initialized: {zone_size_pips} pips/zone")
    
    def should_close_positions(self, positions: List[Any], current_price: float, 
                              balance_analysis: Optional[Dict] = None) -> Dict[str, Any]:
        """
        🎯 หลักฟังก์ชัน: ตัดสินใจปิด Positions แบบ Zone-Based
        
        Args:
            positions: รายการ Positions
            current_price: ราคาปัจจุบัน
            balance_analysis: การวิเคราะห์สมดุล (ไม่ใช้ใน Zone system)
            
        Returns:
            Dict: ผลการตัดสินใจ
        """
        try:
            # เช็คเบื้องต้น
            if len(positions) < 2:
                return {
                    'should_close': False,
                    'reason': 'Need at least 2 positions for zone analysis',
                    'positions_to_close': [],
                    'method': 'zone_based'
                }
            
            # อัพเดท Zones จาก Positions
            success = self.zone_manager.update_zones_from_positions(positions, current_price)
            if not success:
                logger.warning("Failed to update zones - falling back to no action")
                return {
                    'should_close': False,
                    'reason': 'Zone update failed',
                    'positions_to_close': [],
                    'method': 'zone_based'
                }
            
            # 1. 🔍 Zone Analysis
            zone_analyses = self.zone_analyzer.analyze_all_zones(current_price)
            
            if not zone_analyses:
                return {
                    'should_close': False,
                    'reason': 'No zones to analyze',
                    'positions_to_close': [],
                    'method': 'zone_based'
                }
            
            # 2. 🎯 Single Zone Closing (Priority 1)
            single_zone_result = self._check_single_zone_closing(zone_analyses, current_price)
            if single_zone_result['should_close']:
                return single_zone_result
            
            # 3. 🤝 Cross-Zone Support (Priority 2)
            if self.enable_cross_zone_support:
                cross_zone_result = self._check_cross_zone_support(zone_analyses, current_price)
                if cross_zone_result['should_close']:
                    return cross_zone_result
            
            # 4. 🚀 Emergency Zone Recovery (Priority 3)
            if self.enable_auto_recovery:
                recovery_result = self._check_emergency_recovery(zone_analyses, current_price)
                if recovery_result['should_close']:
                    return recovery_result
            
            # 5. ไม่มีการปิด - แสดงสถานะ Zones
            self._log_zone_status_summary(zone_analyses)
            
            return {
                'should_close': False,
                'reason': 'No suitable zone-based closing opportunities',
                'positions_to_close': [],
                'method': 'zone_based',
                'zone_summary': self.zone_manager.get_zone_summary()
            }
            
        except Exception as e:
            logger.error(f"❌ Error in zone-based position analysis: {e}")
            return {
                'should_close': False,
                'reason': f'Zone analysis error: {str(e)}',
                'positions_to_close': [],
                'method': 'zone_based'
            }
    
    def _check_single_zone_closing(self, zone_analyses: Dict[int, ZoneAnalysis], 
                                  current_price: float) -> Dict[str, Any]:
        """ตรวจสอบการปิด Zone เดี่ยว"""
        try:
            for zone_id, analysis in zone_analyses.items():
                zone = self.zone_manager.zones[zone_id]
                
                # เงื่อนไข 1: Zone มีกำไรดี และ Health Score สูง
                if (analysis.total_pnl >= self.min_profit_threshold and 
                    analysis.health_score >= 70 and 
                    analysis.risk_level == 'LOW'):
                    
                    zone_range = f"{zone.price_min:.2f}-{zone.price_max:.2f}"
                    logger.info(f"💰 Single Zone Closing: Zone {zone_id} [{zone_range}]")
                    logger.info(f"   Positions: B{zone.buy_count}:S{zone.sell_count} | "
                               f"P&L: ${analysis.total_pnl:.2f} | Health: {analysis.health_score:.0f}")
                    
                    return {
                        'should_close': True,
                        'reason': f'Profitable Zone {zone_id} [{zone_range}]: ${analysis.total_pnl:.2f} profit',
                        'positions_to_close': zone.positions,
                        'positions_count': zone.total_positions,
                        'expected_pnl': analysis.total_pnl,
                        'method': 'single_zone_profit',
                        'zone_id': zone_id,
                        'zone_range': zone_range,
                        'zone_health': analysis.health_score
                    }
                
                # เงื่อนไข 2: Zone เสี่ยงสูง - ปิดเพื่อลดความเสี่ยง
                elif (analysis.risk_level == 'CRITICAL' and 
                      analysis.total_pnl > self.max_loss_threshold and
                      analysis.health_score < 30):
                    
                    zone_range = f"{zone.price_min:.2f}-{zone.price_max:.2f}"
                    logger.info(f"🚨 Critical Zone Closing: Zone {zone_id} [{zone_range}]")
                    logger.info(f"   Positions: B{zone.buy_count}:S{zone.sell_count} | "
                               f"P&L: ${analysis.total_pnl:.2f} | Risk: {analysis.risk_level}")
                    
                    return {
                        'should_close': True,
                        'reason': f'Critical Zone {zone_id} [{zone_range}]: {analysis.risk_level} risk',
                        'positions_to_close': zone.positions,
                        'positions_count': zone.total_positions,
                        'expected_pnl': analysis.total_pnl,
                        'method': 'single_zone_risk',
                        'zone_id': zone_id,
                        'zone_range': zone_range,
                        'risk_level': analysis.risk_level
                    }
            
            return {'should_close': False}
            
        except Exception as e:
            logger.error(f"❌ Error in single zone checking: {e}")
            return {'should_close': False}
    
    def _check_cross_zone_support(self, zone_analyses: Dict[int, ZoneAnalysis], 
                                 current_price: float) -> Dict[str, Any]:
        """ตรวจสอบการช่วยเหลือข้าม Zones"""
        try:
            # หา Support Opportunities
            support_plans = self.zone_coordinator.analyze_support_opportunities(current_price)
            
            if not support_plans:
                return {'should_close': False}
            
            # เลือกแผนที่ดีที่สุด
            best_plan = support_plans[0]  # เรียงตาม confidence แล้ว
            
            if best_plan.confidence >= 0.7 and best_plan.support_ratio >= 1.0:
                
                # เก็บแผนไว้ดำเนินการ
                self.active_support_plans[best_plan.plan_id] = best_plan
                
                # สร้าง positions_to_close จาก helper zones
                positions_to_close = []
                total_expected_pnl = 0.0
                
                for helper_zone_id in best_plan.helper_zones:
                    helper_zone = self.zone_manager.zones[helper_zone_id]
                    
                    # เลือก positions ที่มีกำไรจาก helper zone
                    profitable_positions = [pos for pos in helper_zone.positions if pos.profit > 0]
                    positions_to_close.extend(profitable_positions[:3])  # สูงสุด 3 ไม้ต่อ zone
                    total_expected_pnl += sum(pos.profit for pos in profitable_positions[:3])
                
                if positions_to_close:
                    logger.info(f"🤝 Cross-Zone Support: Plan {best_plan.plan_id}")
                    logger.info(f"   Helpers: {best_plan.helper_zones} → Troubled: {best_plan.troubled_zones}")
                    logger.info(f"   Expected: ${total_expected_pnl:.2f} from {len(positions_to_close)} positions")
                    
                    return {
                        'should_close': True,
                        'reason': f'Cross-zone support: Zones {best_plan.helper_zones} helping {best_plan.troubled_zones}',
                        'positions_to_close': positions_to_close,
                        'positions_count': len(positions_to_close),
                        'expected_pnl': total_expected_pnl,
                        'method': 'cross_zone_support',
                        'support_plan_id': best_plan.plan_id,
                        'helper_zones': best_plan.helper_zones,
                        'troubled_zones': best_plan.troubled_zones,
                        'confidence': best_plan.confidence
                    }
            
            return {'should_close': False}
            
        except Exception as e:
            logger.error(f"❌ Error in cross-zone support checking: {e}")
            return {'should_close': False}
    
    def _check_emergency_recovery(self, zone_analyses: Dict[int, ZoneAnalysis], 
                                 current_price: float) -> Dict[str, Any]:
        """ตรวจสอบการ Recovery ฉุกเฉิน"""
        try:
            # หา Zones ที่ต้องการ Recovery ฉุกเฉิน
            critical_zones = [
                (zone_id, analysis) for zone_id, analysis in zone_analyses.items()
                if analysis.risk_level == 'CRITICAL' and analysis.total_pnl < -100
            ]
            
            if not critical_zones:
                return {'should_close': False}
            
            # เรียงตามความรุนแรง (ขาดทุนมากที่สุดก่อน)
            critical_zones.sort(key=lambda x: x[1].total_pnl)
            
            most_critical_zone_id, most_critical_analysis = critical_zones[0]
            most_critical_zone = self.zone_manager.zones[most_critical_zone_id]
            
            # ตรวจสอบว่ามี Helper Zones หรือไม่
            helper_zones = [
                (zone_id, analysis) for zone_id, analysis in zone_analyses.items()
                if analysis.total_pnl > 50 and analysis.risk_level == 'LOW'
            ]
            
            if helper_zones:
                # มี Helper - ใช้ Cross-Zone Recovery
                total_help_available = sum(analysis.total_pnl * 0.8 for _, analysis in helper_zones)
                help_needed = abs(most_critical_analysis.total_pnl)
                
                if total_help_available >= help_needed * 0.7:  # 70% coverage
                    
                    # สร้าง Recovery Plan
                    positions_to_close = []
                    expected_pnl = 0.0
                    
                    for helper_zone_id, helper_analysis in helper_zones[:2]:  # สูงสุด 2 helpers
                        helper_zone = self.zone_manager.zones[helper_zone_id]
                        profitable_positions = [pos for pos in helper_zone.positions if pos.profit > 0]
                        positions_to_close.extend(profitable_positions[:2])
                        expected_pnl += sum(pos.profit for pos in profitable_positions[:2])
                    
                    if positions_to_close:
                        logger.info(f"🚀 Emergency Recovery: Zone {most_critical_zone_id} "
                                   f"(${most_critical_analysis.total_pnl:.2f} loss)")
                        logger.info(f"   Using ${expected_pnl:.2f} from helper zones for recovery")
                        
                        return {
                            'should_close': True,
                            'reason': f'Emergency recovery for critical Zone {most_critical_zone_id}',
                            'positions_to_close': positions_to_close,
                            'positions_count': len(positions_to_close),
                            'expected_pnl': expected_pnl,
                            'method': 'emergency_recovery',
                            'critical_zone_id': most_critical_zone_id,
                            'critical_zone_loss': most_critical_analysis.total_pnl,
                            'recovery_type': 'cross_zone_support'
                        }
            
            else:
                # ไม่มี Helper - พิจารณาปิด Critical Zone เพื่อลดความเสี่ยง
                if most_critical_analysis.total_pnl > -300:  # ไม่ให้เสียมากเกินไป
                    
                    logger.info(f"⚠️ Emergency Zone Closure: Zone {most_critical_zone_id} "
                               f"(${most_critical_analysis.total_pnl:.2f} loss) - No helpers available")
                    
                    return {
                        'should_close': True,
                        'reason': f'Emergency closure of critical Zone {most_critical_zone_id}',
                        'positions_to_close': most_critical_zone.positions,
                        'positions_count': most_critical_zone.total_positions,
                        'expected_pnl': most_critical_analysis.total_pnl,
                        'method': 'emergency_closure',
                        'critical_zone_id': most_critical_zone_id,
                        'recovery_type': 'damage_control'
                    }
            
            return {'should_close': False}
            
        except Exception as e:
            logger.error(f"❌ Error in emergency recovery checking: {e}")
            return {'should_close': False}
    
    def _log_zone_status_summary(self, zone_analyses: Dict[int, ZoneAnalysis]):
        """แสดงสรุปสถานะ Zones แบบย่อ"""
        try:
            if not zone_analyses:
                return
                
            # สรุปแบบย่อ
            total_zones = len(zone_analyses)
            profitable_zones = sum(1 for a in zone_analyses.values() if a.total_pnl > 0)
            critical_zones = sum(1 for a in zone_analyses.values() if a.risk_level == 'CRITICAL')
            total_pnl = sum(a.total_pnl for a in zone_analyses.values())
            
            logger.info(f"📊 Zones: {total_zones} active, {profitable_zones} profitable, "
                       f"{critical_zones} critical | Total P&L: ${total_pnl:+.2f}")
            
            # แสดงเฉพาะ Zones ที่น่าสนใจ
            interesting_zones = []
            for zone_id, analysis in zone_analyses.items():
                if (analysis.total_pnl > 30 or analysis.total_pnl < -50 or 
                    analysis.risk_level in ['HIGH', 'CRITICAL']):
                    interesting_zones.append((zone_id, analysis))
            
            if interesting_zones:
                for zone_id, analysis in interesting_zones[:3]:  # แสดงสูงสุด 3 zones
                    zone = self.zone_manager.zones[zone_id]
                    status_emoji = {'LOW': '💚', 'MEDIUM': '🟡', 'HIGH': '🔴', 'CRITICAL': '💀'}
                    emoji = status_emoji.get(analysis.risk_level, '⚪')
                    
                    logger.info(f"  Zone {zone_id}: B{zone.buy_count}:S{zone.sell_count} | "
                               f"${analysis.total_pnl:+.2f} | {analysis.risk_level} {emoji}")
                               
        except Exception as e:
            logger.error(f"❌ Error logging zone summary: {e}")
    
    def close_positions(self, positions_to_close: List[Any]) -> Dict[str, Any]:
        """
        🎯 ปิด Positions แบบ Zone-Based (เรียกใช้ Order Manager)
        
        Args:
            positions_to_close: รายการ ZonePosition หรือ Position ที่ต้องปิด
            
        Returns:
            Dict: ผลการปิด
        """
        try:
            if not positions_to_close:
                return {
                    'success': False,
                    'message': 'No positions to close',
                    'closed_count': 0,
                    'total_profit': 0.0
                }
            
            # แปลง ZonePosition เป็น Position objects สำหรับ Order Manager
            position_objects = []
            zone_info = []
            
            for pos in positions_to_close:
                # ถ้าเป็น ZonePosition ให้แปลงเป็น Position
                if hasattr(pos, 'ticket'):  # ZonePosition
                    position_obj = Position(
                        ticket=pos.ticket,
                        symbol=pos.symbol,
                        type=pos.type,
                        volume=pos.volume,
                        price_open=pos.price_open,
                        price_current=pos.price_current,
                        profit=pos.profit,
                        comment=f"Zone-based closing"
                    )
                    position_objects.append(position_obj)
                    
                    # เก็บข้อมูล Zone สำหรับ logging
                    zone_id = self.zone_manager.calculate_zone_id(pos.price_open)
                    zone_info.append(f"Zone {zone_id}")
                    
                else:  # Position object ปกติ
                    position_objects.append(pos)
                    zone_id = self.zone_manager.calculate_zone_id(getattr(pos, 'price_open', 0))
                    zone_info.append(f"Zone {zone_id}")
            
            # สร้างเหตุผลการปิด
            unique_zones = list(set(zone_info))
            if len(unique_zones) == 1:
                reason = f"Zone-based closing: {unique_zones[0]}"
            else:
                reason = f"Multi-zone closing: {', '.join(unique_zones[:3])}"
                if len(unique_zones) > 3:
                    reason += f" (+{len(unique_zones)-3} more)"
            
            # ใช้ Order Manager ปิด Positions
            close_result = self.order_manager.close_positions_group(position_objects, reason)
            
            if close_result.success:
                closed_count = len(close_result.closed_tickets)
                total_profit = close_result.total_profit if hasattr(close_result, 'total_profit') else 0.0
                
                logger.info(f"✅ Zone-based closing: {closed_count}/{len(positions_to_close)} positions closed")
                logger.info(f"💰 Zones affected: {', '.join(unique_zones)} | Profit: ${total_profit:.2f}")
                
                return {
                    'success': True,
                    'message': f'Successfully closed {closed_count} positions from zones',
                    'closed_count': closed_count,
                    'total_profit': total_profit,
                    'zones_affected': unique_zones,
                    'reason': reason
                }
            else:
                logger.warning(f"❌ Zone-based closing failed: {close_result.error_message}")
                return {
                    'success': False,
                    'message': close_result.error_message,
                    'closed_count': 0,
                    'total_profit': 0.0
                }
                
        except Exception as e:
            logger.error(f"❌ Error in zone-based position closing: {e}")
            return {
                'success': False,
                'message': str(e),
                'closed_count': 0,
                'total_profit': 0.0
            }
    
    def get_zone_status(self) -> Dict[str, Any]:
        """ดึงสถานะ Zone System"""
        zone_summary = self.zone_manager.get_zone_summary()
        coordination_summary = self.zone_coordinator.get_coordination_summary()
        
        return {
            'zone_system': zone_summary,
            'coordination': coordination_summary,
            'active_support_plans': len(self.active_support_plans),
            'last_analysis': self.last_analysis_time,
            'system_status': 'ACTIVE' if zone_summary.get('total_zones', 0) > 0 else 'IDLE'
        }


# ==========================================
# 🎯 HELPER FUNCTIONS
# ==========================================

def create_zone_position_manager(mt5_connection, order_manager, zone_size_pips: float = 30.0) -> ZonePositionManager:
    """
    สร้าง Zone Position Manager instance
    
    Args:
        mt5_connection: MT5 Connection instance
        order_manager: Order Manager instance
        zone_size_pips: ขนาด Zone ในหน่วย pips
        
    Returns:
        ZonePositionManager: Zone Position Manager instance
    """
    return ZonePositionManager(mt5_connection, order_manager, zone_size_pips)

if __name__ == "__main__":
    # Demo Zone Position Management
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    logger.info("🎯 Zone Position Manager Demo")
    logger.info("This demo requires MT5 connection and actual position data")
    logger.info("Zone-based system ready for integration!")
