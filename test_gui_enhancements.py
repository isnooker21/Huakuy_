# -*- coding: utf-8 -*-
"""
Test GUI Enhancements
สคริปต์ทดสอบการปรับปรุง GUI
"""

import sys
import time
import logging
import threading
from typing import Dict, List, Any
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_position_status_widget():
    """ทดสอบ PositionStatusWidget"""
    try:
        logger.info("🧪 Testing PositionStatusWidget...")
        
        # Import modules
        from enhanced_position_widget import PositionStatusWidget
        import tkinter as tk
        
        # สร้าง test window
        root = tk.Tk()
        root.title("Position Status Widget Test")
        root.geometry("800x600")
        
        # Test data
        test_position_data = {
            'ticket': 12345,
            'type': 0,  # BUY
            'volume': 0.1,
            'price_open': 2650.50,
            'price_current': 2651.20,
            'profit': 15.30,
            'status': 'HG - ค้ำ SELL Zone ล่าง (4:1)',
            'relationships': {
                'is_hedging': True,
                'hedge_target': {
                    'ticket': 12346,
                    'direction': 'SELL',
                    'profit': -50.0
                },
                'hedge_ratio': '4:1'
            }
        }
        
        # สร้าง widget
        widget = PositionStatusWidget(root, test_position_data)
        widget.frame.pack(fill='x', padx=10, pady=5)
        
        # Test update
        updated_data = test_position_data.copy()
        updated_data['profit'] = 25.50
        updated_data['status'] = 'Support Guard - ห้ามปิด ค้ำ 2 ไม้'
        
        def update_test():
            time.sleep(2)
            widget.update_status(updated_data)
            logger.info("✅ PositionStatusWidget update test completed")
        
        # รัน update test ใน background
        threading.Thread(target=update_test, daemon=True).start()
        
        # แสดง window
        root.after(5000, root.quit)  # ปิดหลัง 5 วินาที
        root.mainloop()
        
        logger.info("✅ PositionStatusWidget test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ PositionStatusWidget test failed: {e}")
        return False

def test_async_status_updater():
    """ทดสอบ AsyncStatusUpdater"""
    try:
        logger.info("🧪 Testing AsyncStatusUpdater...")
        
        from enhanced_position_widget import AsyncStatusUpdater
        from position_status_manager import PositionStatusManager
        
        # สร้าง mock objects
        class MockGUI:
            def __init__(self):
                self.root = None
                self.position_widgets = {}
                
            def after_idle(self, func):
                func()
        
        class MockStatusManager:
            def analyze_all_positions(self, positions, current_price, zones, market_condition):
                return {}
        
        # สร้าง test objects
        mock_gui = MockGUI()
        mock_status_manager = MockStatusManager()
        
        # สร้าง AsyncStatusUpdater
        updater = AsyncStatusUpdater(
            gui_instance=mock_gui,
            status_manager=mock_status_manager,
            update_interval=1.0  # 1 วินาที
        )
        
        # เริ่ม updates
        updater.start_background_updates()
        
        # รอ 3 วินาที
        time.sleep(3)
        
        # หยุด updates
        updater.stop_background_updates()
        
        logger.info("✅ AsyncStatusUpdater test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ AsyncStatusUpdater test failed: {e}")
        return False

def test_performance_optimizer():
    """ทดสอบ GUIPerformanceOptimizer"""
    try:
        logger.info("🧪 Testing GUIPerformanceOptimizer...")
        
        from gui_performance_optimizer import GUIPerformanceOptimizer
        
        # สร้าง optimizer
        optimizer = GUIPerformanceOptimizer(max_memory_mb=100)
        
        # ทดสอบ update throttling
        assert optimizer.should_update('test_type') == True, "First update should be allowed"
        assert optimizer.should_update('test_type') == False, "Second update should be throttled"
        
        # ทดสอบ performance recording
        optimizer.record_gui_response_time(50.0)
        optimizer.record_update_duration('test', 1.5)
        optimizer.record_success('test_operation')
        optimizer.record_error('test_error')
        
        # ทดสอบ performance report
        report = optimizer.get_performance_report()
        assert 'memory' in report, "Report should contain memory info"
        assert 'performance' in report, "Report should contain performance info"
        assert 'reliability' in report, "Report should contain reliability info"
        
        logger.info("✅ GUIPerformanceOptimizer test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ GUIPerformanceOptimizer test failed: {e}")
        return False

