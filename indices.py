"""
indices.py — palanka.lat
Descarga los datos que necesita el panel financiero personal:
  - mindicador.cl (sin API key): UF, dólar, UTM, tasa de desempleo
  - api.cmfchile.cl (requiere CMF_API_KEY): tasa hipotecaria promedio
    referencial (TIP, tipo Hipotecario UF), usada como valor por defecto
    en el comparador arriendo vs. compra
  - datos.odepa.gob.cl (CKAN, sin API key): precios de una canasta de
    alimentos. El resource_id cambia con el tiempo, así que se resuelve
    dinámicamente vía package_search + package_show. Si algo falla acá
    (la API no respondió durante las pruebas de este script — revisar
    una vez desplegado), la sección de alimentos queda en None y
    build_site.py la omite con gracia en vez de romper el sitio.

Nota sobre comisiones AFP: no vienen de una API (la Superintendencia de
Pensiones no expone una así de simple), así que se mantienen como tabla
fija en build_site.py, igual que INDICE_COSTO_VIDA_BASE en el proyecto de
indicadores — revisar cada cierto tiempo en https://queafp.cl/comisiones
o directamente en spensiones.cl, porque cambian.

Escribe todo a datos.json, que luego consume build_site.py.

Uso local:
    export CMF_API_KEY="tu_api_key"
    python3 indices.py
"""

import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

CMF_API_KEY = os.environ.get("CMF_API_KEY", "")
ARCHIVO_DATOS = "datos.json"

TIPOS_HIPOTECARIO = {
    14: "Hipotecario UF (>1 año, sobre 2.000 UF)",
    24: "Hipotecario UF (>1 año, hasta 2.000 UF)",
}

ODEPA_BASE = "https://datos.odepa.gob.cl/api/3/action"

# ---------------------------------------------------------------------------
# Kanasta Palanka — canasta de referencia propia (no la canasta básica
# oficial del INE), pensada para una familia de 2 adultos + 2 niños.
# Cantidades semanales: estimación referencial nuestra, confirmada por
# Felipe el 2026-07-17 — no provienen de una encuesta oficial.
# (clave, nombre, cantidad_semanal, unidad)
# ---------------------------------------------------------------------------
KANASTA_PALANKA = [
    ("pan", "Pan (Marraqueta)", 4.0, "kg"),
    ("papas", "Papas", 4.0, "kg"),
    ("cebolla", "Cebolla", 1.0, "kg"),
    ("tomate", "Tomate", 2.0, "kg"),
    ("palta", "Palta", 1.0, "kg"),
    ("pollo", "Pollo entero", 2.0, "kg"),
    ("vacuno", "Asado de vacuno", 1.5, "kg"),
    ("huevos", "Huevos", 12, "un"),
    ("leche", "Leche fluida entera", 5.0, "L"),
    ("arroz", "Arroz", 1.0, "kg"),
    ("aceite", "Aceite vegetal", 0.5, "L"),
    ("legumbres", "Legumbres (porotos)", 1.0, "kg"),
    ("fruta", "Fruta de estación", 4.0, "kg"),
]


def http_get(url, timeout=25, reintentos=4):
    """GET con reintentos: las APIs públicas a veces se cuelgan, y este
    script corre solo, sin nadie mirando."""
    ultimo_error = None
    for intento in range(1, reintentos + 1):
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0 Safari/537.36"
                    )
                },
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.read()
        except Exception as e:
            ultimo_error = e
            if intento < reintentos:
                print(f"  aviso: intento {intento} falló ({e}), reintentando...")
                time.sleep(2 * intento)
    raise ultimo_error


def http_get_json(url, timeout=25, reintentos=4):
    return json.loads(http_get(url, timeout=timeout, reintentos=reintentos).decode("utf-8"))


# ---------------------------------------------------------------------------
# mindicador.cl
# ---------------------------------------------------------------------------

def get_mindicador_actual():
    print("Descargando UF, dólar, UTM y desempleo de mindicador.cl ...")
    data = http_get_json("https://mindicador.cl/api")
    out = {}
    for campo in ("uf", "dolar", "utm", "tasa_desempleo"):
        if campo in data:
            out[campo] = {
                "nombre": data[campo]["nombre"],
                "unidad": data[campo]["unidad_medida"],
                "valor": data[campo]["valor"],
                "fecha": data[campo]["fecha"],
            }
    return out


