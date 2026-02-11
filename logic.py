'''
import streamlit as st
import heapq  # 最短経路計算用のライブラリ（標準搭載）
import data   # さきほど作った data.py を読み込む

# --- 1. グラフ（路線網）の構築 ---
def build_graph():
    """
    駅と駅のつながりを「グラフ構造」として構築します。
    graph = {
        "東京": {"有楽町": 3, "神田": 2}, 
        ...
    }
    """
    graph = {}
    
    # 全路線の全駅をループしてつながりを作る
    for line_name, stations in data.TOKYO_LINES.items():
        avg_time = data.LINE_CONFIG[line_name]
        
        # 線上の隣り合う駅をつなぐ
        for i in range(len(stations) - 1):
            st1 = stations[i]
            st2 = stations[i+1]
            
            # st1 -> st2 のつながりを登録
            if st1 not in graph: graph[st1] = {}
            if st2 not in graph: graph[st2] = {}
            
            # 双方向に時間を設定
            graph[st1][st2] = avg_time
            graph[st2][st1] = avg_time

        # 山手線は「神田」と「東京」がつながってループしている（特別処理）
        if line_name == "JR山手線":
            first, last = stations[0], stations[-1] # 東京, 神田
            if first not in graph: graph[first] = {}
            if last not in graph: graph[last] = {}
            graph[first][last] = avg_time
            graph[last][first] = avg_time
            
    return graph

# --- 2. 最短時間計算ロジック（ダイクストラ法） ---
def get_shortest_time(graph, start_node, end_node):
    if start_node == end_node:
        return 0
    
    # 探索の準備
    queue = [(0, start_node)] # (現在のコスト, 駅名)
    visited = {} # 最短時間を記録する辞書

    while queue:
        cost, current_node = heapq.heappop(queue)

        # ゴールに着いたらコスト（時間）を返す
        if current_node == end_node:
            return cost
        
        # 既にこれより早い経路で到達済みならスキップ
        if current_node in visited and visited[current_node] <= cost:
            continue
        visited[current_node] = cost

        # 隣の駅へ移動
        if current_node in graph:
            for neighbor, weight in graph[current_node].items():
                new_cost = cost + weight
                # 乗換ペナルティ（簡易的）：路線が変わるなどの判定は今回は省略していますが
                # 本来はここに「乗換時間+5分」などのロジックを入れます
                heapq.heappush(queue, (new_cost, neighbor))
                
    return float('inf') # 到達不能な場合

# --- 3. UI構築 ---
st.title("🚉 Hub Finder (Network Ver.)")
st.markdown("主要路線の「駅数×平均時間」で計算する本格ロジック版です。")

# グラフを作成
station_graph = build_graph()
# グラフに登録されている全駅名のリスト（重複なしでソート）
all_stations = sorted(list(station_graph.keys()))

st.sidebar.header("メンバー情報入力")
num_members = st.sidebar.number_input("参加人数", 2, 5, 2)

members_data = []
for i in range(num_members):
    st.sidebar.subheader(f"メンバー {i+1}")
    c_st = st.sidebar.selectbox(f"現在地 (M{i+1})", all_stations, index=0, key=f"c_{i}")
    n_st = st.sidebar.selectbox(f"次の予定 (M{i+1})", all_stations, index=1, key=f"n_{i}")
    members_data.append({"name": f"M{i+1}", "current": c_st, "next": n_st})

if st.button("計算開始"):
    results = []
    
    # 進捗バー（計算量が増えるため）
    progress_bar = st.progress(0)
    total_candidates = len(all_stations)

    # 全駅を「集合場所候補」として総当たり計算
    for idx, candidate in enumerate(all_stations):
        total_time = 0
        details = []
        is_reachable = True

        for m in members_data:
            # 現在地 -> 候補地
            t1 = get_shortest_time(station_graph, m["current"], candidate)
            # 候補地 -> 次の予定
            t2 = get_shortest_time(station_graph, candidate, m["next"])
            
            if t1 == float('inf') or t2 == float('inf'):
                is_reachable = False
                break
            
            total_time += (t1 + t2)
            details.append(f"{m['name']}: 行き{t1}分 + 帰り{t2}分")

        if is_reachable:
            results.append({
                "station": candidate,
                "total_time": total_time,
                "details": details
            })
        
        # 進捗更新
        progress_bar.progress((idx + 1) / total_candidates)

    # 結果表示
    if results:
        results.sort(key=lambda x: x["total_time"])
        best = results[0]
        
        st.success(f"👑 最適な集合場所: **{best['station']}**")
        st.metric("全員の移動時間合計", f"{best['total_time']} 分")
        
        with st.expander("詳細内訳"):
            for d in best["details"]:
                st.write(f"- {d}")
                
        st.write("---")
        st.write("#### その他の候補")
        for r in results[1:5]:
            st.write(f"**{r['station']}**: {r['total_time']} 分")
            
    else:
        st.error("経路が見つかりませんでした。データがつながっていない可能性があります。")
'''