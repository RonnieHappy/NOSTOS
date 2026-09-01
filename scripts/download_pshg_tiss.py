from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


API = "https://api.osf.io/v2/nodes/udtqp/files/osfstorage"
ROOT_FOLDER = "61b48a7a2e9cd200b9b631e3"  # skin tissue unstained


def listing(folder: str) -> list[dict]:
    url = f"{API}/{folder}/?page[size]=100"
    rows: list[dict] = []
    while url:
        for attempt in range(6):
            try:
                with urllib.request.urlopen(url, timeout=60) as response:
                    payload = json.load(response)
                break
            except Exception:
                if attempt == 5:
                    raise
                time.sleep(2 ** attempt)
        rows.extend(payload["data"])
        url = payload.get("links", {}).get("next")
    return rows


def download(url: str, target: Path) -> str:
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        for attempt in range(6):
            try:
                urllib.request.urlretrieve(url, target)
                break
            except Exception:
                target.unlink(missing_ok=True)
                if attempt == 5:
                    raise
                time.sleep(2 ** attempt)
    return hashlib.sha256(target.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--root-folder", default=ROOT_FOLDER)
    parser.add_argument("--subset", default="skin tissue unstained / FSHG")
    args = parser.parse_args()
    tasks = []
    for roi in sorted(listing(args.root_folder), key=lambda row: row["attributes"]["name"]):
        if roi["attributes"]["kind"] != "folder":
            continue
        roi_name = roi["attributes"]["name"]
        print(f"indexing {roi_name}", flush=True)
        children = listing(roi["id"])
        fshg = next(row for row in children if row["attributes"]["name"] == "FSHG")
        fshg_children = listing(fshg["id"])
        results = next(row for row in fshg_children if row["attributes"]["name"] == "Results")
        selected = [row for row in fshg_children if row["attributes"]["name"].startswith(f"{roi_name}_FSHG_p")]
        selected += [row for row in listing(results["id"]) if row["attributes"]["name"] in {"FI.tif", "R2.tif", "SNR.tif"}]
        for row in sorted(selected, key=lambda item: item["attributes"]["name"]):
            name = row["attributes"]["name"]
            target = args.output / roi_name / name
            tasks.append((roi_name, row, target))
    def retrieve(task: tuple[str, dict, Path]) -> dict:
        roi_name, row, target = task
        sha256 = download(row["links"]["download"], target)
        return {"roi": roi_name, "osf_file_id": row["id"], "name": row["attributes"]["name"],
                "bytes": target.stat().st_size, "sha256": sha256}
    with ThreadPoolExecutor(max_workers=8) as pool:
        manifest = sorted(pool.map(retrieve, tasks), key=lambda row: (row["roi"], row["name"]))
    receipt = {"dataset": "PSHG-TISS", "doi": "10.17605/OSF.IO/UDTQP",
               "subset": args.subset, "root_folder": args.root_folder, "files": manifest}
    (args.output / "download_manifest.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"rois": len({row['roi'] for row in manifest}), "files": len(manifest)}, indent=2))


if __name__ == "__main__":
    main()
