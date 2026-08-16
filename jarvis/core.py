"""Compatibility import for JARVIS OMEGA V7.

The public `jarvis.core.JarvisOmega` import remains stable for the desktop/CLI
interfaces while the V7 implementation lives in `core_v7.py`.
"""

from .core_v7 import JarvisOmega

__all__ = ['JarvisOmega']
