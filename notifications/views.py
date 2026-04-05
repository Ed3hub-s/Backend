from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from .models import Notification, NotificationPreference
from .serializers import NotificationSerializer, NotificationPreferenceSerializer


class NotificationListView(generics.ListAPIView):
    """List all notifications for authenticated user"""
    serializer_class = NotificationSerializer
    permission_classes = (IsAuthenticated,)
    
    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user).select_related(
            'course', 'session', 'message_obj'
        )


class UnreadNotificationListView(generics.ListAPIView):
    """List unread notifications for authenticated user"""
    serializer_class = NotificationSerializer
    permission_classes = (IsAuthenticated,)
    
    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user, 
            is_read=False
        ).select_related('course', 'session', 'message_obj')


class NotificationMarkReadView(APIView):
    """Mark a single notification as read"""
    permission_classes = (IsAuthenticated,)
    
    def post(self, request, notification_id):
        try:
            notification = Notification.objects.get(
                id=notification_id, 
                recipient=request.user
            )
        except Notification.DoesNotExist:
            return Response(
                {'detail': 'Notification not found.'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        if not notification.is_read:
            notification.is_read = True
            notification.read_at = timezone.now()
            notification.save()
        
        return Response(NotificationSerializer(notification).data)


class NotificationMarkAllReadView(APIView):
    """Mark all notifications as read"""
    permission_classes = (IsAuthenticated,)
    
    def post(self, request):
        updated_count = Notification.objects.filter(
            recipient=request.user, 
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        
        return Response({
            'status': 'success',
            'marked_read': updated_count
        })


class UnreadCountView(APIView):
    """Get unread notification count"""
    permission_classes = (IsAuthenticated,)
    
    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user, 
            is_read=False
        ).count()
        
        return Response({'unread_count': count})


class NotificationDeleteView(APIView):
    """Delete a notification"""
    permission_classes = (IsAuthenticated,)
    
    def delete(self, request, notification_id):
        try:
            notification = Notification.objects.get(
                id=notification_id, 
                recipient=request.user
            )
        except Notification.DoesNotExist:
            return Response(
                {'detail': 'Notification not found.'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        
        notification.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class NotificationPreferenceView(APIView):
    """Get or update notification preferences"""
    permission_classes = (IsAuthenticated,)
    
    def get(self, request):
        prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
        return Response(NotificationPreferenceSerializer(prefs).data)
    
    def patch(self, request):
        prefs, _ = NotificationPreference.objects.get_or_create(user=request.user)
        serializer = NotificationPreferenceSerializer(prefs, data=request.data, partial=True)
        
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        serializer.save()
        return Response(serializer.data)
