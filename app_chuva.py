import streamlit as st
import pandas as pd
import requests
import datetime
import io
import folium
from streamlit_folium import st_folium
import plotly.express as px
import plotly.graph_objects as go

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E CSS
# ==========================================
st.set_page_config(page_title="SIG Climático Pro", page_icon="🌤️", layout="wide")

estilo_customizado = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    .stButton>button {
        border-radius: 8px;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: scale(1.02);
    }
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
    st.title("🌤️ SIG Climático Pro")
    st.markdown("**Sistema Inteligente de Extração Hidrometeorológica (ERA5 + GFS)**")
with col_logo:
    st.caption("v3.0 - Dashboard Avançado")

st.divider()

# ==========================================
# MEMÓRIA DO APLICATIVO
# ==========================================
if "lat" not in st.session_state:
    st.session_state.lat = -25.4200
if "lon" not in st.session_state:
    st.session_state.lon = -49.2700
if "elevacao" not in st.session_state:
    st.session_state.elevacao = "Aguardando..."

# ==========================================
# MENU LATERAL (CONTROLES)
# ==========================================
with st.sidebar:
    st.header("⚙️ Painel de Controle")
    st.markdown("Defina o ponto de estudo abaixo ou **clique diretamente no mapa**.")
    
    col1, col2 = st.columns(2)
    with col1:
        lat_input = st.number_input("Latitude", value=st.session_state.lat, format="%.4f", step=0.1)
    with col2:
        lon_input = st.number_input("Longitude", value=st.session_state.lon, format="%.4f", step=0.1)

    if lat_input != st.session_state.lat or lon_input != st.session_state.lon:
        st.session_state.lat = lat_input
        st.session_state.lon = lon_input
        st.session_state.elevacao = "Aguardando..." # Reseta a altitude ao mudar de local
        st.rerun()

    st.markdown("---")
    st.subheader("📊 Seleção de Dados")
    var_hist = st.checkbox("🌧️ Histórico Mensal (ERA5)", value=True, help="Puxa dados desde 1981 até a semana atual.")
    var_prev = st.checkbox("🔮 Previsão Diária (GFS)", value=True, help="Puxa a previsão acumulada dos próximos 16 dias.")
    
    st.markdown("---")
    btn_extrair = st.button("🚀 INICIAR EXTRAÇÃO DA NUVEM", type="primary", use_container_width=True)

    # Créditos Legais
    st.markdown("---")
    st.markdown("<div style='font-size: 0.8em; color: gray;'>", unsafe_allow_html=True)
    st.markdown("<b>📚 Fontes e Licenças:</b>")
    st.markdown("- <b>ERA5:</b> Dados gerados pelo Copernicus Climate Change Service (C3S).")
    st.markdown("- <b>GFS:</b> Dados fornecidos em domínio público pela NOAA / NCEP.")
    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# CORPO PRINCIPAL (MAPA E DASHBOARD)
# ==========================================
col_metrica1, col_metrica2, col_metrica3, col_vazio = st.columns([1, 1, 1, 1])
with col_metrica1:
    st.metric(label="Latitude Ativa", value=f"{st.session_state.lat:.4f}")
with col_metrica2:
    st.metric(label="Longitude Ativa", value=f"{st.session_state.lon:.4f}")
with col_metrica3:
    st.metric(label="Altitude (Topografia)", value=f"{st.session_state.elevacao}")

# Criação do Mapa Base
mapa = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=11, control_scale=True)

folium.TileLayer(
    tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}',
    attr='Google',
    name='Google Híbrido',
    overlay=False,
    control=True
).add_to(mapa)

folium.Marker(
    [st.session_state.lat, st.session_state.lon],
    popup="Ponto de Extração",
    icon=folium.Icon(color="red", icon="cloud", prefix='fa')
).add_to(mapa)

mapa_resultado = st_folium(mapa, height=450, use_container_width=True, returned_objects=["last_clicked"])

if mapa_resultado.get("last_clicked"):
    click_lat = mapa_resultado["last_clicked"]["lat"]
    click_lon = mapa_resultado["last_clicked"]["lng"]
    
    if click_lat != st.session_state.lat or click_lon != st.session_state.lon:
        st.session_state.lat = click_lat
        st.session_state.lon = click_lon
        st.session_state.elevacao = "Aguardando..."
        st.rerun()

