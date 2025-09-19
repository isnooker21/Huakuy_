# 🎯 วิธีการใช้งาน MT5 Simulator

## 🚀 การเริ่มต้น

### 1. ติดตั้ง Dependencies
```bash
pip install matplotlib numpy pandas
```

### 2. รัน Simulator
```bash
python test_simulator.py
```

หรือ

```bash
python run_simulator.py
```

## 🎮 การใช้งาน

### หน้าต่างหลัก
เมื่อรัน Simulator จะเห็นหน้าต่างหลักที่มี:

1. **Control Panel** (ด้านบน)
   - เลือก Symbol (XAUUSD, EURUSD, GBPUSD, USDJPY)
   - ปุ่ม Start/Stop Simulation
   - ปุ่ม Clear All

2. **Price Chart** (ด้านซ้าย)
   - กราฟราคาแบบ Real-time
   - แสดงการเข้าไม้ (BUY = ▲, SELL = ▼)
   - แสดงการปิดไม้

3. **Trading Info** (ด้านขวา)
   - Open Positions
   - Pending Orders
   - Trading Controls
   - Statistics

### การควบคุม

#### เริ่มการจำลอง
1. เลือก Symbol ที่ต้องการ
2. กดปุ่ม "▶️ Start Simulation"
3. ดูกราฟและข้อมูลการเทรดแบบ Real-time

#### การเทรดด้วยตนเอง
1. ใส่ Volume ที่ต้องการ (เช่น 0.01)
2. กดปุ่ม "🟢 BUY" เพื่อเปิด Position BUY
3. กดปุ่ม "🔴 SELL" เพื่อเปิด Position SELL

#### การหยุดการจำลอง
1. กดปุ่ม "⏹️ Stop Simulation"
2. กดปุ่ม "🗑️ Clear All" เพื่อล้างข้อมูล

## 📊 ข้อมูลที่แสดง

### Price Chart
- **เส้นราคา**: แสดงราคาปัจจุบันแบบ Real-time
- **BUY Markers**: ▲ สีเขียว แสดงการเข้าไม้ BUY
- **SELL Markers**: ▼ สีแดง แสดงการเข้าไม้ SELL
- **Close Markers**: ● สีเหลือง แสดงการปิดไม้

### Positions Panel
แสดง Position ที่เปิดอยู่:
- **Ticket**: หมายเลข Position
- **Type**: ประเภท (🟢 BUY หรือ 🔴 SELL)
- **Volume**: ขนาด Lot
- **Price**: ราคาที่เปิด
- **Profit**: กำไร/ขาดทุน

### Orders Panel
แสดง Pending Orders:
- **Ticket**: หมายเลข Order
- **Type**: ประเภท (🟢 BUY หรือ 🔴 SELL)
- **Volume**: ขนาด Lot
- **Price**: ราคาที่ตั้ง

### Statistics Panel
แสดงสถิติการเทรด:
- **Total Profit**: กำไรรวม
- **Total Positions**: จำนวน Position ทั้งหมด
- **BUY Positions**: จำนวน Position BUY
- **SELL Positions**: จำนวน Position SELL
- **Total Volume**: ปริมาณ Lot รวม
- **Pending Orders**: จำนวน Order ที่รอ
- **Price Points**: จำนวนจุดราคา
- **Last Update**: เวลาอัพเดทล่าสุด

## 🔧 การปรับแต่ง

### เปลี่ยน Symbol
1. เลือกจาก Dropdown Menu
2. กราฟจะอัพเดทตาม Symbol ใหม่

### เปลี่ยน Volume
1. ใส่ตัวเลขในช่อง Volume
2. กดปุ่ม BUY/SELL

### เปลี่ยนสี
แก้ไขในไฟล์ `mt5_simulator_gui.py`:
```python
self.colors = {
    'background': '#1e1e1e',
    'foreground': '#ffffff',
    'buy': '#00ff00',
    'sell': '#ff0000',
    'close': '#ffff00',
    'price': '#00bfff',
    'grid': '#333333'
}
```

## 🐛 การแก้ไขปัญหา

### ปัญหา: Import Error
**แก้ไข**: ติดตั้ง dependencies
```bash
pip install matplotlib numpy pandas
```

### ปัญหา: Chart ไม่แสดง
**แก้ไข**: ตรวจสอบว่าได้กดปุ่ม Start Simulation

### ปัญหา: ข้อมูลไม่อัพเดท
**แก้ไข**: รีสตาร์ท Simulator

### ปัญหา: MT5 Connection Error
**แก้ไข**: ตรวจสอบการเชื่อมต่อ MT5 หรือใช้ Simulation Mode

## 💡 Tips

1. **เริ่มต้น**: ใช้ Simulation Mode ก่อน
2. **ทดสอบ**: ใช้ Manual Trading เพื่อทดสอบ
3. **ดูสถิติ**: ตรวจสอบ Statistics Panel
4. **เปลี่ยน Symbol**: ลองใช้ Symbol ต่างๆ
5. **Clear Data**: ใช้ Clear All เมื่อต้องการเริ่มใหม่

## 🎯 การใช้งานขั้นสูง

### เชื่อมต่อกับระบบจริง
1. ใช้ `run_simulator.py` แทน `test_simulator.py`
2. ตรวจสอบการเชื่อมต่อ MT5
3. ดูการเข้าออกไม้จากระบบจริง

### ปรับแต่งการอัพเดท
แก้ไขในไฟล์ `mt5_simulator_gui.py`:
```python
time.sleep(1)  # เปลี่ยนเป็น 0.5 สำหรับอัพเดทเร็วขึ้น
```

### เพิ่ม Symbol ใหม่
แก้ไขในไฟล์ `mt5_simulator_gui.py`:
```python
symbol_combo = ttk.Combobox(symbol_frame, textvariable=self.symbol_var, 
                           values=["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "NEW_SYMBOL"], 
                           width=10, state="readonly")
```

---

**AUTHOR**: Advanced Trading System  
**VERSION**: 1.0.0 - How to Use Edition  
**DATE**: 2024
