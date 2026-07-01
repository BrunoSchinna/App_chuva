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
# CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Dados Históricas e previsão climática", page_icon="🌍", layout="wide")
st.markdown("<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} div.block-container {padding-top: 2rem;}</style>", unsafe_allow_html=True)

st.title("🌍 Sistema de informações climáticas")
st.markdown("**Sistema Extração Hidrometeorológica (Chuva, Temp e Vento)**")
st.divider()

# ==========================================
# MEMÓRIA DO APP
# ==========================================
if "lat" not in st.session_state: st.session_state.lat = -25.4200
if "lon" not in st.session_state: st.session_state.lon = -49.2700
if "rolar_tela" not in st.session_state: st.session_state.rolar_tela = False

# ==========================================
# MENU LATERAL (BULLETPROOF)
# ==========================================
with st.sidebar:
    st.header("⚙️ Painel de Controle")
    st.markdown("Apenas **clique diretamente no mapa** ou digite abaixo:")
    
    col1, col2 = st.columns(2)
    lat_input = col1.number_input("Lat", value=st.session_state.lat, format="%.4f")
    lon_input = col2.number_input("Lon", value=st.session_state.lon, format="%.4f")

    if lat_input != st.session_state.lat or lon_input != st.session_state.lon:
        st.session_state.lat = lat_input
        st.session_state.lon = lon_input
        st.session_state.rolar_tela = True
        st.rerun()

    st.markdown("---")
    var_hist = st.checkbox("🌧️ Histórico (ERA5)", value=True)
    var_prev = st.checkbox("🔮 Previsão & Voo (GFS)", value=True)

# ==========================================
# MOTOR DE BUSCA (API)
# ==========================================
@st.cache_data(show_spinner=False, ttl=3600)
def extrair_dados(lat, lon, hist, prev):
    df_hist = pd.DataFrame()
    df_prev = pd.DataFrame()
    altitude = "N/A"
    
    if hist:
        hoje = datetime.date.today()
        fim = hoje - datetime.timedelta(days=5)
        url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date=1981-01-01&end_date={fim}&daily=precipitation_sum,temperature_2m_mean&timezone=America%2FSao_Paulo"
        r = requests.get(url)
        if r.status_code == 200:
            d = r.json()
            altitude = d.get('elevation', 'N/A')
            df_bruto = pd.DataFrame({
                'Data': pd.to_datetime(d['daily']['time']),
                'Chuva': d['daily']['precipitation_sum'],
                'Temp': d['daily']['temperature_2m_mean']
            }).set_index('Data')
            df_hist = df_bruto.resample('MS').agg({'Chuva': lambda x: x.sum(min_count=1), 'Temp': 'mean'}).reset_index()

    if prev:
        # AGORA PUXAMOS O VENTO TAMBÉM (wind_speed_10m_max e wind_gusts_10m_max)
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=precipitation_sum,temperature_2m_max,temperature_2m_min,wind_speed_10m_max,wind_gusts_10m_max&timezone=America%2FSao_Paulo&past_days=7&forecast_days=16"
        r = requests.get(url)
        if r.status_code == 200:
            d = r.json()
            if altitude == "N/A": 
                altitude = d.get('elevation', 'N/A')
            df_prev = pd.DataFrame({
                'Data': pd.to_datetime(d['daily']['time']),
                'Chuva': d['daily']['precipitation_sum'],
                'Temp_Max': d['daily']['temperature_2m_max'],
                'Temp_Min': d['daily']['temperature_2m_min'],
                'Vento_Max_kmh': d['daily']['wind_speed_10m_max'],
                'Rajadas_kmh': d['daily']['wind_gusts_10m_max']
            })
            
    return df_hist, df_prev, altitude

if var_hist or var_prev:
    with st.spinner("Conectando aos servidores ERA5 e GFS..."):
        df_historico, df_previsao, altitude_local = extrair_dados(st.session_state.lat, st.session_state.lon, var_hist, var_prev)
else:
    st.warning("Selecione os dados no painel lateral.")
    st.stop()

