from __future__ import annotations

import argparse
import sys
from pathlib import Path

# This script is invoked directly by the Windows release pipeline. When Python runs a
# file by path, sys.path[0] is the script directory (scripts/), not necessarily the
# repository root. Add the root derived from this file's location before importing
# canonical application metadata so the generator works from any current directory.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from jarvis.version import APP_VERSION, WINDOWS_FILE_VERSION


def render_version_info() -> str:
    """Render a PyInstaller Windows version-resource file from canonical version data."""
    numeric = tuple(int(part) for part in WINDOWS_FILE_VERSION.split('.'))
    if len(numeric) != 4:
        raise ValueError(f'Windows file version must have four numeric parts: {WINDOWS_FILE_VERSION!r}')

    return f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={numeric},
    prodvers={numeric},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo([
      StringTable(
        '040904B0',
        [
          StringStruct('CompanyName', 'JARVIS AI OMEGA'),
          StringStruct('FileDescription', 'JARVIS AI OMEGA Desktop'),
          StringStruct('FileVersion', '{WINDOWS_FILE_VERSION}'),
          StringStruct('InternalName', 'JARVIS-OMEGA'),
          StringStruct('OriginalFilename', 'JARVIS-OMEGA.exe'),
          StringStruct('ProductName', 'JARVIS AI OMEGA'),
          StringStruct('ProductVersion', '{APP_VERSION}')
        ]
      )
    ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
"""


def main() -> int:
    parser = argparse.ArgumentParser(description='Generate PyInstaller Windows version metadata.')
    parser.add_argument('output', type=Path)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(render_version_info(), encoding='utf-8')
    print(args.output)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
