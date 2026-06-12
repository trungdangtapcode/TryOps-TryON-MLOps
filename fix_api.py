import re

with open("src/tryops/api.py", "r") as f:
    api_code = f.read()

bad_str = """    @app.get("/v1/health")
    
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

    def health_v1() -> dict[str, str]:
        return health()"""

good_str = """    
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

    @app.get("/v1/health")
    def health_v1() -> dict[str, str]:
        return health()"""

api_code = api_code.replace(bad_str, good_str)

with open("src/tryops/api.py", "w") as f:
    f.write(api_code)

