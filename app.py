# ============================================================
# CALCULADORA AVANZADA DE CARGAS EN FÚTBOL
# Streamlit App - Versión 2.1 (Librería corregida)
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
plt.rcParams["figure.figsize"] = (11, 5)

# ============================================================
# ESTADO GLOBAL Y LIBRERÍA
# ============================================================
if 'session_tasks' not in st.session_state:
    st.session_state.session_tasks = []

if 'saved_sessions' not in st.session_state:
    if os.path.exists("historico_sesiones.json"):
        try:
            with open("historico_sesiones.json", "r", encoding="utf-8") as f:
                st.session_state.saved_sessions = json.load(f)
        except:
            st.session_state.saved_sessions = []
    else:
        st.session_state.saved_sessions = []

if 'custom_task_library' not in st.session_state:
    if os.path.exists("libreria_tareas.json"):
        try:
            with open("libreria_tareas.json", "r", encoding="utf-8") as f:
                st.session_state.custom_task_library = json.load(f)
        except:
            st.session_state.custom_task_library = {}
    else:
        st.session_state.custom_task_library = {}

# ============================================================
# FACTORES POR TIPO DE EJERCICIO
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
# FUNCIONES BASE
# ============================================================
def validar_positivo(valor): return max(valor, 0.001)

def calcular_app(largo, ancho, jugadores):
    return (validar_positivo(largo) * validar_positivo(ancho)) / validar_positivo(jugadores)

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
        base = 6.5 if largo >= 35 else (5.5 if largo >= 30 else (4.5 if largo >= 25 else 3.0))
        return base * 1.15 if ida_vuelta_continua else base
    return 0.0

def minimo_sprint_min(largo, tipo, ida_vuelta_continua):
    if tipo == "Transición/Oleadas":
        base = 1.00 if largo >= 35 else (0.80 if largo >= 30 else (0.60 if largo >= 25 else 0.35))
        return base * 1.10 if ida_vuelta_continua else base
    return 0.0

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
    factor = 0.60 if d < 20 else (0.50 if d < 30 else (0.40 if d < 40 else 0.30))
    return max(1, round(reps * factor, 2)), max(1, round(reps * factor, 2))

def interpretacion_practica(carga_total, hsr_total, sprint_total, acc_total, dec_total, tipo):
    txt_carga = "baja" if carga_total < 300 else ("media" if carga_total < 700 else "alta")
    txt_hsr = "reducida" if hsr_total < 20 else ("moderada" if hsr_total < 50 else "elevada")
    txt_sprint = "baja" if sprint_total < 10 else ("moderada" if sprint_total < 25 else "alta")
    txt_acc = "bajo" if acc_total < 5 else ("moderado" if acc_total < 12 else "alto")
    txt_dec = "bajo" if dec_total < 5 else ("moderado" if dec_total < 12 else "alto")
    return f"En {tipo.lower()}, la carga global es {txt_carga}; además, la exposición al HSR es {txt_hsr}, al sprint {txt_sprint}, aceleraciones {txt_acc} y deceleraciones {txt_dec}."

