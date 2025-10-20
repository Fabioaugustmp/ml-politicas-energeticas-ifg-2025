# app.py
import streamlit as st
import pandas as pd
import geopandas as gpd
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
import pydeck as pdk

# --- Configuração da Página ---
st.set_page_config(layout="wide", page_title="Potencial Energético - Goiás")
st.title("Análise de Potencial Energético Renovável em Goiás")

# ==============================================================================
# FUNÇÕES DE CARREGAMENTO DE DADOS (COM CACHE)
# ==============================================================================

@st.cache_data
def load_data():
    """Carrega o GeoDataFrame principal com dados e previsões."""
    gdf = gpd.read_parquet('df_modelo_final.parquet')
    # Formata as colunas do tooltip aqui para evitar recálculo
    gdf['predicted_potential_SOLAR_formatted'] = gdf['predicted_potential_SOLAR'].round(3)
    gdf['predicted_potential_EOLICO_formatted'] = gdf['predicted_potential_EOLICO'].round(3)
    return gdf

@st.cache_resource
def load_models():
    """Carrega os modelos de ML treinados."""
    model_s = joblib.load('model_solar.joblib')
    model_e = joblib.load('model_eolico.joblib')
    return model_s, model_e

@st.cache_data
def load_raw_data():
    """Carrega os dados brutos de usinas e linhas para o 'Deep Dive'."""
    try:
        # Carrega dados das usinas (já estava correto)
        gdf_usinas = gpd.read_parquet('usinas_por_municipio.parquet')
    except Exception as e:
        st.error(f"Erro ao carregar 'usinas_por_municipio.parquet': {e}")
        gdf_usinas = gpd.GeoDataFrame()
        
    try:
        # --- CORREÇÃO AQUI ---
        # Carrega o GeoDataFrame das LINHAS CLIPPADAS
        gdf_linhas = gpd.read_parquet('linhas_por_municipio.parquet') 
    except Exception as e:
        # Se falhar, tenta ler como Pandas (caso o arquivo errado ainda esteja lá)
        st.warning(f"Falha ao carregar 'linhas_por_municipio.parquet' como GeoDataFrame ({e}). Tentando como Pandas DataFrame...")
        try:
            # Tenta carregar como Pandas para pelo menos ter os dados tabulares
            gdf_linhas = pd.read_parquet('linhas_por_municipio.parquet')
            st.warning("Carregado como Pandas DataFrame. A geometria pode estar ausente ou incorreta.")
        except Exception as e2:
            st.error(f"Erro fatal ao carregar 'linhas_por_municipio.parquet': {e2}")
            gdf_linhas = pd.DataFrame() # Retorna DF vazio se tudo falhar
            
    return gdf_usinas, gdf_linhas

@st.cache_data
def load_clima_data():
    """Carrega os dados climáticos completos para os gráficos de sazonalidade."""
    try:
        df_clima = pd.read_parquet('clima_completo.parquet')
        # Converte datas (pode ser lento, por isso fazemos no cache)                
        df_clima['Data'] = pd.to_datetime(df_clima['Data'], format='%Y/%m/%d')
        df_clima['Mes'] = df_clima['Data'].dt.month
    except Exception as e:
        st.error(f"Erro ao carregar 'clima_completo.parquet': {e}")
        df_clima = pd.DataFrame() # Retorna DF vazio
        
    return df_clima

@st.cache_data
def convert_df_to_csv(df):
    """Converte o dataframe para CSV em memória para o botão de download."""
    return df.to_csv(index=False).encode('utf-8')

# --- Carregar todos os dados ---
gdf_modelo = load_data()
model_solar, model_eolico = load_models()
gdf_usinas_raw, gdf_linhas_raw = load_raw_data()
df_clima_completo = load_clima_data()

# ==============================================================================
# BARRA LATERAL (SIDEBAR)
# ==============================================================================

st.sidebar.header("Configurações de Análise")
tipo_potencial = st.sidebar.selectbox(
    "Escolha o tipo de potencial:",
    ("Energia Solar", "Energia Eólica")
)

# --- Filtros Globais (Sinergia e Escoamento) ---
st.sidebar.subheader("Filtros Globais de Análise")

