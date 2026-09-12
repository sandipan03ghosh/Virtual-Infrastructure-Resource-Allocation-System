from django.contrib.auth.decorators import user_passes_test
from django.core.exceptions import PermissionDenied


def _require_role(test):
    def check(user):
        if user.is_authenticated and not test(user):
            raise PermissionDenied
        return test(user)
    return user_passes_test(check)


manager_required = _require_role(lambda u: u.is_superuser)
staff_or_manager_required = _require_role(lambda u: u.is_staff)
