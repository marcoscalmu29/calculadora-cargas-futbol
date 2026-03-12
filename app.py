# ============================================================
# CALCULADORA AVANZADA DE CARGAS EN FÚTBOL
# Streamlit App - Versión Pro + Login Multi-Usuario (2ª RFEF)
# ============================================================

import math
import json
import copy
import textwrap
from datetime import datetime
import io

import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import streamlit as st

# ============================================================
# CONFIGURACIÓN DE STREAMLIT Y USUARIOS
# ============================================================
st.set_page_config(page_title="Calculadora Cargas Fútbol", layout="wide", page_icon="⚽")
plt.rcParams["figure.figsize"] = (11, 5)

# ------------------------------------------------------------
# DICCIONARIO DE USUARIOS (Añade o cambia los que quieras)
# ------------------------------------------------------------
USUARIOS_PERMITIDOS = {
    "marcos": "1234",
    "mister": "futbol",
    "prepa": "cargas2026"
}

# ============================================================
# SISTEMA DE LOGIN (PANTALLA DE BLOQUEO)
# ============================================================
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.username = ""

if not st.session_state.logged_in:
    st.markdown('<div style="background: linear-gradient(90deg, #0f172a, #1e293b); color: #ffffff; padding: 18px 22px; border-radius: 16px; margin-bottom: 20px; text-align: center; box-shadow: 0 4px 14px rgba(0,0,0,0.18);"><h1 style="margin: 0; font-size: 30px; font-weight: 800; letter-spacing: 1px; text-transform: uppercase;">⚽ PERFORMANCE HUB</h1><p style="margin:5px 0 0 0;">Control de acceso</p></div>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.markdown("### Iniciar Sesión")
        user_input = st.text_input("👤 Usuario")
        pass_input = st.text_input("🔑 Contraseña", type="password")
        
        if st.button("Entrar al sistema", type="primary", use_container_width=True):
            if user_input in USUARIOS_PERMITIDOS and USUARIOS_PERMITIDOS[user_input] == pass_input:
                st.session_state.logged_in = True
                st.session_state.username = user_input
                # Borramos la memoria temporal para cargar los datos limpios del nuevo usuario
                for key in ['session_tasks', 'saved_sessions', 'task_library']:
                    if key in st.session_state: del st.session_state[key]
                st.rerun()
            else:
                st.error("❌ Usuario o contraseña incorrectos")
    st.stop()

# ============================================================
# RUTAS DE ARCHIVOS DINÁMICAS POR USUARIO
# ============================================================
USUARIO_ACTUAL = st.session_state.username
ARCHIVO_HISTORICO = f"historico_{USUARIO_ACTUAL}.json"
ARCHIVO_LIBRERIA = f"libreria_{USUARIO_ACTUAL}.json"

with st.sidebar:
    st.markdown(f"### 👤 Perfil activo:\n**{USUARIO_ACTUAL.upper()}**")
    if st.button("🚪 Cerrar sesión", use_container_width=True):
        st.session_state.logged_in = False
        st.session_state.username = ""
        st.rerun()
    st.divider()

# ============================================================
# ESTADO GLOBAL
# ============================================================

if 'session_tasks' not in st.session_state:
    st.session_state.session_tasks = []

if 'saved_sessions' not in st.session_state:
    st.session_state.saved_sessions = []
    try:
        with open(ARCHIVO_HISTORICO, "r", encoding="utf-8") as f:
            st.session_state.saved_sessions = json.load(f)
    except:
        pass

if 'task_library' not in st.session_state:
    st.session_state.task_library = []
    try:
        with open(ARCHIVO_LIBRERIA, "r", encoding="utf-8") as f:
            st.session_state.task_library = json.load(f)
    except:
        pass

# ============================================================
# REFERENCIA DE PARTIDO REAL (2ª RFEF, promedio 10 jornadas)
# ============================================================

MATCH_REFERENCE_2RFEF = {
    "distance": 11039.7,            # m
    "sprints": 11.08392543,         # n
    "sprint_distance": 185.9381313, # m
    "hsr": 567.234726,              # m
    "acc": 128.54597,               # n
    "dec": 120.173,                 # n
}

AVG_SPRINT_LENGTH_MATCH = (
    MATCH_REFERENCE_2RFEF["sprint_distance"] / MATCH_REFERENCE_2RFEF["sprints"]
    if MATCH_REFERENCE_2RFEF["sprints"] > 0 else 16.8
)

DEFAULT_MATCH_REFERENCE = {
    "distance": MATCH_REFERENCE_2RFEF["distance"],
    "hsr": MATCH_REFERENCE_2RFEF["hsr"],
    "sprint_distance": MATCH_REFERENCE_2RFEF["sprint_distance"],
    "acc": MATCH_REFERENCE_2RFEF["acc"],
    "dec": MATCH_REFERENCE_2RFEF["dec"],
    "sprints": MATCH_REFERENCE_2RFEF["sprints"],
}

DAY_ORDER = {"MD+1": 1, "MD-4": 2, "MD-3": 3, "MD-2": 4, "MD-1": 5, "Partido": 6}

# ============================================================
# FACTORES POR TIPO DE EJERCICIO
# ============================================================

FACTORES_EJERCICIO = {
    "Juego de posición":    {"hsr": 0.55, "sprint": 0.50, "acc": 0.80, "dec": 0.80},
    "Rondo":                {"hsr": 0.50, "sprint": 0.45, "acc": 1.00, "dec": 1.00},
    "Posesión":             {"hsr": 0.85, "sprint": 0.80, "acc": 1.05, "dec": 1.05},
    "Transición/Oleadas":   {"hsr": 2.80, "sprint": 3.20, "acc": 1.15, "dec": 1.15},
    "Box to Box":           {"hsr": 1.00, "sprint": 1.00, "acc": 1.00, "dec": 1.00},
    "Partido condicionado": {"hsr": 1.20, "sprint": 1.15, "acc": 1.15, "dec": 1.15},
    "Partido":              {"hsr": 0.70, "sprint": 6.15, "acc": 0.95, "dec": 0.95},
    "Otro":                 {"hsr": 1.00, "sprint": 1.00, "acc": 1.00, "dec": 1.00},
}

# ============================================================
# MICROCICLO
# ============================================================

MICROCYCLE_DAY_RANGES = {
    "MD+1": {"distance": (60, 70), "hsr": (80, 90), "sprint_distance": (70, 80), "acc": (60, 80), "dec": (60, 80)},
    "MD-4": {"distance": (50, 60), "hsr": (10, 20), "sprint_distance": (5, 10), "acc": (75, 85), "dec": (75, 85)},
    "MD-3": {"distance": (65, 75), "hsr": (65, 80), "sprint_distance": (65, 75), "acc": (40, 50), "dec": (40, 50)},
    "MD-2": {"distance": (35, 45), "hsr": (10, 15), "sprint_distance": (5, 15), "acc": (20, 30), "dec": (20, 30)},
    "MD-1": {"distance": (20, 30), "hsr": (5, 10), "sprint_distance": (0, 5), "acc": (10, 20), "dec": (10, 20)},
    "Partido": {"distance": (100, 100), "hsr": (100, 100), "sprint_distance": (100, 100), "acc": (100, 100), "dec": (100, 100)},
}

WEEKLY_TOTAL_RANGES = {
    "Titular": {
        "distance": (170, 210),
        "hsr": (90, 125),
        "sprint_distance": (75, 105),
        "acc": (145, 185),
        "dec": (145, 185),
    },
    "Suplente": {
        "distance": (230, 280),
        "hsr": (160, 210),
        "sprint_distance": (145, 185),
        "acc": (205, 265),
        "dec": (205, 265),
    },
}

# ============================================================
# UTILIDADES Y FÓRMULAS
# ============================================================

def validar_positivo(valor): return max(valor, 0.001)

def calcular_app(largo, ancho, jugadores):
    return (validar_positivo(largo) * validar_positivo(ancho)) / validar_positivo(jugadores)

def hsr_relativo(app):
    if app < 100: return 0.5
    elif app < 150: return 2.0
    elif app < 182: return 4.0
    elif app < 225: return 6.0
    return 8.0

def clasificar_carga(carga_total):
    if carga_total < 300: return "Baja", "🟢"
    elif carga_total < 700: return "Media", "🟡"
    return "Alta", "🔴"

def wrap_text(texto, width=110): return "\n".join(textwrap.wrap(str(texto), width=width))
def safe_div(a, b): return None if b in [None, 0] else a / b
def pct_of_match(value, ref): return None if ref in [None, 0] else (float(value) / float(ref)) * 100

def microcycle_status(value, min_v, max_v):
    if value is None: return "Sin referencia"
    if value < min_v: return "🟡 Bajo"
    if value > max_v: return "🔴 Alto"
    return "🟢 Adecuado"

def state_color(estado):
    if "🟢" in str(estado): return "background-color: #dcfce7;"
    if "🟡" in str(estado): return "background-color: #fef9c3;"
    if "🔴" in str(estado): return "background-color: #fee2e2;"
    return ""

def get_task_colors(n):
    cmap = plt.get_cmap("tab20")
    return [cmap(i % 20) for i in range(max(1, n))]

def session_ratio_hsr_sprint_vs_acc_dec(hsr, sprint, acc, dec):
    num = float(hsr or 0) + float(sprint or 0)
    den = float(acc or 0) + float(dec or 0)
    return safe_div(num, den)

def current_timestamp(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def factor_longitudinal(largo, ancho, tipo):
    if ancho <= 0: return 1.0
    ratio = largo / ancho
    if tipo not in ["Transición/Oleadas", "Partido", "Partido condicionado"]: return 1.0
    if ratio < 1.3: return 1.00
    if ratio < 1.7: return 1.20
    if ratio < 2.2: return 1.45
    if ratio < 3.0: return 1.70
    return 1.90

def factor_continuidad(ida_vuelta_continua, tipo):
    if not ida_vuelta_continua: return 1.0
    if tipo == "Transición/Oleadas": return 1.35
    return 1.10

def minimo_hsr_min(largo, tipo, ida_vuelta_continua):
    if tipo != "Transición/Oleadas": return 0.0
    if largo >= 35: base = 6.5
    elif largo >= 30: base = 5.5
    elif largo >= 25: base = 4.5
    else: base = 3.0
    return base * 1.15 if ida_vuelta_continua else base

def minimo_sprint_min(largo, tipo, ida_vuelta_continua):
    if tipo != "Transición/Oleadas": return 0.0
    if largo >= 35: base = 1.00
    elif largo >= 30: base = 0.80
    elif largo >= 25: base = 0.60
    else: base = 0.35
    return base * 1.10 if ida_vuelta_continua else base

def metricas_base_excel(app):
    app = validar_positivo(app)
    dt = 19.243 * math.log(app) - 5.029
    d_sprint = 0.001 * app - 0.046
    d_acc = 1.321 * math.log(app) - 0.629
    acc = 0.212 * math.log(app) - 0.23
    d_dec = 1.157 * math.log(app) - 0.418
    dec = 0.104 * math.log(app) - 0.096
    return max(dt, 0), max(d_sprint, 0), max(d_acc, 0), max(acc, 0), max(d_dec, 0), max(dec, 0)

def box_to_box_hsr_ratio(d): return 0.18 if d < 20 else (0.35 if d < 30 else (0.50 if d < 40 else 0.58))
def box_to_box_sprint_ratio(d): return 0.00 if d < 20 else (0.06 if d < 30 else (0.12 if d < 40 else 0.18))
def box_to_box_acc_dec_totales(reps, d):
    f = 0.60 if d < 20 else (0.50 if d < 30 else (0.40 if d < 40 else 0.30))
    return max(1, round(reps * f, 2)), max(1, round(reps * f, 2))

def interpretacion_practica(carga_total, hsr_total, sprint_distance_total, acc_total, dec_total, tipo):
    txt_carga = "baja" if carga_total < 300 else ("media" if carga_total < 700 else "alta")
    txt_hsr = "reducida" if hsr_total < 20 else ("moderada" if hsr_total < 50 else "elevada")
    txt_sprint = "baja" if sprint_distance_total < 10 else ("moderada" if sprint_distance_total < 25 else "alta")
    txt_acc = "bajo" if acc_total < 5 else ("moderado" if acc_total < 12 else "alto")
    txt_dec = "bajo" if dec_total < 5 else ("moderado" if dec_total < 12 else "alto")
    return f"En {tipo.lower()}, la carga global es {txt_carga}; además, la exposición al HSR es {txt_hsr}, la distancia a sprint es {txt_sprint}, aceleraciones {txt_acc} y deceleraciones {txt_dec}."

# ============================================================
# CÁLCULO PRINCIPAL
# ============================================================
def calcular_carga(jugadores, duracion, tipo, ida_vuelta_continua=False, largo=None, ancho=None, repeticiones=None, nombre_tarea="Tarea"):
    if tipo == "Box to Box":
        distancia_carrera = largo
        reps = repeticiones
        distancia_total = distancia_carrera * reps
        hsr_total = distancia_total * box_to_box_hsr_ratio(distancia_carrera)
        sprint_distance_total = distancia_total * box_to_box_sprint_ratio(distancia_carrera)
        sprints_totales = sprint_distance_total / AVG_SPRINT_LENGTH_MATCH if AVG_SPRINT_LENGTH_MATCH > 0 else 0
        acc_total, dec_total = box_to_box_acc_dec_totales(reps, distancia_carrera)
        interp = interpretacion_practica(distancia_total, hsr_total, sprint_distance_total, acc_total, dec_total, tipo)
        clasificacion, semaforo = clasificar_carga(distancia_total)
        return {
            "Nombre tarea": str(nombre_tarea).strip() or "Tarea", "Ejercicio": tipo,
            "Largo (m)": round(distancia_carrera, 2), "Ancho (m)": None, "ApP (m²/jugador)": None, "Jugadores": int(jugadores),
            "Duración (min)": None, "Repeticiones": int(reps), "Ida y vuelta continua": "No aplica",
            "Factor HSR": None, "Factor Sprint": None, "Factor ACC": None, "Factor DEC": None, "Factor longitudinal": None, "Factor continuidad": None, "Suelo HSR/min": None, "Suelo Sprint distancia/min": None,
            "Distancia total (m)": round(distancia_total, 2), "HSR/min (m)": None, "HSR total (m)": round(hsr_total, 2),
            "Distancia sprint/min (m)": None, "Distancia sprint total (m)": round(sprint_distance_total, 2), "Nº sprints/min": None, "Nº sprints totales": round(sprints_totales, 2),
            "ACC/min (n)": None, "ACC total (n)": round(acc_total, 2), "DEC/min (n)": None, "DEC total (n)": round(dec_total, 2),
            "Dist ACC/min (m)": None, "Dist ACC total (m)": None, "Dist DEC/min (m)": None, "Dist DEC total (m)": None,
            "Carga total (m)": round(distancia_total, 2), "Clasificación": clasificacion, "Semáforo": semaforo, "Interpretación": interp,
        }

    app = calcular_app(largo, ancho, jugadores)
    factor_long = factor_longitudinal(largo, ancho, tipo)
    factor_cont = factor_continuidad(ida_vuelta_continua, tipo)
    suelo_hsr = minimo_hsr_min(largo, tipo, ida_vuelta_continua)
    suelo_sprint = minimo_sprint_min(largo, tipo, ida_vuelta_continua)
    factores = FACTORES_EJERCICIO[tipo]
    dt, d_sprint, d_acc, acc, d_dec, dec = metricas_base_excel(app)

    hsr_base = hsr_relativo(app)
    hsr_min_modelo = hsr_base * factores["hsr"] * factor_long * factor_cont
    hsr_min = max(hsr_min_modelo, suelo_hsr)
    hsr_total = hsr_min * duracion

    sprint_distance_min_modelo = d_sprint * factores["sprint"] * factor_long * factor_cont
    sprint_distance_min = max(sprint_distance_min_modelo, suelo_sprint)
    sprint_distance_total = sprint_distance_min * duracion

    sprints_totales = sprint_distance_total / AVG_SPRINT_LENGTH_MATCH if AVG_SPRINT_LENGTH_MATCH > 0 else 0
    sprints_min = sprints_totales / duracion if duracion > 0 else 0

    acc_min = acc * factores["acc"]
    acc_total = acc_min * duracion
    dec_min = dec * factores["dec"]
    dec_total = dec_min * duracion

    dist_acc_min = d_acc * factores["acc"]
    dist_acc_total = dist_acc_min * duracion
    dist_dec_min = d_dec * factores["dec"]
    dist_dec_total = dist_dec_min * duracion

    carga_total = dt * duracion
    clasificacion, semaforo = clasificar_carga(carga_total)
    interp = interpretacion_practica(carga_total, hsr_total, sprint_distance_total, acc_total, dec_total, tipo)

    return {
        "Nombre tarea": str(nombre_tarea).strip() or "Tarea", "Ejercicio": tipo,
        "Largo (m)": round(largo, 2), "Ancho (m)": round(ancho, 2), "ApP (m²/jugador)": round(app, 2), "Jugadores": int(jugadores),
        "Duración (min)": round(duracion, 2), "Repeticiones": None, "Ida y vuelta continua": "Sí" if ida_vuelta_continua else "No",
        "Factor HSR": factores["hsr"], "Factor Sprint": factores["sprint"], "Factor ACC": factores["acc"], "Factor DEC": factores["dec"],
        "Factor longitudinal": round(factor_long, 2), "Factor continuidad": round(factor_cont, 2), "Suelo HSR/min": round(suelo_hsr, 2), "Suelo Sprint distancia/min": round(suelo_sprint, 2),
        "Distancia total (m)": round(carga_total, 2), "HSR/min (m)": round(hsr_min, 2), "HSR total (m)": round(hsr_total, 2),
        "Distancia sprint/min (m)": round(sprint_distance_min, 3), "Distancia sprint total (m)": round(sprint_distance_total, 2),
        "Nº sprints/min": round(sprints_min, 3), "Nº sprints totales": round(sprints_totales, 2),
        "ACC/min (n)": round(acc_min, 3), "ACC total (n)": round(acc_total, 2), "DEC/min (n)": round(dec_min, 3), "DEC total (n)": round(dec_total, 2),
        "Dist ACC/min (m)": round(dist_acc_min, 2), "Dist ACC total (m)": round(dist_acc_total, 2), "Dist DEC/min (m)": round(dist_dec_min, 2), "Dist DEC total (m)": round(dist_dec_total, 2),
        "Carga total (m)": round(carga_total, 2), "Clasificación": clasificacion, "Semáforo": semaforo, "Interpretación": interp,
    }

# ============================================================
# RESUMEN Y ANÁLISIS DE SESIÓN
# ============================================================
def obtener_resumen_sesion():
    if not st.session_state.session_tasks:
        return None, None
    df = pd.DataFrame(st.session_state.session_tasks)
    resumen = pd.DataFrame({
        "Número de tareas": [len(df)],
        "Duración total (min)": [round(df["Duración (min)"].fillna(0).sum(), 2)],
        "Distancia total sesión (m)": [round(df["Distancia total (m)"].fillna(0).sum(), 2)],
        "Distancia sprint total sesión (m)": [round(df["Distancia sprint total (m)"].fillna(0).sum(), 2)],
        "Nº sprints totales sesión": [round(df["Nº sprints totales"].fillna(0).sum(), 2)],
        "HSR total sesión (m)": [round(df["HSR total (m)"].fillna(0).sum(), 2)],
        "ACC total sesión (n)": [round(df["ACC total (n)"].fillna(0).sum(), 2)],
        "DEC total sesión (n)": [round(df["DEC total (n)"].fillna(0).sum(), 2)],
        "Carga total sesión (m)": [round(df["Carga total (m)"].fillna(0).sum(), 2)],
    })
    ratio = session_ratio_hsr_sprint_vs_acc_dec(
        resumen["HSR total sesión (m)"].iloc[0],
        resumen["Distancia sprint total sesión (m)"].iloc[0],
        resumen["ACC total sesión (n)"].iloc[0],
        resumen["DEC total sesión (n)"].iloc[0],
    )
    resumen["Ratio (HSR+Sprint)/(ACC+DEC)"] = [round(ratio, 4) if ratio is not None else None]
    return df, resumen

def build_current_session_microcycle_table(summary_row, day_label):
    ranges = MICROCYCLE_DAY_RANGES.get(day_label)
    if ranges is None: return None
    rows = []
    metric_map = [
        ("Distancia total", float(summary_row["Distancia total sesión (m)"]), DEFAULT_MATCH_REFERENCE["distance"], "distance"),
        ("HSR", float(summary_row["HSR total sesión (m)"]), DEFAULT_MATCH_REFERENCE["hsr"], "hsr"),
        ("Distancia sprint", float(summary_row["Distancia sprint total sesión (m)"]), DEFAULT_MATCH_REFERENCE["sprint_distance"], "sprint_distance"),
        ("ACC", float(summary_row["ACC total sesión (n)"]), DEFAULT_MATCH_REFERENCE["acc"], "acc"),
        ("DEC", float(summary_row["DEC total sesión (n)"]), DEFAULT_MATCH_REFERENCE["dec"], "dec"),
    ]
    for label, value, ref, key in metric_map:
        pct = pct_of_match(value, ref)
        min_v, max_v = ranges[key]
        rows.append({
            "Variable": label,
            "% sesión vs partido": round(pct, 2) if pct is not None else None,
            "Objetivo mínimo (%)": min_v,
            "Objetivo máximo (%)": max_v,
            "Estado": microcycle_status(pct, min_v, max_v),
        })
    return pd.DataFrame(rows)

def build_day_status_summary_html(analysis_df):
    if analysis_df is None or analysis_df.empty: return ""
    n_green = sum(analysis_df["Estado"].astype(str).str.contains("🟢"))
    n_yellow = sum(analysis_df["Estado"].astype(str).str.contains("🟡"))
    n_red = sum(analysis_df["Estado"].astype(str).str.contains("🔴"))
    if n_red >= 2: general, bg, border = "🔴 Sesión demasiado alejada del objetivo del día", "#fee2e2", "#fca5a5"
    elif n_yellow >= 2: general, bg, border = "🟡 Sesión parcialmente ajustada al día", "#fef9c3", "#fde68a"
    else: general, bg, border = "🟢 Sesión bien ajustada al día", "#dcfce7", "#86efac"
    return f'<div style="margin:10px 0 14px 0;padding:14px;border:1px solid {border};border-radius:14px;background:{bg};"><div style="font-weight:700;margin-bottom:6px;">{general}</div><div style="font-size:13px;">Adecuadas: <strong>{n_green}</strong> &nbsp; | &nbsp; Bajas: <strong>{n_yellow}</strong> &nbsp; | &nbsp; Altas: <strong>{n_red}</strong></div></div>'

def build_progress_bars(summary_row, day_label):
    ranges = MICROCYCLE_DAY_RANGES.get(day_label)
    if ranges is None: return "<div>No hay referencias.</div>"
    metrics = [
        ("Distancia total", float(summary_row["Distancia total sesión (m)"]), DEFAULT_MATCH_REFERENCE["distance"], "distance"),
        ("HSR", float(summary_row["HSR total sesión (m)"]), DEFAULT_MATCH_REFERENCE["hsr"], "hsr"),
        ("Sprint", float(summary_row["Distancia sprint total sesión (m)"]), DEFAULT_MATCH_REFERENCE["sprint_distance"], "sprint_distance"),
        ("ACC", float(summary_row["ACC total sesión (n)"]), DEFAULT_MATCH_REFERENCE["acc"], "acc"),
        ("DEC", float(summary_row["DEC total sesión (n)"]), DEFAULT_MATCH_REFERENCE["dec"], "dec"),
    ]
    blocks = []
    for label, value, ref, key in metrics:
        pct = pct_of_match(value, ref) or 0
        min_v, max_v = ranges[key]
        width = min(max(pct, 0), 100)
        if pct < min_v: color = "#eab308"
        elif pct > max_v: color = "#dc2626"
        else: color = "#16a34a"
        blocks.append(f'<div style="margin-bottom:10px;"><div style="display:flex;justify-content:space-between;font-size:13px;"><span><strong>{label}</strong></span><span>{pct:.1f}% (objetivo {min_v}-{max_v}%)</span></div><div style="width:100%;background:#e5e7eb;border-radius:999px;height:12px;overflow:hidden;"><div style="width:{width}%;background:{color};height:12px;"></div></div></div>')
    return "<div style='padding:12px;border:1px solid #e5e7eb;border-radius:14px;background:#fff;'>" + "".join(blocks) + "</div>"

def generar_propuesta_ajuste(summary_row, day_label):
    df = build_current_session_microcycle_table(summary_row, day_label)
    if df is None: return ["No se ha podido generar propuesta de ajuste."]
    propuestas = []
    for _, row in df.iterrows():
        variable = row["Variable"]
        estado = row["Estado"]
        if "🟡" in estado:
            if variable == "HSR": propuestas.append("Aumentar HSR con tareas más longitudinales, mayor espacio útil o bloques de transición/oleadas.")
            elif variable == "Distancia sprint": propuestas.append("Aumentar sprint introduciendo espacios más largos, carreras orientadas o tareas con profundidad.")
            elif variable == "ACC": propuestas.append("Aumentar ACC con tareas más densas, espacios reducidos y cambios frecuentes de orientación.")
            elif variable == "DEC": propuestas.append("Aumentar DEC con tareas de frenada, ida-vuelta o mayor densidad de cambios de dirección.")
            elif variable == "Distancia total": propuestas.append("Aumentar distancia total prolongando duración útil o añadiendo una tarea complementaria.")
        elif "🔴" in estado:
            if variable == "HSR": propuestas.append("Reducir HSR acortando espacio longitudinal o sustituyendo una tarea abierta por una más densa.")
            elif variable == "Distancia sprint": propuestas.append("Reducir sprint limitando profundidad, repeticiones largas o metros libres a espalda.")
            elif variable == "ACC": propuestas.append("Reducir ACC aumentando espacio, bajando densidad o reduciendo número de estímulos cortos.")
            elif variable == "DEC": propuestas.append("Reducir DEC eliminando frenadas repetidas, giros cortos o tareas de ida-vuelta continua.")
            elif variable == "Distancia total": propuestas.append("Reducir distancia total acortando duración efectiva o eliminando un bloque accesorio.")
    if not propuestas: propuestas.append("La sesión está bien ajustada al día del microciclo seleccionado.")
    return propuestas

def session_cards_html():
    data, resumen = obtener_resumen_sesion()
    if data is None:
        return '<div style="padding:14px;border:1px solid #e5e7eb;border-radius:16px;background:#ffffff;">No hay tareas en la sesión.</div>'
    vals = {
        "Distancia total": resumen["Distancia total sesión (m)"].iloc[0],
        "HSR": resumen["HSR total sesión (m)"].iloc[0],
        "Sprint": resumen["Distancia sprint total sesión (m)"].iloc[0],
        "Nº sprints": resumen["Nº sprints totales sesión"].iloc[0],
        "ACC": resumen["ACC total sesión (n)"].iloc[0],
        "DEC": resumen["DEC total sesión (n)"].iloc[0],
    }
    palette = ["#1d4ed8", "#0f766e", "#7c3aed", "#ea580c", "#dc2626", "#0891b2"]
    cards = ""
    for i, (k, v) in enumerate(vals.items()):
        cards += f'<div style="background: linear-gradient(135deg, {palette[i]}, #0f172a); border-radius: 16px; padding: 16px; min-width: 150px; box-shadow: 0 4px 14px rgba(0,0,0,0.10); color: white; flex:1;"><div style="font-size:12px;opacity:0.9;">{k}</div><div style="font-size:24px;font-weight:800;margin-top:4px;">{float(v):.1f}</div></div>'
    return f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin:6px 0 16px 0;">{cards}</div>'

# ============================================================
# GRÁFICOS MATPLOTLIB
# ============================================================
def make_fig_resumen_global():
    data, resumen = obtener_resumen_sesion()
    if data is None: return None
    vals = {"Distancia total": resumen["Distancia total sesión (m)"].iloc[0], "Distancia sprint": resumen["Distancia sprint total sesión (m)"].iloc[0], "Nº sprints": resumen["Nº sprints totales sesión"].iloc[0], "HSR": resumen["HSR total sesión (m)"].iloc[0], "ACC": resumen["ACC total sesión (n)"].iloc[0], "DEC": resumen["DEC total sesión (n)"].iloc[0]}
    fig, ax = plt.subplots(figsize=(12.5, 5))
    ax.axis("off")
    ax.set_title("Resumen global de la sesión", fontsize=16, fontweight="bold", pad=16)
    colors = ["#1d4ed8", "#0f766e", "#7c3aed", "#ea580c", "#dc2626", "#0891b2"]
    x_positions = [0.02, 0.18, 0.34, 0.50, 0.66, 0.82]
    for i, ((label, value), x) in enumerate(zip(vals.items(), x_positions)):
        rect = plt.Rectangle((x, 0.22), 0.14, 0.48, transform=ax.transAxes, facecolor=colors[i], edgecolor="#0f172a", linewidth=1.2, alpha=0.92)
        ax.add_patch(rect)
        ax.text(x + 0.07, 0.55, label, ha="center", va="center", transform=ax.transAxes, fontsize=10, color="white", fontweight="bold")
        ax.text(x + 0.07, 0.38, f"{float(value):.1f}", ha="center", va="center", transform=ax.transAxes, fontsize=16, color="white", fontweight="bold")
    return fig

def make_fig_carga():
    data, _ = obtener_resumen_sesion()
    if data is None: return None
    fig, ax = plt.subplots(figsize=(11.8, 5.5))
    colors = get_task_colors(len(data))
    bars = ax.bar(data["Nombre tarea"], data["Distancia total (m)"], color=colors, edgecolor="black", linewidth=0.8)
    ax.set_title("Distancia total por ejercicio", fontsize=15, fontweight="bold")
    ax.set_ylabel("Distancia total (m)")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    plt.xticks(rotation=30, ha="right")
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2, h, f"{h:.1f}", ha="center", va="bottom", fontsize=9)
    plt.tight_layout()
    return fig

def make_fig_hsr_sprint():
    data, _ = obtener_resumen_sesion()
    if data is None: return None
    x = list(range(len(data)))
    width = 0.38
    colors = get_task_colors(len(data))
    fig, ax = plt.subplots(figsize=(11.8, 5.5))
    for i in range(len(data)):
        ax.bar(x[i] - width/2, data["HSR total (m)"].iloc[i], width=width, color=colors[i], edgecolor="black", linewidth=0.8)
        ax.bar(x[i] + width/2, data["Distancia sprint total (m)"].iloc[i], width=width, color=colors[i], edgecolor="black", linewidth=0.8, alpha=0.45, hatch="//")
        ax.text(x[i] - width/2, data["HSR total (m)"].iloc[i], f"{data['HSR total (m)'].iloc[i]:.1f}", ha="center", va="bottom", fontsize=8)
        ax.text(x[i] + width/2, data["Distancia sprint total (m)"].iloc[i], f"{data['Distancia sprint total (m)'].iloc[i]:.1f}", ha="center", va="bottom", fontsize=8)
    ax.set_title("HSR y distancia sprint por ejercicio", fontsize=15, fontweight="bold")
    ax.set_ylabel("Metros")
    ax.set_xticks(x)
    ax.set_xticklabels(data["Nombre tarea"], rotation=30, ha="right")
    ax.legend(["HSR", "Sprint"], loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    plt.tight_layout()
    return fig

def make_fig_acc_dec():
    data, _ = obtener_resumen_sesion()
    if data is None: return None
    x = list(range(len(data)))
    width = 0.38
    colors = get_task_colors(len(data))
    fig, ax = plt.subplots(figsize=(11.8, 5.5))
    for i in range(len(data)):
        ax.bar(x[i] - width/2, data["ACC total (n)"].iloc[i], width=width, color=colors[i], edgecolor="black", linewidth=0.8)
        ax.bar(x[i] + width/2, data["DEC total (n)"].iloc[i], width=width, color=colors[i], edgecolor="black", linewidth=0.8, alpha=0.45, hatch="xx")
        ax.text(x[i] - width/2, data["ACC total (n)"].iloc[i], f"{data['ACC total (n)'].iloc[i]:.1f}", ha="center", va="bottom", fontsize=8)
        ax.text(x[i] + width/2, data["DEC total (n)"].iloc[i], f"{data['DEC total (n)'].iloc[i]:.1f}", ha="center", va="bottom", fontsize=8)
    ax.set_title("Aceleraciones y deceleraciones por ejercicio", fontsize=15, fontweight="bold")
    ax.set_ylabel("Nº acciones")
    ax.set_xticks(x)
    ax.set_xticklabels(data["Nombre tarea"], rotation=30, ha="right")
    ax.legend(["ACC", "DEC"], loc="upper right")
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    plt.tight_layout()
    return fig

def make_fig_aporte_porcentual(metric_col, title):
    data, _ = obtener_resumen_sesion()
    if data is None or metric_col not in data.columns: return None
    total = float(data[metric_col].fillna(0).sum())
    porcentajes = [0 for _ in range(len(data))] if total <= 0 else [(float(v) / total) * 100 for v in data[metric_col].fillna(0)]
    colors = get_task_colors(len(data))
    fig, ax = plt.subplots(figsize=(11.8, 5.5))
    bars = ax.bar(data["Nombre tarea"], porcentajes, color=colors, edgecolor="black", linewidth=0.8)
    ax.set_title(f"Aporte porcentual por tarea - {title}", fontsize=15, fontweight="bold")
    ax.set_ylabel("% del total de la sesión")
    ax.set_ylim(0, max(100, max(porcentajes) * 1.18 if porcentajes else 100))
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    plt.xticks(rotation=30, ha="right")
    valores_absolutos = list(data[metric_col].fillna(0).astype(float))
    for bar, pct, abs_val in zip(bars, porcentajes, valores_absolutos):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1, f"{pct:.1f}%\n({abs_val:.1f})", ha="center", va="bottom", fontsize=9, fontweight="bold")
    plt.tight_layout()
    return fig

# ============================================================
# PDF EXPORT
# ============================================================
def add_text_page(pdf, title, lines):
    fig = plt.figure(figsize=(8.27, 11.69))
    plt.axis("off")
    y = 0.97
    fig.text(0.05, y, title, fontsize=16, weight="bold", va="top")
    y -= 0.04
    for line in lines:
        wrapped = wrap_text(line, 95)
        n_lines = wrapped.count("\n") + 1
        fig.text(0.05, y, wrapped, fontsize=10, va="top")
        y -= 0.026 * n_lines
        if y < 0.06:
            pdf.savefig(fig, bbox_inches="tight")
            plt.close(fig)
            fig = plt.figure(figsize=(8.27, 11.69))
            plt.axis("off")
            y = 0.97
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

def add_dataframe_page(pdf, title, df, fontsize=8):
    if df is None or df.empty:
        add_text_page(pdf, title, ["No hay datos disponibles."])
        return
    fig, ax = plt.subplots(figsize=(11.69, 8.27))
    ax.axis("off")
    ax.set_title(title, fontsize=16, fontweight="bold", pad=16)
    table = ax.table(cellText=df.astype(str).values, colLabels=df.columns, loc="center", cellLoc="center")
    table.auto_set_font_size(False)
    table.set_fontsize(fontsize)
    table.scale(1, 1.6)
    for (row, col), cell in table.get_celld().items():
        cell.set_edgecolor("#cbd5e1")
        if row == 0:
            cell.set_facecolor("#0f172a")
            cell.get_text().set_color("white")
            cell.get_text().set_weight("bold")
        else:
            cell.set_facecolor("#f8fafc" if row % 2 == 0 else "#eef2ff")
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)

