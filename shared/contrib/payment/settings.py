import os
import environ

env = environ.Env(DEBUG=(bool, False))  # set default values and casting
# Build paths inside the project like this: os.path.join(BASE_DIR, ...)

# Application definition

PAYMENT_INSTALLED_APPS = [
    "paystack",
]


def configure_db(env_name='DATABASE_URL', default=None):
    DATABASES = {
        "default":
        env.db( "DATABASE_URL", default=default)
         }
    DATABASES["default"]["ATOMIC_REQUESTS"] = True
    return DATABASES


# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/2.0/howto/static-files/

PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
PAYSTACK_PUBLIC_KEY = os.getenv("PAYSTACK_PUBLIC_KEY", "")
PAYSTACK_SUCCESS_URL = "redirect_func"
SUCCESS_URL = os.getenv("PAYSTACK_SUCCESS_URL", "http://www.google.com")
PAYSTACK_FAILED_URL = os.getenv("PAYSTACK_FAILED_URL", "http://www.facebook.com")
