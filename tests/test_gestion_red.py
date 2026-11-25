import pytest

from src.graph import GrafoError
from src.gestion_red import GestionRed

DATOS = "data/"


def test_cargar_csv_del_enunciado():
    r = GestionRed()
    informe = r.cargar_aristas(DATOS + "ejemplo_aristas.csv")
    assert (informe["cargados"], informe["rechazados"]) == (3, [])
    assert r.resumen()["nodos"] == 4
    assert r.grafo.obtener_aristas("CuentaB", "CuentaD")[0].atributos["comision"] == 5.1


def test_cargar_json_mixto_es_consistente():
    r = GestionRed()
    informe = r.cargar_json(DATOS + "red_mixta.json")
    assert informe["rechazados"] == []
    assert r.validar() == []
    assert r.resumen()["tipos"]["agencia"] == 2


def test_csv_con_errores_rechaza_solo_las_filas_malas(tmp_path):
    f = tmp_path / "malo.csv"
    f.write_text("origen,destino,comision\nA,B,4.5\nA,B,3\nA,C,abc\nA,D,-1\nA,A,1\nA,E\n", encoding="utf-8")
    r = GestionRed()
    informe = r.cargar_aristas(f)
    assert informe["cargados"] == 1
    assert [l for l, _ in informe["rechazados"]] == [3, 4, 5, 6, 7]


def test_no_crear_nodos_rechaza_inexistentes(tmp_path):
    f = tmp_path / "a.csv"
    f.write_text("origen,destino\nA,B\n", encoding="utf-8")
    r = GestionRed()
    r.agregar_nodo("A")
    informe = r.cargar_aristas(f, crear_nodos=False)
    assert informe["cargados"] == 0 and "no existe" in informe["rechazados"][0][1]


def test_txt_con_espacios_y_punto_y_coma(tmp_path):
    for nombre, texto in (("a.txt", "origen destino comision\nA B 2.5\n"), ("b.txt", "origen;destino;comision\nA;B;2,5\n")):
        f = tmp_path / nombre
        f.write_text(texto, encoding="utf-8")
        r = GestionRed()
        assert r.cargar_aristas(f)["cargados"] == 1
        assert r.grafo.obtener_aristas("A", "B")[0].atributos["comision"] == 2.5


def test_valores_invalidos():
    r = GestionRed()
    r.agregar_nodo("A"); r.agregar_nodo("B")
    for attrs in ({"riesgo": 1.5}, {"comision": -2}, {"tiempo": "rapido"}):
        with pytest.raises(GrafoError):
            r.agregar_arista("A", "B", **attrs)
    with pytest.raises(GrafoError):
        r.agregar_nodo("X", "marciano")


def test_modificar_y_eliminar():
    r = GestionRed()
    r.cargar_json(DATOS + "red_mixta.json")
    r.modificar_arista("Cta-001", "CCE", comision="4.0")
    assert r.grafo.obtener_aristas("Cta-001", "CCE")[0].atributos["comision"] == 4.0
    r.modificar_nodo("ATM-01", ciudad="Wanchaq")
    r.eliminar_nodo("CCE")
    assert not r.grafo.tiene_nodo("CCE") and not r.grafo.tiene_arista("Cta-001", "CCE")
    assert r.validar() == []  # ningún nodo quedó aislado


def test_validar_detecta_nodo_aislado():
    r = GestionRed()
    r.agregar_nodo("Solo")
    assert r.validar() == ["Nodo aislado: Solo"]


def test_multigrafo_rechaza_duplicado_exacto_pero_no_repetidas_distintas():
    r = GestionRed(multi=True)
    r.agregar_nodo("A"); r.agregar_nodo("B")
    r.agregar_arista("A", "B", monto=100)
    r.agregar_arista("A", "B", monto=200)
    with pytest.raises(GrafoError):
        r.agregar_arista("A", "B", monto=100)


def test_guardar_y_recargar_json(tmp_path):
    r = GestionRed()
    r.cargar_json(DATOS + "red_mixta.json")
    r.guardar_json(tmp_path / "copia.json")
    r2 = GestionRed()
    r2.cargar_json(tmp_path / "copia.json")
    assert r2.resumen() == r.resumen()