def test_lazy_loader():
    """ทดสอบ LazyPositionLoader"""
    try:
        logger.info("🧪 Testing LazyPositionLoader...")
        
        from gui_performance_optimizer import LazyPositionLoader
        
        # สร้าง mock positions
        class MockPosition:
            def __init__(self, ticket):
                self.ticket = ticket
        
        positions = [MockPosition(i) for i in range(100)]
        
        # สร้าง lazy loader
        loader = LazyPositionLoader(batch_size=10, max_loaded=20)
        
        # ทดสอบ loading
        visible = loader.load_visible_positions(positions, scroll_position=0)
        assert len(visible) == 10, f"Should load 10 positions, got {len(visible)}"
        
        # ทดสอบ loading more
        visible2 = loader.load_visible_positions(positions, scroll_position=10)
        assert len(visible2) == 10, f"Should load 10 more positions, got {len(visible2)}"
        
        # ทดสอบ stats
        stats = loader.get_load_stats()
        assert 'loaded_count' in stats, "Stats should contain loaded_count"
        
        logger.info("✅ LazyPositionLoader test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ LazyPositionLoader test failed: {e}")
        return False

def test_update_throttler():
    """ทดสอบ UpdateThrottler"""
    try:
        logger.info("🧪 Testing UpdateThrottler...")
        
        from gui_performance_optimizer import UpdateThrottler
        
        # สร้าง throttler
        throttler = UpdateThrottler(min_interval=1.0)
        
        # ทดสอบ throttling
        assert throttler.should_update('test') == True, "First update should be allowed"
        assert throttler.should_update('test') == False, "Second update should be throttled"
        
        # รอ 1 วินาที
        time.sleep(1.1)
        assert throttler.should_update('test') == True, "Update should be allowed after interval"
        
        # ทดสอบ stats
        stats = throttler.get_update_stats()
        assert 'last_updates' in stats, "Stats should contain last_updates"
        
        logger.info("✅ UpdateThrottler test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ UpdateThrottler test failed: {e}")
        return False

def run_integration_test():
    """ทดสอบการรวมระบบ"""
    try:
        logger.info("🧪 Running integration test...")
        
        # ทดสอบการ import modules ทั้งหมด
        from enhanced_position_widget import PositionStatusWidget, AsyncStatusUpdater
        from gui_performance_optimizer import GUIPerformanceOptimizer, LazyPositionLoader, UpdateThrottler
        from position_status_manager import PositionStatusManager
        
        logger.info("✅ All modules imported successfully")
        
        # ทดสอบการสร้าง objects
        optimizer = GUIPerformanceOptimizer()
        loader = LazyPositionLoader()
        throttler = UpdateThrottler()
        
        logger.info("✅ All objects created successfully")
        
        # ทดสอบการทำงานร่วมกัน
        assert optimizer.should_update('integration_test') == True
        assert loader.load_visible_positions([]) == []
        assert throttler.should_update('integration_test') == True
        
        logger.info("✅ Integration test completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Integration test failed: {e}")
        return False

def main():
    """รันการทดสอบทั้งหมด"""
    logger.info("🚀 Starting GUI Enhancements Tests...")
    
    tests = [
        ("PositionStatusWidget", test_position_status_widget),
        ("AsyncStatusUpdater", test_async_status_updater),
        ("GUIPerformanceOptimizer", test_performance_optimizer),
        ("LazyPositionLoader", test_lazy_loader),
        ("UpdateThrottler", test_update_throttler),
        ("Integration Test", run_integration_test)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        logger.info(f"🧪 Running {test_name} test...")
        try:
            result = test_func()
            results.append((test_name, result))
            if result:
                logger.info(f"✅ {test_name} test PASSED")
            else:
                logger.error(f"❌ {test_name} test FAILED")
        except Exception as e:
            logger.error(f"❌ {test_name} test ERROR: {e}")
            results.append((test_name, False))
    
    # สรุปผลการทดสอบ
    logger.info("📊 Test Results Summary:")
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        logger.info(f"   {test_name}: {status}")
    
    logger.info(f"📊 Overall: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    
    if passed == total:
        logger.info("🎉 All tests passed! GUI enhancements are ready.")
        return True
    else:
        logger.error("⚠️ Some tests failed. Please check the implementation.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
