"""Módulo 2 (problemática del grupo): análisis de posibles casos de carding con grafos.

Red dirigida y multi: nodos tarjeta (T), dispositivo (D), comercio (M), cuenta (C) y billetera (B).
Conexiones: uso (T -> D), pago (T -> M, con monto y fecha), liquidacion (M -> C) y
transferencia (C -> B). Una alerta NO prueba fraude: indica qué relaciones conviene revisar.

Algoritmos (V nodos, E conexiones):
- BFS (consultar, proximidad): elementos cercanos por niveles. O(V + E).
- DFS (caminos_hasta): recorre cada ruta hasta llegar a una billetera. Exponencial en el peor
  caso, acotado por max_saltos y max_caminos.
- Grado de un nodo (tarjetas_por_dispositivo, dispositivo_con_cuenta_comun, dispositivos_por_tarjeta,
  cuentas_concentradoras): cuenta con cuántos elementos se relaciona cada nodo. O(V + E).
- BFS inverso: desde una cuenta hacia atrás, para saber qué tarjetas terminan en ella. O(V + E).
- Ráfagas de pagos: ventana deslizante sobre los pagos de cada tarjeta ordenados por fecha.
  O(E log E).
- Ciclos: se reutiliza analisis_transacciones.ciclos (solo como análisis complementario).
"""
from collections import deque
from datetime import datetime

from src.analisis_transacciones import ciclos, proximidad

FORMATO_FECHA = "%Y-%m-%d %H:%M"


def _tipo(g, n):
    return g.nodos[n]["tipo"]


def _entrantes(g):
    ent = {n: [] for n in g.nodos}
    for lista in g.ady.values():
        for a in lista:
            ent[a.destino].append(a)
    return ent


def _hallazgo(tipo, elementos, detalle, relaciones):
    return {"tipo": tipo, "elementos": elementos, "detalle": detalle, "relaciones": relaciones}


# ------------------------------------------------------------------ por grado
def tarjetas_por_dispositivo(g, min_tarjetas=3):
    """Dispositivos desde los que se usan varias tarjetas distintas (grado de entrada)."""
    ent, res = _entrantes(g), []
    for n in g.nodos:
        if _tipo(g, n) != "dispositivo":
            continue
        ts = sorted({a.origen for a in ent[n] if _tipo(g, a.origen) == "tarjeta"})
        if len(ts) >= min_tarjetas:
            res.append(_hallazgo("Varias tarjetas en un mismo dispositivo", [n, *ts],
                                 f"{len(ts)} tarjetas distintas se usaron desde {n}", [f"{t} -> {n}" for t in ts]))
    return res


def dispositivo_con_cuenta_comun(g, min_tarjetas=3):
    """Tarjetas que comparten dispositivo y además terminan en la misma cuenta (el caso del
    ejemplo de la propuesta). Usa DFS desde cada tarjeta hasta la primera cuenta."""
    res = []
    for h in tarjetas_por_dispositivo(g, min_tarjetas):
        d, tarjetas = h["elementos"][0], h["elementos"][1:]
        por_cuenta = {}
        for t in tarjetas:
            for camino in caminos_hasta(g, t, "cuenta", max_saltos=3):
                por_cuenta.setdefault(camino[-1], {}).setdefault(t, camino)
        for c, rutas in por_cuenta.items():
            if len(rutas) >= min_tarjetas:
                res.append(_hallazgo("Tarjetas del mismo dispositivo terminan en la misma cuenta", [d, c, *sorted(rutas)],
                                     f"{len(rutas)} tarjetas de {d} terminan en {c}",
                                     [" -> ".join(rutas[t]) for t in sorted(rutas)]))
    return res


def dispositivos_por_tarjeta(g, min_dispositivos=3):
    """Tarjetas usadas desde muchos dispositivos distintos (grado de salida hacia dispositivos)."""
    res = []
    for n in g.nodos:
        if _tipo(g, n) != "tarjeta":
            continue
        ds = sorted({a.destino for a in g.vecinos(n) if _tipo(g, a.destino) == "dispositivo"})
        if len(ds) >= min_dispositivos:
            res.append(_hallazgo("Una tarjeta en muchos dispositivos", [n, *ds],
                                 f"{n} aparece en {len(ds)} dispositivos distintos", [f"{n} -> {d}" for d in ds]))
    return res


