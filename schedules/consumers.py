"""WebSocket consumer for schedule updates."""
from common.consumers import BaseConsumer


class SchedulesConsumer(BaseConsumer):
    """Handles real-time schedule updates."""
    group_name = "schedules_updates"

    async def handle_message(self, data):
        """Handle incoming messages from schedule consumers"""
        message_type = data.get("type")
        # Handler logic will be implemented in Phase 5
        pass
