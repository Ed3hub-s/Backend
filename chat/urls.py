from django.urls import path
from .views import (
    ConversationListView, StartConversationView,
    MessageListView, SendMessageView,
    DeleteMessageView, ReactMessageView,
    HeartbeatView, PresenceView, UnreadCountView,
)

urlpatterns = [
    path('conversations/', ConversationListView.as_view(), name='conversations'),
    path('conversations/start/', StartConversationView.as_view(), name='start-conversation'),
    path('conversations/<int:conversation_id>/messages/', MessageListView.as_view(), name='messages'),
    path('conversations/<int:conversation_id>/send/', SendMessageView.as_view(), name='send-message'),
    path('messages/<int:message_id>/delete/', DeleteMessageView.as_view(), name='delete-message'),
    path('messages/<int:message_id>/react/', ReactMessageView.as_view(), name='react-message'),
    path('presence/heartbeat/', HeartbeatView.as_view(), name='presence-heartbeat'),
    path('presence/', PresenceView.as_view(), name='presence'),
    path('unread/', UnreadCountView.as_view(), name='unread-count'),
]
