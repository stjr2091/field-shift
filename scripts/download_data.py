"""Download raw data into data/raw/.

Raw data never lives in git. Add a dataset, run this script, commit nothing
from data/raw.

TODO: list the datasets this project needs (rainfall, soil) with their
sources, and fill in the download steps below.
"""

DATASETS = []  # (name, source_url, target_path) entries go here


def main():
    for name, source_url, target_path in DATASETS:
        print(f"TODO: download {name} from {source_url} to {target_path}")


if __name__ == "__main__":
    main()
