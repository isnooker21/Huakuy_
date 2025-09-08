"""
🚀 Dynamic 7D Smart Closing System
ระบบปิดไม้อัจฉริยะที่ใช้ 7D Analysis และ Dynamic Methods

Features:
- Zero Loss Policy (ไม่ปิดขาดทุนเลย)
- Dynamic Method Selection (เลือกวิธีตามสถานการณ์)
- 7D Intelligence Integration (ใช้ 7D Score เลือกไม้)
- Portfolio Health Optimization (เน้นสุขภาพพอร์ต)
- Edge-Based Clearing (ปิดจากขอบบน-ล่าง)
- Multi-Size Groups (2-25 ไม้)
"""

import logging
import math
import random
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import time

logger = logging.getLogger(__name__)

@dataclass
class PortfolioHealth:
    """Portfolio Health Analysis"""
    balance: float
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    total_pnl: float
    buy_count: int
    sell_count: int
    position_count: int
    buy_sell_ratio: float
    imbalance_percentage: float

@dataclass
class ClosingResult:
    """Closing Decision Result"""
    should_close: bool
    positions_to_close: List[Any]
    method: str
    net_pnl: float
    expected_pnl: float
    position_count: int
    buy_count: int
    sell_count: int
    portfolio_improvement: Dict[str, float]
    confidence_score: float
    reason: str