# ==========================================
# PAINEL DE ALERTAS INTELIGENTES (CHUVA E VOO)
# ==========================================
hoje_ts = pd.Timestamp.today().normalize()
if not df_previsao.empty:
    df_proximos = df_previsao[(df_previsao['Data'] >= hoje_ts) & (df_previsao['Data'] <= (hoje_ts + pd.Timedelta(days=5)))]
    chuva_curto_prazo = df_proximos['Chuva'].sum()
    rajada_max = df_proximos['Rajadas_kmh'].max()
    
    if chuva_curto_prazo > 60:
        st.error(f"🚨 **ALERTA CHUVA:** Previsão de alto volume ({chuva_curto_prazo:.1f} mm) para os próximos 5 dias neste local!")
    
    # Alerta especial para Drones se o vento passar de 40 km/h
    if rajada_max > 40:
        st.warning(f"🚁 **ALERTA DE VOO (DRONES):** Rajadas de vento perigosas previstas ({rajada_max:.1f} km/h) nos próximos dias. Risco alto de perda de sinal ou queda!")

# ==========================================
# MAPA E PLACAR
# ==========================================
col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("📍 Latitude", f"{st.session_state.lat:.4f}")
col_m2.metric("📍 Longitude", f"{st.session_state.lon:.4f}")
col_m3.metric("⛰️ Altitude do Terreno", f"{altitude_local} m" if altitude_local != "N/A" else "N/A")

# Mapa limpo e garantido que funciona o clique
mapa = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=11)
folium.TileLayer('https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google', name='Google Híbrido').add_to(mapa)
folium.Marker([st.session_state.lat, st.session_state.lon], icon=folium.Icon(color="red")).add_to(mapa)

mapa_clicado = st_folium(mapa, height=800, use_container_width=True, returned_objects=["last_clicked"])
if mapa_clicado.get("last_clicked"):
    if mapa_clicado["last_clicked"]["lat"] != st.session_state.lat:
        st.session_state.lat = mapa_clicado["last_clicked"]["lat"]
        st.session_state.lon = mapa_clicado["last_clicked"]["lng"]
        st.session_state.rolar_tela = True
        st.rerun()

st.markdown("<div id='area_resultados'></div>", unsafe_allow_html=True)

# ==========================================
# SEÇÃO DE ABAS
# ==========================================
tab1, tab2, tab3 = st.tabs(["📈 Histórico ERA5 (1981-Atual)", "⏪ Passado Recente (Últimos 7 dias)", "🔮 Previsão"])
layout_transparente = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")

# ABA 1: HISTÓRICO
with tab1:
    if not df_historico.empty:
        st.markdown("#### Histórico Mensal de Precipitação")
        fig1 = px.line(df_historico, x='Data', y='Chuva', color_discrete_sequence=['#3498db'])
        fig1.update_traces(connectgaps=False)
        fig1.update_layout(**layout_transparente, yaxis=dict(gridcolor='rgba(128,128,128,0.2)'))
        st.plotly_chart(fig1, use_container_width=True)
        
        st.markdown("#### Temperatura Média Mensal")
        fig2 = px.line(df_historico, x='Data', y='Temp', color_discrete_sequence=['#e74c3c'])
        fig2.update_layout(**layout_transparente, yaxis=dict(gridcolor='rgba(128,128,128,0.2)'))
        st.plotly_chart(fig2, use_container_width=True)

