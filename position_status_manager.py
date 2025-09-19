# -*- coding: utf-8 -*-
"""
Position Status Manager
ระบบจัดการสถานะไม้แบบ Real-time
"""

import logging
import time
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class PositionStatus:
    """คลาสสำหรับเก็บสถานะของ Position"""
    ticket: int
    status: str
    zone: str
    relationships: Dict[str, Any]
    ratio_info: Dict[str, Any]
    last_update: float
    profit: float
    direction: str
    price_open: float
    price_current: float

@dataclass
class ZoneInfo:
    """ข้อมูล Zone"""
    zone_type: str  # 'support', 'resistance', 'breakout'
    strength: float
    level: float
    tolerance: float
    last_touch: float

class PositionStatusManager:
    """คลาสสำหรับจัดการสถานะ Position แบบ Real-time"""
    
    def __init__(self):
        self.status_definitions = {
            'HG': 'ค้ำไม้ฝั่งตรงข้าม',
            'SUPPORT_GUARD': 'ห้ามปิด - ค้ำไม้อื่น', 
            'PROTECTED': 'มีไม้ค้ำแล้ว รอช่วยเหลือ',
            'PROFIT_HELPER': 'ไม้กำไร พร้อมช่วยเหลือ',
            'STANDALONE': 'ยังไม่มีหน้าที่'
        }
        
        self.position_relationships = {}
        self.zone_assignments = {}
        self.status_cache = {}
        self.last_analysis_time = 0
        self.analysis_interval = 3  # วิเคราะห์ทุก 3 วินาที
        
        # 🎯 Dynamic Parameters ตาม Market Condition
        self.zone_tolerance_levels = {
            'volatile': 0.001,    # แม่นยำมาก
            'trending': 0.3,      # ยืดหยุ่น
            'sideways': 0.1       # ปานกลาง
        }
        
        self.min_zone_strength_levels = {
            'volatile': 0.001,    # เข้าได้ง่าย
            'trending': 0.01,     # ปานกลาง
            'sideways': 0.03      # เข้มงวด
        }
        
    def analyze_all_positions(self, positions: List[Any], current_price: float, 
                            zones: Any, market_condition: str = 'sideways') -> Dict[int, PositionStatus]:
        """
        วิเคราะห์สถานะทุกไม้แบบ Real-time
        
        Args:
            positions: รายการ Position ทั้งหมด
            current_price: ราคาปัจจุบัน
            zones: รายการ Zone
            market_condition: สภาวะตลาด ('volatile', 'trending', 'sideways')
            
        Returns:
            Dict[int, PositionStatus]: สถานะของแต่ละ Position
        """
        try:
            current_time = time.time()
            
            # ตรวจสอบว่าต้องวิเคราะห์ใหม่หรือไม่
            if current_time - self.last_analysis_time < self.analysis_interval:
                return self.status_cache
                
            logger.info(f"🔍 [STATUS ANALYSIS] วิเคราะห์สถานะ {len(positions)} ไม้ (Market: {market_condition})")
            
            # ปรับพารามิเตอร์ตาม Market Condition
            self._adjust_zone_parameters(market_condition)
            
            status_results = {}
            
            for position in positions:
                try:
                    # 1. จำแนก Zone
                    zone = self._classify_position_zone(position, current_price, zones)
                    
                    # 2. หา Relationships
                    relationships = self._find_position_relationships(position, positions)
                    
                    # 3. กำหนดสถานะ
                    status = self._determine_position_status(position, zone, relationships)
                    
                    # 4. คำนวณ Ratio (ถ้าเป็น HG)
                    ratio_info = self._calculate_hedge_ratio(position, relationships)
                    
                    # 5. สร้าง PositionStatus Object
                    position_status = PositionStatus(
                        ticket=getattr(position, 'ticket', 0),
                        status=status,
                        zone=zone.get('type', 'unknown'),
                        relationships=relationships,
                        ratio_info=ratio_info,
                        last_update=current_time,
                        profit=getattr(position, 'profit', 0.0),
                        direction='BUY' if getattr(position, 'type', 0) == 0 else 'SELL',
                        price_open=getattr(position, 'price_open', 0.0),
                        price_current=getattr(position, 'price_current', current_price)
                    )
                    
                    status_results[position_status.ticket] = position_status
                    
                except Exception as e:
                    logger.error(f"❌ Error analyzing position {getattr(position, 'ticket', 'unknown')}: {e}")
                    continue
            
            # อัพเดท Cache
            self.status_cache = status_results
            self.last_analysis_time = current_time
            
            # Log สรุปผลการวิเคราะห์
            self._log_analysis_summary(status_results)
            
            return status_results
            
        except Exception as e:
            logger.error(f"❌ Error in analyze_all_positions: {e}")
            return self.status_cache
    
    def _adjust_zone_parameters(self, market_condition: str):
        """ปรับพารามิเตอร์ Zone ตาม Market Condition"""
        self.zone_tolerance = self.zone_tolerance_levels.get(market_condition, 0.1)
        self.min_zone_strength = self.min_zone_strength_levels.get(market_condition, 0.03)
        
        logger.debug(f"🔧 [ZONE PARAMS] Market: {market_condition}, "
                    f"Tolerance: {self.zone_tolerance}, Min Strength: {self.min_zone_strength}")
    
    def _classify_position_zone(self, position: Any, current_price: float, zones: Any) -> Dict[str, Any]:
        """จำแนก Zone ของ Position"""
        try:
            position_price = getattr(position, 'price_open', 0.0)
            position_type = getattr(position, 'type', 0)
            
            # ตรวจสอบว่า zones เป็น list หรือไม่
            if not isinstance(zones, list) or not zones:
                return {
                    'type': 'standalone',
                    'level': position_price,
                    'strength': 0.0,
                    'distance': float('inf')
                }
            
            # หา Zone ที่ใกล้ที่สุด
            closest_zone = None
            min_distance = float('inf')
            
            for zone in zones:
                # ตรวจสอบว่า zone เป็น dict หรือไม่
                if not isinstance(zone, dict):
                    continue
                    
                zone_level = zone.get('level', 0.0)
                distance = abs(position_price - zone_level)
                
                if distance < min_distance:
                    min_distance = distance
                    closest_zone = zone
            
            if closest_zone and min_distance <= self.zone_tolerance:
                return {
                    'type': closest_zone.get('type', 'unknown'),
                    'level': closest_zone.get('level', 0.0),
                    'strength': closest_zone.get('strength', 0.0),
                    'distance': min_distance
                }
            else:
                return {
                    'type': 'standalone',
                    'level': position_price,
                    'strength': 0.0,
                    'distance': min_distance
                }
                
        except Exception as e:
            logger.error(f"❌ Error classifying zone: {e}")
            return {'type': 'unknown', 'level': 0.0, 'strength': 0.0, 'distance': float('inf')}
    
    def _find_position_relationships(self, position: Any, all_positions: List[Any]) -> Dict[str, Any]:
        """หา Relationships ของ Position"""
        try:
            relationships = {
                'is_hedging': False,
                'is_protecting_others': False,
                'is_protected': False,
                'has_assignment': False,
                'hedge_target': None,
                'hedge_ratio': '1:1',
                'protecting': [],
                'protected_by': None
            }
            
            position_ticket = getattr(position, 'ticket', 0)
            position_type = getattr(position, 'type', 0)
            position_profit = getattr(position, 'profit', 0.0)
            
            # หา Position ที่เป็นฝั่งตรงข้าม
            opposite_positions = [
                p for p in all_positions 
                if getattr(p, 'ticket', 0) != position_ticket and 
                   getattr(p, 'type', 0) != position_type
            ]
            
            # ตรวจสอบ HG (Hedge Guard)
            for opp_pos in opposite_positions:
                opp_profit = getattr(opp_pos, 'profit', 0.0)
                
                # ถ้าไม้ฝั่งตรงข้ามขาดทุน และไม้นี้กำไร
                if opp_profit < -5.0 and position_profit > 0:
                    relationships['is_hedging'] = True
                    relationships['hedge_target'] = {
                        'ticket': getattr(opp_pos, 'ticket', 0),
                        'direction': 'BUY' if getattr(opp_pos, 'type', 0) == 0 else 'SELL',
                        'profit': opp_profit
                    }
                    relationships['hedge_ratio'] = self._calculate_hedge_ratio_string(position_profit, opp_profit)
                    break
            
            # ตรวจสอบ Support Guard (ไม้ที่ค้ำไม้อื่น)
            if position_profit > 0:
                protected_positions = [
                    p for p in all_positions 
                    if getattr(p, 'ticket', 0) != position_ticket and 
                       getattr(p, 'type', 0) == position_type and
                       getattr(p, 'profit', 0.0) < -2.0
                ]
                
                if protected_positions:
                    relationships['is_protecting_others'] = True
                    relationships['protecting'] = [
                        {'ticket': getattr(p, 'ticket', 0), 'profit': getattr(p, 'profit', 0.0)}
                        for p in protected_positions
                    ]
            
            # ตรวจสอบ Protected (ไม้ที่ถูกค้ำ)
            if position_profit < -2.0:
                protector_positions = [
                    p for p in all_positions 
                    if getattr(p, 'ticket', 0) != position_ticket and 
                       getattr(p, 'type', 0) == position_type and
                       getattr(p, 'profit', 0.0) > 0
                ]
                
                if protector_positions:
                    relationships['is_protected'] = True
                    relationships['protected_by'] = {
                        'ticket': getattr(protector_positions[0], 'ticket', 0),
                        'profit': getattr(protector_positions[0], 'profit', 0.0)
                    }
            
            # ตรวจสอบ Assignment
            relationships['has_assignment'] = (
                relationships['is_hedging'] or 
                relationships['is_protecting_others'] or 
                relationships['is_protected']
            )
            
            return relationships
            
        except Exception as e:
            logger.error(f"❌ Error finding relationships: {e}")
            return {'is_hedging': False, 'is_protecting_others': False, 'is_protected': False, 'has_assignment': False}
    
    def _determine_position_status(self, position: Any, zone: Dict[str, Any], 
                                 relationships: Dict[str, Any]) -> str:
        """กำหนดสถานะตามตัวอย่างที่ให้มา"""
        try:
            position_profit = getattr(position, 'profit', 0.0)
            
            # ตรวจสอบ HG ก่อน
            if relationships.get('is_hedging'):
                target_info = relationships['hedge_target']
                ratio = relationships.get('hedge_ratio', '1:1')
                return f"HG - ค้ำ {target_info['direction']} Zone {zone.get('type', 'unknown')} ({ratio})"
                
            # ตรวจสอบ Support Guard
            elif relationships.get('is_protecting_others'):
                protected_count = len(relationships['protecting'])
                return f"Support Guard - ห้ามปิด ค้ำ {protected_count} ไม้"
                
            # ตรวจสอบ Protected
            elif relationships.get('is_protected'):
                protector = relationships['protected_by']
                return f"Protected - มี HG ค้ำแล้ว รอช่วยเหลือ (โดย #{protector['ticket']})"
                
            # ตรวจสอบ Profit Helper
            elif position_profit > 0 and not relationships.get('has_assignment'):
                available_zones = self._find_zones_needing_help()
                if available_zones:
                    return f"Profit Helper - พร้อมช่วย Zone {available_zones[0]}"
                else:
                    return "Profit Helper - พร้อมช่วยเหลือ"
                    
            # สถานะ Default
            else:
                return "Standalone - ยังไม่มีหน้าที่"
                
        except Exception as e:
            logger.error(f"❌ Error determining status: {e}")
            return "Unknown - ข้อผิดพลาดในการวิเคราะห์"
    
    def _calculate_hedge_ratio(self, position: Any, relationships: Dict[str, Any]) -> Dict[str, Any]:
        """คำนวณ Ratio สำหรับ HG"""
        try:
            if not relationships.get('is_hedging'):
                return {'ratio': '1:1', 'strength': 0.0}
            
            position_profit = getattr(position, 'profit', 0.0)
            target_profit = relationships['hedge_target']['profit']
            
            if target_profit == 0:
                return {'ratio': '1:1', 'strength': 0.0}
            
            ratio_value = abs(position_profit / target_profit)
            ratio_string = f"{ratio_value:.1f}:1"
            
            # คำนวณความแข็งแกร่งของ HG
            strength = min(ratio_value, 2.0) / 2.0  # 0-1 scale
            
            return {
                'ratio': ratio_string,
                'strength': strength,
                'position_profit': position_profit,
                'target_profit': target_profit
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating hedge ratio: {e}")
            return {'ratio': '1:1', 'strength': 0.0}
    
    def _calculate_hedge_ratio_string(self, position_profit: float, target_profit: float) -> str:
        """คำนวณ Ratio String"""
        try:
            if target_profit == 0:
                return "1:1"
            
            ratio_value = abs(position_profit / target_profit)
            return f"{ratio_value:.1f}:1"
            
        except Exception as e:
            logger.error(f"❌ Error calculating ratio string: {e}")
            return "1:1"
    
    def _find_zones_needing_help(self) -> List[str]:
        """หา Zone ที่ต้องการความช่วยเหลือ"""
        # ตัวอย่าง: หา Zone ที่มีไม้ขาดทุน
        return ['Zone A', 'Zone B']  # Placeholder
    
    def _log_analysis_summary(self, status_results: Dict[int, PositionStatus]):
        """Log สรุปผลการวิเคราะห์"""
        try:
            if not status_results:
                return
            
            # นับสถานะต่างๆ
            status_counts = {}
            for status_obj in status_results.values():
                status_type = status_obj.status.split(' - ')[0]
                status_counts[status_type] = status_counts.get(status_type, 0) + 1
            
            # Log สรุป
            summary_parts = []
            for status_type, count in status_counts.items():
                summary_parts.append(f"{status_type}: {count}")
            
            logger.info(f"📊 [STATUS SUMMARY] {', '.join(summary_parts)}")
            
            # Log ไม้ที่มีสถานะพิเศษ
            special_positions = [
                (ticket, status_obj.status) 
                for ticket, status_obj in status_results.items() 
                if 'HG' in status_obj.status or 'Support Guard' in status_obj.status
            ]
            
            if special_positions:
                for ticket, status in special_positions:
                    logger.info(f"🎯 [SPECIAL STATUS] #{ticket}: {status}")
                    
        except Exception as e:
            logger.error(f"❌ Error logging analysis summary: {e}")
    
    def get_position_status(self, ticket: int) -> Optional[PositionStatus]:
        """ดึงสถานะของ Position ตาม Ticket"""
        return self.status_cache.get(ticket)
    
    def get_all_statuses(self) -> Dict[int, PositionStatus]:
        """ดึงสถานะทั้งหมด"""
        return self.status_cache.copy()
    
    def clear_cache(self):
        """ล้าง Cache"""
        self.status_cache.clear()
        self.last_analysis_time = 0
        logger.info("🧹 [CACHE] Cleared position status cache")
