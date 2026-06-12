import re

with open("src/tryops/api.py", "r") as f:
    api_code = f.read()

bad_str = """    @app.get("/v1/health")
    
    from fastapi import Request"""

good_str = """    
    from fastapi import Request"""

api_code = api_code.replace(bad_str, good_str)

with open("src/tryops/api.py", "w") as f:
    f.write(api_code)

