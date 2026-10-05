import os
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

origin = urlsplit(os.environ["PUBLIC_BASE_URL"])
request = Request(
    "http://127.0.0.1:8000/internal/ready/",
    headers={"Host": origin.netloc, "X-Forwarded-Proto": "https"},
)
with urlopen(request, timeout=5) as response:
    if response.status != 200:
        raise SystemExit(1)
