#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ทดสอบส่ง Order MT5 แบบง่ายที่สุด
"""

try:
    import MetaTrader5 as mt5
    print("✅ Import MetaTrader5 สำเร็จ")
except ImportError:
    print("❌ ไม่พบ MetaTrader5 module")
    print("   ติดตั้งด้วย: pip install MetaTrader5")
    exit(1)

def main():
    print("🚀 ทดสอบส่ง Order MT5")
    print("=" * 40)
    
    # เชื่อมต่อ MT5
    if not mt5.initialize():
        print("❌ ไม่สามารถเชื่อมต่อ MT5 ได้")
        return
    
    print("✅ เชื่อมต่อ MT5 สำเร็จ")
    
    # ข้อมูลบัญชี
    account = mt5.account_info()
    if account:
        print(f"📊 Account: {account.login}, Balance: {account.balance}")
        print(f"🔄 Trade Allowed: {account.trade_allowed}")
    
    # หา Symbol ทองคำ
    symbols = ["XAUUSD", "XAUUSD.v", "GOLD", "XAU/USD"]
    test_symbol = None
    
    for symbol in symbols:
        info = mt5.symbol_info(symbol)
        if info:
            test_symbol = symbol
            print(f"✅ พบ Symbol: {symbol}")
            print(f"   Bid: {info.bid}, Ask: {info.ask}")
            print(f"   Volume Min: {info.volume_min}")
            print(f"   Volume Step: {info.volume_step}")
            print(f"   Trade Mode: {info.trade_mode}")
            break
        else:
            print(f"❌ ไม่พบ: {symbol}")
    
    if not test_symbol:
        print("❌ ไม่พบ Symbol ทองคำ")
        mt5.shutdown()
        return
    
    # ทดสอบส่ง Order แบบง่ายที่สุด
    symbol_info = mt5.symbol_info(test_symbol)
    
    # Request แบบง่าย
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": test_symbol,
        "volume": symbol_info.volume_min,
        "type": mt5.ORDER_TYPE_BUY,
        "price": symbol_info.ask,
        "magic": 123456,
        "comment": "Test Order",
    }
    
    print(f"\n🚀 ส่ง Order: {test_symbol}")
    print(f"   Volume: {request['volume']}")
    print(f"   Price: {request['price']}")
    
    result = mt5.order_send(request)
    
    if result is None:
        print("❌ order_send() ส่งคืน None")
    else:
        print(f"📋 Result: RetCode={result.retcode}")
        if result.retcode == 10009:
            print(f"✅ สำเร็จ! Deal: {result.deal}")
            
            # ลองปิด Order
            print("\n⏳ รอ 2 วินาที แล้วหา Position จริงๆ...")
            import time
            time.sleep(2)
            
            # หา Position ที่เปิดอยู่
            positions = mt5.positions_get(symbol=test_symbol)
            if positions:
                pos = positions[0]  # เอาตัวแรก
                print(f"📊 พบ Position: Ticket={pos.ticket}, Volume={pos.volume}")
                
                close_request = {
                    "action": mt5.TRADE_ACTION_DEAL,
                    "symbol": test_symbol,
                    "volume": pos.volume,
                    "type": mt5.ORDER_TYPE_SELL,
                    "position": pos.ticket,  # ใช้ ticket ของ position
                    "price": symbol_info.bid,
                    "magic": 123456,
                    "comment": "Close Test",
                }
                
                print(f"🔄 ปิด Position: {pos.ticket}")
                close_result = mt5.order_send(close_request)
                
                if close_result and close_result.retcode == 10009:
                    print("✅ ปิด Order สำเร็จจริงๆ!")
                else:
                    print(f"❌ ปิด Order ไม่สำเร็จ: {close_result.retcode if close_result else 'None'}")
                    if close_result:
                        print(f"   Deal: {close_result.deal}, Order: {close_result.order}")
            else:
                print("❌ ไม่พบ Position ที่เปิดอยู่")
        else:
            print(f"❌ ไม่สำเร็จ: RetCode {result.retcode}")
    
    mt5.shutdown()
    print("\n🏁 จบการทดสอบ")

if __name__ == "__main__":
    main()
