"""
🧠 Position Purpose Tracking System
ระบบติดตาม Purpose ของแต่ละ Position อย่างฉลาด

Features:
- 🎯 Multi-Purpose Classification (6 หลักๆ + Sub-types)
- 🌊 Market-Aware Intelligence (ใช้ Market Analysis)
- 🔄 Dynamic Purpose Updates (ปรับตามสถานการณ์)
- ⚖️ Portfolio Context Awareness (พิจารณา Portfolio ทั้งหมด)
- 🚀 Flexible & Adaptive (ยืดหยุ่นทุกสภาพตลาด)
- 🧠 Smart Problem Solving (แก้ไขปัญหาได้เก่ง)

Purpose Types:
- RECOVERY_HELPER: ไม้ที่ช่วยเครีย positions ที่เสีย
- PROBLEM_POSITION: ไม้ที่เสียหนัก รอการช่วยเหลือ
- BALANCE_KEEPER: ไม้ที่ช่วยรักษาสมดุล BUY/SELL
- PROFIT_TAKER: ไม้กำไรดี พร้อมปิด
- TREND_FOLLOWER: ไม้ที่ตาม Trend หลัก
- HEDGE_POSITION: ไม้ป้องกันความเสี่ยง
"""

import logging
import time
import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)

class PurposeType(Enum):
    """🎯 Purpose Types"""
    RECOVERY_HELPER = "RECOVERY_HELPER"      # ช่วยเครีย positions ที่เสีย
    PROBLEM_POSITION = "PROBLEM_POSITION"    # เสียหนัก รอการช่วย
    BALANCE_KEEPER = "BALANCE_KEEPER"        # รักษาสมดุล BUY/SELL
    PROFIT_TAKER = "PROFIT_TAKER"           # กำไรดี พร้อมปิด
    TREND_FOLLOWER = "TREND_FOLLOWER"       # ตาม Trend หลัก
    HEDGE_POSITION = "HEDGE_POSITION"       # ป้องกันความเสี่ยง

class PurposePriority(Enum):
    """📊 Priority Levels"""
    CRITICAL = 100      # ต้องดูแลเร่งด่วน
    HIGH = 80          # สำคัญมาก
    MEDIUM = 60        # ปานกลาง
    LOW = 40           # ไม่เร่งด่วน
    MINIMAL = 20       # น้อยที่สุด

class MarketAlignment(Enum):
    """🌊 Market Alignment Status"""
    STRONG_WITH = "STRONG_WITH"         # ตาม Trend แรง
    WITH = "WITH"                       # ตาม Trend
    NEUTRAL = "NEUTRAL"                 # ไม่ขัดไม่ตาม
    AGAINST = "AGAINST"                 # ขัด Trend
    STRONG_AGAINST = "STRONG_AGAINST"   # ขัด Trend แรง

@dataclass
class PurposeAnalysis:
    """📊 ผลการวิเคราะห์ Purpose"""
    purpose: PurposeType
    sub_purpose: str                    # รายละเอียดเพิ่มเติม
    priority: PurposePriority
    confidence: float                   # ความมั่นใจ 0-100%
    
    # Market Context
    market_alignment: MarketAlignment
    trend_compatibility: float         # เข้ากันกับ Trend 0-100%
    risk_level: float                  # ระดับความเสี่ยง 0-100%
    
    # Purpose Relationships
    helper_for: List[str]              # ช่วยไม้ไหนบ้าง (ticket numbers)
    needs_help_from: List[str]         # ต้องการความช่วยจากไม้ไหน
    balance_partner: Optional[str]     # คู่สมดุล
    
    # Timing & Updates
    assigned_time: datetime
    last_updated: datetime
    update_reason: str
    
    # Smart Metrics
    purpose_score: float               # คะแนน Purpose 0-100
    adaptability: float               # ความยืดหยุ่น 0-100%
    problem_solving_potential: float  # ศักยภาพแก้ปัญหา 0-100%

@dataclass
class MarketContext:
    """🌊 Market Context Information"""
    trend_direction: str               # BULLISH/BEARISH/SIDEWAYS
    trend_strength: float             # 0-100%
    momentum: str                     # STRONG/MODERATE/WEAK
    volatility: float                 # 0-100%
    market_structure: str             # UPTREND/DOWNTREND/RANGING
    
    # Multi-Timeframe
    h4_trend: str
    h1_momentum: str
    m15_signal: str
    
    # Support/Resistance
    near_support: bool
    near_resistance: bool
    support_strength: float
    resistance_strength: float
    
    # Session Info
    market_session: str
    session_characteristics: Dict[str, Any]

@dataclass
class PortfolioContext:
    """⚖️ Portfolio Context"""
    total_positions: int
    buy_count: int
    sell_count: int
    balance_ratio: float              # BUY/SELL ratio
    imbalance_percentage: float
    
    total_pnl: float
    winning_positions: int
    losing_positions: int
    break_even_positions: int
    
    margin_level: float
    free_margin: float
    equity: float
    
    # Zone Information
    active_zones: int
    problematic_zones: List[int]
    profitable_zones: List[int]

