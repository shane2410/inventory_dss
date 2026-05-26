#!/usr/bin/env python3
"""
Scan template files and convert non-UTF-8 encoded files to UTF-8 (without BOM).
Usage:
  python tools/convert_templates_to_utf8.py [path/to/templates]
If no path is given, defaults to './inventory/Templates'.
"""
import sys
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parent.parent / 'inventory' / 'Templates'

def detect_and_convert(path: Path):
    changed = []
    for p in path.rglob('*.html'):
        try:
            b = p.read_bytes()
        except Exception as e:
            print(f"[ERROR] Cannot read {p}: {e}")
            continue
        # Fast check: try utf-8
        try:
            s = b.decode('utf-8')
            # If succeeds and contains typical Vietnamese chars, assume ok
            # But still rewrite to normalize line endings and remove BOM if present
            if s.startswith('\ufeff'):
                s = s.lstrip('\ufeff')
                p.write_text(s, encoding='utf-8')
                changed.append(p)
            continue
        except UnicodeDecodeError:
            # try common fallback encodings
            for enc in ('cp1252', 'latin-1', 'cp1250'):
                try:
                    s = b.decode(enc)
                    p.write_text(s, encoding='utf-8')
                    changed.append(p)
                    print(f"Converted {p} from {enc} -> utf-8")
                    break
                except Exception:
                    continue
            else:
                print(f"[WARN] Could not decode {p} with common encodings")
    return changed

if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    if not target.exists():
        print(f"Target path {target} does not exist")
        sys.exit(2)
    print(f"Scanning templates in {target} ...")
    changed = detect_and_convert(target)
    print(f"Done. Converted {len(changed)} files.")
    if changed:
        for p in changed:
            print(f" - {p}")
