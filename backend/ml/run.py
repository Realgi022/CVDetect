"""Run locally: python -m ml.run [path-to-json]. No model is persisted."""
import argparse
import json
from pathlib import Path

from .baseline import train
from .dataset import load_dataset, split_records
from .evaluate import evaluate


def main():
    parser = argparse.ArgumentParser(description="Offline experimental classifier; not an authorship detector.")
    parser.add_argument("dataset", nargs="?", default=Path(__file__).parent / "fixtures" / "synthetic_smoke.json")
    args = parser.parse_args()
    try:
        records = load_dataset(args.dataset)
        training, test = split_records(records)
        model = train(training, test)
        print(json.dumps(evaluate(model, training, test), indent=2))
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Experiment cannot run: {exc}\n")


if __name__ == "__main__":
    main()
