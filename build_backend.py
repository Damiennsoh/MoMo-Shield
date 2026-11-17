"""Package the canonical backend/ tree as backend.zip.

The repository's backend/ directory is the single source of truth. Keeping a
second, embedded copy of its modules here caused generated bundles to silently
omit newer API routes and configuration.
"""

from pathlib import Path
import zipfile

ROOT = Path(__file__).resolve().parent
BACKEND_DIR = ROOT / "backend"
OUTPUT = ROOT / "backend.zip"


def build_backend() -> Path:
    if not BACKEND_DIR.is_dir():
        raise FileNotFoundError(f"Backend source directory not found: {BACKEND_DIR}")

    files = sorted(
        path for path in BACKEND_DIR.rglob("*")
        if path.is_file()
        and ".env" not in path.name
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".pyo"}
    )
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT))

    print(f"Packaged {len(files)} backend files into {OUTPUT}")
    return OUTPUT


if __name__ == "__main__":
    build_backend()
