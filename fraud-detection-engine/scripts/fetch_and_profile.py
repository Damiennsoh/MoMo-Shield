"""Simulate, download, validate, and profile the live sandbox dataset."""

import argparse
import json
import os
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from momo_fraud.io import load_tables, write_schema_report


BASE_URL = "https://hackathon.innofemme.org/api/w"
DEFAULT_FILES = (
    "transactions.csv",
    "blind.csv",
    "people.csv",
    "sims.csv",
    "sim_events.csv",
    "wallets.csv",
    "bank_accounts.csv",
    "calls.csv",
    "texts.csv",
    "complaints.csv",
)


def load_dotenv(path: Path) -> dict:
    values = {}
    if not path.is_file():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def credential(team_arg=None, team_key_arg=None):
    dotenv = load_dotenv(PROJECT_ROOT / ".env")
    team = team_arg or os.getenv("TEAM") or dotenv.get("TEAM")
    team_key = team_key_arg or os.getenv("TEAM_KEY") or dotenv.get("TEAM_KEY")
    if not team or team.startswith("your_team"):
        raise ValueError("TEAM is missing. Set it in .env or pass --team.")
    if not team_key or team_key.startswith("your_team"):
        raise ValueError("TEAM_KEY is missing. Set it in .env or pass --team-key.")
    return team, team_key


def api_request(url, team_key, method="GET", body=None, timeout=120):
    data = None if body is None else json.dumps(body).encode("utf-8")
    headers = {"x-team-key": team_key, "accept": "application/json"}
    if data is not None:
        headers["content-type"] = "application/json"
    request = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            content = response.read()
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type or content.startswith(b"{"):
                return json.loads(content.decode("utf-8"))
            return content
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Sandbox API returned HTTP {error.code}: {detail}"
        ) from error
    except URLError as error:
        raise RuntimeError(f"Could not reach sandbox API: {error.reason}") from error


def download_world(team, team_key, data_dir, simulate, timeout, retries):
    world_url = f"{BASE_URL}/{team}/world"
    dataset_url = f"{BASE_URL}/{team}/dataset"
    if simulate:
        print("Requesting sandbox world simulation...")
        api_request(
            world_url,
            team_key,
            method="POST",
            body={"action": "simulate"},
            timeout=timeout,
        )
        time.sleep(5)

    data_path = Path(data_dir)
    data_path.mkdir(parents=True, exist_ok=True)
    dataset_info = api_request(dataset_url, team_key, timeout=timeout)
    if isinstance(dataset_info, dict):
        print(
            "Sandbox dataset:",
            dataset_info.get("name", "world"),
            dataset_info.get("kinds", []),
        )

    for filename in DEFAULT_FILES:
        destination = data_path / filename
        suffix = "?answers=0" if filename == "blind.csv" else ""
        source = f"{dataset_url}/{filename}{suffix}"
        last_error = None
        for attempt in range(retries):
            try:
                content = api_request(source, team_key, timeout=timeout)
                if isinstance(content, dict):
                    raise RuntimeError(
                        f"Expected CSV data for {filename}, received JSON."
                    )
                destination.write_bytes(content)
                print(f"Downloaded {filename}: {destination.stat().st_size:,} bytes")
                break
            except (RuntimeError, TimeoutError) as error:
                last_error = error
                if attempt + 1 < retries:
                    time.sleep(2 * (attempt + 1))
        else:
            raise RuntimeError(f"Failed to download {filename}: {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--team")
    parser.add_argument("--team-key")
    parser.add_argument("--data-dir", default=str(PROJECT_ROOT / "data" / "raw"))
    parser.add_argument(
        "--columns-config", default=str(PROJECT_ROOT / "configs" / "columns.yaml")
    )
    parser.add_argument(
        "--output", default=str(PROJECT_ROOT / "reports" / "schema_report.txt")
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Replace the live sandbox world with a fresh simulated dataset.",
    )
    parser.add_argument(
        "--profile-only",
        action="store_true",
        help="Do not contact the API; profile files already in data/raw.",
    )
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()

    if not args.profile_only:
        team, team_key = credential(args.team, args.team_key)
        download_world(
            team,
            team_key,
            args.data_dir,
            args.simulate,
            args.timeout,
            args.retries,
        )

    tables = load_tables(args.data_dir, args.columns_config)
    report_path = write_schema_report(tables, args.output)
    print(f"Profiled {len(tables['transactions']):,} transactions. Report: {report_path}")


if __name__ == "__main__":
    main()
