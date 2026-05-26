#!/usr/bin/env python3
"""
Convert specified file types in the project to UTF-8 with backup.
Usage:
  python tools/convert_files_to_utf8.py [path] [ext1,ext2,...]
Defaults: path=./inventory, exts=py,txt,html,css,js

This script makes a .bak copy before overwriting.
"""
import sys
from pathlib import Path

DEFAULT_DIR = Path(__file__).resolve().parent.parent / 'inventory'
EXTS = ['.py', '.html', '.css', '.js', '.txt']

COMMON_ENCODINGS = ['utf-8', 'cp1258', 'cp1252', 'latin-1', 'iso-8859-1', 'utf-16']


def convert(path: Path, exts):
    changed = []
    for p in path.rglob('*'):
        if p.suffix.lower() not in exts:
            continue
        try:
            b = p.read_bytes()
        except Exception as e:
            print(f"[ERROR] Can't read {p}: {e}")
            continue
        # if already valid utf-8 and no BOM, skip
        try:
            s = b.decode('utf-8')
            if s.startswith('\ufeff'):
                s = s.lstrip('\ufeff')
                bak = p.with_suffix(p.suffix + '.bak')
                p.rename(bak)
                p.write_text(s, encoding='utf-8')
                changed.append((p, 'utf-8-was-bom'))
            continue
        except UnicodeDecodeError:
            # try common encodings
            for enc in COMMON_ENCODINGS:
                try:
                    s = b.decode(enc)
                    # write backup
                    bak = p.with_suffix(p.suffix + '.bak')
                    if not bak.exists():
                        p.copy(bak) if hasattr(p, 'copy') else bak.write_bytes(b)
                    p.write_text(s, encoding='utf-8')
                    changed.append((p, enc))
                    print(f"Converted {p} from {enc} -> utf-8")
                    break
                except Exception:
                    continue
            else:
                print(f"[WARN] Could not decode {p} with COMMON_ENCODINGS")
    return changed

if __name__ == '__main__':
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_DIR
    exts = sys.argv[2].split(',') if len(sys.argv) > 2 else EXTS
    exts = [e if e.startswith('.') else '.'+e for e in exts]
    if not target.exists():
        print(f"Target {target} doesn't exist")
        sys.exit(2)
    print(f"Scanning {target} for {exts} ...")
    changed = convert(target, exts)
    print(f"Done. Converted {len(changed)} files.")
    for p,enc in changed:
        print(f" - {p} (from {enc})")
