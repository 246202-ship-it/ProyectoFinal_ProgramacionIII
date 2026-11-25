import pytest

from src.enrutamiento_financiero import (alternativas, evaluar_ruta, matriz_costos, peso, reporte_comparativo,
                                         ruta_optima, texto_ruta)
from src.gestion_red import GestionRed


@pytest.fixture(scope="module")
def g():
    r = GestionRed()
    assert r.cargar_json("data/red_enrutamiento.json")["rechazados"] == []
    return r.grafo


def canales(g, monto, criterio, algoritmo="dijkstra"):
    valor, ruta = ruta_optima(g, "BancoA", "BancoC", criterio, monto, algoritmo)
    return valor, texto_ruta(ruta)


def test_menor_comision_monto_1000(g):
    assert canales(g, 1000, "comision") == (pytest.approx(4.5), "BancoA -[ACH]-> CCE -[ACH]-> BancoC")


def test_menor_tiempo_monto_1000_usa_billetera(g):
    valor, ruta = canales(g, 1000, "tiempo")
    assert valor == pytest.approx(0.3) and "Billetera" in ruta


def test_comision_porcentual_depende_del_monto(g):
    billetera = [a for a in g.vecinos("BancoA") if a.atributos["canal"] == "Billetera"][0]
    assert peso(billetera, "comision", 1000) == pytest.approx(5.0) and peso(billetera, "comision", 200) == pytest.approx(1.0)


def test_el_limite_transaccional_descarta_canales(g):
    assert canales(g, 5000, "tiempo") == (pytest.approx(1.0), "BancoA -[LBTR]-> LBTR -[LBTR]-> BancoC")
    valor, ruta = canales(g, 100000, "comision")
    assert valor == pytest.approx(25.0) and "LBTR" in ruta
    assert len(alternativas(g, "BancoA", "BancoC", "comision", 100000)) == 1


def test_sin_ruta_si_el_monto_supera_todos_los_limites(g):
    assert ruta_optima(g, "BancoA", "BancoC", "comision", 6_000_000) is None
    assert alternativas(g, "BancoA", "BancoC", "comision", 6_000_000) == []
    assert "No hay ninguna ruta" in reporte_comparativo(g, "BancoA", "BancoC", 6_000_000)


def test_canal_fuera_de_servicio_no_se_usa(g):
    for monto in (100, 1000, 40000):
        for _, ruta in alternativas(g, "BancoA", "BancoC", "comision", monto):
            assert not (len(ruta) == 1 and ruta[0].atributos["canal"] == "Directo")


@pytest.mark.parametrize("criterio", ["comision", "tiempo", "costo", "riesgo", "total", {"comision": 1, "tiempo": 0.5}])
@pytest.mark.parametrize("monto", [100, 1000, 5000, 100000])
def test_dijkstra_y_bellman_ford_coinciden(g, criterio, monto):
    for destino in ("BancoB", "BancoC", "AgenciaCusco"):
        d = ruta_optima(g, "BancoA", destino, criterio, monto, "dijkstra")
        b = ruta_optima(g, "BancoA", destino, criterio, monto, "bellman-ford")
        assert (d is None) == (b is None)
        if d:
            assert d[0] == pytest.approx(b[0])


def test_la_primera_alternativa_es_la_optima(g):
    for criterio in ("comision", "tiempo", "riesgo"):
        alts = alternativas(g, "BancoA", "BancoC", criterio, 1000)
        assert alts[0][0] == pytest.approx(ruta_optima(g, "BancoA", "BancoC", criterio, 1000)[0])
        assert [v for v, _ in alts] == sorted(v for v, _ in alts)


def test_cantidad_de_alternativas(g):
    assert len(alternativas(g, "BancoA", "BancoC", "comision", 1000)) == 9
    assert len(alternativas(g, "BancoA", "BancoC", "comision", 1000, max_saltos=2)) == 6


def test_evaluar_ruta(g):
    _, ruta = ruta_optima(g, "BancoA", "BancoC", "comision", 1000)
    m = evaluar_ruta(ruta, 1000)
    assert (m["saltos"], round(m["comision"], 2), m["tiempo"], round(m["riesgo"], 4)) == (2, 4.5, 27, 0.0298)


def test_interplaza_y_matriz(g):
    valor, ruta = ruta_optima(g, "AgenciaLima", "AgenciaCusco", "comision", 500)
    assert valor == 5 and ruta[0].atributos["canal"] == "Interplaza"
    m = matriz_costos(g, ["BancoA", "BancoC", "AgenciaCusco"], "comision", 1000)
    assert m["BancoA"]["BancoC"] == pytest.approx(4.5) and m["BancoC"]["BancoA"] is None
    assert m["BancoA"]["AgenciaCusco"] == pytest.approx(6.5)   # por BancoC (4.5 + 2), más barato que por AgenciaLima (7)


def test_origen_igual_a_destino_y_criterio_invalido(g):
    assert ruta_optima(g, "BancoA", "BancoA", "comision", 100) == (0.0, [])
    with pytest.raises(ValueError):
        ruta_optima(g, "BancoA", "BancoC", "magia", 100)


def test_reporte(g):
    t = reporte_comparativo(g, "BancoA", "BancoC", 1000)
    assert "Mejor ruta por criterio" in t and "9 en total" in t and "ahorra 35.50" in t