# ============================================================
# FUNCIÓN PRINCIPAL DE CÁLCULO
# ============================================================
def calcular_carga(jugadores, duracion, tipo, modo_espacio, rpe_val, ida_vuelta_continua, m2, largo, ancho, repeticiones, nombre_tarea):
    srpe = rpe_val * duracion
    if tipo == "Box to Box":
        distancia_total = largo * repeticiones
        hsr_total = distancia_total * box_to_box_hsr_ratio(largo)
        sprint_total = distancia_total * box_to_box_sprint_ratio(largo)
        sprints_totales = sprint_total / 19.1
        acc_total, dec_total = box_to_box_acc_dec_totales(repeticiones, largo)
        interp = interpretacion_practica(distancia_total, hsr_total, sprint_total, acc_total, dec_total, tipo)
        clasif, semaforo = clasificar_carga(distancia_total)
        return {
            "Nombre tarea": nombre_tarea.strip() or "Tarea", "Ejercicio": tipo, "RPE": rpe_val, "sRPE": round(srpe, 2),
            "Largo (m)": round(largo, 2), "Ancho (m)": None, "ApP (m²/jugador)": None, "Jugadores": int(jugadores),
            "Duración (min)": round(duracion, 2), "Repeticiones": int(repeticiones), "Ida y vuelta continua": "No aplica",
            "Factor HSR": None, "Factor Sprint": None, "Factor ACC": None, "Factor DEC": None, "Factor longitudinal": None, "Factor continuidad": None, "Suelo HSR/min": None, "Suelo Sprint/min": None,
            "Distancia total (m)": round(distancia_total, 2), "HSR/min (m)": None, "HSR total (m)": round(hsr_total, 2),
            "Sprint/min (m)": None, "Sprint total (m)": round(sprint_total, 2), "Sprints/min (n)": None, "Sprints totales (n)": round(sprints_totales, 2),
            "ACC/min (n)": None, "ACC total (n)": round(acc_total, 2), "DEC/min (n)": None, "DEC total (n)": round(dec_total, 2),
            "Dist ACC/min (m)": None, "Dist ACC total (m)": None, "Dist DEC/min (m)": None, "Dist DEC total (m)": None,
            "Carga total (m)": round(distancia_total, 2), "Clasificación": clasif, "Semáforo": semaforo, "Interpretación": interp
        }

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

    hsr_min_modelo = hsr_relativo(app) * factores["hsr"] * factor_long * factor_cont
    hsr_min = max(hsr_min_modelo, suelo_hsr)
    hsr_total = hsr_min * duracion

    sprint_min_modelo = d_sprint * factores["sprint"] * factor_long * factor_cont
    sprint_min = max(sprint_min_modelo, suelo_sprint)
    sprint_total = sprint_min * duracion
    sprints_totales = sprint_total / 19.1

    acc_min, dec_min = acc * factores["acc"], dec * factores["dec"]
    acc_total, dec_total = acc_min * duracion, dec_min * duracion

    dist_acc_min, dist_dec_min = d_acc * factores["acc"], d_dec * factores["dec"]
    dist_acc_total, dist_dec_total = dist_acc_min * duracion, dist_dec_min * duracion

    carga_total = dt * duracion
    clasif, semaforo = clasificar_carga(carga_total)

    return {
        "Nombre tarea": nombre_tarea.strip() or "Tarea", "Ejercicio": tipo, "RPE": rpe_val, "sRPE": round(srpe, 2),
        "Largo (m)": round(largo_val, 2) if largo_val else None, "Ancho (m)": round(ancho_val, 2) if ancho_val else None,
        "ApP (m²/jugador)": round(app, 2), "Jugadores": int(jugadores), "Duración (min)": round(duracion, 2), "Repeticiones": None,
        "Ida y vuelta continua": "Sí" if ida_vuelta_continua else "No",
        "Factor HSR": factores["hsr"], "Factor Sprint": factores["sprint"], "Factor ACC": factores["acc"], "Factor DEC": factores["dec"],
        "Factor longitudinal": round(factor_long, 2), "Factor continuidad": round(factor_cont, 2), "Suelo HSR/min": round(suelo_hsr, 2), "Suelo Sprint/min": round(suelo_sprint, 2),
        "Distancia total (m)": round(carga_total, 2), "HSR/min (m)": round(hsr_min, 2), "HSR total (m)": round(hsr_total, 2),
        "Sprint/min (m)": round(sprint_min, 3), "Sprint total (m)": round(sprint_total, 2),
        "Sprints/min (n)": round(sprints_totales/duracion if duracion>0 else 0, 3), "Sprints totales (n)": round(sprints_totales, 2),
        "ACC/min (n)": round(acc_min, 3), "ACC total (n)": round(acc_total, 2), "DEC/min (n)": round(dec_min, 3), "DEC total (n)": round(dec_total, 2),
        "Dist ACC/min (m)": round(dist_acc_min, 2), "Dist ACC total (m)": round(dist_acc_total, 2), "Dist DEC/min (m)": round(dist_dec_min, 2), "Dist DEC total (m)": round(dist_dec_total, 2),
        "Carga total (m)": round(carga_total, 2), "Clasificación": clasif, "Semáforo": semaforo,
        "Interpretación": interpretacion_practica(carga_total, hsr_total, sprint_total, acc_total, dec_total, tipo)
    }

# ============================================================
# HISTÓRICO DE SESIONES Y LONGITUDINAL 
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

def get_history_dataframe():
    if not st.session_state.saved_sessions: return None
    rows = []
    for i, sess in enumerate(st.session_state.saved_sessions, start=1):
        row = {"Orden": i, "Microciclo": sess.get("microcycle", "Micro 1"), "Sesión": sess["session_name"], "Objetivo": sess["goal"]}
        row.update(sess["summary"])
        rows.append(row)
    return pd.DataFrame(rows)

