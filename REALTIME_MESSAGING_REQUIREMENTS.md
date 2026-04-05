# Real-Time Messaging System - Requirements & Implementation Guide

## 📊 Current State Analysis

### ✅ What's Already Implemented:

1. **Models** (chat/models.py)
   - Conversation (many-to-many participants)
   - Message (text, image, file, link types)
   - Reaction (emoji reactions)
   - UserPresence (online/offline status)

2. **API Endpoints** (chat/urls.py)
   - `GET /api/chat/conversations/` - List conversations
   - `POST /api/chat/conversations/start/` - Start new conversation
   - `GET /api/chat/conversations/<id>/messages/` - Get messages
   - `POST /api/chat/conversations/<id>/send/` - Send message
   - `DELETE /api/chat/messages/<id>/delete/` - Delete message
   - `POST /api/chat/messages/<id>/react/` - React to message
   - `POST /api/chat/presence/heartbeat/` - Update online status
   - `GET /api/chat/presence/` - Check user online status
   - `GET /api/chat/unread/` - Get unread count

3. **Features**
   - Text messages
   - Image uploads
   - File uploads (max 10MB, no videos)
   - Link detection
   - Message replies
   - Emoji reactions
   - Message deletion
   - Online/offline presence

### ❌ What's Missing for Real-Time:

1. **WebSocket Consumer** - No real-time message delivery
2. **WebSocket Routing** - No WebSocket endpoints configured
3. **Frontend WebSocket Client** - No real-time connection
4. **Typing Indicators** - No "user is typing..." feature
5. **Read Receipts** - No message read status
6. **Message Delivery Status** - No sent/delivered/read indicators
7. **Push Notifications** - No notification when new message arrives

---

## 🏗️ What's Needed for Real-Time Messaging

### 1. Backend Requirements

#### A. WebSocket Consumer (chat/consumers.py)

**Purpose**: Handle real-time WebSocket connections for chat

**Features Needed**:
- Connect/disconnect handling
- Join conversation rooms
- Send/receive messages in real-time
- Typing indicators
- Online presence updates
- Message read receipts
- Delivery confirmations

#### B. WebSocket Routing (chat/routing.py)

**Purpose**: Define WebSocket URL patterns

**Endpoints Needed**:
- `ws://localhost:8000/ws/chat/<conversation_id>/` - Chat room connection

#### C. Enhanced Models

**Additional Fields Needed**:
- Message.delivered_to (ManyToMany to User) - Track delivery
- Message.read_by (ManyToMany to User) - Track read status
- Message.delivered_at (DateTime)
- Message.read_at (DateTime)

#### D. Redis (Already configured ✅)

**Purpose**: Channel layer for WebSocket communication
- Already set up in settings.py
- Already in docker-compose.yml

---

### 2. Frontend Requirements

#### A. WebSocket Hook (useChat.ts)

**Purpose**: Manage WebSocket connection and chat state

**Features Needed**:
- Connect to WebSocket
- Send messages
- Receive messages in real-time
- Handle typing indicators
- Handle presence updates
- Handle read receipts
- Reconnection logic

#### B. Chat Components

**Components Needed**:
- ChatWindow - Main chat interface
- MessageList - Display messages
- MessageInput - Send messages
- TypingIndicator - Show "user is typing..."
- OnlineStatus - Show online/offline badge
- MessageStatus - Show sent/delivered/read status

#### C. Dependencies

**Already Installed**:
- React/Next.js ✅
- date-fns ✅ (for message timestamps)

**Need to Install**:
- None (native WebSocket API)

---

## 🔧 Implementation Steps

### Phase 1: Backend WebSocket Setup

#### Step 1: Create WebSocket Consumer