class PositionPurposeTracker:
    """🧠 Position Purpose Tracking System"""
    
    def __init__(self, market_analyzer=None, price_action_analyzer=None):
        self.market_analyzer = market_analyzer
        self.price_action_analyzer = price_action_analyzer
        
        # 📊 Purpose Database
        self.position_purposes: Dict[str, PurposeAnalysis] = {}
        self.purpose_history: Dict[str, List[PurposeAnalysis]] = {}
        
        # 🔄 Update Control
        self.last_market_update = 0
        self.market_update_interval = 300  # 5 นาที
        self.purpose_update_cooldown = 180  # 3 นาที
        self.last_purpose_updates: Dict[str, float] = {}
        
        # 🎯 Configuration - ปรับให้เหมาะกับการเทรดจริง
        self.config = {
            'min_confidence_threshold': 70,    # Purpose confidence ขั้นต่ำ
            'market_strength_threshold': 60,   # Market strength ที่มีผล
            'problem_loss_threshold': -5,      # ขาดทุนเท่าไหร่ถือว่า Problem (ลดจาก -20 เป็น -5)
            'profit_take_threshold': 5,        # กำไรเท่าไหร่ถือว่า Ready to close (ลดจาก 15 เป็น 5)
            'helper_distance_max': 100,        # Helper ห่างจาก Problem ได้สูงสุดกี่ pips (ปรับสำหรับทองคำ)
            'balance_tolerance': 0.3,          # ความไม่สมดุลที่ยอมรับได้
            'trend_follow_min_strength': 65,   # Trend strength ขั้นต่ำสำหรับ TREND_FOLLOWER
            'heavy_loss_threshold': -50,       # ขาดทุนหนักมาก (เพิ่มใหม่)
            'distance_weight_factor': 0.1,     # น้ำหนักระยะห่าง (เพิ่มใหม่)
        }
        
        logger.info("🧠 Position Purpose Tracker initialized")
        logger.info(f"   📊 Market Update Interval: {self.market_update_interval}s")
        logger.info(f"   🔄 Purpose Update Cooldown: {self.purpose_update_cooldown}s")
        logger.info(f"   🎯 Min Confidence: {self.config['min_confidence_threshold']}%")
    
    def analyze_position_purpose(self, position: Any, all_positions: List[Any], 
                               account_info: Dict, current_price: float) -> PurposeAnalysis:
        """
        🎯 วิเคราะห์ Purpose ของ Position
        """
        try:
            position_ticket = str(getattr(position, 'ticket', id(position)))
            
            # 1. 🌊 Get Market Context
            market_context = self._get_market_context()
            
            # 2. ⚖️ Get Portfolio Context
            portfolio_context = self._analyze_portfolio_context(all_positions, account_info)
            
            # 3. 📊 Analyze Base Purpose
            base_purpose = self._analyze_base_purpose(position, all_positions, current_price, portfolio_context)
            
            # 4. 🌊 Apply Market Intelligence
            market_enhanced_purpose = self._apply_market_intelligence(base_purpose, position, market_context)
            
            # 5. 🔄 Apply Dynamic Adjustments
            final_purpose = self._apply_dynamic_adjustments(
                market_enhanced_purpose, position, all_positions, portfolio_context, market_context
            )
            
            # 6. 💾 Store & Track
            self._store_purpose_analysis(position_ticket, final_purpose)
            
            logger.debug(f"🎯 Purpose Analysis: {position_ticket} → {final_purpose.purpose.value} "
                        f"(Priority: {final_purpose.priority.value}, Confidence: {final_purpose.confidence:.1f}%)")
            
            return final_purpose
            
        except Exception as e:
            logger.error(f"❌ Error analyzing position purpose: {e}")
            return self._default_purpose_analysis(position)
    
    def _get_market_context(self) -> MarketContext:
        """🌊 ดึงข้อมูล Market Context"""
        try:
            current_time = time.time()
            
            # เช็ค Cache
            if (current_time - self.last_market_update) < self.market_update_interval:
                return getattr(self, '_cached_market_context', self._default_market_context())
            
            market_context = MarketContext(
                trend_direction="SIDEWAYS",
                trend_strength=50.0,
                momentum="MODERATE",
                volatility=50.0,
                market_structure="RANGING",
                h4_trend="SIDEWAYS",
                h1_momentum="MODERATE", 
                m15_signal="NEUTRAL",
                near_support=False,
                near_resistance=False,
                support_strength=50.0,
                resistance_strength=50.0,
                market_session="LONDON",
                session_characteristics={}
            )
            
            # 🌊 Use Market Analyzer if available
            if self.market_analyzer:
                try:
                    # Multi-Timeframe Analysis
                    if hasattr(self.market_analyzer, 'analyze_timeframe'):
                        h4_analysis = self.market_analyzer.analyze_timeframe('H4')
                        h1_analysis = self.market_analyzer.analyze_timeframe('H1')
                        m15_analysis = self.market_analyzer.analyze_timeframe('M15')
                        
                        market_context.h4_trend = h4_analysis.trend_direction.value
                        market_context.h1_momentum = h1_analysis.momentum.value
                        market_context.trend_strength = h4_analysis.strength
                        
                        # Determine overall trend
                        if h4_analysis.trend_direction.value == "UP":
                            market_context.trend_direction = "BULLISH"
                        elif h4_analysis.trend_direction.value == "DOWN":
                            market_context.trend_direction = "BEARISH"
                        else:
                            market_context.trend_direction = "SIDEWAYS"
                        
                        market_context.volatility = min(100, h1_analysis.strength * 1.2)
                        
                except Exception as e:
                    logger.warning(f"⚠️ Market Analyzer error: {e}")
            
            # 🎯 Use Price Action Analyzer if available
            if self.price_action_analyzer:
                try:
                    if hasattr(self.price_action_analyzer, 'analyze_market_structure'):
                        trend_analysis = self.price_action_analyzer.analyze_market_structure()
                        
                        market_context.trend_direction = trend_analysis.direction
                        market_context.trend_strength = trend_analysis.strength
                        market_context.momentum = trend_analysis.momentum
                        market_context.market_structure = trend_analysis.swing_structure
                        
                except Exception as e:
                    logger.warning(f"⚠️ Price Action Analyzer error: {e}")
            
            # 💾 Cache result
            self._cached_market_context = market_context
            self.last_market_update = current_time
            
            return market_context
            
        except Exception as e:
            logger.error(f"❌ Error getting market context: {e}")
            return self._default_market_context()
    
    def _analyze_portfolio_context(self, positions: List[Any], account_info: Dict) -> PortfolioContext:
        """⚖️ วิเคราะห์ Portfolio Context"""
        try:
            total_positions = len(positions)
            buy_count = len([p for p in positions if getattr(p, 'type', 0) == 0])
            sell_count = len([p for p in positions if getattr(p, 'type', 0) == 1])
            
            balance_ratio = buy_count / max(1, sell_count)
            imbalance_percentage = abs(buy_count - sell_count) / max(1, total_positions) * 100
            
            total_pnl = sum(getattr(p, 'profit', 0) for p in positions)
            winning_positions = len([p for p in positions if getattr(p, 'profit', 0) > 0])
            losing_positions = len([p for p in positions if getattr(p, 'profit', 0) < 0])
            break_even_positions = total_positions - winning_positions - losing_positions
            
            margin_level = account_info.get('margin_level', 1000)
            free_margin = account_info.get('free_margin', 10000)
            equity = account_info.get('equity', 10000)
            
            return PortfolioContext(
                total_positions=total_positions,
                buy_count=buy_count,
                sell_count=sell_count,
                balance_ratio=balance_ratio,
                imbalance_percentage=imbalance_percentage,
                total_pnl=total_pnl,
                winning_positions=winning_positions,
                losing_positions=losing_positions,
                break_even_positions=break_even_positions,
                margin_level=margin_level,
                free_margin=free_margin,
                equity=equity,
                active_zones=0,  # จะต้องเชื่อมกับ Zone Manager ภายหลัง
                problematic_zones=[],
                profitable_zones=[]
            )
            
        except Exception as e:
            logger.error(f"❌ Error analyzing portfolio context: {e}")
            return PortfolioContext(0, 0, 0, 1.0, 0, 0, 0, 0, 0, 1000, 10000, 10000, 0, [], [])
    
    def _analyze_base_purpose(self, position: Any, all_positions: List[Any], 
                            current_price: float, portfolio_context: PortfolioContext) -> PurposeAnalysis:
        """📊 วิเคราะห์ Base Purpose"""
        try:
            position_ticket = str(getattr(position, 'ticket', id(position)))
            position_type = getattr(position, 'type', 0)  # 0=BUY, 1=SELL
            open_price = getattr(position, 'open_price', current_price)
            profit = getattr(position, 'profit', 0)
            volume = getattr(position, 'volume', 0.01)
            
            # 📊 Calculate metrics
            distance_pips = abs(current_price - open_price) * 10000  # สำหรับ XAUUSD
            profit_percentage = (profit / max(volume * 1000, 100)) * 100  # ประมาณการ
            
            # 🎯 Base Purpose Logic
            purpose = PurposeType.BALANCE_KEEPER  # Default
            sub_purpose = "Standard Position"
            priority = PurposePriority.MEDIUM
            confidence = 70.0
            
            # 💔 PROBLEM_POSITION Detection (Enhanced with Distance Factor)
            is_problem = False
            
            # เงื่อนไขที่ 1: ขาดทุน
            if profit < self.config['problem_loss_threshold']:
                is_problem = True
            
            # เงื่อนไขที่ 2: ระยะห่างไกลมาก + ขาดทุน (ปรับสำหรับทองคำ)
            elif distance_pips > 200 and profit < 0:  # ห่าง > 200 pips + ขาดทุน
                is_problem = True
            
            # เงื่อนไขที่ 3: ระยะห่างไกลมหาศาล (ปรับสำหรับทองคำ)
            elif distance_pips > 400:  # ห่าง > 400 pips
                is_problem = True
            
            if is_problem:
                purpose = PurposeType.PROBLEM_POSITION
                
                # จัดระดับตามความรุนแรง (ปรับสำหรับทองคำ)
                if profit < self.config['heavy_loss_threshold'] or distance_pips > 500:
                    sub_purpose = f"Critical Problem (${profit:.1f}, {distance_pips:.0f} pips)"
                    priority = PurposePriority.CRITICAL
                    confidence = 95.0
                elif profit < -20 or distance_pips > 300:
                    sub_purpose = f"Heavy Problem (${profit:.1f}, {distance_pips:.0f} pips)"
                    priority = PurposePriority.HIGH
                    confidence = 90.0
                elif profit < -10 or distance_pips > 150:
                    sub_purpose = f"Moderate Problem (${profit:.1f}, {distance_pips:.0f} pips)"
                    priority = PurposePriority.HIGH
                    confidence = 85.0
                else:
                    sub_purpose = f"Light Problem (${profit:.1f}, {distance_pips:.0f} pips)"
                    priority = PurposePriority.MEDIUM
                    confidence = 75.0
            
            # 💰 PROFIT_TAKER Detection
            elif profit > self.config['profit_take_threshold']:
                purpose = PurposeType.PROFIT_TAKER
                if profit > 50:
                    sub_purpose = "High Profit Ready"
                    priority = PurposePriority.HIGH
                    confidence = 90.0
                elif profit > 25:
                    sub_purpose = "Good Profit Ready"
                    priority = PurposePriority.MEDIUM
                    confidence = 80.0
                else:
                    sub_purpose = "Small Profit Ready"
                    priority = PurposePriority.LOW
                    confidence = 70.0
            
            # 🔍 RECOVERY_HELPER Detection
            else:
                # หา positions ที่เสียหนักในทิศทางตรงข้าม
                opposite_type = 1 - position_type
                problem_positions = [
                    p for p in all_positions 
                    if (getattr(p, 'type', 0) == opposite_type and 
                        getattr(p, 'profit', 0) < self.config['problem_loss_threshold'])
                ]
                
                if problem_positions and profit >= 0:
                    # เช็คระยะห่างจาก Problem positions
                    for prob_pos in problem_positions:
                        prob_price = getattr(prob_pos, 'open_price', current_price)
                        distance = abs(open_price - prob_price) * 10000
                        
                        if distance <= self.config['helper_distance_max']:
                            purpose = PurposeType.RECOVERY_HELPER
                            sub_purpose = f"Helper for {getattr(prob_pos, 'ticket', 'Unknown')}"
                            priority = PurposePriority.HIGH
                            confidence = 85.0
                            break
            
            # ⚖️ BALANCE_KEEPER Detection
            if purpose == PurposeType.BALANCE_KEEPER:
                if portfolio_context.imbalance_percentage > 50:
                    # เช็คว่า position นี้ช่วยสมดุลหรือไม่
                    minority_side = 0 if portfolio_context.buy_count < portfolio_context.sell_count else 1
                    if position_type == minority_side:
                        sub_purpose = "Balance Maintainer"
                        priority = PurposePriority.HIGH
                        confidence = 80.0
                    else:
                        sub_purpose = "Imbalance Contributor"
                        priority = PurposePriority.LOW
                        confidence = 60.0
            
            return PurposeAnalysis(
                purpose=purpose,
                sub_purpose=sub_purpose,
                priority=priority,
                confidence=confidence,
                market_alignment=MarketAlignment.NEUTRAL,  # จะถูกปรับใน market intelligence
                trend_compatibility=50.0,
                risk_level=50.0,
                helper_for=[],
                needs_help_from=[],
                balance_partner=None,
                assigned_time=datetime.now(),
                last_updated=datetime.now(),
                update_reason="Base Analysis",
                purpose_score=confidence,
                adaptability=70.0,
                problem_solving_potential=60.0
            )
            
        except Exception as e:
            logger.error(f"❌ Error in base purpose analysis: {e}")
            return self._default_purpose_analysis(position)
    
    def _apply_market_intelligence(self, base_purpose: PurposeAnalysis, position: Any, 
                                 market_context: MarketContext) -> PurposeAnalysis:
        """🌊 Apply Market Intelligence"""
        try:
            position_type = getattr(position, 'type', 0)  # 0=BUY, 1=SELL
            profit = getattr(position, 'profit', 0)
            
            # 🌊 Calculate Market Alignment
            market_alignment = self._calculate_market_alignment(position_type, market_context)
            trend_compatibility = self._calculate_trend_compatibility(position_type, market_context)
            
            # 📊 Adjust Purpose based on Market
            enhanced_purpose = base_purpose
            enhanced_purpose.market_alignment = market_alignment
            enhanced_purpose.trend_compatibility = trend_compatibility
            
            # 🎯 TREND_FOLLOWER Enhancement
            if (market_context.trend_strength > self.config['trend_follow_min_strength'] and
                market_alignment in [MarketAlignment.STRONG_WITH, MarketAlignment.WITH] and
                profit >= 0):
                
                if base_purpose.purpose == PurposeType.BALANCE_KEEPER:
                    enhanced_purpose.purpose = PurposeType.TREND_FOLLOWER
                    enhanced_purpose.sub_purpose = f"Following {market_context.trend_direction} Trend"
                    enhanced_purpose.priority = PurposePriority.HIGH
                    enhanced_purpose.confidence = min(95.0, base_purpose.confidence + 15)
                    enhanced_purpose.update_reason = "Market Trend Alignment"
                
                elif base_purpose.purpose == PurposeType.RECOVERY_HELPER:
                    enhanced_purpose.sub_purpose += f" + Trend Follower"
                    enhanced_purpose.confidence = min(95.0, base_purpose.confidence + 10)
            
            # 🚨 Risk Adjustment for Counter-Trend
            elif market_alignment == MarketAlignment.STRONG_AGAINST:
                enhanced_purpose.risk_level = min(100.0, base_purpose.risk_level + 30)
                
                if base_purpose.purpose == PurposeType.RECOVERY_HELPER:
                    enhanced_purpose.priority = PurposePriority.MEDIUM  # ลดความสำคัญ
                    enhanced_purpose.confidence = max(50.0, base_purpose.confidence - 15)
                    enhanced_purpose.sub_purpose += " (Against Trend)"
                
                elif base_purpose.purpose == PurposeType.PROFIT_TAKER and profit > 0:
                    enhanced_purpose.priority = PurposePriority.HIGH  # เร่งปิด
                    enhanced_purpose.sub_purpose += " (Exit Before Reversal)"
            
            # 🛡️ HEDGE_POSITION Detection
            if (market_context.volatility > 80 and 
                portfolio_context.total_positions > 20 and
                market_alignment == MarketAlignment.AGAINST):
                
                if profit >= -10:  # ไม่เสียมาก
                    enhanced_purpose.purpose = PurposeType.HEDGE_POSITION
                    enhanced_purpose.sub_purpose = "Portfolio Hedge"
                    enhanced_purpose.priority = PurposePriority.MEDIUM
                    enhanced_purpose.confidence = 75.0
            
            # 📊 Update Scores
            enhanced_purpose.purpose_score = self._calculate_purpose_score(enhanced_purpose, market_context)
            enhanced_purpose.adaptability = self._calculate_adaptability(enhanced_purpose, market_context)
            enhanced_purpose.problem_solving_potential = self._calculate_problem_solving_potential(
                enhanced_purpose, position, market_context
            )
            
            enhanced_purpose.last_updated = datetime.now()
            
            return enhanced_purpose
            
        except Exception as e:
            logger.error(f"❌ Error applying market intelligence: {e}")
            return base_purpose
    
    def _apply_dynamic_adjustments(self, purpose: PurposeAnalysis, position: Any, 
                                 all_positions: List[Any], portfolio_context: PortfolioContext,
                                 market_context: MarketContext) -> PurposeAnalysis:
        """🔄 Apply Dynamic Adjustments"""
        try:
            enhanced_purpose = purpose
            
            # 🚨 Emergency Adjustments
            if portfolio_context.margin_level < 150:
                if purpose.purpose == PurposeType.RECOVERY_HELPER:
                    enhanced_purpose.priority = PurposePriority.CRITICAL
                    enhanced_purpose.sub_purpose += " (Margin Emergency)"
                elif purpose.purpose == PurposeType.PROFIT_TAKER:
                    enhanced_purpose.priority = PurposePriority.CRITICAL
                    enhanced_purpose.sub_purpose += " (Emergency Exit)"
            
            # ⚖️ Balance Emergency
            if portfolio_context.imbalance_percentage > 80:
                position_type = getattr(position, 'type', 0)
                minority_side = 0 if portfolio_context.buy_count < portfolio_context.sell_count else 1
                
                if position_type == minority_side and purpose.purpose != PurposeType.PROBLEM_POSITION:
                    enhanced_purpose.priority = PurposePriority.HIGH
                    enhanced_purpose.sub_purpose += " (Balance Critical)"
            
            # 🔗 Smart Relationship Building
            enhanced_purpose = self._build_position_relationships(
                enhanced_purpose, position, all_positions, portfolio_context
            )
            
            # 📊 Final Score Calculation
            enhanced_purpose.purpose_score = self._calculate_final_purpose_score(
                enhanced_purpose, portfolio_context, market_context
            )
            
            enhanced_purpose.last_updated = datetime.now()
            enhanced_purpose.update_reason += " + Dynamic Adjustments"
            
            return enhanced_purpose
            
        except Exception as e:
            logger.error(f"❌ Error in dynamic adjustments: {e}")
            return purpose
    
    def _calculate_market_alignment(self, position_type: int, market_context: MarketContext) -> MarketAlignment:
        """🌊 คำนวณ Market Alignment"""
        try:
            is_buy = position_type == 0
            trend_direction = market_context.trend_direction
            trend_strength = market_context.trend_strength
            
            if trend_direction == "BULLISH":
                if is_buy:
                    return MarketAlignment.STRONG_WITH if trend_strength > 75 else MarketAlignment.WITH
                else:
                    return MarketAlignment.STRONG_AGAINST if trend_strength > 75 else MarketAlignment.AGAINST
                    
            elif trend_direction == "BEARISH":
                if is_buy:
                    return MarketAlignment.STRONG_AGAINST if trend_strength > 75 else MarketAlignment.AGAINST
                else:
                    return MarketAlignment.STRONG_WITH if trend_strength > 75 else MarketAlignment.WITH
            
            else:  # SIDEWAYS
                return MarketAlignment.NEUTRAL
                
        except Exception as e:
            logger.error(f"❌ Error calculating market alignment: {e}")
            return MarketAlignment.NEUTRAL
    
    def _calculate_trend_compatibility(self, position_type: int, market_context: MarketContext) -> float:
        """📊 คำนวณ Trend Compatibility Score"""
        try:
            alignment = self._calculate_market_alignment(position_type, market_context)
            trend_strength = market_context.trend_strength
            
            if alignment == MarketAlignment.STRONG_WITH:
                return min(100.0, 80 + trend_strength * 0.2)
            elif alignment == MarketAlignment.WITH:
                return min(90.0, 60 + trend_strength * 0.3)
            elif alignment == MarketAlignment.NEUTRAL:
                return 50.0
            elif alignment == MarketAlignment.AGAINST:
                return max(10.0, 40 - trend_strength * 0.3)
            else:  # STRONG_AGAINST
                return max(5.0, 20 - trend_strength * 0.2)
                
        except Exception as e:
            logger.error(f"❌ Error calculating trend compatibility: {e}")
            return 50.0
    
    def _build_position_relationships(self, purpose: PurposeAnalysis, position: Any,
                                    all_positions: List[Any], portfolio_context: PortfolioContext) -> PurposeAnalysis:
        """🔗 สร้าง Position Relationships"""
        try:
            position_ticket = str(getattr(position, 'ticket', id(position)))
            position_type = getattr(position, 'type', 0)
            open_price = getattr(position, 'open_price', 0)
            profit = getattr(position, 'profit', 0)
            
            enhanced_purpose = purpose
            
            # 🔍 Find Helper Relationships
            if purpose.purpose == PurposeType.RECOVERY_HELPER:
                opposite_type = 1 - position_type
                problem_positions = [
                    p for p in all_positions 
                    if (getattr(p, 'type', 0) == opposite_type and 
                        getattr(p, 'profit', 0) < self.config['problem_loss_threshold'])
                ]
                
                helper_for = []
                for prob_pos in problem_positions:
                    prob_ticket = str(getattr(prob_pos, 'ticket', id(prob_pos)))
                    prob_price = getattr(prob_pos, 'open_price', 0)
                    distance = abs(open_price - prob_price) * 10000
                    
                    if distance <= self.config['helper_distance_max']:
                        helper_for.append(prob_ticket)
                
                enhanced_purpose.helper_for = helper_for
            
            # 🆘 Find Help Needs
            elif purpose.purpose == PurposeType.PROBLEM_POSITION:
                opposite_type = 1 - position_type
                helper_positions = [
                    p for p in all_positions 
                    if (getattr(p, 'type', 0) == opposite_type and 
                        getattr(p, 'profit', 0) >= 0)
                ]
                
                needs_help_from = []
                for helper_pos in helper_positions:
                    helper_ticket = str(getattr(helper_pos, 'ticket', id(helper_pos)))
                    helper_price = getattr(helper_pos, 'open_price', 0)
                    distance = abs(open_price - helper_price) * 10000
                    
                    if distance <= self.config['helper_distance_max']:
                        needs_help_from.append(helper_ticket)
                
                enhanced_purpose.needs_help_from = needs_help_from
            
            # ⚖️ Find Balance Partners
            if purpose.purpose == PurposeType.BALANCE_KEEPER:
                opposite_type = 1 - position_type
                balance_candidates = [
                    p for p in all_positions 
                    if (getattr(p, 'type', 0) == opposite_type and 
                        abs(getattr(p, 'profit', 0) - profit) < 10)  # คล้ายกัน
                ]
                
                if balance_candidates:
                    # เลือกตัวที่ใกล้ที่สุด
                    closest_partner = min(
                        balance_candidates,
                        key=lambda p: abs(getattr(p, 'open_price', 0) - open_price)
                    )
                    enhanced_purpose.balance_partner = str(getattr(closest_partner, 'ticket', id(closest_partner)))
            
            return enhanced_purpose
            
        except Exception as e:
            logger.error(f"❌ Error building position relationships: {e}")
            return purpose
    
    def _calculate_purpose_score(self, purpose: PurposeAnalysis, market_context: MarketContext) -> float:
        """📊 คำนวณ Purpose Score"""
        try:
            base_score = purpose.confidence
            
            # Market Alignment Bonus/Penalty
            if purpose.market_alignment == MarketAlignment.STRONG_WITH:
                base_score += 15
            elif purpose.market_alignment == MarketAlignment.WITH:
                base_score += 10
            elif purpose.market_alignment == MarketAlignment.AGAINST:
                base_score -= 10
            elif purpose.market_alignment == MarketAlignment.STRONG_AGAINST:
                base_score -= 15
            
            # Purpose-specific adjustments
            if purpose.purpose == PurposeType.TREND_FOLLOWER:
                base_score += market_context.trend_strength * 0.3
            elif purpose.purpose == PurposeType.RECOVERY_HELPER:
                base_score += len(purpose.helper_for) * 5
            elif purpose.purpose == PurposeType.PROBLEM_POSITION:
                base_score += len(purpose.needs_help_from) * 3
            
            return max(0, min(100, base_score))
            
        except Exception as e:
            logger.error(f"❌ Error calculating purpose score: {e}")
            return 50.0
    
    def _calculate_adaptability(self, purpose: PurposeAnalysis, market_context: MarketContext) -> float:
        """🔄 คำนวณ Adaptability Score"""
        try:
            base_adaptability = 70.0
            
            # Purpose-based adaptability
            if purpose.purpose == PurposeType.BALANCE_KEEPER:
                base_adaptability = 90.0  # สามารถปรับได้ดี
            elif purpose.purpose == PurposeType.TREND_FOLLOWER:
                base_adaptability = 60.0  # ติด Trend
            elif purpose.purpose == PurposeType.RECOVERY_HELPER:
                base_adaptability = 80.0  # ปรับตาม Problem ได้
            elif purpose.purpose == PurposeType.PROBLEM_POSITION:
                base_adaptability = 40.0  # จำกัด
            elif purpose.purpose == PurposeType.PROFIT_TAKER:
                base_adaptability = 85.0  # ปิดได้เสมอ
            elif purpose.purpose == PurposeType.HEDGE_POSITION:
                base_adaptability = 75.0  # ปรับได้ปานกลาง
            
            # Market volatility adjustment
            volatility_factor = market_context.volatility / 100
            base_adaptability += volatility_factor * 10  # ตลาดผันผวน = ปรับได้มากขึ้น
            
            return max(0, min(100, base_adaptability))
            
        except Exception as e:
            logger.error(f"❌ Error calculating adaptability: {e}")
            return 70.0
    
    def _calculate_problem_solving_potential(self, purpose: PurposeAnalysis, position: Any, 
                                           market_context: MarketContext) -> float:
        """🧠 คำนวณ Problem Solving Potential"""
        try:
            profit = getattr(position, 'profit', 0)
            base_potential = 50.0
            
            # Purpose-based potential
            if purpose.purpose == PurposeType.RECOVERY_HELPER:
                base_potential = 85.0 + len(purpose.helper_for) * 5
            elif purpose.purpose == PurposeType.PROFIT_TAKER:
                base_potential = 80.0 + min(20, profit * 0.5)
            elif purpose.purpose == PurposeType.BALANCE_KEEPER:
                base_potential = 70.0
            elif purpose.purpose == PurposeType.TREND_FOLLOWER:
                base_potential = 75.0 + purpose.trend_compatibility * 0.2
            elif purpose.purpose == PurposeType.HEDGE_POSITION:
                base_potential = 65.0
            elif purpose.purpose == PurposeType.PROBLEM_POSITION:
                base_potential = 20.0 + len(purpose.needs_help_from) * 10
            
            # Market alignment bonus
            if purpose.market_alignment in [MarketAlignment.STRONG_WITH, MarketAlignment.WITH]:
                base_potential += 10
            
            return max(0, min(100, base_potential))
            
        except Exception as e:
            logger.error(f"❌ Error calculating problem solving potential: {e}")
            return 50.0
    
    def _calculate_final_purpose_score(self, purpose: PurposeAnalysis, 
                                     portfolio_context: PortfolioContext,
                                     market_context: MarketContext) -> float:
        """🏆 คำนวณ Final Purpose Score"""
        try:
            # เอาคะแนนต่างๆ มารวม
            purpose_score = purpose.purpose_score * 0.4
            adaptability_score = purpose.adaptability * 0.3
            problem_solving_score = purpose.problem_solving_potential * 0.3
            
            final_score = purpose_score + adaptability_score + problem_solving_score
            
            # Portfolio context adjustments
            if portfolio_context.margin_level < 150:
                if purpose.purpose in [PurposeType.PROFIT_TAKER, PurposeType.RECOVERY_HELPER]:
                    final_score += 15  # เร่งด่วน
            
            if portfolio_context.imbalance_percentage > 70:
                if purpose.purpose == PurposeType.BALANCE_KEEPER:
                    final_score += 10  # สำคัญขึ้น
            
            return max(0, min(100, final_score))
            
        except Exception as e:
            logger.error(f"❌ Error calculating final purpose score: {e}")
            return 50.0
    
    def _store_purpose_analysis(self, position_ticket: str, purpose: PurposeAnalysis):
        """💾 เก็บผล Purpose Analysis"""
        try:
            # เก็บ Current Purpose
            self.position_purposes[position_ticket] = purpose
            
            # เก็บ History
            if position_ticket not in self.purpose_history:
                self.purpose_history[position_ticket] = []
            
            self.purpose_history[position_ticket].append(purpose)
            
            # จำกัด History ไม่เกิน 10 records
            if len(self.purpose_history[position_ticket]) > 10:
                self.purpose_history[position_ticket] = self.purpose_history[position_ticket][-10:]
            
            # Update timestamp
            self.last_purpose_updates[position_ticket] = time.time()
            
        except Exception as e:
            logger.error(f"❌ Error storing purpose analysis: {e}")
    
    def get_position_purpose(self, position_ticket: str) -> Optional[PurposeAnalysis]:
        """🔍 ดึง Purpose ของ Position"""
        return self.position_purposes.get(str(position_ticket))
    
    def get_positions_by_purpose(self, purpose_type: PurposeType) -> List[str]:
        """🎯 ดึง Positions ตาม Purpose Type"""
        return [
            ticket for ticket, purpose in self.position_purposes.items()
            if purpose.purpose == purpose_type
        ]
    
    def get_purpose_summary(self) -> Dict[str, int]:
        """📊 สรุป Purpose ทั้งหมด"""
        summary = {}
        for purpose in PurposeType:
            summary[purpose.value] = len(self.get_positions_by_purpose(purpose))
        return summary
    
    def should_update_purpose(self, position_ticket: str) -> bool:
        """🔄 ตรวจสอบว่าควร Update Purpose หรือไม่"""
        last_update = self.last_purpose_updates.get(str(position_ticket), 0)
        return (time.time() - last_update) >= self.purpose_update_cooldown
    
    def _default_market_context(self) -> MarketContext:
        """🌊 Default Market Context"""
        return MarketContext(
            trend_direction="SIDEWAYS",
            trend_strength=50.0,
            momentum="MODERATE",
            volatility=50.0,
            market_structure="RANGING",
            h4_trend="SIDEWAYS",
            h1_momentum="MODERATE",
            m15_signal="NEUTRAL",
            near_support=False,
            near_resistance=False,
            support_strength=50.0,
            resistance_strength=50.0,
            market_session="LONDON",
            session_characteristics={}
        )
    
    def _default_purpose_analysis(self, position: Any) -> PurposeAnalysis:
        """📊 Default Purpose Analysis"""
        return PurposeAnalysis(
            purpose=PurposeType.BALANCE_KEEPER,
            sub_purpose="Default Analysis",
            priority=PurposePriority.MEDIUM,
            confidence=50.0,
            market_alignment=MarketAlignment.NEUTRAL,
            trend_compatibility=50.0,
            risk_level=50.0,
            helper_for=[],
            needs_help_from=[],
            balance_partner=None,
            assigned_time=datetime.now(),
            last_updated=datetime.now(),
            update_reason="Default Fallback",
            purpose_score=50.0,
            adaptability=70.0,
            problem_solving_potential=50.0
        )


def create_position_purpose_tracker(market_analyzer=None, price_action_analyzer=None):
    """🏭 Factory function สำหรับสร้าง Position Purpose Tracker"""
    return PositionPurposeTracker(market_analyzer, price_action_analyzer)


if __name__ == "__main__":
    # Demo Position Purpose Tracker
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    logger.info("🧠 Position Purpose Tracker Demo")
    logger.info("This system provides intelligent position purpose classification")
    logger.info("Features: Market-Aware, Dynamic Updates, Smart Relationships, Problem Solving")
    logger.info("Position Purpose Tracker ready for integration!")