def generar_pdf_bytes(session_name, day_dropdown, week, meso):
    data, resumen = obtener_resumen_sesion()
    if data is None: return None
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        lines = [f"Sesión: {session_name}", f"Día microciclo: {day_dropdown}", f"Semana: {week}", f"Mesociclo: {meso}", "", "El informe incluye resumen global, control del día del microciclo y gráficas."]
        add_text_page(pdf, "INFORME DE SESIÓN", lines)
        add_dataframe_page(pdf, "Resumen total de la sesión", resumen.copy(), fontsize=10)
        day_df = build_current_session_microcycle_table(resumen.iloc[0], day_dropdown)
        if day_df is not None: add_dataframe_page(pdf, "Ajuste de la sesión al día del microciclo", day_df.copy(), fontsize=9)
        figs = [make_fig_resumen_global(), make_fig_carga(), make_fig_hsr_sprint(), make_fig_acc_dec(), make_fig_aporte_porcentual("Distancia total (m)", "Distancia total"), make_fig_aporte_porcentual("HSR total (m)", "HSR")]
        for fig in figs:
            if fig is not None:
                pdf.savefig(fig, bbox_inches="tight")
                plt.close(fig)
    return buf.getvalue()

def compare_saved_sessions(name_a, name_b):
    if not st.session_state.saved_sessions: return None
    sess_a = next((s for s in st.session_state.saved_sessions if s["session_name"] == name_a), None)
    sess_b = next((s for s in st.session_state.saved_sessions if s["session_name"] == name_b), None)
    if sess_a is None or sess_b is None: return None
    a_sum, b_sum = sess_a["summary"], sess_b["summary"]
    keys = ["Distancia total sesión (m)", "Distancia sprint total sesión (m)", "Nº sprints totales sesión", "HSR total sesión (m)", "ACC total sesión (n)", "DEC total sesión (n)", "Carga total sesión (m)"]
    rows = []
    for key in keys:
        a, b = float(a_sum.get(key, 0)), float(b_sum.get(key, 0))
        diff = b - a
        pct = ((diff / a) * 100) if a != 0 else None
        rows.append({"Variable": key, name_a: round(a, 2), name_b: round(b, 2), "Diferencia": round(diff, 2), "% cambio": round(pct, 2) if pct is not None else None})
    return pd.DataFrame(rows)

