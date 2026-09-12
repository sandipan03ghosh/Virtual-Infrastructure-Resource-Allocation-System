from django.test import SimpleTestCase
from django.urls import reverse, resolve
from user.views import register, check, profile, profile_update, logout_view


class TestUrls(SimpleTestCase):
    
    def test_register_url_is_resolved(self):
        url=reverse('user-register')
        print(resolve(url))
        self.assertEqual(resolve(url).func, register)
        
    def test_check_url_is_resolved(self):
        url=reverse('user-check')
        print(resolve(url))
        self.assertEqual(resolve(url).func, check)
        
    def test_profile_url_is_resolved(self):
        url=reverse('user-profile')
        print(resolve(url))
        self.assertEqual(resolve(url).func, profile)
        
    def test_profile_update_url_is_resolved(self):
        url=reverse('user-profile-update')
        print(resolve(url))
        
    def test_logout_url_is_resolved(self):
        url=reverse('user-logout')
        print(resolve(url))
        self.assertEqual(resolve(url).func, logout_view)    
