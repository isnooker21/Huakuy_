# -*- coding: utf-8 -*-
"""
Zone Position Manager - ระบบจัดการ Positions แบบ Zone-Based
แทนที่ Simple Position Manager ด้วยระบบ Zone ที่แม่นยำกว่า

🎯 หลักการ Zone-Based Position Management:
1. แบ่ง Positions เข้า Zones ตามราคา
2. วิเคราะห์ Zone Health และ Inter-Zone Opportunities  
3. ตัดสินใจปิดแบบ Zone-Specific
4. ประสานงาน Cross-Zone Support

✅ แม่นยำกว่า ✅ ประสิทธิภาพดีกว่า ✅ จัดการเฉพาะจุด
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple

from zone_manager import ZoneManager, Zone, create_zone_manager
from zone_analyzer import ZoneAnalyzer, ZoneAnalysis, create_zone_analyzer  
from zone_coordinator import ZoneCoordinator, SupportPlan, create_zone_coordinator
from calculations import Position
from price_action_analyzer import PriceActionAnalyzer, TrendAnalysis, PriceActionSignal

logger = logging.getLogger(__name__)

class ZonePositionManager:
    """🎯 Zone Position Manager - ระบบจัดการ Positions แบบ Zone-Based"""
    
    def __init__(self, mt5_connection, order_manager, zone_size_pips: float = 30.0):
        """
        เริ่มต้น Zone Position Manager
        
        Args:
            mt5_connection: MT5 Connection instance
            order_manager: Order Manager instance
            zone_size_pips: ขนาด Zone ในหน่วย pips
        """
        self.mt5 = mt5_connection
        self.order_manager = order_manager
        
        # Zone System Components
        self.zone_manager = create_zone_manager(zone_size_pips=zone_size_pips, max_zones=15)
        self.zone_analyzer = create_zone_analyzer(self.zone_manager)
        self.zone_coordinator = create_zone_coordinator(self.zone_manager, self.zone_analyzer)
        
        # 🎯 Price Action Analyzer for Trend-Aware Closing
        self.price_action_analyzer = PriceActionAnalyzer(mt5_connection, self.symbol)
        
        # Configuration
        self.min_profit_threshold = 5.0   # กำไรขั้นต่ำที่ยอมรับ
        self.max_loss_threshold = -200.0  # ขาดทุนสูงสุดต่อ Zone
        self.enable_cross_zone_support = True
        self.enable_auto_recovery = True
        
        # State Tracking
        self.last_analysis_time = None
        self.last_coordination_time = None
        self.active_support_plans = {}
        
        logger.info(f"🎯 Zone Position Manager initialized: {zone_size_pips} pips/zone")
    
    def should_close_positions(self, positions: List[Any], current_price: float, 
                              balance_analysis: Optional[Dict] = None) -> Dict[str, Any]:
        """
        🎯 หลักฟังก์ชัน: ตัดสินใจปิด Positions แบบ Zone-Based
        
        Args:
            positions: รายการ Positions
            current_price: ราคาปัจจุบัน
            balance_analysis: การวิเคราะห์สมดุล (ไม่ใช้ใน Zone system)
            
        Returns:
            Dict: ผลการตัดสินใจ
        """
        try:
            # เช็คเบื้องต้น
            if len(positions) < 2:
                return {
                    'should_close': False,
                    'reason': 'Need at least 2 positions for zone analysis',
                    'positions_to_close': [],
                    'method': 'zone_based'
                }
            
            # อัพเดท Zones จาก Positions
            success = self.zone_manager.update_zones_from_positions(positions, current_price)
            if not success:
                logger.warning("Failed to update zones - falling back to no action")
                return {
                    'should_close': False,
                    'reason': 'Zone update failed',
                    'positions_to_close': [],
                    'method': 'zone_based'
                }
            
            # 1. 🔍 Zone Analysis
            zone_analyses = self.zone_analyzer.analyze_all_zones(current_price)
            
            if not zone_analyses:
                return {
                    'should_close': False,
                    'reason': 'No zones to analyze',
                    'positions_to_close': [],
                    'method': 'zone_based'
                }
            
            # 2. 🎯 NEW: Trend-Aware Smart Closing (Priority 1)
            trend_aware_result = self._check_trend_aware_closing(zone_analyses, current_price)
            if trend_aware_result['should_close']:
                return trend_aware_result
            
            # 3. 🎯 Single Zone Closing (Priority 2)
            single_zone_result = self._check_single_zone_closing(zone_analyses, current_price)
            if single_zone_result['should_close']:
                return single_zone_result
            
            # 4. ⚖️ Cross-Zone Balance Recovery (Priority 3)
            balance_recovery_result = self._check_balance_recovery(zone_analyses, current_price)
            if balance_recovery_result['should_close']:
                return balance_recovery_result
            
            # 5. 🤝 Cross-Zone Support (Priority 4)
            if self.enable_cross_zone_support:
                cross_zone_result = self._check_cross_zone_support(zone_analyses, current_price)
                if cross_zone_result['should_close']:
                    return cross_zone_result
            
            # 6. 🚀 Emergency Zone Recovery (Priority 5)
            if self.enable_auto_recovery:
                recovery_result = self._check_emergency_recovery(zone_analyses, current_price)
                if recovery_result['should_close']:
                    return recovery_result
            
            # 6. ไม่มีการปิด - แสดงสถานะ Zones
            self._log_zone_status_summary(zone_analyses)
            
            # 7. แสดง Balance Recovery Opportunities (ถ้ามี)
            self._log_balance_opportunities(current_price)
            
            return {
                'should_close': False,
                'reason': 'No suitable zone-based closing opportunities',
                'positions_to_close': [],
                'method': 'zone_based',
                'zone_summary': self.zone_manager.get_zone_summary()
            }
            
        except Exception as e:
            logger.error(f"❌ Error in zone-based position analysis: {e}")
            return {
                'should_close': False,
                'reason': f'Zone analysis error: {str(e)}',
                'positions_to_close': [],
                'method': 'zone_based'
            }
    
    def _check_single_zone_closing(self, zone_analyses: Dict[int, ZoneAnalysis], 
                                  current_price: float) -> Dict[str, Any]:
        """ตรวจสอบการปิด Zone เดี่ยว"""
        try:
            for zone_id, analysis in zone_analyses.items():
                zone = self.zone_manager.zones[zone_id]
                
                # เงื่อนไข 1: Zone มีกำไรดี (ปรับให้ยืดหยุ่นกว่าเดิม)
                # ถ้า Portfolio ขาดทุนหนัก ให้ปิดกำไรง่ายขึ้น
                portfolio_loss_factor = 1.0
                if hasattr(self, 'order_manager') and self.order_manager.active_positions:
                    total_portfolio_pnl = sum(getattr(pos, 'profit', 0.0) for pos in self.order_manager.active_positions)
                    if total_portfolio_pnl < -100:  # Portfolio ขาดทุนเกิน $100
                        portfolio_loss_factor = 0.7  # ลดเงื่อนไขลง 30%
                
                min_profit_required = self.min_profit_threshold * portfolio_loss_factor
                min_health_required = max(65, 75 * portfolio_loss_factor)  # ลดจาก 75
                
                if (analysis.total_pnl >= min_profit_required and 
                    analysis.health_score >= min_health_required and 
                    analysis.risk_level in ['LOW', 'MEDIUM'] and  # เพิ่ม MEDIUM
                    analysis.total_pnl > 0):  # ต้องมีกำไรจริง
                    
                    # เพิ่มการตรวจสอบ Portfolio Impact
                    portfolio_impact = self._evaluate_portfolio_impact_before_closing(zone.positions)
                    
                    zone_range = f"{zone.price_min:.2f}-{zone.price_max:.2f}"
                    logger.info(f"💰 Single Zone Closing: Zone {zone_id} [{zone_range}]")
                    logger.info(f"   Positions: B{zone.buy_count}:S{zone.sell_count} | "
                               f"P&L: ${analysis.total_pnl:.2f} | Health: {analysis.health_score:.0f}")
                    logger.info(f"   Portfolio Impact: {portfolio_impact['impact_description']}")
                    
                    # ปิดเฉพาะเมื่อไม่ส่งผลเสียต่อ Portfolio
                    if portfolio_impact['safe_to_close']:
                        return {
                            'should_close': True,
                            'reason': f'Profitable Zone {zone_id} [{zone_range}]: ${analysis.total_pnl:.2f} profit (Safe for portfolio)',
                            'positions_to_close': zone.positions,
                            'positions_count': zone.total_positions,
                            'expected_pnl': analysis.total_pnl,
                            'method': 'single_zone_profit',
                            'zone_id': zone_id,
                            'zone_range': zone_range,
                            'zone_health': analysis.health_score,
                            'portfolio_impact': portfolio_impact
                        }
                    else:
                        logger.warning(f"⚠️ Skip closing Zone {zone_id}: {portfolio_impact['reason']}")
                
                # เงื่อนไข 2: Zone เสี่ยงสูง หรือขาดทุนหนักมาก - ปิดเพื่อลดความเสี่ยง
                elif (analysis.risk_level in ['HIGH', 'CRITICAL'] and 
                      (analysis.total_pnl > self.max_loss_threshold or analysis.total_pnl < -50) and  # ขาดทุนเกิน $50
                      analysis.health_score < 40):  # ลดจาก 30 เป็น 40
                    
                    zone_range = f"{zone.price_min:.2f}-{zone.price_max:.2f}"
                    logger.info(f"🚨 Critical Zone Closing: Zone {zone_id} [{zone_range}]")
                    logger.info(f"   Positions: B{zone.buy_count}:S{zone.sell_count} | "
                               f"P&L: ${analysis.total_pnl:.2f} | Risk: {analysis.risk_level}")
                    
                    return {
                        'should_close': True,
                        'reason': f'Critical Zone {zone_id} [{zone_range}]: {analysis.risk_level} risk',
                        'positions_to_close': zone.positions,
                        'positions_count': zone.total_positions,
                        'expected_pnl': analysis.total_pnl,
                        'method': 'single_zone_risk',
                        'zone_id': zone_id,
                        'zone_range': zone_range,
                        'risk_level': analysis.risk_level
                    }
            
            return {'should_close': False}
            
        except Exception as e:
            logger.error(f"❌ Error in single zone checking: {e}")
            return {'should_close': False}
    
    def _check_trend_aware_closing(self, zone_analyses: Dict[int, ZoneAnalysis], 
                                  current_price: float) -> Dict[str, Any]:
        """
        🎯 NEW: Trend-Aware Smart Closing
        ใช้ Price Action เพื่อตัดสินใจปิดไม้ให้เหมาะกับทิศทางตลาด
        """
        try:
            # วิเคราะห์ Market Structure
            logger.info("🎯 Starting Trend-Aware Analysis...")
            trend_analysis = self.price_action_analyzer.analyze_market_structure()
            
            logger.info(f"📈 Trend Analysis Result:")
            logger.info(f"   Direction: {trend_analysis.direction}")
            logger.info(f"   Strength: {trend_analysis.strength:.1f}%")
            logger.info(f"   Confidence: {trend_analysis.confidence:.1f}%")
            logger.info(f"   Momentum: {trend_analysis.momentum}")
            
            # 🚀 UNLIMITED TRADING: ไม่หยุดเทรดแม้ trend อ่อน - ใช้ Zone Logic ต่อ
            use_zone_logic = False
            if trend_analysis.direction == 'SIDEWAYS' or trend_analysis.strength < 30:
                logger.info(f"🎯 Trend weak ({trend_analysis.strength:.1f}%) or sideways - switching to Zone Logic")
                use_zone_logic = True
            else:
                logger.info(f"🎯 Strong trend ({trend_analysis.strength:.1f}%) - using Trend-Aware Logic")
            
            # หา Zones ที่มี positions
            zones_with_positions = {
                zone_id: analysis for zone_id, analysis in zone_analyses.items()
                if self.zone_manager.zones[zone_id].total_positions > 0
            }
            
            logger.info(f"📊 Found {len(zones_with_positions)} zones with positions")
            
            if not zones_with_positions:
                logger.info("⏸️ No zones with positions - skipping trend analysis")
                return {'should_close': False}
            
            # เลือกใช้ Logic ตาม Trend Strength
            if use_zone_logic:
                # 🎯 Zone Logic: ใช้เมื่อ trend อ่อนหรือ sideways
                logger.info(f"🎯 Using Zone-Based Logic (trend too weak)")
                result = self._analyze_zone_based_closing(zones_with_positions, current_price)
                return result
            else:
                # 🎯 Trend-Aware Logic: ใช้เมื่อ trend แข็งแกร่ง
                logger.info(f"🎯 Analyzing {trend_analysis.direction} trend closing...")
            
            if trend_analysis.direction == 'BULLISH':
                result = self._analyze_bullish_trend_closing(zones_with_positions, trend_analysis, current_price)
                if result['should_close']:
                    logger.info(f"✅ Bullish trend closing recommended: {result['reason']}")
                else:
                    logger.info("⏸️ No suitable bullish trend closing found")
                return result
            elif trend_analysis.direction == 'BEARISH':
                result = self._analyze_bearish_trend_closing(zones_with_positions, trend_analysis, current_price)
                if result['should_close']:
                    logger.info(f"✅ Bearish trend closing recommended: {result['reason']}")
                else:
                    logger.info("⏸️ No suitable bearish trend closing found")
                    # 🆕 Emergency: ถ้าไม่มี profitable SELL แต่มี BUY ขาดทุนหนัก ให้ปิด BUY เดี่ยว
                    emergency_result = self._check_emergency_trend_closing(zones_with_positions, 'BEARISH')
                    if emergency_result['should_close']:
                        logger.info(f"🚨 Emergency bearish closing: {emergency_result['reason']}")
                        return emergency_result
                return result
            
            logger.info(f"⏸️ Trend direction '{trend_analysis.direction}' not supported")
            return {'should_close': False}
            
        except Exception as e:
            logger.error(f"❌ Error in trend-aware closing: {e}")
            return {'should_close': False}
    
    def _analyze_bullish_trend_closing(self, zones_with_positions: Dict, 
                                     trend_analysis: TrendAnalysis, current_price: float) -> Dict[str, Any]:
        """📈 วิเคราะห์การปิดในช่วง Bullish Trend"""
        try:
            profitable_buys = []
            losing_sells = []
            total_profit_potential = 0.0
            
            # หา BUY positions ที่กำไร และ SELL positions ที่ขาดทุน
            for zone_id, analysis in zones_with_positions.items():
                zone = self.zone_manager.zones[zone_id]
                
                for pos in zone.positions:
                    pos_profit = getattr(pos, 'profit', 0.0)
                    pos_type = getattr(pos, 'type', 0)
                    
                    # BUY positions ที่กำไร (ride the trend)
                    if pos_type == 0 and pos_profit > 5.0:
                        profitable_buys.append({
                            'position': pos,
                            'profit': pos_profit,
                            'zone_id': zone_id
                        })
                        total_profit_potential += pos_profit
                    
                    # SELL positions ที่ขาดทุน (cut against trend)
                    elif pos_type == 1 and pos_profit < -10.0:
                        losing_sells.append({
                            'position': pos,
                            'loss': pos_profit,
                            'zone_id': zone_id
                        })
            
            logger.info(f"📊 Bullish Analysis: {len(profitable_buys)} profitable BUYs, {len(losing_sells)} losing SELLs")
            logger.info(f"💰 Total BUY profit potential: ${total_profit_potential:.2f}")
            
            # ปรับเงื่อนไขให้ยืดหยุ่นกว่า
            if profitable_buys and losing_sells and total_profit_potential > 10.0:  # ลดจาก 20 เป็น 10
                # เลือก BUY ที่กำไรดีที่สุด และ SELL ที่ขาดทุนน้อยที่สุด
                best_buy = max(profitable_buys, key=lambda x: x['profit'])
                best_sell = max(losing_sells, key=lambda x: x['loss'])  # loss ที่น้อยที่สุด (ใกล้ 0)
                
                positions_to_close = [best_buy['position'], best_sell['position']]
                expected_pnl = best_buy['profit'] + best_sell['loss']
                
                logger.info(f"🎯 Best pair: BUY +${best_buy['profit']:.2f} + SELL ${best_sell['loss']:.2f} = ${expected_pnl:.2f}")
                
                # ยอมรับ Net loss เล็กน้อยถ้าเป็นการลด exposure
                if expected_pnl > -5.0:  # ยอมรับขาดทุนไม่เกิน $5 เพื่อลด exposure
                    logger.info(f"📈 Bullish Trend Closing: BUY ${best_buy['profit']:.2f} + SELL ${best_sell['loss']:.2f}")
                    
                    return {
                        'should_close': True,
                        'reason': f'Bullish trend: Close profitable BUY + losing SELL (Net: ${expected_pnl:.2f})',
                        'positions_to_close': positions_to_close,
                        'positions_count': len(positions_to_close),
                        'expected_pnl': expected_pnl,
                        'method': 'trend_aware_bullish',
                        'trend_strength': trend_analysis.strength,
                        'trend_confidence': trend_analysis.confidence
                    }
            
            return {'should_close': False}
            
        except Exception as e:
            logger.error(f"❌ Error analyzing bullish trend closing: {e}")
            return {'should_close': False}
    
    def _analyze_bearish_trend_closing(self, zones_with_positions: Dict, 
                                     trend_analysis: TrendAnalysis, current_price: float) -> Dict[str, Any]:
        """📉 วิเคราะห์การปิดในช่วง Bearish Trend"""
        try:
            profitable_sells = []
            losing_buys = []
            total_profit_potential = 0.0
            
            # หา SELL positions ที่กำไร และ BUY positions ที่ขาดทุน
            for zone_id, analysis in zones_with_positions.items():
                zone = self.zone_manager.zones[zone_id]
                
                for pos in zone.positions:
                    pos_profit = getattr(pos, 'profit', 0.0)
                    pos_type = getattr(pos, 'type', 0)
                    
                    # SELL positions ที่กำไร (ride the trend)
                    if pos_type == 1 and pos_profit > 5.0:
                        profitable_sells.append({
                            'position': pos,
                            'profit': pos_profit,
                            'zone_id': zone_id
                        })
                        total_profit_potential += pos_profit
                    
                    # BUY positions ที่ขาดทุน (cut against trend)
                    elif pos_type == 0 and pos_profit < -10.0:
                        losing_buys.append({
                            'position': pos,
                            'loss': pos_profit,
                            'zone_id': zone_id
                        })
            
            logger.info(f"📊 Bearish Analysis: {len(profitable_sells)} profitable SELLs, {len(losing_buys)} losing BUYs")
            logger.info(f"💰 Total SELL profit potential: ${total_profit_potential:.2f}")
            
            # ปรับเงื่อนไขให้ยืดหยุ่นกว่า
            if profitable_sells and losing_buys and total_profit_potential > 10.0:  # ลดจาก 20 เป็น 10
                # เลือก SELL ที่กำไรดีที่สุด และ BUY ที่ขาดทุนน้อยที่สุด
                best_sell = max(profitable_sells, key=lambda x: x['profit'])
                best_buy = max(losing_buys, key=lambda x: x['loss'])  # loss ที่น้อยที่สุด
                
                positions_to_close = [best_sell['position'], best_buy['position']]
                expected_pnl = best_sell['profit'] + best_buy['loss']
                
                logger.info(f"🎯 Best pair: SELL +${best_sell['profit']:.2f} + BUY ${best_buy['loss']:.2f} = ${expected_pnl:.2f}")
                
                # ยอมรับ Net loss เล็กน้อยถ้าเป็นการลด exposure
                if expected_pnl > -5.0:  # ยอมรับขาดทุนไม่เกิน $5 เพื่อลด exposure
                    logger.info(f"📉 Bearish Trend Closing: SELL ${best_sell['profit']:.2f} + BUY ${best_buy['loss']:.2f}")
                    
                    return {
                        'should_close': True,
                        'reason': f'Bearish trend: Close profitable SELL + losing BUY (Net: ${expected_pnl:.2f})',
                        'positions_to_close': positions_to_close,
                        'positions_count': len(positions_to_close),
                        'expected_pnl': expected_pnl,
                        'method': 'trend_aware_bearish',
                        'trend_strength': trend_analysis.strength,
                        'trend_confidence': trend_analysis.confidence
                    }
            
            return {'should_close': False}
            
        except Exception as e:
            logger.error(f"❌ Error analyzing bearish trend closing: {e}")
            return {'should_close': False}
    
    def _check_emergency_trend_closing(self, zones_with_positions: Dict, trend_direction: str) -> Dict[str, Any]:
        """
        🚨 Emergency Trend Closing - ปิดไม้ที่ against trend หนักๆ
        สำหรับกรณีที่ไม่มี profitable positions ในทิศทาง trend
        """
        try:
            worst_positions = []
            
            for zone_id, analysis in zones_with_positions.items():
                zone = self.zone_manager.zones[zone_id]
                
                for pos in zone.positions:
                    pos_profit = getattr(pos, 'profit', 0.0)
                    pos_type = getattr(pos, 'type', 0)
                    
                    # หา positions ที่ขาดทุนหนักและ against trend
                    if trend_direction == 'BEARISH' and pos_type == 0 and pos_profit < -15.0:  # BUY ขาดทุนหนัก
                        worst_positions.append({
                            'position': pos,
                            'loss': pos_profit,
                            'zone_id': zone_id,
                            'type': 'BUY'
                        })
                    elif trend_direction == 'BULLISH' and pos_type == 1 and pos_profit < -15.0:  # SELL ขาดทุนหนัก
                        worst_positions.append({
                            'position': pos,
                            'loss': pos_profit,
                            'zone_id': zone_id,
                            'type': 'SELL'
                        })
            
            # 🚫 DISABLED: ไม่ cut loss แม้ในกรณี emergency - ให้ระบบ recovery จัดการ
            # if worst_positions:
            #     # เลือกตัวที่ขาดทุนหนักที่สุด
            #     worst_position = min(worst_positions, key=lambda x: x['loss'])
            #     
            #     logger.info(f"🚨 Emergency: {worst_position['type']} position losing ${abs(worst_position['loss']):.2f} against {trend_direction} trend")
            #     
            #     return {
            #         'should_close': True,
            #         'reason': f'Emergency {trend_direction} trend: Cut heavy loss {worst_position["type"]} (${worst_position["loss"]:.2f})',
            #         'positions_to_close': [worst_position['position']],
            #         'positions_count': 1,
            #         'expected_pnl': worst_position['loss'],
            #         'method': f'emergency_trend_{trend_direction.lower()}',
            #         'zone_id': worst_position['zone_id']
            #     }
            
            if worst_positions:
                logger.info(f"📊 Emergency Trend: Found {len(worst_positions)} against-trend positions - keeping for recovery")
            
            return {'should_close': False}
            
        except Exception as e:
            logger.error(f"❌ Error in emergency trend closing: {e}")
            return {'should_close': False}
    
    def _analyze_zone_based_closing(self, zones_with_positions: Dict, current_price: float) -> Dict[str, Any]:
        """
        🎯 Zone-Based Closing Logic - ใช้เมื่อ trend อ่อนหรือ sideways
        จะใช้ Zone Health และ P&L เป็นหลักในการตัดสินใจ
        """
        try:
            logger.info("🎯 Zone-Based Analysis: Looking for closing opportunities...")
            
            profitable_positions = []
            losing_positions = []
            
            # วิเคราะห์ positions ในแต่ละ zone
            for zone_id, analysis in zones_with_positions.items():
                zone = self.zone_manager.zones[zone_id]
                
                for pos in zone.positions:
                    pos_profit = getattr(pos, 'profit', 0.0)
                    pos_type = getattr(pos, 'type', 0)
                    
                    if pos_profit > 8.0:  # กำไรดี
                        profitable_positions.append({
                            'position': pos,
                            'profit': pos_profit,
                            'zone_id': zone_id,
                            'type': 'BUY' if pos_type == 0 else 'SELL'
                        })
                    elif pos_profit < -20.0:  # ขาดทุนหนัก
                        losing_positions.append({
                            'position': pos,
                            'loss': pos_profit,
                            'zone_id': zone_id,
                            'type': 'BUY' if pos_type == 0 else 'SELL'
                        })
            
            logger.info(f"📊 Zone Analysis: {len(profitable_positions)} profitable, {len(losing_positions)} heavy losses")
            
            # ปิดกำไรก่อน (conservative approach ในตลาด sideways)
            if profitable_positions:
                best_profit = max(profitable_positions, key=lambda x: x['profit'])
                logger.info(f"✅ Zone Logic: Taking profit on {best_profit['type']} (${best_profit['profit']:.2f})")
                
                return {
                    'should_close': True,
                    'reason': f'Zone-Based: Take profit {best_profit["type"]} ${best_profit["profit"]:.2f} (sideways market)',
                    'positions_to_close': [best_profit['position']],
                    'positions_count': 1,
                    'expected_pnl': best_profit['profit'],
                    'method': 'zone_based_profit',
                    'zone_id': best_profit['zone_id']
                }
            
            # 🚫 DISABLED: ไม่ cut loss - ให้ระบบ recovery จัดการเอง
            # if losing_positions:
            #     worst_loss = min(losing_positions, key=lambda x: x['loss'])
            #     logger.info(f"⚠️ Zone Logic: Cutting heavy loss {worst_loss['type']} (${worst_loss['loss']:.2f})")
            #     
            #     return {
            #         'should_close': True,
            #         'reason': f'Zone-Based: Cut heavy loss {worst_loss["type"]} ${worst_loss["loss"]:.2f}',
            #         'positions_to_close': [worst_loss['position']],
            #         'positions_count': 1,
            #         'expected_pnl': worst_loss['loss'],
            #         'method': 'zone_based_cutloss',
            #         'zone_id': worst_loss['zone_id']
            #     }
            
            if losing_positions:
                logger.info(f"📊 Zone Logic: Found {len(losing_positions)} losing positions - keeping for recovery")
            
            logger.info("⏸️ Zone Logic: No clear closing opportunities found")
            return {'should_close': False}
            
        except Exception as e:
            logger.error(f"❌ Error in zone-based closing: {e}")
            return {'should_close': False}
    
    def _check_balance_recovery(self, zone_analyses: Dict[int, ZoneAnalysis], 
                               current_price: float) -> Dict[str, Any]:
        """
        ⚖️ ตรวจสอบ Cross-Zone Balance Recovery
        
        Args:
            zone_analyses: ผลการวิเคราะห์ Zones
            current_price: ราคาปัจจุบัน
            
        Returns:
            Dict: ผลการตัดสินใจ
        """
        try:
            # หา Balance Recovery Opportunities
            balance_plans = self.zone_coordinator.analyze_balance_recovery_opportunities(current_price)
            
            if not balance_plans:
                return {'should_close': False}
            
            # เลือกแผนที่ดีที่สุด
            best_plan = balance_plans[0]  # เรียงตาม expected_profit แล้ว
            
            # เงื่อนไขการดำเนินการ
            if (best_plan.confidence_score >= 0.6 and 
                best_plan.expected_profit >= 10.0 and
                best_plan.execution_priority in ['HIGH', 'URGENT']):
                
                # เก็บ positions ที่จะปิด
                positions_to_close = []
                zone_info = {}
                
                for zone_id, position in best_plan.positions_to_close:
                    positions_to_close.append(position)
                    
                    if zone_id not in zone_info:
                        zone_info[zone_id] = {'count': 0, 'profit': 0.0}
                    zone_info[zone_id]['count'] += 1
                    zone_info[zone_id]['profit'] += position.profit
                
                if positions_to_close:
                    logger.info(f"⚖️ Cross-Zone Balance Recovery: Zone {best_plan.primary_zone} ↔ Zone {best_plan.partner_zone}")
                    logger.info(f"   Expected Profit: ${best_plan.expected_profit:.2f}")
                    logger.info(f"   Positions: {len(positions_to_close)} from {len(zone_info)} zones")
                    logger.info(f"   Priority: {best_plan.execution_priority} | Confidence: {best_plan.confidence_score:.2f}")
                    
                    # แสดงรายละเอียด Zone Health Improvement
                    for zone_id, improvement in best_plan.health_improvement.items():
                        zone_name = f"Zone {zone_id}"
                        if zone_id == best_plan.primary_zone:
                            zone_name += " (Primary)"
                        elif zone_id == best_plan.partner_zone:
                            zone_name += " (Partner)"
                        logger.info(f"   {zone_name}: Health +{improvement:.1f}")
                    
                    return {
                        'should_close': True,
                        'reason': f'Balance recovery: Zone {best_plan.primary_zone} ↔ Zone {best_plan.partner_zone} (${best_plan.expected_profit:.2f})',
                        'positions_to_close': positions_to_close,
                        'positions_count': len(positions_to_close),
                        'expected_pnl': best_plan.expected_profit,
                        'method': 'balance_recovery',
                        'primary_zone': best_plan.primary_zone,
                        'partner_zone': best_plan.partner_zone,
                        'recovery_type': best_plan.recovery_type,
                        'health_improvement': best_plan.health_improvement,
                        'confidence': best_plan.confidence_score,
                        'zone_info': zone_info
                    }
            
            return {'should_close': False}
            
        except Exception as e:
            logger.error(f"❌ Error in balance recovery checking: {e}")
            return {'should_close': False}
    
    def _check_cross_zone_support(self, zone_analyses: Dict[int, ZoneAnalysis], 
                                 current_price: float) -> Dict[str, Any]:
        """ตรวจสอบการช่วยเหลือข้าม Zones"""
        try:
            # หา Support Opportunities
            support_plans = self.zone_coordinator.analyze_support_opportunities(current_price)
            
            if not support_plans:
                return {'should_close': False}
            
            # เลือกแผนที่ดีที่สุด
            best_plan = support_plans[0]  # เรียงตาม confidence แล้ว
            
            if best_plan.confidence >= 0.7 and best_plan.support_ratio >= 1.0:
                
                # เก็บแผนไว้ดำเนินการ
                self.active_support_plans[best_plan.plan_id] = best_plan
                
                # สร้าง positions_to_close จาก helper zones
                positions_to_close = []
                total_expected_pnl = 0.0
                
                for helper_zone_id in best_plan.helper_zones:
                    helper_zone = self.zone_manager.zones[helper_zone_id]
                    
                    # เลือก positions ที่มีกำไรจาก helper zone
                    profitable_positions = [pos for pos in helper_zone.positions if pos.profit > 0]
                    positions_to_close.extend(profitable_positions[:3])  # สูงสุด 3 ไม้ต่อ zone
                    total_expected_pnl += sum(pos.profit for pos in profitable_positions[:3])
                
                if positions_to_close:
                    logger.info(f"🤝 Cross-Zone Support: Plan {best_plan.plan_id}")
                    logger.info(f"   Helpers: {best_plan.helper_zones} → Troubled: {best_plan.troubled_zones}")
                    logger.info(f"   Expected: ${total_expected_pnl:.2f} from {len(positions_to_close)} positions")
                    
                    return {
                        'should_close': True,
                        'reason': f'Cross-zone support: Zones {best_plan.helper_zones} helping {best_plan.troubled_zones}',
                        'positions_to_close': positions_to_close,
                        'positions_count': len(positions_to_close),
                        'expected_pnl': total_expected_pnl,
                        'method': 'cross_zone_support',
                        'support_plan_id': best_plan.plan_id,
                        'helper_zones': best_plan.helper_zones,
                        'troubled_zones': best_plan.troubled_zones,
                        'confidence': best_plan.confidence
                    }
            
            return {'should_close': False}
            
        except Exception as e:
            logger.error(f"❌ Error in cross-zone support checking: {e}")
            return {'should_close': False}
    
    def _check_emergency_recovery(self, zone_analyses: Dict[int, ZoneAnalysis], 
                                 current_price: float) -> Dict[str, Any]:
        """ตรวจสอบการ Recovery ฉุกเฉิน"""
        try:
            # หา Zones ที่ต้องการ Recovery ฉุกเฉิน
            critical_zones = [
                (zone_id, analysis) for zone_id, analysis in zone_analyses.items()
                if analysis.risk_level == 'CRITICAL' and analysis.total_pnl < -100
            ]
            
            if not critical_zones:
                return {'should_close': False}
            
            # เรียงตามความรุนแรง (ขาดทุนมากที่สุดก่อน)
            critical_zones.sort(key=lambda x: x[1].total_pnl)
            
            most_critical_zone_id, most_critical_analysis = critical_zones[0]
            most_critical_zone = self.zone_manager.zones[most_critical_zone_id]
            
            # ตรวจสอบว่ามี Helper Zones หรือไม่
            helper_zones = [
                (zone_id, analysis) for zone_id, analysis in zone_analyses.items()
                if analysis.total_pnl > 50 and analysis.risk_level == 'LOW'
            ]
            
            if helper_zones:
                # มี Helper - ใช้ Cross-Zone Recovery
                total_help_available = sum(analysis.total_pnl * 0.8 for _, analysis in helper_zones)
                help_needed = abs(most_critical_analysis.total_pnl)
                
                if total_help_available >= help_needed * 0.7:  # 70% coverage
                    
                    # สร้าง Recovery Plan
                    positions_to_close = []
                    expected_pnl = 0.0
                    
                    for helper_zone_id, helper_analysis in helper_zones[:2]:  # สูงสุด 2 helpers
                        helper_zone = self.zone_manager.zones[helper_zone_id]
                        profitable_positions = [pos for pos in helper_zone.positions if pos.profit > 0]
                        positions_to_close.extend(profitable_positions[:2])
                        expected_pnl += sum(pos.profit for pos in profitable_positions[:2])
                    
                    if positions_to_close:
                        logger.info(f"🚀 Emergency Recovery: Zone {most_critical_zone_id} "
                                   f"(${most_critical_analysis.total_pnl:.2f} loss)")
                        logger.info(f"   Using ${expected_pnl:.2f} from helper zones for recovery")
                        
                        return {
                            'should_close': True,
                            'reason': f'Emergency recovery for critical Zone {most_critical_zone_id}',
                            'positions_to_close': positions_to_close,
                            'positions_count': len(positions_to_close),
                            'expected_pnl': expected_pnl,
                            'method': 'emergency_recovery',
                            'critical_zone_id': most_critical_zone_id,
                            'critical_zone_loss': most_critical_analysis.total_pnl,
                            'recovery_type': 'cross_zone_support'
                        }
            
            else:
                # ไม่มี Helper - พิจารณาปิด Critical Zone เพื่อลดความเสี่ยง
                if most_critical_analysis.total_pnl > -300:  # ไม่ให้เสียมากเกินไป
                    
                    logger.info(f"⚠️ Emergency Zone Closure: Zone {most_critical_zone_id} "
                               f"(${most_critical_analysis.total_pnl:.2f} loss) - No helpers available")
                    
                    return {
                        'should_close': True,
                        'reason': f'Emergency closure of critical Zone {most_critical_zone_id}',
                        'positions_to_close': most_critical_zone.positions,
                        'positions_count': most_critical_zone.total_positions,
                        'expected_pnl': most_critical_analysis.total_pnl,
                        'method': 'emergency_closure',
                        'critical_zone_id': most_critical_zone_id,
                        'recovery_type': 'damage_control'
                    }
            
            return {'should_close': False}
            
        except Exception as e:
            logger.error(f"❌ Error in emergency recovery checking: {e}")
            return {'should_close': False}
    
    def _log_zone_status_summary(self, zone_analyses: Dict[int, ZoneAnalysis]):
        """แสดงสรุปสถานะ Zones แบบย่อ"""
        try:
            if not zone_analyses:
                return
                
            # สรุปแบบย่อ
            total_zones = len(zone_analyses)
            profitable_zones = sum(1 for a in zone_analyses.values() if a.total_pnl > 0)
            critical_zones = sum(1 for a in zone_analyses.values() if a.risk_level == 'CRITICAL')
            total_pnl = sum(a.total_pnl for a in zone_analyses.values())
            
            logger.info(f"📊 Zones: {total_zones} active, {profitable_zones} profitable, "
                       f"{critical_zones} critical | Total P&L: ${total_pnl:+.2f}")
            
            # แสดงรายละเอียดทุก Zones
            self._log_detailed_zone_breakdown(zone_analyses)
                               
        except Exception as e:
            logger.error(f"❌ Error logging zone summary: {e}")
    
    def _log_detailed_zone_breakdown(self, zone_analyses: Dict[int, ZoneAnalysis]):
        """
        📋 แสดงรายละเอียดครบถ้วนของทุก Zones
        
        Args:
            zone_analyses: ผลการวิเคราะห์ Zones
        """
        try:
            if not zone_analyses:
                logger.info("📋 No active zones to display")
                return
            
            logger.info("=" * 100)
            logger.info("📋 DETAILED ZONE BREAKDOWN")
            logger.info("=" * 100)
            
            # เรียงตาม Zone ID
            sorted_zones = sorted(zone_analyses.items())
            
            for zone_id, analysis in sorted_zones:
                zone = self.zone_manager.zones[zone_id]
                
                # Zone Header
                balance_status = self._get_balance_status_emoji(zone.balance_ratio)
                risk_emoji = {'LOW': '💚', 'MEDIUM': '🟡', 'HIGH': '🔴', 'CRITICAL': '💀'}
                risk_icon = risk_emoji.get(analysis.risk_level, '⚪')
                
                logger.info(f"🏷️  ZONE {zone_id} [{zone.price_min:.2f} - {zone.price_max:.2f}] "
                           f"({(zone.price_max - zone.price_min) * 100:.0f} pips)")
                logger.info(f"    📊 Positions: B{zone.buy_count}:S{zone.sell_count} | "
                           f"P&L: ${analysis.total_pnl:+7.2f} | Risk: {analysis.risk_level} {risk_icon} | {balance_status}")
                
                # BUY Positions Detail
                if zone.buy_positions:
                    logger.info(f"    📈 BUY Positions ({len(zone.buy_positions)}):")
                    buy_total_pnl = 0.0
                    for pos in sorted(zone.buy_positions, key=lambda x: x.price_open):
                        profit_icon = "💚" if pos.profit > 0 else "🔴" if pos.profit < 0 else "⚪"
                        logger.info(f"        #{pos.ticket} | Open: {pos.price_open:.2f} → Current: {pos.price_current:.2f} | "
                                   f"P&L: ${pos.profit:+6.2f} {profit_icon} | Vol: {pos.volume:.2f}")
                        buy_total_pnl += pos.profit
                    logger.info(f"        📊 BUY Total: ${buy_total_pnl:+.2f}")
                
                # SELL Positions Detail  
                if zone.sell_positions:
                    logger.info(f"    📉 SELL Positions ({len(zone.sell_positions)}):")
                    sell_total_pnl = 0.0
                    for pos in sorted(zone.sell_positions, key=lambda x: x.price_open, reverse=True):
                        profit_icon = "💚" if pos.profit > 0 else "🔴" if pos.profit < 0 else "⚪"
                        logger.info(f"        #{pos.ticket} | Open: {pos.price_open:.2f} → Current: {pos.price_current:.2f} | "
                                   f"P&L: ${pos.profit:+6.2f} {profit_icon} | Vol: {pos.volume:.2f}")
                        sell_total_pnl += pos.profit
                    logger.info(f"        📊 SELL Total: ${sell_total_pnl:+.2f}")
                
                # Zone Summary
                logger.info(f"    🎯 Zone Health: {analysis.health_score:.0f}/100 | "
                           f"Balance Score: {analysis.balance_score:.0f}/100 | "
                           f"Confidence: {analysis.confidence:.2f}")
                
                # Action Recommendation
                action_emoji = {'HOLD': '✋', 'REBALANCE': '⚖️', 'CLOSE': '💰', 'RECOVER': '🚀'}
                action_icon = action_emoji.get(analysis.action_needed, '❓')
                logger.info(f"    💡 Recommended: {analysis.action_needed} {action_icon} | "
                           f"Priority: {analysis.priority}")
                
                logger.info("")  # Blank line between zones
            
            logger.info("=" * 100)
            
        except Exception as e:
            logger.error(f"❌ Error logging detailed zone breakdown: {e}")
    
    def _get_balance_status_emoji(self, balance_ratio: float) -> str:
        """
        ดึง Balance Status Emoji
        
        Args:
            balance_ratio: อัตราส่วน Balance (0.0-1.0)
            
        Returns:
            str: Balance status พร้อม emoji
        """
        try:
            if balance_ratio >= 0.8:
                return "📈 BUY-HEAVY"
            elif balance_ratio <= 0.2:
                return "📉 SELL-HEAVY"
            elif balance_ratio >= 0.6:
                return "📊 BUY-LEANING"
            elif balance_ratio <= 0.4:
                return "📊 SELL-LEANING"
            else:
                return "⚖️ BALANCED"
                
        except Exception:
            return "❓ UNKNOWN"
    
    def _log_balance_opportunities(self, current_price: float):
        """
        📊 แสดงโอกาส Balance Recovery แบบสรุป
        
        Args:
            current_price: ราคาปัจจุบัน
        """
        try:
            # หา Balance Recovery Opportunities
            balance_analyses = self.zone_analyzer.detect_balance_recovery_opportunities(current_price)
            
            if not balance_analyses:
                return
            
            # สรุปโอกาส Balance Recovery
            buy_heavy_count = len([a for a in balance_analyses if a.imbalance_type == 'BUY_HEAVY'])
            sell_heavy_count = len([a for a in balance_analyses if a.imbalance_type == 'SELL_HEAVY'])
            total_excess = sum(a.excess_positions for a in balance_analyses)
            
            if buy_heavy_count > 0 or sell_heavy_count > 0:
                logger.info(f"⚖️ Balance Recovery Opportunities: {buy_heavy_count} BUY-heavy, {sell_heavy_count} SELL-heavy zones")
                logger.info(f"   Total excess positions: {total_excess}")
                
                # หาคู่ที่สามารถ Balance กันได้
                balance_plans = self.zone_analyzer.find_cross_zone_balance_pairs(balance_analyses)
                
                if balance_plans:
                    best_plan = balance_plans[0]
                    total_potential_profit = sum(plan.expected_profit for plan in balance_plans)
                    
                    logger.info(f"   💰 Best opportunity: Zone {best_plan.primary_zone} ↔ Zone {best_plan.partner_zone} (${best_plan.expected_profit:.2f})")
                    logger.info(f"   📈 Total potential: ${total_potential_profit:.2f} from {len(balance_plans)} pairs")
                    
                    # แสดงเงื่อนไขที่ขาดไป (ถ้ามี)
                    if best_plan.confidence_score < 0.6:
                        logger.info(f"   ⚠️ Confidence too low: {best_plan.confidence_score:.2f} (need ≥0.6)")
                    elif best_plan.expected_profit < 10.0:
                        logger.info(f"   ⚠️ Profit too low: ${best_plan.expected_profit:.2f} (need ≥$10)")
                    elif best_plan.execution_priority not in ['HIGH', 'URGENT']:
                        logger.info(f"   ⚠️ Priority too low: {best_plan.execution_priority} (need HIGH/URGENT)")
                
        except Exception as e:
            logger.error(f"❌ Error logging balance opportunities: {e}")
    
    def log_detailed_zone_analysis(self, current_price: float):
        """
        📋 แสดงการวิเคราะห์ Zone แบบละเอียด
        
        Args:
            current_price: ราคาปัจจุบัน
        """
        try:
            # อัพเดท Zones
            positions = []  # จะต้องได้รับจากภายนอก
            logger.info("📋 Detailed Zone Analysis (requires position data)")
            
            # แสดงสถานะ Zone System
            zone_status = self.get_zone_status()
            logger.info(f"🎯 Zone System Status: {zone_status['system_status']}")
            logger.info(f"📊 Active Zones: {zone_status['zone_system'].get('total_zones', 0)}")
            logger.info(f"🤝 Support Plans: {zone_status['active_support_plans']}")
            
            # ใช้ Zone Analyzer แสดงรายงานเต็ม
            self.zone_analyzer.log_zone_analysis(current_price, detailed=True)
            
            # แสดง Balance Recovery Opportunities แบบละเอียด
            self.zone_coordinator.log_balance_recovery_opportunities(current_price, detailed=True)
            
        except Exception as e:
            logger.error(f"❌ Error in detailed zone analysis: {e}")
    
    def debug_zone_calculation_for_price(self, price: float):
        """
        🔍 Debug Zone calculation สำหรับราคาที่กำหนด
        
        Args:
            price: ราคาที่ต้องการ debug
        """
        try:
            logger.info(f"🔍 Debugging Zone Calculation for Price: {price:.2f}")
            debug_info = self.zone_manager.debug_zone_calculation(price)
            return debug_info
        except Exception as e:
            logger.error(f"❌ Error debugging zone calculation: {e}")
            return None
    
    def _evaluate_portfolio_impact_before_closing(self, positions_to_close: List[Any]) -> Dict[str, Any]:
        """
        🎯 ประเมินผลกระทบต่อ Portfolio ก่อนปิด Position
        
        Args:
            positions_to_close: รายการ Position ที่จะปิด
            
        Returns:
            Dict: ข้อมูลผลกระทบ
        """
        try:
            if not positions_to_close:
                return {
                    'safe_to_close': True,
                    'reason': 'No positions to close',
                    'impact_description': 'No impact'
                }
            
            # คำนวณ P&L ที่จะได้จากการปิด
            closing_pnl = sum(getattr(pos, 'profit', 0.0) for pos in positions_to_close)
            closing_count = len(positions_to_close)
            
            # ดึงข้อมูล Portfolio ปัจจุบัน
            all_positions = self.order_manager.active_positions or []
            current_portfolio_pnl = sum(getattr(pos, 'profit', 0.0) for pos in all_positions)
            remaining_positions_count = len(all_positions) - closing_count
            
            # คำนวณ Portfolio P&L หลังปิด
            portfolio_pnl_after = current_portfolio_pnl - closing_pnl
            
            # เงื่อนไขการตัดสินใจ
            safe_to_close = True
            reason = "Safe to close"
            impact_description = f"Close {closing_count} positions, P&L: ${closing_pnl:.2f}"
            
            # 1. ตรวจสอบการปิดทำให้ Portfolio P&L แย่ลง (ปรับให้อ่อนลง)
            # ถ้า Portfolio ขาดทุนอยู่แล้ว ให้ปิดกำไรได้
            if closing_pnl > 0:
                if current_portfolio_pnl > 0 and portfolio_pnl_after < current_portfolio_pnl * 0.7:
                    safe_to_close = False
                    reason = "Closing would significantly worsen profitable portfolio"
                    impact_description += f" → Portfolio P&L: ${current_portfolio_pnl:.2f} → ${portfolio_pnl_after:.2f}"
                elif current_portfolio_pnl < 0 and closing_pnl < abs(current_portfolio_pnl) * 0.1:
                    safe_to_close = False
                    reason = "Profit too small compared to portfolio loss"
                    impact_description += f" → Portfolio P&L: ${current_portfolio_pnl:.2f} → ${portfolio_pnl_after:.2f}"
            
            # 2. ตรวจสอบว่าเหลือ Position น้อยเกินไป
            elif remaining_positions_count < 3:
                safe_to_close = False
                reason = f"Would leave only {remaining_positions_count} positions in portfolio"
                impact_description += f" → {remaining_positions_count} positions remaining"
            
            # 3. ตรวจสอบว่ากำไรน้อยเกินไป (ปรับให้ยืดหยุ่น)
            elif closing_pnl < 5.0:  # ลดจาก $10 เป็น $5
                safe_to_close = False
                reason = f"Profit too small (${closing_pnl:.2f} < $5.00)"
                impact_description += " → Profit too small"
            
            else:
                impact_description += f" → Portfolio P&L: ${current_portfolio_pnl:.2f} → ${portfolio_pnl_after:.2f}"
            
            return {
                'safe_to_close': safe_to_close,
                'reason': reason,
                'impact_description': impact_description,
                'closing_pnl': closing_pnl,
                'current_portfolio_pnl': current_portfolio_pnl,
                'portfolio_pnl_after': portfolio_pnl_after,
                'remaining_positions': remaining_positions_count
            }
            
        except Exception as e:
            logger.error(f"❌ Error evaluating portfolio impact: {e}")
            return {
                'safe_to_close': False,
                'reason': f'Error in evaluation: {str(e)}',
                'impact_description': 'Unknown impact'
            }
    
    def get_zone_price_ranges(self) -> List[Dict[str, Any]]:
        """
        📊 ดึงข้อมูลช่วงราคาของแต่ละ Zone
        
        Returns:
            List[Dict]: รายการ Zone และช่วงราคา
        """
        try:
            zone_ranges = []
            
            for zone_id, zone in self.zone_manager.zones.items():
                if zone.total_positions > 0:
                    zone_ranges.append({
                        'zone_id': zone_id,
                        'price_min': zone.price_min,
                        'price_max': zone.price_max,
                        'price_center': (zone.price_min + zone.price_max) / 2,
                        'size_pips': (zone.price_max - zone.price_min) * 100,  # แปลงเป็น pips
                        'total_positions': zone.total_positions,
                        'buy_count': zone.buy_count,
                        'sell_count': zone.sell_count,
                        'total_pnl': zone.total_pnl,
                        'balance_ratio': zone.balance_ratio
                    })
            
            # เรียงตามราคา
            zone_ranges.sort(key=lambda x: x['price_center'])
            
            return zone_ranges
            
        except Exception as e:
            logger.error(f"❌ Error getting zone price ranges: {e}")
            return []
    
    def log_zone_price_ranges(self):
        """
        📊 แสดงช่วงราคาของแต่ละ Zone
        """
        try:
            zone_ranges = self.get_zone_price_ranges()
            
            if not zone_ranges:
                logger.info("📊 No active zones to display")
                return
            
            logger.info("=" * 80)
            logger.info("📊 ZONE PRICE RANGES & STATUS")
            logger.info("=" * 80)
            
            for zone_range in zone_ranges:
                zone_id = zone_range['zone_id']
                balance_status = "⚖️ BALANCED"
                
                if zone_range['balance_ratio'] > 0.7:
                    balance_status = "📈 BUY-HEAVY"
                elif zone_range['balance_ratio'] < 0.3:
                    balance_status = "📉 SELL-HEAVY"
                
                pnl_status = "💚" if zone_range['total_pnl'] > 0 else "🔴"
                
                logger.info(f"Zone {zone_id:2d} [{zone_range['price_min']:8.2f} - {zone_range['price_max']:8.2f}] "
                           f"({zone_range['size_pips']:3.0f} pips)")
                logger.info(f"        Positions: B{zone_range['buy_count']:2d}:S{zone_range['sell_count']:2d} | "
                           f"P&L: ${zone_range['total_pnl']:+7.2f} {pnl_status} | {balance_status}")
                logger.info("")
            
            # สรุปรวม
            total_zones = len(zone_ranges)
            total_positions = sum(z['total_positions'] for z in zone_ranges)
            total_pnl = sum(z['total_pnl'] for z in zone_ranges)
            
            logger.info(f"📊 Summary: {total_zones} zones, {total_positions} positions, ${total_pnl:+.2f} total P&L")
            logger.info("=" * 80)
            
        except Exception as e:
            logger.error(f"❌ Error logging zone price ranges: {e}")
    
    def close_positions(self, positions_to_close: List[Any]) -> Dict[str, Any]:
        """
        🎯 ปิด Positions แบบ Zone-Based (เรียกใช้ Order Manager)
        
        Args:
            positions_to_close: รายการ ZonePosition หรือ Position ที่ต้องปิด
            
        Returns:
            Dict: ผลการปิด
        """
        try:
            if not positions_to_close:
                return {
                    'success': False,
                    'message': 'No positions to close',
                    'closed_count': 0,
                    'total_profit': 0.0
                }
            
            # แปลง ZonePosition เป็น Position objects สำหรับ Order Manager
            position_objects = []
            zone_info = []
            
            for pos in positions_to_close:
                # ถ้าเป็น ZonePosition ให้แปลงเป็น Position
                if hasattr(pos, 'ticket'):  # ZonePosition
                    position_obj = Position(
                        ticket=pos.ticket,
                        symbol=pos.symbol,
                        type=pos.type,
                        volume=pos.volume,
                        price_open=pos.price_open,
                        price_current=pos.price_current,
                        profit=pos.profit,
                        comment=f"Zone-based closing"
                    )
                    position_objects.append(position_obj)
                    
                    # เก็บข้อมูล Zone สำหรับ logging
                    zone_id = self.zone_manager.calculate_zone_id(pos.price_open)
                    zone_info.append(f"Zone {zone_id}")
                    
                else:  # Position object ปกติ
                    position_objects.append(pos)
                    zone_id = self.zone_manager.calculate_zone_id(getattr(pos, 'price_open', 0))
                    zone_info.append(f"Zone {zone_id}")
            
            # สร้างเหตุผลการปิด
            unique_zones = list(set(zone_info))
            if len(unique_zones) == 1:
                reason = f"Zone-based closing: {unique_zones[0]}"
            else:
                reason = f"Multi-zone closing: {', '.join(unique_zones[:3])}"
                if len(unique_zones) > 3:
                    reason += f" (+{len(unique_zones)-3} more)"
            
            # ใช้ Order Manager ปิด Positions
            close_result = self.order_manager.close_positions_group(position_objects, reason)
            
            if close_result.success:
                closed_count = len(close_result.closed_tickets)
                total_profit = close_result.total_profit if hasattr(close_result, 'total_profit') else 0.0
                
                logger.info(f"✅ Zone-based closing: {closed_count}/{len(positions_to_close)} positions closed")
                logger.info(f"💰 Zones affected: {', '.join(unique_zones)} | Profit: ${total_profit:.2f}")
                
                return {
                    'success': True,
                    'message': f'Successfully closed {closed_count} positions from zones',
                    'closed_count': closed_count,
                    'total_profit': total_profit,
                    'zones_affected': unique_zones,
                    'reason': reason
                }
            else:
                logger.warning(f"❌ Zone-based closing failed: {close_result.error_message}")
                return {
                    'success': False,
                    'message': close_result.error_message,
                    'closed_count': 0,
                    'total_profit': 0.0
                }
                
        except Exception as e:
            logger.error(f"❌ Error in zone-based position closing: {e}")
            return {
                'success': False,
                'message': str(e),
                'closed_count': 0,
                'total_profit': 0.0
            }
    
    def get_zone_status(self) -> Dict[str, Any]:
        """ดึงสถานะ Zone System"""
        zone_summary = self.zone_manager.get_zone_summary()
        coordination_summary = self.zone_coordinator.get_coordination_summary()
        
        return {
            'zone_system': zone_summary,
            'coordination': coordination_summary,
            'active_support_plans': len(self.active_support_plans),
            'last_analysis': self.last_analysis_time,
            'system_status': 'ACTIVE' if zone_summary.get('total_zones', 0) > 0 else 'IDLE'
        }


# ==========================================
# 🎯 HELPER FUNCTIONS
# ==========================================

def create_zone_position_manager(mt5_connection, order_manager, zone_size_pips: float = 30.0) -> ZonePositionManager:
    """
    สร้าง Zone Position Manager instance
    
    Args:
        mt5_connection: MT5 Connection instance
        order_manager: Order Manager instance
        zone_size_pips: ขนาด Zone ในหน่วย pips
        
    Returns:
        ZonePositionManager: Zone Position Manager instance
    """
    return ZonePositionManager(mt5_connection, order_manager, zone_size_pips)

if __name__ == "__main__":
    # Demo Zone Position Management
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    logger.info("🎯 Zone Position Manager Demo")
    logger.info("This demo requires MT5 connection and actual position data")
    logger.info("Zone-based system ready for integration!")
