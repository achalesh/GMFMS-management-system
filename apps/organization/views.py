from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render

from apps.accounts.policies import require_capability

from .forms import OrganizationForm, SystemForm
from .models import OrganizationSetting, SystemSetting
from .services import update_settings


def settings_page(request, *, model, form_class, title, name):
    instance = model.objects.get(pk=1)
    form = form_class(request.POST or None, instance=instance)
    if request.method == "POST" and form.is_valid():
        try:
            update_settings(
                actor=request.user,
                model=model,
                values={key: form.cleaned_data[key] for key in form_class.Meta.fields},
                expected_revision=form.cleaned_data["expected_revision"],
            )
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(
                request, "Settings saved. This change has been recorded in the audit log."
            )
            return redirect(name)
    return render(
        request,
        "organization/settings.html",
        {"form": form, "heading": title, "is_system": model is SystemSetting},
    )


@require_capability("organization.change")
def organization(request):
    return settings_page(
        request,
        model=OrganizationSetting,
        form_class=OrganizationForm,
        title="Organization settings",
        name="organization:settings",
    )


@require_capability("system.change")
def system(request):
    return settings_page(
        request,
        model=SystemSetting,
        form_class=SystemForm,
        title="System & privacy policy",
        name="organization:system",
    )