# ============================================================
# DATAFRAMES HISTÓRICOS Y AVANZADOS
# ============================================================
def get_history_dataframe():
    if not st.session_state.saved_sessions: return None
    rows = []
    for i, sess in enumerate(st.session_state.saved_sessions, start=1):
        row = {"Orden": i, "Sesión": sess["session_name"], "Semana": sess.get("week"), "Mesociclo": sess.get("mesocycle"), "Día microciclo": sess["microcycle_day"]}
        row.update(sess["summary"])
        rows.append(row)
    return pd.DataFrame(rows)

def weekly_summary_dataframe(role_label="Titular"):
    df = get_history_dataframe()
    if df is None: return None
    grouped = df.groupby(["Mesociclo", "Semana"], as_index=False).agg({"Distancia total sesión (m)": "sum", "HSR total sesión (m)": "sum", "Distancia sprint total sesión (m)": "sum", "ACC total sesión (n)": "sum", "DEC total sesión (n)": "sum", "Carga total sesión (m)": "sum"})
    grouped["Ratio (HSR+Sprint)/(ACC+DEC)"] = grouped.apply(lambda r: session_ratio_hsr_sprint_vs_acc_dec(r["HSR total sesión (m)"], r["Distancia sprint total sesión (m)"], r["ACC total sesión (n)"], r["DEC total sesión (n)"]), axis=1)
    ranges = WEEKLY_TOTAL_RANGES[role_label]
    grouped["% dist vs partido"] = grouped["Distancia total sesión (m)"] / DEFAULT_MATCH_REFERENCE["distance"] * 100
    grouped["% hsr vs partido"] = grouped["HSR total sesión (m)"] / DEFAULT_MATCH_REFERENCE["hsr"] * 100
    grouped["% sprint vs partido"] = grouped["Distancia sprint total sesión (m)"] / DEFAULT_MATCH_REFERENCE["sprint_distance"] * 100
    grouped["% acc vs partido"] = grouped["ACC total sesión (n)"] / DEFAULT_MATCH_REFERENCE["acc"] * 100
    grouped["% dec vs partido"] = grouped["DEC total sesión (n)"] / DEFAULT_MATCH_REFERENCE["dec"] * 100

    def week_status(row):
        checks = []
        for col, key in [("% dist vs partido", "distance"), ("% hsr vs partido", "hsr"), ("% sprint vs partido", "sprint_distance"), ("% acc vs partido", "acc"), ("% dec vs partido", "dec")]:
            mn, mx = ranges[key]
            checks.append(microcycle_status(row[col], mn, mx))
        red = sum("🔴" in c for c in checks)
        yellow = sum("🟡" in c for c in checks)
        if red >= 2: return "🔴 Semana sobrecargada"
        if yellow >= 2: return "🟡 Semana infracargada"
        return "🟢 Semana adecuada"

    grouped["Estado semanal"] = grouped.apply(week_status, axis=1)
    return grouped

