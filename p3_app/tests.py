import json
from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from platform_app.mobile_api import _token_for
from platform_app.models import Message, Reminder, Thread, WalletAccount, WalletTransaction

from .models import (
    Badge,
    BeautyEvent,
    Challenge,
    ChallengeParticipation,
    ConciergeRequest,
    EventRegistration,
    Quiz,
    QuizAttempt,
    QuizQuestion,
    UserBadge,
)


class P3CommunityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="p3@example.de",
            email="p3@example.de",
            password="Test-Password-123!",
            first_name="Paula",
        )
        self.other = User.objects.create_user(
            username="other-p3@example.de",
            email="other-p3@example.de",
            password="Other-Password-123!",
        )
        self.staff = User.objects.create_user(
            username="staff-p3@example.de",
            email="staff-p3@example.de",
            password="Staff-Password-123!",
            is_staff=True,
        )
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {_token_for(self.user)}"}
        self.other_auth = {"HTTP_AUTHORIZATION": f"Bearer {_token_for(self.other)}"}
        WalletAccount.objects.create(user=self.user, coin_balance=0)
        WalletAccount.objects.create(user=self.other, coin_balance=0)

    def post_json(self, path, payload=None, auth=None):
        return self.client.post(
            path,
            data=json.dumps(payload or {}),
            content_type="application/json",
            **(auth or self.auth),
        )

    def test_p3_endpoints_require_authentication(self):
        for path in ["/api/mobile/gamification/", "/api/mobile/events/", "/api/mobile/concierge/", "/api/mobile/conversations/"]:
            response = self.client.get(path)
            self.assertEqual(response.status_code, 401, path)
            self.assertEqual(response.json()["error"], "authentication_required")

    def test_challenge_progress_is_daily_and_reward_is_idempotent(self):
        badge = Badge.objects.create(key="routine-star", name="Routine Star")
        challenge = Challenge.objects.create(
            title="2-Tage Routine",
            description="Eigene Routine dokumentieren",
            challenge_type="care",
            target_count=2,
            reward_coins=120,
            badge=badge,
            starts_at=timezone.now() - timedelta(hours=1),
            ends_at=timezone.now() + timedelta(days=5),
            active=True,
        )

        joined = self.post_json(f"/api/mobile/gamification/challenges/{challenge.pk}/join/")
        self.assertEqual(joined.status_code, 201, joined.content)

        first = self.post_json(f"/api/mobile/gamification/challenges/{challenge.pk}/progress/")
        self.assertEqual(first.status_code, 200, first.content)
        self.assertEqual(first.json()["challenge"]["participation"]["progress"], 1)
        self.assertEqual(first.json()["coins_awarded"], 0)

        duplicate_day = self.post_json(f"/api/mobile/gamification/challenges/{challenge.pk}/progress/")
        self.assertEqual(duplicate_day.status_code, 409)
        self.assertEqual(duplicate_day.json()["error"], "progress_already_recorded_today")

        participation = ChallengeParticipation.objects.get(user=self.user, challenge=challenge)
        participation.last_progress_on = timezone.localdate() - timedelta(days=1)
        participation.save(update_fields=["last_progress_on"])

        completed = self.post_json(f"/api/mobile/gamification/challenges/{challenge.pk}/progress/")
        self.assertEqual(completed.status_code, 200, completed.content)
        self.assertEqual(completed.json()["coins_awarded"], 120)
        self.assertTrue(completed.json()["badge_awarded"])
        self.assertTrue(UserBadge.objects.filter(user=self.user, badge=badge).exists())

        replay = self.post_json(f"/api/mobile/gamification/challenges/{challenge.pk}/progress/")
        self.assertEqual(replay.status_code, 200, replay.content)
        self.assertEqual(replay.json()["coins_awarded"], 0)
        wallet = WalletAccount.objects.get(user=self.user)
        self.assertEqual(wallet.coin_balance, 120)
        self.assertEqual(
            WalletTransaction.objects.filter(user=self.user, reference=f"p3:challenge:{challenge.pk}:u:{self.user.pk}").count(),
            1,
        )

    def test_quiz_hides_answers_until_submit_and_rewards_once(self):
        badge = Badge.objects.create(key="knowledge", name="Knowledge")
        quiz = Quiz.objects.create(
            title="Beauty Basics",
            description="Allgemeines Produktwissen",
            passing_percent=70,
            reward_coins=80,
            badge=badge,
            active=True,
            approved=True,
        )
        QuizQuestion.objects.create(
            quiz=quiz,
            question="Was ist morgens wichtig?",
            options=["SPF", "Nichts"],
            correct_index=0,
            explanation="SPF gehört für viele Routinen zum Sonnenschutz; individuelle Fragen bitte fachlich klären.",
            sort_order=10,
        )
        QuizQuestion.objects.create(
            quiz=quiz,
            question="Was gehört zur Produkthygiene?",
            options=["Offen lagern", "Saubere Hände"],
            correct_index=1,
            explanation="Saubere Hände reduzieren Verunreinigungen.",
            sort_order=20,
        )

        listing = self.client.get("/api/mobile/gamification/", **self.auth)
        self.assertEqual(listing.status_code, 200, listing.content)
        questions = listing.json()["quizzes"][0]["questions"]
        self.assertNotIn("correct_index", questions[0])
        self.assertNotIn("explanation", questions[0])

        submitted = self.post_json(f"/api/mobile/gamification/quizzes/{quiz.pk}/submit/", {"answers": [0, 1]})
        self.assertEqual(submitted.status_code, 200, submitted.content)
        self.assertEqual(submitted.json()["result"]["percent"], 100)
        self.assertTrue(submitted.json()["result"]["passed"])
        self.assertEqual(submitted.json()["result"]["coins_awarded"], 80)
        self.assertEqual(submitted.json()["result"]["review"][0]["correct_index"], 0)

        replay = self.post_json(f"/api/mobile/gamification/quizzes/{quiz.pk}/submit/", {"answers": [1, 0]})
        self.assertEqual(replay.status_code, 200, replay.content)
        self.assertEqual(replay.json()["result"]["percent"], 100)
        self.assertEqual(replay.json()["result"]["coins_awarded"], 0)
        self.assertEqual(QuizAttempt.objects.filter(user=self.user, quiz=quiz).count(), 1)
        self.assertEqual(WalletAccount.objects.get(user=self.user).coin_balance, 80)

    def test_event_capacity_waitlist_promotion_and_calendar(self):
        event = BeautyEvent.objects.create(
            title="A+ Member Evening",
            description="Community Event",
            starts_at=timezone.now() + timedelta(days=3),
            ends_at=timezone.now() + timedelta(days=3, hours=2),
            location="Frankfurt",
            capacity=1,
            allow_guest=False,
            active=True,
        )

        first = self.post_json(f"/api/mobile/events/{event.pk}/register/")
        self.assertEqual(first.status_code, 201, first.content)
        self.assertEqual(first.json()["registration"]["status"], "registered")

        second = self.post_json(f"/api/mobile/events/{event.pk}/register/", auth=self.other_auth)
        self.assertEqual(second.status_code, 201, second.content)
        self.assertEqual(second.json()["registration"]["status"], "waitlist")

        calendar_before = self.client.get(f"/api/mobile/events/{event.pk}/calendar/", **self.other_auth)
        self.assertEqual(calendar_before.status_code, 404)

        cancelled = self.post_json(f"/api/mobile/events/{event.pk}/cancel/")
        self.assertEqual(cancelled.status_code, 200, cancelled.content)
        promoted = EventRegistration.objects.get(user=self.other, event=event)
        self.assertEqual(promoted.status, "registered")
        self.assertTrue(Reminder.objects.filter(user=self.other, related_type="p3_event", related_id=str(event.pk)).exists())

        calendar_after = self.client.get(f"/api/mobile/events/{event.pk}/calendar/", **self.other_auth)
        self.assertEqual(calendar_after.status_code, 200, calendar_after.content)
        self.assertEqual(calendar_after["Content-Type"], "text/calendar; charset=utf-8")

    def test_event_guest_uses_two_seats_and_requires_permission(self):
        event = BeautyEvent.objects.create(
            title="Small Event",
            starts_at=timezone.now() + timedelta(days=2),
            ends_at=timezone.now() + timedelta(days=2, hours=1),
            capacity=5,
            allow_guest=False,
            active=True,
        )
        response = self.post_json(f"/api/mobile/events/{event.pk}/register/", {"guest_name": "Gast"})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"], "event_guest_not_allowed")

    def test_concierge_and_conversations_are_owner_scoped_and_hide_internal_messages(self):
        created = self.post_json(
            "/api/mobile/concierge/",
            {
                "request_type": "travel_coordination",
                "title": "Termin rund um Reise",
                "details": "Ich brauche organisatorische Hilfe bei der Terminabstimmung.",
            },
        )
        self.assertEqual(created.status_code, 201, created.content)
        item = ConciergeRequest.objects.get(pk=created.json()["request_id"])
        self.assertEqual(item.user, self.user)
        self.assertEqual(item.thread.user, self.user)
        self.assertEqual(item.thread.messages.count(), 1)

        Message.objects.create(thread=item.thread, sender=self.staff, body="Interne Notiz", is_internal=True)
        Message.objects.create(thread=item.thread, sender=self.staff, body="Wir melden uns mit Optionen.", is_internal=False)

        owner = self.client.get(f"/api/mobile/conversations/{item.thread_id}/", **self.auth)
        self.assertEqual(owner.status_code, 200, owner.content)
        bodies = [message["body"] for message in owner.json()["messages"]]
        self.assertIn("Wir melden uns mit Optionen.", bodies)
        self.assertNotIn("Interne Notiz", bodies)

        other = self.client.get(f"/api/mobile/conversations/{item.thread_id}/", **self.other_auth)
        self.assertEqual(other.status_code, 404)

        reply = self.post_json(
            f"/api/mobile/conversations/{item.thread_id}/",
            {"body": "Danke, vormittags wäre ideal."},
        )
        self.assertEqual(reply.status_code, 200, reply.content)
        self.assertTrue(item.thread.messages.filter(sender=self.user, body__startswith="Danke").exists())

        generic = self.post_json(
            "/api/mobile/conversations/",
            {"subject": "Allgemeine Frage", "body": "Bitte um Rückmeldung."},
        )
        self.assertEqual(generic.status_code, 201, generic.content)
        self.assertEqual(Thread.objects.filter(user=self.user).count(), 2)

        closed = self.post_json(f"/api/mobile/conversations/{generic.json()['thread_id']}/close/")
        self.assertEqual(closed.status_code, 200)
        blocked_reply = self.post_json(
            f"/api/mobile/conversations/{generic.json()['thread_id']}/",
            {"body": "Noch eine Nachricht"},
        )
        self.assertEqual(blocked_reply.status_code, 409)
        self.assertEqual(blocked_reply.json()["error"], "conversation_closed")

    def test_full_export_contains_only_current_users_p3_data_and_visible_messages(self):
        challenge = Challenge.objects.create(
            title="Export Challenge",
            challenge_type="learning",
            target_count=1,
            reward_coins=0,
            starts_at=timezone.now() - timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1),
        )
        ChallengeParticipation.objects.create(user=self.user, challenge=challenge, progress=1)
        ChallengeParticipation.objects.create(user=self.other, challenge=challenge, progress=1)

        thread = Thread.objects.create(user=self.user, subject="Export Thread")
        Message.objects.create(thread=thread, sender=self.user, body="Sichtbar", is_internal=False)
        Message.objects.create(thread=thread, sender=self.staff, body="Intern", is_internal=True)
        other_thread = Thread.objects.create(user=self.other, subject="Fremd")
        Message.objects.create(thread=other_thread, sender=self.other, body="Fremde Nachricht", is_internal=False)

        response = self.client.get("/api/mobile/export/", **self.auth)
        self.assertEqual(response.status_code, 200, response.content)
        data = response.json()["data"]
        self.assertEqual(len(data["gamification"]["challenge_participations"]), 1)
        self.assertEqual([item["subject"] for item in data["conversations"]], ["Export Thread"])
        self.assertEqual([message["body"] for message in data["conversations"][0]["messages"]], ["Sichtbar"])
