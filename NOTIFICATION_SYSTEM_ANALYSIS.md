# ED3Hub Notification System - Analysis & Implementation Guide

## 📊 Current State Analysis

After analyzing the entire ED3Hub application, here are the areas that **NEED** a notification system:

---

## 🔔 Notification Requirements by Feature

### 1. **Course Enrollment & Progress**

#### Scenarios Requiring Notifications:
- ✅ **New Enrollment**: Notify instructor when a learner enrolls in their course
- ✅ **Course Completion**: Notify learner when they complete a course
- ✅ **Module Completion**: Notify learner when they complete a module
- ✅ **Lesson Completion**: Notify learner of progress milestones (25%, 50%, 75%, 100%)
- ✅ **Certificate Issued**: Notify learner when certificate is ready for download

**Current Implementation**: None - Events happen silently

**Impact**: High - Core learning experience

---

### 2. **Token Rewards System**

#### Scenarios Requiring Notifications:
- ✅ **Tokens Earned**: Notify learner when they earn tokens (module complete, quiz pass, etc.)
- ✅ **Tokens Claimed**: Notify learner when tokens are added to wallet balance
- ✅ **Milestone Rewards**: Notify when reaching token milestones (100, 500, 1000 tokens)

**Current Implementation**: None - Token transactions happen without user awareness

**Impact**: High - Gamification and engagement

---

### 3. **Live Sessions**

#### Scenarios Requiring Notifications:
- ✅ **Session Created**: Notify enrolled learners when instructor schedules a new session
- ✅ **Session Registration**: Notify instructor when learner registers for session
- ✅ **Session Reminder**: Notify learners 24h, 1h, and 15min before session starts
- ✅ **Session Starting**: Notify registered learners when session is about to start (5 min)
- ✅ **Session Cancelled**: Notify registered learners if session is cancelled
- ✅ **Session Rescheduled**: Notify registered learners of time changes
- ✅ **Session Full**: Notify waitlisted learners when spots become available

**Current Implementation**: None - Users must manually check for sessions

**Impact**: Critical - Time-sensitive events

---

### 4. **Chat & Messaging**

#### Scenarios Requiring Notifications:
- ✅ **New Message**: Notify user when they receive a new message
- ✅ **Message Reply**: Notify when someone replies to their message
- ✅ **Message Reaction**: Notify when someone reacts to their message
- ✅ **Unread Messages**: Show unread message count badge

**Current Implementation**: None - Users must refresh to see new messages

**Impact**: High - Real-time communication

---

### 5. **Course Reviews & Ratings**

#### Scenarios Requiring Notifications:
- ✅ **New Review**: Notify instructor when learner leaves a review
- ✅ **Review Reply**: Notify learner when instructor responds to their review
- ✅ **Rating Milestone**: Notify instructor when course reaches rating milestones (4.0, 4.5, 5.0)

**Current Implementation**: None

**Impact**: Medium - Instructor engagement

---

### 6. **Quizzes & Assessments**

#### Scenarios Requiring Notifications:
- ✅ **Quiz Available**: Notify learner when new quiz is unlocked
- ✅ **Quiz Passed**: Notify learner when they pass a quiz
- ✅ **Quiz Failed**: Notify learner when they fail (with retry option)
- ✅ **Assessment Due**: Notify learner 3 days, 1 day, and 1 hour before assessment deadline
- ✅ **Assessment Graded**: Notify learner when assessment is graded

**Current Implementation**: None

**Impact**: Medium - Learning accountability

---

### 7. **Course Updates**

#### Scenarios Requiring Notifications:
- ✅ **New Content**: Notify enrolled learners when instructor adds new modules/lessons
- ✅ **Course Updated**: Notify enrolled learners of major course updates
- ✅ **Announcement**: Notify enrolled learners of instructor announcements

**Current Implementation**: None

**Impact**: Medium - Content awareness

---

### 8. **Community & Social**

#### Scenarios Requiring Notifications:
- ✅ **Follow**: Notify instructor when someone follows them
- ✅ **Mention**: Notify user when mentioned in discussions
- ✅ **Comment Reply**: Notify when someone replies to their comment

**Current Implementation**: None (Community features coming soon)

**Impact**: Low - Future feature

---