def automatic_trend(series):
    if len(series) < 3: return "Sin datos suficientes"
    s = pd.Series(series).dropna()
    if len(s) < 3: return "Sin datos suficientes"
    recent = s.tail(3).tolist()
    if recent[2] > recent[1] > recent[0]: return "⬆️ Tendencia ascendente"
    if recent[2] < recent[1] < recent[0]: return "⬇️ Tendencia descendente"
    return "➡️ Tendencia estable"

def weekly_analytics_dataframe(role_label="Titular"):
    wk = weekly_summary_dataframe(role_label)
    if wk is None or wk.empty: return None
    wk = wk.sort_values(["Mesociclo", "Semana"]).copy()
    for col in ["Distancia total sesión (m)", "HSR total sesión (m)", "Distancia sprint total sesión (m)", "ACC total sesión (n)", "DEC total sesión (n)", "Carga total sesión (m)"]:
        wk[f"MM3 {col}"] = wk[col].rolling(3, min_periods=1).mean()
    wk["Desviación dist vs semana tipo"] = wk["% dist vs partido"] - sum(WEEKLY_TOTAL_RANGES[role_label]["distance"]) / 2
    wk["Desviación hsr vs semana tipo"] = wk["% hsr vs partido"] - sum(WEEKLY_TOTAL_RANGES[role_label]["hsr"]) / 2
    wk["Desviación sprint vs semana tipo"] = wk["% sprint vs partido"] - sum(WEEKLY_TOTAL_RANGES[role_label]["sprint_distance"]) / 2
    return wk

