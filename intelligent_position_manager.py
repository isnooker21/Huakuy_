# -*- coding: utf-8 -*-
"""
🧠 Intelligent Position Manager
ระบบปิดตำแหน่งอัจฉริยะที่ครอบคลุมทุกความต้องการ

Features:
- ลดจำนวนไม้อย่างฉลาด
- ฟื้นตัวพอร์ตอัตโนมัติ  
- สมดุล Buy/Sell ดีขึ้น
- ปรับปรุง Margin/Equity/Free Margin
- ไม่ทิ้งไม้แย่ไว้กลางทาง
"""

import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np

logger = logging.getLogger(__name__)

@dataclass
class MarginHealth:
    """สุขภาพ Margin ของพอร์ต"""
    margin_level: float
    free_margin: float
    equity: float
    balance: float
    risk_level: str  # LOW, MEDIUM, HIGH, CRITICAL
    recommendation: str

@dataclass
class PositionScore:
    """คะแนนประเมินตำแหน่ง"""
    position: Any
    profit_score: float      # คะแนนกำไร (-100 to +100)
    balance_score: float     # คะแนนความสมดุล (0 to 100)
    margin_impact: float     # ผลกระทบต่อ margin (0 to 100)
    recovery_potential: float # ศักยภาพฟื้นตัว (0 to 100)
    total_score: float       # คะแนนรวม
    priority: str           # MUST_CLOSE, SHOULD_CLOSE, CAN_HOLD, MUST_HOLD

