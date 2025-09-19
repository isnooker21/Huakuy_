# -*- coding: utf-8 -*-
"""
Enhanced Position Status Widget
Widget สำหรับแสดงสถานะของแต่ละ Position แบบ Real-time
"""

import tkinter as tk
from tkinter import ttk
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class PositionStatusWidget:
    """Widget แสดงสถานะของแต่ละ Position"""
    
    def __init__(self, parent, position_data: Dict[str, Any]):
        self.parent = parent
        self.position_data = position_data
        self.ticket = position_data.get('ticket', 0)
        
        # สร้าง main frame
        self.frame = ttk.Frame(parent, relief='raised', borderwidth=1)
        
        # สีสำหรับสถานะต่างๆ
        self.STATUS_COLORS = {
            'HG': {'bg': '#FF6B6B', 'fg': '#FFFFFF'},           # สีแดง - สำคัญมาก
            'Support Guard': {'bg': '#4ECDC4', 'fg': '#FFFFFF'}, # สีเขียวอ่อน - ห้ามปิด
            'Protected': {'bg': '#45B7D1', 'fg': '#FFFFFF'},     # สีฟ้า - ปลอดภัย
            'Profit Helper': {'bg': '#96CEB4', 'fg': '#000000'}, # สีเขียว - พร้อมช่วย
            'Standalone': {'bg': '#FECA57', 'fg': '#000000'},    # สีเหลือง - ปกติ
            'default': {'bg': '#E8E8E8', 'fg': '#000000'}        # สีเทา - default
        }
        
        self.PROFIT_COLORS = {
            'profit': '#27AE60',    # เขียว
            'loss': '#E74C3C',      # แดง
            'neutral': '#95A5A6'    # เทา
        }
        
        # สร้าง widgets
        self.create_widgets()
        self.update_status(position_data)
        
    def create_widgets(self):
        """สร้าง widgets ทั้งหมด"""
        try:
            # Main container
            self.main_frame = ttk.Frame(self.frame)
            self.main_frame.pack(fill='x', padx=5, pady=3)
            
            # Row 1: Basic Info
            self.basic_frame = ttk.Frame(self.main_frame)
            self.basic_frame.pack(fill='x', pady=2)
            
            # Ticket
            self.ticket_label = ttk.Label(
                self.basic_frame, 
                text=f"#{self.ticket}",
                font=('Segoe UI', 10, 'bold'),
                foreground='#2C3E50'
            )
            self.ticket_label.pack(side='left', padx=(0, 10))
            
            # Type & Volume
            self.type_volume_label = ttk.Label(
                self.basic_frame,
                text="",
                font=('Segoe UI', 9),
                foreground='#34495E'
            )
            self.type_volume_label.pack(side='left', padx=(0, 10))
            
            # Price Info
            self.price_label = ttk.Label(
                self.basic_frame,
                text="",
                font=('Segoe UI', 9),
                foreground='#34495E'
            )
            self.price_label.pack(side='left', padx=(0, 10))
            
            # Profit (with color)
            self.profit_label = ttk.Label(
                self.basic_frame,
                text="",
                font=('Segoe UI', 9, 'bold')
            )
            self.profit_label.pack(side='right')
            
            # Row 2: Status Info
            self.status_frame = ttk.Frame(self.main_frame)
            self.status_frame.pack(fill='x', pady=2)
            
            # Status Icon & Text
            self.status_icon_label = ttk.Label(
                self.status_frame,
                text="🛡️",
                font=('Segoe UI', 10)
            )
            self.status_icon_label.pack(side='left', padx=(0, 5))
            
            self.status_label = ttk.Label(
                self.status_frame,
                text="Status: Loading...",
                font=('Segoe UI', 9),
                foreground='#7F8C8D'
            )
            self.status_label.pack(side='left', padx=(0, 10))
            
            # Row 3: Relationships
            self.relationship_frame = ttk.Frame(self.main_frame)
            self.relationship_frame.pack(fill='x', pady=2)
            
            self.relationship_icon_label = ttk.Label(
                self.relationship_frame,
                text="🎯",
                font=('Segoe UI', 10)
            )
            self.relationship_icon_label.pack(side='left', padx=(0, 5))
            
            self.relationship_label = ttk.Label(
                self.relationship_frame,
                text="Relationships: -",
                font=('Segoe UI', 9),
                foreground='#7F8C8D'
            )
            self.relationship_label.pack(side='left')
            
            # Configure frame styling
            self._apply_default_styling()
            
        except Exception as e:
            logger.error(f"❌ Error creating position widget: {e}")
    
    def update_status(self, status_data: Dict[str, Any]):
        """อัพเดทสถานะแบบ Async"""
        try:
            # อัพเดทข้อมูลพื้นฐาน
            position_type = "BUY" if status_data.get('type', 0) == 0 else "SELL"
            volume = status_data.get('volume', 0.01)
            price_open = status_data.get('price_open', 0.0)
            price_current = status_data.get('price_current', 0.0)
            profit = status_data.get('profit', 0.0)
            
            # อัพเดท Basic Info
            self.type_volume_label.config(text=f"{position_type} {volume}")
            self.price_label.config(text=f"@{price_open:.5f}")
            
            # อัพเดท Profit (พร้อมสี)
            profit_text = f"${profit:.2f}"
            self.profit_label.config(text=profit_text)
            
            if profit > 0:
                self.profit_label.config(foreground=self.PROFIT_COLORS['profit'])
            elif profit < 0:
                self.profit_label.config(foreground=self.PROFIT_COLORS['loss'])
            else:
                self.profit_label.config(foreground=self.PROFIT_COLORS['neutral'])
            
            # อัพเดท Status
            status = status_data.get('status', 'Unknown')
            self.status_label.config(text=f"Status: {status}")
            
            # อัพเดท Relationships
            relationships = status_data.get('relationships', {})
            rel_text = self._format_relationships(relationships)
            self.relationship_label.config(text=f"Relations: {rel_text}")
            
            # อัพเดทสีตามสถานะ
            self._apply_status_color(status)
            
            # อัพเดท Icons ตามสถานะ
            self._update_status_icons(status)
            
        except Exception as e:
            logger.error(f"❌ Error updating position status: {e}")
    
    def _format_relationships(self, relationships: Dict[str, Any]) -> str:
        """จัดรูปแบบ Relationships"""
        try:
            if not relationships:
                return "None"
            
            rel_parts = []
            
            # HG (Hedge Guard)
            if relationships.get('is_hedging'):
                target = relationships.get('hedge_target', {})
                if target:
                    rel_parts.append(f"HG: #{target.get('ticket', 'N/A')} ({target.get('profit', 0):.2f})")
            
            # Protecting others
            if relationships.get('is_protecting_others'):
                protecting = relationships.get('protecting', [])
                if protecting:
                    tickets = [f"#{p.get('ticket', 'N/A')}" for p in protecting[:2]]
                    rel_parts.append(f"Protecting: {', '.join(tickets)}")
            
            # Protected by
            if relationships.get('is_protected'):
                protector = relationships.get('protected_by', {})
                if protector:
                    rel_parts.append(f"Protected by: #{protector.get('ticket', 'N/A')}")
            
            return "; ".join(rel_parts) if rel_parts else "Standalone"
            
        except Exception as e:
            logger.error(f"❌ Error formatting relationships: {e}")
            return "Error"
    
    def _apply_status_color(self, status: str):
        """ใช้สีตามสถานะ"""
        try:
            # หาสีที่เหมาะสม
            color_config = self.STATUS_COLORS.get('default')
            
            for status_key, colors in self.STATUS_COLORS.items():
                if status_key in status:
                    color_config = colors
                    break
            
            # ใช้สีกับ frame
            self.frame.configure(style='Status.TFrame')
            
            # สร้าง style ถ้ายังไม่มี
            style = ttk.Style()
            style.configure('Status.TFrame', 
                          background=color_config['bg'],
                          borderwidth=2,
                          relief='solid')
            
        except Exception as e:
            logger.error(f"❌ Error applying status color: {e}")
    
    def _update_status_icons(self, status: str):
        """อัพเดท Icons ตามสถานะ"""
        try:
            if 'HG' in status:
                self.status_icon_label.config(text="🛡️")
                self.relationship_icon_label.config(text="🎯")
            elif 'Support Guard' in status:
                self.status_icon_label.config(text="🛡️")
                self.relationship_icon_label.config(text="🔒")
            elif 'Protected' in status:
                self.status_icon_label.config(text="🛡️")
                self.relationship_icon_label.config(text="🤝")
            elif 'Profit Helper' in status:
                self.status_icon_label.config(text="💰")
                self.relationship_icon_label.config(text="📈")
            elif 'Standalone' in status:
                self.status_icon_label.config(text="🔹")
                self.relationship_icon_label.config(text="🔸")
            else:
                self.status_icon_label.config(text="❓")
                self.relationship_icon_label.config(text="❓")
                
        except Exception as e:
            logger.error(f"❌ Error updating status icons: {e}")
    
    def _apply_default_styling(self):
        """ใช้ styling เริ่มต้น"""
        try:
            # กำหนด style สำหรับ frame
            style = ttk.Style()
            style.configure('Position.TFrame',
                          background='#FFFFFF',
                          borderwidth=1,
                          relief='solid')
            
            self.frame.configure(style='Position.TFrame')
            
        except Exception as e:
            logger.error(f"❌ Error applying default styling: {e}")
    
    def highlight_change(self, old_status: str, new_status: str):
        """ไฮไลท์เมื่อสถานะเปลี่ยน"""
        try:
            # Flash สีเหลือง
            self.frame.configure(style='Highlight.TFrame')
            
            # สร้าง highlight style
            style = ttk.Style()
            style.configure('Highlight.TFrame',
                          background='#FFD700',
                          borderwidth=3,
                          relief='solid')
            
            # เปลี่ยนกลับหลัง 2 วินาที
            self.parent.after(2000, self._remove_highlight)
            
        except Exception as e:
            logger.error(f"❌ Error highlighting change: {e}")
    
    def _remove_highlight(self):
        """ลบ highlight"""
        try:
            self._apply_status_color(self.status_label.cget('text'))
        except Exception as e:
            logger.error(f"❌ Error removing highlight: {e}")
    
    def destroy(self):
        """ทำลาย widget"""
        try:
            self.frame.destroy()
        except Exception as e:
            logger.error(f"❌ Error destroying widget: {e}")


