#!/usr/bin/env python3
import sys
import os

# Leer datos agrupados desde archivo (sys.argv[1])
inp = sys.argv[1]

# Variables para cada dataset
ventas_sum_x = ventas_sum_y = ventas_sum_xy = ventas_sum_x2 = ventas_count = 0.0
temp_sum_x = temp_sum_y = temp_sum_xy = temp_sum_x2 = temp_count = 0.0
precio_sum_x = precio_sum_y = precio_sum_xy = precio_sum_x2 = precio_count = 0.0

# Forzar encoding ASCII y configurar stdout
os.environ['PYTHONIOENCODING'] = 'ascii'
sys.stdout.reconfigure(encoding='ascii', errors='ignore')

with open(inp, "r", encoding="ascii", errors="ignore") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue

        try:
            key, val = line.split("\t", 1)
            val = float(val)

            # Procesar ventas_publicidad
            if key == "ventas_publicidad_sum_x":
                ventas_sum_x += val
            elif key == "ventas_publicidad_sum_y":
                ventas_sum_y += val
            elif key == "ventas_publicidad_sum_xy":
                ventas_sum_xy += val
            elif key == "ventas_publicidad_sum_x2":
                ventas_sum_x2 += val
            elif key == "ventas_publicidad_count":
                ventas_count += val

            # Procesar temperatura_energia
            elif key == "temperatura_energia_sum_x":
                temp_sum_x += val
            elif key == "temperatura_energia_sum_y":
                temp_sum_y += val
            elif key == "temperatura_energia_sum_xy":
                temp_sum_xy += val
            elif key == "temperatura_energia_sum_x2":
                temp_sum_x2 += val
            elif key == "temperatura_energia_count":
                temp_count += val

            # Procesar precio_demanda
            elif key == "precio_demanda_sum_x":
                precio_sum_x += val
            elif key == "precio_demanda_sum_y":
                precio_sum_y += val
            elif key == "precio_demanda_sum_xy":
                precio_sum_xy += val
            elif key == "precio_demanda_sum_x2":
                precio_sum_x2 += val
            elif key == "precio_demanda_count":
                precio_count += val

        except ValueError:
            continue

# Calcular regresion para ventas_publicidad
if ventas_count > 1:
    n = int(ventas_count)
    denom = (n * ventas_sum_x2 - ventas_sum_x * ventas_sum_x)
    if abs(denom) > 1e-10:
        beta1 = (n * ventas_sum_xy - ventas_sum_x * ventas_sum_y) / denom
        beta0 = (ventas_sum_y - beta1 * ventas_sum_x) / n
        print("ventas_beta0\t" + str(round(beta0, 4)))
        print("ventas_beta1\t" + str(round(beta1, 4)))
        print("ventas_model\ty = " + str(round(beta0, 2)) + " + " + str(round(beta1, 2)) + "x")

# Calcular regresion para temperatura_energia
if temp_count > 1:
    n = int(temp_count)
    denom = (n * temp_sum_x2 - temp_sum_x * temp_sum_x)
    if abs(denom) > 1e-10:
        beta1 = (n * temp_sum_xy - temp_sum_x * temp_sum_y) / denom
        beta0 = (temp_sum_y - beta1 * temp_sum_x) / n
        print("temp_beta0\t" + str(round(beta0, 4)))
        print("temp_beta1\t" + str(round(beta1, 4)))
        print("temp_model\ty = " + str(round(beta0, 2)) + " + " + str(round(beta1, 2)) + "x")

# Calcular regresion para precio_demanda
if precio_count > 1:
    n = int(precio_count)
    denom = (n * precio_sum_x2 - precio_sum_x * precio_sum_x)
    if abs(denom) > 1e-10:
        beta1 = (n * precio_sum_xy - precio_sum_x * precio_sum_y) / denom
        beta0 = (precio_sum_y - beta1 * precio_sum_x) / n
        print("precio_beta0\t" + str(round(beta0, 4)))
        print("precio_beta1\t" + str(round(beta1, 4)))
        print("precio_model\ty = " + str(round(beta0, 2)) + " + " + str(round(beta1, 2)) + "x")

# Forzar flush de stdout
sys.stdout.flush()
