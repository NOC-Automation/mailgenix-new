
#!/usr/bin/env python3
"""
Update DJANGO_ALLOWED_HOSTS inside a .env file based on the EC2 instance's current public IP.
Primary source: EC2 Instance Metadata Service v2 (IMDSv2).
Fallback: IMDSv1; optional AWS CLI (if IMDS fails and CLI is configured/instance role attached).

Features:
- Robust logging (file + stdout) with rotation
- Jakarta timezone (Asia/Jakarta) timestamps
- Permission-safe: fallback to ~/.update_allowed_hosts_logs if /var/log not writable
- Timestamped backup of .env before write
- IPv4 validation
- Dry-run mode
- Preserve existing hosts (optional): replace old IPs with new IP, keep non-IP hosts
- Extra hosts (optional): add arbitrary hosts
"""

import argparse
import logging
from logging.handlers import RotatingFileHandler
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# ---------------------------
# Timezone: Asia/Jakarta (GMT+7)
# ---------------------------
try:
    os.environ["TZ"] = "Asia/Jakarta"
    time.tzset()  # Unix only
except Exception:
    pass

def jakarta_formatter(fmt: str, datefmt: str | None = None) -> logging.Formatter:
    """
    Return a logging.Formatter that prints timestamps in localtime (Asia/Jakarta via TZ).
    """
    f = logging.Formatter(fmt=fmt, datefmt=datefmt)
    # Force formatter to use localtime instead of UTC
    f.converter = time.localtime
    return f

# ---------------------------
# Logging Configuration (robust)
# ---------------------------
def build_logger() -> logging.Logger:
    logger = logging.getLogger("update_allowed_hosts")
    logger.setLevel(logging.INFO)
    logger.propagate = False  # avoid duplicate logs

    fmt = "%(asctime)s | %(levelname)s | %(message)s"
    datefmt = "%Y-%m-%d %H:%M:%S"

    # Try /var/log first
    primary_dir = Path("/var/log/update_allowed_hosts")
    fallback_dir = Path.home() / ".update_allowed_hosts_logs"

    log_paths_tried = []

    def _add_handlers(target_dir: Path):
        target_dir.mkdir(parents=True, exist_ok=True)
        log_file = target_dir / "update_allowed_hosts.log"
        file_handler = RotatingFileHandler(log_file, maxBytes=1_000_000, backupCount=3)
        file_handler.setFormatter(jakarta_formatter(fmt, datefmt))
        logger.addHandler(file_handler)

        console = logging.StreamHandler(sys.stdout)
        console.setFormatter(jakarta_formatter(fmt, datefmt))
        logger.addHandler(console)
        return log_file

    try:
        log_file = _add_handlers(primary_dir)
    except Exception as e:
        # If permission denied or any error, fallback to home dir
        for h in list(logger.handlers):
            logger.removeHandler(h)
        log_paths_tried.append(str(primary_dir))
        log_file = _add_handlers(fallback_dir)
        logger.warning(f"Cannot write logs to {primary_dir}, falling back to {fallback_dir}. Error: {e}")

    logger.info("Logger initialized.")
    return logger

logger = build_logger()

# ---------------------------
# Shell helpers (IMDS & CLI)
# ---------------------------
def run_cmd(cmd: List[str], timeout: int = 10) -> subprocess.CompletedProcess:
    """Run a shell command and return CompletedProcess, logging stderr if any."""
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            logger.error(f"Command failed ({proc.returncode}): {' '.join(cmd)}")
            if proc.stderr:
                logger.error(f"stderr: {proc.stderr.strip()}")
        return proc
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out: {' '.join(cmd)}")
        raise
    except Exception as e:
        logger.exception(f"Error running command: {e}")
        raise


def _get_imds_v2_token(ttl_seconds: int = 21600) -> str:
    """Obtain IMDSv2 token. Returns empty string if failed."""
    try:
        proc = run_cmd(
            ["curl", "-s", "-X", "PUT", "http://169.254.169.254/latest/api/token",
             "-H", f"X-aws-ec2-metadata-token-ttl-seconds: {ttl_seconds}"],
            timeout=5
        )
        return proc.stdout.strip()
    except Exception:
        return ""


