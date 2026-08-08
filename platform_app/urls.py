from django.urls import path

from . import legal_views, mobile_api, views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('club/', views.club, name='club'),
    path('status/', views.status, name='status'),
    path('manifest.json', views.manifest, name='manifest'),
    path('sw.js', views.service_worker, name='sw'),
    path('termine/', views.booking, name='booking'),
    path('termine/warteliste/', views.join_waitlist, name='waitlist'),
    path('wallet/', views.wallet, name='wallet'),
    path('wallet/reward/<int:reward_id>/', views.redeem_reward, name='redeem_reward'),
    path('erinnerungen/', views.reminders, name='reminders'),
    path('erinnerungen/<int:pk>/toggle/', views.reminder_toggle, name='reminder_toggle'),
    path('nachrichten/', views.chat, name='chat'),
    path('profil/', views.profile, name='profile'),
    path('mitgliedskarte/qr.png', views.member_qr, name='member_qr'),
    path('management/', views.management, name='management'),
    path('management/modul/<int:pk>/toggle/', views.toggle_module, name='toggle_module'),

    path('datenschutz/', legal_views.datenschutz, name='datenschutz'),
    path('datenschutz/einstellungen/', legal_views.privacy_choices, name='privacy_choices'),
    path('impressum/', legal_views.impressum, name='impressum'),
    path('support/', legal_views.support, name='support'),
    path('konto-loeschen/', legal_views.account_deletion, name='account_deletion'),
    path('nutzungsbedingungen/', legal_views.terms, name='terms'),

    path('api/mobile/status/', mobile_api.status, name='mobile_status'),
    path('api/mobile/login/', mobile_api.login, name='mobile_login'),
    path('api/mobile/me/', mobile_api.me, name='mobile_me'),
    path('api/mobile/dashboard/', mobile_api.dashboard, name='mobile_dashboard'),
    path('api/mobile/club/', mobile_api.club, name='mobile_club'),
    path('api/mobile/booking/', mobile_api.booking, name='mobile_booking'),
    path('api/mobile/wallet/', mobile_api.wallet, name='mobile_wallet'),
    path('api/mobile/wallet/reward/<int:reward_id>/', mobile_api.redeem_reward, name='mobile_redeem_reward'),
    path('api/mobile/reminders/', mobile_api.reminders, name='mobile_reminders'),
    path('api/mobile/messages/', mobile_api.messages, name='mobile_messages'),
    path('api/mobile/profile/', mobile_api.profile, name='mobile_profile'),
    path('api/mobile/account-deletion/', mobile_api.account_deletion, name='mobile_account_deletion'),
]
