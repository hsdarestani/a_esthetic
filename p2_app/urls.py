from django.urls import path

from . import export_views, views

urlpatterns = [
    path("api/mobile/export/", export_views.mobile_full_export, name="p2_mobile_full_export"),
    path("api/mobile/wallet-pass/", views.mobile_wallet_pass, name="p2_mobile_wallet_pass"),
    path("api/mobile/wallet-pass/qr/", views.mobile_wallet_qr, name="p2_mobile_wallet_qr"),
    path("api/mobile/wallet-pass/apple/", views.mobile_wallet_apple, name="p2_mobile_wallet_apple"),
    path("api/mobile/wallet-pass/google/", views.mobile_wallet_google, name="p2_mobile_wallet_google"),
    path("api/mobile/cabinet/", views.mobile_cabinet, name="p2_mobile_cabinet"),
    path("api/mobile/cabinet/<int:product_id>/archive/", views.mobile_cabinet_archive, name="p2_mobile_cabinet_archive"),
    path("api/mobile/cabinet/<int:product_id>/delete/", views.mobile_cabinet_delete, name="p2_mobile_cabinet_delete"),
    path("api/mobile/cabinet/<int:product_id>/routine/", views.mobile_cabinet_routine, name="p2_mobile_cabinet_routine"),
    path("api/mobile/cabinet/routine/<int:routine_id>/toggle/", views.mobile_routine_toggle, name="p2_mobile_routine_toggle"),
    path("api/mobile/cabinet/routine/<int:routine_id>/delete/", views.mobile_routine_delete, name="p2_mobile_routine_delete"),
    path("api/mobile/shop/", views.mobile_shop, name="p2_mobile_shop"),
    path("api/mobile/shop/orders/", views.mobile_shop_orders, name="p2_mobile_shop_orders"),
    path("api/mobile/shop/orders/<int:order_id>/", views.mobile_shop_order_detail, name="p2_mobile_shop_order_detail"),
    path("api/mobile/shop/orders/<int:order_id>/cancel/", views.mobile_shop_order_cancel, name="p2_mobile_shop_order_cancel"),
]
