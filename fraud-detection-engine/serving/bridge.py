"""Small JSON-over-HTTP adapter; map starter-kit messages to the API schema."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def score_transaction(api_url, payload, timeout_seconds=2.0):
    """Send one prepared feature-vector payload to the scoring API."""
    request = Request(
        api_url.rstrip("/") + "/score",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Scoring API returned HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach scoring API: {error.reason}") from error

