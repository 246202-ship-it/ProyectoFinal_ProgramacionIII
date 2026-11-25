import math

import pytest

from src.distribucion_liquidez import planificar
from src.enrutamiento_financiero import alternativas, ruta_optima
from src.evaluacion_resultados import (casos_de_prueba, ejecutar_todo, exponente, generar_red_enrutamiento,
                                       generar_red_liquidez, generar_transacciones, guardar_csv, medir,
                                       reporte_evaluacion, verificar_plan, verificar_ruta)


def test_todos_los_casos_de_prueba_pasan():
    fallas = [c[:4] for c in casos_de_prueba() if not c[4]]
    assert fallas == []


def test_exponente_de_funciones_conocidas():
    ns = [100, 200, 400, 800]
    assert exponente(ns, [n for n in ns]) == pytest.approx(1.0)
    assert exponente(ns, [n ** 2 for n in ns]) == pytest.approx(2.0)


def test_medir_devuelve_resultado_tiempo_y_memoria():
    r, t, kib = medir(lambda: [0] * 100000, repeticiones=2)
    assert len(r) == 100000 and t > 0 and kib > 500


def test_generadores_son_reproducibles_y_del_tamano_pedido():
    a, b = generar_red_enrutamiento(50, semilla=3), generar_red_enrutamiento(50, semilla=3)
    assert a.n_nodos == 50 and a.n_aristas == b.n_aristas == 49 + 150
    assert generar_red_liquidez(4).n_nodos == 4 + 12 + 2
    assert generar_transacciones(30).n_aristas == 120


def test_verificar_ruta_detecta_violaciones():
    g = generar_red_enrutamiento(40)
    _, ruta = ruta_optima(g, "N0", "N30", "comision", 1000)
    assert verificar_ruta(g, ruta, "N0", "N30", 1000) == []
    assert verificar_ruta(g, ruta, "N0", "N31", 1000)                  # no termina en el destino
    assert verificar_ruta(g, ruta[1:], "N0", "N30", 1000)              # discontinua
    ruta[0].atributos["limite"] = 10
    assert any("no disponible" in e for e in verificar_ruta(g, ruta, "N0", "N30", 1000))


def test_verificar_plan_detecta_violaciones():
    g = generar_red_liquidez(5)
    plan = planificar(g)
    assert verificar_plan(g, plan) == []
    o, d, f, cap, c = plan["usado"][0]
    plan["usado"][0] = (o, d, cap * 2, cap, c)
    assert any("excede su capacidad" in e for e in verificar_plan(g, plan))


@pytest.mark.parametrize("n", [20, 60])
def test_dijkstra_y_bellman_ford_dan_el_mismo_costo_en_redes_grandes(n):
    g = generar_red_enrutamiento(n, semilla=n)
    for destino in (f"N{n // 2}", f"N{n - 1}"):
        d = ruta_optima(g, "N0", destino, "comision", 1000, "dijkstra")
        b = ruta_optima(g, "N0", destino, "comision", 1000, "bellman-ford")
        assert d[0] == pytest.approx(b[0])
        assert d[0] == pytest.approx(alternativas(g, "N0", destino, "comision", 1000, max_saltos=n)[0][0]) if n <= 20 else True


def test_ejecucion_rapida_y_reporte():
    res = ejecutar_todo(rapido=True)
    assert all(f["iguales"] for f in res["enrutamiento"]) and all(f["iguales"] and f["valido"] for f in res["flujo"])
    assert all(f["costo_minimo"] <= f["costo_dinic"] + 1e-6 for f in res["flujo"])
    texto = reporte_evaluacion(res)
    assert "22/22 casos correctos" in texto and "Conclusiones" in texto and not math.isnan(res["enrutamiento"][0]["factor"])


def test_guardar_csv(tmp_path):
    guardar_csv(ejecutar_todo(rapido=True)["transacciones"], tmp_path / "t.csv")
    assert (tmp_path / "t.csv").read_text(encoding="utf-8").splitlines()[0] == "cuentas,transferencias,ms,kib,hallazgos"
