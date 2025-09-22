# -*- coding: utf-8 -*-
"""
Group Closing Manager
ระบบปิดออเดอร์แบบกลุ่ม (Group Closing) ที่รับสถานะไม้จาก Order Tracking System
และสามารถรวมกลุ่ม Protected + HG + Profit Helper เพื่อปิดพร้อมกัน
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class ClosingGroup:
    """ข้อมูลกลุ่มที่พร้อมปิด"""
    group_id: str
    group_type: str
    positions: List[Any]
    total_profit: float
    min_profit_required: float
    can_close: bool
    reason: str
    protected_positions: List[Any] = None
    hg_positions: List[Any] = None
    helper_positions: List[Any] = None
    created_time: float = None

@dataclass
class ProfitHelperSelection:
    """ข้อมูลการเลือก Profit Helper"""
    selected_helpers: List[Any]
    total_helper_profit: float
    distance_from_price: List[float]
    selection_reason: str

class GroupClosingManager:
    """ระบบจัดการปิดออเดอร์แบบกลุ่ม"""
    
    def __init__(self, order_manager=None, mt5_connection=None):
        """
        Args:
            order_manager: OrderManager instance
            mt5_connection: MT5Connection instance
        """
        self.order_manager = order_manager
        self.mt5_connection = mt5_connection
        
        # 🎯 Enhanced Dynamic Minimum Profit Configuration - เครียไม้ได้ไวไม่ปิดติดลบ
        self.min_profit_config = {
            'base_amount': 0.5,      # ลดกำไรขั้นต่ำจาก $2.0 เป็น $0.5
            'multiplier': 0.8,       # ลดคูณจาก 1.5 เป็น 0.8
            'max_amount': 10.0,      # ลดกำไรสูงสุดจาก $20.0 เป็น $10.0
            'group_type_multipliers': {
                'PERFECT_BALANCE': 0.5,      # 1:1 ratio - ปิดเร็ว
                'NEAR_BALANCE': 0.7,         # 2:1, 1:2 ratio
                'DISTANCE_PRIORITY': 0.3,    # ไม้ไกลจากราคาปัจจุบัน
                'RESCUE_PAIRING': 0.8,       # ช่วยไม้ขาดทุน
                'EMERGENCY_PAIRING': 1.0,    # ฉุกเฉิน
                'FLEXIBLE_PAIRING': 1.2,     # ยืดหยุ่นสูงสุด
                'PROTECTED_HG': 0.6,
                'PROTECTED_HG_HELPER': 0.8,
                'MULTI_GROUP': 1.0
            }
        }
        
        # 📊 Enhanced Group Formation Settings - จับคู่ได้หลากหลายไม่จำกัด
        self.group_settings = {
            'max_group_size': 15,        # เพิ่มจาก 10 เป็น 15 ไม้
            'min_profit_margin': 0.05,   # ลดจาก 10% เป็น 5%
            'max_loss_tolerance': -8.0,  # เพิ่มจาก -5.0 เป็น -8.0
            'helper_selection_radius': 80.0,  # เพิ่มจาก 50.0 เป็น 80.0
            'enable_flexible_pairing': True,   # เปิดการจับคู่ยืดหยุ่น
            'enable_distance_priority': True,  # เปิดการจับคู่ตามระยะห่าง
            'enable_multi_position_groups': True,  # เปิดกลุ่มไม้หลายตัว
            'max_pairs_per_cycle': 20,   # สร้างคู่ได้สูงสุด 20 คู่ต่อรอบ
            'time_based_closing': {
                'quick_profit_hours': 6,     # ปิดไม้กำไรที่ 6 ชั่วโมง
                'standard_hours': 12,        # ปิดไม้มาตรฐานที่ 12 ชั่วโมง
                'emergency_hours': 24        # ปิดไม้ฉุกเฉินที่ 24 ชั่วโมง
            }
        }
        
        # 🔄 Tracking
        self.closing_history = []
        self.last_analysis_time = 0
        self.analysis_interval = 5  # วิเคราะห์ทุก 5 วินาที
        
    def analyze_closing_opportunities(self, positions: List[Any], position_statuses: Dict, 
                                    current_price: float) -> List[ClosingGroup]:
        """
        วิเคราะห์โอกาสปิดออเดอร์แบบกลุ่ม
        
        Args:
            positions: List[Position] - รายการ positions ทั้งหมด
            position_statuses: Dict - สถานะไม้จาก position_status_manager
            current_price: float - ราคาปัจจุบัน
            
        Returns:
            List[ClosingGroup] - รายการกลุ่มที่พร้อมปิด
        """
        try:
            logger.info(f"🔍 [GROUP CLOSING] Analyzing closing opportunities for {len(positions)} positions")
            
            closing_groups = []
            
            # 1. รวมกลุ่ม Protected + HG ที่จับคู่กันอยู่
            protected_hg_groups = self.form_protected_hg_groups(positions, position_statuses)
            logger.info(f"📊 Found {len(protected_hg_groups)} Protected+HG groups")
            
            # 2. วิเคราะห์แต่ละกลุ่ม
            for group in protected_hg_groups:
                group_id = f"GROUP_{int(time.time())}_{len(closing_groups)}"
                
                # ตรวจสอบว่าต้องการ Helper หรือไม่
                if group['needs_helper']:
                    # หา Profit Helper
                    available_helpers = self._get_available_profit_helpers(positions, position_statuses)
                    helper_selection = self.select_profit_helpers_from_edge(
                        available_helpers, current_price, group['helper_amount_needed']
                    )
                    
                    if helper_selection.selected_helpers:
                        # รวม Helper เข้ากลุ่ม
                        all_positions = group['protected_positions'] + group['hg_positions'] + helper_selection.selected_helpers
                        total_profit = group['total_profit'] + helper_selection.total_helper_profit
                        group_type = 'PROTECTED_HG_HELPER'
                    else:
                        # ไม่มี Helper เพียงพอ
                        all_positions = group['protected_positions'] + group['hg_positions']
                        total_profit = group['total_profit']
                        group_type = 'PROTECTED_HG'
                else:
                    # ไม่ต้องการ Helper
                    all_positions = group['protected_positions'] + group['hg_positions']
                    total_profit = group['total_profit']
                    group_type = 'PROTECTED_HG'
                
                # คำนวณกำไรขั้นต่ำ
                min_profit_required = self.calculate_dynamic_minimum_profit(
                    len(all_positions), group_type
                )
                
                # ตรวจสอบว่าสามารถปิดได้หรือไม่
                can_close = total_profit >= min_profit_required
                
                closing_group = ClosingGroup(
                    group_id=group_id,
                    group_type=group_type,
                    positions=all_positions,
                    total_profit=total_profit,
                    min_profit_required=min_profit_required,
                    can_close=can_close,
                    reason=f"{group_type} group - Profit: ${total_profit:.2f}, Required: ${min_profit_required:.2f}",
                    protected_positions=group['protected_positions'],
                    hg_positions=group['hg_positions'],
                    helper_positions=helper_selection.selected_helpers if group['needs_helper'] else [],
                    created_time=time.time()
                )
                
                closing_groups.append(closing_group)
                
                if can_close:
                    logger.info(f"✅ [GROUP CLOSING] Group {group_id} ready to close: {closing_group.reason}")
                else:
                    logger.info(f"⚠️ [GROUP CLOSING] Group {group_id} needs more profit: {closing_group.reason}")
            
            # 3. เก็บประวัติ
            self.closing_history.extend(closing_groups)
            if len(self.closing_history) > 100:  # จำกัดประวัติ
                self.closing_history = self.closing_history[-100:]
            
            logger.info(f"🎯 [GROUP CLOSING] Analysis complete: {len(closing_groups)} groups found")
            return closing_groups
            
        except Exception as e:
            logger.error(f"❌ [GROUP CLOSING] Error analyzing opportunities: {e}")
            return []
    
    def form_protected_hg_groups(self, positions: List[Any], position_statuses: Dict) -> List[Dict]:
        """
        รวมกลุ่ม Protected + HG ที่จับคู่กันอยู่
        
        Args:
            positions: List[Position]
            position_statuses: Dict
            
        Returns:
            List[Dict] - รายการกลุ่ม Protected + HG
        """
        try:
            groups = []
            processed_tickets = set()
            
            for ticket, status_obj in position_statuses.items():
                if ticket in processed_tickets:
                    continue
                
                status = status_obj.status
                
                # ตรวจสอบ Protected
                if 'Protected' in status:
                    protected_pos = self._get_position_by_ticket(positions, ticket)
                    if not protected_pos:
                        continue
                    
                    # หา HG ที่ค้ำไม้นี้
                    hg_positions = self._find_hedge_guards_for_protected(
                        positions, position_statuses, protected_pos
                    )
                    
                    if hg_positions:
                        # คำนวณกำไรรวม
                        total_profit = self._calculate_group_profit([protected_pos] + hg_positions)
                        
                        group = {
                            'protected_positions': [protected_pos],
                            'hg_positions': hg_positions,
                            'total_profit': total_profit,
                            'needs_helper': total_profit < 0,
                            'helper_amount_needed': abs(total_profit) + self.min_profit_config['base_amount']
                        }
                        
                        groups.append(group)
                        
                        # ทำเครื่องหมายว่าได้ประมวลผลแล้ว
                        processed_tickets.add(ticket)
                        for hg_pos in hg_positions:
                            processed_tickets.add(getattr(hg_pos, 'ticket', 0))
            
            logger.info(f"📊 [GROUP FORMATION] Formed {len(groups)} Protected+HG groups")
            return groups
            
        except Exception as e:
            logger.error(f"❌ [GROUP FORMATION] Error forming groups: {e}")
            return []
    
    def select_profit_helpers_from_edge(self, available_helpers: List[Any], 
                                      current_price: float, amount_needed: float) -> ProfitHelperSelection:
        """
        เลือก Profit Helper จากขอบนอกสุด
        
        Args:
            available_helpers: List[Position] - ไม้ที่มีสถานะ Profit Helper
            current_price: float - ราคาปัจจุบัน  
            amount_needed: float - จำนวนเงินที่ต้องการเพิ่ม
            
        Returns:
            ProfitHelperSelection - ไม้ Helper ที่เลือกแล้ว
        """
        try:
            if not available_helpers:
                return ProfitHelperSelection([], 0.0, [], "No helpers available")
            
            # คำนวณระยะห่างจากราคาปัจจุบัน
            helper_distances = []
            for helper in available_helpers:
                helper_price = getattr(helper, 'price_open', 0.0)
                distance = abs(helper_price - current_price)
                profit = getattr(helper, 'profit', 0.0)
                
                helper_distances.append({
                    'position': helper,
                    'distance': distance,
                    'profit': profit,
                    'price': helper_price
                })
            
            # เรียงตามระยะห่าง (ไกลสุดก่อน)
            helper_distances.sort(key=lambda x: x['distance'], reverse=True)
            
            # เลือกทีละตัวจนกว่ากำไรรวมจะเป็นบวก
            selected_helpers = []
            total_helper_profit = 0.0
            distances = []
            
            for helper_data in helper_distances:
                if total_helper_profit >= amount_needed:
                    break
                
                selected_helpers.append(helper_data['position'])
                total_helper_profit += helper_data['profit']
                distances.append(helper_data['distance'])
            
            selection_reason = f"Selected {len(selected_helpers)} helpers from edge, total profit: ${total_helper_profit:.2f}"
            
            logger.info(f"🎯 [HELPER SELECTION] {selection_reason}")
            
            return ProfitHelperSelection(
                selected_helpers=selected_helpers,
                total_helper_profit=total_helper_profit,
                distance_from_price=distances,
                selection_reason=selection_reason
            )
            
        except Exception as e:
            logger.error(f"❌ [HELPER SELECTION] Error selecting helpers: {e}")
            return ProfitHelperSelection([], 0.0, [], f"Error: {e}")
    
    def calculate_dynamic_minimum_profit(self, position_count: int, group_type: str, current_price: float = None) -> float:
        """
        คำนวณกำไรขั้นต่ำแบบ Dynamic แบบยืดหยุ่น - เครียไม้ได้ไวไม่ปิดติดลบ
        
        Args:
            position_count: int - จำนวนไม้ในกลุ่ม
            group_type: str - ประเภทกลุ่ม
            current_price: float - ราคาปัจจุบัน (สำหรับคำนวณระยะห่าง)
            
        Returns:
            float - กำไรขั้นต่ำที่ต้องการ
        """
        try:
            # กำไรพื้นฐาน (ลดลงแล้ว)
            base_amount = self.min_profit_config['base_amount']
            
            # คูณตามจำนวนไม้ (ลดลงแล้ว)
            multiplier = self.min_profit_config['multiplier']
            position_multiplier = (position_count - 1) * multiplier
            
            # คูณตามประเภทกลุ่ม (เพิ่มประเภทใหม่)
            group_multiplier = self.min_profit_config['group_type_multipliers'].get(group_type, 1.0)
            
            # คำนวณกำไรขั้นต่ำ
            min_profit = (base_amount + position_multiplier) * group_multiplier
            
            # 🎯 เงื่อนไขพิเศษตามประเภทกลุ่ม
            
            # Distance Priority - ปิดไม้ไกลจากราคาปัจจุบันก่อน
            if group_type == 'DISTANCE_PRIORITY' and current_price:
                min_profit = min(min_profit, 0.3)  # ลดเหลือ $0.3
            
            # Rescue Pairing - ช่วยไม้ขาดทุน
            elif group_type == 'RESCUE_PAIRING':
                min_profit = max(min_profit, -1.0)  # อนุญาตติดลบ -$1.0
            
            # Emergency Pairing - ฉุกเฉิน
            elif group_type == 'EMERGENCY_PAIRING':
                min_profit = max(min_profit, -2.0)  # อนุญาตติดลบ -$2.0
            
            # Flexible Pairing - ยืดหยุ่นสูงสุด
            elif group_type == 'FLEXIBLE_PAIRING':
                min_profit = max(min_profit, -3.0)  # อนุญาตติดลบ -$3.0
            
            # Perfect Balance - ปิดเร็ว
            elif group_type == 'PERFECT_BALANCE':
                min_profit = min(min_profit, 0.2)  # ลดเหลือ $0.2
            
            # Near Balance - ปิดเร็วขึ้น
            elif group_type == 'NEAR_BALANCE':
                min_profit = min(min_profit, 0.4)  # ลดเหลือ $0.4
            
            # จำกัดไม่เกินค่าสูงสุด
            max_amount = self.min_profit_config['max_amount']
            min_profit = min(min_profit, max_amount)
            
            logger.debug(f"💰 [ENHANCED MIN PROFIT] Position count: {position_count}, Group type: {group_type}, Min profit: ${min_profit:.2f}")
            
            return min_profit
            
        except Exception as e:
            logger.error(f"❌ [ENHANCED MIN PROFIT] Error calculating minimum profit: {e}")
            return self.min_profit_config['base_amount']
    
    def analyze_enhanced_closing_opportunities(self, positions: List[Any], position_statuses: Dict, 
                                             current_price: float) -> List[ClosingGroup]:
        """
        วิเคราะห์โอกาสปิดออเดอร์แบบยืดหยุ่น - เครียไม้ได้ไวไม่ปิดติดลบ
        """
        try:
            logger.info(f"🎯 [ENHANCED CLOSING] Starting enhanced analysis with {len(positions)} positions")
            
            # 1. จับคู่แบบ Perfect Balance (1:1)
            perfect_groups = self._form_perfect_balance_groups(positions, position_statuses, current_price)
            
            # 2. จับคู่แบบ Near Balance (2:1, 1:2)
            near_groups = self._form_near_balance_groups(positions, position_statuses, current_price)
            
            # 3. จับคู่แบบ Distance Priority (ไม้ไกลจากราคาปัจจุบัน)
            distance_groups = self._form_distance_priority_groups(positions, position_statuses, current_price)
            
            # 4. จับคู่แบบ Rescue Pairing (ช่วยไม้ขาดทุน)
            rescue_groups = self._form_rescue_pairing_groups(positions, position_statuses, current_price)
            
            # 5. จับคู่แบบ Emergency Pairing (ฉุกเฉิน)
            emergency_groups = self._form_emergency_pairing_groups(positions, position_statuses, current_price)
            
            # 6. จับคู่แบบ Flexible Pairing (ยืดหยุ่นสูงสุด)
            flexible_groups = self._form_flexible_pairing_groups(positions, position_statuses, current_price)
            
            # รวมกลุ่มทั้งหมด
            all_groups = perfect_groups + near_groups + distance_groups + rescue_groups + emergency_groups + flexible_groups
            
            # เรียงตาม priority และกำไร
            all_groups.sort(key=lambda x: (x.priority if hasattr(x, 'priority') else 0, x.total_profit), reverse=True)
            
            # จำกัดจำนวนกลุ่ม
            max_groups = self.group_settings.get('max_pairs_per_cycle', 20)
            selected_groups = all_groups[:max_groups]
            
            logger.info(f"🎯 [ENHANCED CLOSING] Found {len(selected_groups)} enhanced closing opportunities")
            
            return selected_groups
            
        except Exception as e:
            logger.error(f"❌ [ENHANCED CLOSING] Error in enhanced analysis: {e}")
            return []
    
    def _form_perfect_balance_groups(self, positions: List[Any], position_statuses: Dict, current_price: float) -> List[ClosingGroup]:
        """สร้างกลุ่ม Perfect Balance (1:1 ratio)"""
        try:
            groups = []
            buy_positions = [p for p in positions if getattr(p, 'type', 0) == 0]
            sell_positions = [p for p in positions if getattr(p, 'type', 0) == 1]
            
            # จับคู่ 1:1
            for i in range(min(len(buy_positions), len(sell_positions))):
                buy_pos = buy_positions[i]
                sell_pos = sell_positions[i]
                
                total_profit = getattr(buy_pos, 'profit', 0) + getattr(sell_pos, 'profit', 0)
                min_profit_required = self.calculate_dynamic_minimum_profit(2, 'PERFECT_BALANCE', current_price)
                
                if total_profit >= min_profit_required:
                    group = ClosingGroup(
                        group_id=f"PERFECT_BALANCE_{getattr(buy_pos, 'ticket', 0)}_{getattr(sell_pos, 'ticket', 0)}",
                        group_type="PERFECT_BALANCE",
                        positions=[buy_pos, sell_pos],
                        total_profit=total_profit,
                        min_profit_required=min_profit_required,
                        can_close=True,
                        reason=f"Perfect Balance (1:1) - Profit: ${total_profit:.2f}",
                        protected_positions=[],
                        hg_positions=[],
                        helper_positions=[],
                        created_time=time.time()
                    )
                    groups.append(group)
            
            return groups
            
        except Exception as e:
            logger.error(f"❌ [PERFECT BALANCE] Error forming groups: {e}")
            return []
    
    def _form_near_balance_groups(self, positions: List[Any], position_statuses: Dict, current_price: float) -> List[ClosingGroup]:
        """สร้างกลุ่ม Near Balance (2:1, 1:2 ratio)"""
        try:
            groups = []
            buy_positions = [p for p in positions if getattr(p, 'type', 0) == 0]
            sell_positions = [p for p in positions if getattr(p, 'type', 0) == 1]
            
            # จับคู่ 2:1
            for i in range(min(len(buy_positions) // 2, len(sell_positions))):
                buy_pos1 = buy_positions[i * 2]
                buy_pos2 = buy_positions[i * 2 + 1]
                sell_pos = sell_positions[i]
                
                total_profit = (getattr(buy_pos1, 'profit', 0) + 
                              getattr(buy_pos2, 'profit', 0) + 
                              getattr(sell_pos, 'profit', 0))
                min_profit_required = self.calculate_dynamic_minimum_profit(3, 'NEAR_BALANCE', current_price)
                
                if total_profit >= min_profit_required:
                    group = ClosingGroup(
                        group_id=f"NEAR_BALANCE_2:1_{getattr(buy_pos1, 'ticket', 0)}_{getattr(sell_pos, 'ticket', 0)}",
                        group_type="NEAR_BALANCE",
                        positions=[buy_pos1, buy_pos2, sell_pos],
                        total_profit=total_profit,
                        min_profit_required=min_profit_required,
                        can_close=True,
                        reason=f"Near Balance (2:1) - Profit: ${total_profit:.2f}",
                        protected_positions=[],
                        hg_positions=[],
                        helper_positions=[],
                        created_time=time.time()
                    )
                    groups.append(group)
            
            # จับคู่ 1:2
            for i in range(min(len(buy_positions), len(sell_positions) // 2)):
                buy_pos = buy_positions[i]
                sell_pos1 = sell_positions[i * 2]
                sell_pos2 = sell_positions[i * 2 + 1]
                
                total_profit = (getattr(buy_pos, 'profit', 0) + 
                              getattr(sell_pos1, 'profit', 0) + 
                              getattr(sell_pos2, 'profit', 0))
                min_profit_required = self.calculate_dynamic_minimum_profit(3, 'NEAR_BALANCE', current_price)
                
                if total_profit >= min_profit_required:
                    group = ClosingGroup(
                        group_id=f"NEAR_BALANCE_1:2_{getattr(buy_pos, 'ticket', 0)}_{getattr(sell_pos1, 'ticket', 0)}",
                        group_type="NEAR_BALANCE",
                        positions=[buy_pos, sell_pos1, sell_pos2],
                        total_profit=total_profit,
                        min_profit_required=min_profit_required,
                        can_close=True,
                        reason=f"Near Balance (1:2) - Profit: ${total_profit:.2f}",
                        protected_positions=[],
                        hg_positions=[],
                        helper_positions=[],
                        created_time=time.time()
                    )
                    groups.append(group)
            
            return groups
            
        except Exception as e:
            logger.error(f"❌ [NEAR BALANCE] Error forming groups: {e}")
            return []
    
    def _form_distance_priority_groups(self, positions: List[Any], position_statuses: Dict, current_price: float) -> List[ClosingGroup]:
        """สร้างกลุ่ม Distance Priority (ไม้ไกลจากราคาปัจจุบัน)"""
        try:
            groups = []
            
            # หาไม้ที่ไกลจากราคาปัจจุบัน
            distant_positions = []
            for pos in positions:
                price_open = getattr(pos, 'price_open', 0)
                distance = abs(price_open - current_price) if current_price else 0
                
                if distance >= 20.0:  # ไม้ไกลจากราคาปัจจุบัน 20 points ขึ้นไป
                    distant_positions.append((pos, distance))
            
            # เรียงตามระยะห่าง (ไกลที่สุดก่อน)
            distant_positions.sort(key=lambda x: x[1], reverse=True)
            
            # จับคู่ไม้ไกล
            buy_distant = [p for p, d in distant_positions if getattr(p, 'type', 0) == 0]
            sell_distant = [p for p, d in distant_positions if getattr(p, 'type', 0) == 1]
            
            for i in range(min(len(buy_distant), len(sell_distant))):
                buy_pos = buy_distant[i]
                sell_pos = sell_distant[i]
                
                total_profit = getattr(buy_pos, 'profit', 0) + getattr(sell_pos, 'profit', 0)
                min_profit_required = self.calculate_dynamic_minimum_profit(2, 'DISTANCE_PRIORITY', current_price)
                
                if total_profit >= min_profit_required:
                    group = ClosingGroup(
                        group_id=f"DISTANCE_PRIORITY_{getattr(buy_pos, 'ticket', 0)}_{getattr(sell_pos, 'ticket', 0)}",
                        group_type="DISTANCE_PRIORITY",
                        positions=[buy_pos, sell_pos],
                        total_profit=total_profit,
                        min_profit_required=min_profit_required,
                        can_close=True,
                        reason=f"Distance Priority - Profit: ${total_profit:.2f}",
                        protected_positions=[],
                        hg_positions=[],
                        helper_positions=[],
                        created_time=time.time()
                    )
                    groups.append(group)
            
            return groups
            
        except Exception as e:
            logger.error(f"❌ [DISTANCE PRIORITY] Error forming groups: {e}")
            return []
    
    def _form_rescue_pairing_groups(self, positions: List[Any], position_statuses: Dict, current_price: float) -> List[ClosingGroup]:
        """สร้างกลุ่ม Rescue Pairing (ช่วยไม้ขาดทุน)"""
        try:
            groups = []
            
            # หาไม้ขาดทุน
            losing_positions = [p for p in positions if getattr(p, 'profit', 0) <= -5.0]
            profitable_positions = [p for p in positions if getattr(p, 'profit', 0) > 0]
            
            # จับคู่ไม้ขาดทุนกับไม้กำไร
            for losing_pos in losing_positions:
                for profit_pos in profitable_positions:
                    total_profit = getattr(losing_pos, 'profit', 0) + getattr(profit_pos, 'profit', 0)
                    min_profit_required = self.calculate_dynamic_minimum_profit(2, 'RESCUE_PAIRING', current_price)
                    
                    if total_profit >= min_profit_required:
                        group = ClosingGroup(
                            group_id=f"RESCUE_PAIRING_{getattr(losing_pos, 'ticket', 0)}_{getattr(profit_pos, 'ticket', 0)}",
                            group_type="RESCUE_PAIRING",
                            positions=[losing_pos, profit_pos],
                            total_profit=total_profit,
                            min_profit_required=min_profit_required,
                            can_close=True,
                            reason=f"Rescue Pairing - Profit: ${total_profit:.2f}",
                            protected_positions=[],
                            hg_positions=[],
                            helper_positions=[],
                            created_time=time.time()
                        )
                        groups.append(group)
                        break  # ใช้ไม้กำไรตัวหนึ่งช่วยไม้ขาดทุนตัวหนึ่ง
            
            return groups
            
        except Exception as e:
            logger.error(f"❌ [RESCUE PAIRING] Error forming groups: {e}")
            return []
    
    def _form_emergency_pairing_groups(self, positions: List[Any], position_statuses: Dict, current_price: float) -> List[ClosingGroup]:
        """สร้างกลุ่ม Emergency Pairing (ฉุกเฉิน)"""
        try:
            groups = []
            
            # หาไม้ที่ขาดทุนมาก
            emergency_positions = [p for p in positions if getattr(p, 'profit', 0) <= -10.0]
            
            # จับคู่ไม้ฉุกเฉิน
            buy_emergency = [p for p in emergency_positions if getattr(p, 'type', 0) == 0]
            sell_emergency = [p for p in emergency_positions if getattr(p, 'type', 0) == 1]
            
            for i in range(min(len(buy_emergency), len(sell_emergency))):
                buy_pos = buy_emergency[i]
                sell_pos = sell_emergency[i]
                
                total_profit = getattr(buy_pos, 'profit', 0) + getattr(sell_pos, 'profit', 0)
                min_profit_required = self.calculate_dynamic_minimum_profit(2, 'EMERGENCY_PAIRING', current_price)
                
                if total_profit >= min_profit_required:
                    group = ClosingGroup(
                        group_id=f"EMERGENCY_PAIRING_{getattr(buy_pos, 'ticket', 0)}_{getattr(sell_pos, 'ticket', 0)}",
                        group_type="EMERGENCY_PAIRING",
                        positions=[buy_pos, sell_pos],
                        total_profit=total_profit,
                        min_profit_required=min_profit_required,
                        can_close=True,
                        reason=f"Emergency Pairing - Profit: ${total_profit:.2f}",
                        protected_positions=[],
                        hg_positions=[],
                        helper_positions=[],
                        created_time=time.time()
                    )
                    groups.append(group)
            
            return groups
            
        except Exception as e:
            logger.error(f"❌ [EMERGENCY PAIRING] Error forming groups: {e}")
            return []
    
    def _form_flexible_pairing_groups(self, positions: List[Any], position_statuses: Dict, current_price: float) -> List[ClosingGroup]:
        """สร้างกลุ่ม Flexible Pairing (ยืดหยุ่นสูงสุด)"""
        try:
            groups = []
            
            # หาไม้ที่เหลือทั้งหมด
            remaining_positions = positions
            
            # จับคู่แบบยืดหยุ่น (ไม่จำกัดอัตราส่วน)
            buy_positions = [p for p in remaining_positions if getattr(p, 'type', 0) == 0]
            sell_positions = [p for p in remaining_positions if getattr(p, 'type', 0) == 1]
            
            # จับคู่ไม้ที่เหลือ
            for i in range(min(len(buy_positions), len(sell_positions))):
                buy_pos = buy_positions[i]
                sell_pos = sell_positions[i]
                
                total_profit = getattr(buy_pos, 'profit', 0) + getattr(sell_pos, 'profit', 0)
                min_profit_required = self.calculate_dynamic_minimum_profit(2, 'FLEXIBLE_PAIRING', current_price)
                
                if total_profit >= min_profit_required:
                    group = ClosingGroup(
                        group_id=f"FLEXIBLE_PAIRING_{getattr(buy_pos, 'ticket', 0)}_{getattr(sell_pos, 'ticket', 0)}",
                        group_type="FLEXIBLE_PAIRING",
                        positions=[buy_pos, sell_pos],
                        total_profit=total_profit,
                        min_profit_required=min_profit_required,
                        can_close=True,
                        reason=f"Flexible Pairing - Profit: ${total_profit:.2f}",
                        protected_positions=[],
                        hg_positions=[],
                        helper_positions=[],
                        created_time=time.time()
                    )
                    groups.append(group)
            
            return groups
            
        except Exception as e:
            logger.error(f"❌ [FLEXIBLE PAIRING] Error forming groups: {e}")
            return []
    
    def execute_group_closing(self, closing_group: ClosingGroup) -> Dict[str, Any]:
        """
        ปิดกลุ่มออเดอร์
        
        Args:
            closing_group: ClosingGroup - กลุ่มที่ต้องการปิด
            
        Returns:
            Dict[str, Any] - ผลลัพธ์การปิด
        """
        try:
            if not closing_group.can_close:
                return {
                    'success': False,
                    'message': f'Group {closing_group.group_id} cannot be closed: {closing_group.reason}',
                    'group_id': closing_group.group_id
                }
            
            logger.info(f"🚀 [GROUP CLOSING] Executing group {closing_group.group_id}")
            logger.info(f"   Type: {closing_group.group_type}")
            logger.info(f"   Positions: {len(closing_group.positions)}")
            logger.info(f"   Total Profit: ${closing_group.total_profit:.2f}")
            logger.info(f"   Min Required: ${closing_group.min_profit_required:.2f}")
            
            # ตรวจสอบ Zero Loss Policy
            if not self._check_zero_loss_policy(closing_group):
                return {
                    'success': False,
                    'message': f'Group {closing_group.group_id} failed Zero Loss Policy check',
                    'group_id': closing_group.group_id
                }
            
            # ส่งคำสั่งปิดไปยัง OrderManager
            if self.order_manager:
                result = self.order_manager.close_positions_group_raw(
                    closing_group.positions, 
                    f"Group Closing: {closing_group.group_type}"
                )
                
                if result.success:
                    logger.info(f"✅ [GROUP CLOSING] Successfully closed group {closing_group.group_id}")
                    logger.info(f"   Closed positions: {len(result.closed_tickets)}")
                    logger.info(f"   Total profit: ${result.total_profit:.2f}")
                    
                    return {
                        'success': True,
                        'message': f'Group {closing_group.group_id} closed successfully',
                        'group_id': closing_group.group_id,
                        'closed_tickets': result.closed_tickets,
                        'total_profit': result.total_profit,
                        'closed_count': len(result.closed_tickets)
                    }
                else:
                    logger.error(f"❌ [GROUP CLOSING] Failed to close group {closing_group.group_id}: {result.error_message}")
                    return {
                        'success': False,
                        'message': f'Group {closing_group.group_id} failed: {result.error_message}',
                        'group_id': closing_group.group_id
                    }
            else:
                logger.error("❌ [GROUP CLOSING] OrderManager not available")
                return {
                    'success': False,
                    'message': 'OrderManager not available',
                    'group_id': closing_group.group_id
                }
                
        except Exception as e:
            logger.error(f"❌ [GROUP CLOSING] Error executing group closing: {e}")
            return {
                'success': False,
                'message': f'Error: {e}',
                'group_id': closing_group.group_id
            }
    
    def _get_position_by_ticket(self, positions: List[Any], ticket: int) -> Optional[Any]:
        """หา Position ตาม Ticket"""
        try:
            for pos in positions:
                if hasattr(pos, 'ticket') and pos.ticket == ticket:
                    return pos
            return None
        except Exception as e:
            logger.error(f"❌ Error finding position by ticket: {e}")
            return None
    
    def _find_hedge_guards_for_protected(self, positions: List[Any], position_statuses: Dict, 
                                       protected_pos: Any) -> List[Any]:
        """หา HG ที่ค้ำไม้ Protected"""
        try:
            hg_positions = []
            protected_ticket = getattr(protected_pos, 'ticket', 0)
            
            for ticket, status_obj in position_statuses.items():
                status = status_obj.status
                if 'HG' in status and ticket != protected_ticket:
                    # ตรวจสอบว่าเป็น HG ของไม้นี้หรือไม่
                    relationships = getattr(status_obj, 'relationships', {})
                    if relationships.get('is_hedging'):
                        hedge_target = relationships.get('hedge_target', {})
                        if hedge_target.get('ticket') == protected_ticket:
                            hg_pos = self._get_position_by_ticket(positions, ticket)
                            if hg_pos:
                                hg_positions.append(hg_pos)
            
            return hg_positions
            
        except Exception as e:
            logger.error(f"❌ Error finding hedge guards: {e}")
            return []
    
    def _get_available_profit_helpers(self, positions: List[Any], position_statuses: Dict) -> List[Any]:
        """หาไม้ที่มีสถานะ Profit Helper"""
        try:
            helpers = []
            for ticket, status_obj in position_statuses.items():
                status = status_obj.status
                if 'Profit Helper' in status:
                    helper_pos = self._get_position_by_ticket(positions, ticket)
                    if helper_pos:
                        helpers.append(helper_pos)
            return helpers
        except Exception as e:
            logger.error(f"❌ Error getting profit helpers: {e}")
            return []
    
    def _calculate_group_profit(self, positions: List[Any]) -> float:
        """คำนวณกำไรรวมของกลุ่ม"""
        try:
            total_profit = 0.0
            for pos in positions:
                profit = getattr(pos, 'profit', 0.0)
                swap = getattr(pos, 'swap', 0.0)
                commission = getattr(pos, 'commission', 0.0)
                total_profit += profit + swap + commission
            return total_profit
        except Exception as e:
            logger.error(f"❌ Error calculating group profit: {e}")
            return 0.0
    
    def _check_zero_loss_policy(self, closing_group: ClosingGroup) -> bool:
        """ตรวจสอบ Zero Loss Policy"""
        try:
            # ตรวจสอบว่ากลุ่มมีกำไรมากกว่าขั้นต่ำหรือไม่
            if closing_group.total_profit < closing_group.min_profit_required:
                logger.warning(f"🚫 [ZERO LOSS] Group {closing_group.group_id} profit insufficient")
                return False
            
            # ตรวจสอบว่ามีไม้ทั้ง BUY และ SELL หรือไม่ (Hedge Pair)
            buy_count = 0
            sell_count = 0
            
            for pos in closing_group.positions:
                pos_type = getattr(pos, 'type', 0)
                if pos_type == 0:  # BUY
                    buy_count += 1
                elif pos_type == 1:  # SELL
                    sell_count += 1
            
            # ถ้ามีไม้ทั้ง BUY และ SELL ให้ผ่าน
            if buy_count > 0 and sell_count > 0:
                logger.info(f"✅ [ZERO LOSS] Group {closing_group.group_id} is hedge pair - approved")
                return True
            
            # ถ้าเป็นกลุ่มเดียวต้องมีกำไรมาก
            if closing_group.total_profit >= closing_group.min_profit_required * 1.5:
                logger.info(f"✅ [ZERO LOSS] Group {closing_group.group_id} has sufficient profit - approved")
                return True
            
            logger.warning(f"🚫 [ZERO LOSS] Group {closing_group.group_id} failed policy check")
            return False
            
        except Exception as e:
            logger.error(f"❌ [ZERO LOSS] Error checking policy: {e}")
            return False
    
    def get_closing_statistics(self) -> Dict[str, Any]:
        """ดึงสถิติการปิดกลุ่ม"""
        try:
            total_groups = len(self.closing_history)
            successful_groups = len([g for g in self.closing_history if g.can_close])
            
            return {
                'total_groups_analyzed': total_groups,
                'successful_groups': successful_groups,
                'success_rate': (successful_groups / total_groups * 100) if total_groups > 0 else 0,
                'last_analysis_time': self.last_analysis_time
            }
        except Exception as e:
            logger.error(f"❌ Error getting statistics: {e}")
            return {}
    
    def clear_history(self):
        """ล้างประวัติการปิดกลุ่ม"""
        self.closing_history.clear()
        logger.info("🧹 [GROUP CLOSING] History cleared")
