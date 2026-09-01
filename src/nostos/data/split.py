from __future__ import annotations

import argparse
import json
import random
from pathlib import Path


def participant_split(
    participant_ids: list[str],
    seed: int = 240826,
    train_fraction: float = 0.70,
    validation_fraction: float = 0.15,
) -> dict[str, list[str]]:
    if not participant_ids:
        raise ValueError("No participant IDs were provided.")
    if train_fraction <= 0 or validation_fraction <= 0:
        raise ValueError("Train and validation fractions must be positive.")
    if train_fraction + validation_fraction >= 1:
        raise ValueError("Train and validation fractions must leave a positive test fraction.")

    ids = sorted(set(participant_ids))
    random.Random(seed).shuffle(ids)
    total = len(ids)
    train_end = round(total * train_fraction)
    validation_end = train_end + round(total * validation_fraction)
    return {
        "train": sorted(ids[:train_end]),
        "validation": sorted(ids[train_end:validation_end]),
        "test": sorted(ids[validation_end:]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Create participant-safe NOSTOS splits.")
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=240826)
    args = parser.parse_args()

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    splits = participant_split(manifest["participants"], seed=args.seed)
    payload = {"schema_version": 1, "seed": args.seed, "splits": splits}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({name: len(ids) for name, ids in splits.items()}, indent=2))


if __name__ == "__main__":
    main()
