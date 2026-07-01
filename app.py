import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

st.set_page_config(page_title="Cricket Analytics Dashboard", page_icon="🏏", layout="wide")


# ---------------------------------------------------------------------------
# DATA LOADING + CLEANUP
# ---------------------------------------------------------------------------
@st.cache_data
def load_data():
    bat = pd.read_csv("Batting_Final.csv")
    bowl = pd.read_csv("Bowling_Final.csv")
    mm = pd.read_csv("Match_Master.csv")

    for col in ["Team", "Batter"]:
        bat[col] = bat[col].astype(str).str.strip()
    for col in ["Team", "Bowler"]:
        bowl[col] = bowl[col].astype(str).str.strip()

    bat = bat[~bat["Batter"].str.contains(r"^-+$", regex=True, na=False)]
    bowl = bowl[~bowl["Bowler"].str.contains(r"^-+$", regex=True, na=False)]
    bat = bat.drop_duplicates().reset_index(drop=True)
    bowl = bowl.drop_duplicates().reset_index(drop=True)

    # Match Master se exact 'Toss' aur 'Result' columns fetch kiye
    mm_small = mm[["Match_ID", "Tournament", "Ground", "Date", "Toss", "Result", "Team 1", "Team 2"]]
    mm_small["Date"] = pd.to_datetime(mm_small["Date"])
    bat = bat.merge(mm_small, on="Match_ID", how="left")
    bowl = bowl.merge(mm_small, on="Match_ID", how="left")

    def opposition(row):
        if row["Team"] == row["Team 1"]:
            return row["Team 2"]
        return row["Team 1"]

    bat["Opposition"] = bat.apply(opposition, axis=1)
    bowl["Opposition"] = bowl.apply(opposition, axis=1)

    return bat, bowl, mm


bat, bowl, mm = load_data()


# ---------------------------------------------------------------------------
# CAREER AGGREGATES
# ---------------------------------------------------------------------------
@st.cache_data
def build_batting_career(bat):
    rows = []
    for player, grp in bat.groupby("Batter"):
        dismissed = grp[~grp["Dismissal_Type"].isin(["Not Out", "Retired Hurt"])]
        not_outs = len(grp) - len(dismissed)
        runs = grp["Runs"].sum()
        balls = grp["Balls"].sum()
        innings = len(grp)
        outs = len(dismissed)
        avg = round(runs / outs, 2) if outs > 0 else runs
        st_rate = round(runs / balls * 100, 2) if balls > 0 else 0

        # Exact 'Batting_Hand' aur 'Bowling_Style' columns use kiye
        b_hand = grp["Batting_Hand"].dropna().iloc[0] if "Batting_Hand" in grp.columns and not grp["Batting_Hand"].dropna().empty else "N/A"
        b_style = grp["Bowling_Style"].dropna().iloc[0] if "Bowling_Style" in grp.columns and not grp["Bowling_Style"].dropna().empty else "N/A"

        rows.append({
            "Player": player,
            "Team": grp["Team"].iloc[-1],
            "Matches": grp["Match_ID"].nunique(),
            "Innings": innings,
            "Runs": runs,
            "Balls": balls,
            "Highest Score": grp["Runs"].max(),
            "Not Outs": not_outs,
            "Average": avg,
            "Strike Rate": st_rate,
            "4s": grp["4s"].sum(),
            "6s": grp["6s"].sum(),
            "Batting_Hand": b_hand,
            "Bowling_Style": b_style
        })
    return pd.DataFrame(rows)


@st.cache_data
def build_bowling_career(bowl):
    rows = []
    for player, grp in bowl.groupby("Bowler"):
        overs = grp["overs"].sum()
        balls = grp["balls"].sum()
        runs = grp["runs"].sum()
        wkts = grp["wickets"].sum()
        econ = round(runs / overs, 2) if overs > 0 else 0
        avg = round(runs / wkts, 2) if wkts > 0 else 0
        st_rate = round(balls / wkts, 2) if wkts > 0 else 0
        dot_pct = round(grp["0s"].sum() / balls * 100, 2) if balls > 0 else 0
        rows.append({
            "Player": player,
            "Team": grp["Team"].iloc[-1],
            "Matches": grp["Match_ID"].nunique(),
            "Overs": round(overs, 1),
            "Runs Conceded": runs,
            "Wickets": wkts,
            "Economy": econ,
            "Bowling Average": avg,
            "Bowling SR": st_rate,
            "Dot %": dot_pct,
        })
    return pd.DataFrame(rows)


bat_career = build_batting_career(bat)
bowl_career = build_bowling_career(bowl)

all_players = sorted(set(bat["Batter"]).union(set(bowl["Bowler"])))
all_teams = sorted(list(set(bat["Team"].dropna().unique()).union(set(bowl["Team"].dropna().unique()))))
all_tournaments = sorted(mm["Tournament"].dropna().unique())


# ---------------------------------------------------------------------------
# SIDEBAR NAVIGATION
# ---------------------------------------------------------------------------
st.sidebar.title("🏏 Cricket Analytics")
page = st.sidebar.radio("Go to", ["Home", "Player Profile", "Compare Players", "Team Analysis"])

