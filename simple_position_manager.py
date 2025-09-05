# -*- coding: utf-8 -*-
"""
Simple Position Manager
ระบบจัดการไม้แบบเรียบง่าย - วิเคราะห์ทุกไม้แล้วตัดสินใจปิด

🎯 หลักการ:
1. วิเคราะห์ทุกไม้ในพอร์ต
2. จำลองการปิดทุกแบบ (2 ไม้, 3 ไม้, หลายไม้)
3. ตัดสินใจ: ปิดแล้วพอร์ตดีขึ้นไหม? ลดไม้ได้ไหม?
4. ปิดได้ทุกแบบ ยกเว้น ปิดไม้เดี่ยวที่เก็บแต่กำไร

✅ เรียบง่าย ✅ เร็ว ✅ ยืดหยุ่น ✅ มีเหตุผล
"""

import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from itertools import combinations

logger = logging.getLogger(__name__)

class SimplePositionManager:
    """🚀 Hybrid Adaptive Position Manager + Universal Recovery - ระบบจัดการไม้แบบปรับตัวได้พร้อม Recovery"""
    
    def __init__(self, mt5_connection, order_manager):
        self.mt5 = mt5_connection
        self.order_manager = order_manager
        
        # 🎯 Adaptive Settings
        self.max_acceptable_loss = 5.0  # ยอมรับขาดทุนสูงสุด $5 เพื่อลดไม้ (รวมสเปรด)
        self.min_positions_to_close = 2  # ปิดอย่างน้อย 2 ไม้ขึ้นไป
        self.max_positions_per_round = 10  # ปิดสูงสุด 10 ไม้ต่อรอบ
        
        # 🎯 Adaptive Mode Thresholds
        self.normal_mode_threshold = 40.0  # Wrong positions < 40% = Normal Mode
        self.balance_mode_threshold = 70.0  # Wrong positions 40-70% = Balance Mode
        # Wrong positions > 70% = Survival Mode
        
        # 🎯 Universal Recovery Integration
        self.recovery_manager = None  # จะถูกตั้งค่าใน integration
        self.enable_universal_recovery = True  # เปิดใช้ Universal Recovery
        
        # 📊 สถิติ
        self.total_closures = 0
        self.total_positions_closed = 0
        self.total_profit_realized = 0.0
        self.current_mode = "Normal"  # Normal, Balance, Survival
        
    def analyze_portfolio_health(self, positions: List[Any], current_price: float) -> Dict[str, Any]:
        """
        🏥 วิเคราะห์สุขภาพ Portfolio และกำหนด Management Mode
        
        Args:
            positions: รายการ positions ทั้งหมด
            current_price: ราคาปัจจุบัน
            
        Returns:
            Dict: สุขภาพ Portfolio และ Mode ที่แนะนำ
        """
        if not positions:
            return {
                'mode': 'Normal',
                'wrong_percentage': 0.0,
                'wrong_buys': 0,
                'wrong_sells': 0,
                'total_positions': 0,
                'health_status': 'Excellent'
            }
            
        # นับ Wrong Positions
        wrong_buys = 0  # BUY เหนือราคาปัจจุบัน (ซื้อแพง)
        wrong_sells = 0  # SELL ใต้ราคาปัจจุบัน (ขายถูก)
        total_positions = len(positions)
        
        for pos in positions:
            if hasattr(pos, 'type'):
                pos_type = pos.type
            else:
                pos_type = pos.order_type if hasattr(pos, 'order_type') else 'unknown'
                
            if pos_type == 0:  # BUY
                if pos.price_open > current_price:
                    wrong_buys += 1
            elif pos_type == 1:  # SELL
                if pos.price_open < current_price:
                    wrong_sells += 1
        
        wrong_total = wrong_buys + wrong_sells
        wrong_percentage = (wrong_total / total_positions) * 100 if total_positions > 0 else 0
        
        # กำหนด Mode ตาม Wrong Percentage
        if wrong_percentage < self.normal_mode_threshold:
            mode = 'Normal'
            health_status = 'Good'
        elif wrong_percentage < self.balance_mode_threshold:
            mode = 'Balance'
            health_status = 'Fair'
        else:
            mode = 'Survival'
            health_status = 'Critical'
            
        self.current_mode = mode
        
        logger.info(f"🏥 Portfolio Health Analysis:")
        logger.info(f"   Total Positions: {total_positions}")
        logger.info(f"   Wrong BUYs: {wrong_buys} (above price)")
        logger.info(f"   Wrong SELLs: {wrong_sells} (below price)")
        logger.info(f"   Wrong Percentage: {wrong_percentage:.1f}%")
        logger.info(f"   Management Mode: {mode}")
        logger.info(f"   Health Status: {health_status}")
        
        return {
            'mode': mode,
            'wrong_percentage': wrong_percentage,
            'wrong_buys': wrong_buys,
            'wrong_sells': wrong_sells,
            'total_positions': total_positions,
            'health_status': health_status
        }

    def should_close_positions(self, positions: List[Any], current_price: float) -> Dict[str, Any]:
        """
        🔍 ตรวจสอบว่าควรปิดไม้หรือไม่ (Enhanced with Universal Recovery)
        
        Args:
            positions: รายการ positions ทั้งหมด
            current_price: ราคาปัจจุบัน
            
        Returns:
            Dict: ผลการตรวจสอบพร้อมรายการไม้ที่ควรปิด
        """
        try:
            # เช็คเบื้องต้น
            if len(positions) < 2:
                return {
                    'should_close': False,
                    'reason': 'Need at least 2 positions to close',
                    'positions_to_close': [],
                    'method': 'none'
                }
            
            # 🚀 1. Universal Recovery Check (ถ้าเปิดใช้)
            if self.enable_universal_recovery and self.recovery_manager:
                try:
                    # วิเคราะห์ Balance
                    balance_analysis = self._analyze_portfolio_balance(positions, current_price)
                    
                    # วิเคราะห์ Drag Recovery
                    drag_analysis = self.recovery_manager.analyze_dragged_positions(positions, current_price)
                    
                    # หา Smart Combinations
                    smart_combinations = self.recovery_manager.find_smart_combinations(
                        positions, current_price, balance_analysis
                    )
                    
                    if smart_combinations:
                        best_combination = smart_combinations[0]  # Top scored
                        
                        logger.info(f"🎯 Universal Recovery: {best_combination['type']} (Score: {best_combination['score']:.2f})")
                        logger.info(f"💰 Profit: ${best_combination['total_profit']:.2f}")
                        logger.info(f"📊 Positions: {len(best_combination['positions'])}")
                        
                        return {
                            'should_close': True,
                            'reason': f"Universal Recovery: {best_combination['type']} (Score: {best_combination['score']:.2f})",
                            'positions_to_close': best_combination['positions'],
                            'expected_pnl': best_combination['total_profit'],
                            'positions_count': len(best_combination['positions']),
                            'combination_type': best_combination['type'],
                            'method': 'universal_recovery',
                            'drag_analysis': drag_analysis
                        }
                        
                except Exception as recovery_error:
                    logger.warning(f"⚠️ Universal Recovery error: {recovery_error}")
                    # Continue to adaptive method
            
            # 🎯 2. Fallback to Adaptive Method
            # วิเคราะห์สุขภาพ Portfolio
            health_analysis = self.analyze_portfolio_health(positions, current_price)
            
            # วิเคราะห์ทุกไม้ (ไม่ log เพื่อความเร็ว)
            analyzed_positions = self._analyze_all_positions(positions, current_price)
            
            if len(analyzed_positions) < 2:
                return {
                    'should_close': False,
                    'reason': 'Not enough valid positions after analysis',
                    'positions_to_close': [],
                    'method': 'none'
                }
            
            # หาการจับคู่ที่ดีที่สุดแบบ Adaptive
            best_combination = self._find_adaptive_closing_combination(
                analyzed_positions, current_price, health_analysis
            )
            
            if best_combination:
                # ตรวจสอบอีกครั้งก่อนปิด - ต้องมีกำไรจริงๆ
                expected_pnl = best_combination['total_pnl']
                
                # Double-check P&L โดยใช้ profit จาก position จริง
                actual_pnl = sum(pos.profit for pos in best_combination['positions'] if hasattr(pos, 'profit'))
                if actual_pnl != 0.0:
                    expected_pnl = actual_pnl  # ใช้ค่าจริงจาก MT5
                    logger.info(f"🔍 Using actual P&L from positions: ${actual_pnl:.2f}")
                
                # ADAPTIVE PROFIT THRESHOLD ตาม Mode
                mode = health_analysis['mode']
                if mode == 'Survival':
                    min_profit = 0.10  # Survival: ยอมรับกำไรน้อย
                elif mode == 'Balance':
                    min_profit = 0.25  # Balance: กำไรปานกลาง
                else:  # Normal
                    min_profit = 0.50  # Normal: ต้องการกำไรดี
                
                # ป้องกันการปิดติดลบอย่างเข้มงวด
                if expected_pnl > min_profit:
                    logger.info(f"🎯 ADAPTIVE CLOSE ({mode} Mode): {len(best_combination['positions'])} positions, ${expected_pnl:.2f}")
                    return {
                        'should_close': True,
                        'reason': best_combination.get('reason', f'{mode} mode: Profitable combination'),
                        'positions_to_close': best_combination['positions'],
                        'expected_pnl': expected_pnl,
                        'positions_count': len(best_combination['positions']),
                        'combination_type': best_combination.get('type', mode),
                        'method': 'adaptive'
                    }
                else:
                    logger.info(f"🚫 Not profitable enough ({mode} Mode): ${expected_pnl:.2f} < ${min_profit:.2f}")
                    return {
                        'should_close': False,
                        'reason': f'{mode} Mode: ${expected_pnl:.2f} < ${min_profit:.2f}',
                        'positions_to_close': [],
                        'method': 'adaptive_insufficient'
                    }
            else:
                # ไม่ log เพื่อลด noise
                return {
                    'should_close': False,
                    'reason': 'No suitable closing combination found',
                    'positions_to_close': [],
                    'method': 'adaptive_no_combination'
                }
                
        except Exception as e:
            logger.error(f"🚨 CRITICAL ERROR in position analysis: {e}")
            import traceback
            logger.error(f"🚨 Traceback: {traceback.format_exc()}")
            return {
                'should_close': False,
                'reason': f'Analysis error: {e}',
                'positions_to_close': []
            }
    
    def _find_best_closing_combination_balanced(self, analyzed_positions: List[Dict], current_price: float) -> Optional[Dict]:
        """
        🎯 หาการจับคู่ที่ดีที่สุดแบบสมดุล Portfolio
        
        Logic:
        1. เช็ค Portfolio Balance
        2. ถ้าเบี้ยว → บังคับปิดฝั่งที่เยอะ
        3. ถ้าสมดุล → ปิดตามระยะห่าง + กำไร
        
        Args:
            analyzed_positions: รายการ positions ที่วิเคราะห์แล้ว
            current_price: ราคาปัจจุบัน
            
        Returns:
            Dict: การจับคู่ที่ดีที่สุด หรือ None
        """
        try:
            if len(analyzed_positions) < 2:
                return None
                
            # 1. วิเคราะห์ Portfolio Balance
            balance_analysis = self._analyze_portfolio_balance(analyzed_positions, current_price)
            
            # 2. เลือกกลยุทธ์ตาม Balance
            if balance_analysis['is_imbalanced']:
                # Portfolio เบี้ยว → ใช้ Balance Priority Strategy
                return self._find_balance_priority_combination(analyzed_positions, balance_analysis, current_price)
            else:
                # Portfolio สมดุล → ใช้ Distance + Profit Strategy  
                return self._find_distance_profit_combination(analyzed_positions, current_price)
                
        except Exception as e:
            logger.error(f"Error finding balanced combination: {e}")
            # Fallback ไปใช้ระบบเดิม
            return self._find_best_closing_combination(analyzed_positions)
    
    def _analyze_portfolio_balance(self, analyzed_positions: List[Dict], current_price: float) -> Dict[str, Any]:
        """📊 วิเคราะห์ความสมดุลของ Portfolio"""
        buy_positions = [pos for pos in analyzed_positions if pos['position'].type == 0]
        sell_positions = [pos for pos in analyzed_positions if pos['position'].type == 1]
        
        total_positions = len(analyzed_positions)
        buy_count = len(buy_positions)
        sell_count = len(sell_positions)
        
        if total_positions == 0:
            return {'is_imbalanced': False, 'imbalance_side': None}
        
        buy_ratio = buy_count / total_positions
        sell_ratio = sell_count / total_positions
        
        # เบี้ยวถ้าฝั่งหนึ่งมากกว่า 70%
        imbalanced = max(buy_ratio, sell_ratio) > 0.7
        
        if imbalanced:
            imbalance_side = 'BUY' if buy_ratio > sell_ratio else 'SELL'
            imbalance_severity = max(buy_ratio, sell_ratio)
        else:
            imbalance_side = None
            imbalance_severity = 0.0
            
        return {
            'is_imbalanced': imbalanced,
            'imbalance_side': imbalance_side,
            'imbalance_severity': imbalance_severity,
            'buy_count': buy_count,
            'sell_count': sell_count,
            'buy_ratio': buy_ratio,
            'sell_ratio': sell_ratio
        }
    
    def _find_balance_priority_combination(self, analyzed_positions: List[Dict], balance_analysis: Dict, current_price: float) -> Optional[Dict]:
        """🎯 หาการจับคู่แบบ Balance Priority (ปิดฝั่งที่เยอะก่อน)"""
        try:
            imbalance_side = balance_analysis['imbalance_side']
            
            # แยกไม้ตามฝั่ง
            buy_positions = [pos for pos in analyzed_positions if pos['position'].type == 0]
            sell_positions = [pos for pos in analyzed_positions if pos['position'].type == 1]
            
            # เรียงตามระยะห่าง (ห่างมาก → ปิดก่อน) - ใช้ current_price แทน distance_from_price
            buy_positions.sort(key=lambda x: abs(x['position'].price_open - current_price), reverse=True)
            sell_positions.sort(key=lambda x: abs(x['position'].price_open - current_price), reverse=True)
            
            best_combination = None
            best_score = -999999
            
            # ทดสอบการจับคู่ต่างๆ โดยให้ความสำคัญกับการลดฝั่งที่เยอะ
            for size in range(2, min(6, len(analyzed_positions) + 1)):  # 2-5 positions
                for combination in combinations(analyzed_positions, size):
                    combo_buy = [pos for pos in combination if pos['position'].type == 0]
                    combo_sell = [pos for pos in combination if pos['position'].type == 1]
                    
                    # คำนวณ P&L
                    total_pnl = sum(pos['current_pnl'] for pos in combination)
                    
                    if total_pnl <= 0:  # ต้องมีกำไรเท่านั้น
                        continue
                        
                    # คำนวณคะแนน Balance Priority
                    score = total_pnl  # เริ่มจากกำไร
                    
                    # โบนัสสำหรับการลดฝั่งที่เยอะ
                    if imbalance_side == 'BUY' and len(combo_buy) > len(combo_sell):
                        score += 50  # โบนัสการลด BUY
                    elif imbalance_side == 'SELL' and len(combo_sell) > len(combo_buy):
                        score += 50  # โบนัสการลด SELL
                    
                    # โบนัสสำหรับการปิดไม้ห่าง - คำนวณจาก current_price
                    distance_bonus = sum(abs(pos['position'].price_open - current_price) for pos in combination) * 0.1
                    score += distance_bonus
                    
                    if score > best_score:
                        best_score = score
                        best_combination = {
                            'positions': [pos['position'] for pos in combination],
                            'total_pnl': total_pnl,
                            'combination_size': size,
                            'strategy': 'Balance Priority',
                            'balance_improvement': f"Reduce {imbalance_side} imbalance"
                        }
            
            return best_combination
            
        except Exception as e:
            logger.error(f"Error in balance priority combination: {e}")
            return None
    
    def _find_distance_profit_combination(self, analyzed_positions: List[Dict], current_price: float) -> Optional[Dict]:
        """🎯 หาการจับคู่แบบ Distance + Profit Priority (Portfolio สมดุลแล้ว)"""
        try:
            best_combination = None
            best_score = -999999
            
            # ทดสอบการจับคู่ต่างๆ โดยให้ความสำคัญกับไม้ห่าง + กำไร
            for size in range(2, min(6, len(analyzed_positions) + 1)):  # 2-5 positions
                for combination in combinations(analyzed_positions, size):
                    # คำนวณ P&L
                    total_pnl = sum(pos['current_pnl'] for pos in combination)
                    
                    if total_pnl <= 0:  # ต้องมีกำไรเท่านั้น
                        continue
                        
                    # คำนวณคะแนน Distance + Profit
                    profit_score = total_pnl * 10  # กำไรมีน้ำหนักมาก
                    distance_score = sum(abs(pos['position'].price_open - current_price) for pos in combination)
                    
                    # รวมคะแนน
                    total_score = profit_score + distance_score
                    
                    if total_score > best_score:
                        best_score = total_score
                        best_combination = {
                            'positions': [pos['position'] for pos in combination],
                            'total_pnl': total_pnl,
                            'combination_size': size,
                            'strategy': 'Distance + Profit',
                            'balance_improvement': 'Maintain balance'
                        }
            
            return best_combination
            
        except Exception as e:
            logger.error(f"Error in distance profit combination: {e}")
            return None

    def _find_adaptive_closing_combination(self, analyzed_positions: List[Dict], current_price: float, health_analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        🚀 หาการจับคู่ปิดแบบ Adaptive ตาม Management Mode
        
        Args:
            analyzed_positions: รายการ positions ที่วิเคราะห์แล้ว
            current_price: ราคาปัจจุบัน
            health_analysis: ผลวิเคราะห์สุขภาพ Portfolio
            
        Returns:
            Optional[Dict]: การจับคู่ที่ดีที่สุด หรือ None
        """
        mode = health_analysis['mode']
        logger.info(f"🎯 Using {mode} Mode for combination selection")
        
        if mode == 'Normal':
            return self._find_normal_mode_combination(analyzed_positions, current_price)
        elif mode == 'Balance':
            return self._find_balance_mode_combination(analyzed_positions, current_price, health_analysis)
        else:  # Survival
            return self._find_survival_mode_combination(analyzed_positions, current_price)
    
    def _find_normal_mode_combination(self, analyzed_positions: List[Dict], current_price: float) -> Optional[Dict[str, Any]]:
        """
        🟢 Normal Mode: เน้นเก็บกำไรสูงสุด
        Portfolio สุขภาพดี (Wrong < 40%)
        """
        logger.info("🟢 Normal Mode: เน้นเก็บกำไรสูงสุด")
        return self._find_max_profit_combination(analyzed_positions, current_price)
    
    def _find_balance_mode_combination(self, analyzed_positions: List[Dict], current_price: float, health_analysis: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        🟡 Balance Mode: เน้นแก้สมดุล Portfolio
        Portfolio เริ่มเสียสมดุล (Wrong 40-70%)
        """
        logger.info("🟡 Balance Mode: เน้นแก้สมดุล Portfolio")
        
        # ใช้ _analyze_portfolio_balance ที่มีอยู่แล้ว
        balance_analysis = self._analyze_portfolio_balance(analyzed_positions, current_price)
        
        return self._find_balance_priority_combination(analyzed_positions, balance_analysis, current_price)
    
    def _find_survival_mode_combination(self, analyzed_positions: List[Dict], current_price: float) -> Optional[Dict[str, Any]]:
        """
        🔴 Survival Mode: เน้นความอยู่รอด
        Portfolio วิกฤต (Wrong > 70%)
        """
        logger.info("🔴 Survival Mode: เน้นความอยู่รอด - ปิดทุก Combination ที่มีกำไร")
        return self._find_any_profitable_combination(analyzed_positions, current_price)
    
    def _find_max_profit_combination(self, analyzed_positions: List[Dict], current_price: float) -> Optional[Dict[str, Any]]:
        """🟢 หาการจับคู่ที่ให้กำไรสูงสุด"""
        try:
            max_combinations = min(1000, len(analyzed_positions) * 20)
            best_combination = None
            best_score = 0
            
            for size in range(2, min(6, len(analyzed_positions) + 1)):
                combinations_count = 0
                for combo in combinations(analyzed_positions, size):
                    if combinations_count >= max_combinations:
                        break
                        
                    total_pnl = sum(pos['current_pnl'] for pos in combo)
                    
                    if total_pnl > 0.50:  # ต้องมีกำไรอย่างน้อย $0.50
                        # Score = กำไรสูง + ลดไม้เยอะ
                        score = total_pnl * 10 + len(combo) * 2
                        
                        if score > best_score:
                            best_score = score
                            best_combination = {
                                'positions': [pos['position'] for pos in combo],
                                'total_pnl': total_pnl,
                                'size': len(combo),
                                'reason': f'Max profit: ${total_pnl:.2f}',
                                'type': 'normal_mode'
                            }
                    
                    combinations_count += 1
                    
            return best_combination
            
        except Exception as e:
            logger.error(f"Error in max profit combination: {e}")
            return None
    
    def _find_any_profitable_combination(self, analyzed_positions: List[Dict], current_price: float) -> Optional[Dict[str, Any]]:
        """🔴 หาการจับคู่ใดก็ได้ที่มีกำไร (Survival Mode)"""
        try:
            # ใน Survival Mode ปิดทุก Combination ที่มีกำไร แม้น้อย
            for size in range(2, min(4, len(analyzed_positions) + 1)):  # จำกัดขนาดเพื่อความเร็ว
                for combo in combinations(analyzed_positions, size):
                    total_pnl = sum(pos['current_pnl'] for pos in combo)
                    
                    if total_pnl > 0.10:  # ลดเกณฑ์เหลือ $0.10 เพื่อความอยู่รอด
                        return {
                            'positions': [pos['position'] for pos in combo],
                            'total_pnl': total_pnl,
                            'size': len(combo),
                            'reason': f'Survival mode: ${total_pnl:.2f}',
                            'type': 'survival_mode'
                        }
                        
            return None
            
        except Exception as e:
            logger.error(f"Error in survival combination: {e}")
            return None
    
    def close_positions(self, positions_to_close: List[Any]) -> Dict[str, Any]:
        """
        🔥 ปิดไม้ตามรายการที่กำหนด
        
        Args:
            positions_to_close: รายการไม้ที่จะปิด
            
        Returns:
            Dict: ผลการปิดไม้
        """
        try:
            if not positions_to_close:
                return {
                    'success': False,
                    'message': 'No positions to close',
                    'closed_count': 0,
                    'total_profit': 0.0
                }
            
            start_time = datetime.now()
            successful_closes = 0
            total_profit = 0.0
            close_details = []
            
            # 🔥 ปิดไม้เป็นกลุ่ม (ใช้ close_positions_group)
            try:
                close_result = self.order_manager.close_positions_group(positions_to_close, "Simple Position Manager")
                
                if close_result.success:
                    successful_closes = len(positions_to_close)
                    # ดึง profit จาก close_result
                    total_profit = getattr(close_result, 'total_profit', 0.0)
                    
                    # ถ้าไม่มี profit หรือเป็น 0 ให้ใช้ราคาปิดจริงจาก MT5
                    if total_profit == 0.0:
                        logger.info(f"📊 No profit data from close_result, calculating from actual close prices...")
                        
                    # 📊 แสดงรายละเอียดแต่ละไม้ที่ปิด (ใช้ actual profit หรือคำนวณจริง)
                    logger.info(f"✅ GROUP CLOSE SUCCESS:")
                    actual_total_profit = 0.0
                    
                    for i, position in enumerate(positions_to_close):
                        pos_type = position.type.upper() if isinstance(position.type, str) else ("BUY" if position.type == 0 else "SELL")
                        symbol = "├─" if i < len(positions_to_close) - 1 else "└─"
                        
                        # แสดงรายละเอียด position โดยไม่แสดง individual profit (เพราะไม่แม่นยำ)
                        logger.info(f"  {symbol} #{position.ticket} {pos_type} {position.volume:.2f}lot @ {position.price_open:.2f}")
                        
                        actual_total_profit += 0.0  # จะใช้ total_profit จาก close_result
                        
                        close_details.append({
                            'ticket': position.ticket,
                            'profit': 0.0,  # ไม่แสดง individual profit
                            'success': True
                        })
                    
                    # ใช้ total_profit จาก close_result (ถ้ามี) หรือคำนวณใหม่
                    # actual_total_profit จะเป็น 0 เสมอ ให้ใช้ total_profit เดิม
                    
                    logger.info(f"📊 TOTAL RESULT: {successful_closes} positions closed, ${total_profit:.2f} total profit")
                else:
                    # ถ้า group close ไม่สำเร็จ ลองปิดทีละตัว
                    logger.warning("Group close failed, trying individual closes...")
                    for position in positions_to_close:
                        try:
                            # ใช้ MT5 direct close
                            individual_result = self.mt5.close_position_direct(position.ticket)
                            if individual_result and hasattr(individual_result, 'success') and individual_result.success:
                                successful_closes += 1
                                # ดึง profit จาก result
                                if hasattr(individual_result, 'profit'):
                                    profit = individual_result.profit
                                elif hasattr(individual_result, 'total_profit'):
                                    profit = individual_result.total_profit
                                else:
                                    profit = 0.0
                                    
                                total_profit += profit
                                close_details.append({
                                    'ticket': position.ticket,
                                    'profit': profit,
                                    'success': True
                                })
                                
                                # แสดงรายละเอียดแต่ละไม้ที่ปิดสำเร็จ
                                pos_type = position.type.upper() if isinstance(position.type, str) else ("BUY" if position.type == 0 else "SELL")
                                logger.info(f"✅ #{position.ticket} {pos_type} {position.volume:.2f}lot @ {position.price_open:.2f} → ${profit:.2f} profit")
                            else:
                                close_details.append({
                                    'ticket': position.ticket,
                                    'profit': 0.0,
                                    'success': False,
                                    'error': 'MT5 close failed'
                                })
                        except Exception as e:
                            logger.error(f"Error closing position #{position.ticket}: {e}")
                            close_details.append({
                                'ticket': position.ticket,
                                'profit': 0.0,
                                'success': False,
                                'error': str(e)
                            })
                    
                    # สรุปผลรวมสำหรับ individual closes
                    if successful_closes > 0:
                        logger.info(f"📊 INDIVIDUAL CLOSE SUMMARY: {successful_closes} positions closed, ${total_profit:.2f} total profit")
                            
            except Exception as e:
                logger.error(f"Error in group close: {e}")
                close_details.append({
                    'ticket': 'GROUP',
                    'profit': 0.0,
                    'success': False,
                    'error': str(e)
                })
            
            # 📊 สรุปผลลัพธ์
            execution_time = (datetime.now() - start_time).total_seconds()
            
            if successful_closes > 0:
                self.total_closures += 1
                self.total_positions_closed += successful_closes
                self.total_profit_realized += total_profit
                
                return {
                    'success': True,
                    'message': f'Closed {successful_closes}/{len(positions_to_close)} positions successfully',
                    'closed_count': successful_closes,
                    'total_profit': total_profit,
                    'execution_time': execution_time,
                    'details': close_details
                }
            else:
                return {
                    'success': False,
                    'message': 'No positions were successfully closed',
                    'closed_count': 0,
                    'total_profit': 0.0,
                    'execution_time': execution_time,
                    'details': close_details
                }
                
        except Exception as e:
            logger.error(f"Error executing position closure: {e}")
            return {
                'success': False,
                'message': f'Execution error: {e}',
                'closed_count': 0,
                'total_profit': 0.0
            }
    
    def _analyze_all_positions(self, positions: List[Any], current_price: float) -> List[Dict[str, Any]]:
        """🔍 วิเคราะห์ทุกไม้ในพอร์ต"""
        analyzed = []
        
        # 📊 ดึงข้อมูลสเปรดจาก MT5 (เงียบๆ)
        spread = self._get_current_spread()
        
        for pos in positions:
            try:
                # คำนวณ P&L ปัจจุบัน รวมสเปรด
                if hasattr(pos, 'type') and hasattr(pos, 'price_open') and hasattr(pos, 'volume'):
                    pos_type = pos.type.upper() if isinstance(pos.type, str) else ("BUY" if pos.type == 0 else "SELL")
                    
                    # ใช้ profit จาก position โดยตรง (แม่นยำที่สุด)
                    if hasattr(pos, 'profit'):
                        pnl = pos.profit
                    else:
                        # Fallback: คำนวณ P&L พื้นฐาน (ถ้าไม่มี profit field)
                        if pos_type == "BUY":
                            # BUY: ปิดที่ bid price 
                            close_price = current_price - (spread / 100)  # spread points -> price
                            pnl_before_costs = (close_price - pos.price_open) * pos.volume * 100
                        else:  # SELL
                            # SELL: ปิดที่ ask price
                            close_price = current_price + (spread / 100)
                            pnl_before_costs = (pos.price_open - close_price) * pos.volume * 100
                        
                        # หักค่าธรรมเนียม
                        commission_cost = pos.volume * 0.5
                        pnl = pnl_before_costs - commission_cost
                    
                    # คำนวณระยะห่างจากราคาปัจจุบัน
                    distance_pips = abs(current_price - pos.price_open) * 100
                    
                    # คำนวณอายุของไม้ (ถ้ามีข้อมูล)
                    age_minutes = 0
                    if hasattr(pos, 'time'):
                        try:
                            pos_time = datetime.fromtimestamp(pos.time)
                            age_minutes = (datetime.now() - pos_time).total_seconds() / 60
                        except:
                            age_minutes = 0
                    
                    analyzed.append({
                        'position': pos,
                        'ticket': pos.ticket,
                        'type': pos_type,
                        'volume': pos.volume,
                        'price_open': pos.price_open,
                        'current_pnl': pnl,
                        'distance_pips': distance_pips,
                        'age_minutes': age_minutes,
                        'is_profit': pnl > 0,
                        'is_loss': pnl < 0
                    })
                    
                    # Skip individual position logging for speed
                    
            except Exception as e:
                logger.warning(f"Error analyzing position {pos.ticket}: {e}")
                continue
        
        return analyzed
    
    def _find_best_closing_combination(self, analyzed_positions: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """🎯 หาการจับคู่ที่ดีที่สุดสำหรับการปิด"""
        try:
            best_combination = None
            best_score = -999999
            combinations_tested = 0
            max_combinations = 500  # ลดจำนวนการทดสอบเพื่อความเร็ว
            
            # แยกไม้กำไรและไม้เสีย (เงียบๆ)
            profit_positions = [p for p in analyzed_positions if p['is_profit']]
            loss_positions = [p for p in analyzed_positions if p['is_loss']]
            
            # 🎯 ลองทุกแบบการจับคู่ (2 ไม้ ถึง max_positions_per_round ไม้)
            max_size = min(len(analyzed_positions) + 1, self.max_positions_per_round + 1, 5)  # จำกัดไม่เกิน 4 ไม้
            
            for size in range(self.min_positions_to_close, max_size):
                
                # ใช้ simple iteration แทน combinations เพื่อป้องกัน memory issue
                try:
                    from itertools import combinations
                    combination_iter = combinations(analyzed_positions, size)
                except ImportError:
                    logger.error("🚨 itertools.combinations not available, using fallback")
                    continue
                
                # ลองทุกการจับคู่ที่เป็นไปได้
                for combination in combination_iter:
                    combinations_tested += 1
                    
                    # จำกัดจำนวนการทดสอบ (เงียบๆ)
                    if combinations_tested > max_combinations:
                        break
                    
                    # คำนวณผลรวม
                    total_pnl = sum(p['current_pnl'] for p in combination)
                    profit_count = sum(1 for p in combination if p['is_profit'])
                    loss_count = sum(1 for p in combination if p['is_loss'])
                    
                    # 🚫 กฎที่ห้าม: ไม่ปิดไม้เดี่ยวที่เก็บแต่กำไร
                    if len(combination) == 1 and profit_count == 1:
                        continue
                    
                    # 🚫 ไม่ปิดแต่ไม้กำไรอย่างเดียว (ต้องมีไม้เสียด้วย)
                    if loss_count == 0 and profit_count > 1:
                        continue
                    
                    # 🚫 ไม่ปิดถ้าติดลบเลย (เข้มงวดมาก)
                    if total_pnl <= 0:  # เปลี่ยนจาก < 0 เป็น <= 0 (ไม่ยอมแม้แต่ $0)
                        continue
                    
                    # 📊 คำนวณคะแนน
                    score = self._calculate_combination_score(combination, total_pnl, profit_count, loss_count)
                    
                    if score > best_score:
                        best_score = score
                        best_combination = {
                            'positions': [p['position'] for p in combination],
                            'total_pnl': total_pnl,
                            'profit_count': profit_count,
                            'loss_count': loss_count,
                            'score': score,
                            'type': self._get_combination_type(profit_count, loss_count),
                            'reason': self._get_combination_reason(total_pnl, profit_count, loss_count, len(combination))
                        }
                
                # Break ออกจาก outer loop ถ้าถึงขีดจำกัด
                if combinations_tested > max_combinations:
                    break
            
            # ไม่ log จำนวนการทดสอบเพื่อความเร็ว
            return best_combination
            
        except Exception as e:
            logger.error(f"Error finding best combination: {e}")
            return None
    
    def _calculate_combination_score(self, combination: Tuple, total_pnl: float, profit_count: int, loss_count: int) -> float:
        """📊 คำนวณคะแนนของการจับคู่"""
        try:
            score = 0.0
            
            # 1. คะแนนจากกำไร (สำคัญที่สุด)
            if total_pnl > 0:
                score += total_pnl * 100  # กำไร $1 = 100 คะแนน
            else:
                score += total_pnl * 50   # ขาดทุน $1 = -50 คะแนน
            
            # 2. คะแนนจากการลดจำนวนไม้
            position_reduction_score = len(combination) * 10  # ลดไม้ 1 ตัว = 10 คะแนน
            score += position_reduction_score
            
            # 3. คะแนนพิเศษสำหรับการผสมไม้กำไรกับไม้เสีย
            if profit_count > 0 and loss_count > 0:
                score += 50  # โบนัสสำหรับการจับคู่ที่สมดุล
            
            # 4. คะแนนจากอายุของไม้เสีย (ยิ่งเก่ายิ่งดี)
            for p in combination:
                if p['is_loss'] and p['age_minutes'] > 60:  # ไม้เสียเก่ากว่า 1 ชม
                    score += min(p['age_minutes'] / 10, 20)  # สูงสุด 20 คะแนน
            
            # 5. คะแนนจากระยะห่างของไม้เสีย (ยิ่งไกลยิ่งควรปิด)
            for p in combination:
                if p['is_loss'] and p['distance_pips'] > 50:  # ไม้เสียห่าง > 50 pips
                    score += min(p['distance_pips'] / 10, 30)  # สูงสุด 30 คะแนน
            
            return score
            
        except Exception as e:
            logger.error(f"Error calculating combination score: {e}")
            return 0.0
    
    def _get_combination_type(self, profit_count: int, loss_count: int) -> str:
        """🏷️ ระบุประเภทของการจับคู่"""
        if profit_count > 0 and loss_count > 0:
            return "MIXED"  # ผสมกำไรกับขาดทุน
        elif profit_count > 0:
            return "PROFIT_ONLY"  # กำไรอย่างเดียว
        else:
            return "LOSS_ONLY"  # ขาดทุนอย่างเดียว
    
    def _get_combination_reason(self, total_pnl: float, profit_count: int, loss_count: int, total_count: int) -> str:
        """📝 อธิบายเหตุผลการปิด"""
        if total_pnl > 2.0:
            return f"Excellent profit: ${total_pnl:.2f} from {total_count} positions (after spread & commission)"
        elif total_pnl > 0.5:
            return f"Good profit: ${total_pnl:.2f} from {total_count} positions (after spread & commission)"
        elif total_pnl > 0:
            return f"Small profit: ${total_pnl:.2f} from {total_count} positions (after spread & commission)"
        else:
            return f"REJECTED: Would lose ${abs(total_pnl):.2f} - only profitable closes allowed"
    
    def get_statistics(self) -> Dict[str, Any]:
        """📊 ดึงสถิติการทำงาน"""
        return {
            'total_closures': self.total_closures,
            'total_positions_closed': self.total_positions_closed,
            'total_profit_realized': self.total_profit_realized,
            'avg_positions_per_closure': self.total_positions_closed / max(self.total_closures, 1),
            'avg_profit_per_closure': self.total_profit_realized / max(self.total_closures, 1)
        }
    
    def configure_settings(self, **settings):
        """⚙️ ปรับแต่งการตั้งค่า"""
        if 'max_acceptable_loss' in settings:
            self.max_acceptable_loss = settings['max_acceptable_loss']
        if 'min_positions_to_close' in settings:
            self.min_positions_to_close = settings['min_positions_to_close']
        if 'max_positions_per_round' in settings:
            self.max_positions_per_round = settings['max_positions_per_round']
        
        logger.info("⚙️ Simple Position Manager settings updated")
    
    def _get_current_spread(self) -> float:
        """📊 ดึงข้อมูลสเปรดปัจจุบัน"""
        try:
            # ลองดึงจาก MT5 symbol info
            if hasattr(self.mt5, 'get_symbol_info'):
                symbol_info = self.mt5.get_symbol_info('XAUUSD.v')  # หรือ symbol ที่ใช้
                if symbol_info and hasattr(symbol_info, 'spread'):
                    return float(symbol_info.spread)
            
            # Fallback: ใช้ค่าเฉลี่ยสำหรับ Gold
            return 45.0  # 45 points สำหรับ XAUUSD
            
        except Exception as e:
            logger.warning(f"Error getting spread: {e}, using default 45 points")
            return 45.0
    
    def _get_current_price(self) -> float:
        """ดึงราคาปัจจุบันจาก MT5"""
        try:
            tick = self.mt5.symbol_info_tick("XAUUSD.v")
            if tick:
                return (tick.bid + tick.ask) / 2
            return 3550.0  # default fallback
        except Exception as e:
            logger.warning(f"Error getting current price: {e}, using default 3550.0")
            return 3550.0
    
    def _analyze_single_position(self, pos: Any, current_price: float) -> Dict[str, Any]:
        """วิเคราะห์ position เดี่ยว"""
        try:
            # ใช้ profit จาก position โดยตรง (แม่นยำที่สุด)
            if hasattr(pos, 'profit'):
                pnl = pos.profit
            else:
                # Fallback: คำนวณ P&L เอง
                pos_type = pos.type.upper() if isinstance(pos.type, str) else ("BUY" if pos.type == 0 else "SELL")
                spread = self._get_current_spread()
                
                if pos_type == "BUY":
                    close_price = current_price - (spread / 100)
                    pnl_before_costs = (close_price - pos.price_open) * pos.volume * 100
                else:  # SELL
                    close_price = current_price + (spread / 100)
                    pnl_before_costs = (pos.price_open - close_price) * pos.volume * 100
                
                # หักค่าธรรมเนียม
                commission_cost = pos.volume * 0.5
                pnl = pnl_before_costs - commission_cost
            
            return {
                'ticket': pos.ticket,
                'current_pnl': pnl,
                'is_profit': pnl > 0,
                'is_loss': pnl < 0
            }
        except Exception as e:
            logger.warning(f"Error analyzing position {pos.ticket}: {e}")
            return {'ticket': pos.ticket, 'current_pnl': 0.0, 'is_profit': False, 'is_loss': False}
    
    def _get_actual_close_profit(self, ticket: int) -> float:
        """ดึง profit จริงจากประวัติการปิด MT5"""
        try:
            # ดึงประวัติ deals ของ ticket นี้
            from datetime import datetime, timedelta
            end_time = datetime.now()
            start_time = end_time - timedelta(minutes=5)  # ย้อนหลัง 5 นาที
            
            deals = self.mt5.history_deals_get(start_time, end_time)
            if deals:
                for deal in deals:
                    # หา deal ที่ปิด position นี้
                    if hasattr(deal, 'position_id') and deal.position_id == ticket:
                        if hasattr(deal, 'profit'):
                            return float(deal.profit)
            
            return 0.0
        except Exception as e:
            logger.warning(f"Error getting actual close profit for {ticket}: {e}")
            return 0.0
