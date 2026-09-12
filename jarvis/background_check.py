"""Non-recording packaged dependency check, used by Windows build CI."""


def main():
    import sounddevice  # noqa: F401
    import vosk  # noqa: F401
    import pystray  # noqa: F401
    from playwright.sync_api import sync_playwright
    # Starts and stops the bundled driver; no microphone or browser is opened.
    with sync_playwright():
        pass
    return 0