class IntelligentPositionManager:
    """🧠 ระบบปิดตำแหน่งอัจฉริยะ"""
    
    def __init__(self, mt5_connection, order_manager, symbol: str = "XAUUSD"):
        self.mt5_connection = mt5_connection
        self.order_manager = order_manager
        self.symbol = symbol
        
        # 🎯 เกณฑ์การตัดสินใจแบบ Dynamic
        self.margin_thresholds = {
            'critical': 150,    # Margin Level < 150% = วิกฤต
            'high_risk': 300,   # < 300% = เสี่ยงสูง
            'medium_risk': 500, # < 500% = เสี่ยงปานกลาง
            'safe': 1000        # > 1000% = ปลอดภัย
        }
        
        # 🎯 เป้าหมายการปรับปรุง
        self.improvement_targets = {
            'position_reduction': 0.8,    # ลดไม้ 20%
            'margin_improvement': 1.5,    # เพิ่ม margin level 50%
            'balance_improvement': 0.9,   # ปรับ buy/sell ratio ให้ดีขึ้น 10%
            'equity_protection': 0.95     # ปกป้อง equity อย่างน้อย 95%
        }
        
        logger.info("🧠 Intelligent Position Manager initialized")
    
    def analyze_closing_decision(self, positions: List[Any], account_info: Dict) -> Dict[str, Any]:
        """
        🎯 วิเคราะห์การปิดตำแหน่งแบบอัจฉริยะ
        
        Args:
            positions: รายการตำแหน่งทั้งหมด
            account_info: ข้อมูลบัญชี
            
        Returns:
            Dict: คำแนะนำการปิดตำแหน่ง
        """
        try:
            if not positions:
                return {'should_close': False, 'reason': 'No positions to analyze'}
            
            # 1. 📊 วิเคราะห์สุขภาพ Margin
            margin_health = self._analyze_margin_health(account_info)
            logger.info(f"💊 Margin Health: {margin_health.risk_level} - {margin_health.recommendation}")
            
            # 2. 🎯 ให้คะแนนทุกตำแหน่ง
            position_scores = self._score_all_positions(positions, account_info, margin_health)
            
            # 3. 🧠 วิเคราะห์ Portfolio Balance
            balance_analysis = self._analyze_portfolio_balance(positions, account_info)
            
            # 4. 🎯 ตัดสินใจอัจฉริยะ
            decision = self._make_intelligent_decision(position_scores, margin_health, balance_analysis)
            
            return decision
            
        except Exception as e:
            logger.error(f"❌ Error in intelligent closing analysis: {e}")
            return {'should_close': False, 'reason': f'Analysis error: {e}'}
    
    def _analyze_margin_health(self, account_info: Dict) -> MarginHealth:
        """📊 วิเคราะห์สุขภาพ Margin"""
        try:
            margin_level = account_info.get('margin_level', 0)
            free_margin = account_info.get('margin_free', 0)
            equity = account_info.get('equity', 0)
            balance = account_info.get('balance', 0)
            
            # กำหนดระดับความเสี่ยง
            if margin_level < self.margin_thresholds['critical']:
                risk_level = 'CRITICAL'
                recommendation = 'ปิดไม้ด่วน! Margin Level อันตราย'
            elif margin_level < self.margin_thresholds['high_risk']:
                risk_level = 'HIGH'
                recommendation = 'ควรปิดไม้ลดความเสี่ยง'
            elif margin_level < self.margin_thresholds['medium_risk']:
                risk_level = 'MEDIUM'
                recommendation = 'ปิดไม้บางส่วนเพื่อปรับปรุง'
            elif margin_level < self.margin_thresholds['safe']:
                risk_level = 'LOW'
                recommendation = 'ปิดไม้เพื่อเพิ่มประสิทธิภาพ'
            else:
                risk_level = 'SAFE'
                recommendation = 'ปิดเฉพาะกำไรดี'
            
            return MarginHealth(
                margin_level=margin_level,
                free_margin=free_margin,
                equity=equity,
                balance=balance,
                risk_level=risk_level,
                recommendation=recommendation
            )
            
        except Exception as e:
            logger.error(f"❌ Error analyzing margin health: {e}")
            return MarginHealth(0, 0, 0, 0, 'UNKNOWN', 'Cannot analyze')
    
    def _score_all_positions(self, positions: List[Any], account_info: Dict, 
                           margin_health: MarginHealth) -> List[PositionScore]:
        """🎯 ให้คะแนนทุกตำแหน่ง"""
        try:
            scores = []
            total_volume = sum(getattr(pos, 'volume', 0) for pos in positions)
            buy_count = sum(1 for pos in positions if getattr(pos, 'type', 0) == 0)
            sell_count = len(positions) - buy_count
            
            for pos in positions:
                # 📊 คะแนนกำไร (-100 to +100)
                profit = getattr(pos, 'profit', 0)
                profit_score = min(100, max(-100, profit * 10))  # $1 = 10 points
                
                # ⚖️ คะแนนความสมดุล (0 to 100)
                pos_type = getattr(pos, 'type', 0)
                if pos_type == 0:  # BUY
                    balance_need = sell_count / max(1, buy_count)  # ต้องการ SELL มากไหม
                else:  # SELL
                    balance_need = buy_count / max(1, sell_count)  # ต้องการ BUY มากไหม
                balance_score = min(100, balance_need * 50)
                
                # 💊 ผลกระทบต่อ Margin (0 to 100)
                pos_volume = getattr(pos, 'volume', 0)
                volume_ratio = pos_volume / max(0.01, total_volume)
                margin_impact = volume_ratio * 100
                
                # 🔄 ศักยภาพฟื้นตัว (0 to 100)
                if profit > 0:
                    recovery_potential = 20  # กำไรแล้ว ศักยภาพต่ำ
                elif profit > -5:
                    recovery_potential = 80  # ขาดทุนน้อย ศักยภาพสูง
                elif profit > -20:
                    recovery_potential = 40  # ขาดทุนปานกลาง
                else:
                    recovery_potential = 10  # ขาดทุนหนัก ศักยภาพต่ำ
                
                # 🧮 คะแนนรวม (ถ่วงน้ำหนักตาม margin health)
                if margin_health.risk_level == 'CRITICAL':
                    # วิกฤต: เน้น margin impact และ profit
                    total_score = (profit_score * 0.4) + (margin_impact * 0.4) + (balance_score * 0.1) + (recovery_potential * 0.1)
                elif margin_health.risk_level == 'HIGH':
                    # เสี่ยงสูง: เน้น profit และ balance
                    total_score = (profit_score * 0.4) + (balance_score * 0.3) + (margin_impact * 0.2) + (recovery_potential * 0.1)
                else:
                    # ปกติ: เน้น balance และ recovery
                    total_score = (profit_score * 0.3) + (balance_score * 0.3) + (recovery_potential * 0.3) + (margin_impact * 0.1)
                
                # 🎯 กำหนด Priority
                if total_score > 70:
                    priority = 'MUST_CLOSE'
                elif total_score > 30:
                    priority = 'SHOULD_CLOSE'
                elif total_score > -30:
                    priority = 'CAN_HOLD'
                else:
                    priority = 'MUST_HOLD'
                
                scores.append(PositionScore(
                    position=pos,
                    profit_score=profit_score,
                    balance_score=balance_score,
                    margin_impact=margin_impact,
                    recovery_potential=recovery_potential,
                    total_score=total_score,
                    priority=priority
                ))
            
            # เรียงตามคะแนน (สูงสุดก่อน)
            scores.sort(key=lambda x: x.total_score, reverse=True)
            
            return scores
            
        except Exception as e:
            logger.error(f"❌ Error scoring positions: {e}")
            return []
    
    def _analyze_portfolio_balance(self, positions: List[Any], account_info: Dict) -> Dict[str, Any]:
        """⚖️ วิเคราะห์ความสมดุลของพอร์ต"""
        try:
            if not positions:
                return {'buy_ratio': 0.5, 'sell_ratio': 0.5, 'balance_score': 100, 'needs_rebalance': False}
            
            buy_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 0]
            sell_positions = [pos for pos in positions if getattr(pos, 'type', 0) == 1]
            
            total_count = len(positions)
            buy_ratio = len(buy_positions) / total_count
            sell_ratio = len(sell_positions) / total_count
            
            # คะแนนความสมดุล (100 = สมดุลสมบูรณ์)
            balance_score = 100 - abs(buy_ratio - sell_ratio) * 200
            
            # ต้องการ rebalance ไหม
            needs_rebalance = abs(buy_ratio - sell_ratio) > 0.3  # เกิน 30%
            
            # กำไร/ขาดทุนแยกตามประเภท
            buy_profit = sum(getattr(pos, 'profit', 0) for pos in buy_positions)
            sell_profit = sum(getattr(pos, 'profit', 0) for pos in sell_positions)
            
            return {
                'buy_ratio': buy_ratio,
                'sell_ratio': sell_ratio,
                'buy_count': len(buy_positions),
                'sell_count': len(sell_positions),
                'balance_score': balance_score,
                'needs_rebalance': needs_rebalance,
                'buy_profit': buy_profit,
                'sell_profit': sell_profit,
                'total_profit': buy_profit + sell_profit
            }
            
        except Exception as e:
            logger.error(f"❌ Error analyzing portfolio balance: {e}")
            return {'balance_score': 0, 'needs_rebalance': True}
    
    def _make_intelligent_decision(self, position_scores: List[PositionScore], 
                                 margin_health: MarginHealth, balance_analysis: Dict) -> Dict[str, Any]:
        """🧠 ตัดสินใจอัจฉริยะ"""
        try:
            if not position_scores:
                return {'should_close': False, 'reason': 'No positions to close'}
            
            # 🎯 เลือกตำแหน่งที่จะปิด
            positions_to_close = []
            closing_reasons = []
            
            # 1. 🚨 CRITICAL: ปิดทันทีถ้า margin วิกฤต
            if margin_health.risk_level == 'CRITICAL':
                # ปิดตำแหน่งที่มี margin impact สูงสุด 3 อันดับแรก
                high_impact = [score for score in position_scores if score.margin_impact > 50][:3]
                positions_to_close.extend([score.position for score in high_impact])
                closing_reasons.append(f'CRITICAL margin level: {margin_health.margin_level:.1f}%')
            
            # 2. 🎯 MUST_CLOSE: ปิดตำแหน่งที่ได้คะแนนสูง
            must_close = [score for score in position_scores if score.priority == 'MUST_CLOSE']
            if must_close:
                # ปิดไม่เกิน 5 ตำแหน่ง เพื่อไม่ให้กระทบตลาด
                positions_to_close.extend([score.position for score in must_close[:5]])
                closing_reasons.append(f'{len(must_close)} high-priority positions')
            
            # 3. ⚖️ BALANCE: ปิดเพื่อปรับสมดุล
            if balance_analysis.get('needs_rebalance', False):
                balance_closes = self._select_balance_positions(position_scores, balance_analysis)
                positions_to_close.extend(balance_closes)
                if balance_closes:
                    closing_reasons.append(f'Portfolio rebalancing: {len(balance_closes)} positions')
            
            # 4. 🎯 SMART PAIRING: จับคู่กำไร-ขาดทุน
            if not positions_to_close:  # ถ้ายังไม่มีอะไรให้ปิด
                smart_pairs = self._find_smart_pairs(position_scores)
                if smart_pairs:
                    positions_to_close.extend(smart_pairs)
                    closing_reasons.append(f'Smart profit-loss pairing: {len(smart_pairs)} positions')
            
            # 🚫 ป้องกันไม่ให้ทิ้งไม้แย่ไว้
            if positions_to_close:
                positions_to_close = self._avoid_leaving_bad_positions(positions_to_close, position_scores)
            
            # 📊 สรุปผลการตัดสินใจ
            if positions_to_close:
                expected_pnl = sum(getattr(pos, 'profit', 0) for pos in positions_to_close)
                reduction_percentage = len(positions_to_close) / len(position_scores) * 100
                
                return {
                    'should_close': True,
                    'positions_to_close': positions_to_close,
                    'positions_count': len(positions_to_close),
                    'expected_pnl': expected_pnl,
                    'reduction_percentage': reduction_percentage,
                    'reasons': closing_reasons,
                    'margin_health': margin_health.risk_level,
                    'balance_improvement': balance_analysis.get('balance_score', 0),
                    'method': 'intelligent_decision'
                }
            else:
                return {
                    'should_close': False,
                    'reason': 'No beneficial closing opportunities found',
                    'margin_health': margin_health.risk_level,
                    'balance_score': balance_analysis.get('balance_score', 0)
                }
                
        except Exception as e:
            logger.error(f"❌ Error in intelligent decision making: {e}")
            return {'should_close': False, 'reason': f'Decision error: {e}'}
    
    def _select_balance_positions(self, position_scores: List[PositionScore], 
                                balance_analysis: Dict) -> List[Any]:
        """⚖️ เลือกตำแหน่งสำหรับปรับสมดุล"""
        try:
            positions_to_close = []
            
            # ถ้า BUY มากเกินไป → ปิด BUY ที่แย่ที่สุด
            if balance_analysis['buy_ratio'] > 0.65:
                buy_positions = [score for score in position_scores 
                               if getattr(score.position, 'type', 0) == 0]
                # เรียงจากแย่สุดไปดีสุด และปิดแย่สุด 2 ตำแหน่ง
                buy_positions.sort(key=lambda x: x.total_score)
                positions_to_close.extend([score.position for score in buy_positions[:2]])
            
            # ถ้า SELL มากเกินไป → ปิด SELL ที่แย่ที่สุด  
            elif balance_analysis['sell_ratio'] > 0.65:
                sell_positions = [score for score in position_scores 
                                if getattr(score.position, 'type', 0) == 1]
                sell_positions.sort(key=lambda x: x.total_score)
                positions_to_close.extend([score.position for score in sell_positions[:2]])
            
            return positions_to_close
            
        except Exception as e:
            logger.error(f"❌ Error selecting balance positions: {e}")
            return []
    
    def _find_smart_pairs(self, position_scores: List[PositionScore]) -> List[Any]:
        """🎯 หาคู่ profit-loss ที่ดี"""
        try:
            profitable = [score for score in position_scores if getattr(score.position, 'profit', 0) > 3.0]
            losing = [score for score in position_scores if getattr(score.position, 'profit', 0) < -8.0]
            
            if not profitable or not losing:
                return []
            
            # จับคู่กำไรดีสุดกับขาดทุนแย่สุด
            best_profit = max(profitable, key=lambda x: getattr(x.position, 'profit', 0))
            worst_loss = min(losing, key=lambda x: getattr(x.position, 'profit', 0))
            
            expected_pnl = getattr(best_profit.position, 'profit', 0) + getattr(worst_loss.position, 'profit', 0)
            
            # ปิดถ้าผลรวมไม่ขาดทุนเกิน $2
            if expected_pnl > -2.0:
                return [best_profit.position, worst_loss.position]
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Error finding smart pairs: {e}")
            return []
    
    def _avoid_leaving_bad_positions(self, positions_to_close: List[Any], 
                                   position_scores: List[PositionScore]) -> List[Any]:
        """🚫 ป้องกันไม่ให้ทิ้งไม้แย่ไว้"""
        try:
            # หาตำแหน่งที่แย่ที่สุดที่ยังไม่ได้เลือกปิด
            remaining_scores = [score for score in position_scores 
                              if score.position not in positions_to_close]
            
            if not remaining_scores:
                return positions_to_close
            
            # เรียงจากแย่สุดไปดีสุด
            remaining_scores.sort(key=lambda x: x.total_score)
            worst_remaining = remaining_scores[0]
            
            # ถ้าตำแหน่งที่แย่ที่สุดที่เหลือแย่มาก (< -50 คะแนน)
            if worst_remaining.total_score < -50:
                # หาตำแหน่งที่ดีที่สุดในกลุ่มที่จะปิดมาแลกเปลี่ยน
                closing_scores = [score for score in position_scores 
                                if score.position in positions_to_close]
                if closing_scores:
                    best_closing = max(closing_scores, key=lambda x: x.total_score)
                    
                    # ถ้าตำแหน่งที่จะปิดดีกว่าที่เหลือมาก
                    if best_closing.total_score - worst_remaining.total_score > 30:
                        # แลกเปลี่ยน: เอาไม้แย่ออกแทน
                        positions_to_close.remove(best_closing.position)
                        positions_to_close.append(worst_remaining.position)
                        logger.info(f"🔄 Swapped position to avoid leaving bad position behind")
            
            return positions_to_close
            
        except Exception as e:
            logger.error(f"❌ Error avoiding bad positions: {e}")
            return positions_to_close


def create_intelligent_position_manager(mt5_connection, order_manager, symbol: str = "XAUUSD") -> IntelligentPositionManager:
    """🏭 Factory function สำหรับสร้าง Intelligent Position Manager"""
    return IntelligentPositionManager(mt5_connection, order_manager, symbol)
