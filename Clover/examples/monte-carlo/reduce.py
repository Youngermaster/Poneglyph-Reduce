#!/usr/bin/env python3
import sys

def reducer():
    inside_count = 0
    total_count = 0

    for line in sys.stdin:
        key, value = line.strip().split("\t")
        value = int(value)
        if key == "inside":
            inside_count += value
        elif key == "total":
            total_count += value

    if total_count > 0:
        pi_estimate = 4 * inside_count / total_count
        print(f"Estimación de pi: {pi_estimate}")
    else:
        print("No se encontraron datos válidos.")

if __name__ == "__main__":
    reducer()
