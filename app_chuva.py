import streamlit as st
import pandas as pd
import requests
import datetime
import io
import folium
from streamlit_folium import st_folium

# ==========================================
# CONFIGURAÇÃO DA PÁGINA E CSS
# ==========================================
st.set_page_config(page_title="SIG Climático Pro", page_icon="🌤️", layout="wide")

# CSS customizado para os botões e espaçamentos
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
    st.caption("v2.3 - Mapa Ampliado")

st.divider()

# ==========================================
# MEMÓRIA DO APLICATIVO
# ==========================================
if "lat" not in st.session_state:
    st.session_state.lat = -25.4200
if "lon" not in st.session_state:
    st.session_state.lon = -49.2700

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
    st.markdown("- <b>ERA5:</b> Dados gerados pelo programa europeu Copernicus Climate Change Service (C3S).")
    st.markdown("- <b>GFS:</b> Dados fornecidos em domínio público pela NOAA / NCEP.")
    st.markdown("</div>", unsafe_allow_html=True)

# ==========================================
# CORPO PRINCIPAL (MAPA E DASHBOARD)
# ==========================================
col_metrica1, col_metrica2, col_vazio = st.columns([1, 1, 2])
with col_metrica1:
    st.metric(label="Latitude Ativa", value=f"{st.session_state.lat:.4f}")
with col_metrica2:
    st.metric(label="Longitude Ativa", value=f"{st.session_state.lon:.4f}")

# Criação do Mapa Base
mapa = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=11, control_scale=True)

# Camada do Google Híbrido (Satélite + Divisas Municipais/Estaduais + Ruas)
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

# 🔥 ALTERAÇÃO AQUI: Aumentado o "height" de 350 para 550 para melhorar a visualização!
mapa_resultado = st_folium(mapa, height=550, use_container_width=True, returned_objects=["last_clicked"])

if mapa_resultado.get("last_clicked"):
    click_lat = mapa_resultado["last_clicked"]["lat"]
    click_lon = mapa_resultado["last_clicked"]["lng"]
    
    if click_lat != st.session_state.lat or click_lon != st.session_state.lon:
        st.session_state.lat = click_lat
        st.session_state.lon = click_lon
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
            df_previsao = pd.DataFrame()

            # 1. PUXA HISTÓRICO
            if var_hist:
                try:
                    hoje = datetime.date.today()
                    fim_historico = hoje - datetime.timedelta(days=5)
                    inicio_historico = "1981-01-01"

                    url_hist = f"https://archive-api.open-meteo.com/v1/archive?latitude={st.session_state.lat}&longitude={st.session_state.lon}&start_date={inicio_historico}&end_date={fim_historico}&daily=precipitation_sum&timezone=America%2FSao_Paulo"
                    resp_hist = requests.get(url_hist)
                    
                    if resp_hist.status_code == 200:
                        dados_hist = resp_hist.json()
                        df_bruto = pd.DataFrame({
                            'Data': pd.to_datetime(dados_hist['daily']['time']),
                            'Chuva Histórica (mm/mês)': dados_hist['daily']['precipitation_sum']
                        })
                        df_bruto.set_index('Data', inplace=True)
                        df_historico = df_bruto.resample('MS').sum().reset_index()
                except Exception as e:
                    st.error(f"❌ Erro ao baixar o histórico: {e}")

            # 2. PUXA PREVISÃO
            if var_prev:
                try:
                    url_prev = f"https://api.open-meteo.com/v1/forecast?latitude={st.session_state.lat}&longitude={st.session_state.lon}&daily=precipitation_sum&timezone=America%2FSao_Paulo&forecast_days=16"
                    resp_prev = requests.get(url_prev)
                    
                    if resp_prev.status_code == 200:
                        dados_prev = resp_prev.json()
                        df_previsao = pd.DataFrame({
                            'Data': pd.to_datetime(dados_prev['daily']['time']),
                            'Chuva Prevista (mm/dia)': dados_prev['daily']['precipitation_sum']
                        })
                except Exception as e:
                    st.error(f"❌ Erro ao baixar a previsão: {e}")

            # ==========================================
            # APRESENTAÇÃO DOS GRÁFICOS
            # ==========================================
            st.success("✅ Download concluído com sucesso!")

            tab1, tab2 = st.tabs(["📈 Histórico (ERA5)", "🔮 Previsão (GFS)"])

            with tab1:
                if not df_historico.empty:
                    st.markdown("#### Acumulado Mensal Observado")
                    st.line_chart(data=df_historico, x='Data', y='Chuva Histórica (mm/mês)', color="#3498db")
                    with st.expander("👁️ Visualizar Planilha de Histórico"):
                        st.dataframe(df_historico.style.format({'Data': lambda x: x.strftime('%Y-%m')}), use_container_width=True)

            with tab2:
                if not df_previsao.empty:
                    st.markdown("#### Chuva Prevista (Próximos 16 dias)")
                    st.bar_chart(data=df_previsao, x='Data', y='Chuva Prevista (mm/dia)', color="#2ecc71")
                    with st.expander("👁️ Visualizar Planilha de Previsão"):
                        st.dataframe(df_previsao.style.format({'Data': lambda x: x.strftime('%d/%m/%Y')}), use_container_width=True)

            # ==========================================
            # BOTÃO DE DOWNLOAD ELEGANTE
            # ==========================================
            if not df_historico.empty or not df_previsao.empty:
                st.markdown("<br>", unsafe_allow_html=True)
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    if not df_historico.empty:
                        df_hist_save = df_historico.copy()
                        df_hist_save['Data'] = df_hist_save['Data'].dt.strftime('%Y-%m')
                        df_hist_save.to_excel(writer, sheet_name="Historico_ERA5", index=False)
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
