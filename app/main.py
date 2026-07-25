import streamlit as st
import pandas as pd
import numpy as np
import pickle
import os
import plotly.graph_objects as go

st.set_page_config(page_title="Football Intelligence", page_icon="⚽", layout="wide")

st.markdown("""
<style>
    .stApp { background-color: #f0f2f5; }
    .club-card {
        background: white; border-radius: 12px;
        padding: 15px 20px; margin: 8px 0;
        border-left: 4px solid #1a73e8;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
    }
    .rank-number { font-size: 1.8em; font-weight: bold; color: #1a73e8; }
    .stButton > button {
        background: linear-gradient(135deg, #1a73e8, #0d47a1);
        color: white !important; font-weight: bold;
        border-radius: 8px; border: none;
    }
    [data-testid="stMetricValue"] { color: #1a73e8 !important; }
    [data-testid="stMetricLabel"] { color: #444 !important; }
    [data-testid="metric-container"] {
        background: white; border-radius: 10px;
        padding: 15px; box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }
</style>
""", unsafe_allow_html=True)

# ============================================
# CHARGEMENT MODÈLES
# ============================================
@st.cache_resource
def load_models():
    data_path = os.path.expanduser('~/Desktop/football-intelligence/data/')
    with open(data_path + 'advanced_model.pkl', 'rb') as f:
        advanced = pickle.load(f)
    return advanced

data = load_models()
players_top5 = data['players_top5']
clubs_top5 = data['clubs_top5']
club_style = data['club_style']
club_needs = data['club_needs']
player_trending = data['player_trending']

league_names = {
    'GB1': '🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League',
    'ES1': '🇪🇸 La Liga',
    'FR1': '🇫🇷 Ligue 1',
    'IT1': '🇮🇹 Serie A',
    'L1': '🇩🇪 Bundesliga'
}
league_colors = {
    'GB1': '#FF0000', 'ES1': '#FFA500',
    'FR1': '#0055A4', 'IT1': '#007AC2', 'L1': '#333333'
}
position_icons = {
    'Attack': '⚡', 'Midfield': '🎯',
    'Defender': '🛡️', 'Goalkeeper': '🧤'
}
trend_icons = {'hausse': '📈', 'baisse': '📉', 'stable': '➡️'}

# ============================================
# FONCTION RECOMMANDATION AVANCÉE
# ============================================
def recommend_clubs_advanced(player_name, top_n=5):
    player_data = players_top5[players_top5['name_player'].str.lower().str.contains(player_name.lower())]
    if player_data.empty:
        return None, None
    player_data = player_data.iloc[0]

    pid = player_data['player_id']
    position = player_data['position']
    player_value = player_data['market_value_in_eur']
    current_club = player_data['current_club_id']

    trending_data = player_trending[player_trending['player_id'] == pid]
    trending = trending_data.iloc[0]['trending'] if len(trending_data) > 0 else 'stable'
    trending_pct = trending_data.iloc[0]['trending_pct'] if len(trending_data) > 0 else 0.0

    club_scores = []
    for _, club in club_style.iterrows():
        club_id = club['current_club_id']
        if club_id == current_club:
            continue

        player_off = player_data['offensive_score']
        club_off = club['club_offensive_style']
        max_off = players_top5['offensive_score'].max()
        style_score = max(0, min(1, 1 - abs(player_off - club_off) / (max_off + 0.001)))

        needs = club_needs.get(club_id, {})
        position_need = needs.get(position, {})
        need_score = 1.0 if position_need.get('needs_player', False) else 0.4

        club_avg = club['avg_market_value']
        if club_avg > 0:
            ratio = player_value / club_avg
            if 0.5 <= ratio <= 3:
                value_score = 1.0
            elif ratio < 0.5:
                value_score = ratio / 0.5
            else:
                value_score = max(0, 1 - (ratio - 3) / 10)
        else:
            value_score = 0

        trend_map = {'hausse': 1.0, 'stable': 0.6, 'baisse': 0.3}
        trend_score = trend_map.get(trending, 0.6)

        final_score = (
            style_score * 0.30 +
            need_score * 0.25 +
            value_score * 0.30 +
            trend_score * 0.15
        )

        club_scores.append({
            'club_id': club_id,
            'name': club['name'],
            'league': club['domestic_competition_id'],
            'final_score': round(final_score, 3),
            'style_score': round(style_score * 100, 1),
            'need_score': round(need_score * 100, 1),
            'value_score': round(value_score * 100, 1),
            'trend_score': round(trend_score * 100, 1),
            'needs_player': position_need.get('needs_player', False),
            'club_avg_value': round(club_avg / 1e6, 1)
        })

    results_df = pd.DataFrame(club_scores).sort_values('final_score', ascending=False)
    results = []
    league_count = {}
    for _, row in results_df.iterrows():
        league = row['league']
        league_count[league] = league_count.get(league, 0) + 1
        if league_count[league] <= 2:
            results.append(row)
        if len(results) == top_n:
            break

    return results, player_data, trending, trending_pct

