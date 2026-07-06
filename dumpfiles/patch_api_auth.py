import re

with open("src/tryops/api.py", "r") as f:
    api_code = f.read()

# We'll update the new endpoints to require 'api_key: str = None'
replacements = {
    'def get_history(kind: str = None, limit: int = 50) -> dict[str, Any]:':
        'def get_history(api_key: str = None, kind: str = None, limit: int = 50) -> dict[str, Any]:\n        auth = authenticate_api_key(api_key, required_scope="admin:read")\n        if not auth["allowed"]:\n            return _admin_auth_error("unknown", auth, "history")',
    
    'def get_dashboard() -> dict[str, Any]:':
        'def get_dashboard(api_key: str = None) -> dict[str, Any]:\n        auth = authenticate_api_key(api_key, required_scope="admin:read")\n        if not auth["allowed"]:\n            return _admin_auth_error("unknown", auth, "dashboard")',

    'def get_models() -> dict[str, Any]:':
        'def get_models(api_key: str = None) -> dict[str, Any]:\n        auth = authenticate_api_key(api_key, required_scope="admin:read")\n        if not auth["allowed"]:\n            return _admin_auth_error("unknown", auth, "models")',

    'def get_single_request(id: str) -> dict[str, Any]:':
        'def get_single_request(id: str, api_key: str = None) -> dict[str, Any]:\n        auth = authenticate_api_key(api_key, required_scope="admin:read")\n        if not auth["allowed"]:\n            return _admin_auth_error("unknown", auth, "request")',
    
    'def promote_model(id: str, payload: dict[str, Any]) -> dict[str, Any]:':
        'def promote_model(id: str, payload: dict[str, Any]) -> dict[str, Any]:\n        auth = authorize_admin_payload(payload, required_scope="promotion:evaluate")\n        if not auth["allowed"]:\n            return _admin_auth_error("unknown", auth, "models")',
}

for k, v in replacements.items():
    api_code = api_code.replace(k, v)

# wait, we need to import authenticate_api_key from tryops.auth
if 'authenticate_api_key' not in api_code:
    api_code = api_code.replace(
        "from tryops.auth import authorize_admin_payload",
        "from tryops.auth import authorize_admin_payload, authenticate_api_key"
    )

with open("src/tryops/api.py", "w") as f:
    f.write(api_code)

import re

with open("src/tryops/api.py", "r") as f:
    api_code = f.read()

lineage_code = """
    @app.get("/api/lineage/{id}")
    def get_lineage(id: str, api_key: str = None) -> dict[str, Any]:
        auth = authenticate_api_key(api_key, required_scope="lineage:read")
        if not auth["allowed"]:
            return _admin_auth_error("unknown", auth, "lineage")
        return {"status": "ok", "data": {"id": id, "hashes": {}}}
"""

if "/api/lineage/{id}" not in api_code:
    parts = api_code.split('def health_v1() -> dict[str, str]:')
    api_code = parts[0] + lineage_code + "\n    def health_v1() -> dict[str, str]:" + parts[1]

with open("src/tryops/api.py", "w") as f:
    f.write(api_code)
