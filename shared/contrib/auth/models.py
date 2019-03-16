from typing import Dict, List, Optional, Set, Tuple, Union
from datetime import datetime, timedelta
import jwt
from django.contrib.auth.models import (
    AbstractBaseUser,
    UnicodeUsernameValidator,
    UserManager,
    send_mail,
    timezone,
)

from django.contrib.auth.models import _
from django.db import models
from rest_framework_jwt import utils
from shared.backends import ValidationError

PersonalInfoType = Union[str, Dict[str, str]]


def jwt_get_secret_key(payload=None, model=None):
    """
    For enhanced security you may want to use a secret key based on user.

    This way you have an option to logout only this user if:
        - token is compromised
        - password is changed
        - etc.
    """
    if utils.api_settings.JWT_GET_USER_SECRET_KEY:
        User = model  # noqa: N806
        user = User.objects.get(pk=payload.get('user_id'))
        key = str(utils.api_settings.JWT_GET_USER_SECRET_KEY(user))
        return key
    return utils.api_settings.JWT_SECRET_KEY


def jwt_decode_handler(token, model=None):
    options = {
        'verify_exp': utils.api_settings.JWT_VERIFY_EXPIRATION,
    }
    # get user from token, BEFORE verification, to get user secret key
    unverified_payload = utils.jwt.decode(token, None, False)
    secret_key = jwt_get_secret_key(unverified_payload, model)
    return utils.jwt.decode(
        token,
        utils.api_settings.JWT_PUBLIC_KEY or secret_key,
        utils.api_settings.JWT_VERIFY,
        options=options,
        leeway=utils.api_settings.JWT_LEEWAY,
        audience=utils.api_settings.JWT_AUDIENCE,
        issuer=utils.api_settings.JWT_ISSUER,
        algorithms=[utils.api_settings.JWT_ALGORITHM])


def jwt_encode_handler(payload, model):
    key = utils.api_settings.JWT_PRIVATE_KEY or jwt_get_secret_key(
        payload, model)
    return utils.jwt.encode(payload, key,
                            utils.api_settings.JWT_ALGORITHM).decode('utf-8')


def get_payload(token: str) -> Optional[str]:
    try:
        payload = utils.jwt_decode_handler(token)
    except jwt.ExpiredSignature:
        payload = None
    except jwt.DecodeError:
        payload = None
    if not payload:
        return None
    username = utils.jwt_get_username_from_payload_handler(payload)
    return username


class VerificationSerializer(object):
    def __init__(self, model):
        self.model = model

    def _check_payload(self, token):
        # Check payload valid (based off of JSONWebTokenAuthentication,
        # may want to refactor)
        try:
            payload = jwt_decode_handler(token, self.model)
        except jwt.ExpiredSignature:
            msg = _('Signature has expired.')
            raise ValidationError(msg)
        except jwt.DecodeError:
            msg = _('Error decoding signature.')
            raise ValidationError(msg)
        return payload

    def _check_user(self, payload):
        from rest_framework_jwt.serializers import (jwt_get_username_from_payload,)
        username = jwt_get_username_from_payload(payload)

        if not username:
            msg = _('Invalid payload.')
            raise ValidationError(msg)

        # Make sure user exists
        try:
            user = self.model.objects.get_by_natural_key(username)
        except self.model.DoesNotExist:
            msg = _("User doesn't exist.")
            raise ValidationError(msg)

        if not user.is_active:
            msg = _('User account is disabled.')
            raise ValidationError(msg)

        return user


class AbstractUser(AbstractBaseUser):
    """
    An abstract base class implementing a fully featured User model with
    admin-compliant permissions.

    Username and password are required. Other fields are optional.
    """
    username_validator = UnicodeUsernameValidator()

    username = models.CharField(
        _('username'),
        max_length=150,
        unique=True,
        help_text=
        _('Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only.'
          ),
        validators=[username_validator],
        error_messages={
            'unique': _("A user with that username already exists."),
        },
    )
    first_name = models.CharField(_('first name'), max_length=30, blank=True)
    last_name = models.CharField(_('last name'), max_length=150, blank=True)
    email = models.EmailField(_('email address'), blank=True)
    is_staff = models.BooleanField(
        _('staff status'),
        default=False,
        help_text=_(
            'Designates whether the user can log into this admin site.'),
    )
    is_active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_(
            'Designates whether this user should be treated as active. '
            'Unselect this instead of deleting accounts.'),
    )
    date_joined = models.DateTimeField(_('date joined'), default=timezone.now)
    is_superuser = models.BooleanField(
        _('superuser status'),
        default=False,
        help_text=_('Designates that this user has all permissions without '
                    'explicitly assigning them.'))
    objects = UserManager()

    EMAIL_FIELD = 'email'
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = ['email']

    class Meta:
        verbose_name = _('user')
        verbose_name_plural = _('users')
        abstract = True

    def clean(self):
        super().clean()
        self.email = self.__class__.objects.normalize_email(self.email)

    def get_full_name(self):
        """
        Return the first_name plus the last_name, with a space in between.
        """
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        """Send an email to this user."""
        send_mail(subject, message, from_email, [self.email], **kwargs)

    @property
    def password_hash(self) -> str:
        return self.password

    def get_new_token(self) -> str:
        payload = utils.jwt_payload_handler(self)
        return jwt_encode_handler(payload, self.__class__)

    @classmethod
    def verify_token(cls, token: str, email: str) -> bool:
        # may want to refactor)
        result = get_payload(token)
        if not result:
            return False
        return result == email

    def mark_as_verified(self):
        self.verified_email = True
        self.save()

    @classmethod
    def validate_token(cls,token):
        validator = VerificationSerializer(cls)
        payload = validator._check_payload(token=token)
        user = validator._check_user(payload=payload)
        return {'token': token, 'user': user}


