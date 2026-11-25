import math

import pytest

from src.gestion_red import GestionRed
from src.visual import (FONDO, TIPO_COLOR, aclarar, calcular_layout, columnas_de, curva, mezclar, punto_en)


def carding():
    r = GestionRed(multi=True)
    r.cargar_nodos("data/carding_nodos.csv")
    r.cargar_aristas("data/transacciones.csv", crear_nodos=False)
    return r.grafo


def test_columnas_para_carding():
    g = carding()
    pos = calcular_layout(g, 1000, 700)
    assert set(pos) == set(g.nodos)
    x = {t: {pos[n][0] for n in g.nodos if g.nodos[n]["tipo"] == t} for t in ("tarjeta", "dispositivo", "comercio", "cuenta", "billetera")}
    assert all(len(v) == 1 for v in x.values())                         # una columna por tipo
    c = {t: v.pop() for t, v in x.items()}
    assert c["tarjeta"] < c["dispositivo"] < c["comercio"] < c["cuenta"] < c["billetera"]


def test_fuerzas_para_otras_redes_dentro_del_lienzo_y_reproducible():
    r = GestionRed()
    r.cargar_json("data/red_enrutamiento.json")
    a, b = calcular_layout(r.grafo, 1000, 700), calcular_layout(r.grafo, 1000, 700)
    assert a == b and set(a) == set(r.grafo.nodos)
    assert all(40 - 1e-6 <= x <= 960 + 1e-6 and 40 - 1e-6 <= y <= 660 + 1e-6 for x, y in a.values())
    puntos = list(a.values())
    assert min(math.dist(p, q) for i, p in enumerate(puntos) for q in puntos[i + 1:]) > 5   # no se encimen


def test_red_vacia_y_un_nodo():
    r = GestionRed()
    assert calcular_layout(r.grafo) == {}
    r.agregar_nodo("A")
    assert set(calcular_layout(r.grafo)) == {"A"}


def test_mezclar_y_aclarar():
    assert mezclar("#000000", "#ffffff", 0) == "#000000" and mezclar("#000000", "#ffffff", 1) == "#ffffff"
    assert mezclar("#000000", "#ffffff", 0.5) == "#808080" and mezclar("#000000", "#ffffff", 7) == "#ffffff"
    assert aclarar("#ff0000", 1) == "#ffffff"
    assert all(len(c) == 7 and mezclar(FONDO, c, 0.3).startswith("#") for c in TIPO_COLOR.values())


def test_curvas_entre_nodos():
    a, b = (0, 0), (100, 60)
    assert curva(a, b, False) == [a, b] and punto_en(a, b, False, 0.5) == (50, 30)
    pts = curva(a, b, True, n=10)
    assert len(pts) == 11 and pts[0] == a and pts[-1] == b
    assert punto_en(a, b, True, 0.5) == pytest.approx((50, 30))          # la S pasa por el centro


def test_columnas_solo_en_la_red_de_carding():
    g = carding()
    c = columnas_de(g, calcular_layout(g, 1000, 700))
    assert set(c) == {"tarjeta", "dispositivo", "comercio", "cuenta", "billetera"} and c["tarjeta"] < c["billetera"]
    r = GestionRed()
    r.cargar_json("data/red_enrutamiento.json")
    assert columnas_de(r.grafo, calcular_layout(r.grafo)) == {}