def compute_monotony_strain_acwr(history_df):
    if history_df is None or len(history_df) == 0: return None
    loads = history_df["Carga total sesión (m)"].astype(float).tolist()
    mean_load = sum(loads) / len(loads)
    std_load = pd.Series(loads).std(ddof=0)
    monotony = (mean_load / std_load) if std_load and std_load > 0 else None
    strain = (mean_load * monotony) if monotony is not None else None
    acute_window = loads[-7:] if len(loads) >= 1 else loads
    chronic_window = loads[-28:] if len(loads) >= 1 else loads
    acute = sum(acute_window) / len(acute_window) if acute_window else None
    chronic = sum(chronic_window) / len(chronic_window) if chronic_window else None
    acwr = (acute / chronic) if acute is not None and chronic not in [None, 0] else None
    return {
        "Monotony": round(monotony, 3) if monotony is not None else None,
        "Strain": round(strain, 2) if strain is not None else None,
        "ACWR": round(acwr, 3) if acwr is not None else None
    }

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

def session_cards_html():
    data, resumen = obtener_resumen_sesion()
    if data is None:
        return '<div style="padding:12px;border:1px solid #e2e8f0;border-radius:12px;background:#fff;">No hay tareas en la sesión.</div>'
    vals = {"sRPE": resumen["sRPE total sesión"].iloc[0], "Distancia total": resumen["Distancia total sesión (m)"].iloc[0], "HSR total": resumen["HSR total sesión (m)"].iloc[0], "Sprint total": resumen["Sprint total sesión (m)"].iloc[0], "ACC totales": resumen["ACC total sesión (n)"].iloc[0], "DEC totales": resumen["DEC total sesión (n)"].iloc[0]}
    cards = ""
    for k, v in vals.items():
        cards += f'<div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:14px;padding:14px 16px;min-width:170px;box-shadow:0 2px 8px rgba(0,0,0,0.05);"><div style="font-size:13px;color:#475569;">{k}</div><div style="font-size:24px;font-weight:700;color:#0f172a;">{float(v):.1f}</div></div>'
    return f'<div style="display:flex;gap:12px;flex-wrap:wrap;margin:8px 0 16px 0;">{cards}</div>'

# ============================================================
# FUNCIONES PARA GRÁFICOS MATPLOTLIB
# ============================================================
def grafico_aporte_por_tarea(df, variable_col, titulo):
    df_plot = df.copy()
    df_plot[variable_col] = df_plot[variable_col].fillna(0)
    total = df_plot[variable_col].sum()
    if total <= 0: return None
    df_plot["Porcentaje"] = (df_plot[variable_col] / total) * 100
    df_plot = df_plot.sort_values("Porcentaje", ascending=True)
    fig, ax = plt.subplots(figsize=(11, 4))
    bars = ax.barh(df_plot["Nombre tarea"], df_plot["Porcentaje"], color="#3b82f6")
    ax.set_title(f"Aporte porcentual por tarea - {titulo}", fontweight="bold")
    ax.set_xlabel("Porcentaje (%)")
    ax.set_xlim(0, max(100, df_plot["Porcentaje"].max() * 1.15))
    for bar, pct in zip(bars, df_plot["Porcentaje"]):
        ax.text(pct, bar.get_y() + bar.get_height()/2, f" {pct:.1f}%", va="center")
    plt.tight_layout()
    return fig

