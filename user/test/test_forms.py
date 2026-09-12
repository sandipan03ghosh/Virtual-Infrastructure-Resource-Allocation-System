from django.test import TestCase
from user.forms import CreateUserForm, UserUpdateForm, ProfileUpdateForm

class TestForms(TestCase):
    
    def test_create_user_form_valid_data(self):
        form = CreateUserForm(data={
            'username': 'testuser',
            'email': 'test@example.com',
            'password1': 'testpassword',
            'password2': 'testpassword'
        })
        
        self.assertTrue(form.is_valid())
    
    def test_create_user_form_no_data(self):
        form = CreateUserForm(data={})
        
        self.assertFalse(form.is_valid())
        self.assertEqual(len(form.errors), 4)  
    
    def test_user_update_form_valid_data(self):
        form = UserUpdateForm(data={
            'username': 'newusername',
            'email': 'new@example.com'
        })
        
        self.assertTrue(form.is_valid())
    
    def test_user_update_form_no_data(self):
        form = UserUpdateForm(data={})
        
        self.assertFalse(form.is_valid())
    
    def test_profile_update_form_valid_data(self):
        form = ProfileUpdateForm(data={
            'address': '123 Geri St',
            'phone': '7603040347',
        })
        
        self.assertTrue(form.is_valid())
    
    def test_profile_update_form_no_data(self):
        form = ProfileUpdateForm(data={})
        
        self.assertFalse(form.is_valid())
