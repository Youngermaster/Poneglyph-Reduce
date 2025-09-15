#!/usr/bin/env python3
import sys
import math

def mapper():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            x_str, y_str = line.split()
            x, y = float(x_str), float(y_str)
            inside = 1 if x*x + y*y <= 1 else 0
            print(f"inside\t{inside}")
            print("total\t1")
        except ValueError:
            continue  # si hay una línea inválida, la ignora

if __name__ == "__main__":
    mapper()
