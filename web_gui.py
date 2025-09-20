# -*- coding: utf-8 -*-
"""
Web-based GUI for Trading System
GUI แบบ Web ที่เร็วกว่าและเสถียรกว่า Tkinter
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Dict, List, Any, Optional
import threading

from aiohttp import web, WSMsgType
import aiohttp_cors

logger = logging.getLogger(__name__)

class WebTradingGUI:
    """Web-based Trading GUI ที่เร็วกว่าและเสถียรกว่า Tkinter"""
    
    def __init__(self, trading_system, host='localhost', port=8080):
        self.trading_system = trading_system
        self.host = host
        self.port = port
        
        # Web server
        self.app = None
        self.runner = None
        self.site = None
        
        # WebSocket connections
        self.websocket_connections = set()
        
        # Data cache
        self.cached_data = {
            'account_info': {},
            'trading_status': {},
            'positions': [],
            'position_status': {},
            'performance': {},
            'logs': []
        }
        
        # Update intervals (วินาที)
        self.update_intervals = {
            'account_info': 30,      # 30 วินาที
            'trading_status': 10,    # 10 วินาที
            'positions': 5,          # 5 วินาที
            'position_status': 5,    # 5 วินาที
            'performance': 60,       # 1 นาที
            'logs': 2                # 2 วินาที
        }
        
        self.last_updates = {}
        
        # Background update task
        self.update_task = None
        self.running = False
        
    async def start_server(self):
        """เริ่ม Web Server"""
        try:
            # สร้าง aiohttp app
            self.app = web.Application()
            
            # ตั้งค่า CORS
            cors = aiohttp_cors.setup(self.app, defaults={
                "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                    allow_methods="*"
                )
            })
            
            # เพิ่ม routes
            self.app.router.add_get('/', self.serve_index)
            self.app.router.add_get('/ws', self.websocket_handler)
            self.app.router.add_get('/api/status', self.api_status)
            self.app.router.add_post('/api/command', self.api_command)
            
            # ตั้งค่า CORS สำหรับทุก routes
            for route in list(self.app.router.routes()):
                cors.add(route)
            
            # เริ่ม server
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            
            logger.info(f"🌐 Web GUI started at http://{self.host}:{self.port}")
            
            # เริ่ม background updates
            self.running = True
            self.update_task = asyncio.create_task(self.background_updates())
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error starting web server: {e}")
            return False
    
    async def stop_server(self):
        """หยุด Web Server"""
        try:
            self.running = False
            
            if self.update_task:
                self.update_task.cancel()
            
            # ปิด WebSocket connections
            for ws in list(self.websocket_connections):
                await ws.close()
            
            if self.site:
                await self.site.stop()
            
            if self.runner:
                await self.runner.cleanup()
            
            logger.info("🛑 Web GUI stopped")
            
        except Exception as e:
            logger.error(f"❌ Error stopping web server: {e}")
    
    async def serve_index(self, request):
        """Serve HTML page"""
        html_content = self.get_html_template()
        return web.Response(text=html_content, content_type='text/html')
    
    async def websocket_handler(self, request):
        """Handle WebSocket connections"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self.websocket_connections.add(ws)
        logger.info(f"🔗 WebSocket connected. Total connections: {len(self.websocket_connections)}")
        
        try:
            # ส่งข้อมูลเริ่มต้น
            await self.send_initial_data(ws)
            
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    data = json.loads(msg.data)
                    await self.handle_websocket_message(ws, data)
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f'WebSocket error: {ws.exception()}')
                    
        except Exception as e:
            logger.error(f"❌ WebSocket error: {e}")
        finally:
            self.websocket_connections.discard(ws)
            logger.info(f"🔌 WebSocket disconnected. Total connections: {len(self.websocket_connections)}")
        
        return ws
    
    async def send_initial_data(self, ws):
        """ส่งข้อมูลเริ่มต้น"""
        try:
            initial_data = {
                'type': 'initial_data',
                'data': self.cached_data
            }
            await ws.send_str(json.dumps(initial_data))
        except Exception as e:
            logger.error(f"❌ Error sending initial data: {e}")
    
    async def handle_websocket_message(self, ws, data):
        """จัดการ WebSocket messages"""
        try:
            message_type = data.get('type')
            
            if message_type == 'ping':
                await ws.send_str(json.dumps({'type': 'pong'}))
            elif message_type == 'get_status':
                await ws.send_str(json.dumps({
                    'type': 'status_update',
                    'data': self.cached_data
                }))
            elif message_type == 'command':
                await self.handle_command(data.get('command'), data.get('params', {}))
                
        except Exception as e:
            logger.error(f"❌ Error handling WebSocket message: {e}")
    
    async def handle_command(self, command, params):
        """จัดการ commands"""
        try:
            if command == 'start_trading':
                if self.trading_system:
                    success = self.trading_system.start_trading()
                    await self.broadcast_message({
                        'type': 'command_result',
                        'command': command,
                        'success': success
                    })
            elif command == 'stop_trading':
                if self.trading_system:
                    self.trading_system.stop_trading()
                    await self.broadcast_message({
                        'type': 'command_result',
                        'command': command,
                        'success': True
                    })
            elif command == 'connect_mt5':
                if self.trading_system and hasattr(self.trading_system, 'mt5_connection'):
                    success = self.trading_system.mt5_connection.connect_mt5()
                    await self.broadcast_message({
                        'type': 'command_result',
                        'command': command,
                        'success': success
                    })
                    
        except Exception as e:
            logger.error(f"❌ Error handling command {command}: {e}")
    
    async def broadcast_message(self, message):
        """ส่งข้อความไปยัง WebSocket connections ทั้งหมด"""
        if not self.websocket_connections:
            return
        
        message_str = json.dumps(message)
        disconnected = set()
        
        for ws in self.websocket_connections:
            try:
                await ws.send_str(message_str)
            except Exception as e:
                logger.debug(f"WebSocket send error: {e}")
                disconnected.add(ws)
        
        # ลบ connections ที่ตัด
        self.websocket_connections -= disconnected
    
    async def background_updates(self):
        """Background updates loop"""
        while self.running:
            try:
                current_time = time.time()
                
                # อัพเดทข้อมูลต่างๆ
                await self.update_account_info(current_time)
                await self.update_trading_status(current_time)
                await self.update_positions(current_time)
                await self.update_position_status(current_time)
                await self.update_performance(current_time)
                await self.update_logs(current_time)
                
                # รอ 1 วินาทีก่อนรอบถัดไป
                await asyncio.sleep(1)
                
            except Exception as e:
                logger.error(f"❌ Error in background updates: {e}")
                await asyncio.sleep(5)
    
    async def update_account_info(self, current_time):
        """อัพเดทข้อมูลบัญชี"""
        try:
            last_update = self.last_updates.get('account_info', 0)
            if current_time - last_update < self.update_intervals['account_info']:
                return
            
            if self.trading_system and hasattr(self.trading_system, 'mt5_connection'):
                account_info = self.trading_system.mt5_connection.get_account_info()
                if account_info:
                    self.cached_data['account_info'] = account_info
                    await self.broadcast_message({
                        'type': 'account_update',
                        'data': account_info
                    })
            
            self.last_updates['account_info'] = current_time
            
        except Exception as e:
            logger.error(f"❌ Error updating account info: {e}")
    
    async def update_trading_status(self, current_time):
        """อัพเดทสถานะการเทรด"""
        try:
            last_update = self.last_updates.get('trading_status', 0)
            if current_time - last_update < self.update_intervals['trading_status']:
                return
            
            if self.trading_system:
                trading_status = {
                    'is_running': self.trading_system.is_running,
                    'active_positions': len(self.trading_system.order_manager.active_positions) if hasattr(self.trading_system, 'order_manager') else 0,
                    'total_profit': 0,
                    'daily_profit': 0,
                    'win_rate': 0,
                    'profit_factor': 0
                }
                
                # คำนวณ profit จาก positions
                if hasattr(self.trading_system, 'order_manager'):
                    positions = self.trading_system.order_manager.active_positions
                    if positions:
                        total_profit = sum(getattr(pos, 'profit', 0) for pos in positions)
                        profitable_count = sum(1 for pos in positions if getattr(pos, 'profit', 0) > 0)
                        
                        trading_status['total_profit'] = total_profit
                        trading_status['daily_profit'] = total_profit
                        trading_status['win_rate'] = (profitable_count / len(positions)) * 100 if positions else 0
                
                self.cached_data['trading_status'] = trading_status
                await self.broadcast_message({
                    'type': 'trading_status_update',
                    'data': trading_status
                })
            
            self.last_updates['trading_status'] = current_time
            
        except Exception as e:
            logger.error(f"❌ Error updating trading status: {e}")
    
    async def update_positions(self, current_time):
        """อัพเดท positions"""
        try:
            last_update = self.last_updates.get('positions', 0)
            if current_time - last_update < self.update_intervals['positions']:
                return
            
            positions_data = []
            
            if self.trading_system and hasattr(self.trading_system, 'order_manager'):
                positions = self.trading_system.order_manager.active_positions
                
                for pos in positions:
                    position_data = {
                        'ticket': getattr(pos, 'ticket', 0),
                        'symbol': getattr(pos, 'symbol', ''),
                        'type': 'BUY' if getattr(pos, 'type', 0) == 0 else 'SELL',
                        'volume': getattr(pos, 'volume', 0),
                        'price_open': getattr(pos, 'price_open', 0),
                        'price_current': getattr(pos, 'price_current', 0),
                        'profit': getattr(pos, 'profit', 0),
                        'swap': getattr(pos, 'swap', 0),
                        'comment': getattr(pos, 'comment', '')
                    }
                    
                    # คำนวณ profit percentage
                    if position_data['price_open'] > 0:
                        if position_data['type'] == 'BUY':
                            profit_pct = ((position_data['price_current'] - position_data['price_open']) / position_data['price_open']) * 100
                        else:
                            profit_pct = ((position_data['price_open'] - position_data['price_current']) / position_data['price_open']) * 100
                        position_data['profit_pct'] = profit_pct
                    else:
                        position_data['profit_pct'] = 0
                    
                    positions_data.append(position_data)
            
            self.cached_data['positions'] = positions_data
            await self.broadcast_message({
                'type': 'positions_update',
                'data': positions_data
            })
            
            self.last_updates['positions'] = current_time
            
        except Exception as e:
            logger.error(f"❌ Error updating positions: {e}")
    
    async def update_position_status(self, current_time):
        """อัพเดทสถานะ positions"""
        try:
            last_update = self.last_updates.get('position_status', 0)
            if current_time - last_update < self.update_intervals['position_status']:
                return
            
            status_data = {}
            
            if (self.trading_system and 
                hasattr(self.trading_system, 'status_manager') and 
                self.trading_system.status_manager):
                
                positions = self.trading_system.order_manager.active_positions
                if positions:
                    # วิเคราะห์สถานะ
                    status_results = self.trading_system.status_manager.analyze_all_positions(
                        positions=positions,
                        current_price=2650.0,  # Default price
                        zones=[],
                        market_condition='sideways'
                    )
                    
                    for ticket, status_obj in status_results.items():
                        status_data[ticket] = {
                            'status': status_obj.status,
                            'zone': status_obj.zone,
                            'relationships': status_obj.relationships,
                            'profit': status_obj.profit,
                            'direction': status_obj.direction
                        }
            
            self.cached_data['position_status'] = status_data
            await self.broadcast_message({
                'type': 'position_status_update',
                'data': status_data
            })
            
            self.last_updates['position_status'] = current_time
            
        except Exception as e:
            logger.error(f"❌ Error updating position status: {e}")
    
    async def update_performance(self, current_time):
        """อัพเดท performance metrics"""
        try:
            last_update = self.last_updates.get('performance', 0)
            if current_time - last_update < self.update_intervals['performance']:
                return
            
            performance_data = {
                'memory_usage': 0,
                'response_time': 0,
                'error_count': 0,
                'success_count': 0,
                'timestamp': datetime.now().isoformat()
            }
            
            # ดึงข้อมูล performance จาก system
            if hasattr(self.trading_system, 'performance_optimizer'):
                report = self.trading_system.performance_optimizer.get_performance_report()
                if report:
                    performance_data.update(report)
            
            self.cached_data['performance'] = performance_data
            await self.broadcast_message({
                'type': 'performance_update',
                'data': performance_data
            })
            
            self.last_updates['performance'] = current_time
            
        except Exception as e:
            logger.error(f"❌ Error updating performance: {e}")
    
    async def update_logs(self, current_time):
        """อัพเดท logs"""
        try:
            last_update = self.last_updates.get('logs', 0)
            if current_time - last_update < self.update_intervals['logs']:
                return
            
            # ดึง logs ล่าสุด (จำลอง)
            logs_data = [
                {
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'level': 'INFO',
                    'message': 'System running normally'
                }
            ]
            
            self.cached_data['logs'] = logs_data
            await self.broadcast_message({
                'type': 'logs_update',
                'data': logs_data
            })
            
            self.last_updates['logs'] = current_time
            
        except Exception as e:
            logger.error(f"❌ Error updating logs: {e}")
    
    async def api_status(self, request):
        """API endpoint สำหรับดึงสถานะ"""
        return web.json_response(self.cached_data)
    
    async def api_command(self, request):
        """API endpoint สำหรับส่ง commands"""
        try:
            data = await request.json()
            command = data.get('command')
            params = data.get('params', {})
            
            await self.handle_command(command, params)
            
            return web.json_response({'success': True})
            
        except Exception as e:
            logger.error(f"❌ API command error: {e}")
            return web.json_response({'success': False, 'error': str(e)})
    
    def get_html_template(self):
        """HTML template สำหรับ Web GUI"""
        return """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🚀 Enhanced 7D Smart Trading System - Web GUI</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a1a 0%, #2d2d2d 100%);
            color: #ffffff;
            min-height: 100vh;
        }
        
        .header {
            background: #1a1a1a;
            padding: 20px;
            border-bottom: 2px solid #00ff88;
            text-align: center;
        }
        
        .header h1 {
            color: #00ff88;
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .status-bar {
            background: #2d2d2d;
            padding: 10px 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #444;
        }
        
        .status-item {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        
        .status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background: #ff4444;
        }
        
        .status-indicator.connected {
            background: #00ff88;
        }
        
        .status-indicator.running {
            background: #00ff88;
        }
        
        .main-container {
            display: grid;
            grid-template-columns: 1fr 2fr;
            gap: 20px;
            padding: 20px;
            min-height: calc(100vh - 200px);
        }
        
        .control-panel {
            background: #2d2d2d;
            border-radius: 10px;
            padding: 20px;
            border: 1px solid #444;
        }
        
        .control-section {
            margin-bottom: 30px;
        }
        
        .control-section h3 {
            color: #00ff88;
            margin-bottom: 15px;
            font-size: 1.2em;
        }
        
        .button {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 14px;
            font-weight: bold;
            margin: 5px;
            transition: all 0.3s ease;
        }
        
        .button:hover {
            background: #45a049;
            transform: translateY(-2px);
        }
        
        .button.danger {
            background: #f44336;
        }
        
        .button.danger:hover {
            background: #da190b;
        }
        
        .button:disabled {
            background: #666;
            cursor: not-allowed;
        }
        
        .info-panel {
            background: #2d2d2d;
            border-radius: 10px;
            padding: 20px;
            border: 1px solid #444;
        }
        
        .info-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
        }
        
        .info-item {
            background: #1a1a1a;
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #00ff88;
        }
        
        .info-label {
            color: #ccc;
            font-size: 0.9em;
            margin-bottom: 5px;
        }
        
        .info-value {
            color: #fff;
            font-size: 1.1em;
            font-weight: bold;
        }
        
        .info-value.positive {
            color: #00ff88;
        }
        
        .info-value.negative {
            color: #ff4444;
        }
        
        .tabs {
            display: flex;
            background: #1a1a1a;
            border-radius: 10px 10px 0 0;
            overflow: hidden;
        }
        
        .tab {
            background: #2d2d2d;
            color: #ccc;
            padding: 15px 20px;
            cursor: pointer;
            border: none;
            flex: 1;
            transition: all 0.3s ease;
        }
        
        .tab.active {
            background: #00ff88;
            color: #1a1a1a;
        }
        
        .tab-content {
            background: #2d2d2d;
            padding: 20px;
            border-radius: 0 0 10px 10px;
            min-height: 400px;
        }
        
        .positions-table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        
        .positions-table th,
        .positions-table td {
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #444;
        }
        
        .positions-table th {
            background: #1a1a1a;
            color: #00ff88;
            font-weight: bold;
        }
        
        .positions-table tr:hover {
            background: #333;
        }
        
        .log-container {
            background: #1a1a1a;
            border-radius: 8px;
            padding: 15px;
            height: 300px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
        }
        
        .log-entry {
            margin-bottom: 5px;
            padding: 2px 0;
        }
        
        .log-entry.info {
            color: #00ff88;
        }
        
        .log-entry.warning {
            color: #ffaa00;
        }
        
        .log-entry.error {
            color: #ff4444;
        }
        
        .connection-status {
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 10px 20px;
            border-radius: 25px;
            font-weight: bold;
            z-index: 1000;
        }
        
        .connection-status.connected {
            background: #00ff88;
            color: #1a1a1a;
        }
        
        .connection-status.disconnected {
            background: #ff4444;
            color: white;
        }
        
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        
        .loading {
            animation: pulse 1.5s infinite;
        }
        
        @media (max-width: 768px) {
            .main-container {
                grid-template-columns: 1fr;
            }
            
            .info-grid {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🚀 Enhanced 7D Smart Trading System</h1>
        <p>Web-based GUI - Fast & Stable</p>
    </div>
    
    <div class="status-bar">
        <div class="status-item">
            <div class="status-indicator" id="mt5-status"></div>
            <span>MT5: <span id="mt5-text">Disconnected</span></span>
        </div>
        <div class="status-item">
            <div class="status-indicator" id="trading-status"></div>
            <span>Trading: <span id="trading-text">Stopped</span></span>
        </div>
        <div class="status-item">
            <span>Last Update: <span id="last-update">Never</span></span>
        </div>
    </div>
    
    <div class="connection-status disconnected" id="ws-status">
        Disconnected
    </div>
    
    <div class="main-container">
        <div class="control-panel">
            <div class="control-section">
                <h3>🔗 MT5 Connection</h3>
                <button class="button" id="connect-btn" onclick="sendCommand('connect_mt5')">
                    Connect MT5
                </button>
                <button class="button danger" id="disconnect-btn" onclick="sendCommand('disconnect_mt5')" disabled>
                    Disconnect
                </button>
            </div>
            
            <div class="control-section">
                <h3>🎯 Trading Control</h3>
                <button class="button" id="start-btn" onclick="sendCommand('start_trading')">
                    ▶️ Start Trading
                </button>
                <button class="button danger" id="stop-btn" onclick="sendCommand('stop_trading')" disabled>
                    ⏹️ Stop Trading
                </button>
            </div>
            
            <div class="control-section">
                <h3>🚨 Emergency</h3>
                <button class="button danger" onclick="sendCommand('close_all_positions')">
                    🛑 Close All Positions
                </button>
            </div>
        </div>
        
        <div class="info-panel">
            <div class="tabs">
                <button class="tab active" onclick="showTab('overview')">Overview</button>
                <button class="tab" onclick="showTab('positions')">Positions</button>
                <button class="tab" onclick="showTab('status')">Position Status</button>
                <button class="tab" onclick="showTab('performance')">Performance</button>
                <button class="tab" onclick="showTab('logs')">Logs</button>
            </div>
            
            <div id="overview" class="tab-content">
                <h3>📊 Account Information</h3>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Balance</div>
                        <div class="info-value" id="balance">$0.00</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Equity</div>
                        <div class="info-value" id="equity">$0.00</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Margin</div>
                        <div class="info-value" id="margin">$0.00</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Free Margin</div>
                        <div class="info-value" id="free-margin">$0.00</div>
                    </div>
                </div>
                
                <h3 style="margin-top: 30px;">📈 Trading Status</h3>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Active Positions</div>
                        <div class="info-value" id="active-positions">0</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Total P&L</div>
                        <div class="info-value" id="total-pnl">$0.00</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Win Rate</div>
                        <div class="info-value" id="win-rate">0%</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Profit Factor</div>
                        <div class="info-value" id="profit-factor">0.00</div>
                    </div>
                </div>
            </div>
            
            <div id="positions" class="tab-content" style="display: none;">
                <h3>📋 Positions</h3>
                <table class="positions-table">
                    <thead>
                        <tr>
                            <th>Ticket</th>
                            <th>Symbol</th>
                            <th>Type</th>
                            <th>Volume</th>
                            <th>Open Price</th>
                            <th>Current Price</th>
                            <th>Profit</th>
                            <th>Profit %</th>
                        </tr>
                    </thead>
                    <tbody id="positions-table-body">
                        <tr>
                            <td colspan="8" style="text-align: center; color: #666;">
                                No positions found
                            </td>
                        </tr>
                    </tbody>
                </table>
            </div>
            
            <div id="status" class="tab-content" style="display: none;">
                <h3>🎯 Position Status</h3>
                <div id="position-status-container">
                    <p style="color: #666; text-align: center;">
                        Position status will be displayed here
                    </p>
                </div>
            </div>
            
            <div id="performance" class="tab-content" style="display: none;">
                <h3>📊 Performance Metrics</h3>
                <div class="info-grid">
                    <div class="info-item">
                        <div class="info-label">Memory Usage</div>
                        <div class="info-value" id="memory-usage">0 MB</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Response Time</div>
                        <div class="info-value" id="response-time">0 ms</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Error Count</div>
                        <div class="info-value" id="error-count">0</div>
                    </div>
                    <div class="info-item">
                        <div class="info-label">Success Rate</div>
                        <div class="info-value" id="success-rate">0%</div>
                    </div>
                </div>
            </div>
            
            <div id="logs" class="tab-content" style="display: none;">
                <h3>📝 System Logs</h3>
                <div class="log-container" id="log-container">
                    <div class="log-entry info">System started...</div>
                </div>
            </div>
        </div>
    </div>

    <script>
        let ws = null;
        let reconnectInterval = null;
        let data = {};
        
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws`;
            
            ws = new WebSocket(wsUrl);
            
            ws.onopen = function(event) {
                console.log('WebSocket connected');
                updateConnectionStatus(true);
                clearInterval(reconnectInterval);
            };
            
            ws.onmessage = function(event) {
                try {
                    const message = JSON.parse(event.data);
                    handleWebSocketMessage(message);
                } catch (e) {
                    console.error('Error parsing WebSocket message:', e);
                }
            };
            
            ws.onclose = function(event) {
                console.log('WebSocket disconnected');
                updateConnectionStatus(false);
                
                // Auto-reconnect after 3 seconds
                reconnectInterval = setInterval(connectWebSocket, 3000);
            };
            
            ws.onerror = function(error) {
                console.error('WebSocket error:', error);
            };
        }
        
        function updateConnectionStatus(connected) {
            const statusEl = document.getElementById('ws-status');
            if (connected) {
                statusEl.textContent = 'Connected';
                statusEl.className = 'connection-status connected';
            } else {
                statusEl.textContent = 'Disconnected';
                statusEl.className = 'connection-status disconnected';
            }
        }
        
        function handleWebSocketMessage(message) {
            switch (message.type) {
                case 'initial_data':
                    data = message.data;
                    updateUI();
                    break;
                case 'account_update':
                    data.account_info = message.data;
                    updateAccountInfo();
                    break;
                case 'trading_status_update':
                    data.trading_status = message.data;
                    updateTradingStatus();
                    break;
                case 'positions_update':
                    data.positions = message.data;
                    updatePositions();
                    break;
                case 'position_status_update':
                    data.position_status = message.data;
                    updatePositionStatus();
                    break;
                case 'performance_update':
                    data.performance = message.data;
                    updatePerformance();
                    break;
                case 'logs_update':
                    data.logs = message.data;
                    updateLogs();
                    break;
                case 'command_result':
                    handleCommandResult(message.command, message.success);
                    break;
            }
            
            document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
        }
        
        function updateUI() {
            updateAccountInfo();
            updateTradingStatus();
            updatePositions();
            updatePositionStatus();
            updatePerformance();
            updateLogs();
        }
        
        function updateAccountInfo() {
            const accountInfo = data.account_info || {};
            
            document.getElementById('balance').textContent = `$${(accountInfo.balance || 0).toFixed(2)}`;
            document.getElementById('equity').textContent = `$${(accountInfo.equity || 0).toFixed(2)}`;
            document.getElementById('margin').textContent = `$${(accountInfo.margin || 0).toFixed(2)}`;
            document.getElementById('free-margin').textContent = `$${(accountInfo.margin_free || 0).toFixed(2)}`;
        }
        
        function updateTradingStatus() {
            const tradingStatus = data.trading_status || {};
            
            // Update status indicators
            const mt5Status = document.getElementById('mt5-status');
            const tradingStatusEl = document.getElementById('trading-status');
            const mt5Text = document.getElementById('mt5-text');
            const tradingText = document.getElementById('trading-text');
            
            // MT5 Status (simplified - assume connected if we have data)
            mt5Status.className = 'status-indicator connected';
            mt5Text.textContent = 'Connected';
            
            // Trading Status
            if (tradingStatus.is_running) {
                tradingStatusEl.className = 'status-indicator running';
                tradingText.textContent = 'Running';
                document.getElementById('start-btn').disabled = true;
                document.getElementById('stop-btn').disabled = false;
            } else {
                tradingStatusEl.className = 'status-indicator';
                tradingText.textContent = 'Stopped';
                document.getElementById('start-btn').disabled = false;
                document.getElementById('stop-btn').disabled = true;
            }
            
            // Update trading metrics
            document.getElementById('active-positions').textContent = tradingStatus.active_positions || 0;
            
            const totalPnl = document.getElementById('total-pnl');
            const pnlValue = tradingStatus.total_profit || 0;
            totalPnl.textContent = `$${pnlValue.toFixed(2)}`;
            totalPnl.className = `info-value ${pnlValue >= 0 ? 'positive' : 'negative'}`;
            
            document.getElementById('win-rate').textContent = `${(tradingStatus.win_rate || 0).toFixed(1)}%`;
            document.getElementById('profit-factor').textContent = (tradingStatus.profit_factor || 0).toFixed(2);
        }
        
        function updatePositions() {
            const positions = data.positions || [];
            const tbody = document.getElementById('positions-table-body');
            
            if (positions.length === 0) {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; color: #666;">No positions found</td></tr>';
                return;
            }
            
            tbody.innerHTML = positions.map(pos => `
                <tr>
                    <td>#${pos.ticket}</td>
                    <td>${pos.symbol}</td>
                    <td>${pos.type}</td>
                    <td>${pos.volume}</td>
                    <td>${pos.price_open.toFixed(5)}</td>
                    <td>${pos.price_current.toFixed(5)}</td>
                    <td class="${pos.profit >= 0 ? 'positive' : 'negative'}">$${pos.profit.toFixed(2)}</td>
                    <td class="${pos.profit_pct >= 0 ? 'positive' : 'negative'}">${pos.profit_pct.toFixed(2)}%</td>
                </tr>
            `).join('');
        }
        
        function updatePositionStatus() {
            const positionStatus = data.position_status || {};
            const container = document.getElementById('position-status-container');
            
            if (Object.keys(positionStatus).length === 0) {
                container.innerHTML = '<p style="color: #666; text-align: center;">No position status data</p>';
                return;
            }
            
            container.innerHTML = Object.entries(positionStatus).map(([ticket, status]) => `
                <div class="info-item" style="margin-bottom: 15px;">
                    <div class="info-label">Position #${ticket}</div>
                    <div class="info-value">${status.status}</div>
                    <div style="font-size: 0.9em; color: #ccc; margin-top: 5px;">
                        Profit: $${status.profit.toFixed(2)} | Direction: ${status.direction}
                    </div>
                </div>
            `).join('');
        }
        
        function updatePerformance() {
            const performance = data.performance || {};
            
            document.getElementById('memory-usage').textContent = `${(performance.memory_usage || 0).toFixed(1)} MB`;
            document.getElementById('response-time').textContent = `${(performance.response_time || 0).toFixed(1)} ms`;
            document.getElementById('error-count').textContent = performance.error_count || 0;
            document.getElementById('success-rate').textContent = `${(performance.success_rate || 0).toFixed(1)}%`;
        }
        
        function updateLogs() {
            const logs = data.logs || [];
            const container = document.getElementById('log-container');
            
            container.innerHTML = logs.map(log => `
                <div class="log-entry ${log.level.toLowerCase()}">
                    [${log.timestamp}] ${log.level}: ${log.message}
                </div>
            `).join('');
            
            // Auto-scroll to bottom
            container.scrollTop = container.scrollHeight;
        }
        
        function sendCommand(command, params = {}) {
            if (ws && ws.readyState === WebSocket.OPEN) {
                ws.send(JSON.stringify({
                    type: 'command',
                    command: command,
                    params: params
                }));
            } else {
                alert('WebSocket not connected');
            }
        }
        
        function handleCommandResult(command, success) {
            if (success) {
                console.log(`Command ${command} executed successfully`);
            } else {
                alert(`Command ${command} failed`);
            }
        }
        
        function showTab(tabName) {
            // Hide all tab contents
            const contents = document.querySelectorAll('.tab-content');
            contents.forEach(content => content.style.display = 'none');
            
            // Remove active class from all tabs
            const tabs = document.querySelectorAll('.tab');
            tabs.forEach(tab => tab.classList.remove('active'));
            
            // Show selected tab content
            document.getElementById(tabName).style.display = 'block';
            
            // Add active class to clicked tab
            event.target.classList.add('active');
        }
        
        // Connect WebSocket when page loads
        document.addEventListener('DOMContentLoaded', function() {
            connectWebSocket();
            
            // Send ping every 30 seconds to keep connection alive
            setInterval(() => {
                if (ws && ws.readyState === WebSocket.OPEN) {
                    ws.send(JSON.stringify({type: 'ping'}));
                }
            }, 30000);
        });
    </script>
</body>
</html>
        """
    
    def run(self):
        """Run the web server (blocking)"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            # เริ่ม server
            loop.run_until_complete(self.start_server())
            
            # รัน server
            loop.run_forever()
            
        except KeyboardInterrupt:
            logger.info("🛑 Shutting down web server...")
            loop.run_until_complete(self.stop_server())
        except Exception as e:
            logger.error(f"❌ Error running web server: {e}")
        finally:
            loop.close()


def create_web_gui(trading_system, host='localhost', port=8080):
    """สร้าง Web GUI instance"""
    return WebTradingGUI(trading_system, host, port)


# สำหรับใช้แทน Tkinter GUI
if __name__ == "__main__":
    # ตัวอย่างการใช้งาน
    import logging
    
    logging.basicConfig(level=logging.INFO)
    
    # สร้าง Web GUI (ไม่ต้องมี trading_system จริงสำหรับทดสอบ)
    web_gui = create_web_gui(None, host='0.0.0.0', port=8080)
    web_gui.run()
