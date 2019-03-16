import os
from decimal import Decimal
from typing import NamedTuple

# from django.contrib.postgres.fields import JSONField
from django.db import models
from django.utils.crypto import get_random_string

from .fields import TimeStampedModel


def generate_random():
    return get_random_string(12).upper()


class PaymentMixin(TimeStampedModel):
    PAYSTACK = 1
    RAVEPAY = 2
    CHOICES = ((PAYSTACK, "Paystack"), (RAVEPAY, "Ravepay"))
    user = models.IntegerField(null=True)
    amount = models.DecimalField(default=0, max_digits=10, decimal_places=2)
    order = models.CharField(
        max_length=20, default=generate_random, primary_key=True)
    payment_method = models.IntegerField(choices=CHOICES, default=PAYSTACK)
    made_payment = models.BooleanField(default=False)
    # extra_data = JSONField(null=True)

    class Meta:
        abstract = True


    @classmethod
    def pending_payment(cls, user_id,  made_payment=False):
        return cls.objects.filter(
            user=user_id, made_payment=made_payment).first()

    @classmethod
    def generate_payment_details(cls, user_id):
        instance = cls.pending_payment(user_id)
        if not instance:
            return None
        return instance.details


    def update_user_details(self, **kwargs):
        user_details = self.extra_data
        user_details.update(**kwargs)
        self.extra_data = user_details
        self.save()


    def miscellaneous_actions(self):
        pass


    def on_payment_verification(self, amount, paystack_data, **kwargs):
        self.made_payment = True
        self.amount = Decimal(amount)
        extra_data = self.extra_data
        extra_data['paystack_details'] = paystack_data
        if kwargs.get('kind'):
            extra_data['kind'] = kwargs['kind']
        self.extra_data = extra_data
        self.save()
        return self

class PlanPayment(PaymentMixin):
    plan = models.CharField(max_length=100, null=True, blank=True)

    class Meta:
        abstract = True

    def get_currency(self) -> Dict[str, str]:
        return {}

    @property
    def details(self):
        user_details = self.extra_data or {}
        return {
            "amount": self.price,
            "order": self.order,
            "user_details": user_details,
            "paid": self.made_payment,
            **self.get_currency(),
        }
