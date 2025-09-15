#!/usr/bin/env python3
import sys

def reducer():
    sum_x = 0.0
    sum_y = 0.0
    sum_xy = 0.0
    sum_x2 = 0.0
    n = 0

    for line in sys.stdin:
        key, val = line.strip().split("\t")
        val = float(val)
        if key == "sum_x":
            sum_x += val
        elif key == "sum_y":
            sum_y += val
        elif key == "sum_xy":
            sum_xy += val
        elif key == "sum_x2":
            sum_x2 += val
        elif key == "count":
            n += int(val)

    if n > 0:
        denom = (n * sum_x2 - sum_x**2)
        if denom == 0:
            print("No se puede calcular regresión: división por cero.")
            return

        beta1 = (n * sum_xy - sum_x * sum_y) / denom
        beta0 = (sum_y - beta1 * sum_x) / n

        print(f"N = {n}")
        print(f"Beta0 (intercepto) = {beta0}")
        print(f"Beta1 (pendiente) = {beta1}")
        print(f"Modelo: y ≈ {beta0:.4f} + {beta1:.4f} * x")
    else:
        print("No data found.")

if __name__ == "__main__":
    reducer()
