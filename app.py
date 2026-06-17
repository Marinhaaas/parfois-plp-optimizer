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

st.title("🎯 Parfois - Centro de Otimização & Evolução de PLPs")
st.markdown("Auditoria de eficiência, cutoffs móveis e evolução relativa de CTR temporal (Exclusivo para PLPs Principais).")
st.markdown("---")

# Componente Lateral de Upload de Ficheiros
st.sidebar.header("⚙️ Configurações de Entrada")
file_1 = st.sidebar.file_uploader("1. Ficheiro Período Atual", type=["csv"], key="file1")
file_2 = st.sidebar.file_uploader("2. Ficheiro Período Anterior (Para Evolução)", type=["csv"], key="file2")

# Checkbox mágica para inverter ficheiros caso o upload tenha sido feito ao contrário
inverter_arquivos = st.sidebar.checkbox("🔄 Inverter Ficheiros (Atual ↔ Anterior)")

# Lógica de Inversão
file_atual = file_2 if inverter_arquivos else file_1
file_antigo = file_1 if inverter_arquivos else file_2

def extrair_datas_ga4(linhas):
    """Lê as primeiras linhas e extrai o período de datas no formato dd/mm/aaaa a dd/mm/aaaa"""
    for linha in linhas[:15]:
        match = re.search(r'(\d{8})-(\d{8})', linha)
        if match:
            d1, d2 = match.groups()
            inicio = f"{d1[6:8]}/{d1[4:6]}/{d1[:4]}"
            fim = f"{d2[6:8]}/{d2[4:6]}/{d2[:4]}"
            return f"{inicio} a {fim}"
    return "Período Não Detetado"

def parse_ga4_universal(linhas_brutas):
    """Motor Híbrido com Regex estrita para isolar as 12 categorias de foco Parfois."""
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
    
    padrao_regex = re.compile(r"^PLP - (Bags|New In|Clothing|Shoes|Jewellery|Wallets|Watches|Accessories|Leather|Stainless Steel|925 Sterling Silver|Travel Bags)$")
    
    if is_wide_layout:
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
        return None, 0, 0, 0, 0, 0, 0, None
        
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

def gerar_overview_dict(catalogo):
    dados_out = {}
    for cat_nome, df_bruto in catalogo.items():
        res = calcular_metricas_categoria(df_bruto)
        if res[0] is not None:
            dados_out[cat_nome] = res
    return dados_out

# Formatações Visuais para Tabelas
def format_ctr_current_and_diff(ctr_at, ctr_an):
    diff = ctr_at - ctr_an
    if diff > 0: return f"{ctr_at:.2f}% (🟢 +{diff:.2f}%)"
    elif diff < 0: return f"{ctr_at:.2f}% (🔴 {diff:.2f}%)"
    return f"{ctr_at:.2f}% (➖ {diff:.2f}%)"

def format_pos_diff(val):
    if val > 0: return f"⬇️ Mais {val} Linhas"
    elif val < 0: return f"⬆️ Menos {abs(val)} Linhas"
    return "➖ Manteve"

