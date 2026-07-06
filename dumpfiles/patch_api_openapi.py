import re

with open("src/tryops/api.py", "r") as f:
    api_code = f.read()

old_fastapi = """    app = FastAPI(
        title="TryOps API",
        version="0.1.0",
        description="Enterprise MLOps control plane for VTON and optimized LLM serving.",
    )"""

new_fastapi = """    app = FastAPI(
        title="TryOps Console API",
        version="0.1.0",
        description="Enterprise MLOps control plane for VTON and optimized LLM serving.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )"""

api_code = api_code.replace(old_fastapi, new_fastapi)

with open("src/tryops/api.py", "w") as f:
    f.write(api_code)

