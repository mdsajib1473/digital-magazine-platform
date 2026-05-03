"""Auth forms for the Unmad Digital Archive."""

from django import forms
from django.contrib.auth.forms import (
    AuthenticationForm,
    PasswordChangeForm,
    PasswordResetForm,
    SetPasswordForm,
    UserCreationForm,
)

from .models import CustomUser

# Single source of truth for input styling. Keeps every auth field consistent
# with the issue card / search bar look-and-feel from Phase 4a.
INPUT_CLASSES = (
    "block w-full px-4 py-2.5 text-sm bg-white border border-slate-300 "
    "rounded-md shadow-sm placeholder-slate-400 "
    "focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 "
    "transition"
)


class _TailwindFormMixin:
    """Apply INPUT_CLASSES to every visible widget on a form.

    Composing this with Django's stock auth forms means we get styled inputs
    without rewriting form rendering or pulling in django-crispy-forms.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get("class", "")
            field.widget.attrs["class"] = f"{existing} {INPUT_CLASSES}".strip()
            # Make autofocus on the first field; small DX win on login/signup.
            if not field.widget.attrs.get("autofocus") and field is next(
                iter(self.fields.values())
            ):
                field.widget.attrs["autofocus"] = "autofocus"


class StyledAuthenticationForm(_TailwindFormMixin, AuthenticationForm):
    """Vanilla AuthenticationForm with Tailwind-styled inputs."""


class CustomSignupForm(_TailwindFormMixin, UserCreationForm):
    """Signup form keyed on our CustomUser model.

    - Email is required at the form level (model allows blank, but we want
      an email on file for password reset and purchase receipts).
    - phone_number stays optional, matching the model.
    """

    # Explicitly required -- password reset + purchase receipts both depend on
    # having an email on file, so we enforce it at the form level even though
    # AbstractUser.email allows blank.
    email = forms.EmailField(
        required=True,
        label="Email address",
        help_text="Required. Used for password reset and purchase receipts.",
        widget=forms.EmailInput(attrs={"placeholder": "you@example.com"}),
    )
    phone_number = forms.CharField(
        required=False,
        max_length=20,
        label="Phone number",
        help_text="Optional. We'll never share it.",
    )

    class Meta:
        model = CustomUser
        fields = ("username", "email", "phone_number")

    def clean_email(self):
        """Reject duplicate emails proactively (the DB has no unique index)."""
        email = self.cleaned_data["email"].strip().lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email


class StyledPasswordResetForm(_TailwindFormMixin, PasswordResetForm):
    """Password reset request form (email input) with Tailwind-styled input."""


class StyledSetPasswordForm(_TailwindFormMixin, SetPasswordForm):
    """Set-new-password form (two password inputs) with Tailwind-styled inputs."""


class StyledPasswordChangeForm(_TailwindFormMixin, PasswordChangeForm):
    """Logged-in password change form with Tailwind-styled inputs."""


class UserProfileForm(_TailwindFormMixin, forms.ModelForm):
    """Let authenticated users edit their own contact details.

    Email is kept required here (mirrors signup) because password reset and
    future purchase receipts both depend on a valid address being on file.
    Username is intentionally NOT editable -- changing it would invalidate
    saved URLs and support requests.
    """

    email = forms.EmailField(
        required=True,
        label="Email address",
        help_text="Required. Used for password reset and purchase receipts.",
    )

    class Meta:
        model = CustomUser
        fields = ("email", "first_name", "last_name", "phone_number")
        labels = {
            "first_name": "First name",
            "last_name": "Last name",
            "phone_number": "Phone number",
        }

    def clean_email(self):
        """Reject duplicates, but let the current user keep their own email."""
        email = self.cleaned_data["email"].strip().lower()
        qs = CustomUser.objects.filter(email__iexact=email)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email
