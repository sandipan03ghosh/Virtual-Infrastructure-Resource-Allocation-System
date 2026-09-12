from django.test import TestCase
from staff.forms import StaffRegisterForm


class StaffRegisterFormTest(TestCase):
    def test_valid_data(self):
        form = StaffRegisterForm(data={
            'username': 'newclerk',
            'email': 'newclerk@example.com',
            'password1': 'S3cure!Pass123',
            'password2': 'S3cure!Pass123',
        })
        self.assertTrue(form.is_valid())

    def test_missing_email_is_invalid(self):
        form = StaffRegisterForm(data={
            'username': 'newclerk',
            'password1': 'S3cure!Pass123',
            'password2': 'S3cure!Pass123',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('email', form.errors)

    def test_password_mismatch_is_invalid(self):
        form = StaffRegisterForm(data={
            'username': 'newclerk',
            'email': 'newclerk@example.com',
            'password1': 'S3cure!Pass123',
            'password2': 'Different!Pass456',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('password2', form.errors)
