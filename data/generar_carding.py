"""Genera data/carding_nodos.csv y data/transacciones.csv: red simulada de carding.

Nodos: T### tarjetas, D### dispositivos, M### comercios, C### cuentas, B### billeteras.
Conexiones: uso (tarjeta -> dispositivo), pago (tarjeta -> comercio), liquidacion
(comercio -> cuenta) y transferencia (cuenta -> billetera).
Actividad normal (T001-T040) + 4 escenarios sospechosos plantados (códigos T9xx, M9xx, C9xx).
Uso:  python data/generar_carding.py     (semilla fija: siempre el mismo resultado)
"""
import csv
import os
import random
from datetime import datetime, timedelta

azar = random.Random(2026)
NOMBRES = {"T": "tarjeta", "D": "dispositivo", "M": "comercio", "C": "cuenta", "B": "billetera"}
nodos, filas, usos = set(), [], set()
base = datetime(2026, 10, 1, 8, 0)


def cod(letra, n):
    nodos.add(f"{letra}{n:03d}")
    return f"{letra}{n:03d}"


def fecha(dia, hora=None, minuto=None):
    f = base + timedelta(days=dia - 1, hours=azar.randint(0, 12) if hora is None else hora - 8,
                         minutes=azar.randint(0, 59) if minuto is None else minuto)
    return f.strftime("%Y-%m-%d %H:%M")


def conexion(o, d, tipo, monto="", f=""):
    filas.append({"origen": o, "destino": d, "tipo": tipo, "monto": monto, "fecha": f})


def uso(t, d, f):
    if (t, d) not in usos:
        usos.add((t, d))
        conexion(t, d, "uso", "", f)


def pago(t, d, m, monto, f):
    uso(t, d, f)
    conexion(t, m, "pago", round(monto, 2), f)
    totales[m] = totales.get(m, 0) + monto
    ultima[m] = f


totales, ultima = {}, {}

# --- Actividad normal: 40 tarjetas, casi cada una con su propio dispositivo (2 parejas comparten uno)
comercios = [cod("M", i) for i in range(1, 16)]
cuenta_de = {m: cod("C", i) for i, m in enumerate(comercios, 1)}
for i in range(1, 41):
    t = cod("T", i)
    dispositivos = [cod("D", i - 1 if i in (36, 38) else i)]      # T035-T036 y T037-T038 comparten dispositivo
    if i % 8 == 0:
        dispositivos.append(cod("D", 100 + i))          # tarjeta usada desde celular y computadora
    for dia in azar.sample(range(1, 29), azar.randint(2, 5)):
        pago(t, azar.choice(dispositivos), azar.choice(comercios),
             azar.uniform(20, 400) if azar.random() < 0.9 else azar.uniform(500, 900), fecha(dia))

# --- Escenario A: 5 tarjetas en un mismo dispositivo, pagos a 2 comercios nuevos que liquidan en la misma cuenta
d_a, c_a = cod("D", 900), cod("C", 900)
for i, t in enumerate([cod("T", 901 + k) for k in range(5)]):
    for m in (cod("M", 901), cod("M", 902)):
        pago(t, d_a, m, azar.uniform(300, 900), fecha(12, 10 + i, azar.randint(0, 59)))
for m in (cod("M", 901), cod("M", 902)):
    cuenta_de[m] = c_a

# --- Escenario B: una tarjeta usada desde 4 dispositivos distintos en 4 comercios distintos
t_b = cod("T", 910)
for k in range(4):
    m = cod("M", 903 + k)
    cuenta_de[m] = cod("C", 901 + k)
    pago(t_b, cod("D", 910 + k), m, azar.uniform(150, 600), fecha(15, 9 + k, azar.randint(0, 59)))

# --- Escenario C: ráfaga de pagos en pocos minutos (primero montos de prueba, luego montos altos)
t_c, d_c, m_c = cod("T", 920), cod("D", 920), cod("M", 907)
cuenta_de[m_c] = cod("C", 905)
for minuto, monto in enumerate([1.5, 2, 3, 5, 120, 450, 800, 950]):
    pago(t_c, d_c, m_c, monto, fecha(18, 14, minuto))

# --- Escenario D: una cuenta recibe de 6 comercios, con 12 tarjetas distintas, y manda todo a una billetera
c_d, b_d = cod("C", 930), cod("B", 930)
for k in range(6):
    m = cod("M", 930 + k)
    cuenta_de[m] = c_d
    for j in range(2):
        t = cod("T", 930 + 2 * k + j)
        pago(t, cod("D", 930 + 2 * k + j), m, azar.uniform(200, 700), fecha(20 + k, 11 + j, azar.randint(0, 59)))

# --- Liquidación de cada comercio a su cuenta y transferencias de las cuentas a billeteras
for m, c in cuenta_de.items():
    if m in totales:
        nodos.add(c)
        conexion(m, c, "liquidacion", round(totales[m], 2), ultima[m])
conexion("C001", cod("B", 1), "transferencia", 1200, "2026-10-28 10:00")
conexion("C005", cod("B", 2), "transferencia", 900, "2026-10-29 11:30")
conexion(c_d, b_d, "transferencia", round(sum(totales[cod("M", 930 + k)] for k in range(6)) * 0.97, 2), "2026-10-27 23:40")
conexion(c_a, cod("B", 900), "transferencia", round((totales[cod("M", 901)] + totales[cod("M", 902)]) * 0.95, 2), "2026-10-14 02:10")

filas.sort(key=lambda f: f["fecha"])
for i, f in enumerate(filas, 1):
    f["id"] = f"X{i:04d}"

usados = {f[k] for f in filas for k in ("origen", "destino")}
nodos &= usados          # sin nodos sueltos

carpeta = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(carpeta, "carding_nodos.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.writer(f)
    w.writerow(["id", "tipo"])
    for n in sorted(nodos):
        w.writerow([n, NOMBRES[n[0]]])
with open(os.path.join(carpeta, "transacciones.csv"), "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["id", "origen", "destino", "tipo", "monto", "fecha"])
    w.writeheader()
    w.writerows(filas)
print(f"{len(nodos)} nodos y {len(filas)} conexiones escritos en {carpeta}")
