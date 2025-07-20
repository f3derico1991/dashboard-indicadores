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
        gc = gspread.service_account(filename='nueva-clave.json')
        #gc = gspread.service_account_from_dict(st.secrets["google_credentials"])
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
    valor_str = plot_df['Valor'].astype(str)
    valor_limpio = valor_str.str.replace(',', '.', regex=False).str.replace('%', '', regex=False).str.strip()
    plot_df['Valor_Num'] = pd.to_numeric(valor_limpio, errors='coerce')
    plot_df.dropna(subset=['Valor_Num'], inplace=True)
    return plot_df

# Función auxiliar para generar un gráfico individual
def generate_single_figure(plot_df, chart_type, graph_index):
    metric_name = plot_df['Métrica'].iloc[0]
    color_palette = ['gold', 'SteelBlue', 'IndianRed']
    current_color = color_palette[graph_index % len(color_palette)]

    def get_hover_format(metric_name):
        if '%' in metric_name.lower() or 'tasa' in metric_name.lower():
            return "<b>Mes:</b> %{x}<br><b>Valor:</b> %{y:,.2f}%<extra></extra>".replace(",", "X").replace(".", ",").replace("X", ".")
        else:
            return "<b>Mes:</b> %{x}<br><b>Valor:</b> %{y:,.0f}<extra></extra>".replace(",", "X").replace(".", ",").replace("X", ".")
    hover_template = get_hover_format(metric_name)

    if chart_type == 'Línea':
        fig = px.line(plot_df, x='Mes', y='Valor_Num', markers=True)
        fig.update_traces(line=dict(width=4, color=current_color), marker=dict(size=8, color=current_color),
                          hovertemplate=hover_template, hoverlabel=dict(bgcolor="black", font_size=16, font_color="white"))
    else:
        fig = px.bar(plot_df, x='Mes', y='Valor_Num')
        fig.update_traces(marker_color=current_color, hovertemplate=hover_template, hoverlabel=dict(bgcolor="black", font_size=16, font_color="white"))
    
    fig.update_layout(height=300, xaxis_title=None, yaxis_title=None, plot_bgcolor='rgba(0,0,0,0)',
                      xaxis=dict(tickfont=dict(size=16, color='black')),
                      yaxis=dict(tickfont=dict(size=16, color='black'), tickformat=",.0f", showgrid=True, gridcolor='LightGray'))
    return fig