def mesocycle_matrix_dataframe():
    if not st.session_state.saved_sessions: return None
    rows = []
    for sess in st.session_state.saved_sessions:
        plan = sess["summary"]
        rows.append({"Mesociclo": sess.get("mesocycle", "Mesociclo 1"), "Semana": sess.get("week", 1), "Día": sess.get("microcycle_day"), "Sesión": sess.get("session_name"), "Distancia": plan.get("Distancia total sesión (m)", 0), "HSR": plan.get("HSR total sesión (m)", 0), "Sprint": plan.get("Distancia sprint total sesión (m)", 0), "ACC": plan.get("ACC total sesión (n)", 0), "DEC": plan.get("DEC total sesión (n)", 0), "Carga": plan.get("Carga total sesión (m)", 0)})
    df = pd.DataFrame(rows)
    df["Orden día"] = df["Día"].map(DAY_ORDER)
    return df.sort_values(["Mesociclo", "Semana", "Orden día", "Sesión"])

def neuromuscular_index_from_summary(summary):
    acc = float(summary.get("ACC total sesión (n)", 0))
    dec = float(summary.get("DEC total sesión (n)", 0))
    hsr = float(summary.get("HSR total sesión (m)", 0))
    return acc + dec + (hsr / 10)

def detect_consecutive_neuromuscular_alerts():
    if not st.session_state.saved_sessions: return []
    rows = [{"session_name": sess["session_name"], "mesocycle": sess.get("mesocycle", "Mesociclo 1"), "week": sess.get("week", 1), "day": sess.get("microcycle_day"), "order": DAY_ORDER.get(sess.get("microcycle_day"), 99), "nm_index": neuromuscular_index_from_summary(sess["summary"])} for sess in st.session_state.saved_sessions]
    df = pd.DataFrame(rows).sort_values(["mesocycle", "week", "order"])
    alerts = []
    for (meso, week), grp in df.groupby(["mesocycle", "week"]):
        grp = grp.sort_values("order").reset_index(drop=True)
        if len(grp) < 2: continue
        threshold = grp["nm_index"].quantile(0.75) if len(grp) >= 3 else grp["nm_index"].mean()
        for i in range(len(grp) - 1):
            a, b = grp.iloc[i], grp.iloc[i + 1]
            if a["nm_index"] >= threshold and b["nm_index"] >= threshold:
                alerts.append(f"Alerta neuromuscular: {meso} - Semana {week} tiene dos días consecutivos altos ({a['day']} y {b['day']}).")
    return alerts

# ============================================================
# FRONTEND - UI
# ============================================================
st.markdown('<div style="background: linear-gradient(90deg, #0f172a, #1e293b); color: #ffffff; padding: 18px 22px; border-radius: 16px; margin-bottom: 20px; text-align: center; box-shadow: 0 4px 14px rgba(0,0,0,0.18);"><h1 style="margin: 0; font-size: 30px; font-weight: 800; letter-spacing: 1px; text-transform: uppercase;">CALCULADORA AVANZADA DE CARGAS EN FÚTBOL</h1></div>', unsafe_allow_html=True)

tabs = st.tabs(["Calculadora", "Sesión", "Librería", "Microciclo", "Análisis", "Histórico", "Comparación", "Mesociclo", "Justificación"])

