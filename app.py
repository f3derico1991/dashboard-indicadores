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

# Función para formatear números al estilo español
def format_number_es(num):
    if pd.isna(num): return "N/A"
    return f"{num:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# FUNCIÓN AUXILIAR PARA PREPARAR DATOS
def prepare_metric_data(metric_df):
    plot_df = metric_df.melt(id_vars=['Métrica'], var_name='Mes', value_name='Valor')
    plot_df['Valor_Num'] = plot_df['Valor'].astype(str).str.replace('%', '', regex=False).str.strip()
    plot_df['Valor_Num'] = pd.to_numeric(plot_df['Valor_Num'], errors='coerce')
    plot_df.dropna(subset=['Valor_Num'], inplace=True)
    return plot_df

# Función auxiliar para generar un gráfico individual
def generate_single_figure(plot_df, chart_type):
    metric_name = plot_df['Métrica'].iloc[0]
    
    def get_hover_format(metric_name):
        if '%' in metric_name.lower() or 'tasa' in metric_name.lower():
            return "<b>Mes:</b> %{x}<br><b>Valor:</b> %{y:,.2f}%<extra></extra>".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            return "<b>Mes:</b> %{x}<br><b>Valor:</b> %{y:,.0f}<extra></extra>".replace(",", "X").replace(".", ",").replace("X", ".")
    
    hover_template = get_hover_format(metric_name)

    if chart_type == 'Línea':
        fig = px.line(plot_df, x='Mes', y='Valor_Num', markers=True)
        fig.update_traces(line=dict(width=4, color='gold'), marker=dict(size=8, color='darkorange'),
                          hovertemplate=hover_template, hoverlabel=dict(bgcolor="black", font_size=16, font_color="white"))
    else: # Barras
        fig = px.bar(plot_df, x='Mes', y='Valor_Num')
        fig.update_traces(marker_color='gold', hovertemplate=hover_template, hoverlabel=dict(bgcolor="black", font_size=16, font_color="white"))
    
    fig.update_layout(height=300, xaxis_title=None, yaxis_title=None, plot_bgcolor='rgba(0,0,0,0)',
                      xaxis=dict(tickfont=dict(size=16, color='black')),
                      yaxis=dict(tickfont=dict(size=16, color='black'), tickformat=",.0f", showgrid=True, gridcolor='LightGray'))
    return fig