def get_player_scores(player_row):
    experience = min(player_row.get('total_appearances', 50) / 200, 1)
    return [
        round(min(player_row['offensive_score'] * 5, 1) * 100),
        round(player_row.get('regularity_score', 0) * 100),
        round(player_row.get('discipline_score', 0) * 100),
        round(player_row.get('potential_ratio', 0) * 100),
        round(experience * 100)
    ]

# ============================================
# SIDEBAR
# ============================================
with st.sidebar:
    st.markdown("## ⚽ Football Intelligence")
    st.divider()
    page = st.radio("Navigation", [
        "🔍 Recherche Joueur",
        "🏆 Classement Top 5 Ligues",
        "⚖️ Comparaison Joueurs"
    ])
    st.divider()
    st.markdown("**Base de données**")
    st.markdown(f"👥 {len(players_top5):,} joueurs")
    st.markdown(f"🏟️ {len(clubs_top5)} clubs")
    st.markdown(f"🌍 5 ligues européennes")
    st.divider()
    st.markdown("**Ligues couvertes**")
    for name in league_names.values():
        st.markdown(name)

# ============================================
# PAGE 1 — RECHERCHE JOUEUR
# ============================================
if page == "🔍 Recherche Joueur":
    st.markdown("""
    <div style='text-align:center; padding:20px 0'>
        <h1 style='color:#1a73e8'>⚽ Football Intelligence Platform</h1>
        <p style='color:#666'>Prédiction de transfert basée sur le style de jeu, les performances, les besoins des clubs et la valeur marchande</p>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    col1, col2 = st.columns([4, 1])
    with col1:
        player_input = st.text_input("", placeholder="🔍 Ex: Kylian Mbappé, Erling Haaland, Florian Thauvin...")
    with col2:
        search_btn = st.button("⚡ Analyser", type="primary", use_container_width=True)

    if search_btn and player_input:
        with st.spinner("Analyse en cours..."):
            result = recommend_clubs_advanced(player_input)

        if result[0] is None:
            st.error(f"❌ '{player_input}' non trouvé.")
            st.info("💡 Vérifie l'orthographe ou essaie avec le prénom seulement.")
        else:
            results, player_row, trending, trending_pct = result
            trend_icon = trend_icons.get(trending, '➡️')

            st.divider()
            st.markdown(f"## {position_icons.get(player_row['position'], '👤')} {player_row['name_player']}")

            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("🎯 Position", player_row['position'])
            c2.metric("🎂 Âge", f"{int(player_row['age'])} ans")
            c3.metric("💰 Valeur", f"{player_row['market_value_in_eur']/1e6:.1f}M€")
            c4.metric(f"{trend_icon} Tendance", f"{trending} ({trending_pct:+.1f}%)")
            club_name = str(player_row['name_club']) if pd.notna(player_row['name_club']) else "N/A"
            c5.metric("🏟️ Club", club_name[:18] + "..." if len(club_name) > 18 else club_name)

            st.divider()
            left, right = st.columns([1, 1])

            with left:
                st.markdown("### 🏆 Top 5 Clubs Recommandés")
                for i, row in enumerate(results):
                    score = round(row['final_score'] * 100, 1)
                    league = league_names.get(row['league'], '')
                    medal = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"][i]
                    need_tag = "⚠️ Besoin au poste" if row['needs_player'] else "✅"
                    st.markdown(f"""
                    <div class='club-card'>
                        <span class='rank-number'>{medal}</span>
                        <strong style='color:#1e2a3a'> {row['name']}</strong>
                        <span style='float:right;color:#1a73e8;font-size:1.2em;font-weight:bold'>{score}%</span><br>
                        <span style='color:#666'>{league}</span> &nbsp;|&nbsp;
                        <span style='color:#888'>Moy. club: {row['club_avg_value']}M€</span> &nbsp;|&nbsp;
                        <span style='color:#e67e22'>{need_tag}</span>
                    </div>
                    """, unsafe_allow_html=True)

            with right:
                st.markdown("### 📊 Détail des scores")
                scores = [round(r['final_score'] * 100, 1) for r in results]
                names = [' '.join(r['name'].split()[:2]) for r in results]
                colors = [league_colors.get(r['league'], '#1a73e8') for r in results]
                fig = go.Figure(go.Bar(
                    x=scores, y=names, orientation='h',
                    marker=dict(color=colors),
                    text=[f"{s}%" for s in scores],
                    textposition='outside', textfont=dict(color='black')
                ))
                fig.update_layout(
                    plot_bgcolor='white', paper_bgcolor='white',
                    font=dict(color='#1e2a3a'),
                    xaxis=dict(range=[0, 100], gridcolor='#eee'),
                    yaxis=dict(autorange='reversed'),
                    margin=dict(l=10, r=60, t=10, b=10), height=280
                )
                st.plotly_chart(fig, use_container_width=True)

                # Radar scores ML
                st.markdown("### 🕸️ Profil du joueur")
                values_pct = get_player_scores(player_row)
                categories = ['Offensif', 'Régularité', 'Discipline', 'Potentiel', 'Expérience']
                fig2 = go.Figure(go.Scatterpolar(
                    r=values_pct + [values_pct[0]],
                    theta=categories + [categories[0]],
                    fill='toself', fillcolor='rgba(26,115,232,0.2)',
                    line=dict(color='#1a73e8', width=2)
                ))
                fig2.update_layout(
                    polar=dict(
                        bgcolor='white',
                        radialaxis=dict(visible=True, range=[0, 100], gridcolor='#ddd', color='#666'),
                        angularaxis=dict(gridcolor='#ddd', color='#333')
                    ),
                    paper_bgcolor='white', font=dict(color='#1e2a3a'),
                    margin=dict(l=40, r=40, t=40, b=40), height=280, showlegend=False
                )
                st.plotly_chart(fig2, use_container_width=True)

            st.divider()

            # Explication des critères
            st.markdown("### 🧠 Critères de prédiction utilisés")
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.markdown("#### 🎨 Style de jeu (30%)")
                st.markdown("Compatibilité entre le profil offensif du joueur et le style du club")
            with c2:
                st.markdown("#### 📋 Besoin au poste (25%)")
                st.markdown("Le club manque-t-il de joueurs à ce poste par rapport à la moyenne ?")
            with c3:
                st.markdown("#### 💰 Valeur marchande (30%)")
                st.markdown("La valeur du joueur est-elle cohérente avec le niveau financier du club ?")
            with c4:
                st.markdown("#### 📈 Trending (15%)")
                st.markdown(f"Valeur en **{trending}** ({trending_pct:+.1f}%) sur les 6 derniers mois")

            st.divider()
            st.markdown("### 📋 Statistiques détaillées")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.markdown("#### ⚽ Performance")
                st.metric("Buts / 90 min", f"{player_row.get('goals_per90', 0):.2f}")
                st.metric("Passes déc. / 90", f"{player_row.get('assists_per90', 0):.2f}")
                st.metric("Minutes / match", f"{player_row.get('minutes_per_game', 0):.0f} min")
            with c2:
                st.markdown("#### 📊 Expérience")
                st.metric("Matchs joués", f"{int(player_row.get('total_appearances', 0))}")
                st.metric("Buts totaux", f"{int(player_row.get('total_goals', 0))}")
                st.metric("Passes déc. totales", f"{int(player_row.get('total_assists', 0))}")
            with c3:
                st.markdown("#### 🎯 Profil")
                st.metric("Cartons jaunes", f"{int(player_row.get('total_yellow', 0))}")
                st.metric("Cartons rouges", f"{int(player_row.get('total_red', 0))}")
                st.metric("Pied fort", str(player_row.get('foot', 'N/A')).capitalize())

    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("👥 Joueurs Top 5", f"{len(players_top5):,}")
        c2.metric("🏟️ Clubs", f"{len(clubs_top5)}")
        c3.metric("🌍 Ligues", "5")
        c4.metric("📊 Apparences", "708,901")

# ============================================
# PAGE 2 — CLASSEMENT
# ============================================
elif page == "🏆 Classement Top 5 Ligues":
    st.markdown("""
    <div style='text-align:center; padding:20px 0'>
        <h1 style='color:#1a73e8'>🏆 Classement des Meilleurs Joueurs</h1>
        <p style='color:#666'>Top joueurs des 5 grands championnats européens</p>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        position_filter = st.selectbox("🎯 Poste", ["Tous", "Attack", "Midfield", "Defender", "Goalkeeper"])
    with c2:
        league_filter = st.selectbox("🌍 Ligue", ["Toutes", "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League", "🇪🇸 La Liga", "🇫🇷 Ligue 1", "🇮🇹 Serie A", "🇩🇪 Bundesliga"])
    with c3:
        age_max = st.slider("Âge maximum", 18, 40, 35)
    with c4:
        top_n = st.slider("Nb joueurs", 10, 50, 20)

    league_map = {
        "🏴󠁧󠁢󠁥󠁮󠁧󠁿 Premier League": "GB1", "🇪🇸 La Liga": "ES1",
        "🇫🇷 Ligue 1": "FR1", "🇮🇹 Serie A": "IT1", "🇩🇪 Bundesliga": "L1"
    }

    df_filtered = players_top5.copy()
    if position_filter != "Tous":
        df_filtered = df_filtered[df_filtered['position'] == position_filter]
    if league_filter != "Toutes":
        df_filtered = df_filtered[df_filtered['domestic_competition_id'] == league_map.get(league_filter)]
    df_filtered = df_filtered[df_filtered['age'] <= age_max]

    df_filtered = df_filtered.copy()
    df_filtered['global_score'] = (
        df_filtered['offensive_score'] * 0.35 +
        df_filtered.get('regularity_score', pd.Series([0]*len(df_filtered))).fillna(0) * 0.25 +
        df_filtered.get('discipline_score', pd.Series([0]*len(df_filtered))).fillna(0) * 0.20 +
        df_filtered.get('potential_ratio', pd.Series([0]*len(df_filtered))).fillna(0) * 0.20
    )
    top_players = df_filtered.sort_values('global_score', ascending=False).head(top_n)

    if len(top_players) == 0:
        st.warning("Aucun joueur trouvé avec ces filtres.")
    else:
        st.markdown(f"**{len(top_players)} joueurs trouvés**")
        fig = go.Figure(go.Bar(
            x=top_players['global_score'].round(3),
            y=top_players['name_player'],
            orientation='h',
            marker=dict(color=[league_colors.get(l, '#1a73e8') for l in top_players['domestic_competition_id']]),
            text=top_players['name_player'],
            textposition='inside',
            textfont=dict(color='white', size=11)
        ))
        fig.update_layout(
            plot_bgcolor='white', paper_bgcolor='white',
            font=dict(color='#1e2a3a'),
            xaxis=dict(gridcolor='#eee', title='Score Global'),
            yaxis=dict(showticklabels=False, autorange='reversed'),
            margin=dict(l=10, r=10, t=10, b=10),
            height=max(400, top_n * 25)
        )
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("**Légende :**")
        cols = st.columns(5)
        for i, (code, name) in enumerate(league_names.items()):
            cols[i].markdown(f"<span style='color:{league_colors[code]};font-weight:bold'>■</span> {name}", unsafe_allow_html=True)

        st.divider()
        cols_display = ['name_player', 'position', 'age', 'name_club', 'domestic_competition_id', 'market_value_in_eur', 'goals_per90', 'assists_per90']
        available_cols = [c for c in cols_display if c in top_players.columns]
        display_df = top_players[available_cols].copy()
        display_df.columns = ['Joueur', 'Poste', 'Âge', 'Club', 'Ligue', 'Valeur', 'Buts/90', 'Passes/90'][:len(available_cols)]
        if 'Valeur' in display_df.columns:
            display_df['Valeur'] = display_df['Valeur'].apply(lambda x: f"{x/1e6:.1f}M€")
        if 'Ligue' in display_df.columns:
            display_df['Ligue'] = display_df['Ligue'].map(league_names)
        display_df = display_df.reset_index(drop=True)
        display_df.index += 1
        st.dataframe(display_df, use_container_width=True, height=420)

# ============================================
# PAGE 3 — COMPARAISON
# ============================================
elif page == "⚖️ Comparaison Joueurs":
    st.markdown("""
    <div style='text-align:center; padding:20px 0'>
        <h1 style='color:#1a73e8'>⚖️ Comparaison de Joueurs</h1>
        <p style='color:#666'>Compare les profils, performances et clubs recommandés pour 2 joueurs</p>
    </div>
    """, unsafe_allow_html=True)
    st.divider()

    col1, col2 = st.columns(2)
    with col1:
        player1_input = st.text_input("👤 Joueur 1", placeholder="Ex: Kylian Mbappé")
    with col2:
        player2_input = st.text_input("👤 Joueur 2", placeholder="Ex: Erling Haaland")

    compare_btn = st.button("⚖️ Comparer", type="primary", use_container_width=True)

    if compare_btn and player1_input and player2_input:
        r1 = recommend_clubs_advanced(player1_input)
        r2 = recommend_clubs_advanced(player2_input)

        if r1[0] is None:
            st.error(f"❌ '{player1_input}' non trouvé.")
        elif r2[0] is None:
            st.error(f"❌ '{player2_input}' non trouvé.")
        else:
            res1, p1, trend1, tpct1 = r1
            res2, p2, trend2, tpct2 = r2

            st.divider()
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"### {position_icons.get(p1['position'], '👤')} {p1['name_player']}")
                st.metric("Position", p1['position'])
                st.metric("Âge", f"{int(p1['age'])} ans")
                st.metric("Valeur", f"{p1['market_value_in_eur']/1e6:.1f}M€")
                st.metric(f"{trend_icons.get(trend1)} Tendance", f"{trend1} ({tpct1:+.1f}%)")
            with col2:
                st.markdown(f"### {position_icons.get(p2['position'], '👤')} {p2['name_player']}")
                st.metric("Position", p2['position'])
                st.metric("Âge", f"{int(p2['age'])} ans")
                st.metric("Valeur", f"{p2['market_value_in_eur']/1e6:.1f}M€")
                st.metric(f"{trend_icons.get(trend2)} Tendance", f"{trend2} ({tpct2:+.1f}%)")

            st.divider()
            st.markdown("### 🕸️ Comparaison des profils")
            categories = ['Offensif', 'Régularité', 'Discipline', 'Potentiel', 'Expérience']
            v1 = get_player_scores(p1)
            v2 = get_player_scores(p2)

            fig = go.Figure()
            fig.add_trace(go.Scatterpolar(
                r=v1 + [v1[0]], theta=categories + [categories[0]],
                fill='toself', fillcolor='rgba(26,115,232,0.2)',
                line=dict(color='#1a73e8', width=2), name=p1['name_player']
            ))
            fig.add_trace(go.Scatterpolar(
                r=v2 + [v2[0]], theta=categories + [categories[0]],
                fill='toself', fillcolor='rgba(255,100,0,0.2)',
                line=dict(color='#ff6400', width=2), name=p2['name_player']
            ))
            fig.update_layout(
                polar=dict(
                    bgcolor='white',
                    radialaxis=dict(visible=True, range=[0, 100], gridcolor='#ddd', color='#666'),
                    angularaxis=dict(gridcolor='#ddd', color='#333')
                ),
                paper_bgcolor='white', font=dict(color='#1e2a3a'),
                legend=dict(bgcolor='white'),
                margin=dict(l=60, r=60, t=60, b=60), height=420
            )
            st.plotly_chart(fig, use_container_width=True)

            st.divider()
            st.markdown("### 📊 Stats comparées")
            stats = {
                'Buts / 90 min': 'goals_per90',
                'Passes déc. / 90': 'assists_per90',
                'Minutes / match': 'minutes_per_game',
                'Matchs joués': 'total_appearances',
                'Buts totaux': 'total_goals',
                'Cartons jaunes': 'total_yellow',
            }
            rows = []
            for label, key in stats.items():
                v1_val = float(p1.get(key, 0))
                v2_val = float(p2.get(key, 0))
                winner = "🟦" if v1_val > v2_val else ("🟧" if v2_val > v1_val else "🟰")
                rows.append({
                    p1['name_player'][:15]: round(v1_val, 2),
                    'Stat': label,
                    p2['name_player'][:15]: round(v2_val, 2),
                    '': winner
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            st.divider()
            st.markdown("### 🏆 Clubs recommandés")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**{p1['name_player']}**")
                for i, row in enumerate(res1[:3]):
                    score = round(row['final_score'] * 100, 1)
                    league = league_names.get(row['league'], '')
                    medal = ["🥇", "🥈", "🥉"][i]
                    st.markdown(f"{medal} **{row['name']}** — {league} — {score}%")
            with col2:
                st.markdown(f"**{p2['name_player']}**")
                for i, row in enumerate(res2[:3]):
                    score = round(row['final_score'] * 100, 1)
                    league = league_names.get(row['league'], '')
                    medal = ["🥇", "🥈", "🥉"][i]
                    st.markdown(f"{medal} **{row['name']}** — {league} — {score}%")
    else:
        st.info("👆 Entre les noms de 2 joueurs et clique sur Comparer !")
        st.markdown("### 💡 Exemples")
        for p1, p2 in [("Kylian Mbappé", "Erling Haaland"), ("Toni Kroos", "Luka Modric"), ("Virgil van Dijk", "Marquinhos")]:
            st.markdown(f"- **{p1}** vs **{p2}**")