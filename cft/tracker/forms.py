# tracker/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.db import transaction
from .models import Profile
from .models import User, Profile, Challenge, Community
from django.contrib.auth.forms import UserCreationForm

class UserRegisterForm(UserCreationForm):
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(max_length=254, required=True, help_text='Required. Enter a valid email.')

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('first_name', 'last_name', 'username', 'email')

    def __init__(self, *args, **kwargs):
        super(UserRegisterForm, self).__init__(*args, **kwargs)
        for visible in self.visible_fields():
            visible.field.widget.attrs['class'] = 'form-control'
            if visible.name == 'first_name':
                visible.field.widget.attrs['placeholder'] = 'First Name'
            if visible.name == 'last_name':
                visible.field.widget.attrs['placeholder'] = 'Last Name'
            if visible.name == 'username':
                visible.field.widget.attrs['placeholder'] = 'Username'
            if visible.name == 'email':
                visible.field.widget.attrs['placeholder'] = 'Email Address'
            if visible.name == 'password1':
                visible.field.widget.attrs['placeholder'] = 'Password'
            if visible.name == 'password2':
                visible.field.widget.attrs['placeholder'] = 'Confirm Password'


    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data["first_name"]
        user.last_name = self.cleaned_data["last_name"]
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user

class UserUpdateForm(forms.ModelForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email']

    # NEW: Add __init__ to apply styling
    def __init__(self, *args, **kwargs):
        super(UserUpdateForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['phone_number', 'location']

    # NEW: Add __init__ to apply styling
    def __init__(self, *args, **kwargs):
        super(ProfileUpdateForm, self).__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs.update({'class': 'form-control'})

class ChallengeForm(forms.ModelForm):
    end_date = forms.DateField(widget=forms.DateInput(attrs={'type': 'date'}))

    class Meta:
        model = Challenge
        fields = ['community', 'title', 'description', 'goal', 'unit', 'reward_achievement', 'end_date']
        help_texts = {
            'reward_achievement': 'Optional. Select a badge to award upon completion.'
        }