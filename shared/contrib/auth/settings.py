
import environ
import datetime
env = environ.Env(DEBUG=(bool, False))  # set default values and casting

JWT_ALLOW_REFRESH = True
LAST_ACTIVITY_INTERVAL_SECS = 3600

def configure_db(env_name='DATABASE_URL', default=None):
    DATABASES = {
        "default":
        env.db( "DATABASE_URL", default=default)
         }
    DATABASES["default"]["ATOMIC_REQUESTS"] = True
    return DATABASES


def jwt_user_secret_key(SECRET_KEY):
    JWT_AUTH = {
        "JWT_RESPONSE_PAYLOAD_HANDLER":
        "shared.contrib.auth.utils.jwt_response_payload_handler",
        "JWT_AUTH_HEADER_PREFIX": "Token",
        "JWT_EXPIRATION_DELTA": datetime.timedelta(days=2),
        "JWT_GET_USER_SECRET_KEY": lambda user: user.password_hash + SECRET_KEY,
    }
    return JWT_AUTH

# Password validation
# https://docs.djangoproject.com/en/2.1/ref/settings/#auth-password-validators


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]
MIDDLEWARE = [
    # 'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    # 'django.middleware.common.CommonMiddleware',
    # 'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    # 'django.contrib.messages.middleware.MessageMiddleware',
    # 'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
