from django.contrib import admin
from django.urls import include, path, reverse_lazy
from django.views.generic import RedirectView

admin.site.site_header = "A+ Esthetic Verwaltung"
admin.site.site_title = "A+ Esthetic Admin"
admin.site.index_title = "Verwaltung"

urlpatterns = [
    path("secure-admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("login/", RedirectView.as_view(url=reverse_lazy("account_login"), permanent=False), name="login"),
    path("", include("p0_app.urls")),
    path("", include("p1_app.urls")),
    path("", include("platform_app.urls")),
]
