from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.utils import timezone
from .models import Conversation, Message, UserPresence
from .serializers import MessageSerializer
import json


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        
        if self.user.is_anonymous:
            await self.close()
            return
        
        self.conversation_id = self.scope['url_route']['kwargs']['conversation_id']
        self.room_group_name = f'chat_{self.conversation_id}'
        
        # Check if user is participant
        is_participant = await self.check_participant()
        if not is_participant:
            await self.close()
            return
        
        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        
        await self.accept()
        
        # Update presence
        await self.update_presence()
        
        # Notify others user joined
        await self.channel_layer.group_send(
            self.room_group_name,
            {
                'type': 'user_joined',
                'user_id': self.user.id,
                'username': self.user.username,
            }
        )
    
    async def disconnect(self, close_code):
        if hasattr(self, 'room_group_name'):
            # Leave room group
            await self.channel_layer.group_discard(
                self.room_group_name,
                self.channel_name
            )
            
            # Notify others user left
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'user_left',
                    'user_id': self.user.id,
                    'username': self.user.username,
                }
            )
    
    async def receive_json(self, content):
        message_type = content.get('type')
        
        if message_type == 'chat_message':
            # Save message to database
            text = content.get('text', '').strip()
            if not text:
                return
            
            message = await self.save_message(text)
            
            # Send message to room group
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'chat_message',
                    'message': await self.serialize_message(message),
                }
            )
        
        elif message_type == 'typing':
            # Broadcast typing indicator
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'typing_indicator',
                    'user_id': self.user.id,
                    'username': self.user.username,
                    'is_typing': content.get('is_typing', True),
                }
            )
        
        elif message_type == 'read_receipt':
            # Mark message as read
            message_id = content.get('message_id')
            if message_id:
                await self.mark_message_read(message_id)
                
                # Notify sender
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'read_receipt',
                        'message_id': message_id,
                        'user_id': self.user.id,
                        'username': self.user.username,
                    }
                )
        
        elif message_type == 'message_delivered':
            # Mark message as delivered
            message_id = content.get('message_id')
            if message_id:
                # Notify sender
                await self.channel_layer.group_send(
                    self.room_group_name,
                    {
                        'type': 'message_delivered',
                        'message_id': message_id,
                        'user_id': self.user.id,
                    }
                )
    
    # Handlers for different message types
    async def chat_message(self, event):
        """Send chat message to WebSocket"""
        await self.send_json(event)
    
    async def typing_indicator(self, event):
        """Send typing indicator to WebSocket (except to the user who is typing)"""
        if event['user_id'] != self.user.id:
            await self.send_json(event)
    
    async def user_joined(self, event):
        """Notify when user joins"""
        if event['user_id'] != self.user.id:
            await self.send_json(event)
    
    async def user_left(self, event):
        """Notify when user leaves"""
        if event['user_id'] != self.user.id:
            await self.send_json(event)
    
    async def read_receipt(self, event):
        """Send read receipt to WebSocket"""
        await self.send_json(event)
    
    async def message_delivered(self, event):
        """Send delivery confirmation to WebSocket"""
        await self.send_json(event)
    
    # Database operations
    @database_sync_to_async
    def check_participant(self):
        """Check if user is participant in conversation"""
        return Conversation.objects.filter(
            id=self.conversation_id,
            participants=self.user
        ).exists()
    
    @database_sync_to_async
    def save_message(self, text):
        """Save message to database"""
        conversation = Conversation.objects.get(id=self.conversation_id)
        message = Message.objects.create(
            conversation=conversation,
            sender=self.user,
            text=text,
            msg_type='text'
        )
        conversation.save()  # Update conversation timestamp
        return message
    
    @database_sync_to_async
    def serialize_message(self, message):
        """Serialize message for JSON response"""
        return MessageSerializer(message).data
    
    @database_sync_to_async
    def mark_message_read(self, message_id):
        """Mark message as read"""
        try:
            message = Message.objects.get(
                id=message_id,
                conversation_id=self.conversation_id
            )
            # You can add read tracking here if needed
            # For now, just acknowledge the read receipt
        except Message.DoesNotExist:
            pass
    
    @database_sync_to_async
    def update_presence(self):
        """Update user's last seen timestamp"""
        UserPresence.objects.update_or_create(
            user=self.user,
            defaults={'last_seen': timezone.now()}
        )
