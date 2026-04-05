import mimetypes
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q, Count
from django.utils import timezone
from rest_framework import status
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Conversation, Message, Reaction, UserPresence
from .serializers import ConversationSerializer, MessageSerializer, ReactionSerializer

BLOCKED_VIDEO_TYPES = [
    'video/mp4', 'video/mpeg', 'video/quicktime', 'video/x-msvideo',
    'video/x-matroska', 'video/webm', 'video/ogg',
]
ALLOWED_IMAGE_TYPES = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


def get_or_create_conversation(user_a, user_b):
    id_list = list(
        Conversation.objects
        .filter(participants=user_a)
        .filter(participants=user_b)
        .annotate(count=Count('participants'))
        .filter(count=2)
        .order_by('created_at')
        .values_list('id', flat=True)
    )
    if id_list:
        if len(id_list) > 1:
            Conversation.objects.filter(id__in=id_list[1:]).delete()
        return Conversation.objects.get(id=id_list[0])
    conv = Conversation.objects.create()
    conv.participants.add(user_a, user_b)
    return conv


class ConversationListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        convs = Conversation.objects.filter(participants=request.user).prefetch_related('participants', 'messages').distinct()
        serializer = ConversationSerializer(convs, many=True, context={'request': request})
        return Response(serializer.data)


class StartConversationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        other_id = request.data.get('user_id')
        if not other_id:
            return Response({'error': 'user_id required'}, status=400)
        try:
            other = User.objects.get(id=other_id)
        except User.DoesNotExist:
            return Response({'error': 'User not found'}, status=404)
        if other == request.user:
            return Response({'error': 'Cannot chat with yourself'}, status=400)
        conv = get_or_create_conversation(request.user, other)
        # Clean up any duplicates that may have slipped through, keep oldest
        duplicates = (
            Conversation.objects
            .filter(participants=request.user)
            .filter(participants=other)
            .annotate(count=Count('participants'))
            .filter(count=2)
            .order_by('created_at')
        )
        ids = list(duplicates.values_list('id', flat=True))
        if len(ids) > 1:
            Conversation.objects.filter(id__in=ids[1:]).delete()
            conv = Conversation.objects.get(id=ids[0])
        return Response(ConversationSerializer(conv, context={'request': request}).data)


class MessageListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):
        try:
            conv = Conversation.objects.get(id=conversation_id, participants=request.user)
        except Conversation.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        since_id = request.query_params.get('since_id')
        qs = conv.messages.filter(is_deleted=False).select_related('sender', 'reply_to__sender').prefetch_related('reactions__user')
        if since_id:
            qs = qs.filter(id__gt=since_id)

        serializer = MessageSerializer(qs, many=True, context={'request': request})
        return Response(serializer.data)


class SendMessageView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request, conversation_id):
        try:
            conv = Conversation.objects.get(id=conversation_id, participants=request.user)
        except Conversation.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        file = request.FILES.get('file')
        text = request.data.get('text', '').strip()
        msg_type = request.data.get('msg_type', 'text')
        reply_to_id = request.data.get('reply_to_id')

        if file:
            mime, _ = mimetypes.guess_type(file.name)
            mime = mime or file.content_type or ''
            if mime in BLOCKED_VIDEO_TYPES:
                return Response({'error': 'Video files are not allowed.'}, status=400)
            if file.size > MAX_FILE_SIZE:
                return Response({'error': 'File too large. Max 10MB.'}, status=400)
            msg_type = 'image' if mime in ALLOWED_IMAGE_TYPES else 'file'
        elif not text:
            return Response({'error': 'Message cannot be empty.'}, status=400)
        else:
            # auto-detect links
            words = text.split()
            if any(w.startswith('http://') or w.startswith('https://') or w.startswith('www.') for w in words):
                msg_type = 'link'
            else:
                msg_type = 'text'

        reply_to = None
        if reply_to_id:
            try:
                reply_to = Message.objects.get(id=reply_to_id, conversation=conv)
            except Message.DoesNotExist:
                pass

        msg = Message.objects.create(
            conversation=conv,
            sender=request.user,
            msg_type=msg_type,
            text=text,
            file=file,
            reply_to=reply_to,
        )
        conv.save()  # bump updated_at
        return Response(MessageSerializer(msg, context={'request': request}).data, status=201)


class DeleteMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, message_id):
        try:
            msg = Message.objects.get(id=message_id, sender=request.user)
        except Message.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)
        msg.is_deleted = True
        msg.text = 'This message was deleted.'
        msg.file = None
        msg.save()
        return Response({'status': 'deleted'})


class ReactMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, message_id):
        try:
            msg = Message.objects.get(id=message_id, conversation__participants=request.user)
        except Message.DoesNotExist:
            return Response({'error': 'Not found'}, status=404)

        emoji = request.data.get('emoji', '').strip()
        if not emoji:
            return Response({'error': 'emoji required'}, status=400)

        reaction, created = Reaction.objects.get_or_create(message=msg, user=request.user, defaults={'emoji': emoji})
        if not created:
            if reaction.emoji == emoji:
                reaction.delete()
                return Response({'status': 'removed'})
            reaction.emoji = emoji
            reaction.save()

        return Response(ReactionSerializer(reaction).data, status=201 if created else 200)


class UnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        count = Message.objects.filter(
            conversation__participants=request.user,
            is_deleted=False,
        ).exclude(sender=request.user).count()
        return Response({'unread': count})


class HeartbeatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        UserPresence.objects.update_or_create(
            user=request.user,
            defaults={'last_seen': timezone.now()},
        )
        return Response({'status': 'ok'})


class PresenceView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        raw = request.query_params.get('user_ids', '')
        try:
            user_ids = [int(i) for i in raw.split(',') if i.strip()]
        except ValueError:
            return Response({'error': 'invalid user_ids'}, status=400)

        cutoff = timezone.now() - timezone.timedelta(seconds=60)
        online_ids = set(
            UserPresence.objects.filter(user_id__in=user_ids, last_seen__gte=cutoff)
            .values_list('user_id', flat=True)
        )
        return Response({uid: uid in online_ids for uid in user_ids})