# ---------------------------------------------------------------------------
# api.cmfchile.cl (TIP hipotecario) — mismo enfoque que inmo.heuristika.pro
# ---------------------------------------------------------------------------

def _extraer_items(data, clave, recurso):
    bloque = data.get(clave, [])
    if isinstance(bloque, list):
        return bloque
    if isinstance(bloque, dict):
        sub = bloque.get(recurso.upper(), [])
        return sub if isinstance(sub, list) else ([sub] if sub else [])
    return []


def get_tasa_hipotecaria_promedio():
    if not CMF_API_KEY:
        print("AVISO: no hay CMF_API_KEY definida, se omite tasa hipotecaria referencial.")
        return None

    print("Descargando tasa hipotecaria referencial (TIP) de la CMF ...")
    anio = datetime.now().year
    url = (
        f"https://api.cmfchile.cl/api-sbifv3/recursos_api/tip/{anio}"
        f"?apikey={CMF_API_KEY}&formato=json"
    )
    try:
        data = http_get_json(url)
    except Exception as e:
        print(f"  error al traer TIP: {e}")
        return None

    items = _extraer_items(data, "TIPs", "tip")
    ultimo_por_tipo = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            tipo = int(item.get("Tipo"))
        except (TypeError, ValueError):
            continue
        if tipo not in TIPOS_HIPOTECARIO:
            continue
        try:
            valor = float(item.get("Valor"))
        except (TypeError, ValueError):
            continue
        fecha = item.get("Fecha")
        if not fecha:
            continue
        actual = ultimo_por_tipo.get(tipo)
        if not actual or fecha > actual["fecha"]:
            ultimo_por_tipo[tipo] = {"fecha": fecha, "valor": valor}

    if not ultimo_por_tipo:
        print("  aviso: no se encontraron datos de TIP hipotecario para este año.")
        return None

    valores = [v["valor"] for v in ultimo_por_tipo.values()]
    fecha_mas_reciente = max(v["fecha"] for v in ultimo_por_tipo.values())
    promedio = round(sum(valores) / len(valores), 2)
    return {
        "nombre": "Tasa hipotecaria promedio referencial (TIP)",
        "unidad": "Porcentaje",
        "valor": promedio,
        "fecha": fecha_mas_reciente,
    }


# ---------------------------------------------------------------------------
# datos.odepa.gob.cl (CKAN) — precios de alimentos
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Kanasta Palanka — precios por producto y región, best-effort.
#
# Esto es deliberadamente defensivo: la API de ODEPA no respondió durante
# las pruebas de este script (posible bloqueo de red desde ese entorno, o
# que efectivamente no esté disponible), así que TODO lo de acá abajo está
# protegido con try/except — si algo falla, retorna None y build_site.py
# omite/deja en blanco lo correspondiente en vez de inventar un precio.
# Antes de confiar en esta sección, correr una vez con conexión real y
# revisar qué trae — probablemente haya que ajustar cómo se buscan los
# datasets y qué columnas se leen en _parsear_precios_por_region.
# ---------------------------------------------------------------------------

def _buscar_dataset_odepa(termino):
    url = f"{ODEPA_BASE}/package_search?q={urllib.parse.quote(termino)}"
    data = http_get_json(url, reintentos=2)
    resultados = data.get("result", {}).get("results", [])
    if not resultados:
        return None
    return resultados[0].get("id") or resultados[0].get("name")


def _recursos_csv_recientes(dataset_id, maximo=4):
    """Devuelve hasta `maximo` URLs de recursos CSV del dataset, del más
    reciente al más antiguo. Antes solo se usaba el más reciente, pero el
    reporte semanal de ODEPA no siempre cubre las mismas regiones cada
    semana (mercados que no reportaron ese período) — usar varios recursos
    recientes y fusionarlos (ver get_kanasta_palanka_precios) da más
    cobertura regional sin inventar ningún precio."""
    pkg = http_get_json(f"{ODEPA_BASE}/package_show?id={dataset_id}", reintentos=2)
    recursos = pkg.get("result", {}).get("resources", [])
    recursos_csv = [r for r in recursos if str(r.get("format", "")).lower() == "csv"]
    if not recursos_csv:
        return []
    recursos_csv.sort(key=lambda r: r.get("last_modified") or r.get("created") or "", reverse=True)
    return [r.get("url") for r in recursos_csv[:maximo] if r.get("url")]


