# app.py
import streamlit as st
import pandas as pd
import geopandas as gpd
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
import pydeck as pdk
import duckdb

# --- Configuração da Página ---
st.set_page_config(layout="wide", page_title="Potencial Energético - Goiás")
st.title("Análise de Potencial Energético Renovável em Goiás")

# ==============================================================================
# FUNÇÕES DE ACESSO A DADOS (CACHEADAS)
# ==============================================================================

@st.cache_data
def load_main_data():
    """
    Carrega o GeoDataFrame principal para o mapa.
    Otimização: Downcast de floats para reduzir uso de memória.
    Nota: Revertida a conversão para 'category' que causava lentidão no mapa.
    """
    gdf = gpd.read_parquet('df_modelo_final.parquet')

    # Otimização de Memória: Downcast de colunas numéricas para usar menos espaço
    for col in ['predicted_potential_SOLAR', 'predicted_potential_EOLICO', 'potencia_hidro_mw', 'km_linhas_transmissao']:
        if col in gdf.columns:
            gdf[col] = pd.to_numeric(gdf[col], downcast='float')

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

@st.cache_resource
def get_duckdb_connection():
    """Cria e armazena em cache uma conexão com o DuckDB."""
    # Conecta a um banco de dados em memória para máxima velocidade
    return duckdb.connect(database=':memory:', read_only=False)

@st.cache_data
def query_sazonalidade(_con, nome_estacao):
    """
    Busca dados de sazonalidade para uma estação diretamente do arquivo Parquet usando DuckDB.
    """
    # Correção: A coluna 'Mes' é derivada da coluna 'Data' em tempo de execução usando as funções do DuckDB.
    query = """
    SELECT
        month(strptime("Data", '%Y/%m/%d')) as "Mes",
        avg("RADIACAO GLOBAL (Kj/m²)") as radiacao,
        sum("PRECIPITAÇÃO TOTAL, HORÁRIO (mm)") as precipitacao
    FROM read_parquet('clima_completo.parquet')
    WHERE "Estacao" = ?
    GROUP BY "Mes"
    ORDER BY "Mes"
    """
    result_df = _con.execute(query, [nome_estacao]).fetchdf()
    if result_df.empty:
        return pd.Series(dtype='float64'), pd.Series(dtype='float64')

    # Garante que todos os 12 meses estejam presentes para o gráfico
    result_df = result_df.set_index('Mes').reindex(range(1, 13))
    return result_df['radiacao'], result_df['precipitacao']

@st.cache_data
def query_usinas(_con, municipio):
    """Busca usinas para um município diretamente do arquivo Parquet."""
    query = "SELECT NomEmpreendimento, SigTipoGeracao, MdaPotenciaFiscalizadaKw FROM read_parquet('usinas_por_municipio.parquet') WHERE nm_mun = ?"
    return _con.execute(query, [municipio]).fetchdf()

@st.cache_data
def query_linhas(_con, municipio):
    """Busca linhas de transmissão para um município diretamente do arquivo Parquet."""
    query = "SELECT nom_linhadetransmissao, val_niveltensao_kv, comprimento_segmento_km FROM read_parquet('linhas_por_municipio.parquet') WHERE nm_mun = ?"
    return _con.execute(query, [municipio]).fetchdf()

@st.cache_data
def convert_df_to_csv(df):
    """Converte o dataframe para CSV em memória para o botão de download."""
    return df.to_csv(index=False).encode('utf-8')

# --- Carregamento Inicial e Conexões ---
gdf_modelo = load_main_data()
model_solar, model_eolico = load_models()
con = get_duckdb_connection()

# ==============================================================================
# BARRA LATERAL (SIDEBAR)
# ==============================================================================
st.sidebar.header("Configurações de Análise")
tipo_potencial = st.sidebar.selectbox(
    "Escolha o tipo de potencial:",
    ("Energia Solar", "Energia Eólica")
)