# 1. Filtro por Potencial
min_potencial = st.sidebar.slider(
    "Filtrar por Potencial Mínimo:",
    min_value=0.0, max_value=1.0, value=0.0, step=0.05
)

# 2. Filtro por Potência Hídrica (Sinergia)
max_hidro = float(gdf_modelo['potencia_hidro_mw'].max())
min_hidro_sinergia = st.sidebar.slider(
    "Sinergia: Potência Hídrica Mínima (MW):",
    min_value=0.0, max_value=max_hidro, value=0.0, step=10.0
)

# 3. Filtro por Linhas de Transmissão (Capacidade de Escoamento)
max_linhas = float(gdf_modelo['km_linhas_transmissao'].max())
min_linhas = st.sidebar.slider(
    "Escoamento: Km Mínimos de Linhas:",
    min_value=0.0, max_value=max_linhas, value=0.0, step=20.0
)

# --- Lógica Principal (Modelo e Simulador) ---
if tipo_potencial == "Energia Solar":
    coluna_potencial = 'predicted_potential_SOLAR'
    titulo_mapa = 'Mapa de Potencial para Energia SOLAR em Goiás'
    
    # Pega as features do modelo
    features_s = model_solar.feature_names_in_
    df_importance = pd.DataFrame({
        'Feature': features_s, 
        'Importance': model_solar.feature_importances_
    }).sort_values(by='Importance', ascending=False)
    
    # --- SIMULADOR "WHAT-IF" (SOLAR) ---
    st.sidebar.subheader("Simulador Solar (What-If)")
    input_data_s = {}
    for feature in features_s:
        min_val = float(gdf_modelo[feature].min())
        max_val = float(gdf_modelo[feature].max())
        mean_val = float(gdf_modelo[feature].mean())
        
        input_data_s[feature] = st.sidebar.slider(
            f"Ajustar '{feature}'", min_value=min_val, max_value=max_val, value=mean_val,
            key=f"solar_{feature}" # Chave única para evitar conflito
        )

    # Passa o DataFrame (com nomes) para o predict
    input_df_s = pd.DataFrame([input_data_s])
    predicted_score_s = model_solar.predict(input_df_s[features_s])[0]

    st.sidebar.metric(
        label="Score Solar Simulado:",
        value=f"{predicted_score_s:.3f}"
    )
    
else: # Energia Eólica
    coluna_potencial = 'predicted_potential_EOLICO'
    titulo_mapa = 'Mapa de Potencial para Energia EÓLICA em Goiás'
    
    # Pega as features do modelo
    features_e = model_eolico.feature_names_in_
    df_importance = pd.DataFrame({
        'Feature': features_e, 
        'Importance': model_eolico.feature_importances_
    }).sort_values(by='Importance', ascending=False)

    # --- SIMULADOR "WHAT-IF" (EÓLICO) ---
    st.sidebar.subheader("Simulador Eólico (What-If)")
    input_data_e = {}
    for feature in features_e:
        min_val = float(gdf_modelo[feature].min())
        max_val = float(gdf_modelo[feature].max())
        mean_val = float(gdf_modelo[feature].mean())
        
        input_data_e[feature] = st.sidebar.slider(
            f"Ajustar '{feature}'", min_value=min_val, max_value=max_val, value=mean_val,
            key=f"eolico_{feature}" # Chave única para evitar conflito
        )

    # Passa o DataFrame (com nomes) para o predict
    input_df_e = pd.DataFrame([input_data_e])
    predicted_score_e = model_eolico.predict(input_df_e[features_e])[0]

    st.sidebar.metric(
        label="Score Eólico Simulado:",
        value=f"{predicted_score_e:.3f}"
    )

# ==============================================================================
# APLICA OS FILTROS GLOBAIS
# ==============================================================================
gdf_filtrado = gdf_modelo[
    (gdf_modelo[coluna_potencial] >= min_potencial) &
    (gdf_modelo['potencia_hidro_mw'] >= min_hidro_sinergia) &
    (gdf_modelo['km_linhas_transmissao'] >= min_linhas)
].copy()

st.sidebar.info(f"{len(gdf_filtrado)} de {len(gdf_modelo)} municípios exibidos.")


# ==============================================================================
# PÁGINA PRINCIPAL (EXIBIÇÃO EM ABAS)
# ==============================================================================

