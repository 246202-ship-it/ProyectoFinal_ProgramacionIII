"""Interfaz gráfica (Tkinter): el grafo a la izquierda y un panel por módulo a la derecha.

Cada escenario tiene su red (Carding, Enrutamiento, Liquidez); el lienzo muestra la de la
pestaña activa. Interacción en el mapa:
- pasar el mouse por un nodo lo agranda y muestra sus datos y vecinos;
- clic en un nodo = enfocarlo (se ilumina su vecindad y fluye el dinero por sus conexiones);
- arrastrar un nodo lo mueve; arrastrar el fondo mueve la vista; rueda = zoom;
- clic en la leyenda resalta todos los nodos de ese tipo;
- doble clic (o el botón "Simular ataque") anima cómo se propaga un ataque por la cadena.
"""
import math
import os
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from src import carding, distribucion_liquidez as liq, enrutamiento_financiero as enr, evaluacion_resultados as ev
from src.gestion_red import TIPOS_NODO, GestionRed
from src.graph import GrafoError
from src.visual import (ETIQUETA_TIPO, FONDO, TIPO_COLOR, aclarar, calcular_layout, columnas_de, curva, mezclar,
                        punto_en)

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ANCHO, ALTO = 1000, 700            # tamaño del "mundo" donde se calculan las posiciones
RESALTE, NIVELES = "#ff3d81", {1: "#ff9f1c", 2: "#ffd166", 3: "#fff3b0"}
HOT, HOT_ARISTA = "#ff2e4d", "#ff7a3d"          # elementos comprometidos en la simulación
PANEL, PANEL2, TEXTO, TENUE = "#11193a", "#1a2552", "#e6ebff", "#8d9bd6"
ACENTO, ACENTO2 = "#7c4dff", "#00e5ff"
FUENTE = "Segoe UI"
FPS_MS = 33                         # un fotograma cada 33 ms (~30 por segundo)
DUR_PASO = 1.3                      # segundos que dura cada oleada de la simulación a velocidad 1


def cargar_redes():
    """Las tres redes de ejemplo, cargadas desde data/."""
    d = lambda f: os.path.join(RAIZ, "data", f)
    c = GestionRed(multi=True)
    c.cargar_nodos(d("carding_nodos.csv"))
    c.cargar_aristas(d("transacciones.csv"), crear_nodos=False)
    e, l = GestionRed(), GestionRed()
    e.cargar_json(d("red_enrutamiento.json"))
    l.cargar_json(d("distribucion_liquidez.json"))
    return {"Carding": c, "Enrutamiento": e, "Liquidez": l}


def parsear_atributos(texto):
    """'comision=4.5, canal=ACH' -> {'comision': '4.5', 'canal': 'ACH'}."""
    res = {}
    for par in filter(None, (p.strip() for p in texto.split(","))):
        if "=" not in par:
            raise ValueError(f"'{par}' debe tener la forma clave=valor")
        k, v = par.split("=", 1)
        res[k.strip()] = v.strip()
    return res


