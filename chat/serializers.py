from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Conversation, Message, Reaction


class ParticipantSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('id', 'username', 'full_name', 'avatar')

    def get_full_name(self, obj):
        return f'{obj.first_name} {obj.last_name}'.strip() or obj.username

    def get_avatar(self, obj):
        try:
            if obj.profile.avatar:
                request = self.context.get('request')
                return request.build_absolute_uri(obj.profile.avatar.url) if request else obj.profile.avatar.url
        except Exception:
            pass
        return None


class ReactionSerializer(serializers.ModelSerializer):
    user_id = serializers.IntegerField(source='user.id', read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model = Reaction
        fields = ('id', 'user_id', 'username', 'emoji')


class ReplySnippetSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = ('id', 'sender_name', 'text', 'msg_type')

    def get_sender_name(self, obj):
        return f'{obj.sender.first_name} {obj.sender.last_name}'.strip() or obj.sender.username


class MessageSerializer(serializers.ModelSerializer):
    sender = ParticipantSerializer(read_only=True)
    reactions = ReactionSerializer(many=True, read_only=True)
    reply_to = ReplySnippetSerializer(read_only=True)
    reply_to_id = serializers.PrimaryKeyRelatedField(
        queryset=Message.objects.all(), source='reply_to', write_only=True, required=False, allow_null=True
    )
    file_url = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = (
            'id', 'conversation', 'sender', 'msg_type', 'text',
            'file', 'file_url', 'file_name',
            'reply_to', 'reply_to_id', 'reactions', 'is_deleted', 'created_at',
        )
        read_only_fields = ('id', 'sender', 'created_at', 'is_deleted')
        extra_kwargs = {'file': {'write_only': True}, 'conversation': {'read_only': True}}

    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            return request.build_absolute_uri(obj.file.url) if request else obj.file.url
        return None

    def get_file_name(self, obj):
        if obj.file:
            return obj.file.name.split('/')[-1]
        return None


class ConversationSerializer(serializers.ModelSerializer):
    participants = ParticipantSerializer(many=True, read_only=True)
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()
    other_user = serializers.SerializerMethodField()

    class Meta:
        model = Conversation
        fields = ('id', 'participants', 'other_user', 'last_message', 'unread_count', 'updated_at')

    def get_other_user(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        other = obj.participants.exclude(id=request.user.id).first()
        if other:
            return ParticipantSerializer(other, context=self.context).data
        return None

    def get_last_message(self, obj):
        msg = obj.messages.filter(is_deleted=False).last()
        if msg:
            return {
                'text': msg.text if msg.msg_type == 'text' else f'[{msg.msg_type}]',
                'created_at': msg.created_at,
                'sender_id': msg.sender_id,
            }
        return None

    def get_unread_count(self, obj):
        return 0
