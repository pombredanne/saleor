from __future__ import unicode_literals
from datetime import timedelta

from django.db import models
from django.contrib.auth import authenticate, get_user_model
from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils import timezone
from django.utils.crypto import get_random_string

User = get_user_model()
now = timezone.now


class ExternalUserData(models.Model):

    user = models.ForeignKey(User, related_name='external_ids')
    service = models.TextField(db_index=True)
    username = models.TextField(db_index=True)

    class Meta:
        unique_together = [['service', 'username']]


class UniqueTokenManager(models.Manager):  # this might end up in `utils`

    def __init__(self, token_field, token_length):
        self.token_field = token_field
        self.token_length = token_length
        super(UniqueTokenManager, self).__init__()

    def create(self, **kwargs):
        assert self.token_field not in kwargs, 'Token field already filled.'
        for _x in xrange(100):
            token = get_random_string(self.token_length)
            conflict_filter = {self.token_field: token}
            conflict = self.get_query_set().filter(**conflict_filter)
            if not conflict.exists():
                kwargs[self.token_field] = token
                return super(UniqueTokenManager, self).create(**kwargs)
        raise RuntimeError('Could not create unique token.')


class AbstractToken(models.Model):

    TOKEN_LENGTH = 32

    token = models.CharField(max_length=TOKEN_LENGTH, unique=True)
    valid_until = models.DateTimeField(
        default=lambda: now() + timedelta(settings.ACCOUNT_ACTIVATION_DAYS))

    objects = UniqueTokenManager(token_field='token',
                                 token_length=TOKEN_LENGTH)

    class Meta:
        abstract = True


class EmailConfirmationRequest(AbstractToken):

    email = models.EmailField()

    def get_authenticated_user(self):
        user, _created = User.objects.get_or_create(email=self.email)
        EmailConfirmationRequest.objects.filter(email=self.email).delete()
        return authenticate(user=user)

    def get_confirmation_url(self):
        return reverse('registration:confirm_email',
                       kwargs={'token': self.token})


class EmailChangeRequest(AbstractToken):

    user = models.ForeignKey(User, related_name="email_change_requests")
    email = models.EmailField()  # email address that user is switching to

    def get_confirmation_url(self):
        return reverse('registration:change_email',
                       kwargs={'token': self.token})
