# -*- coding: utf-8 -*-
"""
Zone Analyzer - วิเคราะห์ Zone Health และ Performance
วิเคราะห์ความสุขภาพของแต่ละ Zone และหาโอกาสในการปรับปรุง

🎯 หลักการ Zone Analysis:
1. วิเคราะห์ Zone Health Score แบบละเอียด
2. หา Zone Patterns และ Trends
3. คำนวณ Risk และ Opportunity
4. สนับสนุน Decision Making

✅ วิเคราะห์ลึก ✅ ตัดสินใจแม่นยำ ✅ ลดความเสี่ยง
"""

import logging
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from zone_manager import Zone, ZoneManager, ZonePosition

logger = logging.getLogger(__name__)

@dataclass
class ZoneAnalysis:
    """ผลการวิเคราะห์ Zone"""
    zone_id: int
    
    # Basic Metrics
    health_score: float
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    profit_potential: float
    
    # Financial Analysis
    total_pnl: float
    unrealized_pnl: float
    realized_pnl: float
    max_loss: float
    max_profit: float
    
    # Balance Analysis
    balance_score: float
    imbalance_severity: str  # BALANCED, MILD, MODERATE, SEVERE
    dominant_side: str  # BUY, SELL, BALANCED
    
    # Position Analysis
    avg_age_minutes: float
    avg_distance_pips: float
    position_quality: str  # EXCELLENT, GOOD, FAIR, POOR
    
    # Recommendations
    action_needed: str  # HOLD, REBALANCE, CLOSE, RECOVER
    priority: str  # LOW, MEDIUM, HIGH, URGENT
    confidence: float  # 0.0-1.0

@dataclass
class ZoneComparison:
    """การเปรียบเทียบ Zones"""
    zone_pairs: List[Tuple[int, int]]
    synergy_score: float
    cooperation_potential: float
    combined_health: float
    recommended_action: str

@dataclass
class BalanceRecoveryAnalysis:
    """การวิเคราะห์ Balance Recovery ระหว่าง Zones"""
    zone_id: int
    imbalance_type: str  # BUY_HEAVY, SELL_HEAVY, BALANCED
    excess_positions: int
    excess_type: str  # BUY, SELL, NONE
    recovery_candidates: List[Any]  # Positions ที่เหมาะสมสำหรับ Recovery
    health_improvement_score: float  # คะแนนการปรับปรุง Zone หลังปิดไม้
    cooperation_readiness: float  # ความพร้อมในการร่วมมือ

@dataclass
class CrossZoneBalancePlan:
    """แผนการ Balance Recovery ระหว่าง Zones"""
    primary_zone: int
    partner_zone: int
    recovery_type: str  # BALANCE_RECOVERY, MUTUAL_SUPPORT
    positions_to_close: List[Tuple[int, Any]]  # (zone_id, position)
    expected_profit: float
    health_improvement: Dict[int, float]  # zone_id -> improvement_score
    execution_priority: str  # LOW, MEDIUM, HIGH, URGENT
    confidence_score: float

