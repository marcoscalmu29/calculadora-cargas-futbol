# ============================================================
# CALCULADORA AVANZADA DE CARGAS EN FÚTBOL
# Streamlit App - Versión Profesional Completa y Corregida
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
# INICIALIZACIÓN DE MEMORIA Y ARCHIVOS (ESTADO GLOBAL)
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
# FUNCIONES MATEMÁTICAS BASE
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
    app = max(app, 1) # Evitar log(0)
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
    txt_hsr = "reducida" if hsr_total < 20 else ("moderada" if hsr_total < 50 else "elevada")
    txt_sprint = "baja" if sprint_total < 10 else ("moderada" if sprint_total < 25 else "alta")
    txt_acc = "bajo" if acc_total < 5 else ("moderado" if acc_total < 12 else "alto")
    txt_dec = "bajo" if dec_total < 5 else ("moderado" if dec_total < 12 else "alto")
    return f"En {tipo.lower()}, la carga global es {txt_carga}; además, la exposición al HSR es {txt_hsr}, al sprint {txt_sprint}, aceleraciones {txt_acc} y deceleraciones {txt_dec}."

# ============================================================
# CÁLCULO DE LA TAREA
# ============================================================
def calcular_carga(jugadores, duracion, tipo, modo_espacio, rpe_val, ida_vuelta_continua, m2, largo, ancho, repeticiones, nombre_tarea):
    srpe = rpe_val * duracion

    if tipo == "Box to Box":
        distancia_total = largo * repeticiones
        hsr_total = distancia_total * box_to_box_hsr_ratio(largo)
        sprint_total = distancia_total * box_to_box_sprint_ratio(largo)
        sprints_totales = sprint_total / 19.1
        acc_total, dec_total = box_to_box_acc_dec_totales(repeticiones, largo)
        interpretacion = interpretacion_practica(distancia_total, hsr_total, sprint_total, acc_total, dec_total, tipo)
        clasif, semaforo = clasificar_carga(distancia_total)

        return {
            "Nombre tarea": nombre_tarea.strip() or "Tarea", "Ejercicio": tipo, "RPE": rpe_val, "sRPE": round(srpe, 2),
            "Largo (m)": round(largo, 2), "Ancho (m)": None, "ApP (m²/jugador)": None, "Jugadores": int(jugadores),
            "Duración (min)": round(duracion, 2), "Repeticiones": int(repeticiones), "Ida y vuelta continua": "No aplica",
            "Distancia total (m)": round(distancia_total, 2), "HSR total (m)": round(hsr_total, 2), "Sprint total (m)": round(sprint_total, 2),
            "Sprints totales (n)": round(sprints_totales, 2), "ACC total (n)": round(acc_total, 2), "DEC total (n)": round(dec_total, 2),
            "Carga total (m)": round(distancia_total, 2), "Clasificación": clasif, "Semáforo": semaforo, "Interpretación": interpretacion
        }

    # Resto de tareas
    if modo_espacio == "m2":
        app, largo_val, ancho_val = m2, None, None
        factor_long = factor_cont = 1.0
        suelo_hsr = suelo_sprint = 0.0
    else:
        app = calcular_app(largo, ancho, jugadores)
        largo_val, ancho_val = largo, ancho
        factor_long = factor_longitudinal(largo, ancho, tipo)
        factor_cont = factor_continuidad(ida_vuelta_continua, tipo)
        suelo_hsr = minimo_hsr_min(largo, tipo, ida_vuelta_continua)
        suelo_sprint = minimo_sprint_min(largo, tipo, ida_vuelta_continua)

    factores = FACTORES_EJERCICIO[tipo]
    dt, d_sprint, d_acc, acc, d_dec, dec = metricas_base_excel(app)

    hsr_min = max(hsr_relativo(app) * factores["hsr"] * factor_long * factor_cont, suelo_hsr)
    sprint_min = max(d_sprint * factores["sprint"] * factor_long * factor_cont, suelo_sprint)
    
    hsr_total, sprint_total = hsr_min * duracion, sprint_min * duracion
    sprints_totales = sprint_total / 19.1
    acc_total, dec_total = (acc * factores["acc"]) * duracion, (dec * factores["dec"]) * duracion
    carga_total = dt * duracion
    clasif, semaforo = clasificar_carga(carga_total)
    
    return {
        "Nombre tarea": nombre_tarea.strip() or "Tarea", "Ejercicio": tipo, "RPE": rpe_val, "sRPE": round(srpe, 2),
        "Largo (m)": round(largo_val, 2) if largo_val else None, "Ancho (m)": round(ancho_val, 2) if ancho_val else None,
        "ApP (m²/jugador)": round(app, 2), "Jugadores": int(jugadores), "Duración (min)": round(duracion, 2), "Repeticiones": None,
        "Ida y vuelta continua": "Sí" if ida_vuelta_continua else "No",
        "Distancia total (m)": round(carga_total, 2), "HSR total (m)": round(hsr_total, 2), "Sprint total (m)": round(sprint_total, 2),
        "Sprints totales (n)": round(sprints_totales, 2), "ACC total (n)": round(acc_total, 2), "DEC total (n)": round(dec_total, 2),
        "Carga total (m)": round(carga_total, 2), "Clasificación": clasif, "Semáforo": semaforo, 
        "Interpretación": interpretacion_practica(carga_total, hsr_total, sprint_total, acc_total, dec_total, tipo)
    }

