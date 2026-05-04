from .permissions import build_role_context, ensure_role_groups


def role_access(request):
    ensure_role_groups()
    return build_role_context(getattr(request, 'user', None))