# ==========================================
# LÓGICA DE EXTRAÇÃO E RESULTADOS
# ==========================================
if btn_extrair:
    if not var_hist and not var_prev:
        st.warning("⚠️ Selecione pelo menos uma variável no menu lateral antes de prosseguir!")
    else:
        st.divider()
        with st.spinner("📡 Conectando aos supercomputadores globais... Aguarde."):
            df_historico = pd.DataFrame()
            df_clima = pd.DataFrame()
            df_previsao = pd.DataFrame()

            # 1. PUXA HISTÓRICO E CLIMATOLOGIA
            if var_hist:
                try:
                    hoje = datetime.date.today()
                    fim_historico = hoje - datetime.timedelta(days=5)
                    inicio_historico = "1981-01-01"

                    url_hist = f"https://archive-api.open-meteo.com/v1/archive?latitude={st.session_state.lat}&longitude={st.session_state.lon}&start_date={inicio_historico}&end_date={fim_historico}&daily=precipitation_sum&timezone=America%2FSao_Paulo"
                    resp_hist = requests.get(url_hist)
                    
                    if resp_hist.status_code == 200:
                        dados_hist = resp_hist.json()
                        
                        # Atualiza a altitude na memória do sistema
                        elevacao = dados_hist.get("elevation", "N/A")
                        st.session_state.elevacao = f"{elevacao} m"

                        df_bruto = pd.DataFrame({
                            'Data': pd.to_datetime(dados_hist['daily']['time']),
                            'Chuva_Observada': dados_hist['daily']['precipitation_sum']
                        })
                        df_bruto.set_index('Data', inplace=True)
                        
                        # Histórico Mensal Contínuo
                        df_historico = df_bruto.resample('MS').sum().reset_index()
                        
                        # Cálculo da Normal Climatológica (Média por Mês)
                        df_temp = df_bruto.copy()
                        df_temp['Mes'] = df_temp.index.month
                        # Agrupa por ano e mês, soma, depois tira a média de cada mês
                        df_soma_mensal = df_temp.groupby([df_temp.index.year, 'Mes'])['Chuva_Observada'].sum().reset_index()
                        df_clima = df_soma_mensal.groupby('Mes')['Chuva_Observada'].mean().reset_index()
                        
                        meses_nome = {1:'Jan', 2:'Fev', 3:'Mar', 4:'Abr', 5:'Mai', 6:'Jun', 7:'Jul', 8:'Ago', 9:'Set', 10:'Out', 11:'Nov', 12:'Dez'}
                        df_clima['Mês'] = df_clima['Mes'].map(meses_nome)
                        df_clima.rename(columns={'Chuva_Observada': 'Media_Historica'}, inplace=True)
                        
                except Exception as e:
                    st.error(f"❌ Erro ao baixar o histórico: {e}")

            # 2. PUXA PREVISÃO E CALCULA ACUMULADO
            if var_prev:
                try:
                    url_prev = f"https://api.open-meteo.com/v1/forecast?latitude={st.session_state.lat}&longitude={st.session_state.lon}&daily=precipitation_sum&timezone=America%2FSao_Paulo&forecast_days=16"
                    resp_prev = requests.get(url_prev)
                    
                    if resp_prev.status_code == 200:
                        dados_prev = resp_prev.json()
                        
                        if st.session_state.elevacao == "Aguardando...":
                            elevacao = dados_prev.get("elevation", "N/A")
                            st.session_state.elevacao = f"{elevacao} m"

                        df_previsao = pd.DataFrame({
                            'Data': pd.to_datetime(dados_prev['daily']['time']),
                            'Chuva_Diaria': dados_prev['daily']['precipitation_sum']
                        })
                        # Cria a curva acumulada somando os dias
                        df_previsao['Chuva_Acumulada'] = df_previsao['Chuva_Diaria'].cumsum()

                except Exception as e:
                    st.error(f"❌ Erro ao baixar a previsão: {e}")

            # ==========================================
            # APRESENTAÇÃO DOS GRÁFICOS COM PLOTLY
            # ==========================================
            st.success("✅ Download e Cálculos Hidrológicos concluídos!")
            
            # Força o Streamlit a recarregar a tela para atualizar a métrica de Altitude lá em cima
            if "ja_atualizou_altitude" not in st.session_state:
                st.session_state.ja_atualizou_altitude = True
                st.rerun()
            else:
                del st.session_state["ja_atualizou_altitude"]

            tab1, tab2 = st.tabs(["📈 Histórico e Climatologia", "🔮 Previsão (16 Dias)"])

            with tab1:
                if not df_historico.empty:
                    st.markdown("#### Normal Climatológica (Média de 1981 a Hoje)")
                    fig_clima = px.bar(df_clima, x='Mês', y='Media_Historica', text_auto='.1f', 
                                       labels={'Media_Historica': 'Chuva Esperada (mm)'}, 
                                       template="plotly_white")
                    fig_clima.update_traces(marker_color='#34495e', textfont_size=12, textangle=0, textposition="outside", cliponaxis=False)
                    st.plotly_chart(fig_clima, use_container_width=True)
                    
                    st.divider()

                    st.markdown("#### Série Histórica Mensal Completa")
                    fig_hist = px.line(df_historico, x='Data', y='Chuva_Observada', 
                                       labels={'Chuva_Observada': 'Chuva Total (mm)', 'Data': 'Ano'},
                                       template="plotly_white")
                    fig_hist.update_traces(line_color='#3498db', line_width=2)
                    st.plotly_chart(fig_hist, use_container_width=True)

            with tab2:
                if not df_previsao.empty:
                    st.markdown("#### Hidrograma Meteorológico (Diário vs Acumulado)")
                    
                    # Gráfico Combinado: Barras (Diário) + Linha (Acumulado)
                    fig_prev = go.Figure()
                    
                    # Barras de chuva diária
                    fig_prev.add_trace(go.Bar(
                        x=df_previsao['Data'], y=df_previsao['Chuva_Diaria'], 
                        name='Chuva Diária (mm)', marker_color='#2ecc71',
                        text=df_previsao['Chuva_Diaria'].round(1), textposition='auto'
                    ))
                    
                    # Linha de chuva acumulada
                    fig_prev.add_trace(go.Scatter(
                        x=df_previsao['Data'], y=df_previsao['Chuva_Acumulada'], 
                        name='Volume Acumulado (mm)', mode='lines+markers', 
                        line=dict(color='#e74c3c', width=3),
                        marker=dict(size=8)
                    ))
                    
                    fig_prev.update_layout(
                        template="plotly_white", 
                        hovermode="x unified",
                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                    )
                    
                    st.plotly_chart(fig_prev, use_container_width=True)

            # ==========================================
            # BOTÃO DE DOWNLOAD
            # ==========================================
            if not df_historico.empty or not df_previsao.empty:
                st.markdown("<br>", unsafe_allow_html=True)
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    if not df_historico.empty:
                        df_hist_save = df_historico.copy()
                        df_hist_save['Data'] = df_hist_save['Data'].dt.strftime('%Y-%m')
                        df_hist_save.to_excel(writer, sheet_name="Historico_ERA5", index=False)
                        
                        df_clima_save = df_clima[['Mês', 'Media_Historica']].copy()
                        df_clima_save['Media_Historica'] = df_clima_save['Media_Historica'].round(2)
                        df_clima_save.to_excel(writer, sheet_name="Normal_Climatologica", index=False)
                        
                    if not df_previsao.empty:
                        df_prev_save = df_previsao.copy()
                        df_prev_save['Data'] = df_prev_save['Data'].dt.strftime('%Y-%m-%d')
                        df_prev_save.to_excel(writer, sheet_name="Previsao_GFS", index=False)
                
                col_btn1, col_btn2, col_btn3 = st.columns([1, 2, 1])
                with col_btn2:
                    st.download_button(
                        label="💾 BAIXAR DADOS EM EXCEL",
                        data=buffer.getvalue(),
                        file_name=f"Dados_Climaticos_{st.session_state.lat:.2f}_{st.session_state.lon:.2f}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        type="primary",
                        use_container_width=True
                    )