# ABA 2: ÚLTIMOS 7 DIAS
with tab2:
    if not df_previsao.empty:
        df_7dias = df_previsao[(df_previsao['Data'] >= (hoje_ts - pd.Timedelta(days=7))) & (df_previsao['Data'] < hoje_ts)].copy()
        chuva_acumulada_7d = df_7dias['Chuva'].sum()
        
        st.metric(label="Total Chovido na Última Semana", value=f"{chuva_acumulada_7d:.1f} mm")
        st.divider()
        
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.markdown("**Chuva por Dia**")
            fig3 = px.bar(df_7dias, x='Data', y='Chuva', text_auto='.1f', color_discrete_sequence=['#2ecc71'])
            fig3.update_layout(**layout_transparente, yaxis=dict(gridcolor='rgba(128,128,128,0.2)'))
            st.plotly_chart(fig3, use_container_width=True)
        with col_g2:
            st.markdown("**Temperaturas Alcançadas**")
            fig4 = go.Figure()
            fig4.add_trace(go.Scatter(x=df_7dias['Data'], y=df_7dias['Temp_Max'], name='Máx', line=dict(color='#e74c3c')))
            fig4.add_trace(go.Scatter(x=df_7dias['Data'], y=df_7dias['Temp_Min'], name='Mín', line=dict(color='#3498db')))
            fig4.update_layout(**layout_transparente, yaxis=dict(gridcolor='rgba(128,128,128,0.2)'), legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig4, use_container_width=True)
            
        st.divider()
        st.markdown("#### Velocidade do Vento e Rajadas (km/h) 🚁")
        fig_vento_7d = go.Figure()
        fig_vento_7d.add_trace(go.Scatter(x=df_7dias['Data'], y=df_7dias['Rajadas_kmh'], name='Rajadas (Pico)', line=dict(color='#e67e22', width=2, dash='dot')))
        fig_vento_7d.add_trace(go.Bar(x=df_7dias['Data'], y=df_7dias['Vento_Max_kmh'], name='Vento Constante', marker_color='#f1c40f', opacity=0.6))
        fig_vento_7d.update_layout(**layout_transparente, yaxis=dict(gridcolor='rgba(128,128,128,0.2)'), hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
        st.plotly_chart(fig_vento_7d, use_container_width=True)

# ABA 3: PREVISÃO E VOO
with tab3:
    if not df_previsao.empty:
        df_futuro = df_previsao[df_previsao['Data'] >= hoje_ts].copy()
        
        st.markdown("#### Previsão Diária de Chuva")
        fig5 = px.bar(df_futuro, x='Data', y='Chuva', text_auto='.1f', color_discrete_sequence=['#2ecc71'])
        fig5.update_layout(**layout_transparente, yaxis=dict(gridcolor='rgba(128,128,128,0.2)'))
        st.plotly_chart(fig5, use_container_width=True)
        
        st.divider()
        
        col_prev1, col_prev2 = st.columns(2)
        with col_prev1:
            st.markdown("#### Previsão de Temperatura")
            fig6 = go.Figure()
            fig6.add_trace(go.Scatter(x=df_futuro['Data'], y=df_futuro['Temp_Max'], name='Máx', line=dict(color='#e74c3c', width=3)))
            fig6.add_trace(go.Scatter(x=df_futuro['Data'], y=df_futuro['Temp_Min'], name='Mín', line=dict(color='#3498db', width=3)))
            fig6.update_layout(**layout_transparente, yaxis=dict(gridcolor='rgba(128,128,128,0.2)'), hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig6, use_container_width=True)
            
        with col_prev2:
            st.markdown("#### Previsão de Ventos")
            fig_vento_prev = go.Figure()
            fig_vento_prev.add_trace(go.Scatter(x=df_futuro['Data'], y=df_futuro['Rajadas_kmh'], name='Rajadas Perigosas', mode='lines+markers', line=dict(color='#e67e22', width=2, dash='dot')))
            fig_vento_prev.add_trace(go.Bar(x=df_futuro['Data'], y=df_futuro['Vento_Max_kmh'], name='Vento Constante', marker_color='#f1c40f', opacity=0.6))
            fig_vento_prev.update_layout(**layout_transparente, yaxis=dict(gridcolor='rgba(128,128,128,0.2)'), hovermode="x unified", legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1))
            st.plotly_chart(fig_vento_prev, use_container_width=True)

# ==========================================
# EXPORTAÇÃO EXCEL E RODAPÉ
# ==========================================
if not df_historico.empty or not df_previsao.empty:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        if not df_historico.empty:
            df_historico.to_excel(writer, sheet_name="Historico_Mensal", index=False)
        if not df_previsao.empty:
            df_previsao.to_excel(writer, sheet_name="Previsao_e_Passado", index=False)
            
    st.divider()
    col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
    with col_btn2:
        st.download_button("💾 BAIXAR DADOS EM EXCEL", data=buffer.getvalue(), file_name="SIG_Climatico_Export.xlsx", type="primary", use_container_width=True)

if st.session_state.rolar_tela:
    components.html("<script>setTimeout(function(){window.parent.document.getElementById('area_resultados').scrollIntoView({behavior:'smooth'});}, 300);</script>", height=0)
    st.session_state.rolar_tela = False

st.divider()
st.markdown(
    """
    <div style='text-align: center; font-size: 0.85em; color: #7f8c8d;'>
        <b>📚 Referências de Dados e Licenças Tecnológicas:</b><br><br>
        Os dados hidrometeorológicos deste aplicativo são agregados e fornecidos via 
        <a href='https://open-meteo.com/' target='_blank' style='color: #7f8c8d; text-decoration: none;'><b>Open-Meteo API</b></a> (Licença CC BY 4.0).<br>
        • <b>Dados Históricos:</b> Contém informações modificadas do programa europeu <i>Copernicus Climate Change Service</i> (Reanálise ERA5).<br>
        • <b>Dados de Previsão:</b> Provenientes do modelo global GFS, mantido pela <i>NOAA / NCEP</i> (Estados Unidos).<br><br>
        <i>⚠️ Aviso Legal: O uso destes dados é indicado para consultas e estudos preliminares.</i>
    </div>
    """, 
    unsafe_allow_html=True
)