def _imds_get(path: str, token: Optional[str], timeout: int = 5) -> str:
    """Fetch a metadata path using IMDSv2 token if available, otherwise IMDSv1."""
    headers = []
    if token:
        headers = ["-H", f"X-aws-ec2-metadata-token: {token}"]
    cmd = ["curl", "-s"] + headers + [f"http://169.254.169.254/latest/meta-data/{path}"]
    proc = run_cmd(cmd, timeout=timeout)
    return proc.stdout.strip()


def get_instance_id() -> str:
    """Fetch EC2 instance-id via IMDSv2 (preferred), fallback IMDSv1."""
    logger.info("Fetching instance-id from EC2 metadata (IMDSv2)...")
    token = _get_imds_v2_token()
    instance_id = _imds_get("instance-id", token) or _imds_get("instance-id", None)
    if not instance_id:
        raise RuntimeError("Failed to obtain instance-id from metadata (IMDS).")
    logger.info(f"Instance ID: {instance_id}")
    return instance_id


def get_public_ip_via_metadata() -> str:
    """Preferred: fetch public IPv4 via IMDSv2 (no AWS CLI needed)."""
    logger.info("Fetching public IPv4 from EC2 metadata (IMDSv2)...")
    token = _get_imds_v2_token()
    public_ip = _imds_get("public-ipv4", token) or _imds_get("public-ipv4", None)
    if not public_ip:
        raise RuntimeError("Failed to obtain public-ipv4 from metadata.")
    logger.info(f"Public IP (IMDS): {public_ip}")
    return public_ip


def get_public_ip_via_aws_cli(instance_id: str) -> str:
    """Fallback: Query AWS CLI for the public IP of the given instance."""
    logger.info("Querying AWS CLI for public IP (fallback)...")
    cmd = [
        "aws", "ec2", "describe-instances", "--instance-ids", instance_id,
        "--query", "Reservations[0].Instances[0].PublicIpAddress", "--output", "text",
    ]
    proc = run_cmd(cmd, timeout=20)
    if proc.returncode != 0:
        raise RuntimeError(f"AWS CLI error: {proc.stderr.strip()}")
    public_ip = proc.stdout.strip()
    if not public_ip or public_ip in ("None", "null"):
        raise RuntimeError("Public IP not found via AWS CLI (instance may not have public IP).")
    logger.info(f"Public IP (CLI): {public_ip}")
    return public_ip

# ---------------------------
# .env update helpers
# ---------------------------
def is_valid_ipv4(ip: str) -> bool:
    """Simple IPv4 validation."""
    pattern = r"^(?:\d{1,3}\.){3}\d{1,3}$"
    if not re.match(pattern, ip):
        return False
    try:
        return all(0 <= int(p) <= 255 for p in ip.split("."))
    except ValueError:
        return False


def backup_file(path: Path) -> Path:
    """Create a timestamped backup of the file."""
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")  # localtime (Jakarta)
    backup_path = path.with_suffix(path.suffix + f".bak.{timestamp}")
    shutil.copy2(path, backup_path)
    logger.info(f"Backup created: {backup_path}")
    return backup_path


def parse_hosts(value: str) -> List[str]:
    """Parse comma-separated hosts string to a list, stripping spaces, removing empties."""
    return [h.strip() for h in value.split(",") if h.strip()]


def join_hosts(hosts: List[str]) -> str:
    """Join hosts list to a canonical comma-separated string."""
    return ",".join(hosts)


def updated_endswith_newline(text: str) -> bool:
    return text.endswith("\n")