# Codificación oficial de regiones (INE) — varios datasets de ODEPA traen el
# código numérico de región en vez del nombre (así se vio en producción:
# "10", "13", "15"... en vez de "Los Lagos", "Metropolitana", "Arica y
# Parinacota"). Se traduce acá para que la tabla del sitio muestre nombres.
REGION_CODIGO_NOMBRE = {
    "1": "Tarapacá",
    "2": "Antofagasta",
    "3": "Atacama",
    "4": "Coquimbo",
    "5": "Valparaíso",
    "6": "O'Higgins",
    "7": "Maule",
    "8": "Biobío",
    "9": "La Araucanía",
    "10": "Los Lagos",
    "11": "Aysén",
    "12": "Magallanes",
    "13": "Metropolitana",
    "14": "Los Ríos",
    "15": "Arica y Parinacota",
    "16": "Ñuble",
}


def _region_nombre(valor_crudo):
    """Normaliza el valor de la columna región: si es un código numérico
    (incluye formatos tipo "9.0" o "09"), lo traduce a nombre. Si ya viene
    como texto, lo deja tal cual."""
    valor = (valor_crudo or "").strip()
    if not valor:
        return None
    try:
        codigo = str(int(float(valor)))
    except (TypeError, ValueError):
        return valor
    return REGION_CODIGO_NOMBRE.get(codigo, valor)


def _parsear_precios_por_region(csv_bytes):
    """Intento genérico de leer un CSV de ODEPA y encontrar una columna de
    región y una de precio por nombre (no conocemos el esquema real, ver
    nota arriba). Si no encuentra columnas reconocibles, retorna {}."""
    import csv
    import io

    texto = csv_bytes.decode("utf-8", errors="ignore")
    lector = csv.DictReader(io.StringIO(texto))
    if not lector.fieldnames:
        return {}

    col_region = next(
        (c for c in lector.fieldnames if "region" in c.lower() or "región" in c.lower()), None
    )
    col_precio = next((c for c in lector.fieldnames if "precio" in c.lower()), None)
    if not col_region or not col_precio:
        return {}

    precios = {}
    for fila in lector:
        region = _region_nombre(fila.get(col_region))
        if not region:
            continue
        try:
            precio = float(str(fila.get(col_precio)).replace(".", "").replace(",", "."))
        except (TypeError, ValueError):
            continue
        precios[region] = precio  # última fila leída para esa región gana (asume orden cronológico)
    return precios


def get_kanasta_palanka_precios():
    """Best-effort: intenta traer el precio al consumidor por región de
    cada producto de la Kanasta Palanka. Devuelve un dict
    clave_producto -> {region: precio_unitario} | None.

    Fusiona los últimos recursos CSV disponibles del dataset (no solo el
    más reciente) para cubrir más regiones: se recorren de más antiguo a
    más nuevo, y cada uno pisa al anterior, así cada región queda con el
    precio más reciente disponible para ella, aunque no haya reportado en
    el archivo de esta semana. Esto no inventa ningún dato — solo evita
    perder una región que sí reportó precio hace poco.

    Igual que el resto de esta sección, esto no se pudo probar contra la
    API real desde este entorno — revisar una vez desplegado y ajustar el
    parseo de columnas en _parsear_precios_por_region si hace falta."""
    resultado = {}
    for clave, nombre, _cantidad, _unidad in KANASTA_PALANKA:
        try:
            dataset_id = _buscar_dataset_odepa(f"precio consumidor {nombre}")
            if not dataset_id:
                resultado[clave] = None
                continue
            urls_csv = _recursos_csv_recientes(dataset_id, maximo=4)
            if not urls_csv:
                resultado[clave] = None
                continue
            precios_region = {}
            for url_csv in reversed(urls_csv):  # más antiguo -> más nuevo
                try:
                    crudo = http_get(url_csv, reintentos=2)
                    precios_region.update(_parsear_precios_por_region(crudo))
                except Exception as e:
                    print(f"  aviso Kanasta Palanka ({nombre}, recurso {url_csv}): {e}")
            resultado[clave] = precios_region or None
        except Exception as e:
            print(f"  aviso Kanasta Palanka ({nombre}): {e}")
            resultado[clave] = None
    return resultado


def _mediana(valores):
    ordenados = sorted(valores)
    n = len(ordenados)
    mitad = n // 2
    if n % 2 == 0:
        return (ordenados[mitad - 1] + ordenados[mitad]) / 2
    return ordenados[mitad]


