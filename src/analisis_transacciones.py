"""Módulo 2: análisis de transacciones y detección de operaciones sospechosas.

Red: grafo dirigido y multi (una arista por transferencia, con atributo "monto").
Un patrón detectado es un indicador para revisión, NO una prueba de fraude.

Algoritmos elegidos (V cuentas, E transferencias):
- BFS (proximidad y rastreo de fondos): O(V + E). Da el mínimo de saltos; DFS no.
- Tarjan (componentes fuertemente conexas): O(V + E). Encuentra grupos donde el dinero
  circula; es lineal, mientras enumerar todos los ciclos es exponencial.
- DFS con límite de largo (ciclos concretos, solo dentro de cada componente): exponencial
  en el peor caso, por eso se acota con max_largo y max_ciclos.
- Agrupación por pares (fragmentación) y conteo de vecinos (dispersión/concentración,
  cuentas puente): O(E) y O(sum de grado^2).
"""
from collections import deque


def pares(g):
    """Resume las transferencias por par: {(origen, destino): {"n", "total", "montos"}}. O(E)."""
    r = {}
    for a in g.aristas():
        p = r.setdefault((a.origen, a.destino), {"n": 0, "total": 0.0, "montos": []})
        m = a.atributos.get("monto", 0.0)
        p["n"] += 1
        p["total"] += m
        p["montos"].append(m)
    return r


def _salidas(g, monto_min=0):
    """Cuentas a las que envía cada cuenta, contando solo pares con total >= monto_min."""
    sal = {n: set() for n in g.nodos}
    for (o, d), q in pares(g).items():
        if q["total"] >= monto_min:
            sal[o].add(d)
    return sal


# ---------------------------------------------------------- relaciones y rastreo
def relaciones_directas(g, cuenta):
    """A quién envía y de quién recibe una cuenta, con el monto total. O(E)."""
    g.obtener_nodo(cuenta)
    envia, recibe = {}, {}
    for (o, d), p in pares(g).items():
        if o == cuenta:
            envia[d] = p["total"]
        if d == cuenta:
            recibe[o] = p["total"]
    return {"envia_a": envia, "recibe_de": recibe}


def proximidad(g, origen, max_nivel=3):
    """Nivel de cercanía (saltos, ignorando la dirección) de cada cuenta respecto a origen.
    BFS: O(V + E)."""
    g.obtener_nodo(origen)
    vecinos = {n: set() for n in g.nodos}
    for (o, d) in pares(g):
        vecinos[o].add(d)
        vecinos[d].add(o)
    nivel, cola = {origen: 0}, deque([origen])
    while cola:
        u = cola.popleft()
        if nivel[u] == max_nivel:
            continue
        for v in vecinos[u]:
            if v not in nivel:
                nivel[v] = nivel[u] + 1
                cola.append(v)
    return nivel


def rastrear_fondos(g, origen, max_saltos=6):
    """Sigue el dinero que sale de origen. Devuelve {"caminos": {cuenta: [camino más corto]},
    "intermediarios": [...], "receptoras_finales": [...]}. BFS: O(V + E)."""
    g.obtener_nodo(origen)
    sal = _salidas(g)
    padre, saltos, cola = {origen: None}, {origen: 0}, deque([origen])
    while cola:
        u = cola.popleft()
        if saltos[u] == max_saltos:
            continue
        for v in sorted(sal[u]):
            if v not in padre:
                padre[v], saltos[v] = u, saltos[u] + 1
                cola.append(v)
    caminos = {}
    for n in padre:
        if n == origen:
            continue
        ruta, x = [], n
        while x is not None:
            ruta.append(x)
            x = padre[x]
        caminos[n] = ruta[::-1]
    return {"caminos": caminos,
            "intermediarios": sorted(n for n in caminos if sal[n]),
            "receptoras_finales": sorted(n for n in caminos if not sal[n])}


