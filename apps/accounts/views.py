from axes.decorators import axes_dispatch
from django.contrib import messages
from django.contrib.auth import views as auth_views
from django.shortcuts import render
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters

from apps.audit.services import record_event

from .forms import SafePasswordResetForm, StaffAuthenticationForm
from .models import User
from .policies import require_capability
from .rate_limit import PasswordResetThrottleMixin


@method_decorator(axes_dispatch, name="dispatch")
class LoginView(auth_views.LoginView):
    template_name = "registration/login.html"
    authentication_form = StaffAuthenticationForm


class PasswordChangeView(auth_views.PasswordChangeView):
    template_name = "registration/password_form.html"
    success_url = reverse_lazy("dashboard:home")
    extra_context = {"heading": "Change your password", "button_label": "Update password"}

    def form_valid(self, form):
        response = super().form_valid(form)
        record_event(
            actor=self.request.user, action="auth.password_changed", entity=self.request.user
        )
        messages.success(self.request, "Your password has been updated.")
        return response


class PasswordResetView(PasswordResetThrottleMixin, auth_views.PasswordResetView):
    form_class = SafePasswordResetForm
    template_name = "registration/password_form.html"
    email_template_name = "registration/password_reset_email.txt"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = reverse_lazy("accounts:password_reset_done")
    extra_context = {"heading": "Reset your password", "button_label": "Send reset link"}


@method_decorator(sensitive_post_parameters(), name="dispatch")
@method_decorator(never_cache, name="dispatch")
class PasswordResetConfirmView(auth_views.PasswordResetConfirmView):
    template_name = "registration/password_reset_confirm.html"
    success_url = reverse_lazy("accounts:password_reset_complete")

    def form_valid(self, form):
        response = super().form_valid(form)
        record_event(actor=self.user, action="auth.password_reset", entity=self.user)
        return response


@require_capability("accounts.manage")
def users(request):
    from django.core.paginator import Paginator

    accounts = User.objects.order_by("username").prefetch_related("role_assignments__role")
    return render(
        request,
        "accounts/users.html",
        {"page": Paginator(accounts, 25).get_page(request.GET.get("page"))},
    )
