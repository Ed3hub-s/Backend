from django.urls import path
from .views import (
    NotificationListView,
    UnreadNotificationListView,
    NotificationMarkReadView,
    NotificationMarkAllReadView,
    UnreadCountView,
    NotificationDeleteView,
    NotificationPreferenceView,
)

urlpatterns = [
    path('', NotificationListView.as_view(), name='notification-list'),
    path('unread/', UnreadNotificationListView.as_view(), name='notification-unread'),
    path('unread-count/', UnreadCountView.as_view(), name='notification-unread-count'),
    path('<int:notification_id>/read/', NotificationMarkReadView.as_view(), name='notification-mark-read'),
    path('mark-all-read/', NotificationMarkAllReadView.as_view(), name='notification-mark-all-read'),
    path('<int:notification_id>/delete/', NotificationDeleteView.as_view(), name='notification-delete'),
    path('preferences/', NotificationPreferenceView.as_view(), name='notification-preferences'),
]