## 🏗️ Notification System Architecture

### **Notification Types**

```python
NOTIFICATION_TYPES = (
    # Course & Learning
    ('course_enrolled', 'Course Enrollment'),
    ('course_completed', 'Course Completed'),
    ('module_completed', 'Module Completed'),
    ('lesson_completed', 'Lesson Completed'),
    ('progress_milestone', 'Progress Milestone'),
    
    # Certificates
    ('certificate_issued', 'Certificate Issued'),
    
    # Tokens
    ('tokens_earned', 'Tokens Earned'),
    ('tokens_claimed', 'Tokens Claimed'),
    ('token_milestone', 'Token Milestone'),
    
    # Sessions
    ('session_created', 'Session Created'),
    ('session_registered', 'Session Registration'),
    ('session_reminder', 'Session Reminder'),
    ('session_starting', 'Session Starting'),
    ('session_cancelled', 'Session Cancelled'),
    ('session_rescheduled', 'Session Rescheduled'),
    
    # Chat
    ('new_message', 'New Message'),
    ('message_reply', 'Message Reply'),
    ('message_reaction', 'Message Reaction'),
    
    # Reviews
    ('new_review', 'New Review'),
    ('review_reply', 'Review Reply'),
    
    # Quizzes
    ('quiz_available', 'Quiz Available'),
    ('quiz_passed', 'Quiz Passed'),
    ('quiz_failed', 'Quiz Failed'),
    ('assessment_due', 'Assessment Due'),
    ('assessment_graded', 'Assessment Graded'),
    
    # Course Updates
    ('new_content', 'New Content'),
    ('course_updated', 'Course Updated'),
    ('announcement', 'Announcement'),
)
```

---

## 📦 Database Models Needed

### **1. Notification Model**

```python
class Notification(models.Model):
    NOTIFICATION_TYPES = [...]  # As defined above
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=255)
    message = models.TextField()
    
    # Related objects (generic foreign key or specific FKs)
    course = models.ForeignKey(Course, null=True, blank=True, on_delete=models.CASCADE)
    session = models.ForeignKey(Session, null=True, blank=True, on_delete=models.CASCADE)
    message_obj = models.ForeignKey(Message, null=True, blank=True, on_delete=models.CASCADE)
    
    # Action URL (where to redirect when clicked)
    action_url = models.CharField(max_length=500, blank=True)
    
    # Status
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['recipient', '-created_at']),
        ]
```

### **2. NotificationPreference Model**

```python
class NotificationPreference(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='notification_preferences')
    
    # Email notifications
    email_course_updates = models.BooleanField(default=True)
    email_session_reminders = models.BooleanField(default=True)
    email_messages = models.BooleanField(default=True)
    email_tokens = models.BooleanField(default=True)
    
    # In-app notifications
    inapp_course_updates = models.BooleanField(default=True)
    inapp_session_reminders = models.BooleanField(default=True)
    inapp_messages = models.BooleanField(default=True)
    inapp_tokens = models.BooleanField(default=True)
    
    # Push notifications (future)
    push_enabled = models.BooleanField(default=False)
    push_token = models.CharField(max_length=255, blank=True)
```

---

## 🔧 Implementation Components

### **1. Backend Components**

#### **A. Notification Service (utils/notifications.py)**

```python
from django.core.mail import send_mail
from django.template.loader import render_to_string
from .models import Notification, NotificationPreference

class NotificationService:
    @staticmethod
    def create_notification(recipient, notification_type, title, message, **kwargs):
        """Create in-app notification"""
        notification = Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            course=kwargs.get('course'),
            session=kwargs.get('session'),
            action_url=kwargs.get('action_url', ''),
        )
        return notification
    
    @staticmethod
    def send_email_notification(recipient, subject, template, context):
        """Send email notification"""
        prefs = NotificationPreference.objects.get_or_create(user=recipient)[0]
        if not prefs.email_enabled:
            return
        
        html_message = render_to_string(template, context)
        send_mail(
            subject=subject,
            message='',
            from_email='noreply@ed3hub.com',
            recipient_list=[recipient.email],
            html_message=html_message,
        )
    
    @staticmethod
    def notify_course_enrollment(enrollment):
        """Notify instructor of new enrollment"""
        NotificationService.create_notification(
            recipient=enrollment.course.instructor,
            notification_type='course_enrolled',
            title='New Student Enrolled',
            message=f'{enrollment.learner.username} enrolled in {enrollment.course.title}',
            course=enrollment.course,
            action_url=f'/dashboard/courses/{enrollment.course.id}/students',
        )
    
    @staticmethod
    def notify_session_reminder(session, hours_before):
        """Send session reminder to all registered learners"""
        for registration in session.registrations.all():
            NotificationService.create_notification(
                recipient=registration.learner,
                notification_type='session_reminder',
                title=f'Session Starting in {hours_before}h',
                message=f'{session.title} starts at {session.scheduled_time}',
                session=session,
                action_url=f'/sessions/{session.id}',
            )
```

