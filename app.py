import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import re

# Configuração inicial da página web do Streamlit
st.set_page_config(
    page_title="Parfois - Otimizador de PLPs Mestre",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 Parfois - Centro de Otimização de Catálogo & PLPs")
st.markdown("Carrega o relatório mestre do GA4 para mapear a eficiência e obter as diretrizes de corte automáticas para o Salesforce (SFCC).")
st.markdown("---")

# Componente Lateral de Upload do Ficheiro CSV
st.sidebar.header("⚙️ Configurações de Entrada")
ficheiro_carregado = st.sidebar.file_uploader("Carrega o CSV Mestre do GA4 (Layout Horizontal ou Vertical)", type=["csv"])

def parse_ga4_universal(linhas_brutas):
    """
    Motor Híbrido: Detecta o formato do ficheiro, aplica o filtro estrito de Regex
    para isolar apenas as PLPs principais e constrói as tabelas na memória.
    """
    idx_pos = None
    for idx, linha in enumerate(linhas_brutas):
        if 'Item list position' in linha:
            idx_pos = idx
            break
            
    if idx_pos is None:
        return {}, "Não foi possível localizar a dimensão 'Item list position' no ficheiro."
        
    linha_metrica = [m.strip() for m in linhas_brutas[idx_pos].strip().split(',')]
    linha_superior = [c.strip() for c in linhas_brutas[idx_pos-1].strip().split(',')] if idx_pos > 0 else []
    
    is_wide_layout = len(linha_superior) > 1 and 'Item list name' in linha_superior[0]
    cat_dict = {}
    
    # Expressão Regular Estrita: Começa com 'PLP - ' e NÃO contém '/'
    padrao_regex = re.compile(r"^PLP - [^/]+$")
    
    if is_wide_layout:
        # --- LAYOUT MATRIZ HORIZONTAL (WIDE) ---
        category_columns = {}
        for i in range(1, len(linha_superior)-1, 2):
            c_name = linha_superior[i]
            if c_name and c_name != 'Totals' and c_name != 'Item list name':
                category_columns[c_name] = {
                    'views_idx': i,
                    'clicks_idx': i+1
                }
                
        data_rows = []
        for linha in linhas_brutas[idx_pos+1:]:
            partes = [p.strip() for p in linha.strip().split(',')]
            if not partes or 'Grand total' in linha or partes[0] == '':
                continue
            data_rows.append(partes)
            
        for c_name, idxs in category_columns.items():
            if padrao_regex.match(c_name):
                v_idx = idxs['views_idx']
                c_idx = idxs['clicks_idx']
                
                rows_cat = []
                for r in data_rows:
                    if len(r) > max(v_idx, c_idx):
                        rows_cat.append([r[0], r[v_idx], r[c_idx]])
                        
                df_cat = pd.DataFrame(rows_cat, columns=['Item list position', 'Items viewed in list', 'Items clicked in list'])
                cat_dict[c_name] = df_cat
                
    else:
        # --- LAYOUT VERTICAL ANTIGO ---
        linhas_dados = []
        for linha in linhas_brutas[idx_pos+1:]:
            partes = [p.strip() for p in linha.strip().split(',')]
            if not partes or 'Grand total' in linha or partes[0] == '':
                continue
            if len(partes) >= 4:
                linhas_dados.append(partes[:4])
            else:
                linhas_dados.append(partes[:3])
                
        df_all = pd.DataFrame(linhas_dados, columns=linha_metrica[:len(linhas_dados[0])])
        df_all.columns = [c.strip() for c in df_all.columns]
        
        if "Item list name" in df_all.columns:
            df_all = df_all[df_all["Item list name"].astype(str).apply(lambda x: bool(padrao_regex.match(x)))].copy()
            for c_name in df_all["Item list name"].unique():
                sub_df = df_all[df_all["Item list name"] == c_name][['Item list position', 'Items viewed in list', 'Items clicked in list']].copy()
                cat_dict[c_name] = sub_df
        else:
            cat_dict["Categoria Unificada"] = df_all[['Item list position', 'Items viewed in list', 'Items clicked in list']].copy()
            
    return cat_dict, None

def calcular_metricas_categoria(df_cat):
    """Auxiliar para limpar dados e calcular marcos decisórios de uma categoria."""
    df_f = df_cat.copy()
    df_f['Item list position'] = pd.to_numeric(df_f['Item list position'], errors='coerce')
    df_f['Items viewed in list'] = pd.to_numeric(df_f['Items viewed in list'], errors='coerce')
    df_f['Items clicked in list'] = pd.to_numeric(df_f['Items clicked in list'], errors='coerce')
    df_f = df_f.dropna().copy()
    df_f = df_f[df_f['Item list position'] != -1]
    df_f = df_f.sort_values(by='Item list position').reset_index(drop=True)
    
    t_views = df_f['Items viewed in list'].sum()
    t_clicks = df_f['Items clicked in list'].sum()
    
    if t_views == 0 or t_clicks == 0:
        return None, 0, 0, 0, 0, 0, None
        
    df_f['cum_views_pct'] = (df_f['Items viewed in list'].cumsum() / t_views) * 100
    df_f['cum_clicks_pct'] = (df_f['Items clicked in list'].cumsum() / t_clicks) * 100
    df_f['eficiencia_marginal'] = df_f['cum_clicks_pct'] - df_f['cum_views_pct']
    
    idx_max = df_f['eficiencia_marginal'].idxmax()
    ponto_otimo = df_f.loc[idx_max]
    pos_corte = int(ponto_otimo['Item list position'])
    
    idx_75 = (df_f['cum_clicks_pct'] >= 75).idxmax()
    pos_75 = int(df_f.loc[idx_75, 'Item list position'])
    
    pos_media_bruta = (pos_corte + pos_75) / 2
    pos_recomendada = int(round(pos_media_bruta / 2) * 2)
    
    linha_prox = (df_f['Item list position'] - pos_recomendada).abs().idxmin()
    cliques_rec = df_f.loc[linha_prox, 'cum_clicks_pct']
    
    return df_f, t_views, t_clicks, pos_corte, pos_75, pos_recomendada, cliques_rec, ponto_otimo

# Fluxo de Renderização Principal
if ficheiro_carregado is not None:
    try:
        linhas_ficheiro = [linha.decode("utf-8") for linha in ficheiro_carregado.readlines()]
        catalogo_categorias, erro = parse_ga4_universal(linhas_ficheiro)
        
        if erro:
            st.error(erro)
            st.stop()
            
        # --- PROCESSAMENTO DA REVOLUCIONÁRIA METRICA BULK (OVERVIEW GLOBAL) ---
        dados_overview = []
        df_processados = {}
        
        for cat_nome, df_bruto in catalogo_categorias.items():
            res = calcular_metricas_categoria(df_bruto)
            if res[0] is not None:
                df_limpo, tv, tc, pc, p75, prec, crec, p_ot = res
                df_processados[cat_nome] = (df_limpo, pc, p75, prec, crec, p_ot)
                ctr_geral = (tc / tv * 100) if tv > 0 else 0
                
                dados_overview.append({
                    "Categoria Principal": cat_nome,
                    "Visualizações Totais": tv,
                    "Cliques Totais": tc,
                    "CTR Geral (%)": round(ctr_geral, 3),
                    "Eficiência Máxima": f"Pos {pc}",
                    "Marco 75% Cliques": f"Pos {p75}",
                    "CUTOFF RECOMENDADO (SFCC)": prec,
                    "% Cliques Garantidos": f"{crec:.1f}%"
                })
                
        df_overview = pd.DataFrame(dados_overview).sort_values(by="Cliques Totais", ascending=False).reset_index(drop=True)
        
        # --- CRIAÇÃO DAS ABAS VIRTUAIS NA INTERFACE WEB ---
        tab_global, tab_individual = st.tabs(["🌍 Overview Global", "📈 Análise por Categoria"])
        
        # ---- ABA 1: OVERVIEW GLOBAL (VISÃO EXECUTIVA) ----
        with tab_global:
            st.subheader("📊 Matriz Geral de Decisões de Catálogo")
            st.markdown("Esta tabela consolida todas as PLPs extraídas, ordenadas por volume de interação. Usa esta visão para auditorias rápidas do Salesforce.")
            
            # Formatação visual da tabela nativa do Streamlit
            st.dataframe(
                df_overview, 
                use_container_width=True,
                column_config={
                    "Visualizações Totais": st.column_config.NumberColumn(format="%d"),
                    "Cliques Totais": st.column_config.NumberColumn(format="%d"),
                    "CUTOFF RECOMENDADO (SFCC)": st.column_config.NumberColumn(help="Inserir este valor exato como limite manual no Salesforce.")
                }
            )
            
            # Botão para exportar a listagem completa de cutoffs para Excel/CSV
            st.download_button(
                label="📥 Exportar Tabela de Cutoffs Geral (CSV)",
                data=df_overview.to_csv(index=False).encode('utf-8'),
                file_name="tabela_geral_cutoffs_parfois.csv",
                mime="text/csv"
            )
            
        # ---- ABA 2: ANÁLISE INDIVIDUAL (DETALHE OPERACIONAL) ----
        with tab_individual:
            lista_opcoes = sorted(list(df_processados.keys()))
            categoria_selecionada = st.selectbox("Escolha a Categoria Principal para inspecionar:", lista_opcoes)
            
            # Recuperar cálculos pré-processados
            df_filtrado, pos_corte, pos_75, pos_recomendada, cliques_rec, ponto_otimo = df_processados[categoria_selecionada]
            
            # Cartões de Métricas (KPI Cards)
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric(label="Eficiência Matemática Máxima", value=f"Posição {pos_corte}")
                st.caption(f"Zénite de engajamento (Diferencial Δ: {ponto_otimo['eficiencia_marginal']:.2f}%)")
            with c2:
                st.metric(label="Meta 75% dos Cliques Úteis", value=f"Posição {pos_75}")
                st.caption("Fronteira crítica onde o tráfego desaba.")
            with c3:
                st.markdown(f"""
                <div style="background-color:#b91c1c;padding:12px;border-radius:8px;text-align:center;">
                    <p style="margin:0;font-size:12px;font-weight:bold;color:white;text-transform:uppercase;">Cutoff Mobile Recomendado</p>
                    <h2 style="margin:0;color:white;font-size:28px;font-weight:bold;">Posição {pos_recomendada}</h2>
                </div>
                """, unsafe_allow_html=True)
                st.caption(f"Garante a captura visual de **{cliques_rec:.1f}%** das intenções de clique.")

            st.info(f"**Diretriz Operacional:** Fixar produtos manualmente via *pins* até à **Posição {pos_recomendada}**. A partir daí, o Salesforce (SFCC) assume a automação inteligente (gerindo os restantes **{(100-cliques_rec):.1f}%** de cliques).")

            # Gerar Gráfico Ultra-Focado nas Linhas Verticais
            sns.set_theme(style="whitegrid")
            fig, ax1 = plt.subplots(figsize=(12, 5.2))

            limite_x = max(pos_corte, pos_75, pos_recomendada)
            limite_x = max(limite_x + 30, 120)
            df_vis = df_filtrado[df_filtrado['Item list position'] <= limite_x]

            ax1.plot(df_vis['Item list position'], df_vis['cum_clicks_pct'], color='#1e6b27', label='% Cliques Acumulados', linewidth=2.5)
            ax1.plot(df_vis['Item list position'], df_vis['cum_views_pct'], color='#1d4ed8', label='% Visualizações Acumuladas', linewidth=2.5)

            ax1.set_xlabel('Posição no Catálogo (PLP)', fontsize=11, fontweight='bold', labelpad=8)
            ax1.set_ylabel('Percentagem Acumulada (%)', fontsize=11, fontweight='bold', labelpad=8)
            ax1.set_ylim(0, 115)
            ax1.set_xlim(-2, limite_x)
            ax1.tick_params(axis='both', which='major', labelsize=9, width=2)

            # Linhas Verticais Altamente Visíveis e Grossas
            ax1.axvline(x=pos_corte, color='#d97706', linestyle='--', linewidth=3.0, alpha=0.9, label=f'Eficiência Máxima (Pos. {pos_corte})')
            ax1.axvline(x=pos_75, color='#6b21a8', linestyle=':', linewidth=3.0, alpha=0.9, label=f'Meta 75% Cliques (Pos. {pos_75})')
            ax1.axvline(x=pos_recomendada, color='#dc2626', linestyle='-.', linewidth=5.0, label=f'CUTOFF PARFOIS (Pos. {pos_recomendada})')

            # Anotações Geométricas Alinhadas Automaticamente
            ax1.annotate(f'Eficiência Máxima: Pos {pos_corte}\nΔ = {ponto_otimo["eficiencia_marginal"]:.2f}%', 
                         xy=(pos_corte, ponto_otimo['cum_clicks_pct']),
                         xytext=(pos_corte + (limite_x * 0.04), ponto_otimo['cum_clicks_pct'] - 22),
                         arrowprops=dict(facecolor='#d97706', edgecolor='#d97706', shrink=0.05, width=1.5, headwidth=5, headlength=5),
                         fontweight='bold', fontsize=9, bbox=dict(boxstyle="round,pad=0.3", fc="#fef3c7", alpha=0.95, ec="#d97706", lw=1.5))

            ax1.annotate(f'Marco 75% Cliques: Pos {pos_75}',
                         xy=(pos_75, df_filtrado.loc[(df_filtrado['Item list position'] - pos_75).abs().idxmin(), 'cum_clicks_pct']),
                         xytext=(pos_75 - (limite_x * 0.16), df_filtrado.loc[(df_filtrado['Item list position'] - pos_75).abs().idxmin(), 'cum_clicks_pct'] + 12),
                         arrowprops=dict(facecolor='#6b21a8', edgecolor='#6b21a8', shrink=0.05, width=1.5, headwidth=5, headlength=5),
                         fontweight='bold', fontsize=9, bbox=dict(boxstyle="round,pad=0.3", fc="#f3e8ff", alpha=0.95, ec="#6b21a8", lw=1.5))

            ax1.annotate(f'RECOMENDADO: Posição {pos_recomendada}\nCaptura: {cliques_rec:.1f}% dos Cliques',
                         xy=(pos_recomendada, cliques_rec),
                         xytext=(pos_recomendada - (limite_x * 0.22), 103), 
                         arrowprops=dict(facecolor='#dc2626', edgecolor='#dc2626', shrink=0.05, width=2.5, headwidth=7, headlength=7),
                         fontweight='bold', fontsize=10, color='white',
                         bbox=dict(boxstyle="round,pad=0.4", fc="#b91c1c", alpha=1, ec="#7f1d1d", lw=2))

            ax1.legend(loc='lower right', frameon=True, facecolor='white', edgecolor='#e5e7eb', fontsize=9)
            plt.tight_layout()
            
            st.pyplot(fig)

    except Exception as e:
        st.error(f"Erro crítico ao processar a estrutura de dados: {e}")
else:
    st.info("Aguardando upload do ficheiro CSV mestre na barra lateral para iniciar a análise.")
