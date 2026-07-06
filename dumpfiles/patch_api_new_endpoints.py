import re

with open("src/tryops/api.py", "r") as f:
    api_code = f.read()

new_endpoints_str = """
    @app.get("/api/history")
    def get_history(kind: str = None, limit: int = 50) -> dict[str, Any]:
        from tryops import db
        conn = db.connect()
        try:
            reqs = db.list_requests(conn, kind=kind, limit=limit)
            return {"status": "ok", "data": reqs}
        finally:
            conn.close()

    @app.get("/api/request/{id}")
    def get_single_request(id: str) -> dict[str, Any]:
        from tryops import db
        conn = db.connect()
        try:
            req = db.get_request(conn, id)
            if not req:
                return structured_error(
                    request_id="unknown",
                    code="request_not_found",
                    message="request not found",
                    workload="api"
                )
            return {"status": "ok", "data": req}
        finally:
            conn.close()

    @app.post("/api/feedback")
    def post_feedback(payload: dict[str, Any]) -> dict[str, Any]:
        from tryops import db
        conn = db.connect()
        try:
            fid = db.insert_feedback(conn, payload)
            # also insert audit entry
            db.insert_audit(
                conn, 
                actor=payload.get("user_id", "anonymous"), 
                action="submit_feedback", 
                target=payload.get("request_id", "unknown"),
                detail=fid
            )
            return {"status": "ok", "id": fid}
        finally:
            conn.close()

    @app.get("/api/dashboard")
    def get_dashboard() -> dict[str, Any]:
        from tryops import db
        conn = db.connect()
        try:
            return db.dashboard_summary(conn)
        finally:
            conn.close()

    @app.get("/api/models")
    def get_models() -> dict[str, Any]:
        from tryops import db
        conn = db.connect()
        try:
            models = db.list_models(conn)
            return {"status": "ok", "data": models}
        finally:
            conn.close()

    @app.post("/api/models/{id}/promote")
    def promote_model(id: str, payload: dict[str, Any]) -> dict[str, Any]:
        from tryops import db
        # this is naive, actually we should use evaluate_promotion then update db
        conn = db.connect()
        try:
            record = payload.copy()
            record["id"] = id
            db.upsert_model(conn, record)
            db.insert_audit(
                conn,
                actor=payload.get("user_id", "anonymous"),
                action="promote_model",
                target=id,
                detail=record.get("stage", "unknown")
            )
            return {"status": "ok"}
        finally:
            conn.close()
"""

# inject right before def _record
parts = api_code.split("def _record(")
api_code = parts[0] + new_endpoints_str + "\n\ndef _record(" + parts[1]

with open("src/tryops/api.py", "w") as f:
    f.write(api_code)

