"""Backward-compatible entry point for the canonical release self-check.

Historical automation may still call ``self_check_v75.py``. Keep that filename as a
thin wrapper only; release/version behavior lives in ``self_check_release.py`` and
uses ``jarvis.version.APP_VERSION``.
"""

from self_check_release import main


if __name__ == '__main__':
    raise SystemExit(main())
