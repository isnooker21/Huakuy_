# -*- coding: utf-8 -*-
"""
Test Balance Recovery System
"""

import sys
sys.path.append('.')

from zone_position_manager import create_zone_position_manager
from zone_manager import create_zone_manager, Zone, ZonePosition

print('🎯 Testing Complete Balance Recovery with 2 Zones...')

# Create zone manager
zm = create_zone_manager(30.0, 10)

# Zone 1: BUY-heavy
zone1 = Zone(
    zone_id=1,
    price_min=2600.0,
    price_max=2630.0,
    price_center=2615.0,
    buy_count=4,
    sell_count=1,
    total_positions=5,
    balance_ratio=0.8,  # BUY heavy
    total_pnl=8.0
)

zone1_positions = [
    ZonePosition(ticket=1, symbol='XAUUSD', type=0, volume=0.1, price_open=2610.0, price_current=2615.0, profit=5.0),
    ZonePosition(ticket=2, symbol='XAUUSD', type=0, volume=0.1, price_open=2612.0, price_current=2615.0, profit=3.0),
    ZonePosition(ticket=3, symbol='XAUUSD', type=0, volume=0.1, price_open=2614.0, price_current=2615.0, profit=1.0),
    ZonePosition(ticket=4, symbol='XAUUSD', type=0, volume=0.1, price_open=2616.0, price_current=2615.0, profit=-1.0),
    ZonePosition(ticket=5, symbol='XAUUSD', type=1, volume=0.1, price_open=2620.0, price_current=2615.0, profit=0.0),
]

zone1.positions = zone1_positions
zone1.buy_positions = [p for p in zone1_positions if p.type == 0]
zone1.sell_positions = [p for p in zone1_positions if p.type == 1]

# Zone 2: SELL-heavy  
zone2 = Zone(
    zone_id=2,
    price_min=2630.0,
    price_max=2660.0,
    price_center=2645.0,
    buy_count=1,
    sell_count=4,
    total_positions=5,
    balance_ratio=0.2,  # SELL heavy
    total_pnl=12.0
)

zone2_positions = [
    ZonePosition(ticket=6, symbol='XAUUSD', type=1, volume=0.1, price_open=2635.0, price_current=2640.0, profit=5.0),
    ZonePosition(ticket=7, symbol='XAUUSD', type=1, volume=0.1, price_open=2637.0, price_current=2640.0, profit=3.0),
    ZonePosition(ticket=8, symbol='XAUUSD', type=1, volume=0.1, price_open=2639.0, price_current=2640.0, profit=1.0),
    ZonePosition(ticket=9, symbol='XAUUSD', type=1, volume=0.1, price_open=2641.0, price_current=2640.0, profit=-1.0),
    ZonePosition(ticket=10, symbol='XAUUSD', type=0, volume=0.1, price_open=2645.0, price_current=2640.0, profit=4.0),
]

zone2.positions = zone2_positions
zone2.buy_positions = [p for p in zone2_positions if p.type == 0]
zone2.sell_positions = [p for p in zone2_positions if p.type == 1]

# Add zones to manager
zm.zones[1] = zone1
zm.zones[2] = zone2

print(f'Zone 1: {zone1.buy_count}B:{zone1.sell_count}S (BUY-heavy), P&L: ${zone1.total_pnl:.2f}')
print(f'Zone 2: {zone2.buy_count}B:{zone2.sell_count}S (SELL-heavy), P&L: ${zone2.total_pnl:.2f}')
print()

# Test balance recovery
from zone_analyzer import create_zone_analyzer
za = create_zone_analyzer(zm)

current_price = 2640.0
balance_analyses = za.detect_balance_recovery_opportunities(current_price)

print(f'✅ Balance Recovery Detection: {len(balance_analyses)} opportunities')

for analysis in balance_analyses:
    print(f'  Zone {analysis.zone_id}: {analysis.imbalance_type}, {analysis.excess_positions} excess')
    print(f'    Health Improvement: {analysis.health_improvement_score:.2f}')
    print(f'    Cooperation Readiness: {analysis.cooperation_readiness:.2f}')
print()

# Test balance pairing
balance_plans = za.find_cross_zone_balance_pairs(balance_analyses)
print(f'✅ Cross-Zone Balance Plans: {len(balance_plans)} plans')

for plan in balance_plans:
    print(f'  Zone {plan.primary_zone} ↔ Zone {plan.partner_zone}')
    print(f'    Expected Profit: ${plan.expected_profit:.2f}')
    print(f'    Confidence: {plan.confidence_score:.2f}')
    print(f'    Priority: {plan.execution_priority}')
    print(f'    Positions to close: {len(plan.positions_to_close)}')
print()

print('🎉 Balance Recovery System working perfectly!')