st.sidebar.subheader("Filtros Globais de Análise")
min_potencial = st.sidebar.slider(
    "Filtrar por Potencial Mínimo:",
    min_value=0.0, max_value=1.0, value=0.0, step=0.05
)
max_hidro = float(gdf_modelo['potencia_hidro_mw'].max())
min_hidro_sinergia = st.sidebar.slider(
    "Sinergia: Potência Hídrica Mínima (MW):",
    min_value=0.0, max_value=max_hidro, value=0.0, step=10.0
)
max_linhas = float(gdf_modelo['km_linhas_transmissao'].max())
min_linhas = st.sidebar.slider(
    "Escoamento: Km Mínimos de Linhas:",
    min_value=0.0, max_value=max_linhas, value=0.0, step=20.0
)

# --- Lógica Principal (Modelo e Simulador) ---
if tipo_potencial == "Energia Solar":
    coluna_potencial = 'predicted_potential_SOLAR'
    titulo_mapa = 'Mapa de Potencial para Energia SOLAR em Goiás'
    features = model_solar.feature_names_in_
    df_importance = pd.DataFrame({
        'Feature': features, 
        'Importance': model_solar.feature_importances_
    }).sort_values(by='Importance', ascending=False)
    
    st.sidebar.subheader("Simulador Solar (What-If)")
    input_data = {}
    for feature in features:
        min_val, max_val, mean_val = (
            float(gdf_modelo[feature].min()),
            float(gdf_modelo[feature].max()),
            float(gdf_modelo[feature].mean())
        )
        input_data[feature] = st.sidebar.slider(
            f"Ajustar '{feature}'", min_val, max_val, mean_val, key=f"solar_{feature}"
        )
    predicted_score = model_solar.predict(pd.DataFrame([input_data]))[0]
    st.sidebar.metric(label="Score Solar Simulado:", value=f"{predicted_score:.3f}")
    
else: # Energia Eólica
    coluna_potencial = 'predicted_potential_EOLICO'
    titulo_mapa = 'Mapa de Potencial para Energia EÓLICA em Goiás'
    features = model_eolico.feature_names_in_
    df_importance = pd.DataFrame({
        'Feature': features, 
        'Importance': model_eolico.feature_importances_
    }).sort_values(by='Importance', ascending=False)

    st.sidebar.subheader("Simulador Eólico (What-If)")
    input_data = {}
    for feature in features:
        min_val, max_val, mean_val = (
            float(gdf_modelo[feature].min()),
            float(gdf_modelo[feature].max()),
            float(gdf_modelo[feature].mean())
        )
        input_data[feature] = st.sidebar.slider(
            f"Ajustar '{feature}'", min_val, max_val, mean_val, key=f"eolico_{feature}"
        )
    predicted_score = model_eolico.predict(pd.DataFrame([input_data]))[0]
    st.sidebar.metric(label="Score Eólico Simulado:", value=f"{predicted_score:.3f}")

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
        min_pot_filtrado = gdf_filtrado[coluna_potencial].min()
        max_pot_filtrado = gdf_filtrado[coluna_potencial].max()
        
        if (max_pot_filtrado - min_pot_filtrado) > 0:
            gdf_filtrado['cor_intensidade'] = (gdf_filtrado[coluna_potencial] - min_pot_filtrado) / (max_pot_filtrado - min_pot_filtrado)
        else:
            gdf_filtrado['cor_intensidade'] = 0.5

        color_range = [[25, 138, 255, 150], [90, 203, 107, 150], [255, 170, 0, 150], [255, 0, 0, 150]]
        
        indices = (gdf_filtrado['cor_intensidade'] * (len(color_range) - 1)).astype(int)
        gdf_filtrado['cor_rgba'] = indices.map(dict(enumerate(color_range)))

        view_state = pdk.ViewState(latitude=-15.93, longitude=-49.82, zoom=5.5, pitch=45)
        polygon_layer = pdk.Layer(
            'GeoJsonLayer', data=gdf_filtrado, opacity=0.8, stroked=True, filled=True,
            extruded=True, wireframe=True, get_elevation='cor_intensidade * 50000',
            get_fill_color='cor_rgba', get_line_color=[255, 255, 255, 100], pickable=True
        )
        tooltip = {
            "html": "<b>Município:</b> {nm_mun}<br/><b>Pot. Solar:</b> {predicted_potential_SOLAR_formatted}<br/><b>Pot. Eólico:</b> {predicted_potential_EOLICO_formatted}<br/><b>Pot. Hidro:</b> {potencia_hidro_mw} MW<br/><b>Linhas:</b> {km_linhas_transmissao} km",
            "style": {"backgroundColor": "steelblue", "color": "white"}
        }
        st.pydeck_chart(pdk.Deck(layers=[polygon_layer], initial_view_state=view_state, tooltip=tooltip, map_style='mapbox://styles/mapbox/light-v9'))

