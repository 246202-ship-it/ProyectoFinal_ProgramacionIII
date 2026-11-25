"""Módulo 4: planificación y optimización de la distribución de liquidez hacia bóvedas.

Red dirigida: bóvedas (atributo "disponible" = efectivo que pueden enviar), agencias y puntos de
atención (atributo "demanda" = efectivo que necesitan) y rutas con "capacidad" (máximo por
período) y "costo" (costo operativo por cada 1 000 trasladados). Sin "capacidad" la ruta no
tiene límite.

Modelo: se agrega una fuente S (conectada a cada bóveda con su disponible) y un sumidero T
(conectado desde cada agencia con su demanda). Lo máximo que se puede distribuir es el flujo
máximo de S a T; entre todas las distribuciones máximas, la más barata es el flujo máximo de
costo mínimo.

Algoritmos (V nodos, E rutas):
- Dinic, O(V^2 E): flujo máximo; en la práctica el más rápido.
- Edmonds-Karp (BFS), O(V E^2): flujo máximo, más simple; se usa para comparar y validar.
- Flujo de costo mínimo por caminos de aumento con SPFA (Bellman-Ford con cola): aumenta
  siempre por el camino más barato del grafo residual; se necesita porque el residual tiene
  costos negativos (Dijkstra simple no sirve). Es la opción por defecto: cumple "optimizar
  según disponibilidad, demanda y costos".
- Corte mínimo (alcanzables en el residual): identifica los cuellos de botella.
"""
from collections import deque
import math

INF = math.inf
EPS = 1e-9


class _Red:
    """Red residual: arco i y su inverso i ^ 1. a[i] = [destino, capacidad_restante, costo]."""

    def __init__(self, n):
        self.ady = [[] for _ in range(n)]
        self.a = []

    def agregar(self, u, v, cap, costo=0.0):
        self.ady[u].append(len(self.a))
        self.a.append([v, cap, costo])
        self.ady[v].append(len(self.a))
        self.a.append([u, 0.0, -costo])
        return len(self.a) - 2

    def flujo(self, i):
        return self.a[i ^ 1][1]


def _aumentar(R, camino, f):
    for i in camino:
        R.a[i][1] -= f
        R.a[i ^ 1][1] += f


def edmonds_karp(R, s, t):
    """Flujo máximo con caminos de aumento más cortos (BFS). O(V E^2)."""
    total = 0.0
    while True:
        previo, cola = {s: None}, deque([s])
        while cola and t not in previo:
            u = cola.popleft()
            for i in R.ady[u]:
                v, c, _ = R.a[i]
                if c > EPS and v not in previo:
                    previo[v] = i
                    cola.append(v)
        if t not in previo:
            return total
        camino, v = [], t
        while v != s:
            i = previo[v]
            camino.append(i)
            v = R.a[i ^ 1][0]
        f = min(R.a[i][1] for i in camino)
        _aumentar(R, camino, f)
        total += f


def dinic(R, s, t):
    """Flujo máximo con grafo de niveles y flujo bloqueante (iterativo). O(V^2 E)."""
    n, total = len(R.ady), 0.0
    while True:
        nivel = [-1] * n
        nivel[s] = 0
        cola = deque([s])
        while cola:
            u = cola.popleft()
            for i in R.ady[u]:
                v, c, _ = R.a[i]
                if c > EPS and nivel[v] < 0:
                    nivel[v] = nivel[u] + 1
                    cola.append(v)
        if nivel[t] < 0:
            return total
        puntero = [0] * n
        while True:
            camino, u = [], s
            while u != t:
                for k in range(puntero[u], len(R.ady[u])):
                    i = R.ady[u][k]
                    v, c, _ = R.a[i]
                    if c > EPS and nivel[v] == nivel[u] + 1:
                        puntero[u] = k
                        camino.append(i)
                        u = v
                        break
                else:
                    if not camino:
                        break
                    i = camino.pop()          # callejón sin salida: retroceder
                    u = R.a[i ^ 1][0]
                    puntero[u] += 1
            if u != t:
                break
            f = min(R.a[i][1] for i in camino)
            _aumentar(R, camino, f)
            total += f


