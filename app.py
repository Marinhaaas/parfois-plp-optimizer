import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns

st.set_page_config(
    page_title="Parfois - Otimizador de PLPs Mestre",
    page_icon="🎯",
    layout="wide"
)

st.title("🎯 Parfois - Otimizador de Catálogo (Mestre / Multi-Layout)")
st.markdown("Carrega qualquer relatório do GA4. O motor detecta automaticamente o formato (linhas ou colunas), limpa subcategorias e calcula a linha de corte.")
st.markdown("---")

st.sidebar.header("Configurações de Entrada")
ficheiro_carregado = st.sidebar.file_uploader("Carrega o CSV do GA4 (Layout Vertical ou Horizontal)", type=["csv"])

def parse_ga4_universal(linhas_brutas):
    """
    Motor Inteligente: Detecta se o ficheiro está em formato Matriz Larga (Horizontal)
    ou Lista Longa (Vertical), processa, limpa subcategorias e devolve um dicionário de categorias.
    """
    idx_pos = None
    for idx, linha in enumerate(linhas_brutas):
        if 'Item list position' in linha:
            idx_pos = idx
            break
            
    if idx_pos is None:
        return {}, "Não foi possível localizar a dimensão 'Item list position' no ficheiro. Garante que é um relatório padrão do GA4."
        
    linha_metrica = [m.strip() for m in linhas_brutas[idx_pos].strip().split(',')]
    linha_superior = [c.strip() for c in linhas_brutas[idx_pos-1].strip().split(',')] if idx_pos > 0 else []
    
    # DETECÇÃO DE LAYOUT: Se a linha superior tiver dados e contiver 'Item list name', é uma Matriz Horizontal
    is_wide_layout = len(linha_superior) > 1 and 'Item list name' in linha_superior[0]
    
    cat_dict = {}
    
    if is_wide_layout:
        # --- PROCESSAMENTO DO NOVO LAYOUT MATRIZ HORIZONTAL (WIDE) ---
        # Mapear pares de colunas (Views e Clicks) para cada Categoria
        category_columns = {}
        for i in range(1, len(linha_superior)-1, 2):
            c_name = linha_superior[i]
            if c_name and c_name != 'Totals' and c_name != 'Item list name':
                category_columns[c_name] = {
                    'views_idx': i,
                    'clicks_idx': i+1
                }
                
        # Extrair linhas de dados puros
        data_rows = []
        for linha in linhas_brutas[idx_pos+1:]:
            partes = [p.strip() for p in linha.strip().split(',')]
            if not partes or 'Grand total' in linha or partes[0] == '':
                continue
            data_rows.append(partes)
            
        # Isolar e estruturar cada categoria individualmente
        for c_name, idxs in category_columns.items():
            # Filtro de Segurança Parfois: Apenas PLPs Principais, ignorando subcategorias
            if c_name.startswith("PLP - ") and "/" not in c_name:
                v_idx = idxs['views_idx']
                c_idx = idxs['clicks_idx']
                
                rows_cat = []
                for r in data_rows:
                    if len(r) > max(v_idx, c_idx):
                        rows_cat.append([r[0], r[v_idx], r[c_idx]])
                        
                df_cat = pd.DataFrame(rows_cat, columns=['Item list position', 'Items viewed in list', 'Items clicked in list'])
                cat_dict[c_name] = df_cat
                
    else:
        # --- PROCESSAMENTO DO LAYOUT VERTICAL (ESTILOS ANTIGOS) ---
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
            # Filtro de Segurança Parfois aplicado ao layout antigo vertical
            df_all = df_all[
                df_all["Item list name"].astype(str).str.startswith("PLP - ") & 
                ~df_all["Item list name"].astype(str).str.contains("/")
            ].copy()
            
            for c_name in df_all["Item list name"].unique():
                sub_df = df_all[df_all["Item_list_name"] == c_name][['Item list position', 'Items viewed in list', 'Items clicked in list']].copy()
                cat_dict[c_name] = sub_df
        else:
            cat_dict["Categoria Unificada"] = df_all[['Item list position', 'Items viewed in list', 'Items clicked in list']].copy()
            
    return cat_dict, None