def _filtrar_outliers_precio(precios_region):
    """Los CSV de ODEPA a veces traen un valor mal cargado para una región
    (typo, unidad distinta, etc.) que dispara el promedio nacional. Filtro
    simple y robusto: si un precio se aleja demasiado de la mediana entre
    regiones (fuera de [0.4x, 2.5x]), se descarta para el cálculo del
    promedio nacional y del costo de esa región — mejor omitir un dato
    sospechoso que inventar un número, pero tampoco queremos que ensucie
    el promedio de todos los demás."""
    if not precios_region or len(precios_region) < 3:
        return dict(precios_region or {})
    mediana = _mediana(list(precios_region.values()))
    if mediana <= 0:
        return dict(precios_region)
    filtrados = {
        region: precio
        for region, precio in precios_region.items()
        if 0.4 * mediana <= precio <= 2.5 * mediana
    }
    return filtrados or dict(precios_region)


def calcular_costos_kanasta(precios_por_producto):
    """A partir de clave_producto -> {region: precio_unitario} | None,
    calcula el costo semanal por región y el promedio nacional (promedio
    de los precios unitarios disponibles entre regiones, por producto).
    Antes de promediar, filtra outliers evidentes por producto (ver
    _filtrar_outliers_precio) para que una región con un dato mal cargado
    no dispare el promedio nacional ni el costo de esa región."""
    precios_filtrados = {
        clave: _filtrar_outliers_precio(precios)
        for clave, precios in precios_por_producto.items()
    }

    regiones = set()
    for precios in precios_filtrados.values():
        if precios:
            regiones.update(precios.keys())

    costo_por_region = {}
    for region in regiones:
        total = 0.0
        productos_con_precio = 0
        for clave, _nombre, cantidad, _unidad in KANASTA_PALANKA:
            precios = precios_filtrados.get(clave)
            precio_region = precios.get(region) if precios else None
            if precio_region is not None:
                total += precio_region * cantidad
                productos_con_precio += 1
        if productos_con_precio > 0:
            costo_por_region[region] = {
                "monto": round(total),
                "productos_con_precio": productos_con_precio,
                "productos_totales": len(KANASTA_PALANKA),
            }

    total_nacional = 0.0
    productos_con_precio_nacional = 0
    for clave, _nombre, cantidad, _unidad in KANASTA_PALANKA:
        precios = precios_filtrados.get(clave)
        if precios:
            promedio_unitario = sum(precios.values()) / len(precios)
            total_nacional += promedio_unitario * cantidad
            productos_con_precio_nacional += 1

    costo_nacional = round(total_nacional) if productos_con_precio_nacional > 0 else None

    return costo_por_region, costo_nacional, productos_con_precio_nacional


def actualizar_historial_kanasta(historial, valor_hoy):
    """Un punto por día — si corre 2 veces el mismo día, reemplaza el
    punto en vez de duplicarlo (mismo patrón que el índice de costo de
    vida de indicadores.heuristika.pro). Si hoy no se pudo calcular un
    valor (falta algún componente en vivo), no se agrega ningún punto —
    mejor un hueco que un cero inventado. Genérica: sirve tanto para el
    historial semanal como el mensual."""
    if valor_hoy is None:
        return historial
    hoy = datetime.now().strftime("%Y-%m-%d")
    if historial and historial[-1]["fecha"] == hoy:
        historial[-1]["valor"] = valor_hoy
    else:
        historial.append({"fecha": hoy, "valor": valor_hoy})
    return historial[-90:]


# ---------------------------------------------------------------------------
# Kanasta Semanal y Kanasta Mensual — ampliación de Kanasta Palanka más allá
# de los alimentos, definida con Felipe el 2026-07-17/18. Familia de
# referencia: 2 adultos + 2 niños. Quedan fuera arriendo/dividendo y
# colegio, por decisión explícita.
#
# Kanasta Semanal = alimentos (ODEPA, en vivo) + bencina + supermercado otros
# Kanasta Mensual = (Kanasta Semanal x 4,33 semanas/mes) + cuentas básicas
#                    + internet/celulares + transporte público
#
# Todo lo que no es "alimentos" es un valor de referencia FIJO (no viene de
# una API), igual que las comisiones AFP — hay que revisarlo cada cierto
# tiempo, no se actualiza solo. Cada bloque documenta su fuente y fecha.
# ---------------------------------------------------------------------------

SEMANAS_POR_MES = 4.33

