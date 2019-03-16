import traceback
import html
import decimal
import typing
import json
from starlette.applications import Starlette
from starlette.responses import Response, HTMLResponse, PlainTextResponse
from starlette.requests import Request
from starlette.exceptions import ExceptionMiddleware
from starlette.background import BackgroundTask
from .graphql import CGraphQLApp as GraphQLApp
from starlette.requests import HTTPConnection
from starlette.middleware.wsgi import WSGIMiddleware
from starlette.routing import Router, Mount
from asgiref.sync import sync_to_async, async_to_sync, SyncToAsync
from starlette.middleware.authentication import AuthenticationMiddleware
from starlette.authentication import requires
from starlette.middleware.cors import CORSMiddleware
from sentry_asgi import SentryMiddleware
import sentry_sdk
from .backends import GraphqlBackend


class DecimalEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, decimal.Decimal):
            return str(obj)
        return json.JSONEncoder.default(self, obj)


class JSONResponse(Response):
    media_type = "application/json"

    def render(self, content: typing.Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=None,
            separators=(",", ":"),
            cls=DecimalEncoder,
        ).encode("utf-8")


def default_on_error(conn: HTTPConnection, exc: Exception) -> Response:
    return JSONResponse({"detail": str(exc)}, status_code=403)


def create_asgi_app(**kwargs):
    sentry_settings = kwargs.pop("sentry_settings", None)
    auth_validation = kwargs.pop("auth_validation", None)
    protect = kwargs.pop("protect", None)
    schema = kwargs.pop("schema", None)
    print(kwargs)
    app = Starlette(**kwargs)
    # app.add_middleware(
    #     CORSMiddleware, allow_methods=["*"], allow_origins=["*"], allow_headers=["*"]
    # )
    if auth_validation:
        app.add_middleware(
            AuthenticationMiddleware,
            backend=GraphqlBackend(auth_validation),
            on_error=default_on_error,
        )

    # app.add_exception_handler(Exception, get_debug_response)
    if sentry_settings:
        sentry_sdk.init(dsn=sentry_settings)
        app.add_middleware(SentryMiddleware)
    if schema:
        # if protect:
        #     app.add_route(
        #         "/graphql",
        #         requires('authenticated')(GraphQLApp(schema=schema)))
        # else:
        app.add_route("/graphql", GraphQLApp(schema=schema))
    return app


def create_app(application, wsgi=False):
    if wsgi:
        return WSGIMiddleware(application)
    return application

def initialize_router(asgi, wsgi=None, asgi_path="/",**kwargs):
    apps = [{"path":asgi_path, 'app':asgi}]
    if wsgi:
        wsgi_instance = {**wsgi, 'wsgi':True}
        apps.append(wsgi_instance)

    return _initialize_router(apps, **kwargs)
    
def _initialize_router(apps, debug=True, sentry_settings=None):
    app = Router(
        [Mount(x["path"], app=create_app(x["app"], x.get("wsgi"))) for x in apps]
    )
    if debug:
        app = ExceptionMiddleware(app, debug=True)
        app.add_exception_handler(Exception, get_debug_response)
    app = CORSMiddleware(
        app, allow_methods=["*"], allow_origins=["*"], allow_headers=["*"]
    )
    return app


class DatabaseSyncToAsync(SyncToAsync):
    """
    SyncToAsync version that cleans up old database connections when it exits.
    """

    def thread_handler(self, loop, *args, **kwargs):
        from django.db import connections, close_old_connections

        try:
            return super().thread_handler(loop, *args, **kwargs)
        finally:
            close_old_connections()
            connections.close_all()


# The class is TitleCased, but we want to encourage use as a callable/decorator
database_sync_to_async = DatabaseSyncToAsync


def get_debug_response(request: Request, exc: Exception) -> Response:
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        exc_html = "".join(traceback.format_tb(exc.__traceback__))
        exc_html = html.escape(exc_html)
        content = (
            f"<html><body><h1>500 Server Error</h1><pre>{exc_html}</pre></body></html>"
        )
        return HTMLResponse(content, status_code=500)
    content = "".join(traceback.format_tb(exc.__traceback__))
    return PlainTextResponse(content, status_code=500)
