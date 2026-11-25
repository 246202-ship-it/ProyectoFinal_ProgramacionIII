import random

import pytest

from src.distribucion_liquidez import (_Red, dinic, edmonds_karp, flujo_costo_minimo, planificar, reporte,
                                       rutas_de_distribucion)
from src.gestion_red import GestionRed


def cargar():
    r = GestionRed()
    assert r.cargar_json("data/distribucion_liquidez.json")["rechazados"] == []
    return r


@pytest.mark.parametrize("algoritmo", [dinic, edmonds_karp])
def test_flujo_maximo_clasico_clrs(algoritmo):
    R = _Red(6)  # s=0, v1=1, v2=2, v3=3, v4=4, t=5
    for u, v, c in ((0, 1, 16), (0, 2, 13), (1, 3, 12), (2, 1, 4), (2, 4, 14), (3, 2, 9), (3, 5, 20), (4, 3, 7), (4, 5, 4)):
        R.agregar(u, v, c)
    assert algoritmo(R, 0, 5) == 23


def test_flujo_de_costo_minimo_pequeno():
    R = _Red(4)  # dos caminos s->t: barato (cap 5, costo 1+1) y caro (cap 10, costo 3+3)
    for u, v, c, w in ((0, 1, 5, 1), (1, 3, 5, 1), (0, 2, 10, 3), (2, 3, 10, 3)):
        R.agregar(u, v, c, w)
    assert flujo_costo_minimo(R, 0, 3) == (15, 5 * 2 + 10 * 6)


def test_datos_base_distribuye_lo_posible_con_costo_minimo():
    g = cargar().grafo
    p = planificar(g)
    assert p["distribuido"] == 1_060_000 and p["demanda_total"] == 1_070_000
    assert p["pendiente"] == {"Ag-Sicuani": 10_000}
    assert p["costo"] == pytest.approx(10364.5)
    assert not p["factible"]
    assert p["limitaciones"] == ["Ruta saturada BovedaCusco -> Ag-Sicuani (capacidad 80,000)"]


def test_los_tres_algoritmos_distribuyen_lo_mismo():
    g = cargar().grafo
    totales = {a: planificar(g, a)["distribuido"] for a in ("costo_minimo", "dinic", "edmonds-karp")}
    assert set(totales.values()) == {1_060_000}


def test_se_respetan_capacidades_y_conservacion():
    g = cargar().grafo
    p = planificar(g)
    entra, sale = {}, {}
    for o, d, f, cap, _ in p["usado"]:
        assert f <= cap + 1e-6
        sale[o] = sale.get(o, 0) + f
        entra[d] = entra.get(d, 0) + f
    for n in ("BovedaArequipa", "BovedaCusco", "BovedaTrujillo", "BovedaPiura"):   # nodos de paso: entra = sale
        assert entra.get(n, 0) == pytest.approx(sale.get(n, 0))
    assert sum(p["salida"].values()) == pytest.approx(p["distribuido"])


def test_si_la_boveda_central_tiene_poco_se_usa_la_reserva():
    r = cargar()
    r.modificar_nodo("BovedaCentral", disponible=800_000)
    p = planificar(r.grafo)
    assert p["distribuido"] == 1_060_000
    assert p["salida"]["BovedaCentral"] == pytest.approx(800_000)
    assert p["salida"]["BovedaReserva"] == pytest.approx(260_000)    # solo lo indispensable: es más cara
    assert p["costo"] > 10364.5


def test_oferta_insuficiente_se_reporta():
    r = cargar()
    r.modificar_nodo("BovedaCentral", disponible=100_000)
    r.modificar_nodo("BovedaReserva", disponible=0)
    p = planificar(r.grafo)
    assert p["distribuido"] == 100_000
    assert any("BovedaCentral sin efectivo" in x for x in p["limitaciones"])


def test_agencia_sin_ruta_no_recibe_nada():
    r = cargar()
    r.agregar_nodo("Ag-Aislada", "agencia", demanda=5000)
    r.agregar_nodo("Boveda-X", "boveda_regional")
    r.agregar_arista("Boveda-X", "Ag-Aislada", capacidad=9000, costo=1)
    p = planificar(r.grafo)
    assert p["entregado"]["Ag-Aislada"] == 0 and p["pendiente"]["Ag-Aislada"] == 5000


def test_sin_demanda_o_sin_oferta():
    r = GestionRed()
    r.agregar_nodo("B", "boveda_central", disponible=100)
    r.agregar_nodo("A", "agencia")
    r.agregar_arista("B", "A", capacidad=50)
    p = planificar(r.grafo)
    assert (p["distribuido"], p["factible"]) == (0, True)


def test_rutas_de_distribucion_suman_lo_distribuido():
    p = planificar(cargar().grafo)
    rutas = rutas_de_distribucion(p)
    assert sum(f for f, _ in rutas) == pytest.approx(p["distribuido"])
    assert all(c[0].startswith("Boveda") and c[-1].startswith("Ag-") for _, c in rutas)


def test_reporte():
    r = cargar()
    t = reporte(r.grafo, planificar(r.grafo))
    assert "FALTAN 10,000" in t and "Ruta saturada" in t and "Costo operativo del traslado: 10,364.50" in t


def test_algoritmo_invalido():
    with pytest.raises(ValueError):
        planificar(cargar().grafo, "magia")


@pytest.mark.parametrize("semilla", range(25))
def test_redes_aleatorias_los_algoritmos_coinciden(semilla):
    azar = random.Random(semilla)
    r = GestionRed()
    n = 12
    for i in range(n):
        r.agregar_nodo(f"N{i}", "boveda_regional", **({"disponible": azar.randint(50, 200)} if i < 2 else {}),
                       **({"demanda": azar.randint(50, 200)} if i >= n - 3 else {}))
    for _ in range(40):
        o, d = azar.sample(range(n), 2)
        if not r.grafo.tiene_arista(f"N{o}", f"N{d}"):
            r.agregar_arista(f"N{o}", f"N{d}", capacidad=azar.randint(10, 120), costo=azar.randint(1, 20))
    d, e, c = (planificar(r.grafo, a) for a in ("dinic", "edmonds-karp", "costo_minimo"))
    assert d["distribuido"] == pytest.approx(e["distribuido"]) == pytest.approx(c["distribuido"])
    assert c["costo"] <= d["costo"] + 1e-6 and c["costo"] <= e["costo"] + 1e-6