# ============================================================
# LÓGICA DE SESIONES E HISTÓRICO
# ============================================================
def obtener_resumen_sesion():
    if not st.session_state.session_tasks: return None, None
    df = pd.DataFrame(st.session_state.session_tasks)
    resumen = pd.DataFrame([{
        "Número de tareas": len(df),
        "Duración total (min)": df["Duración (min)"].fillna(0).sum(),
        "RPE medio": df["RPE"].mean(),
        "sRPE total sesión": df["sRPE"].fillna(0).sum(),
        "Distancia total sesión (m)": df["Distancia total (m)"].fillna(0).sum(),
        "Sprint total sesión (m)": df["Sprint total (m)"].fillna(0).sum(),
        "Sprints totales sesión (n)": df["Sprints totales (n)"].fillna(0).sum(),
        "HSR total sesión (m)": df["HSR total (m)"].fillna(0).sum(),
        "ACC total sesión (n)": df["ACC total (n)"].fillna(0).sum(),
        "DEC total sesión (n)": df["DEC total (n)"].fillna(0).sum(),
        "Carga total sesión (m)": df["Carga total (m)"].fillna(0).sum()
    }])
    return df, resumen

def build_planning_table(summary_row, goal_name):
    ranges = SESSION_GOALS.get(goal_name, SESSION_GOALS["Personalizado"])
    metrics = [
        ("Distancia total sesión (m)", "distance"), ("HSR total sesión (m)", "hsr"),
        ("Sprint total sesión (m)", "sprint"), ("Sprints totales sesión (n)", "sprints"),
        ("ACC total sesión (n)", "acc"), ("DEC total sesión (n)", "dec")
    ]
    rows = []
    for label, key in metrics:
        real = float(summary_row[label])
        min_v, max_v = ranges[key]
        estado = "🟡 Bajo" if real < min_v else ("🔴 Alto" if real > max_v else "🟢 Adecuado")
        rows.append({"Variable": label, "Obj. mínimo": min_v, "Obj. máximo": max_v, "Valor sesión": round(real, 2), "Estado": estado})
    return pd.DataFrame(rows)

def save_session_to_history(name, goal):
    data, resumen = obtener_resumen_sesion()
    if data is None: return False
    payload = {"session_name": name, "goal": goal, "tasks": data.to_dict("records"), "summary": resumen.iloc[0].to_dict()}
    
    idx = next((i for i, s in enumerate(st.session_state.saved_sessions) if s["session_name"] == name), None)
    if idx is not None: st.session_state.saved_sessions[idx] = payload
    else: st.session_state.saved_sessions.append(payload)
    
    with open("historico_sesiones.json", "w", encoding="utf-8") as f:
        json.dump(st.session_state.saved_sessions, f, ensure_ascii=False, indent=2)
    return True

# ============================================================
# SOLUCIÓN DE LAS TARJETAS HTML (TODO EN UNA LÍNEA)
# ============================================================
def session_cards_html():
    data, resumen = obtener_resumen_sesion()
    if data is None:
        return '<div style="padding:12px;border:1px solid #e2e8f0;border-radius:12px;background:#fff;">No hay tareas en la sesión.</div>'

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
        color = "#2563eb" if "sRPE" in k else "#0f172a"
        # ¡ATENCIÓN! Todo en una sola línea y sin tabulaciones a la izquierda
        cards += f'<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;padding:14px 16px;min-width:140px;box-shadow:0 2px 8px rgba(0,0,0,0.05);"><div style="font-size:13px;color:#475569;">{k}</div><div style="font-size:24px;font-weight:700;color:{color};">{float(v):.1f}</div></div>'
        
    return f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin:8px 0 16px 0;">{cards}</div>'

