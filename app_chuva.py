import streamlit as st
import pandas as pd
import requests
import datetime
import io
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go
import streamlit.components.v1 as components

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E CSS
# ==========================================
st.set_page_config(page_title="SIG Climático Pro", page_icon="🌤️", layout="wide")

estilo_customizado = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    div.block-container {
        padding-top: 2rem;
    }
    </style>
"""
st.markdown(estilo_customizado, unsafe_allow_html=True)

# ==========================================
# CABEÇALHO DO APP
# ==========================================
col_titulo, col_logo = st.columns([4, 1])
with col_titulo:
    st.title("🌤️ Rain Forecast - Seu aplicativo de histórico e previsão")
    st.markdown("**Sistema Extração Hidrometeorológica (Automático)**")
with col_logo:
    st.caption("v4.1 - Auto-Scroll & Temp Forecast")

st.divider()

# ==========================================
# MEMÓRIA DO APLICATIVO E STATUS DE SCROLL
# ==========================================
if "lat" not in st.session_state:
    st.session_state.lat = -25.4200
if "lon" not in st.session_state:
    st.session_state.lon = -49.2700
if "rolar_tela" not in st.session_state:
    st.session_state.rolar_tela = False

# ==========================================
# MENU LATERAL (Apenas Filtros, sem botão!)
# ==========================================
with st.sidebar:
    st.header("⚙️ Painel de Controle")
    st.markdown("Apenas **clique diretamente no mapa** e o sistema fará o resto.")
    
    col1, col2 = st.columns(2)
    with col1:
        lat_input = st.number_input("Latitude", value=st.session_state.lat, format="%.4f", step=0.1)
    with col2:
        lon_input = st.number_input("Longitude", value=st.session_state.lon, format="%.4f", step=0.1)

    if lat_input != st.session_state.lat or lon_input != st.session_state.lon:
        st.session_state.lat = lat_input
        st.session_state.lon = lon_input
        st.session_state.rolar_tela = True
        st.rerun()

    st.markdown("---")
    st.subheader("📊 Seleção de Dados")
    var_hist = st.checkbox("🌧️ Histórico Mensal (ERA5)", value=True)
    var_prev = st.checkbox("🔮 Previsão Diária (GFS + Temp)", value=True)
    
    st.markdown("---")
    st.markdown("<div style='font-size: 0.8em; color: gray;'>", unsafe_allow_html=True)
    st.markdown("📚 Fontes e Licenças:")
    st.markdown("-ERA5: Copernicus Climate Change Service (C3S).")
    st.markdown("-GFS: NOAA / NCEP.")
    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# MOTOR DE BUSCA COM CACHE (Super Rápido)
# ==========================================
@st.cache_data(show_spinner=False, ttl=3600)
def buscar_dados_api(lat, lon, quer_hist, quer_prev):
    df_h = pd.DataFrame()
    df_c = pd.DataFrame()
    df_p = pd.DataFrame()
    alt = "N/A"
    chuva_7_dias = 0.0
    
    if quer_hist:
        hoje = datetime.date.today()
        fim = hoje - datetime.timedelta(days=5)
        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date=1981-01-01&end_date={fim}&daily=precipitation_sum&timezone=America%2FSao_Paulo"
        r = requests.get(url)
        if r.status_code == 200:
            d = r.json()
            alt = f"{d.get('elevation', 'N/A')} m"
            df_bruto = pd.DataFrame({'Data': pd.to_datetime(d['daily']['time']), 'Chuva_Observada': d['daily']['precipitation_sum']}).set_index('Data')
            df_h = df_bruto.resample('MS').sum().reset_index()
            
            df_temp = df_bruto.copy()
            df_temp['Mes'] = df_temp.index.month
            df_soma = df_temp.groupby([df_temp.index.year, 'Mes'])['Chuva_Observada'].sum().reset_index()
            df_c = df_soma.groupby('Mes')['Chuva_Observada'].mean().reset_index()
            meses_nome = {1:'Jan', 2:'Fev', 3:'Mar', 4:'Abr', 5:'Mai', 6:'Jun', 7:'Jul', 8:'Ago', 9:'Set', 10:'Out', 11:'Nov', 12:'Dez'}
            df_c['Mês'] = df_c['Mes'].map(meses_nome)
            df_c.rename(columns={'Chuva_Observada': 'Media_Historica'}, inplace=True)
            
    if quer_prev:
        # Adicionado past_days=7 e dados de temperatura máxima e mínima
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=precipitation_sum,temperature_2m_max,temperature_2m_min&timezone=America%2FSao_Paulo&past_days=7&forecast_days=16"
        r = requests.get(url)
        if r.status_code == 200:
            d = r.json()
            if alt == "N/A": alt = f"{d.get('elevation', 'N/A')} m"
            df_p = pd.DataFrame({
                'Data': pd.to_datetime(d['daily']['time']), 
                'Chuva_Diaria': d['daily']['precipitation_sum'],
                'Temp_Max': d['daily']['temperature_2m_max'],
                'Temp_Min': d['daily']['temperature_2m_min']
            })
            df_p['Chuva_Acumulada'] = df_p['Chuva_Diaria'].cumsum()
            
            # Cálculo do acumulado dos últimos 7 dias (excluindo hoje)
            hoje_ts = pd.Timestamp.today().normalize()
            mask_7d = (df_p['Data'] >= (hoje_ts - pd.Timedelta(days=7))) & (df_p['Data'] < hoje_ts)
            chuva_7_dias = df_p.loc[mask_7d, 'Chuva_Diaria'].sum()
            
    return df_h, df_c, df_p, alt, chuva_7_dias

# ==========================================
# EXECUÇÃO AUTOMÁTICA DOS DADOS
# ==========================================
if var_hist or var_prev:
    with st.spinner("📡 Calculando e processando os dados para este local..."):
        df_historico, df_clima, df_previsao, elevacao, chuva_7_dias = buscar_dados_api(st.session_state.lat, st.session_state.lon, var_hist, var_prev)
else:
    st.warning("Selecione pelo menos um dado para análise no painel.")
    st.stop()

# ==========================================
# PAINEL DE MÉTRICAS SUPERIOR
# ==========================================
col_m1, col_m2, col_m3, col_m4 = st.columns([1, 1, 1, 1])
col_m1.metric(label="Latitude Ativa", value=f"{st.session_state.lat:.4f}")
col_m2.metric(label="Longitude Ativa", value=f"{st.session_state.lon:.4f}")
col_m3.metric(label="Altitude Local", value=elevacao)
col_m4.metric(label="Chuva (Últimos 7 dias)", value=f"{chuva_7_dias:.1f} mm")

# ==========================================
# MAPA INTERATIVO (O GATILHO)
# ==========================================
mapa = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=11, control_scale=True)
folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Google Híbrido'
).add_to(mapa)
folium.Marker([st.session_state.lat, st.session_state.lon], icon=folium.Icon(color="red", icon="cloud", prefix='fa')).add_to(mapa)

mapa_resultado = st_folium(mapa, height=800, use_container_width=True, returned_objects=["last_clicked"])

# Se clicar no mapa, atualiza coordenada e pede para rolar a tela!
if mapa_resultado.get("last_clicked"):
    click_lat = mapa_resultado["last_clicked"]["lat"]
    click_lon = mapa_resultado["last_clicked"]["lng"]
    if click_lat != st.session_state.lat or click_lon != st.session_state.lon:
        st.session_state.lat = click_lat
        st.session_state.lon = click_lon
        st.session_state.rolar_tela = True
        st.rerun()

# ==========================================
# ANCORA DE ROLAGEM INVISÍVEL
# ==========================================
st.markdown("<div id='area_resultados'></div>", unsafe_allow_html=True)

# ==========================================
# GRÁFICOS E RESULTADOS
# ==========================================
tab1, tab2 = st.tabs(["📈 Histórico e Climatologia", "🔮 Previsão de Chuva e Temp"])

with tab1:
    if not df_historico.empty:
        st.markdown("#### Normal Climatológica (Média de 1981 a Hoje)")
        fig_clima = px.bar(df_clima, x='Mês', y='Media_Historica', text_auto='.1f', template="plotly_white")
        fig_clima.update_traces(marker_color='#34495e', textfont_size=12, textposition="outside", cliponaxis=False)
        st.plotly_chart(fig_clima, use_container_width=True)
        st.divider()
        st.markdown("#### Série Histórica Mensal Completa")
        fig_hist = px.line(df_historico, x='Data', y='Chuva_Observada', template="plotly_white")
        fig_hist.update_traces(line_color='#3498db', line_width=2)
        st.plotly_chart(fig_hist, use_container_width=True)

with tab2:
    if not df_previsao.empty:
        # Gráfico de Precipitação
        st.markdown("#### Hidrograma Meteorológico (Diário vs Acumulado)")
        fig_prev = go.Figure()
        fig_prev.add_trace(go.Bar(x=df_previsao['Data'], y=df_previsao['Chuva_Diaria'], name='Diária (mm)', marker_color='#2ecc71', text=df_previsao['Chuva_Diaria'].round(1), textposition='auto'))
        fig_prev.add_trace(go.Scatter(x=df_previsao['Data'], y=df_previsao['Chuva_Acumulada'], name='Acumulada (mm)', mode='lines+markers', line=dict(color='#e74c3c', width=3)))
        fig_prev.update_layout(template="plotly_white", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_prev, use_container_width=True)
        
        st.divider()
        
        # Gráfico de Temperatura (Novo)
        st.markdown("#### Previsão de Temperatura (Máxima e Mínima)")
        fig_temp = go.Figure()
        fig_temp.add_trace(go.Scatter(x=df_previsao['Data'], y=df_previsao['Temp_Max'], name='Máxima (°C)', mode='lines+markers', line=dict(color='#e74c3c', width=3)))
        fig_temp.add_trace(go.Scatter(x=df_previsao['Data'], y=df_previsao['Temp_Min'], name='Mínima (°C)', mode='lines+markers', line=dict(color='#3498db', width=3)))
        fig_temp.update_layout(template="plotly_white", hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_temp, use_container_width=True)

if not df_historico.empty or not df_previsao.empty:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        if not df_historico.empty:
            df_hist_save = df_historico.copy()
            df_hist_save['Data'] = df_hist_save['Data'].dt.strftime('%Y-%m')
            df_hist_save.to_excel(writer, sheet_name="Historico_ERA5", index=False)
            df_clima.round(2).to_excel(writer, sheet_name="Normal_Climatologica", index=False)
        if not df_previsao.empty:
            df_prev_save = df_previsao.copy()
            df_prev_save['Data'] = df_prev_save['Data'].dt.strftime('%Y-%m-%d')
            # A exportação agora inclui automaticamente as colunas Temp_Max e Temp_Min criadas
            df_prev_save.to_excel(writer, sheet_name="Previsao_GFS_e_Temp", index=False)
    
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        st.download_button("💾 BAIXAR DADOS EM EXCEL", data=buffer.getvalue(), file_name=f"Dados_Climaticos_{st.session_state.lat:.2f}_{st.session_state.lon:.2f}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", type="primary", use_container_width=True)

# ==========================================
# GATILHO DA ROLAGEM MÁGICA
# ==========================================
if st.session_state.rolar_tela:
    components.html(
        """
        <script>
        setTimeout(function() {
            var doc = window.parent.document;
            var element = doc.getElementById('area_resultados');
            if (element) {
                element.scrollIntoView({behavior: 'smooth', block: 'start'});
            }
        }, 300);
        </script>
        """, height=0
    )
    st.session_state.rolar_tela = False