search = st.sidebar.text_input("🔍 Search Player")
if search:
    matches = [p for p in all_players if search.lower() in p.lower()]
    if matches:
        st.sidebar.write(matches[:10])


# ---------------------------------------------------------------------------
# PAGE: HOME
# ---------------------------------------------------------------------------
def show_home():
    st.title("🏏 Cricket Analytics Dashboard")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Players", len(all_players))
    c2.metric("Total Matches", mm["Match_ID"].nunique())
    c3.metric("Total Runs", int(bat["Runs"].sum()))
    c4.metric("Total Wickets", int(bowl["wickets"].sum()))

    st.divider()
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Top Run Scorers")
        top_runs = bat_career.sort_values("Runs", ascending=False).head(10)
        fig = px.bar(top_runs, x="Runs", y="Player", orientation="h", color="Runs")
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width='stretch')

    with col2:
        st.subheader("Top Wicket Takers")
        top_wkts = bowl_career.sort_values("Wickets", ascending=False).head(10)
        fig = px.bar(top_wkts, x="Wickets", y="Player", orientation="h", color="Wickets")
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width='stretch')


# ---------------------------------------------------------------------------
# PAGE: PLAYER PROFILE
# ---------------------------------------------------------------------------
def show_player_profile():
    st.title("Player Profile")

    selected_team = st.sidebar.selectbox("Select Team", ["All Teams"] + all_teams)

    if selected_team != "All Teams":
        team_bat_players = set(bat[bat["Team"] == selected_team]["Batter"])
        team_bowl_players = set(bowl[bowl["Team"] == selected_team]["Bowler"])
        team_players = sorted(list(team_bat_players.union(team_bowl_players)))
    else:
        team_players = all_players

    if not team_players:
        st.warning("No players found for the selected team.")
        return

    default_player = search if search in team_players else team_players[0]

    idx = team_players.index(default_player) if default_player in team_players else 0
    player = st.sidebar.selectbox("Select Player", team_players, index=idx)

    bcareer = bat_career[bat_career["Player"] == player]
    wcareer = bowl_career[bowl_career["Player"] == player]

    st.header(player)
    if not bcareer.empty:
        hand = bcareer.iloc[0]["Batting_Hand"]
        style = bcareer.iloc[0]["Bowling_Style"]
        st.markdown(f"**Style:** 🏏 {hand} | 🥎 {style}")

    c1, c2, c3, c4 = st.columns(4)
    if not bcareer.empty:
        row = bcareer.iloc[0]
        c1.metric("Matches (Batting)", row["Matches"])
        c2.metric("Runs", row["Runs"])
        c3.metric("Highest Score", row["Highest Score"])
        c4.metric("Batting Average", row["Average"])
        c5, c6 = st.columns(2)
        c5.metric("Strike Rate", row["Strike Rate"])
        c6.metric("4s / 6s", f"{row['4s']} / {row['6s']}")
    else:
        st.info("No batting record for this player.")

    if not wcareer.empty:
        st.subheader("Bowling Summary")
        row = wcareer.iloc[0]
        b1, b2, b3, b4, b5 = st.columns(5)
        b1.metric("Overs", row["Overs"])
        b2.metric("Wickets", int(row["Wickets"]))
        b3.metric("Economy", row["Economy"])
        b4.metric("Bowling Average", row["Bowling Average"])
        b5.metric("Dot %", row["Dot %"])

    st.divider()

    # --- Match History (Batting) ---
    st.subheader("Match History (Batting)")
    player_bat = bat[bat["Batter"] == player][
        ["Match_ID", "Date", "Team", "Opposition", "Runs", "Balls", "4s", "6s", "SR", "Dismissal_Type", "Toss", "Result"]
    ].sort_values("Date")

    if not player_bat.empty:
        st.dataframe(player_bat, width='stretch', hide_index=True)
    else:
        st.info("No batting match history available.")

    st.divider()

    # --- Match History (Bowling) ---
    st.subheader("Match History (Bowling)")
    player_bowl = bowl[bowl["Bowler"] == player][
        ["Match_ID", "Date","Team", "Opposition", "overs", "maidens", "runs", "wickets", "Economy", "0s", "Toss", "Result"]
    ].sort_values("Date")

    if not player_bowl.empty:
        st.dataframe(player_bowl, width='stretch', hide_index=True)
    else:
        st.info("No bowling match history available.")

    st.divider()

    st.subheader("Performance Charts")
    ch1, ch2 = st.columns(2)

    with ch1:
        if not player_bat.empty:
            fig = px.line(player_bat, x="Match_ID", y="Runs", markers=True, title="Runs per Match")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No batting timeline data available.")

    with ch2:
        if not player_bat.empty:
            fig = px.line(player_bat, x="Match_ID", y="SR", markers=True, title="Strike Rate Trend")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No strike rate timeline data available.")

    ch3, ch4 = st.columns(2)
    with ch3:
        if not player_bowl.empty:
            fig = px.bar(player_bowl, x="Match_ID", y="wickets", title="Wickets per Match")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No bowling charts available.")

    with ch4:
        if not player_bat.empty:
            dismissal_counts = player_bat["Dismissal_Type"].value_counts().reset_index()
            dismissal_counts.columns = ["Dismissal_Type", "Count"]
            fig = px.pie(dismissal_counts, names="Dismissal_Type", values="Count", title="Dismissal Breakdown")
            st.plotly_chart(fig, width='stretch')
        else:
            st.info("No dismissal data available.")

    ch5, ch6 = st.columns(2)
    with ch5:
        if not player_bat.empty:
            vs_opp = player_bat.groupby("Opposition")["Runs"].sum().reset_index().sort_values("Runs", ascending=False)
            fig = px.bar(vs_opp, x="Opposition", y="Runs", title="Runs vs Opposition")
            st.plotly_chart(fig, width='stretch')

    with ch6:
        if not player_bat.empty:
            vs_ground = bat[bat["Batter"] == player].groupby("Ground")["Runs"].sum().reset_index().sort_values(
                "Runs", ascending=False)
            if not vs_ground.empty:
                fig = px.bar(vs_ground, x="Ground", y="Runs", title="Runs vs Ground")
                st.plotly_chart(fig, width='stretch')