# ------------------------------------------------------------------- patrones
def componentes_fuertes(g, monto_min=0):
    """Grupos de cuentas donde el dinero puede volver a su punto de partida (tamaño >= 2).
    Solo cuentan los pares con total >= monto_min (con montos chicos casi toda red tiene
    circulación normal). Tarjan iterativo (sin recursión): O(V + E)."""
    sal = {n: sorted(v) for n, v in _salidas(g, monto_min).items()}
    indice, bajo, en_pila, pila, comps = {}, {}, set(), [], []
    for raiz in g.nodos:
        if raiz in indice:
            continue
        indice[raiz] = bajo[raiz] = len(indice)
        pila.append(raiz)
        en_pila.add(raiz)
        trabajo = [(raiz, iter(sal[raiz]))]
        while trabajo:
            u, it = trabajo[-1]
            for v in it:
                if v not in indice:
                    indice[v] = bajo[v] = len(indice)
                    pila.append(v)
                    en_pila.add(v)
                    trabajo.append((v, iter(sal[v])))
                    break
                if v in en_pila:
                    bajo[u] = min(bajo[u], indice[v])
            else:
                trabajo.pop()
                if trabajo:
                    padre = trabajo[-1][0]
                    bajo[padre] = min(bajo[padre], bajo[u])
                if bajo[u] == indice[u]:
                    comp = []
                    while True:
                        w = pila.pop()
                        en_pila.discard(w)
                        comp.append(w)
                        if w == u:
                            break
                    if len(comp) > 1:
                        comps.append(sorted(comp))
    return comps


def ciclos(g, max_largo=6, max_ciclos=200, monto_min=5000, similitud=0.8):
    """Ciclos de transferencias (A -> B -> ... -> A) donde el dinero vuelve casi intacto: cada
    tramo mueve al menos monto_min y el tramo menor es >= similitud * el mayor. Se busca solo
    dentro de cada componente fuerte; cada ciclo se reporta una vez (empieza en su cuenta de
    menor orden). Devuelve [{"cuentas": [...], "monto_min": float}]. Exponencial en el peor
    caso, por eso se acota con max_largo y max_ciclos."""
    p = pares(g)
    sal = {n: sorted(v) for n, v in _salidas(g, monto_min).items()}
    orden = {n: i for i, n in enumerate(g.nodos)}
    res = []
    for comp in componentes_fuertes(g, monto_min):
        miembros = set(comp)
        for inicio in sorted(comp, key=orden.get):
            camino, visto = [inicio], {inicio}

            def dfs(u):
                for v in sal[u]:
                    if len(res) >= max_ciclos:
                        return
                    if v not in miembros or orden[v] < orden[inicio]:
                        continue
                    if v == inicio:
                        if len(camino) >= 2:
                            ruta = camino + [inicio]
                            tramos = [p[(a, b)]["total"] for a, b in zip(ruta, ruta[1:])]
                            if min(tramos) >= similitud * max(tramos):
                                res.append({"cuentas": list(camino), "monto_min": min(tramos)})
                    elif v not in visto and len(camino) < max_largo:
                        visto.add(v)
                        camino.append(v)
                        dfs(v)
                        camino.pop()
                        visto.remove(v)

            dfs(inicio)
    return res


def fragmentacion(g, umbral=1000, min_ops=3):
    """Pares con varias transferencias, todas bajo el umbral, que juntas lo superan. O(E)."""
    return [{"origen": o, "destino": d, "operaciones": q["n"], "total": q["total"]}
            for (o, d), q in pares(g).items()
            if q["n"] >= min_ops and max(q["montos"]) < umbral and q["total"] >= umbral]


def dispersion_concentracion(g, min_intermediarios=3, tolerancia=0.2):
    """Una cuenta reparte entre varios intermediarios que reenvían casi todo (±tolerancia) a una
    misma cuenta (origen -> varios -> destino). Cuenta los caminos de 2 saltos. O(sum de grado^2)."""
    p, sal = pares(g), _salidas(g)
    hallazgos = []
    for s in g.nodos:
        por_destino = {}
        for m in sal[s]:
            for d in sal[m]:
                if d != s and d != m and abs(p[(m, d)]["total"] / p[(s, m)]["total"] - 1) <= tolerancia:
                    por_destino.setdefault(d, []).append(m)
        for d, ms in por_destino.items():
            if len(ms) >= min_intermediarios:
                hallazgos.append({"origen": s, "destino": d, "intermediarios": sorted(ms),
                                  "total_enviado": sum(p[(s, m)]["total"] for m in ms),
                                  "total_recibido": sum(p[(m, d)]["total"] for m in ms)})
    return hallazgos


