# ============================================================
# CALCULADORA AVANZADA DE CARGAS EN FÚTBOL - STREAMLIT
# ============================================================

import streamlit as st
import math
import json
import copy
import textwrap
from datetime import datetime
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import io

# ============================================================
# CONFIGURACIÓN DE PÁGINA Y AUTENTICACIÓN
# ============================================================
st.set_page_config(page_title="Calculadora de Cargas", layout="wide")

USUARIO_CORRECTO = "admin"
PASS_CORRECTA = "1234"

if "authenticated" not in st.session_state:
    st.session_state["authenticated"] = False

if not st.session_state["authenticated"]:
    st.title("🔐 Inicio de Sesión")
    st.markdown("Por favor, introduce tus credenciales para acceder a la calculadora.")
    
    with st.form("login_form"):
        user = st.text_input("Usuario")
        pwd = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Entrar")
        
        if submit:
            if user == USUARIO_CORRECTO and pwd == PASS_CORRECTA:
                st.session_state["authenticated"] = True
                st.rerun()
            else:
                st.error("Usuario o contraseña incorrectos")
    st.stop() # Detiene la ejecución aquí si no está autenticado

# ============================================================
# ESTADO GLOBAL (SESSION STATE)
# ============================================================
if "session_tasks" not in st.session_state: st.session_state.session_tasks = []
if "last_result" not in st.session_state: st.session_state.last_result = None
if "saved_sessions" not in st.session_state: st.session_state.saved_sessions = []
if "task_library" not in st.session_state: st.session_state.task_library = []

# ============================================================
# CONSTANTES Y REFERENCIAS
# ============================================================
MATCH_REFERENCE_2RFEF = {
    "distance": 11039.7, "sprints": 11.0839, "sprint_distance": 185.9381,
    "hsr": 567.2347, "acc": 128.5459, "dec": 120.173,
}

AVG_SPRINT_LENGTH_MATCH = (
    MATCH_REFERENCE_2RFEF["sprint_distance"] / MATCH_REFERENCE_2RFEF["sprints"]
    if MATCH_REFERENCE_2RFEF["sprints"] > 0 else 16.8
)

DEFAULT_MATCH_REFERENCE = MATCH_REFERENCE_2RFEF.copy()

DAY_ORDER = {"MD+1": 1, "MD-4": 2, "MD-3": 3, "MD-2": 4, "MD-1": 5, "Partido": 6}

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

MICROCYCLE_DAY_RANGES = {
    "MD+1": {"distance": (60, 70), "hsr": (80, 90), "sprint_distance": (70, 80), "acc": (60, 80), "dec": (60, 80)},
    "MD-4": {"distance": (50, 60), "hsr": (10, 20), "sprint_distance": (5, 10), "acc": (75, 85), "dec": (75, 85)},
    "MD-3": {"distance": (65, 75), "hsr": (65, 80), "sprint_distance": (65, 75), "acc": (40, 50), "dec": (40, 50)},
    "MD-2": {"distance": (35, 45), "hsr": (10, 15), "sprint_distance": (5, 15), "acc": (20, 30), "dec": (20, 30)},
    "MD-1": {"distance": (20, 30), "hsr": (5, 10), "sprint_distance": (0, 5), "acc": (10, 20), "dec": (10, 20)},
    "Partido": {"distance": (100, 100), "hsr": (100, 100), "sprint_distance": (100, 100), "acc": (100, 100), "dec": (100, 100)},
}

WEEKLY_TOTAL_RANGES = {
    "Titular": {"distance": (170, 210), "hsr": (90, 125), "sprint_distance": (75, 105), "acc": (145, 185), "dec": (145, 185)},
    "Suplente": {"distance": (230, 280), "hsr": (160, 210), "sprint_distance": (145, 185), "acc": (205, 265), "dec": (205, 265)},
}

# ============================================================
# FUNCIONES MATEMÁTICAS Y DE LÓGICA (Simplificadas para espacio)
# ============================================================
def calcular_app(largo, ancho, jugadores): return (largo * ancho) / jugadores if jugadores > 0 else 0

def hsr_relativo(app):
    if app < 100: return 0.5
    if app < 150: return 2.0
    if app < 182: return 4.0
    if app < 225: return 6.0
    return 8.0

