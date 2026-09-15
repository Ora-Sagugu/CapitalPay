"""Helpers for tests that hit operations APIs."""
from apps.rbac.models import Role, UserRole


def attach_super_admin(user):
    """Give a SystemUser Super Admin so existing API tests keep full access."""
    role, _ = Role.objects.get_or_create(
        code="super_admin",
        defaults={
            "name": "Super Admin",
            "description": "Full access to all functions and data",
            "is_system": True,
        },
    )
    UserRole.objects.get_or_create(user=user, role=role)
    return user