# FUNCIÓN REUTILIZABLE PARA CREAR LA SECCIÓN INTERACTIVA
def create_interactive_section(df, section_title):
    st.header(section_title)
    if df is None or df.empty: return
    if 'Métrica' not in df.columns: return

    all_months = [col for col in df.columns if col != 'Métrica']
    with st.expander("📅 Filtrar por Rango de Meses", expanded=False):
        selected_months = st.multiselect("Selecciona los meses:", options=all_months, default=all_months, key=f"ms_{section_title}")
    if not selected_months: st.warning("Debes seleccionar al menos un mes."); return
    filtered_df = df[['Métrica'] + selected_months]

    gb = GridOptionsBuilder.from_dataframe(filtered_df)
    gb.configure_selection('multiple', use_checkbox=True, rowMultiSelectWithClick=True)
    gb.configure_grid_options(domLayout='autoHeight')
    gridOptions = gb.build()

    st.info("Selecciona hasta 3 filas en la tabla para generar gráficos.")
    grid_response = AgGrid(filtered_df, gridOptions=gridOptions, update_mode=GridUpdateMode.MODEL_CHANGED,
                           data_return_mode=DataReturnMode.AS_INPUT, allow_unsafe_jscode=True, theme='streamlit', key=f"grid_{section_title}")

    selected = pd.DataFrame(grid_response['selected_rows'])
    
    if not selected.empty:
        if st.button("🔄 Limpiar Selección", key=f"clear_{section_title}"): st.rerun()
        st.markdown("---")
        
        selected_to_show = selected.head(3)
        all_plot_data = [prepare_metric_data(pd.DataFrame([row])) for _, row in selected_to_show.iterrows()]
        all_plot_data = [df for df in all_plot_data if not df.empty]

        if not all_plot_data: st.warning("Las métricas seleccionadas no tienen datos válidos para mostrar."); return
        
        st.subheader("📈 Estadísticas Clave")
        stats_data_transposed = {}
        for plot_df in all_plot_data:
            metric_name = plot_df['Métrica'].iloc[0]
            stats_data_transposed[metric_name] = {"Promedio": plot_df['Valor_Num'].mean(), "Máximo": plot_df['Valor_Num'].max(),
                                                   "Mínimo": plot_df['Valor_Num'].min(), "Último Mes": plot_df['Valor_Num'].iloc[-1]}
        
        if stats_data_transposed:
            stats_df = pd.DataFrame(stats_data_transposed)
            stats_df.index.name = "Estadística"
            styled_df = stats_df.style.format(format_number_es)\
                                      .background_gradient(cmap='YlGnBu', axis=1)\
                                      .set_properties(**{'text-align': 'right', 'padding-right': '10px'})\
                                      .set_table_styles([{'selector': 'th', 'props': [('text-align', 'center'), ('font-weight', 'bold')]},
                                                         {'selector': 'th.row_heading', 'props': [('text-align', 'left'), ('font-weight', 'bold')]},
                                                         {'selector': 'td, th', 'props': [('border', '1px solid #ddd')]}])\
                                      .set_table_attributes('style="width:100%; border-collapse: collapse;"')
            st.markdown(styled_df.to_html(), unsafe_allow_html=True)
        
        st.markdown("---")
        st.subheader("📊 Visualización")

        display_mode = "Separadas"
        if len(all_plot_data) > 1:
            display_mode = st.radio("Modo de visualización:", ("Separadas", "Juntas"), horizontal=True, key=f"disp_{section_title}")
        
        chart_type = st.radio("Elige el tipo de gráfico:", ('Línea', 'Barras'), horizontal=True, key=f"radio_type_{section_title}")

        # ---> BLOQUE if/else CORREGIDO <---
        if display_mode == "Juntas" and len(all_plot_data) > 1:
            st.markdown(f"**Comparando {len(all_plot_data)} métricas**")
            combined_df = pd.concat(all_plot_data)
            color_map = {combined_df['Métrica'].unique()[0]: 'gold', combined_df['Métrica'].unique()[1]: '#1f2c38'}
            if len(combined_df['Métrica'].unique()) > 2:
                 color_map[combined_df['Métrica'].unique()[2]] = 'IndianRed'
            
            fig = None
            if chart_type == 'Barras':
                fig = px.bar(combined_df, x='Mes', y='Valor_Num', color='Métrica', barmode='group',
                             text_auto=True, color_discrete_map=color_map)
                fig.update_traces(texttemplate='%{y:,.0f}'.replace(",", "."), textposition='outside', textfont_size=14)
            else:
                fig = px.line(combined_df, x='Mes', y='Valor_Num', color='Métrica', markers=True, color_discrete_map=color_map)
                fig.update_traces(hovertemplate="<b>%{data.name}</b><br><b>Mes:</b> %{x}<br><b>Valor:</b> %{y:,.2f}<extra></extra>".replace(",","."),
                                  hoverlabel=dict(bgcolor="black",font_size=16,font_color="white"))

            max_y = combined_df['Valor_Num'].max()
            fig.update_layout(height=450, plot_bgcolor='whitesmoke', yaxis_title="Cantidad", xaxis_title=None,
                              legend_title_text='', legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                              yaxis=dict(range=[0, max_y * 1.15], dtick=2500, tickfont=dict(size=14), showgrid=True, gridcolor='LightGray'),
                              xaxis=dict(tickfont=dict(size=14)))
            st.plotly_chart(fig, use_container_width=True)
        
        else: # Modo Separadas o una sola métrica
            num_plots = len(all_plot_data)
            
            if num_plots == 1:
                # Para un solo gráfico, lo centramos para que no ocupe todo el ancho.
                _, viz_col, _ = st.columns([0.5, 3, 0.5])
                plot_containers = [viz_col]
            else: # 2 o 3 gráficos
                plot_containers = st.columns(num_plots)

            for i, plot_df in enumerate(all_plot_data):
                with plot_containers[i]:
                    metric_name = plot_df['Métrica'].iloc[0]
                    st.markdown(f"**{metric_name}**")
                    fig = generate_single_figure(plot_df, chart_type, i)
                    st.plotly_chart(fig, use_container_width=True)

# CUERPO PRINCIPAL DEL DASHBOARD
col1, col2 = st.columns([1, 4]) 
with col1:
    try:
        image = Image.open('assets/Logo-mas-simple.png')
        st.image(image, width=150)
    except FileNotFoundError:
        st.warning("Logo no encontrado.")
with col2:
    st.title("Indicadores Internos")
    st.markdown("Dashboard interactivo con actualización automática desde Google Sheets.")

st.markdown("---")

tab_names = ["📊 Alcance", "🧩 Uso y Participación", "💬 Retroalimentación", "🏛️ Valor Público"]
tab1, tab2, tab3, tab4 = st.tabs(tab_names)

with tab1: create_interactive_section(load_data_from_gsheet("Alcance"), "Alcance")
with tab2: create_interactive_section(load_data_from_gsheet("Uso y Participación"), "Uso y Participación")
with tab3: create_interactive_section(load_data_from_gsheet("Retroalimentación"), "Retroalimentación")
with tab4: create_interactive_section(load_data_from_gsheet("Valor Público"), "Valor Público / Ahorro")