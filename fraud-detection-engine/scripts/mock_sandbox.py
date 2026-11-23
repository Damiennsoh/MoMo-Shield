"""Compatibility entry point for the existing mock data generator."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    runpy.run_path(
        str(Path(__file__).resolve().parents[1] / "mock_sandbox.py"),
        run_name="__main__",
    )