def clasificar_carga(carga_total):
    if carga_total < 300: return "Baja", "🟢"
    if carga_total < 700: return "Media", "🟡"
    return "Alta", "🔴"

def metricas_base_excel(app):
    if app <= 0: return 0,0,0,0,0,0
    dt = max(19.243 * math.log(app) - 5.029, 0)
    d_sprint = max(0.001 * app - 0.046, 0)
    d_acc = max(1.321 * math.log(app) - 0.629, 0)
    acc = max(0.212 * math.log(app) - 0.23, 0)
    d_dec = max(1.157 * math.log(app) - 0.418, 0)
    dec = max(0.104 * math.log(app) - 0.096, 0)
    return dt, d_sprint, d_acc, acc, d_dec, dec

def factor_longitudinal(largo, ancho, tipo):
    if ancho <= 0 or tipo not in ["Transición/Oleadas", "Partido", "Partido condicionado"]: return 1.0
    ratio = largo / ancho
    if ratio < 1.3: return 1.00
    if ratio < 1.7: return 1.20
    if ratio < 2.2: return 1.45
    if ratio < 3.0: return 1.70
    return 1.90

def factor_continuidad(ida_vuelta_continua, tipo):
    if not ida_vuelta_continua: return 1.0
    return 1.35 if tipo == "Transición/Oleadas" else 1.10

def minimo_hsr_min(largo, tipo, ida_vuelta_continua):
    if tipo != "Transición/Oleadas": return 0.0
    base = 6.5 if largo >= 35 else (5.5 if largo >= 30 else (4.5 if largo >= 25 else 3.0))
    return base * 1.15 if ida_vuelta_continua else base

def minimo_sprint_min(largo, tipo, ida_vuelta_continua):
    if tipo != "Transición/Oleadas": return 0.0
    base = 1.00 if largo >= 35 else (0.80 if largo >= 30 else (0.60 if largo >= 25 else 0.35))
    return base * 1.10 if ida_vuelta_continua else base

def box_to_box_logic(largo, repeticiones):
    distancia_total = largo * repeticiones
    hsr_ratio = 0.18 if largo < 20 else (0.35 if largo < 30 else (0.50 if largo < 40 else 0.58))
    sprint_ratio = 0.00 if largo < 20 else (0.06 if largo < 30 else (0.12 if largo < 40 else 0.18))
    hsr_total = distancia_total * hsr_ratio
    sprint_distance_total = distancia_total * sprint_ratio
    sprints_totales = sprint_distance_total / AVG_SPRINT_LENGTH_MATCH if AVG_SPRINT_LENGTH_MATCH > 0 else 0
    factor_acc = 0.60 if largo < 20 else (0.50 if largo < 30 else (0.40 if largo < 40 else 0.30))
    acc_total = dec_total = max(1, round(repeticiones * factor_acc, 2))
    return distancia_total, hsr_total, sprint_distance_total, sprints_totales, acc_total, dec_total

