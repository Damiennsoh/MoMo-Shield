"""Generate private credentials and local-IP settings for the optional demo stack."""

from pathlib import Path
import secrets
import socket

ROOT = Path(__file__).resolve().parent
TEMPLATE = ROOT / ".env.demo.example"
OUTPUT = ROOT / ".env.demo"


def detect_lan_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("192.0.2.1", 80))
        result = sock.getsockname()[0]
        return result if not result.startswith("127.") else "127.0.0.1"
    except OSError:
        return "127.0.0.1"
    finally:
        sock.close()


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(".env.demo already exists; refusing to overwrite its private credentials.")

    address = detect_lan_ip()
    contents = TEMPLATE.read_text(encoding="utf-8")
    contents = contents.replace("192.168.1.50", address)
    contents = contents.replace("REPLACE_WITH_RANDOM_URLSAFE_TOKEN", secrets.token_urlsafe(32))
    contents = contents.replace("REPLACE_WITH_RANDOM_HEX_PASSWORD", secrets.token_hex(24), 1)
    contents = contents.replace("REPLACE_WITH_DIFFERENT_RANDOM_HEX_PASSWORD", secrets.token_hex(24))
    OUTPUT.write_text(contents, encoding="utf-8")
    try:
        OUTPUT.chmod(0o600)
    except OSError:
        pass
    print("Created ignored .env.demo with fresh credentials; values were not printed.")
    print(f"Detected LAN IP: {address}")
    if address == "127.0.0.1":
        print("No LAN interface was detected. Connect to trusted Wi-Fi and set DEMO_LAN_IP and ASTERISK_MEDIA_IP manually.")
    print("Review .env.demo, then run Docker Compose as described in README.md.")


if __name__ == "__main__":
    main()
