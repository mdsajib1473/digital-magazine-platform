from django.contrib.auth import login
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import CustomSignupForm


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