def cadenas_de_paso(g, ratio_min=0.9, ratio_max=1.1, min_puentes=2, monto_min=5000):
    """Cadenas S -> P1 -> P2 ... -> T donde cada cuenta intermedia reenvía casi todo lo que
    recibe (cuenta puente: salida/entrada entre ratio_min y ratio_max). Las cuentas que ya
    forman parte de un ciclo se reportan aparte. O(V + E)."""
    p, sal = pares(g), _salidas(g)
    entra, sale, pred = {}, {}, {n: [] for n in g.nodos}
    for (o, d), q in p.items():
        sale[o] = sale.get(o, 0) + q["total"]
        entra[d] = entra.get(d, 0) + q["total"]
        pred[d].append(o)
    en_ciclo = {n for c in componentes_fuertes(g, monto_min) for n in c}
    puentes = {n for n in g.nodos if n not in en_ciclo and entra.get(n, 0) > 0 and sale.get(n, 0) > 0
               and ratio_min <= sale[n] / entra[n] <= ratio_max}
    cadenas = []
    for n in sorted(puentes):
        if any(u in puentes for u in pred[n]):
            continue                                  # no es el primer puente de la cadena
        ruta = [max(pred[n], key=lambda u: p[(u, n)]["total"]), n]
        while ruta[-1] in puentes and len(ruta) <= g.n_nodos:
            siguientes = sorted(sal[ruta[-1]], key=lambda v: -p[(ruta[-1], v)]["total"])
            ruta.append(siguientes[0])
        if len(ruta) - 2 >= min_puentes:
            cadenas.append({"cuentas": ruta, "monto_inicial": p[(ruta[0], ruta[1])]["total"],
                            "monto_final": p[(ruta[-2], ruta[-1])]["total"]})
    return cadenas


# --------------------------------------------------------------------- reporte
def analizar(g, umbral=1000, min_ops=3, max_largo=6, min_intermediarios=3, monto_min=5000):
    """Ejecuta todas las detecciones. Devuelve [{"tipo", "cuentas", "detalle"}]."""
    h = []
    for c in componentes_fuertes(g, monto_min):
        h.append({"tipo": "Grupo con circulación de fondos", "cuentas": c,
                  "detalle": f"{len(c)} cuentas donde el dinero grande puede volver a su origen"})
    for c in ciclos(g, max_largo, monto_min=monto_min):
        h.append({"tipo": "Ciclo de transferencias", "cuentas": c["cuentas"] + [c["cuentas"][0]],
                  "detalle": f"el tramo menor del ciclo mueve {c['monto_min']:,.2f}"})
    for f in fragmentacion(g, umbral, min_ops):
        h.append({"tipo": "Operaciones fragmentadas", "cuentas": [f["origen"], f["destino"]],
                  "detalle": f"{f['operaciones']} transferencias bajo {umbral:,} que suman {f['total']:,.2f}"})
    for d in dispersion_concentracion(g, min_intermediarios):
        h.append({"tipo": "Dispersión y concentración", "cuentas": [d["origen"], *d["intermediarios"], d["destino"]],
                  "detalle": f"{len(d['intermediarios'])} intermediarios: salen {d['total_enviado']:,.2f}, "
                             f"llegan {d['total_recibido']:,.2f}"})
    for c in cadenas_de_paso(g, monto_min=monto_min):
        h.append({"tipo": "Cadena de transferencias sucesivas", "cuentas": c["cuentas"],
                  "detalle": f"de {c['monto_inicial']:,.2f} a {c['monto_final']:,.2f} pasando por "
                             f"{len(c['cuentas']) - 2} cuentas puente"})
    return h


def reporte(hallazgos):
    """Texto del reporte de relaciones sospechosas."""
    lineas = ["REPORTE DE OPERACIONES A REVISAR",
              "Los patrones son indicadores para auditoría; no prueban fraude ni lavado de activos.", ""]
    if not hallazgos:
        return "\n".join(lineas + ["No se encontraron patrones."])
    for i, x in enumerate(hallazgos, 1):
        lineas.append(f"{i}. {x['tipo']}: {' -> '.join(x['cuentas'])}\n   {x['detalle']}")
    return "\n".join(lineas)
