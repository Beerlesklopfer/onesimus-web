"""WebSocket consumer for jobs real-time updates."""
from common.consumers import BaseConsumer


class JobsConsumer(BaseConsumer):
    """Handles real-time job status updates."""
    group_name = "jobs_updates"

    async def handle_message(self, data):
        """Handle incoming messages from jobs consumers"""
        message_type = data.get("type")
        # Handler logic will be implemented in Phase 3
        pass
