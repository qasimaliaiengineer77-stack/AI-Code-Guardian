import socket
import threading
import time
import webbrowser

import uvicorn
from backend.main import app

HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex((HOST, PORT)) == 0:
            webbrowser.open(URL)
            return

    config = uvicorn.Config(
        app,
        host=HOST,
        port=PORT,
        log_level="info",
    )
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    try:
        for _ in range(100):
            if server.started:
                break
            if not thread.is_alive():
                raise RuntimeError("Guardian server failed to start.")
            time.sleep(0.2)

        if not server.started:
            raise RuntimeError("Server startup timed out.")

        webbrowser.open(URL)
        thread.join()

    except KeyboardInterrupt:
        server.should_exit = True
        thread.join(timeout=10)


if __name__ == "__main__":
    main()