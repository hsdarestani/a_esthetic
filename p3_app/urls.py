from django.urls import path

from . import export_views, views

urlpatterns = [
    path("api/mobile/export/", export_views.mobile_full_export, name="p3_mobile_full_export"),
    path("api/mobile/gamification/", views.mobile_gamification, name="p3_mobile_gamification"),
    path("api/mobile/gamification/challenges/<int:challenge_id>/join/", views.mobile_challenge_join, name="p3_mobile_challenge_join"),
    path("api/mobile/gamification/challenges/<int:challenge_id>/progress/", views.mobile_challenge_progress, name="p3_mobile_challenge_progress"),
    path("api/mobile/gamification/quizzes/<int:quiz_id>/submit/", views.mobile_quiz_submit, name="p3_mobile_quiz_submit"),
    path("api/mobile/events/", views.mobile_events, name="p3_mobile_events"),
    path("api/mobile/events/<int:event_id>/register/", views.mobile_event_register, name="p3_mobile_event_register"),
    path("api/mobile/events/<int:event_id>/cancel/", views.mobile_event_cancel, name="p3_mobile_event_cancel"),
    path("api/mobile/events/<int:event_id>/calendar/", views.mobile_event_calendar, name="p3_mobile_event_calendar"),
    path("api/mobile/concierge/", views.mobile_concierge, name="p3_mobile_concierge"),
    path("api/mobile/conversations/", views.mobile_conversations, name="p3_mobile_conversations"),
    path("api/mobile/conversations/<int:thread_id>/", views.mobile_conversation_detail, name="p3_mobile_conversation_detail"),
    path("api/mobile/conversations/<int:thread_id>/close/", views.mobile_conversation_close, name="p3_mobile_conversation_close"),
]
