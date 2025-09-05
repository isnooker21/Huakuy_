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