def flujo_costo_minimo(R, s, t):
    """Flujo máximo de costo mínimo: aumenta por el camino más barato (SPFA) hasta saturar.
    Devuelve (flujo, costo). O(F * V * E) en el peor caso, con F = cantidad de aumentos."""
    n, total, costo = len(R.ady), 0.0, 0.0
    while True:
        dist, previo = [INF] * n, [-1] * n
        dist[s] = 0.0
        en_cola, cola = [False] * n, deque([s])
        while cola:
            u = cola.popleft()
            en_cola[u] = False
            for i in R.ady[u]:
                v, c, w = R.a[i]
                if c > EPS and dist[u] + w < dist[v] - 1e-12:
                    dist[v], previo[v] = dist[u] + w, i
                    if not en_cola[v]:
                        en_cola[v] = True
                        cola.append(v)
        if dist[t] == INF:
            return total, costo
        camino, v = [], t
        while v != s:
            i = previo[v]
            camino.append(i)
            v = R.a[i ^ 1][0]
        f = min(R.a[i][1] for i in camino)
        _aumentar(R, camino, f)
        total += f
        costo += f * dist[t]


# --------------------------------------------------------------------- modelo
def construir(g):
    """Convierte el Grafo en red residual con fuente y sumidero."""
    ids = {n: i for i, n in enumerate(g.nodos)}
    R, s, t = _Red(len(ids) + 2), len(ids), len(ids) + 1
    rutas = []
    for lista in g.ady.values():
        for a in lista:
            rutas.append((a, R.agregar(ids[a.origen], ids[a.destino],
                                       a.atributos.get("capacidad", INF), a.atributos.get("costo", 0) / 1000)))
    ofertas, demandas = {}, {}
    for nombre, at in g.nodos.items():
        if at.get("disponible", 0) > 0:
            ofertas[nombre] = R.agregar(s, ids[nombre], at["disponible"])
        if at.get("demanda", 0) > 0:
            demandas[nombre] = R.agregar(ids[nombre], t, at["demanda"])
    return R, s, t, ids, rutas, ofertas, demandas


def planificar(g, algoritmo="costo_minimo"):
    """Calcula la distribución. algoritmo: "costo_minimo" (por defecto), "dinic" o "edmonds-karp"
    (estos dos solo maximizan lo distribuido, sin buscar el costo mínimo)."""
    R, s, t, ids, rutas, ofertas, demandas = construir(g)
    if algoritmo == "costo_minimo":
        flujo_costo_minimo(R, s, t)
    elif algoritmo == "dinic":
        dinic(R, s, t)
    elif algoritmo == "edmonds-karp":
        edmonds_karp(R, s, t)
    else:
        raise ValueError("algoritmo debe ser 'costo_minimo', 'dinic' o 'edmonds-karp'")

    nombres = list(ids)
    usado = [(a, R.flujo(i)) for a, i in rutas]
    salida = {b: R.flujo(i) for b, i in ofertas.items()}
    entregado = {a: R.flujo(i) for a, i in demandas.items()}
    demanda = {a: g.nodos[a]["demanda"] for a in demandas}
    pendiente = {a: demanda[a] - entregado[a] for a in demanda if demanda[a] - entregado[a] > EPS}

    # Corte mínimo: lo que se alcanza desde S en el residual; las rutas que lo cruzan limitan el total
    alcanzable, cola = {s}, deque([s])
    while cola:
        u = cola.popleft()
        for i in R.ady[u]:
            if R.a[i][1] > EPS and R.a[i][0] not in alcanzable:
                alcanzable.add(R.a[i][0])
                cola.append(R.a[i][0])
    limitaciones = []
    for a, i in rutas:
        if ids[a.origen] in alcanzable and ids[a.destino] not in alcanzable:
            limitaciones.append(f"Ruta saturada {a.origen} -> {a.destino} (capacidad {a.atributos['capacidad']:,.0f})")
    for b, i in ofertas.items():
        if ids[b] not in alcanzable and pendiente:
            limitaciones.append(f"Bóveda {b} sin efectivo disponible (se usó todo: {salida[b]:,.0f})")
    return {"algoritmo": algoritmo, "distribuido": sum(entregado.values()), "demanda_total": sum(demanda.values()),
            "oferta_total": sum(g.nodos[b]["disponible"] for b in ofertas),
            "costo": sum(f * a.atributos.get("costo", 0) / 1000 for a, f in usado),
            "usado": [(a.origen, a.destino, f, a.atributos.get("capacidad", INF), a.atributos.get("costo", 0))
                      for a, f in usado if f > EPS],
            "salida": salida, "entregado": entregado, "pendiente": pendiente, "limitaciones": limitaciones,
            "factible": not pendiente, "nodos": nombres}


