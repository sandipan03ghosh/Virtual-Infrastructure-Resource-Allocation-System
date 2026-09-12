from django.shortcuts import render, redirect
from django.contrib.auth import logout
from django.contrib.auth.forms import UserCreationForm
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit
from .forms import CreateUserForm, UserUpdateForm, ProfileUpdateForm
from django.contrib import messages
# Create your views here.
def register(request):
    if request.method=='POST':
        form=CreateUserForm(request.POST)
        if form.is_valid():
            form.save() 
            username=form.cleaned_data.get('username')
            messages.success(request,f'Account has been created for {username}')
            return redirect('user-login')
            #return render(request, 'user/login.html')
    else:    
        form=CreateUserForm()
        
    helper = FormHelper()
    helper.form_method = 'post'
    helper.add_input(Submit('submit', 'Sign Up', css_class='btn-primary'))

    return render(request, 'user/register.html', {'form': form, 'helper': helper})

def logout_view(request):
    logout(request)
    # return redirect('dashboard-index')
    return render(request, 'user/logout.html')

def profile(request):
    return render(request, 'user/profile.html')

def check(request):
    if request.user.is_authenticated:
        return redirect('dashboard-index')
    else:
        return redirect('user-login')


def profile_update(request):
    if request.method=="POST":
        user_form=UserUpdateForm(request.POST, instance=request.user)
        profile_form=ProfileUpdateForm(request.POST, request.FILES, instance=request.user.profile)
        if user_form.is_valid() and profile_form.is_valid():
            user_form.save()
            profile_form.save()
            return redirect('user-profile')
    else:
        user_form=UserUpdateForm(instance=request.user)
        profile_form=ProfileUpdateForm(instance=request.user.profile)    
    context={
        'user_form':user_form,
        'profile_form':profile_form,
    }
    return render(request, 'user/profile_update.html', context)