# Execução do Site Interativo
if ficheiro_carregado is not None:
    try:
        # Ler o ficheiro carregado em modo texto puro descodificado
        linhas_ficheiro = [linha.decode("utf-8") for linha in ficheiro_carregado.readlines()]
        
        # Chamar o interpretador universal de layouts
        catalogo_categorias, erro = parse_ga4_universal(linhas_ficheiro)
        
        if erro:
            st.error(erro)
            st.stop()
            
        if not catalogo_categorias:
            st.error("Erro: Nenhuma categoria principal válida (começando por 'PLP - ' e sem barras) foi detectada neste arquivo.")
            st.stop()
            
        # Criar o menu dropdown lateral alimentado pelas categorias detectadas
        lista_opcoes = sorted(list(catalogo_categorias.keys()))
        categoria_selecionada = st.sidebar.selectbox("Escolha a Categoria para Análise", lista_opcoes)
        
        # Extrair a tabela da categoria escolhida
        df_filtrado = catalogo_categorias[categoria_selecionada].copy()
        
        # 3. Conversões Numéricas e Esterilização Final dos dados da categoria
        df_filtrado['Item list position'] = pd.to_numeric(df_filtrado['Item list position'], errors='coerce')
        df_filtrado['Items viewed in list'] = pd.to_numeric(df_filtrado['Items viewed in list'], errors='coerce')
        df_filtrado['Items clicked in list'] = pd.to_numeric(df_filtrado['Items clicked in list'], errors='coerce')
        df_filtrado = df_filtrado.dropna().copy()
        
        # Filtrar o ruído da Posição -1 e reordenar o catálogo do topo para o fundo
        df_filtrado = df_filtrado[df_filtrado['Item list position'] != -1]
        df_filtrado = df_filtrado.sort_values(by='Item list position').reset_index(drop=True)

        # 4. Cálculos das Percentagens Cumulativas
        total_views = df_filtrado['Items viewed in list'].sum()
        total_clicks = df_filtrado['Items clicked in list'].sum()

        if total_views == 0 or total_clicks == 0:
            st.warning(f"A categoria '{categoria_selecionada}' contém dados zerados de visualizações ou cliques nesta amostragem.")
            st.stop()

        df_filtrado['cum_views_pct'] = (df_filtrado['Items viewed in list'].cumsum() / total_views) * 100
        df_filtrado['cum_clicks_pct'] = (df_filtrado['Items clicked in list'].cumsum() / total_clicks) * 100
        df_filtrado['eficiencia_marginal'] = df_filtrado['cum_clicks_pct'] - df_filtrado['cum_views_pct']

        # 5. Localização dos Marcos Decisórios e Cálculo da Média Parfois (Grelha Par)
        idx_max = df_filtrado['eficiencia_marginal'].idxmax()
        ponto_otimo = df_filtrado.loc[idx_max]
        pos_corte = int(ponto_otimo['Item list position'])

        idx_75 = (df_filtrado['cum_clicks_pct'] >= 75).idxmax()
        ponto_75 = df_filtrado.loc[idx_75]
        pos_75 = int(ponto_75['Item list position'])

        pos_media_bruta = (pos_corte + pos_75) / 2
        pos_recomendada = int(round(pos_media_bruta / 2) * 2)
        
        linha_prox = (df_filtrado['Item list position'] - pos_recomendada).abs().idxmin()
        cliques_rec = df_filtrado.loc[linha_prox, 'cum_clicks_pct']

        # --- RENDERIZAR DASHBOARD NA INTERFACE WEB ---
        st.subheader(f"📊 Categoria Principal Selecionada: {categoria_selecionada}")
        
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric(label="Eficiência Matemática Máxima", value=f"Posição {pos_corte}")
            st.caption("Pico de engajamento bruto antes da fadiga de scroll.")
        with c2:
            st.metric(label="Meta 75% dos Cliques Úteis", value=f"Posição {pos_75}")
            st.caption("Fronteira onde o tráfego se torna irrelevante.")
        with c3:
            st.markdown(f"""
            <div style="background-color:#b91c1c;padding:12px;border-radius:8px;text-align:center;">
                <p style="margin:0;font-size:12px;font-weight:bold;color:white;text-transform:uppercase;">Cutoff Mobile Recomendado</p>
                <h2 style="margin:0;color:white;font-size:28px;font-weight:bold;">Posição {pos_recomendada}</h2>
            </div>
            """, unsafe_allow_html=True)
            st.caption(f"Garante a captura manual de **{cliques_rec:.1f}%** das intenções de clique.")

        st.info(f"**Diretriz Operacional:** Fixar produtos manualmente via *pins* até à **Posição {pos_recomendada}**. A partir daí, o Salesforce (SFCC) assume a automação inteligente do restante catálogo (gerindo de forma dinâmica os restantes **{(100-cliques_rec):.1f}%** de cliques).")

        # --- GERAR GRÁFICO REFORÇADO VISUALMENTE ---
        sns.set_theme(style="whitegrid")
        fig, ax1 = plt.subplots(figsize=(12, 5.2))

        limite_x = max(pos_corte, pos_75, pos_recomendada)
        limite_x = max(limite_x + 30, 120) # Margem de segurança para catálogos muito curtos
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
        
        # Renderizar na Interface Web
        st.pyplot(fig)

    except Exception as e:
        st.error(f"Erro crítico ao processar a estrutura de dados: {e}")
else:
    st.info("Aguardando upload do ficheiro CSV mestre na barra lateral para iniciar a análise.")