# ============================================================
# GRÁFICOS (Retornan Figuras para Streamlit)
# ============================================================
def generar_grafico(tipo_grafico):
    if not st.session_state.session_tasks: return None
    df = pd.DataFrame(st.session_state.session_tasks)
    fig, ax = plt.subplots(figsize=(10, 4))
    
    if tipo_grafico == "carga":
        ax.bar(df["Nombre tarea"], df["Distancia total (m)"].fillna(0), color="#3b82f6")
        ax.set_title("Distancia Total por Tarea", fontweight="bold")
    elif tipo_grafico == "hsr":
        x = range(len(df))
        ax.bar(x, df["HSR total (m)"].fillna(0), width=0.4, label="HSR (>19.8 km/h)", color="#10b981")
        ax.bar([i + 0.4 for i in x], df["Sprint total (m)"].fillna(0), width=0.4, label="Sprint (>25.2 km/h)", color="#ef4444")
        ax.set_xticks([i + 0.2 for i in x])
        ax.set_xticklabels(df["Nombre tarea"])
        ax.set_title("Alta Velocidad por Tarea", fontweight="bold")
        ax.legend()
    elif tipo_grafico == "acc":
        x = range(len(df))
        ax.bar(x, df["ACC total (n)"].fillna(0), width=0.4, label="Aceleraciones", color="#f59e0b")
        ax.bar([i + 0.4 for i in x], df["DEC total (n)"].fillna(0), width=0.4, label="Deceleraciones", color="#6366f1")
        ax.set_xticks([i + 0.2 for i in x])
        ax.set_xticklabels(df["Nombre tarea"])
        ax.set_title("Carga Mecánica por Tarea", fontweight="bold")
        ax.legend()
    elif tipo_grafico == "timeline":
        df["Dur_plot"] = df["Duración (min)"].fillna(0)
        lefts = [sum(df["Dur_plot"].iloc[:i]) for i in range(len(df))]
        ax.barh(["Timeline"] * len(df), df["Dur_plot"], left=lefts, color="#e2e8f0", edgecolor="#64748b")
        for i, row in df.iterrows():
            ax.text(lefts[i] + (row["Dur_plot"]/2), 0, row["Nombre tarea"][:12], ha="center", va="center", fontsize=9, fontweight="bold")
        ax.set_title("Estructura Temporal", fontweight="bold")
        
    plt.xticks(rotation=35 if tipo_grafico != "timeline" else 0, ha="right" if tipo_grafico != "timeline" else "center")
    plt.tight_layout()
    return fig

def generar_pdf(session_name, goal):
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        # Portada / Tabla
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.axis('off')
        _, resumen = obtener_resumen_sesion()
        plt.title(f"Informe de Cargas: {session_name} ({goal})", fontsize=16, fontweight='bold', pad=20)
        celdas = [[k, f"{v.iloc[0]:.2f}"] for k, v in resumen.items()]
        tabla = ax.table(cellText=celdas, colLabels=["Métrica", "Valor"], loc='center', cellLoc='center')
        tabla.scale(1, 2.2)
        tabla.set_fontsize(11)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        # Gráficas
        for tipo in ["carga", "hsr", "acc", "timeline"]:
            f = generar_grafico(tipo)
            if f:
                pdf.savefig(f, bbox_inches='tight')
                plt.close(f)
    return buf.getvalue()

# ============================================================
# INTERFAZ WEB (FRONTEND COMPLETO)
# ============================================================

st.title("⚽ Calculadora Avanzada de Cargas en Fútbol")

# Dividir la pantalla en pestañas
tab_calc, tab_sesion, tab_analisis, tab_historico, tab_comp, tab_info = st.tabs([
    "🛠️ Calculadora", "📋 Sesión Actual", "📈 Análisis", "📂 Histórico", "⚖️ Comparar", "ℹ️ Info"
])