# --- ABA 2: RANKINGS E DEEP DIVE ---
with tab2:
    st.subheader("Ranking de Municípios (Filtrado)")
    ranking_cols = ['nm_mun', coluna_potencial, 'potencia_hidro_mw', 'km_linhas_transmissao', 'estacao_mais_proxima']
    ranking = gdf_filtrado[ranking_cols].sort_values(by=coluna_potencial, ascending=False)
    st.dataframe(ranking, use_container_width=True)
    
    csv = convert_df_to_csv(ranking)
    st.download_button("Download do Ranking como CSV", csv, f"ranking_{str(tipo_potencial).lower().replace(' ', '_')}.csv", 'text/csv')
    
    st.divider()
    st.subheader("Investigação Detalhada por Município")
    
    lista_municipios = ranking['nm_mun'].tolist()
    
    if not lista_municipios:
        st.info("Nenhum município selecionado pelos filtros para inspecionar.")
    else:
        municipio_selecionado = st.selectbox("Selecione um município para inspecionar:", lista_municipios)
        
        dados_municipio = gdf_modelo[gdf_modelo['nm_mun'] == municipio_selecionado].iloc[0]
        
        st.write(f"#### Métricas Principais: {municipio_selecionado}")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Score Solar", f"{dados_municipio['predicted_potential_SOLAR_formatted']}")
        col2.metric("Score Eólico", f"{dados_municipio['predicted_potential_EOLICO_formatted']}")
        col3.metric("Pot. Hídrica", f"{dados_municipio['potencia_hidro_mw']:.1f} MW")
        col4.metric("Linhas (km)", f"{dados_municipio['km_linhas_transmissao']:.1f} km")
        
        st.write("##### Análise de Sazonalidade (Estação Mais Próxima)")
        nome_estacao = dados_municipio['estacao_mais_proxima']
        st.write(f"Dados da estação: **{nome_estacao}**")
        
        radiacao_mensal, chuva_mensal = query_sazonalidade(con, nome_estacao)
        
        if radiacao_mensal is None or radiacao_mensal.empty:
            st.warning("Não foram encontrados dados de sazonalidade para esta estação.")
        else:
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

        col_raw1, col_raw2 = st.columns(2)
        with col_raw1:
            st.write("##### Usinas Registradas (ANEEL)")
            usinas_no_municipio = query_usinas(con, municipio_selecionado)
            if not usinas_no_municipio.empty:
                st.dataframe(usinas_no_municipio, use_container_width=True)
            else:
                st.info("Nenhuma usina registrada para este município.")

        with col_raw2:
            st.write("##### Linhas de Transmissão (ONS)")
            linhas_no_municipio = query_linhas(con, municipio_selecionado)
            if not linhas_no_municipio.empty:
                st.dataframe(linhas_no_municipio, use_container_width=True)
            else:
                st.info("Nenhuma linha de transmissão registrada para este município.")

# --- ABA 3: DETALHES DO MODELO ---
with tab3:
    st.subheader(f"Importância das Features ({tipo_potencial})")
    fig_features, ax_features = plt.subplots(figsize=(8, 6))
    sns.barplot(x='Importance', y='Feature', data=df_importance, hue='Feature', palette='viridis', ax=ax_features, legend=False)
    ax_features.set_title(f'Importância das Features ({tipo_potencial})')
    st.pyplot(fig_features)
    st.info("Esta visualização mostra quais fatores o modelo de Machine Learning mais considerou ao criar o score de potencial. Valores mais altos indicam maior influência na previsão.")