"""URL configuration for the accounts app.

Includes Django's full ``django.contrib.auth.urls`` set so we get login,
logout, and password change/reset flows for free, then layers our custom
signup view + styled login/password-reset forms on top.

IMPORTANT: every override below MUST appear *before* the catch-all
``include("django.contrib.auth.urls")`` -- Django's URL resolver walks
this list top-to-bottom and picks the first match, so a contrib.auth URL
listed earlier wins.
"""

from django.contrib.auth.views import (
    LoginView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetView,
)
from django.urls import include, path, reverse_lazy

from .forms import (
    StyledAuthenticationForm,
    StyledPasswordChangeForm,
    StyledPasswordResetForm,
    StyledSetPasswordForm,
)
from .views import LibraryView, ProfileView, SignupView

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("library/", LibraryView.as_view(), name="library"),
    path("profile/", ProfileView.as_view(), name="profile"),
    # Override the stock login view so we can swap in the styled form.
    path(
        "login/",
        LoginView.as_view(authentication_form=StyledAuthenticationForm),
        name="login",
    ),
    # Password reset: request step -- email input. Styled form so the <input>
    # matches the login/signup aesthetic.
    path(
        "password_reset/",
        PasswordResetView.as_view(form_class=StyledPasswordResetForm),
        name="password_reset",
    ),
    # Password reset: confirm step -- two password inputs. Styled form for
    # consistent input rendering.
    path(
        "reset/<uidb64>/<token>/",
        PasswordResetConfirmView.as_view(form_class=StyledSetPasswordForm),
        name="password_reset_confirm",
    ),
    # Password change (logged-in flow): three password inputs. Styled form
    # + explicit success_url so the done page can reverse() cleanly even
    # though we keep the default template_name.
    path(
        "password_change/",
        PasswordChangeView.as_view(
            form_class=StyledPasswordChangeForm,
            success_url=reverse_lazy("password_change_done"),
        ),
        name="password_change",
    ),
    # Delegate the rest (logout, password_change_done, password_reset_done,
    # password_reset_complete, ...) to the default contrib.auth URLConf.
    path("", include("django.contrib.auth.urls")),
]
