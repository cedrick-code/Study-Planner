from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import StudyTask


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')


class StudyTaskForm(forms.ModelForm):
    class Meta:
        model = StudyTask
        fields = ('title', 'description', 'due_date', 'completed')
        widgets = {'due_date': forms.DateInput(attrs={'type': 'date'})}
