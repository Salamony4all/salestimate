
import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# --- Configuration ---
WATCH_PATHS = ['.', 'templates']
EXCLUDED_DIRS = ['./static/images', './__pycache__', './.venv', './.idx']
MAIN_APP_FILE = 'main.py'
PORT = '5000'
# ---------------------

class AppReloader(FileSystemEventHandler):
    """Restarts the Flask application when a file changes."""
    def __init__(self):
        self.process = None
        self.start_process()

    def start_process(self):
        """Starts the Flask server in a new process."""
        if self.process:
            self.process.kill()
            self.process.wait()

        command = [
            "python", "-u", "-m", "flask", "--app", "main", "run",
            "--debug", "--no-reload", f"--port={PORT}"
        ]

        # Activate virtual environment if it exists
        prefixed_command = f"source .venv/bin/activate && {' '.join(command)}"

        print(f"Starting server with command: {prefixed_command}")
        self.process = subprocess.Popen(prefixed_command, shell=True, executable="/bin/bash")

    def on_any_event(self, event):
        """
        Called when a file or directory is modified, created, deleted, or moved.
        """
        is_excluded = any(event.src_path.startswith(d) for d in EXCLUDED_DIRS)
        if not event.is_directory and not is_excluded and not event.src_path.endswith('.pyc'):
            print(f"Change detected in {event.src_path}. Reloading server...")
            self.start_process()

if __name__ == "__main__":
    event_handler = AppReloader()
    observer = Observer()

    for path in WATCH_PATHS:
        observer.schedule(event_handler, path, recursive=True)

    print("Starting file watcher...")
    observer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        if event_handler.process:
            event_handler.process.kill()
            event_handler.process.wait()
        print("Watcher and server stopped.")

    observer.join()
