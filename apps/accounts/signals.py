import logging

from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger("gmfms.security")


@receiver(user_logged_in)
def login_record(sender, request, user, **kwargs):
    from apps.audit.services import record_event

    record_event(actor=user, action="auth.login", entity=user)
    logger.info("Authentication succeeded user_id=%s", user.pk)


@receiver(user_logged_out)
def logout_record(sender, request, user, **kwargs):
    if user:
        from apps.audit.services import record_event

        record_event(actor=user, action="auth.logout", entity=user)
        logger.info("Session ended user_id=%s", user.pk)


@receiver(user_login_failed)
def failure_record(sender, **kwargs):
    # Do not log submitted credentials or raw identifying values.
    logger.warning("Authentication failed")


@receiver(post_save, sender="accounts.User")
def bootstrap_superuser_role(sender, instance, created, **kwargs):
    if instance.is_superuser:
        from .models import Role, UserJurisdiction, UserRole

        role, _ = Role.objects.get_or_create(
            code=Role.Code.SUPER_ADMIN, defaults={"description": "Full system administration"}
        )
        assignment, _ = UserRole.objects.get_or_create(user=instance, role=role)
        UserJurisdiction.objects.get_or_create(assignment=assignment, scope="STATE")
