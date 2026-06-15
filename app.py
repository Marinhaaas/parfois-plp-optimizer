import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st

# Configuração inicial da página web do Streamlit
st.set_page_config(
    page_title="Parfois - Otimizador de PLPs",
    page_icon="🎯",
    layout="wide"
)

# Título Principal e Subtítulo na Interface Web
st.title("🎯 Parfois - Otimizador de Catálogo & Cutoff de PLPs")
st.markdown("Carrega o relatório de listagem exportado do GA4 para calcular matematicamente o ponto de corte ideal para dispositivos móveis.")
st.markdown("---")

# Componente Lateral de Upload do Ficheiro CSV
st.sidebar.header("Configurações de Entrada")
ficheiro_carregado = st.sidebar.file_uploader("Carrega o ficheiro CSV do GA4", type=["csv"])

def analisar_eficiencia_com_dados(df_bruto):
    """
    Processa os dados de forma idêntica ao script original, 
    mas adaptado para interagir diretamente com a interface web.
    """
    # 1. Localizar dinamicamente a linha do cabeçalho real nos dados carregados
    # Como o Streamlit nos dá os dados em memória, podemos fazer o reset do cabeçalho
    df_bruto.columns = [str(col).strip() for col in df_bruto.columns]
    
    # Se o Pandas leu os metadados como colunas, precisamos de localizar a linha certa
    linhas_a_pular = None
    for idx, row in df_bruto.iterrows():
        # Verificar se alguma célula contém a string chave do cabeçalho
        if any('Item list position' in str(cell) for cell in row.values):
            linhas_a_pular = idx
            break
            
    if linhas_a_pular is not None:
        # Reconfigurar as colunas com base na linha correta localizada
        novas_colunas = [str(cell).strip() for cell in df_bruto.iloc[linhas_a_pular].values]
        df_limpo = df_bruto.iloc[linhas_a_pular+1:].copy()
        df_limpo.columns = novas_colunas
    else:
        df_limpo = df_bruto.copy()

    col_posicao = df_limpo.columns[0]
    col_views = df_limpo.columns[1]
    col_clicks = df_limpo.columns[2]

    # 2. Conversão numérica e limpeza de dados estruturais e ruídos (Grand Total e Posição -1)
    df_limpo = df_limpo.dropna(subset=[col_posicao]).copy()
    df_limpo = df_limpo[~df_limpo.apply(lambda row: row.astype(str).str.contains('Grand total').any(), axis=1)]
    
    df_limpo[col_posicao] = pd.to_numeric(df_limpo[col_posicao], errors='coerce')
    df_limpo[col_views] = pd.to_numeric(df_limpo[col_views], errors='coerce')
    df_limpo[col_clicks] = pd.to_numeric(df_limpo[col_clicks], errors='coerce')
    df_limpo = df_limpo.dropna().copy()

    df_limpo = df_limpo[df_limpo[col_posicao] != -1]
    df_limpo = df_limpo.sort_values(by=col_posicao).reset_index(drop=True)

    # 3. Cálculos de Percentagens Cumulativas
    total_views = df_limpo[col_views].sum()
    total_clicks = df_limpo[col_clicks].sum()

    df_limpo['cum_views_pct'] = (df_limpo[col_views].cumsum() / total_views) * 100
    df_limpo['cum_clicks_pct'] = (df_limpo[col_clicks].cumsum() / total_clicks) * 100
    df_limpo['eficiencia_marginal'] = df_limpo['cum_clicks_pct'] - df_limpo['cum_views_pct']

    # 4. Localização dos Marcos Críticos de Decisão
    idx_max_eficiencia = df_limpo['eficiencia_marginal'].idxmax()
    ponto_otimo = df_limpo.loc[idx_max_eficiencia]
    posicao_corte = int(ponto_otimo[col_posicao])

    idx_75_clicks = (df_limpo['cum_clicks_pct'] >= 75).idxmax()
    ponto_75_clicks = df_limpo.loc[idx_75_clicks]
    posicao_75_clicks = int(ponto_75_clicks[col_posicao])

    posicao_media_bruta = (posicao_corte + posicao_75_clicks) / 2
    posicao_corte_recomendado = int(round(posicao_media_bruta / 2) * 2)
    
    linha_proxima = (df_limpo[col_posicao] - posicao_corte_recomendado).abs().idxmin()
    cliques_no_corte_recomendado = df_limpo.loc[linha_proxima, 'cum_clicks_pct']

    return df_limpo, posicao_corte, posicao_75_clicks, posicao_corte_recomendado, cliques_no_corte_recomendado, ponto_otimo, col_posicao, col_views, col_clicks