# Fluxo de Renderização Principal
if file_atual is not None:
    try:
        # 1. Processar Ficheiro Atual
        linhas_atual = [l.decode("utf-8") for l in file_atual.readlines()]
        data_atual_str = extrair_datas_ga4(linhas_atual)
        cat_atual, err_at = parse_ga4_universal(linhas_atual)
        if err_at: st.error(err_at); st.stop()
        if not cat_atual: st.error("Erro: Nenhuma categoria válida da lista das 12 principais encontrada."); st.stop()
        dict_atual = gerar_overview_dict(cat_atual)
        
        # 2. Processar Ficheiro Antigo (Se fornecido)
        dict_antigo = None
        data_antigo_str = ""
        if file_antigo is not None:
            linhas_antigo = [l.decode("utf-8") for l in file_antigo.readlines()]
            data_antigo_str = extrair_datas_ga4(linhas_antigo)
            cat_antigo, err_an = parse_ga4_universal(linhas_antigo)
            if not err_an and cat_antigo:
                dict_antigo = gerar_overview_dict(cat_antigo)

        # 3. Construir Tabela de Overview Atual
        dados_overview = []
        for cat_nome, res in dict_atual.items():
            _, tv, tc, pc, p75, prec, crec, _ = res
            ctr = (tc / tv * 100) if tv > 0 else 0
            dados_overview.append({
                "Categoria": cat_nome,
                "Visualizações": tv,
                "Cliques": tc,
                "CTR Geral (%)": round(ctr, 2),
                "Eficiência (Zénite)": f"Pos {pc}",
                "Marco 75%": f"Pos {p75}",
                "CUTOFF PARFOIS": prec,
                "Captura (%)": f"{crec:.1f}%"
            })
        df_overview = pd.DataFrame(dados_overview).sort_values(by="Cliques", ascending=False).reset_index(drop=True)

        # --- DEFINIÇÃO DAS ABAS INTERACTIVAS ---
        abas = ["🌍 Overview Atual", "📈 Análise Individual"]
        if dict_antigo:
            abas.append("🔄 Evolução Temporal")
            
        tabs = st.tabs(abas)
        
        # ---- TAB 1: OVERVIEW ATUAL ----
        with tabs[0]:
            st.subheader(f"📋 Matriz Operacional de Catálogo ({data_atual_str})")
            st.dataframe(df_overview, use_container_width=True)

        # ---- TAB 2: ANÁLISE INDIVIDUAL ----
        with tabs[1]:
            lista_opcoes = sorted(list(dict_atual.keys()))
            categoria_selecionada = st.selectbox("Escolha a Categoria Principal para inspecionar:", lista_opcoes)
            
            df_filtrado, tv, tc, pos_corte, pos_75, pos_recomendada, cliques_rec, ponto_otimo = dict_atual[categoria_selecionada]
            
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric(label="Eficiência Máxima", value=f"Posição {pos_corte}")
            with c2:
                st.metric(label="Meta 75% Cliques", value=f"Posição {pos_75}")
            with c3:
                st.markdown(f'<div style="background-color:#b91c1c;padding:12px;border-radius:8px;text-align:center;"><p style="margin:0;font-size:12px;font-weight:bold;color:white;text-transform:uppercase;">Cutoff SFCC Recomendado</p><h2 style="margin:0;color:white;font-size:28px;font-weight:bold;">Posição {pos_recomendada}</h2></div>', unsafe_allow_html=True)
                st.caption(f"Captura de **{cliques_rec:.1f}%** das intenções garantidas.")

            # Gráfico Principal
            sns.set_theme(style="whitegrid")
            fig, ax1 = plt.subplots(figsize=(12, 5.2))
            limite_x = max(pos_corte, pos_75, pos_recomendada) + 30
            df_vis = df_filtrado[df_filtrado['Item list position'] <= limite_x]

            ax1.plot(df_vis['Item list position'], df_vis['cum_clicks_pct'], color='#1e6b27', label='% Cliques Acumulados', linewidth=2.5)
            ax1.plot(df_vis['Item list position'], df_vis['cum_views_pct'], color='#1d4ed8', label='% Visualizações Acumuladas', linewidth=2.5)
            ax1.set_xlabel('Posição no Catálogo (PLP)', fontweight='bold')
            ax1.set_ylabel('Percentagem Acumulada (%)', fontweight='bold')
            ax1.set_ylim(0, 115)
            ax1.set_xlim(-2, limite_x)

            ax1.axvline(x=pos_corte, color='#d97706', linestyle='--', linewidth=3.0, alpha=0.9, label=f'Eficiência Máxima (Pos. {pos_corte})')
            ax1.axvline(x=pos_75, color='#6b21a8', linestyle=':', linewidth=3.0, alpha=0.9, label=f'Meta 75% Cliques (Pos. {pos_75})')
            ax1.axvline(x=pos_recomendada, color='#dc2626', linestyle='-.', linewidth=5.0, label=f'CUTOFF PARFOIS (Pos. {pos_recomendada})')

            ax1.annotate(f'Eficiência: Pos {pos_corte}\nΔ={ponto_otimo["eficiencia_marginal"]:.2f}%', xy=(pos_corte, ponto_otimo['cum_clicks_pct']), xytext=(pos_corte + (limite_x * 0.04), ponto_otimo['cum_clicks_pct'] - 22), arrowprops=dict(facecolor='#d97706', edgecolor='#d97706', shrink=0.05, width=1.5, headwidth=5, headlength=5), fontweight='bold', fontsize=9, bbox=dict(boxstyle="round,pad=0.3", fc="#fef3c7", alpha=0.95, ec="#d97706", lw=1.5))
            ax1.annotate(f'RECOMENDADO: Posição {pos_recomendada}', xy=(pos_recomendada, cliques_rec), xytext=(pos_recomendada - (limite_x * 0.22), 103), arrowprops=dict(facecolor='#dc2626', edgecolor='#dc2626', shrink=0.05, width=2.5, headwidth=7, headlength=7), fontweight='bold', fontsize=10, color='white', bbox=dict(boxstyle="round,pad=0.4", fc="#b91c1c", alpha=1, ec="#7f1d1d", lw=2))
            ax1.legend(loc='lower right', frameon=True, facecolor='white', edgecolor='#e5e7eb', fontsize=9)
            plt.tight_layout()
            st.pyplot(fig)

        # ---- TAB 3: EVOLUÇÃO TEMPORAL (VISUAL & RELATIVA) ----
        if dict_antigo:
            with tabs[2]:
                st.subheader(f"🔄 Painel Visual de Evolução Temporal")
                st.markdown(f"**Comparação de Períodos:** _{data_antigo_str}_ **➡️** _{data_atual_str}_")
                
                lista_comum = sorted(list(set(dict_atual.keys()).intersection(set(dict_antigo.keys()))))
                dados_comp = []
                for cat in lista_comum:
                    _, tv_at, tc_at, _, _, prec_at, _, _ = dict_atual[cat]
                    _, tv_an, tc_an, _, _, prec_an, _, _ = dict_antigo[cat]
                    
                    ctr_at = (tc_at / tv_at * 100) if tv_at > 0 else 0
                    ctr_an = (tc_an / tv_an * 100) if tv_an > 0 else 0
                    
                    dados_comp.append({
                        "Categoria": cat,
                        "CTR Anterior": f"{ctr_an:.2f}%",
                        "CTR Atual (Evolução)": format_ctr_current_and_diff(ctr_at, ctr_an),
                        "Cutoff Anterior": f"Pos {prec_an}",
                        "Cutoff Atual": f"Pos {prec_at}",
                        "Variação Cutoff": format_pos_diff(prec_at - prec_an)
                    })
                
                df_comp_visual = pd.DataFrame(dados_comp)
                st.markdown("#### 🌍 1. Overview Global de Performance")
                st.dataframe(df_comp_visual, use_container_width=True)
                
                st.markdown("---")
                st.markdown("#### 🔍 2. Raio-X Posicional de CTR por Categoria")
                
                cat_comp = st.selectbox("Escolha a Categoria para auditar o comportamento do CTR posição a posição:", lista_comum)
                
                df_at, tv_at, tc_at, pc_at, p75_at, prec_at, crec_at, p_ot_at = dict_atual[cat_comp]
                df_an, tv_an, tc_an, pc_an, p75_an, prec_an, crec_an, p_ot_an = dict_antigo[cat_comp]
                
                ctr_at_cat = (tc_at / tv_at * 100)
                ctr_an_cat = (tc_an / tv_an * 100)
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric(label=f"CTR Médio Global ({cat_comp})", value=f"{ctr_at_cat:.2f}%", delta=f"{ctr_at_cat - ctr_an_cat:.2f}% (Pontos Perc.)")
                with col2:
                    st.info("💡 **Como ler o gráfico abaixo:** Barras Verdes indicam que os produtos nessas posições converteram melhor agora do que no período anterior. Barras Vermelhas indicam perda de interesse visual (necessidade de trocar os produtos manuais).")
                
                # Gráfico de Variação de CTR Posicional
                df_at['ctr_pos'] = (df_at['Items clicked in list'] / df_at['Items viewed in list'] * 100).fillna(0)
                df_an['ctr_pos'] = (df_an['Items clicked in list'] / df_an['Items viewed in list'] * 100).fillna(0)
                
                m_diff = pd.merge(df_at[['Item list position', 'ctr_pos']], df_an[['Item list position', 'ctr_pos']], 
                                  on='Item list position', suffixes=('_atual', '_anterior'))
                m_diff['diff_ctr'] = m_diff['ctr_pos_atual'] - m_diff['ctr_pos_anterior']
                
                limite_diff = max(prec_at, prec_an) + 12
                m_diff_vis = m_diff[m_diff['Item list position'] <= limite_diff].copy()
                
                cores_barras = ['#1e6b27' if v >= 0 else '#dc2626' for v in m_diff_vis['diff_ctr']]
                
                fig_diff, ax_diff = plt.subplots(figsize=(12, 4.5))
                ax_diff.bar(m_diff_vis['Item list position'], m_diff_vis['diff_ctr'], color=cores_barras, edgecolor='none', width=0.8)
                ax_diff.axhline(y=0, color='#9ca3af', linestyle='-', linewidth=1.5)
                ax_diff.axvline(x=prec_at, color='#dc2626', linestyle='-.', linewidth=2, label=f'Cutoff Atual (Pos. {prec_at})')
                
                ax_diff.set_xlabel('Posição na Listagem (Grelha Parfois)', fontsize=11, fontweight='bold')
                ax_diff.set_ylabel('Variação Absoluta de CTR (%)', fontsize=11, fontweight='bold')
                ax_diff.set_title(f'Balanço de Eficiência Posicional ({data_atual_str}) vs Anterior', fontsize=12, fontweight='bold')
                ax_diff.legend(loc='upper right', frameon=True, facecolor='white')
                
                plt.tight_layout()
                st.pyplot(fig_diff)

    except Exception as e:
        st.error(f"Erro ao processar estrutura: {e}")
else:
    st.info("Aguardando upload do ficheiro CSV mestre na barra lateral para iniciar a análise.")
