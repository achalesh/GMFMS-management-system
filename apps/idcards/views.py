from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from apps.audit.models import AuditLog
from apps.facilitators.selectors import permitted, registry_for
from apps.registrations.security import staff_budget

from .services import card_state, download_card, issue_card, revoke_card


class DecisionForm(forms.Form):
    revision = forms.IntegerField(widget=forms.HiddenInput)
    reason = forms.CharField(
        max_length=2000, widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"})
    )


class DownloadForm(DecisionForm):
    format = forms.ChoiceField(
        choices=[
            ("pdf", "Card size - two pages"),
            ("print_pdf", "A4 sheets with crop marks - two pages"),
        ],
        widget=forms.Select(attrs={"class": "form-control"}),
    )


def record(user, pk):
    return get_object_or_404(registry_for(user, "cards.issue"), pk=pk)


@login_required
@never_cache
def index(request, pk):
    f = record(request.user, pk)
    cards = list(
        f.cards.select_related(
            "facilitator__current_appointment__panchayat__block__district__state",
            "facilitator__application",
            "generated_by",
        )
    )
    for card in cards:
        card.current_state = card_state(card)
    return render(request, "idcards/index.html", {"facilitator": f, "cards": cards})


@login_required
@never_cache
@staff_budget("card-generation", 30)
def generate(request, pk):
    f = record(request.user, pk)
    form = DecisionForm(request.POST or None, initial={"revision": f.revision})
    if request.method == "POST" and form.is_valid():
        try:
            card = issue_card(actor=request.user, facilitator_id=f.pk, **form.cleaned_data)
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(
                request, "New card version generated. Earlier issued versions are superseded."
            )
            return redirect("idcards:detail", pk=f.pk, card_id=card.pk)
    return render(
        request,
        "idcards/action.html",
        {
            "facilitator": f,
            "form": form,
            "label": "Generate new card version",
            "operation": "generate",
        },
    )


@login_required
@never_cache
def detail(request, pk, card_id):
    f = record(request.user, pk)
    card = get_object_or_404(f.cards, pk=card_id)
    return render(
        request,
        "idcards/detail.html",
        {
            "facilitator": f,
            "card": card,
            "state": card_state(card),
            "can_revoke": permitted(request.user, f.current_appointment.panchayat),
            "events": AuditLog.objects.filter(
                entity_type="idcards.identitycard", entity_id=str(card.pk)
            )
            .select_related("user")
            .order_by("-timestamp")[:100],
        },
    )


@login_required
@never_cache
@require_safe
def preview(request, pk, card_id, side):
    f = record(request.user, pk)
    card = get_object_or_404(f.cards, pk=card_id)
    if side not in {"front", "back"}:
        raise Http404
    if card_state(card) != "CURRENT":
        return HttpResponse("This card is not current; preview unavailable.", status=409)
    try:
        response = FileResponse(getattr(card, side).open("rb"), content_type="image/png")
    except OSError:
        raise Http404 from None
    response["X-Content-Type-Options"] = "nosniff"
    return response


@login_required
@never_cache
def action(request, pk, card_id, operation):
    f = record(request.user, pk)
    card = get_object_or_404(f.cards, pk=card_id)
    if operation not in {"download", "revoke"}:
        raise Http404
    if operation == "revoke" and not permitted(request.user, f.current_appointment.panchayat):
        raise PermissionDenied
    form = (DownloadForm if operation == "download" else DecisionForm)(
        request.POST or None, initial={"revision": f.revision}
    )
    if request.method == "POST" and form.is_valid():
        try:
            if operation == "revoke":
                revoke_card(actor=request.user, card_id=card.pk, **form.cleaned_data)
            else:
                _, content = download_card(actor=request.user, card_id=card.pk, **form.cleaned_data)
                response = HttpResponse(content, content_type="application/pdf")
                response["Content-Disposition"] = (
                    'attachment; filename="' + card.card_number + '.pdf"'
                )
                response["X-Content-Type-Options"] = "nosniff"
                return response
        except ValidationError as exc:
            form.add_error(None, exc)
        else:
            messages.success(
                request, "Card revoked. The facilitator identity has not been revoked."
            )
            return redirect("idcards:detail", pk=f.pk, card_id=card.pk)
    return render(
        request,
        "idcards/action.html",
        {
            "facilitator": f,
            "card": card,
            "form": form,
            "operation": operation,
            "label": "Download / reprint card" if operation == "download" else "Revoke card",
        },
    )
