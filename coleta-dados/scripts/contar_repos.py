import csv
import sys
from pathlib import Path

csv_path = Path(sys.argv[1])

with open(csv_path) as f:
    repos = set(row["repo_id"] for row in csv.DictReader(f, delimiter='|'))

print(f"Repositórios: {len(repos)}")