def calcular_carga(jugadores, duracion, tipo, ida_vuelta_continua, largo, ancho, repeticiones, nombre_tarea):
    if tipo == "Box to Box":
        dist_total, hsr_total, sprint_dist, sprints_tot, acc_tot, dec_tot = box_to_box_logic(largo, repeticiones)
        clasificacion, semaforo = clasificar_carga(dist_total)
        return {
            "Nombre tarea": nombre_tarea, "Ejercicio": tipo, "Jugadores": jugadores, 
            "Distancia total (m)": round(dist_total, 2), "HSR total (m)": round(hsr_total, 2),
            "Distancia sprint total (m)": round(sprint_dist, 2), "Nº sprints totales": round(sprints_tot, 2),
            "ACC total (n)": round(acc_tot, 2), "DEC total (n)": round(dec_tot, 2),
            "Carga total (m)": round(dist_total, 2), "Clasificación": clasificacion, "Semáforo": semaforo,
            "Interpretación": "Interpretación calculada para Box to Box"
        }
    
    app = calcular_app(largo, ancho, jugadores)
    f_long = factor_longitudinal(largo, ancho, tipo)
    f_cont = factor_continuidad(ida_vuelta_continua, tipo)
    suelo_hsr = minimo_hsr_min(largo, tipo, ida_vuelta_continua)
    suelo_sprint = minimo_sprint_min(largo, tipo, ida_vuelta_continua)
    factores = FACTORES_EJERCICIO[tipo]
    
    dt, d_sprint, d_acc, acc, d_dec, dec = metricas_base_excel(app)
    
    hsr_min = max(hsr_relativo(app) * factores["hsr"] * f_long * f_cont, suelo_hsr)
    sprint_min = max(d_sprint * factores["sprint"] * f_long * f_cont, suelo_sprint)
    
    carga_total = dt * duracion
    clasificacion, semaforo = clasificar_carga(carga_total)
    
    return {
        "Nombre tarea": nombre_tarea, "Ejercicio": tipo, "Largo (m)": largo, "Ancho (m)": ancho,
        "Jugadores": jugadores, "Duración (min)": duracion,
        "Distancia total (m)": round(carga_total, 2), 
        "HSR total (m)": round(hsr_min * duracion, 2),
        "Distancia sprint total (m)": round(sprint_min * duracion, 2),
        "Nº sprints totales": round((sprint_min * duracion) / AVG_SPRINT_LENGTH_MATCH if AVG_SPRINT_LENGTH_MATCH > 0 else 0, 2),
        "ACC total (n)": round(acc * factores["acc"] * duracion, 2),
        "DEC total (n)": round(dec * factores["dec"] * duracion, 2),
        "Carga total (m)": round(carga_total, 2), "Clasificación": clasificacion, "Semáforo": semaforo,
        "Interpretación": "Carga generada correctamente."
    }

def obtener_resumen_sesion():
    if not st.session_state.session_tasks: return None, None
    df = pd.DataFrame(st.session_state.session_tasks)
    
    resumen = pd.DataFrame({
        "Número de tareas": [len(df)],
        "Distancia total sesión (m)": [df["Distancia total (m)"].fillna(0).sum()],
        "HSR total sesión (m)": [df["HSR total (m)"].fillna(0).sum()],
        "Distancia sprint total sesión (m)": [df["Distancia sprint total (m)"].fillna(0).sum()],
        "Nº sprints totales sesión": [df["Nº sprints totales"].fillna(0).sum()],
        "ACC total sesión (n)": [df["ACC total (n)"].fillna(0).sum()],
        "DEC total sesión (n)": [df["DEC total (n)"].fillna(0).sum()],
        "Carga total sesión (m)": [df["Carga total (m)"].fillna(0).sum()],
    })
    return df, resumen

# ============================================================
# INTERFAZ GRÁFICA STREAMLIT
# ============================================================

st.title("⚽ Calculadora Avanzada de Cargas en Fútbol")

# Variables de control general de la sesión
with st.container():
    col1, col2, col3, col4 = st.columns(4)
    session_name = col1.text_input("Nombre de la Sesión", "Sesión 1")
    mesocycle_name = col2.text_input("Mesociclo", "Mesociclo 1")
    week_val = col3.number_input("Semana", min_value=1, max_value=20, value=1)
    day_val = col4.selectbox("Día microciclo", ["MD+1", "MD-4", "MD-3", "MD-2", "MD-1", "Partido"], index=2)

tab1, tab2, tab3, tab4 = st.tabs(["Calculadora", "Resumen Sesión", "Librería e Histórico", "Justificación"])

