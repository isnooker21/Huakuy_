# -*- coding: utf-8 -*-
"""
GUI Performance Optimizer
โมดูลสำหรับเพิ่มประสิทธิภาพ GUI และจัดการ Memory
"""

import time
import threading
import logging
from typing import Dict, List, Any, Optional, Set
from collections import deque
import gc

logger = logging.getLogger(__name__)

class GUIPerformanceOptimizer:
    """คลาสสำหรับเพิ่มประสิทธิภาพ GUI"""
    
    def __init__(self, max_memory_mb: int = 200):
        self.max_memory_mb = max_memory_mb
        self.max_widgets = 50
        self.max_history_size = 100
        
        # Memory tracking
        self.memory_usage_history = deque(maxlen=50)
        self.last_memory_check = 0
        self.memory_check_interval = 30  # ตรวจสอบทุก 30 วินาที
        
        # Update throttling
        self.update_intervals = {
            'position_status': 5.0,    # อัพเดทสถานะไม้ทุก 5 วินาที
            'account_info': 60.0,      # อัพเดทข้อมูลบัญชีทุก 60 วินาที
            'portfolio_info': 120.0,   # อัพเดทข้อมูลพอร์ตทุก 120 วินาที
            'hedge_analysis': 30.0,    # วิเคราะห์ hedge ทุก 30 วินาที
            'market_status': 15.0      # อัพเดทสถานะตลาดทุก 15 วินาที
        }
        
        self.last_updates = {}
        
        # Performance monitoring
        self.performance_metrics = {
            'gui_response_time': deque(maxlen=100),
            'update_durations': deque(maxlen=50),
            'memory_usage': deque(maxlen=100),
            'error_count': 0,
            'success_count': 0
        }
        
        # Cleanup management
        self.cleanup_intervals = {
            'widgets': 300,      # ล้าง widgets ทุก 5 นาที
            'memory': 60,        # ตรวจสอบ memory ทุก 1 นาที
            'logs': 600          # ล้าง logs ทุก 10 นาที
        }
        
        self.last_cleanup = {}
        
    def should_update(self, update_type: str) -> bool:
        """ตรวจสอบว่าควรอัพเดทหรือไม่"""
        try:
            current_time = time.time()
            last_update = self.last_updates.get(update_type, 0)
            interval = self.update_intervals.get(update_type, 5.0)
            
            if current_time - last_update >= interval:
                self.last_updates[update_type] = current_time
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking update throttle: {e}")
            return True  # ถ้าเกิด error ให้อัพเดท
    
    def start_performance_monitoring(self):
        """เริ่มการติดตามประสิทธิภาพ"""
        try:
            monitoring_thread = threading.Thread(
                target=self._performance_monitoring_loop,
                daemon=True,
                name="GUIPerformanceMonitor"
            )
            monitoring_thread.start()
            logger.info("🚀 GUI Performance Monitoring started")
            
        except Exception as e:
            logger.error(f"❌ Error starting performance monitoring: {e}")
    
    def _performance_monitoring_loop(self):
        """ลูปติดตามประสิทธิภาพ"""
        while True:
            try:
                current_time = time.time()
                
                # ตรวจสอบ memory
                if self._should_check_memory(current_time):
                    self._check_memory_usage()
                
                # ทำความสะอาด
                self._perform_cleanup(current_time)
                
                # รอ 30 วินาที
                time.sleep(30)
                
            except Exception as e:
                logger.error(f"❌ Error in performance monitoring loop: {e}")
                time.sleep(60)
    
    def _should_check_memory(self, current_time: float) -> bool:
        """ตรวจสอบว่าควรตรวจสอบ memory หรือไม่"""
        return current_time - self.last_memory_check >= self.memory_check_interval
    
    def _check_memory_usage(self):
        """ตรวจสอบการใช้ memory"""
        try:
            import psutil
            import os
            
            # ดึง memory usage ของ process
            process = psutil.Process(os.getpid())
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024
            
            # เก็บข้อมูล
            self.memory_usage_history.append(memory_mb)
            self.performance_metrics['memory_usage'].append(memory_mb)
            
            # ตรวจสอบว่าต้องทำความสะอาดหรือไม่
            if memory_mb > self.max_memory_mb:
                logger.warning(f"⚠️ High memory usage: {memory_mb:.1f}MB (limit: {self.max_memory_mb}MB)")
                self._force_cleanup()
            
            # Log สถิติ
            avg_memory = sum(self.memory_usage_history) / len(self.memory_usage_history)
            max_memory = max(self.memory_usage_history)
            
            logger.debug(f"📊 Memory: Current: {memory_mb:.1f}MB, Avg: {avg_memory:.1f}MB, Max: {max_memory:.1f}MB")
            
            self.last_memory_check = time.time()
            
        except ImportError:
            logger.warning("⚠️ psutil not available - memory monitoring disabled")
        except Exception as e:
            logger.error(f"❌ Error checking memory usage: {e}")
    
    def _perform_cleanup(self, current_time: float):
        """ทำความสะอาดตามกำหนด"""
        try:
            for cleanup_type, interval in self.cleanup_intervals.items():
                last_cleanup = self.last_cleanup.get(cleanup_type, 0)
                
                if current_time - last_cleanup >= interval:
                    if cleanup_type == 'memory':
                        self._cleanup_memory()
                    elif cleanup_type == 'widgets':
                        self._cleanup_widgets()
                    elif cleanup_type == 'logs':
                        self._cleanup_logs()
                    
                    self.last_cleanup[cleanup_type] = current_time
                    
        except Exception as e:
            logger.error(f"❌ Error performing cleanup: {e}")
    
    def _cleanup_memory(self):
        """ทำความสะอาด memory"""
        try:
            # เรียก garbage collection
            collected = gc.collect()
            
            if collected > 0:
                logger.debug(f"🧹 Garbage collected: {collected} objects")
            
            # ล้าง history ที่เก่าเกินไป
            if len(self.memory_usage_history) > 30:
                self.memory_usage_history.clear()
            
            if len(self.performance_metrics['gui_response_time']) > 50:
                self.performance_metrics['gui_response_time'].clear()
                
        except Exception as e:
            logger.error(f"❌ Error cleaning up memory: {e}")
    
    def _cleanup_widgets(self):
        """ทำความสะอาด widgets"""
        try:
            # ฟังก์ชันนี้จะถูกเรียกจาก GUI เพื่อล้าง widgets ที่ไม่ใช้
            logger.debug("🧹 Widget cleanup scheduled")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up widgets: {e}")
    
    def _cleanup_logs(self):
        """ทำความสะอาด logs"""
        try:
            # ล้าง performance metrics เก่า
            for metric in self.performance_metrics.values():
                if hasattr(metric, 'clear') and len(metric) > 100:
                    metric.clear()
            
            logger.debug("🧹 Log cleanup completed")
            
        except Exception as e:
            logger.error(f"❌ Error cleaning up logs: {e}")
    
    def _force_cleanup(self):
        """บังคับทำความสะอาดเมื่อ memory สูง"""
        try:
            logger.warning("🧹 Forcing cleanup due to high memory usage")
            
            # Garbage collection
            collected = gc.collect()
            
            # ล้างข้อมูลเก่า
            self.memory_usage_history.clear()
            self.performance_metrics['gui_response_time'].clear()
            self.performance_metrics['update_durations'].clear()
            
            logger.info(f"🧹 Force cleanup completed: {collected} objects collected")
            
        except Exception as e:
            logger.error(f"❌ Error in force cleanup: {e}")
    
    def record_gui_response_time(self, response_time_ms: float):
        """บันทึกเวลาตอบสนอง GUI"""
        try:
            self.performance_metrics['gui_response_time'].append(response_time_ms)
            
            # ตรวจสอบว่าเร็วพอหรือไม่
            if response_time_ms > 100:  # มากกว่า 100ms
                logger.warning(f"⚠️ Slow GUI response: {response_time_ms:.1f}ms")
            
        except Exception as e:
            logger.error(f"❌ Error recording GUI response time: {e}")
    
    def record_update_duration(self, update_type: str, duration_seconds: float):
        """บันทึกระยะเวลาการอัพเดท"""
        try:
            self.performance_metrics['update_durations'].append(duration_seconds)
            
            # ตรวจสอบว่าเร็วพอหรือไม่
            if duration_seconds > 5.0:  # มากกว่า 5 วินาที
                logger.warning(f"⚠️ Slow {update_type} update: {duration_seconds:.1f}s")
            
        except Exception as e:
            logger.error(f"❌ Error recording update duration: {e}")
    
    def record_error(self, error_type: str):
        """บันทึก error"""
        try:
            self.performance_metrics['error_count'] += 1
            logger.debug(f"📊 Error recorded: {error_type} (Total: {self.performance_metrics['error_count']})")
            
        except Exception as e:
            logger.error(f"❌ Error recording error: {e}")
    
    def record_success(self, operation_type: str):
        """บันทึกความสำเร็จ"""
        try:
            self.performance_metrics['success_count'] += 1
            logger.debug(f"📊 Success recorded: {operation_type} (Total: {self.performance_metrics['success_count']})")
            
        except Exception as e:
            logger.error(f"❌ Error recording success: {e}")
    
    def get_performance_report(self) -> Dict[str, Any]:
        """ดึงรายงานประสิทธิภาพ"""
        try:
            # คำนวณสถิติ
            response_times = list(self.performance_metrics['gui_response_time'])
            update_durations = list(self.performance_metrics['update_durations'])
            memory_usage = list(self.performance_metrics['memory_usage'])
            
            report = {
                'memory': {
                    'current_mb': memory_usage[-1] if memory_usage else 0,
                    'average_mb': sum(memory_usage) / len(memory_usage) if memory_usage else 0,
                    'max_mb': max(memory_usage) if memory_usage else 0,
                    'limit_mb': self.max_memory_mb
                },
                'performance': {
                    'avg_response_time_ms': sum(response_times) / len(response_times) if response_times else 0,
                    'max_response_time_ms': max(response_times) if response_times else 0,
                    'avg_update_duration_s': sum(update_durations) / len(update_durations) if update_durations else 0,
                    'max_update_duration_s': max(update_durations) if update_durations else 0
                },
                'reliability': {
                    'error_count': self.performance_metrics['error_count'],
                    'success_count': self.performance_metrics['success_count'],
                    'success_rate': (
                        self.performance_metrics['success_count'] / 
                        (self.performance_metrics['success_count'] + self.performance_metrics['error_count']) * 100
                        if (self.performance_metrics['success_count'] + self.performance_metrics['error_count']) > 0 else 0
                    )
                },
                'status': 'healthy' if self._is_performance_healthy() else 'needs_attention'
            }
            
            return report
            
        except Exception as e:
            logger.error(f"❌ Error generating performance report: {e}")
            return {}
    
    def _is_performance_healthy(self) -> bool:
        """ตรวจสอบว่าประสิทธิภาพดีหรือไม่"""
        try:
            # ตรวจสอบ memory
            memory_usage = list(self.performance_metrics['memory_usage'])
            if memory_usage and memory_usage[-1] > self.max_memory_mb * 0.8:
                return False
            
            # ตรวจสอบ response time
            response_times = list(self.performance_metrics['gui_response_time'])
            if response_times and max(response_times) > 200:  # มากกว่า 200ms
                return False
            
            # ตรวจสอบ success rate
            total_operations = self.performance_metrics['success_count'] + self.performance_metrics['error_count']
            if total_operations > 10:  # มีการทำงานมากกว่า 10 ครั้ง
                success_rate = self.performance_metrics['success_count'] / total_operations * 100
                if success_rate < 90:  # success rate น้อยกว่า 90%
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error checking performance health: {e}")
            return False


