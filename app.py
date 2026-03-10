# ============================================================
# CALCULADORA AVANZADA DE CARGAS EN FÚTBOL
# Streamlit App - Versión Funcional Original
# ============================================================

import os
import math
import json
import copy
import io
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import streamlit as st

# ============================================================
# CONFIGURACIÓN DE STREAMLIT
# ============================================================
st.set_page_config(page_title="Calculadora Cargas Fútbol", layout="wide", page_icon="⚽")
plt.rcParams["figure.figsize"] = (10, 4)

# ============================================================
# INICIALIZACIÓN DE MEMORIA Y ARCHIVOS
# ============================================================
if 'session_tasks' not in st.session_state:
    st.session_state.session_tasks = []

if 'saved_sessions' not in st.session_state:
    if os.path.exists("historico_sesiones.json"):
        with open("historico_sesiones.json", "r", encoding="utf-8") as f:
            st.session_state.saved_sessions = json.load(f)
    else:
        st.session_state.saved_sessions = []

if 'custom_task_library' not in st.session_state:
    if os.path.exists("libreria_tareas.json"):
        with open("libreria_tareas.json", "r", encoding="utf-8") as f:
            st.session_state.custom_task_library = json.load(f)
    else:
        st.session_state.custom_task_library = {}

# ============================================================
# DICCIONARIOS Y CONSTANTES
# ============================================================

FACTORES_EJERCICIO = {
    "Figura de pases":      {"hsr": 0.40, "sprint": 0.35, "acc": 0.60, "dec": 0.60},
    "Juego de posición":    {"hsr": 0.55, "sprint": 0.50, "acc": 0.80, "dec": 0.80},
    "Rondo":                {"hsr": 0.50, "sprint": 0.45, "acc": 1.00, "dec": 1.00},
    "Posesión":             {"hsr": 0.85, "sprint": 0.80, "acc": 1.05, "dec": 1.05},
    "Transición/Oleadas":   {"hsr": 2.80, "sprint": 3.20, "acc": 1.15, "dec": 1.15},
    "Box to Box":           {"hsr": 1.00, "sprint": 1.00, "acc": 1.00, "dec": 1.00},
    "Tarea analítica":      {"hsr": 1.20, "sprint": 1.10, "acc": 1.00, "dec": 1.00},
    "Partido condicionado": {"hsr": 1.20, "sprint": 1.15, "acc": 1.15, "dec": 1.15},
    "Partido":              {"hsr": 0.70, "sprint": 6.15, "acc": 0.95, "dec": 0.95},
    "Otro":                 {"hsr": 1.00, "sprint": 1.00, "acc": 1.00, "dec": 1.00},
}

SESSION_GOALS = {
    "Compensatoria": {"hsr": (0, 120), "sprint": (0, 40), "sprints": (0, 2), "acc": (0, 25), "dec": (0, 25), "distance": (500, 2500)},
    "MD-4": {"hsr": (250, 500), "sprint": (60, 140), "sprints": (3, 7), "acc": (25, 60), "dec": (25, 60), "distance": (2500, 5000)},
    "MD-3": {"hsr": (350, 700), "sprint": (100, 180), "sprints": (5, 9), "acc": (35, 75), "dec": (35, 75), "distance": (3500, 6500)},
    "MD-2": {"hsr": (120, 300), "sprint": (40, 100), "sprints": (2, 5), "acc": (20, 45), "dec": (20, 45), "distance": (1800, 4000)},
    "Activación / MD-1": {"hsr": (20, 120), "sprint": (0, 50), "sprints": (0, 3), "acc": (10, 30), "dec": (10, 30), "distance": (800, 2200)},
    "Personalizado": {"hsr": (0, 99999), "sprint": (0, 99999), "sprints": (0, 99999), "acc": (0, 99999), "dec": (0, 99999), "distance": (0, 99999)},
}

# ============================================================
# FUNCIONES MATEMÁTICAS
# ============================================================

def calcular_app(largo, ancho, jugadores):
    if largo <= 0 or ancho <= 0 or jugadores <= 0: return 1
    return (largo * ancho) / jugadores

def hsr_relativo(app):
    if app < 100: return 0.5
    elif app < 150: return 2.0
    elif app < 182: return 4.0
    elif app < 225: return 6.0
    else: return 8.0

def clasificar_carga(carga_total):
    if carga_total < 300: return "Baja", "🟢"
    elif carga_total < 700: return "Media", "🟡"
    else: return "Alta", "🔴"

def factor_longitudinal(largo, ancho, tipo):
    if ancho <= 0: return 1.0
    ratio = largo / ancho
    if tipo not in ["Transición/Oleadas", "Partido", "Partido condicionado"]: return 1.0
    if ratio < 1.3: return 1.00
    elif ratio < 1.7: return 1.20
    elif ratio < 2.2: return 1.45
    elif ratio < 3.0: return 1.70
    else: return 1.90

def factor_continuidad(ida_vuelta_continua, tipo):
    if not ida_vuelta_continua: return 1.0
    if tipo == "Transición/Oleadas": return 1.35
    return 1.10

