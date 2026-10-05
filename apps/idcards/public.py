import re

from .models import IdentityCard
from .services import card_state


def with_card(profile, facilitator, token):
    if not re.fullmatch(r"[A-Za-z0-9_-]{32,64}", token):
        return None
    card = IdentityCard.objects.filter(facilitator=facilitator, public_token=token).first()
    if not card:
        return None
    state = card_state(card)
    profile["card"] = {
        "number": card.card_number,
        "version": card.version,
        "status": state,
        "issued_on": card.issue_date.isoformat(),
        "valid_until": card.valid_until.isoformat(),
    }
    if state != "CURRENT":
        profile["identity_status"] = profile["status"]
        profile["is_authorized"] = False
        profile["status_label"] = {
            "REVOKED": "ID Card Revoked",
            "SUPERSEDED": "ID Card Superseded",
            "EXPIRED": "ID Card Expired",
            "OUTDATED": "ID Card Outdated",
            "INACTIVE": "Card Authorization Inactive",
        }[state]
        profile["status"] = (
            "REVOKED" if state == "REVOKED" else "EXPIRED" if state == "EXPIRED" else "INACTIVE"
        )
        for key in ["mobile", "email", "social_profiles"]:
            profile.pop(key, None)
    return profile
