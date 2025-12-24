from django import forms
from django.contrib.auth.forms import AuthenticationForm
from .models import User

class UserRegistrationForm(forms.ModelForm):
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Enter password',
            'class': 'form-control password-input'
        }),
        help_text="""
        <ul class="password-requirements">
            <li>At least 8 characters long</li>
            <li>At least one uppercase letter</li>
            <li>At least one lowercase letter</li>
            <li>At least one number</li>
            <li>At least one special character</li>
            <li>Cannot contain spaces</li>
            <li>Cannot be too similar to your other personal information</li>
            <li>Cannot be a commonly used password</li>
        </ul>
        """
    )
    confirm_password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'placeholder': 'Confirm password',
            'class': 'form-control password-input'
        })
    )

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name', 'password']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter email'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter first name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter last name'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError("Passwords do not match")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user

class UserLoginForm(AuthenticationForm):
    username = forms.EmailField(widget=forms.EmailInput(attrs={'autofocus': True, 'class': 'form-control', 'placeholder': 'Your email address'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control password-input', 'placeholder': 'Your password'}))
    
    def clean(self):
        email = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')
        
        if email and password:
            try:
                user = User.objects.get(email=email)
                # Skip approval check for admin users
                if not user.is_staff and not user.is_approved:
                    raise forms.ValidationError("Your account is pending approval.")
            except User.DoesNotExist:
                raise forms.ValidationError("Invalid email or password.")
        
        return super().clean() 