def minimo_hsr_min(largo, tipo, ida_vuelta_continua):
    if tipo == "Transición/Oleadas":
        if largo >= 35: base = 6.5
        elif largo >= 30: base = 5.5
        elif largo >= 25: base = 4.5
        else: base = 3.0
        if ida_vuelta_continua: base *= 1.15
        return base
    return 0.0

def minimo_sprint_min(largo, tipo, ida_vuelta_continua):
    if tipo == "Transición/Oleadas":
        if largo >= 35: base = 1.00
        elif largo >= 30: base = 0.80
        elif largo >= 25: base = 0.60
        else: base = 0.35
        if ida_vuelta_continua: base *= 1.10
        return base
    return 0.0

def metricas_base_excel(app):
    app = max(app, 1)
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

def interpretacion_practica(carga_total, hsr_total, sprint_total, acc_total, dec_total, tipo):
    txt_carga = "baja" if carga_total < 300 else ("media" if carga_total < 700 else "alta")
    return f"En {tipo.lower()}, la carga global es {txt_carga}; HSR: {hsr_total:.1f}m, Sprint: {sprint_total:.1f}m."

# ============================================================
# CÁLCULOS Y SESIONES
# ============================================================

def calcular_carga(jugadores, duracion, tipo, modo_espacio, rpe_val, ida_vuelta_continua, m2, largo, ancho, repeticiones, nombre_tarea):
    srpe = rpe_val * duracion
    if tipo == "Box to Box":
        dist_total = largo * repeticiones
        hsr_total = dist_total * box_to_box_hsr_ratio(largo)
        sprint_total = dist_total * box_to_box_sprint_ratio(largo)
        acc_t, dec_t = box_to_box_acc_dec_totales(repeticiones, largo)
        clasif, sem = clasificar_carga(dist_total)
        return {
            "Nombre tarea": nombre_tarea or "Tarea", "Ejercicio": tipo, "RPE": rpe_val, "sRPE": round(srpe, 2),
            "Largo (m)": round(largo, 2), "Ancho (m)": None, "ApP (m²/jugador)": None, "Jugadores": int(jugadores),
            "Duración (min)": round(duracion, 2), "Repeticiones": int(repeticiones), "Ida y vuelta continua": "N/A",
            "Distancia total (m)": round(dist_total, 2), "HSR total (m)": round(hsr_total, 2), "Sprint total (m)": round(sprint_total, 2),
            "Sprints totales (n)": round(sprint_total/19.1, 2), "ACC total (n)": round(acc_t, 2), "DEC total (n)": round(dec_t, 2),
            "Carga total (m)": round(dist_total, 2), "Clasificación": clasif, "Semáforo": sem, 
            "Interpretación": interpretacion_practica(dist_total, hsr_total, sprint_total, acc_t, dec_t, tipo)
        }

    if modo_espacio == "m2":
        app = m2
        l_v, a_v, f_l, f_c, s_h, s_s = None, None, 1.0, 1.0, 0.0, 0.0
    else:
        app = calcular_app(largo, ancho, jugadores)
        l_v, a_v = largo, ancho
        f_l = factor_longitudinal(largo, ancho, tipo)
        f_c = factor_continuidad(ida_vuelta_continua, tipo)
        s_h = minimo_hsr_min(largo, tipo, ida_vuelta_continua)
        s_s = minimo_sprint_min(largo, tipo, ida_vuelta_continua)

    fact = FACTORES_EJERCICIO[tipo]
    dt, ds, dacc, nacc, ddec, ndec = metricas_base_excel(app)
    hsr_t = max(hsr_relativo(app) * fact["hsr"] * f_l * f_c, s_h) * duracion
    spr_t = max(ds * fact["sprint"] * f_l * f_c, s_s) * duracion
    ct = dt * duracion
    cl, sem = clasificar_carga(ct)
    return {
        "Nombre tarea": nombre_tarea or "Tarea", "Ejercicio": tipo, "RPE": rpe_val, "sRPE": round(srpe, 2),
        "Largo (m)": l_v, "Ancho (m)": a_v, "ApP (m²/jugador)": round(app, 2), "Jugadores": int(jugadores),
        "Duración (min)": round(duracion, 2), "Repeticiones": None, "Ida y vuelta continua": "Sí" if ida_vuelta_continua else "No",
        "Distancia total (m)": round(ct, 2), "HSR total (m)": round(hsr_t, 2), "Sprint total (m)": round(spr_t, 2),
        "Sprints totales (n)": round(spr_t/19.1, 2), "ACC total (n)": round(nacc*fact["acc"]*duracion, 2), "DEC total (n)": round(ndec*fact["dec"]*duracion, 2),
        "Carga total (m)": round(ct, 2), "Clasificación": cl, "Semáforo": sem, 
        "Interpretación": interpretacion_practica(ct, hsr_t, spr_t, 0, 0, tipo)
    }

