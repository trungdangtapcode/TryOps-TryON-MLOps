from __future__ import annotations

from pathlib import Path
from typing import Any

from tryops import db
from tryops.runtime_artifacts import account_object_key, artifact_uri, storage_from_env
from tryops.simple_image import read_png_rgb


def main() -> None:
    storage = storage_from_env()
    if storage is None:
        raise SystemExit("MinIO runtime artifact storage is not configured")

    conn = db.connect()
    migrated = 0
    skipped = 0
    try:
        rows = db._fetchall(  # type: ignore[attr-defined]
            conn,
            """SELECT id, account_id, request_id, output_summary
               FROM requests
               WHERE kind='vton'
                 AND status='completed'
                 AND output_summary IS NOT NULL
                 AND output_summary NOT LIKE 'artifact:%'""",
        )
        for row in rows:
            record = dict(row)
            legacy_path = str(record.get("output_summary") or "")
            path = Path(legacy_path)
            if not legacy_path.startswith("artifacts/runtime/vton/") or not path.is_file():
                skipped += 1
                continue
            existing = db.find_artifact_by_legacy_path(conn, legacy_path)
            if existing:
                ref = artifact_uri(str(existing["id"]))
                db.update_request_output_summary_by_legacy_path(
                    conn,
                    legacy_path=legacy_path,
                    output_summary=ref,
                )
                db.update_job_result_path_by_legacy_path(conn, legacy_path=legacy_path, result_path=ref)
                migrated += 1
                continue

            account_id = str(record.get("account_id") or db.DEMO_ACCOUNT_ID)
            request_id = str(record.get("request_id") or record.get("id") or path.stem)
            image = read_png_rgb(path)
            object_key = account_object_key(account_id, "requests", request_id, "output.png")
            metadata = storage.put_file(object_key=object_key, path=path, content_type="image/png")
            artifact_id = db.insert_artifact_object(
                conn,
                {
                    **metadata,
                    "account_id": account_id,
                    "request_id": request_id,
                    "role": "vton_output",
                    "legacy_path": legacy_path,
                    "width": image.width,
                    "height": image.height,
                    "status": "active",
                },
            )
            ref = artifact_uri(artifact_id)
            db.update_request_output_summary_by_legacy_path(
                conn,
                legacy_path=legacy_path,
                output_summary=ref,
            )
            db.update_job_result_path_by_legacy_path(conn, legacy_path=legacy_path, result_path=ref)
            _upload_report_if_present(
                conn,
                storage=storage,
                account_id=account_id,
                request_id=request_id,
                legacy_output_path=path,
            )
            migrated += 1
    finally:
        conn.close()
    print(f"Runtime artifact migration complete: migrated={migrated} skipped={skipped}")


def _upload_report_if_present(
    conn: Any,
    *,
    storage: Any,
    account_id: str,
    request_id: str,
    legacy_output_path: Path,
) -> None:
    report_path = legacy_output_path.with_suffix(legacy_output_path.suffix + ".json")
    if not report_path.is_file():
        return
    object_key = account_object_key(account_id, "requests", request_id, "report.json")
    metadata = storage.put_file(object_key=object_key, path=report_path, content_type="application/json")
    db.insert_artifact_object(
        conn,
        {
            **metadata,
            "account_id": account_id,
            "request_id": request_id,
            "role": "vton_report",
            "legacy_path": str(report_path),
            "status": "active",
        },
    )


if __name__ == "__main__":
    main()