# ------------------------------------------------------------
# PESTAÑA 1: CALCULADORA
# ------------------------------------------------------------
with tab_calc:
    st.header("1. Configuración de Sesión")
    col_s1, col_s2, col_s3 = st.columns([2, 1, 1])
    with col_s1: session_name = st.text_input("Nombre de la Sesión", value="Sesión 1")
    with col_s2: goal = st.selectbox("Objetivo", list(SESSION_GOALS.keys()), index=2) # MD-3 por defecto
    with col_s3: 
        st.write("") # Espaciador
        st.write("")
        if st.button("💾 Guardar Sesión en Histórico", use_container_width=True):
            if save_session_to_history(session_name, goal): st.success("¡Sesión guardada!")
            else: st.error("Añade tareas primero.")

    st.divider()
    st.header("2. Diseño de Tarea")
    
    # Selector de librería
    presets = ["(Crear tarea desde cero)"] + list(st.session_state.custom_task_library.keys())
    sel_preset = st.selectbox("📂 Cargar desde Librería Personal", presets)
    
    # Autorellenar si se elige preset
    if sel_preset != "(Crear tarea desde cero)":
        d = st.session_state.custom_task_library[sel_preset]
        def_n, def_t = d.get("Nombre", ""), d.get("Ejercicio", "Transición/Oleadas")
        def_mod, def_l, def_a, def_m2 = d.get("Modo", "campo"), float(d.get("Largo", 30)), float(d.get("Ancho", 15)), float(d.get("m2", 120))
        def_j, def_dur, def_rep = int(d.get("Jugadores", 10)), float(d.get("Duracion", 9)), int(d.get("Repeticiones", 8))
        def_rpe, def_ida = int(d.get("RPE", 5)), d.get("IdaVuelta", True)
    else:
        def_n, def_t, def_mod = "Tarea 1", "Transición/Oleadas", "campo"
        def_l, def_a, def_m2, def_j, def_dur, def_rep = 30.0, 15.0, 120.0, 10, 9.0, 8
        def_rpe, def_ida = 5, True

    c1, c2, c3 = st.columns([2, 2, 1])
    with c1: 
        t_nombre = st.text_input("Nombre de la tarea", value=def_n)
        t_tipo = st.selectbox("Tipo de Ejercicio", list(FACTORES_EJERCICIO.keys()), index=list(FACTORES_EJERCICIO.keys()).index(def_t) if def_t in FACTORES_EJERCICIO else 0)
    with c2:
        t_rpe = st.slider("RPE (1-10)", 1, 10, value=def_rpe)
        st.write("")
        if st.button("⭐ Guardar en Librería", use_container_width=True):
            st.session_state.custom_task_library[t_nombre] = {
                "Nombre": t_nombre, "Ejercicio": t_tipo, "Modo": "m2" if 't_modo' in locals() and t_modo=="m2" else "campo",
                "Largo": 't_largo' in locals() and t_largo or def_l, "Ancho": 't_ancho' in locals() and t_ancho or def_a, "m2": 't_m2' in locals() and t_m2 or def_m2,
                "Jugadores": 't_jug' in locals() and t_jug or def_j, "Duracion": 't_dur' in locals() and t_dur or def_dur, 
                "Repeticiones": 't_rep' in locals() and t_rep or def_rep, "RPE": t_rpe, "IdaVuelta": 't_ida' in locals() and t_ida or def_ida
            }
            with open("libreria_tareas.json", "w", encoding="utf-8") as f: json.dump(st.session_state.custom_task_library, f)
            st.rerun()

    es_box = (t_tipo == "Box to Box")
    
    col_dim1, col_dim2, col_dim3 = st.columns(3)
    if es_box:
        with col_dim1: t_largo = st.number_input("Distancia carrera (m)", value=def_l)
        with col_dim2: t_rep = st.number_input("Repeticiones", value=def_rep)
        with col_dim3: 
            t_jug = st.number_input("Jugadores implicados", value=def_j)
            t_dur = st.number_input("Duración total (min) - Para sRPE", value=def_dur)
        t_modo, t_ancho, t_m2, t_ida = "campo", 0, 0, False
    else:
        t_modo = st.radio("Definir espacio por:", ["Dimensiones del campo (Largo x Ancho)", "Metros cuadrados (m²/jugador)"], index=1 if def_mod=="m2" else 0)
        t_modo = "m2" if "Metros" in t_modo else "campo"
        
        with col_dim1: t_jug = st.number_input("Jugadores", value=def_j)
        with col_dim2: t_dur = st.number_input("Duración (min)", value=def_dur)
        with col_dim3: t_ida = st.checkbox("Ida y vuelta continua (Transiciones)", value=def_ida)
        
        if t_modo == "m2":
            t_m2 = st.number_input("m²/jugador", value=def_m2)
            t_largo, t_ancho, t_rep = 0, 0, 0
        else:
            c_l, c_a = st.columns(2)
            with c_l: t_largo = st.number_input("Largo (m)", value=def_l)
            with c_a: t_ancho = st.number_input("Ancho (m)", value=def_a)
            t_m2, t_rep = 0, 0

    st.write("")
    if st.button("➕ Calcular y Añadir a la Sesión", type="primary", use_container_width=True):
        res = calcular_carga(t_jug, t_dur, t_tipo, t_modo, t_rpe, t_ida, t_m2, t_largo, t_ancho, t_rep, t_nombre)
        st.session_state.session_tasks.append(res)
        st.success(f"¡{t_nombre} calculada y añadida con éxito!")

    st.divider()
    st.header("3. Gestor de Tareas Activas")
    if st.session_state.session_tasks:
        df_edit = pd.DataFrame(st.session_state.session_tasks)
        st.dataframe(df_edit[["Nombre tarea", "Ejercicio", "Duración (min)", "sRPE", "Carga total (m)", "Semáforo"]], use_container_width=True)
        
        cdel1, cdel2, cdel3 = st.columns(3)
        with cdel1:
            idx_edit = st.selectbox("Selecciona una tarea:", range(len(df_edit)), format_func=lambda x: df_edit.iloc[x]["Nombre tarea"])
        with cdel2:
            st.write("")
            if st.button("📄 Duplicar Tarea", use_container_width=True):
                dup = copy.deepcopy(st.session_state.session_tasks[idx_edit])
                dup["Nombre tarea"] += " (copia)"
                st.session_state.session_tasks.insert(idx_edit + 1, dup)
                st.rerun()
        with cdel3:
            st.write("")
            if st.button("🗑️ Eliminar Tarea", use_container_width=True):
                st.session_state.session_tasks.pop(idx_edit)
                st.rerun()
        
        if st.button("🚨 Borrar TODA la sesión", type="secondary"):
            st.session_state.session_tasks = []
            st.rerun()