def obtener_resumen_sesion():
    if not st.session_state.session_tasks: return None, None
    df = pd.DataFrame(st.session_state.session_tasks)
    res = pd.DataFrame([{
        "Número de tareas": len(df), "Duración total (min)": df["Duración (min)"].sum(),
        "sRPE total sesión": df["sRPE"].sum(), "Distancia total sesión (m)": df["Distancia total (m)"].sum(),
        "Sprint total sesión (m)": df["Sprint total (m)"].sum(), "Sprints totales sesión (n)": df["Sprints totales (n)"].sum(),
        "HSR total sesión (m)": df["HSR total (m)"].sum(), "ACC total sesión (n)": df["ACC total (n)"].sum(),
        "DEC total sesión (n)": df["DEC total (n)"].sum(), "Carga total sesión (m)": df["Carga total (m)"].sum()
    }])
    return df, res

def save_session_to_history(name, goal):
    data, resumen = obtener_resumen_sesion()
    if data is None: return False
    payload = {"session_name": name, "goal": goal, "tasks": data.to_dict("records"), "summary": resumen.iloc[0].to_dict()}
    st.session_state.saved_sessions.append(payload)
    with open("historico_sesiones.json", "w", encoding="utf-8") as f: json.dump(st.session_state.saved_sessions, f, indent=2)
    return True

# ============================================================
# INTERFAZ VISUAL (TARJETAS)
# ============================================================

def session_cards_html():
    data, resumen = obtener_resumen_sesion()
    if data is None: return "<div>No hay tareas.</div>"
    vals = {
        "sRPE Total": resumen["sRPE total sesión"].iloc[0],
        "Distancia (m)": resumen["Distancia total sesión (m)"].iloc[0],
        "HSR (m)": resumen["HSR total sesión (m)"].iloc[0],
        "Sprint (m)": resumen["Sprint total sesión (m)"].iloc[0],
        "ACC (n)": resumen["ACC total sesión (n)"].iloc[0],
        "DEC (n)": resumen["DEC total sesión (n)"].iloc[0],
    }
    cards = ""
    for k, v in vals.items():
        cards += f'<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:12px;padding:12px;min-width:130px;box-shadow:0 2px 5px rgba(0,0,0,0.05);margin:5px;"><div style="font-size:12px;color:#64748b;">{k}</div><div style="font-size:20px;font-weight:700;">{float(v):.1f}</div></div>'
    return f'<div style="display:flex;flex-wrap:wrap;">{cards}</div>'

# ============================================================
# GRÁFICOS
# ============================================================

def generar_grafico(tipo):
    if not st.session_state.session_tasks: return None
    df = pd.DataFrame(st.session_state.session_tasks)
    fig, ax = plt.subplots()
    if tipo == "carga":
        ax.bar(df["Nombre tarea"], df["Distancia total (m)"])
        ax.set_title("Distancia por Tarea")
    elif tipo == "hsr":
        ax.bar(df["Nombre tarea"], df["HSR total (m)"], color="green")
        ax.set_title("HSR por Tarea")
    plt.xticks(rotation=45)
    return fig

# ============================================================
# ESTRUCTURA DE PESTAÑAS
# ============================================================

st.title("⚽ Calculadora de Cargas en Fútbol")

t1, t2, t3, t4 = st.tabs(["Calculadora", "Sesión", "Histórico", "Info"])

with t1:
    col_a, col_b = st.columns(2)
    with col_a:
        s_name = st.text_input("Sesión", "Sesión 1")
        t_name = st.text_input("Nombre Tarea", "Tarea 1")
        ejer = st.selectbox("Ejercicio", list(FACTORES_EJERCICIO.keys()))
    with col_b:
        rpe = st.slider("RPE", 1, 10, 5)
        jug = st.number_input("Jugadores", 1, 30, 10)
        dur = st.number_input("Duración", 1.0, 120.0, 10.0)
    
    modo = st.radio("Espacio", ["Largo x Ancho", "m2/jugador"])
    c1, c2 = st.columns(2)
    if modo == "Largo x Ancho":
        with c1: lar = st.number_input("Largo", 1.0, 120.0, 30.0)
        with c2: anc = st.number_input("Ancho", 1.0, 120.0, 20.0)
        m2_val = 0
    else:
        m2_val = st.number_input("m2", 1.0, 500.0, 120.0)
        lar = anc = 0
    
    if st.button("Añadir Tarea"):
        res = calcular_carga(jug, dur, ejer, "m2" if modo=="m2" else "campo", rpe, False, m2_val, lar, anc, 8, t_name)
        st.session_state.session_tasks.append(res)
        st.success("Añadida!")

with t2:
    data, resumen = obtener_resumen_sesion()
    if data is not None:
        st.markdown(session_cards_html(), unsafe_allow_html=True)
        st.dataframe(data)
        st.pyplot(generar_grafico("carga"))
        if st.button("Guardar Sesión"):
            save_session_to_history(s_name, "General")
            st.success("Guardada en histórico")
    else:
        st.write("Sin datos.")

with t3:
    if st.session_state.saved_sessions:
        h_df = pd.DataFrame([{"Sesión": s["session_name"], **s["summary"]} for s in st.session_state.saved_sessions])
        st.dataframe(h_df)
    else:
        st.write("No hay sesiones.")

with t4:
    st.write("Calculadora basada en modelos de área por jugador.")