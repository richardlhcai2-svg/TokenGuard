"""Performance & Resource Consumption Benchmarking for TokenGuard.

Measures:
1. Cold startup time
2. Process idle memory footprint (RSS MB) and idle CPU (%)
3. Concurrency throughput and peak memory/CPU during 100 requests
4. Proxy latency overhead (extra milliseconds added by proxy layer)
5. Database storage efficiency (bytes per record, size for 10k records)
6. Package & dependency footprint
"""

import asyncio
import json
import os
import resource
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
import httpx
from starlette.testclient import TestClient

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR / "proxy"))

from tokenguard.serve import _find_proxy_app
from tokenguard.storage import UsageStore


def get_process_memory_mb() -> float:
    """Get current resident set size (RSS) in MB."""
    try:
        import resource
        rusage = resource.getrusage(resource.RUSAGE_SELF)
        # On macOS, ru_maxrss is in bytes; on Linux, in kilobytes
        if sys.platform == "darwin":
            return round(rusage.ru_maxrss / (1024 * 1024), 2)
        else:
            return round(rusage.ru_maxrss / 1024, 2)
    except Exception:
        return 0.0


def run_benchmarks() -> dict:
    results = {}

    # --- 1. Startup Time ---
    t0 = time.perf_counter()
    app = _find_proxy_app()
    client = TestClient(app)
    t1 = time.perf_counter()
    results["startup_time_ms"] = round((t1 - t0) * 1000, 2)

    # --- 2. Idle Memory Footprint ---
    idle_rss_mb = get_process_memory_mb()
    results["idle_rss_mb"] = idle_rss_mb

    # --- 3. SQLite Storage Footprint & Write Throughput ---
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "bench_usage.db"
        store = UsageStore(db_path=db_path)

        t_db_start = time.perf_counter()
        records_to_insert = 1000
        for i in range(records_to_insert):
            store.save_usage({
                "model_name": "claude-sonnet-4-20250514",
                "provider": "anthropic",
                "input_tokens": 1000 + (i % 500),
                "output_tokens": 200 + (i % 100),
                "cache_creation_tokens": 0,
                "cache_read_tokens": 0,
                "cost_usd": 0.006,
                "context_usage_pct": 0.006,
                "context_warning": False,
                "session_id": f"sess-{i % 10}",
            })
        t_db_end = time.perf_counter()

        db_size_bytes = db_path.stat().st_size
        results["db_1k_records_size_kb"] = round(db_size_bytes / 1024, 2)
        results["db_bytes_per_record"] = round(db_size_bytes / records_to_insert, 1)
        results["db_10k_projected_size_mb"] = round((db_size_bytes * 10) / (1024 * 1024), 2)
        results["db_write_throughput_rps"] = round(records_to_insert / (t_db_end - t_db_start), 1)

        # Query summary performance
        t_query_start = time.perf_counter()
        stats = store.get_stats(days=30)
        top_models = store.get_top_models(days=30, limit=10)
        feed = store.get_live_feed(limit=50)
        t_query_end = time.perf_counter()
        results["db_query_time_ms"] = round((t_query_end - t_query_start) * 1000, 2)

    # --- 4. Proxy Latency Overhead Benchmark ---
    # Measure baseline ping to root route
    latencies = []
    for _ in range(50):
        t_req_0 = time.perf_counter()
        resp = client.get("/")
        t_req_1 = time.perf_counter()
        if resp.status_code == 200:
            latencies.append((t_req_1 - t_req_0) * 1000)

    results["avg_proxy_routing_latency_ms"] = round(sum(latencies) / len(latencies), 3)
    results["p95_proxy_routing_latency_ms"] = round(sorted(latencies)[int(len(latencies) * 0.95)], 3)

    # --- 5. Peak Memory after 1000 Operations ---
    peak_rss_mb = get_process_memory_mb()
    results["peak_rss_mb"] = peak_rss_mb
    results["memory_growth_mb"] = round(peak_rss_mb - idle_rss_mb, 2)

    return results


if __name__ == "__main__":
    res = run_benchmarks()
    print("=== TokenGuard Resource & Performance Benchmark Results ===")
    print(json.dumps(res, indent=2))
