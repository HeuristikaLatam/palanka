"""
build_site.py — palanka.lat
Lee datos.json (generado por indices.py) y escribe index.html: el panel
financiero personal de Palanka — indicadores del día, calculadora de
sueldo bruto a líquido (dependiente y boleta de honorarios), comparador
arriendo vs. compra, simulador de inversión (DCA) y una sección de
precios de alimentos (ODEPA), con la identidad visual de Palanka (azul
marino + ámbar).

Fuentes verificadas manualmente al escribir este archivo (julio 2026):
  - Tabla de Impuesto Único de Segunda Categoría: sii.cl (tramos y
    factores expresados en UTM, así se mantienen vigentes aunque cambie
    el valor de la UTM mes a mes).
  - Retención boletas de honorarios 2026: 15,25% (Ley 21.133, sii.cl).
  - Tope imponible AFP/salud: 90 UF. Tope seguro cesantía: 135,2 UF
    (Superintendencia de Pensiones, 2026).
  - Comisión AFP por administradora: queAFP.cl / Superintendencia de
    Pensiones, julio 2026 — estos valores SÍ cambian con cierta
    frecuencia y no vienen de una API, así que conviene revisarlos cada
    tanto en https://queafp.cl/comisiones.

Uso local:
    python3 indices.py
    python3 build_site.py
    open index.html
"""

import json
from datetime import datetime

with open("datos.json", "r", encoding="utf-8") as f:
    DATA = json.load(f)


def fmt(valor, unidad, key=None):
    if unidad == "Porcentaje":
        return f"{valor:.2f}%"
    if key == "uf":
        return f"${valor:,.2f}".replace(",", "@").replace(".", ",").replace("@", ".")
    return f"${valor:,.0f}".replace(",", ".")


