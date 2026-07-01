import customtkinter as ctk
import tkintermapview
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import pandas as pd
import threading
import requests
import datetime
from tkinter import messagebox, ttk, filedialog

# Configuração visual do CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

class AppSIGClimatico(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("SIG Climático Pro - 100% API Integrada (ERA5 + GFS)")
        self.geometry("1250x780")

        # Variáveis de controle
        self.lat_selecionada = None
        self.lon_selecionada = None
        self.marcador_atual = None
        self.df_historico = pd.DataFrame() # Tabela Histórica Mensal (ERA5)
        self.df_previsao = pd.DataFrame()  # Tabela Previsão Diária (GFS)

        self.criar_interface()
        self.log("Sistema pronto! Navegue no mapa, clique em um local ou digite as coordenadas.")

    def criar_interface(self):
        # ==========================================
        # PAINEL LATERAL ESQUERDO (CONTROLES)
        # ==========================================
        self.frame_esq = ctk.CTkFrame(self, width=320, corner_radius=0)
        self.frame_esq.pack(side="left", fill="y", padx=10, pady=10)

        ctk.CTkLabel(self.frame_esq, text="🌍 SIG Climático", font=ctk.CTkFont(size=20, weight="bold")).pack(pady=(20, 10))

        # Painel de Entrada de Coordenadas
        frame_manual = ctk.CTkFrame(self.frame_esq)
        frame_manual.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(frame_manual, text="Definir Localização:", font=ctk.CTkFont(weight="bold")).pack(pady=(5, 5))
        
        row1 = ctk.CTkFrame(frame_manual, fg_color="transparent")
        row1.pack(fill="x", padx=5, pady=5)
        ctk.CTkLabel(row1, text="Lat:").pack(side="left", padx=5)
        self.entry_lat = ctk.CTkEntry(row1, width=80, placeholder_text="-25.42")
        self.entry_lat.pack(side="left", padx=5)
        
        ctk.CTkLabel(row1, text="Lon:").pack(side="left", padx=5)
        self.entry_lon = ctk.CTkEntry(row1, width=80, placeholder_text="-49.27")
        self.entry_lon.pack(side="left", padx=5)

        self.btn_localizar = ctk.CTkButton(frame_manual, text="📍 Buscar Coordenadas", height=35, font=ctk.CTkFont(weight="bold"), command=self.inserir_coordenadas_manuais)
        self.btn_localizar.pack(pady=(5, 10), padx=10, fill="x")

        # Painel de Exibição do Ponto Ativo
        frame_coord = ctk.CTkFrame(self.frame_esq)
        frame_coord.pack(fill="x", padx=10, pady=5)
        ctk.CTkLabel(frame_coord, text="Ponto Confirmado:", font=ctk.CTkFont(weight="bold")).pack(pady=(5, 0))
        self.lbl_lat = ctk.CTkLabel(frame_coord, text="Latitude: --", font=("Consolas", 14))
        self.lbl_lat.pack(pady=2)
        self.lbl_lon = ctk.CTkLabel(frame_coord, text="Longitude: --", font=("Consolas", 14))
        self.lbl_lon.pack(pady=(2, 10))

        # Seleção de Variáveis
        frame_vars = ctk.CTkFrame(self.frame_esq)
        frame_vars.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(frame_vars, text="Dados para Extrair (Nuvem):", font=ctk.CTkFont(weight="bold")).pack(pady=5)
        
        self.var_hist = ctk.BooleanVar(value=True)
        self.var_prev = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(frame_vars, text="Histórico ERA5 (1981 - Atual | Mensal)", variable=self.var_hist).pack(pady=5, padx=10, anchor="w")
        ctk.CTkCheckBox(frame_vars, text="Previsão GFS (Próximos 16 dias | Diária)", variable=self.var_prev).pack(pady=5, padx=10, anchor="w")

        # Botões de Ação
        self.btn_extrair = ctk.CTkButton(self.frame_esq, text="👁️ Extrair da API", height=40, font=ctk.CTkFont(weight="bold"), command=self.iniciar_extracao)
        self.btn_extrair.pack(pady=(20, 5), padx=10, fill="x")

        self.btn_salvar = ctk.CTkButton(self.frame_esq, text="💾 Salvar em Excel", height=40, font=ctk.CTkFont(weight="bold"), fg_color="#27ae60", hover_color="#2ecc71", state="disabled", command=self.salvar_excel)
        self.btn_salvar.pack(pady=5, padx=10, fill="x")

        # Log de Sistema
        self.txt_log = ctk.CTkTextbox(self.frame_esq, height=150, font=("Consolas", 11))
        self.txt_log.pack(fill="both", expand=True, padx=10, pady=10)
        self.txt_log.configure(state="disabled")

        # ==========================================
        # PAINEL DIREITO (SISTEMA DE ABAS)
        # ==========================================
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(side="right", fill="both", expand=True, padx=(0, 10), pady=10)
        
        self.tab_mapa = self.tabview.add("🌍 Mapa Interativo")
        self.tab_hist_graf = self.tabview.add("📈 Chuva Histórica")
        self.tab_temp_hist = self.tabview.add("🌡️ Temp. Histórica")
        self.tab_hist_tab = self.tabview.add("📊 Dados em Tabela")
        self.tab_previsao = self.tabview.add("🔮 Chuva Previsão")
        self.tab_temp_prev = self.tabview.add("🌡️ Temp. Previsão")

        self.configurar_mapa_interativo()

        # Configura Tabela Histórico Mensal
        self.tree_hist = ttk.Treeview(self.tab_hist_tab)
        self.tree_hist.pack(fill="both", expand=True, padx=10, pady=10)
        scroll_hist = ttk.Scrollbar(self.tab_hist_tab, orient="vertical", command=self.tree_hist.yview)
        scroll_hist.pack(side="right", fill="y")
        self.tree_hist.configure(yscrollcommand=scroll_hist.set)

        # Configura Divisão da Aba de Previsão
        self.frame_prev_grafico = ctk.CTkFrame(self.tab_previsao)
        self.frame_prev_grafico.pack(fill="both", expand=True, padx=5, pady=5)
        
        self.tree_prev = ttk.Treeview(self.tab_previsao, height=6)
        self.tree_prev.pack(fill="x", side="bottom", padx=5, pady=5)

    def configurar_mapa_interativo(self):
        self.map_widget = tkintermapview.TkinterMapView(self.tab_mapa, corner_radius=10)
        self.map_widget.pack(fill="both", expand=True, padx=10, pady=10)
        self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=y&hl=pt-BR&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
        self.map_widget.set_position(-15.7801, -47.9292)
        self.map_widget.set_zoom(4)
        self.map_widget.add_left_click_map_command(self.ao_clicar_no_mapa)

    def log(self, texto):
        def _append():
            try:
                self.txt_log.configure(state="normal")
                self.txt_log.insert("end", texto + "\n")
                self.txt_log.see("end")
                self.txt_log.configure(state="disabled")
            except: pass
        self.after(0, _append)

    def ao_clicar_no_mapa(self, coords):
        lat = round(coords[0], 4)
        lon = round(coords[1], 4)
        self.entry_lat.delete(0, 'end')
        self.entry_lat.insert(0, str(lat))
        self.entry_lon.delete(0, 'end')
        self.entry_lon.insert(0, str(lon))
        self.atualizar_marcador(lat, lon)
        self.iniciar_extracao()

    def inserir_coordenadas_manuais(self):
        try:
            lat = float(self.entry_lat.get().replace(',', '.'))
            lon = float(self.entry_lon.get().replace(',', '.'))
            self.map_widget.set_position(lat, lon)
            self.map_widget.set_zoom(10)
            self.atualizar_marcador(lat, lon)
            self.log(f"📍 Ponto encontrado: Lat {lat}, Lon {lon}")
        except ValueError:
            messagebox.showerror("Erro", "Por favor, digite números válidos para Latitude e Longitude.")

    def atualizar_marcador(self, lat, lon):
        self.lat_selecionada = lat
        self.lon_selecionada = lon
        self.lbl_lat.configure(text=f"Latitude: {lat}")
        self.lbl_lon.configure(text=f"Longitude: {lon}")
        if self.marcador_atual:
            self.marcador_atual.delete()
        self.marcador_atual = self.map_widget.set_marker(lat, lon, text="Ponto de Extração")

    def iniciar_extracao(self):
        if self.lat_selecionada is None or self.lon_selecionada is None:
            messagebox.showwarning("Aviso", "Selecione um ponto no mapa ou confirme as coordenadas primeiro!")
            return
        if not self.var_hist.get() and not self.var_prev.get():
            messagebox.showwarning("Aviso", "Selecione pelo menos uma variável!")
            return
            
        self.btn_extrair.configure(state="disabled", text="⏳ Conectando aos Servidores...")
        self.btn_salvar.configure(state="disabled")
        threading.Thread(target=self._worker_extracao, daemon=True).start()

    def _worker_extracao(self):
        try:
            self.log("\n--- Nova Extração via API Iniciada ---")
            self.df_historico = pd.DataFrame()
            self.df_previsao = pd.DataFrame()

            # =====================================================================
            # 1. PUXA O HISTÓRICO VIA API (ERA5 ARCHIVE) - Chuva + Temperatura
            # =====================================================================
            if self.var_hist.get():
                self.log("🌧️🌡️ Baixando histórico do ERA5 (1981 - Atual)...")
                try:
                    hoje = datetime.date.today()
                    fim_historico = hoje - datetime.timedelta(days=5)
                    inicio_historico = "1981-01-01"

                    # Adicionado: temperature_2m_mean requisitado na API do histórico
                    url_hist = f"https://archive-api.open-meteo.com/v1/archive?latitude={self.lat_selecionada}&longitude={self.lon_selecionada}&start_date={inicio_historico}&end_date={fim_historico}&daily=precipitation_sum,temperature_2m_mean&timezone=America%2FSao_Paulo"
                    resposta = requests.get(url_hist)
                    
                    if resposta.status_code == 200:
                        dados_hist = resposta.json()
                        df_bruto = pd.DataFrame({
                            'Data': pd.to_datetime(dados_hist['daily']['time']),
                            'Chuva': dados_hist['daily']['precipitation_sum'],
                            'Temp': dados_hist['daily']['temperature_2m_mean']
                        })
                        
                        df_bruto.set_index('Data', inplace=True)
                        # Agrupamento Inteligente: Soma para Chuva, Média para Temperatura
                        df_mensal = df_bruto.resample('MS').agg({'Chuva': 'sum', 'Temp': 'mean'}).reset_index()
                        
                        df_mensal.rename(columns={
                            'Chuva': 'Chuva Histórica (mm/mes)',
                            'Temp': 'Temp Média Histórica (°C)'
                        }, inplace=True)
                        self.df_historico = df_mensal
                        self.log("✅ Histórico (Chuva + Temperatura) carregado com sucesso!")
                    else:
                        self.log(f"⚠️ Erro ao acessar histórico (Código {resposta.status_code}).")
                except Exception as e:
                    self.log(f"⚠️ Falha ao baixar histórico: {e}")

            # =====================================================================
            # 2. PUXA A PREVISÃO DIÁRIA VIA INTERNET (API GFS) - Chuva + Temperatura
            # =====================================================================
            if self.var_prev.get():
                self.log("📡 Baixando previsão para os próximos 16 dias...")
                try:
                    # Adicionado: temperature_2m_max e temperature_2m_min requisitados na API de previsão
                    url_prev = f"https://api.open-meteo.com/v1/forecast?latitude={self.lat_selecionada}&longitude={self.lon_selecionada}&daily=precipitation_sum,temperature_2m_max,temperature_2m_min&timezone=America%2FSao_Paulo&forecast_days=16"
                    resposta = requests.get(url_prev)
                    
                    if resposta.status_code == 200:
                        dados_prev = resposta.json()
                        self.df_previsao = pd.DataFrame({
                            'Data': pd.to_datetime(dados_prev['daily']['time']),
                            'Chuva Prevista (mm/dia)': dados_prev['daily']['precipitation_sum'],
                            'Temp Max Prevista (°C)': dados_prev['daily']['temperature_2m_max'],
                            'Temp Min Prevista (°C)': dados_prev['daily']['temperature_2m_min']
                        })
                        self.log("✅ Previsão (Chuva + Temperatura) carregada com sucesso!")
                    else:
                        self.log(f"⚠️ Erro ao acessar previsão (Código {resposta.status_code}).")
                except Exception as e:
                    self.log(f"⚠️ Falha de conexão com a internet: {e}")

            if self.df_historico.empty and self.df_previsao.empty:
                raise Exception("Nenhum dado pôde ser extraído da internet.")

            self.after(0, self.atualizar_visuais)

        except Exception as e:
            self.log(f"❌ Erro crítico: {str(e)}")
            self.after(0, lambda: self.btn_extrair.configure(state="normal", text="👁️ Extrair da API"))

    def atualizar_visuais(self):
        try:
            # --- 1. ATUALIZA HISTÓRICO MENSAL (ERA5) ---
            if not self.df_historico.empty:
                for item in self.tree_hist.get_children(): self.tree_hist.delete(item)
                df_visual = self.df_historico.copy()
                df_visual['Chuva Histórica (mm/mes)'] = df_visual['Chuva Histórica (mm/mes)'].round(1)
                df_visual['Temp Média Histórica (°C)'] = df_visual['Temp Média Histórica (°C)'].round(1)
                df_visual['Data'] = df_visual['Data'].dt.strftime('%Y-%m')
                
                self.tree_hist["columns"] = list(df_visual.columns)
                self.tree_hist["show"] = "headings"
                for col in df_visual.columns:
                    self.tree_hist.heading(col, text=col)
                    self.tree_hist.column(col, width=150, anchor="center")
                for _, row in df_visual.iterrows():
                    self.tree_hist.insert("", "end", values=list(row.values))

                # Gráfico Chuva Histórica
                for widget in self.tab_hist_graf.winfo_children(): widget.destroy()
                fig_hist, ax_hist = plt.subplots(figsize=(8, 4), dpi=100)
                fig_hist.patch.set_facecolor('#2b2b2b')
                ax_hist.set_facecolor('#2b2b2b')
                ax_hist.plot(self.df_historico['Data'], self.df_historico['Chuva Histórica (mm/mes)'], label='Chuva Observada ERA5 (Mensal)', color='#3498db', linewidth=1.5)
                ax_hist.tick_params(colors='white')
                ax_hist.legend(facecolor='#2b2b2b', labelcolor='white')
                ax_hist.grid(True, linestyle='--', alpha=0.3, color='white')
                fig_hist.autofmt_xdate()
                canvas_hist = FigureCanvasTkAgg(fig_hist, master=self.tab_hist_graf)
                canvas_hist.draw()
                canvas_hist.get_tk_widget().pack(fill="both", expand=True)

                # NOVO: Gráfico de Temperatura Histórica
                for widget in self.tab_temp_hist.winfo_children(): widget.destroy()
                fig_temp_hist, ax_temp_hist = plt.subplots(figsize=(8, 4), dpi=100)
                fig_temp_hist.patch.set_facecolor('#2b2b2b')
                ax_temp_hist.set_facecolor('#2b2b2b')
                ax_temp_hist.plot(self.df_historico['Data'], self.df_historico['Temp Média Histórica (°C)'], label='Temp Média ERA5 (°C)', color='#e74c3c', linewidth=1.5)
                ax_temp_hist.tick_params(colors='white')
                ax_temp_hist.legend(facecolor='#2b2b2b', labelcolor='white')
                ax_temp_hist.grid(True, linestyle='--', alpha=0.3, color='white')
                fig_temp_hist.autofmt_xdate()
                canvas_temp_hist = FigureCanvasTkAgg(fig_temp_hist, master=self.tab_temp_hist)
                canvas_temp_hist.draw()
                canvas_temp_hist.get_tk_widget().pack(fill="both", expand=True)

            # --- 2. ATUALIZA PREVISÃO DIÁRIA (GFS) ---
            if not self.df_previsao.empty:
                for item in self.tree_prev.get_children(): self.tree_prev.delete(item)
                df_prev_vis = self.df_previsao.copy()
                df_prev_vis['Chuva Prevista (mm/dia)'] = df_prev_vis['Chuva Prevista (mm/dia)'].round(1)
                df_prev_vis['Temp Max Prevista (°C)'] = df_prev_vis['Temp Max Prevista (°C)'].round(1)
                df_prev_vis['Temp Min Prevista (°C)'] = df_prev_vis['Temp Min Prevista (°C)'].round(1)
                df_prev_vis['Data'] = df_prev_vis['Data'].dt.strftime('%d/%m/%Y')
                
                self.tree_prev["columns"] = list(df_prev_vis.columns)
                self.tree_prev["show"] = "headings"
                for col in df_prev_vis.columns:
                    self.tree_prev.heading(col, text=col)
                    self.tree_prev.column(col, width=130, anchor="center")
                for _, row in df_prev_vis.iterrows():
                    self.tree_prev.insert("", "end", values=list(row.values))

                # Gráfico Previsão de Chuva
                for widget in self.frame_prev_grafico.winfo_children(): widget.destroy()
                fig_prev, ax_prev = plt.subplots(figsize=(8, 3), dpi=100)
                fig_prev.patch.set_facecolor('#2b2b2b')
                ax_prev.set_facecolor('#2b2b2b')
                ax_prev.bar(self.df_previsao['Data'], self.df_previsao['Chuva Prevista (mm/dia)'], color='#2ecc71', alpha=0.8, label='Previsão GFS (Diária)')
                ax_prev.tick_params(colors='white')
                ax_prev.legend(facecolor='#2b2b2b', labelcolor='white')
                ax_prev.grid(True, linestyle='--', alpha=0.3, color='white')
                fig_prev.autofmt_xdate()
                canvas_prev = FigureCanvasTkAgg(fig_prev, master=self.frame_prev_grafico)
                canvas_prev.draw()
                canvas_prev.get_tk_widget().pack(fill="both", expand=True)

                # NOVO: Gráfico Previsão de Temperatura (Máxima e Mínima com preenchimento)
                for widget in self.tab_temp_prev.winfo_children(): widget.destroy()
                fig_temp_prev, ax_temp_prev = plt.subplots(figsize=(8, 4), dpi=100)
                fig_temp_prev.patch.set_facecolor('#2b2b2b')
                ax_temp_prev.set_facecolor('#2b2b2b')
                ax_temp_prev.plot(self.df_previsao['Data'], self.df_previsao['Temp Max Prevista (°C)'], label='Temp Máx (°C)', color='#e67e22', linewidth=2)
                ax_temp_prev.plot(self.df_previsao['Data'], self.df_previsao['Temp Min Prevista (°C)'], label='Temp Mín (°C)', color='#3498db', linewidth=2)
                ax_temp_prev.fill_between(self.df_previsao['Data'], self.df_previsao['Temp Min Prevista (°C)'], self.df_previsao['Temp Max Prevista (°C)'], color='#e67e22', alpha=0.1)
                ax_temp_prev.tick_params(colors='white')
                ax_temp_prev.legend(facecolor='#2b2b2b', labelcolor='white')
                ax_temp_prev.grid(True, linestyle='--', alpha=0.3, color='white')
                fig_temp_prev.autofmt_xdate()
                canvas_temp_prev = FigureCanvasTkAgg(fig_temp_prev, master=self.tab_temp_prev)
                canvas_temp_prev.draw()
                canvas_temp_prev.get_tk_widget().pack(fill="both", expand=True)

            self.btn_extrair.configure(state="normal", text="👁️ Extrair da API")
            self.btn_salvar.configure(state="normal")
            
            if self.var_hist.get(): self.tabview.set("📈 Chuva Histórica")
            elif self.var_prev.get(): self.tabview.set("🔮 Chuva Previsão")

        except Exception as e:
            self.log(f"⚠️ Erro ao atualizar visuais: {e}")
            self.btn_extrair.configure(state="normal", text="👁️ Extrair da API")

    def salvar_excel(self):
        if self.df_historico.empty and self.df_previsao.empty: return
            
        arquivo = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            initialfile=f"Dados_Climaticos_Lat{self.lat_selecionada}_Lon{self.lon_selecionada}.xlsx",
            title="Salvar Dados",
            filetypes=[("Excel files", "*.xlsx")]
        )
        
        if arquivo:
            try:
                with pd.ExcelWriter(arquivo, engine='openpyxl') as writer:
                    if not self.df_historico.empty:
                        df_salvar_hist = self.df_historico.copy()
                        df_salvar_hist['Data'] = df_salvar_hist['Data'].dt.strftime('%Y-%m')
                        df_salvar_hist.to_excel(writer, sheet_name="Historico_ERA5_Mensal", index=False)
                        
                    if not self.df_previsao.empty:
                        df_salvar_prev = self.df_previsao.copy()
                        df_salvar_prev['Data'] = df_salvar_prev['Data'].dt.strftime('%Y-%m-%d')
                        df_salvar_prev.to_excel(writer, sheet_name="Previsao_GFS_16Dias", index=False)

                self.log(f"💾 Arquivo salvo com sucesso em:\n{arquivo}")
                messagebox.showinfo("Sucesso", "Planilha salva com sucesso!")
            except Exception as e:
                self.log(f"❌ Erro ao salvar arquivo: {e}")

if __name__ == "__main__":
    app = AppSIGClimatico()
    app.mainloop()
