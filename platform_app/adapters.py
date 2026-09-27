from allauth.account.adapter import DefaultAccountAdapter


class AestheticAccountAdapter(DefaultAccountAdapter):
    MOBILE_SOCIAL_SESSION_KEY = "aesthetic_mobile_social"
    MOBILE_SOCIAL_FINISH = "/mobile-social/finish/"

    def _mobile_social_redirect(self, request):
        if request.session.get(self.MOBILE_SOCIAL_SESSION_KEY):
            return self.MOBILE_SOCIAL_FINISH
        return ""

    def get_login_redirect_url(self, request):
        target = self._mobile_social_redirect(request)
        if target:
            return target
        return super().get_login_redirect_url(request)

    def get_signup_redirect_url(self, request):
        target = self._mobile_social_redirect(request)
        if target:
            return target
        return super().get_signup_redirect_url(request)
