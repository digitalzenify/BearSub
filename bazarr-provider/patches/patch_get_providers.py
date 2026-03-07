#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
import shutil
import sys


BAZARR_GET_PROVIDERS = Path("/opt/bazarr/bazarr/app/get_providers.py")


def backup_file(path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.bak.subsdump.{ts}")
    shutil.copy2(path, backup)
    return backup


def patch_throttle_map(content: str) -> str:
    if '"subsdump": {' in content and 'ProviderError: (datetime.timedelta(hours=1), "1 hour")' in content:
        return content

    needle = (
        '        "subdl": {\n'
        '            ProviderError: (datetime.timedelta(hours=1), "1 hour"),\n'
        '        }\n'
    )

    replacement = (
        '        "subdl": {\n'
        '            ProviderError: (datetime.timedelta(hours=1), "1 hour"),\n'
        '        },\n'
        '        "subsdump": {\n'
        '            ProviderError: (datetime.timedelta(hours=1), "1 hour"),\n'
        '        }\n'
    )

    if needle not in content:
        raise RuntimeError("Could not find subdl throttle block")

    return content.replace(needle, replacement, 1)


def patch_auth_map(content: str) -> str:
    if '"subsdump": {' in content and "settings.subsdump.api_url" in content and "settings.subsdump.api_key" in content:
        return content

    needle = (
        '        "subdl": {\n'
        "            'api_key': settings.subdl.api_key,\n"
        '        },\n'
    )

    replacement = (
        '        "subdl": {\n'
        "            'api_key': settings.subdl.api_key,\n"
        '        },\n'
        '        "subsdump": {\n'
        "            'api_url': settings.subsdump.api_url,\n"
        "            'api_key': settings.subsdump.api_key,\n"
        '        },\n'
    )

    if needle not in content:
        raise RuntimeError("Could not find subdl auth block")

    return content.replace(needle, replacement, 1)


def main() -> int:
    if not BAZARR_GET_PROVIDERS.exists():
        print(f"ERROR: Bazarr get_providers file not found: {BAZARR_GET_PROVIDERS}")
        return 1

    content = BAZARR_GET_PROVIDERS.read_text(encoding="utf-8")
    original = content

    try:
        content = patch_throttle_map(content)
        content = patch_auth_map(content)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return 2

    if content == original:
        print("OK: get_providers.py already contains subsdump mappings")
        return 0

    backup = backup_file(BAZARR_GET_PROVIDERS)
    BAZARR_GET_PROVIDERS.write_text(content, encoding="utf-8")

    print("OK: patched get_providers.py")
    print(f"Backup: {backup}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
