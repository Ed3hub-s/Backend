from unfold.admin import ModelAdmin
from django.contrib import admin
from .models import Conversation, Message, Reaction


@admin.register(Conversation)
class ConversationAdmin(ModelAdmin):
    list_display = ('id', 'participant_names', 'updated_at')
    readonly_fields = ('created_at', 'updated_at')

    def participant_names(self, obj):
        return ', '.join(u.username for u in obj.participants.all())
    participant_names.short_description = 'Participants'


@admin.register(Message)
class MessageAdmin(ModelAdmin):
    list_display = ('id', 'sender', 'conversation', 'msg_type', 'short_text', 'is_deleted', 'created_at')
    list_filter = ('msg_type', 'is_deleted')
    readonly_fields = ('created_at',)

    def short_text(self, obj):
        return obj.text[:60]
    short_text.short_description = 'Text'


@admin.register(Reaction)
class ReactionAdmin(ModelAdmin):
    list_display = ('id', 'user', 'message', 'emoji')
