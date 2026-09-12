from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from user.forms import CreateUserForm, UserUpdateForm, ProfileUpdateForm

class TestViews(TestCase):

    def setUp(self):
        self.client = Client()
        self.register_url = reverse('user-register')
        self.logout_url = reverse('user-logout')
        self.profile_url = reverse('user-profile')
        self.profile_update_url = reverse('user-profile-update')
        self.user = User.objects.create_user(username='testuser', email='test@example.com', password='testpassword')

    def test_register_view_GET(self):
        response = self.client.get(self.register_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'user/register.html')

    def test_register_view_POST(self):
        response = self.client.post(self.register_url, {
            'username': 'newuser',
            'email': 'new@example.com',
            'password1': '123@Srinjoy',
            'password2': '123@Srinjoy'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('user-login'))

    def test_logout_view(self):
        response = self.client.get(self.logout_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'user/logout.html')

    def test_profile_view(self):
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'user/profile.html')

    def test_profile_update_view_GET(self):
        self.client.login(username='testuser', password='testpassword')
        response = self.client.get(self.profile_update_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'user/profile_update.html')

    def test_profile_update_view_POST(self):
        self.client.login(username='testuser', password='testpassword')
        response = self.client.post(self.profile_update_url, {
            'username': 'updateduser',
            'email': 'updated@example.com',
            'address': '123 Updated St',
            'phone': '1234567890',
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('user-profile'))
