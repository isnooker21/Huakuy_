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
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import numpy as np
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

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
    """คะแนนประเมินตำแหน่ง - 7 มิติ"""
    position: Any
    profit_score: float      # คะแนนกำไร (-100 to +100)
    balance_score: float     # คะแนนความสมดุล (0 to 100)
    margin_impact: float     # ผลกระทบต่อ margin (0 to 100)
    recovery_potential: float # ศักยภาพฟื้นตัว (0 to 100)
    time_score: float        # คะแนนเวลาถือ (0 to 100)
    correlation_score: float # คะแนนความสัมพันธ์ (0 to 100)
    volatility_score: float  # คะแนนความผันผวน (0 to 100)
    total_score: float       # คะแนนรวม 7 มิติ
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
            
            # 2. 🎯 ให้คะแนนทุกตำแหน่ง (7 มิติ)
            position_scores = self._score_all_positions(positions, account_info, margin_health)
            
            # 📊 แสดงการวิเคราะห์ 7 มิติ (ทุก 10 รอบ)
            if len(positions) > 0 and (len(positions) % 10 == 0):
                self._log_7d_analysis(position_scores, top_n=3)
            
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
        """🚀 ให้คะแนนทุกตำแหน่ง (7 มิติ) - Parallel Processing สำหรับ Performance"""
        try:
            if not positions:
                return []
            
            # 🚀 เลือกใช้ Parallel หรือ Sequential ตามจำนวน positions
            # เน้น Sequential เพื่อความเร็วและความเสถียร (Parallel ใช้เมื่อจำเป็นจริงๆ)
            if len(positions) > 100:  # เพิ่มจาก 50 เป็น 100
                return self._score_positions_parallel(positions, account_info, margin_health)
            else:
                return self._score_positions_sequential(positions, account_info, margin_health)
                
        except Exception as e:
            logger.error(f"❌ Error scoring positions: {e}")
            return []
    
    def _score_positions_sequential(self, positions: List[Any], account_info: Dict, 
                                  margin_health: MarginHealth) -> List[PositionScore]:
        """📊 Sequential 7D Scoring (สำหรับ positions น้อย)"""
        try:
            scores = []
            total_volume = sum(getattr(pos, 'volume', 0) for pos in positions)
            buy_count = sum(1 for pos in positions if getattr(pos, 'type', 0) == 0)
            sell_count = len(positions) - buy_count
            
            for pos in positions:
                # 📊 คะแนนกำไร (-100 to +100) - ENHANCED FOR PROFIT
                profit = getattr(pos, 'profit', 0)
                if profit > 5:
                    profit_score = min(100, 50 + (profit * 5))  # กำไร >$5 ได้คะแนนสูงมาก
                elif profit > 0:
                    profit_score = profit * 20  # กำไรเล็กๆ ได้คะแนนดี $1 = 20 points
                elif profit > -10:
                    profit_score = profit * 8   # ขาดทุนน้อย ลดคะแนนปานกลาง
                else:
                    profit_score = max(-100, -80 + (profit + 10) * 2)  # ขาดทุนมาก ลดคะแนนหนัก
                
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
                
                # ⏰ คะแนนเวลาถือ (0 to 100)
                pos_time = getattr(pos, 'time', 0)
                current_time = int(time.time())
                hold_hours = (current_time - pos_time) / 3600 if pos_time > 0 else 0
                
                if hold_hours < 1:
                    time_score = 90  # ใหม่มาก คะแนนสูง
                elif hold_hours < 6:
                    time_score = 80  # ใหม่ คะแนนดี
                elif hold_hours < 24:
                    time_score = 60  # วันเดียว คะแนนปานกลาง
                elif hold_hours < 72:
                    time_score = 40  # 3 วัน คะแนนต่ำ
                else:
                    time_score = 20  # เก่ามาก คะแนนต่ำมาก
                
                # 🔗 คะแนนความสัมพันธ์ (0 to 100) - ตำแหน่งที่ช่วยกันได้
                correlation_score = 50  # ค่าเริ่มต้น
                if pos_type == 0:  # BUY
                    if sell_count > buy_count:
                        correlation_score = 80  # BUY ช่วย balance ได้
                    elif sell_count == 0:
                        correlation_score = 30  # BUY เดี่ยวๆ
                else:  # SELL
                    if buy_count > sell_count:
                        correlation_score = 80  # SELL ช่วย balance ได้
                    elif buy_count == 0:
                        correlation_score = 30  # SELL เดี่ยวๆ
                
                # 📊 คะแนนความผันผวน (0 to 100) - ตำแหน่งที่มีความเสี่ยงต่ำ
                volatility_score = 70  # ค่าเริ่มต้น
                if abs(profit) < 2:
                    volatility_score = 90  # ความผันผวนต่ำ
                elif abs(profit) < 10:
                    volatility_score = 70  # ความผันผวนปานกลาง
                elif abs(profit) < 30:
                    volatility_score = 50  # ความผันผวนสูง
                else:
                    volatility_score = 30  # ความผันผวนสูงมาก
                
                # 🧮 คะแนนรวม 7 มิติ (ถ่วงน้ำหนักตาม margin health)
                if margin_health.risk_level == 'CRITICAL':
                    # วิกฤต: เน้น margin impact, profit, time
                    total_score = (
                        (profit_score * 0.30) + (margin_impact * 0.25) + (time_score * 0.20) +
                        (volatility_score * 0.10) + (balance_score * 0.08) + 
                        (recovery_potential * 0.05) + (correlation_score * 0.02)
                    )
                elif margin_health.risk_level == 'HIGH':
                    # เสี่ยงสูง: เน้น profit, balance, volatility
                    total_score = (
                        (profit_score * 0.25) + (balance_score * 0.20) + (volatility_score * 0.18) +
                        (margin_impact * 0.15) + (time_score * 0.12) + 
                        (recovery_potential * 0.07) + (correlation_score * 0.03)
                    )
                else:
                    # ปกติ: เน้น balance, recovery, correlation
                    total_score = (
                        (balance_score * 0.22) + (recovery_potential * 0.20) + (correlation_score * 0.18) +
                        (profit_score * 0.15) + (volatility_score * 0.12) + 
                        (time_score * 0.08) + (margin_impact * 0.05)
                    )
                
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
                    time_score=time_score,
                    correlation_score=correlation_score,
                    volatility_score=volatility_score,
                    total_score=total_score,
                    priority=priority
                ))
            
            # เรียงตามคะแนน (สูงสุดก่อน)
            scores.sort(key=lambda x: x.total_score, reverse=True)
            
            return scores
            
        except Exception as e:
            logger.error(f"❌ Error scoring positions: {e}")
            return []
    
    def _score_positions_parallel(self, positions: List[Any], account_info: Dict, 
                                margin_health: MarginHealth) -> List[PositionScore]:
        """⚡ Parallel 7D Scoring (สำหรับ positions เยอะ) - เร็วขึ้น 5-10x"""
        try:
            scores = []
            total_volume = sum(getattr(pos, 'volume', 0) for pos in positions)
            buy_count = sum(1 for pos in positions if getattr(pos, 'type', 0) == 0)
            sell_count = len(positions) - buy_count
            
            # 🚀 แบ่ง positions เป็น chunks สำหรับ parallel processing
            chunk_size = max(10, len(positions) // 4)  # แบ่งเป็น 4 chunks
            position_chunks = [positions[i:i + chunk_size] for i in range(0, len(positions), chunk_size)]
            
            logger.info(f"⚡ Parallel Scoring: {len(positions)} positions → {len(position_chunks)} chunks")
            
            # 🧵 Thread-safe scoring
            scores_lock = threading.Lock()
            
            def score_chunk(chunk):
                """Score positions ใน chunk เดียว"""
                chunk_scores = []
                
                for pos in chunk:
                    try:
                        # 📊 คะแนนกำไร (-100 to +100) - ENHANCED FOR PROFIT
                        profit = getattr(pos, 'profit', 0)
                        if profit > 5:
                            profit_score = min(100, 50 + (profit * 5))  # กำไร >$5 ได้คะแนนสูงมาก
                        elif profit > 0:
                            profit_score = profit * 20  # กำไรเล็กๆ ได้คะแนนดี $1 = 20 points
                        elif profit > -10:
                            profit_score = profit * 8   # ขาดทุนน้อย ลดคะแนนปานกลาง
                        else:
                            profit_score = max(-100, -80 + (profit + 10) * 2)  # ขาดทุนมาก ลดคะแนนหนัก
                        
                        # ⚖️ คะแนนความสมดุล (0 to 100)
                        pos_type = getattr(pos, 'type', 0)
                        if pos_type == 0:  # BUY
                            balance_need = sell_count / max(1, buy_count)
                        else:  # SELL
                            balance_need = buy_count / max(1, sell_count)
                        balance_score = min(100, balance_need * 50)
                        
                        # 💊 ผลกระทบต่อ Margin (0 to 100)
                        pos_volume = getattr(pos, 'volume', 0)
                        volume_ratio = pos_volume / max(0.01, total_volume)
                        margin_impact = volume_ratio * 100
                        
                        # 🔄 ศักยภาพฟื้นตัว (0 to 100)
                        if profit > 0:
                            recovery_potential = 20
                        elif profit > -5:
                            recovery_potential = 80
                        elif profit > -20:
                            recovery_potential = 40
                        else:
                            recovery_potential = 10
                        
                        # ⏰ คะแนนเวลาถือ (0 to 100)
                        pos_time = getattr(pos, 'time', 0)
                        current_time = int(time.time())
                        hold_hours = (current_time - pos_time) / 3600 if pos_time > 0 else 0
                        
                        if hold_hours < 1:
                            time_score = 90
                        elif hold_hours < 6:
                            time_score = 80
                        elif hold_hours < 24:
                            time_score = 60
                        elif hold_hours < 72:
                            time_score = 40
                        else:
                            time_score = 20
                        
                        # 🔗 คะแนนความสัมพันธ์ (0 to 100)
                        correlation_score = 50
                        if pos_type == 0:  # BUY
                            if sell_count > buy_count:
                                correlation_score = 80
                            elif sell_count == 0:
                                correlation_score = 30
                        else:  # SELL
                            if buy_count > sell_count:
                                correlation_score = 80
                            elif buy_count == 0:
                                correlation_score = 30
                        
                        # 📊 คะแนนความผันผวน (0 to 100)
                        volatility_score = 70
                        if abs(profit) < 2:
                            volatility_score = 90
                        elif abs(profit) < 10:
                            volatility_score = 70
                        elif abs(profit) < 30:
                            volatility_score = 50
                        else:
                            volatility_score = 30
                        
                        # 🧮 คะแนนรวม 7 มิติ - PROFIT-FOCUSED
                        if margin_health.risk_level == 'CRITICAL':
                            total_score = (
                                (profit_score * 0.40) + (balance_score * 0.20) + (recovery_potential * 0.15) +
                                (margin_impact * 0.10) + (correlation_score * 0.08) + 
                                (time_score * 0.05) + (volatility_score * 0.02)
                            )
                        elif margin_health.risk_level == 'HIGH':
                            total_score = (
                                (profit_score * 0.35) + (balance_score * 0.25) + (recovery_potential * 0.15) +
                                (correlation_score * 0.10) + (margin_impact * 0.08) + 
                                (time_score * 0.05) + (volatility_score * 0.02)
                            )
                        else:  # NORMAL/LOW risk
                            total_score = (
                                (profit_score * 0.30) + (balance_score * 0.25) + (recovery_potential * 0.20) +
                                (correlation_score * 0.12) + (margin_impact * 0.08) + 
                                (time_score * 0.03) + (volatility_score * 0.02)
                            )
                        
                        # 🎯 กำหนด Priority
                        if total_score > 70:
                            priority = 'MUST_CLOSE'
                        elif total_score > 30:
                            priority = 'SHOULD_CLOSE'
                        elif total_score > -30:
                            priority = 'CAN_HOLD'
                        else:
                            priority = 'MUST_HOLD'
                        
                        chunk_scores.append(PositionScore(
                            position=pos,
                            profit_score=profit_score,
                            balance_score=balance_score,
                            margin_impact=margin_impact,
                            recovery_potential=recovery_potential,
                            time_score=time_score,
                            correlation_score=correlation_score,
                            volatility_score=volatility_score,
                            total_score=total_score,
                            priority=priority
                        ))
                        
                    except Exception as e:
                        logger.error(f"❌ Error scoring position in chunk: {e}")
                        continue
                
                return chunk_scores
            
            # 🚀 Execute parallel processing
            with ThreadPoolExecutor(max_workers=min(4, len(position_chunks))) as executor:
                future_to_chunk = {executor.submit(score_chunk, chunk): chunk for chunk in position_chunks}
                
                for future in as_completed(future_to_chunk):
                    try:
                        chunk_scores = future.result()
                        with scores_lock:
                            scores.extend(chunk_scores)
                    except Exception as e:
                        logger.error(f"❌ Parallel scoring error: {e}")
            
            # เรียงตามคะแนน (สูงสุดก่อน)
            scores.sort(key=lambda x: x.total_score, reverse=True)
            
            logger.info(f"⚡ Parallel Scoring Complete: {len(scores)} positions scored")
            return scores
            
        except Exception as e:
            logger.error(f"❌ Error in parallel scoring: {e}")
            # Fallback to sequential
            return self._score_positions_sequential(positions, account_info, margin_health)
    
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
            
            # ต้องการ rebalance ไหม - เข้มงวดขึ้น
            needs_rebalance = abs(buy_ratio - sell_ratio) > 0.2  # เกิน 20% (ลดจาก 30%)
            
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
            
            # 🚫 ลบ CRITICAL margin closing - อาจปิดติดลบได้
            
            # 🚫 ลบระบบเดิมออกทั้งหมด - ใช้เฉพาะ Intelligent Mass Closing
            
            # 💰 INTELLIGENT POSITIVE SUM CLOSING: ใช้ 4-dimensional scoring หาชุดที่ผลรวมบวกเสมอ
            intelligent_combination = self._find_intelligent_positive_combination(position_scores, margin_health)
            if intelligent_combination:
                positions_to_close.extend(intelligent_combination['positions'])
                profit_count = intelligent_combination.get('profit_count', 0)
                loss_count = intelligent_combination.get('loss_count', 0) 
                net_pnl = intelligent_combination.get('net_pnl', 0)
                closing_reasons.append(f'Intelligent positive combination: {profit_count}P+{loss_count}L = +${net_pnl:.2f}')
            
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
    
    # 🚫 ลบ _select_balance_positions - ไม่ใช้แล้ว
    
    # 🚫 ลบ _find_smart_pairs และ _find_multiple_smart_pairs - ไม่ใช้แล้ว
    
    # 🚫 ลบ _find_mass_profit_opportunities - ไม่ใช้แล้ว
    def _old_find_mass_profit_opportunities(self, position_scores: List[PositionScore], 
                                       margin_health: MarginHealth) -> List[Any]:
        """💰 หาโอกาสปิดกำไรแบบกลุ่ม - เพิ่ม Zone Balance Protection"""
        try:
            # คำนวณเงื่อนไขตาม lot size และ margin health
            total_volume = sum(getattr(pos, 'volume', 0.01) for pos in 
                             [score.position for score in position_scores])
            avg_volume_per_position = total_volume / len(position_scores) if position_scores else 0.01
            
            # คำนวณ cost base ตาม volume
            volume_cost_factor = avg_volume_per_position * 100  # 100$ per 0.01 lot base cost
            
            if margin_health.risk_level in ['CRITICAL', 'HIGH']:
                min_profit_per_lot = 120.0  # $120 per 0.01 lot
                min_total_profit_factor = 3.0  # 3x cost factor
                reason = "High margin risk - only excellent profits"
            elif margin_health.risk_level == 'MEDIUM':
                min_profit_per_lot = 100.0  # $100 per 0.01 lot
                min_total_profit_factor = 2.5  # 2.5x cost factor
                reason = "Medium margin risk - good profits"
            else:
                min_profit_per_lot = 80.0   # $80 per 0.01 lot
                min_total_profit_factor = 2.0  # 2x cost factor
                reason = "Safe margin - moderate profits"
            
            # หาตำแหน่งกำไรที่เข้าเกณฑ์ (คำนวณตาม lot size)
            profitable_positions = []
            for score in position_scores:
                pos = score.position
                profit = getattr(pos, 'profit', 0)
                volume = getattr(pos, 'volume', 0.01)
                profit_per_lot = profit / volume if volume > 0 else 0
                
                if profit_per_lot > min_profit_per_lot:
                    profitable_positions.append(pos)
            
            if not profitable_positions:
                logger.info(f"⚠️ No positions meet profit per lot criteria (${min_profit_per_lot:.0f}/0.01lot)")
                return []
            
            # 🎯 Zone Balance Protection: ตรวจสอบผลกระทบต่อ Zone
            safe_positions = self._filter_zone_safe_positions(profitable_positions)
            
            if safe_positions:
                total_profit = sum(getattr(pos, 'profit', 0) for pos in safe_positions)
                total_volume_safe = sum(getattr(pos, 'volume', 0.01) for pos in safe_positions)
                total_closing_cost = self._calculate_closing_cost(total_volume_safe, safe_positions)
                min_total_profit = total_closing_cost * min_total_profit_factor
                net_profit_after_cost = total_profit - total_closing_cost
                
                # เงื่อนไขเข้มงวด: ต้องกำไรสุทธิอย่างน้อย $10 และเกิน min_total_profit
                if net_profit_after_cost >= 10.0 and total_profit >= min_total_profit:
                    logger.info(f"💰 Zone-Safe Mass Profit: {len(safe_positions)} positions, ${total_profit:.2f} total")
                    logger.info(f"   📊 Volume: {total_volume_safe:.2f} lots, Cost: ${total_closing_cost:.2f}, Net: +${net_profit_after_cost:.2f}")
                    logger.info(f"   Reason: {reason} + Zone Balance Protected")
                    return safe_positions
                else:
                    logger.info(f"⚠️ Mass Profit blocked: Net ${net_profit_after_cost:.2f} or Total ${total_profit:.2f} < Required ${min_total_profit:.2f}")
            else:
                logger.info(f"🚫 Mass Profit blocked: Would damage Zone Balance")
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Error finding mass profit opportunities: {e}")
            return []
    
    def _filter_zone_safe_positions(self, positions: List[Any]) -> List[Any]:
        """🎯 กรองตำแหน่งที่ปิดได้โดยไม่ทำลาย Zone Balance"""
        try:
            # จัดกลุ่มตำแหน่งตาม Zone (ประมาณจากราคา)
            zone_groups = {}
            
            for pos in positions:
                price_open = getattr(pos, 'price_open', 0)
                # คำนวณ Zone โดยประมาณ (30 pips = 3.0 points)
                zone_id = int(price_open // 3.0)
                
                if zone_id not in zone_groups:
                    zone_groups[zone_id] = {'BUY': [], 'SELL': []}
                
                pos_type = getattr(pos, 'type', 0)
                if pos_type == 0:  # BUY
                    zone_groups[zone_id]['BUY'].append(pos)
                else:  # SELL
                    zone_groups[zone_id]['SELL'].append(pos)
            
            safe_positions = []
            
            # ตรวจสอบแต่ละ Zone
            for zone_id, zone_positions in zone_groups.items():
                buy_count = len(zone_positions['BUY'])
                sell_count = len(zone_positions['SELL'])
                total_in_zone = buy_count + sell_count
                
                logger.info(f"🔍 Zone {zone_id}: {buy_count} BUY, {sell_count} SELL")
                
                # 🚫 ไม่ปิดตำแหน่งเดี่ยว - ต้องมีการจับคู่เสมอ
                if total_in_zone == 1:
                    logger.info(f"🚫 Zone {zone_id}: Single position - BLOCKED (no pairing available)")
                    continue  # ข้ามไป ไม่ปิด
                
                # ถ้า Zone สมดุลดี (ต่างกันไม่เกิน 1 ตัว) → ปิดได้ทั้งหมด
                elif abs(buy_count - sell_count) <= 1:
                    safe_positions.extend(zone_positions['BUY'] + zone_positions['SELL'])
                    logger.info(f"✅ Zone {zone_id}: Balanced - safe to close all")
                
                # ถ้า Zone ไม่สมดุล → ปิดแค่ส่วนเกิน
                else:
                    if buy_count > sell_count:
                        # BUY เกิน → ปิด BUY ส่วนเกิน + SELL ทั้งหมด
                        excess_buys = buy_count - sell_count - 1  # เหลือ BUY เกิน SELL แค่ 1 ตัว
                        safe_positions.extend(zone_positions['BUY'][:excess_buys])
                        safe_positions.extend(zone_positions['SELL'])
                        logger.info(f"⚖️ Zone {zone_id}: BUY-heavy - closing {excess_buys} excess BUYs + all SELLs")
                    else:
                        # SELL เกิน → ปิด SELL ส่วนเกิน + BUY ทั้งหมด
                        excess_sells = sell_count - buy_count - 1
                        safe_positions.extend(zone_positions['SELL'][:excess_sells])
                        safe_positions.extend(zone_positions['BUY'])
                        logger.info(f"⚖️ Zone {zone_id}: SELL-heavy - closing {excess_sells} excess SELLs + all BUYs")
            
            # 🎯 Cross-Zone Pairing: หาคู่จาก Zone อื่นสำหรับตำแหน่งเดี่ยว
            cross_zone_pairs = self._find_cross_zone_pairs(zone_groups)
            if cross_zone_pairs:
                safe_positions.extend(cross_zone_pairs)
                logger.info(f"🔄 Cross-Zone Pairing: Added {len(cross_zone_pairs)} positions")
            
            return safe_positions
            
        except Exception as e:
            logger.error(f"❌ Error filtering zone-safe positions: {e}")
            return positions  # Fallback: คืนค่าเดิม
    
    def _calculate_closing_cost(self, total_volume: float, positions: List[Any] = None) -> float:
        """💰 คำนวณ cost การปิดตำแหน่ง (spread + slippage + commission + buffer)"""
        try:
            # คำนวณ spread จริงจาก MT5 (ถ้ามี positions)
            current_spread_cost = 0.0
            if positions and self.mt5_connection:
                try:
                    # ดึง spread ปัจจุบัน
                    tick_info = self.mt5_connection.get_current_tick(self.symbol)
                    if tick_info:
                        current_spread = tick_info.get('spread', 0.0)  # spread in points
                        # แปลง spread เป็น USD สำหรับ XAUUSD
                        spread_usd_per_lot = current_spread * 0.01  # 1 point = $0.01 for 0.01 lot XAUUSD
                        current_spread_cost = spread_usd_per_lot * (total_volume / 0.01)
                        logger.debug(f"📊 Current spread: {current_spread} points = ${current_spread_cost:.2f} for {total_volume:.2f} lots")
                except Exception as e:
                    logger.warning(f"⚠️ Cannot get current spread: {e}")
            
            # Base costs สำหรับ XAUUSD - ลดลงเพื่อให้ปิดกำไรง่ายขึ้น
            commission_per_lot = 0.30  # $0.30 per 0.01 lot (ลดจาก $0.50)
            slippage_cost_per_lot = 1.50  # $1.50 per 0.01 lot (ลดจาก $3.00)
            buffer_per_lot = 1.00  # $1.00 per 0.01 lot (ลดจาก $2.00)
            
            # ใช้ spread จริงหรือ estimate
            if current_spread_cost > 0:
                spread_cost = current_spread_cost
            else:
                spread_cost = 1.50 * (total_volume / 0.01)  # Fallback: $1.50 per 0.01 lot
            
            # คำนวณตาม volume
            volume_in_standard_lots = total_volume / 0.01
            
            total_commission = commission_per_lot * volume_in_standard_lots
            total_slippage = slippage_cost_per_lot * volume_in_standard_lots  
            total_buffer = buffer_per_lot * volume_in_standard_lots
            
            total_cost = spread_cost + total_commission + total_slippage + total_buffer
            
            # ลบ log ที่เยอะเกินไป - เหลือแค่ total cost
            logger.debug(f"💰 Closing Cost: ${total_cost:.2f} for {total_volume:.2f} lots")
            
            return total_cost
            
        except Exception as e:
            logger.error(f"❌ Error calculating closing cost: {e}")
            # Realistic fallback: $3 per 0.01 lot (ลดจาก $7)
            fallback_cost = (total_volume / 0.01) * 3.0
            logger.warning(f"⚠️ Using fallback cost: ${fallback_cost:.2f}")
            return fallback_cost
    
    def _find_cross_zone_pairs(self, zone_groups: Dict) -> List[Any]:
        """🔄 หาคู่ตำแหน่งจาก Zone อื่นๆ เพื่อไม่ให้ปิดเดี่ยว"""
        try:
            cross_zone_pairs = []
            
            # หา Zone ที่มีตำแหน่งเดี่ยว
            single_zones = []
            losing_zones = []  # Zone ที่มีตำแหน่งขาดทุน
            
            for zone_id, zone_positions in zone_groups.items():
                buy_count = len(zone_positions['BUY'])
                sell_count = len(zone_positions['SELL'])
                total_in_zone = buy_count + sell_count
                
                if total_in_zone == 1:
                    # Zone เดี่ยว - ต้องหาคู่
                    single_pos = (zone_positions['BUY'] + zone_positions['SELL'])[0]
                    profit = getattr(single_pos, 'profit', 0)
                    pos_type = getattr(single_pos, 'type', 0)
                    
                    single_zones.append({
                        'zone_id': zone_id,
                        'position': single_pos,
                        'profit': profit,
                        'type': 'BUY' if pos_type == 0 else 'SELL'
                    })
                
                # หา Zone ที่มีตำแหน่งขาดทุนหนัก
                for pos in zone_positions['BUY'] + zone_positions['SELL']:
                    profit = getattr(pos, 'profit', 0)
                    pos_type = getattr(pos, 'type', 0)
                    if profit < -15.0:  # ขาดทุนหนัก
                        losing_zones.append({
                            'zone_id': zone_id,
                            'position': pos,
                            'profit': profit,
                            'type': 'BUY' if pos_type == 0 else 'SELL'
                        })
            
            # จับคู่ตำแหน่งเดี่ยวกับตำแหน่งขาดทุนจาก Zone อื่น
            for single in single_zones:
                best_pair = None
                best_net_profit = -999999
                
                for losing in losing_zones:
                    if losing['zone_id'] == single['zone_id']:
                        continue  # ไม่จับคู่ Zone เดียวกัน
                    
                    expected_pnl = single['profit'] + losing['profit']
                    
                    # คำนวณ cost การปิด
                    single_volume = getattr(single['position'], 'volume', 0.01)
                    losing_volume = getattr(losing['position'], 'volume', 0.01)
                    total_volume = single_volume + losing_volume
                    closing_cost = self._calculate_closing_cost(total_volume, [single['position'], losing['position']])
                    net_profit = expected_pnl - closing_cost
                    
                    # เลือกเฉพาะคู่ที่กำไรสุทธิ (ไม่ยอมรับขาดทุน)
                    if net_profit > best_net_profit and net_profit >= 2.0:  # ต้องกำไรสุทธิอย่างน้อย $2
                        best_net_profit = net_profit
                        best_pair = losing
                
                # เพิ่มเฉพาะคู่ที่กำไรสุทธิ
                if best_pair and best_net_profit >= 2.0:
                    cross_zone_pairs.extend([single['position'], best_pair['position']])
                    logger.info(f"🔄 Cross-Zone Pair: Zone {single['zone_id']} {single['type']} ${single['profit']:.2f} + Zone {best_pair['zone_id']} {best_pair['type']} ${best_pair['profit']:.2f}")
                    logger.info(f"   💰 Net Profit: ${best_net_profit:.2f}")
                    
                    # ลบ losing position ที่ใช้แล้วออกจาก list
                    losing_zones.remove(best_pair)
                else:
                    logger.info(f"🚫 No suitable pair for Zone {single['zone_id']} {single['type']} ${single['profit']:.2f}")
            
            return cross_zone_pairs
            
        except Exception as e:
            logger.error(f"❌ Error finding cross-zone pairs: {e}")
            return []
    
    def _find_intelligent_mass_closing(self, position_scores: List[PositionScore], 
                                     margin_health: MarginHealth) -> List[Any]:
        """🧠 ระบบปิดแบบกลุ่มฉลาด - ไม่ขาดทุนเลย, ไม่จำกัดจำนวน"""
        try:
            # แยกตำแหน่งตามประเภท
            profitable_positions = []
            losing_positions = []
            
            for score in position_scores:
                pos = score.position
                profit = getattr(pos, 'profit', 0)
                
                if profit > 1.0:  # กำไร
                    profitable_positions.append({
                        'position': pos,
                        'profit': profit,
                        'volume': getattr(pos, 'volume', 0.01),
                        'score': score.total_score
                    })
                elif profit < -5.0:  # ขาดทุน
                    losing_positions.append({
                        'position': pos,
                        'profit': profit,
                        'volume': getattr(pos, 'volume', 0.01),
                        'score': score.total_score
                    })
            
            if not profitable_positions:
                logger.info("🚫 No profitable positions for intelligent mass closing")
                return []
            
            # เรียงลำดับ
            profitable_positions.sort(key=lambda x: x['profit'], reverse=True)  # กำไรมากสุดก่อน
            losing_positions.sort(key=lambda x: x['profit'])  # ขาดทุนมากสุดก่อน
            
            # 🧠 หาชุดการปิดที่ดีที่สุด
            best_combination = self._find_best_closing_combination(profitable_positions, losing_positions, margin_health)
            
            if best_combination:
                positions_to_close = [item['position'] for item in best_combination['positions']]
                logger.info(f"🧠 Intelligent Mass Closing: {len(positions_to_close)} positions")
                logger.info(f"   💰 Total Profit: ${best_combination['total_profit']:.2f}")
                logger.info(f"   💸 Total Cost: ${best_combination['total_cost']:.2f}")
                logger.info(f"   ✅ Net Profit: +${best_combination['net_profit']:.2f}")
                return positions_to_close
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Error in intelligent mass closing: {e}")
            return []
    
    def _find_best_closing_combination(self, profitable_positions: List[Dict], 
                                     losing_positions: List[Dict], margin_health: MarginHealth) -> Optional[Dict]:
        """🎯 หาชุดการปิดที่ดีที่สุด - กำไรสุทธิสูงสุด"""
        try:
            best_combination = None
            best_net_profit = 0
            
            # เริ่มจากการปิดกำไรทั้งหมด
            all_profitable = profitable_positions.copy()
            
            # 🚫 ปิดเฉพาะกำไรเท่านั้น - ไม่รวมขาดทุนเลย
            combination = all_profitable
            
            if not combination:
                logger.info("🚫 No profitable positions to close")
                return None
            
            # คำนวณผลลัพธ์
            total_profit = sum(item['profit'] for item in combination)
            total_volume = sum(item['volume'] for item in combination)
            positions_list = [item['position'] for item in combination]
            total_cost = self._calculate_closing_cost(total_volume, positions_list)
            net_profit = total_profit - total_cost
            
            # ต้องกำไรสุทธิอย่างน้อย $10
            if net_profit >= 10.0:
                best_combination = {
                    'positions': combination,
                    'total_profit': total_profit,
                    'total_cost': total_cost,
                    'net_profit': net_profit,
                    'count': len(combination)
                }
                logger.info(f"💰 All profits closing: {len(combination)} positions, Net: +${net_profit:.2f}")
                return best_combination
            
            # ถ้าปิดทั้งหมดไม่คุ้ม ลองปิดเฉพาะกำไรดีมาก (>$15)
            excellent_profits = [pos for pos in profitable_positions if pos['profit'] > 15.0]
            if excellent_profits:
                total_profit = sum(item['profit'] for item in excellent_profits)
                total_volume = sum(item['volume'] for item in excellent_profits)
                positions_list = [item['position'] for item in excellent_profits]
                total_cost = self._calculate_closing_cost(total_volume, positions_list)
                net_profit = total_profit - total_cost
                
                # เกณฑ์สูงสำหรับกำไรดีมาก
                if net_profit >= 8.0:  # ลดจาก $10 เป็น $8 สำหรับกำไรดีมาก
                    best_combination = {
                        'positions': excellent_profits,
                        'total_profit': total_profit,
                        'total_cost': total_cost,
                        'net_profit': net_profit,
                        'count': len(excellent_profits)
                    }
                    logger.info(f"💎 Excellent profits only: {len(excellent_profits)} positions, Net: +${net_profit:.2f}")
                    return best_combination
            
            # ไม่มีชุดไหนที่คุ้มค่า
            logger.info(f"🚫 No profitable combinations found. All profits net: ${net_profit:.2f} < $10.00")
            if excellent_profits:
                excellent_net = sum(item['profit'] for item in excellent_profits) - self._calculate_closing_cost(
                    sum(item['volume'] for item in excellent_profits), 
                    [item['position'] for item in excellent_profits]
                )
                logger.info(f"   Excellent profits net: ${excellent_net:.2f} < $8.00")
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Error finding best closing combination: {e}")
            return None
    
    def _find_intelligent_positive_combination(self, position_scores: List[PositionScore], 
                                             margin_health: MarginHealth) -> Optional[Dict]:
        """🧠 หาชุดการปิดที่ดีที่สุดโดยใช้ 4-dimensional scoring และผลรวมบวกเสมอ"""
        try:
            # แยกตำแหน่งตามกำไร/ขาดทุน พร้อม 4D scores
            profitable_positions = []
            losing_positions = []
            
            for score in position_scores:
                pos = score.position
                profit = getattr(pos, 'profit', 0)
                
                position_data = {
                    'position': pos,
                    'profit': profit,
                    'volume': getattr(pos, 'volume', 0.01),
                    'profit_score': score.profit_score,
                    'balance_score': score.balance_score,
                    'margin_impact': score.margin_impact,
                    'recovery_potential': score.recovery_potential,
                    'time_score': score.time_score,
                    'correlation_score': score.correlation_score,
                    'volatility_score': score.volatility_score,
                    'total_score': score.total_score,
                    'priority': score.priority
                }
                
                if profit > 1.0:  # กำไร
                    profitable_positions.append(position_data)
                elif profit < -5.0:  # ขาดทุน
                    losing_positions.append(position_data)
            
            if not profitable_positions:
                logger.info("🚫 No profitable positions for intelligent combination")
                return None
            
            # เรียงตาม 4D total_score
            profitable_positions.sort(key=lambda x: x['total_score'], reverse=True)
            losing_positions.sort(key=lambda x: x['total_score'], reverse=True)  # ขาดทุนที่มีโอกาสฟื้นตัวสูงสุดก่อน
            
            best_combination = None
            best_net_profit = 0
            
            # 🎯 เพิ่มการตรวจสอบ Balance ก่อนเลือกตำแหน่ง
            all_positions = [score.position for score in position_scores]
            balance_analysis = self._analyze_portfolio_balance(all_positions, {})
            
            # ลองหาชุดการปิดที่ดีที่สุด (ยืดหยุ่นได้ 2-30 ไม้)
            max_positions = min(30, len(profitable_positions) + len(losing_positions))
            
            for total_count in range(2, max_positions + 1):
                for profit_count in range(1, min(total_count, len(profitable_positions) + 1)):
                    loss_count = total_count - profit_count
                    
                    if loss_count > len(losing_positions):
                        continue
                    
                    # เลือกตำแหน่งตาม 4D score พร้อม Balance Check
                    selected_profits = profitable_positions[:profit_count]
                    selected_losses = losing_positions[:loss_count]
                    
                    # 🎯 BALANCE ENFORCEMENT: ตรวจสอบการปิดแบบ Balance
                    all_selected_positions = [pos['position'] for pos in selected_profits + selected_losses]
                    closing_balance = self._check_closing_balance(all_selected_positions, balance_analysis)
                    
                    # ปฏิเสธการปิดที่ทำให้ไม่ Balance มากขึ้น
                    if not closing_balance['will_improve_balance']:
                        continue
                    
                    # คำนวณผลรวม
                    total_profit = sum(pos['profit'] for pos in selected_profits)
                    total_loss = sum(pos['profit'] for pos in selected_losses)  # profit เป็นลบอยู่แล้ว
                    gross_pnl = total_profit + total_loss
                    
                    # คำนวณ cost การปิด
                    all_positions_data = selected_profits + selected_losses
                    all_positions = [pos['position'] for pos in all_positions_data]
                    total_volume = sum(pos['volume'] for pos in all_positions_data)
                    closing_cost = self._calculate_closing_cost(total_volume, all_positions)
                    
                    net_pnl = gross_pnl - closing_cost
                    
                    # คำนวณคะแนนรวม 4D
                    total_4d_score = sum(pos['total_score'] for pos in all_positions_data)
                    avg_4d_score = total_4d_score / len(all_positions_data)
                    
                    # เลือกเฉพาะชุดที่ให้ผลรวมบวก และมีคะแนน 4D ดี
                    score_threshold = 60 if margin_health.risk_level == 'CRITICAL' else 70  # ลดเกณฑ์เมื่อ margin วิกฤต
                    
                    if net_pnl > 0 and avg_4d_score >= score_threshold and net_pnl > best_net_profit:
                        best_net_profit = net_pnl
                        best_combination = {
                            'positions': all_positions,
                            'net_pnl': net_pnl,
                            'gross_pnl': gross_pnl,
                            'closing_cost': closing_cost,
                            'profit_count': profit_count,
                            'loss_count': loss_count,
                            'avg_4d_score': avg_4d_score,
                            'total_4d_score': total_4d_score
                        }
                        
                        logger.info(f"🧠 Better 7D combination: {profit_count}P+{loss_count}L, 7D:{avg_4d_score:.1f}, Net:+${net_pnl:.2f}")
                        logger.info(f"⚖️ Balance: {closing_balance['reason']}")
            
            return best_combination
            
        except Exception as e:
            logger.error(f"❌ Error finding intelligent positive combination: {e}")
            return None
    
    def _check_closing_balance(self, positions_to_close: List[Any], current_balance: Dict) -> Dict[str, Any]:
        """⚖️ ตรวจสอบว่าการปิดตำแหน่งจะทำให้ Balance ดีขึ้นไหม"""
        try:
            if not positions_to_close:
                return {'will_improve_balance': False, 'reason': 'No positions to close'}
            
            # นับ BUY/SELL ที่จะปิด
            buy_close_count = sum(1 for pos in positions_to_close if getattr(pos, 'type', 0) == 0)
            sell_close_count = sum(1 for pos in positions_to_close if getattr(pos, 'type', 0) == 1)
            
            if buy_close_count == 0 and sell_close_count == 0:
                return {'will_improve_balance': False, 'reason': 'No valid positions to close'}
            
            # คำนวณ Balance หลังปิด
            remaining_buy = current_balance.get('buy_count', 0) - buy_close_count
            remaining_sell = current_balance.get('sell_count', 0) - sell_close_count
            total_remaining = remaining_buy + remaining_sell
            
            if total_remaining <= 0:
                return {'will_improve_balance': True, 'reason': 'Closing all positions'}
            
            # คำนวณ Balance Ratio หลังปิด
            new_buy_ratio = remaining_buy / total_remaining
            new_sell_ratio = remaining_sell / total_remaining
            new_balance_score = 100 - abs(new_buy_ratio - new_sell_ratio) * 200
            
            # เปรียบเทียบกับ Balance ปัจจุบัน
            current_balance_score = current_balance.get('balance_score', 0)
            improvement = new_balance_score - current_balance_score
            
            # อนุญาตการปิดที่:
            # 1. ปรับปรุง Balance (improvement > 0)
            # 2. ไม่ทำให้แย่ลงมาก (improvement > -10)
            # 3. หรือ Balance อยู่ในเกณฑ์ดีอยู่แล้ว (new_balance_score > 80)
            will_improve = (improvement > 0 or improvement > -10 or new_balance_score > 80)
            
            reason = f"Balance: {current_balance_score:.1f}→{new_balance_score:.1f} ({improvement:+.1f})"
            
            return {
                'will_improve_balance': will_improve,
                'reason': reason,
                'current_balance_score': current_balance_score,
                'new_balance_score': new_balance_score,
                'improvement': improvement,
                'buy_close': buy_close_count,
                'sell_close': sell_close_count,
                'remaining_buy': remaining_buy,
                'remaining_sell': remaining_sell
            }
            
        except Exception as e:
            logger.error(f"❌ Error checking closing balance: {e}")
            return {'will_improve_balance': True, 'reason': f'Error: {e}'}  # Default to allow
    
    def _log_7d_analysis(self, position_scores: List[PositionScore], top_n: int = 5):
        """📊 แสดงการวิเคราะห์ 7 มิติของตำแหน่งดีสุด"""
        try:
            logger.info("📊 7-Dimensional Position Analysis (Top 5):")
            logger.info("=" * 80)
            
            for i, score in enumerate(position_scores[:top_n]):
                pos = score.position
                ticket = getattr(pos, 'ticket', 'N/A')
                pos_type = 'BUY' if getattr(pos, 'type', 0) == 0 else 'SELL'
                profit = getattr(pos, 'profit', 0)
                volume = getattr(pos, 'volume', 0.01)
                
                logger.info(f"#{i+1} {pos_type} {ticket} | Vol:{volume:.2f} | P&L:${profit:+.2f} | Total:{score.total_score:.1f}")
                logger.info(f"    💰 Profit:{score.profit_score:.1f} | ⚖️ Balance:{score.balance_score:.1f} | 💊 Margin:{score.margin_impact:.1f}")
                logger.info(f"    🔄 Recovery:{score.recovery_potential:.1f} | ⏰ Time:{score.time_score:.1f}")
                logger.info(f"    🔗 Correlation:{score.correlation_score:.1f} | 📊 Volatility:{score.volatility_score:.1f}")
                logger.info(f"    🎯 Priority: {score.priority}")
                logger.info("-" * 60)
                
        except Exception as e:
            logger.error(f"❌ Error logging 7D analysis: {e}")
    
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
