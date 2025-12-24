from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _

class UppercaseValidator:
    def validate(self, password, user=None):
        if not any(char.isupper() for char in password):
            raise ValidationError(
                _("The password must contain at least one uppercase letter."),
                code='password_no_upper',
            )

    def get_help_text(self):
        return _("Your password must contain at least one uppercase letter.")


class LowercaseValidator:
    def validate(self, password, user=None):
        if not any(char.islower() for char in password):
            raise ValidationError(
                _("The password must contain at least one lowercase letter."),
                code='password_no_lower',
            )

    def get_help_text(self):
        return _("Your password must contain at least one lowercase letter.")


class SpecialCharacterValidator:
    def __init__(self):
        self.special_characters = "[~!@#\$%\^&\*\(\)_\+{}\":;'\[\]]"

    def validate(self, password, user=None):
        if not any(char in self.special_characters for char in password):
            raise ValidationError(
                _("The password must contain at least one special character."),
                code='password_no_special',
            )

    def get_help_text(self):
        return _("Your password must contain at least one special character.")


class NumericValidator:
    def validate(self, password, user=None):
        if not any(char.isdigit() for char in password):
            raise ValidationError(
                _("The password must contain at least one number."),
                code='password_no_number',
            )

    def get_help_text(self):
        return _("Your password must contain at least one number.")


class NoSpacesValidator:
    def validate(self, password, user=None):
        if ' ' in password:
            raise ValidationError(
                _("The password cannot contain spaces."),
                code='password_has_spaces',
            )

    def get_help_text(self):
        return _("Your password cannot contain spaces.") 