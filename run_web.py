import os
import sys

BASE_DIR = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)


def resource_path(relative_path):
    base_path = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base_path, relative_path)


def find_available_port(start_port: int = 8501, max_tries: int = 20) -> int:
    import socket

    for p in range(start_port, start_port + max_tries):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex(("127.0.0.1", p)) != 0:
                    return p
        except Exception:
            return p
    return start_port


def main():
    import contextlib
    import threading
    import time
    import webbrowser

    from streamlit.web import cli as stcli

    app_path = resource_path("app_web.py")
    env_port = os.environ.get("STREAMLIT_SERVER_PORT") or os.environ.get("PORT")
    port = int(env_port) if env_port and env_port.isdigit() else find_available_port(8501)
    headless = os.environ.get("HEADLESS", "false").lower() in ("true", "1", "yes")

    if not headless:

        def open_browser():
            time.sleep(1.2)
            with contextlib.suppress(Exception):
                webbrowser.open(f"http://localhost:{port}")

        threading.Thread(target=open_browser, daemon=True).start()

    sys.argv = [
        "streamlit",
        "run",
        app_path,
        "--global.developmentMode=false",
        "--server.headless=true",
        "--server.address=localhost",
        f"--server.port={port}",
        "--server.enableCORS=false",
        "--server.enableXsrfProtection=false",
        "--browser.gatherUsageStats=false",
    ]
    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