def fecha_legible(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d-%m-%Y")
    except Exception:
        return iso or "—"


def fecha_hora_legible(iso):
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%d-%m-%Y a las %H:%M")
    except Exception:
        return iso or "—"


macro = DATA.get("macro", {})
tasa_hip = DATA.get("tasa_hipotecaria")
kanasta = DATA.get("kanasta_palanka", {})

# ---------------------------------------------------------------------------
# Tablas fijas usadas por las calculadoras (ver notas de fuente arriba)
# ---------------------------------------------------------------------------

# (clave, nombre, comisión %)
AFP_COMISIONES = [
    ("uno", "AFP Uno", 0.46),
    ("modelo", "AFP Modelo", 0.58),
    ("planvital", "AFP PlanVital", 1.16),
    ("habitat", "AFP Habitat", 1.27),
    ("capital", "AFP Capital", 1.44),
    ("cuprum", "AFP Cuprum", 1.44),
    ("provida", "AFP ProVida", 1.45),
]

# (desde_utm, hasta_utm o None, factor, rebaja_utm) — Impuesto Único 2da Categoría
TRAMOS_IMPUESTO_UTM = [
    (0, 13.5, 0, 0),
    (13.5, 30, 0.04, 0.54),
    (30, 50, 0.08, 1.74),
    (50, 70, 0.135, 4.49),
    (70, 90, 0.23, 11.14),
    (90, 120, 0.304, 17.80),
    (120, 150, 0.35, 23.32),
    (150, None, 0.40, 30.82),
]

TOPE_IMPONIBLE_UF = 90.0       # AFP y salud
TOPE_CESANTIA_UF = 135.2
RETENCION_BOLETA_PCT = 15.25   # vigente 2026, sube a 16% en 2027 y 17% en 2028
COTIZACION_AFP_PCT = 10.0
COTIZACION_SALUD_PCT = 7.0
CESANTIA_TRABAJADOR_PCT = 0.6  # solo contrato indefinido

# ---------------------------------------------------------------------------
# KPIs del resumen
# ---------------------------------------------------------------------------

KPI_ORDEN = [("uf", "UF"), ("dolar", "Dólar obs."), ("tasa_desempleo", "Desempleo")]

kpi_cards = ""
for key, label in KPI_ORDEN:
    d = macro.get(key)
    if not d:
        continue
    kpi_cards += f"""
    <div class="kpi">
      <div class="kpi-label">{label}</div>
      <div class="kpi-val">{fmt(d['valor'], d['unidad'], key)}</div>
      <div class="kpi-fecha">{fecha_legible(d['fecha'])}</div>
    </div>"""

# ---------------------------------------------------------------------------
# Kanasta Palanka — canasta de referencia propia (2 adultos + 2 niños,
# cantidades semanales estimadas, no oficiales). Precios desde ODEPA,
# best-effort — ver notas de fuente en indices.py.
# ---------------------------------------------------------------------------

KANASTA_PALANKA_INFO = [
    ("Pan (Marraqueta)", 4.0, "kg"),
    ("Papas", 4.0, "kg"),
    ("Cebolla", 1.0, "kg"),
    ("Tomate", 2.0, "kg"),
    ("Palta", 1.0, "kg"),
    ("Pollo entero", 2.0, "kg"),
    ("Asado de vacuno", 1.5, "kg"),
    ("Huevos", 12, "un"),
    ("Leche fluida entera", 5.0, "L"),
    ("Arroz", 1.0, "kg"),
    ("Aceite vegetal", 0.5, "L"),
    ("Legumbres (porotos)", 1.0, "kg"),
    ("Fruta de estación", 4.0, "kg"),
]

kanasta_costo_alimentos = kanasta.get("costo_alimentos")
kanasta_productos_con_precio = kanasta.get("productos_con_precio", 0)
kanasta_productos_totales = kanasta.get("productos_totales", len(KANASTA_PALANKA_INFO))

kanasta_bencina = kanasta.get("bencina", {})
kanasta_otros = kanasta.get("supermercado_otros", {})
kanasta_otros_items = kanasta_otros.get("items", [])
kanasta_cuentas = kanasta.get("cuentas_basicas", {})
kanasta_internet = kanasta.get("internet_celular", {})
kanasta_transporte = kanasta.get("transporte_publico", {})

kanasta_semanal = kanasta.get("semanal", {})
kanasta_semanal_total = kanasta_semanal.get("costo_total")
kanasta_semanal_historial = kanasta_semanal.get("historial", [])

kanasta_mensual = kanasta.get("mensual", {})
kanasta_mensual_total = kanasta_mensual.get("costo_total")
kanasta_mensual_historial = kanasta_mensual.get("historial", [])


def _fmt_cantidad(cantidad, unidad):
    if unidad == "un":
        return f"{int(cantidad)} un"
    texto = f"{cantidad:g}".replace(".", ",")
    return f"{texto} {unidad}"


kanasta_productos_chips = "".join(
    f"""
      <div class="kanasta-producto-chip"><span class="nombre">{nombre}</span><span class="cantidad">{_fmt_cantidad(cantidad, unidad)}</span></div>"""
    for nombre, cantidad, unidad in KANASTA_PALANKA_INFO
)
kanasta_productos_html = f"""
      <div class="kanasta-productos-grid">{kanasta_productos_chips}
      </div>"""

kanasta_otros_chips = "".join(
    f"""
      <div class="kanasta-producto-chip"><span class="nombre">{item['nombre']}</span><span class="cantidad">{fmt(item['costo_semana'], 'Pesos')}/sem</span></div>"""
    for item in kanasta_otros_items
) or '<div class="kanasta-chart-empty">Sin datos de supermercado otros.</div>'
kanasta_otros_html = f"""
      <div class="kanasta-productos-grid">{kanasta_otros_chips}
      </div>"""

kanasta_semanal_val = fmt(kanasta_semanal_total, "Pesos") if kanasta_semanal_total else "—"
kanasta_semanal_sub = (
    f"Alimentos {fmt(kanasta_costo_alimentos, 'Pesos')} + bencina {fmt(kanasta_bencina.get('costo_semana', 0), 'Pesos')} + "
    f"aseo {fmt(kanasta_otros.get('costo_semana', 0), 'Pesos')} + transporte {fmt(kanasta_transporte.get('costo_semana', 0), 'Pesos')}"
    if kanasta_semanal_total
    else "Aún sin datos suficientes de ODEPA"
)

kanasta_mensual_val = fmt(kanasta_mensual_total, "Pesos") if kanasta_mensual_total else "—"
kanasta_mensual_sub = (
    "Kanasta Semanal x 4,33 + cuentas básicas + internet/celulares"
    if kanasta_mensual_total
    else "Aún sin datos suficientes de ODEPA"
)


def _kanasta_chart_js(canvas_id, historial):
    if len(historial) >= 2:
        html = f'<canvas id="{canvas_id}"></canvas>'
        labels = json.dumps([fecha_legible(p["fecha"]) for p in historial])
        valores = json.dumps([p["valor"] for p in historial])
        js = f"""
    (function() {{
      new Chart(document.getElementById('{canvas_id}'), {{
        type: 'line',
        data: {{
          labels: {labels},
          datasets: [{{
            data: {valores},
            borderColor: '#dfa25b',
            backgroundColor: '#dfa25b22',
            borderWidth: 2,
            pointRadius: 3,
            pointHoverRadius: 5,
            pointBackgroundColor: '#dfa25b',
            tension: 0.25,
            fill: true,
          }}]
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          plugins: {{
            legend: {{ display: false }},
            tooltip: {{
              backgroundColor: '#1c2838',
              borderColor: '#34465d',
              borderWidth: 1,
              titleColor: '#dfa25b',
              bodyColor: '#f4f6f8',
              padding: 10,
              displayColors: false,
            }},
          }},
          scales: {{
            x: {{ ticks: {{ color: '#9fb0c3', font: {{ size: 10 }}, maxRotation: 0 }}, grid: {{ display: false }} }},
            y: {{ ticks: {{ color: '#9fb0c3', font: {{ size: 10 }} }}, grid: {{ color: '#34465d' }} }}
          }}
        }}
      }});
    }})();"""
        return html, js
    html = '<div class="kanasta-chart-empty">Con un solo registro todavía no hay curva que mostrar — vuelve en unos días para ver la tendencia.</div>'
    return html, ""


kanasta_semanal_chart_html, kanasta_semanal_chart_js = _kanasta_chart_js("chartKanastaSemanal", kanasta_semanal_historial)
kanasta_mensual_chart_html, kanasta_mensual_chart_js = _kanasta_chart_js("chartKanastaMensual", kanasta_mensual_historial)
kanasta_chart_js = kanasta_semanal_chart_js + "\n" + kanasta_mensual_chart_js

# Desglose por categoría de la Kanasta Mensual — tarjetas con barra de
# proporción en vez de una tabla plana, para que destaque el peso relativo
# de cada categoría dentro del total.
if kanasta_mensual_total:
    kanasta_semanal_mensualizado = round((kanasta_semanal_total or 0) * 4.33)
    categorias = [
        ("Kanasta Semanal", "Alimentos + bencina + aseo del hogar + transporte público, x 4,33 semanas", kanasta_semanal_mensualizado),
        ("Cuentas básicas", "Luz + agua + gas", kanasta_cuentas.get("total_mes", 0)),
        ("Internet y celulares", "Wifi hogar + 3 planes celular", kanasta_internet.get("total_mes", 0)),
    ]
    filas = ""
    for nombre, detalle, monto in categorias:
        pct = round((monto / kanasta_mensual_total) * 100) if kanasta_mensual_total else 0
        filas += f"""
      <div class="cat-row">
        <div class="cat-row-top">
          <div>
            <div class="cat-label">{nombre}</div>
            <div class="cat-detalle">{detalle}</div>
          </div>
          <div class="cat-amount-wrap">
            <div class="cat-amount">{fmt(monto, 'Pesos')}</div>
            <div class="cat-pct">{pct}%</div>
          </div>
        </div>
        <div class="cat-bar"><div class="cat-bar-fill" style="width:{pct}%;"></div></div>
      </div>"""
    kanasta_categorias_html = f'<div class="kanasta-categorias">{filas}\n    </div>'
else:
    kanasta_categorias_html = '<div class="kanasta-chart-empty">Sin datos suficientes todavía</div>'

# ---------------------------------------------------------------------------
# Opciones de AFP para el <select>
# ---------------------------------------------------------------------------

afp_options_html = "\n".join(
    f'<option value="{comision}">{nombre} ({comision:.2f}%)</option>'
    for _clave, nombre, comision in AFP_COMISIONES
)

cargado_en = fecha_hora_legible(DATA.get("generado", ""))
uf_valor = macro.get("uf", {}).get("valor")
utm_valor = macro.get("utm", {}).get("valor")
tasa_hip_valor = tasa_hip["valor"] if tasa_hip else 4.8  # referencia si no hay datos CMF

# ---------------------------------------------------------------------------
# Diagnóstico "¿Cómo están tus finanzas personales?" — 8 preguntas, formato
# nunca/a veces/siempre (0/1/2 puntos). El área con puntaje más bajo es la
# "más desatendida"; en caso de empate manda DIAGNOSTICO_PRIORIDAD (definida
# con Felipe el 2026-07-18: deudas y fondo de emergencia primero, por ser
# las más urgentes de resolver).
# ---------------------------------------------------------------------------

DIAGNOSTICO_PREGUNTAS = [
    ("emergencia", "Fondo de emergencia", "¿Apartas algo de plata cada mes para tener un colchón de emergencia?"),
    ("deudas", "Deudas", "¿Tus deudas (tarjetas, créditos) las pagas sin generar intereses por atraso?"),
    ("orden", "Orden de dinero", "¿Tienes una idea clara de en qué se te va la plata cada mes?"),
    ("inversion", "Ahorro e inversión", "¿Haces crecer tu plata con algo más que la cuenta corriente (depósitos, fondos, acciones)?"),
    ("apv", "Jubilación / APV", "¿Has hecho algo por tu jubilación además de la cotización obligatoria?"),
    ("seguros", "Seguros", "¿Tienes en regla tus seguros básicos (salud, vida si tienes dependientes, hogar)?"),
    ("metas", "Metas financieras", "¿Tienes alguna meta financiera con monto y fecha (no solo \"ahorrar más\")?"),
    ("educacion", "Educación financiera", "¿Te informas sobre finanzas personales más allá de lo que te exige el día a día?"),
]

DIAGNOSTICO_PRIORIDAD = ["deudas", "emergencia", "orden", "inversion", "apv", "seguros", "metas", "educacion"]

DIAGNOSTICO_RESULTADOS = {
    "emergencia": "Tu colchón de emergencia necesita cariño. No se trata de tener guardada una fortuna — partir con lo que puedas, cada mes, ya hace una diferencia enorme el día que algo se complica.",
    "deudas": "Ojo con tus deudas — no es un reto, es solo una alerta amigable: los intereses por atraso son de los gastos más caros y silenciosos que existen. No hace falta resolverlo todo hoy, pero sí vale la pena anotar qué debes, a quién y a qué tasa, para no perderle la pista.",
    "orden": "Te falta un poco de orden con la plata del día a día. No hace falta anotar cada peso — basta con tener una idea clara de en qué se te va el mes, para decidir con más tranquilidad.",
    "inversion": "Tu plata está durmiendo. Dejarla quieta en la cuenta corriente significa que va perdiendo valor con el tiempo — no hace falta ser experto para empezar con algo simple y de a poco.",
    "apv": "Tu jubilación te está esperando. La cotización obligatoria sola, para la mayoría, no alcanza — vale la pena mirar el simulador de APV de este panel y ver qué opciones tienes.",
    "seguros": "Sería bueno revisar tus seguros. No es para asustarte, pero un imprevisto de salud o un accidente sin cobertura puede cambiarte los planes de un día para otro.",
    "metas": "Te falta ponerle nombre y fecha a tus metas. \"Ahorrar más\" es difícil de lograr porque es difícil de medir — un monto y una fecha hacen todo mucho más concreto.",
    "educacion": "Te vendría bien informarte un poco más sobre tus finanzas. No hace falta ser experto, pero entender lo básico (tasas, inflación, cómo funciona tu AFP) te da más control sobre tus decisiones.",
}

diagnostico_preguntas_js = json.dumps(
    [{"clave": clave, "area": area, "pregunta": pregunta} for clave, area, pregunta in DIAGNOSTICO_PREGUNTAS],
    ensure_ascii=False,
)
diagnostico_prioridad_js = json.dumps(DIAGNOSTICO_PRIORIDAD, ensure_ascii=False)
diagnostico_resultados_js = json.dumps(DIAGNOSTICO_RESULTADOS, ensure_ascii=False)

# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

HTML = f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Panel Financiero · Palanka</title>
<style>
  :root{{
    --bg:#1c2838; --card:#243347; --line:#34465d; --text:#f4f6f8;
    --muted:#9fb0c3; --amber:#dfa25b;
  }}
  *{{box-sizing:border-box;}}
  body{{
    margin:0; background:var(--bg); color:var(--text);
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    padding:32px 24px 60px;
  }}
  .wrap{{max-width:1000px; margin:0 auto;}}

  .header{{position:relative; display:flex; align-items:center; justify-content:center; margin-bottom:6px;}}
  .header-title{{text-align:center;}}
  .page-title{{font-size:24px; font-weight:700; letter-spacing:.01em;}}
  .page-title .flag{{font-size:20px;}}
  .header-logo{{position:absolute; right:0; top:0; display:flex; flex-direction:column; align-items:flex-end; gap:6px;}}
  .brand-mark{{
    width:36px; height:36px; border-radius:50%; background:var(--amber);
    display:flex; align-items:center; justify-content:center;
    font-weight:800; font-size:16px; color:var(--bg);
  }}
  .brand-name{{font-size:11px; font-weight:600; letter-spacing:.08em; color:var(--muted);}}
  .brand-tagline{{
    font-size:11px; color:var(--muted); letter-spacing:.12em; text-transform:uppercase;
    display:flex; align-items:center; justify-content:center; gap:10px; margin:14px 0 6px;
  }}
  .brand-tagline .dash{{display:inline-block; width:22px; height:1px; background:var(--amber);}}
  .update-note{{font-size:11px; color:var(--muted); line-height:1.6; margin-bottom:28px; text-align:center;}}

  h1{{font-size:14px; font-weight:600; color:var(--muted); text-transform:uppercase;
     letter-spacing:.08em; margin:0 0 4px;}}
  .section-sub{{font-size:12px; color:var(--muted); margin:0 0 18px;}}
  .section{{padding:32px 0; border-top:1px solid var(--line);}}
  .section:first-of-type{{border-top:none; padding-top:0;}}

  .subhead-box{{
    border:1px solid var(--amber); border-radius:8px; padding:8px 14px; margin:0 0 16px;
    font-size:11px; text-transform:uppercase; letter-spacing:.08em; color:var(--amber);
    display:inline-block;
    background:linear-gradient(135deg, rgba(223,162,91,.12), rgba(223,162,91,0));
  }}

  .kpis{{display:flex; gap:12px; flex-wrap:wrap;}}
  .kpi{{
    flex:1 1 150px; background:var(--card); border:1px solid var(--line);
    border-radius:10px; padding:16px 18px;
  }}
  .kpi-label{{font-size:11px; color:var(--muted); margin-bottom:6px;}}
  .kpi-val{{font-size:20px; font-weight:700; font-variant-numeric:tabular-nums;}}
  .kpi-fecha{{font-size:10px; color:var(--muted); margin-top:6px;}}

  .tool-box{{background:var(--card); border:1px solid var(--line); border-radius:10px; padding:22px;}}
  .field-grid{{display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:14px; margin-bottom:18px;}}
  .field label{{display:block; font-size:11px; color:var(--muted); margin-bottom:6px;}}
  .field input, .field select{{
    width:100%; background:var(--bg); border:1px solid var(--line); border-radius:6px;
    color:var(--text); padding:8px 10px; font-size:14px; font-family:inherit;
  }}
  .field-check{{display:flex; align-items:center; gap:8px; font-size:12px; color:var(--text); margin-bottom:14px;}}

  .tabs{{display:flex; gap:8px; margin-bottom:18px;}}
  .tab-btn{{
    background:var(--bg); border:1px solid var(--line); border-radius:20px;
    padding:8px 18px; font-size:12px; color:var(--muted); cursor:pointer; font-family:inherit;
  }}
  .tab-btn.active{{border-color:var(--amber); color:var(--amber); font-weight:600;}}
  .tab-panel{{display:none;}}
  .tab-panel.active{{display:block;}}

  .btn{{
    background:var(--amber); color:#1c2838; border:none; border-radius:20px;
    padding:10px 22px; font-size:13px; font-weight:700; cursor:pointer; font-family:inherit;
  }}
  .btn:hover{{opacity:.9;}}

  .resultado{{margin-top:20px; display:none;}}
  .resultado.show{{display:block;}}
  .resultado-grid{{display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:12px; margin-top:14px;}}
  .resultado-item{{background:var(--bg); border:1px solid var(--line); border-radius:8px; padding:12px 14px;}}
  .resultado-item-label{{font-size:10px; color:var(--muted); margin-bottom:4px;}}
  .resultado-item-val{{font-size:16px; font-weight:700; font-variant-numeric:tabular-nums;}}
  .resultado-destacado{{color:var(--amber); font-size:24px; font-weight:800; margin-bottom:4px;}}
  .resultado-nota{{font-size:11px; color:var(--muted); margin-top:14px; line-height:1.6;}}
  .aviso-box{{
    border:1px solid var(--amber); border-radius:8px; padding:12px 16px; margin-top:16px;
    font-size:11px; color:var(--text); line-height:1.6;
    background:linear-gradient(135deg, rgba(223,162,91,.10), rgba(223,162,91,0));
  }}
  .validacion-box{{
    display:none; border:1px solid #e2735f; border-radius:8px; padding:11px 15px; margin-top:14px;
    font-size:12px; color:#ffcfc5; line-height:1.5;
    background:linear-gradient(135deg, rgba(226,115,95,.14), rgba(226,115,95,0));
  }}

  .table-scroll{{overflow-x:auto; -webkit-overflow-scrolling:touch; margin-top:10px;}}
  .proyeccion-table{{width:100%; border-collapse:collapse; font-size:13px;}}
  .proyeccion-table th, .proyeccion-table td{{padding:8px 10px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap;}}
  .proyeccion-table th:first-child, .proyeccion-table td:first-child{{text-align:left; color:var(--muted);}}
  .btn-secondary{{background:transparent; border:1px solid var(--amber); color:var(--amber);}}
  .btn-secondary:hover{{background:rgba(223,162,91,.1); opacity:1;}}

  .card-box{{background:var(--card); border:1px solid var(--line); border-radius:10px; padding:20px;}}
  .card-box.placeholder{{opacity:.6;}}
  .card-box-title{{font-size:13px; font-weight:700; color:var(--amber); margin-bottom:8px;}}
  .card-box-text{{font-size:12px; color:var(--muted); line-height:1.6;}}
  .odepa-link{{display:inline-block; margin-top:12px; color:var(--amber); font-size:12px; text-decoration:none; font-weight:600;}}

  .footer{{margin-top:36px; font-size:11px; color:var(--muted); line-height:1.6;}}
  .footer a{{color:var(--amber); text-decoration:none;}}

  @media (max-width: 480px){{
    body{{padding:20px 14px 44px;}}
    .header{{flex-direction:column; align-items:center; gap:10px;}}
    .header-logo{{position:static; align-items:center;}}
    .page-title{{font-size:19px;}}
    .field-grid{{grid-template-columns:1fr;}}
  }}

  .kanasta-productos-grid{{
    display:grid; grid-template-columns:repeat(auto-fill,minmax(180px,1fr)); gap:8px; margin:14px 0 4px;
  }}
  .kanasta-producto-chip{{
    background:var(--bg); border:1px solid var(--line); border-radius:8px; padding:8px 12px;
    font-size:12px; display:flex; align-items:center; justify-content:space-between; gap:8px;
  }}
  .kanasta-producto-chip .nombre{{color:var(--text);}}
  .kanasta-producto-chip .cantidad{{color:var(--amber); font-variant-numeric:tabular-nums; white-space:nowrap; font-weight:600;}}

  .ejemplos-table{{width:100%; border-collapse:collapse; font-size:12.5px; margin:16px 0 6px;}}
  .ejemplos-table th{{
    text-align:left; font-size:10.5px; text-transform:uppercase; letter-spacing:.06em;
    color:var(--muted); border-bottom:1px solid var(--line); padding:7px 8px;
  }}
  .ejemplos-table td{{padding:8px; border-bottom:1px solid var(--line); color:var(--text); vertical-align:top;}}
  .ejemplos-table td.riesgo-bajo{{color:#8fd19e;}}
  .ejemplos-table td.riesgo-medio{{color:var(--amber);}}
  .ejemplos-table td.riesgo-alto{{color:#e2735f;}}

  .kanasta-box{{
    display:grid; grid-template-columns:1fr 1.4fr; gap:0;
    background:var(--card); border:1px solid var(--line); border-radius:14px;
    overflow:hidden; margin:18px 0 26px;
  }}
  .kanasta-col{{padding:26px 24px; display:flex; flex-direction:column;}}
  .kanasta-col + .kanasta-col{{border-left:1px solid var(--line);}}
  .kanasta-col-title{{
    font-size:11px; font-weight:700; letter-spacing:.08em; text-transform:uppercase;
    color:var(--amber); margin-bottom:10px;
  }}
  .kanasta-hoy{{align-items:center; justify-content:center; text-align:center;}}
  .kanasta-hoy-val{{font-size:42px; font-weight:800; color:var(--amber); line-height:1.1;}}
  .kanasta-hoy-sub{{font-size:12px; color:var(--muted); margin-top:8px;}}
  .kanasta-hoy-nota{{font-size:11px; color:var(--muted); margin-top:14px; text-transform:uppercase; letter-spacing:.06em;}}
  .kanasta-grafico{{justify-content:center;}}
  .kanasta-chart-wrap{{position:relative; height:200px; width:100%;}}
  .kanasta-chart-empty{{
    font-size:12.5px; color:var(--muted); text-align:center; padding:24px 8px;
    display:flex; align-items:center; justify-content:center; height:100%;
  }}
  @media (max-width: 720px){{
    .kanasta-box{{grid-template-columns:1fr;}}
    .kanasta-col + .kanasta-col{{border-left:none; border-top:1px solid var(--line);}}
  }}

  .kanasta-categorias{{display:flex; flex-direction:column; gap:14px; margin-top:14px;}}
  .cat-row{{
    background:var(--card); border:1px solid var(--line); border-radius:12px; padding:18px 20px;
  }}
  .cat-row-top{{display:flex; align-items:flex-start; justify-content:space-between; gap:16px; margin-bottom:12px;}}
  .cat-label{{font-size:15px; font-weight:700; color:var(--text);}}
  .cat-detalle{{font-size:11.5px; color:var(--muted); margin-top:3px;}}
  .cat-amount-wrap{{text-align:right; flex-shrink:0;}}
  .cat-amount{{font-size:20px; font-weight:800; color:var(--amber); font-variant-numeric:tabular-nums; white-space:nowrap;}}
  .cat-pct{{font-size:11px; color:var(--muted); margin-top:2px;}}
  .cat-bar{{height:8px; border-radius:4px; background:var(--bg); overflow:hidden;}}
  .cat-bar-fill{{height:100%; border-radius:4px; background:linear-gradient(90deg, #b9793a, #dfa25b, #f0c98a);}}

  .diag-progreso-wrap{{margin-bottom:22px;}}
  .diag-progreso-bar{{height:6px; border-radius:3px; background:var(--bg); overflow:hidden;}}
  .diag-progreso-fill{{height:100%; border-radius:3px; background:var(--amber); transition:width .3s ease;}}
  .diag-progreso-label{{font-size:11px; color:var(--muted); margin-top:8px; text-align:center;}}
  .diag-pregunta{{font-size:18px; font-weight:700; color:var(--text); text-align:center; margin:10px 0 24px; line-height:1.4;}}
  .diag-opciones{{display:flex; gap:10px; flex-wrap:wrap; justify-content:center;}}
  .diag-opcion-btn{{
    flex:1 1 140px; background:var(--bg); border:1px solid var(--line); border-radius:10px;
    padding:14px 12px; font-size:13px; font-weight:600; color:var(--text); cursor:pointer;
    font-family:inherit; transition:border-color .15s ease, color .15s ease;
  }}
  .diag-opcion-btn:hover{{border-color:var(--amber); color:var(--amber);}}
  .diag-resultado-titulo{{font-size:12px; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); text-align:center;}}
  .diag-resultado-area{{font-size:26px; font-weight:800; color:var(--amber); text-align:center; margin:8px 0 16px;}}
  .diag-resultado-texto{{font-size:14px; color:var(--text); line-height:1.6; text-align:center; max-width:520px; margin:0 auto 22px;}}
  #diag-resultado-box{{display:flex; flex-direction:column; align-items:center;}}
  #diag-resultado-box .btn{{margin-top:0;}}
  @media (max-width: 480px){{
    .diag-opcion-btn{{flex:1 1 100%;}}
    #diag-resultado-box .btn-secondary{{margin-left:0 !important; margin-top:10px;}}
  }}
</style>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.5.0/chart.umd.min.js"></script>
</head>
<body>
<div class="wrap">

  <div class="header">
    <div class="header-title">
      <div class="page-title">Panel Financiero <span class="flag">🇨🇱</span></div>
    </div>
    <div class="header-logo">
      <div class="brand-mark">K</div>
      <div class="brand-name">PALANKA</div>
    </div>
  </div>
  <div class="brand-tagline"><span class="dash"></span>Finanzas personales para chilenos reales<span class="dash"></span></div>
  <div class="update-note">La información que estás viendo fue cargada el {cargado_en}.</div>

  <section id="resumen" class="section">
    <h1>Indicadores del día</h1>
    <div class="section-sub">UF, dólar y tasa de desempleo — el contexto rápido antes de cualquier decisión.</div>
    <div class="kpis">{kpi_cards}</div>
  </section>

  <section id="sueldo" class="section">
    <div class="subhead-box">Calculadora</div>
    <h1>Sueldo bruto a líquido</h1>
    <div class="section-sub">Elige tu situación: contrato de trabajo o boleta de honorarios.</div>

    <div class="tabs">
      <button class="tab-btn active" data-tab="dependiente" onclick="cambiarTab('dependiente')">Contrato (dependiente)</button>
      <button class="tab-btn" data-tab="boleta" onclick="cambiarTab('boleta')">Boleta de honorarios</button>
    </div>

    <div class="tool-box">
      <div class="tab-panel active" id="panel-dependiente">
        <div class="field-grid">
          <div class="field">
            <label for="dep-bruto">Sueldo bruto mensual (CLP)</label>
            <input type="number" id="dep-bruto" placeholder="ej. 1200000" min="0" step="1000">
          </div>
          <div class="field">
            <label for="dep-afp">AFP</label>
            <select id="dep-afp">{afp_options_html}
            </select>
          </div>
          <div class="field">
            <label for="dep-uf">UF del día</label>
            <input type="number" id="dep-uf" value="{uf_valor if uf_valor else ''}" step="0.01">
          </div>
          <div class="field">
            <label for="dep-utm">UTM del mes</label>
            <input type="number" id="dep-utm" value="{utm_valor if utm_valor else ''}" step="1">
          </div>
        </div>
        <div class="field-grid">
          <div class="field">
            <label for="dep-salud-tipo">Salud</label>
            <select id="dep-salud-tipo" onchange="toggleIsapre()">
              <option value="fonasa">Fonasa (7%)</option>
              <option value="isapre">Isapre</option>
            </select>
          </div>
          <div class="field" id="dep-isapre-field" style="display:none;">
            <label for="dep-isapre-uf">Valor plan pactado (UF)</label>
            <input type="number" id="dep-isapre-uf" placeholder="ej. 3.5" min="0" step="0.01">
          </div>
        </div>
        <div class="field-check">
          <input type="checkbox" id="dep-indefinido" checked>
          <label for="dep-indefinido" style="margin:0;">Contrato indefinido (aplica seguro de cesantía del trabajador, 0,6%)</label>
        </div>
        <button class="btn" onclick="calcularDependiente()">Calcular líquido</button>
        <div class="validacion-box" id="dep-validacion"></div>

        <div class="resultado" id="dep-resultado">
          <div class="resultado-destacado" id="dep-liquido"></div>
          <div class="resultado-nota">Líquido a recibir</div>
          <div class="resultado-grid">
            <div class="resultado-item"><div class="resultado-item-label">AFP (10% + comisión)</div><div class="resultado-item-val" id="dep-afp-val"></div></div>
            <div class="resultado-item"><div class="resultado-item-label" id="dep-salud-label">Salud (7%)</div><div class="resultado-item-val" id="dep-salud-val"></div></div>
            <div class="resultado-item"><div class="resultado-item-label">Seguro cesantía</div><div class="resultado-item-val" id="dep-cesantia-val"></div></div>
            <div class="resultado-item"><div class="resultado-item-label">Impuesto único</div><div class="resultado-item-val" id="dep-impuesto-val"></div></div>
          </div>
          <div class="resultado-nota">
            Cálculo referencial con topes imponibles de 90 UF (AFP y salud) y 135,2 UF (cesantía), y la tabla
            de Impuesto Único de Segunda Categoría vigente del SII. Si eliges Isapre, el descuento de salud es
            el mayor entre el 7% legal y el valor del plan pactado en UF (así aparece en la liquidación real).
            No incluye APV ni cuenta 2.
          </div>
        </div>
      </div>

      <div class="tab-panel" id="panel-boleta">
        <div class="field-grid">
          <div class="field">
            <label for="bol-bruto">Monto bruto de la boleta (CLP)</label>
            <input type="number" id="bol-bruto" placeholder="ej. 800000" min="0" step="1000">
          </div>
        </div>
        <button class="btn" onclick="calcularBoleta()">Calcular retención</button>
        <div class="validacion-box" id="bol-validacion"></div>

        <div class="resultado" id="bol-resultado">
          <div class="resultado-destacado" id="bol-liquido"></div>
          <div class="resultado-nota">Líquido a recibir (después de retención)</div>
          <div class="resultado-grid">
            <div class="resultado-item"><div class="resultado-item-label">Retención (15,25%, 2026)</div><div class="resultado-item-val" id="bol-retencion-val"></div></div>
          </div>
          <div class="aviso-box">
            Precauciones: esta retención es un <strong>anticipo de impuesto</strong>, no el impuesto final — se
            regulariza en tu Declaración de Renta (abril del año siguiente), donde puedes recuperar parte o
            deber más, según tus ingresos totales del año. Además, hoy una parte de lo retenido también se
            destina a cotizaciones previsionales obligatorias para los emisores de boleta, salvo que hayas
            ejercido alguna opción de exclusión — revisa tu caso específico en
            <a href="https://www.mifuturo.cl" target="_blank" rel="noopener" style="color:inherit;">mifuturo.cl</a>
            o con tu contador antes de gastar el 100% de este monto.
          </div>
        </div>
      </div>
    </div>
  </section>

  <section id="inversion-inmobiliaria" class="section">
    <div class="subhead-box">Análisis</div>
    <h1>Inversión inmobiliaria</h1>
    <div class="section-sub">Rentabilidad de comprar una propiedad para arrendar: cap rate, cash-on-cash, ROI y patrimonio proyectado.</div>
    <div class="tool-box">
      <div class="field-grid">
        <div class="field">
          <label for="avc-precio">Precio de la propiedad (UF)</label>
          <input type="number" id="avc-precio" placeholder="ej. 4000" min="0" step="1">
        </div>
        <div class="field">
          <label for="avc-pie">Pie (%)</label>
          <input type="number" id="avc-pie" placeholder="ej. 20" min="0" max="100" step="1">
        </div>
        <div class="field">
          <label for="avc-tasa">Tasa anual crédito (%)</label>
          <input type="number" id="avc-tasa" value="{tasa_hip_valor}" step="0.01">
        </div>
        <div class="field">
          <label for="avc-plazo">Plazo del crédito (años)</label>
          <input type="number" id="avc-plazo" placeholder="ej. 25" min="1" step="1">
        </div>
        <div class="field">
          <label for="avc-gastos">Gastos operacionales mensuales (contribuciones, seguro, mantención — CLP)</label>
          <input type="number" id="avc-gastos" placeholder="ej. 120000" min="0" step="1000">
        </div>
        <div class="field">
          <label for="avc-arriendo">Arriendo mensual esperado (CLP)</label>
          <input type="number" id="avc-arriendo" placeholder="ej. 550000" min="0" step="1000">
        </div>
        <div class="field">
          <label for="avc-vacancia">Vacancia estimada (% del año)</label>
          <input type="number" id="avc-vacancia" value="5" min="0" max="100" step="1">
        </div>
        <div class="field">
          <label for="avc-reajuste">Reajuste UF / plusvalía anual estimada (%)</label>
          <input type="number" id="avc-reajuste" value="3" step="0.1">
        </div>
        <div class="field">
          <label for="avc-uf">UF del día</label>
          <input type="number" id="avc-uf" value="{uf_valor if uf_valor else ''}" step="0.01">
        </div>
      </div>
      <button class="btn" onclick="calcularInversionInmobiliaria()">Analizar inversión</button>
      <div class="validacion-box" id="avc-validacion"></div>

      <div class="resultado" id="avc-resultado">
        <div class="resultado-grid">
          <div class="resultado-item"><div class="resultado-item-label">Dividendo mensual</div><div class="resultado-item-val" id="avc-dividendo"></div></div>
          <div class="resultado-item"><div class="resultado-item-label">Flujo de caja mensual (año 1)</div><div class="resultado-item-val" id="avc-flujo"></div></div>
          <div class="resultado-item"><div class="resultado-item-label">Cap Rate</div><div class="resultado-item-val" id="avc-caprate"></div></div>
          <div class="resultado-item"><div class="resultado-item-label">Cash-on-Cash Return</div><div class="resultado-item-val" id="avc-coc"></div></div>
        </div>

        <div class="resultado-nota" style="margin-top:20px;">Patrimonio y ROI proyectado</div>
        <div class="table-scroll">
          <table class="proyeccion-table">
            <thead><tr><th></th><th>5 años</th><th>10 años</th><th>20 años</th></tr></thead>
            <tbody>
              <tr><td>Patrimonio (equity)</td><td id="avc-pat-5"></td><td id="avc-pat-10"></td><td id="avc-pat-20"></td></tr>
              <tr><td>ROI acumulado</td><td id="avc-roi-5"></td><td id="avc-roi-10"></td><td id="avc-roi-20"></td></tr>
            </tbody>
          </table>
        </div>

        <div class="resultado-nota">
          Cap Rate = ingreso operativo neto anual / precio de la propiedad. Cash-on-Cash = flujo de caja anual (año 1) /
          inversión inicial (pie). ROI acumulado = (patrimonio + flujos de caja acumulados − inversión inicial) /
          inversión inicial. Cálculo referencial con supuestos simplificados — no considera impuestos a la ganancia de
          capital, costos de cierre, ni variaciones futuras de tasa o arriendo.
        </div>

        <button class="btn btn-secondary" onclick="descargarInversionInmobiliaria()" style="margin-top:16px;">Descargar resultados</button>
      </div>
    </div>
  </section>

  <section id="inversion" class="section">
    <div class="subhead-box">Simulador</div>
    <h1>Aportes periódicos (DCA)</h1>
    <div class="section-sub">
      Cuánto podrías acumular aportando un monto fijo cada mes. <strong>DCA</strong> (Dollar-Cost Averaging,
      o "promedio de costo en dólares", aunque en Chile se aplica igual en pesos o UF) es la estrategia de
      invertir un monto fijo de forma regular — por ejemplo, cada mes — sin importar si el precio del
      instrumento subió o bajó ese período. Al comprar siempre el mismo monto, terminas comprando más
      cuotas cuando el precio está bajo y menos cuando está alto, lo que suaviza tu costo promedio de compra
      en el tiempo y evita el intento (casi siempre fallido) de acertar el momento perfecto para invertir.
      Es la lógica detrás de los aportes automáticos a fondos mutuos, APV o ahorro programado.
      <br><br>
      <strong>Algunos ejemplos reales en Chile</strong> (la rentabilidad pasada no garantiza la futura, y
      salvo el depósito a plazo, ninguno de estos instrumentos asegura tu capital):
    </div>
    <div class="table-scroll">
      <table class="ejemplos-table">
        <thead><tr><th>Instrumento</th><th>Riesgo</th><th>Rentabilidad de referencia</th></tr></thead>
        <tbody>
          <tr>
            <td>Depósito a plazo (30 días, pesos)</td>
            <td class="riesgo-bajo">Bajo</td>
            <td>Tasas de mercado en torno a 0,25%–0,40% mensual (jul-2026) — equivalente a ~3%–5% anual. Capital asegurado hasta el monto de la garantía estatal, si aplica.</td>
          </tr>
          <tr>
            <td>Fondos mutuos balanceados</td>
            <td class="riesgo-medio">Medio</td>
            <td>Muy variable año a año: cerraron 2025 con +9,9%, pero en 2022 rentaron -2,8%. Mezclan renta fija y variable.</td>
          </tr>
          <tr>
            <td>Fondos mutuos accionarios / acciones (IPSA)</td>
            <td class="riesgo-alto">Alto</td>
            <td>Alta volatilidad: los fondos accionarios cerraron 2025 con +31,8%, pero el IPSA también ha tenido décadas casi planas o negativas (ej. -0,71% anual promedio entre 2011–2020).</td>
          </tr>
          <tr>
            <td>Multifondos AFP / APV (A a E)</td>
            <td>Según fondo</td>
            <td>El fondo A es el más riesgoso (más renta variable) y el E el más conservador — usa el simulador de APV arriba para proyectar tu caso.</td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="tool-box">
      <div class="field-grid">
        <div class="field">
          <label for="dca-aporte">Aporte mensual (CLP)</label>
          <input type="number" id="dca-aporte" placeholder="ej. 150000" min="0" step="1000">
        </div>
        <div class="field">
          <label for="dca-tasa">Retorno anual esperado (%)</label>
          <input type="number" id="dca-tasa" placeholder="ej. 7" step="0.1">
        </div>
        <div class="field">
          <label for="dca-anios">Años</label>
          <input type="number" id="dca-anios" placeholder="ej. 15" min="1" step="1">
        </div>
      </div>
      <button class="btn" onclick="calcularDCA()">Proyectar</button>
      <div class="validacion-box" id="dca-validacion"></div>

      <div class="resultado" id="dca-resultado">
        <div class="resultado-destacado" id="dca-final"></div>
        <div class="resultado-nota">Monto proyectado al final del período</div>
        <div class="resultado-grid">
          <div class="resultado-item"><div class="resultado-item-label">Total aportado</div><div class="resultado-item-val" id="dca-aportado"></div></div>
          <div class="resultado-item"><div class="resultado-item-label">Ganancia estimada</div><div class="resultado-item-val" id="dca-ganancia"></div></div>
        </div>
        <div class="resultado-nota">
          Proyección referencial con interés compuesto y rentabilidad constante — la rentabilidad real de
          cualquier instrumento varía mes a mes. No es una promesa ni recomendación de inversión.
        </div>
      </div>
    </div>
  </section>

  <section id="apv" class="section">
    <div class="subhead-box">Simulador</div>
    <h1>Ahorro Previsional Voluntario (APV)</h1>
    <div class="section-sub">
      Proyecta cuánto podrías acumular en tu cuenta de APV según el régimen tributario que elijas.
      <strong>Régimen A</strong>: el Estado bonifica el 15% de tu ahorro anual, con tope de 6 UTM al año.
      <strong>Régimen B</strong>: tus aportes rebajan tu base imponible (menos impuesto a la renta), con
      tope de 600 UF al año (50 UF al mes si el descuento es por planilla).
      <br><br>
      <strong>¿Por qué existen dos regímenes?</strong> Buscan que el incentivo del Estado al ahorro
      previsional voluntario funcione para distintos niveles de ingreso. Si tu tasa marginal de impuesto es
      baja (tramos inferiores de la tabla de Impuesto Único, o no pagas impuesto), normalmente te conviene
      más el <strong>Régimen A</strong>: la bonificación fija del 15% suele superar lo que ahorrarías
      rebajando una base imponible ya baja. Si tu tasa marginal es más alta (tramos superiores), el
      <strong>Régimen B</strong> suele convenir más, porque el ahorro tributario crece junto con tu tasa.
      <strong>¿Quién puede usarlo?</strong> Cualquier trabajador afiliado al sistema de pensiones —
      dependiente o independiente (boleta de honorarios) — puede abrir una cuenta de APV en una AFP, un
      banco, una administradora de fondos mutuos o una compañía de seguros autorizada; no depende del tipo
      de contrato. Puedes combinar ambos regímenes en distintas cuentas si quieres optimizar según tu
      situación tributaria.
    </div>
    <div class="tool-box">
      <div class="field-grid">
        <div class="field">
          <label for="apv-monto">Aporte mensual (CLP)</label>
          <input type="number" id="apv-monto" placeholder="ej. 100000" min="0" step="1000">
        </div>
        <div class="field">
          <label for="apv-regimen">Régimen</label>
          <select id="apv-regimen" onchange="toggleApvMarginal()">
            <option value="A">Régimen A (bonificación 15%)</option>
            <option value="B">Régimen B (rebaja base imponible)</option>
          </select>
        </div>
        <div class="field">
          <label for="apv-edad">Edad actual</label>
          <input type="number" id="apv-edad" placeholder="ej. 35" min="18" max="80" step="1">
        </div>
        <div class="field">
          <label for="apv-jubilacion">Edad de jubilación estimada</label>
          <input type="number" id="apv-jubilacion" value="65" min="19" max="90" step="1">
        </div>
        <div class="field">
          <label for="apv-retorno">Retorno anual esperado (%)</label>
          <input type="number" id="apv-retorno" placeholder="ej. 5" step="0.1">
        </div>
        <div class="field">
          <label for="apv-uf">UF del día</label>
          <input type="number" id="apv-uf" value="{uf_valor if uf_valor else ''}" step="0.01">
        </div>
        <div class="field">
          <label for="apv-utm">UTM del mes</label>
          <input type="number" id="apv-utm" value="{utm_valor if utm_valor else ''}" step="1">
        </div>
        <div class="field" id="apv-marginal-field" style="display:none;">
          <label for="apv-marginal">Tasa marginal de impuesto estimada (%)</label>
          <input type="number" id="apv-marginal" placeholder="ej. 13.5" min="0" max="40" step="0.1">
        </div>
      </div>
      <button class="btn" onclick="calcularAPV()">Proyectar APV</button>
      <div class="validacion-box" id="apv-validacion"></div>

      <div class="resultado" id="apv-resultado">
        <div class="resultado-destacado" id="apv-total"></div>
        <div class="resultado-nota">Total estimado al momento de jubilar</div>
        <div class="resultado-grid">
          <div class="resultado-item"><div class="resultado-item-label">Total aportado</div><div class="resultado-item-val" id="apv-aportado"></div></div>
          <div class="resultado-item"><div class="resultado-item-label">Ganancia por rentabilidad</div><div class="resultado-item-val" id="apv-ganancia"></div></div>
          <div class="resultado-item"><div class="resultado-item-label" id="apv-bono-label">Bonificación estatal acumulada</div><div class="resultado-item-val" id="apv-bono-val"></div></div>
        </div>
        <div class="resultado-nota" id="apv-nota-regimen"></div>
        <div class="resultado-nota">
          Simulación educativa con interés compuesto y rentabilidad constante — no reemplaza una proyección de
          pensión oficial ni considera comisiones de la administradora, inflación, cambios de tasa, ni la
          modalidad de pensión (retiro programado, renta vitalicia, etc). Topes verificados en
          Superintendencia de Pensiones y SII, julio 2026.
        </div>
      </div>
    </div>
  </section>

  <section id="diagnostico" class="section">
    <div class="subhead-box">Diagnóstico</div>
    <h1>¿Cómo están tus finanzas personales?</h1>
    <div class="section-sub">
      8 preguntas rápidas para ver qué parte de tus finanzas está más desatendida. Sin juzgar — es solo un
      punto de partida.
    </div>
    <div class="tool-box">
      <div id="diag-progreso-wrap" class="diag-progreso-wrap">
        <div class="diag-progreso-bar"><div class="diag-progreso-fill" id="diag-progreso-fill"></div></div>
        <div class="diag-progreso-label" id="diag-progreso-label">Pregunta 1 de 8</div>
      </div>

      <div id="diag-pregunta-box">
        <div class="diag-pregunta" id="diag-pregunta-texto"></div>
        <div class="diag-opciones">
          <button class="diag-opcion-btn" data-valor="0" onclick="responderDiagnostico(0)">Nunca</button>
          <button class="diag-opcion-btn" data-valor="1" onclick="responderDiagnostico(1)">A veces</button>
          <button class="diag-opcion-btn" data-valor="2" onclick="responderDiagnostico(2)">Siempre</button>
        </div>
        <button class="btn-secondary btn" id="diag-atras-btn" onclick="atrasDiagnostico()" style="display:none; margin-top:14px;">Volver a la pregunta anterior</button>
      </div>

      <div id="diag-resultado-box" style="display:none;">
        <div class="diag-resultado-titulo">Tu área más desatendida:</div>
        <div class="diag-resultado-area" id="diag-resultado-area"></div>
        <div class="diag-resultado-texto" id="diag-resultado-texto"></div>
        <a class="btn" id="diag-resultado-cta" href="https://palanka.lat/librospalanka" target="_blank" rel="noopener">Ver libros de Palanka</a>
        <button class="btn-secondary btn" onclick="reiniciarDiagnostico()" style="margin-left:10px;">Volver a hacer el test</button>
      </div>
    </div>
  </section>

  <section id="kanasta-semanal" class="section">
    <div class="subhead-box">Kanasta Palanka</div>
    <h1>Kanasta Semanal</h1>
    <div class="section-sub">
      Nuestra propia referencia de gasto semanal — no es la canasta básica oficial de Chile. Estimamos lo
      que gasta en una semana una familia de 2 adultos y 2 niños en tres cosas: alimentos ({kanasta_productos_totales}
      productos, precios de <a href="https://datos.odepa.gob.cl" target="_blank" rel="noopener">ODEPA</a>
      en vivo), bencina ({kanasta_bencina.get('litros_semana', 24):.0f} litros/semana a un precio de referencia
      fijo, ya que este sitio no tiene acceso en vivo al precio de la CNE) y productos de aseo del hogar
      (precios promediados en 4 cadenas de supermercado, actualizados a mano). El costo se expresa en base
      semanal; los precios de alimentos se actualizan a diario, el resto se revisa periódicamente.
      {kanasta_productos_html}
      {kanasta_otros_html}
    </div>

    <div class="kanasta-box">
      <div class="kanasta-col kanasta-hoy">
        <div class="kanasta-col-title">Costo hoy</div>
        <div class="kanasta-hoy-val">{kanasta_semanal_val}</div>
        <div class="kanasta-hoy-sub">{kanasta_semanal_sub}</div>
        <div class="kanasta-hoy-nota">Total semanal</div>
      </div>
      <div class="kanasta-col kanasta-grafico">
        <div class="kanasta-col-title">Seguimiento</div>
        <div class="kanasta-chart-wrap">{kanasta_semanal_chart_html}</div>
      </div>
    </div>
  </section>

  <section id="kanasta-mensual" class="section">
    <div class="subhead-box">Kanasta Palanka</div>
    <h1>Kanasta Mensual</h1>
    <div class="section-sub">
      Cuánto necesita al mes la misma familia de referencia (2 adultos + 2 niños) para cubrir lo básico,
      sin contar arriendo/dividendo ni colegio. Es la Kanasta Semanal llevada a base mensual (x 4,33 semanas),
      más cuentas básicas (luz, agua y gas) e internet y celulares — estos dos últimos son valores de
      referencia fijos, actualizados a mano, no en vivo.
    </div>

    <div class="kanasta-box">
      <div class="kanasta-col kanasta-hoy">
        <div class="kanasta-col-title">Costo hoy</div>
        <div class="kanasta-hoy-val">{kanasta_mensual_val}</div>
        <div class="kanasta-hoy-sub">{kanasta_mensual_sub}</div>
        <div class="kanasta-hoy-nota">Total mensual</div>
      </div>
      <div class="kanasta-col kanasta-grafico">
        <div class="kanasta-col-title">Seguimiento</div>
        <div class="kanasta-chart-wrap">{kanasta_mensual_chart_html}</div>
      </div>
    </div>

    <div class="subhead-box">Desglose por categoría</div>
    {kanasta_categorias_html}
  </section>

  <div class="footer">
    Fuentes: <a href="https://mindicador.cl" target="_blank">mindicador.cl</a> (Banco Central de Chile),
    <a href="https://api.cmfchile.cl" target="_blank">CMF Bancos</a>,
    <a href="https://www.sii.cl" target="_blank">SII</a> (tabla de Impuesto Único),
    <a href="https://www.spensiones.cl" target="_blank">Superintendencia de Pensiones</a> (topes y comisiones AFP) y
    <a href="https://datos.odepa.gob.cl" target="_blank">ODEPA</a>.
    Un desarrollo de <a href="https://www.palanka.lat" target="_blank">Palanka</a> — Finanzas personales para
    chilenos reales. Información con fines educativos, no constituye asesoría legal, tributaria ni financiera
    personalizada.
  </div>

</div>

<script>
const TRAMOS_IMPUESTO_UTM = {json.dumps(TRAMOS_IMPUESTO_UTM)};
const TOPE_IMPONIBLE_UF = {TOPE_IMPONIBLE_UF};
const TOPE_CESANTIA_UF = {TOPE_CESANTIA_UF};
const RETENCION_BOLETA_PCT = {RETENCION_BOLETA_PCT};
const COTIZACION_AFP_PCT = {COTIZACION_AFP_PCT};
const COTIZACION_SALUD_PCT = {COTIZACION_SALUD_PCT};
const CESANTIA_TRABAJADOR_PCT = {CESANTIA_TRABAJADOR_PCT};

function clp(n) {{
  return '$' + Math.round(n).toLocaleString('es-CL');
}}

function mostrarValidacion(id, faltantes) {{
  const el = document.getElementById(id);
  if (!el) return;
  el.textContent = 'Te falta un dato: completa ' + faltantes.join(', ') + ' antes de calcular.';
  el.style.display = 'block';
}}

function ocultarValidacion(id) {{
  const el = document.getElementById(id);
  if (el) el.style.display = 'none';
}}

function cambiarTab(tab) {{
  document.querySelectorAll('.tab-btn').forEach(function(b) {{
    b.classList.toggle('active', b.dataset.tab === tab);
  }});
  document.querySelectorAll('.tab-panel').forEach(function(p) {{
    p.classList.toggle('active', p.id === 'panel-' + tab);
  }});
}}

function impuestoUnico(baseTributableClp, utm) {{
  if (!utm) return 0;
  const baseUtm = baseTributableClp / utm;
  for (const [desde, hasta, factor, rebajaUtm] of TRAMOS_IMPUESTO_UTM) {{
    if (hasta === null || baseUtm <= hasta) {{
      if (baseUtm <= desde && factor === 0) return 0;
      const impuestoUtm = (baseUtm * factor) - rebajaUtm;
      return Math.max(0, impuestoUtm * utm);
    }}
  }}
  return 0;
}}

function toggleIsapre() {{
  const esIsapre = document.getElementById('dep-salud-tipo').value === 'isapre';
  document.getElementById('dep-isapre-field').style.display = esIsapre ? 'block' : 'none';
}}

function calcularDependiente() {{
  const bruto = parseFloat(document.getElementById('dep-bruto').value);
  const comisionAfp = parseFloat(document.getElementById('dep-afp').value);
  const uf = parseFloat(document.getElementById('dep-uf').value);
  const utm = parseFloat(document.getElementById('dep-utm').value);
  const indefinido = document.getElementById('dep-indefinido').checked;
  const esIsapre = document.getElementById('dep-salud-tipo').value === 'isapre';
  const planIsapreUf = parseFloat(document.getElementById('dep-isapre-uf').value);
  const resultadoBox = document.getElementById('dep-resultado');

  const faltantes = [];
  if (!bruto || bruto <= 0) faltantes.push('el sueldo bruto mensual');
  if (!uf) faltantes.push('la UF del día');
  if (!utm) faltantes.push('la UTM del mes');
  if (esIsapre && (isNaN(planIsapreUf) || planIsapreUf <= 0)) faltantes.push('el valor del plan Isapre pactado');

  if (faltantes.length > 0) {{
    mostrarValidacion('dep-validacion', faltantes);
    resultadoBox.classList.remove('show');
    return;
  }}
  ocultarValidacion('dep-validacion');

  const topeImponible = TOPE_IMPONIBLE_UF * uf;
  const topeCesantia = TOPE_CESANTIA_UF * uf;

  const imponibleAfpSalud = Math.min(bruto, topeImponible);
  const imponibleCesantia = Math.min(bruto, topeCesantia);

  const afp = imponibleAfpSalud * ((COTIZACION_AFP_PCT + comisionAfp) / 100);
  const saludLegal = imponibleAfpSalud * (COTIZACION_SALUD_PCT / 100);
  let salud = saludLegal;
  let etiquetaSalud = 'Salud (7%, Fonasa)';
  if (esIsapre) {{
    const saludPlan = planIsapreUf * uf;
    salud = Math.max(saludLegal, saludPlan);
    etiquetaSalud = 'Salud (Isapre' + (saludPlan > saludLegal ? ', plan sobre el 7%' : '') + ')';
  }}
  document.getElementById('dep-salud-label').textContent = etiquetaSalud;
  const cesantia = indefinido ? imponibleCesantia * (CESANTIA_TRABAJADOR_PCT / 100) : 0;

  const baseTributable = bruto - afp - salud - cesantia;
  const impuesto = impuestoUnico(baseTributable, utm);

  const liquido = bruto - afp - salud - cesantia - impuesto;

  document.getElementById('dep-liquido').textContent = clp(liquido);
  document.getElementById('dep-afp-val').textContent = clp(afp);
  document.getElementById('dep-salud-val').textContent = clp(salud);
  document.getElementById('dep-cesantia-val').textContent = clp(cesantia);
  document.getElementById('dep-impuesto-val').textContent = clp(impuesto);
  resultadoBox.classList.add('show');
}}

function calcularBoleta() {{
  const bruto = parseFloat(document.getElementById('bol-bruto').value);
  const resultadoBox = document.getElementById('bol-resultado');
  if (!bruto || bruto <= 0) {{
    mostrarValidacion('bol-validacion', ['el monto bruto de la boleta']);
    resultadoBox.classList.remove('show');
    return;
  }}
  ocultarValidacion('bol-validacion');
  const retencion = bruto * (RETENCION_BOLETA_PCT / 100);
  const liquido = bruto - retencion;
  document.getElementById('bol-liquido').textContent = clp(liquido);
  document.getElementById('bol-retencion-val').textContent = clp(retencion);
  resultadoBox.classList.add('show');
}}

let ultimoResultadoInversion = null;

function saldoInsolutoUf(montoFinanciadoUf, iMensual, n, k) {{
  if (k >= n) return 0;
  if (iMensual === 0) return montoFinanciadoUf * (1 - k / n);
  return montoFinanciadoUf * (Math.pow(1 + iMensual, n) - Math.pow(1 + iMensual, k)) / (Math.pow(1 + iMensual, n) - 1);
}}

function calcularInversionInmobiliaria() {{
  const precioUf = parseFloat(document.getElementById('avc-precio').value);
  const piePct = parseFloat(document.getElementById('avc-pie').value);
  const tasaAnual = parseFloat(document.getElementById('avc-tasa').value);
  const anios = parseFloat(document.getElementById('avc-plazo').value);
  const gastos = parseFloat(document.getElementById('avc-gastos').value) || 0;
  const arriendo = parseFloat(document.getElementById('avc-arriendo').value);
  const vacanciaPct = parseFloat(document.getElementById('avc-vacancia').value) || 0;
  const reajusteAnual = parseFloat(document.getElementById('avc-reajuste').value) / 100;
  const uf = parseFloat(document.getElementById('avc-uf').value);
  const resultadoBox = document.getElementById('avc-resultado');

  const faltantes = [];
  if (!precioUf || precioUf <= 0) faltantes.push('el precio de la propiedad');
  if (!piePct || piePct <= 0) faltantes.push('el pie (%)');
  if (!tasaAnual) faltantes.push('la tasa anual del crédito');
  if (!anios || anios <= 0) faltantes.push('el plazo del crédito');
  if (!arriendo || arriendo <= 0) faltantes.push('el arriendo mensual esperado');
  if (!uf) faltantes.push('la UF del día');

  if (faltantes.length > 0) {{
    mostrarValidacion('avc-validacion', faltantes);
    resultadoBox.classList.remove('show');
    return;
  }}
  ocultarValidacion('avc-validacion');

  const pieUf = precioUf * (piePct / 100);
  const montoFinanciadoUf = precioUf - pieUf;
  const n = anios * 12;
  const iMensual = (tasaAnual / 100) / 12;

  let dividendoUf;
  if (iMensual === 0) {{
    dividendoUf = montoFinanciadoUf / n;
  }} else {{
    dividendoUf = montoFinanciadoUf * (iMensual * Math.pow(1 + iMensual, n)) / (Math.pow(1 + iMensual, n) - 1);
  }}
  const dividendoClpHoy = dividendoUf * uf;

  const vacanciaFrac = vacanciaPct / 100;
  const arriendoEfectivoMensual = arriendo * (1 - vacanciaFrac);
  const ingresoAnualBruto = arriendoEfectivoMensual * 12;
  const gastosAnual = gastos * 12;
  const noiAnual = ingresoAnualBruto - gastosAnual; // ingreso operativo neto, antes de la deuda

  const precioClpHoy = precioUf * uf;
  const capRate = (noiAnual / precioClpHoy) * 100;

  const flujoMensual = arriendoEfectivoMensual - gastos - dividendoClpHoy;
  const flujoAnual = flujoMensual * 12;

  const pieClpHoy = pieUf * uf;
  const cashOnCash = (flujoAnual / pieClpHoy) * 100;

  function patrimonioYRoi(anioObjetivo) {{
    const k = Math.min(anioObjetivo * 12, n);
    const ufProyectada = uf * Math.pow(1 + reajusteAnual, anioObjetivo);
    const saldoUf = saldoInsolutoUf(montoFinanciadoUf, iMensual, n, k);
    const equityUf = precioUf - saldoUf;
    const patrimonio = equityUf * ufProyectada;
    const flujoAcumulado = flujoAnual * anioObjetivo;
    const roi = ((patrimonio + flujoAcumulado - pieClpHoy) / pieClpHoy) * 100;
    return {{ patrimonio, roi }};
  }}

  const r5 = patrimonioYRoi(5);
  const r10 = patrimonioYRoi(10);
  const r20 = patrimonioYRoi(20);

  document.getElementById('avc-dividendo').textContent = clp(dividendoClpHoy) + '/mes';
  document.getElementById('avc-flujo').textContent = clp(flujoMensual) + '/mes';
  document.getElementById('avc-caprate').textContent = capRate.toFixed(2) + '%';
  document.getElementById('avc-coc').textContent = cashOnCash.toFixed(2) + '%';
  document.getElementById('avc-pat-5').textContent = clp(r5.patrimonio);
  document.getElementById('avc-pat-10').textContent = clp(r10.patrimonio);
  document.getElementById('avc-pat-20').textContent = clp(r20.patrimonio);
  document.getElementById('avc-roi-5').textContent = r5.roi.toFixed(1) + '%';
  document.getElementById('avc-roi-10').textContent = r10.roi.toFixed(1) + '%';
  document.getElementById('avc-roi-20').textContent = r20.roi.toFixed(1) + '%';
  resultadoBox.classList.add('show');

  ultimoResultadoInversion = {{
    precioUf, piePct, tasaAnual, anios, arriendo, vacanciaPct, gastos, reajustePct: reajusteAnual * 100,
    dividendoClpHoy, flujoMensual, capRate, cashOnCash,
    pat5: r5.patrimonio, roi5: r5.roi, pat10: r10.patrimonio, roi10: r10.roi, pat20: r20.patrimonio, roi20: r20.roi,
  }};
}}

function descargarInversionInmobiliaria() {{
  if (!ultimoResultadoInversion) return;
  const r = ultimoResultadoInversion;
  const lineas = [
    'Análisis de Inversión Inmobiliaria — Palanka',
    'Generado: ' + new Date().toLocaleString('es-CL'),
    '',
    'Datos ingresados:',
    '  Precio propiedad: ' + r.precioUf + ' UF',
    '  Pie: ' + r.piePct + '%',
    '  Tasa anual crédito: ' + r.tasaAnual + '%',
    '  Plazo crédito: ' + r.anios + ' años',
    '  Arriendo mensual esperado: ' + clp(r.arriendo),
    '  Vacancia estimada: ' + r.vacanciaPct + '%',
    '  Gastos operacionales mensuales: ' + clp(r.gastos),
    '  Reajuste UF / plusvalía anual: ' + r.reajustePct.toFixed(1) + '%',
    '',
    'Resultados:',
    '  Dividendo mensual: ' + clp(r.dividendoClpHoy),
    '  Flujo de caja mensual (año 1): ' + clp(r.flujoMensual),
    '  Cap Rate: ' + r.capRate.toFixed(2) + '%',
    '  Cash-on-Cash Return: ' + r.cashOnCash.toFixed(2) + '%',
    '',
    '  Patrimonio a 5 años: ' + clp(r.pat5) + '  |  ROI acumulado: ' + r.roi5.toFixed(1) + '%',
    '  Patrimonio a 10 años: ' + clp(r.pat10) + '  |  ROI acumulado: ' + r.roi10.toFixed(1) + '%',
    '  Patrimonio a 20 años: ' + clp(r.pat20) + '  |  ROI acumulado: ' + r.roi20.toFixed(1) + '%',
    '',
    'Cálculo referencial, no constituye asesoría financiera. Fuente: tablero.palanka.lat',
  ];
  const blob = new Blob([lineas.join('\\n')], {{ type: 'text/plain;charset=utf-8' }});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'analisis-inversion-inmobiliaria.txt';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}}

function calcularDCA() {{
  const aporte = parseFloat(document.getElementById('dca-aporte').value);
  const tasaAnual = parseFloat(document.getElementById('dca-tasa').value);
  const anios = parseFloat(document.getElementById('dca-anios').value);
  const resultadoBox = document.getElementById('dca-resultado');

  const faltantes = [];
  if (!aporte || aporte <= 0) faltantes.push('el aporte mensual');
  if (!anios || anios <= 0) faltantes.push('los años');

  if (faltantes.length > 0) {{
    mostrarValidacion('dca-validacion', faltantes);
    resultadoBox.classList.remove('show');
    return;
  }}
  ocultarValidacion('dca-validacion');

  const n = anios * 12;
  const iMensual = (tasaAnual || 0) / 100 / 12;
  let valorFinal;
  if (iMensual === 0) {{
    valorFinal = aporte * n;
  }} else {{
    valorFinal = aporte * ((Math.pow(1 + iMensual, n) - 1) / iMensual);
  }}
  const totalAportado = aporte * n;
  const ganancia = valorFinal - totalAportado;

  document.getElementById('dca-final').textContent = clp(valorFinal);
  document.getElementById('dca-aportado').textContent = clp(totalAportado);
  document.getElementById('dca-ganancia').textContent = clp(ganancia);
  resultadoBox.classList.add('show');
}}

function toggleApvMarginal() {{
  const esB = document.getElementById('apv-regimen').value === 'B';
  document.getElementById('apv-marginal-field').style.display = esB ? 'block' : 'none';
}}

function calcularAPV() {{
  const monto = parseFloat(document.getElementById('apv-monto').value);
  const regimen = document.getElementById('apv-regimen').value;
  const edad = parseFloat(document.getElementById('apv-edad').value);
  const jubilacion = parseFloat(document.getElementById('apv-jubilacion').value);
  const retorno = parseFloat(document.getElementById('apv-retorno').value);
  const uf = parseFloat(document.getElementById('apv-uf').value);
  const utm = parseFloat(document.getElementById('apv-utm').value);
  const marginal = parseFloat(document.getElementById('apv-marginal').value);
  const resultadoBox = document.getElementById('apv-resultado');

  const faltantes = [];
  if (!monto || monto <= 0) faltantes.push('el aporte mensual');
  if (!edad || edad <= 0) faltantes.push('tu edad actual');
  if (!jubilacion || jubilacion <= edad) faltantes.push('una edad de jubilación mayor a tu edad actual');
  if (!uf) faltantes.push('la UF del día');
  if (!utm) faltantes.push('la UTM del mes');
  if (regimen === 'B' && (isNaN(marginal) || marginal < 0)) faltantes.push('la tasa marginal de impuesto estimada');

  if (faltantes.length > 0) {{
    mostrarValidacion('apv-validacion', faltantes);
    resultadoBox.classList.remove('show');
    return;
  }}
  ocultarValidacion('apv-validacion');

  const anios = jubilacion - edad;
  const n = anios * 12;
  const iMensual = (retorno || 0) / 100 / 12;
  let totalAportes;
  if (iMensual === 0) {{
    totalAportes = monto * n;
  }} else {{
    totalAportes = monto * ((Math.pow(1 + iMensual, n) - 1) / iMensual);
  }}
  const totalAportado = monto * n;
  const aporteAnual = monto * 12;

  let bonoProyectado = 0;
  let notaRegimen = '';

  if (regimen === 'A') {{
    const topeBonoAnual = 6 * utm;
    const bonoAnual = Math.min(aporteAnual * 0.15, topeBonoAnual);
    const iAnual = Math.pow(1 + iMensual, 12) - 1;
    bonoProyectado = iAnual === 0 ? bonoAnual * anios : bonoAnual * ((Math.pow(1 + iAnual, anios) - 1) / iAnual);
    document.getElementById('apv-bono-label').textContent = 'Bonificación estatal acumulada (proyectada)';
    document.getElementById('apv-bono-val').textContent = clp(bonoProyectado);
    const aporteMensualParaTope = (topeBonoAnual / 0.15) / 12;
    notaRegimen = 'Régimen A: el Estado bonifica el 15% de tu aporte anual, con tope de 6 UTM al año (' +
      clp(topeBonoAnual) + ' hoy). Para llegar al tope máximo necesitas aportar aproximadamente ' +
      clp(aporteMensualParaTope) + ' al mes.';
  }} else {{
    const topeAnualClp = 600 * uf;
    const aporteAnualTopado = Math.min(aporteAnual, topeAnualClp);
    const ahorroTributarioAnual = aporteAnualTopado * (marginal / 100);
    bonoProyectado = ahorroTributarioAnual * anios;
    document.getElementById('apv-bono-label').textContent = 'Ahorro tributario acumulado (estimado, no invertido)';
    document.getElementById('apv-bono-val').textContent = clp(bonoProyectado);
    notaRegimen = 'Régimen B: tus aportes rebajan tu base imponible hasta un tope de 600 UF al año (' +
      clp(topeAnualClp) + ' hoy). El ahorro tributario estimado usa la tasa marginal que ingresaste y no ' +
      'asume que ese ahorro se reinvierta (a diferencia del Régimen A, acá no es un depósito adicional en tu cuenta).';
  }}

  const totalFinal = regimen === 'A' ? totalAportes + bonoProyectado : totalAportes;
  const ganancia = totalAportes - totalAportado;

  document.getElementById('apv-total').textContent = clp(totalFinal);
  document.getElementById('apv-aportado').textContent = clp(totalAportado);
  document.getElementById('apv-ganancia').textContent = clp(ganancia);
  document.getElementById('apv-nota-regimen').textContent = notaRegimen;
  resultadoBox.classList.add('show');
}}

const DIAG_PREGUNTAS = {diagnostico_preguntas_js};
const DIAG_PRIORIDAD = {diagnostico_prioridad_js};
const DIAG_RESULTADOS = {diagnostico_resultados_js};

let diagIndice = 0;
let diagRespuestas = [];

function actualizarProgresoDiagnostico() {{
  const pct = (diagIndice / DIAG_PREGUNTAS.length) * 100;
  document.getElementById('diag-progreso-fill').style.width = pct + '%';
  document.getElementById('diag-progreso-label').textContent = 'Pregunta ' + (diagIndice + 1) + ' de ' + DIAG_PREGUNTAS.length;
}}

function mostrarPreguntaDiagnostico() {{
  document.getElementById('diag-pregunta-texto').textContent = DIAG_PREGUNTAS[diagIndice].pregunta;
  document.getElementById('diag-atras-btn').style.display = diagIndice > 0 ? 'inline-block' : 'none';
  actualizarProgresoDiagnostico();
}}

function responderDiagnostico(valor) {{
  diagRespuestas[diagIndice] = valor;
  diagIndice++;
  if (diagIndice >= DIAG_PREGUNTAS.length) {{
    mostrarResultadoDiagnostico();
  }} else {{
    mostrarPreguntaDiagnostico();
  }}
}}

function atrasDiagnostico() {{
  if (diagIndice === 0) return;
  diagIndice--;
  mostrarPreguntaDiagnostico();
}}

function mostrarResultadoDiagnostico() {{
  const puntajes = {{}};
  DIAG_PREGUNTAS.forEach(function(p, i) {{ puntajes[p.clave] = diagRespuestas[i]; }});

  let minPuntaje = Math.min.apply(null, Object.values(puntajes));
  let claveGanadora = DIAG_PRIORIDAD.find(function(clave) {{ return puntajes[clave] === minPuntaje; }});
  if (!claveGanadora) claveGanadora = DIAG_PREGUNTAS[0].clave;

  const areaGanadora = DIAG_PREGUNTAS.find(function(p) {{ return p.clave === claveGanadora; }});

  document.getElementById('diag-pregunta-box').style.display = 'none';
  document.getElementById('diag-progreso-wrap').style.display = 'none';
  document.getElementById('diag-resultado-area').textContent = areaGanadora.area;
  document.getElementById('diag-resultado-texto').textContent = DIAG_RESULTADOS[claveGanadora];
  document.getElementById('diag-resultado-box').style.display = 'flex';
}}

function reiniciarDiagnostico() {{
  diagIndice = 0;
  diagRespuestas = [];
  document.getElementById('diag-resultado-box').style.display = 'none';
  document.getElementById('diag-pregunta-box').style.display = 'block';
  document.getElementById('diag-progreso-wrap').style.display = 'block';
  mostrarPreguntaDiagnostico();
}}

mostrarPreguntaDiagnostico();

{kanasta_chart_js}
</script>

</body>
</html>
"""

with open("index.html", "w", encoding="utf-8") as f:
    f.write(HTML)

print("OK -> index.html")