class ZoneAnalyzer:
    """🔍 Zone Analyzer - วิเคราะห์ Zone Health และ Performance"""
    
    def __init__(self, zone_manager: ZoneManager):
        """
        เริ่มต้น Zone Analyzer
        
        Args:
            zone_manager: Zone Manager instance
        """
        self.zone_manager = zone_manager
        
        # Analysis Configuration
        self.health_thresholds = {
            'excellent': 80.0,
            'good': 60.0,
            'fair': 40.0,
            'poor': 20.0
        }
        
        self.risk_thresholds = {
            'low': -50.0,
            'medium': -100.0,
            'high': -200.0,
            'critical': -300.0
        }
        
        self.imbalance_thresholds = {
            'balanced': 0.6,    # 40:60 ถือว่าสมดุล
            'mild': 0.7,        # 30:70 เสียสมดุลเล็กน้อย
            'moderate': 0.8,    # 20:80 เสียสมดุลปานกลาง
            'severe': 0.9       # 10:90 เสียสมดุลรุนแรง
        }
        
        logger.info("🔍 Zone Analyzer initialized")
    
    def analyze_zone(self, zone: Zone, current_price: float) -> ZoneAnalysis:
        """
        วิเคราะห์ Zone แบบละเอียด
        
        Args:
            zone: Zone ที่ต้องการวิเคราะห์
            current_price: ราคาปัจจุบัน
            
        Returns:
            ZoneAnalysis: ผลการวิเคราะห์
        """
        try:
            # Basic Health Score
            health_score = zone.health_score
            
            # Financial Analysis
            total_pnl = zone.total_pnl
            unrealized_pnl = self._calculate_unrealized_pnl(zone, current_price)
            realized_pnl = total_pnl - unrealized_pnl
            
            max_loss = min(pos.profit for pos in zone.positions) if zone.positions else 0.0
            max_profit = max(pos.profit for pos in zone.positions) if zone.positions else 0.0
            
            # Balance Analysis
            balance_score, imbalance_severity, dominant_side = self._analyze_balance(zone)
            
            # Position Analysis
            avg_age_minutes = sum(pos.age_minutes for pos in zone.positions) / len(zone.positions) if zone.positions else 0.0
            avg_distance_pips = sum(pos.distance_pips for pos in zone.positions) / len(zone.positions) if zone.positions else 0.0
            
            # Risk Assessment
            risk_level = self._assess_risk_level(zone, current_price)
            
            # Profit Potential
            profit_potential = self._calculate_profit_potential(zone, current_price)
            
            # Position Quality
            position_quality = self._assess_position_quality(zone)
            
            # Recommendations
            action_needed, priority, confidence = self._generate_recommendations(zone, health_score, risk_level)
            
            return ZoneAnalysis(
                zone_id=zone.zone_id,
                health_score=health_score,
                risk_level=risk_level,
                profit_potential=profit_potential,
                total_pnl=total_pnl,
                unrealized_pnl=unrealized_pnl,
                realized_pnl=realized_pnl,
                max_loss=max_loss,
                max_profit=max_profit,
                balance_score=balance_score,
                imbalance_severity=imbalance_severity,
                dominant_side=dominant_side,
                avg_age_minutes=avg_age_minutes,
                avg_distance_pips=avg_distance_pips,
                position_quality=position_quality,
                action_needed=action_needed,
                priority=priority,
                confidence=confidence
            )
            
        except Exception as e:
            logger.error(f"❌ Error analyzing zone {zone.zone_id}: {e}")
            # Return default analysis
            return ZoneAnalysis(
                zone_id=zone.zone_id,
                health_score=0.0,
                risk_level='HIGH',
                profit_potential=0.0,
                total_pnl=0.0,
                unrealized_pnl=0.0,
                realized_pnl=0.0,
                max_loss=0.0,
                max_profit=0.0,
                balance_score=0.0,
                imbalance_severity='UNKNOWN',
                dominant_side='UNKNOWN',
                avg_age_minutes=0.0,
                avg_distance_pips=0.0,
                position_quality='UNKNOWN',
                action_needed='HOLD',
                priority='LOW',
                confidence=0.0
            )
    
    def _calculate_unrealized_pnl(self, zone: Zone, current_price: float) -> float:
        """คำนวณ Unrealized P&L"""
        unrealized = 0.0
        
        for pos in zone.positions:
            if pos.type == 0:  # BUY
                unrealized += (current_price - pos.price_open) * pos.volume * 100
            else:  # SELL
                unrealized += (pos.price_open - current_price) * pos.volume * 100
                
        return unrealized
    
    def _analyze_balance(self, zone: Zone) -> Tuple[float, str, str]:
        """วิเคราะห์ความสมดุลของ Zone"""
        if zone.total_positions == 0:
            return 0.0, 'UNKNOWN', 'UNKNOWN'
            
        buy_ratio = zone.buy_count / zone.total_positions
        sell_ratio = zone.sell_count / zone.total_positions
        
        # Balance Score (0-100)
        if buy_ratio == 0.5:
            balance_score = 100.0  # Perfect balance
        else:
            deviation = abs(buy_ratio - 0.5)
            balance_score = max(0.0, 100.0 - (deviation * 200))
        
        # Imbalance Severity
        max_ratio = max(buy_ratio, sell_ratio)
        if max_ratio <= self.imbalance_thresholds['balanced']:
            imbalance_severity = 'BALANCED'
        elif max_ratio <= self.imbalance_thresholds['mild']:
            imbalance_severity = 'MILD'
        elif max_ratio <= self.imbalance_thresholds['moderate']:
            imbalance_severity = 'MODERATE'
        else:
            imbalance_severity = 'SEVERE'
        
        # Dominant Side
        if buy_ratio > 0.6:
            dominant_side = 'BUY'
        elif sell_ratio > 0.6:
            dominant_side = 'SELL'
        else:
            dominant_side = 'BALANCED'
            
        return balance_score, imbalance_severity, dominant_side
    
    def _assess_risk_level(self, zone: Zone, current_price: float) -> str:
        """ประเมินระดับความเสี่ยง"""
        # Base risk from P&L
        if zone.total_pnl >= self.risk_thresholds['low']:
            risk_level = 'LOW'
        elif zone.total_pnl >= self.risk_thresholds['medium']:
            risk_level = 'MEDIUM'
        elif zone.total_pnl >= self.risk_thresholds['high']:
            risk_level = 'HIGH'
        else:
            risk_level = 'CRITICAL'
        
        # Adjust for other factors
        if zone.balance_ratio < 0.2 or zone.balance_ratio > 0.8:
            # Severe imbalance increases risk
            if risk_level == 'LOW':
                risk_level = 'MEDIUM'
            elif risk_level == 'MEDIUM':
                risk_level = 'HIGH'
        
        # High age positions increase risk
        if zone.positions:
            avg_age = sum(pos.age_minutes for pos in zone.positions) / len(zone.positions)
            if avg_age > 240:  # 4 hours
                if risk_level == 'LOW':
                    risk_level = 'MEDIUM'
                    
        return risk_level
    
    def _calculate_profit_potential(self, zone: Zone, current_price: float) -> float:
        """คำนวณศักยภาพกำไร"""
        if not zone.positions:
            return 0.0
            
        potential = 0.0
        
        for pos in zone.positions:
            # คำนวณ potential จากการปิดที่ราคาปัจจุบัน
            if pos.type == 0:  # BUY
                pos_potential = (current_price - pos.price_open) * pos.volume * 100
            else:  # SELL
                pos_potential = (pos.price_open - current_price) * pos.volume * 100
                
            potential += max(0, pos_potential)  # เฉพาะที่มีกำไร
            
        return potential
    
    def _assess_position_quality(self, zone: Zone) -> str:
        """ประเมินคุณภาพ Positions"""
        if not zone.positions:
            return 'UNKNOWN'
            
        profit_ratio = zone.profit_positions / zone.total_positions
        avg_profit = zone.total_pnl / zone.total_positions
        
        # Score based on profit ratio and average profit
        quality_score = (profit_ratio * 50) + min(avg_profit, 50)
        
        if quality_score >= 70:
            return 'EXCELLENT'
        elif quality_score >= 50:
            return 'GOOD'
        elif quality_score >= 30:
            return 'FAIR'
        else:
            return 'POOR'
    
    def _generate_recommendations(self, zone: Zone, health_score: float, risk_level: str) -> Tuple[str, str, float]:
        """สร้างคำแนะนำ"""
        confidence = 0.7  # Base confidence
        
        # Action based on health and risk
        if health_score >= 70 and risk_level == 'LOW':
            action = 'HOLD'
            priority = 'LOW'
            confidence = 0.9
        elif health_score >= 50 and risk_level in ['LOW', 'MEDIUM']:
            action = 'HOLD'
            priority = 'MEDIUM'
            confidence = 0.8
        elif zone.balance_ratio < 0.3 or zone.balance_ratio > 0.7:
            action = 'REBALANCE'
            priority = 'HIGH'
            confidence = 0.8
        elif risk_level == 'CRITICAL' or zone.total_pnl < -200:
            action = 'RECOVER'
            priority = 'URGENT'
            confidence = 0.9
        elif zone.total_pnl > 100:
            action = 'CLOSE'
            priority = 'MEDIUM'
            confidence = 0.7
        else:
            action = 'HOLD'
            priority = 'MEDIUM'
            confidence = 0.6
            
        return action, priority, confidence
    
    def analyze_all_zones(self, current_price: float) -> Dict[int, ZoneAnalysis]:
        """
        วิเคราะห์ Zones ทั้งหมด
        
        Args:
            current_price: ราคาปัจจุบัน
            
        Returns:
            Dict[int, ZoneAnalysis]: ผลการวิเคราะห์ทุก Zones
        """
        analyses = {}
        
        for zone_id, zone in self.zone_manager.zones.items():
            if zone.total_positions > 0:
                analyses[zone_id] = self.analyze_zone(zone, current_price)
                
        return analyses
    
    def find_cooperation_opportunities(self, analyses: Dict[int, ZoneAnalysis]) -> List[ZoneComparison]:
        """
        หาโอกาสความร่วมมือระหว่าง Zones
        
        Args:
            analyses: ผลการวิเคราะห์ Zones
            
        Returns:
            List[ZoneComparison]: โอกาสความร่วมมือ
        """
        opportunities = []
        
        # หา Helper และ Troubled Zones
        helper_zones = [zone_id for zone_id, analysis in analyses.items() 
                       if analysis.total_pnl > 0 and analysis.risk_level in ['LOW', 'MEDIUM']]
        
        troubled_zones = [zone_id for zone_id, analysis in analyses.items() 
                         if analysis.total_pnl < 0 or analysis.risk_level in ['HIGH', 'CRITICAL']]
        
        # สร้าง Cooperation Pairs
        for helper_id in helper_zones:
            for troubled_id in troubled_zones:
                helper_analysis = analyses[helper_id]
                troubled_analysis = analyses[troubled_id]
                
                # คำนวณ Synergy Score
                synergy_score = self._calculate_synergy_score(helper_analysis, troubled_analysis)
                
                if synergy_score > 0.5:  # มีศักยภาพความร่วมมือ
                    cooperation = ZoneComparison(
                        zone_pairs=[(helper_id, troubled_id)],
                        synergy_score=synergy_score,
                        cooperation_potential=helper_analysis.profit_potential,
                        combined_health=(helper_analysis.health_score + troubled_analysis.health_score) / 2,
                        recommended_action='CROSS_ZONE_SUPPORT'
                    )
                    opportunities.append(cooperation)
        
        # เรียงตาม Synergy Score
        opportunities.sort(key=lambda x: x.synergy_score, reverse=True)
        
        return opportunities[:5]  # Top 5 opportunities
    
    def _calculate_synergy_score(self, helper: ZoneAnalysis, troubled: ZoneAnalysis) -> float:
        """คำนวณ Synergy Score ระหว่าง 2 Zones"""
        score = 0.0
        
        # Helper มีกำไรเพียงพอหรือไม่
        if helper.total_pnl > abs(troubled.total_pnl):
            score += 0.4
        elif helper.total_pnl > abs(troubled.total_pnl) * 0.5:
            score += 0.2
            
        # Balance Complementarity
        if helper.dominant_side != troubled.dominant_side and helper.dominant_side != 'BALANCED':
            score += 0.3
            
        # Risk Compatibility
        if helper.risk_level == 'LOW' and troubled.risk_level in ['HIGH', 'CRITICAL']:
            score += 0.2
        elif helper.risk_level == 'MEDIUM' and troubled.risk_level == 'CRITICAL':
            score += 0.1
            
        # Confidence Factor
        confidence_factor = (helper.confidence + troubled.confidence) / 2
        score *= confidence_factor
        
        return min(1.0, score)
    
    def generate_zone_report(self, analyses: Dict[int, ZoneAnalysis], current_price: float) -> str:
        """
        สร้างรายงาน Zone Analysis
        
        Args:
            analyses: ผลการวิเคราะห์ Zones
            current_price: ราคาปัจจุบัน
            
        Returns:
            str: รายงาน Zone Analysis
        """
        report = []
        report.append("=" * 60)
        report.append("🔍 ZONE ANALYSIS REPORT")
        report.append("=" * 60)
        
        if not analyses:
            report.append("No zones to analyze")
            return "\n".join(report)
        
        # Summary Statistics
        total_zones = len(analyses)
        avg_health = sum(a.health_score for a in analyses.values()) / total_zones
        total_pnl = sum(a.total_pnl for a in analyses.values())
        
        report.append(f"📊 Summary: {total_zones} zones, Avg Health: {avg_health:.1f}, Total P&L: ${total_pnl:+.2f}")
        report.append("")
        
        # Zone Details
        for zone_id in sorted(analyses.keys()):
            analysis = analyses[zone_id]
            zone = self.zone_manager.zones[zone_id]
            
            # Status Emoji
            status_emoji = {
                'LOW': '💚', 'MEDIUM': '🟡', 'HIGH': '🔴', 'CRITICAL': '💀'
            }.get(analysis.risk_level, '⚪')
            
            action_emoji = {
                'HOLD': '✋', 'REBALANCE': '⚖️', 'CLOSE': '💰', 'RECOVER': '🚀'
            }.get(analysis.action_needed, '❓')
            
            report.append(f"Zone {zone_id:2d} [{zone.price_min:.2f}-{zone.price_max:.2f}]:")
            report.append(f"  📊 Positions: B{zone.buy_count}:S{zone.sell_count} | "
                         f"P&L: ${analysis.total_pnl:+.2f} | Health: {analysis.health_score:.0f}")
            report.append(f"  🎯 Balance: {analysis.balance_score:.0f} ({analysis.imbalance_severity}) | "
                         f"Risk: {analysis.risk_level} {status_emoji}")
            report.append(f"  💡 Action: {analysis.action_needed} {action_emoji} | "
                         f"Priority: {analysis.priority} | Confidence: {analysis.confidence:.1f}")
            report.append("")
        
        # Cooperation Opportunities
        opportunities = self.find_cooperation_opportunities(analyses)
        if opportunities:
            report.append("🤝 COOPERATION OPPORTUNITIES:")
            for i, opp in enumerate(opportunities[:3], 1):
                helper_id, troubled_id = opp.zone_pairs[0]
                report.append(f"  {i}. Zone {helper_id} → Zone {troubled_id} "
                             f"(Synergy: {opp.synergy_score:.2f})")
        
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def detect_balance_recovery_opportunities(self, current_price: float) -> List[BalanceRecoveryAnalysis]:
        """
        🎯 หาโอกาส Balance Recovery ในแต่ละ Zone
        
        Args:
            current_price: ราคาปัจจุบัน
            
        Returns:
            List[BalanceRecoveryAnalysis]: รายการโอกาส Balance Recovery
        """
        opportunities = []
        
        try:
            for zone_id, zone in self.zone_manager.zones.items():
                if zone.total_positions >= 3:  # ต้องมีไม้อย่างน้อย 3 ตัว
                    analysis = self._analyze_zone_balance_recovery(zone, current_price)
                    if analysis.excess_positions > 0:
                        opportunities.append(analysis)
            
            # เรียงตาม Health Improvement Score
            opportunities.sort(key=lambda x: x.health_improvement_score, reverse=True)
            
            logger.debug(f"🎯 Found {len(opportunities)} balance recovery opportunities")
            return opportunities
            
        except Exception as e:
            logger.error(f"❌ Error detecting balance recovery opportunities: {e}")
            return []
    
    def _analyze_zone_balance_recovery(self, zone: Zone, current_price: float) -> BalanceRecoveryAnalysis:
        """
        วิเคราะห์ Balance Recovery สำหรับ Zone เดียว
        
        Args:
            zone: Zone ที่ต้องการวิเคราะห์
            current_price: ราคาปัจจุบัน
            
        Returns:
            BalanceRecoveryAnalysis: ผลการวิเคราะห์
        """
        try:
            total_positions = zone.total_positions
            buy_count = zone.buy_count
            sell_count = zone.sell_count
            
            if total_positions == 0:
                return BalanceRecoveryAnalysis(
                    zone_id=zone.zone_id,
                    imbalance_type='BALANCED',
                    excess_positions=0,
                    excess_type='NONE',
                    recovery_candidates=[],
                    health_improvement_score=0.0,
                    cooperation_readiness=0.0
                )
            
            # คำนวณ Imbalance
            buy_ratio = buy_count / total_positions
            sell_ratio = sell_count / total_positions
            
            # กำหนด Imbalance Type และ Excess
            if buy_ratio >= 0.7:  # BUY เกิน 70%
                imbalance_type = 'BUY_HEAVY'
                excess_type = 'BUY'
                excess_positions = buy_count - (total_positions // 2)
                candidates = [pos for pos in zone.positions if pos.type == 0]  # BUY positions
            elif sell_ratio >= 0.7:  # SELL เกิน 70%
                imbalance_type = 'SELL_HEAVY'
                excess_type = 'SELL'
                excess_positions = sell_count - (total_positions // 2)
                candidates = [pos for pos in zone.positions if pos.type == 1]  # SELL positions
            else:
                imbalance_type = 'BALANCED'
                excess_type = 'NONE'
                excess_positions = 0
                candidates = []
            
            # เลือก Recovery Candidates (เรียงตามกำไร → อายุน้อย → ระยะใกล้)
            recovery_candidates = []
            if excess_positions > 0 and candidates:
                sorted_candidates = sorted(candidates, key=lambda pos: (
                    -pos.profit,        # กำไรมากก่อน
                    pos.age_minutes,    # อายุน้อยก่อน
                    pos.distance_pips   # ระยะใกล้ก่อน
                ))
                recovery_candidates = sorted_candidates[:excess_positions]
            
            # คำนวณ Health Improvement Score
            health_improvement_score = self._calculate_zone_health_improvement(
                zone, recovery_candidates, current_price
            )
            
            # คำนวณ Cooperation Readiness
            cooperation_readiness = self._calculate_cooperation_readiness(
                zone, recovery_candidates, current_price
            )
            
            return BalanceRecoveryAnalysis(
                zone_id=zone.zone_id,
                imbalance_type=imbalance_type,
                excess_positions=excess_positions,
                excess_type=excess_type,
                recovery_candidates=recovery_candidates,
                health_improvement_score=health_improvement_score,
                cooperation_readiness=cooperation_readiness
            )
            
        except Exception as e:
            logger.error(f"❌ Error analyzing zone {zone.zone_id} balance recovery: {e}")
            return BalanceRecoveryAnalysis(
                zone_id=zone.zone_id,
                imbalance_type='UNKNOWN',
                excess_positions=0,
                excess_type='NONE',
                recovery_candidates=[],
                health_improvement_score=0.0,
                cooperation_readiness=0.0
            )
    
    def _calculate_zone_health_improvement(self, zone: Zone, candidates: List[Any], current_price: float) -> float:
        """
        🎯 คำนวณคะแนนการปรับปรุง Zone Health หลังจากปิดไม้
        
        Args:
            zone: Zone ปัจจุบัน
            candidates: Positions ที่จะปิด
            current_price: ราคาปัจจุบัน
            
        Returns:
            float: คะแนนการปรับปรุง (0-100)
        """
        try:
            if not candidates:
                return 0.0
            
            # คำนวณ Balance Improvement
            remaining_positions = zone.total_positions - len(candidates)
            if remaining_positions <= 0:
                return 0.0  # ไม่ปิดหมด
            
            # จำลอง Balance หลังปิดไม้
            remaining_buy = zone.buy_count
            remaining_sell = zone.sell_count
            
            for pos in candidates:
                if pos.type == 0:  # BUY
                    remaining_buy -= 1
                else:  # SELL
                    remaining_sell -= 1
            
            # คำนวณ Balance Score หลังปิด
            if remaining_positions > 0:
                new_buy_ratio = remaining_buy / remaining_positions
                new_balance_score = 100.0 - abs(new_buy_ratio - 0.5) * 200
            else:
                new_balance_score = 0.0
            
            # คำนวณ P&L Improvement
            candidates_profit = sum(pos.profit for pos in candidates)
            pnl_improvement = max(0, candidates_profit)  # เฉพาะกำไร
            
            # คำนวณ Risk Reduction
            candidates_loss = abs(min(0, candidates_profit))
            risk_reduction = candidates_loss * 0.5  # ลดความเสี่ยง
            
            # คำนวณ current balance score จาก balance_ratio
            current_balance_score = 100.0 - abs(zone.balance_ratio - 0.5) * 200
            
            # รวมคะแนน
            balance_factor = max(0, new_balance_score - current_balance_score) * 0.4
            profit_factor = min(50, pnl_improvement) * 0.4
            risk_factor = min(30, risk_reduction) * 0.2
            
            total_score = balance_factor + profit_factor + risk_factor
            
            return min(100.0, max(0.0, total_score))
            
        except Exception as e:
            logger.error(f"❌ Error calculating health improvement: {e}")
            return 0.0
    
    def _calculate_cooperation_readiness(self, zone: Zone, candidates: List[Any], current_price: float) -> float:
        """
        คำนวณความพร้อมในการร่วมมือกับ Zone อื่น
        
        Args:
            zone: Zone ปัจจุบัน
            candidates: Positions ที่จะปิด
            current_price: ราคาปัจจุบัน
            
        Returns:
            float: ความพร้อมในการร่วมมือ (0-1.0)
        """
        try:
            if not candidates:
                return 0.0
            
            # ปัจจัยความพร้อม
            readiness = 0.0
            
            # 1. Profit Potential (40%)
            total_profit = sum(pos.profit for pos in candidates)
            if total_profit > 0:
                readiness += 0.4 * min(1.0, total_profit / 50.0)  # ปรับตามกำไร
            
            # 2. Balance Necessity (30%)
            imbalance_severity = abs(zone.balance_ratio - 0.5) * 2  # 0-1
            readiness += 0.3 * imbalance_severity
            
            # 3. Zone Health (20%)
            zone_health = zone.health_score / 100.0
            readiness += 0.2 * (1.0 - zone_health)  # Zone แย่ = พร้อมร่วมมือมากขึ้น
            
            # 4. Position Quality (10%)
            avg_profit = total_profit / len(candidates) if candidates else 0
            if avg_profit > 0:
                readiness += 0.1
            
            return min(1.0, max(0.0, readiness))
            
        except Exception as e:
            logger.error(f"❌ Error calculating cooperation readiness: {e}")
            return 0.0
    
    def find_cross_zone_balance_pairs_with_7d(self, recovery_analyses: List[BalanceRecoveryAnalysis], position_scores: List[Any] = None) -> List[CrossZoneBalancePlan]:
        """
        🎯 หาคู่ Zone ที่สามารถทำ Balance Recovery ร่วมกันได้ + 7D Intelligence
        
        Args:
            recovery_analyses: รายการ Balance Recovery Analysis
            position_scores: 7D scores from IntelligentPositionManager
            
        Returns:
            List[CrossZoneBalancePlan]: แผน Balance Recovery ระหว่าง Zones (enhanced with 7D)
        """
        if position_scores:
            logger.info(f"🎯 Cross-Zone Balance Recovery with 7D Intelligence: {len(position_scores)} scored positions")
            return self._find_cross_zone_pairs_with_7d_scoring(recovery_analyses, position_scores)
        else:
            logger.info(f"⚠️ No 7D scores available, using standard Cross-Zone analysis")
            return self.find_cross_zone_balance_pairs(recovery_analyses)
    
    def find_cross_zone_balance_pairs(self, recovery_analyses: List[BalanceRecoveryAnalysis]) -> List[CrossZoneBalancePlan]:
        """
        🤝 หาคู่ Zone ที่สามารถทำ Balance Recovery ร่วมกันได้
        
        Args:
            recovery_analyses: รายการ Balance Recovery Analysis
            
        Returns:
            List[CrossZoneBalancePlan]: แผน Balance Recovery ระหว่าง Zones
        """
        balance_plans = []
        
        try:
            # แยก Zones ตาม Imbalance Type
            buy_heavy_zones = [a for a in recovery_analyses if a.imbalance_type == 'BUY_HEAVY']
            sell_heavy_zones = [a for a in recovery_analyses if a.imbalance_type == 'SELL_HEAVY']
            
            # จับคู่ BUY_HEAVY กับ SELL_HEAVY
            for buy_analysis in buy_heavy_zones:
                for sell_analysis in sell_heavy_zones:
                    plan = self._create_balance_recovery_plan(buy_analysis, sell_analysis)
                    if plan.confidence_score > 0.5:  # มีความเป็นไปได้
                        balance_plans.append(plan)
            
            # เรียงตาม Expected Profit และ Health Improvement
            balance_plans.sort(key=lambda x: (
                x.expected_profit,
                sum(x.health_improvement.values()),
                x.confidence_score
            ), reverse=True)
            
            logger.debug(f"🤝 Found {len(balance_plans)} cross-zone balance recovery plans")
            return balance_plans[:10]  # Top 10 plans
            
        except Exception as e:
            logger.error(f"❌ Error finding cross-zone balance pairs: {e}")
            return []
    
    def _create_balance_recovery_plan(self, buy_analysis: BalanceRecoveryAnalysis, sell_analysis: BalanceRecoveryAnalysis) -> CrossZoneBalancePlan:
        """
        สร้างแผน Balance Recovery ระหว่าง 2 Zones
        
        Args:
            buy_analysis: Zone ที่ BUY เกิน
            sell_analysis: Zone ที่ SELL เกิน
            
        Returns:
            CrossZoneBalancePlan: แผน Balance Recovery
        """
        try:
            # คำนวณจำนวนไม้ที่จะปิด
            positions_to_close_count = min(
                buy_analysis.excess_positions,
                sell_analysis.excess_positions,
                3  # จำกัดไม่เกิน 3 คู่ต่อครั้ง
            )
            
            if positions_to_close_count <= 0:
                return CrossZoneBalancePlan(
                    primary_zone=buy_analysis.zone_id,
                    partner_zone=sell_analysis.zone_id,
                    recovery_type='BALANCE_RECOVERY',
                    positions_to_close=[],
                    expected_profit=0.0,
                    health_improvement={},
                    execution_priority='LOW',
                    confidence_score=0.0
                )
            
            # เลือกไม้ที่จะปิด
            positions_to_close = []
            
            # เลือก BUY positions จาก BUY_HEAVY zone
            buy_candidates = buy_analysis.recovery_candidates[:positions_to_close_count]
            for pos in buy_candidates:
                positions_to_close.append((buy_analysis.zone_id, pos))
            
            # เลือก SELL positions จาก SELL_HEAVY zone  
            sell_candidates = sell_analysis.recovery_candidates[:positions_to_close_count]
            for pos in sell_candidates:
                positions_to_close.append((sell_analysis.zone_id, pos))
            
            # คำนวณ Expected Profit
            expected_profit = 0.0
            for zone_id, pos in positions_to_close:
                expected_profit += max(0, pos.profit)  # เฉพาะกำไร
            
            # คำนวณ Health Improvement
            health_improvement = {
                buy_analysis.zone_id: buy_analysis.health_improvement_score,
                sell_analysis.zone_id: sell_analysis.health_improvement_score
            }
            
            # กำหนด Execution Priority
            avg_health_improvement = sum(health_improvement.values()) / len(health_improvement)
            total_readiness = buy_analysis.cooperation_readiness + sell_analysis.cooperation_readiness
            
            if expected_profit > 100 and avg_health_improvement > 60:
                execution_priority = 'URGENT'
            elif expected_profit > 50 and avg_health_improvement > 40:
                execution_priority = 'HIGH'
            elif expected_profit > 20 or avg_health_improvement > 30:
                execution_priority = 'MEDIUM'
            else:
                execution_priority = 'LOW'
            
            # คำนวณ Confidence Score
            profit_factor = min(1.0, expected_profit / 100.0) * 0.3
            health_factor = (avg_health_improvement / 100.0) * 0.4
            readiness_factor = (total_readiness / 2.0) * 0.3
            
            confidence_score = profit_factor + health_factor + readiness_factor
            
            return CrossZoneBalancePlan(
                primary_zone=buy_analysis.zone_id,
                partner_zone=sell_analysis.zone_id,
                recovery_type='BALANCE_RECOVERY',
                positions_to_close=positions_to_close,
                expected_profit=expected_profit,
                health_improvement=health_improvement,
                execution_priority=execution_priority,
                confidence_score=min(1.0, confidence_score)
            )
            
        except Exception as e:
            logger.error(f"❌ Error creating balance recovery plan: {e}")
            return CrossZoneBalancePlan(
                primary_zone=buy_analysis.zone_id,
                partner_zone=sell_analysis.zone_id,
                recovery_type='BALANCE_RECOVERY',
                positions_to_close=[],
                expected_profit=0.0,
                health_improvement={},
                execution_priority='LOW',
                confidence_score=0.0
            )
    
    def _find_cross_zone_pairs_with_7d_scoring(self, recovery_analyses: List[BalanceRecoveryAnalysis], position_scores: List[Any]) -> List[CrossZoneBalancePlan]:
        """
        🎯 หาคู่ Cross-Zone ด้วย 7D Intelligence
        
        Args:
            recovery_analyses: รายการ Balance Recovery Analysis
            position_scores: 7D scores from IntelligentPositionManager
            
        Returns:
            List[CrossZoneBalancePlan]: แผน Balance Recovery ที่ใช้ 7D scoring
        """
        try:
            logger.info(f"🎯 7D Cross-Zone Analysis: {len(recovery_analyses)} zones, {len(position_scores)} scored positions")
            
            # สร้าง position_scores mapping
            position_score_map = {}
            for pos_score in position_scores:
                ticket = pos_score.position.ticket
                position_score_map[ticket] = pos_score.total_score
            
            balance_plans = []
            
            # แยก Zones ตาม Imbalance Type
            buy_heavy_zones = [a for a in recovery_analyses if a.imbalance_type == 'BUY_HEAVY']
            sell_heavy_zones = [a for a in recovery_analyses if a.imbalance_type == 'SELL_HEAVY']
            
            # จับคู่ BUY_HEAVY กับ SELL_HEAVY ด้วย 7D intelligence
            for buy_analysis in buy_heavy_zones:
                for sell_analysis in sell_heavy_zones:
                    plan = self._create_7d_enhanced_balance_plan(buy_analysis, sell_analysis, position_score_map)
                    if plan.confidence_score > 0.3:  # Lower threshold เพราะใช้ 7D
                        balance_plans.append(plan)
            
            # เรียงตาม 7D Score, Expected Profit, และ Health Improvement
            balance_plans.sort(key=lambda x: (
                getattr(x, 'avg_7d_score', 0),  # 7D Score เป็นอันดับแรก
                x.expected_profit,
                sum(x.health_improvement.values()),
                x.confidence_score
            ), reverse=True)
            
            logger.info(f"🎯 Found {len(balance_plans)} 7D-enhanced cross-zone balance plans")
            return balance_plans[:10]  # Top 10 plans
            
        except Exception as e:
            logger.error(f"❌ Error in 7D cross-zone analysis: {e}")
            return []
    
    def _create_7d_enhanced_balance_plan(self, buy_analysis: BalanceRecoveryAnalysis, sell_analysis: BalanceRecoveryAnalysis, position_score_map: dict) -> CrossZoneBalancePlan:
        """
        สร้างแผน Balance Recovery ด้วย 7D Intelligence
        
        Args:
            buy_analysis: Zone ที่ BUY เกิน
            sell_analysis: Zone ที่ SELL เกิน
            position_score_map: mapping ticket -> 7D score
            
        Returns:
            CrossZoneBalancePlan: แผน Balance Recovery enhanced ด้วย 7D
        """
        try:
            # เลือก positions ตาม 7D score
            buy_candidates_with_7d = []
            for pos in buy_analysis.recovery_candidates:
                ticket = pos.ticket
                score_7d = position_score_map.get(ticket, 0)
                buy_candidates_with_7d.append({'position': pos, 'score_7d': score_7d, 'pnl': pos.profit})
            
            sell_candidates_with_7d = []
            for pos in sell_analysis.recovery_candidates:
                ticket = pos.ticket
                score_7d = position_score_map.get(ticket, 0)
                sell_candidates_with_7d.append({'position': pos, 'score_7d': score_7d, 'pnl': pos.profit})
            
            # เรียงตาม 7D score (ดีที่สุดก่อน)
            buy_candidates_with_7d.sort(key=lambda x: x['score_7d'], reverse=True)
            sell_candidates_with_7d.sort(key=lambda x: x['score_7d'], reverse=True)
            
            # เลือกจำนวนที่เหมาะสม
            positions_to_close_count = min(
                len(buy_candidates_with_7d),
                len(sell_candidates_with_7d),
                3  # จำกัดไม่เกิน 3 คู่
            )
            
            if positions_to_close_count <= 0:
                return self._create_empty_balance_plan(buy_analysis.zone_id, sell_analysis.zone_id)
            
            # เลือก top positions ตาม 7D score
            selected_buys = buy_candidates_with_7d[:positions_to_close_count]
            selected_sells = sell_candidates_with_7d[:positions_to_close_count]
            
            positions_to_close = []
            expected_profit = 0
            total_7d_score = 0
            
            # เพิ่ม BUY positions
            for candidate in selected_buys:
                pos = candidate['position']
                positions_to_close.append((buy_analysis.zone_id, pos))
                expected_profit += pos.profit
                total_7d_score += candidate['score_7d']
            
            # เพิ่ม SELL positions
            for candidate in selected_sells:
                pos = candidate['position']
                positions_to_close.append((sell_analysis.zone_id, pos))
                expected_profit += pos.profit
                total_7d_score += candidate['score_7d']
            
            avg_7d_score = total_7d_score / (len(selected_buys) + len(selected_sells)) if positions_to_close else 0
            
            # คำนวณ Health Improvement
            health_improvement = {
                buy_analysis.zone_id: min(positions_to_close_count * 0.1, 0.3),
                sell_analysis.zone_id: min(positions_to_close_count * 0.1, 0.3)
            }
            
            # คำนวณ Confidence Score ด้วย 7D
            confidence_score = min(0.5 + (avg_7d_score / 100.0), 0.95)
            
            plan = CrossZoneBalancePlan(
                primary_zone=buy_analysis.zone_id,
                partner_zone=sell_analysis.zone_id,
                recovery_type='7D_BALANCE_RECOVERY',
                positions_to_close=positions_to_close,
                expected_profit=expected_profit,
                health_improvement=health_improvement,
                execution_priority='HIGH' if avg_7d_score > 60 else 'MEDIUM',
                confidence_score=confidence_score
            )
            
            # เพิ่ม 7D metadata
            setattr(plan, 'avg_7d_score', avg_7d_score)
            setattr(plan, 'position_count', len(positions_to_close))
            
            logger.debug(f"🎯 7D Balance Plan: Zones {buy_analysis.zone_id}-{sell_analysis.zone_id}, "
                        f"7D Score: {avg_7d_score:.1f}, Expected: ${expected_profit:.2f}")
            
            return plan
            
        except Exception as e:
            logger.error(f"❌ Error creating 7D balance plan: {e}")
            return self._create_empty_balance_plan(buy_analysis.zone_id, sell_analysis.zone_id)
    
    def _create_empty_balance_plan(self, primary_zone: int, partner_zone: int) -> CrossZoneBalancePlan:
        """สร้าง empty balance plan"""
        return CrossZoneBalancePlan(
            primary_zone=primary_zone,
            partner_zone=partner_zone,
            recovery_type='BALANCE_RECOVERY',
            positions_to_close=[],
            expected_profit=0.0,
            health_improvement={},
            execution_priority='LOW',
            confidence_score=0.0
        )
    
    def log_zone_analysis(self, current_price: float, detailed: bool = False):
        """
        แสดงผลการวิเคราะห์ Zones ใน Log
        
        Args:
            current_price: ราคาปัจจุบัน
            detailed: แสดงรายละเอียดหรือไม่
        """
        analyses = self.analyze_all_zones(current_price)
        
        if not analyses:
            logger.info("🔍 No zones to analyze")
            return
            
        if detailed:
            # แสดงรายงานเต็ม
            report = self.generate_zone_report(analyses, current_price)
            for line in report.split('\n'):
                logger.info(line)
        else:
            # แสดงสรุปแค่ Actions ที่สำคัญ
            urgent_actions = [a for a in analyses.values() if a.priority in ['HIGH', 'URGENT']]
            
            if urgent_actions:
                logger.info("🚨 URGENT ZONE ACTIONS:")
                for analysis in urgent_actions:
                    zone = self.zone_manager.zones[analysis.zone_id]
                    logger.info(f"  Zone {analysis.zone_id}: {analysis.action_needed} "
                               f"(P&L: ${analysis.total_pnl:+.2f}, Risk: {analysis.risk_level})")
            else:
                logger.info("✅ All zones stable - no urgent actions needed")


# ==========================================
# 🎯 HELPER FUNCTIONS  
# ==========================================

def create_zone_analyzer(zone_manager: ZoneManager) -> ZoneAnalyzer:
    """
    สร้าง Zone Analyzer instance
    
    Args:
        zone_manager: Zone Manager instance
        
    Returns:
        ZoneAnalyzer: Zone Analyzer instance
    """
    return ZoneAnalyzer(zone_manager)

if __name__ == "__main__":
    # Demo Zone Analysis
    from zone_manager import create_zone_manager, demo_zone_system
    
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    logger.info("🔍 Zone Analyzer Demo")
    
    # สร้าง Zone Manager และ Demo Data
    zm = create_zone_manager()
    demo_zone_system()  # สร้างข้อมูล Demo
    
    # สร้าง Zone Analyzer
    za = create_zone_analyzer(zm)
    
    # วิเคราะห์ Zones
    current_price = 2640.0
    za.log_zone_analysis(current_price, detailed=True)