# FUNCIÓN REUTILIZABLE PARA CREAR LA SECCIÓN INTERACTIVA
def create_interactive_section(df, section_title):
    st.header(section_title)
    if df is None or df.empty: return
    if 'Métrica' not in df.columns: return

    # Filtro de Meses
    all_months = [col for col in df.columns if col != 'Métrica']
    with st.expander("📅 Filtrar por Rango de Meses", expanded=False):
        selected_months = st.multiselect("Selecciona los meses:", options=all_months, default=all_months, key=f"ms_{section_title}")
    if not selected_months: st.warning("Debes seleccionar al menos un mes."); return
    filtered_df = df[['Métrica'] + selected_months]

    # Configuración de AgGrid
    gb = GridOptionsBuilder.from_dataframe(filtered_df)
    gb.configure_selection('multiple', use_checkbox=True, rowMultiSelectWithClick=True)
    gb.configure_grid_options(domLayout='autoHeight')
    gridOptions = gb.build()

    st.info("Selecciona hasta 2 filas en la tabla para generar gráficos.")
    grid_response = AgGrid(filtered_df, gridOptions=gridOptions, update_mode=GridUpdateMode.MODEL_CHANGED,
                           data_return_mode=DataReturnMode.AS_INPUT, allow_unsafe_jscode=True, theme='streamlit', key=f"grid_{section_title}")

    selected = pd.DataFrame(grid_response['selected_rows'])
    
    if not selected.empty:
        if st.button("🔄 Limpiar Selección", key=f"clear_{section_title}"): st.rerun()
        st.markdown("---")
        
        selected_to_show = selected.head(2)
        all_plot_data = [prepare_metric_data(pd.DataFrame([row])) for _, row in selected_to_show.iterrows()]
        all_plot_data = [df for df in all_plot_data if not df.empty]

        if not all_plot_data: st.warning("Las métricas seleccionadas no tienen datos válidos para mostrar."); return
        
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
                st.metric(label="Promedio", value=format_number_es(avg_val))
                st.metric(label="Máximo", value=format_number_es(max_val))
                st.metric(label="Mínimo", value=format_number_es(min_val))
                st.metric(label="Último Mes", value=format_number_es(last_val))
        
        st.markdown("---")
        st.subheader("📊 Visualización")

        # --- LÓGICA DE VISUALIZACIÓN CON FLEXIBILIDAD TOTAL ---
        display_mode = "Separadas"
        # Mostramos los selectores de modo y tipo
        if len(all_plot_data) == 2:
            display_mode = st.radio("Modo de visualización:", ("Separadas", "Juntas"), horizontal=True, key=f"disp_{section_title}")
        
        chart_type = st.radio("Elige el tipo de gráfico:", ('Línea', 'Barras'), horizontal=True, key=f"radio_type_{section_title}")

        # --- MODO JUNTAS (COMPARACIÓN) ---
        if display_mode == "Juntas" and len(all_plot_data) == 2:
            st.markdown(f"**Comparando: {all_plot_data[0]['Métrica'].iloc[0]} vs. {all_plot_data[1]['Métrica'].iloc[0]}**")
            combined_df = pd.concat(all_plot_data)
            color_map = {combined_df['Métrica'].unique()[0]: 'gold', combined_df['Métrica'].unique()[1]: '#1f2c38'}

            fig = None
            if chart_type == 'Barras':
                fig = px.bar(combined_df, x='Mes', y='Valor_Num', color='Métrica', barmode='group',
                             text_auto=True, color_discrete_map=color_map)
                fig.update_traces(texttemplate='%{y:,.0f}'.replace(",", "."), textposition='outside', textfont_size=14)
            else: # Línea
                fig = px.line(combined_df, x='Mes', y='Valor_Num', color='Métrica', markers=True,
                              color_discrete_map=color_map)
                fig.update_traces(hovertemplate="<b>%{data.name}</b><br><b>Mes:</b> %{x}<br><b>Valor:</b> %{y:,.2f}<extra></extra>".replace(",","."),
                                  hoverlabel=dict(bgcolor="black",font_size=16,font_color="white"))

            max_y = combined_df['Valor_Num'].max()
            fig.update_layout(
                height=450,
                plot_bgcolor='whitesmoke',
                yaxis_title="Cantidad",
                xaxis_title=None,
                legend_title_text='',
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                yaxis=dict(
                    range=[0, max_y * 1.15], dtick=2500, tickfont=dict(size=14),
                    showgrid=True, gridcolor='LightGray'
                ),
                xaxis=dict(tickfont=dict(size=14))
            )
            st.plotly_chart(fig, use_container_width=True)

        # --- MODO SEPARADAS (O UNA SOLA MÉTRICA) ---
        else:
            viz_cols = st.columns(len(all_plot_data))
            for i, plot_df in enumerate(all_plot_data):
                with viz_cols[i]:
                    metric_name = plot_df['Métrica'].iloc[0]
                    st.markdown(f"**{metric_name}**")
                    fig = generate_single_figure(plot_df, chart_type)
                    st.plotly_chart(fig, use_container_width=True)

# CUERPO PRINCIPAL DEL DASHBOARD
try:
    image = Image.open('assets/images1.jpeg')
    st.image(image, width=400) 
except FileNotFoundError:
    st.warning("Advertencia: No se encontró el logo en 'assets/images1.jpeg'.")

st.title("📊 Indicadores Internos")

tab_names = ["📊 Alcance", "🧩 Uso y Participación", "💬 Retroalimentación", "🏛️ Valor Público"]
tab1, tab2, tab3, tab4 = st.tabs(tab_names)

with tab1:
    create_interactive_section(load_data_from_gsheet("Alcance"), "Alcance")
with tab2:
    create_interactive_section(load_data_from_gsheet("Uso y Participación"), "Uso y Participación")
with tab3:
    create_interactive_section(load_data_from_gsheet("Retroalimentación"), "Retroalimentación")
with tab4:
    create_interactive_section(load_data_from_gsheet("Valor Público"), "Valor Público - Ahorro")