import sys
from collections import defaultdict

inp = sys.argv[1]
counts = defaultdict(int)
with open(inp, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        line = line.strip()
        if not line: continue
        k, v = line.split("\t", 1)
        counts[k] += int(v)

for k in sorted(counts.keys()):
    print(f"{k}\t{counts[k]}")
