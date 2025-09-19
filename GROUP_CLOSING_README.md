# 🎯 Group Closing Manager

ระบบปิดออเดอร์แบบกลุ่ม (Group Closing) ที่รับสถานะไม้จาก Order Tracking System และสามารถรวมกลุ่ม Protected + HG + Profit Helper เพื่อปิดพร้อมกัน

## 📋 ภาพรวม

ระบบ Group Closing Manager ถูกออกแบบมาเพื่อ:
- รับสถานะไม้จาก `position_status_manager.py`
- รวมกลุ่ม Protected + HG ที่จับคู่กันอยู่แล้ว
- เลือก Profit Helper จากขอบนอกสุด (ไกลจากราคาปัจจุบันที่สุด)
- คำนวณกำไรขั้นต่ำแบบ Dynamic
- ปิดหลายไม้พร้อมกันในคำสั่งเดียว

## 🔧 ฟีเจอร์หลัก

### 1. Integration กับ Position Status Manager
- รับสถานะไม้: HG, Protected, Support Guard, Profit Helper, Standalone
- ใช้ข้อมูล relationships ที่มีอยู่แล้ว
- วิเคราะห์ความสัมพันธ์ระหว่างไม้

### 2. Group Formation Logic
- รวมกลุ่ม Protected + HG ที่จับคู่กันอยู่แล้ว
- คำนวณกำไร/ขาดทุนรวมของกลุ่ม
- หา Profit Helper เพิ่มเติมถ้าจำเป็น

### 3. Profit Helper Selection
- เลือกจากขอบนอกสุด (ไกลจากราคาปัจจุบันที่สุด) ก่อนเสมอ
- เรียงลำดับระยะห่างจากราคาปัจจุบัน: ไกลสุด → ใกล้สุด
- เลือกทีละตัวจนกว่ากำไรรวมจะเป็นบวก

### 4. Dynamic Minimum Profit
- กำไรขั้นต่ำปรับตามจำนวนไม้ในกลุ่ม
- สูตร: `min_profit = base_amount + (position_count * multiplier)`
- ตัวอย่าง: 2-3 ไม้ = +$2, 4-6 ไม้ = +$5, 7+ ไม้ = +$10

### 5. Group Closing Execution
- ปิดหลายไม้พร้อมกันในคำสั่งเดียว
- ตรวจสอบ Zero Loss Policy ก่อนปิด
- รองรับ Error Handling และ Rollback

## 🚀 การใช้งาน

### การตั้งค่าเบื้องต้น

```python
from group_closing_manager import GroupClosingManager
from position_status_manager import PositionStatusManager
from order_management import OrderManager
from mt5_connection import MT5Connection

# สร้างการเชื่อมต่อ
mt5_connection = MT5Connection()
order_manager = OrderManager(mt5_connection)
status_manager = PositionStatusManager()
group_closer = GroupClosingManager(order_manager, mt5_connection)
```

### การวิเคราะห์โอกาสปิดกลุ่ม

```python
# วิเคราะห์สถานะไม้
position_statuses = status_manager.analyze_all_positions(positions, current_price, zones)

# วิเคราะห์โอกาสปิดกลุ่ม
closing_groups = group_closer.analyze_closing_opportunities(
    positions, position_statuses, current_price
)

# แสดงผลลัพธ์
for group in closing_groups:
    print(f"Group {group.group_id}: {group.group_type}")
    print(f"  Positions: {len(group.positions)}")
    print(f"  Total Profit: ${group.total_profit:.2f}")
    print(f"  Can Close: {group.can_close}")
```

### การปิดกลุ่ม

```python
# ปิดกลุ่มที่พร้อมปิด
for group in closing_groups:
    if group.can_close:
        result = group_closer.execute_group_closing(group)
        
        if result['success']:
            print(f"✅ Successfully closed group: {result['message']}")
            print(f"   Closed positions: {result['closed_count']}")
            print(f"   Total profit: ${result['total_profit']:.2f}")
        else:
            print(f"❌ Failed to close group: {result['message']}")
```

## ⚙️ การตั้งค่า

### Dynamic Minimum Profit Configuration

```python
group_closer.min_profit_config = {
    'base_amount': 2.0,      # กำไรขั้นต่ำพื้นฐาน
    'multiplier': 1.5,       # คูณตามจำนวนไม้
    'max_amount': 20.0,      # กำไรสูงสุด
    'group_type_multipliers': {
        'PROTECTED_HG': 1.0,
        'PROTECTED_HG_HELPER': 1.2,
        'MULTI_GROUP': 1.5
    }
}
```

### Group Formation Settings

```python
group_closer.group_settings = {
    'max_group_size': 10,        # จำนวนไม้สูงสุดในกลุ่ม
    'min_profit_margin': 0.1,    # กำไรขั้นต่ำ 10%
    'max_loss_tolerance': -5.0,  # ขาดทุนสูงสุดที่ยอมรับ
    'helper_selection_radius': 50.0  # ระยะห่างสูงสุดสำหรับเลือก Helper
}
```

## 📊 ข้อมูลที่ส่งคืน

### ClosingGroup

