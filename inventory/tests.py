from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .permissions import (
	ROLE_MANAGER,
	ROLE_OTHER,
	ROLE_STAFF,
	assign_user_role,
	ensure_role_groups,
)


class RoleAccessTests(TestCase):
	def setUp(self):
		ensure_role_groups()
		self.User = get_user_model()

	def create_user_with_role(self, username, role_code):
		user = self.User.objects.create_user(username=username, password='pass12345')
		assign_user_role(user, role_code)
		return user

	def test_other_role_only_sees_dashboard(self):
		user = self.create_user_with_role('other', ROLE_OTHER)
		self.client.force_login(user)

		response = self.client.get(reverse('dashboard'))
		context = response.context[-1] if isinstance(response.context, list) else response.context

		self.assertEqual(response.status_code, 200)
		self.assertTrue(context['show_dashboard_link'])
		self.assertFalse(context['show_forecast_link'])
		self.assertFalse(context['show_material_link'])
		self.assertFalse(context['show_product_link'])
		self.assertFalse(context['show_abc_link'])
		self.assertFalse(context['show_alert_link'])
		self.assertFalse(context['show_import_link'])
		self.assertFalse(context['show_system_link'])
		self.assertFalse(context['show_access_control_link'])

	def test_staff_role_cannot_open_material_page(self):
		user = self.create_user_with_role('staff', ROLE_STAFF)
		self.client.force_login(user)

		response = self.client.get(reverse('material-list'))

		self.assertEqual(response.status_code, 403)
		self.assertContains(response, 'Bạn chưa được cấp quyền truy cập trang web này.', status_code=403)

	def test_manager_role_cannot_open_system_page(self):
		user = self.create_user_with_role('manager', ROLE_MANAGER)
		self.client.force_login(user)

		response = self.client.get(reverse('system-settings'))

		self.assertEqual(response.status_code, 403)
		self.assertContains(response, 'Bạn chưa được cấp quyền truy cập trang web này.', status_code=403)

	def test_admin_role_can_open_access_control(self):
		user = self.User.objects.create_superuser(username='admin', password='pass12345')
		self.client.force_login(user)

		response = self.client.get(reverse('access-control'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Quyền truy cập')