class Dynamic7DSmartCloser:
    """🚀 Dynamic 7D Smart Closing System"""
    
    def __init__(self, intelligent_manager=None):
        self.intelligent_manager = intelligent_manager
        self.safety_buffer = 2.0  # กำไรขั้นต่ำ $2
        self.max_group_size = 25  # สูงสุด 25 ไม้
        self.min_group_size = 2   # ต่ำสุด 2 ไม้
        
        # Dynamic thresholds
        self.emergency_margin_threshold = 150.0  # Margin Level < 150%
        self.critical_margin_threshold = 120.0   # Margin Level < 120%
        self.imbalance_threshold = 70.0          # Imbalance > 70%
        
        logger.info("🚀 Dynamic 7D Smart Closer initialized")
    
    def find_optimal_closing(self, positions: List[Any], account_info: Dict, 
                           market_conditions: Optional[Dict] = None) -> Optional[ClosingResult]:
        """
        🎯 หาการปิดไม้ที่ดีที่สุด
        """
        try:
            if len(positions) < 2:
                logger.info("⏸️ Need at least 2 positions for closing")
                return None
            
            logger.info(f"🚀 DYNAMIC 7D ANALYSIS: {len(positions)} positions")
            
            # 1. 📊 Portfolio Health Analysis
            portfolio_health = self._analyze_portfolio_health(positions, account_info)
            logger.info(f"💊 Portfolio Health: Margin {portfolio_health.margin_level:.1f}%, "
                       f"Imbalance {portfolio_health.imbalance_percentage:.1f}%")
            
            # 2. 🧠 7D Analysis (if available)
            position_scores = None
            if self.intelligent_manager:
                try:
                    margin_health = self.intelligent_manager._analyze_margin_health(account_info)
                    position_scores = self.intelligent_manager._score_all_positions(positions, account_info, margin_health)
                    logger.info(f"🧠 7D Scores calculated for {len(position_scores)} positions")
                except Exception as e:
                    logger.warning(f"⚠️ 7D Analysis failed: {e}, using fallback")
            
            # 3. 🎯 Dynamic Method Selection
            selected_methods = self._select_dynamic_methods(portfolio_health, market_conditions)
            logger.info(f"🎯 Selected {len(selected_methods)} dynamic methods")
            
            # 4. 🔄 Try methods by priority
            best_result = None
            best_score = -999999
            
            for method_name, min_size, max_size, priority in selected_methods:
                logger.debug(f"🔍 Trying {method_name} (sizes {min_size}-{max_size}, priority {priority:.1f})")
                
                for size in range(min_size, min(max_size + 1, len(positions) + 1)):
                    # ใช้ 7D Scores หรือ fallback
                    if position_scores:
                        result = self._try_7d_method(method_name, position_scores, size, portfolio_health)
                    else:
                        result = self._try_fallback_method(method_name, positions, size, portfolio_health)
                    
                    if result and result['net_pnl'] > self.safety_buffer:  # Zero Loss Policy
                        # คำนวณ Total Impact Score
                        impact_score = self._calculate_total_impact_score(result, portfolio_health)
                        final_score = impact_score * priority  # Apply priority multiplier
                        
                        logger.debug(f"💰 {method_name}_{size}: Net ${result['net_pnl']:.2f}, "
                                   f"Impact {impact_score:.1f}, Final {final_score:.1f}")
                        
                        if final_score > best_score:
                            best_score = final_score
                            best_result = result
                            best_result['method'] = f"{method_name}_{size}"
                            best_result['priority'] = priority
                            best_result['impact_score'] = impact_score
                            best_result['final_score'] = final_score
            
            if best_result:
                # Create final result
                closing_result = ClosingResult(
                    should_close=True,
                    positions_to_close=best_result['positions'],
                    method=best_result['method'],
                    net_pnl=best_result['net_pnl'],
                    expected_pnl=best_result['net_pnl'],
                    position_count=len(best_result['positions']),
                    buy_count=len([p for p in best_result['positions'] if getattr(p, 'type', 0) == 0]),
                    sell_count=len([p for p in best_result['positions'] if getattr(p, 'type', 0) == 1]),
                    portfolio_improvement=best_result.get('portfolio_improvement', {}),
                    confidence_score=min(100, best_result['final_score']),
                    reason=f"Dynamic 7D: {best_result['method']}, Priority {best_result['priority']:.1f}"
                )
                
                logger.info(f"✅ BEST CLOSING FOUND: {closing_result.method}")
                logger.info(f"💰 Net P&L: ${closing_result.net_pnl:.2f}, "
                           f"Positions: {closing_result.position_count} "
                           f"({closing_result.buy_count}B+{closing_result.sell_count}S)")
                logger.info(f"🏆 Confidence: {closing_result.confidence_score:.1f}%")
                
                return closing_result
            
            logger.info("⏸️ No profitable closing opportunities found")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error in dynamic closing analysis: {e}")
            return None
    
    def _analyze_portfolio_health(self, positions: List[Any], account_info: Dict) -> PortfolioHealth:
        """📊 วิเคราะห์สุขภาพพอร์ต"""
        try:
            balance = account_info.get('balance', 0)
            equity = account_info.get('equity', balance)
            margin = account_info.get('margin', 1)
            free_margin = account_info.get('free_margin', equity - margin)
            margin_level = (equity / max(margin, 1)) * 100
            
            total_pnl = sum(getattr(pos, 'profit', 0) for pos in positions)
            buy_count = len([p for p in positions if getattr(p, 'type', 0) == 0])
            sell_count = len([p for p in positions if getattr(p, 'type', 0) == 1])
            position_count = len(positions)
            
            buy_sell_ratio = buy_count / max(1, sell_count)
            imbalance_percentage = abs(buy_count - sell_count) / max(1, position_count) * 100
            
            return PortfolioHealth(
                balance=balance,
                equity=equity,
                margin=margin,
                free_margin=free_margin,
                margin_level=margin_level,
                total_pnl=total_pnl,
                buy_count=buy_count,
                sell_count=sell_count,
                position_count=position_count,
                buy_sell_ratio=buy_sell_ratio,
                imbalance_percentage=imbalance_percentage
            )
        except Exception as e:
            logger.error(f"❌ Error analyzing portfolio health: {e}")
            return PortfolioHealth(0, 0, 1, 0, 100, 0, 0, 0, 0, 1.0, 0)
    
    def _select_dynamic_methods(self, portfolio_health: PortfolioHealth, 
                               market_conditions: Optional[Dict] = None) -> List[Tuple[str, int, int, float]]:
        """🎯 เลือกวิธีการปิดแบบ Dynamic"""
        methods = []
        
        # 📊 Position count-based selection
        total_positions = portfolio_health.position_count
        
        if total_positions > 40:
            # เยอะมาก → เน้น Large Groups
            methods.extend([
                ('large_groups_7d', 15, 25, 1.0),
                ('mixed_edge_7d', 12, 20, 0.9),
                ('emergency_mass_closing', 20, 25, 0.8)
            ])
        elif total_positions > 25:
            # ปานกลาง → เน้น Medium Groups
            methods.extend([
                ('medium_groups_7d', 8, 15, 1.0),
                ('mixed_edge_7d', 8, 12, 0.9),
                ('smart_7d_selection', 6, 12, 0.8)
            ])
        elif total_positions > 10:
            # น้อย → เน้น Small Groups
            methods.extend([
                ('small_groups_7d', 4, 8, 1.0),
                ('balanced_pairs_7d', 2, 6, 0.9),
                ('smart_7d_selection', 3, 8, 0.8)
            ])
        else:
            # น้อยมาก → เน้น Pairs
            methods.extend([
                ('balanced_pairs_7d', 2, 4, 1.0),
                ('smart_7d_selection', 2, 6, 0.9)
            ])
        
        # ⚖️ Imbalance-based selection
        if portfolio_health.imbalance_percentage > self.imbalance_threshold:
            methods.extend([
                ('force_balance_7d', 4, 16, 1.3),
                ('cross_balance_groups_7d', 6, 18, 1.2)
            ])
        
        # 🚨 Margin-based selection
        if portfolio_health.margin_level < self.emergency_margin_threshold:
            methods.extend([
                ('emergency_margin_relief', 8, 25, 1.5),
                ('high_margin_impact_7d', 6, 20, 1.4)
            ])
        
        # 🎯 Edge-based methods (always available)
        methods.extend([
            ('top_edge_7d', 3, 12, 0.7),
            ('bottom_edge_7d', 3, 12, 0.7),
            ('mixed_edge_7d', 4, 15, 0.8)
        ])
        
        # Sort by priority (highest first)
        return sorted(methods, key=lambda x: x[3], reverse=True)
    
    def _try_7d_method(self, method_name: str, position_scores: List[Any], 
                      size: int, portfolio_health: PortfolioHealth) -> Optional[Dict]:
        """🧠 ลองใช้วิธีการที่มี 7D Scores"""
        try:
            if method_name == 'smart_7d_selection':
                # เรียงตาม 7D Score
                sorted_positions = sorted(position_scores, 
                                        key=lambda x: x.total_score, reverse=True)
                selected = sorted_positions[:size]
                
            elif method_name == 'top_edge_7d':
                # ขอบบน + 7D Score
                top_positions = self._get_top_edge_positions(position_scores)
                selected = sorted(top_positions, 
                                key=lambda x: x.total_score, reverse=True)[:size]
                
            elif method_name == 'bottom_edge_7d':
                # ขอบล่าง + 7D Score
                bottom_positions = self._get_bottom_edge_positions(position_scores)
                selected = sorted(bottom_positions,
                                key=lambda x: x.total_score, reverse=True)[:size]
                
            elif method_name == 'mixed_edge_7d':
                # ขอบผสม + 7D Score
                top_half = self._get_top_edge_positions(position_scores)[:size//2]
                bottom_half = self._get_bottom_edge_positions(position_scores)[:size//2]
                remaining = size - len(top_half) - len(bottom_half)
                if remaining > 0:
                    middle_positions = [p for p in position_scores 
                                      if p not in top_half and p not in bottom_half]
                    middle_best = sorted(middle_positions, 
                                       key=lambda x: x.total_score, reverse=True)[:remaining]
                    selected = top_half + bottom_half + middle_best
                else:
                    selected = top_half + bottom_half
                    
            elif method_name == 'force_balance_7d':
                # บังคับ Balance + 7D Score
                selected = self._find_7d_balance_combination(position_scores, size, portfolio_health)
                
            elif method_name in ['small_groups_7d', 'medium_groups_7d', 'large_groups_7d']:
                # กลุ่มต่างขนาด + 7D Score
                selected = self._find_7d_optimal_group(position_scores, size, portfolio_health)
                
            elif method_name == 'emergency_margin_relief':
                # Emergency Margin + 7D Score
                selected = self._find_7d_margin_relief(position_scores, size, portfolio_health)
                
            else:
                # Fallback to smart selection
                sorted_positions = sorted(position_scores, 
                                        key=lambda x: x.total_score, reverse=True)
                selected = sorted_positions[:size]
            
            if not selected:
                return None
            
            # คำนวณผลลัพธ์
            positions = [score.position for score in selected]
            return self._calculate_combination_result(positions, portfolio_health)
            
        except Exception as e:
            logger.error(f"❌ Error in 7D method {method_name}: {e}")
            return None
    
    def _try_fallback_method(self, method_name: str, positions: List[Any], 
                           size: int, portfolio_health: PortfolioHealth) -> Optional[Dict]:
        """🔄 ลองใช้วิธีการ Fallback (ไม่มี 7D)"""
        try:
            if method_name.endswith('_7d'):
                # ลบ _7d suffix สำหรับ fallback
                base_method = method_name.replace('_7d', '')
            else:
                base_method = method_name
            
            if base_method == 'smart_selection':
                # เรียงตาม profit
                sorted_positions = sorted(positions, 
                                        key=lambda x: getattr(x, 'profit', 0), reverse=True)
                selected = sorted_positions[:size]
                
            elif base_method == 'top_edge':
                # ขอบบน
                sorted_by_price = sorted(positions, 
                                       key=lambda x: getattr(x, 'open_price', 0), reverse=True)
                selected = sorted_by_price[:size]
                
            elif base_method == 'bottom_edge':
                # ขอบล่าง
                sorted_by_price = sorted(positions, 
                                       key=lambda x: getattr(x, 'open_price', 0))
                selected = selected[:size]
                
            elif base_method == 'mixed_edge':
                # ขอบผสม
                sorted_by_price_high = sorted(positions, 
                                            key=lambda x: getattr(x, 'open_price', 0), reverse=True)
                sorted_by_price_low = sorted(positions, 
                                           key=lambda x: getattr(x, 'open_price', 0))
                top_half = sorted_by_price_high[:size//2]
                bottom_half = sorted_by_price_low[:size//2]
                selected = top_half + bottom_half
                
            else:
                # Default: เรียงตาม profit
                sorted_positions = sorted(positions, 
                                        key=lambda x: getattr(x, 'profit', 0), reverse=True)
                selected = sorted_positions[:size]
            
            if not selected:
                return None
            
            return self._calculate_combination_result(selected, portfolio_health)
            
        except Exception as e:
            logger.error(f"❌ Error in fallback method {method_name}: {e}")
            return None
    
    def _get_top_edge_positions(self, position_scores: List[Any]) -> List[Any]:
        """🔝 หา positions ขอบบน (ราคาสูงสุด)"""
        return sorted(position_scores, 
                     key=lambda x: getattr(x.position, 'open_price', 0), reverse=True)
    
    def _get_bottom_edge_positions(self, position_scores: List[Any]) -> List[Any]:
        """🔻 หา positions ขอบล่าง (ราคาต่ำสุด)"""
        return sorted(position_scores, 
                     key=lambda x: getattr(x.position, 'open_price', 0))
    
    def _find_7d_balance_combination(self, position_scores: List[Any], size: int, 
                                   portfolio_health: PortfolioHealth) -> List[Any]:
        """⚖️ หาชุดที่ Balance และมี 7D Score ดี"""
        try:
            buy_scores = [s for s in position_scores if getattr(s.position, 'type', 0) == 0]
            sell_scores = [s for s in position_scores if getattr(s.position, 'type', 0) == 1]
            
            # เรียงตาม 7D Score
            buy_scores.sort(key=lambda x: x.total_score, reverse=True)
            sell_scores.sort(key=lambda x: x.total_score, reverse=True)
            
            # พยายาม balance
            target_buy = size // 2
            target_sell = size - target_buy
            
            selected_buys = buy_scores[:min(target_buy, len(buy_scores))]
            selected_sells = sell_scores[:min(target_sell, len(sell_scores))]
            
            # เติมให้ครบ size ถ้าไม่พอ
            selected = selected_buys + selected_sells
            if len(selected) < size:
                remaining_scores = [s for s in position_scores if s not in selected]
                remaining_scores.sort(key=lambda x: x.total_score, reverse=True)
                selected.extend(remaining_scores[:size - len(selected)])
            
            return selected[:size]
            
        except Exception as e:
            logger.error(f"❌ Error finding 7D balance combination: {e}")
            return []
    
    def _find_7d_optimal_group(self, position_scores: List[Any], size: int, 
                             portfolio_health: PortfolioHealth) -> List[Any]:
        """🎯 หากลุ่มที่ดีที่สุดตาม 7D Score"""
        try:
            # เรียงตาม 7D Score
            sorted_scores = sorted(position_scores, key=lambda x: x.total_score, reverse=True)
            
            # เลือก top positions
            return sorted_scores[:size]
            
        except Exception as e:
            logger.error(f"❌ Error finding 7D optimal group: {e}")
            return []
    
    def _find_7d_margin_relief(self, position_scores: List[Any], size: int, 
                             portfolio_health: PortfolioHealth) -> List[Any]:
        """🚨 หาชุดที่ช่วยลด Margin Risk"""
        try:
            # เรียงตาม margin_impact (สูงสุดก่อน) และ profit
            sorted_scores = sorted(position_scores, 
                                 key=lambda x: (x.margin_impact, x.profit_score), reverse=True)
            
            return sorted_scores[:size]
            
        except Exception as e:
            logger.error(f"❌ Error finding 7D margin relief: {e}")
            return []
    
    def _calculate_combination_result(self, positions: List[Any], 
                                    portfolio_health: PortfolioHealth) -> Dict:
        """💰 คำนวณผลลัพธ์ของการปิดชุด positions"""
        try:
            if not positions:
                return None
            
            # คำนวณ P&L รวม
            total_profit = sum(getattr(pos, 'profit', 0) for pos in positions)
            
            # คำนวณ cost การปิด
            closing_cost = self._calculate_closing_cost(positions)
            
            net_pnl = total_profit - closing_cost
            
            # คำนวณการปรับปรุง Portfolio
            buy_count = len([p for p in positions if getattr(p, 'type', 0) == 0])
            sell_count = len([p for p in positions if getattr(p, 'type', 0) == 1])
            
            portfolio_improvement = {
                'pnl_improvement': net_pnl,
                'position_reduction': len(positions),
                'balance_improvement': self._calculate_balance_improvement(
                    buy_count, sell_count, portfolio_health
                ),
                'margin_improvement': self._calculate_margin_improvement(
                    positions, portfolio_health
                )
            }
            
            return {
                'positions': positions,
                'total_profit': total_profit,
                'closing_cost': closing_cost,
                'net_pnl': net_pnl,
                'buy_count': buy_count,
                'sell_count': sell_count,
                'portfolio_improvement': portfolio_improvement
            }
            
        except Exception as e:
            logger.error(f"❌ Error calculating combination result: {e}")
            return None
    
    def _calculate_closing_cost(self, positions: List[Any]) -> float:
        """💸 คำนวณ cost การปิด"""
        try:
            total_volume = sum(getattr(pos, 'volume', 0.01) for pos in positions)
            
            # ประมาณการ cost (spread + commission + slippage)
            spread_cost = total_volume * 0.8    # $0.8 per lot
            commission_cost = total_volume * 0.3  # $0.3 per lot  
            slippage_cost = total_volume * 1.0   # $1.0 per lot
            
            return spread_cost + commission_cost + slippage_cost
            
        except Exception as e:
            logger.error(f"❌ Error calculating closing cost: {e}")
            return len(positions) * 2.0  # Fallback cost
    
    def _calculate_balance_improvement(self, buy_count: int, sell_count: int, 
                                     portfolio_health: PortfolioHealth) -> float:
        """⚖️ คำนวณการปรับปรุง Balance"""
        try:
            current_imbalance = abs(portfolio_health.buy_count - portfolio_health.sell_count)
            after_buy_count = portfolio_health.buy_count - buy_count
            after_sell_count = portfolio_health.sell_count - sell_count
            after_imbalance = abs(after_buy_count - after_sell_count)
            
            return current_imbalance - after_imbalance
            
        except Exception as e:
            logger.error(f"❌ Error calculating balance improvement: {e}")
            return 0.0
    
    def _calculate_margin_improvement(self, positions: List[Any], 
                                    portfolio_health: PortfolioHealth) -> float:
        """📊 คำนวณการปรับปรุง Margin"""
        try:
            # ประมาณการ margin ที่จะได้คืน
            total_volume = sum(getattr(pos, 'volume', 0.01) for pos in positions)
            margin_per_lot = 100  # ประมาณ $100 per lot
            margin_released = total_volume * margin_per_lot
            
            current_margin = portfolio_health.margin
            after_margin = current_margin - margin_released
            
            current_margin_level = portfolio_health.margin_level
            after_margin_level = (portfolio_health.equity / max(after_margin, 1)) * 100
            
            return after_margin_level - current_margin_level
            
        except Exception as e:
            logger.error(f"❌ Error calculating margin improvement: {e}")
            return 0.0
    
    def _calculate_total_impact_score(self, result: Dict, portfolio_health: PortfolioHealth) -> float:
        """🏆 คำนวณคะแนนผลกระทบรวม"""
        try:
            improvement = result['portfolio_improvement']
            
            # 1. P&L Score (40%)
            pnl_score = improvement['pnl_improvement'] * 10
            
            # 2. Position Reduction Score (25%)
            reduction_score = improvement['position_reduction'] * 5
            
            # 3. Balance Improvement Score (20%)
            balance_score = improvement['balance_improvement'] * 8
            
            # 4. Margin Improvement Score (15%)
            margin_score = improvement['margin_improvement'] * 2
            
            total_score = (pnl_score * 0.4 + reduction_score * 0.25 + 
                          balance_score * 0.2 + margin_score * 0.15)
            
            return max(0, total_score)
            
        except Exception as e:
            logger.error(f"❌ Error calculating total impact score: {e}")
            return 0.0


def create_dynamic_7d_smart_closer(intelligent_manager=None):
    """🏭 Factory function สำหรับสร้าง Dynamic 7D Smart Closer"""
    return Dynamic7DSmartCloser(intelligent_manager)


if __name__ == "__main__":
    # Demo Dynamic 7D Smart Closer
    import logging
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    logger.info("🚀 Dynamic 7D Smart Closer Demo")
    logger.info("This system provides intelligent, dynamic position closing")
    logger.info("Features: Zero Loss, 7D Intelligence, Edge Clearing, Multi-Size Groups")
    logger.info("Dynamic 7D Smart Closer ready for integration!")
