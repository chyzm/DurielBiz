from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from .models import User
from reports.models import Branch


def get_role_home_url(user):
    if user.role == User.Role.INVENTORY:
        return "inventory:overview"
    return "reports:dashboard"


def is_admin_user(user):
    return bool(getattr(user, "is_authenticated", False) and getattr(user, "role", "") == User.Role.ADMIN)


def get_user_branch(user):
    if not getattr(user, "is_authenticated", False) or is_admin_user(user):
        return None
    return getattr(user, "branch", None)


def active_branches_for_user(user):
    branches = Branch.objects.filter(is_active=True).order_by("name")
    if is_admin_user(user):
        return branches
    branch = get_user_branch(user)
    if branch is None:
        return branches.none()
    return branches.filter(pk=branch.pk)


def scope_queryset_to_user_branch(queryset, user, field_name="branch"):
    if is_admin_user(user):
        return queryset
    branch = get_user_branch(user)
    if branch is None:
        return queryset.none()
    return queryset.filter(**{field_name: branch})


def role_required(*allowed_roles):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")
            if request.user.role not in allowed_roles:
                messages.error(request, "You do not have permission to access that page.")
                return redirect(get_role_home_url(request.user))
            if request.user.role != User.Role.ADMIN and not getattr(request.user, "branch_id", None):
                messages.error(request, "Your account is not assigned to a branch.")
                return redirect("accounts:logout")
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator
