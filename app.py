import streamlit as st
import heapq
import math
import data

# --- 1. 計算ヘルパー関数 ---
def calculate_distance_km(lat1, lon1, lat2, lon2):
    km_per_lat = 111.0
    km_per_lon = 91.0
    dy = (lat1 - lat2) * km_per_lat
    dx = (lon1 - lon2) * km_per_lon
    return math.sqrt(dx**2 + dy**2)

def calculate_walking_time(dist_km):
    speed_kmh = 4.0
    return (dist_km / speed_kmh) * 60

# --- 2. 経路・路線判定ヘルパー関数（New!） ---
def get_connecting_line_name(station1, station2):
    """
    2つの駅をつなぐ「路線名」を特定して返す。
    見つからない場合は「徒歩」とみなす。
    """
    # 同じ駅の場合
    if station1 == station2:
        return "移動なし"

    for line_name, stations in data.TOKYO_LINES.items():
        if station1 in stations and station2 in stations:
            # リスト内で隣り合っているか確認
            idx1 = stations.index(station1)
            idx2 = stations.index(station2)
            if abs(idx1 - idx2) == 1:
                return line_name
            
            # 環状線のループ部分（始点と終点）の判定
            if line_name in ["JR山手線", "都営大江戸線"]:
                if (idx1 == 0 and idx2 == len(stations)-1) or \
                   (idx1 == len(stations)-1 and idx2 == 0):
                    return line_name
                    
    # 路線図上で隣り合っていないなら、徒歩移動と判定
    return "徒歩"

def format_route_display(path):
    """
    パスを「路線ごとのセグメント」に分割して表示を整形する。
    例: 
    - 電車: 【JR京浜東北線】（蒲田 → 田町）
    - 徒歩（乗換）: (徒歩)
    - 徒歩（始点/終点）: (徒歩)（有楽町 → 日比谷）
    """
    if not path: return ""
    if len(path) == 1: return f"{path[0]}"

    segments = []
    
    # --- 1. パスを「路線ごとの塊」に分解する ---
    current_start = path[0]
    # 最初の区間の路線名を取得
    current_line = get_connecting_line_name(path[0], path[1])
    
    for i in range(1, len(path) - 1):
        # 次の区間の路線名
        next_line = get_connecting_line_name(path[i], path[i+1])
        
        # 路線が変わったら、そこまでを1つのセグメントとして保存
        if next_line != current_line:
            segments.append({
                "line": current_line,
                "start": current_start,
                "end": path[i]
            })
            # 新しいセグメントの開始
            current_start = path[i]
            current_line = next_line
            
    # 最後のセグメントを追加
    segments.append({
        "line": current_line,
        "start": current_start,
        "end": path[-1]
    })
    
    # --- 2. 表示用文字列を作成する ---
    display_parts = []
    
    for i, seg in enumerate(segments):
        line = seg["line"]
        start = seg["start"]
        end = seg["end"]
        
        if line == "徒歩":
            # 徒歩の場合の特別ルール
            # 「電車」と「電車」に挟まれている場合（＝純粋な乗換）は駅名を省略して「(徒歩)」のみ
            is_transfer = (i > 0) and (i < len(segments) - 1)
            
            if is_transfer:
                display_parts.append("(徒歩)")
            else:
                # 最初や最後の移動が徒歩の場合は、どこからどこまで歩くかを表示
                display_parts.append(f"(徒歩)（{start} → {end}）")
        else:
            # 電車の場合: 【路線名】（始点 → 終点）
            display_parts.append(f"【{line}】（{start} → {end}）")
    
    return " → ".join(display_parts)

# --- 3. グラフ構築 ---
# app.py 内の build_graph 関数を修正

def build_graph():
    graph = {}
    
    # 路線ごとの平均速度設定 (km/h)
    # ※ 直線距離ではなく「線路の道のり」を想定して少し遅めに設定するか、
    #    距離に補正係数をかけることで調整します。
    LINE_SPEEDS = {
        "JR": 55.0,        # JRは比較的速い
        "JR山手線": 45.0,  # 頻繁に止まるため少し遅い
        "JR中央線(快速)": 65.0,
        "JR埼京線": 60.0,
        "Subway": 35.0,    # 地下鉄はカーブが多く遅め
        "都営大江戸線": 30.0 # 特に深い・カーブ多い
    }
    
    # デフォルトの停車ロスタイム（分）
    STOP_PENALTY = 1.0 

    # (A) 電車ルート
    for line_name, stations in data.TOKYO_LINES.items():
        # その路線の速度を決定
        speed = LINE_SPEEDS.get(line_name)
        if not speed:
            # JRか地下鉄かでデフォルト値を分ける
            if "JR" in line_name:
                speed = LINE_SPEEDS["JR"]
            else:
                speed = LINE_SPEEDS["Subway"]

        for i in range(len(stations) - 1):
            st1, st2 = stations[i], stations[i+1]
            if st1 not in graph: graph[st1] = {}
            if st2 not in graph: graph[st2] = {}
            
            # --- ここが新しい計算ロジック ---
            travel_time = 3.0 # データがない場合のデフォルト
            
            # 両方の駅の座標データがある場合のみ精密計算
            if st1 in data.STATION_LOCATIONS and st2 in data.STATION_LOCATIONS:
                loc1 = data.STATION_LOCATIONS[st1]
                loc2 = data.STATION_LOCATIONS[st2]
                
                # 直線距離(km)
                dist_km = calculate_distance_km(loc1[0], loc1[1], loc2[0], loc2[1])
                
                # 線路は直線ではないため、距離に補正係数(1.2倍)を掛ける
                rail_dist_km = dist_km * 1.2
                
                # 時間 = (距離 / 速度) * 60 + 停車ロス
                calc_time = (rail_dist_km / speed) * 60 + STOP_PENALTY
                
                # 最低でも1分はかかるとする（0分防止）
                travel_time = max(calc_time, 1.0)
            
            # -----------------------------

            # グラフに重みを設定
            graph[st1][st2] = min(graph[st1].get(st2, float('inf')), travel_time)
            graph[st2][st1] = min(graph[st2].get(st1, float('inf')), travel_time)

        # 環状線（山手線・大江戸線）の始点・終点接続も同様に計算
        if line_name in ["JR山手線", "都営大江戸線"]:
            first, last = stations[0], stations[-1]
            if first not in graph: graph[first] = {}
            if last not in graph: graph[last] = {}
            
            travel_time = 3.0
            if first in data.STATION_LOCATIONS and last in data.STATION_LOCATIONS:
                loc1 = data.STATION_LOCATIONS[first]
                loc2 = data.STATION_LOCATIONS[last]
                dist_km = calculate_distance_km(loc1[0], loc1[1], loc2[0], loc2[1])
                rail_dist_km = dist_km * 1.2
                calc_time = (rail_dist_km / speed) * 60 + STOP_PENALTY
                travel_time = max(calc_time, 1.0)

            graph[first][last] = min(graph[first].get(last, float('inf')), travel_time)
            graph[last][first] = min(graph[last].get(first, float('inf')), travel_time)

    # (B) 徒歩ルート（ここは前回のまま）
    # ... (前回のコードと同じなので省略可能です) ...
    # もし build_graph 全体を書き換えるなら、前回の (B) 部分も忘れずに入れてください
    station_names_with_loc = list(data.STATION_LOCATIONS.keys())
    MAX_WALK_DIST_KM = 0.8

    for i in range(len(station_names_with_loc)):
        for j in range(i + 1, len(station_names_with_loc)):
            s1 = station_names_with_loc[i]
            s2 = station_names_with_loc[j]
            
            if s1 not in graph or s2 not in graph: continue

            loc1 = data.STATION_LOCATIONS[s1]
            loc2 = data.STATION_LOCATIONS[s2]
            dist = calculate_distance_km(loc1[0], loc1[1], loc2[0], loc2[1])
            
            if dist <= MAX_WALK_DIST_KM and dist > 0:
                walk_time = calculate_walking_time(dist)
                current_weight = graph[s1].get(s2, float('inf'))
                if walk_time < current_weight:
                    graph[s1][s2] = walk_time
                    graph[s2][s1] = walk_time

    return graph