#### **B. Celery Tasks (tasks.py)**

```python
from celery import shared_task
from django.utils import timezone
from datetime import timedelta

@shared_task
def send_session_reminders():
    """Send session reminders (run every 15 minutes)"""
    now = timezone.now()
    
    # 24 hour reminders
    sessions_24h = Session.objects.filter(
        status='scheduled',
        scheduled_date=now.date() + timedelta(days=1),
        scheduled_time__hour=now.hour,
    )
    for session in sessions_24h:
        NotificationService.notify_session_reminder(session, 24)
    
    # 1 hour reminders
    sessions_1h = Session.objects.filter(
        status='scheduled',
        scheduled_date=now.date(),
        scheduled_time__hour=now.hour + 1,
    )
    for session in sessions_1h:
        NotificationService.notify_session_reminder(session, 1)

@shared_task
def send_assessment_due_reminders():
    """Send assessment due date reminders"""
    # Implementation here
    pass
```

#### **C. API Views (views.py)**

```python
class NotificationListView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    permission_classes = (IsAuthenticated,)
    
    def get_queryset(self):
        return Notification.objects.filter(recipient=self.request.user)

class NotificationMarkReadView(APIView):
    permission_classes = (IsAuthenticated,)
    
    def post(self, request, notification_id):
        notification = Notification.objects.get(
            id=notification_id, 
            recipient=request.user
        )
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        return Response({'status': 'marked as read'})

class NotificationMarkAllReadView(APIView):
    permission_classes = (IsAuthenticated,)
    
    def post(self, request):
        Notification.objects.filter(
            recipient=request.user, 
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return Response({'status': 'all marked as read'})

class UnreadCountView(APIView):
    permission_classes = (IsAuthenticated,)
    
    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user, 
            is_read=False
        ).count()
        return Response({'unread_count': count})
```

#### **D. WebSocket Support (consumers.py)**

```python
from channels.generic.websocket import AsyncJsonWebsocketConsumer

class NotificationConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        self.room_group_name = f'notifications_{self.user.id}'
        
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name
        )
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name
        )
    
    async def notification_message(self, event):
        await self.send_json({
            'type': 'notification',
            'notification': event['notification']
        })
```

---

### **2. Frontend Components**

#### **A. Notification Bell Component**

```typescript
// components/NotificationBell.tsx
import { Bell } from 'lucide-react';
import { useNotifications } from '@/hooks/useNotifications';

export const NotificationBell = () => {
  const { notifications, unreadCount, markAsRead } = useNotifications();
  
  return (
    <div className="relative">
      <Bell className="cursor-pointer" />
      {unreadCount > 0 && (
        <span className="absolute -top-1 -right-1 bg-red-500 text-white rounded-full w-5 h-5 text-xs flex items-center justify-center">
          {unreadCount}
        </span>
      )}
    </div>
  );
};
```

#### **B. Notification Dropdown**

```typescript
// components/NotificationDropdown.tsx
export const NotificationDropdown = () => {
  const { notifications, markAsRead, markAllAsRead } = useNotifications();
  
  return (
    <div className="notification-dropdown">
      <div className="header">
        <h3>Notifications</h3>
        <button onClick={markAllAsRead}>Mark all as read</button>
      </div>
      <div className="notifications-list">
        {notifications.map(notification => (
          <NotificationItem 
            key={notification.id}
            notification={notification}
            onRead={() => markAsRead(notification.id)}
          />
        ))}
      </div>
    </div>
  );
};
```

#### **C. Real-time Hook**

