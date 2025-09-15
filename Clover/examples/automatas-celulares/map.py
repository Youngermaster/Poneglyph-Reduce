#!/usr/bin/env python3
"""
Mapper para Game of Life (MapReduce-style).
Lee la grilla desde stdin (formato descrito arriba).
Emite por cada celda:
 - Una línea META\theight\twidth (una vez)
 - Para cada celda (i,j): "i,j\tSELF\t0/1"
 - Para cada vecino de una celda viva: "ni,nj\tNEIGH\t1"
Salida por stdout, línea única por emisión (tab-separated).
"""
import sys

def mapper():
    first = True
    grid = []
    width = height = 0

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        if first:
            parts = line.split()
            if len(parts) >= 2:
                width, height = int(parts[0]), int(parts[1])
                first = False
                continue
            else:
                # si primer línea no válida, salir
                return
        row = [int(x) for x in line.split()]
        grid.append(row)

    # output META
    print(f"META\t{width}\t{height}")

    # offsets de vecinos (8 vecinos)
    neigh_offsets = [(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]

    for i in range(len(grid)):
        row = grid[i]
        for j in range(len(row)):
            state = row[j]
            # Emitir SELF para indicar el estado actual (útil para reducers)
            print(f"{i},{j}\tSELF\t{state}")

            # si está viva, emitir incrementos a sus vecinos
            if state == 1:
                for di, dj in neigh_offsets:
                    ni, nj = i + di, j + dj
                    # mantener dentro de la grilla (no wrapping)
                    if 0 <= ni < height and 0 <= nj < width:
                        print(f"{ni},{nj}\tNEIGH\t1")

if __name__ == "__main__":
    mapper()
