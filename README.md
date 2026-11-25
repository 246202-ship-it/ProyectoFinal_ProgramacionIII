# 🏦 OptiFin - Sistema de Análisis y Optimización de Redes Financieras

![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)
![Status](https://img.shields.io/badge/Estado-En%20Desarrollo-yellow)
![Course](https://img.shields.io/badge/Curso-Programaci%C3%B3n%20III-green)

Sistema algorítmico modular desarrollado en Python para modelar, analizar y optimizar operaciones en redes financieras representadas mediante estructuras de grafos. 

Este proyecto integra escenarios críticos de la operatividad bancaria —prevención de fraudes, enrutamiento óptimo de transacciones y distribución de liquidez hacia bóvedas— respaldados por un análisis riguroso de complejidad computacional y validación empírica[cite: 1, 2, 3].

---

## 📋 Tabla de Contenidos
1. [Arquitectura y Estructura del Proyecto](#-arquitectura-y-estructura-del-proyecto)
2. [Módulos Funcionales y Decisiones Algorítmicas](#-módulos-funcionales-y-decisiones-algorítmicas)
3. [Requisitos e Instalación](#-requisitos-e-instalación)
4. [Ejecución del Sistema](#-ejecución-del-sistema)
5. [Formato de Datos de Entrada](#-formato-de-datos-de-entrada)
6. [Ejecución de Pruebas Automatizadas](#-ejecución-de-pruebas-automatizadas)
7. [Equipo de Desarrollo](#-equipo-de-desarrollo)

---

## 📁 Arquitectura y Estructura del Proyecto

El repositorio mantiene una separación clara entre la interfaz, las estructuras de datos base, los módulos operativos, los conjuntos de datos simulados y las pruebas unitarias[cite: 7]:

```text
proyecto_optifin/
├── main.py                        # Punto de entrada principal del sistema
├── README.md                      # Documentación del proyecto
├── requirements.txt               # Dependencias y versiones exactas
├── .gitignore                     # Exclusión de entornos virtuales y temporales
├── data/                          # Datasets simulados de redes financieras
│   ├── transacciones.csv          # Red transaccional para detección de anomalías
│   ├── red_enrutamiento.csv       # Red interbancaria, ATMs y plataformas de pago
│   └── distribucion_liquidez.csv  # Red de bóvedas centrales, regionales y agencias
├── src/                           # Código fuente modular
│   ├── graph.py                   # Estructura de datos base (Grafo)
│   ├── gestion_red.py             # Módulo 1: Creación, carga, edición y visualización
│   ├── analisis_transacciones.py  # Módulo 2: Prevención de fraudes y lavado de activos
│   ├── enrutamiento_financiero.py # Módulo 3: Optimización de rutas y comisiones
│   ├── distribucion_liquidez.py   # Módulo 4: Flujo y abastecimiento de efectivo
│   ├── evaluacion_resultados.py   # Módulo 5: Benchmarking y métricas computacionales
│   └── utils.py                   # Funciones auxiliares y validaciones
├── tests/                         # Pruebas unitarias y escenarios de validación
│   ├── test_gestion_red.py
│   ├── test_transacciones.py
│   ├── test_enrutamiento.py
│   ├── test_liquidez.py
│   └── test_evaluacion.py
└── docs/                          # Documentación académica
    └── informe.pdf                # Informe técnico y sustentación teórica
```[cite: 7, 9]

---

## ⚙️ Módulos Funcionales y Decisiones Algorítmicas

Todas las operaciones operan sobre una representación unificada basada en **Listas de Adyacencia** (`src/graph.py`), soportando grafos dirigidos/no dirigidos y multipesos[cite: 4, 7].

| Módulo | Problema Operativo | Algoritmos Implementados *(Editar según su elección)* | Complejidad Temporal |
| :--- | :--- | :--- | :--- |
| **1. Gestión de Red** | Modelamiento de entidades (cuentas, ATMs, bóvedas) y carga/validación de datos[cite: 3, 4]. | Listas de Adyacencia / Validación de integridad[cite: 4] | $O(V + E)$ |
| **2. Análisis de Transacciones** | Rastreo de fondos, detección de ciclos, pitufeo (*smurfing*) y lavado de activos[cite: 4, 5]. | *[Ej. BFS / DFS / Tarjan (SCC)]* | *[Ej. $O(V + E)$]* |
| **3. Enrutamiento Financiero** | Minimización de comisiones y latencia en transferencias interbancarias y billeteras[cite: 5, 6]. | *[Ej. Dijkstra / Bellman-Ford / A\*]* | *[Ej. $O((V + E) \log V)$]* |
| **4. Distribución de Liquidez** | Abastecimiento óptimo de efectivo desde bóvedas centrales hacia agencias según capacidad[cite: 6]. | *[Ej. Edmonds-Karp / Dinic / Min-Cost Max-Flow]* | *[Ej. $O(V \cdot E^2)$]* |
| **5. Evaluación y Validación** | Comparación empírica de tiempos de ejecución, uso de memoria y escalabilidad[cite: 6, 7]. | Análisis asintótico vs. empírico (`time`, `tracemalloc`) | — |

> **Nota de Auditoría:** Los patrones identificados en el Módulo 2 constituyen indicadores computacionales de alerta temprana para revisión y no representan, por sí solos, prueba concluyente de ilícitos financieros[cite: 5].

---

## 🛠️ Requisitos e Instalación

### Prerrequisitos
* **Python:** Versión `3.10` o superior *(ajustar según tu entorno)*[cite: 9].
* **Git:** Para clonar el repositorio[cite: 9].

### Pasos de configuración

1. **Clonar el repositorio:**
   ```bash
   git clone [https://github.com/](https://github.com/)[TU-USUARIO]/[NOMBRE-DEL-REPO].git
   cd proyecto_optifin
   ```[cite: 9]

2. **Crear y activar un entorno virtual (recomendado):**
   * En **Linux / macOS**:
     ```bash
     python3 -m venv venv
     source venv/bin/activate
     ```
   * En **Windows**:
     ```bash
     python -m venv venv
     venv\Scripts\activate
     ```

3. **Instalar las dependencias:**
   ```bash
   pip install -r requirements.txt
   ```[cite: 9]

---

## 🚀 Ejecución del Sistema

Para iniciar la aplicación principal, ejecuta desde la raíz del proyecto:

```bash
python main.py
```

### Flujo de uso recomendado:
1. **Cargar Red:** Seleccionar la opción de carga desde `data/` (formato `.csv`, `.json` o `.txt`) o generar una red de prueba[cite: 4, 9].
2. **Seleccionar Escenario Operativo:** Navegar por los módulos de *Detección de Fraudes*, *Enrutamiento de Operaciones* o *Distribución de Liquidez*[cite: 2, 4, 5, 6].
3. **Visualizar y Exportar:** Generar las gráficas de la red financiera y revisar los reportes comparativos en consola/archivo[cite: 3, 4].

---

## 📊 Formato de Datos de Entrada

Los archivos ubicados en la carpeta `data/` permiten reproducir los casos de prueba documentados en `docs/informe.pdf`[cite: 7, 9]:

* **`data/transacciones.csv`**: Registra transferencias dirigidas entre cuentas.
  ```csv
  origen,destino,monto,fecha,riesgo
  CuentaA,CuentaB,4500.00,2026-11-01,0.15
  CuentaB,CuentaC,4450.00,2026-11-01,0.82
  ```[cite: 2, 4]
* **`data/red_enrutamiento.csv`**: Define canales interbancarios, ATMs y plataformas con sus costos y latencias[cite: 5].
  ```csv
  origen,destino,comision,tiempo_ms,disponible
  Banco_A,Camara_Compensacion,1.50,120,True
  Camara_Compensacion,Billetera_X,0.50,45,True
  ```[cite: 2, 5]
* **`data/distribucion_liquidez.csv`**: Modela la oferta de bóvedas centrales, demanda de agencias y capacidad máxima de transporte blindado[cite: 6].
  ```csv
  origen,destino,capacidad_max,costo_transporte
  Boveda_Central,Boveda_Regional_Sur,500000,250.00
  Boveda_Regional_Sur,Agencia_Centro,120000,80.00
  ```[cite: 6]

---

## 🧪 Ejecución de Pruebas Automatizadas

Para validar la integridad de las estructuras de datos, el cumplimiento de restricciones financieras y reproducir los resultados experimentales del informe, ejecuta la suite de pruebas en `tests/`[cite: 7, 8, 9]:

```bash
# Si utilizas pytest:
pytest tests/ -v

# O utilizando unittest nativo de Python:
python -m unittest discover -s tests
