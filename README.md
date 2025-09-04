# Trading System - Percentage Based Calculations

ระบบเทรดที่ใช้การคำนวณเป็นเปอร์เซ็นต์ สำหรับการเทรด XAUUSD (ทองคำ) และ Forex ผ่าน MetaTrader 5

## ⭐ คุณสมบัติหลัก

### 📊 การคำนวณเป็นเปอร์เซ็นต์
- **กำไร/ขาดทุนเป็น %** ของเงินทุน
- **แรงตลาดเป็น %** สำหรับกรองสัญญาณ
- **สมดุลพอร์ต Buy:Sell เป็น %**
- **ความเสี่ยงต่อ Trade เป็น %**
- **การใช้เงินทุนเป็น %**

### 🎯 เงื่อนไขการเทรด
- **Green Candle → BUY, Red Candle → SELL**
- **One Order per Candle** (ห้ามเปิดซ้อน)
- **Market Strength Filter** (แรงตลาด > 0.5%)
- **Volume Filter** (Volume > 120% ของค่าเฉลี่ย)
- **Portfolio Balance Control** (Buy:Sell ไม่เกิน 70:30)

### 🔐 การจัดการความเสี่ยง
- **Position Sizing** ตามเปอร์เซ็นต์ความเสี่ยง
- **Stop Loss** เป็นเปอร์เซ็นต์ของเงินทุน
- **Daily Loss Limit** (ขาดทุนสูงสุดต่อวัน)
- **Maximum Drawdown Control**
- **Emergency Close All** ในกรณีฉุกเฉิน

### 📈 การปิด Position
- **Group Close Only** (ปิดเป็นกลุ่มเท่านั้น)
- **Profit Target** เป็นเปอร์เซ็นต์
- **Pullback Wait Strategy** (รอ Pullback 0.3-0.5%)
- **Scaling Close** (1:1, 1:2, 1:3, 2:3)

## 🏗️ โครงสร้างโปรเจค

```
Huakuy_/
├── main_new.py              # ไฟล์หลักสำหรับเริ่มต้นระบบ
├── mt5_connection.py        # โมดูลเชื่อมต่อ MT5
├── trading_conditions.py   # โมดูลเงื่อนไขการเทรด
├── order_management.py     # โมดูลจัดการ Orders
├── calculations.py         # โมดูลคำนวณ Lot และเปอร์เซ็นต์
├── portfolio_manager.py    # โมดูลบริหารพอร์ต
├── gui.py                  # โมดูล GUI
├── requirements.txt        # Dependencies
├── README.md              # คู่มือการใช้งาน
└── trading_system.log     # Log file
```

## 🚀 การติดตั้งและใช้งาน

### ข้อกำหนดระบบ
- Python 3.8 หรือสูงกว่า
- MetaTrader 5 Terminal
- Windows OS (สำหรับ MT5 API)

### การติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```

### การเริ่มต้นใช้งาน

1. **เปิด MetaTrader 5** และล็อกอินบัญชี
2. **เปิดใช้งาน Algo Trading** ใน MT5
3. **รันระบบ:**
   ```bash
   python main_new.py
   ```

### การใช้งาน GUI

#### 🔌 การเชื่อมต่อ
- คลิก **"Connect MT5"** เพื่อเชื่อมต่อ
- ตรวจสอบสถานะ **"Connected"** เป็นสีเขียว

#### ▶️ การเริ่มเทรด
- คลิก **"Start Trading"** เพื่อเริ่มระบบอัตโนมัติ
- ระบบจะวิเคราะห์แท่งเทียนและส่ง Order ตามเงื่อนไข

#### ⏹️ การหยุดเทรด
- คลิก **"Stop Trading"** เพื่อหยุดระบบ
- คลิก **"Close All Positions"** เพื่อปิด Position ทั้งหมด

## 📊 การตรวจสอบผลการทำงาน

### แท็บ Account Information
- **Balance, Equity, Margin**
- **Margin Level** (เปลี่ยนสีตามระดับ)

### แท็บ Portfolio Balance
- **Buy:Sell Ratio** เป็นเปอร์เซ็นต์
- **Progress Bar** แสดงสัดส่วน
- **เตือนความไม่สมดุล** เมื่อเกิน 70%

### แท็บ Performance Metrics
- **Total P&L %** กำไรขาดทุนรวม
- **Daily P&L %** กำไรขาดทุนต่อวัน
- **Win Rate %** อัตราชนะ
- **Max Drawdown %** ขาดทุนสูงสุด
- **Profit Factor** อัตราส่วนกำไรต่อขาดทุน

