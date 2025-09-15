#!/usr/bin/env python3
import sys

def mapper():
    """
    Mapper para regresión lineal.
    Lee pares (x, y) y emite:
      sum_x -> x
      sum_y -> y
      sum_xy -> x*y
      sum_x2 -> x^2
      count -> 1
    """
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            x_str, y_str = line.split()
            x, y = float(x_str), float(y_str)
            print(f"sum_x\t{x}")
            print(f"sum_y\t{y}")
            print(f"sum_xy\t{x*y}")
            print(f"sum_x2\t{x*x}")
            print("count\t1")
        except ValueError:
            continue

if __name__ == "__main__":
    mapper()
