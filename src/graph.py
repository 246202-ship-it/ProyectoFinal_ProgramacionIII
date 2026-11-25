"""Estructura de datos común: grafo con lista de adyacencia.

- nodos: dict id -> atributos (siempre incluye "tipo").
- ady[u]: lista de Arista salientes de u. En grafos no dirigidos cada arista se guarda
  en ambos extremos compartiendo el mismo dict de atributos (modificar una modifica ambas).
- _pares[(u, v)]: aristas de u a v, para buscar duplicados y eliminar en O(1) promedio.

Complejidades (V nodos, E aristas): agregar nodo/arista O(1); buscar arista O(1);
vecinos(u) O(grado); eliminar arista O(grado(u)); eliminar nodo O(V + E); espacio O(V + E).
"""
from dataclasses import dataclass, field


class GrafoError(Exception):
    """Error de estructura o de datos de la red."""


@dataclass
class Arista:
    origen: str
    destino: str
    atributos: dict = field(default_factory=dict)

    def peso(self, clave="comision", defecto=1.0):
        """Valor de un atributo numérico (el peso depende del criterio: comisión, tiempo, costo...)."""
        return self.atributos.get(clave, defecto)


class Grafo:
    def __init__(self, dirigido=True, ponderado=True, multi=False):
        """multi=True permite varias aristas entre el mismo par (varias transferencias)."""
        self.dirigido, self.ponderado, self.multi = dirigido, ponderado, multi
        self.nodos = {}
        self.ady = {}
        self._pares = {}
        self._ent = {}
        self._m = 0

    # ------------------------------------------------------------------ nodos
    def agregar_nodo(self, nodo, tipo="cuenta", **atributos):
        if nodo in self.nodos:
            raise GrafoError(f"El nodo '{nodo}' ya existe")
        self.nodos[nodo] = {"tipo": tipo, **atributos}
        self.ady[nodo] = []
        self._ent[nodo] = 0

    def tiene_nodo(self, nodo):
        return nodo in self.nodos

    def obtener_nodo(self, nodo):
        self._exigir(nodo)
        return self.nodos[nodo]

    def modificar_nodo(self, nodo, **atributos):
        self._exigir(nodo)
        self.nodos[nodo].update(atributos)

    def eliminar_nodo(self, nodo):
        """Elimina el nodo y todas sus aristas. O(V + E)."""
        self._exigir(nodo)
        for u, v in [p for p in self._pares if nodo in p]:
            if (u, v) in self._pares:
                self.eliminar_arista(u, v)
        del self.nodos[nodo], self.ady[nodo], self._ent[nodo]

    # ----------------------------------------------------------------- aristas
    def agregar_arista(self, origen, destino, **atributos):
        self._exigir(origen)
        self._exigir(destino)
        if not self.multi and (origen, destino) in self._pares:
            raise GrafoError(f"Ya existe la conexión {origen} -> {destino}")
        arista = Arista(origen, destino, atributos)
        self._guardar(arista)
        if not self.dirigido and origen != destino:
            self._guardar(Arista(destino, origen, atributos))
        self._m += 1
        return arista

    def _guardar(self, arista):
        self.ady[arista.origen].append(arista)
        self._pares.setdefault((arista.origen, arista.destino), []).append(arista)
        self._ent[arista.destino] += 1

    def tiene_arista(self, origen, destino):
        return (origen, destino) in self._pares

    def obtener_aristas(self, origen, destino):
        return list(self._pares.get((origen, destino), []))

    def modificar_arista(self, origen, destino, **atributos):
        """Modifica todas las aristas entre el par (si hay varias en paralelo, todas)."""
        aristas = self.obtener_aristas(origen, destino)
        if not aristas:
            raise GrafoError(f"No existe la conexión {origen} -> {destino}")
        for a in aristas:
            a.atributos.update(atributos)

    def eliminar_arista(self, origen, destino):
        """Elimina todas las aristas entre el par (y la inversa si no es dirigido)."""
        if (origen, destino) not in self._pares:
            raise GrafoError(f"No existe la conexión {origen} -> {destino}")
        quitadas = self._quitar(origen, destino)
        if not self.dirigido and origen != destino:
            self._quitar(destino, origen)
        self._m -= quitadas

    def _quitar(self, u, v):
        n = len(self._pares.pop((u, v)))
        self.ady[u] = [a for a in self.ady[u] if a.destino != v]
        self._ent[v] -= n
        return n

    # ---------------------------------------------------------------- consultas
    def vecinos(self, nodo):
        """Aristas que salen de nodo."""
        self._exigir(nodo)
        return self.ady[nodo]

    def aristas(self):
        """Cada arista una sola vez (en no dirigidos se omite la copia espejo)."""
        for lista in self.ady.values():
            for a in lista:
                if self.dirigido or a.origen <= a.destino:
                    yield a

    @property
    def n_nodos(self):
        return len(self.nodos)

    @property
    def n_aristas(self):
        return self._m

    def grado_salida(self, nodo):
        return len(self.vecinos(nodo))

    def grado_entrada(self, nodo):
        self._exigir(nodo)
        return self._ent[nodo]

    def invertido(self):
        """Grafo con todas las aristas al revés (comparte los atributos)."""
        g = Grafo(self.dirigido, self.ponderado, self.multi)
        for n, attrs in self.nodos.items():
            g.agregar_nodo(n, **attrs)
        for a in self.aristas():
            g.agregar_arista(a.destino, a.origen, **a.atributos)
        return g

    def copia(self):
        g = Grafo(self.dirigido, self.ponderado, self.multi)
        for n, attrs in self.nodos.items():
            g.agregar_nodo(n, **attrs)
        for a in self.aristas():
            g.agregar_arista(a.origen, a.destino, **a.atributos)
        return g

    def _exigir(self, nodo):
        if nodo not in self.nodos:
            raise GrafoError(f"El nodo '{nodo}' no existe")
