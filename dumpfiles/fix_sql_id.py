import re

with open("src/tryops/api.py", "r") as f:
    api_code = f.read()

bad_str = """        db.insert_request(conn, {
            "id": request_id,"""

good_str = """        import uuid
        db.insert_request(conn, {
            "id": str(uuid.uuid4()),"""

api_code = api_code.replace(bad_str, good_str)

with open("src/tryops/api.py", "w") as f:
    f.write(api_code)

