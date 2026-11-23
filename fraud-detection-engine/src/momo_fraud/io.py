"""Load sandbox tables and normalize source columns."""

from pathlib import Path
from typing import Dict

import pandas as pd
import yaml


TABLE_FILES = {
    "transactions": "transactions.csv",
    "blind_transactions": "blind.csv",
    "people": "people.csv",
    "sims": "sims.csv",
    "wallets": "wallets.csv",
    "bank_accounts": "bank_accounts.csv",
    "calls": "calls.csv",
    "texts": "texts.csv",
    "sim_events": "sim_events.csv",
    "complaints": "complaints.csv",
}

TIMESTAMP_COLUMNS = {
    "transactions": "timestamp",
    "calls": "timestamp",
    "texts": "timestamp",
    "sim_events": "timestamp",
    "wallets": "opened_at",
}


def load_yaml_config(path: str | Path | None) -> dict:
    if path is None:
        return {}
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Config file does not exist: {config_path}")
    with config_path.open(encoding="utf-8") as file:
        config = yaml.safe_load(file) or {}
    if not isinstance(config, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {config_path}")
    return config


def load_tables(
    data_dir: str | Path,
    columns_config: str | Path | None = None,
) -> Dict[str, pd.DataFrame]:
    """Load available CSV tables; transactions are required, others are optional."""
    data_path = Path(data_dir)
    if not data_path.is_dir():
        raise FileNotFoundError(f"Data directory does not exist: {data_path}")

    config = load_yaml_config(columns_config)
    mappings = config.get("columns", {})

    tables: Dict[str, pd.DataFrame] = {}
    for table_name, filename in TABLE_FILES.items():
        path = data_path / filename
        if not path.is_file():
            if table_name == "transactions":
                raise FileNotFoundError(f"Required transactions table not found: {path}")
            tables[table_name] = pd.DataFrame()
            continue

        frame = pd.read_csv(path)
        rename_map = mappings.get(table_name, {})
        if rename_map:
            frame = frame.rename(columns=rename_map)
        timestamp_column = TIMESTAMP_COLUMNS.get(table_name)
        if timestamp_column and timestamp_column in frame:
            frame[timestamp_column] = pd.to_datetime(
                frame[timestamp_column], errors="coerce", utc=True
            )
        tables[table_name] = frame

    required = {"timestamp", "payer_number", "payee_number", "amount", "type"}
    missing = required.difference(tables["transactions"].columns)
    if missing:
        raise ValueError(
            "Transactions table is missing required internal columns: "
            + ", ".join(sorted(missing))
        )
    invalid_timestamps = tables["transactions"]["timestamp"].isna().sum()
    if invalid_timestamps:
        raise ValueError(
            f"Transactions table has {invalid_timestamps} invalid timestamps."
        )
    return tables


def write_schema_report(
    tables: Dict[str, pd.DataFrame], output_path: str | Path
) -> Path:
    """Write a compact report of table columns, row counts, and null counts."""
    report_path = Path(output_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["Sandbox schema report", "====================="]
    for table_name, frame in tables.items():
        lines.extend(["", f"{table_name}: {len(frame):,} rows"])
        if frame.empty and len(frame.columns) == 0:
            lines.append("  (table not present)")
            continue
        for column in frame.columns:
            lines.append(
                f"  {column}: dtype={frame[column].dtype}, "
                f"nulls={int(frame[column].isna().sum()):,}"
            )
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path