# ------------------------------------------------------------
# TAB 1: CALCULADORA
# ------------------------------------------------------------
with tabs[0]:
    st.header("1. Configuración de Sesión")
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1: sess_name = st.text_input("Sesión:", value="Sesión 1")
    with col_m2: meso_name = st.text_input("Mesociclo:", value="Mesociclo 1")
    with col_m3: week_val = st.number_input("Semana:", min_value=1, max_value=20, value=1)
    with col_m4: day_val = st.selectbox("Día microciclo:", ["MD+1", "MD-4", "MD-3", "MD-2", "MD-1", "Partido"], index=2)
    
    st.markdown(f'<div style="display:flex;gap:10px;flex-wrap:wrap;margin:6px 0 10px 0;"><div style="background:#eff6ff;border:1px solid #bfdbfe;padding:8px 12px;border-radius:999px;font-size:13px;"><strong>Tareas:</strong> {len(st.session_state.session_tasks)}</div><div style="background:#ecfeff;border:1px solid #a5f3fc;padding:8px 12px;border-radius:999px;font-size:13px;"><strong>Día:</strong> {day_val}</div><div style="background:#faf5ff;border:1px solid #d8b4fe;padding:8px 12px;border-radius:999px;font-size:13px;"><strong>Semana:</strong> {week_val}</div><div style="background:#fff7ed;border:1px solid #fdba74;padding:8px 12px;border-radius:999px;font-size:13px;"><strong>Mesociclo:</strong> {meso_name}</div></div>', unsafe_allow_html=True)

    if st.button("💾 Guardar / Actualizar Sesión", type="primary"):
        data_tmp, res_tmp = obtener_resumen_sesion()
        if data_tmp is not None:
            payload = {"session_name": sess_name, "microcycle_day": day_val, "week": week_val, "mesocycle": meso_name, "summary": res_tmp.iloc[0].to_dict(), "tasks": data_tmp.to_dict("records"), "updated_at": current_timestamp()}
            idx = next((i for i, s in enumerate(st.session_state.saved_sessions) if s["session_name"] == sess_name), None)
            if idx is not None: st.session_state.saved_sessions[idx] = payload
            else: st.session_state.saved_sessions.append(payload)
            with open(ARCHIVO_HISTORICO, "w", encoding="utf-8") as f: json.dump(st.session_state.saved_sessions, f, ensure_ascii=False, indent=2)
            st.success(f"Sesión '{sess_name}' guardada.")
        else: st.error("No hay tareas para guardar.")

    st.divider()
    st.header("2. Tarea")
    col_t1, col_t2 = st.columns(2)
    with col_t1: t_name = st.text_input("Nombre tarea:", value="Tarea 1")
    with col_t2: 
        presets = ["(Vacío)"] + [t["Nombre tarea"] for t in st.session_state.task_library]
        sel_preset = st.selectbox("Cargar desde librería:", presets)

    if sel_preset != "(Vacío)":
        d = next(t for t in st.session_state.task_library if t["Nombre tarea"] == sel_preset)
        def_t, def_l, def_a, def_j, def_dur, def_rep, def_ida = d.get("Ejercicio", "Transición/Oleadas"), float(d.get("Largo (m)", 30)), float(d.get("Ancho (m)", 15)), int(d.get("Jugadores", 10)), float(d.get("Duración (min)", 9) or 9), int(d.get("Repeticiones", 8) or 8), d.get("Ida y vuelta continua") == "Sí"
    else:
        def_t, def_l, def_a, def_j, def_dur, def_rep, def_ida = "Transición/Oleadas", 30.0, 15.0, 10, 9.0, 8, True

    tipo_val = st.selectbox("Ejercicio", list(FACTORES_EJERCICIO.keys()), index=list(FACTORES_EJERCICIO.keys()).index(def_t) if def_t in FACTORES_EJERCICIO else 0)
    
    col_d1, col_d2, col_d3 = st.columns(3)
    es_box = (tipo_val == "Box to Box")
    with col_d1: 
        jugadores_val = st.number_input("Jugadores", value=def_j)
        if es_box: largo_val = st.number_input("Distancia carrera (m)", value=def_l)
        else: largo_val = st.number_input("Largo (m)", value=def_l)
    with col_d2:
        if es_box: 
            repeticiones_val = st.number_input("Repeticiones", value=def_rep)
            ancho_val, duracion_val = 0, 0
        else:
            ancho_val = st.number_input("Ancho (m)", value=def_a)
            duracion_val = st.number_input("Duración (min)", value=def_dur)
            repeticiones_val = 0
    with col_d3:
        if not es_box: ida_vuelta_val = st.checkbox("Ida y vuelta continua", value=def_ida)
        else: ida_vuelta_val = False

    c_b1, c_b2 = st.columns(2)
    with c_b1:
        if st.button("➕ Calcular y Añadir", type="primary", use_container_width=True):
            res = calcular_carga(jugadores_val, duracion_val if not es_box else None, tipo_val, ida_vuelta_val, largo_val, ancho_val if not es_box else None, repeticiones_val if es_box else None, t_name)
            st.session_state.session_tasks.append(res)
            st.rerun()
    with c_b2:
        if st.button("⭐ Guardar en Librería", use_container_width=True):
            res = calcular_carga(jugadores_val, duracion_val if not es_box else None, tipo_val, ida_vuelta_val, largo_val, ancho_val if not es_box else None, repeticiones_val if es_box else None, t_name)
            idx = next((i for i, t in enumerate(st.session_state.task_library) if t["Nombre tarea"] == t_name), None)
            if idx is not None: st.session_state.task_library[idx] = res
            else: st.session_state.task_library.append(res)
            with open(ARCHIVO_LIBRERIA, "w", encoding="utf-8") as f: json.dump(st.session_state.task_library, f, ensure_ascii=False, indent=2)
            st.success("Guardado en librería.")

    st.divider()
    if st.session_state.session_tasks:
        st.header("3. Gestor de Tareas de Sesión")
        df_edit = pd.DataFrame(st.session_state.session_tasks)
        idx_edit = st.selectbox("Selecciona tarea para gestionar:", range(len(df_edit)), format_func=lambda x: f"{x+1}. {df_edit.iloc[x]['Nombre tarea']} ({df_edit.iloc[x]['Ejercicio']})")
        ce1, ce2 = st.columns(2)
        with ce1:
            if st.button("🗑️ Eliminar seleccionada", use_container_width=True):
                st.session_state.session_tasks.pop(idx_edit)
                st.rerun()
        with ce2:
            if st.button("🚨 Reiniciar sesión (Borrar todas)", type="secondary", use_container_width=True):
                st.session_state.session_tasks = []
                st.rerun()

