from django.utils.deprecation import MiddlewareMixin


class XFrameOptionsMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # Don't set it if it's already in the response
        if response.get("X-Frame-Options") is not None:
            return response

        # Don't set it if they used @xframe_options_exempt
        if getattr(response, "xframe_options_exempt", False):
            return response

        # Don't set for zoom app
        # We don't use xframe_options_exempt here since that doesn't catch error pages
        if request.path.startswith("/zoom"):
            return response

        response["X-Frame-Options"] = "DENY"
        return response