tab1, tab2, tab3, tab4 = st.tabs([
    "🗺️ Mapa Potencial", 
    "📊 Rankings e Sinergia", 
    "🤖 Detalhes do Modelo", 
    "🔌 Linhas de Transmissão"
])

# --- ABA 1: MAPA INTERATIVO ---
with tab1:
    st.subheader(titulo_mapa)
    
    if gdf_filtrado.empty:
        st.warning("Nenhum município corresponde aos filtros selecionados.")
    else:
        # Normaliza a cor *apenas* nos dados filtrados para melhor contraste
        min_pot_filtrado = gdf_filtrado[coluna_potencial].min()
        max_pot_filtrado = gdf_filtrado[coluna_potencial].max()
        
        # Evita divisão por zero se houver apenas um município
        if (max_pot_filtrado - min_pot_filtrado) > 0:
            gdf_filtrado['cor_intensidade'] = (gdf_filtrado[coluna_potencial] - min_pot_filtrado) / \
                                              (max_pot_filtrado - min_pot_filtrado)
        else:
            gdf_filtrado['cor_intensidade'] = 0.5 # Valor médio

        color_range = [
            [25, 138, 255, 150], [90, 203, 107, 150], [255, 170, 0, 150], [255, 0, 0, 150]
        ]
        
        def get_color(intensidade, color_range):
            idx = int(intensidade * (len(color_range) - 1))
            return color_range[idx]

        gdf_filtrado['cor_rgba'] = gdf_filtrado['cor_intensidade'].apply(lambda x: get_color(x, color_range))

        view_state = pdk.ViewState(latitude=-15.93, longitude=-49.82, zoom=5.5, pitch=45)

        polygon_layer = pdk.Layer(
            'GeoJsonLayer',
            data=gdf_filtrado, # Usa dados filtrados
            opacity=0.8,
            stroked=True,
            filled=True,
            extruded=True,
            wireframe=True,
            get_elevation='cor_intensidade * 50000',
            get_fill_color='cor_rgba',
            get_line_color=[255, 255, 255, 100],
            pickable=True
        )

        tooltip = {
            "html": "<b>Município:</b> {nm_mun}<br/>"
                    "<b>Pot. Solar:</b> {predicted_potential_SOLAR_formatted}<br/>"
                    "<b>Pot. Eólico:</b> {predicted_potential_EOLICO_formatted}<br/>"
                    "<b>Pot. Hidro:</b> {potencia_hidro_mw} MW<br/>"
                    "<b>Linhas:</b> {km_linhas_transmissao} km",
            "style": {"backgroundColor": "steelblue", "color": "white"}
        }

        st.pydeck_chart(pdk.Deck(
            layers=[polygon_layer],
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style='mapbox://styles/mapbox/light-v9'
        ))

