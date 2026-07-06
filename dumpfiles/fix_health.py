import re

with open("src/tryops/api.py", "r") as f:
    api_code = f.read()

# I am placing health_v1 right after health
parts = api_code.split('def health() -> dict[str, str]:\n        return {"status": "ok"}')
api_code = parts[0] + 'def health() -> dict[str, str]:\n        return {"status": "ok"}\n\n    @app.get("/v1/health")\n    def health_v1() -> dict[str, str]:\n        return health()' + parts[1]

with open("src/tryops/api.py", "w") as f:
    f.write(api_code)

