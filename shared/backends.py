from starlette.authentication import (
    AuthenticationBackend, AuthenticationError, SimpleUser, AuthCredentials)


class ValidationError(Exception):
    pass


class GraphqlBackend(AuthenticationBackend):
    def __init__(self, validateToken):
        self.validateToken = validateToken

    async def authenticate(self, request):
        if "Authorization" not in request.headers:
            return
        auth = request.headers["Authorization"]
        token = auth.replace("Bearer", "").replace("Token", "").strip()
        try:
            result = self.validateToken(token)
        except (ValueError, UnicodeDecodeError, ValidationError) as exc:
            raise AuthenticationError('Invalid token credentials')

        # TODO: You'd want to verify the username and password here,
        #       possibly by installing `DatabaseMiddleware`
        #       and retrieving user information from `request.database`.
        return AuthCredentials(["authenticated"]), SimpleUser(result)
