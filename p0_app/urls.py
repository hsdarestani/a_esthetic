from django.urls import path

from . import booking_proxy_views, dashboard_proxy_views, views

urlpatterns = [
    path("konto-loeschen/", views.account_deletion_page, name="p0_account_deletion"),
    path("api/mobile/dashboard/", dashboard_proxy_views.mobile_dashboard, name="p0_mobile_dashboard"),
    path("api/mobile/booking/", booking_proxy_views.mobile_booking, name="p0_mobile_booking"),
    path("api/mobile/booking/manageable/", booking_proxy_views.mobile_manageable_appointments, name="p0_mobile_manageable_appointments"),
    path("api/mobile/booking/<str:appointment_id>/change/", booking_proxy_views.mobile_appointment_change, name="p0_mobile_appointment_change"),
    path("api/mobile/slots/", booking_proxy_views.mobile_slots, name="p0_mobile_slots"),
    path("api/mobile/wallet/", views.mobile_wallet, name="p0_mobile_wallet"),
    path("api/mobile/wallet/reward/<int:reward_id>/", views.mobile_redeem_reward, name="p0_mobile_redeem_reward"),
    path("api/mobile/account-deletion/", views.mobile_account_deletion, name="p0_mobile_account_deletion"),
    path("api/mobile/devices/", views.mobile_devices, name="p0_mobile_devices"),
    path("api/mobile/devices/<int:device_id>/revoke/", views.mobile_revoke_device, name="p0_mobile_revoke_device"),
    path("api/mobile/export/", views.mobile_export, name="p0_mobile_export"),
]