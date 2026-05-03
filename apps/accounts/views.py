from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView, UpdateView

from apps.magazines.models import Purchase

from .forms import CustomSignupForm, UserProfileForm


class SignupView(CreateView):
    """Create a CustomUser and immediately authenticate them.

    Uses CreateView so the form/save lifecycle stays standard. After save,
    we log the user in and let LOGIN_REDIRECT_URL ('home') take them to the
    landing page -- same UX as a successful login.
    """

    form_class = CustomSignupForm
    template_name = "registration/signup.html"
    success_url = reverse_lazy("home")

    def form_valid(self, form):
        response = super().form_valid(form)
        login(self.request, self.object)
        return response


class LibraryView(LoginRequiredMixin, ListView):
    """The signed-in user's purchased issues.

    Queries Purchase (not Issue) and select_relates the joined Issue +
    Category in a single round-trip. This lets the template surface
    purchase-time metadata (date, amount paid) alongside the cover --
    information that would be lost if we filtered Issues directly.

    Access control is enforced two ways:
      1. LoginRequiredMixin -> anonymous users get 302'd to LOGIN_URL.
      2. .filter(user=self.request.user) -> the queryset can only ever
         contain the requesting user's own purchases. No risk of leaking
         someone else's library through a tampered URL parameter.
    """

    template_name = "accounts/library.html"
    context_object_name = "purchases"
    paginate_by = 12

    def get_queryset(self):
        return (
            Purchase.objects.filter(user=self.request.user)
            .select_related("issue", "issue__category")
            .order_by("-purchased_at")
        )


class ProfileView(LoginRequiredMixin, UpdateView):
    """Let an authenticated user edit their own contact details.

    Key invariants:
      - ``get_object()`` returns ``self.request.user`` -- a user can only
        ever edit their own profile; path-based tampering is impossible
        because we never read a pk/slug from the URL.
      - ``success_url`` points back at the profile page so the user sees
        the updated values and the success flash.
    """

    form_class = UserProfileForm
    template_name = "accounts/profile.html"
    success_url = reverse_lazy("profile")

    def get_object(self, queryset=None):
        return self.request.user

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Your profile has been updated.")
        return response
