"""Dibujo del grafo: posiciones de los nodos y colores por tipo (sin depender de Tkinter)."""
import math
import random

FONDO = "#0a0f24"                  # azul noche: sobre él los colores neón se ven más vivos
TIPO_COLOR = {"tarjeta": "#00e5ff", "dispositivo": "#4dff91", "comercio": "#ffb627", "cuenta": "#b388ff",
              "billetera": "#ff4d8d", "cliente": "#2ee6c5", "agencia": "#ff8a4c", "boveda_central": "#5c7cff",
              "boveda_regional": "#8f9dff", "atm": "#d8f542", "entidad": "#9fb3d9", "plataforma": "#ff6fd8",
              "agente": "#7dd3ff", "compensacion": "#8cf0a0", "servidor": "#ff6b6b"}
ETIQUETA_TIPO = {"tarjeta": "Tarjetas", "dispositivo": "Dispositivos", "comercio": "Comercios",
                 "cuenta": "Cuentas", "billetera": "Billeteras"}
COLUMNAS = ["tarjeta", "dispositivo", "comercio", "cuenta", "billetera"]


def calcular_layout(g, ancho=1000, alto=700, margen=40, semilla=1, iteraciones=150):
    """Posiciones {nodo: (x, y)} dentro de ancho x alto. Si la red es de carding (tarjeta ->
    dispositivo -> comercio -> cuenta -> billetera) usa una columna por tipo; si no,
    Fruchterman-Reingold (fuerzas de repulsión y atracción), O(iteraciones * V^2)."""
    nodos = list(g.nodos)
    if not nodos:
        return {}
    tipos = {g.nodos[n]["tipo"] for n in nodos}
    if len(tipos) > 1 and tipos <= set(COLUMNAS):
        presentes = [t for t in COLUMNAS if t in tipos]
        pos = {}
        for i, t in enumerate(presentes):
            x = margen + i * (ancho - 2 * margen) / max(1, len(presentes) - 1)
            col = sorted(n for n in nodos if g.nodos[n]["tipo"] == t)
            for j, n in enumerate(col):
                pos[n] = (x, margen + j * (alto - 2 * margen) / max(1, len(col) - 1) if len(col) > 1 else alto / 2)
        return pos

    az = random.Random(semilla)
    p = {n: [az.random(), az.random()] for n in nodos}
    k = math.sqrt(1 / len(nodos))
    aristas = {(a.origen, a.destino) for lista in g.ady.values() for a in lista if a.origen != a.destino}
    temp = 0.1
    for _ in range(iteraciones):
        fuerza = {n: [0.0, 0.0] for n in nodos}
        for i, u in enumerate(nodos):
            for v in nodos[i + 1:]:
                dx, dy = p[u][0] - p[v][0], p[u][1] - p[v][1]
                d = max(math.hypot(dx, dy), 1e-4)
                f = k * k / d
                for n, s in ((u, 1), (v, -1)):
                    fuerza[n][0] += s * dx / d * f
                    fuerza[n][1] += s * dy / d * f
        for u, v in aristas:
            dx, dy = p[u][0] - p[v][0], p[u][1] - p[v][1]
            d = max(math.hypot(dx, dy), 1e-4)
            f = d * d / k
            for n, s in ((u, -1), (v, 1)):
                fuerza[n][0] += s * dx / d * f
                fuerza[n][1] += s * dy / d * f
        for n in nodos:
            fx, fy = fuerza[n]
            d = max(math.hypot(fx, fy), 1e-9)
            p[n][0] += fx / d * min(d, temp)
            p[n][1] += fy / d * min(d, temp)
        temp = max(temp * 0.97, 0.002)
    xs, ys = [q[0] for q in p.values()], [q[1] for q in p.values()]
    x0, y0 = min(xs), min(ys)
    sx, sy = (max(xs) - x0) or 1, (max(ys) - y0) or 1
    return {n: (margen + (q[0] - x0) / sx * (ancho - 2 * margen), margen + (q[1] - y0) / sy * (alto - 2 * margen))
            for n, q in p.items()}


# ------------------------------------------------------------------ color y curvas
def _rgb(color):
    c = color.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def mezclar(base, color, t):
    """Color resultante de poner `color` sobre `base` con opacidad t (0 a 1). Tkinter no tiene
    transparencia: así se simulan brillos y atenuados mezclando con el fondo."""
    t = max(0.0, min(1.0, t))
    return "#%02x%02x%02x" % tuple(round(a + (b - a) * t) for a, b in zip(_rgb(base), _rgb(color)))


def aclarar(color, t=0.4):
    return mezclar(color, "#ffffff", t)


def columnas_de(g, pos):
    """{tipo: x} si el dibujo está en columnas por tipo (red de carding); si no, {}."""
    xs = {}
    for n, a in g.nodos.items():
        xs.setdefault(a["tipo"], set()).add(round(pos[n][0], 3))
    if len(xs) >= 3 and set(xs) <= set(COLUMNAS) and all(len(v) == 1 for v in xs.values()):
        return {t: next(iter(v)) for t, v in xs.items()}
    return {}


def punto_en(a, b, suave, t):
    """Punto de la conexión a -> b en t (0 a 1). suave=True: curva en S (Bézier); si no, recta."""
    if not suave:
        return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
    mx, u = (a[0] + b[0]) / 2, 1 - t
    c0, c1, c2, c3 = u ** 3, 3 * u * u * t, 3 * u * t * t, t ** 3
    return c0 * a[0] + c1 * mx + c2 * mx + c3 * b[0], c0 * a[1] + c1 * a[1] + c2 * b[1] + c3 * b[1]


def curva(a, b, suave=False, n=14):
    """Puntos para dibujar la conexión a -> b."""
    return [a, b] if not suave else [punto_en(a, b, True, i / n) for i in range(n + 1)]