def pares_de_relaciones(relaciones):
    """['T1 -> M1 -> C1 (..)', ...] -> {('T1','M1'), ('M1','C1')}."""
    pares = set()
    for r in relaciones:
        ruta = r.split(" (")[0].split(" -> ")
        pares.update(zip(ruta, ruta[1:]))
    return pares


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("OptiFin - Redes financieras y análisis de carding")
        self.geometry("1380x780")
        self.redes = cargar_redes()
        self.nombre = tk.StringVar(value="Carding")
        self.layouts, self.columnas, self.resalte, self.alertas = {}, {}, {}, []
        self.escala, self.dx, self.dy, self.ajustado = 1.0, 0.0, 0.0, False
        self.turno_ruta = 0
        # estado de la interacción y de las animaciones
        self.sel, self.hover, self.sim = None, None, None
        self._anim, self.ondas = {}, []              # nodo -> grado de agrandado (0 a 1); ondas expansivas
        self._grados, self._incidentes, self._vecinos = {}, {}, {}
        self._leyenda, self._arrastre, self._red_activa = [], None, None
        self._inicio, self._movido = (0, 0), False
        self._t0 = self._ultimo = time.monotonic()
        self._estilos()
        self._armar()
        self.cambiar_red("Carding")
        self._tick_id = self.after(FPS_MS, self._tick)

    def destroy(self):
        try:
            self.after_cancel(self._tick_id)
        except (AttributeError, tk.TclError, ValueError):
            pass
        super().destroy()

    def _estilos(self):
        """Tema oscuro con acentos de color para toda la ventana."""
        self.configure(bg=FONDO)
        st = ttk.Style(self)
        try:
            st.theme_use("clam")
        except tk.TclError:
            pass
        st.configure(".", background=PANEL, foreground=TEXTO, fieldbackground=PANEL2, bordercolor=PANEL2,
                     lightcolor=PANEL2, darkcolor=PANEL2, troughcolor=FONDO, focuscolor=ACENTO, insertcolor=TEXTO,
                     font=(FUENTE, 9))
        st.configure("TFrame", background=PANEL)
        st.configure("Barra.TFrame", background=FONDO)
        st.configure("TLabel", background=PANEL, foreground=TEXTO)
        st.configure("Barra.TLabel", background=FONDO, foreground="#c9d3ff")
        st.configure("Ayuda.TLabel", background=FONDO, foreground=TENUE)
        st.configure("TLabelframe", background=PANEL, bordercolor="#2c3a7d")
        st.configure("TLabelframe.Label", background=PANEL, foreground=ACENTO2, font=(FUENTE, 9, "bold"))
        st.configure("TButton", background="#26357a", foreground=TEXTO, padding=(8, 5), borderwidth=0, focusthickness=0)
        st.map("TButton", background=[("pressed", "#4b63d6"), ("active", "#3a4fb5")])
        st.configure("Accion.TButton", background=ACENTO, foreground="white", font=(FUENTE, 9, "bold"))
        st.map("Accion.TButton", background=[("pressed", "#6236e0"), ("active", "#9470ff")])
        st.configure("Peligro.TButton", background="#d6244a", foreground="white", font=(FUENTE, 9, "bold"))
        st.map("Peligro.TButton", background=[("pressed", "#a81a38"), ("active", "#ff4d70")])
        st.configure("TNotebook", background=FONDO, borderwidth=0, tabmargins=(2, 4, 2, 0))
        st.configure("TNotebook.Tab", background=PANEL2, foreground=TENUE, padding=(12, 6), borderwidth=0)
        st.map("TNotebook.Tab", background=[("selected", ACENTO)], foreground=[("selected", "white")])
        for w in ("TEntry", "TCombobox", "TSpinbox"):
            st.configure(w, fieldbackground=PANEL2, foreground=TEXTO, arrowcolor=ACENTO2, padding=3)
        st.map("TCombobox", fieldbackground=[("readonly", PANEL2)], foreground=[("readonly", TEXTO)])
        st.configure("Treeview", background=PANEL2, fieldbackground=PANEL2, foreground=TEXTO, rowheight=24, borderwidth=0)
        st.configure("Treeview.Heading", background="#26357a", foreground=TEXTO, relief="flat")
        st.map("Treeview", background=[("selected", ACENTO)], foreground=[("selected", "white")])
        st.configure("Horizontal.TScale", background=FONDO, troughcolor=PANEL2)
        for k, v in (("background", PANEL2), ("foreground", TEXTO), ("selectBackground", ACENTO)):
            self.option_add(f"*TCombobox*Listbox.{k}", v)

    # ----------------------------------------------------------------- red actual
    @property
    def red(self):
        return self.redes[self.nombre.get()]

    @property
    def g(self):
        return self.red.grafo

    def cambiar_red(self, nombre=None):
        if nombre:
            self.nombre.set(nombre)
        if self.nombre.get() != self._red_activa:         # otra red: se pierde la selección y la simulación
            self._red_activa = self.nombre.get()
            self.detener_sim()
            self.sel = self.hover = None
            self._anim = {}
        self.resalte = {}
        self.cb_origen["values"] = self.cb_destino["values"] = sorted(self.redes["Enrutamiento"].grafo.nodos)
        self.ajustar_vista()
        self.info.config(text=f"Red {self.nombre.get()}: {self.g.n_nodos} nodos, {self.g.n_aristas} conexiones")

    def _posiciones(self):
        n = self.nombre.get()
        if n not in self.layouts:
            self.layouts[n] = calcular_layout(self.g, ANCHO, ALTO)
            self.columnas[n] = columnas_de(self.g, self.layouts[n])
        return self.layouts[n]

    def _cambio_estructura(self):
        self.layouts.pop(self.nombre.get(), None)
        self.columnas.pop(self.nombre.get(), None)
        self.resalte = {}
        self.detener_sim()
        if self.sel not in self.g.nodos:
            self.sel = None
        self.dibujar()
        self.info.config(text=f"Red {self.nombre.get()}: {self.g.n_nodos} nodos, {self.g.n_aristas} conexiones")

    # --------------------------------------------------------------------- armado
    def _armar(self):
        izq = ttk.Frame(self, style="Barra.TFrame")
        izq.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        self.lienzo = tk.Canvas(izq, bg=FONDO, highlightthickness=1, highlightbackground="#26357a")
        self.lienzo.pack(fill="both", expand=True)
        barra = ttk.Frame(izq, style="Barra.TFrame")
        barra.pack(fill="x", pady=(6, 0))
        self.v_pausa, self.v_vel = tk.StringVar(value="Pausar"), tk.DoubleVar(value=1.0)
        ttk.Button(barra, text="▶ Simular ataque", style="Peligro.TButton", command=self.simular_ataque).pack(side="left")
        ttk.Button(barra, textvariable=self.v_pausa, command=self.pausar_sim).pack(side="left", padx=4)
        ttk.Button(barra, text="Reiniciar", command=self.reiniciar_sim).pack(side="left")
        ttk.Label(barra, text="Velocidad", style="Barra.TLabel").pack(side="left", padx=(10, 2))
        ttk.Scale(barra, from_=0.4, to=3.0, variable=self.v_vel, length=110).pack(side="left")
        ttk.Button(barra, text="Ajustar vista", command=self.ajustar_vista).pack(side="right")
        ttk.Button(barra, text="Limpiar", command=self.limpiar).pack(side="right", padx=4)
        self.info = ttk.Label(izq, text="", wraplength=760, style="Barra.TLabel")
        self.info.pack(fill="x", pady=(4, 0))
        ttk.Label(izq, style="Ayuda.TLabel", text="Pasa el mouse por un nodo para agrandarlo · clic para enfocarlo · "
                  "arrástralo para moverlo · doble clic para simular un ataque desde ahí").pack(fill="x")
        l = self.lienzo
        l.bind("<Configure>", lambda e: self.ajustar_vista() if not self.ajustado else self.dibujar())
        l.bind("<ButtonPress-1>", self._presionar)
        l.bind("<B1-Motion>", self._arrastrar)
        l.bind("<ButtonRelease-1>", self._soltar)
        l.bind("<Double-Button-1>", self._doble_clic)
        l.bind("<Motion>", self._mover)
        l.bind("<Leave>", lambda e: setattr(self, "hover", None))
        l.bind("<MouseWheel>", lambda e: self._zoom(e.x, e.y, 1.15 if e.delta > 0 else 1 / 1.15))
        l.bind("<Button-4>", lambda e: self._zoom(e.x, e.y, 1.15))
        l.bind("<Button-5>", lambda e: self._zoom(e.x, e.y, 1 / 1.15))

        self.pestanas = ttk.Notebook(self, width=520)
        self.pestanas.pack(side="left", fill="y", padx=(0, 6), pady=6)
        self._pestana_red()
        self._pestana_carding()
        self._pestana_enrutamiento()
        self._pestana_liquidez()
        self._pestana_evaluacion()
        self.pestanas.bind("<<NotebookTabChanged>>", self._al_cambiar_pestana)

    def _al_cambiar_pestana(self, _=None):
        idx = self.pestanas.index("current")
        destino = {1: "Carding", 2: "Enrutamiento", 3: "Liquidez"}.get(idx)
        if destino:
            self.cambiar_red(destino)

    @staticmethod
    def _caja(padre, alto=14):
        marco = ttk.Frame(padre)
        marco.pack(fill="both", expand=True, pady=4)
        t = tk.Text(marco, height=alto, wrap="word", font=("Consolas", 9), bg="#0b1330", fg=TEXTO, relief="flat",
                    insertbackground=TEXTO, selectbackground=ACENTO, padx=8, pady=6)
        s = ttk.Scrollbar(marco, command=t.yview)
        t.configure(yscrollcommand=s.set)
        t.pack(side="left", fill="both", expand=True)
        s.pack(side="right", fill="y")
        return t

    def _guardable(self, padre, caja, nombre):
        ttk.Button(padre, text="Guardar reporte...", command=lambda: self.guardar_texto(caja, nombre)).pack(anchor="e")

    @staticmethod
    def escribir(caja, texto):
        caja.delete("1.0", "end")
        caja.insert("1.0", texto)

    def guardar_texto(self, caja, nombre="reporte.txt"):
        ruta = filedialog.asksaveasfilename(initialdir=os.path.join(RAIZ, "docs"), initialfile=nombre,
                                            defaultextension=".txt")
        if ruta:
            with open(ruta, "w", encoding="utf-8") as f:
                f.write(caja.get("1.0", "end"))

    def error(self, mensaje):
        messagebox.showerror("Error", mensaje)

    def _hacer(self, funcion, *args, mensaje=None):
        """Ejecuta una operación del Módulo 1 mostrando los errores de validación."""
        try:
            funcion(*args)
        except (GrafoError, ValueError, OSError, KeyError) as e:
            return self.error(str(e))
        self._cambio_estructura()
        if mensaje:
            self.escribir(self.salida_red, mensaje)

    # --------------------------------------------------------------- pestaña 1: red
    def _pestana_red(self):
        f = ttk.Frame(self.pestanas, padding=6)
        self.pestanas.add(f, text="1. Red")
        fila = ttk.Frame(f)
        fila.pack(fill="x")
        ttk.Label(fila, text="Red:").pack(side="left")
        cb = ttk.Combobox(fila, textvariable=self.nombre, values=list(self.redes), state="readonly", width=14)
        cb.pack(side="left", padx=4)
        cb.bind("<<ComboboxSelected>>", lambda e: self.cambiar_red())
        for texto, cmd in (("Cargar JSON", self.cargar_json), ("Cargar nodos CSV", self.cargar_nodos),
                           ("Cargar conexiones CSV/TXT", self.cargar_aristas)):
            ttk.Button(f, text=texto, command=cmd).pack(fill="x", pady=1)
        fila = ttk.Frame(f)
        fila.pack(fill="x", pady=1)
        ttk.Button(fila, text="Guardar JSON", command=self.guardar_json).pack(side="left", expand=True, fill="x")
        ttk.Button(fila, text="Validar red", command=self.validar).pack(side="left", expand=True, fill="x")

        nodo = ttk.LabelFrame(f, text="Nodo", padding=4)
        nodo.pack(fill="x", pady=4)
        self.v_nodo, self.v_tipo, self.v_attr_nodo = tk.StringVar(), tk.StringVar(value="cuenta"), tk.StringVar()
        ttk.Entry(nodo, textvariable=self.v_nodo, width=14).grid(row=0, column=0)
        ttk.Combobox(nodo, textvariable=self.v_tipo, values=sorted(TIPOS_NODO), state="readonly", width=15).grid(row=0, column=1, padx=4)
        ttk.Entry(nodo, textvariable=self.v_attr_nodo, width=22).grid(row=0, column=2)
        ttk.Label(nodo, text="id    |    tipo    |    atributos (clave=valor, ...)").grid(row=1, column=0, columnspan=3, sticky="w")
        b = ttk.Frame(nodo)
        b.grid(row=2, column=0, columnspan=3, sticky="ew")
        for t, c in (("Agregar", self.agregar_nodo), ("Modificar", self.modificar_nodo), ("Eliminar", self.eliminar_nodo)):
            ttk.Button(b, text=t, command=c).pack(side="left", expand=True, fill="x")

        con = ttk.LabelFrame(f, text="Conexión", padding=4)
        con.pack(fill="x")
        self.v_o, self.v_d, self.v_attr_arista = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ttk.Entry(con, textvariable=self.v_o, width=12).grid(row=0, column=0)
        ttk.Entry(con, textvariable=self.v_d, width=12).grid(row=0, column=1, padx=4)
        ttk.Entry(con, textvariable=self.v_attr_arista, width=26).grid(row=0, column=2)
        ttk.Label(con, text="origen   |   destino   |   atributos (comision=4.5, tiempo=2)").grid(row=1, column=0, columnspan=3, sticky="w")
        b = ttk.Frame(con)
        b.grid(row=2, column=0, columnspan=3, sticky="ew")
        for t, c in (("Agregar", self.agregar_arista), ("Modificar", self.modificar_arista), ("Eliminar", self.eliminar_arista)):
            ttk.Button(b, text=t, command=c).pack(side="left", expand=True, fill="x")
        self.salida_red = self._caja(f, 10)

    def _pedir(self, tipos):
        return filedialog.askopenfilename(initialdir=os.path.join(RAIZ, "data"), filetypes=tipos)

    def cargar_json(self):
        ruta = self._pedir([("JSON", "*.json")])
        if ruta:
            self._hacer(lambda: self._informe(self.red.cargar_json(ruta)))

    def cargar_nodos(self):
        ruta = self._pedir([("CSV/TXT", "*.csv *.txt")])
        if ruta:
            self._hacer(lambda: self._informe(self.red.cargar_nodos(ruta)))

    def cargar_aristas(self):
        ruta = self._pedir([("CSV/TXT", "*.csv *.txt")])
        if ruta:
            self._hacer(lambda: self._informe(self.red.cargar_aristas(ruta)))

    def _informe(self, informe):
        malos = "\n".join(f"  línea {l}: {m}" for l, m in informe["rechazados"][:15])
        self.escribir(self.salida_red, f"Cargados: {informe['cargados']}. Rechazados: {len(informe['rechazados'])}\n{malos}")

    def guardar_json(self):
        ruta = filedialog.asksaveasfilename(initialdir=os.path.join(RAIZ, "data"), defaultextension=".json")
        if ruta:
            self._hacer(self.red.guardar_json, ruta, mensaje=f"Guardado en {ruta}")

    def validar(self):
        problemas = self.red.validar()
        self.escribir(self.salida_red, f"{self.red.resumen()}\n\n" + ("Red consistente." if not problemas else "\n".join(problemas[:40])))

    def agregar_nodo(self):
        self._hacer(lambda: self.red.agregar_nodo(self.v_nodo.get(), self.v_tipo.get(), **parsear_atributos(self.v_attr_nodo.get())))

    def modificar_nodo(self):
        self._hacer(lambda: self.red.modificar_nodo(self.v_nodo.get(), tipo=self.v_tipo.get(), **parsear_atributos(self.v_attr_nodo.get())))

    def eliminar_nodo(self):
        self._hacer(self.red.eliminar_nodo, self.v_nodo.get())

    def agregar_arista(self):
        self._hacer(lambda: self.red.agregar_arista(self.v_o.get(), self.v_d.get(), **parsear_atributos(self.v_attr_arista.get())))

    def modificar_arista(self):
        self._hacer(lambda: self.red.modificar_arista(self.v_o.get(), self.v_d.get(), **parsear_atributos(self.v_attr_arista.get())))

    def eliminar_arista(self):
        self._hacer(self.red.eliminar_arista, self.v_o.get(), self.v_d.get())

    # ------------------------------------------------------------ pestaña 2: carding
    def _pestana_carding(self):
        f = ttk.Frame(self.pestanas, padding=6)
        self.pestanas.add(f, text="2. Carding")
        u = ttk.LabelFrame(f, text="Umbrales de alerta", padding=4)
        u.pack(fill="x")
        self.umbral = {}
        for i, (clave, texto, valor) in enumerate((("min_tarjetas", "Tarjetas por dispositivo ≥", 3), ("min_dispositivos", "Dispositivos por tarjeta ≥", 3),
                                                   ("min_comercios", "Comercios por cuenta ≥", 3), ("min_pagos", "Pagos en ráfaga ≥", 4),
                                                   ("ventana_min", "Ventana de la ráfaga (min)", 10))):
            self.umbral[clave] = tk.IntVar(value=valor)
            ttk.Label(u, text=texto).grid(row=i // 2, column=(i % 2) * 2, sticky="w")
            ttk.Spinbox(u, from_=1, to=500, width=4, textvariable=self.umbral[clave]).grid(row=i // 2, column=(i % 2) * 2 + 1, padx=(2, 10))
        ttk.Button(f, text="Analizar red de carding", style="Accion.TButton", command=self.analizar_carding).pack(fill="x", pady=4)
        self.lista = ttk.Treeview(f, columns=("tipo", "detalle"), show="headings", height=6, selectmode="browse")
        self.lista.heading("tipo", text="Alerta")
        self.lista.heading("detalle", text="Detalle")
        self.lista.column("tipo", width=190)
        self.lista.column("detalle", width=290)
        self.lista.pack(fill="x")
        self.lista.bind("<<TreeviewSelect>>", self.elegir_alerta)
        fila = ttk.Frame(f)
        fila.pack(fill="x", pady=4)
        ttk.Label(fila, text="Elemento (clic en el mapa o escribir):").pack(side="left")
        self.v_ficha = tk.StringVar()
        ttk.Entry(fila, textvariable=self.v_ficha, width=8).pack(side="left", padx=4)
        ttk.Button(fila, text="Ver conexiones", command=self.ficha).pack(side="left")
        sim = ttk.LabelFrame(f, text="Simulación de ataque", padding=4)
        sim.pack(fill="x", pady=(2, 0))
        ttk.Label(sim, wraplength=480, text="Elige una tarjeta (clic en el mapa o en una alerta) y mira cómo se "
                  "propaga el dinero oleada por oleada hasta las billeteras. También sirve el doble clic en un nodo.").pack(anchor="w")
        ttk.Button(sim, text="▶ Simular ataque desde el elemento elegido", style="Peligro.TButton",
                   command=self.simular_ataque).pack(fill="x", pady=(4, 0))
        self.salida_carding = self._caja(f, 8)
        self._guardable(f, self.salida_carding, "reporte_carding.txt")

    def _umbrales(self):
        return {k: v.get() for k, v in self.umbral.items()}

    def analizar_carding(self):
        self.cambiar_red("Carding")
        self.alertas = carding.analizar_carding(self.g, **self._umbrales())
        self.lista.delete(*self.lista.get_children())
        for i, a in enumerate(self.alertas):
            self.lista.insert("", "end", iid=str(i), values=(a["tipo"], a["detalle"]))
        self.escribir(self.salida_carding, carding.reporte(self.alertas))

    def elegir_alerta(self, _=None):
        sel = self.lista.selection()
        if sel:
            a = self.alertas[int(sel[0])]
            self.resaltar(nodos=a["elementos"], aristas=pares_de_relaciones(a["relaciones"]))

    def ficha(self):
        self.cambiar_red("Carding")
        nodo = self.v_ficha.get().strip()
        try:
            c = carding.consultar(self.g, nodo, **self._umbrales())
        except GrafoError as e:
            return self.error(str(e))
        self.escribir(self.salida_carding, carding.reporte_consulta(c))
        colores = {n: NIVELES.get(k, "#fff3b0") for k, v in c["niveles"].items() for n in v}
        colores[nodo] = RESALTE
        self.resaltar(nodos=colores, aristas=pares_de_relaciones([" -> ".join(p) for p in c["caminos"]]), colores=colores)

    # ------------------------------------------------------- pestaña 3: enrutamiento
    def _pestana_enrutamiento(self):
        f = ttk.Frame(self.pestanas, padding=6)
        self.pestanas.add(f, text="3. Enrutamiento")
        fila = ttk.Frame(f)
        fila.pack(fill="x")
        self.v_ruta_o, self.v_ruta_d = tk.StringVar(value="BancoA"), tk.StringVar(value="BancoC")
        self.v_monto, self.v_crit = tk.StringVar(value="1000"), tk.StringVar(value="comision")
        ttk.Label(fila, text="Origen").grid(row=0, column=0)
        ttk.Label(fila, text="Destino").grid(row=0, column=1)
        ttk.Label(fila, text="Monto").grid(row=0, column=2)
        ttk.Label(fila, text="Resaltar la mejor por").grid(row=0, column=3)
        self.cb_origen = ttk.Combobox(fila, textvariable=self.v_ruta_o, width=14)
        self.cb_destino = ttk.Combobox(fila, textvariable=self.v_ruta_d, width=14)
        self.cb_origen.grid(row=1, column=0, padx=2)
        self.cb_destino.grid(row=1, column=1, padx=2)
        ttk.Entry(fila, textvariable=self.v_monto, width=10).grid(row=1, column=2, padx=2)
        ttk.Combobox(fila, textvariable=self.v_crit, values=list(enr.CRITERIOS), state="readonly", width=10).grid(row=1, column=3, padx=2)
        ttk.Button(f, text="Comparar rutas y comisiones", style="Accion.TButton", command=self.comparar_rutas).pack(fill="x", pady=6)
        ttk.Label(f, text="Tip: clic en dos nodos del mapa para elegir origen y destino.").pack(anchor="w")
        self.salida_enr = self._caja(f, 22)
        self._guardable(f, self.salida_enr, "reporte_enrutamiento.txt")

    def comparar_rutas(self):
        self.cambiar_red("Enrutamiento")
        try:
            monto = float(self.v_monto.get().replace(",", "."))
            o, d = self.v_ruta_o.get(), self.v_ruta_d.get()
            texto = enr.reporte_comparativo(self.g, o, d, monto)
            mejor = enr.ruta_optima(self.g, o, d, self.v_crit.get(), monto)
        except (GrafoError, ValueError) as e:
            return self.error(str(e))
        self.escribir(self.salida_enr, texto)
        if mejor and mejor[1]:
            canales = mejor[1]
            self.resaltar(nodos=[canales[0].origen] + [a.destino for a in canales], aristas={(a.origen, a.destino): 4 for a in canales})

    # ---------------------------------------------------------- pestaña 4: liquidez
    def _pestana_liquidez(self):
        f = ttk.Frame(self.pestanas, padding=6)
        self.pestanas.add(f, text="4. Liquidez")
        fila = ttk.Frame(f)
        fila.pack(fill="x")
        ttk.Label(fila, text="Algoritmo:").pack(side="left")
        self.v_alg = tk.StringVar(value="costo_minimo")
        ttk.Combobox(fila, textvariable=self.v_alg, values=["costo_minimo", "dinic", "edmonds-karp"], state="readonly", width=14).pack(side="left", padx=4)
        ttk.Button(f, text="Planificar distribución de efectivo", style="Accion.TButton", command=self.planificar).pack(fill="x", pady=6)
        ttk.Label(f, text="Rojo = agencia con demanda pendiente; el grosor de las rutas indica el efectivo enviado.").pack(anchor="w")
        self.salida_liq = self._caja(f, 24)
        self._guardable(f, self.salida_liq, "reporte_liquidez.txt")

    def planificar(self):
        self.cambiar_red("Liquidez")
        try:
            plan = liq.planificar(self.g, self.v_alg.get())
        except (GrafoError, ValueError) as e:
            return self.error(str(e))
        self.escribir(self.salida_liq, liq.reporte(self.g, plan))
        aristas = {(o, d): 1 + 7 * f / cap if cap != math.inf else 3 for o, d, f, cap, _ in plan["usado"]}
        nodos = {n for par in aristas for n in par}
        colores = {a: "#d62728" for a in plan["pendiente"]}
        self.resaltar(nodos=nodos | set(colores), aristas=aristas, colores=colores)

    # ---------------------------------------------------------- pestaña 5: evaluación
    def _pestana_evaluacion(self):
        f = ttk.Frame(self.pestanas, padding=6)
        self.pestanas.add(f, text="5. Evaluación")
        ttk.Button(f, text="Ejecutar casos de prueba y comparaciones (unos segundos)", style="Accion.TButton", command=self.evaluar).pack(fill="x", pady=4)
        self.salida_ev = self._caja(f, 30)
        self._guardable(f, self.salida_ev, "resultados_evaluacion.txt")

    def evaluar(self):
        self.config(cursor="watch")
        self.update_idletasks()
        try:
            self.escribir(self.salida_ev, ev.reporte_evaluacion(ev.ejecutar_todo()))
        finally:
            self.config(cursor="")

    # ---------------------------------------------------------------------- dibujo
    def resaltar(self, nodos=(), aristas=(), colores=None):
        """Resalta nodos y aristas ({(o, d): ancho} o un conjunto de pares). Sin argumentos: quita."""
        if not isinstance(aristas, dict):
            aristas = {p: 3 for p in aristas}
        extremos = {n for par in aristas for n in par}                 # los nodos de las aristas también se destacan
        self.resalte = {"nodos": set(nodos) | extremos, "aristas": aristas, "colores": colores or {}} if (nodos or aristas) else {}
        self.dibujar()

    def limpiar(self):
        """Quita resaltado, selección y simulación."""
        self.detener_sim()
        self.sel = None
        self.resaltar()

    def ajustar_vista(self):
        self.update_idletasks()
        w, h = max(self.lienzo.winfo_width(), 200), max(self.lienzo.winfo_height(), 200)
        self.escala = min(w / ANCHO, h / ALTO) * 0.95
        self.dx, self.dy = (w - ANCHO * self.escala) / 2, (h - ALTO * self.escala) / 2
        self.ajustado = True
        self.dibujar()

    def _xy(self, pos, n):
        return pos[n][0] * self.escala + self.dx, pos[n][1] * self.escala + self.dy

    def _radio(self, n):
        """Los nodos con más conexiones se dibujan más grandes."""
        return (3.5 + min(6.5, 1.5 * math.sqrt(self._grados.get(n, 1)))) * max(0.7, min(1.8, self.escala ** 0.5))

    def _preparar_vecindad(self):
        g = self.g
        self._incidentes, self._vecinos, self._grados = {}, {}, {}
        for lista in g.ady.values():
            for a in lista:
                par = (a.origen, a.destino)
                for x, y in ((a.origen, a.destino), (a.destino, a.origen)):
                    self._incidentes.setdefault(x, set()).add(par)
                    self._vecinos.setdefault(x, set()).add(y)
                    self._grados[x] = self._grados.get(x, 0) + 1

    def dibujar(self):
        """Capa base: columnas, conexiones, nodos y leyenda. La capa animada (etiqueta "anim") se
        repinta aparte en cada fotograma."""
        c, g = self.lienzo, self.g
        c.delete("all")
        self._leyenda = []
        if not g.n_nodos:
            return
        pos = self._posiciones()
        cols = self.columnas.get(self.nombre.get(), {})
        self._preparar_vecindad()
        r, sim = self.resalte, self.sim
        ar, nodos_r, colores = r.get("aristas", {}), r.get("nodos", set()), r.get("colores", {})
        sel = self.sel if self.sel in g.nodos else None
        foco = ({sel} | self._vecinos.get(sel, set())) if (sel and not r and not sim) else None
        comp = sim["comp"] if sim else set()
        tipo = lambda n: g.nodos[n]["tipo"]

        for t, x in cols.items():                          # columnas de colores con su título
            sx = x * self.escala + self.dx
            ancho = max(40, 110 * self.escala)
            c.create_rectangle(sx - ancho / 2, 0, sx + ancho / 2, c.winfo_height(), fill=mezclar(FONDO, TIPO_COLOR[t], 0.06), outline="")
            cuantos = sum(1 for a in g.nodos.values() if a["tipo"] == t)
            c.create_text(sx, 16, text=f"{ETIQUETA_TIPO.get(t, t)} ({cuantos})", fill=TIPO_COLOR[t], font=(FUENTE, 10, "bold"))

        suave, aristas = bool(cols), []
        for lista in g.ady.values():
            for a in lista:
                if not g.dirigido and a.origen > a.destino:
                    continue
                par = (a.origen, a.destino)
                col = TIPO_COLOR.get(tipo(a.origen), "#8899bb")
                ancho_r = ar.get(par) or (ar.get((a.destino, a.origen)) if not g.dirigido else None)
                if sim:
                    caliente = par in sim["calientes"] or (not g.dirigido and (a.destino, a.origen) in sim["calientes"])
                    prio, color, w = (2, HOT_ARISTA, 2.4) if caliente else (0, mezclar(FONDO, col, 0.10), 1)
                elif ancho_r:
                    prio, color, w = 2, RESALTE, ancho_r
                elif foco is not None:
                    prio, color, w = ((2, aclarar(col, 0.2), 2.2) if sel in par else (0, mezclar(FONDO, col, 0.08), 1))
                elif r:
                    prio, color, w = 0, mezclar(FONDO, col, 0.10), 1
                else:
                    prio, color, w = 1, mezclar(FONDO, col, 0.45), 1
                aristas.append((prio, par, color, w))
        for prio, par, color, w in sorted(aristas, key=lambda x: x[0]):
            pts = curva(self._xy(pos, par[0]), self._xy(pos, par[1]), suave)
            c.create_line(*[v for p in pts for v in p], fill=color, width=w, arrow=tk.LAST if g.dirigido else None,
                          arrowshape=(10, 12, 4) if prio == 2 else (6, 7, 3))

        nodos = []
        for n in g.nodos:
            destacado = n in nodos_r or n in comp
            atenuado = bool(sim and n not in comp) or bool(r and not sim and n not in nodos_r) or (foco is not None and n not in foco)
            nodos.append((destacado or (foco is not None and n in foco), n, destacado, atenuado))
        for _, n, destacado, atenuado in sorted(nodos, key=lambda x: x[0]):
            x, y = self._xy(pos, n)
            base = HOT if n in comp else (colores.get(n) or TIPO_COLOR.get(tipo(n), "#8899bb"))
            rr = self._radio(n) * (1.35 if destacado else 1)
            if atenuado:
                c.create_oval(x - rr, y - rr, x + rr, y + rr, fill=mezclar(FONDO, base, 0.28), outline="")
                continue
            c.create_oval(x - rr * 1.9, y - rr * 1.9, x + rr * 1.9, y + rr * 1.9, fill=mezclar(FONDO, base, 0.14), outline="")
            c.create_oval(x - rr * 1.4, y - rr * 1.4, x + rr * 1.4, y + rr * 1.4, fill=mezclar(FONDO, base, 0.26), outline="")
            c.create_oval(x - rr, y - rr, x + rr, y + rr, fill=base, outline="#ffffff" if destacado else aclarar(base, 0.5),
                          width=2 if destacado else 1)
            if g.n_nodos <= 40 or destacado or (foco is not None and n in foco):
                c.create_text(x, y - rr - 9, text=n, font=(FUENTE, 8), fill=TEXTO)

        tipos = sorted({a["tipo"] for a in g.nodos.values()})            # leyenda: un clic resalta ese tipo
        alto = c.winfo_height()
        y0 = alto - 12 - len(tipos) * 20
        c.create_rectangle(8, y0 - 6, 150, alto - 6, fill=PANEL, outline="#26357a")
        for i, t in enumerate(tipos):
            y = y0 + 8 + i * 20
            activo = self.resalte.get("filtro") == t
            c.create_oval(16, y - 5, 26, y + 5, fill=TIPO_COLOR.get(t, "#8899bb"), outline="#ffffff" if activo else "")
            c.create_text(34, y, text=ETIQUETA_TIPO.get(t, t), anchor="w", font=(FUENTE, 9, "bold" if activo else "normal"), fill=TEXTO)
            self._leyenda.append((8, y - 10, 150, y + 10, t))

    # ------------------------------------------------------------- animación (capa "anim")
    def _onda(self, n, color=HOT, dur=1.2, alcance=4.0):
        self.ondas.append({"n": n, "t0": time.monotonic(), "dur": dur, "color": color, "alcance": alcance})

    def _tick(self):
        self._tick_id = self.after(FPS_MS, self._tick)           # se reprograma primero: un error no detiene la animación
        ahora = time.monotonic()
        dt, self._ultimo = min(ahora - self._ultimo, 0.1), ahora
        self._avanzar_sim(dt)
        self._superponer(ahora)

    def _superponer(self, ahora):
        """Repinta lo que se mueve: nodos agrandados, flujo de dinero, ondas, tooltip y panel de la simulación."""
        c, g = self.lienzo, self.g
        c.delete("anim")
        if not g.n_nodos:
            return
        pos, fase, w = self._posiciones(), ahora - self._t0, c.winfo_width()
        suave = bool(self.columnas.get(self.nombre.get()))
        xy = lambda n: self._xy(pos, n)
        comp = self.sim["comp"] if self.sim else set()
        objetivo = {n for n in (self.hover, self.sel) if n in g.nodos}
        for n in list(self._anim):
            if n not in g.nodos:
                del self._anim[n]
        for n in objetivo | set(self._anim):                       # agrandado suave (hover y selección)
            t = self._anim.get(n, 0.0)
            t += ((1.0 if n in objetivo else 0.0) - t) * 0.28
            if n not in objetivo and t < 0.02:
                self._anim.pop(n, None)
            else:
                self._anim[n] = t

        # conexiones del nodo bajo el mouse o seleccionado: más brillantes, con dinero fluyendo
        flujo = set()
        for n in objetivo:
            flujo |= self._incidentes.get(n, set())
            for u, v in self._incidentes.get(n, ()):
                col = aclarar(TIPO_COLOR.get(g.nodos[u]["tipo"], "#8899bb"), 0.35)
                pts = curva(xy(u), xy(v), suave)
                c.create_line(*[q for p in pts for q in p], fill=col, width=2.6, tags="anim",
                              arrow=tk.LAST if g.dirigido else None, arrowshape=(10, 12, 4))
        flujo |= set(self.resalte.get("aristas", {}))
        for u, v in list(flujo)[:160]:
            if u in g.nodos and v in g.nodos:
                semilla = (sum(map(ord, u + v)) % 97) / 97
                for k in range(3):
                    x, y = punto_en(xy(u), xy(v), suave, (fase * 0.45 + semilla + k / 3) % 1)
                    c.create_oval(x - 2.6, y - 2.6, x + 2.6, y + 2.6, fill="#ffffff", outline="", tags="anim")

        # simulación: los "paquetes" de dinero viajan por las conexiones de la oleada actual
        s = self.sim
        if s and not s["fin"]:
            p = s["p"] * s["p"] * (3 - 2 * s["p"])
            for u, v in s["res"]["pasos"][s["paso"]]["aristas"]:
                for estela, (dp, rad, mezcla) in enumerate(((0, 4.5, 1.0), (0.07, 3.2, 0.55), (0.14, 2.2, 0.3))):
                    x, y = punto_en(xy(u), xy(v), suave, max(0.0, p - dp))
                    c.create_oval(x - rad, y - rad, x + rad, y + rad, fill=mezclar(FONDO, "#ffd0a8", mezcla), outline="", tags="anim")

        # ondas expansivas (un nodo se compromete o se selecciona)
        for o in list(self.ondas):
            k = (ahora - o["t0"]) / o["dur"]
            if k >= 1 or o["n"] not in g.nodos:
                self.ondas.remove(o)
                continue
            x, y = xy(o["n"])
            for retraso in (0, 0.2):
                kk = k - retraso
                if kk > 0:
                    rr = self._radio(o["n"]) * (1 + kk * o["alcance"])
                    c.create_oval(x - rr, y - rr, x + rr, y + rr, outline=mezclar(FONDO, o["color"], 0.9 * (1 - kk)),
                                  width=max(1, 3.5 * (1 - kk)), tags="anim")

        # nodos agrandados con brillo y etiqueta
        for n, t in self._anim.items():
            x, y = xy(n)
            tipo = g.nodos[n]["tipo"]
            base = HOT if n in comp else TIPO_COLOR.get(tipo, "#8899bb")
            rr = self._radio(n) * (1 + 0.9 * t)
            for f, a in ((2.3, 0.10), (1.7, 0.20), (1.3, 0.34)):
                c.create_oval(x - rr * f, y - rr * f, x + rr * f, y + rr * f, fill=mezclar(FONDO, base, a * t), outline="", tags="anim")
            c.create_oval(x - rr, y - rr, x + rr, y + rr, fill=aclarar(base, 0.18 * t), outline="#ffffff", width=2, tags="anim")
            if n == self.sel:                                       # latido continuo del nodo enfocado
                k = (fase * 0.8) % 1
                rp = rr * (1 + 1.8 * k)
                c.create_oval(x - rp, y - rp, x + rp, y + rp, outline=mezclar(FONDO, base, 0.7 * (1 - k)), width=2, tags="anim")
            c.create_text(x + 1, y - rr - 11, text=n, font=(FUENTE, 10, "bold"), fill=FONDO, tags="anim")
            c.create_text(x, y - rr - 12, text=n, font=(FUENTE, 10, "bold"), fill="#ffffff", tags="anim")
            vec = sorted(self._vecinos.get(n, ()))
            if len(vec) <= 14:                                      # rótulos de los vecinos directos
                for m in vec:
                    mx, my = xy(m)
                    mc = TIPO_COLOR.get(g.nodos[m]["tipo"], "#8899bb")
                    mr = self._radio(m) * 1.5
                    c.create_oval(mx - mr, my - mr, mx + mr, my + mr, outline=aclarar(mc, 0.3), width=2, tags="anim")
                    c.create_text(mx, my - mr - 8, text=m, font=(FUENTE, 8, "bold"), fill=aclarar(mc, 0.5), tags="anim")
        if self.hover in g.nodos:
            self._tooltip(self.hover, w)
        if s:
            self._panel_sim(w, fase)

    def _tooltip(self, n, ancho_lienzo):
        c, g = self.lienzo, self.g
        at = g.nodos[n]
        x, y = self._xy(self._posiciones(), n)
        lineas = [n, f"{at['tipo']}: recibe de {g.grado_entrada(n)}, envía a {g.grado_salida(n)}"]
        lineas += [f"{k}: {v}" for k, v in at.items() if k != "tipo"][:4]
        caja_w, caja_h = max(len(l) for l in lineas) * 6.8 + 20, len(lineas) * 16 + 12
        x0 = x + 18 if x + 18 + caja_w < ancho_lienzo else x - 18 - caja_w
        y0 = max(6, y - 14)
        borde = TIPO_COLOR.get(at["tipo"], "#8899bb")
        c.create_rectangle(x0, y0, x0 + caja_w, y0 + caja_h, fill=PANEL, outline=borde, width=2, tags="anim")
        for i, l in enumerate(lineas):
            c.create_text(x0 + 10, y0 + 8 + i * 16, text=l, anchor="w", tags="anim",
                          font=(FUENTE, 10, "bold") if i == 0 else (FUENTE, 9), fill=aclarar(borde, 0.4) if i == 0 else TEXTO)

    def _panel_sim(self, ancho_lienzo, fase):
        c, s, g = self.lienzo, self.sim, self.g
        res = s["res"]
        total_pasos = len(res["pasos"])
        x1, y0 = ancho_lienzo - 14, 14
        x0 = x1 - 244
        c.create_rectangle(x0, y0, x1, y0 + 104, fill=PANEL, outline=HOT, width=2, tags="anim")
        latido = 0.5 + 0.5 * math.sin(fase * 6)
        c.create_oval(x0 + 10, y0 + 11, x0 + 21, y0 + 22, fill=mezclar(PANEL, HOT, 0.4 + 0.6 * latido), outline="", tags="anim")
        titulo = "Ataque simulado" if s["fin"] else "Ataque en curso"
        c.create_text(x0 + 30, y0 + 17, text=titulo, anchor="w", fill=aclarar(HOT, 0.35), font=(FUENTE, 11, "bold"), tags="anim")
        actual = total_pasos if s["fin"] else s["paso"] + 1
        hechos = res["pasos"][:s["paso"]]
        monto = sum(p["monto"] for p in hechos)
        lineas = [f"Oleada {actual} de {total_pasos}", f"Comprometidos: {len(s['comp'])} de {g.n_nodos}"]
        if res["monto"] > 0:
            lineas.append(f"Pagos expuestos: {monto:,.2f}")
        else:
            lineas.append(f"Conexiones activadas: {len(s['calientes'])}")
        for i, l in enumerate(lineas):
            c.create_text(x0 + 12, y0 + 42 + i * 18, text=l, anchor="w", fill=TEXTO, font=(FUENTE, 9), tags="anim")
        c.create_rectangle(x0 + 12, y0 + 92, x1 - 12, y0 + 97, fill=PANEL2, outline="", tags="anim")
        c.create_rectangle(x0 + 12, y0 + 92, x0 + 12 + (x1 - x0 - 24) * len(s["comp"]) / max(1, g.n_nodos), y0 + 97,
                           fill=HOT, outline="", tags="anim")

    # ------------------------------------------------------------ simulación de ataque
    def _fuentes_ataque(self):
        """Desde dónde empieza el ataque: el nodo enfocado, el escrito en la ficha, la alerta elegida o,
        si no hay nada elegido, el elemento que más envía y no recibe."""
        g = self.g
        for n in (self.sel, self.v_ficha.get().strip()):
            if n in g.nodos:
                return [n]
        sel = self.lista.selection()
        if sel and self.nombre.get() == "Carding":
            elem = [n for n in self.alertas[int(sel[0])]["elementos"] if n in g.nodos]
            tarjetas = [n for n in elem if g.nodos[n]["tipo"] == "tarjeta"]
            if tarjetas or elem:
                return tarjetas or elem[:1]
        origenes = [n for n in g.nodos if g.grado_salida(n) > 0 and g.grado_entrada(n) == 0]
        return [max(origenes or list(g.nodos), key=g.grado_salida)] if g.nodos else []

    def simular_ataque(self, fuentes=None):
        fuentes = fuentes or self._fuentes_ataque()
        if not fuentes:
            return
        res = carding.simular_ataque(self.g, fuentes)
        if not res["pasos"]:
            self.info.config(text=f"{', '.join(fuentes)} no envía dinero a otros elementos: elige una tarjeta, un dispositivo o un comercio.")
            return
        self.resalte = {}
        self.ondas = []
        self.sim = {"res": res, "paso": 0, "p": 0.0, "comp": set(res["fuentes"]), "calientes": set(), "pausa": False, "fin": False}
        self.v_pausa.set("Pausar")
        for f in res["fuentes"]:
            self._onda(f, HOT, dur=1.5, alcance=6)
        if self.nombre.get() == "Carding":
            self.escribir(self.salida_carding, carding.reporte_simulacion(res))
        self.info.config(text=f"Ataque simulado desde {', '.join(res['fuentes'])}: {len(res['pasos'])} oleadas.")
        self.dibujar()

    def _avanzar_sim(self, dt):
        s = self.sim
        if not s or s["fin"] or s["pausa"]:
            return
        s["p"] += dt * self.v_vel.get() / DUR_PASO
        if s["p"] < 1:
            return
        paso = s["res"]["pasos"][s["paso"]]
        for u, v in paso["aristas"]:
            s["calientes"].add((u, v))
            if not self.g.dirigido:
                s["calientes"].add((v, u))
        for n in paso["nodos"]:
            s["comp"].add(n)
            self._onda(n, HOT)
        s["paso"] += 1
        s["p"] = 0.0
        if s["paso"] >= len(s["res"]["pasos"]):
            s["fin"] = True
            r = s["res"]
            self.info.config(text=f"Fin de la simulación: {r['alcanzados']} de {r['total']} elementos alcanzados"
                                  f"{', billeteras: ' + ', '.join(r['billeteras']) if r['billeteras'] else ''}.")
        self.dibujar()

    def pausar_sim(self):
        s = self.sim
        if not s:
            return
        if s["fin"]:
            return self.reiniciar_sim()
        s["pausa"] = not s["pausa"]
        self.v_pausa.set("Seguir" if s["pausa"] else "Pausar")

    def reiniciar_sim(self):
        if self.sim:
            self.simular_ataque(self.sim["res"]["fuentes"])

    def detener_sim(self):
        self.sim = None
        self.ondas = []
        if hasattr(self, "v_pausa"):
            self.v_pausa.set("Pausar")

    # ----------------------------------------------------------------- interacción
    def _en_leyenda(self, x, y):
        for x0, y0, x1, y1, t in self._leyenda:
            if x0 <= x <= x1 and y0 <= y <= y1:
                return t
        return None

    def _presionar(self, e):
        self._inicio, self._movido = (e.x, e.y), False
        self._arrastre = None if self._en_leyenda(e.x, e.y) else self.nodo_en(e.x, e.y)

    def _arrastrar(self, e):
        ix, iy = self._inicio
        if abs(e.x - ix) + abs(e.y - iy) > 3:
            self._movido = True
        if not self._movido:
            return
        if self._arrastre:                                    # mover el nodo (las conexiones lo siguen)
            self._posiciones()[self._arrastre] = ((e.x - self.dx) / self.escala, (e.y - self.dy) / self.escala)
            self.dibujar()
        else:                                                 # mover la vista
            self.dx += e.x - ix
            self.dy += e.y - iy
            self._inicio = (e.x, e.y)
            self.dibujar()

    def _soltar(self, e):
        self._arrastre = None
        if self._movido:
            return
        t = self._en_leyenda(e.x, e.y)
        if t:
            return self._filtrar_tipo(t)
        n = self.nodo_en(e.x, e.y)
        if n:
            self.seleccionar(n)
        elif self.sel:                                        # clic en el fondo: suelta el enfoque
            self.sel = None
            self.dibujar()

    def _doble_clic(self, e):
        n = self.nodo_en(e.x, e.y)
        if n:
            self._movido = False
            self.sel = n
            self.simular_ataque([n])

    def _mover(self, e):
        n = None if self._en_leyenda(e.x, e.y) else self.nodo_en(e.x, e.y, 12)
        if n != self.hover:
            self.hover = n
            self.lienzo.config(cursor="hand2" if n else "")

    def _filtrar_tipo(self, t):
        if self.resalte.get("filtro") == t:
            return self.resaltar()
        self.resaltar(nodos=[n for n, a in self.g.nodos.items() if a["tipo"] == t])
        self.resalte["filtro"] = t
        self.dibujar()

    def _zoom(self, x, y, factor):
        self.dx, self.dy = x - (x - self.dx) * factor, y - (y - self.dy) * factor
        self.escala *= factor
        self.dibujar()

    def nodo_en(self, x, y, radio=10):
        pos, mejor, dm = self._posiciones(), None, radio
        for n in self.g.nodos:
            nx, ny = self._xy(pos, n)
            d = math.hypot(nx - x, ny - y)
            if d <= dm:
                mejor, dm = n, d
        return mejor

    def seleccionar(self, n):
        """Clic en un nodo: lo enfoca, muestra sus datos y lo copia a los campos de la pestaña activa."""
        if n is None:
            return
        g = self.g
        self.sel = n
        self._onda(n, TIPO_COLOR.get(g.nodos[n]["tipo"], "#8899bb"), dur=0.9, alcance=3)
        self.info.config(text=f"{n} ({g.nodos[n]['tipo']}): recibe de {g.grado_entrada(n)}, envía a {g.grado_salida(n)} | "
                              f"{ {k: v for k, v in g.nodos[n].items() if k != 'tipo'} }")
        self.v_nodo.set(n)
        self.v_tipo.set(g.nodos[n]["tipo"])
        if self.nombre.get() == "Carding":
            self.v_ficha.set(n)
        elif self.nombre.get() == "Enrutamiento":
            (self.v_ruta_o if self.turno_ruta % 2 == 0 else self.v_ruta_d).set(n)
            self.turno_ruta += 1
        if not self.v_o.get() or self.v_d.get():          # conexión: primer clic = origen, segundo = destino
            self.v_o.set(n)
            self.v_d.set("")
        else:
            self.v_d.set(n)
        self.dibujar()


def main():
    App().mainloop()