# ------------------------------------------------------------
# PESTAÑA 2: SESIÓN ACTUAL
# ------------------------------------------------------------
with tab_sesion:
    data, resumen = obtener_resumen_sesion()
    if data is None:
        st.info("No hay tareas. Configura la sesión en la pestaña 'Calculadora'.")
    else:
        st.markdown(session_cards_html(), unsafe_allow_html=True)
        
        col_down1, col_down2 = st.columns(2)
        with col_down1:
            csv_sesion = data.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descargar Tareas (CSV)", data=csv_sesion, file_name="tareas_sesion.csv", mime="text/csv", use_container_width=True)
        with col_down2:
            pdf_bytes = generar_pdf(session_name, goal)
            st.download_button("📄 Descargar Informe Visual (PDF)", data=pdf_bytes, file_name=f"Informe_{session_name}.pdf", mime="application/pdf", use_container_width=True)

        st.subheader("Semáforo de Planificación")
        st.dataframe(build_planning_table(resumen.iloc[0], goal), use_container_width=True)
        
        st.subheader("Análisis Gráfico")
        c_g1, c_g2 = st.columns(2)
        with c_g1: st.pyplot(generar_grafico("carga"))
        with c_g2: st.pyplot(generar_grafico("hsr"))
        c_g3, c_g4 = st.columns(2)
        with c_g3: st.pyplot(generar_grafico("acc"))
        with c_g4: st.pyplot(generar_grafico("timeline"))

# ------------------------------------------------------------
# PESTAÑA 3: ANÁLISIS LONGITUDINAL
# ------------------------------------------------------------
with tab_analisis:
    st.header("Análisis de Micro/Mesociclo")
    if not st.session_state.saved_sessions:
        st.info("Guarda varias sesiones en el histórico para ver su evolución.")
    else:
        historico_df = pd.DataFrame([{"Sesión": s["session_name"], **s["summary"]} for s in st.session_state.saved_sessions])
        
        metric_sel = st.selectbox("Métrica a visualizar:", ["sRPE total sesión", "Carga total sesión (m)", "HSR total sesión (m)", "Sprint total sesión (m)", "ACC total sesión (n)", "DEC total sesión (n)"])
        
        fig_hist, ax_hist = plt.subplots(figsize=(11, 4))
        ax_hist.plot(historico_df["Sesión"], historico_df[metric_sel], marker="o", color="#2563eb", linewidth=2)
        ax_hist.set_title(f"Evolución: {metric_sel}", fontweight="bold")
        plt.xticks(rotation=45, ha="right")
        st.pyplot(fig_hist)

