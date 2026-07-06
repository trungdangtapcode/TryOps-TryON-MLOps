import re

with open("src/tryops/api.py", "r") as f:
    api_code = f.read()

# Add /api/{endpoint} annotations
endpoints = [
    ("/llm/generate", "/api/llm/generate"),
    ("/vton/infer", "/api/vton/infer"),
    ("/vton/jobs", "/api/vton/jobs"),
    ("/vton/jobs/{job_id}", "/api/vton/jobs/{job_id}"),
    ("/promotion/evaluate", "/api/promotion/evaluate"),
    ("/lineage", "/api/lineage"),
    ("/health", "/api/health"),
    ("/ready", "/api/ready"),
    ("/metrics", "/api/metrics")
]

for base, api_prefix in endpoints:
    if api_prefix not in api_code:
        # insert @app.post(api_prefix) before @app.post(base) (or get)
        methods = ["get", "post"]
        for m in methods:
            if f'@app.{m}("{base}")' in api_code:
                api_code = api_code.replace(
                    f'@app.{m}("{base}")',
                    f'@app.{m}("{api_prefix}")\n    @app.{m}("{base}")'
                )

# Also need to persist to DB in _record
record_func_old = """def _record(
    endpoint: str,
    request_id: str,
    workload: str,
    model_alias: str,
    started_at: float,
    payload: dict[str, Any],
    response: dict[str, Any],
) -> None:
    event = record_api_observation(
        endpoint=endpoint,
        request_id=request_id,
        workload=workload,
        model_alias=model_alias,
        status=str(response.get("status", "unknown")),
        started_at=started_at,
        payload=payload,
        response=response,
    )
    response["trace"] = event["trace"]"""

record_func_new = """def _record(
    endpoint: str,
    request_id: str,
    workload: str,
    model_alias: str,
    started_at: float,
    payload: dict[str, Any],
    response: dict[str, Any],
) -> None:
    event = record_api_observation(
        endpoint=endpoint,
        request_id=request_id,
        workload=workload,
        model_alias=model_alias,
        status=str(response.get("status", "unknown")),
        started_at=started_at,
        payload=payload,
        response=response,
    )
    response["trace"] = event["trace"]

    from tryops import db
    import sqlite3
    try:
        conn = db.connect()
        latency_ms = (perf_counter() - started_at) * 1000
        
        input_summary = None
        output_summary = None
        
        if workload == "llm":
            input_summary = payload.get("prompt", "")[:500] if payload.get("prompt") else None
            output_summary = str(response.get("output", {}).get("text", ""))[:500] if response.get("output") else None
        elif workload == "vton":
            input_summary = f"Person: {payload.get('person_image_path', '')}, Garment: {payload.get('garment_image_path', '')}"
            out_img = response.get("report", {}).get("output_image_path")
            if out_img:
                output_summary = out_img
            else:
                out_img = payload.get("output_image_path", "")
                output_summary = out_img
                
        metrics = response.get("report", {}).get("metrics", {}) if workload == "vton" else response.get("metrics", {})
        vram_gb = metrics.get("peak_vram_gb")
        energy_wh = metrics.get("energy_wh")
        cost_usd = metrics.get("estimated_cost_usd")
        
        status = str(response.get("status", "failed" if "error" in response else "completed"))
        if "error" in response:
            status = "failed"
            
        db.insert_request(conn, {
            "id": request_id,
            "kind": workload,
            "model_alias": model_alias,
            "adapter": response.get("routing", {}).get("primary_adapter", ""),
            "input_summary": input_summary,
            "output_summary": output_summary,
            "latency_ms": latency_ms,
            "vram_gb": vram_gb,
            "energy_wh": energy_wh,
            "cost_usd": cost_usd,
            "quality": None,
            "status": status,
            "user_hash": payload.get("user_id"),
            "request_id": request_id,
            "trace_id": event.get("trace", {}).get("trace_id")
        })
    except Exception as e:
        print(f"Failed to persist request to db: {e}")
    finally:
        if 'conn' in locals():
            conn.close()"""

api_code = api_code.replace(record_func_old, record_func_new)

with open("src/tryops/api.py", "w") as f:
    f.write(api_code)

