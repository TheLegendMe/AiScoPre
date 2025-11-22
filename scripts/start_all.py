import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    # Simple multi-process launcher for local development.
    services = [
        ("match_service", ["python", "-m", "services.match_service"]),
        ("team_service", ["python", "-m", "services.team_service"]),
        ("user_service", ["python", "-m", "services.user_service"]),
        ("model_service", ["python", "-m", "services.model_service"]),
        ("feature_service", ["python", "-m", "services.feature_service"]),
        ("prediction_service", ["python", "-m", "services.prediction_service"]),
        ("gateway", ["python", "-m", "services.gateway"]),
    ]

    procs: list[tuple[str, subprocess.Popen]] = []
    try:
        for name, cmd in services:
            proc = subprocess.Popen(cmd, cwd=str(ROOT))
            procs.append((name, proc))
            print(f"Started {name} with PID {proc.pid}")
            # Stagger startup a little so dependencies have time to bind ports.
            time.sleep(0.3)

        print("All services started. Press Ctrl+C to stop.")
        while True:
            time.sleep(1.0)
            # Optional: exit if any child dies.
            for name, proc in procs:
                if proc.poll() is not None:
                    print(f"Service {name} exited with code {proc.returncode}, shutting down.")
                    return
    except KeyboardInterrupt:
        print("Received keyboard interrupt, terminating services...")
    finally:
        for name, proc in procs:
            proc.terminate()
        for name, proc in procs:
            try:
                proc.wait(timeout=5.0)
            except subprocess.TimeoutExpired:
                proc.kill()


if __name__ == "__main__":
    if sys.version_info < (3, 10):
        print("Python 3.10+ recommended", file=sys.stderr)
    main()

