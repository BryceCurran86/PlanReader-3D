"""S3 driver: every page of every listed original, smallest page first, N workers, per-page budget. Read-only.

usage: python tools/item8_s3/s3_driver.py <sources_dir> <out_dir> [budget_seconds=1500] [workers=5]

<sources_dir> is the private sources directory (the one that holds au_qld_lot16_power, au_qld_3laurel, au_qld_q5446_... and
au_qld_maryborough_service_station). The originals are never copied or published; only counts are written to <out_dir>."""
import concurrent.futures
import json
import subprocess
import sys
import time
from pathlib import Path

import fitz

HERE = Path(__file__).resolve().parent
DOCS = [
    ("lot16", "au_qld_lot16_power/1. Construction Plans - Lot 16 Power (REV E).pdf"),
    ("3laurel", "au_qld_3laurel/3LAUREL - Construction Plan Set Rev3 08.05.26.pdf"),
    ("q5446", "au_qld_q5446_armstrong32_harlequin/Q5446_Standard_Plans_V1_20220320.pdf"),
    ("maryborough", "au_qld_maryborough_service_station/Arch_Combined_Maryborough_Service_Station.pdf"),
]


def main() -> None:
    sources = Path(sys.argv[1])
    out = Path(sys.argv[2])
    budget = float(sys.argv[3]) if len(sys.argv) > 3 else 1500.0
    workers = int(sys.argv[4]) if len(sys.argv) > 4 else 5
    out.mkdir(parents=True, exist_ok=True)
    jobs = []
    for label, relative in DOCS:
        pdf = sources / relative
        with fitz.open(pdf) as doc:
            for index, page in enumerate(doc):
                jobs.append((len(page.get_drawings()), label, pdf, index + 1))
    jobs.sort(key=lambda j: (j[0], j[1], j[3]))
    log = (out / "driver.log").open("a", encoding="utf-8")

    def run(job):
        drawings, label, pdf, page = job
        target = out / f"{label}_p{page}.json"
        if target.exists():
            return f"{label} p{page} cached"
        started = time.time()
        try:
            proc = subprocess.run(
                [sys.executable, str(HERE / "s3_census.py"), label, str(pdf), str(page), str(target), str(budget)],
                capture_output=True, text=True, timeout=budget + 600)
            tail = (proc.stdout.strip().splitlines() or ["(no output)"])[-1]
        except subprocess.TimeoutExpired:
            target.write_text(json.dumps(dict(label=label, page=page, status="killed_wall_clock", rows=[], structures_found=0,
                                              structures_processed=0, seconds=round(time.time() - started, 1))),
                              encoding="utf-8")
            tail = f"{label} {page} killed_wall_clock"
        line = f"[{drawings} drawings] {tail}"
        log.write(line + "\n")
        log.flush()
        return line

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for line in pool.map(run, jobs):
            print(line, flush=True)
    print("ALL DONE", flush=True)


if __name__ == "__main__":
    main()
