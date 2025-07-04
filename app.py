import streamlit as st
import pandas as pd
import gspread
import plotly.express as px
from PIL import Image
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode, DataReturnMode

# CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Dashboard de Métricas Clave", page_icon="🚀", layout="wide")

# CONEXIÓN A GOOGLE SHEETS
@st.cache_data(ttl=600)
def load_data_from_gsheet(sheet_name):
    try:
        # ---> CAMBIO CLAVE PARA LA SEGURIDAD <---
        # En lugar de leer un archivo JSON local, usamos los "Secrets" de Streamlit.
        # Streamlit gestionará de forma segura el contenido de tu archivo de credenciales.
        # ¡Asegúrate de haber configurado st.secrets["google_credentials"] en tu despliegue!
        gc = gspread.service_account_from_dict(st.secrets["google_credentials"])
        
        # El nombre de la hoja de cálculo sigue siendo necesario.
        spreadsheet_name = "copia-Indicadores internos +Simple 2025"
        spreadsheet = gc.open(spreadsheet_name)
        worksheet = spreadsheet.worksheet(sheet_name)
        data = worksheet.get_all_records()

        if not data:
            st.warning(f"La pestaña '{sheet_name}' está vacía.")
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        # Asegurarnos que la columna Métrica sea la primera
        if 'Métrica' in df.columns:
            df = df[['Métrica'] + [col for col in df.columns if col != 'Métrica']]
        return df
    except Exception as e:
        st.error(f"Error al cargar la pestaña '{sheet_name}': {e}. "
                 "Si estás en la web, asegúrate de que los 'Secrets' de Streamlit estén bien configurados y que has compartido el Google Sheet con el 'client_email'.")
        return None

# FUNCIÓN AUXILIAR PARA PREPARAR DATOS Y ESTADÍSTICAS
def prepare_metric_data(metric_df):
    plot_df = metric_df.melt(id_vars=['Métrica'], var_name='Mes', value_name='Valor')
    plot_df['Valor_Num'] = plot_df['Valor'].astype(str).str.replace('%', '', regex=False).str.strip()
    plot_df['Valor_Num'] = pd.to_numeric(plot_df['Valor_Num'], errors='coerce')
    plot_df.dropna(subset=['Valor_Num'], inplace=True)
    return plot_df

