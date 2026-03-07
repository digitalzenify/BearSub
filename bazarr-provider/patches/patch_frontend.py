#!/usr/bin/env python3

from pathlib import Path
from datetime import datetime
import shutil
import sys


FRONTEND_ASSETS = Path("/opt/bazarr/frontend/build/assets")

SUBSDUMP_BLOCK = (
    '{key:"subsdump",name:"SubsDump",description:"Self-hosted subtitle archive and Bazarr provider.",'
    'inputs:['
    '{type:"text",key:"api_url",name:"API URL",defaultValue:"https://subs.d3lphi3r.com"},'
    '{type:"password",key:"api_key",name:"API Key"}'
    ']}'
)

ANCHORS = [
    '},{key:"subdl",inputs:[{type:"text",key:"api_key"}]}',
    '},{key:"d3lphi3r_subs",name:"D3lphi3r Subs",description:"Custom subtitles provider (self-hosted).",inputs:[{type:"text",key:"api_url",name:"API URL",defaultValue:"https://subs.d3lphi3r.com"},{type:"password",key:"api_key",name:"API Key"}]}',
]


def backup_file(path: Path) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = path.with_name(f"{path.name}.bak.subsdump.{ts}")
    shutil.copy2(path, backup)
    return backup


def patch_content(content: str) -> tuple[str, bool]:
    if 'key:"subsdump"' in content:
        return content, False

    for anchor in ANCHORS:
        if anchor in content:
            return content.replace(anchor, anchor + "," + SUBSDUMP_BLOCK, 1), True

    raise RuntimeError("Could not find a known provider anchor in frontend asset")


def main() -> int:
    if not FRONTEND_ASSETS.exists():
        print(f"ERROR: Frontend assets directory not found: {FRONTEND_ASSETS}")
        return 1

    js_files = sorted(FRONTEND_ASSETS.glob("index-*.js"))
    if not js_files:
        print("ERROR: No frontend build assets found")
        return 2

    patched_count = 0
    skipped_count = 0

    for js_file in js_files:
        content = js_file.read_text(encoding="utf-8")

        try:
            updated, changed = patch_content(content)
        except RuntimeError:
            continue

        if not changed:
            print(f"OK: already patched: {js_file}")
            skipped_count += 1
            continue

        backup = backup_file(js_file)
        js_file.write_text(updated, encoding="utf-8")

        print(f"OK: patched: {js_file}")
        print(f"Backup: {backup}")
        patched_count += 1

    if patched_count == 0 and skipped_count == 0:
        print("ERROR: Could not patch any frontend asset")
        return 3

    print(f"Done. patched={patched_count}, skipped={skipped_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
