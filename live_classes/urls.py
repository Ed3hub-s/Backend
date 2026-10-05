from django.urls import path
from .bundles import BundleListView, EducatorBundleView

from .views import (
    EducatorLiveClassAnalyticsView,
    EducatorLiveClassDetailView,
    EducatorLiveClassListCreateView,
    JoinLiveClassView,
    LeaveLiveClassView,
    LiveClassDetailView,
    LiveClassMarketplaceView,
    LiveClassRecordingsView,
    MyLiveClassesView,
    PaystackLiveClassWebhookView,
    RecordingAccessView,
    RegisterLiveClassView,
    VerifyLiveClassPaymentView,
)

urlpatterns = [
    path('bundles/', BundleListView.as_view(), name='live-class-bundles'),
    path('educator/bundles/', EducatorBundleView.as_view(), name='educator-live-class-bundles'),
    path('', LiveClassMarketplaceView.as_view(), name='live-class-marketplace'),
    path('mine/', MyLiveClassesView.as_view(), name='my-live-classes'),
    path('educator/', EducatorLiveClassListCreateView.as_view(), name='educator-live-classes'),
    path('educator/<slug:slug>/', EducatorLiveClassDetailView.as_view(), name='educator-live-class-detail'),
    path('educator/<slug:slug>/analytics/', EducatorLiveClassAnalyticsView.as_view(), name='live-class-analytics'),
    path('recordings/<int:recording_id>/access/', RecordingAccessView.as_view(), name='recording-access'),
    path('webhooks/paystack/', PaystackLiveClassWebhookView.as_view(), name='paystack-live-class-webhook'),
    path('<slug:slug>/', LiveClassDetailView.as_view(), name='live-class-detail'),
    path('<slug:slug>/register/', RegisterLiveClassView.as_view(), name='live-class-register'),
    path('<slug:slug>/verify-payment/', VerifyLiveClassPaymentView.as_view(), name='live-class-payment-verify'),
    path('<slug:slug>/join/', JoinLiveClassView.as_view(), name='live-class-join'),
    path('<slug:slug>/leave/', LeaveLiveClassView.as_view(), name='live-class-leave'),
    path('<slug:slug>/recordings/', LiveClassRecordingsView.as_view(), name='live-class-recordings'),
]