# --- Bencina ---------------------------------------------------------------
# 16.000 km/año (punto medio del rango familiar 14.000-18.000 km/año) /
# 52 semanas = ~308 km/semana, / 12,9 km/l (rendimiento mixto real de un
# auto promedio) = ~24 litros/semana.
BENCINA_LITROS_SEMANA = 24.0

# palanka.lat no tiene configuradas las credenciales CNE_EMAIL/CNE_PASSWORD
# (a diferencia de indicadores.heuristika.pro, que sí lee el precio real de
# la bencina 93 desde la CNE). Mientras no se agregue esa integración acá,
# este es un precio de referencia fijo de mercado — revisar cada cierto
# tiempo en https://bencinaenlinea.cl o similar.
BENCINA_PRECIO_REFERENCIA = 1175.0  # $/litro, referencia jul-2026

# --- Supermercado otros (aseo del hogar) ------------------------------------
# (clave, nombre, precio_promedio_4_cadenas, duracion_semanas)
# Precios cotizados por Felipe el 2026-07-18 en Líder/Jumbo/Unimarc/Santa
# Isabel, promediados. duracion_semanas es un supuesto propio (cuánto le
# dura el producto a la familia de referencia), no un dato observado.
SUPERMERCADO_OTROS = [
    ("papel_higienico", "Papel higiénico Confort Elite (4 rollos)", 3833, 1),
    ("detergente", "Detergente Omo polvo (2,7 kg)", 8958, 2),
    ("lavaloza", "Lavaloza (750 ml)", 2440, 3),
    ("cloro", "Cloro Clorinda gel (1 L)", 2055, 3),
    ("jabon", "Jabón líquido Ballerina", 1778, 3),
    ("pasta_dientes", "Pasta de dientes Colgate Triple Acción", 2435, 1),
    ("shampoo", "Shampoo Familand", 2240, 2),
    ("bolsas_basura", "Bolsas de basura Virutex negra (10 un)", 1278, 2),
]

# --- Cuentas básicas (mensual) ---------------------------------------------
# Luz: 225 kWh/mes (consumo estimado desde electrodomésticos: refrigerador,
# lavadora, secadora, TV x2, microondas, 6 ampolletas, más margen para
# hervidor y otros menores). Tarifa BT1, Concepción/CGE, Tramo 4
# (221-230 kWh), simulada en cuentadelaluz.cl el 2026-07-18: cargo fijo
# $1.064 + $258/kWh = $59.219.
CUENTA_LUZ_MES = 59219
# Agua: 20 m3/mes x $1.400/m3 (dato de mercado aportado por Felipe).
CUENTA_AGUA_MES = 28000
# Gas: 22,5 kg/mes (promedio anualizado entre ~15 kg en verano y ~30 kg en
# invierno) = 1,5 cilindros de 15 kg x $24.500 promedio (rango $23.000-
# $26.000 cotizado por Felipe).
CUENTA_GAS_MES = 36750

# --- Internet y celulares (mensual) -----------------------------------------
# Estimación de mercado (no cotizada contra un proveedor específico): plan
# wifi hogar estándar + 3 planes celular estándar (2 adultos + 1 hijo).
INTERNET_WIFI_MES = 17000
CELULAR_PLAN_MES = 10500
CELULAR_CANTIDAD_PLANES = 3

# --- Transporte público (semanal) -------------------------------------------
# Tarifa oficial Red Movilidad / Metro Región Metropolitana, vigente desde
# el 22-feb-2026. Supuesto: la madre vuelve en transporte público de lunes
# a viernes, 10 pasajes a la semana. Es parte de la Kanasta Semanal (junto a
# alimentos, bencina y supermercado otros), no un componente aparte del mes.
TRANSPORTE_PUBLICO_TARIFA = 795
TRANSPORTE_PUBLICO_PASAJES_SEMANA = 10


def calcular_bencina_semanal(precio_litro=None):
    precio = precio_litro if precio_litro is not None else BENCINA_PRECIO_REFERENCIA
    return round(BENCINA_LITROS_SEMANA * precio)


def calcular_supermercado_otros_semanal():
    return round(sum(precio / duracion for _clave, _nombre, precio, duracion in SUPERMERCADO_OTROS))


def calcular_cuentas_basicas_mes():
    return CUENTA_LUZ_MES + CUENTA_AGUA_MES + CUENTA_GAS_MES


