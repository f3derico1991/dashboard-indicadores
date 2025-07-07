import streamlit as st
import pandas as pd
import gspread
import plotly.express as px
from PIL import Image
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode
from io import BytesIO
from fpdf import FPDF # ---> NUEVO: Importar la librería para PDF

# --- CONFIGURACIÓN DE LA PÁGINA Y CONEXIÓN (sin cambios) ---
st.set_page_config(page_title="Dashboard de Métricas Clave", page_icon="🚀", layout="wide")

@st.cache_data(ttl=600)
def load_data_from_gsheet(sheet_name):
    try:
        gc = gspread.service_account_from_dict(st.secrets["google_credentials"])
        spreadsheet_name = "copia-Indicadores internos +Simple 2025"
        spreadsheet = gc.open(spreadsheet_name)
        worksheet = spreadsheet.worksheet(sheet_name)
        data = worksheet.get_all_records()
        if not data:
            st.warning(f"La pestaña '{sheet_name}' está vacía.")
            return pd.DataFrame()
        df = pd.DataFrame(data)
        if 'Métrica' in df.columns:
            df = df[['Métrica'] + [col for col in df.columns if col != 'Métrica']]
        return df
    except Exception as e:
        st.error(f"Error al cargar la pestaña '{sheet_name}': {e}.")
        return None

# --- FUNCIONES AUXILIARES MEJORADAS ---

def prepare_metric_data(metric_df):
    plot_df = metric_df.melt(id_vars=['Métrica'], var_name='Mes', value_name='Valor')
    plot_df['Valor_Num'] = plot_df['Valor'].astype(str).str.replace('%', '', regex=False).str.strip()
    plot_df['Valor_Num'] = pd.to_numeric(plot_df['Valor_Num'], errors='coerce')
    plot_df.dropna(subset=['Valor_Num'], inplace=True)
    return plot_df

# ---> NUEVO: Formateo inteligente para KPIs
def format_kpi(metric_name, value):
    if '%' in metric_name.lower() or 'tasa' in metric_name.lower():
        return f"{value:.2f}%"
    else:
        return f"{value:,.0f}"

# ---> NUEVO: Función para generar el PDF
def create_pdf(selected_data, kpi_data, figures):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    
    # Título del PDF
    pdf.cell(0, 10, "Reporte de Métricas Clave", 0, 1, "C")
    pdf.ln(10)

    for i, data in enumerate(selected_data):
        metric_name = data['metric_name']
        
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 10, f"Métrica: {metric_name}", 0, 1)

        # KPIs
        pdf.set_font("Arial", "", 12)
        kpis = kpi_data[i]
        for key, value in kpis.items():
            pdf.cell(40, 10, f"{key}: {value}", 0, 0)
        pdf.ln(10)

        # Gráfico
        fig = figures[i]
        if fig:
            # Guardar el gráfico como una imagen temporal en memoria
            img_bytes = fig.to_image(format="png")
            img_file = BytesIO(img_bytes)
            
            # Añadir la imagen al PDF
            pdf.image(img_file, x=10, w=190) # w=190 para que ocupe casi todo el ancho
            pdf.ln(10)
    
    return pdf.output(dest='S').encode('latin-1')

# --- FUNCIÓN PRINCIPAL DE LA SECCIÓN INTERACTIVA (Reestructurada) ---

