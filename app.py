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

def analisar_eficiencia_com_dados(linhas_brutas):
    """
    Processa as linhas de texto brutas do ficheiro, ignora metadados,
    contorna a quebra do Grand Total e executa o motor matemático.
    """
    # 1. Localizar dinamicamente a linha do cabeçalho real
    linhas_a_pular = 0
    for idx, linha in enumerate(linhas_brutas):
        if 'Item list position' in linha:
            linhas_a_pular = idx
            break

    # 2. Processar apenas as linhas de dados puras, ignorando o lixo estrutural e Grand Total
    linhas_dados = []
    for linha in linhas_brutas[linhas_a_pular+1:]:
        partes = linha.strip().split(',')
        if not partes or 'Grand total' in linha or partes[0] == '':
            continue
        linhas_dados.append(partes[:3])

    # Criar o DataFrame de forma limpa com 3 colunas estritas
    nomes_colunas = [col.strip() for col in linhas_brutas[linhas_a_pular].strip().split(',')]
    df_limpo = pd.DataFrame(linhas_dados, columns=nomes_colunas)

    col_posicao = df_limpo.columns[0]
    col_views = df_limpo.columns[1]
    col_clicks = df_limpo.columns[2]

    # 3. Conversão numérica e limpeza de ruído técnico (Posição -1)
    df_limpo[col_posicao] = pd.to_numeric(df_limpo[col_posicao], errors='coerce')
    df_limpo[col_views] = pd.to_numeric(df_limpo[col_views], errors='coerce')
    df_limpo[col_clicks] = pd.to_numeric(df_limpo[col_clicks], errors='coerce')
    df_limpo = df_limpo.dropna().copy()

    df_limpo = df_limpo[df_limpo[col_posicao] != -1]
    df_limpo = df_limpo.sort_values(by=col_posicao).reset_index(drop=True)

    # 4. Cálculos de Percentagens Cumulativas
    total_views = df_limpo[col_views].sum()
    total_clicks = df_limpo[col_clicks].sum()

    df_limpo['cum_views_pct'] = (df_limpo[col_views].cumsum() / total_views) * 100
    df_limpo['cum_clicks_pct'] = (df_limpo[col_clicks].cumsum() / total_clicks) * 100
    df_limpo['eficiencia_marginal'] = df_limpo['cum_clicks_pct'] - df_limpo['cum_views_pct']

    # 5. Localização dos Marcos Críticos de Decisão
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

# Lógica de Renderização da Aplicação Web
if ficheiro_carregado is not None:
    try:
        # CORREÇÃO CRÍTICA: Ler o ficheiro como linhas de texto descodificado (UTF-8)
        # Isto evita passar o CSV bruto diretamente para o pd.read_csv e contorna o erro de tokenização
        linhas_ficheiro = [linha.decode("utf-8") for linha in ficheiro_carregado.readlines()]
        
        # Executar o motor de processamento matemático passando as linhas brutas
        df, pos_corte, pos_75, pos_recomendada, cliques_rec, p_otimo, col_pos, col_v, col_c = analisar_eficiencia_com_dados(linhas_ficheiro)
        
        # --- PASSO 1: DASHBOARD DE MÉTRICAS (KPI CARDS) ---
        st.subheader("📊 Resultados e Diretrizes para o Salesforce (SFCC)")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(label="Ponto de Maior Eficiência Matemática", value=f"Posição {pos_corte}")
            st.caption(f"Pico de atenção do utilizador (Diferencial Δ: {p_otimo['eficiencia_marginal']:.2f}%)")
            
        with col2:
            st.metric(label="Marco de Volume Crítico (75% dos Cliques)", value=f"Posição {pos_75}")
            st.caption("A partir desta posição o tráfego restante torna-se residual.")
            
        with col3:
            st.markdown(f"""
            <div style="background-color:#b91c1c;padding:12px;border-radius:8px;text-align:center;">
                <p style="margin:0;font-size:14px;font-weight:bold;color:white;text-transform:uppercase;">Cutoff Parfois Recomendado</p>
                <h2 style="margin:0;color:white;font-size:32px;font-weight:bold;">Posição {pos_recomendada}</h2>
            </div>
            """, unsafe_allow_html=True)
            st.caption(f"Arredondado para 2 colunas. Garante manualmente **{cliques_rec:.1f}%** de todos os cliques úteis.")

        st.info(f"**Nota operacional para a equipa de Merchandising:** Devem fixar produtos com *pins* manuais até à **Posição {pos_recomendada}**. Da posição seguinte em diante, removam qualquer bloqueio estático para que o algoritmo do Salesforce reordene a página automaticamente com base em stock e *Sales Velocity* (automatizando os restantes **{(100-cliques_rec):.1f}%** de cliques).")
        st.markdown("---")

        # --- PASSO 2: GERAR E MOSTRAR O GRÁFICO DIRETAMENTE NA PÁGINA ---
        st.subheader("📈 Análise Visual das Curvas de Acumulação (Foco Total nas Linhas Verticais)")
        
        sns.set_theme(style="whitegrid")
        fig, ax1 = plt.subplots(figsize=(12, 5.5))

        # Configurar limites do gráfico de forma fluida
        limite_eixo_x = max(pos_corte, pos_75, pos_recomendada)
        limite_eixo_x = max(limite_eixo_x + 30, 120) 
        df_visualizacao = df[df[col_pos] <= limite_eixo_x]

        # Desenhar curvas suavizadas de acumulação (Sem marcadores e limpas)
        ax1.plot(df_visualizacao[col_pos], df_visualizacao['cum_clicks_pct'], color='#1e6b27', label='% Cliques Acumulados', linewidth=2.5)
        ax1.plot(df_visualizacao[col_pos], df_visualizacao['cum_views_pct'], color='#1d4ed8', label='% Visualizações Acumuladas', linewidth=2.5)

        ax1.set_xlabel('Posição no Catálogo (PLP)', fontsize=11, fontweight='bold', labelpad=8)
        ax1.set_ylabel('Percentagem Acumulada (%)', fontsize=11, fontweight='bold', labelpad=8)
        ax1.set_ylim(0, 115) 
        ax1.set_xlim(-2, limite_eixo_x)
        ax1.tick_params(axis='both', which='major', labelsize=9)

        # Traçar barreiras verticais nítidas e fortemente demarcadas de diagnóstico
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
        
        # Renderizar o gráfico nativamente na interface web do Streamlit
        st.pyplot(fig)
        
    except Exception as e:
        st.error(f"Ocorreu um erro ao processar o ficheiro: {e}. Certifica-te de que carregaste um relatório padrão do GA4.")
else:
    st.info("Aguardando upload do ficheiro CSV na barra lateral para iniciar a análise.")
