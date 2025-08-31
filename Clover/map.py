import sys, re
inp = sys.argv[1]
with open(inp, "r", encoding="utf-8", errors="ignore") as f:
    for line in f:
        for w in re.findall(r"[A-Za-z]+", line.lower()):
            print(f"{w}\t1")