def cuentas_concentradoras(g, min_comercios=3):
    """Cuentas que reciben liquidaciones de varios comercios. Con BFS inverso cuenta cuántas
    tarjetas distintas terminan en esa cuenta."""
    ent, res = _entrantes(g), []
    for c in g.nodos:
        if _tipo(g, c) != "cuenta":
            continue
        ms = sorted({a.origen for a in ent[c] if _tipo(g, a.origen) == "comercio"})
        if len(ms) < min_comercios:
            continue
        visto, cola = {c}, deque([c])
        while cola:                                   # BFS hacia atrás
            u = cola.popleft()
            for a in ent[u]:
                if a.origen not in visto:
                    visto.add(a.origen)
                    cola.append(a.origen)
        tarjetas = sorted(n for n in visto if _tipo(g, n) == "tarjeta")
        res.append(_hallazgo("Cuenta que concentra varios comercios", [c, *ms],
                             f"{c} recibe de {len(ms)} comercios; {len(tarjetas)} tarjetas distintas terminan en ella",
                             [f"{m} -> {c}" for m in ms]))
    return res


# ---------------------------------------------------------------------- tiempo
def _minutos(texto):
    return datetime.strptime(texto, FORMATO_FECHA).timestamp() / 60


def rafagas_de_pagos(g, ventana_min=10, min_pagos=4):
    """Tarjetas con muchos pagos en pocos minutos. Ventana deslizante: O(E log E)."""
    res = []
    for t in g.nodos:
        if _tipo(g, t) != "tarjeta":
            continue
        pagos = []
        for a in g.vecinos(t):
            if a.atributos.get("tipo") == "pago" and a.atributos.get("fecha"):
                try:
                    pagos.append((_minutos(a.atributos["fecha"]), a))
                except ValueError:
                    continue
        pagos.sort(key=lambda p: p[0])
        mejor, i = (0, 0, 0), 0
        for j in range(len(pagos)):
            while pagos[j][0] - pagos[i][0] > ventana_min:
                i += 1
            if j - i + 1 > mejor[0]:
                mejor = (j - i + 1, i, j)
        n, i, j = mejor
        if n >= min_pagos:
            grupo = [a for _, a in pagos[i:j + 1]]
            montos = [a.atributos.get("monto", 0) for a in grupo]
            comercios = sorted({a.destino for a in grupo})
            res.append(_hallazgo("Ráfaga de pagos", [t, *comercios],
                                 f"{n} pagos en {pagos[j][0] - pagos[i][0]:.0f} min (montos de {min(montos):,.2f} a {max(montos):,.2f})",
                                 [f"{t} -> {a.destino} ({a.atributos.get('monto', 0):,.2f} a las {a.atributos['fecha'][-5:]})" for a in grupo]))
    return res


# ------------------------------------------------------------- DFS y consulta
def caminos_hasta(g, origen, tipo_final="billetera", max_saltos=6, max_caminos=50):
    """DFS: caminos simples desde origen hasta un nodo de tipo_final (por defecto una billetera)."""
    g.obtener_nodo(origen)
    caminos, camino, visitado = [], [origen], {origen}

    def dfs(u):
        if len(caminos) >= max_caminos:
            return
        if u != origen and _tipo(g, u) == tipo_final:
            caminos.append(list(camino))
            return
        if len(camino) > max_saltos:
            return
        for v in sorted({a.destino for a in g.vecinos(u)}):
            if v not in visitado:
                visitado.add(v)
                camino.append(v)
                dfs(v)
                camino.pop()
                visitado.remove(v)

    dfs(origen)
    return caminos


def analizar_carding(g, min_tarjetas=3, min_dispositivos=3, min_comercios=3, ventana_min=10, min_pagos=4):
    """Todas las alertas de carding. Devuelve [{"tipo", "elementos", "detalle", "relaciones"}]."""
    h = (tarjetas_por_dispositivo(g, min_tarjetas) + dispositivo_con_cuenta_comun(g, min_tarjetas)
         + dispositivos_por_tarjeta(g, min_dispositivos)
         + cuentas_concentradoras(g, min_comercios) + rafagas_de_pagos(g, ventana_min, min_pagos))
    for c in ciclos(g, monto_min=0):
        h.append(_hallazgo("Ciclo de movimientos", c["cuentas"] + [c["cuentas"][0]],
                           "el dinero vuelve a un nodo ya visitado", [f"{a} -> {b}" for a, b in zip(c["cuentas"], c["cuentas"][1:] + [c["cuentas"][0]])]))
    return h


def consultar(g, nodo, max_nivel=3, **umbrales):
    """Ficha de un elemento (tarjeta, cuenta...): quién está cerca (BFS por niveles), caminos hasta
    billeteras (DFS) y alertas en las que participa."""
    niveles = {}
    for n, nivel in proximidad(g, nodo, max_nivel).items():
        if n != nodo:
            niveles.setdefault(nivel, []).append(n)
    return {"nodo": nodo, "tipo": _tipo(g, nodo), "niveles": {k: sorted(v) for k, v in sorted(niveles.items())},
            "caminos": caminos_hasta(g, nodo),
            "alertas": [h for h in analizar_carding(g, **umbrales) if nodo in h["elementos"]]}