def update_env_allowed_hosts(
    env_path: Path,
    public_ip: str,
    preserve_existing: bool = False,
    extra_hosts: Optional[List[str]] = None,
    dry_run: bool = False,
) -> bool:
    """
    Update DJANGO_ALLOWED_HOSTS in .env:
      - If preserve_existing=False (default): set to 'localhost,<public_ip>' (+ extra_hosts if provided).
      - If preserve_existing=True: keep non-IP hosts already present, ensure 'localhost', replace any old IPv4 with <public_ip>, add extra_hosts.

    Returns True if changes are made; False if no change required.
    """
    logger.info(f"Updating DJANGO_ALLOWED_HOSTS in: {env_path}")

    # Ensure .env exists; create empty if not
    if not env_path.exists():
        logger.warning(".env not found, creating a new one.")
        env_path.touch()

    original = env_path.read_text(encoding="utf-8")
    lines = original.splitlines()

    key = "DJANGO_ALLOWED_HOSTS"
    found_idx = None
    current_value = None

    for idx, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            found_idx = idx
            current_value = line.split("=", 1)[1].strip()
            break

    # Build new hosts
    hosts_set = set()
    if preserve_existing and current_value:
        existing = parse_hosts(current_value)
        # Keep non-IP hosts, drop old IPs
        for h in existing:
            if not is_valid_ipv4(h):
                hosts_set.add(h)
    # Always ensure localhost
    hosts_set.add("localhost")
    # Add new public IP
    hosts_set.add(public_ip)
    # Add extras if any
    if extra_hosts:
        for h in extra_hosts:
            if h and h.strip():
                hosts_set.add(h.strip())

    new_value = join_hosts(sorted(hosts_set))
    new_line = f"{key}={new_value}"

    if found_idx is not None:
        if lines[found_idx].strip() == new_line:
            logger.info("DJANGO_ALLOWED_HOSTS already up-to-date. No changes made.")
            return False
        lines[found_idx] = new_line
    else:
        logger.info("DJANGO_ALLOWED_HOSTS not found. Adding a new line at the end.")
        lines.append(new_line)

    updated = "\n".join(lines) + ("\n" if not updated_endswith_newline(original) else "")

    if dry_run:
        logger.info("[DRY-RUN] Skipping write. Preview of change:")
        logger.info(f"New DJANGO_ALLOWED_HOSTS line:\n{new_line}")
        return True

    # Backup then atomic-ish write; ensure resulting file is readable by ubuntu (0644)
    backup_file(env_path)
    tmp_path = env_path.with_suffix(".tmp")
    tmp_path.write_text(updated, encoding="utf-8")
    os.chmod(tmp_path, 0o644)  # ensure readable by non-root
    tmp_path.replace(env_path)

    logger.info("DJANGO_ALLOWED_HOSTS updated successfully.")
    return True

# ---------------------------
# CLI
# ---------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Update DJANGO_ALLOWED_HOSTS in .env from EC2 public IP (IMDSv2 first, CLI fallback optional)."
    )
    parser.add_argument("--env-path", type=str, help="Path to .env file.")
    parser.add_argument("--dry-run", action="store_true", help="Show intended changes without writing.")
    parser.add_argument(
        "--preserve-existing",
        action="store_true",
        help="Preserve existing non-IP hosts and replace old IPs with current public IP.",
    )
    parser.add_argument(
        "--extra-hosts",
        type=str,
        help="Comma-separated extra hosts to include (e.g., 'api.example.com,admin.example.com').",
    )
    return parser.parse_args()


def main():
    try:
        args = parse_args()

        env_path_str = args.env_path or os.environ.get("ENV_PATH") or "/home/ubuntu/mailgenix/automation/.env"
        env_path = Path(env_path_str).resolve()
        logger.info(f"Using .env path: {env_path}")

        # Prefer IMDS; fallback to CLI if you want (optional)
        try:
            public_ip = get_public_ip_via_metadata()
        except Exception as e:
            logger.warning(f"IMDS public IP fetch failed: {e}")
            # Optional CLI fallback:
            try:
                instance_id = get_instance_id()
                public_ip = get_public_ip_via_aws_cli(instance_id)
            except Exception as e2:
                raise RuntimeError(f"Failed to obtain public IP via metadata and AWS CLI: {e2}") from e

        if not is_valid_ipv4(public_ip):
            raise ValueError(f"Invalid IPv4 format received: {public_ip}")

        extra_hosts = parse_hosts(args.extra_hosts) if args.extra_hosts else None

        changed = update_env_allowed_hosts(
            env_path,
            public_ip,
            preserve_existing=args.preserve_existing,
            extra_hosts=extra_hosts,
            dry_run=args.dry_run,
        )

        if changed:
            logger.info("Done. You can now restart your Django app.")
        else:
            logger.info("No change required.")

        sys.exit(0)

    except Exception as e:
        logger.exception(f"Failed to update DJANGO_ALLOWED_HOSTS: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

