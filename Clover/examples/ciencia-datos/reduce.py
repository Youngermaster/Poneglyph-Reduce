#!/usr/bin/env python3
import sys

def reducer():
    total_sum = 0.0
    total_sumsq = 0.0
    total_count = 0

    for line in sys.stdin:
        key, val = line.strip().split("\t")
        val = float(val)
        if key == "sum":
            total_sum += val
        elif key == "sumsq":
            total_sumsq += val
        elif key == "count":
            total_count += int(val)

    if total_count > 0:
        mean = total_sum / total_count
        variance = (total_sumsq / total_count) - (mean ** 2)
        print(f"N = {total_count}")
        print(f"Mean = {mean}")
        print(f"Variance = {variance}")
    else:
        print("No data found.")

if __name__ == "__main__":
    reducer()