# FUNCIÓN REUTILIZABLE PARA CREAR LA SECCIÓN INTERACTIVA
def create_interactive_section(df, section_title):
    st.header(section_title)
    if df is None or df.empty:
        st.info("No hay datos disponibles para esta sección o hubo un error al cargarlos.")
        return
    if 'Métrica' not in df.columns:
        st.warning("La primera columna de tu hoja de cálculo debe llamarse exactamente 'Métrica'.")
        return

    # Filtro de Meses
    all_months = [col for col in df.columns if col != 'Métrica']
    with st.expander("📅 Filtrar por Rango de Meses", expanded=False):
        selected_months = st.multiselect(
            "Selecciona los meses que quieres analizar:",
            options=all_months,
            default=all_months,
            key=f"multiselect_{section_title}"
        )
    if not selected_months:
        st.warning("Debes seleccionar al menos un mes.")
        return
    filtered_df = df[['Métrica'] + selected_months]

    # Configuración de AgGrid
    gb = GridOptionsBuilder.from_dataframe(filtered_df)
    gb.configure_selection('multiple', use_checkbox=True, rowMultiSelectWithClick=True)
    gb.configure_grid_options(domLayout='autoHeight')
    gridOptions = gb.build()

    st.info("Selecciona hasta 2 filas en la tabla para comparar sus gráficos.")
    grid_response = AgGrid(filtered_df, gridOptions=gridOptions, update_mode=GridUpdateMode.MODEL_CHANGED,
                           data_return_mode=DataReturnMode.AS_INPUT, allow_unsafe_jscode=True, theme='streamlit', key=f"grid_{section_title}")

    selected = pd.DataFrame(grid_response['selected_rows'])
    
    if not selected.empty:
        # Botones y Lógica de Visualización
        col_btn1, col_btn2 = st.columns([1, 4])
        with col_btn1:
            if st.button("🔄 Limpiar Selección", key=f"clear_{section_title}"):
                st.rerun()
        with col_btn2:
            csv_data = selected.to_csv(index=False).encode('utf-8')
            st.download_button(
               label="📥 Descargar Datos Seleccionados (CSV)",
               data=csv_data,
               file_name=f'datos_{section_title.replace(" ", "_")}.csv',
               mime='text/csv',
            )

        st.markdown("---")

        all_plot_data = []
        for index, row in selected.iterrows():
            metric_df = pd.DataFrame([row])
            plot_df = prepare_metric_data(metric_df)
            if not plot_df.empty:
                all_plot_data.append(plot_df)

        st.subheader("📈 Estadísticas Clave")
        kpi_cols = st.columns(len(all_plot_data))
        for i, plot_df in enumerate(all_plot_data):
            with kpi_cols[i]:
                metric_name = plot_df['Métrica'].iloc[0]
                st.markdown(f"**{metric_name}**")
                avg_val = plot_df['Valor_Num'].mean()
                max_val = plot_df['Valor_Num'].max()
                min_val = plot_df['Valor_Num'].min()
                last_val = plot_df['Valor_Num'].iloc[-1]
                st.metric(label="Promedio", value=f"{avg_val:.2f}")
                st.metric(label="Máximo", value=f"{max_val:.2f}")
                st.metric(label="Mínimo", value=f"{min_val:.2f}")
                st.metric(label="Último Mes", value=f"{last_val:.2f}")
        
        st.markdown("---")
        st.subheader("📊 Visualización")

        chart_options = ('Lado a Lado', 'Combinado') if len(selected) > 1 else ('Línea', 'Barras')
        display_mode = 'Línea'
        if len(selected) > 1:
            display_mode = st.radio("Elige cómo mostrar los gráficos:", chart_options, horizontal=True, key=f"display_{section_title}")
        
        chart_type = st.radio("Elige el tipo de gráfico:", ('Línea', 'Barras'), horizontal=True, key=f"radio_{section_title}")

        if len(selected) > 1 and display_mode == 'Combinado':
            combined_df = pd.concat(all_plot_data)
            fig = px.line(combined_df, x='Mes', y='Valor_Num', color='Métrica', markers=True,
                          color_discrete_map={'Usuarios totales de la app': 'gold', 'Tasa de crecimiento mensual de usuarios totales (acumulados)': 'darkorange'})
            fig.update_traces(hovertemplate="<b>%{data.name}</b><br><b>Mes:</b> %{x}<br><b>Valor:</b> %{y:.2f}<extra></extra>")
            fig.update_layout(height=400, xaxis_title=None, yaxis_title=None, plot_bgcolor='rgba(0,0,0,0)',
                              xaxis=dict(tickfont=dict(size=16, color='black')),
                              yaxis=dict(tickfont=dict(size=16, color='black')),
                              hoverlabel=dict(bgcolor="black",font_size=16,font_color="white"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            viz_cols = st.columns(len(all_plot_data))
            for i, plot_df in enumerate(all_plot_data):
                with viz_cols[i]:
                    metric_name = plot_df['Métrica'].iloc[0]
                    st.markdown(f"**{metric_name}**")
                    if chart_type == 'Línea':
                        fig = px.line(plot_df, x='Mes', y='Valor_Num', markers=True)
                        fig.update_traces(line=dict(width=4, color='gold'), marker=dict(size=8, color='darkorange'),
                                          hovertemplate="<b>Mes:</b> %{x}<br><b>Valor:</b> %{y:.2f}<extra></extra>",
                                          hoverlabel=dict(bgcolor="black", font_size=16, font_color="white"))
                    else:
                        fig = px.bar(plot_df, x='Mes', y='Valor_Num')
                        fig.update_traces(marker_color='gold',
                                          hovertemplate="<b>Mes:</b> %{x}<br><b>Valor:</b> %{y:.2f}<extra></extra>",
                                          hoverlabel=dict(bgcolor="black", font_size=16, font_color="white"))
                    fig.update_layout(height=300, xaxis_title=None, yaxis_title=None, plot_bgcolor='rgba(0,0,0,0)',
                                      xaxis=dict(tickfont=dict(size=16, color='black')),
                                      yaxis=dict(tickfont=dict(size=16, color='black')))
                    st.plotly_chart(fig, use_container_width=True)

# CUERPO PRINCIPAL DEL DASHBOARD
try:
    image = Image.open('assets/images1.jpeg')
    st.image(image, width=400) 
except FileNotFoundError:
    st.warning("Advertencia: No se encontró el logo en 'assets/images.jpeg'.")

st.title("📊 Indicadores Internos")
st.markdown("Este dashboard se conecta directamente a tu Google Sheet. Los datos se actualizan cada 10 minutos.")

tab_names = ["📊 Alcance", "🧩 Uso y Participación", "💬 Retroalimentación", "🏛️ Valor Público"]
tab1, tab2, tab3, tab4 = st.tabs(tab_names)

with tab1:
    df_alcance = load_data_from_gsheet("Alcance")
    create_interactive_section(df_alcance, "Alcance")
with tab2:
    df_uso = load_data_from_gsheet("Uso y Participación")
    create_interactive_section(df_uso, "Uso y Participación")
with tab3:
    df_retro = load_data_from_gsheet("Retroalimentación")
    create_interactive_section(df_retro, "Retroalimentación")
with tab4:
    df_valor = load_data_from_gsheet("Valor Público")
    create_interactive_section(df_valor, "Valor Público / Ahorro")