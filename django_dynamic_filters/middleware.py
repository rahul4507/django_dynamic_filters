"""
Middleware to store the current request in thread local storage
"""

from threading import local

_thread_locals = local()


class RequestMiddleware:
    """
    Middleware that stores the request object in thread local storage
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Store request in thread local storage
        _thread_locals.request = request

        # Process the request
        response = self.get_response(request)

        # Clean up
        if hasattr(_thread_locals, 'request'):
            del _thread_locals.request

        return response


def get_current_request():
    """
    Get the current request from thread local storage
    """
    return getattr(_thread_locals, 'request', None)