def rutas_de_distribucion(plan):
    """Descompone el plan en caminos concretos: [(monto, [bóveda, ..., agencia])]."""
    flujo = {}
    for o, d, f, _, _ in plan["usado"]:
        flujo.setdefault(o, {})[d] = flujo.get(o, {}).get(d, 0) + f
    resultado = []
    for origen, enviado in plan["salida"].items():
        for destino, recibido in plan["entregado"].items():
            while True:
                previo, cola = {origen: None}, deque([origen])
                while cola and destino not in previo:
                    u = cola.popleft()
                    for v, f in flujo.get(u, {}).items():
                        if f > EPS and v not in previo:
                            previo[v] = u
                            cola.append(v)
                if destino not in previo or origen == destino:
                    break
                camino, x = [], destino
                while x is not None:
                    camino.append(x)
                    x = previo[x]
                camino.reverse()
                f = min(flujo[a][b] for a, b in zip(camino, camino[1:]))
                for a, b in zip(camino, camino[1:]):
                    flujo[a][b] -= f
                resultado.append((f, camino))
    return sorted(resultado, key=lambda r: -r[0])


def reporte(g, plan):
    L = ["PLAN DE DISTRIBUCIÓN DE LIQUIDEZ", f"Algoritmo: {plan['algoritmo']}", "",
         f"Efectivo disponible: {plan['oferta_total']:,.0f} | demanda: {plan['demanda_total']:,.0f} | "
         f"distribuido: {plan['distribuido']:,.0f}",
         f"Costo operativo del traslado: {plan['costo']:,.2f}", "", "Bóvedas de origen:"]
    for b, f in plan["salida"].items():
        d = g.nodos[b]["disponible"]
        L.append(f"  {b:<16} envía {f:>12,.0f} de {d:>12,.0f}  (quedan {d - f:,.0f})")
    L += ["", "Agencias:"]
    for a, f in plan["entregado"].items():
        d = g.nodos[a]["demanda"]
        L.append(f"  {a:<16} recibe {f:>12,.0f} de {d:>12,.0f}  " + ("OK" if d - f <= EPS else f"FALTAN {d - f:,.0f}"))
    L += ["", "Uso de rutas (de mayor a menor utilización):"]
    for o, d, f, cap, _ in sorted(plan["usado"], key=lambda r: -(r[2] / r[3] if r[3] != INF else 0)):
        L.append(f"  {o:<14} -> {d:<16} {f:>10,.0f} / {cap:>10,.0f}" + (f"  ({f / cap:.0%})" if cap != INF else ""))
    L += ["", "Rutas de distribución:"]
    for f, camino in rutas_de_distribucion(plan):
        L.append(f"  {f:>10,.0f}  {' -> '.join(camino)}")
    L += ["", "Limitaciones:"] + (["  " + x for x in plan["limitaciones"]] if plan["limitaciones"] else ["  ninguna: se cubre toda la demanda"])
    return "\n".join(L)
