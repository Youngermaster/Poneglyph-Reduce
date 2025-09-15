#!/usr/bin/env python3
import sys

def mapper():
    """
    Mapper: lee números de stdin, emite:
    sum -> valor
    sumsq -> valor^2
    count -> 1
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            x = float(line)
            print(f"sum\t{x}")
            print(f"sumsq\t{x*x}")
            print("count\t1")
        except ValueError:
            continue

if __name__ == "__main__":
    mapper()
