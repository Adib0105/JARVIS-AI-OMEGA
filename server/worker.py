"""Durable billing inbox worker: python -m server.worker (run beside the API)."""
import signal
import threading
from .app import create_app


def main():
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    app = create_app()
    while not stop.is_set():
        app.state.billing.retry_pending()
        stop.wait(30)


if __name__ == '__main__':
    main()
