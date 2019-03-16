import json
import os
from decimal import Decimal

from django import forms
from django.conf import settings
from django.shortcuts import reverse

from asgiref.sync import sync_to_async
from paystack import signals as p_signals
from paystack.utils import PaystackAPI
from paystack.utils import get_js_script as p_get_js_scripts



class PaymentForm(forms.Form):
    create = forms.BooleanField(required=False)
    plan = forms.CharField()
    duration = forms.CharField()
    coupon = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        data = args[0]
        self.pricing = kwargs.pop("pricing_details")
        super().__init__(*args, **kwargs)

    def clean_plan(self):
        plans = self.pricing["plans"].keys()
        plan = self.cleaned_data.get("plan")
        if plan not in plans:
            raise forms.ValidationError("Plan passed not supported")
        return plan

    def get_payment_plans(self, plan):
        plans = self.pricing["plans"][plan]
        discount = self.pricing["discount"]
        annual_plans = {}
        if "semi_annual" in plans.keys():
            for key, value in plans["semi_annual"].items():
                annual_plans[key] = value * 2 * (1 - (discount / 100))
            plans["annual"] = annual_plans
            plans["annually"] = annual_plans
        if "monthly" in plans.keys():
            for key, value in plans["monthly"].items():
                annual_plans[key] = value * 12 * (1 - (discount / 100))
            plans["annual"] = annual_plans
            plans["annually"] = annual_plans
        return plans

    def get_plan_codes(self, plan):
        plan_codes = self.pricing["plan_code"][plan]
        duration = self.cleaned_data.get("duration")
        return plan_codes[duration]

    def clean_duration(self):
        payment_plans = self.get_payment_plans(self.cleaned_data.get("plan"))
        duration = self.cleaned_data.get("duration")
        durations = payment_plans.keys()
        if duration not in durations:
            raise forms.ValidationError("Duration passed not supported")
        return duration



    def purchase_template(self, user, user_details=None):
        result = self.template.create_user_payment(user)
        result.amount = self.determine_new_price(country=user_details.get("country"))
        result.extra_data = {**user_details, "level": self.level_value}
        result.made_payment = True
        result.save()
        return result

    def paystack_details(self):
        pass

    def determine_new_price(self, country):
        return self.template.determine_new_price(self.level_value, country)

    def determine_plan_amount(self, instance, country, currency=None):
        plans = self.get_payment_plans(instance.plan)
        considered_plans = plans[instance.duration]
        c_currency = currency or instance.get_currency_for_country(country)["currency"]
        return considered_plans[c_currency.lower()]

    def create_payment_instance(self, currency="ngn"):
        data = user_details or {}
        if currency:
            data["currency"] = currency
        result = PlanPayment.pending_payment(user)
        if not result:
            result = PlanPayment.objects.create(user=user)
        if not result.made_payment:
            result.kind = self.user_kind
            result.plan = self.cleaned_data.get("plan")
            result.duration = self.cleaned_data.get("duration")
            coupon = self.cleaned_data.get("coupon")
            result.amount = self.determine_plan_amount(
                result, data.get("country"), currency=currency
            )
            result.coupon = Coupon.get_discount(coupon)
            extra_data = {
                **data,
                "default_rate": result.amount,
                "user_kind": self.user_kind,
            }
            country = data.get("country", "United States")
            country_currency = utils.get_currency(country)
            if self.user_kind == "agent":
                if not result.coupon:
                    extra_data["plan_code"] = self.get_plan_codes(result.plan)[
                        currency or country_currency
                    ]
            result.extra_data = extra_data
            result.save()
            return result
        

    def save_plan_form(self, user, user_details=None, currency=None, redirect_url=None):
        # check if any payment currently exists
        result = self.create_payment_instance(currency=currency)
        if result:
            payment_detail = result.details
            base_url = redirect_url or settings.CURRENT_DOMAIN
            payment_detail = self.add_paystack_details_to_response(payment_detail,base_url=base_url)
        status = True
        return result.details, status

    def save(self, user, user_details=None, currency=None, redirect_url=None):
        return self.save_plan_form(
            user,
            user_details=user_details,
            currency=currency,
            redirect_url=redirect_url,
        )
    
    def add_paystack_details_to_response(self, payment_detail, base_url=""):
        path = f"paystack/verify-payment/${payment_detail['order']}"
        amount = int(Decimal(payment_detail["amount"]) * 100)
        link = f"{base_url}/{path}" + f"?amount={amount}"
        payment_detail["user_details"].update(
            key=settings.PAYSTACK_PUBLIC_KEY,
            redirect_url=link,
            kind="paystack",
            js_script=p_get_js_scripts(),
        )
        return payment_detail


def create_payment(user_id, body, pricing_details, user_details):
    currency = body.pop("currency", None)
    kind = body.pop("kind", "client")
    redirect_url = body.pop("redirect_url", None)
    instance = PaymentForm(body, pricing_details=pricing_details, kind=kind)
    if instance.is_valid():
        value, coupon_used = instance.save(
            user_id,
            user_details=user_details,
            currency=currency,
            redirect_url=redirect_url,
        )
        result = {"data": value}
        if not coupon_used:
            result["coupon_used"] = False
        # import pdb; pdb.set_trace()
        return True, result
    return False, {"errors": instance.errors}


def fetch_subscription_from_paystack(record):
    paystack_info = record.extra_data.get("paystack_details")
    if paystack_info.get("plan") and paystack_info.get("customer"):
        paystack_instance = PaystackAPI()
        extra_data = record.extra_data
        plan_details = extra_data.get("paystack_details", {}).pop("plan_details", None)
        if not plan_details:
            _, _, plan_details = paystack_instance.subscription_api.get_plan(
                paystack_info["plan"]
            )
        result = paystack_instance.subscription_api.get_all_subscriptions(
            {"plan": plan_details["id"], "customer": paystack_info["customer"]["id"]}
        )
        result = result[2]
        extra_data["paystack_details"] = {
            **extra_data["paystack_details"],
            "plan_id": plan_details["id"],
            "subscription_code": result[0]["subscription_code"],
            "email_token": result[0]["email_token"],
        }
        record.extra_data = extra_data
        record.save()
        return record

def process_paystack_payment(request, order, kind="paystack", data=None):
    amount = request.get("amount")
    txrf = request.get("trxref")
    # on_payment_verified(PaystackAPI, txrf, amount, order)
    p_signals.payment_verified.send(
        sender=PaystackAPI,
        ref=txrf,
        amount=int(amount),
        order=order,
        request=request,
        data=data,
    )
    return plan

@sync_to_async
def paystack_verification(request, amount_only=True, **kwargs):
    amount = request.get("amount")
    txrf = request.get("trxref")
    paystack_instance = PaystackAPI()
    result = paystack_instance.verify_payment(
        txrf, amount=int(amount), amount_only=amount_only
    )
    if not amount_only:
        result = (
            result[0],
            result[1],
            paystack_instance.transaction_api.get_customer_and_auth_details(result[2]),
        )
    return result
