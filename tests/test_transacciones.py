import pytest

from src.analisis_transacciones import (analizar, cadenas_de_paso, ciclos, componentes_fuertes,
                                        dispersion_concentracion, fragmentacion, proximidad,
                                        rastrear_fondos, relaciones_directas, reporte)
from src.gestion_red import GestionRed


@pytest.fixture(scope="module")
def g():
    r = GestionRed(multi=True)
    informe = r.cargar_aristas("data/movimientos_cuentas.csv")
    assert informe["rechazados"] == []
    return r.grafo


def red(*transferencias):
    r = GestionRed(multi=True)
    for i, (o, d, m) in enumerate(transferencias):
        for n in (o, d):
            if not r.grafo.tiene_nodo(n):
                r.agregar_nodo(n)
        r.agregar_arista(o, d, monto=m, id=str(i))
    return r.grafo


def test_carga_de_datos(g):
    assert g.n_aristas == 154


def test_circulacion_detectada(g):
    assert componentes_fuertes(g, monto_min=5000) == [["R1", "R2", "R3", "R4"]]
    c = ciclos(g)
    assert len(c) == 1 and c[0]["cuentas"] == ["R1", "R2", "R3", "R4"]
    assert c[0]["monto_min"] == pytest.approx(18360)  # dos vueltas por el tramo R4 -> R1


def test_fragmentacion_detectada(g):
    f = fragmentacion(g)
    assert [(x["origen"], x["destino"], x["operaciones"]) for x in f] == [("F01", "F02", 12)]


def test_dispersion_concentracion_detectada(g):
    d = dispersion_concentracion(g)
    assert len(d) == 1 and (d[0]["origen"], d[0]["destino"]) == ("O1", "D1")
    assert d[0]["intermediarios"] == ["M1", "M2", "M3", "M4", "M5"]


def test_cadena_de_paso_detectada(g):
    assert [c["cuentas"] for c in cadenas_de_paso(g)] == [["S1", "P1", "P2", "P3", "T1"]]


def test_sin_falsos_positivos_en_cuentas_normales(g):
    implicadas = {c for h in analizar(g) for c in h["cuentas"]}
    assert not any(c.startswith("C") for c in implicadas)


def test_proximidad_y_relaciones(g):
    n = proximidad(g, "O1")
    assert (n["O1"], n["M3"], n["D1"]) == (0, 1, 2)
    assert "M3" not in proximidad(g, "S1")
    rel = relaciones_directas(g, "F01")
    assert list(rel["envia_a"]) == ["F02"] and rel["recibe_de"] == {}


def test_rastreo_de_fondos(g):
    r = rastrear_fondos(g, "S1")
    assert r["caminos"]["T1"] == ["S1", "P1", "P2", "P3", "T1"]
    assert r["intermediarios"] == ["P1", "P2", "P3"] and r["receptoras_finales"] == ["T1"]


def test_sin_filtro_de_monto_la_red_normal_si_tiene_circulacion(g):
    """Justifica el filtro por monto: con montos chicos casi toda red tiene ciclos normales."""
    assert len(componentes_fuertes(g)[0]) > 20


def test_casos_borde():
    vacio = red()
    assert analizar(vacio) == [] and "No se encontraron" in reporte([])
    lineal = red(("A", "B", 10), ("B", "C", 10))
    assert componentes_fuertes(lineal) == [] and ciclos(lineal) == []
    ida_y_vuelta = red(("A", "B", 10000), ("B", "A", 9000))
    assert ciclos(ida_y_vuelta)[0]["monto_min"] == 9000
    assert ciclos(red(("A", "B", 10000), ("B", "A", 1000))) == []   # el dinero no vuelve casi intacto


def test_reporte_incluye_aviso_y_cuentas(g):
    texto = reporte(analizar(g))
    assert "no prueban fraude" in texto and "F01 -> F02" in texto and "S1 -> P1 -> P2 -> P3 -> T1" in texto