def generar_pdf(session_name, goal, df, resumen):
    buf = io.BytesIO()
    with PdfPages(buf) as pdf:
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.axis('off')
        plt.title(f"Informe de Cargas: {session_name} ({goal})", fontsize=16, fontweight='bold', pad=20)
        celdas = [[k, f"{v.iloc[0]:.2f}" if isinstance(v.iloc[0], float) else str(v.iloc[0])] for k, v in resumen.items()]
        tabla = ax.table(cellText=celdas, colLabels=["Métrica", "Valor Total"], loc='center', cellLoc='center')
        tabla.scale(1, 2.5)
        tabla.set_fontsize(12)
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(11, 5))
        ax.bar(df["Nombre tarea"], df["Distancia total (m)"].fillna(0), color="#3b82f6")
        ax.set_title("Distancia total por tarea")
        plt.xticks(rotation=35, ha="right")
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
        
        x = range(len(df))
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.bar(x, df["HSR total (m)"].fillna(0), width=0.4, label="HSR total (m)", color="#10b981")
        ax.bar([i + 0.4 for i in x], df["Sprint total (m)"].fillna(0), width=0.4, label="Sprint total (m)", color="#ef4444")
        ax.set_xticks([i + 0.2 for i in x])
        ax.set_xticklabels(df["Nombre tarea"], rotation=35, ha="right")
        ax.set_title("HSR y Sprint por tarea")
        ax.legend()
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

        fig, ax = plt.subplots(figsize=(12, 3.8))
        df["Dur_plot"] = df["Duración (min)"].fillna(0)
        lefts = [sum(df["Dur_plot"].iloc[:i]) for i in range(len(df))]
        ax.barh(["Sesión"] * len(df), df["Dur_plot"], left=lefts, color="#e2e8f0", edgecolor="#64748b")
        for i, row in df.iterrows():
            ax.text(lefts[i] + (row["Dur_plot"]/2), 0, row["Nombre tarea"], ha="center", va="center", fontsize=9)
        ax.set_title("Timeline de la sesión")
        ax.set_xlabel("Tiempo acumulado (min)")
        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)
    return buf.getvalue()

# ============================================================
# INTERFAZ WEB (FRONTEND COMPLETO)
# ============================================================
st.markdown("""
<div style="background: linear-gradient(90deg, #0f172a, #1e293b); color: #ffffff; padding: 18px 22px; border-radius: 14px; margin-bottom: 20px; text-align: center; box-shadow: 0 4px 14px rgba(0,0,0,0.18);">
    <h1 style="margin: 0; font-size: 30px; font-weight: 800; letter-spacing: 1px; text-transform: uppercase; color: #ffffff;">
        CALCULADORA AVANZADA DE CARGAS EN FÚTBOL
    </h1>
</div>
""", unsafe_allow_html=True)

tab_calc, tab_sesion, tab_analisis, tab_historico, tab_comp, tab_info = st.tabs([
    "🛠️ Calculadora", "📋 Sesión Actual", "📈 Análisis", "📂 Histórico Semanal", "⚖️ Comparar", "ℹ️ Justificación"
])