class AsyncStatusUpdater:
    """Background Thread สำหรับอัพเดทสถานะ"""
    
    def __init__(self, gui_instance, status_manager, update_interval: float = 5.0):
        self.gui = gui_instance
        self.status_manager = status_manager
        self.update_interval = update_interval
        self.stop_flag = False
        self.update_thread = None
        self.last_positions = {}
        self.last_status_results = {}
        
        # Update throttling
        self.update_throttler = UpdateThrottler(min_interval=2.0)
        
        # Memory management
        self.max_widgets = 50  # จำกัดจำนวน widgets
        
    def start_background_updates(self):
        """เริ่ม Background Updates"""
        try:
            if self.update_thread and self.update_thread.is_alive():
                logger.warning("🔄 Status updater already running")
                return
            
            self.stop_flag = False
            self.update_thread = threading.Thread(
                target=self._background_update_loop, 
                daemon=True,
                name="AsyncStatusUpdater"
            )
            self.update_thread.start()
            logger.info("🚀 Async Status Updater started")
            
        except Exception as e:
            logger.error(f"❌ Error starting async status updater: {e}")
    
    def stop_background_updates(self):
        """หยุด Background Updates"""
        try:
            self.stop_flag = True
            if self.update_thread and self.update_thread.is_alive():
                self.update_thread.join(timeout=3)
            logger.info("🛑 Async Status Updater stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping async status updater: {e}")
    
    def _background_update_loop(self):
        """Background update loop"""
        while not self.stop_flag:
            try:
                # ดึงข้อมูล Positions
                positions = self._get_positions_async()
                
                if not positions:
                    time.sleep(self.update_interval)
                    continue
                
                # วิเคราะห์สถานะ (ใน Background)
                status_results = self._analyze_status_async(positions)
                
                if status_results:
                    # ตรวจสอบการเปลี่ยนแปลง
                    changes_detected = self._detect_status_changes(status_results)
                    
                    # ส่งผลลัพธ์ไป GUI Thread
                    self.gui.root.after_idle(
                        lambda: self._update_gui_with_results(status_results, changes_detected)
                    )
                
                # รอ interval
                time.sleep(self.update_interval)
                
            except Exception as e:
                logger.error(f"❌ Background update error: {e}")
                time.sleep(10)  # รอนานขึ้นเมื่อเกิด error
    
    def _get_positions_async(self) -> List[Any]:
        """ดึงข้อมูล Positions แบบ async"""
        try:
            if not self.gui.trading_system:
                return []
            
            if hasattr(self.gui.trading_system, 'order_manager'):
                return self.gui.trading_system.order_manager.active_positions
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Error getting positions async: {e}")
            return []
    
    def _analyze_status_async(self, positions: List[Any]) -> Dict[int, Any]:
        """วิเคราะห์สถานะแบบ async"""
        try:
            if not self.status_manager:
                return {}
            
            # ดึงราคาปัจจุบัน
            current_price = self._get_current_price()
            if current_price == 0:
                return {}
            
            # ดึง zones (ถ้ามี)
            zones = self._get_zones_async()
            
            # วิเคราะห์สถานะ
            status_results = self.status_manager.analyze_all_positions(
                positions=positions,
                current_price=current_price,
                zones=zones,
                market_condition='sideways'  # Default
            )
            
            return status_results
            
        except Exception as e:
            logger.error(f"❌ Error analyzing status async: {e}")
            return {}
    
    def _get_current_price(self) -> float:
        """ดึงราคาปัจจุบัน"""
        try:
            if (self.gui.trading_system and 
                hasattr(self.gui.trading_system, 'mt5_connection') and
                self.gui.trading_system.actual_symbol):
                
                tick_data = self.gui.trading_system.mt5_connection.get_current_tick(
                    self.gui.trading_system.actual_symbol
                )
                if tick_data:
                    return tick_data.get('bid', 0.0)
            
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ Error getting current price: {e}")
            return 0.0
    
    def _get_zones_async(self) -> List[Dict]:
        """ดึง zones แบบ async"""
        try:
            if (self.gui.trading_system and 
                hasattr(self.gui.trading_system, 'zone_analyzer') and
                self.gui.trading_system.zone_analyzer):
                
                zones = self.gui.trading_system.zone_analyzer.get_zones()
                if zones:
                    return zones.get('support', []) + zones.get('resistance', [])
            
            return []
            
        except Exception as e:
            logger.error(f"❌ Error getting zones async: {e}")
            return []
    
    def _detect_status_changes(self, status_results: Dict[int, Any]) -> Dict[int, str]:
        """ตรวจสอบการเปลี่ยนแปลงสถานะ"""
        try:
            changes = {}
            
            for ticket, status_obj in status_results.items():
                old_status = self.last_status_results.get(ticket, {}).get('status', '')
                new_status = status_obj.status
                
                if old_status and old_status != new_status:
                    changes[ticket] = new_status
            
            return changes
            
        except Exception as e:
            logger.error(f"❌ Error detecting status changes: {e}")
            return {}
    
    def _update_gui_with_results(self, status_results: Dict[int, Any], changes: Dict[int, str]):
        """อัพเดท GUI ด้วยผลลัพธ์"""
        try:
            if not hasattr(self.gui, 'update_position_status_display'):
                return
            
            # อัพเดท GUI
            self.gui.update_position_status_display(status_results)
            
            # แสดง highlight สำหรับการเปลี่ยนแปลง
            for ticket, new_status in changes.items():
                widget = self.gui.position_widgets.get(ticket)
                if widget:
                    old_status = self.last_status_results.get(ticket, {}).get('status', '')
                    widget.highlight_change(old_status, new_status)
            
            # อัพเดท cache
            self.last_status_results = {
                ticket: {
                    'status': status_obj.status,
                    'last_update': status_obj.last_update
                }
                for ticket, status_obj in status_results.items()
            }
            
        except Exception as e:
            logger.error(f"❌ Error updating GUI with results: {e}")


