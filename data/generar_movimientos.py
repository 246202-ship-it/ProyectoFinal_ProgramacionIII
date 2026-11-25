"""Genera data/movimientos_cuentas.csv: movimientos entre cuentas con ruido normal y 4 patrones sospechosos plantados.

Uso:  python data/generar_movimientos.py     (semilla fija: el resultado siempre es el mismo)
"""
import csv
import os
import random

azar = random.Random(2026)
filas = []


def op(origen, destino, monto, dia):
    filas.append({"id": f"T{len(filas) + 1:04d}", "origen": origen, "destino": destino,
                  "monto": round(monto, 2), "fecha": f"2026-10-{dia:02d}"})


# 1) Actividad normal: 40 cuentas, montos pequeños, cada par se repite poco
normales = [f"C{i:03d}" for i in range(1, 41)]
usados = {}
while len(filas) < 120:
    o, d = azar.sample(normales, 2)
    if usados.get((o, d), 0) >= 2:
        continue
    usados[(o, d)] = usados.get((o, d), 0) + 1
    op(o, d, azar.uniform(50, 700) if azar.random() < 0.9 else azar.uniform(1500, 8000), azar.randint(1, 28))

# 2) Circulación reiterada: el dinero da la vuelta R1 -> R2 -> R3 -> R4 -> R1 (dos vueltas)
for vuelta, dia in ((0, 3), (1, 10)):
    for i, (a, b) in enumerate((("R1", "R2"), ("R2", "R3"), ("R3", "R4"), ("R4", "R1"))):
        op(a, b, 9500 - 100 * i - 40 * vuelta, dia + i)

# 3) Fragmentación: 12 transferencias justo debajo del umbral de 1000
for i in range(12):
    op("F01", "F02", azar.uniform(800, 990), 1 + 2 * i)

# 4) Dispersión y concentración: O1 reparte entre 5 intermediarios que luego juntan todo en D1
for i in range(1, 6):
    op("O1", f"M{i}", 2000 + azar.uniform(-30, 30), 5)
    op(f"M{i}", "D1", 1950 + azar.uniform(-30, 30), 6)

# 5) Cadena de paso: S1 -> P1 -> P2 -> P3 -> T1 reenviando casi todo
monto = 15000
for i, (a, b) in enumerate((("S1", "P1"), ("P1", "P2"), ("P2", "P3"), ("P3", "T1"))):
    op(a, b, monto, 12 + i)
    monto -= 200

azar.shuffle(filas)
filas.sort(key=lambda f: f["fecha"])
for i, f in enumerate(filas, 1):
    f["id"] = f"T{i:04d}"

ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), "movimientos_cuentas.csv")
with open(ruta, "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["id", "origen", "destino", "monto", "fecha"])
    w.writeheader()
    w.writerows(filas)
print(f"{len(filas)} transacciones escritas en {ruta}")
