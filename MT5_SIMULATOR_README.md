# 🎯 MT5 Trading Simulator

หน้าต่างการจำลองการเข้าไม้แบบ MT5 แบบ Real-time พร้อมกราฟและแสดงการเข้าออกไม้แบบ Visual

## ✨ Features

### 📈 **Real-time Price Chart**
- แสดงกราฟราคาแบบ Real-time
- รองรับหลาย Symbol (XAUUSD, EURUSD, GBPUSD, USDJPY)
- แสดงเส้นราคาแบบ Live Update

### 🎮 **Visual Trading**
- แสดงการเข้าไม้แบบ Visual (BUY = ▲, SELL = ▼)
- แสดงการปิดไม้แบบ Real-time
- Markers สีเขียวสำหรับ BUY, สีแดงสำหรับ SELL

### 📊 **Trading Information**
- แสดง Position ที่เปิดอยู่
- แสดง Pending Orders
- สถิติการเทรดแบบ Real-time

### 🎯 **Manual Trading**
- เปิด Position ด้วยตนเอง
- ปรับ Volume ได้
- ควบคุมการเทรดแบบ Manual

### 🔗 **System Integration**
- เชื่อมต่อกับระบบเทรดหลัก
- แสดงการเข้าออกไม้จากระบบจริง
- รองรับทั้ง Simulation และ Real Trading

## 🚀 การใช้งาน

### 1. ติดตั้ง Dependencies
```bash
pip install -r requirements_simulator.txt
```

### 2. รัน Simulator
```bash
python run_simulator.py
```

### 3. ใช้งาน Simulator
1. เลือก Symbol ที่ต้องการ
2. กดปุ่ม "▶️ Start Simulation"
3. ดูกราฟและข้อมูลการเทรดแบบ Real-time
4. ใช้ปุ่ม Manual Trading เพื่อเปิด Position

## 📁 ไฟล์ที่เกี่ยวข้อง

### Core Files
- `mt5_simulator_gui.py` - หน้าต่าง GUI หลัก
- `mt5_simulator_integration.py` - เชื่อมต่อกับระบบหลัก
- `run_simulator.py` - ไฟล์รันหลัก

### Configuration
- `requirements_simulator.txt` - Dependencies
- `MT5_SIMULATOR_README.md` - คู่มือการใช้งาน

## 🎮 การควบคุม

### ปุ่มควบคุม
- **▶️ Start Simulation** - เริ่มการจำลอง
- **⏹️ Stop Simulation** - หยุดการจำลอง
- **🗑️ Clear All** - ล้างข้อมูลทั้งหมด
- **🟢 BUY** - เปิด Position BUY
- **🔴 SELL** - เปิด Position SELL

### การตั้งค่า
- **Symbol Selection** - เลือกสัญลักษณ์การเทรด
- **Volume Input** - ปรับขนาด Lot
- **Manual Trading** - ควบคุมการเทรดด้วยตนเอง

## 📊 ข้อมูลที่แสดง

### Price Chart
- เส้นราคาแบบ Real-time
- Markers การเข้าไม้ (BUY/SELL)
- Markers การปิดไม้
- Grid และ Labels

### Positions Panel
- รายการ Position ที่เปิดอยู่
- ข้อมูล Ticket, Type, Volume, Price, Profit
- สีเขียวสำหรับ BUY, สีแดงสำหรับ SELL

### Orders Panel
- รายการ Pending Orders
- ข้อมูล Ticket, Type, Volume, Price

### Statistics Panel
- Total Profit
- Total Positions
- BUY/SELL Count
- Total Volume
- Pending Orders
- Price Points
- Last Update Time

## 🔧 การปรับแต่ง

### สี
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

### การอัพเดท
- **Price Update**: ทุก 1 วินาที
- **Position Update**: ทุก 0.5 วินาที
- **Chart Update**: ทุก 1 วินาที

## 🐛 Troubleshooting

### ปัญหาที่อาจเกิดขึ้น
1. **Import Error**: ตรวจสอบว่าได้ติดตั้ง dependencies แล้ว
2. **MT5 Connection Error**: ตรวจสอบการเชื่อมต่อ MT5
3. **Chart Not Updating**: ตรวจสอบว่าได้กดปุ่ม Start Simulation

### การแก้ไข
1. ติดตั้ง dependencies ใหม่
2. ตรวจสอบการเชื่อมต่อ MT5
3. รีสตาร์ท Simulator

## 📝 Notes

- Simulator นี้ทำงานแยกจากระบบหลัก
- ไม่มีการแก้ไขไฟล์เดิม
- รองรับทั้ง Simulation และ Real Trading
- ใช้ Threading สำหรับ Real-time Updates

## 🎯 Future Features

- [ ] รองรับ Multiple Timeframes
- [ ] แสดง Technical Indicators
- [ ] รองรับ Order Management
- [ ] แสดง Trading History
- [ ] รองรับ Custom Themes
- [ ] แสดง Risk Management Info

---

**AUTHOR**: Advanced Trading System  
**VERSION**: 1.0.0 - MT5 Simulator Edition  
**DATE**: 2024
