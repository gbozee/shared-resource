from starlette.responses import JSONResponse
from shared.starlette import create_asgi_app

def create_auth_app_instance(**kwargs):
    app = create_asgi_app(**kwargs)
    return app
