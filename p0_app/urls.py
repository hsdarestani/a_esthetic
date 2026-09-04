from django.urls import path

from . import (
    admin_mobile_views,
    canonical_booking_views,
    notification_views,
    package_bridge_views,
    referral_views,
    reward_views,
    views,
)

urlpatterns = [
    path("konto-loeschen/", views.account_deletion_page, name="p0_account_deletion"),
    path("api/mobile/dashboard/", canonical_booking_views.mobile_dashboard, name="p0_mobile_dashboard"),
    path("api/mobile/booking/", canonical_booking_views.retired_mobile_booking, name="p0_retired_mobile_booking"),
    path("api/mobile/club/", referral_views.mobile_club, name="p0_mobile_club"),
    path("api/mobile/package-booking/", package_bridge_views.mobile_package_booking, name="p0_mobile_package_booking"),
    path("api/mobile/wallet/", views.mobile_wallet, name="p0_mobile_wallet"),
    path("api/mobile/wallet/reward/<int:reward_id>/", reward_views.mobile_redeem_reward, name="p0_mobile_redeem_reward"),
    path("api/mobile/reward-redemptions/", reward_views.mobile_reward_redemptions, name="p0_mobile_reward_redemptions"),
    path("api/mobile/notifications/", notification_views.mobile_notifications, name="p0_mobile_notifications"),
    path("api/mobile/notifications/read-all/", notification_views.mobile_notifications_read_all, name="p0_mobile_notifications_read_all"),
    path("api/mobile/notifications/<int:notification_id>/read/", notification_views.mobile_notification_read, name="p0_mobile_notification_read"),
    path("api/mobile/notifications/devices/", notification_views.mobile_push_devices, name="p0_mobile_push_devices"),
    path("api/mobile/admin/", admin_mobile_views.mobile_admin_overview, name="p0_mobile_admin_overview"),
    path("api/mobile/admin/customers/", admin_mobile_views.mobile_admin_customers, name="p0_mobile_admin_customers"),
    path("api/mobile/admin/modules/<slug:key>/", admin_mobile_views.mobile_admin_module, name="p0_mobile_admin_module"),
    path("api/mobile/admin/rewards/<int:redemption_id>/", admin_mobile_views.mobile_admin_reward, name="p0_mobile_admin_reward"),
    path("api/mobile/admin/notifications/", admin_mobile_views.mobile_admin_notification, name="p0_mobile_admin_notification"),
    path("api/mobile/account-deletion/", views.mobile_account_deletion, name="p0_mobile_account_deletion"),
    path("api/mobile/devices/", views.mobile_devices, name="p0_mobile_devices"),
    path("api/mobile/devices/<int:device_id>/revoke/", views.mobile_revoke_device, name="p0_mobile_revoke_device"),
    path("api/mobile/export/", views.mobile_export, name="p0_mobile_export"),
]