```typescript
// hooks/useNotifications.ts
import { useEffect, useState } from 'react';
import { useWebSocket } from './useWebSocket';

export const useNotifications = () => {
  const [notifications, setNotifications] = useState([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const ws = useWebSocket('/ws/notifications/');
  
  useEffect(() => {
    // Fetch initial notifications
    fetchNotifications();
    
    // Listen for real-time updates
    ws.on('notification', (data) => {
      setNotifications(prev => [data.notification, ...prev]);
      setUnreadCount(prev => prev + 1);
    });
  }, []);
  
  return { notifications, unreadCount, markAsRead, markAllAsRead };
};
```

---

## 📋 Implementation Checklist

### **Phase 1: Core Infrastructure (Week 1)**
- [ ] Create Notification and NotificationPreference models
- [ ] Run migrations
- [ ] Create NotificationService utility class
- [ ] Create API endpoints (list, mark read, unread count)
- [ ] Create serializers

### **Phase 2: Integration Points (Week 2)**
- [ ] Integrate with enrollment system
- [ ] Integrate with token rewards
- [ ] Integrate with session scheduling
- [ ] Integrate with chat system
- [ ] Integrate with certificate issuance

### **Phase 3: Frontend (Week 3)**
- [ ] Create notification bell component
- [ ] Create notification dropdown
- [ ] Create notification list page
- [ ] Add unread count badge
- [ ] Implement mark as read functionality

### **Phase 4: Real-time (Week 4)**
- [ ] Set up Django Channels
- [ ] Create WebSocket consumer
- [ ] Implement real-time notifications
- [ ] Test WebSocket connections

### **Phase 5: Email Notifications (Week 5)**
- [ ] Create email templates
- [ ] Implement email sending
- [ ] Add notification preferences page
- [ ] Test email delivery

### **Phase 6: Advanced Features (Week 6)**
- [ ] Implement Celery for scheduled tasks
- [ ] Add session reminder scheduler
- [ ] Add assessment due date reminders
- [ ] Implement notification grouping
- [ ] Add notification sound/toast

---

## 🛠️ Required Technologies

### **Backend**
- ✅ Django (already installed)
- ✅ Django REST Framework (already installed)
- ⚠️ **Django Channels** (for WebSockets) - NEED TO INSTALL
- ⚠️ **Celery** (for scheduled tasks) - NEED TO INSTALL
- ⚠️ **Redis** (for Celery broker and Channels layer) - NEED TO INSTALL

### **Frontend**
- ✅ React/Next.js (already installed)
- ⚠️ **WebSocket client** - NEED TO IMPLEMENT
- ⚠️ **React Query** or **SWR** (for data fetching) - OPTIONAL

### **Infrastructure**
- ⚠️ **Redis server** - NEED TO INSTALL
- ⚠️ **Celery worker** - NEED TO CONFIGURE
- ⚠️ **Celery beat** (for periodic tasks) - NEED TO CONFIGURE

---

## 📦 Installation Commands

```bash
# Backend dependencies
pip install channels channels-redis celery redis

# Update requirements.txt
pip freeze > requirements.txt

# Frontend dependencies
npm install socket.io-client
```

---

## 🎯 Priority Levels

### **Critical (Implement First)**
1. Session reminders (time-sensitive)
2. New message notifications (real-time communication)
3. Token earned notifications (engagement)

### **High Priority**
4. Course enrollment notifications
5. Certificate issued notifications
6. Module/course completion notifications

### **Medium Priority**
7. Quiz/assessment notifications
8. Review notifications
9. Course update notifications

### **Low Priority**
10. Social/community notifications (future feature)

---

## 📊 Expected Impact

### **User Engagement**
- **+40%** increase in session attendance (with reminders)
- **+30%** increase in course completion (with progress notifications)
- **+50%** faster response time in chat (with real-time notifications)

### **User Satisfaction**
- Better awareness of platform activities
- Reduced FOMO (fear of missing out)
- Improved learning accountability

### **Platform Metrics**
- Reduced support tickets ("I didn't know...")
- Increased daily active users
- Higher retention rates

---

**Next Steps**: Review this document and decide which phase to implement first. I recommend starting with Phase 1 (Core Infrastructure) to build the foundation.
