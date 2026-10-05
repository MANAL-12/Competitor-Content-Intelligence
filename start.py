import os
import subprocess
import sys


PORT = os.environ.get("PORT", "8501")


print("Starting competitor monitoring service...")

monitor_process = subprocess.Popen(
    [
        sys.executable,
        "src/detection/monitor.py"
    ]
)


print("Starting Streamlit dashboard...")


try:

    subprocess.run(
        [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            "dashboard/app.py",
            "--server.address=0.0.0.0",
            "--server.port",
            PORT
        ],
        check=True
    )

finally:

    print("Stopping monitoring service...")

    monitor_process.terminate()

    monitor_process.wait()