class UpdateThrottler:
    """จำกัดความถี่การอัพเดท"""
    
    def __init__(self, min_interval: float = 2.0):
        self.min_interval = min_interval
        self.last_updates = {}
        
    def should_update(self, ticket: int) -> bool:
        """ตรวจสอบว่าควรอัพเดทหรือไม่"""
        try:
            now = time.time()
            last_update = self.last_updates.get(ticket, 0)
            
            if now - last_update >= self.min_interval:
                self.last_updates[ticket] = now
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ Error checking update throttle: {e}")
            return True


class LazyPositionLoader:
    """โหลด Position ทีละส่วน"""
    
    def __init__(self, batch_size: int = 20):
        self.batch_size = batch_size
        self.loaded_positions = set()
        self.total_positions = 0
        
    def load_visible_positions_only(self, positions: List[Any], scroll_position: int = 0) -> List[Any]:
        """โหลดแค่ Position ที่มองเห็น"""
        try:
            # คำนวณ Position ที่อยู่ในหน้าจอ
            start_idx = scroll_position
            end_idx = min(start_idx + self.batch_size, len(positions))
            
            visible_positions = positions[start_idx:end_idx]
            
            # อัพเดท loaded positions
            for pos in visible_positions:
                ticket = getattr(pos, 'ticket', 0)
                self.loaded_positions.add(ticket)
            
            return visible_positions
            
        except Exception as e:
            logger.error(f"❌ Error loading visible positions: {e}")
            return positions[:self.batch_size]


# Import required modules
import threading
import time
