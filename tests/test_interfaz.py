"""Prueba de humo de la interfaz. Se omite si no hay pantalla (en Linux: xvfb-run python -m pytest)."""
import pytest

tk = pytest.importorskip("tkinter")
from src import interfaz


@pytest.fixture
def app(monkeypatch):
    errores = []
    monkeypatch.setattr(interfaz.messagebox, "showerror", lambda t, m: errores.append(m))
    try:
        a = interfaz.App()
    except tk.TclError:
        pytest.skip("no hay pantalla disponible")
    a.errores = errores
    a.update()
    yield a
    a.destroy()


def test_parsear_atributos_y_relaciones():
    assert interfaz.parsear_atributos("comision=4.5, canal = ACH") == {"comision": "4.5", "canal": "ACH"}
    assert interfaz.parsear_atributos("") == {}
    with pytest.raises(ValueError):
        interfaz.parsear_atributos("sin_igual")
    assert interfaz.pares_de_relaciones(["T1 -> M1 -> C1 (5 a las 10:00)", "D1 -> M2"]) == {("T1", "M1"), ("M1", "C1"), ("D1", "M2")}


def test_analisis_de_carding_en_la_interfaz(app):
    app.analizar_carding()
    assert len(app.lista.get_children()) == 5
    app.lista.selection_set("0")
    app.update()
    assert "D900" in app.resalte["nodos"]
    app.v_ficha.set("T901")
    app.ficha()
    assert "FICHA DE T901" in app.salida_carding.get("1.0", "end") and app.resalte["nodos"]
    app.resaltar()
    assert app.resalte == {}


def test_modulo_1_agregar_modificar_eliminar_y_errores(app):
    n = app.g.n_nodos
    app.v_nodo.set("T999")
    app.v_tipo.set("tarjeta")
    app.agregar_nodo()
    assert app.g.n_nodos == n + 1 and app.errores == []
    app.agregar_nodo()                                                  # duplicado
    assert len(app.errores) == 1
    app.v_o.set("T999")
    app.v_d.set("M001")
    app.v_attr_arista.set("tipo=pago, monto=-5")
    app.agregar_arista()                                                # monto inválido
    assert len(app.errores) == 2 and not app.g.tiene_arista("T999", "M001")
    app.v_attr_arista.set("tipo=pago, monto=50")
    app.agregar_arista()
    assert app.g.tiene_arista("T999", "M001")
    app.eliminar_nodo()
    assert not app.g.tiene_nodo("T999")


def test_enrutamiento_liquidez_y_evaluacion(app):
    app.pestanas.select(2)
    app.update()
    assert app.nombre.get() == "Enrutamiento"
    app.comparar_rutas()
    assert "ahorra" in app.salida_enr.get("1.0", "end") and app.resalte["aristas"]
    app.v_monto.set("abc")
    app.comparar_rutas()
    assert app.errores
    app.pestanas.select(3)
    app.update()
    app.planificar()
    assert "FALTAN 10,000" in app.salida_liq.get("1.0", "end") and "Ag-Sicuani" in app.resalte["nodos"]
    app.evaluar()
    assert "22/22 casos correctos" in app.salida_ev.get("1.0", "end")


def test_clic_en_nodo_y_zoom(app):
    pos = app._posiciones()
    x, y = app._xy(pos, "T901")
    assert app.nodo_en(x, y) == "T901"
    app.seleccionar("T901")
    assert app.v_ficha.get() == "T901"
    antes = app.escala
    app._zoom(100, 100, 1.5)
    assert app.escala == pytest.approx(antes * 1.5)


class Ev:
    """Evento de mouse mínimo."""
    def __init__(self, x, y):
        self.x, self.y = x, y


def test_hover_clic_arrastre_y_leyenda(app):
    x, y = app._xy(app._posiciones(), "T901")
    app._mover(Ev(x, y))
    assert app.hover == "T901"
    app._tick()                                                         # el nodo se agranda suavemente
    assert app._anim["T901"] > 0
    app._presionar(Ev(x, y))
    app._soltar(Ev(x, y))
    assert app.sel == "T901"
    app._presionar(Ev(x, y))                                            # arrastrar el nodo lo mueve
    app._arrastrar(Ev(x + 40, y + 25))
    app._soltar(Ev(x + 40, y + 25))
    assert app._xy(app._posiciones(), "T901") == pytest.approx((x + 40, y + 25))
    x0, y0, _, _, tipo = app._leyenda[0]
    app._presionar(Ev(x0 + 5, y0 + 5))
    app._soltar(Ev(x0 + 5, y0 + 5))
    assert app.resalte["filtro"] == tipo
    app.limpiar()
    assert app.resalte == {} and app.sel is None


def test_simulacion_de_ataque_animada(app):
    app.simular_ataque(["T901"])
    assert app.sim and app.sim["comp"] == {"T901"}
    for _ in range(400):                                                # avanza la animación sin esperar tiempo real
        app._avanzar_sim(0.1)
        app._superponer(0)
        if app.sim["fin"]:
            break
    assert app.sim["fin"] and {"D900", "C900", "B900"} <= app.sim["comp"]
    assert "T901" in app.salida_carding.get("1.0", "end")
    app.pausar_sim()                                                    # al terminar, "pausar" reinicia
    assert not app.sim["fin"] and app.sim["comp"] == {"T901"}
    app.simular_ataque(["B900"])                                        # una billetera no envía dinero: no arranca otra
    assert app.sim["res"]["fuentes"] == ["T901"]
    app.limpiar()
    assert app.sim is None
