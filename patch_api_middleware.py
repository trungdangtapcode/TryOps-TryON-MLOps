import re

with open("src/tryops/api.py", "r") as f:
    api_code = f.read()

middleware_str = """
    from fastapi import Request
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > 10 * 1024 * 1024:
                return JSONResponse(
                    status_code=413,
                    content=structured_error(
                        request_id="unknown",
                        code="payload_too_large",
                        message="request payload exceeded 10MB limit",
                        workload="api"
                    )
                )
            return await call_next(request)

    app.add_middleware(PayloadSizeLimitMiddleware)
"""

parts = api_code.split('def health_v1() -> dict[str, str]:')
api_code = parts[0] + middleware_str + "\n    def health_v1() -> dict[str, str]:" + parts[1]

with open("src/tryops/api.py", "w") as f:
    f.write(api_code)

