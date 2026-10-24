import os
from getpass import getpass

import requests

api_key = os.getenv("WALLEX_API_KEY")

if not api_key:
    api_key = getpass("Wallex API Key: ")

url = "https://api.wallex.ir/v1/prop/user/packages/history"

response = requests.get(
    url,
    headers={"x-api-key": api_key},
    timeout=20,
)

response.raise_for_status()
data = response.json()

if not data.get("success"):
    raise RuntimeError("Wallex API did not return success")

for package in data.get("result", []):
    print(
        {
            "package_title": package.get("package_title"),
            "client_id": package.get("client_id"),
            "status": package.get("status"),
            "created_at": package.get("created_at"),
            "expire_at": package.get("expire_at"),
        }
    )
