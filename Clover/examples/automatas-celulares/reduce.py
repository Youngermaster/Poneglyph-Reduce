#!/usr/bin/env python3
"""
Reducer para Game of Life.
Lee emisiones del mapper (sorted por key idealmente).
- Detecta META para obtener width/height.
- Para cada celda "i,j" calcula conteo de vecinos y estado SELF.
- Aplica reglas de Conway y genera la nueva grilla por stdout en el mismo formato:
  Primero: width height
  Luego: las filas con 0/1 separadas por espacios.
"""
import sys
from collections import defaultdict

def reducer():
    width = height = None
    neigh_counts = defaultdict(int)
    self_state = {}  # (i,j) -> 0/1
    seen_cells = set()

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        # Manejar META
        if parts[0] == "META":
            # formato: META\twidth\theight OR META\theight\twidth (mapper imprime width height)
            try:
                width = int(parts[1])
                height = int(parts[2])
            except Exception:
                # intentar invertir por seguridad
                width = int(parts[2])
                height = int(parts[1])
            continue

        # keys tipo "i,j" con tags
        if len(parts) < 3:
            continue
        key = parts[0]
        tag = parts[1]
        val = parts[2]

        try:
            i_str, j_str = key.split(",")
            i, j = int(i_str), int(j_str)
        except Exception:
            continue

        seen_cells.add((i,j))

        if tag == "NEIGH":
            try:
                neigh_counts[(i,j)] += int(val)
            except Exception:
                pass
        elif tag == "SELF":
            try:
                self_state[(i,j)] = int(val)
            except Exception:
                self_state[(i,j)] = 0

    # Si no recibimos META, inferir bounds por valores vistos (fallback)
    if width is None or height is None:
        max_i = max((i for i,_ in seen_cells), default=-1)
        max_j = max((j for _,j in seen_cells), default=-1)
        height = max_i + 1
        width  = max_j + 1

    # Construir nueva grilla con las reglas de Conway
    new_grid = [[0 for _ in range(width)] for __ in range(height)]
    for i in range(height):
        for j in range(width):
            ncount = neigh_counts.get((i,j), 0)
            s = self_state.get((i,j), 0)
            # Reglas:
            if s == 1:
                # vivo: sobrevive con 2 o 3 vecinos
                new_grid[i][j] = 1 if ncount in (2,3) else 0
            else:
                # muerto: nace con exactamente 3 vecinos
                new_grid[i][j] = 1 if ncount == 3 else 0

    # Imprimir misma cabecera y filas
    print(f"{width} {height}")
    for i in range(height):
        print(" ".join(str(x) for x in new_grid[i]))


if __name__ == "__main__":
    reducer()
