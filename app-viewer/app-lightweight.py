# app_2_fixed.py
import streamlit as st
import pandas as pd
import geopandas as gpd
import joblib
import duckdb
import plotly.express as px
import altair as alt
import json
import shapely.wkt
import shapely.wkb
from shapely.geometry import shape

# ==============================================================================
# CONFIGURAÇÃO DA PÁGINA
# ==============================================================================
st.set_page_config(layout="wide", page_title="Potencial Energético - Goiás")
st.title("Análise de Potencial Energético Renovável em Goiás")

# ==============================================================================
# FUNÇÕES CACHEADAS DE CARREGAMENTO
# ==============================================================================

@st.cache_data
def load_main_data():
    df = pd.read_parquet('df_modelo_simplificado.parquet')
    float_cols = ['predicted_potential_SOLAR', 'predicted_potential_EOLICO', 'potencia_hidro_mw', 'km_linhas_transmissao']
    for col in float_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], downcast='float')
    df['predicted_potential_SOLAR_formatted'] = df['predicted_potential_SOLAR'].round(3)
    df['predicted_potential_EOLICO_formatted'] = df['predicted_potential_EOLICO'].round(3)
    return df

@st.cache_resource
def load_models():
    return joblib.load('model_solar.joblib'), joblib.load('model_eolico.joblib')

@st.cache_resource
def get_duckdb_connection():
    con = duckdb.connect(database=':memory:')
    con.execute("CREATE TABLE clima AS SELECT * FROM read_parquet('clima_completo.parquet');")
    con.execute("CREATE TABLE usinas AS SELECT * FROM read_parquet('usinas_por_municipio.parquet');")
    con.execute("CREATE TABLE linhas AS SELECT * FROM read_parquet('linhas_por_municipio.parquet');")
    return con

@st.cache_data
def get_feature_ranges(df, features):
    return {
        f: {"min": float(df[f].min()), "max": float(df[f].max()), "mean": float(df[f].mean())}
        for f in features
    }

@st.cache_data
def query_sazonalidade(con, estacao):
    query = """
    SELECT 
        month(strptime("Data", '%Y/%m/%d')) AS Mes,
        avg("RADIACAO GLOBAL (Kj/m²)") AS radiacao,
        sum("PRECIPITAÇÃO TOTAL, HORÁRIO (mm)") AS precipitacao
    FROM clima
    WHERE "Estacao" = ?
    GROUP BY Mes
    ORDER BY Mes
    """
    df = con.execute(query, [estacao]).fetchdf().set_index('Mes').reindex(range(1, 13))
    return df['radiacao'], df['precipitacao']

@st.cache_data
def query_usinas(con, municipio):
    return con.execute("SELECT NomEmpreendimento, SigTipoGeracao, MdaPotenciaFiscalizadaKw FROM usinas WHERE nm_mun = ?", [municipio]).fetchdf()

@st.cache_data
def query_linhas(con, municipio):
    return con.execute("SELECT nom_linhadetransmissao, val_niveltensao_kv, comprimento_segmento_km FROM linhas WHERE nm_mun = ?", [municipio]).fetchdf()

@st.cache_data
def convert_df_to_csv(df):
    return df.to_csv(index=False).encode('utf-8')

@st.cache_data(show_spinner=False)
def make_sazonalidade_chart(radiacao_mensal, chuva_mensal, municipio, estacao):
    """Gera o gráfico de sazonalidade com matplotlib, mas de forma otimizada e cacheada."""
    fig, ax1 = plt.subplots(figsize=(10, 4))
    ax1.set_xlabel('Mês')
    ax1.set_ylabel('Radiação Solar Média (Kj/m²)', color='orange')
    ax1.plot(
        radiacao_mensal.index, radiacao_mensal.values,
        color='orange', alpha=0.8, linewidth=2.5, marker='o', label='Radiação Solar'
    )
    ax1.tick_params(axis='y', labelcolor='orange')
    ax2 = ax1.twinx()
    ax2.set_ylabel('Precipitação Média (mm)', color='blue')
    ax2.plot(
        chuva_mensal.index, chuva_mensal.values,
        color='blue', alpha=0.8, linewidth=2.5, marker='s', label='Precipitação'
    )
    ax2.tick_params(axis='y', labelcolor='blue')
    fig.suptitle(f'Sazonalidade em {municipio} (Estação: {estacao})')
    fig.tight_layout()
    return fig

# ==============================================================================
# CARREGAMENTO INICIAL
# ==============================================================================
gdf_modelo = load_main_data()
model_solar, model_eolico = load_models()
con = get_duckdb_connection()

# ==============================================================================
# SIDEBAR
# ==============================================================================
st.sidebar.header("Configurações de Análise")
tipo_potencial = st.sidebar.selectbox("Tipo de potencial:", ("Energia Solar", "Energia Eólica"))

