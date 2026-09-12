from django.test import TestCase
from django.contrib.auth.models import User
from user.models import Profile

class ProfileModelTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Set up non-modified objects used by all test methods
        cls.user = User.objects.create_user(username='test', password='Agniva@2004')

    def test_str_method(self):
        # Since the Profile object is created automatically upon user creation,
        # we should access it via the user.profile attribute
        profile = self.user.profile
        expected_str = f'{self.user.username}-Profile'
        self.assertEqual(str(profile), expected_str)