### แท็บ Risk Management
- **Portfolio Risk %** ความเสี่ยงรวม
- **Exposure %** การใช้เงินทุน
- **Losing Positions** จำนวน Position ขาดทุน

### แท็บ Positions
- **รายการ Position** ทั้งหมด
- **คลิกขวา** เพื่อเมนูปิด Position
- **Scaling Close** แบบต่างๆ

### แท็บ Trading Log
- **Log แบบ Real-time** ทุกการทำงาน
- **สีแยกตาม Level** (Error=แดง, Warning=ส้ม, Info=เขียว)

### แท็บ Settings
- **Risk Settings** ปรับความเสี่ยง
- **Balance Settings** ปรับเกณฑ์สมดุล
- **Save Settings** บันทึกการตั้งค่า

## ⚙️ การตั้งค่าเริ่มต้น

### Risk Management (%)
- **Max Risk per Trade:** 2.0%
- **Max Portfolio Exposure:** 80.0%
- **Max Daily Loss:** 10.0%
- **Profit Target:** 2.0%
- **Max Drawdown Limit:** 15.0%

### Balance Control (%)
- **Balance Warning Threshold:** 70.0%
- **Balance Stop Threshold:** 80.0%
- **Min Market Strength:** 0.5%
- **Min Volume Percentage:** 120.0%

## 🔧 การปรับแต่ง

### แก้ไขการตั้งค่าใน Code
```python
# ใน main_new.py
trading_system = TradingSystem(
    initial_balance=10000.0,  # เงินทุนเริ่มต้น
    symbol="XAUUSD"           # สัญลักษณ์การเทรด (ทองคำ)
)

# ใน portfolio_manager.py
self.max_risk_per_trade = 2.0      # ความเสี่ยงต่อ Trade
self.profit_target = 2.0           # เป้าหมายกำไร
self.max_daily_loss = 10.0         # ขาดทุนสูงสุดต่อวัน
```

### เพิ่มสัญลักษณ์การเทรด
แก้ไขในไฟล์ `main_new.py`:
```python
symbols = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY"]
for symbol in symbols:
    # สร้าง trading system แยกต่างหาก
```

### คุณสมบัติใหม่ที่เพิ่ม
- **🔍 Auto Symbol Detection**: ค้นหาสัญลักษณ์ทองคำในโบรกเกอร์อัตโนมัติ
- **⚡ Smart Filling Type**: ตรวจสอบและจดจำ filling type ที่ใช้ได้
- **💰 Gold-Specific Calculations**: คำนวณ lot size พิเศษสำหรับทองคำ
- **🎯 Broker Compatibility**: รองรับโบรกเกอร์ต่างๆ ที่มีสัญลักษณ์ทองคำแตกต่างกัน

## 📝 Log Files

ระบบจะสร้างไฟล์ Log:
- **trading_system.log** - บันทึกการทำงานทั้งหมด
- **ใช้ UTF-8 encoding** สำหรับภาษาไทย

## ⚠️ ข้อควรระวัง

1. **ทดสอบใน Demo Account** ก่อนใช้จริง
2. **ตรวจสอบการเชื่อมต่อ MT5** ก่อนเทรด
3. **กำหนด Risk Management** ให้เหมาะสม
4. **ติดตาม Log** เพื่อดูการทำงาน
5. **สำรองข้อมูล** การตั้งค่าเป็นประจำ

## 🆘 การแก้ไขปัญหา

### ไม่สามารถเชื่อมต่อ MT5
- ตรวจสอบ MT5 Terminal เปิดอยู่
- เปิดใช้งาน "Allow DLL imports"
- เปิดใช้งาน "Allow WebRequest"

### ไม่สามารถส่ง Order
- ตรวจสอบ Margin Level > 100%
- ตรวจสอบ Market Hours
- ตรวจสอบ Symbol trading allowed

### GUI ไม่แสดงข้อมูล
- ตรวจสอบการเชื่อมต่อ MT5
- รีสตาร์ท Application
- ตรวจสอบ Log สำหรับข้อผิดพลาด

## 📞 การสนับสนุน

หากพบปัญหาหรือต้องการความช่วยเหลือ:
1. ตรวจสอบ **trading_system.log**
2. ตรวจสอบ **Console Output**
3. ตรวจสอบการตั้งค่า MT5

---

**⚡ Trading System - Percentage Based Calculations**  
*ระบบเทรดอัตโนมัติที่ใช้การคำนวณเป็นเปอร์เซ็นต์*
