from .models import UserProfile


def is_admin_identity(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    return bool(
        user.is_superuser
        or profile.role == "admin"
        or (user.is_staff and profile.role in {"admin", "manager"})
    )


def account_state(user):
    profile, _ = UserProfile.objects.get_or_create(user=user)
    if is_admin_identity(user):
        return {
            "locked": False,
            "profile_complete": True,
            "email_verified": True,
            "phone_verified": True,
            "missing": [],
            "auth_provider": profile.auth_provider,
        }

    if not profile.onboarding_required:
        return {
            "locked": False,
            "profile_complete": True,
            "email_verified": True,
            "phone_verified": True,
            "missing": [],
            "auth_provider": profile.auth_provider,
        }

    missing = []
    if not user.first_name.strip():
        missing.append("first_name")
    if not user.last_name.strip():
        missing.append("last_name")
    if not profile.salutation:
        missing.append("salutation")
    if not profile.phone.strip():
        missing.append("phone")
    if not profile.email_verified_at:
        missing.append("email_verification")
    if not profile.phone_verified_at:
        missing.append("phone_verification")

    complete = not missing and bool(profile.profile_completed_at)
    return {
        "locked": not complete,
        "profile_complete": complete,
        "email_verified": bool(profile.email_verified_at),
        "phone_verified": bool(profile.phone_verified_at),
        "missing": missing,
        "auth_provider": profile.auth_provider,
    }
