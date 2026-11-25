import pytest

from src.carding import (analizar_carding, caminos_hasta, consultar, cuentas_concentradoras,
                         dispositivo_con_cuenta_comun, dispositivos_por_tarjeta, rafagas_de_pagos, reporte,
                         reporte_consulta, reporte_simulacion, simular_ataque, tarjetas_por_dispositivo)
from src.gestion_red import GestionRed


@pytest.fixture(scope="module")
def g():
    r = GestionRed(multi=True)
    assert r.cargar_nodos("data/carding_nodos.csv")["rechazados"] == []
    assert r.cargar_aristas("data/transacciones.csv", crear_nodos=False)["rechazados"] == []
    assert r.validar() == []
    return r.grafo


def red(*conexiones, **tipos):
    """Red mínima: conexiones (origen, destino, atributos); el tipo de cada nodo sale de su letra."""
    letras = {"T": "tarjeta", "D": "dispositivo", "M": "comercio", "C": "cuenta", "B": "billetera"}
    r = GestionRed(multi=True)
    for i, (o, d, at) in enumerate(conexiones):
        for n in (o, d):
            if not r.grafo.tiene_nodo(n):
                r.agregar_nodo(n, letras[n[0]])
        r.agregar_arista(o, d, id=str(i), **at)
    return r.grafo


def test_carga_de_datos(g):
    assert (g.n_nodos, g.n_aristas) == (173, 263)


def test_tarjetas_en_un_mismo_dispositivo(g):
    h = tarjetas_por_dispositivo(g)
    assert [x["elementos"] for x in h] == [["D900", "T901", "T902", "T903", "T904", "T905"]]
    assert len(tarjetas_por_dispositivo(g, min_tarjetas=2)) > 1       # con 2 aparecen los dispositivos familiares


def test_dispositivo_y_cuenta_en_comun(g):
    h = dispositivo_con_cuenta_comun(g)
    assert [x["elementos"][:2] for x in h] == [["D900", "C900"]] and len(h[0]["relaciones"]) == 5


def test_una_tarjeta_en_muchos_dispositivos(g):
    assert [x["elementos"][0] for x in dispositivos_por_tarjeta(g)] == ["T910"]


def test_cuenta_concentradora(g):
    h = cuentas_concentradoras(g)
    assert len(h) == 1 and h[0]["elementos"][0] == "C930" and "12 tarjetas" in h[0]["detalle"]


def test_rafaga_de_pagos(g):
    h = rafagas_de_pagos(g)
    assert len(h) == 1 and h[0]["elementos"] == ["T920", "M907"] and h[0]["detalle"].startswith("8 pagos en 7 min")
    assert rafagas_de_pagos(g, ventana_min=3, min_pagos=8) == []


def test_las_alertas_son_exactamente_los_cuatro_escenarios_plantados(g):
    h = analizar_carding(g)
    assert sorted(x["tipo"] for x in h) == sorted([
        "Varias tarjetas en un mismo dispositivo", "Tarjetas del mismo dispositivo terminan en la misma cuenta",
        "Una tarjeta en muchos dispositivos", "Cuenta que concentra varios comercios", "Ráfaga de pagos"])
    implicados = {e for x in h for e in x["elementos"]}
    assert all(int(e[1:]) >= 900 for e in implicados)        # ningún elemento de la actividad normal


def test_dfs_hasta_billetera(g):
    assert caminos_hasta(g, "T901") == [["T901", "M901", "C900", "B900"], ["T901", "M902", "C900", "B900"]]
    assert caminos_hasta(g, "B900") == []


def test_ficha_de_una_tarjeta_con_bfs(g):
    c = consultar(g, "T901")
    assert c["niveles"][1] == ["D900", "M901", "M902"] and "T902" in c["niveles"][2] and c["niveles"][3] == ["B900"]
    assert [a["tipo"] for a in c["alertas"]] == ["Varias tarjetas en un mismo dispositivo",
                                                 "Tarjetas del mismo dispositivo terminan en la misma cuenta"]
    assert "FICHA DE T901" in reporte_consulta(c)
    assert consultar(g, "T001")["alertas"] == []


def test_reporte_con_aviso_y_evidencia(g):
    t = reporte(analizar_carding(g))
    assert "no significan que una persona haya cometido fraude" in t and "T901 -> D900" in t and "C930" in t


def test_casos_borde():
    assert analizar_carding(red()) == [] and "No se encontraron" in reporte([])
    # dos tarjetas en un dispositivo no alcanzan el umbral de 3
    pocas = red(("T1", "D1", {}), ("T2", "D1", {}))
    assert tarjetas_por_dispositivo(pocas) == []
    # ciclo de dinero: se detecta como complementario
    ciclo = red(("C1", "C2", {"monto": 100}), ("C2", "C3", {"monto": 100}), ("C3", "C1", {"monto": 100}))
    assert [x["tipo"] for x in analizar_carding(ciclo)] == ["Ciclo de movimientos"]
    # fecha mal escrita no rompe la búsqueda de ráfagas
    mala = red(*[("T1", "M1", {"tipo": "pago", "monto": 5, "fecha": "ayer"}) for _ in range(1)])
    assert rafagas_de_pagos(mala) == []


def test_simulacion_de_ataque_por_oleadas(g):
    r = simular_ataque(g, ["T901"])
    assert r["pasos"][0]["nodos"] == ["M902", "D900", "M901"] or set(r["pasos"][0]["nodos"]) == {"M901", "M902", "D900"}
    assert [set(p["nodos"]) for p in r["pasos"][1:]] == [{"C900"}, {"B900"}]       # comercio -> cuenta -> billetera
    assert r["billeteras"] == ["B900"] and r["alcanzados"] == 6 and r["total"] == g.n_nodos
    assert r["monto"] > 0 and "Billeteras alcanzadas: B900" in reporte_simulacion(r)
    assert all(u in r["visto"] and v in r["visto"] for p in r["pasos"] for u, v in p["aristas"])


def test_simulacion_sin_salida_varias_fuentes_y_limite(g):
    assert simular_ataque(g, ["B900"])["pasos"] == []                    # una billetera no envía a nadie
    assert "no sale dinero" in reporte_simulacion(simular_ataque(g, ["B900"]))
    dos = simular_ataque(g, ["T901", "T902"])
    assert dos["fuentes"] == ["T901", "T902"] and dos["alcanzados"] >= simular_ataque(g, ["T901"])["alcanzados"]
    assert len(simular_ataque(g, ["T901"], max_pasos=1)["pasos"]) == 1
    with pytest.raises(Exception):
        simular_ataque(g, ["NO_EXISTE"])


def test_simulacion_en_red_minima():
    h = red(("T1", "M1", {"tipo": "pago", "monto": 10}), ("T1", "M1", {"tipo": "pago", "monto": 5}),
            ("M1", "C1", {"tipo": "liquidacion", "monto": 15}), ("C1", "B1", {"tipo": "transferencia"}))
    r = simular_ataque(h, ["T1"])
    assert [p["aristas"] for p in r["pasos"]] == [[("T1", "M1")], [("M1", "C1")], [("C1", "B1")]]
    assert r["monto"] == 15                                              # los dos pagos cuentan, aunque sea una sola conexión dibujada
