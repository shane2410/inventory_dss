from functools import wraps

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.shortcuts import redirect, render
from django.urls import reverse


ROLE_ADMIN = 'admin'
ROLE_MANAGER = 'manager'
ROLE_STAFF = 'staff'
ROLE_OTHER = 'other'

ROLE_DEFINITIONS = (
    (ROLE_ADMIN, 'Admin'),
    (ROLE_MANAGER, 'Quản lý kho'),
    (ROLE_STAFF, 'Nhân viên kho'),
    (ROLE_OTHER, 'Khác'),
)

ROLE_LABELS = dict(ROLE_DEFINITIONS)
ALL_ROLE_CODES = tuple(code for code, _ in ROLE_DEFINITIONS)
ROLE_FORM_CHOICES = ROLE_DEFINITIONS


def ensure_role_groups():
    for role_code, _ in ROLE_DEFINITIONS:
        Group.objects.get_or_create(name=role_code)


def normalize_role_code(role_code):
    if role_code in ALL_ROLE_CODES:
        return role_code
    return ROLE_OTHER


def get_user_role_code(user):
    if not user or not user.is_authenticated:
        return ROLE_OTHER

    if user.is_superuser:
        return ROLE_ADMIN

    user_group_names = set(user.groups.values_list('name', flat=True))
    for role_code in (ROLE_MANAGER, ROLE_STAFF, ROLE_OTHER):
        if role_code in user_group_names:
            return role_code

    return ROLE_OTHER


def get_user_role_label(user):
    return ROLE_LABELS.get(get_user_role_code(user), ROLE_LABELS[ROLE_OTHER])


def build_role_context(user):
    role_code = get_user_role_code(user)
    is_admin = role_code == ROLE_ADMIN
    is_manager = role_code == ROLE_MANAGER
    is_staff = role_code == ROLE_STAFF
    is_other = role_code == ROLE_OTHER

    can_view_shared_pages = not is_other

    return {
        'current_user_role': role_code,
        'current_user_role_label': ROLE_LABELS.get(role_code, ROLE_LABELS[ROLE_OTHER]),
        'show_dashboard_link': True,
        'show_forecast_link': can_view_shared_pages,
        'show_material_link': can_view_shared_pages,
        'show_product_link': can_view_shared_pages,
        'show_abc_link': can_view_shared_pages,
        'show_alert_link': can_view_shared_pages,
        'show_inventory_analysis_link': can_view_shared_pages,
        'show_import_link': can_view_shared_pages,
        'show_multilevel_bom_link': can_view_shared_pages,
        'show_system_link': is_admin,
        'show_access_control_link': is_admin,
        'can_view_dashboard': True,
        'can_view_forecast': can_view_shared_pages,
        'can_view_material': is_admin or is_manager,
        'can_view_product': can_view_shared_pages,
        'can_view_abc': can_view_shared_pages,
        'can_view_alert': can_view_shared_pages,
        'can_view_inventory_analysis': can_view_shared_pages,
        'can_view_import': can_view_shared_pages,
        'can_view_multilevel_bom': can_view_shared_pages,
        'can_view_system': is_admin,
        'can_view_access_control': is_admin,
        'is_admin_role': is_admin,
        'is_manager_role': is_manager,
        'is_staff_role': is_staff,
        'is_other_role': is_other,
    }


def role_required(*allowed_roles):
    allowed_role_set = {normalize_role_code(role_code) for role_code in allowed_roles} or set(ALL_ROLE_CODES)

    def decorator(view_func):
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            ensure_role_groups()
            role_code = get_user_role_code(request.user)

            request.session['display_name'] = request.user.username
            request.session['is_admin'] = request.user.is_superuser
            request.session['user_role'] = role_code

            if request.user.is_superuser or role_code in allowed_role_set:
                return view_func(request, *args, **kwargs)

            return render(request, 'inventory/access_denied.html', {
                'error_message': 'Bạn chưa được cấp quyền truy cập trang web này.',
                'back_url': reverse('dashboard'),
                'current_user_role_label': ROLE_LABELS.get(role_code, ROLE_LABELS[ROLE_OTHER]),
            }, status=403)

        return wrapped_view

    return decorator


def assign_user_role(user, role_code):
    ensure_role_groups()
    role_code = normalize_role_code(role_code)

    if role_code == ROLE_ADMIN:
        user.groups.clear()
        if not user.is_superuser:
            user.is_superuser = True
            user.save(update_fields=['is_superuser'])
        return user

    if user.is_superuser:
        user.is_superuser = False
        user.save(update_fields=['is_superuser'])

    user.groups.clear()
    group = Group.objects.get(name=role_code)
    user.groups.add(group)
    return user


def create_user_with_role(username, password, role_code):
    ensure_role_groups()
    role_code = normalize_role_code(role_code)
    User = get_user_model()

    if role_code == ROLE_ADMIN:
        return User.objects.create_superuser(username=username, password=password)

    user = User.objects.create_user(username=username, password=password)
    return assign_user_role(user, role_code)
