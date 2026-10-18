"""Load test: replays a realistic mix of requests through the same process pool the bot uses.

    python scripts/loadtest.py --requests 400 --concurrency 40 --workers 4

Reports throughput and p50/p95/p99 latency per tool, error count and cache effect.
"""
from __future__ import annotations
import argparse
import asyncio
import os
import random
import statistics
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

MIX = [  # (weight, tool, input generator)
    (20, "beam", lambda: f"L={random.choice([4, 5, 6, 8, 10])} type=ss w={random.randint(5, 40)} P={random.randint(10, 80)}@2"),
    (12, "rc", lambda: f"b=300 h={random.choice([500, 600, 700])} fc=28 fy=420 Mu={random.randint(80, 350)} Vu={random.randint(60, 250)}"),
    (8, "column", lambda: f"b=400 h=500 fc=28 fy=420 Pu={random.randint(800, 2500)} Mu={random.randint(30, 200)}"),
    (8, "truss", lambda: f"type={random.choice(['pratt', 'howe', 'warren'])} span=12 h=3 n={random.choice([4, 6, 8])} P={random.randint(10, 50)}"),
    (8, "frame", lambda: f"type=portal L={random.choice([5, 6, 8])} H=4 w={random.randint(5, 25)} P={random.randint(5, 30)}"),
    (6, "footing", lambda: f"PD={random.randint(400, 1200)} PL={random.randint(200, 800)} qa={random.choice([150, 200, 250])} c1=400 c2=400"),
    (6, "slab", lambda: f"Lx={random.choice([3, 4, 5])} Ly={random.choice([5, 6])} edges=FSFS wD=2 wL=3"),
    (6, "bearing", lambda: f"B=2 L=2 Df=1.5 c=0 phi={random.choice([25, 30, 35])} gamma=18"),
    (5, "sbeam", lambda: f"Mu={random.randint(50, 300)} Vu=100 Lb={random.choice([2, 3, 4])}"),
    (5, "mix", lambda: f"fc={random.choice([25, 28, 30, 35])}"),
    (4, "channel", lambda: f"shape=trap b=3 z=2 n=0.015 S=0.001 Q={random.randint(2, 15)}"),
    (4, "section", lambda: f"T bf={random.choice([600, 800])} tf=120 bw=300 h={random.choice([500, 600])}"),
    (3, "slope", lambda: f"H={random.choice([6, 8, 10])} beta={random.choice([25, 30, 35])} c=10 phi=30"),
    (3, "codes", lambda: random.choice(["punching shear", "الحد الأدنى للحديد في الكمرات", "load combination"])),
    (2, "schedule", lambda: "C1 Pu=1500 Mu=80; C2 Pu=2200 Mu=60; C3 Pu=900"),
]


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(round(p / 100 * (len(xs) - 1))))]


async def main(a):
    os.environ["WORKERS"] = str(a.workers)
    from civilbot.bot import launch as L   # noqa — needs telegram installed (or the test stub)
    t0 = time.time()
    await asyncio.to_thread(L.start_pool)
    print(f"pool ready ({a.workers} workers) in {time.time() - t0:.1f}s")
    weights = [m[0] for m in MIX]
    lat, errs = {}, 0
    sem = asyncio.Semaphore(a.concurrency)
    reqs = [random.choices(MIX, weights)[0] for _ in range(a.requests)]

    async def one(m):
        nonlocal errs
        _, tool, gen = m
        async with sem:
            s = time.perf_counter()
            try:
                await L.offload("tool", tool, gen(), cache=a.cache)
            except Exception:
                errs += 1
            lat.setdefault(tool, []).append(time.perf_counter() - s)
    t0 = time.perf_counter()
    await asyncio.gather(*(one(m) for m in reqs))
    wall = time.perf_counter() - t0
    allv = [x for v in lat.values() for x in v]
    print(f"\n{a.requests} requests, concurrency {a.concurrency}: {wall:.1f}s → {a.requests / wall:.1f} req/s , errors {errs}")
    print(f"overall  p50 {pct(allv, 50):.2f}s  p95 {pct(allv, 95):.2f}s  p99 {pct(allv, 99):.2f}s  (includes queueing)")
    print(f"{'tool':10s} {'n':>4s} {'p50':>6s} {'p95':>6s} {'max':>6s}")
    for t, v in sorted(lat.items(), key=lambda kv: -statistics.median(kv[1])):
        print(f"{t:10s} {len(v):4d} {pct(v, 50):6.2f} {pct(v, 95):6.2f} {max(v):6.2f}")
    if a.cache:
        print(f"cache hits {L.CACHE.hits} / misses {L.CACHE.miss}")
    L.POOL.shutdown()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--requests", type=int, default=300)
    ap.add_argument("--concurrency", type=int, default=30)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1))
    ap.add_argument("--cache", action="store_true")
    asyncio.run(main(ap.parse_args()))
