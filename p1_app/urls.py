from django.urls import path

from . import views

urlpatterns = [
    path("api/mobile/progress/", views.mobile_progress, name="p1_mobile_progress"),
    path("api/mobile/progress/<int:album_id>/upload/", views.mobile_progress_upload, name="p1_mobile_progress_upload"),
    path("api/mobile/progress/<int:album_id>/delete/", views.mobile_progress_album_delete, name="p1_mobile_progress_album_delete"),
    path("api/mobile/progress/photo/<int:photo_id>/", views.mobile_progress_photo, name="p1_mobile_progress_photo"),
    path("api/mobile/aftercare/", views.mobile_aftercare, name="p1_mobile_aftercare"),
    path("api/mobile/aftercare/task/<int:status_id>/toggle/", views.mobile_aftercare_task_toggle, name="p1_mobile_aftercare_task_toggle"),
    path("api/mobile/aftercare/followup/<int:followup_id>/response/", views.mobile_followup_response, name="p1_mobile_followup_response"),
    path("api/mobile/beauty-plans/", views.mobile_beauty_plans, name="p1_mobile_beauty_plans"),
    path("api/mobile/beauty-plans/<int:plan_id>/steps/", views.mobile_beauty_plan_step, name="p1_mobile_beauty_plan_step"),
    path("api/mobile/beauty-plans/<int:plan_id>/archive/", views.mobile_beauty_plan_archive, name="p1_mobile_beauty_plan_archive"),
    path("api/mobile/beauty-plans/steps/<int:step_id>/toggle/", views.mobile_beauty_plan_step_toggle, name="p1_mobile_beauty_plan_step_toggle"),
]