def calcular_internet_celular_mes():
    return INTERNET_WIFI_MES + (CELULAR_PLAN_MES * CELULAR_CANTIDAD_PLANES)


def calcular_transporte_publico_semanal():
    return round(TRANSPORTE_PUBLICO_TARIFA * TRANSPORTE_PUBLICO_PASAJES_SEMANA)


def main():
    datos_previos = {}
    if os.path.exists(ARCHIVO_DATOS):
        try:
            with open(ARCHIVO_DATOS, "r", encoding="utf-8") as f:
                datos_previos = json.load(f)
        except Exception as e:
            print(f"aviso: no se pudo leer {ARCHIVO_DATOS} previo ({e}), se parte de cero.")

    kanasta_previa = datos_previos.get("kanasta_palanka", {})
    historial_semanal = kanasta_previa.get("semanal", {}).get("historial")
    if historial_semanal is None:
        historial_semanal = kanasta_previa.get("historial", [])  # datos.json de antes de la ampliación
    historial_mensual = kanasta_previa.get("mensual", {}).get("historial", [])

    macro = get_mindicador_actual()
    tasa_hipotecaria = get_tasa_hipotecaria_promedio()

    precios_kanasta = get_kanasta_palanka_precios()
    costo_por_region, costo_alimentos, productos_con_precio = calcular_costos_kanasta(precios_kanasta)

    costo_bencina = calcular_bencina_semanal()
    costo_otros = calcular_supermercado_otros_semanal()
    costo_transporte = calcular_transporte_publico_semanal()
    costo_semanal_total = (
        costo_alimentos + costo_bencina + costo_otros + costo_transporte
        if costo_alimentos is not None
        else None
    )
    historial_semanal = actualizar_historial_kanasta(historial_semanal, costo_semanal_total)

    cuentas_basicas_mes = calcular_cuentas_basicas_mes()
    internet_celular_mes = calcular_internet_celular_mes()
    costo_mensual_total = (
        round(costo_semanal_total * SEMANAS_POR_MES) + cuentas_basicas_mes + internet_celular_mes
        if costo_semanal_total is not None
        else None
    )
    historial_mensual = actualizar_historial_kanasta(historial_mensual, costo_mensual_total)

    kanasta_palanka = {
        "productos": [
            {"clave": clave, "nombre": nombre, "cantidad": cantidad, "unidad": unidad}
            for clave, nombre, cantidad, unidad in KANASTA_PALANKA
        ],
        "costo_por_region": costo_por_region,
        "costo_alimentos": costo_alimentos,
        "productos_con_precio": productos_con_precio,
        "productos_totales": len(KANASTA_PALANKA),
        "bencina": {
            "litros_semana": BENCINA_LITROS_SEMANA,
            "precio_referencia": BENCINA_PRECIO_REFERENCIA,
            "costo_semana": costo_bencina,
        },
        "supermercado_otros": {
            "items": [
                {
                    "clave": clave,
                    "nombre": nombre,
                    "precio_promedio": precio,
                    "duracion_semanas": duracion,
                    "costo_semana": round(precio / duracion),
                }
                for clave, nombre, precio, duracion in SUPERMERCADO_OTROS
            ],
            "costo_semana": costo_otros,
        },
        "semanal": {
            "costo_total": costo_semanal_total,
            "historial": historial_semanal,
        },
        "cuentas_basicas": {
            "luz_mes": CUENTA_LUZ_MES,
            "agua_mes": CUENTA_AGUA_MES,
            "gas_mes": CUENTA_GAS_MES,
            "total_mes": cuentas_basicas_mes,
        },
        "internet_celular": {
            "wifi_mes": INTERNET_WIFI_MES,
            "celular_mes": CELULAR_PLAN_MES,
            "cantidad_planes": CELULAR_CANTIDAD_PLANES,
            "total_mes": internet_celular_mes,
        },
        "transporte_publico": {
            "tarifa": TRANSPORTE_PUBLICO_TARIFA,
            "pasajes_semana": TRANSPORTE_PUBLICO_PASAJES_SEMANA,
            "costo_semana": costo_transporte,
        },
        "mensual": {
            "costo_total": costo_mensual_total,
            "historial": historial_mensual,
        },
    }

    salida = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "macro": macro,
        "tasa_hipotecaria": tasa_hipotecaria,
        "kanasta_palanka": kanasta_palanka,
    }

    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    print(f"OK -> {ARCHIVO_DATOS}")


if __name__ == "__main__":
    main()