```python
@dataclass
class ClosingGroup:
    group_id: str                    # ID ของกลุ่ม
    group_type: str                  # ประเภทกลุ่ม
    positions: List[Any]             # รายการ Position ในกลุ่ม
    total_profit: float              # กำไรรวม
    min_profit_required: float       # กำไรขั้นต่ำที่ต้องการ
    can_close: bool                  # สามารถปิดได้หรือไม่
    reason: str                      # เหตุผล
    protected_positions: List[Any]   # ไม้ Protected
    hg_positions: List[Any]          # ไม้ HG
    helper_positions: List[Any]      # ไม้ Helper
    created_time: float              # เวลาที่สร้าง
```

### ProfitHelperSelection

```python
@dataclass
class ProfitHelperSelection:
    selected_helpers: List[Any]      # ไม้ Helper ที่เลือก
    total_helper_profit: float       # กำไรรวมของ Helper
    distance_from_price: List[float] # ระยะห่างจากราคาปัจจุบัน
    selection_reason: str            # เหตุผลการเลือก
```

## 🔄 การทำงานของระบบ

### 1. Group Formation Flow
```
Analyze Position Statuses → Find Protected Positions → Find HG Positions
↓
Calculate Group Profit → Check if Helper Needed → Select Helpers from Edge
↓
Form Closing Groups → Check Zero Loss Policy → Ready to Close
```

### 2. Helper Selection Flow
```
Get Available Helpers → Calculate Distance from Current Price
↓
Sort by Distance (Farthest First) → Select One by One
↓
Check if Total Profit >= Amount Needed → Return Selected Helpers
```

### 3. Group Closing Flow
```
Check if Group Can Close → Verify Zero Loss Policy → Send to OrderManager
↓
Execute Group Closing → Update Position Status → Log Results
```

## 🎯 ตัวอย่างการใช้งาน

### ตัวอย่างพื้นฐาน

```python
# วิเคราะห์สถานะไม้
position_statuses = status_manager.analyze_all_positions(positions, current_price, zones)

# วิเคราะห์โอกาสปิดกลุ่ม
closing_groups = group_closer.analyze_closing_opportunities(
    positions, position_statuses, current_price
)

# ปิดกลุ่มที่พร้อมปิด
for group in closing_groups:
    if group.can_close:
        result = group_closer.execute_group_closing(group)
        print(f"Result: {result}")
```

### ตัวอย่างขั้นสูง

```python
# ตั้งค่าการปิดกลุ่ม
group_closer.min_profit_config['base_amount'] = 3.0
group_closer.min_profit_config['multiplier'] = 2.0

# วิเคราะห์แบบต่อเนื่อง
while True:
    positions = get_current_positions()
    position_statuses = status_manager.analyze_all_positions(positions, current_price, zones)
    closing_groups = group_closer.analyze_closing_opportunities(positions, position_statuses, current_price)
    
    for group in closing_groups:
        if group.can_close:
            result = group_closer.execute_group_closing(group)
            handle_closing_result(result)
    
    time.sleep(5)  # รอ 5 วินาที
```

## 🛠️ การแก้ไขปัญหา

### ปัญหาที่พบบ่อย

1. **No groups found**
   - ตรวจสอบว่ามีไม้ Protected และ HG หรือไม่
   - ตรวจสอบการวิเคราะห์สถานะไม้

2. **Group cannot close**
   - ตรวจสอบกำไรรวมของกลุ่ม
   - ตรวจสอบกำไรขั้นต่ำที่ต้องการ

3. **Helper selection failed**
   - ตรวจสอบว่ามีไม้ Profit Helper หรือไม่
   - ตรวจสอบระยะห่างจากราคาปัจจุบัน

### การ Debug

```python
# เปิด Debug Mode
logging.basicConfig(level=logging.DEBUG)

# ตรวจสอบสถิติ
stats = group_closer.get_closing_statistics()
print(f"Statistics: {stats}")

# ตรวจสอบประวัติ
for group in group_closer.closing_history:
    print(f"Group {group.group_id}: {group.reason}")
```

## 📈 Performance Tips

1. **จำกัดขนาดกลุ่ม** - ตั้งค่า `max_group_size` ให้เหมาะสม
2. **ปรับกำไรขั้นต่ำ** - ตั้งค่า `base_amount` และ `multiplier` ให้เหมาะสม
3. **จำกัดรัศมีเลือก Helper** - ตั้งค่า `helper_selection_radius` ให้เหมาะสม
4. **ล้างประวัติเป็นระยะ** - ใช้ `clear_history()` เพื่อประหยัด memory

## 🔒 ความปลอดภัย

- ตรวจสอบ Zero Loss Policy ก่อนปิดกลุ่ม
- ตรวจสอบการเชื่อมต่อ MT5 ก่อนส่งคำสั่ง
- มี Error Handling ที่ครอบคลุม
- Log การกระทำทั้งหมดเพื่อการตรวจสอบ

## 📝 ตัวอย่างการใช้งาน

ดูไฟล์ `GROUP_CLOSING_EXAMPLE.py` สำหรับตัวอย่างการใช้งานที่สมบูรณ์

## 🤝 การสนับสนุน

หากมีปัญหาหรือคำถาม กรุณาตรวจสอบ:
1. Log files สำหรับ error messages
2. Position status analysis
3. Group formation logic
4. Zero Loss Policy check
