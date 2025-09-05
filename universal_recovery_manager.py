"""
🚀 Universal Recovery + Smart Balance System
===============================================

ระบบกู้คืนและสร้างสมดุลพอร์ตแบบครบวงจร
- BUY + SELL Drag Recovery
- Multi-Position Smart Combinations  
- Balance-Aware Exit Logic
- Protected Position System
- Enhanced Tracking & Persistence

Author: Huakuy Trading System
Version: 1.0.0
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import itertools
import os

logger = logging.getLogger(__name__)

@dataclass
class RecoveryPair:
    """Recovery Pair Data Structure"""
    primary_ticket: int
    recovery_ticket: int
    pair_type: str  # 'buy_drag', 'sell_drag'
    created_time: datetime
    target_profit: float
    status: str  # 'active', 'completed', 'failed'
    
@dataclass
class BalancePosition:
    """Balance Position Data Structure"""
    ticket: int
    direction: str  # 'BUY', 'SELL'
    purpose: str   # 'balance', 'force_counter', 'zone_defense'
    created_time: datetime
    target_balance: float
    
@dataclass
class RecoveryGroup:
    """Recovery Group Data Structure"""
    group_id: str
    positions: List[int]  # ticket numbers
    group_type: str  # 'recovery', 'balance', 'mixed'
    target_profit: float
    created_time: datetime
    priority: int  # 1=highest, 5=lowest

class UniversalRecoveryManager:
    """
    🎯 Universal Recovery + Smart Balance Manager
    
    หน้าที่หลัก:
    1. BUY/SELL Drag Recovery - กู้คืนไม้โดนลาก
    2. Multi-Position Combinations - รวมไม้หลายตัวปิดกำไร
    3. Balance-Aware Logic - รักษาสมดุลพอร์ต
    4. Protected Positions - ป้องกันการปิดผิด
    5. Enhanced Tracking - ติดตามแม่นยำ
    """
    
    def __init__(self, mt5_manager=None):
        self.mt5_manager = mt5_manager
        
        # 🔧 Core Data Structures
        self.recovery_pairs: Dict[str, RecoveryPair] = {}
        self.balance_positions: Dict[int, BalancePosition] = {}
        self.recovery_groups: Dict[str, RecoveryGroup] = {}
        
        # 🎯 Configuration
        self.config = {
            # Drag Detection
            'drag_threshold_pips': 20,  # ถือว่าโดนลากเมื่อขาดทุน > 20 pips
            'drag_age_hours': 2,        # อายุขั้นต่ำก่อนถือว่าโดนลาก
            
            # Recovery Creation
            'recovery_distance_pips': 15,  # ระยะห่าง Recovery Position
            'max_recovery_per_position': 2,  # สูงสุด 2 Recovery ต่อไม้
            
            # Balance Management
            'imbalance_threshold': 70.0,   # % ที่ถือว่าเสียสมดุล
            'force_counter_threshold': 85.0,  # % ที่บังคับ Counter-trade
            
            # Exit Logic
            'min_profit_usd': 0.50,      # กำไรขั้นต่ำ
            'max_positions_per_combo': 8,  # สูงสุด 8 ไม้ต่อการปิด
            'balance_bonus_score': 30,    # โบนัสคะแนนสมดุล
            
            # Protection
            'protect_recovery_pairs': True,   # ป้องกัน Recovery Pairs
            'protect_balance_positions': True, # ป้องกัน Balance Positions
            'min_group_size': 2,             # ขนาดกลุ่มขั้นต่ำ
        }
        
        # 📁 File Paths
        self.data_file = "universal_recovery_data.json"
        self.backup_file = "universal_recovery_backup.json"
        
        # Load existing data
        self.load_data()
        
        logger.info("🚀 Universal Recovery Manager initialized")
        
    # ==========================================
    # 📊 DRAG DETECTION & RECOVERY CREATION
    # ==========================================
    
    def analyze_dragged_positions(self, positions: List[Any], current_price: float) -> Dict:
        """
        🔍 วิเคราะห์ไม้ที่โดนลากและสร้าง Recovery Plan
        """
        try:
            dragged_positions = []
            recovery_opportunities = []
            
            for position in positions:
                drag_analysis = self._analyze_single_position_drag(position, current_price)
                
                if drag_analysis['is_dragged']:
                    dragged_positions.append({
                        'position': position,
                        'drag_info': drag_analysis
                    })
                    
                    # สร้าง Recovery Plan
                    recovery_plan = self._create_recovery_plan(position, drag_analysis, current_price)
                    if recovery_plan:
                        recovery_opportunities.append(recovery_plan)
            
            return {
                'dragged_count': len(dragged_positions),
                'dragged_positions': dragged_positions,
                'recovery_opportunities': recovery_opportunities,
                'total_drag_loss': sum(pos['drag_info']['loss_pips'] for pos in dragged_positions)
            }
            
        except Exception as e:
            logger.error(f"🚨 Error analyzing dragged positions: {e}")
            return {'dragged_count': 0, 'dragged_positions': [], 'recovery_opportunities': []}
    
    def _analyze_single_position_drag(self, position: Any, current_price: float) -> Dict:
        """วิเคราะห์ไม้เดี่ยวว่าโดนลากไหม"""
        
        # คำนวณ Loss Pips
        if position.type == 0:  # BUY
            loss_pips = (position.price_open - current_price) * 10000
        else:  # SELL
            loss_pips = (current_price - position.price_open) * 10000
            
        # เช็คอายุไม้
        position_age = datetime.now() - datetime.fromtimestamp(position.time)
        age_hours = position_age.total_seconds() / 3600
        
        # เช็คเงื่อนไข Drag
        is_dragged = (
            loss_pips > self.config['drag_threshold_pips'] and
            age_hours > self.config['drag_age_hours'] and
            position.profit < 0
        )
        
        return {
            'is_dragged': is_dragged,
            'loss_pips': loss_pips,
            'age_hours': age_hours,
            'profit_usd': position.profit,
            'drag_severity': min(loss_pips / 50.0, 5.0)  # 1-5 scale
        }
    
    def _create_recovery_plan(self, dragged_position: Any, drag_info: Dict, current_price: float) -> Optional[Dict]:
        """สร้างแผน Recovery สำหรับไม้โดนลาก"""
        
        try:
            # เช็คว่ามี Recovery อยู่แล้วไหม
            existing_recovery = self._find_existing_recovery(dragged_position.ticket)
            if existing_recovery and len(existing_recovery) >= self.config['max_recovery_per_position']:
                return None
            
            # คำนวณ Recovery Position
            recovery_distance = self.config['recovery_distance_pips'] / 10000
            
            if dragged_position.type == 0:  # BUY โดนลาก
                # สร้าง BUY ต่ำกว่า (Lower BUY)
                recovery_price = current_price - recovery_distance
                recovery_type = 'BUY'
                pair_type = 'buy_drag'
                
            else:  # SELL โดนลาก  
                # สร้าง SELL สูงกว่า (Higher SELL)
                recovery_price = current_price + recovery_distance
                recovery_type = 'SELL'
                pair_type = 'sell_drag'
            
            # คำนวณ Lot Size (เท่ากับไม้เดิมหรือปรับตาม Risk)
            recovery_lot = dragged_position.volume
            
            # คำนวณเป้าหมายกำไร
            target_profit = abs(drag_info['profit_usd']) * 0.1  # กำไร 10% ของขาดทุน
            
            recovery_plan = {
                'dragged_ticket': dragged_position.ticket,
                'recovery_type': recovery_type,
                'recovery_price': recovery_price,
                'recovery_lot': recovery_lot,
                'pair_type': pair_type,
                'target_profit': target_profit,
                'comment': f"REC_{recovery_type}_{dragged_position.ticket}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                'priority': min(int(drag_info['drag_severity']), 5)
            }
            
            return recovery_plan
            
        except Exception as e:
            logger.error(f"🚨 Error creating recovery plan: {e}")
            return None
    
    # ==========================================
    # 🎯 MULTI-POSITION COMBINATIONS
    # ==========================================
    
    def find_smart_combinations(self, positions: List[Any], current_price: float, balance_analysis: Dict) -> List[Dict]:
        """
        🧠 หา Smart Combinations ที่ยืดหยุ่นและสมดุล
        """
        try:
            all_combinations = []
            
            # 1. Recovery Pair Combinations
            recovery_combos = self._find_recovery_combinations(positions)
            all_combinations.extend(recovery_combos)
            
            # 2. Multi-Position Profit Combinations
            profit_combos = self._find_multi_profit_combinations(positions, current_price)
            all_combinations.extend(profit_combos)
            
            # 3. Balance-Priority Combinations
            balance_combos = self._find_balance_combinations(positions, balance_analysis)
            all_combinations.extend(balance_combos)
            
            # 4. Mixed Recovery + Profit Combinations
            mixed_combos = self._find_mixed_combinations(positions, current_price)
            all_combinations.extend(mixed_combos)
            
            # 5. Score และ Rank ทุก Combinations
            scored_combinations = []
            for combo in all_combinations:
                score = self._calculate_combination_score(combo, balance_analysis, current_price)
                combo['score'] = score
                scored_combinations.append(combo)
            
            # Sort by score (สูงสุดก่อน)
            scored_combinations.sort(key=lambda x: x['score'], reverse=True)
            
            # Filter เฉพาะที่ผ่านเงื่อนไข
            valid_combinations = self._filter_valid_combinations(scored_combinations)
            
            logger.info(f"🎯 Found {len(valid_combinations)} valid combinations from {len(all_combinations)} total")
            
            return valid_combinations[:10]  # Return top 10
            
        except Exception as e:
            logger.error(f"🚨 Error finding smart combinations: {e}")
            return []
    
    def _find_recovery_combinations(self, positions: List[Any]) -> List[Dict]:
        """หา Recovery Pair Combinations"""
        
        combinations = []
        
        # หา Recovery Pairs ที่พร้อมปิด
        for pair_key, pair_info in self.recovery_pairs.items():
            if pair_info.status != 'active':
                continue
                
            # หาไม้ทั้งคู่
            primary_pos = self._find_position_by_ticket(positions, pair_info.primary_ticket)
            recovery_pos = self._find_position_by_ticket(positions, pair_info.recovery_ticket)
            
            if primary_pos and recovery_pos:
                total_profit = primary_pos.profit + recovery_pos.profit
                
                if total_profit > 0:  # มีกำไรรวม
                    combinations.append({
                        'type': 'recovery_pair',
                        'positions': [primary_pos, recovery_pos],
                        'total_profit': total_profit,
                        'pair_type': pair_info.pair_type,
                        'priority': 5  # สูงสุด
                    })
        
        return combinations
    
    def _find_multi_profit_combinations(self, positions: List[Any], current_price: float) -> List[Dict]:
        """หา Multi-Position Profit Combinations"""
        
        combinations = []
        profitable_positions = [pos for pos in positions if pos.profit > 0]
        losing_positions = [pos for pos in positions if pos.profit < 0]
        
        if not profitable_positions or not losing_positions:
            return combinations
        
        # สร้าง combinations ขนาด 2-8 ไม้
        for combo_size in range(2, min(self.config['max_positions_per_combo'] + 1, len(positions) + 1)):
            
            # ลองทุก combination
            for combo_positions in itertools.combinations(positions, combo_size):
                total_profit = sum(pos.profit for pos in combo_positions)
                
                if total_profit >= self.config['min_profit_usd']:
                    
                    # ต้องมีทั้งไม้กำไรและขาดทุน
                    profit_count = sum(1 for pos in combo_positions if pos.profit > 0)
                    loss_count = sum(1 for pos in combo_positions if pos.profit < 0)
                    
                    if profit_count > 0 and loss_count > 0:
                        combinations.append({
                            'type': 'multi_profit',
                            'positions': list(combo_positions),
                            'total_profit': total_profit,
                            'profit_positions': profit_count,
                            'loss_positions': loss_count,
                            'priority': 3
                        })
        
        return combinations
    
    def _find_balance_combinations(self, positions: List[Any], balance_analysis: Dict) -> List[Dict]:
        """หา Balance-Priority Combinations"""
        
        combinations = []
        
        if balance_analysis.get('imbalance_percentage', 0) < self.config['imbalance_threshold']:
            return combinations  # ไม่เสียสมดุล
        
        buy_positions = [pos for pos in positions if pos.type == 0]
        sell_positions = [pos for pos in positions if pos.type == 1]
        
        imbalance_side = balance_analysis.get('imbalance_side', '')
        
        # หา combination ที่ช่วยแก้สมดุล
        if imbalance_side == 'BUY':
            # ต้องปิด BUY มากกว่า SELL
            target_positions = buy_positions
            balance_positions = sell_positions
            
        else:  # SELL
            # ต้องปิด SELL มากกว่า BUY  
            target_positions = sell_positions
            balance_positions = buy_positions
        
        # สร้าง combinations ที่เน้นแก้สมดุล
        for target_count in range(2, min(6, len(target_positions) + 1)):
            for balance_count in range(1, min(target_count, len(balance_positions) + 1)):
                
                for target_combo in itertools.combinations(target_positions, target_count):
                    for balance_combo in itertools.combinations(balance_positions, balance_count):
                        
                        all_positions = list(target_combo) + list(balance_combo)
                        total_profit = sum(pos.profit for pos in all_positions)
                        
                        if total_profit >= self.config['min_profit_usd']:
                            combinations.append({
                                'type': 'balance_priority',
                                'positions': all_positions,
                                'total_profit': total_profit,
                                'balance_improvement': target_count - balance_count,
                                'priority': 4
                            })
        
        return combinations
    
    def _find_mixed_combinations(self, positions: List[Any], current_price: float) -> List[Dict]:
        """หา Mixed Recovery + Normal Combinations"""
        
        combinations = []
        
        # หาไม้ที่เป็น Recovery
        recovery_positions = []
        normal_positions = []
        
        for position in positions:
            if self._is_recovery_position(position):
                recovery_positions.append(position)
            else:
                normal_positions.append(position)
        
        if not recovery_positions or not normal_positions:
            return combinations
        
        # สร้าง mixed combinations
        for recovery_count in range(1, min(4, len(recovery_positions) + 1)):
            for normal_count in range(1, min(5, len(normal_positions) + 1)):
                
                if recovery_count + normal_count > self.config['max_positions_per_combo']:
                    continue
                
                for recovery_combo in itertools.combinations(recovery_positions, recovery_count):
                    for normal_combo in itertools.combinations(normal_positions, normal_count):
                        
                        all_positions = list(recovery_combo) + list(normal_combo)
                        total_profit = sum(pos.profit for pos in all_positions)
                        
                        if total_profit >= self.config['min_profit_usd']:
                            combinations.append({
                                'type': 'mixed_recovery',
                                'positions': all_positions,
                                'total_profit': total_profit,
                                'recovery_count': recovery_count,
                                'normal_count': normal_count,
                                'priority': 3
                            })
        
        return combinations
    
    # ==========================================
    # 📊 COMBINATION SCORING & VALIDATION
    # ==========================================
    
    def _calculate_combination_score(self, combination: Dict, balance_analysis: Dict, current_price: float) -> float:
        """
        🎯 คำนวณคะแนน Combination แบบครบวงจร
        """
        
        score = 0.0
        positions = combination['positions']
        
        # 1. 💰 Profit Score (Base Score)
        profit_score = combination['total_profit'] * 10
        score += profit_score
        
        # 2. 🎯 Priority Score
        priority_score = combination.get('priority', 1) * 20
        score += priority_score
        
        # 3. 🔄 Recovery Score
        recovery_positions = [pos for pos in positions if self._is_recovery_position(pos)]
        recovery_score = len(recovery_positions) * 25
        score += recovery_score
        
        # 4. ⚖️ Balance Score
        buy_count = len([pos for pos in positions if pos.type == 0])
        sell_count = len([pos for pos in positions if pos.type == 1])
        
        imbalance_side = balance_analysis.get('imbalance_side', '')
        imbalance_pct = balance_analysis.get('imbalance_percentage', 0)
        
        if imbalance_pct > self.config['imbalance_threshold']:
            if imbalance_side == 'BUY' and buy_count > sell_count:
                balance_score = (buy_count - sell_count) * self.config['balance_bonus_score']
                score += balance_score
            elif imbalance_side == 'SELL' and sell_count > buy_count:
                balance_score = (sell_count - buy_count) * self.config['balance_bonus_score']
                score += balance_score
        
        # 5. 🗑️ Position Reduction Score
        reduction_score = len(positions) * 5
        score += reduction_score
        
        # 6. 📊 Loss Recovery Score
        losing_positions = [pos for pos in positions if pos.profit < 0]
        loss_recovery_score = len(losing_positions) * 15
        score += loss_recovery_score
        
        # 7. 🎲 Diversity Score (หลากหลาย Lot Size)
        lot_sizes = [pos.volume for pos in positions]
        unique_lots = len(set(lot_sizes))
        diversity_score = unique_lots * 3
        score += diversity_score
        
        # 8. ⏰ Age Score (ไม้เก่าได้คะแนนเพิ่ม)
        current_time = datetime.now()
        age_scores = []
        for pos in positions:
            position_time = datetime.fromtimestamp(pos.time)
            age_hours = (current_time - position_time).total_seconds() / 3600
            age_scores.append(min(age_hours / 24.0, 3.0))  # สูงสุด 3 คะแนน
        
        age_score = sum(age_scores) * 2
        score += age_score
        
        # 9. 🎯 Type Bonus
        combo_type = combination.get('type', '')
        type_bonuses = {
            'recovery_pair': 50,
            'balance_priority': 40,
            'mixed_recovery': 35,
            'multi_profit': 25
        }
        type_bonus = type_bonuses.get(combo_type, 0)
        score += type_bonus
        
        # 10. 🚫 Penalty Factors
        
        # ปรับลดถ้ากำไรน้อย
        if combination['total_profit'] < 1.0:
            score *= 0.8
        
        # ปรับลดถ้าไม้เยอะเกินไป
        if len(positions) > 6:
            score *= 0.9
        
        # ปรับลดถ้าไม่มีไม้ขาดทุน (ไม่ช่วยกู้คืน)
        if not losing_positions:
            score *= 0.7
        
        return round(score, 2)
    
    def _filter_valid_combinations(self, combinations: List[Dict]) -> List[Dict]:
        """กรอง Combinations ที่ผ่านเงื่อนไข"""
        
        valid = []
        
        for combo in combinations:
            if self._is_valid_combination(combo):
                valid.append(combo)
        
        return valid
    
    def _is_valid_combination(self, combination: Dict) -> bool:
        """เช็คว่า Combination นี้ Valid ไหม"""
        
        positions = combination['positions']
        
        # 1. เช็คกำไรขั้นต่ำ
        if combination['total_profit'] < self.config['min_profit_usd']:
            return False
        
        # 2. เช็คจำนวนไม้
        if len(positions) < 2 or len(positions) > self.config['max_positions_per_combo']:
            return False
        
        # 3. เช็ค Protected Positions
        if self.config['protect_recovery_pairs']:
            if self._breaks_recovery_pairs(positions):
                return False
        
        if self.config['protect_balance_positions']:
            if self._breaks_balance_strategy(positions):
                return False
        
        # 4. ต้องมีไม้ขาดทุนอย่างน้อย 1 ไม้
        losing_positions = [pos for pos in positions if pos.profit < 0]
        if not losing_positions:
            return False
        
        # 5. เช็ค Lot Size Compatibility
        if not self._is_lot_compatible(positions):
            return False
        
        return True
    
    # ==========================================
    # 🛡️ PROTECTION & VALIDATION
    # ==========================================
    
    def _is_recovery_position(self, position: Any) -> bool:
        """เช็คว่าไม้นี้เป็น Recovery Position ไหม"""
        
        comment = getattr(position, 'comment', '')
        
        # เช็คจาก Comment
        if any(prefix in comment for prefix in ['REC_BUY_', 'REC_SELL_', 'BAL_', 'GRP_']):
            return True
        
        # เช็คจาก Recovery Pairs
        for pair_info in self.recovery_pairs.values():
            if position.ticket in [pair_info.primary_ticket, pair_info.recovery_ticket]:
                return True
        
        # เช็คจาก Balance Positions
        if position.ticket in self.balance_positions:
            return True
        
        return False
    
    def _breaks_recovery_pairs(self, positions: List[Any]) -> bool:
        """เช็คว่าการปิดไม้เหล่านี้จะทำลาย Recovery Pairs ไหม"""
        
        position_tickets = [pos.ticket for pos in positions]
        
        for pair_info in self.recovery_pairs.values():
            if pair_info.status != 'active':
                continue
            
            # เช็คว่ามีการปิดเฉพาะไม้เดี่ยวใน Pair ไหม
            primary_in = pair_info.primary_ticket in position_tickets
            recovery_in = pair_info.recovery_ticket in position_tickets
            
            if primary_in != recovery_in:  # ปิดแค่ไม้เดียว
                return True
        
        return False
    
    def _breaks_balance_strategy(self, positions: List[Any]) -> bool:
        """เช็คว่าการปิดจะทำลาย Balance Strategy ไหม"""
        
        # เช็คว่ามี Balance Position ที่สำคัญไหม
        for position in positions:
            if position.ticket in self.balance_positions:
                balance_info = self.balance_positions[position.ticket]
                
                # ถ้าเป็น Force Counter หรือ Zone Defense ห้ามปิดเดี่ยว
                if balance_info.purpose in ['force_counter', 'zone_defense']:
                    # ต้องมีไม้อื่นในทิศตรงข้ามด้วย
                    opposite_direction = 'SELL' if balance_info.direction == 'BUY' else 'BUY'
                    
                    has_opposite = any(
                        (pos.type == 0 and opposite_direction == 'BUY') or
                        (pos.type == 1 and opposite_direction == 'SELL')
                        for pos in positions if pos.ticket != position.ticket
                    )
                    
                    if not has_opposite:
                        return True
        
        return False
    
    def _is_lot_compatible(self, positions: List[Any]) -> bool:
        """เช็ค Lot Size Compatibility"""
        
        # เช็คว่า Lot Size ไม่แปลกเกินไป
        lot_sizes = [pos.volume for pos in positions]
        
        # ห้าม Lot เล็กเกินไป
        if any(lot < 0.01 for lot in lot_sizes):
            return False
        
        # ห้าม Lot ใหญ่เกินไป (เทียบกับเฉลี่ย)
        avg_lot = sum(lot_sizes) / len(lot_sizes)
        if any(lot > avg_lot * 5 for lot in lot_sizes):
            return False
        
        return True
    
    # ==========================================
    # 🎯 EXECUTION & MANAGEMENT
    # ==========================================
    
    def execute_combination(self, combination: Dict) -> Dict:
        """
        🚀 Execute Combination - ปิดไม้ตาม Combination
        """
        
        try:
            positions = combination['positions']
            combo_type = combination.get('type', 'unknown')
            
            logger.info(f"🎯 Executing {combo_type} combination: {len(positions)} positions")
            
            # Prepare close data
            close_data = []
            total_lot = 0
            
            for position in positions:
                close_data.append({
                    'ticket': position.ticket,
                    'lot': position.volume,
                    'type': 'BUY' if position.type == 0 else 'SELL',
                    'profit': position.profit
                })
                total_lot += position.volume
            
            # Log before execution
            logger.info(f"💰 Combination Profit: ${combination['total_profit']:.2f}")
            logger.info(f"📊 Total Lot: {total_lot:.2f}")
            logger.info(f"🎯 Positions: {[pos.ticket for pos in positions]}")
            
            # Execute close via MT5 Manager
            if self.mt5_manager:
                close_result = self.mt5_manager.close_positions_group(
                    [pos.ticket for pos in positions],
                    f"Universal Recovery: {combo_type}"
                )
                
                if close_result.get('success', False):
                    # Update tracking data
                    self._update_after_execution(combination, close_result)
                    
                    logger.info(f"✅ Successfully closed {len(positions)} positions")
                    logger.info(f"💰 Total Profit: ${close_result.get('total_profit', 0):.2f}")
                    
                    return {
                        'success': True,
                        'positions_closed': len(positions),
                        'total_profit': close_result.get('total_profit', 0),
                        'combination_type': combo_type
                    }
                else:
                    logger.error(f"❌ Failed to close combination: {close_result.get('error', 'Unknown error')}")
                    return {'success': False, 'error': close_result.get('error', 'Close failed')}
            
            else:
                logger.warning("⚠️ No MT5 Manager available - simulation mode")
                return {'success': True, 'simulation': True}
                
        except Exception as e:
            logger.error(f"🚨 Error executing combination: {e}")
            return {'success': False, 'error': str(e)}
    
    def _update_after_execution(self, combination: Dict, close_result: Dict):
        """Update tracking data หลังปิดไม้"""
        
        closed_tickets = close_result.get('closed_positions', [])
        
        # Update Recovery Pairs
        for pair_key, pair_info in list(self.recovery_pairs.items()):
            if (pair_info.primary_ticket in closed_tickets and 
                pair_info.recovery_ticket in closed_tickets):
                # ปิดครบคู่แล้ว
                pair_info.status = 'completed'
                logger.info(f"✅ Recovery pair completed: {pair_key}")
        
        # Update Balance Positions
        for ticket in closed_tickets:
            if ticket in self.balance_positions:
                del self.balance_positions[ticket]
                logger.info(f"✅ Balance position closed: {ticket}")
        
        # Update Recovery Groups
        for group_id, group_info in list(self.recovery_groups.items()):
            remaining_positions = [t for t in group_info.positions if t not in closed_tickets]
            if not remaining_positions:
                del self.recovery_groups[group_id]
                logger.info(f"✅ Recovery group completed: {group_id}")
            else:
                group_info.positions = remaining_positions
        
        # Save updated data
        self.save_data()
    
    # ==========================================
    # 💾 DATA PERSISTENCE
    # ==========================================
    
    def save_data(self):
        """บันทึกข้อมูลลง JSON"""
        
        try:
            data = {
                'recovery_pairs': {
                    k: {
                        'primary_ticket': v.primary_ticket,
                        'recovery_ticket': v.recovery_ticket,
                        'pair_type': v.pair_type,
                        'created_time': v.created_time.isoformat(),
                        'target_profit': v.target_profit,
                        'status': v.status
                    }
                    for k, v in self.recovery_pairs.items()
                },
                'balance_positions': {
                    str(k): {
                        'ticket': v.ticket,
                        'direction': v.direction,
                        'purpose': v.purpose,
                        'created_time': v.created_time.isoformat(),
                        'target_balance': v.target_balance
                    }
                    for k, v in self.balance_positions.items()
                },
                'recovery_groups': {
                    k: {
                        'group_id': v.group_id,
                        'positions': v.positions,
                        'group_type': v.group_type,
                        'target_profit': v.target_profit,
                        'created_time': v.created_time.isoformat(),
                        'priority': v.priority
                    }
                    for k, v in self.recovery_groups.items()
                },
                'last_updated': datetime.now().isoformat()
            }
            
            # สร้าง backup ก่อน
            if os.path.exists(self.data_file):
                import shutil
                shutil.copy2(self.data_file, self.backup_file)
            
            # บันทึกข้อมูลใหม่
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            logger.debug("💾 Universal recovery data saved")
            
        except Exception as e:
            logger.error(f"🚨 Error saving data: {e}")
    
    def load_data(self):
        """โหลดข้อมูลจาก JSON"""
        
        try:
            if not os.path.exists(self.data_file):
                logger.info("📁 No existing data file - starting fresh")
                return
            
            with open(self.data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # โหลด Recovery Pairs
            for k, v in data.get('recovery_pairs', {}).items():
                self.recovery_pairs[k] = RecoveryPair(
                    primary_ticket=v['primary_ticket'],
                    recovery_ticket=v['recovery_ticket'],
                    pair_type=v['pair_type'],
                    created_time=datetime.fromisoformat(v['created_time']),
                    target_profit=v['target_profit'],
                    status=v['status']
                )
            
            # โหลด Balance Positions
            for k, v in data.get('balance_positions', {}).items():
                self.balance_positions[int(k)] = BalancePosition(
                    ticket=v['ticket'],
                    direction=v['direction'],
                    purpose=v['purpose'],
                    created_time=datetime.fromisoformat(v['created_time']),
                    target_balance=v['target_balance']
                )
            
            # โหลด Recovery Groups
            for k, v in data.get('recovery_groups', {}).items():
                self.recovery_groups[k] = RecoveryGroup(
                    group_id=v['group_id'],
                    positions=v['positions'],
                    group_type=v['group_type'],
                    target_profit=v['target_profit'],
                    created_time=datetime.fromisoformat(v['created_time']),
                    priority=v['priority']
                )
            
            logger.info(f"📁 Loaded data: {len(self.recovery_pairs)} pairs, {len(self.balance_positions)} balance positions")
            
        except Exception as e:
            logger.error(f"🚨 Error loading data: {e}")
            
            # ลองโหลด backup
            try:
                if os.path.exists(self.backup_file):
                    logger.info("🔄 Trying to load backup file...")
                    import shutil
                    shutil.copy2(self.backup_file, self.data_file)
                    self.load_data()  # Recursive call
            except Exception as backup_error:
                logger.error(f"🚨 Backup load failed: {backup_error}")
    
    # ==========================================
    # 🔧 UTILITY METHODS
    # ==========================================
    
    def _find_position_by_ticket(self, positions: List[Any], ticket: int) -> Optional[Any]:
        """หาไม้จาก ticket number"""
        for pos in positions:
            if pos.ticket == ticket:
                return pos
        return None
    
    def _find_existing_recovery(self, primary_ticket: int) -> List[RecoveryPair]:
        """หา Recovery ที่มีอยู่แล้วสำหรับไม้นี้"""
        return [pair for pair in self.recovery_pairs.values() 
                if pair.primary_ticket == primary_ticket and pair.status == 'active']
    
    def get_status_summary(self) -> Dict:
        """ดูสถานะรวม Universal Recovery System"""
        
        active_pairs = sum(1 for pair in self.recovery_pairs.values() if pair.status == 'active')
        completed_pairs = sum(1 for pair in self.recovery_pairs.values() if pair.status == 'completed')
        
        return {
            'recovery_pairs': {
                'active': active_pairs,
                'completed': completed_pairs,
                'total': len(self.recovery_pairs)
            },
            'balance_positions': len(self.balance_positions),
            'recovery_groups': len(self.recovery_groups),
            'config': self.config
        }
    
    def cleanup_old_data(self, days_old: int = 7):
        """ทำความสะอาดข้อมูลเก่า"""
        
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        # ลบ Recovery Pairs เก่า
        old_pairs = [k for k, v in self.recovery_pairs.items() 
                    if v.created_time < cutoff_date and v.status == 'completed']
        
        for key in old_pairs:
            del self.recovery_pairs[key]
        
        # ลบ Balance Positions เก่า
        old_balance = [k for k, v in self.balance_positions.items()
                      if v.created_time < cutoff_date]
        
        for key in old_balance:
            del self.balance_positions[key]
        
        if old_pairs or old_balance:
            logger.info(f"🧹 Cleaned up {len(old_pairs)} old pairs and {len(old_balance)} old balance positions")
            self.save_data()


# ==========================================
# 🎯 INTEGRATION HELPER FUNCTIONS
# ==========================================

def create_universal_recovery_manager(mt5_manager=None) -> UniversalRecoveryManager:
    """สร้าง Universal Recovery Manager instance"""
    return UniversalRecoveryManager(mt5_manager=mt5_manager)

def integrate_with_position_manager(position_manager, recovery_manager: UniversalRecoveryManager):
    """เชื่อมต่อกับ Position Manager เดิม"""
    
    # เพิ่ม method ใหม่ใน position_manager
    position_manager.recovery_manager = recovery_manager
    
    # Override should_close_positions method
    original_should_close = position_manager.should_close_positions
    
    def enhanced_should_close_positions(positions, current_price, balance_analysis=None):
        """Enhanced version with Universal Recovery"""
        
        try:
            # 1. เช็ค Drag Recovery ก่อน
            drag_analysis = recovery_manager.analyze_dragged_positions(positions, current_price)
            
            # 2. หา Smart Combinations
            if balance_analysis is None:
                balance_analysis = position_manager._analyze_portfolio_balance(positions, current_price)
            
            smart_combinations = recovery_manager.find_smart_combinations(positions, current_price, balance_analysis)
            
            if smart_combinations:
                best_combination = smart_combinations[0]  # Top scored
                
                logger.info(f"🎯 Universal Recovery found combination: {best_combination['type']}")
                logger.info(f"💰 Profit: ${best_combination['total_profit']:.2f}")
                logger.info(f"📊 Score: {best_combination['score']:.2f}")
                
                return {
                    'should_close': True,
                    'combination': best_combination,
                    'method': 'universal_recovery',
                    'drag_analysis': drag_analysis
                }
            
            # 3. Fallback ไปใช้ระบบเดิม
            return original_should_close(positions, current_price, balance_analysis)
            
        except Exception as e:
            logger.error(f"🚨 Error in enhanced should_close_positions: {e}")
            return original_should_close(positions, current_price, balance_analysis)
    
    # Replace method
    position_manager.should_close_positions = enhanced_should_close_positions
    
    logger.info("🔗 Universal Recovery integrated with Position Manager")

