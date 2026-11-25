import pytest

from src.graph import Grafo, GrafoError


def red():
    g = Grafo()
    for n in "ABCD":
        g.agregar_nodo(n)
    g.agregar_arista("A", "B", comision=4.5)
    g.agregar_arista("A", "C", comision=2.0)
    g.agregar_arista("B", "D", comision=5.1)
    return g


def test_conteos_y_grados():
    g = red()
    assert (g.n_nodos, g.n_aristas) == (4, 3)
    assert (g.grado_salida("A"), g.grado_entrada("D")) == (2, 1)


def test_vecinos_y_peso():
    assert [(a.destino, a.peso("comision")) for a in red().vecinos("A")] == [("B", 4.5), ("C", 2.0)]


def test_nodo_duplicado_y_arista_a_nodo_inexistente():
    g = red()
    with pytest.raises(GrafoError):
        g.agregar_nodo("A")
    with pytest.raises(GrafoError):
        g.agregar_arista("A", "Z")


def test_arista_duplicada_solo_en_simple():
    g = red()
    with pytest.raises(GrafoError):
        g.agregar_arista("A", "B")
    m = Grafo(multi=True)
    m.agregar_nodo("A"); m.agregar_nodo("B")
    m.agregar_arista("A", "B", monto=1); m.agregar_arista("A", "B", monto=2)
    assert m.n_aristas == 2


def test_eliminar_nodo_quita_sus_aristas():
    g = red()
    g.eliminar_nodo("B")
    assert (g.n_nodos, g.n_aristas, g.grado_entrada("D")) == (3, 1, 0)


def test_no_dirigido_es_simetrico_y_comparte_atributos():
    g = Grafo(dirigido=False)
    g.agregar_nodo("A"); g.agregar_nodo("B")
    g.agregar_arista("A", "B", costo=3)
    g.modificar_arista("B", "A", costo=9)
    assert g.obtener_aristas("A", "B")[0].atributos["costo"] == 9
    assert (g.n_aristas, len(list(g.aristas()))) == (1, 1)
    g.eliminar_arista("B", "A")
    assert (g.n_aristas, g.tiene_arista("A", "B")) == (0, False)


def test_invertido():
    inv = red().invertido()
    assert inv.tiene_arista("B", "A") and not inv.tiene_arista("A", "B")
