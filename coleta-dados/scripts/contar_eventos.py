import csv
import sys
from collections import Counter
from pathlib import Path

csv.field_size_limit(sys.maxsize)


csv_path = Path(sys.argv[1])

with open(csv_path) as f:
    counts = Counter(row["event_type"] for row in csv.DictReader(f, delimiter='|'))

for t, c in counts.most_common():
    print(f"{t}: {c}")
print(f"total: {sum(counts.values())}")