# ------------------------------------------------------------
# TAB 2: SESIÓN ACTUAL
# ------------------------------------------------------------
with tabs[1]:
    st.markdown(session_cards_html(), unsafe_allow_html=True)
    data, resumen = obtener_resumen_sesion()
    
    if data is not None:
        st.subheader("Descargas")
        cd1, cd2, cd3 = st.columns(3)
        with cd1:
            csv_data = data.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Exportar CSV", csv_data, "tareas.csv", "text/csv", use_container_width=True)
        with cd2:
            buf_ex = io.BytesIO()
            with pd.ExcelWriter(buf_ex, engine='openpyxl') as writer:
                data.to_excel(writer, sheet_name="Tareas", index=False)
                resumen.to_excel(writer, sheet_name="Resumen", index=False)
            st.download_button("📊 Exportar Excel", buf_ex.getvalue(), "sesion.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with cd3:
            pdf_bytes = generar_pdf_bytes(sess_name, day_val, week_val, meso_name)
            if pdf_bytes: st.download_button("📄 Exportar PDF", pdf_bytes, "informe.pdf", "application/pdf", use_container_width=True)

        st.subheader("Tablas")
        st.dataframe(data, use_container_width=True)
        st.dataframe(resumen, use_container_width=True)

        st.subheader("Gráficas")
        cg1, cg2 = st.columns(2)
        with cg1: st.pyplot(make_fig_resumen_global())
        with cg2: st.pyplot(make_fig_carga())
        
        cg3, cg4 = st.columns(2)
        with cg3: st.pyplot(make_fig_hsr_sprint())
        with cg4: st.pyplot(make_fig_acc_dec())

        st.markdown("#### Aporte porcentual")
        cp1, cp2 = st.columns(2)
        with cp1: st.pyplot(make_fig_aporte_porcentual("Distancia total (m)", "Distancia total"))
        with cp2: st.pyplot(make_fig_aporte_porcentual("HSR total (m)", "HSR"))
    else:
        st.info("Añade tareas en la Calculadora para ver la sesión.")

# ------------------------------------------------------------
# TAB 3: LIBRERÍA
# ------------------------------------------------------------
with tabs[2]:
    st.header("Librería de Tareas Guardadas")
    if st.session_state.task_library:
        df_lib = pd.DataFrame(st.session_state.task_library)[["Nombre tarea", "Ejercicio", "Distancia total (m)", "HSR total (m)", "Distancia sprint total (m)", "Nº sprints totales", "ACC total (n)", "DEC total (n)"]]
        st.dataframe(df_lib, use_container_width=True)
        
        sel_del = st.selectbox("Eliminar tarea de la librería:", [t["Nombre tarea"] for t in st.session_state.task_library])
        if st.button("Eliminar de librería", type="primary"):
            st.session_state.task_library = [t for t in st.session_state.task_library if t["Nombre tarea"] != sel_del]
            with open(ARCHIVO_LIBRERIA, "w", encoding="utf-8") as f: json.dump(st.session_state.task_library, f, ensure_ascii=False, indent=2)
            st.rerun()

        json_lib = json.dumps(st.session_state.task_library, ensure_ascii=False, indent=2).encode('utf-8')
        st.download_button("Exportar Librería JSON", json_lib, f"libreria_{USUARIO_ACTUAL}.json", "application/json")
    else:
        st.info("La librería está vacía.")

# ------------------------------------------------------------
# TAB 4: MICROCICLO
# ------------------------------------------------------------
with tabs[3]:
    st.header("Ajuste de la sesión al microciclo")
    if data is not None:
        analysis_df = build_current_session_microcycle_table(resumen.iloc[0], day_val)
        st.markdown(f"**Día seleccionado:** {day_val}")
        st.markdown(build_day_status_summary_html(analysis_df), unsafe_allow_html=True)
        st.markdown(build_progress_bars(resumen.iloc[0], day_val), unsafe_allow_html=True)
        
        st.dataframe(analysis_df.style.apply(lambda row: [state_color(row["Estado"]) for _ in row], axis=1), use_container_width=True)
        
        propuestas = generar_propuesta_ajuste(resumen.iloc[0], day_val)
        html_props = "".join([f"<li>{p}</li>" for p in propuestas])
        st.markdown(f'<div style="margin-top:12px;padding:14px;border:1px solid #e5e7eb;border-radius:14px;background:#fafafa;"><strong>Propuesta automática de ajuste</strong><ul style="margin:8px 0 0 18px;">{html_props}</ul></div>', unsafe_allow_html=True)
    else:
        st.info("Añade tareas para analizar el microciclo.")

# ------------------------------------------------------------
# TAB 5: ANÁLISIS
# ------------------------------------------------------------
with tabs[4]:
    st.header("Análisis de Calidad y Tendencias")
    wk = weekly_analytics_dataframe()
    if wk is not None and not wk.empty:
        st.subheader("Evolución por semanas y Medias Móviles")
        st.dataframe(wk.style.apply(lambda row: [state_color(row.get("Estado semanal","")) for _ in row], axis=1), use_container_width=True)
        
        st.subheader("Tendencias Automáticas")
        textos = [
            f"Distancia total: {automatic_trend(wk['Distancia total sesión (m)'])}",
            f"HSR: {automatic_trend(wk['HSR total sesión (m)'])}",
            f"Sprint: {automatic_trend(wk['Distancia sprint total sesión (m)'])}",
            f"ACC: {automatic_trend(wk['ACC total sesión (n)'])}",
            f"DEC: {automatic_trend(wk['DEC total sesión (n)'])}",
            f"Carga total: {automatic_trend(wk['Carga total sesión (m)'])}",
        ]
        st.markdown("<div style='padding:14px;border:1px solid #e5e7eb;border-radius:14px;background:#fff;'><ul>" + "".join([f"<li>{t}</li>" for t in textos]) + "</ul></div>", unsafe_allow_html=True)

        fig, ax = plt.subplots(figsize=(11, 4))
        ax.plot(wk["Semana"], wk["Distancia total sesión (m)"], marker="o", label="Semanal")
        if "MM3 Distancia total sesión (m)" in wk.columns:
            ax.plot(wk["Semana"], wk["MM3 Distancia total sesión (m)"], marker="o", label="Media móvil 3")
        ax.set_title("Distancia total semanal y media móvil")
        ax.set_xlabel("Semana")
        ax.legend()
        ax.grid(alpha=0.3)
        st.pyplot(fig)
    else:
        st.info("Guarda varias semanas en el histórico para ver tendencias.")

# ------------------------------------------------------------
# TAB 6: HISTÓRICO
# ------------------------------------------------------------
with tabs[5]:
    st.header("Histórico de Sesiones")
    hist_df = get_history_dataframe()
    if hist_df is not None:
        st.dataframe(hist_df, use_container_width=True)
        
        json_hist = json.dumps(st.session_state.saved_sessions, ensure_ascii=False, indent=2).encode('utf-8')
        st.download_button("📥 Exportar Backup Completo (JSON)", json_hist, f"historico_{USUARIO_ACTUAL}.json", "application/json")
        
        with st.expander("⚠️ Zona de peligro"):
            if st.button("🚨 Borrar todo el histórico"):
                st.session_state.saved_sessions = []
                with open(ARCHIVO_HISTORICO, "w", encoding="utf-8") as f: json.dump([], f)
                st.rerun()
    else:
        st.info("No hay sesiones guardadas.")

# ------------------------------------------------------------
# TAB 7: COMPARACIÓN
# ------------------------------------------------------------
with tabs[6]:
    st.header("Comparación A/B")
    if st.session_state.saved_sessions and len(st.session_state.saved_sessions) > 1:
        nombres = [s["session_name"] for s in st.session_state.saved_sessions]
        ca, cb = st.columns(2)
        with ca: sel_a = st.selectbox("Sesión A", nombres, index=0)
        with cb: sel_b = st.selectbox("Sesión B", nombres, index=1)
        
        df_comp = compare_saved_sessions(sel_a, sel_b)
        if df_comp is not None: 
            st.dataframe(df_comp, use_container_width=True)
            
            metrics = ["Distancia total sesión (m)", "HSR total sesión (m)", "Distancia sprint total sesión (m)", "ACC total sesión (n)", "DEC total sesión (n)", "Carga total sesión (m)"]
            sess_a = next(s for s in st.session_state.saved_sessions if s["session_name"] == sel_a)
            sess_b = next(s for s in st.session_state.saved_sessions if s["session_name"] == sel_b)
            a_vals = [float(sess_a["summary"].get(m, 0)) for m in metrics]
            b_vals = [float(sess_b["summary"].get(m, 0)) for m in metrics]
            
            x = list(range(len(metrics)))
            width = 0.38
            fig, ax = plt.subplots(figsize=(12.5, 5.8))
            ax.bar([i - width/2 for i in x], a_vals, width=width, label=sel_a)
            ax.bar([i + width/2 for i in x], b_vals, width=width, label=sel_b)
            ax.set_title("Comparación visual de métricas entre sesiones", fontsize=15, fontweight="bold")
            ax.set_xticks(x)
            ax.set_xticklabels(["Distancia total", "HSR", "Sprint", "ACC", "DEC", "Carga total"], rotation=20, ha="right")
            ax.grid(axis="y", linestyle="--", alpha=0.3)
            ax.legend()
            st.pyplot(fig)
    else:
        st.info("Necesitas al menos 2 sesiones guardadas para comparar.")

# ------------------------------------------------------------
# TAB 8: MESOCICLO (PLANIFICACIÓN AVANZADA)
# ------------------------------------------------------------
with tabs[7]:
    st.header("Planificación y Carga Neuromuscular")
    matrix_df = mesocycle_matrix_dataframe()
    if matrix_df is not None:
        st.subheader("Matriz del Mesociclo")
        st.dataframe(matrix_df, use_container_width=True)

        st.subheader("Alertas Neuromusculares Consecutivas")
        alerts = detect_consecutive_neuromuscular_alerts()
        if alerts:
            st.markdown("<div style='padding:14px;border:1px solid #fca5a5;border-radius:14px;background:#fef2f2;'><ul>" + "".join([f"<li>{a}</li>" for a in alerts]) + "</ul></div>", unsafe_allow_html=True)
        else:
            st.success("No se han detectado alertas de carga neuromuscular consecutiva excesiva.")

        st.subheader("Duplicador Rápido")
        dup_sel = st.selectbox("Elegir sesión para duplicar y cargar al editor actual:", [s["session_name"] for s in st.session_state.saved_sessions])
        if st.button("Duplicar sesión completa"):
            sess = next(s for s in st.session_state.saved_sessions if s["session_name"] == dup_sel)
            st.session_state.session_tasks = copy.deepcopy(sess["tasks"])
            st.success(f"Sesión '{dup_sel}' cargada en la calculadora. Ve a la primera pestaña.")
    else:
        st.info("Guarda sesiones en el histórico para ver la matriz.")

# ------------------------------------------------------------
# TAB 9: JUSTIFICACIÓN
# ------------------------------------------------------------
with tabs[8]:
    JUSTIFICACION_HTML = """<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:18px;padding:22px;line-height:1.65;">
<h2 style="margin-top:0;color:#0f172a;">Justificación de la aplicación</h2>

<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px;margin:18px 0;">
    <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:14px;padding:16px;">
        <h3 style="margin-top:0;color:#1d4ed8;">1. ¿Para qué sirve?</h3>
        <p style="margin-bottom:0;">La aplicación traduce el diseño de la tarea a una estimación de carga externa útil para planificar sesiones, comparar ejercicios, acumular cargas y valorar si la sesión se ajusta al día del microciclo.</p>
    </div>
    <div style="background:#ecfeff;border:1px solid #a5f3fc;border-radius:14px;padding:16px;">
        <h3 style="margin-top:0;color:#0891b2;">2. ¿Qué calcula?</h3>
        <p style="margin-bottom:0;">Distancia total, HSR, distancia sprint, nº de sprints, aceleraciones y deceleraciones, además de su distribución por tarea dentro de la sesión.</p>
    </div>
    <div style="background:#faf5ff;border:1px solid #d8b4fe;border-radius:14px;padding:16px;">
        <h3 style="margin-top:0;color:#7e22ce;">3. ¿Cómo lo hace?</h3>
        <p style="margin-bottom:0;">Combina ecuaciones base dependientes del espacio por jugador con factores correctores específicos de cada ejercicio y ajustes de longitudinalidad, continuidad y suelos mínimos.</p>
    </div>
    <div style="background:#fff7ed;border:1px solid #fdba74;border-radius:14px;padding:16px;">
        <h3 style="margin-top:0;color:#ea580c;">4. ¿Cómo se interpreta?</h3>
        <p style="margin-bottom:0;">La sesión se compara con el partido como referencia del 100% y se valora si la exposición es adecuada según el momento del microciclo.</p>
    </div>
</div>

<h3 style="color:#0f172a;">1) Base del modelo: el espacio por jugador</h3>
<p>La variable estructural de partida es el <strong>ApP (área por jugador)</strong>, ya que resume la relación entre espacio disponible y número de participantes. A partir de este valor se estiman las principales métricas locomotoras y mecánicas del ejercicio.</p>

<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:16px;margin-bottom:16px;">
    <strong>Fórmula base</strong>
    <div style="margin-top:10px;font-family:monospace;font-size:16px;background:#ffffff;padding:12px;border-radius:10px;border:1px solid #e2e8f0;">
        ApP = (largo × ancho) / nº jugadores
    </div>
</div>

<h3 style="color:#0f172a;">2) Fórmulas de cálculo por métrica</h3>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px;margin:16px 0;">
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:16px;">
        <strong>Distancia total por minuto</strong>
        <div style="margin-top:8px;font-family:monospace;font-size:15px;background:#ffffff;padding:10px;border-radius:10px;border:1px solid #e2e8f0;">DT/min = 19.243 × ln(ApP) − 5.029</div>
    </div>
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:16px;">
        <strong>Distancia sprint por minuto</strong>
        <div style="margin-top:8px;font-family:monospace;font-size:15px;background:#ffffff;padding:10px;border-radius:10px;border:1px solid #e2e8f0;">Sprint/min = 0.001 × ApP − 0.046</div>
    </div>
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:16px;">
        <strong>Distancia en aceleración por minuto</strong>
        <div style="margin-top:8px;font-family:monospace;font-size:15px;background:#ffffff;padding:10px;border-radius:10px;border:1px solid #e2e8f0;">Dist ACC/min = 1.321 × ln(ApP) − 0.629</div>
    </div>
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:16px;">
        <strong>Nº aceleraciones por minuto</strong>
        <div style="margin-top:8px;font-family:monospace;font-size:15px;background:#ffffff;padding:10px;border-radius:10px;border:1px solid #e2e8f0;">ACC/min = 0.212 × ln(ApP) − 0.23</div>
    </div>
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:16px;">
        <strong>Distancia en deceleración por minuto</strong>
        <div style="margin-top:8px;font-family:monospace;font-size:15px;background:#ffffff;padding:10px;border-radius:10px;border:1px solid #e2e8f0;">Dist DEC/min = 1.157 × ln(ApP) − 0.418</div>
    </div>
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:16px;">
        <strong>Nº deceleraciones por minuto</strong>
        <div style="margin-top:8px;font-family:monospace;font-size:15px;background:#ffffff;padding:10px;border-radius:10px;border:1px solid #e2e8f0;">DEC/min = 0.104 × ln(ApP) − 0.096</div>
    </div>
</div>

<h3 style="color:#0f172a;">3) Referencia real de partido empleada</h3>
<p>Para contextualizar mejor los análisis, la aplicación toma como referencia la media de los últimos 10 partidos de un equipo de <strong>2ª RFEF</strong>. Estos valores se usan como base para comparar la sesión con el partido y para estimar con mayor realismo la longitud media del sprint.</p>

<div style="overflow-x:auto;margin-bottom:18px;">
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
        <thead>
            <tr style="background:#0f172a;color:#ffffff;">
                <th style="padding:10px;border:1px solid #cbd5e1;">Variable</th>
                <th style="padding:10px;border:1px solid #cbd5e1;">Promedio</th>
            </tr>
        </thead>
        <tbody>
            <tr><td style="padding:9px;border:1px solid #e2e8f0;">Distancia total</td><td style="padding:9px;border:1px solid #e2e8f0;">11039,7 m</td></tr>
            <tr style="background:#f8fafc;"><td style="padding:9px;border:1px solid #e2e8f0;">Nº sprints</td><td style="padding:9px;border:1px solid #e2e8f0;">11,08</td></tr>
            <tr><td style="padding:9px;border:1px solid #e2e8f0;">Distancia sprint</td><td style="padding:9px;border:1px solid #e2e8f0;">185,93 m</td></tr>
            <tr style="background:#f8fafc;"><td style="padding:9px;border:1px solid #e2e8f0;">HSR</td><td style="padding:9px;border:1px solid #e2e8f0;">567,23 m</td></tr>
            <tr><td style="padding:9px;border:1px solid #e2e8f0;">ACC</td><td style="padding:9px;border:1px solid #e2e8f0;">128,54</td></tr>
            <tr style="background:#f8fafc;"><td style="padding:9px;border:1px solid #e2e8f0;">DEC</td><td style="padding:9px;border:1px solid #e2e8f0;">120,17</td></tr>
        </tbody>
    </table>
</div>

<h3 style="color:#0f172a;">4) Explicación del HSR</h3>
<p>El <strong>HSR</strong> no se estima con una única ecuación lineal, sino mediante un modelo práctico por tramos en función del ApP, corregido después por el tipo de ejercicio y por la estructura espacial y temporal de la tarea. Esto permite representar mejor que no todas las tareas con el mismo espacio generan la misma exposición a alta velocidad.</p>

<div style="display:flex;flex-wrap:wrap;gap:10px;margin-bottom:16px;">
    <div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:12px;padding:10px 14px;"><strong>ApP &lt; 100</strong> → HSR base = 0.5</div>
    <div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:12px;padding:10px 14px;"><strong>100–149.99</strong> → HSR base = 2.0</div>
    <div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:12px;padding:10px 14px;"><strong>150–181.99</strong> → HSR base = 4.0</div>
    <div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:12px;padding:10px 14px;"><strong>182–224.99</strong> → HSR base = 6.0</div>
    <div style="background:#eef2ff;border:1px solid #c7d2fe;border-radius:12px;padding:10px 14px;"><strong>≥ 225</strong> → HSR base = 8.0</div>
</div>

<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:14px;margin-bottom:18px;">
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:16px;">
        <strong>HSR corregido por minuto</strong>
        <div style="margin-top:8px;font-family:monospace;font-size:15px;background:#ffffff;padding:10px;border-radius:10px;border:1px solid #e2e8f0;">HSR/min = max(HSR_base × factor_hsr × factor_long × factor_cont, suelo_hsr)</div>
    </div>
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:16px;">
        <strong>Sprint corregido por minuto</strong>
        <div style="margin-top:8px;font-family:monospace;font-size:15px;background:#ffffff;padding:10px;border-radius:10px;border:1px solid #e2e8f0;">Sprint/min = max(Sprint_base × factor_sprint × factor_long × factor_cont, suelo_sprint)</div>
    </div>
</div>

<h3 style="color:#0f172a;">5) Factores de corrección por tipo de ejercicio</h3>
<p>Cada tipo de tarea aplica factores específicos sobre HSR, sprint, aceleraciones y deceleraciones. Estos factores permiten ajustar la estimación a la naturaleza del ejercicio. Por ejemplo, las transiciones y oleadas multiplican especialmente HSR y sprint, mientras que rondos o juegos de posición concentran más acciones mecánicas cortas.</p>

<div style="overflow-x:auto;margin-bottom:18px;">
    <table style="width:100%;border-collapse:collapse;font-size:14px;text-align:center;">
        <thead>
            <tr style="background:#0f172a;color:#ffffff;">
                <th style="padding:10px;border:1px solid #cbd5e1;">Ejercicio</th>
                <th style="padding:10px;border:1px solid #cbd5e1;">Factor HSR</th>
                <th style="padding:10px;border:1px solid #cbd5e1;">Factor Sprint</th>
                <th style="padding:10px;border:1px solid #cbd5e1;">Factor ACC</th>
                <th style="padding:10px;border:1px solid #cbd5e1;">Factor DEC</th>
            </tr>
        </thead>
        <tbody>
            <tr><td style="padding:9px;border:1px solid #e2e8f0;">Juego de posición</td><td style="padding:9px;border:1px solid #e2e8f0;">0.55</td><td style="padding:9px;border:1px solid #e2e8f0;">0.50</td><td style="padding:9px;border:1px solid #e2e8f0;">0.80</td><td style="padding:9px;border:1px solid #e2e8f0;">0.80</td></tr>
            <tr style="background:#f8fafc;"><td style="padding:9px;border:1px solid #e2e8f0;">Rondo</td><td style="padding:9px;border:1px solid #e2e8f0;">0.50</td><td style="padding:9px;border:1px solid #e2e8f0;">0.45</td><td style="padding:9px;border:1px solid #e2e8f0;">1.00</td><td style="padding:9px;border:1px solid #e2e8f0;">1.00</td></tr>
            <tr><td style="padding:9px;border:1px solid #e2e8f0;">Posesión</td><td style="padding:9px;border:1px solid #e2e8f0;">0.85</td><td style="padding:9px;border:1px solid #e2e8f0;">0.80</td><td style="padding:9px;border:1px solid #e2e8f0;">1.05</td><td style="padding:9px;border:1px solid #e2e8f0;">1.05</td></tr>
            <tr style="background:#f8fafc;"><td style="padding:9px;border:1px solid #e2e8f0;">Transición/Oleadas</td><td style="padding:9px;border:1px solid #e2e8f0;">2.80</td><td style="padding:9px;border:1px solid #e2e8f0;">3.20</td><td style="padding:9px;border:1px solid #e2e8f0;">1.15</td><td style="padding:9px;border:1px solid #e2e8f0;">1.15</td></tr>
            <tr><td style="padding:9px;border:1px solid #e2e8f0;">Box to Box</td><td style="padding:9px;border:1px solid #e2e8f0;">1.00</td><td style="padding:9px;border:1px solid #e2e8f0;">1.00</td><td style="padding:9px;border:1px solid #e2e8f0;">1.00</td><td style="padding:9px;border:1px solid #e2e8f0;">1.00</td></tr>
            <tr style="background:#f8fafc;"><td style="padding:9px;border:1px solid #e2e8f0;">Partido condicionado</td><td style="padding:9px;border:1px solid #e2e8f0;">1.20</td><td style="padding:9px;border:1px solid #e2e8f0;">1.15</td><td style="padding:9px;border:1px solid #e2e8f0;">1.15</td><td style="padding:9px;border:1px solid #e2e8f0;">1.15</td></tr>
            <tr><td style="padding:9px;border:1px solid #e2e8f0;">Partido</td><td style="padding:9px;border:1px solid #e2e8f0;">0.70</td><td style="padding:9px;border:1px solid #e2e8f0;">6.15</td><td style="padding:9px;border:1px solid #e2e8f0;">0.95</td><td style="padding:9px;border:1px solid #e2e8f0;">0.95</td></tr>
            <tr style="background:#f8fafc;"><td style="padding:9px;border:1px solid #e2e8f0;">Otro</td><td style="padding:9px;border:1px solid #e2e8f0;">1.00</td><td style="padding:9px;border:1px solid #e2e8f0;">1.00</td><td style="padding:9px;border:1px solid #e2e8f0;">1.00</td><td style="padding:9px;border:1px solid #e2e8f0;">1.00</td></tr>
        </tbody>
    </table>
</div>

<h3 style="color:#0f172a;">6) Factores estructurales adicionales</h3>
<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin:16px 0;">
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:16px;">
        <strong>Factor longitudinal</strong>
        <p style="margin:8px 0 0 0;">Corrige tareas largas y estrechas, especialmente en transición, partido y partido condicionado, porque favorecen más metros útiles de carrera y mayor probabilidad de HSR/sprint.</p>
    </div>
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:16px;">
        <strong>Factor continuidad</strong>
        <p style="margin:8px 0 0 0;">Aumenta la estimación cuando la tarea tiene una lógica continua de ida y vuelta, especialmente en transiciones/oleadas.</p>
    </div>
    <div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:16px;">
        <strong>Suelos mínimos</strong>
        <p style="margin:8px 0 0 0;">En algunas tareas de transición se aplica un suelo mínimo de HSR y sprint por minuto para evitar infraestimar esfuerzos que en la práctica siempre aparecen.</p>
    </div>
</div>

<h3 style="color:#0f172a;">7) Box to Box</h3>
<p>El ejercicio box to box sigue una lógica específica distinta al resto del modelo: parte de la distancia de carrera y del número de repeticiones, y aplica proporciones diferentes para estimar HSR, sprint y acciones ACC/DEC según la longitud del esfuerzo.</p>
<div style="background:#f8fafc;border:1px solid #e2e8f0;border-radius:14px;padding:16px;margin-bottom:18px;">
    <div style="font-family:monospace;font-size:15px;background:#ffffff;padding:10px;border-radius:10px;border:1px solid #e2e8f0;">Distancia total = distancia_carrera × repeticiones</div>
</div>

<h3 style="color:#0f172a;">8) Integración en el microciclo</h3>
<p>La calculadora permite valorar si la carga total de la sesión es coherente con el día del microciclo en el que se ubica. De esta forma, no solo estima carga por tarea, sino que también permite interpretar si el contenido de la sesión está alineado con las exigencias esperadas de MD+1, MD-4, MD-3, MD-2 o MD-1.</p>
</div>"""
    st.markdown(JUSTIFICACION_HTML, unsafe_allow_html=True)