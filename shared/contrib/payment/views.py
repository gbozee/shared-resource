from starlette.authentication import requires
from starlette.background import BackgroundTask
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse

from shared.starlette import create_asgi_app

from . import forms


def create_payment_app_instance(services=forms, **kwargs):
    app = create_asgi_app(**kwargs)

    @app.route("/create-payment", methods=["POST"])
    @requires(['authenticated'])
    async def create_payment(request):
        body = await request.json()
        is_valid, result = services.create_payment(body, )
        if is_valid:
            return JSONResponse(result, status_code=200)
        return JSONResponse(result, status_code=400)

    @app.route("/paystack/verify-payment/{order}/")
    async def paystack_verify_payment(request):
        order = request.path_params["order"]
        url = determine_base_route(request._scope)
        response = await services.paystack_verification(request.query_params)
        if response[0]:
            paystack_response = None
            if len(response) == 3:
                paystack_response = response[2]
            task = BackgroundTask(services.process_paystack_payment, request.query_params, order, "paystack", data=paystack_response)
            return JSONResponse({"success": True}, background=task)
        return JSONResponse({"success": False}, status_code=400)

    return app

def determine_base_route(scope):
    scheme = scope.get("scheme", "http")
    server = scope.get("server", None)
    path = scope.get("root_path", "") + scope["path"]
    query_string = scope["query_string"]

    host_header = None
    for key, value in scope["headers"]:
        if key == b"host":
            host_header = value.decode("latin-1")
            break

    if host_header is not None:
        url = "%s://%s" % (scheme, host_header)
    else:
        host, port = server
        default_port = {"http": 80, "https": 443, "ws": 80, "wss": 443}[scheme]
        if port == default_port:
            url = "%s://%s" % (scheme, host)
        else:
            url = "%s://%s:%s" % (scheme, host, port)
    return url
