#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
import shutil
import sys


BAZARR_CONFIG = Path("/opt/bazarr/bazarr/app/config.py")


def backup_file(path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.bak.subsdump.{ts}")
    shutil.copy2(path, backup)
    return backup


def main() -> int:
    if not BAZARR_CONFIG.exists():
        print(f"ERROR: Bazarr config file not found: {BAZARR_CONFIG}")
        return 1

    content = BAZARR_CONFIG.read_text(encoding="utf-8")

    if "Validator('subsdump.api_url'" in content and "Validator('subsdump.api_key'" in content:
        print("OK: subsdump validators already exist in config.py")
        return 0

    needle = (
        "    # subdl section\n"
        "    Validator('subdl.api_key', must_exist=True, default='', is_type_of=str, cast=str),\n"
    )

    insert = (
        "    # subdl section\n"
        "    Validator('subdl.api_key', must_exist=True, default='', is_type_of=str, cast=str),\n"
        "\n"
        "    # subsdump section\n"
        "    Validator('subsdump.api_url', must_exist=True, default='https://subs.d3lphi3r.com', is_type_of=str, cast=str),\n"
        "    Validator('subsdump.api_key', must_exist=True, default='', is_type_of=str, cast=str),\n"
    )

    if needle not in content:
        print("ERROR: Could not find subdl validator block in config.py")
        return 2

    backup = backup_file(BAZARR_CONFIG)
    updated = content.replace(needle, insert, 1)
    BAZARR_CONFIG.write_text(updated, encoding="utf-8")

    print("OK: patched config.py")
    print(f"Backup: {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
