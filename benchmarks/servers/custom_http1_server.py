import sys
import multiprocessing
from src.core import HighPerformanceWSGIServer
from benchmarks.servers.wsgi_app import app

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    workers = min(4, max(1, (multiprocessing.cpu_count() // 2)))

    server = HighPerformanceWSGIServer(
        app=app, host="0.0.0.0", port=port, workers=workers
    )
    server.run()