```python
# Backend/chat/consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import User
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
            }
        )
    
    async def receive_json(self, content):
        message_type = content.get('type')
        
        if message_type == 'chat_message':
            # Save message to database
            message = await self.save_message(content.get('text'))
            
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
            # Mark messages as read
            message_id = content.get('message_id')
            await self.mark_message_read(message_id)
            
            # Notify sender
            await self.channel_layer.group_send(
                self.room_group_name,
                {
                    'type': 'read_receipt',
                    'message_id': message_id,
                    'user_id': self.user.id,
                }
            )
    
    # Handlers for different message types
    async def chat_message(self, event):
        await self.send_json(event)
    
    async def typing_indicator(self, event):
        # Don't send typing indicator to the user who is typing
        if event['user_id'] != self.user.id:
            await self.send_json(event)
    
    async def user_joined(self, event):
        await self.send_json(event)
    
    async def user_left(self, event):
        await self.send_json(event)
    
    async def read_receipt(self, event):
        await self.send_json(event)
    
    # Database operations
    @database_sync_to_async
    def check_participant(self):
        return Conversation.objects.filter(
            id=self.conversation_id,
            participants=self.user
        ).exists()
    
    @database_sync_to_async
    def save_message(self, text):
        conversation = Conversation.objects.get(id=self.conversation_id)
        message = Message.objects.create(
            conversation=conversation,
            sender=self.user,
            text=text,
            msg_type='text'
        )
        return message
    
    @database_sync_to_async
    def serialize_message(self, message):
        from .serializers import MessageSerializer
        return MessageSerializer(message).data
    
    @database_sync_to_async
    def mark_message_read(self, message_id):
        try:
            message = Message.objects.get(id=message_id)
            # Add read tracking logic here
        except Message.DoesNotExist:
            pass
    
    @database_sync_to_async
    def update_presence(self):
        from django.utils import timezone
        UserPresence.objects.update_or_create(
            user=self.user,
            defaults={'last_seen': timezone.now()}
        )
```

#### Step 2: Create WebSocket Routing

```python
# Backend/chat/routing.py
from django.urls import path
from .consumers import ChatConsumer

websocket_urlpatterns = [
    path('ws/chat/<int:conversation_id>/', ChatConsumer.as_asgi()),
]
```

#### Step 3: Update ASGI Configuration

```python
# Backend/core/asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from notifications.routing import websocket_urlpatterns as notification_patterns
from chat.routing import websocket_urlpatterns as chat_patterns

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(
            notification_patterns + chat_patterns
        )
    ),
})
```

---

### Phase 2: Frontend WebSocket Setup

#### Step 1: Create useChat Hook

```typescript
// Frontend/src/hooks/useChat.ts
import { useState, useEffect, useCallback, useRef } from 'react';

interface Message {
  id: number;
  sender: {
    id: number;
    username: string;
  };
  text: string;
  msg_type: string;
  created_at: string;
  is_deleted: boolean;
}

interface TypingUser {
  user_id: number;
  username: string;
}

export const useChat = (conversationId: number) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [typingUsers, setTypingUsers] = useState<TypingUser[]>([]);
  const [onlineUsers, setOnlineUsers] = useState<number[]>([]);
  const [connected, setConnected] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';

  // Connect to WebSocket
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token || !conversationId) return;

    const ws = new WebSocket(`${WS_URL}/ws/chat/${conversationId}/?token=${token}`);

    ws.onopen = () => {
      console.log('Chat WebSocket connected');
      setConnected(true);
    };

    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'chat_message':
          setMessages(prev => [...prev, data.message]);
          break;

        case 'typing_indicator':
          if (data.is_typing) {
            setTypingUsers(prev => {
              if (!prev.find(u => u.user_id === data.user_id)) {
                return [...prev, { user_id: data.user_id, username: data.username }];
              }
              return prev;
            });
          } else {
            setTypingUsers(prev => prev.filter(u => u.user_id !== data.user_id));
          }
          break;

        case 'user_joined':
          setOnlineUsers(prev => [...new Set([...prev, data.user_id])]);
          break;

        case 'user_left':
          setOnlineUsers(prev => prev.filter(id => id !== data.user_id));
          break;

        case 'read_receipt':
          // Update message read status
          setMessages(prev =>
            prev.map(msg =>
              msg.id === data.message_id
                ? { ...msg, read_by: [...(msg.read_by || []), data.user_id] }
                : msg
            )
          );
          break;
      }
    };

    ws.onerror = (error) => {
      console.error('Chat WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('Chat WebSocket disconnected');
      setConnected(false);
    };

    wsRef.current = ws;

    return () => {
      ws.close();
    };
  }, [conversationId, WS_URL]);

  // Send message
  const sendMessage = useCallback((text: string) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'chat_message',
        text: text,
      }));
    }
  }, []);

  // Send typing indicator
  const sendTyping = useCallback((isTyping: boolean) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'typing',
        is_typing: isTyping,
      }));
    }
  }, []);

  // Handle typing with auto-stop
  const handleTyping = useCallback(() => {
    sendTyping(true);

    if (typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }

    typingTimeoutRef.current = setTimeout(() => {
      sendTyping(false);
    }, 3000);
  }, [sendTyping]);

  // Send read receipt
  const markAsRead = useCallback((messageId: number) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'read_receipt',
        message_id: messageId,
      }));
    }
  }, []);

  return {
    messages,
    typingUsers,
    onlineUsers,
    connected,
    sendMessage,
    handleTyping,
    markAsRead,
  };
};
```

