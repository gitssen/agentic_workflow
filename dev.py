import os
import sys
import time
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
        # Terminate existing process if any
        if self.process:
            print("\n  [Dev] Change detected. Restarting...")
            self.process.terminate()
            try:
                self.process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self.process.kill()

        # If tools changed, we should register them first
        # This is a bit simplistic; you could check which file changed.
        # But running registration is quick thanks to our hashing.
        print("  [Dev] Checking tool registry...")
        subprocess.run([PYTHON_BIN, REGISTER_SCRIPT])

        # Start the main process
        # We use a new session to ensure it gets stdin/stdout correctly
        self.process = subprocess.Popen([PYTHON_BIN, MAIN_SCRIPT])

    def on_modified(self, event):
        if event.is_directory:
            return
        if event.src_path.endswith(".py") and not "/__pycache__/" in event.src_path:
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
            event_handler.process.terminate()
    observer.join()

if __name__ == "__main__":
    main()