class LazyPositionLoader:
    """โหลด Position ทีละส่วนเพื่อเพิ่มประสิทธิภาพ"""
    
    def __init__(self, batch_size: int = 20, max_loaded: int = 50):
        self.batch_size = batch_size
        self.max_loaded = max_loaded
        self.loaded_positions = set()
        self.loaded_widgets = {}
        self.load_order = deque(maxlen=max_loaded)
        
    def load_visible_positions(self, all_positions: List[Any], scroll_position: int = 0) -> List[Any]:
        """โหลดแค่ Position ที่มองเห็น"""
        try:
            if not all_positions:
                return []
            
            # คำนวณตำแหน่งที่ควรโหลด
            start_idx = scroll_position
            end_idx = min(start_idx + self.batch_size, len(all_positions))
            
            # โหลด positions ที่มองเห็น
            visible_positions = []
            for i in range(start_idx, end_idx):
                if i < len(all_positions):
                    pos = all_positions[i]
                    ticket = getattr(pos, 'ticket', 0)
                    
                    if ticket not in self.loaded_positions:
                        self.loaded_positions.add(ticket)
                        self.load_order.append(ticket)
                        
                        # ลบ positions เก่าถ้าเกินขีดจำกัด
                        if len(self.loaded_positions) > self.max_loaded:
                            oldest_ticket = self.load_order.popleft()
                            self.loaded_positions.discard(oldest_ticket)
                            if oldest_ticket in self.loaded_widgets:
                                del self.loaded_widgets[oldest_ticket]
                    
                    visible_positions.append(pos)
            
            return visible_positions
            
        except Exception as e:
            logger.error(f"❌ Error loading visible positions: {e}")
            return all_positions[:self.batch_size]
    
    def unload_position(self, ticket: int):
        """ยกเลิกการโหลด position"""
        try:
            self.loaded_positions.discard(ticket)
            if ticket in self.loaded_widgets:
                del self.loaded_widgets[ticket]
            
            # ลบออกจาก load order
            if ticket in self.load_order:
                self.load_order.remove(ticket)
                
        except Exception as e:
            logger.error(f"❌ Error unloading position: {e}")
    
    def is_loaded(self, ticket: int) -> bool:
        """ตรวจสอบว่า position โหลดแล้วหรือไม่"""
        return ticket in self.loaded_positions
    
    def get_load_stats(self) -> Dict[str, Any]:
        """ดึงสถิติการโหลด"""
        return {
            'loaded_count': len(self.loaded_positions),
            'max_loaded': self.max_loaded,
            'load_order': list(self.load_order),
            'loaded_tickets': list(self.loaded_positions)
        }


class UpdateThrottler:
    """จำกัดความถี่การอัพเดทเพื่อเพิ่มประสิทธิภาพ"""
    
    def __init__(self, min_interval: float = 2.0):
        self.min_interval = min_interval
        self.last_updates = {}
        self.update_counts = {}
        
    def should_update(self, key: str) -> bool:
        """ตรวจสอบว่าควรอัพเดทหรือไม่"""
        try:
            current_time = time.time()
            last_update = self.last_updates.get(key, 0)
            
            if current_time - last_update >= self.min_interval:
                self.last_updates[key] = current_time
                self.update_counts[key] = self.update_counts.get(key, 0) + 1
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking update throttle: {e}")
            return True
    
    def get_update_stats(self) -> Dict[str, Any]:
        """ดึงสถิติการอัพเดท"""
        return {
            'last_updates': self.last_updates.copy(),
            'update_counts': self.update_counts.copy(),
            'min_interval': self.min_interval
        }
    
    def reset_stats(self):
        """รีเซ็ตสถิติ"""
        self.last_updates.clear()
        self.update_counts.clear()