# ---------------------------------------------------------------------------
# PAGE: COMPARE PLAYERS
# ---------------------------------------------------------------------------
def show_compare():
    st.title("Player Compare")

    col1, col2 = st.columns(2)
    player_a = col1.selectbox("Player A", all_players, index=0)
    player_b = col2.selectbox("Player B", all_players, index=1 if len(all_players) > 1 else 0)

    a_bat = bat_career[bat_career["Player"] == player_a]
    b_bat = bat_career[bat_career["Player"] == player_b]
    a_bowl = bowl_career[bowl_career["Player"] == player_a]
    b_bowl = bowl_career[bowl_career["Player"] == player_b]

    st.subheader("Batting Comparison")
    metrics = ["Runs", "Average", "Strike Rate", "Highest Score"]
    comp_rows = []
    for m in metrics:
        a_val = a_bat[m].iloc[0] if not a_bat.empty else 0
        b_val = b_bat[m].iloc[0] if not b_bat.empty else 0
        comp_rows.append({"Metric": m, player_a: a_val, player_b: b_val})
    comp_df = pd.DataFrame(comp_rows)
    st.dataframe(comp_df, width='stretch', hide_index=True)

    fig = go.Figure()
    fig.add_trace(go.Bar(name=player_a, x=comp_df["Metric"], y=comp_df[player_a]))
    fig.add_trace(go.Bar(name=player_b, x=comp_df["Metric"], y=comp_df[player_b]))
    fig.update_layout(barmode="group", title="Batting: Head to Head")
    st.plotly_chart(fig, width='stretch')

    st.subheader("Bowling Comparison")
    b_metrics = ["Wickets", "Economy", "Bowling Average", "Dot %"]
    comp_rows2 = []
    for m in b_metrics:
        a_val = a_bowl[m].iloc[0] if not a_bowl.empty else 0
        b_val = b_bowl[m].iloc[0] if not b_bowl.empty else 0
        comp_rows2.append({"Metric": m, player_a: a_val, player_b: b_val})
    comp_df2 = pd.DataFrame(comp_rows2)
    st.dataframe(comp_df2, width='stretch', hide_index=True)

    fig2 = go.Figure()
    fig2.add_trace(go.Bar(name=player_a, x=comp_df2["Metric"], y=comp_df2[player_a]))
    fig2.add_trace(go.Bar(name=player_b, x=comp_df2["Metric"], y=comp_df2[player_b]))
    fig2.update_layout(barmode="group", title="Bowling: Head to Head")
    st.plotly_chart(fig2, width='stretch')


# ---------------------------------------------------------------------------
# PAGE: TEAM ANALYSIS
# ---------------------------------------------------------------------------
def show_team_analysis():
    st.title("Team Analysis")
    team = st.sidebar.selectbox("Select Team", all_teams)

    st.header(team)
    team_bat = bat_career[bat_career["Team"] == team].sort_values("Runs", ascending=False)
    team_bowl = bowl_career[bowl_career["Team"] == team].sort_values("Wickets", ascending=False)

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Batting Contribution")
        fig = px.pie(team_bat, names="Player", values="Runs", title="Runs Share by Player")
        st.plotly_chart(fig, width='stretch')
        st.dataframe(team_bat, width='stretch', hide_index=True)

    with c2:
        st.subheader("Bowling Contribution")
        fig = px.pie(team_bowl, names="Player", values="Wickets", title="Wickets Share by Player")
        st.plotly_chart(fig, width='stretch')
        st.dataframe(team_bowl, width='stretch', hide_index=True)


# ---------------------------------------------------------------------------
# ROUTER
# ---------------------------------------------------------------------------
if page == "Home":
    show_home()
elif page == "Player Profile":
    show_player_profile()
elif page == "Compare Players":
    show_compare()
elif page == "Team Analysis":
    show_team_analysis()