st.sidebar.subheader("Filtros Globais")
min_potencial = st.sidebar.slider("Potencial Mínimo:", 0.0, 1.0, 0.0, 0.05)
max_hidro = float(gdf_modelo['potencia_hidro_mw'].max())
min_hidro = st.sidebar.slider("Potência Hídrica Mínima (MW):", 0.0, max_hidro, 0.0, 10.0)
max_linhas = float(gdf_modelo['km_linhas_transmissao'].max())
min_linhas = st.sidebar.slider("Km Mínimos de Linhas:", 0.0, max_linhas, 0.0, 20.0)

# ==============================================================================
# LÓGICA DO MODELO
# ==============================================================================
if tipo_potencial == "Energia Solar":
    col_pot = 'predicted_potential_SOLAR'
    model, title = model_solar, 'Mapa de Potencial Solar'
else:
    col_pot = 'predicted_potential_EOLICO'
    model, title = model_eolico, 'Mapa de Potencial Eólico'

features = model.feature_names_in_
df_importance = pd.DataFrame({'Feature': features, 'Importance': model.feature_importances_}).sort_values('Importance', ascending=False)

st.sidebar.subheader(f"Simulador {tipo_potencial} (What-If)")
ranges = get_feature_ranges(gdf_modelo, features)
input_data = {f: st.sidebar.slider(f"{f}", ranges[f]["min"], ranges[f]["max"], ranges[f]["mean"]) for f in features}
predicted = model.predict(pd.DataFrame([input_data]))[0]
st.sidebar.metric(f"Score Simulado ({tipo_potencial})", f"{predicted:.3f}")

# ==============================================================================
# FILTROS GLOBAIS
# ==============================================================================
mask = (
    (gdf_modelo[col_pot] >= min_potencial)
    & (gdf_modelo['potencia_hidro_mw'] >= min_hidro)
    & (gdf_modelo['km_linhas_transmissao'] >= min_linhas)
)
gdf_filtrado = gdf_modelo.loc[mask]
st.sidebar.info(f"{len(gdf_filtrado)} de {len(gdf_modelo)} municípios exibidos.")

# ==============================================================================
# ABAS
# ==============================================================================
tab1, tab2, tab3, tab4 = st.tabs(["🗺️ Mapa Potencial", "📊 Rankings", "🤖 Modelo", "🔌 Linhas"])

# ==============================================================================
# MAPA
# ==============================================================================
with tab1:
    st.subheader(title)

    if gdf_filtrado.empty:
        st.warning("Nenhum município encontrado com esses filtros.")
    else:
        # 🔹 Detecta e converte geometria automaticamente
        geom_sample = gdf_filtrado["geometry"].iloc[0]

        if isinstance(geom_sample, (bytes, bytearray)):
            gdf_filtrado["geometry"] = gdf_filtrado["geometry"].apply(lambda x: shapely.wkb.loads(x))
        elif isinstance(geom_sample, str):
            try:
                gdf_filtrado["geometry"] = gdf_filtrado["geometry"].apply(shapely.wkt.loads)
            except Exception:
                gdf_filtrado["geometry"] = gdf_filtrado["geometry"].apply(lambda x: shape(json.loads(x)))

        # 🔹 Cria GeoDataFrame
        gdf_filtrado = gpd.GeoDataFrame(gdf_filtrado, geometry="geometry", crs="EPSG:4674")

        # 🔹 Corrige e simplifica
        gdf_filtrado = gdf_filtrado[gdf_filtrado.is_valid].copy()
        gdf_filtrado["geometry"] = gdf_filtrado["geometry"].simplify(0.01, preserve_topology=True)

        gdf_filtrado["nm_mun"] = (
            gdf_filtrado["nm_mun"]
            .astype(str)
            .str.encode("utf-8", "ignore")
            .str.decode("utf-8")
        )

        geojson_data = json.loads(gdf_filtrado.to_json())

        fig = px.choropleth_mapbox(
            gdf_filtrado,
            geojson=geojson_data,
            locations=gdf_filtrado.index,
            color=col_pot,
            hover_name="nm_mun",
            mapbox_style="carto-positron",
            zoom=5.5,
            center={"lat": -15.93, "lon": -49.82},
            opacity=0.6,
        )

        st.plotly_chart(fig, use_container_width=True)

# ==============================================================================
# RANKINGS
# ==============================================================================
with tab2:
    st.subheader("Ranking de Municípios (Filtrado)")
    ranking_cols = ['nm_mun', col_pot, 'potencia_hidro_mw', 'km_linhas_transmissao', 'estacao_mais_proxima']
    ranking = gdf_filtrado[ranking_cols].sort_values(by=col_pot, ascending=False)
    st.dataframe(ranking, use_container_width=True)

    csv = convert_df_to_csv(ranking)
    st.download_button("Baixar CSV do Ranking", csv, f"ranking_{tipo_potencial.lower()}.csv")

# ==============================================================================
# IMPORTÂNCIA DAS FEATURES
# ==============================================================================
with tab3:
    st.subheader(f"Importância das Features - {tipo_potencial}")
    chart = alt.Chart(df_importance).mark_bar().encode(
        x='Importance',
        y=alt.Y('Feature', sort='-x'),
        color='Importance'
    )
    st.altair_chart(chart, use_container_width=True)
    st.caption("Quanto maior a importância, maior o peso da variável na previsão do potencial energético.")
