"""Módulo 1: gestión y modelamiento de redes financieras.

Envuelve a Grafo con validaciones (nodos válidos, valores numéricos, duplicados) y
carga/guarda redes en CSV, TXT y JSON. Los demás módulos usan self.grafo.
"""
import csv
import json

from src.graph import Grafo, GrafoError
from src.utils import a_numero

TIPOS_NODO = {"cuenta", "cliente", "tarjeta", "dispositivo", "comercio", "billetera", "agencia", "boveda_central", "boveda_regional", "atm",
              "entidad", "plataforma", "agente", "compensacion", "servidor"}
# Atributos numéricos de las conexiones y su rango válido (mínimo, máximo)
NUMERICOS = {"comision": (0, None), "comision_pct": (0, 100), "costo": (0, None), "tiempo": (0, None), "capacidad": (0, None),
             "limite": (0, None), "monto": (0, None), "disponible": (0, None), "demanda": (0, None), "riesgo": (0, 1), "peso": (0, None)}


class GestionRed:
    def __init__(self, dirigido=True, ponderado=True, multi=False):
        self.grafo = Grafo(dirigido, ponderado, multi)

    # ------------------------------------------------------------------ nodos
    def agregar_nodo(self, nodo, tipo="cuenta", **atributos):
        nodo = str(nodo).strip()
        if not nodo:
            raise GrafoError("El nodo necesita un identificador")
        self._validar_tipo(tipo)
        self.grafo.agregar_nodo(nodo, tipo, **self._limpiar(atributos))

    def modificar_nodo(self, nodo, **atributos):
        if "tipo" in atributos:
            self._validar_tipo(atributos["tipo"])
        self.grafo.modificar_nodo(nodo, **self._limpiar(atributos))

    def eliminar_nodo(self, nodo):
        self.grafo.eliminar_nodo(nodo)

    # ----------------------------------------------------------------- aristas
    def agregar_arista(self, origen, destino, **atributos):
        if origen == destino:
            raise GrafoError(f"Una conexión no puede unir un nodo consigo mismo ({origen})")
        atributos = self._limpiar(atributos)
        if self.grafo.multi and any(a.atributos == atributos for a in self.grafo.obtener_aristas(origen, destino)):
            raise GrafoError(f"Conexión duplicada {origen} -> {destino} con los mismos datos")
        return self.grafo.agregar_arista(origen, destino, **atributos)

    def modificar_arista(self, origen, destino, **atributos):
        self.grafo.modificar_arista(origen, destino, **self._limpiar(atributos))

    def eliminar_arista(self, origen, destino):
        self.grafo.eliminar_arista(origen, destino)

    # ------------------------------------------------------------ validaciones
    @staticmethod
    def _validar_tipo(tipo):
        if tipo not in TIPOS_NODO:
            raise GrafoError(f"Tipo de nodo inválido '{tipo}'. Válidos: {', '.join(sorted(TIPOS_NODO))}")

    @staticmethod
    def _limpiar(atributos):
        """Convierte los atributos numéricos y comprueba su rango; ignora valores vacíos."""
        limpio = {}
        for clave, valor in atributos.items():
            if valor is None or valor == "":
                continue
            if clave in NUMERICOS:
                valor = a_numero(valor, clave)
                minimo, maximo = NUMERICOS[clave]
                if valor < minimo or (maximo is not None and valor > maximo):
                    rango = f"entre {minimo} y {maximo}" if maximo is not None else f"mayor o igual a {minimo}"
                    raise GrafoError(f"'{clave}' debe ser {rango} y es {valor:g}")
            limpio[clave] = valor
        return limpio

    def validar(self):
        """Revisa toda la red. Devuelve una lista de problemas (vacía = red consistente)."""
        g, problemas = self.grafo, []
        vistos = set()
        for a in g.aristas():
            if a.origen not in g.nodos or a.destino not in g.nodos:
                problemas.append(f"Conexión con nodo inexistente: {a.origen} -> {a.destino}")
            if a.origen == a.destino:
                problemas.append(f"Bucle en {a.origen}")
            try:
                self._limpiar(a.atributos)
            except GrafoError as e:
                problemas.append(f"Conexión {a.origen} -> {a.destino}: {e}")
            clave = (a.origen, a.destino, tuple(sorted(a.atributos.items(), key=str)))
            if clave in vistos:
                problemas.append(f"Conexión duplicada {a.origen} -> {a.destino}")
            vistos.add(clave)
        for n, attrs in g.nodos.items():
            if attrs.get("tipo") not in TIPOS_NODO:
                problemas.append(f"Nodo {n} con tipo inválido '{attrs.get('tipo')}'")
            if g.grado_salida(n) + g.grado_entrada(n) == 0:
                problemas.append(f"Nodo aislado: {n}")
        return problemas

    def resumen(self):
        g = self.grafo
        tipos = {}
        for attrs in g.nodos.values():
            tipos[attrs["tipo"]] = tipos.get(attrs["tipo"], 0) + 1
        return {"nodos": g.n_nodos, "aristas": g.n_aristas, "dirigido": g.dirigido,
                "ponderado": g.ponderado, "multi": g.multi, "tipos": tipos}

    # ------------------------------------------------------------------- carga
    def cargar_nodos(self, ruta):
        """CSV/TXT con columnas id,tipo,... Devuelve {"cargados": n, "rechazados": [(linea, motivo)]}."""
        informe = {"cargados": 0, "rechazados": []}
        for linea, fila, error in _leer_tabla(ruta, obligatorias=("id",)):
            try:
                if error:
                    raise GrafoError(error)
                self.agregar_nodo(fila.pop("id"), fila.pop("tipo", "cuenta") or "cuenta", **fila)
                informe["cargados"] += 1
            except GrafoError as e:
                informe["rechazados"].append((linea, str(e)))
        return informe

    def cargar_aristas(self, ruta, crear_nodos=True, tipo_nuevos="cuenta"):
        """CSV/TXT con columnas origen,destino,... (el resto son atributos).
        Si crear_nodos es False, los nodos inexistentes se rechazan."""
        informe = {"cargados": 0, "rechazados": []}
        for linea, fila, error in _leer_tabla(ruta, obligatorias=("origen", "destino")):
            try:
                if error:
                    raise GrafoError(error)
                o, d = fila.pop("origen"), fila.pop("destino")
                for n in (o, d):
                    if not self.grafo.tiene_nodo(n):
                        if not crear_nodos:
                            raise GrafoError(f"El nodo '{n}' no existe")
                        self.agregar_nodo(n, tipo_nuevos)
                self.agregar_arista(o, d, **fila)
                informe["cargados"] += 1
            except GrafoError as e:
                informe["rechazados"].append((linea, str(e)))
        return informe

    def cargar_json(self, ruta):
        """Reemplaza la red actual por la del JSON {dirigido, ponderado, multi, nodos[], aristas[]}."""
        with open(ruta, encoding="utf-8") as f:
            datos = json.load(f)
        self.grafo = Grafo(datos.get("dirigido", True), datos.get("ponderado", True), datos.get("multi", False))
        informe = {"cargados": 0, "rechazados": []}
        for i, n in enumerate(datos.get("nodos", []), 1):
            try:
                n = dict(n)
                self.agregar_nodo(n.pop("id"), n.pop("tipo", "cuenta"), **n)
                informe["cargados"] += 1
            except (GrafoError, KeyError) as e:
                informe["rechazados"].append((f"nodo {i}", str(e)))
        for i, a in enumerate(datos.get("aristas", []), 1):
            try:
                a = dict(a)
                self.agregar_arista(a.pop("origen"), a.pop("destino"), **a)
                informe["cargados"] += 1
            except (GrafoError, KeyError) as e:
                informe["rechazados"].append((f"arista {i}", str(e)))
        return informe

    def guardar_json(self, ruta):
        g = self.grafo
        datos = {"dirigido": g.dirigido, "ponderado": g.ponderado, "multi": g.multi,
                 "nodos": [{"id": n, **attrs} for n, attrs in g.nodos.items()],
                 "aristas": [{"origen": a.origen, "destino": a.destino, **a.atributos} for a in g.aristas()]}
        with open(ruta, "w", encoding="utf-8") as f:
            json.dump(datos, f, indent=2, ensure_ascii=False)

    def guardar_aristas_csv(self, ruta):
        columnas = sorted({k for a in self.grafo.aristas() for k in a.atributos})
        with open(ruta, "w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["origen", "destino", *columnas])
            for a in self.grafo.aristas():
                w.writerow([a.origen, a.destino, *[a.atributos.get(c, "") for c in columnas]])


def _leer_tabla(ruta, obligatorias):
    """Lee CSV o TXT (separado por coma, punto y coma, tabulador o espacios).
    Devuelve [(línea, {columna: valor}, motivo_de_error_o_None)]. Las líneas con # se ignoran."""
    with open(ruta, encoding="utf-8-sig") as f:
        lineas = [(i, t.strip()) for i, t in enumerate(f, 1) if t.strip() and not t.lstrip().startswith("#")]
    if not lineas:
        return []
    sep = next((s for s in (",", ";", "\t") if s in lineas[0][1]), None)

    def partir(texto):
        if sep is None:
            return texto.split()
        return [c.strip() for c in next(csv.reader([texto], delimiter=sep))]

    cabecera = [c.lower() for c in partir(lineas[0][1])]
    faltan = [c for c in obligatorias if c not in cabecera]
    if faltan:
        raise GrafoError(f"Al archivo {ruta} le faltan las columnas: {', '.join(faltan)}")
    filas = []
    for i, texto in lineas[1:]:
        celdas = partir(texto)
        motivo = None if len(celdas) == len(cabecera) else \
            f"se esperaban {len(cabecera)} columnas y hay {len(celdas)}"
        filas.append((i, dict(zip(cabecera, celdas)), motivo))
    return filas
