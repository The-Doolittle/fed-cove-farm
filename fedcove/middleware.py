from django.http import HttpResponse


class HealthCheckMiddleware:
    """Answer /healthz before host validation, so the container healthcheck
    (which calls localhost) works whatever ALLOWED_HOSTS is set to."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/healthz":
            return HttpResponse("ok")
        return self.get_response(request)
