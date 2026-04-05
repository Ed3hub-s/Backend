from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async


class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        self.room_group_name = f'notifications_{self.user.id}'
        
        # Join notification group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
    
    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
    
    async def receive_json(self, content):
        """Handle messages from WebSocket"""
        message_type = content.get('type')
        
        if message_type == 'mark_read':
            notification_id = content.get('notification_id')
            await self.mark_notification_read(notification_id)
    
    async def notification_message(self, event):
        """Send notification to WebSocket"""
        await self.send_json({
            'type': 'notification',
            'notification': event['notification']
        })
    
    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark notification as read"""
        from .models import Notification
        from django.utils import timezone
        
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient=self.user
            )
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
        except Notification.DoesNotExist:
            pass
