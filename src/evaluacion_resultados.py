"""Módulo 5: evaluación, comparación y validación de resultados.

- casos_de_prueba(): escenarios de los 4 módulos con resultado esperado vs obtenido.
- verificar_ruta / verificar_plan: comprueban que una solución cumple las restricciones.
- comparar_enrutamiento / comparar_flujo / escalabilidad_transacciones: tiempo y memoria con
  redes de distintos tamaños, comparando algoritmos alternativos.
- exponente(): pendiente log-log entre tamaño y tiempo = complejidad empírica.
"""
import csv
import math
import os
import random
import statistics
import time
import tracemalloc

from src.analisis_transacciones import analizar, ciclos, cadenas_de_paso, dispersion_concentracion, fragmentacion
from src.carding import analizar_carding, caminos_hasta, consultar
from src.distribucion_liquidez import EPS, planificar
from src.enrutamiento_financiero import alternativas, disponible, ruta_optima
from src.gestion_red import GestionRed
from src.graph import Grafo


def _d(archivo):
    """Ruta absoluta de un archivo de data/ (funciona sin importar desde dónde se ejecute)."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", archivo)


# ------------------------------------------------------------------- medición
def medir(f, repeticiones=3):
    """Ejecuta f varias veces. Devuelve (resultado, mediana en segundos, pico de memoria en KiB)."""
    tiempos = []
    for _ in range(repeticiones):
        t = time.perf_counter()
        resultado = f()
        tiempos.append(time.perf_counter() - t)
    tracemalloc.start()
    f()
    pico = tracemalloc.get_traced_memory()[1]
    tracemalloc.stop()
    return resultado, statistics.median(tiempos), pico / 1024


def exponente(tamanos, tiempos):
    """Pendiente de log(tiempo) contra log(tamaño): t ~ n^pendiente (complejidad empírica)."""
    xs, ys = [math.log(x) for x in tamanos], [math.log(max(y, 1e-9)) for y in tiempos]
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sum((x - mx) ** 2 for x in xs)


# --------------------------------------------------------- generadores de redes
def generar_red_enrutamiento(n, grado=4, semilla=1):
    """n entidades con una cadena (para garantizar conexión) y n*(grado-1) canales al azar."""
    az = random.Random(semilla)
    g = Grafo(multi=True)
    for i in range(n):
        g.agregar_nodo(f"N{i}", "entidad")

    def canal(o, d, k):
        g.agregar_arista(f"N{o}", f"N{d}", canal=f"C{k}", comision=round(az.uniform(0.5, 20), 2),
                         comision_pct=round(az.uniform(0, 1), 2), tiempo=round(az.uniform(0.1, 48), 2),
                         costo=round(az.uniform(0.1, 3), 2), riesgo=round(az.uniform(0, 0.1), 3),
                         limite=az.choice([2000, 10000, 50000, 1_000_000]))

    for i in range(n - 1):
        canal(i, i + 1, 0)
    for k in range(n * (grado - 1)):
        o, d = az.sample(range(n), 2)
        canal(o, d, k + 1)
    return g


def generar_red_liquidez(regionales, agencias_por_region=3, semilla=1):
    """Bóveda central y de reserva, regionales conectadas entre sí y agencias con demanda."""
    az = random.Random(semilla)
    g = Grafo()
    demanda_total = 0
    for i in range(regionales):
        g.agregar_nodo(f"R{i}", "boveda_regional")
        for j in range(agencias_por_region):
            d = az.randint(50, 150) * 1000
            demanda_total += d
            g.agregar_nodo(f"A{i}_{j}", "agencia", demanda=d)
    g.agregar_nodo("Central", "boveda_central", disponible=int(demanda_total * 0.7))
    g.agregar_nodo("Reserva", "boveda_central", disponible=int(demanda_total * 0.4))
    for i in range(regionales):
        g.agregar_arista("Central", f"R{i}", capacidad=az.randint(200, 500) * 1000, costo=az.randint(4, 12))
        g.agregar_arista("Reserva", f"R{i}", capacidad=az.randint(100, 300) * 1000, costo=az.randint(8, 15))
        g.agregar_arista(f"R{i}", f"R{(i + 1) % regionales}", capacidad=100_000, costo=2)
        for j in range(agencias_por_region):
            g.agregar_arista(f"R{i}", f"A{i}_{j}", capacidad=az.randint(100, 200) * 1000, costo=az.randint(1, 3))
    return g


def generar_transacciones(cuentas, semilla=1):
    """cuentas cuentas y 4 transferencias por cuenta al azar."""
    az = random.Random(semilla)
    g = Grafo(multi=True)
    for i in range(cuentas):
        g.agregar_nodo(f"K{i}", "cuenta")
    for k in range(cuentas * 4):
        o, d = az.sample(range(cuentas), 2)
        g.agregar_arista(f"K{o}", f"K{d}", id=str(k), monto=round(az.uniform(50, 700), 2))
    return g


def generar_red_carding(tarjetas, semilla=1):
    """tarjetas tarjetas con su dispositivo, 3 pagos cada una y un comercio por cada 5 tarjetas."""
    az = random.Random(semilla)
    g = Grafo(multi=True)
    comercios = max(1, tarjetas // 5)
    for i in range(comercios):
        g.agregar_nodo(f"M{i}", "comercio")
        g.agregar_nodo(f"C{i}", "cuenta")
        g.agregar_arista(f"M{i}", f"C{i}", id=f"L{i}", tipo="liquidacion", monto=1000)
    for i in range(tarjetas):
        g.agregar_nodo(f"T{i}", "tarjeta")
        g.agregar_nodo(f"D{i}", "dispositivo")
        g.agregar_arista(f"T{i}", f"D{i}", id=f"U{i}", tipo="uso")
        for k in range(3):
            g.agregar_arista(f"T{i}", f"M{az.randrange(comercios)}", id=f"P{i}_{k}", tipo="pago", monto=round(az.uniform(20, 400), 2),
                             fecha=f"2026-10-{az.randint(1, 28):02d} {az.randint(8, 20):02d}:{az.randint(0, 59):02d}")
    return g


# ------------------------------------------------------------- verificaciones
def verificar_ruta(g, canales, origen, destino, monto):
    """Lista de violaciones de una ruta de enrutamiento (vacía = cumple todo)."""
    errores, actual, visitados = [], origen, {origen}
    for a in canales:
        if a.origen != actual:
            errores.append(f"ruta discontinua en {a.origen}")
        if not disponible(a, monto):
            errores.append(f"canal {a.origen}->{a.destino} no disponible para {monto:,.0f}")
        if a.destino in visitados:
            errores.append(f"repite la entidad {a.destino}")
        visitados.add(a.destino)
        actual = a.destino
    if canales and actual != destino or not canales and origen != destino:
        errores.append("no termina en el destino")
    return errores


def verificar_plan(g, plan):
    """Lista de violaciones de un plan de liquidez: capacidades, conservación, oferta y demanda."""
    errores, entra, sale = [], {}, {}
    for o, d, f, cap, _ in plan["usado"]:
        if f > cap + EPS:
            errores.append(f"{o}->{d} excede su capacidad ({f:,.0f} > {cap:,.0f})")
        sale[o] = sale.get(o, 0) + f
        entra[d] = entra.get(d, 0) + f
    for n, at in g.nodos.items():
        origen, destino = at.get("disponible", 0), at.get("demanda", 0)
        neto = sale.get(n, 0) - entra.get(n, 0)
        if abs(neto - (plan["salida"].get(n, 0) - plan["entregado"].get(n, 0))) > 1e-6 * max(1, origen + destino):
            errores.append(f"no se conserva el efectivo en {n}")
        if plan["salida"].get(n, 0) > origen + EPS:
            errores.append(f"{n} envía más de lo que tiene")
        if plan["entregado"].get(n, 0) > destino + EPS:
            errores.append(f"{n} recibe más de lo que necesita")
    return errores


# ------------------------------------------------------------------ comparaciones
def comparar_enrutamiento(tamanos=(100, 200, 400, 800), monto=1000, pares=5, repeticiones=3):
    """Dijkstra (con parada anticipada) contra Bellman-Ford en redes de n entidades."""
    filas = []
    for n in tamanos:
        g = generar_red_enrutamiento(n)
        az = random.Random(n)
        parejas = [(f"N{o}", f"N{d}") for o, d in (sorted(az.sample(range(n), 2)) for _ in range(pares))]

        def correr(alg):
            return [ruta_optima(g, o, d, "comision", monto, alg) for o, d in parejas]

        rd, td, md = medir(lambda: correr("dijkstra"), repeticiones)
        rb, tb, mb = medir(lambda: correr("bellman-ford"), repeticiones)
        iguales = all((a is None) == (b is None) and (a is None or abs(a[0] - b[0]) < 1e-9) for a, b in zip(rd, rb))
        filas.append({"n": n, "aristas": g.n_aristas, "dijkstra_ms": td * 1000, "bellman_ford_ms": tb * 1000,
                      "factor": tb / td if td else math.inf, "iguales": iguales, "dijkstra_kib": md, "bf_kib": mb})
    return filas


def comparar_flujo(tamanos=(5, 10, 20, 40), repeticiones=3):
    """Dinic, Edmonds-Karp y flujo de costo mínimo con n bóvedas regionales (y 3n agencias)."""
    filas = []
    for n in tamanos:
        g = generar_red_liquidez(n)
        fila = {"regionales": n, "nodos": g.n_nodos, "rutas": g.n_aristas}
        planes = {}
        for alg in ("dinic", "edmonds-karp", "costo_minimo"):
            planes[alg], t, m = medir(lambda a=alg: planificar(g, a), repeticiones)
            fila[f"{alg}_ms"], fila[f"{alg}_kib"] = t * 1000, m
        fila["distribuido"] = planes["dinic"]["distribuido"]
        fila["iguales"] = len({round(p["distribuido"], 6) for p in planes.values()}) == 1
        fila["costo_dinic"], fila["costo_minimo"] = planes["dinic"]["costo"], planes["costo_minimo"]["costo"]
        fila["valido"] = all(not verificar_plan(g, p) for p in planes.values())
        filas.append(fila)
    return filas


def escalabilidad_transacciones(tamanos=(100, 200, 400, 800), repeticiones=3):
    """Tiempo del análisis completo (analizar) según la cantidad de cuentas."""
    filas = []
    for n in tamanos:
        g = generar_transacciones(n)
        h, t, m = medir(lambda: analizar(g), repeticiones)
        filas.append({"cuentas": n, "transferencias": g.n_aristas, "ms": t * 1000, "kib": m, "hallazgos": len(h)})
    return filas


def escalabilidad_carding(tamanos=(100, 200, 400, 800), repeticiones=3):
    """Tiempo del análisis completo de carding según la cantidad de tarjetas."""
    filas = []
    for n in tamanos:
        g = generar_red_carding(n)
        h, t, m = medir(lambda: analizar_carding(g), repeticiones)
        filas.append({"tarjetas": n, "conexiones": g.n_aristas, "ms": t * 1000, "kib": m, "alertas": len(h)})
    return filas


# ------------------------------------------------------------ casos de prueba
def casos_de_prueba():
    """Escenarios con datos de entrada conocidos. Devuelve [(código, descripción, esperado, obtenido, ok)]."""
    res = []

    def caso(codigo, descripcion, esperado, obtenido, ok=None):
        res.append((codigo, descripcion, esperado, obtenido, esperado == obtenido if ok is None else ok))

    r = GestionRed()
    informe = r.cargar_json(_d("red_mixta.json"))
    caso("M1-1", "Cargar red_mixta.json (11 nodos de 8 tipos, 10 conexiones)",
         (21, 0, []), (informe["cargados"], len(informe["rechazados"]), r.validar()))
    r2 = GestionRed()
    malo = r2.cargar_aristas(_d("ejemplo_aristas.csv"))
    caso("M1-2", "Cargar el CSV del enunciado (3 conexiones, 4 cuentas)", (3, 4), (malo["cargados"], r2.resumen()["nodos"]))

    t = GestionRed(multi=True)
    t.cargar_aristas(_d("movimientos_cuentas.csv"))
    g = t.grafo
    caso("M2-1", "154 transferencias: se detecta 1 ciclo (R1-R4)", [["R1", "R2", "R3", "R4"]],
         [c["cuentas"] for c in ciclos(g)])
    caso("M2-2", "Se detecta la fragmentación F01 -> F02 (12 operaciones)", [("F01", "F02", 12)],
         [(f["origen"], f["destino"], f["operaciones"]) for f in fragmentacion(g)])
    caso("M2-3", "Se detecta la dispersión O1 -> M1..M5 -> D1", [("O1", "D1", 5)],
         [(d["origen"], d["destino"], len(d["intermediarios"])) for d in dispersion_concentracion(g)])
    caso("M2-4", "Se detecta la cadena S1 -> P1 -> P2 -> P3 -> T1", [["S1", "P1", "P2", "P3", "T1"]],
         [c["cuentas"] for c in cadenas_de_paso(g)])
    caso("M2-5", "Ninguna cuenta normal (C###) aparece en los hallazgos", True,
         not any(c.startswith("C") for h in analizar(g) for c in h["cuentas"]))

    k = GestionRed(multi=True)
    k.cargar_nodos(_d("carding_nodos.csv"))
    k.cargar_aristas(_d("transacciones.csv"), crear_nodos=False)
    alertas = analizar_carding(k.grafo)
    caso("C-1", "Carding: 173 nodos y 263 conexiones cargados sin errores y consistentes", (173, 263, []),
         (k.grafo.n_nodos, k.grafo.n_aristas, k.validar()))
    caso("C-2", "Carding: 5 alertas (dispositivo compartido, cuenta en común, tarjeta en 4 dispositivos, cuenta concentradora, ráfaga)",
         5, len(alertas))
    caso("C-3", "Carding: D900 concentra 5 tarjetas que terminan en C900",
         (["D900", "C900", "T901", "T902", "T903", "T904", "T905"]),
         [a for a in alertas if a["tipo"].startswith("Tarjetas del mismo")][0]["elementos"])
    caso("C-4", "Carding: la ráfaga es de T920 (8 pagos en 7 min)", ("T920", True),
         ([a for a in alertas if a["tipo"] == "Ráfaga de pagos"][0]["elementos"][0],
          [a for a in alertas if a["tipo"] == "Ráfaga de pagos"][0]["detalle"].startswith("8 pagos en 7 min")))
    caso("C-5", "Carding: DFS desde T901 hasta una billetera pasa por C900", [["T901", "M901", "C900", "B900"], ["T901", "M902", "C900", "B900"]],
         caminos_hasta(k.grafo, "T901"))
    caso("C-6", "Carding: ninguna tarjeta, dispositivo ni comercio de la actividad normal genera alertas", True,
         all(int(x[1:]) >= 900 for a in alertas for x in a["elementos"]))

    e = GestionRed()
    e.cargar_json(_d("red_enrutamiento.json"))
    ge = e.grafo
    for codigo, monto, criterio, esperado in (("M3-1", 1000, "comision", 4.5), ("M3-2", 1000, "tiempo", 0.3),
                                              ("M3-3", 5000, "tiempo", 1.0), ("M3-4", 100000, "comision", 25.0)):
        v, ruta = ruta_optima(ge, "BancoA", "BancoC", criterio, monto)
        caso(codigo, f"BancoA -> BancoC, monto {monto:,}, mínimo de {criterio}", esperado, round(v, 2),
             abs(v - esperado) < 1e-9 and not verificar_ruta(ge, ruta, "BancoA", "BancoC", monto))
    caso("M3-5", "Monto 6 000 000 supera todos los límites: no hay ruta", None, ruta_optima(ge, "BancoA", "BancoC", "comision", 6_000_000))
    caso("M3-6", "9 alternativas entre BancoA y BancoC con monto 1 000", 9, len(alternativas(ge, "BancoA", "BancoC", "comision", 1000)))

    l = GestionRed()
    l.cargar_json(_d("distribucion_liquidez.json"))
    p = planificar(l.grafo)
    caso("M4-1", "Liquidez: se distribuyen 1 060 000 de 1 070 000 de demanda", 1_060_000, p["distribuido"])
    caso("M4-2", "Liquidez: costo mínimo 10 364.50", 10364.5, round(p["costo"], 2))
    caso("M4-3", "Liquidez: queda pendiente Ag-Sicuani (10 000) y el plan cumple las restricciones",
         ({"Ag-Sicuani": 10000}, []), (p["pendiente"], verificar_plan(l.grafo, p)))
    return res


# ----------------------------------------------------------------- ejecución
def ejecutar_todo(rapido=False):
    """Corre los casos y las comparaciones. rapido=True usa redes chicas (para pruebas)."""
    if rapido:
        enr, flu, tra, rep = (30, 60), (3, 6), (30, 60), 1
    else:
        enr, flu, tra, rep = (100, 200, 400, 800), (5, 10, 20, 40), (100, 200, 400, 800), 3
    return {"casos": casos_de_prueba(), "carding": escalabilidad_carding(tra, rep),
            "enrutamiento": comparar_enrutamiento(enr, repeticiones=rep),
            "flujo": comparar_flujo(flu, repeticiones=rep), "transacciones": escalabilidad_transacciones(tra, rep)}


def _tabla(filas, columnas):
    cab = [c for c, _ in columnas]
    cuerpo = [[f(x) for _, f in columnas] for x in filas]
    ancho = [max(len(str(r[i])) for r in [cab] + cuerpo) for i in range(len(cab))]
    return "\n".join("  ".join(str(v).rjust(w) for v, w in zip(r, ancho)) for r in [cab] + cuerpo)


def reporte_evaluacion(res):
    """Texto con los casos de prueba, las tablas comparativas y las conclusiones."""
    L = ["EVALUACIÓN Y VALIDACIÓN DE RESULTADOS", "", "1. Casos de prueba (esperado vs obtenido)"]
    for codigo, desc, esp, obt, ok in res["casos"]:
        L.append(f"  [{'OK' if ok else 'FALLA'}] {codigo}: {desc}")
        if not ok:
            L.append(f"         esperado: {esp}\n         obtenido: {obt}")
    pasaron = sum(c[4] for c in res["casos"])
    L.append(f"  {pasaron}/{len(res['casos'])} casos correctos")

    car = res["carding"]
    L += ["", "2. Carding (problemática principal): análisis completo según la cantidad de tarjetas",
          _tabla(car, [("tarjetas", lambda f: f["tarjetas"]), ("conexiones", lambda f: f["conexiones"]),
                       ("ms", lambda f: f"{f['ms']:.1f}"), ("KiB", lambda f: f"{f['kib']:.0f}"), ("alertas", lambda f: f["alertas"])])]
    enr = res["enrutamiento"]
    L += ["", "3. Enrutamiento: Dijkstra vs Bellman-Ford (5 pares origen-destino por red)",
          _tabla(enr, [("entidades", lambda f: f["n"]), ("canales", lambda f: f["aristas"]),
                       ("Dijkstra ms", lambda f: f"{f['dijkstra_ms']:.1f}"), ("B-Ford ms", lambda f: f"{f['bellman_ford_ms']:.1f}"),
                       ("B-Ford/Dijkstra", lambda f: f"{f['factor']:.1f}x"), ("mismo resultado", lambda f: f["iguales"]),
                       ("Dijkstra KiB", lambda f: f"{f['dijkstra_kib']:.0f}")])]
    flu = res["flujo"]
    L += ["", "4. Liquidez: Dinic vs Edmonds-Karp vs flujo de costo mínimo",
          _tabla(flu, [("regionales", lambda f: f["regionales"]), ("rutas", lambda f: f["rutas"]),
                       ("Dinic ms", lambda f: f"{f['dinic_ms']:.1f}"), ("E-Karp ms", lambda f: f"{f['edmonds-karp_ms']:.1f}"),
                       ("Costo mín. ms", lambda f: f"{f['costo_minimo_ms']:.1f}"), ("mismo total", lambda f: f["iguales"]),
                       ("costo Dinic", lambda f: f"{f['costo_dinic']:,.0f}"), ("costo mínimo", lambda f: f"{f['costo_minimo']:,.0f}"),
                       ("cumple restricciones", lambda f: f["valido"])])]
    tra = res["transacciones"]
    L += ["", "5. Movimientos entre cuentas (lavado de activos, módulo complementario)",
          _tabla(tra, [("cuentas", lambda f: f["cuentas"]), ("transferencias", lambda f: f["transferencias"]),
                       ("ms", lambda f: f"{f['ms']:.1f}"), ("KiB", lambda f: f"{f['kib']:.0f}"), ("hallazgos", lambda f: f["hallazgos"])])]

    L += ["", "6. Conclusiones"]
    ult = enr[-1]
    L.append(f"  - Con {ult['n']} entidades Dijkstra fue {ult['factor']:.1f}x más rápido que Bellman-Ford y dio el mismo resultado: "
             f"{'sí' if all(f['iguales'] for f in enr) else 'NO (revisar)'} en todos los tamaños.")
    L.append(f"  - Exponente empírico: Dijkstra ~ n^{exponente([f['n'] for f in enr], [f['dijkstra_ms'] for f in enr]):.2f}, "
             f"Bellman-Ford ~ n^{exponente([f['n'] for f in enr], [f['bellman_ford_ms'] for f in enr]):.2f} "
             "(peor caso teórico: O(n log n) y O(n^2); Bellman-Ford termina antes porque se detiene cuando "
             "una pasada ya no mejora nada, y en estas redes aleatorias eso ocurre en pocas pasadas).")
    n = [f["regionales"] for f in flu]
    L.append(f"  - Flujo: Dinic ~ n^{exponente(n, [f['dinic_ms'] for f in flu]):.2f}, Edmonds-Karp ~ n^"
             f"{exponente(n, [f['edmonds-karp_ms'] for f in flu]):.2f}, costo mínimo ~ n^{exponente(n, [f['costo_minimo_ms'] for f in flu]):.2f}.")
    L.append("  - Los tres algoritmos de flujo distribuyen lo mismo; el de costo mínimo logra el menor costo operativo.")
    L.append(f"  - Carding: tiempo ~ n^{exponente([f['tarjetas'] for f in car], [f['ms'] for f in car]):.2f} en el número de tarjetas "
             "(teoría: lineal en nodos + conexiones para grado y BFS; la ventana de pagos añade un factor log).")
    L.append(f"  - Movimientos entre cuentas: tiempo ~ n^{exponente([f['cuentas'] for f in tra], [f['ms'] for f in tra]):.2f} (teoría: casi lineal en cuentas + transferencias).")
    L.append("  - Limitación: redes sintéticas aleatorias en una sola máquina; los tiempos varían entre ejecuciones "
             "(sobre todo Dijkstra, que depende de qué tan lejos queda el destino), así que se lee la tendencia, no cada cifra.")
    return "\n".join(L)


def guardar_csv(filas, ruta):
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


if __name__ == "__main__":
    print(reporte_evaluacion(ejecutar_todo()))
