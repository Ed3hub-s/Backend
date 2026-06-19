from django.urls import path

from .views import AnalyticsSummaryView, AnalyticsTrackView


urlpatterns = [
    path('track/', AnalyticsTrackView.as_view(), name='analytics-track'),
    path('summary/', AnalyticsSummaryView.as_view(), name='analytics-summary'),
]
