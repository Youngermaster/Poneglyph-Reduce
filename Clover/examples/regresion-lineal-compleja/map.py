#!/usr/bin/env python3
import sys

# Leer datos desde archivo (sys.argv[1]) - FORMATO COMPATIBLE CON WORKERS
inp = sys.argv[1]
with open(inp, "r", encoding="ascii", errors="ignore") as f:
    for line in f:
        line = line.strip()
        if not line or line.startswith('#'):
            continue

        try:
            # Formato: dataset_name x y
            parts = line.split()
            if len(parts) >= 3:
                dataset = parts[0]
                x = float(parts[1])
                y = float(parts[2])

                # Emitir sumas parciales por dataset
                print(f"{dataset}_sum_x\t{x}")
                print(f"{dataset}_sum_y\t{y}")
                print(f"{dataset}_sum_xy\t{x*y}")
                print(f"{dataset}_sum_x2\t{x*x}")
                print(f"{dataset}_count\t1")

        except (ValueError, IndexError):
            # Ignorar líneas malformadas
            continue