# ------------------------------------------------------------
# 1. CALCULADORA
# ------------------------------------------------------------
with tab_calc:
    col_s1, col_s2, col_s3, col_s4 = st.columns([2, 1, 1, 1])
    with col_s1: session_name = st.text_input("Nombre de la Sesión", value="Sesión 1")
    with col_s2: goal = st.selectbox("Objetivo sesión:", list(SESSION_GOALS.keys()), index=2)
    with col_s3: micro_sel = st.selectbox("Microciclo:", [f"Micro {i}" for i in range(1, 41)], index=0)
    with col_s4: 
        st.write("")
        if st.button("💾 Guardar sesión", use_container_width=True):
            data_tmp, res_tmp = obtener_resumen_sesion()
            if data_tmp is not None:
                payload = {"session_name": session_name, "goal": goal, "microcycle": micro_sel, "tasks": data_tmp.to_dict("records"), "summary": res_tmp.iloc[0].to_dict()}
                idx = next((i for i, s in enumerate(st.session_state.saved_sessions) if s["session_name"] == session_name), None)
                if idx is not None: st.session_state.saved_sessions[idx] = payload
                else: st.session_state.saved_sessions.append(payload)
                with open("historico_sesiones.json", "w", encoding="utf-8") as f: json.dump(st.session_state.saved_sessions, f, ensure_ascii=False, indent=2)
                st.success(f"Sesión '{session_name}' guardada en {micro_sel}.")
            else:
                st.error("No hay tareas para guardar.")

    st.divider()
    
    # 1. Seleccionamos librería arriba
    presets = ["Seleccionar tarea frecuente"] + list(st.session_state.custom_task_library.keys())
    c1, c2 = st.columns(2)
    with c1: t_nombre = st.text_input("Nombre tarea:", value="Tarea 1")
    with c2: sel_preset = st.selectbox("Librería:", presets)

    if sel_preset != "Seleccionar tarea frecuente":
        d = st.session_state.custom_task_library[sel_preset]
        def_t = d.get("Ejercicio", "Transición/Oleadas"); def_mod = d.get("Espacio", "campo"); def_l = float(d.get("Largo", 30)); def_a = float(d.get("Ancho", 15)); def_m2 = float(d.get("m2", 120)); def_j = int(d.get("Jugadores", 10)); def_dur = float(d.get("Duracion", 9)); def_rep = int(d.get("Repeticiones", 8)); def_rpe = int(d.get("RPE", 5)); def_ida = d.get("Ida_vuelta", True)
    else:
        def_t = "Transición/Oleadas"; def_mod = "campo"; def_l = 30.0; def_a = 15.0; def_m2 = 120.0; def_j = 10; def_dur = 9.0; def_rep = 8; def_rpe = 5; def_ida = True

    c_ej, c_rpe = st.columns(2)
    with c_ej: t_tipo = st.selectbox("Ejercicio:", list(FACTORES_EJERCICIO.keys()), index=list(FACTORES_EJERCICIO.keys()).index(def_t) if def_t in FACTORES_EJERCICIO else 0)
    with c_rpe: t_rpe = st.slider("RPE (1-10):", 1, 10, value=def_rpe)

    es_box = (t_tipo == "Box to Box")
    col_dim1, col_dim2, col_dim3 = st.columns(3)
    if es_box:
        with col_dim1: t_largo = st.number_input("Distancia carrera (m)", value=def_l)
        with col_dim2: t_rep = st.number_input("Repeticiones", value=def_rep)
        with col_dim3: 
            t_jug = st.number_input("Jugadores implicados", value=def_j)
            t_dur = st.number_input("Duración total (min)", value=def_dur)
        t_modo, t_ancho, t_m2, t_ida = "campo", 0, 0, False
    else:
        t_modo = st.radio("Espacio:", [("Calcular desde largo x ancho", "campo"), ("Introducir m²/jugador", "m2")], format_func=lambda x: x[0], index=1 if def_mod=="m2" else 0)[1]
        with col_dim1: t_jug = st.number_input("Jugadores:", value=def_j)
        with col_dim2: t_dur = st.number_input("Duración (min):", value=def_dur)
        with col_dim3: t_ida = st.checkbox("Ida y vuelta continua", value=def_ida)
        
        if t_modo == "m2":
            t_m2 = st.number_input("m²/jugador:", value=def_m2)
            t_largo, t_ancho, t_rep = 0, 0, 0
        else:
            cc1, cc2 = st.columns(2)
            with cc1: t_largo = st.number_input("Largo (m):", value=def_l)
            with cc2: t_ancho = st.number_input("Ancho (m):", value=def_a)
            t_m2, t_rep = 0, 0

    st.write("")
    # 2. BOTONES DE ACCIÓN AL FINAL (Problema solucionado)
    col_btn_calc, col_btn_save = st.columns(2)
    
    with col_btn_calc:
        if st.button("➕ Calcular y Añadir tarea", type="primary", use_container_width=True):
            res = calcular_carga(t_jug, t_dur, t_tipo, t_modo, t_rpe, t_ida, t_m2, t_largo, t_ancho, t_rep, t_nombre)
            st.session_state.session_tasks.append(res)
            st.success(f"Tarea añadida. Total en sesión: {len(st.session_state.session_tasks)}")
            
    with col_btn_save:
        if st.button("⭐ Guardar en Librería (Plantilla)", use_container_width=True):
            st.session_state.custom_task_library[t_nombre] = {
                "Nombre tarea": t_nombre, "Ejercicio": t_tipo, "Espacio": t_modo,
                "Largo": float(t_largo), "Ancho": float(t_ancho), "m2": float(t_m2),
                "Jugadores": int(t_jug), "Duracion": float(t_dur), 
                "Repeticiones": int(t_rep), "RPE": int(t_rpe), "Ida_vuelta": bool(t_ida)
            }
            with open("libreria_tareas.json", "w", encoding="utf-8") as f: 
                json.dump(st.session_state.custom_task_library, f)
            st.success(f"Tarea '{t_nombre}' guardada en la librería.")

    st.divider()
    if st.session_state.session_tasks:
        df_edit = pd.DataFrame(st.session_state.session_tasks)
        st.markdown("### Gestión de Tareas")
        
        c_sel, c_btn1, c_btn2, c_btn3, c_btn4, c_btn5 = st.columns([3, 1, 1, 1, 1, 1])
        with c_sel: idx_edit = st.selectbox("Editar tarea:", range(len(df_edit)), format_func=lambda x: f"{x+1}. {df_edit.iloc[x]['Nombre tarea']} ({df_edit.iloc[x]['Ejercicio']})")
        
        with c_btn1:
            st.write("")
            if st.button("✏️ Editar", use_container_width=True):
                res = calcular_carga(t_jug, t_dur, t_tipo, t_modo, t_rpe, t_ida, t_m2, t_largo, t_ancho, t_rep, t_nombre)
                st.session_state.session_tasks[idx_edit] = res
                st.rerun()
        with c_btn2:
            st.write("")
            if st.button("📄 Duplicar", use_container_width=True):
                dup = copy.deepcopy(st.session_state.session_tasks[idx_edit])
                dup["Nombre tarea"] += " (copia)"
                st.session_state.session_tasks.insert(idx_edit + 1, dup)
                st.rerun()
        with c_btn3:
            st.write("")
            if st.button("⬆️ Subir", use_container_width=True) and idx_edit > 0:
                st.session_state.session_tasks[idx_edit-1], st.session_state.session_tasks[idx_edit] = st.session_state.session_tasks[idx_edit], st.session_state.session_tasks[idx_edit-1]
                st.rerun()
        with c_btn4:
            st.write("")
            if st.button("⬇️ Bajar", use_container_width=True) and idx_edit < len(st.session_state.session_tasks)-1:
                st.session_state.session_tasks[idx_edit+1], st.session_state.session_tasks[idx_edit] = st.session_state.session_tasks[idx_edit], st.session_state.session_tasks[idx_edit+1]
                st.rerun()
        with c_btn5:
            st.write("")
            if st.button("🗑️ Eliminar", use_container_width=True):
                st.session_state.session_tasks.pop(idx_edit)
                st.rerun()
                
        if st.button("🚨 Reiniciar sesión entera", type="secondary"):
            st.session_state.session_tasks = []
            st.rerun()

