# -*- coding: utf-8 -*-
"""
Group Closing Manager Example
ตัวอย่างการใช้งานระบบ Group Closing Manager
"""

import logging
from group_closing_manager import GroupClosingManager
from position_status_manager import PositionStatusManager
from order_management import OrderManager
from mt5_connection import MT5Connection

# ตั้งค่า logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def example_usage():
    """ตัวอย่างการใช้งานระบบ Group Closing Manager"""
    
    # 1. สร้างการเชื่อมต่อ
    mt5_connection = MT5Connection()
    order_manager = OrderManager(mt5_connection)
    status_manager = PositionStatusManager()
    group_closer = GroupClosingManager(order_manager, mt5_connection)
    
    # 2. ข้อมูลตัวอย่าง
    positions = [
        # Protected Position
        type('Position', (), {
            'ticket': 1001,
            'type': 0,  # BUY
            'profit': -25.50,
            'price_open': 2000.0,
            'price_current': 1995.0
        })(),
        
        # HG Position
        type('Position', (), {
            'ticket': 1002,
            'type': 1,  # SELL
            'profit': 15.30,
            'price_open': 2005.0,
            'price_current': 1995.0
        })(),
        
        # Profit Helper 1 (ไกลจากราคาปัจจุบัน)
        type('Position', (), {
            'ticket': 1003,
            'type': 0,  # BUY
            'profit': 8.20,
            'price_open': 1980.0,
            'price_current': 1995.0
        })(),
        
        # Profit Helper 2 (ใกล้จากราคาปัจจุบัน)
        type('Position', (), {
            'ticket': 1004,
            'type': 1,  # SELL
            'profit': 12.40,
            'price_open': 2010.0,
            'price_current': 1995.0
        })(),
        
        # Standalone Position
        type('Position', (), {
            'ticket': 1005,
            'type': 0,  # BUY
            'profit': 5.80,
            'price_open': 1990.0,
            'price_current': 1995.0
        })()
    ]
    
    # 3. วิเคราะห์สถานะไม้
    current_price = 1995.0
    position_statuses = status_manager.analyze_all_positions(positions, current_price, [])
    
    logger.info("📊 Position Statuses:")
    for ticket, status_obj in position_statuses.items():
        logger.info(f"   #{ticket}: {status_obj.status}")
    
    # 4. วิเคราะห์โอกาสปิดกลุ่ม
    logger.info("\n🔍 Analyzing closing opportunities...")
    closing_groups = group_closer.analyze_closing_opportunities(
        positions, position_statuses, current_price
    )
    
    # 5. แสดงผลลัพธ์
    logger.info(f"\n📋 Found {len(closing_groups)} closing groups:")
    for group in closing_groups:
        logger.info(f"\n🎯 Group {group.group_id}:")
        logger.info(f"   Type: {group.group_type}")
        logger.info(f"   Positions: {len(group.positions)}")
        logger.info(f"   Total Profit: ${group.total_profit:.2f}")
        logger.info(f"   Min Required: ${group.min_profit_required:.2f}")
        logger.info(f"   Can Close: {group.can_close}")
        logger.info(f"   Reason: {group.reason}")
        
        if group.can_close:
            logger.info("   ✅ Ready to close!")
        else:
            logger.info("   ⚠️ Needs more profit")
    
    # 6. ปิดกลุ่มที่พร้อมปิด
    for group in closing_groups:
        if group.can_close:
            logger.info(f"\n🚀 Executing group closing for {group.group_id}...")
            result = group_closer.execute_group_closing(group)
            
            if result['success']:
                logger.info(f"✅ Successfully closed group: {result['message']}")
                logger.info(f"   Closed positions: {result['closed_count']}")
                logger.info(f"   Total profit: ${result['total_profit']:.2f}")
            else:
                logger.error(f"❌ Failed to close group: {result['message']}")
    
    # 7. แสดงสถิติ
    stats = group_closer.get_closing_statistics()
    logger.info(f"\n📊 Closing Statistics:")
    logger.info(f"   Total groups analyzed: {stats['total_groups_analyzed']}")
    logger.info(f"   Successful groups: {stats['successful_groups']}")
    logger.info(f"   Success rate: {stats['success_rate']:.1f}%")

def advanced_usage():
    """ตัวอย่างการใช้งานขั้นสูง"""
    
    # สร้างระบบ
    mt5_connection = MT5Connection()
    order_manager = OrderManager(mt5_connection)
    group_closer = GroupClosingManager(order_manager, mt5_connection)
    
    # ตั้งค่าการปิดกลุ่ม
    group_closer.min_profit_config['base_amount'] = 3.0  # เพิ่มกำไรขั้นต่ำ
    group_closer.min_profit_config['multiplier'] = 2.0   # เพิ่มคูณตามจำนวนไม้
    
    # ตั้งค่าการเลือก Helper
    group_closer.group_settings['helper_selection_radius'] = 100.0  # เพิ่มรัศมีเลือก Helper
    
    logger.info("🔧 Advanced configuration applied")
    
    # ตัวอย่างการวิเคราะห์แบบต่อเนื่อง
    logger.info("🔄 Starting continuous analysis...")
    
    for i in range(3):  # วิเคราะห์ 3 รอบ
        logger.info(f"\n--- Analysis Round {i+1} ---")
        
        # จำลองข้อมูล Position (ในระบบจริงจะดึงจาก MT5)
        positions = create_sample_positions(i)
        
        # วิเคราะห์สถานะ
        status_manager = PositionStatusManager()
        position_statuses = status_manager.analyze_all_positions(positions, 1995.0, [])
        
        # วิเคราะห์โอกาสปิด
        closing_groups = group_closer.analyze_closing_opportunities(
            positions, position_statuses, 1995.0
        )
        
        logger.info(f"Found {len(closing_groups)} groups in round {i+1}")
        
        # ปิดกลุ่มที่พร้อม
        for group in closing_groups:
            if group.can_close:
                result = group_closer.execute_group_closing(group)
                logger.info(f"Group {group.group_id}: {result['message']}")
    
    # แสดงสถิติสุดท้าย
    stats = group_closer.get_closing_statistics()
    logger.info(f"\n📊 Final Statistics: {stats}")

def create_sample_positions(round_num: int):
    """สร้างข้อมูล Position ตัวอย่าง"""
    positions = []
    
    # สร้าง Position ตามรอบ
    for i in range(3 + round_num):
        ticket = 2000 + i
        pos_type = i % 2  # สลับ BUY/SELL
        profit = (i - 1) * 10.0  # กำไร/ขาดทุนสลับกัน
        
        position = type('Position', (), {
            'ticket': ticket,
            'type': pos_type,
            'profit': profit,
            'price_open': 2000.0 + (i * 5),
            'price_current': 1995.0,
            'swap': 0.0,
            'commission': 0.0
        })()
        
        positions.append(position)
    
    return positions

if __name__ == "__main__":
    logger.info("🚀 Starting Group Closing Manager Example")
    
    # ตัวอย่างพื้นฐาน
    example_usage()
    
    # ตัวอย่างขั้นสูง
    advanced_usage()
    
    logger.info("✅ Example completed")
