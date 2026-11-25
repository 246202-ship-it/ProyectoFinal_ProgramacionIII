"""Módulo 3: optimización del enrutamiento de operaciones y cálculo de comisiones.

Red: grafo dirigido y multi (varios canales entre las mismas entidades). Atributos de cada
canal: comision (fija), comision_pct (% del monto), tiempo (horas), costo (operativo),
riesgo (0-1), limite (monto máximo por operación), activo ("no" = canal fuera de servicio),
canal (nombre).

Algoritmos (V entidades, E canales):
- Dijkstra con heap, O((V + E) log V): los pesos nunca son negativos (el Módulo 1 lo valida),
  así que es el más rápido para la ruta óptima. Con pesos de comisión que dependen del monto,
  basta recalcular el peso de cada canal para el monto pedido.
- Bellman-Ford, O(V * E): se implementa solo para validar a Dijkstra y medir la diferencia.
- DFS con retroceso para listar TODAS las alternativas (caminos simples) y compararlas:
  exponencial en el peor caso, aceptable en redes de decenas de entidades y acotado por
  max_saltos.
- Dijkstra desde cada entidad para la matriz de costos entre entidades: O(V (V + E) log V).
El riesgo es multiplicativo (1 - producto de (1 - riesgo)); se optimiza con peso -log(1 - riesgo).
"""
import heapq
import math

INF = math.inf
CRITERIOS = ("comision", "tiempo", "costo", "riesgo", "total")


def peso(a, criterio, monto=0):
    """Peso de un canal. criterio: nombre de CRITERIOS o dict {criterio: ponderación}."""
    if isinstance(criterio, dict):
        return sum(w * peso(a, k, monto) for k, w in criterio.items())
    at = a.atributos
    if criterio == "comision":
        return at.get("comision", 0) + at.get("comision_pct", 0) * monto / 100
    if criterio == "tiempo":
        return at.get("tiempo", 0)
    if criterio == "costo":
        return at.get("costo", 0)
    if criterio == "total":
        return peso(a, "comision", monto) + at.get("costo", 0)
    if criterio == "riesgo":
        r = at.get("riesgo", 0)
        return INF if r >= 1 else -math.log(1 - r)
    raise ValueError(f"Criterio desconocido '{criterio}'. Válidos: {', '.join(CRITERIOS)}")


def disponible(a, monto):
    """El canal está activo y permite ese monto."""
    limite = a.atributos.get("limite")
    if limite is not None and monto > limite:
        return False
    return str(a.atributos.get("activo", "si")).strip().lower() not in ("no", "false", "0")


def _recorrer(g, origen, criterio, monto, destino=None):
    """Dijkstra desde origen (se detiene al llegar a destino si se indica)."""
    g.obtener_nodo(origen)
    dist, prev, cola = {origen: 0.0}, {}, [(0.0, origen)]
    while cola:
        c, u = heapq.heappop(cola)
        if c > dist[u]:
            continue
        if u == destino:
            break
        for a in g.vecinos(u):
            w = peso(a, criterio, monto)
            if w == INF or not disponible(a, monto):
                continue
            if c + w < dist.get(a.destino, INF):
                dist[a.destino], prev[a.destino] = c + w, a
                heapq.heappush(cola, (c + w, a.destino))
    return dist, prev


def _camino(prev, origen, destino):
    ruta, x = [], destino
    while x != origen:
        ruta.append(prev[x])
        x = prev[x].origen
    return ruta[::-1]


def ruta_optima(g, origen, destino, criterio="comision", monto=0, algoritmo="dijkstra"):
    """Mejor ruta según el criterio. Devuelve (valor, [canales]) o None si no hay ruta."""
    g.obtener_nodo(destino)
    if algoritmo == "bellman-ford":
        dist, prev = _bellman_ford(g, origen, criterio, monto)
    else:
        dist, prev = _recorrer(g, origen, criterio, monto, destino)
    if destino not in dist or dist[destino] == INF:
        return None
    return dist[destino], _camino(prev, origen, destino)


def _bellman_ford(g, origen, criterio, monto):
    g.obtener_nodo(origen)
    canales = [(a, peso(a, criterio, monto)) for lista in g.ady.values() for a in lista if disponible(a, monto)]
    dist, prev = {origen: 0.0}, {}
    for _ in range(g.n_nodos - 1):
        cambio = False
        for a, w in canales:
            if a.origen in dist and dist[a.origen] + w < dist.get(a.destino, INF):
                dist[a.destino], prev[a.destino] = dist[a.origen] + w, a
                cambio = True
        if not cambio:
            break
    return dist, prev


