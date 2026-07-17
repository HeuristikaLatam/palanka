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
ODEPA_TERMINOS_BUSQUEDA = ["precios consumidor canasta", "precios al consumidor"]


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

def get_datos_odepa():
    """Intenta resolver dinámicamente un dataset de precios al consumidor
    en el portal CKAN de ODEPA y traer su recurso CSV más reciente.

    Esto es best-effort a propósito: la API de ODEPA no respondió durante
    las pruebas de este script (posible bloqueo de red o cambio de
    disponibilidad), así que TODO este bloque está protegido — si algo
    falla, se retorna None y build_site.py omite la sección con gracia.
    Antes de confiar en esta sección, correr una vez con conexión real y
    revisar qué trae.
    """
    try:
        dataset_id = None
        for termino in ODEPA_TERMINOS_BUSQUEDA:
            url = f"{ODEPA_BASE}/package_search?q={urllib.parse.quote(termino)}"
            data = http_get_json(url, reintentos=2)
            resultados = data.get("result", {}).get("results", [])
            if resultados:
                dataset_id = resultados[0].get("id") or resultados[0].get("name")
                break
        if not dataset_id:
            print("  aviso ODEPA: no se encontró ningún dataset de precios al consumidor.")
            return None

        url_pkg = f"{ODEPA_BASE}/package_show?id={dataset_id}"
        pkg = http_get_json(url_pkg, reintentos=2)
        recursos = pkg.get("result", {}).get("resources", [])
        recursos_csv = [
            r for r in recursos
            if str(r.get("format", "")).lower() in ("csv", "xlsx")
        ]
        if not recursos_csv:
            print("  aviso ODEPA: el dataset no tiene recursos CSV/XLSX.")
            return None

        # nos quedamos con el más reciente según su fecha de creación/modificación
        recursos_csv.sort(key=lambda r: r.get("last_modified") or r.get("created") or "", reverse=True)
        recurso = recursos_csv[0]

        return {
            "dataset": pkg.get("result", {}).get("title", dataset_id),
            "recurso_url": recurso.get("url"),
            "recurso_nombre": recurso.get("name"),
            "actualizado": recurso.get("last_modified") or recurso.get("created"),
        }
    except Exception as e:
        print(f"  aviso ODEPA: no se pudo resolver el dataset ({e}). Se omite la sección.")
        return None


def main():
    macro = get_mindicador_actual()
    tasa_hipotecaria = get_tasa_hipotecaria_promedio()
    odepa = get_datos_odepa()

    salida = {
        "generado": datetime.now(timezone.utc).isoformat(),
        "macro": macro,
        "tasa_hipotecaria": tasa_hipotecaria,
        "odepa": odepa,
    }

    with open(ARCHIVO_DATOS, "w", encoding="utf-8") as f:
        json.dump(salida, f, ensure_ascii=False, indent=2)

    print(f"OK -> {ARCHIVO_DATOS}")


if __name__ == "__main__":
    main()
