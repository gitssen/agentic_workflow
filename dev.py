import os
import sys
import time
import signal
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# The paths to watch
WATCH_DIR = "."
MAIN_SCRIPT = "main.py"
REGISTER_SCRIPT = "register_tools.py"
PYTHON_BIN = os.path.join("venv", "bin", "python3")

class AppReloader(FileSystemEventHandler):
    def __init__(self):
        self.process = None
        self.restart()

    def restart(self):
        # Terminate existing process group if any
        if self.process:
            print("\n  [Dev] Change detected. Restarting...")
            try:
                # Kill the entire process group (including any subprocesses like mcp_server.py)
                os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
                self.process.wait(timeout=2)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                except ProcessLookupError:
                    pass

        # If tools changed, we should register them first
        # This is a bit simplistic; you could check which file changed.
        # But running registration is quick thanks to our hashing.
        print("  [Dev] Checking tool registry...")
        subprocess.run([PYTHON_BIN, REGISTER_SCRIPT])

        # Start the main process in a new session to create its own process group
        # This allows us to kill the host and all its children together.
        self.process = subprocess.Popen([PYTHON_BIN, MAIN_SCRIPT], preexec_fn=os.setsid)

    def on_modified(self, event):
        if event.is_directory:
            return
        # Ignore history file and pycache
        if event.src_path.endswith(".py") and not any(x in event.src_path for x in ["/__pycache__/", ".agent_history"]):
            self.restart()

def main():
    if not os.path.exists(PYTHON_BIN):
        print(f"Error: Virtual environment not found at {PYTHON_BIN}")
        sys.exit(1)

    print(f"--- Dev Reloader Started ---")
    print(f"Watching for changes in: {WATCH_DIR}")
    print(f"Press Ctrl+C to stop.")

    event_handler = AppReloader()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIR, recursive=True)
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        if event_handler.process:
            print("\n  [Dev] Stopping...")
            try:
                os.killpg(os.getpgid(event_handler.process.pid), signal.SIGTERM)
            except ProcessLookupError:
                pass
    observer.join()

if __name__ == "__main__":
    main()