# Lógica de Renderização do Site
if ficheiro_carregado is not None:
    try:
        # Ler o arquivo pulando a validação inicial de cabeçalho para o parser nativo do Streamlit
        # Lemos como object para garantir a manipulação limpa de texto nas linhas iniciais de comentários do GA4
        df_input = pd.read_csv(ficheiro_carregado, header=None, index_col=False)
        
        # Executar o motor de processamento matemático
        df, pos_corte, pos_75, pos_recomendada, cliques_rec, p_otimo, col_pos, col_v, col_c = analisar_eficiencia_com_dados(df_input)
        
        # --- PASSO 1: RENDERIZAR MÉTRICAS EM FORMATO DE DASHBOARD (KPI CARDS) ---
        st.subheader("📊 Resultados e Diretrizes para o Salesforce (SFCC)")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(label="Ponto de Maior Eficiência Matemática", value=f"Posição {pos_corte}")
            st.caption(f"Pico de atenção do utilizador (Diferencial Δ: {p_otimo['eficiencia_marginal']:.2f}%)")
            
        with col2:
            st.metric(label="Marco de Volume Crítico (75% dos Cliques)", value=f"Posição {pos_75}")
            st.caption("A partir desta posição o tráfego restante torna-se residual.")
            
        with col3:
            # Grande destaque visual para a recomendação final de negócio
            st.markdown(f"""
            <div style="background-color:#b91c1c;padding:12px;border-radius:8px;text-align:center;">
                <p style="margin:0;font-size:14px;font-weight:bold;color:white;text-transform:uppercase;">Cutoff Parfois Recomendado</p>
                <h2 style="margin:0;color:white;font-size:32px;font-weight:bold;">Posição {pos_recomendada}</h2>
            </div>
            """, unsafe_allow_html=True)
            st.caption(f"Arredondado para 2 colunas. Garante manualmente **{cliques_rec:.1f}%** de todos os cliques úteis.")

        st.markdown(f"**Nota operacional para a equipa de Merchandising:** Devem fixar produtos com *pins* manuais até à **Posição {pos_recomendada}**. Da posição seguinte em diante, removam qualquer bloqueio estático para que o algoritmo do Salesforce reordene a página automaticamente com base em stock e *Sales Velocity* (automatizando os restantes **{(100-cliques_rec):.1f}%** de cliques).")
        st.markdown("---")

        # --- PASSO 2: GERAR E MOSTRAR O GRÁFICO DIRETAMENTE NA PÁGINA ---
        st.subheader("📈 Análise Visual das Curvas de Acumulação")
        
        sns.set_theme(style="whitegrid")
        fig, ax1 = plt.subplots(figsize=(12, 5.5))

        # Configurar limites do gráfico de forma fluida
        limite_eixo_x = max(pos_corte, pos_75, pos_recomendada)
        limite_eixo_x = max(limite_eixo_x + 30, 120) 
        df_visualizacao = df[df[col_pos] <= limite_eixo_x]

        # Desenhar curvas suavizadas de acumulação
        ax1.plot(df_visualizacao[col_pos], df_visualizacao['cum_clicks_pct'], color='#1e6b27', label='% Cliques Acumulados', linewidth=2.5)
        ax1.plot(df_visualizacao[col_pos], df_visualizacao['cum_views_pct'], color='#1d4ed8', label='% Visualizações Acumuladas', linewidth=2.5)

        ax1.set_xlabel('Posição no Catálogo (PLP)', fontsize=11, fontweight='bold', labelpad=8)
        ax1.set_ylabel('Percentagem Acumulada (%)', fontsize=11, fontweight='bold', labelpad=8)
        ax1.set_ylim(0, 115) 
        ax1.set_xlim(-2, limite_eixo_x)
        ax1.tick_params(axis='both', which='major', labelsize=9)

        # Traçar barreiras verticais nítidas de diagnóstico
        ax1.axvline(x=pos_corte, color='#d97706', linestyle='--', linewidth=3.0, alpha=0.9, label=f'Eficiência Máxima (Pos. {pos_corte})')
        ax1.axvline(x=pos_75, color='#6b21a8', linestyle=':', linewidth=3.0, alpha=0.9, label=f'Meta 75% Cliques (Pos. {pos_75})')
        ax1.axvline(x=pos_recomendada, color='#dc2626', linestyle='-.', linewidth=5.0, label=f'CUTOFF PARFOIS (Pos. {pos_recomendada})')

        # Tags Dinâmicas Alinhadas Geometricamente
        ax1.annotate(f'Eficiência Máxima: Pos {pos_corte}\nΔ = {p_otimo["eficiencia_marginal"]:.2f}%', 
                     xy=(pos_corte, p_otimo['cum_clicks_pct']),
                     xytext=(pos_corte + (limite_eixo_x * 0.04), p_otimo['cum_clicks_pct'] - 22),
                     arrowprops=dict(facecolor='#d97706', edgecolor='#d97706', shrink=0.05, width=1.5, headwidth=5, headlength=5),
                     fontweight='bold', fontsize=9, bbox=dict(boxstyle="round,pad=0.3", fc="#fef3c7", alpha=0.95, ec="#d97706", lw=1.5))

        ax1.annotate(f'Marco 75% Cliques: Pos {pos_75}',
                     xy=(pos_75, df.loc[(df[col_pos] - pos_75).abs().idxmin(), 'cum_clicks_pct']),
                     xytext=(pos_75 - (limite_eixo_x * 0.16), df.loc[(df[col_pos] - pos_75).abs().idxmin(), 'cum_clicks_pct'] + 12),
                     arrowprops=dict(facecolor='#6b21a8', edgecolor='#6b21a8', shrink=0.05, width=1.5, headwidth=5, headlength=5),
                     fontweight='bold', fontsize=9, bbox=dict(boxstyle="round,pad=0.3", fc="#f3e8ff", alpha=0.95, ec="#6b21a8", lw=1.5))

        ax1.annotate(f'RECOMENDADO: Posição {pos_recomendada}\nCaptura: {cliques_rec:.1f}% dos Cliques Úteis',
                     xy=(pos_recomendada, cliques_rec),
                     xytext=(pos_recomendada - (limite_eixo_x * 0.22), 103), 
                     arrowprops=dict(facecolor='#dc2626', edgecolor='#dc2626', shrink=0.05, width=2.5, headwidth=7, headlength=7),
                     fontweight='bold', fontsize=10, color='white',
                     bbox=dict(boxstyle="round,pad=0.4", fc="#b91c1c", alpha=1, ec="#7f1d1d", lw=2))

        ax1.legend(loc='lower right', frameon=True, facecolor='white', edgecolor='#e5e7eb', fontsize=9)
        plt.tight_layout()
        
        # O Streamlit renderiza o gráfico de Matplotlib nativamente na página web
        st.pyplot(fig)
        
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar o ficheiro: {e}. Certifica-te de que carregaste um relatório padrão do GA4.")
else:
    # Estado inicial do site quando ainda não foi feito nenhum upload
    st.info("Aguardando upload do ficheiro CSV na barra lateral para iniciar a análise.")