# ------------------------------------------------------------ simulación de propagación
def _monto(a):
    try:
        return float(a.atributos.get("monto") or 0)
    except (TypeError, ValueError):
        return 0.0


def simular_ataque(g, fuentes, max_pasos=10):
    """Simula cómo se propaga un ataque por la red: BFS por oleadas siguiendo el sentido del dinero.

    Cada oleada es un salto: los nodos recién alcanzados pasan a ser la frontera de la siguiente.
    Devuelve {"fuentes", "pasos": [{"nodos", "aristas", "monto"}], "visto", "alcanzados", "total",
    "por_tipo", "billeteras", "monto"}. O(V + E)."""
    fuentes = list(dict.fromkeys(fuentes))
    for f in fuentes:
        g.obtener_nodo(f)
    visto, usadas, contadas = {f: 0 for f in fuentes}, set(), set()
    pasos, frontera = [], fuentes
    while frontera and len(pasos) < max_pasos:
        nuevos, aristas, monto = [], [], 0.0
        for u in frontera:
            for a in g.vecinos(u):
                clave = (u, a.destino) if g.dirigido else tuple(sorted((u, a.destino)))
                if clave not in usadas:
                    usadas.add(clave)
                    aristas.append((u, a.destino))
                if a.atributos.get("tipo") == "pago" and id(a.atributos) not in contadas:
                    contadas.add(id(a.atributos))
                    monto += _monto(a)
                if a.destino not in visto:
                    visto[a.destino] = len(pasos) + 1
                    nuevos.append(a.destino)
        if not aristas:
            break
        pasos.append({"nodos": nuevos, "aristas": aristas, "monto": monto})
        frontera = nuevos
    por_tipo = {}
    for n in visto:
        por_tipo[_tipo(g, n)] = por_tipo.get(_tipo(g, n), 0) + 1
    return {"fuentes": fuentes, "pasos": pasos, "visto": visto, "alcanzados": len(visto), "total": g.n_nodos,
            "por_tipo": por_tipo, "billeteras": sorted(n for n in visto if _tipo(g, n) == "billetera"),
            "monto": sum(p["monto"] for p in pasos)}


def reporte_simulacion(res):
    L = [f"SIMULACIÓN DE PROPAGACIÓN desde {', '.join(res['fuentes'])}",
         "Es un escenario hipotético sobre datos simulados: muestra por dónde podría moverse el dinero.", ""]
    if not res["pasos"]:
        return "\n".join(L + ["Desde estos elementos no sale dinero hacia otros."])
    for i, p in enumerate(res["pasos"], 1):
        L.append(f"Oleada {i}: {len(p['nodos'])} elementos nuevos, {len(p['aristas'])} conexiones"
                 + (f", pagos por {p['monto']:,.2f}" if p["monto"] else ""))
        if p["nodos"]:
            L.append("   " + ", ".join(p["nodos"][:12]) + (f" ... (+{len(p['nodos']) - 12})" if len(p["nodos"]) > 12 else ""))
    L += ["", f"Alcanzados: {res['alcanzados']} de {res['total']} elementos "
          f"({', '.join(f'{v} {k}' for k, v in sorted(res['por_tipo'].items()))}).",
          f"Billeteras alcanzadas: {', '.join(res['billeteras']) or 'ninguna'}.",
          f"Monto en pagos de la cadena: {res['monto']:,.2f}."]
    return "\n".join(L)


# --------------------------------------------------------------------- reportes
def reporte(hallazgos):
    L = ["REPORTE DE POSIBLES CASOS DE CARDING",
         "Las alertas no significan que una persona haya cometido fraude; indican relaciones que conviene revisar.", ""]
    if not hallazgos:
        return "\n".join(L + ["No se encontraron alertas."])
    for i, x in enumerate(hallazgos, 1):
        L.append(f"{i}. {x['tipo']}: {', '.join(x['elementos'])}\n   {x['detalle']}")
        L += [f"     - {r}" for r in x["relaciones"][:8]]
        if len(x["relaciones"]) > 8:
            L.append(f"     ... y {len(x['relaciones']) - 8} relaciones más")
    return "\n".join(L)


def reporte_consulta(c):
    L = [f"FICHA DE {c['nodo']} ({c['tipo']})", "", "Elementos relacionados por nivel de cercanía:"]
    L += [f"  nivel {k}: {', '.join(v)}" for k, v in c["niveles"].items()] or ["  ninguno"]
    L += ["", "Caminos hasta una billetera:"] + ([f"  {' -> '.join(p)}" for p in c["caminos"]] or ["  ninguno"])
    L += ["", "Alertas en las que participa:"] + ([f"  {a['tipo']}: {a['detalle']}" for a in c["alertas"]] or ["  ninguna"])
    return "\n".join(L)
