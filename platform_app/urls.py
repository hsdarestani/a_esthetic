from django.urls import path
from . import views, legal_views

urlpatterns=[
 path('',views.dashboard,name='dashboard'), path('club/',views.club,name='club'), path('beauty-assistent/',views.beauty_assistant,name='beauty_assistant'), path('health/',views.health,name='health'), path('manifest.json',views.manifest,name='manifest'), path('sw.js',views.service_worker,name='sw'),
 path('termine/',views.booking,name='booking'),path('termine/warteliste/',views.join_waitlist,name='waitlist'),
 path('wallet/',views.wallet,name='wallet'),path('wallet/reward/<int:reward_id>/',views.redeem_reward,name='redeem_reward'),
 path('beauty-passport/',views.passport,name='passport'),path('erinnerungen/',views.reminders,name='reminders'),path('erinnerungen/<int:pk>/toggle/',views.reminder_toggle,name='reminder_toggle'),
 path('nachrichten/',views.chat,name='chat'),path('profil/',views.profile,name='profile'),path('profil/einwilligung/<int:template_id>/',views.accept_consent,name='accept_consent'),path('profil/einwilligung/<int:record_id>/widerrufen/',views.withdraw_consent,name='withdraw_consent'),
 path('mitgliedskarte/qr.png',views.member_qr,name='member_qr'),path('dokument/<int:pk>/',views.protected_document,name='protected_document'),
 path('management/',views.management,name='management'),path('management/modul/<int:pk>/toggle/',views.toggle_module,name='toggle_module'),
 path('datenschutz/', legal_views.datenschutz, name='datenschutz'),
 path('datenschutz/einstellungen/', legal_views.privacy_choices, name='privacy_choices'),
 path('impressum/', legal_views.impressum, name='impressum'),
 path('support/', legal_views.support, name='support'),
 path('konto-loeschen/', legal_views.account_deletion, name='account_deletion'),
 path('medizinische-hinweise/', legal_views.medical_notice, name='medical_notice'),
 path('nutzungsbedingungen/', legal_views.terms, name='terms'),
]