def alternativas(g, origen, destino, criterio="comision", monto=0, max_saltos=5, max_rutas=500):
    """Rutas posibles sin repetir entidades, de la mejor a la peor. Devuelve [(valor, [canales])].
    Se detiene en max_rutas (en redes grandes la lista es parcial), pero la ruta óptima siempre se incluye."""
    g.obtener_nodo(origen)
    g.obtener_nodo(destino)
    rutas, camino, visitado = [], [], {origen}

    def dfs(u, acumulado):
        if u == destino:
            rutas.append((acumulado, list(camino)))
            return
        if len(camino) == max_saltos or len(rutas) >= max_rutas:
            return
        for a in g.vecinos(u):
            w = peso(a, criterio, monto)
            if a.destino in visitado or w == INF or not disponible(a, monto):
                continue
            visitado.add(a.destino)
            camino.append(a)
            dfs(a.destino, acumulado + w)
            camino.pop()
            visitado.remove(a.destino)

    if origen != destino:
        dfs(origen, 0.0)
        optima = ruta_optima(g, origen, destino, criterio, monto)
        if optima and len(optima[1]) <= max_saltos and (not rutas or optima[0] < min(r[0] for r in rutas) - 1e-9):
            rutas.append(optima)      # con el tope max_rutas la búsqueda puede no haber llegado a la mejor
    return sorted(rutas, key=lambda r: r[0])


def evaluar_ruta(canales, monto=0):
    """Totales de una ruta: comisión, tiempo, costo operativo, riesgo acumulado y saltos."""
    ok = 1.0
    for a in canales:
        ok *= 1 - a.atributos.get("riesgo", 0)
    return {"comision": sum(peso(a, "comision", monto) for a in canales),
            "tiempo": sum(a.atributos.get("tiempo", 0) for a in canales),
            "costo": sum(a.atributos.get("costo", 0) for a in canales),
            "riesgo": 1 - ok, "saltos": len(canales)}


def texto_ruta(canales, origen=None):
    if not canales:
        return origen or "(sin saltos)"
    return canales[0].origen + "".join(f" -[{a.atributos.get('canal', '')}]-> {a.destino}" for a in canales)


def matriz_costos(g, entidades, criterio="comision", monto=0):
    """Costo mínimo entre cada par de entidades dadas: {origen: {destino: valor o None}}."""
    res = {}
    for o in entidades:
        dist, _ = _recorrer(g, o, criterio, monto)
        res[o] = {d: (dist[d] if d in dist and dist[d] != INF else None) for d in entidades}
    return res


def reporte_comparativo(g, origen, destino, monto, max_filas=6):
    """Reporte con la mejor ruta por criterio y la lista de alternativas ordenada por comisión."""
    lineas = [f"ENRUTAMIENTO {origen} -> {destino}  |  monto: {monto:,.2f}", ""]
    rutas = alternativas(g, origen, destino, "comision", monto)
    if not rutas:
        return "\n".join(lineas + ["No hay ninguna ruta disponible para ese monto (límites o canales fuera de servicio)."])
    lineas.append("Mejor ruta por criterio:")
    for crit in ("comision", "tiempo", "costo", "riesgo"):
        _, canales = ruta_optima(g, origen, destino, crit, monto)
        m = evaluar_ruta(canales, monto)
        lineas.append(f"  {crit:<9} {texto_ruta(canales)}\n            comisión {m['comision']:.2f} | "
                      f"{m['tiempo']:.2f} h | costo {m['costo']:.2f} | riesgo {m['riesgo']:.1%}")
    lineas += ["", f"Alternativas ({len(rutas)} en total, de menor a mayor comisión):"]
    for _, canales in rutas[:max_filas]:
        m = evaluar_ruta(canales, monto)
        lineas.append(f"  {m['comision']:>8.2f}  {m['tiempo']:>6.2f} h  riesgo {m['riesgo']:>5.1%}  {texto_ruta(canales)}")
    mejor, peor = evaluar_ruta(rutas[0][1], monto)["comision"], evaluar_ruta(rutas[-1][1], monto)["comision"]
    lineas.append(f"\nElegir la mejor frente a la peor alternativa ahorra {peor - mejor:.2f} en comisiones.")
    return "\n".join(lineas)