def create_interactive_section(df, section_title):
    st.header(section_title)
    if df is None or df.empty:
        st.info("No hay datos disponibles para esta sección.")
        return pd.DataFrame(), None, [], [] # Devolvemos valores vacíos

    # Filtro de Meses
    all_months = [col for col in df.columns if col != 'Métrica']
    with st.expander("📅 Filtrar por Rango de Meses", expanded=False):
        selected_months = st.multiselect("Selecciona meses:", options=all_months, default=all_months, key=f"ms_{section_title}")
    
    if not selected_months:
        st.warning("Debes seleccionar al menos un mes.")
        return pd.DataFrame(), None, [], []
    
    filtered_df = df[['Métrica'] + selected_months]

    # Configuración de AgGrid
    gb = GridOptionsBuilder.from_dataframe(filtered_df)
    gb.configure_selection('multiple', use_checkbox=True, rowMultiSelectWithClick=True)
    gb.configure_grid_options(domLayout='autoHeight')
    gridOptions = gb.build()

    st.info("Selecciona hasta 2 filas para comparar.")
    grid_response = AgGrid(filtered_df, gridOptions=gridOptions, update_mode=GridUpdateMode.MODEL_CHANGED,
                           data_return_mode=DataReturnMode.AS_INPUT, theme='streamlit', key=f"grid_{section_title}")

    selected_rows = pd.DataFrame(grid_response['selected_rows'])
    
    # Inicializamos las variables que devolveremos
    figures_to_download = []
    kpi_data_to_download = []

    if not selected_rows.empty:
        if st.button("🔄 Limpiar Selección", key=f"clear_{section_title}"):
            st.rerun()
        st.markdown("---")

        all_plot_data = [prepare_metric_data(pd.DataFrame([row])) for _, row in selected_rows.iterrows()]
        
        # Mostrar KPIs con formato correcto
        st.subheader("📈 Estadísticas Clave")
        kpi_cols = st.columns(len(all_plot_data))
        for i, plot_df in enumerate(all_plot_data):
            if not plot_df.empty:
                with kpi_cols[i]:
                    metric_name = plot_df['Métrica'].iloc[0]
                    st.markdown(f"**{metric_name}**")
                    kpis = {
                        "Promedio": plot_df['Valor_Num'].mean(),
                        "Máximo": plot_df['Valor_Num'].max(),
                        "Mínimo": plot_df['Valor_Num'].min(),
                        "Último Mes": plot_df['Valor_Num'].iloc[-1]
                    }
                    kpi_data_to_download.append({k: format_kpi(metric_name, v) for k, v in kpis.items()})
                    for key, value in kpis.items():
                        st.metric(label=key, value=format_kpi(metric_name, value))

        st.markdown("---")
        st.subheader("📊 Visualización")
        
        chart_type = st.radio("Tipo de gráfico:", ('Línea', 'Barras'), horizontal=True, key=f"radio_{section_title}")
        
        def get_hover_format(metric_name):
            return "<b>Mes:</b> %{x}<br><b>Valor:</b> %{y:.2f}%<extra></extra>" if '%' in metric_name.lower() or 'tasa' in metric_name.lower() else "<b>Mes:</b> %{x}<br><b>Valor:</b> %{y}<extra></extra>"

        viz_cols = st.columns(len(all_plot_data))
        for i, plot_df in enumerate(all_plot_data):
            if not plot_df.empty:
                with viz_cols[i]:
                    metric_name = plot_df['Métrica'].iloc[0]
                    st.markdown(f"**{metric_name}**")
                    hover_template = get_hover_format(metric_name)
                    
                    if chart_type == 'Línea':
                        fig = px.line(plot_df, x='Mes', y='Valor_Num', markers=True)
                        fig.update_traces(line=dict(width=4, color='gold'), marker=dict(size=8, color='darkorange'), hovertemplate=hover_template, hoverlabel=dict(bgcolor="black", font_size=16, font_color="white"))
                    else:
                        fig = px.bar(plot_df, x='Mes', y='Valor_Num')
                        fig.update_traces(marker_color='gold', hovertemplate=hover_template, hoverlabel=dict(bgcolor="black", font_size=16, font_color="white"))
                    
                    fig.update_layout(height=300, xaxis_title=None, yaxis_title=None, plot_bgcolor='rgba(0,0,0,0)', xaxis=dict(tickfont=dict(size=16, color='black')), yaxis=dict(tickfont=dict(size=16, color='black')))
                    st.plotly_chart(fig, use_container_width=True)
                    figures_to_download.append(fig)

    selected_data_for_download = [{"metric_name": row['Métrica']} for _, row in selected_rows.iterrows()]
    return filtered_df, selected_data_for_download, kpi_data_to_download, figures_to_download

# --- CUERPO PRINCIPAL DEL DASHBOARD ---

# Logo y Título
try:
    image = Image.open('assets/images1.jpeg')
    st.image(image, width=400) 
except FileNotFoundError:
    st.warning("Advertencia: No se encontró el logo.")
st.title("📊 Indicadores Internos")
st.markdown("Dashboard interactivo conectado a Google Sheets. Actualización cada 10 minutos.")

# Pestañas
tab_names = ["📊 Alcance", "🧩 Uso y Participación", "💬 Retroalimentación", "🏛️ Valor Público"]
tabs = st.tabs(tab_names)

# ---> NUEVO: Almacenar resultados de todas las pestañas
all_filtered_dfs = {}
all_selected_data = []
all_kpis = []
all_figures = []

for tab, name in zip(tabs, tab_names):
    with tab:
        df = load_data_from_gsheet(name.split(" ")[1]) # Extrae el nombre de la hoja del título
        filtered_df, selected_data, kpis, figures = create_interactive_section(df, name)
        all_filtered_dfs[name] = filtered_df
        if selected_data:
            all_selected_data.extend(selected_data)
            all_kpis.extend(kpis)
            all_figures.extend(figures)

# --- BOTÓN DE DESCARGA EN LA BARRA LATERAL ---
st.sidebar.header("Opciones de Descarga")
if all_selected_data:
    pdf_bytes = create_pdf(all_selected_data, all_kpis, all_figures)
    st.sidebar.download_button(
        label="📥 Descargar Reporte en PDF",
        data=pdf_bytes,
        file_name="reporte_dashboard.pdf",
        mime="application/pdf"
    )
else:
    st.sidebar.info("Selecciona al menos una métrica para generar el reporte en PDF.")