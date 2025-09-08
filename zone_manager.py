# -*- coding: utf-8 -*-
"""
Zone Manager - หลักระบบจัดการ Zones
จัดการ Positions แบบแบ่ง Zone ตามราคา เพื่อการวิเคราะห์และจัดการที่แม่นยำ

🎯 หลักการ Zone-Based Management:
1. แบ่ง Positions เข้า Zones ตามราคา (30 pips/zone)
2. ติดตาม Zone Status แบบ Real-time
3. คำนวณ Zone Health และ P&L
4. สนับสนุน Inter-Zone Cooperation

✅ ความแม่นยำสูง ✅ จัดการเฉพาะจุด ✅ ประสิทธิภาพดี
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

@dataclass
class ZonePosition:
    """Position ข้อมูลใน Zone"""
    ticket: int
    symbol: str
    type: int  # 0=BUY, 1=SELL
    volume: float
    price_open: float
    price_current: float
    profit: float
    age_minutes: float = 0.0
    distance_pips: float = 0.0

@dataclass  
class Zone:
    """Zone Data Structure - หน่วยพื้นฐานของระบบ"""
    zone_id: int
    price_min: float
    price_max: float
    price_center: float
    
    # Position Data
    positions: List[ZonePosition] = field(default_factory=list)
    buy_positions: List[ZonePosition] = field(default_factory=list)
    sell_positions: List[ZonePosition] = field(default_factory=list)
    
    # Zone Statistics
    buy_count: int = 0
    sell_count: int = 0
    total_positions: int = 0
    total_volume: float = 0.0
    
    # Financial Metrics
    total_pnl: float = 0.0
    profit_positions: int = 0
    loss_positions: int = 0
    
    # Zone Health
    health_score: float = 0.0
    balance_ratio: float = 0.5  # 0=all SELL, 0.5=balanced, 1=all BUY
    
    # Support Capacity
    available_profit: float = 0.0  # กำไรที่สามารถช่วยได้
    help_needed: float = 0.0       # ความช่วยเหลือที่ต้องการ
    status: str = 'NEUTRAL'        # HELPER, TROUBLED, NEUTRAL, CRITICAL
    
    # Zone Activity
    last_updated: datetime = field(default_factory=datetime.now)
    is_active: bool = True

class ZoneManager:
    """🎯 Zone Manager - หลักระบบจัดการ Zones"""
    
    def __init__(self, zone_size_pips: float = 30.0, max_zones: int = 50):
        """
        เริ่มต้น Zone Manager
        
        Args:
            zone_size_pips: ขนาด Zone ในหน่วย pips (default: 30 pips)
            max_zones: จำนวน Zone สูงสุดที่ติดตาม (default: 50)
        """
        self.zone_size_pips = zone_size_pips
        self.zone_size_points = zone_size_pips / 10  # สำหรับ XAUUSD (30 pips = 3.0 points)
        self.max_zones = max_zones
        
        # Zone Storage
        self.zones: Dict[int, Zone] = {}
        self.active_zones: List[int] = []
        
        # Zone Boundaries
        self.base_price: float = 0.0  # ราคาฐานสำหรับคำนวณ Zone
        self.price_range: Tuple[float, float] = (0.0, 0.0)
        
        # Statistics
        self.total_positions: int = 0
        self.last_update: datetime = datetime.now()
        
        logger.info(f"🎯 Zone Manager initialized: {zone_size_pips} pips/zone, max {max_zones} zones")
    
    def calculate_zone_id(self, price: float) -> int:
        """
        คำนวณ Zone ID จากราคา
        
        Args:
            price: ราคาที่ต้องการหา Zone
            
        Returns:
            int: Zone ID
        """
        # 🎯 ใช้ Dynamic Base Price แทนการตั้งครั้งเดียว
        if self.base_price == 0.0:
            # ใช้ราคาที่ปัดลงให้เหมาะกับ Zone Size
            # สำหรับ 30 pips (300 points), ปัดลงเป็นหลัก zone_size_points
            zone_aligned_price = math.floor(price / self.zone_size_points) * self.zone_size_points
            self.base_price = zone_aligned_price
            logger.info(f"🎯 Base Price initialized (zone-aligned): {self.base_price:.2f}")
            
        # คำนวณ Zone ID จากการหาร
        zone_offset = (price - self.base_price) / self.zone_size_points
        zone_id = int(math.floor(zone_offset))
        
        # 🔧 ปรับ Base Price ถ้า Zone ID ติดลบมากเกินไป
        if zone_id < -5:
            # ปรับ Base Price ลงเพื่อให้ Zone ID เป็นบวก
            zone_aligned_price = math.floor(price / self.zone_size_points) * self.zone_size_points
            logger.info(f"🔧 Adjusting Base Price: {self.base_price:.2f} → {zone_aligned_price:.2f}")
            self.base_price = zone_aligned_price
            zone_offset = (price - self.base_price) / self.zone_size_points
            zone_id = int(math.floor(zone_offset))
        
        return zone_id
    
    def debug_zone_calculation(self, price: float) -> Dict[str, Any]:
        """
        🔍 Debug การคำนวณ Zone เพื่อแสดงรายละเอียด
        
        Args:
            price: ราคาที่ต้องการ debug
            
        Returns:
            Dict: ข้อมูลการคำนวณ Zone
        """
        zone_id = self.calculate_zone_id(price)
        zone_range = self.get_zone_price_range(zone_id)
        
        debug_info = {
            'current_price': price,
            'base_price': self.base_price,
            'zone_size_pips': self.zone_size_pips,
            'zone_size_points': self.zone_size_points,
            'price_difference': price - self.base_price,
            'zone_offset': (price - self.base_price) / self.zone_size_points,
            'zone_id': zone_id,
            'zone_range': zone_range,
            'zone_center': (zone_range[0] + zone_range[1]) / 2
        }
        
        # คำนวณ Zone Width เป็น pips
        zone_width_pips = (zone_range[1] - zone_range[0]) * 10
        
        logger.info(f"🔍 Zone Calculation Debug:")
        logger.info(f"   Current Price: {price:.2f}")
        logger.info(f"   Base Price: {self.base_price:.2f}")
        logger.info(f"   Price Difference: {debug_info['price_difference']:.2f}")
        logger.info(f"   Zone Size: {self.zone_size_pips} pips ({self.zone_size_points} points)")
        logger.info(f"   Zone Offset: {debug_info['zone_offset']:.3f}")
        logger.info(f"   Zone ID: {zone_id}")
        logger.info(f"   Zone Range: {zone_range[0]:.2f} - {zone_range[1]:.2f} (Width: {zone_width_pips:.1f} pips)")
        logger.info(f"   Zone Center: {debug_info['zone_center']:.2f}")
        
        return debug_info
    
    def get_zone_price_range(self, zone_id: int) -> Tuple[float, float]:
        """
        คำนวณช่วงราคาของ Zone
        
        Args:
            zone_id: Zone ID
            
        Returns:
            Tuple[float, float]: (price_min, price_max)
        """
        price_min = self.base_price + (zone_id * self.zone_size_points)
        price_max = price_min + self.zone_size_points
        
        return price_min, price_max
    
    def create_zone(self, zone_id: int) -> Zone:
        """
        สร้าง Zone ใหม่
        
        Args:
            zone_id: Zone ID
            
        Returns:
            Zone: Zone ที่สร้างใหม่
        """
        price_min, price_max = self.get_zone_price_range(zone_id)
        price_center = (price_min + price_max) / 2
        
        zone = Zone(
            zone_id=zone_id,
            price_min=price_min,
            price_max=price_max,
            price_center=price_center
        )
        
        self.zones[zone_id] = zone
        
        if zone_id not in self.active_zones:
            self.active_zones.append(zone_id)
            self.active_zones.sort()
            
        logger.debug(f"📍 Created Zone {zone_id}: {price_min:.2f}-{price_max:.2f}")
        
        return zone
    
    def get_or_create_zone(self, zone_id: int) -> Zone:
        """
        ดึง Zone หรือสร้างใหม่ถ้าไม่มี
        
        Args:
            zone_id: Zone ID
            
        Returns:
            Zone: Zone ที่ต้องการ
        """
        if zone_id not in self.zones:
            return self.create_zone(zone_id)
        return self.zones[zone_id]
    
    def add_position_to_zone(self, position: Any, current_price: float) -> bool:
        """
        เพิ่ม Position เข้า Zone
        
        Args:
            position: Position object
            current_price: ราคาปัจจุบัน
            
        Returns:
            bool: สำเร็จหรือไม่
        """
        try:
            # คำนวณ Zone ID จากราคาเปิด
            zone_id = self.calculate_zone_id(getattr(position, 'price_open', current_price))
            zone = self.get_or_create_zone(zone_id)
            
            # สร้าง ZonePosition
            zone_position = ZonePosition(
                ticket=getattr(position, 'ticket', 0),
                symbol=getattr(position, 'symbol', 'XAUUSD'),
                type=getattr(position, 'type', 0),
                volume=getattr(position, 'volume', 0.01),
                price_open=getattr(position, 'price_open', current_price),
                price_current=current_price,
                profit=getattr(position, 'profit', 0.0)
            )
            
            # คำนวณข้อมูลเพิ่มเติม
            zone_position.distance_pips = abs(current_price - zone_position.price_open) * 100
            
            # คำนวณอายุ
            if hasattr(position, 'time_open') and position.time_open:
                try:
                    if isinstance(position.time_open, datetime):
                        age_delta = datetime.now() - position.time_open
                    else:
                        age_delta = datetime.now() - datetime.fromtimestamp(position.time_open)
                    zone_position.age_minutes = age_delta.total_seconds() / 60
                except:
                    zone_position.age_minutes = 0.0
            
            # เพิ่มเข้า Zone
            zone.positions.append(zone_position)
            
            if zone_position.type == 0:  # BUY
                zone.buy_positions.append(zone_position)
                zone.buy_count += 1
            else:  # SELL
                zone.sell_positions.append(zone_position)
                zone.sell_count += 1
                
            zone.total_positions += 1
            zone.total_volume += zone_position.volume
            zone.total_pnl += zone_position.profit
            
            if zone_position.profit > 0:
                zone.profit_positions += 1
            else:
                zone.loss_positions += 1
                
            zone.last_updated = datetime.now()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error adding position to zone: {e}")
            return False
    
    def update_zones_from_positions(self, positions: List[Any], current_price: float) -> bool:
        """
        อัพเดท Zones จาก Positions ทั้งหมด
        
        Args:
            positions: รายการ Positions
            current_price: ราคาปัจจุบัน
            
        Returns:
            bool: สำเร็จหรือไม่
        """
        try:
            # ล้าง Zones เดิม
            self.clear_zones()
            
            # เพิ่ม Positions เข้า Zones
            for position in positions:
                self.add_position_to_zone(position, current_price)
            
            # คำนวณ Zone Health
            self.calculate_all_zone_health()
            
            # อัพเดทสถิติ
            self.total_positions = len(positions)
            self.last_update = datetime.now()
            
            # จำกัดจำนวน Zones
            self.cleanup_inactive_zones()
            
            logger.debug(f"📊 Updated {len(self.active_zones)} zones from {len(positions)} positions")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating zones: {e}")
            return False
    
    def clear_zones(self):
        """ล้าง Zones ทั้งหมด"""
        for zone in self.zones.values():
            zone.positions.clear()
            zone.buy_positions.clear()
            zone.sell_positions.clear()
            zone.buy_count = 0
            zone.sell_count = 0
            zone.total_positions = 0
            zone.total_volume = 0.0
            zone.total_pnl = 0.0
            zone.profit_positions = 0
            zone.loss_positions = 0
            zone.health_score = 0.0
            zone.balance_ratio = 0.5
            zone.available_profit = 0.0
            zone.help_needed = 0.0
            zone.status = 'NEUTRAL'
    
    def calculate_zone_health(self, zone: Zone) -> float:
        """
        คำนวณ Zone Health Score
        
        Args:
            zone: Zone ที่ต้องการคำนวณ
            
        Returns:
            float: Health Score (0-100)
        """
        if zone.total_positions == 0:
            return 0.0
            
        score = 50.0  # Base score
        
        # 1. P&L Score (40 คะแนน)
        if zone.total_pnl > 0:
            pnl_score = min(zone.total_pnl / 10, 40)  # $10 = 40 คะแนน
            score += pnl_score
        else:
            pnl_penalty = max(zone.total_pnl / 10, -40)  # -$10 = -40 คะแนน
            score += pnl_penalty
            
        # 2. Volume-Weighted Balance Score (30 คะแนน) - ปรับให้ดู Volume แทนจำนวน
        if zone.buy_count > 0 and zone.sell_count > 0:
            # มีทั้ง BUY และ SELL = ดี
            balance_bonus = 30
            
            # 🎯 คำนวณ Volume-Weighted Balance แทนการนับไม้
            buy_volume = sum(getattr(pos, 'volume', 0.01) for pos in zone.positions if getattr(pos, 'type', 0) == 0)
            sell_volume = sum(getattr(pos, 'volume', 0.01) for pos in zone.positions if getattr(pos, 'type', 0) == 1)
            total_volume = buy_volume + sell_volume
            
            if total_volume > 0:
                volume_buy_ratio = buy_volume / total_volume
                
                # ลดคะแนนถ้าเสียสมดุลมาก (ตาม Volume)
                if volume_buy_ratio < 0.2 or volume_buy_ratio > 0.8:  # เสียสมดุลมาก
                    balance_bonus *= 0.5
                elif volume_buy_ratio < 0.3 or volume_buy_ratio > 0.7:  # เสียสมดุลปานกลาง  
                    balance_bonus *= 0.7
                
                zone.balance_ratio = volume_buy_ratio
            else:
                # Fallback ถ้าไม่มี Volume data
                total = zone.buy_count + zone.sell_count
                buy_ratio = zone.buy_count / total if total > 0 else 0.5
                zone.balance_ratio = buy_ratio
                
            score += balance_bonus
        else:
            # มีฝั่งเดียว = ไม่ดี
            score -= 15
            zone.balance_ratio = 1.0 if zone.buy_count > 0 else 0.0
            
        # 3. Profit Ratio Score (20 คะแนน)
        if zone.total_positions > 0:
            profit_ratio = zone.profit_positions / zone.total_positions
            profit_score = profit_ratio * 20
            score += profit_score
            
        # 4. Position Count Score (10 คะแนน)
        if zone.total_positions >= 2:
            count_bonus = min(zone.total_positions * 2, 10)
            score += count_bonus
        
        # จำกัดช่วง 0-100
        zone.health_score = max(0.0, min(100.0, score))
        
        return zone.health_score
    
    def calculate_all_zone_health(self):
        """คำนวณ Health Score ทุก Zones"""
        for zone in self.zones.values():
            if zone.total_positions > 0:
                self.calculate_zone_health(zone)
                self.determine_zone_status(zone)
    
    def determine_zone_status(self, zone: Zone):
        """
        กำหนดสถานะ Zone
        
        Args:
            zone: Zone ที่ต้องการกำหนดสถานะ
        """
        if zone.total_positions == 0:
            zone.status = 'NEUTRAL'
            zone.available_profit = 0.0
            zone.help_needed = 0.0
            return
            
        # คำนวณ Support Capacity
        if zone.total_pnl > 0:
            # มีกำไร - สามารถช่วยได้
            zone.available_profit = zone.total_pnl * 0.8  # เก็บ 20% ไว้
            zone.help_needed = 0.0
        else:
            # ขาดทุน - ต้องการความช่วยเหลือ
            zone.available_profit = 0.0
            zone.help_needed = abs(zone.total_pnl)
            
        # กำหนดสถานะตาม Health Score และ P&L
        if zone.health_score >= 70 and zone.total_pnl > 0:
            zone.status = 'HELPER'
        elif zone.health_score <= 30 or zone.total_pnl < -50:
            zone.status = 'TROUBLED'
        elif zone.total_pnl < -100:
            zone.status = 'CRITICAL'
        else:
            zone.status = 'NEUTRAL'
    
    def get_helper_zones(self) -> List[Zone]:
        """ดึง Zones ที่สามารถช่วยเหลือได้"""
        return [zone for zone in self.zones.values() 
                if zone.status == 'HELPER' and zone.available_profit > 0]
    
    def get_troubled_zones(self) -> List[Zone]:
        """ดึง Zones ที่ต้องการความช่วยเหลือ"""
        return [zone for zone in self.zones.values() 
                if zone.status in ['TROUBLED', 'CRITICAL'] and zone.help_needed > 0]
    
    def cleanup_inactive_zones(self):
        """ลบ Zones ที่ไม่มี Positions"""
        inactive_zones = [zone_id for zone_id, zone in self.zones.items() 
                         if zone.total_positions == 0]
        
        for zone_id in inactive_zones:
            if zone_id in self.active_zones:
                self.active_zones.remove(zone_id)
                
        # จำกัดจำนวน Active Zones
        # 🚀 UNLIMITED ZONES: ยกเลิกการจำกัดจำนวน Zone เพื่อรองรับราคาที่วิ่งไกล
        # if len(self.active_zones) > self.max_zones:
        #     # เก็บ Zones ที่มี Positions เยอะที่สุด
        #     zone_scores = [(zone_id, self.zones[zone_id].total_positions) 
        #                   for zone_id in self.active_zones]
        #     zone_scores.sort(key=lambda x: x[1], reverse=True)
        #     
        #     self.active_zones = [zone_id for zone_id, _ in zone_scores[:self.max_zones]]
        logger.debug(f"🚀 UNLIMITED ZONES: Active zones: {len(self.active_zones)} (no limit)")
    
    def get_zone_summary(self) -> Dict[str, Any]:
        """
        ดึงสรุปข้อมูล Zones
        
        Returns:
            Dict: สรุปข้อมูล Zones
        """
        helper_zones = self.get_helper_zones()
        troubled_zones = self.get_troubled_zones()
        
        total_help_available = sum(zone.available_profit for zone in helper_zones)
        total_help_needed = sum(zone.help_needed for zone in troubled_zones)
        
        return {
            'total_zones': len(self.active_zones),
            'active_positions': self.total_positions,
            'helper_zones': len(helper_zones),
            'troubled_zones': len(troubled_zones),
            'total_help_available': total_help_available,
            'total_help_needed': total_help_needed,
            'rescue_feasible': total_help_available >= total_help_needed,
            'last_update': self.last_update,
            'zones': {zone_id: {
                'range': f"{zone.price_min:.2f}-{zone.price_max:.2f}",
                'positions': f"B{zone.buy_count}:S{zone.sell_count}",
                'pnl': zone.total_pnl,
                'health': zone.health_score,
                'status': zone.status
            } for zone_id, zone in self.zones.items() if zone.total_positions > 0}
        }
    
    def log_zone_status(self, detailed: bool = False):
        """
        แสดงสถานะ Zones ใน Log
        
        Args:
            detailed: แสดงรายละเอียดหรือไม่
        """
        summary = self.get_zone_summary()
        
        if summary['total_zones'] == 0:
            logger.info("📊 No active zones")
            return
            
        logger.info("=" * 50)
        logger.info("📊 ZONE STATUS REPORT")
        logger.info("=" * 50)
        
        for zone_id in sorted(self.active_zones):
            if zone_id in self.zones:
                zone = self.zones[zone_id]
                if zone.total_positions > 0:
                    status_emoji = {
                        'HELPER': '💚',
                        'TROUBLED': '🔴', 
                        'CRITICAL': '💀',
                        'NEUTRAL': '🟡'
                    }.get(zone.status, '⚪')
                    
                    logger.info(f"Zone {zone_id:2d} [{zone.price_min:.2f}-{zone.price_max:.2f}]: "
                              f"B{zone.buy_count}:S{zone.sell_count} | "
                              f"P&L: ${zone.total_pnl:+.2f} | "
                              f"Health: {zone.health_score:.0f} | "
                              f"Status: {zone.status} {status_emoji}")
        
        logger.info("-" * 50)
        logger.info(f"📈 Summary: {summary['total_zones']} zones, "
                   f"{summary['helper_zones']} helpers, "
                   f"{summary['troubled_zones']} troubled")
        
        if summary['troubled_zones'] > 0:
            logger.info(f"🚨 Rescue: ${summary['total_help_available']:.2f} available, "
                       f"${summary['total_help_needed']:.2f} needed - "
                       f"{'✅ FEASIBLE' if summary['rescue_feasible'] else '❌ INSUFFICIENT'}")
        
        logger.info("=" * 50)


# ==========================================
# 🎯 HELPER FUNCTIONS
# ==========================================

def create_zone_manager(zone_size_pips: float = 30.0, max_zones: int = 100) -> ZoneManager:
    """
    สร้าง Zone Manager instance
    
    Args:
        zone_size_pips: ขนาด Zone ในหน่วย pips
        max_zones: จำนวน Zone สูงสุด
        
    Returns:
        ZoneManager: Zone Manager instance
    """
    return ZoneManager(zone_size_pips=zone_size_pips, max_zones=max_zones)

def demo_zone_system():
    """Demo การทำงานของ Zone System"""
    logger.info("🎯 Zone System Demo")
    
    # สร้าง Zone Manager
    zm = create_zone_manager(zone_size_pips=30.0)
    
    # จำลอง Positions
    class MockPosition:
        def __init__(self, ticket, type, volume, price_open, profit):
            self.ticket = ticket
            self.type = type
            self.volume = volume
            self.price_open = price_open
            self.profit = profit
            self.symbol = 'XAUUSD'
            self.time_open = datetime.now()
    
    positions = [
        MockPosition(1, 0, 0.1, 2600.0, 50.0),   # BUY Zone 0
        MockPosition(2, 1, 0.1, 2610.0, -30.0),  # SELL Zone 0  
        MockPosition(3, 0, 0.2, 2650.0, -80.0),  # BUY Zone 1
        MockPosition(4, 1, 0.1, 2655.0, 40.0),   # SELL Zone 1
        MockPosition(5, 0, 0.1, 2680.0, 25.0),   # BUY Zone 2
    ]
    
    current_price = 2640.0
    
    # อัพเดท Zones
    zm.update_zones_from_positions(positions, current_price)
    
    # แสดงผล
    zm.log_zone_status(detailed=True)

if __name__ == "__main__":
    # ตั้งค่า Logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    # รัน Demo
    demo_zone_system()