with tab1:
    st.header("Añadir / Editar Tarea")
    
    with st.form("task_form"):
        colA, colB = st.columns(2)
        task_name = colA.text_input("Nombre de la tarea", "Tarea 1")
        tipo_ej = colB.selectbox("Tipo de Ejercicio", list(FACTORES_EJERCICIO.keys()), index=3)
        
        colC, colD, colE = st.columns(3)
        jugadores = colC.number_input("Jugadores", min_value=1, value=10)
        largo = colD.number_input("Largo (m) / Distancia", min_value=1.0, value=30.0)
        
        # Dependiendo del tipo, mostramos unos u otros, pero Streamlit forms evalúa al pulsar submit.
        # Para interactividad real, los campos deben estar fuera del form, pero por simplicidad los mantenemos genéricos
        ancho = colE.number_input("Ancho (m)", min_value=1.0, value=15.0)
        
        colF, colG, colH = st.columns(3)
        duracion = colF.number_input("Duración (min)", min_value=0.5, value=9.0)
        repeticiones = colG.number_input("Repeticiones (Solo Box to Box)", min_value=1, value=8)
        ida_vuelta = colH.checkbox("Ida y vuelta continua", value=True)
        
        submitted = st.form_submit_button("Añadir Tarea a la Sesión")
        
        if submitted:
            res = calcular_carga(jugadores, duracion, tipo_ej, ida_vuelta, largo, ancho, repeticiones, task_name)
            st.session_state.session_tasks.append(res)
            st.success(f"Tarea '{task_name}' añadida correctamente.")

    if st.session_state.session_tasks:
        st.subheader("Tareas Actuales")
        st.dataframe(pd.DataFrame(st.session_state.session_tasks))
        if st.button("Limpiar Sesión Actual"):
            st.session_state.session_tasks = []
            st.rerun()

with tab2:
    st.header("Análisis de la Sesión")
    df_tareas, df_resumen = obtener_resumen_sesion()
    
    if df_resumen is not None:
        st.subheader("Totales")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        col1.metric("Carga Total (m)", f"{df_resumen['Carga total sesión (m)'].iloc[0]:.1f}")
        col2.metric("Distancia (m)", f"{df_resumen['Distancia total sesión (m)'].iloc[0]:.1f}")
        col3.metric("HSR (m)", f"{df_resumen['HSR total sesión (m)'].iloc[0]:.1f}")
        col4.metric("Sprint (m)", f"{df_resumen['Distancia sprint total sesión (m)'].iloc[0]:.1f}")
        col5.metric("ACC / DEC", f"{df_resumen['ACC total sesión (n)'].iloc[0]:.0f} / {df_resumen['DEC total sesión (n)'].iloc[0]:.0f}")

        # Gráfico básico
        st.subheader("Carga por Tarea")
        fig, ax = plt.subplots(figsize=(10, 4))
        ax.bar(df_tareas["Nombre tarea"], df_tareas["Carga total (m)"], color="#1d4ed8")
        ax.set_ylabel("Carga (m)")
        st.pyplot(fig)
        
        # Guardar en histórico
        if st.button("Guardar Sesión en Histórico"):
            ses_data = {
                "session_name": session_name, "microcycle_day": day_val,
                "week": week_val, "mesocycle": mesocycle_name,
                "summary": df_resumen.iloc[0].to_dict(),
                "tasks": df_tareas.to_dict(orient="records"),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            st.session_state.saved_sessions.append(ses_data)
            st.success("Sesión guardada en el histórico.")
            
        # Exportaciones (CSV/Excel simuladas en base64 o descargas)
        st.download_button(
            label="Descargar CSV de la sesión",
            data=df_tareas.to_csv(index=False).encode("utf-8"),
            file_name=f"sesion_{session_name}.csv",
            mime="text/csv"
        )
    else:
        st.info("Añade tareas en la Calculadora para ver el resumen de la sesión.")

with tab3:
    st.header("Histórico de Sesiones Guardadas")
    if st.session_state.saved_sessions:
        hist_df = pd.DataFrame([{
            "Sesión": s["session_name"], "Día": s["microcycle_day"], 
            "Semana": s["week"], "Mesociclo": s["mesocycle"],
            "Carga Total": s["summary"]["Carga total sesión (m)"]
        } for s in st.session_state.saved_sessions])
        st.dataframe(hist_df)
    else:
        st.write("No hay sesiones guardadas en el histórico todavía.")

with tab4:
    st.header("Justificación y Referencias")
    st.markdown("""
    La aplicación integra una lógica de cálculo de carga externa orientada a la planificación de tareas, control de sesión, análisis del microciclo e interpretación semanal relativa al partido.
    
    **Referencia de partido utilizada:** Los valores de referencia se han obtenido a partir del promedio de los últimos 10 partidos de un equipo de 2ª RFEF.
    
    *Buchheit, M. (2023). The 11 evidence-informed and inferred principles of microcycle periodization in elite football. Sport Performance & Science Reports, 218.*
    """)