# ------------------------------------------------------------
# 2. SESIÓN ACTUAL
# ------------------------------------------------------------
with tab_sesion:
    st.markdown("### Tarjetas resumen")
    st.markdown(session_cards_html(), unsafe_allow_html=True)
    
    data, resumen = obtener_resumen_sesion()
    if data is not None:
        st.markdown("### Tareas acumuladas")
        st.dataframe(data, use_container_width=True)
        
        st.markdown("### Resumen total de la sesión")
        st.dataframe(resumen, use_container_width=True)

        st.markdown("### Planificación de la sesión")
        st.markdown(f"**Objetivo seleccionado:** {goal}")
        st.dataframe(build_planning_table(resumen.iloc[0], goal), use_container_width=True)

        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            csv_sesion = data.to_csv(index=False).encode('utf-8')
            st.download_button("Exportar CSV", data=csv_sesion, file_name="tareas_sesion.csv", mime="text/csv", use_container_width=True)
        with col_d2:
            buffer_excel = io.BytesIO()
            with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                data.to_excel(writer, sheet_name="Tareas", index=False)
                resumen.to_excel(writer, sheet_name="Resumen", index=False)
            st.download_button("Exportar Excel", data=buffer_excel.getvalue(), file_name=f"Sesion_{session_name}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with col_d3:
            pdf_bytes = generar_pdf(session_name, goal, data, resumen)
            st.download_button("Exportar PDF", data=pdf_bytes, file_name=f"Informe_{session_name}.pdf", mime="application/pdf", use_container_width=True)

        st.markdown("### Panel de Gráficas")
        c_g1, c_g2 = st.columns(2)
        with c_g1:
            f_carga, ax = plt.subplots(figsize=(11,5))
            ax.bar(data["Nombre tarea"], data["Distancia total (m)"].fillna(0))
            ax.set_title("Distancia total por tarea")
            plt.xticks(rotation=35, ha="right"); plt.tight_layout()
            st.pyplot(f_carga)
        with c_g2:
            f_hsr, ax = plt.subplots(figsize=(11,5))
            x = range(len(data))
            ax.bar(x, data["HSR total (m)"].fillna(0), width=0.4, label="HSR total (m)")
            ax.bar([i + 0.4 for i in x], data["Sprint total (m)"].fillna(0), width=0.4, label="Sprint total (m)")
            ax.set_xticks([i + 0.2 for i in x]); ax.set_xticklabels(data["Nombre tarea"], rotation=35, ha="right")
            ax.set_title("HSR y Sprint por tarea"); ax.legend(); plt.tight_layout()
            st.pyplot(f_hsr)
            
        c_g3, c_g4 = st.columns(2)
        with c_g3:
            f_acc, ax = plt.subplots(figsize=(11,5))
            ax.bar(x, data["ACC total (n)"].fillna(0), width=0.4, label="ACC total (n)")
            ax.bar([i + 0.4 for i in x], data["DEC total (n)"].fillna(0), width=0.4, label="DEC total (n)")
            ax.set_xticks([i + 0.2 for i in x]); ax.set_xticklabels(data["Nombre tarea"], rotation=35, ha="right")
            ax.set_title("ACC y DEC por tarea"); ax.legend(); plt.tight_layout()
            st.pyplot(f_acc)
        with c_g4:
            f_time, ax = plt.subplots(figsize=(12, 3.8))
            data["Dur_plot"] = data["Duración (min)"].fillna(0)
            lefts = [sum(data["Dur_plot"].iloc[:i]) for i in range(len(data))]
            ax.barh(["Sesión"] * len(data), data["Dur_plot"], left=lefts)
            for i, row in data.iterrows(): ax.text(lefts[i] + (row["Dur_plot"]/2), 0, row["Nombre tarea"], ha="center", va="center", fontsize=9)
            ax.set_title("Timeline de la sesión"); ax.set_xlabel("Tiempo acumulado (min)"); plt.tight_layout()
            st.pyplot(f_time)

# ------------------------------------------------------------
# 3. ANÁLISIS LONGITUDINAL Y ACWR
# ------------------------------------------------------------
with tab_analisis:
    st.markdown("### Histórico longitudinal")
    history_df = get_history_dataframe()
    if history_df is not None:
        st.dataframe(history_df, use_container_width=True)
        metrics = compute_monotony_strain_acwr(history_df)
        if metrics:
            st.markdown("### Indicadores longitudinales (Carga)")
            st.dataframe(pd.DataFrame([metrics]), use_container_width=True)
            
        st.markdown("### Gráficos micro/mesociclo")
        metric_sel = st.selectbox("Métrica a visualizar:", ["Carga total sesión (m)", "HSR total sesión (m)", "Sprint total sesión (m)", "ACC total sesión (n)", "DEC total sesión (n)"])
        fig_hist, ax_hist = plt.subplots(figsize=(11, 4))
        ax_hist.plot(history_df["Sesión"], history_df[metric_sel], marker="o")
        ax_hist.set_title(f"Evolución de {metric_sel}")
        plt.xticks(rotation=35, ha="right"); plt.tight_layout()
        st.pyplot(fig_hist)
    else:
        st.info("No hay histórico para analizar.")

# ------------------------------------------------------------
# 4. HISTÓRICO SEMANAL (NUEVO DASHBOARD)
# ------------------------------------------------------------
with tab_historico:
    st.markdown("### Base de Datos Semanal (Mesociclo)")
    if st.session_state.saved_sessions:
        
        # 1. Preparar datos con Microciclo
        hist_data = []
        for s in st.session_state.saved_sessions:
            row = {"Microciclo": s.get("microcycle", "Micro 1"), "Sesión": s["session_name"], "Objetivo": s["goal"]}
            row.update(s["summary"])
            hist_data.append(row)
        hist_df_export = pd.DataFrame(hist_data)
        
        # 2. Filtro visual por Microciclo
        micros_disponibles = hist_df_export["Microciclo"].unique()
        filtro_micro = st.selectbox("Visualizar semana completa:", ["Todos los Microciclos"] + list(micros_disponibles))
        
        df_mostrar = hist_df_export if filtro_micro == "Todos los Microciclos" else hist_df_export[hist_df_export["Microciclo"] == filtro_micro]
        
        # 3. Tarjetas visuales de suma semanal (solo si filtras un micro)
        if filtro_micro != "Todos los Microciclos":
            tot_carga = df_mostrar["Carga total sesión (m)"].sum()
            tot_hsr = df_mostrar["HSR total sesión (m)"].sum()
            tot_sprint = df_mostrar["Sprint total sesión (m)"].sum()
            tot_srpe = df_mostrar["sRPE total sesión"].sum()
            
            st.markdown(f"#### Totales del {filtro_micro}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("sRPE Semanal", f"{tot_srpe:.1f}")
            c2.metric("Carga Semanal", f"{tot_carga:.1f} m")
            c3.metric("HSR Semanal", f"{tot_hsr:.1f} m")
            c4.metric("Sprint Semanal", f"{tot_sprint:.1f} m")
            st.write("")

        # 4. Tabla con colores (Mapa de calor)
        columnas_calor = ["sRPE total sesión", "Carga total sesión (m)", "HSR total sesión (m)", "Sprint total sesión (m)", "ACC total sesión (n)", "DEC total sesión (n)"]
        
        # Aplicamos un estilo visual degradado (YlOrRd = Amarillo a Rojo)
        st.dataframe(
            df_mostrar.style.background_gradient(cmap="YlOrRd", subset=columnas_calor).format(precision=1),
            use_container_width=True
        )
        
        json_hist = json.dumps(st.session_state.saved_sessions, ensure_ascii=False, indent=2).encode('utf-8')
        st.download_button("📥 Exportar Backup (JSON)", data=json_hist, file_name="historico_sesiones.json", mime="application/json")
    else:
        st.info("No hay sesiones guardadas en el histórico.")

# ------------------------------------------------------------
# 5. COMPARACIÓN
# ------------------------------------------------------------
with tab_comp:
    st.markdown("### Comparación entre sesiones")
    nombres = [s["session_name"] for s in st.session_state.saved_sessions]
    if len(nombres) < 2:
        st.info("Selecciona dos sesiones para comparar (necesitas al menos 2 en el histórico).")
    else:
        col_c1, col_c2 = st.columns(2)
        with col_c1: compare_a = st.selectbox("Sesión A:", nombres, index=0)
        with col_c2: compare_b = st.selectbox("Sesión B:", nombres, index=1)
        
        if st.button("Comparar sesiones", type="primary"):
            df_A = next(s for s in st.session_state.saved_sessions if s["session_name"] == compare_a)["summary"]
            df_B = next(s for s in st.session_state.saved_sessions if s["session_name"] == compare_b)["summary"]
            
            keys = ["sRPE total sesión", "Distancia total sesión (m)", "Sprint total sesión (m)", "Sprints totales sesión (n)", "HSR total sesión (m)", "ACC total sesión (n)", "DEC total sesión (n)", "Carga total sesión (m)"]
            comp_data = []
            for k in keys:
                a, b = float(df_A.get(k,0)), float(df_B.get(k,0))
                diff = b - a
                pct = ((diff/a)*100) if a!=0 else None
                comp_data.append({"Variable": k, compare_a: round(a,2), compare_b: round(b,2), "Diferencia": round(diff,2), "% cambio": round(pct,2) if pct is not None else None})
                
            st.dataframe(pd.DataFrame(comp_data), use_container_width=True)

# ------------------------------------------------------------
# 6. JUSTIFICACIÓN
# ------------------------------------------------------------
with tab_info:
    JUSTIFICACION_HTML = """
    <h2>JUSTIFICACIÓN</h2>
    <p><strong>Base de la calculadora</strong><br>
    La aplicación se construye a partir de un modelo híbrido: por un lado, incorpora ecuaciones base obtenidas del Excel de referencia; por otro, incluye ajustes prácticos para tareas longitudinales y específicas del entrenamiento en fútbol.</p>

    <p><strong>Variables derivadas del Excel</strong><br>
    Las ecuaciones utilizadas como base son:</p>
    <ul>
    <li><strong>Distancia total (DT, m/min)</strong> = 19.243 &times; ln(m&sup2;/jugador) &minus; 5.029</li>
    <li><strong>Distancia sprint (D_Sprint, m/min)</strong> = 0.001 &times; (m&sup2;/jugador) &minus; 0.046</li>
    <li><strong>Distancia en aceleraci&oacute;n (D_ACC, m/min)</strong> = 1.321 &times; ln(m&sup2;/jugador) &minus; 0.629</li>
    <li><strong>Aceleraciones (ACC, n&ordm;/min)</strong> = 0.212 &times; ln(m&sup2;/jugador) &minus; 0.23</li>
    <li><strong>Distancia en deceleraci&oacute;n (D_DEC, m/min)</strong> = 1.157 &times; ln(m&sup2;/jugador) &minus; 0.418</li>
    <li><strong>Deceleraciones (DEC, n&ordm;/min)</strong> = 0.104 &times; ln(m&sup2;/jugador) &minus; 0.096</li>
    </ul>

    <p><strong>Base de datos y seguimiento longitudinal</strong><br>
    La aplicación permite guardar sesiones en un histórico, compararlas entre sí, visualizar evolución longitudinal de carga total, HSR, sprint, ACC y DEC, y calcular monotony, strain y ACWR de forma práctica.</p>
    """
    st.markdown(JUSTIFICACION_HTML, unsafe_allow_html=True)