#### Step 2: Create Chat Components

```typescript
// Frontend/src/components/ChatWindow.tsx
'use client';

import { useChat } from '@/hooks/useChat';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { TypingIndicator } from './TypingIndicator';

interface ChatWindowProps {
  conversationId: number;
  otherUser: {
    id: number;
    username: string;
  };
}

export const ChatWindow = ({ conversationId, otherUser }: ChatWindowProps) => {
  const {
    messages,
    typingUsers,
    onlineUsers,
    connected,
    sendMessage,
    handleTyping,
    markAsRead,
  } = useChat(conversationId);

  const isOnline = onlineUsers.includes(otherUser.id);

  return (
    <div className="flex flex-col h-full bg-white rounded-lg shadow">
      {/* Header */}
      <div className="p-4 border-b flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="w-10 h-10 bg-blue-500 rounded-full flex items-center justify-center text-white font-semibold">
              {otherUser.username[0].toUpperCase()}
            </div>
            {isOnline && (
              <span className="absolute bottom-0 right-0 w-3 h-3 bg-green-500 border-2 border-white rounded-full" />
            )}
          </div>
          <div>
            <h3 className="font-semibold">{otherUser.username}</h3>
            <p className="text-sm text-gray-500">
              {isOnline ? 'Online' : 'Offline'}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
          <span className="text-xs text-gray-500">
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* Messages */}
      <MessageList messages={messages} onMessageVisible={markAsRead} />

      {/* Typing Indicator */}
      {typingUsers.length > 0 && (
        <TypingIndicator users={typingUsers} />
      )}

      {/* Input */}
      <MessageInput
        onSend={sendMessage}
        onTyping={handleTyping}
        disabled={!connected}
      />
    </div>
  );
};
```

---

## 📋 Complete Implementation Checklist

### Backend

- [ ] Install dependencies (channels, channels-redis, daphne, celery, redis)
- [ ] Create chat/consumers.py with ChatConsumer
- [ ] Create chat/routing.py with WebSocket URL patterns
- [ ] Update core/asgi.py to include chat routing
- [ ] Add message delivery/read tracking fields (optional)
- [ ] Test WebSocket connection

### Frontend

- [ ] Create hooks/useChat.ts
- [ ] Create components/ChatWindow.tsx
- [ ] Create components/MessageList.tsx
- [ ] Create components/MessageInput.tsx
- [ ] Create components/TypingIndicator.tsx
- [ ] Create components/OnlineStatus.tsx
- [ ] Test real-time messaging

### Infrastructure

- [x] Redis running (already in docker-compose)
- [x] Channels configured (already done)
- [x] ASGI server (Daphne already configured)

---

## 🚀 How Real-Time Works

### Message Flow:

1. **User A types message** → Frontend sends via WebSocket
2. **Backend receives** → Saves to database
3. **Backend broadcasts** → Sends to all users in conversation room
4. **User B receives** → Message appears instantly
5. **User B reads** → Read receipt sent back
6. **User A sees** → "Read" indicator appears

### Typing Indicator Flow:

1. **User A types** → Frontend sends typing event
2. **Backend broadcasts** → Sends to other users
3. **User B sees** → "User A is typing..." appears
4. **User A stops** → After 3 seconds, typing stops

### Presence Flow:

1. **User connects** → WebSocket opens
2. **Backend tracks** → User added to online list
3. **Others notified** → "User A joined" event
4. **User disconnects** → "User A left" event
5. **Status updates** → Online/offline badge changes

---

## 🎯 Key Differences: Polling vs WebSocket

### Current (Polling):
- Frontend calls API every X seconds
- High server load
- Delayed messages (up to X seconds)
- More bandwidth usage

### With WebSocket:
- Persistent connection
- Instant message delivery
- Low server load
- Minimal bandwidth
- Real-time typing indicators
- Real-time presence

---

## 📊 Performance Considerations

### Scalability:
- **Redis** handles channel layer (already configured)
- **Daphne** handles WebSocket connections (already configured)
- Can scale horizontally with multiple servers
- Redis Pub/Sub ensures messages reach all servers

### Optimization:
- Limit message history loaded (pagination)
- Compress WebSocket messages
- Debounce typing indicators
- Lazy load old messages

---

**Next Steps**: Implement the ChatConsumer and useChat hook to enable real-time messaging!
