"""
WebSocket consumers for real-time updates.
Handles WebSocket connections and message broadcasting.
"""

import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.layers import get_channel_layer


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Consumer for general app notifications.
    Broadcasts to all connected clients when events occur.
    """
    async def connect(self):
        self.user = self.scope["user"]
        await self.channel_layer.group_add("notifications", self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard("notifications", self.channel_name)

    async def receive(self, text_data):
        """Handle incoming messages (echo back for testing)"""
        data = json.loads(text_data)
        await self.send(text_data=json.dumps({"type": "notification", "data": data}))

    async def notification_message(self, event):
        """Handle broadcast messages"""
        await self.send(text_data=json.dumps(event["message"]))


class BaseConsumer(AsyncWebsocketConsumer):
    """
    Base WebSocket consumer for real-time updates.
    Subclasses should set group_name and handle specific events.
    """
    group_name = None

    async def connect(self):
        if self.group_name:
            await self.channel_layer.group_add(self.group_name, self.channel_name)
        self.user = self.scope["user"]
        await self.accept()

    async def disconnect(self, close_code):
        if self.group_name:
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def receive(self, text_data):
        """Handle incoming messages"""
        try:
            data = json.loads(text_data)
            await self.handle_message(data)
        except json.JSONDecodeError:
            await self.send_error("Invalid JSON")

    async def handle_message(self, data):
        """Override in subclasses to handle specific message types"""
        pass

    async def send_error(self, error_message):
        """Send error message to client"""
        await self.send(text_data=json.dumps({
            "type": "error",
            "message": error_message
        }))

    async def update_event(self, event):
        """Handle broadcast events"""
        await self.send(text_data=json.dumps(event["message"]))
