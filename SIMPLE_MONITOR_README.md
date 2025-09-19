# 🎯 Simple Trading Monitor

แสดงข้อมูลการเข้าไม้และราคาปัจจุบันแบบง่ายๆ ไม่มีกราฟซับซ้อน

## ✨ Features

### 💰 **Current Price Display**
- แสดงราคาปัจจุบันแบบ Real-time
- รองรับหลาย Symbol (XAUUSD, EURUSD, GBPUSD, USDJPY)
- อัพเดททุก 1 วินาที

### 📈 **Recent Trades**
- แสดงการเข้าไม้แบบ Real-time
- แสดงการปิดไม้พร้อมกำไร/ขาดทุน
- เก็บประวัติ 50 การเทรดล่าสุด

### 📊 **Open Positions**
- แสดง Position ที่เปิดอยู่
- ข้อมูล Ticket, Type, Volume, Price, Profit
- อัพเดทแบบ Real-time

### 📈 **Statistics**
- ราคาปัจจุบัน
- จำนวน Position ที่เปิดอยู่
- จำนวน BUY/SELL Positions
- Total Volume และ Total Profit
- เวลาอัพเดทล่าสุด

## 🚀 การใช้งาน

### 1. รัน Monitor
```bash
python test_simple_monitor.py
```

### 2. ใช้งาน Monitor
1. เลือก **Symbol** ที่ต้องการ
2. กดปุ่ม **"▶️ Start Monitor"**
3. ดูข้อมูลการเทรดแบบ Real-time
4. ดูราคาปัจจุบันและ Position ที่เปิดอยู่

## 📁 ไฟล์ที่เกี่ยวข้อง

### Core Files
- `simple_trading_monitor.py` - Monitor หลัก
- `test_simple_monitor.py` - ไฟล์ทดสอบ

## 🎮 การควบคุม

### ปุ่มควบคุม
- **▶️ Start Monitor** - เริ่มการตรวจสอบ
- **⏹️ Stop Monitor** - หยุดการตรวจสอบ
- **🗑️ Clear All** - ล้างข้อมูลทั้งหมด

### การตั้งค่า
- **Symbol Selection** - เลือกสัญลักษณ์การเทรด
- **Auto Update** - อัพเดทอัตโนมัติทุก 1 วินาที

## 📊 ข้อมูลที่แสดง

### Current Price
- ราคาปัจจุบันแบบ Real-time
- แสดงเป็นตัวเลขใหญ่
- อัพเดททุก 1 วินาที

### Recent Trades
- การเข้าไม้ (BUY/SELL)
- การปิดไม้พร้อมกำไร/ขาดทุน
- เวลาและราคา
- เก็บประวัติ 50 การเทรดล่าสุด

### Open Positions
- รายการ Position ที่เปิดอยู่
- ข้อมูล Ticket, Type, Volume, Price, Profit
- สีเขียวสำหรับ BUY, สีแดงสำหรับ SELL

### Statistics
- Current Price
- Open Positions Count
- BUY/SELL Count
- Total Volume
- Total Profit
- Last Update Time

## 🔧 การปรับแต่ง

### เปลี่ยน Symbol
1. เลือกจาก Dropdown Menu
2. ข้อมูลจะอัพเดทตาม Symbol ใหม่

### เปลี่ยนการอัพเดท
แก้ไขในไฟล์ `simple_trading_monitor.py`:
```python
time.sleep(1)  # เปลี่ยนเป็น 0.5 สำหรับอัพเดทเร็วขึ้น
```

### เปลี่ยนสี
แก้ไขในไฟล์ `simple_trading_monitor.py`:
```python
self.colors = {
    'background': '#1e1e1e',
    'foreground': '#ffffff',
    'buy': '#00ff00',
    'sell': '#ff0000',
    'price': '#00bfff',
    'profit': '#00ff00',
    'loss': '#ff0000'
}
```

## 🐛 การแก้ไขปัญหา

### ปัญหา: Import Error
**แก้ไข**: tkinter มักจะติดตั้งมาพร้อม Python
- **macOS**: `brew install python-tk`
- **Ubuntu/Debian**: `sudo apt-get install python3-tk`

### ปัญหา: ข้อมูลไม่อัพเดท
**แก้ไข**: ตรวจสอบว่าได้กดปุ่ม Start Monitor

### ปัญหา: MT5 Connection Error
**แก้ไข**: ตรวจสอบการเชื่อมต่อ MT5 หรือใช้ Simulation Mode

## 💡 Tips

1. **เริ่มต้น**: ใช้ Simulation Mode ก่อน
2. **ดูข้อมูล**: ตรวจสอบ Recent Trades และ Statistics
3. **เปลี่ยน Symbol**: ลองใช้ Symbol ต่างๆ
4. **Clear Data**: ใช้ Clear All เมื่อต้องการเริ่มใหม่

## 🎯 การใช้งานขั้นสูง

### เชื่อมต่อกับระบบจริง
1. ตรวจสอบการเชื่อมต่อ MT5
2. ดูการเข้าออกไม้จากระบบจริง
3. ข้อมูลจะอัพเดทแบบ Real-time

### ปรับแต่งการแสดงผล
แก้ไขในไฟล์ `simple_trading_monitor.py`:
```python
# เปลี่ยนจำนวนบรรทัดที่เก็บ
if len(lines) > 50:  # เปลี่ยนเป็น 100 สำหรับเก็บมากขึ้น
```

---

**AUTHOR**: Advanced Trading System  
**VERSION**: 1.0.0 - Simple Monitor Edition  
**DATE**: 2024