# ------------------------------------------------------------
# PESTAÑA 4: HISTÓRICO
# ------------------------------------------------------------
with tab_historico:
    st.header("Base de Datos de Sesiones")
    if not st.session_state.saved_sessions:
        st.info("No hay sesiones guardadas.")
    else:
        historico_df = pd.DataFrame([{"Sesión": s["session_name"], "Objetivo": s["goal"], **s["summary"]} for s in st.session_state.saved_sessions])
        st.dataframe(historico_df, use_container_width=True)
        
        csv_hist = historico_df.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Histórico (CSV)", data=csv_hist, file_name="historico_cargas.csv", mime="text/csv")

# ------------------------------------------------------------
# PESTAÑA 5: COMPARACIÓN
# ------------------------------------------------------------
with tab_comp:
    st.header("Comparador A/B de Sesiones")
    nombres = [s["session_name"] for s in st.session_state.saved_sessions]
    if len(nombres) < 2:
        st.info("Necesitas al menos 2 sesiones guardadas para comparar.")
    else:
        col_c1, col_c2 = st.columns(2)
        with col_c1: ses_A = st.selectbox("Sesión A (Referencia)", nombres, index=0)
        with col_c2: ses_B = st.selectbox("Sesión B (A comparar)", nombres, index=1)
        
        df_A = next(s for s in st.session_state.saved_sessions if s["session_name"] == ses_A)["summary"]
        df_B = next(s for s in st.session_state.saved_sessions if s["session_name"] == ses_B)["summary"]
        
        keys = ["sRPE total sesión", "Carga total sesión (m)", "HSR total sesión (m)", "Sprint total sesión (m)", "ACC total sesión (n)"]
        comp_data = []
        for k in keys:
            a, b = float(df_A.get(k,0)), float(df_B.get(k,0))
            diff = b - a
            pct = f"{((diff/a)*100):.1f}%" if a!=0 else "-"
            comp_data.append({"Métrica": k, ses_A: round(a,1), ses_B: round(b,1), "Diferencia": round(diff,1), "% Evolución": pct})
            
        st.dataframe(pd.DataFrame(comp_data), use_container_width=True)

# ------------------------------------------------------------
# PESTAÑA 6: JUSTIFICACIÓN
# ------------------------------------------------------------
with tab_info:
    st.markdown("""
    ## JUSTIFICACIÓN TÉCNICA
    La aplicación se construye a partir de un modelo híbrido: incorpora las ecuaciones base de un Excel estandarizado 
    y añade ajustes prácticos para tareas longitudinales y entrenamiento específico en fútbol.
    
    ### Fórmulas del Excel:
    - **Distancia total (m/min)** = $19.243 \\times \ln(m^2/\text{jugador}) - 5.029$
    - **Distancia sprint (m/min)** = $0.001 \\times (m^2/\text{jugador}) - 0.046$
    - **Distancia en aceleración (m/min)** = $1.321 \\times \ln(m^2/\text{jugador}) - 0.629$
    - **Aceleraciones (nº/min)** = $0.212 \\times \ln(m^2/\text{jugador}) - 0.23$
    - **Distancia en deceleración (m/min)** = $1.157 \\times \ln(m^2/\text{jugador}) - 0.418$
    - **Deceleraciones (nº/min)** = $0.104 \\times \ln(m^2/\text{jugador}) - 0.096$
    
    ### Integración de RPE
    Se ha integrado la métrica **sRPE (Session-RPE)** multiplicando el valor subjetivo de esfuerzo (1-10) 
    por la duración de la tarea, permitiendo cruzar la Carga Externa objetiva con la Interna subjetiva.
    
    ### Base de datos y seguimiento longitudinal
    La aplicación permite guardar sesiones en un histórico, compararlas entre sí, visualizar la evolución 
    longitudinal de la carga total, HSR, sprint, ACC y DEC, permitiendo adaptar los mesociclos de forma visual y precisa.
    """)