# --- 4. ダイクストラ法 ---
def get_shortest_path(graph, start_node, end_node):
    if start_node == end_node: return 0, [start_node] # Path includes start
    
    queue = [(0, start_node, [start_node])] # Path keeps track of visited nodes
    visited = {}

    while queue:
        cost, current_node, path = heapq.heappop(queue)
        
        if current_node == end_node:
            return cost, path
        
        if current_node in visited and visited[current_node] <= cost: continue
        visited[current_node] = cost

        if current_node in graph:
            for neighbor, weight in graph[current_node].items():
                new_cost = cost + weight
                heapq.heappush(queue, (new_cost, neighbor, path + [neighbor]))
                
    return float('inf'), []

# --- 5. UI ---
def station_selector(label, key_prefix):
    col1, col2 = st.columns(2)
    with col1:
        lines = list(data.TOKYO_LINES.keys())
        selected_line = st.selectbox(f"{label}路線", lines, key=f"{key_prefix}_line")
    with col2:
        stations = data.TOKYO_LINES[selected_line]
        selected_station = st.selectbox(f"{label}駅", stations, key=f"{key_prefix}_station")
    return selected_station

st.title("🚉 Hub Finder")
st.markdown("経路表示を最適化しました。乗換や徒歩移動のポイントのみ表示します。")

station_graph = build_graph()
all_candidate_stations = sorted(list(station_graph.keys()))

st.sidebar.header("設定")
num_members = st.sidebar.number_input("参加人数", 2, 5, 2)

members_data = []
for i in range(num_members):
    st.subheader(f"👤 メンバー {i+1}")
    c_st = station_selector("現在地", f"m{i}_curr")
    n_st = station_selector("次の予定", f"m{i}_next")
    members_data.append({"name": f"M{i+1}", "current": c_st, "next": n_st})
    st.markdown("---")

if st.button("🚀 計算開始"):
    results = []
    progress_bar = st.progress(0)
    total_candidates = len(all_candidate_stations)

    for idx, candidate in enumerate(all_candidate_stations):
        total_time = 0
        details = []
        is_reachable = True

        for m in members_data:
            t1, path1 = get_shortest_path(station_graph, m["current"], candidate)
            t2, path2 = get_shortest_path(station_graph, candidate, m["next"])
            
            if t1 == float('inf') or t2 == float('inf'):
                is_reachable = False
                break
            
            total_time += (t1 + t2)
            
            # 【変更点】 経路表示用関数を通す
            route_str_1 = format_route_display(path1)
            # path2は [集合場所, ..., 次の場所] となっているので、そのまま整形
            route_str_2 = format_route_display(path2)
            
            # 集合場所を強調するために少し記法を変えて結合
            # path1の最後とpath2の最初は同じ「集合場所」なので重複しないように表示も可能だが
            # ここではわかりやすく「行き」と「帰り」で分ける
            details.append(f"**{m['name']}** ({int(t1+t2)}分)\n- 往: {route_str_1}\n- 復: {route_str_2}")

        if is_reachable:
            results.append({
                "station": candidate,
                "total_time": total_time,
                "details": details
            })
        
        if idx % 10 == 0:
            progress_bar.progress((idx + 1) / total_candidates)
    
    progress_bar.progress(1.0)

    if results:
        results.sort(key=lambda x: x["total_time"])
        best = results[0]
        
        st.success(f"👑 最適な集合場所: **{best['station']}**")
        st.metric("全員の移動時間合計", f"{best['total_time']:.1f} 分")
        
        with st.expander("詳細経路を見る", expanded=True):
            st.write(f"### 集合場所: {best['station']}")
            for d in best["details"]:
                st.markdown(d) # マークダウンを有効にして太字などを反映
        
        st.write("---")
        st.write("#### 🥈 その他の候補")
        for r in results[1:6]:
            st.write(f"**{r['station']}**: {r['total_time']:.1f} 分")
            
    else:
        st.error("経路が見つかりませんでした。")