# --- ABA 2: RANKINGS E DEEP DIVE ---
with tab2:
    st.subheader("Ranking de Municípios (Filtrado)")
    ranking_cols = ['nm_mun', coluna_potencial, 'potencia_hidro_mw', 'km_linhas_transmissao', 'estacao_mais_proxima']
    ranking = gdf_filtrado[ranking_cols].sort_values(by=coluna_potencial, ascending=False)
    
    st.dataframe(ranking, use_container_width=True)
    
    # Botão de Download
    csv = convert_df_to_csv(ranking)
    st.download_button(
        label="Download do Ranking como CSV",
        data=csv,
        # file_name=f"ranking_{tipo_potencial.lower().replace(' ', '_')}.csv",
        file_name=f"ranking_{str(tipo_potencial).lower().replace(' ', '_')}.csv",
        mime='text/csv',
    )
    
    # --- Seção "Deep Dive" por Município ---
    st.divider() 
    st.subheader("Investigação Detalhada por Município")
    
    lista_municipios = ranking['nm_mun'].tolist()
    
    if not lista_municipios:
        st.info("Nenhum município selecionado pelos filtros para inspecionar.")
    else:
        # Dropdown para selecionar o município
        municipio_selecionado = st.selectbox(
            "Selecione um município para inspecionar:",
            lista_municipios
        )
        
        # Pega a linha completa de dados do município
        dados_municipio = gdf_modelo[gdf_modelo['nm_mun'] == municipio_selecionado].iloc[0]
        
        st.write(f"#### Métricas Principais: {municipio_selecionado}")
        
        # Exibe as métricas com st.metric
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Score Solar", f"{dados_municipio['predicted_potential_SOLAR_formatted']}")
        col2.metric("Score Eólico", f"{dados_municipio['predicted_potential_EOLICO_formatted']}")
        col3.metric("Pot. Hídrica", f"{dados_municipio['potencia_hidro_mw']:.1f} MW")
        col4.metric("Linhas (km)", f"{dados_municipio['km_linhas_transmissao']:.1f} km")
        
        # --- Gráfico de Sazonalidade Específico ---
        st.write("##### Análise de Sazonalidade (Estação Mais Próxima)")
        nome_estacao = dados_municipio['estacao_mais_proxima']
        st.write(f"Dados da estação: **{nome_estacao}**")
        
        if df_clima_completo.empty:
            st.warning("Dados climáticos não foram carregados.")
        else:
            clima_estacao = df_clima_completo[df_clima_completo['Estacao'] == nome_estacao]
            
            if clima_estacao.empty:
                st.warning("Não foram encontrados dados de sazonalidade para esta estação.")
            else:
                # Recalcula as médias mensais para essa estação
                radiacao_mensal = clima_estacao.groupby('Mes')['RADIACAO GLOBAL (Kj/m²)'].mean()
                chuva_mensal = clima_estacao.groupby('Mes')['PRECIPITAÇÃO TOTAL, HORÁRIO (mm)'].sum()
                
                # Cria o gráfico
                fig_sazonal, ax1 = plt.subplots(figsize=(10, 4))
                ax1.set_xlabel('Mês')
                ax1.set_ylabel('Radiação Solar Média (Kj/m²)', color='orange')
                ax1.plot(radiacao_mensal.index, radiacao_mensal.values, color='orange', alpha=0.7, label='Radiação Solar')
                ax1.tick_params(axis='y', labelcolor='orange')
                
                ax2 = ax1.twinx()
                ax2.set_ylabel('Precipitação Média (mm)', color='blue')
                ax2.plot(chuva_mensal.index, chuva_mensal.values, color='blue', marker='o', label='Precipitação')
                ax2.tick_params(axis='y', labelcolor='blue')
                
                fig_sazonal.suptitle(f'Sazonalidade em {municipio_selecionado} (via {nome_estacao})')
                st.pyplot(fig_sazonal)

        # --- Tabelas de Dados Brutos ---
        col_raw1, col_raw2 = st.columns(2)
        
        with col_raw1:
            st.write("##### Usinas Registradas (ANEEL)")
            if gdf_usinas_raw.empty:
                st.warning("Dados de usinas não foram carregados.")
            else:
                usinas_no_municipio = gdf_usinas_raw[gdf_usinas_raw['nm_mun'] == municipio_selecionado]
                st.dataframe(usinas_no_municipio[['NomEmpreendimento', 'SigTipoGeracao', 'MdaPotenciaFiscalizadaKw']], use_container_width=True)
        
        with col_raw2:
            st.write("##### Linhas de Transmissão (ONS)")
            if gdf_linhas_raw.empty:
                st.warning("Dados de linhas não foram carregados.")
            else:
                linhas_no_municipio = gdf_linhas_raw[gdf_linhas_raw['nm_mun'] == municipio_selecionado]
                st.dataframe(linhas_no_municipio[['nom_linhadetransmissao', 'val_niveltensao_kv', 'comprimento_segmento_km']], use_container_width=True)

# --- ABA 3: DETALHES DO MODELO ---
with tab3:
    st.subheader(f"Importância das Features ({tipo_potencial})")
    fig_features, ax_features = plt.subplots(figsize=(8, 6))
    
    # Corrige o warning do seaborn
    sns.barplot(
        x='Importance', 
        y='Feature', 
        data=df_importance, 
        hue='Feature',  
        palette='viridis', 
        ax=ax_features, 
        legend=False    
    )
    ax_features.set_title(f'Importância das Features ({tipo_potencial})')
    st.pyplot(fig_features)
    
    st.info("Esta visualização mostra quais fatores o modelo de Machine Learning mais considerou "
            "ao criar o score de potencial. Valores mais altos indicam maior influência na previsão.")