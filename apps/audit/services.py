import logging

from .models import AuditLog

logger = logging.getLogger("gmfms.audit")


def record_event(*, actor, action, entity, old_values=None, new_values=None, reason=""):
    event = AuditLog.objects.create(
        user=actor if actor and actor.is_authenticated else None,
        action=action,
        entity_type=entity._meta.label_lower,
        entity_id=str(entity.pk),
        old_values=old_values or {},
        new_values=new_values or {},
        reason=reason,
    )
    logger.info("event_id=%s action=%s", event.pk, action)
    return event
