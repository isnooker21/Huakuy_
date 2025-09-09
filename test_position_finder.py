#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🔍 Position & Ticket Finder Test
ทดสอบการหา positions และ tickets จาก MT5 โดยตรง
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from mt5_connection import MT5Connection
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def test_position_finder():
    """🔍 ทดสอบการหา positions จาก MT5"""
    print("=" * 60)
    print("🔍 POSITION & TICKET FINDER TEST")
    print("=" * 60)
    
    try:
        # 1. เชื่อมต่อ MT5
        print("1. 🔗 Connecting to MT5...")
        mt5 = MT5Connection()
        
        if not mt5.connect_mt5():
            print("❌ Cannot connect to MT5")
            return False
            
        if not mt5.check_connection_health():
            print("❌ MT5 connection unhealthy")
            return False
            
        print("✅ MT5 Connected Successfully")
        
        # 2. ดึง positions ทั้งหมด
        print("\n2. 📊 Getting ALL positions from MT5...")
        all_positions = mt5.get_positions()
        
        if not all_positions:
            print("❌ No positions found in MT5")
            return False
            
        print(f"✅ Found {len(all_positions)} total positions")
        
        # 3. แสดงรายละเอียด positions
        print("\n3. 📋 Position Details:")
        print("-" * 80)
        print(f"{'Ticket':<12} {'Symbol':<8} {'Type':<4} {'Volume':<8} {'Price':<10} {'Profit':<10} {'Magic':<8}")
        print("-" * 80)
        
        for i, pos in enumerate(all_positions):
            ticket = pos.get('ticket', 'N/A')
            symbol = pos.get('symbol', 'N/A')
            pos_type = 'BUY' if pos.get('type', 0) == 0 else 'SELL'
            volume = pos.get('volume', 0)
            price = pos.get('price_open', 0)
            profit = pos.get('profit', 0)
            magic = pos.get('magic', 0)
            
            print(f"{ticket:<12} {symbol:<8} {pos_type:<4} {volume:<8.2f} {price:<10.2f} {profit:<10.2f} {magic:<8}")
            
            # แสดงแค่ 10 ตัวแรก
            if i >= 9:
                remaining = len(all_positions) - 10
                if remaining > 0:
                    print(f"... และอีก {remaining} positions")
                break
        
        # 4. ทดสอบการหา position เฉพาะ
        print(f"\n4. 🎯 Testing Position Lookup:")
        
        # เอา tickets 5 ตัวแรกมาทดสอบ
        test_tickets = [pos.get('ticket') for pos in all_positions[:5]]
        print(f"Testing tickets: {test_tickets}")
        
        for ticket in test_tickets:
            # ลองหาใน list
            found = False
            for pos in all_positions:
                if pos.get('ticket') == ticket:
                    found = True
                    break
                    
            status = "✅ FOUND" if found else "❌ NOT FOUND"
            print(f"  Ticket {ticket}: {status}")
        
        # 5. ทดสอบ Magic Number distribution
        print(f"\n5. 🎭 Magic Number Distribution:")
        magic_count = {}
        for pos in all_positions:
            magic = pos.get('magic', 0)
            magic_count[magic] = magic_count.get(magic, 0) + 1
            
        for magic, count in sorted(magic_count.items()):
            print(f"  Magic {magic}: {count} positions")
        
        # 6. ทดสอบ Symbol distribution  
        print(f"\n6. 📈 Symbol Distribution:")
        symbol_count = {}
        for pos in all_positions:
            symbol = pos.get('symbol', 'UNKNOWN')
            symbol_count[symbol] = symbol_count.get(symbol, 0) + 1
            
        for symbol, count in sorted(symbol_count.items()):
            print(f"  {symbol}: {count} positions")
        
        # 7. Account Info
        print(f"\n7. 💰 Account Information:")
        account_info = mt5.get_account_info()
        if account_info:
            print(f"  Balance: ${account_info.get('balance', 0):,.2f}")
            print(f"  Equity: ${account_info.get('equity', 0):,.2f}")
            print(f"  Margin: ${account_info.get('margin', 0):,.2f}")
            print(f"  Free Margin: ${account_info.get('margin_free', 0):,.2f}")
            print(f"  Margin Level: {account_info.get('margin_level', 0):,.2f}%")
        else:
            print("  ❌ Cannot get account info")
            
        print("\n" + "=" * 60)
        print("✅ TEST COMPLETED SUCCESSFULLY")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False
    finally:
        try:
            mt5.disconnect_mt5()
        except:
            pass

if __name__ == "__main__":
    print("🚀 Starting Position Finder Test...")
    success = test_position_finder()
    
    if success:
        print("\n✅ Test completed successfully!")
    else:
        print("\n❌ Test failed!")
        
    input("\nPress Enter to exit...")
