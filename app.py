import streamlit as st
import heapq
import math
import logic
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

def get_connecting_line_name(station1, station2):
    if station1 == station2: return "移動なし"
    for line_name, stations in data.TOKYO_LINES.items():
        if station1 in stations and station2 in stations:
            idx1 = stations.index(station1)
            idx2 = stations.index(station2)
            if abs(idx1 - idx2) == 1: return line_name
            if line_name in ["JR山手線", "都営大江戸線"]:
                if (idx1 == 0 and idx2 == len(stations)-1) or \
                   (idx1 == len(stations)-1 and idx2 == 0):
                    return line_name
    return "徒歩"

# app.py の format_route_display 関数

def format_route_display(path, graph):
    if not path: return ""
    if len(path) == 1: return f"🏁 {path[0]} (移動なし)"

    segments = []
    
    current_start = path[0]
    current_line = get_connecting_line_name(path[0], path[1])
    current_time = graph[path[0]].get(path[1], 0)
    
    for i in range(1, len(path) - 1):
        u, v = path[i], path[i+1]
        next_line = get_connecting_line_name(u, v)
        weight = graph[u].get(v, 0)
        
        if next_line != current_line:
            segments.append({
                "line": current_line,
                "start": current_start,
                "end": path[i],
                "time": current_time
            })
            current_start = path[i]
            current_line = next_line
            current_time = weight
        else:
            current_time += weight
            
    segments.append({
        "line": current_line,
        "start": current_start,
        "end": path[-1],
        "time": current_time
    })
    
    lines = []
    for i, seg in enumerate(segments):
        # 【修正】 セミコロンを削除し、` ` で時間を囲むだけにする
        time_str = f"`{int(seg['time'])}分`"
        
        if seg['line'] == "徒歩":
            line_str = f"🚶 **(徒歩)** （{seg['start']} → {seg['end']}） {time_str}"
        else:
            line_str = f"🚃 **【{seg['line']}】** （{seg['start']} → {seg['end']}） {time_str}"
        
        lines.append(line_str)
        if i < len(segments) - 1:
            lines.append("↓")
            
    return "  \n".join(lines)

# --- 2. グラフ構築 ---
def build_graph():
    graph = {}
    STOP_PENALTY = 1.0 
    
    # デフォルト設定（データがない路線用）
    DEFAULT_CONF = {"speed_kmh": 40.0, "interval_min": 8}

    for line_name, stations in data.TOKYO_LINES.items():
        # その路線の設定を取得
        conf = data.LINE_CONFIG.get(line_name, DEFAULT_CONF)
        speed = conf["speed_kmh"]

        for i in range(len(stations) - 1):
            st1, st2 = stations[i], stations[i+1]
            if st1 not in graph: graph[st1] = {}
            if st2 not in graph: graph[st2] = {}
            
            travel_time = 3.0
            if st1 in data.STATION_LOCATIONS and st2 in data.STATION_LOCATIONS:
                loc1 = data.STATION_LOCATIONS[st1]
                loc2 = data.STATION_LOCATIONS[st2]
                dist_km = calculate_distance_km(loc1[0], loc1[1], loc2[0], loc2[1])
                
                # 時間 = (距離 * 1.2 / 時速) * 60 + 停車ロス
                calc_time = (dist_km * 1.2 / speed) * 60 + STOP_PENALTY
                travel_time = max(calc_time, 1.0)
            
            graph[st1][st2] = min(graph[st1].get(st2, float('inf')), travel_time)
            graph[st2][st1] = min(graph[st2].get(st1, float('inf')), travel_time)

        # 環状線（山手線・大江戸線）の接続
        if line_name in ["JR山手線", "都営大江戸線"]:
            first, last = stations[0], stations[-1]
            if first not in graph: graph[first] = {}
            if last not in graph: graph[last] = {}
            
            travel_time = 3.0
            if first in data.STATION_LOCATIONS and last in data.STATION_LOCATIONS:
                loc1 = data.STATION_LOCATIONS[first]
                loc2 = data.STATION_LOCATIONS[last]
                dist_km = calculate_distance_km(loc1[0], loc1[1], loc2[0], loc2[1])
                calc_time = (dist_km * 1.2 / speed) * 60 + STOP_PENALTY
                travel_time = max(calc_time, 1.0)

            graph[first][last] = min(graph[first].get(last, float('inf')), travel_time)
            graph[last][first] = min(graph[last].get(first, float('inf')), travel_time)

    # (B) 徒歩ルート（ここは変更なし）
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

# --- 3. ダイクストラ法 ---
def get_shortest_path(graph, start_node, end_node):
    if start_node == end_node: return 0, [start_node]
    
    # 優先度付きキュー: (経過時間, 現在地, 経路リスト, 直前の路線名)
    queue = [(0, start_node, [start_node], None)]
    
    # 訪問済み記録: (ノード, 到着した路線) -> 最短時間
    visited = {}
    
    # デフォルト設定（データがない路線用）
    DEFAULT_CONF = {"speed_kmh": 40.0, "interval_min": 8}

    while queue:
        cost, current_node, path, prev_line = heapq.heappop(queue)
        
        if current_node == end_node: return cost, path
        
        state_key = (current_node, prev_line)
        if state_key in visited and visited[state_key] <= cost:
            continue
        visited[state_key] = cost

        if current_node in graph:
            for neighbor, weight in graph[current_node].items():
                next_line = get_connecting_line_name(current_node, neighbor)
                added_cost = 0
                
                # --- 乗り換えロジック (Level 2) ---
                if prev_line is not None and next_line != prev_line:
                    # 次に乗る路線のデータを取得
                    conf = data.LINE_CONFIG.get(next_line, DEFAULT_CONF)
                    interval = conf["interval_min"]
                    
                    # 待ち時間コスト = 平均待ち時間(間隔/2) + ホーム移動(2分)
                    wait_cost = (interval / 2.0) + 2.0
                    
                    # 1. 電車同士の乗り換え
                    if prev_line != "徒歩" and next_line != "徒歩":
                        added_cost = wait_cost
                    
                    # 2. 徒歩から電車への乗り換え
                    elif prev_line == "徒歩" and next_line != "徒歩":
                        added_cost = wait_cost
                        
                    # 3. 電車から徒歩へ（待ち時間なし）
                    else:
                        added_cost = 0
                # -------------------------------
                
                new_cost = cost + weight + added_cost
                heapq.heappush(queue, (new_cost, neighbor, path + [neighbor], next_line))

    return float('inf'), []

# --- 4. UI ---
def station_selector(label, key_prefix):
    # --- 1. 全駅のリストアップと整形 ---
    # 選択肢リストを作成: [{"display": "蒲田 【JR京浜東北線】", "raw": "蒲田", "line": "JR京浜東北線", "reading": "かまた"}, ...]
    all_options = []
    for line, stations in data.TOKYO_LINES.items():
        for s in stations:
            reading = data.STATION_READINGS.get(s, "")
            all_options.append({
                "display": f"{s} 【{line}】", # UI表示用
                "raw": s,                     # ロジック用（駅名のみ）
                "line": line,                 # フィルタ用
                "reading": reading            # 検索用
            })

    # --- 2. 検索・絞り込みUI ---
    # コンテナを使って視覚的にグループ化
    with st.container():
        col1, col2 = st.columns([1, 1])
        
        with col1:
            # A. ひらがな検索（全路線から検索）
            search_query = st.text_input(
                f"{label}: 駅名検索", 
                key=f"{key_prefix}_search",
                placeholder="ひらがな入力 (例: か)",
                help="入力すると自動で候補が絞り込まれます"
            )
        
        with col2:
            # B. 路線フィルター（任意）
            line_options = ["すべての路線"] + list(data.TOKYO_LINES.keys())
            filter_line = st.selectbox(
                f"{label}: 路線絞り込み", 
                line_options, 
                key=f"{key_prefix}_filter"
            )

    # --- 3. フィルタリング処理 ---
    filtered_list = []
    for opt in all_options:
        # 路線フィルターのチェック
        if filter_line != "すべての路線" and opt["line"] != filter_line:
            continue
        
        # テキスト検索のチェック
        if search_query:
            # 駅名(raw) または 読み仮名(reading) に検索ワードが含まれるか
            if (search_query not in opt["raw"]) and (search_query not in opt["reading"]):
                continue
        
        filtered_list.append(opt["display"])

    # 検索結果が0件の場合のハンドリング
    if not filtered_list:
        filtered_list = ["(候補なし)"]

    # --- 4. 最終選択プルダウン ---
    selected_display = st.selectbox(
        f"{label}: 駅を選択", 
        filtered_list, 
        key=f"{key_prefix}_final"
    )

    # --- 5. 値の取り出し ---
    # "(候補なし)" が選ばれている場合は None を返すなどの処理が必要ですが、
    # ここでは便宜上、選択肢の文字列操作で駅名を取り出します
    if selected_display == "(候補なし)":
        return None # または適当なデフォルト値
    
    # "蒲田 【JR京浜東北線】" -> " 【" で分割して前の部分 "蒲田" を取得
    selected_station = selected_display.split(" 【")[0]
    
    return selected_station

st.title("🚉 Hub Finder")
st.markdown("全員の集合に最適な駅を計算します。")

station_graph = build_graph()
all_candidate_stations = sorted(list(station_graph.keys()))

st.sidebar.header("参加者設定")
num_members = st.sidebar.number_input("参加人数", 2, 5, 2)

members_data = []
for i in range(num_members):
    st.subheader(f"👤 メンバー {i+1}")
    c_st = station_selector("現在地", f"m{i}_curr")
    n_st = station_selector("次の予定", f"m{i}_next")
    members_data.append({"name": f"メンバー{i+1}", "current": c_st, "next": n_st})
    st.markdown("---")

# --- ボタンエリア（横並び） ---
col1, col2 = st.columns(2)
# use_container_width=True でボタンをカラムいっぱいに広げて押しやすくする
pressed_efficiency = col1.button("🚀 効率重視で検索\n(合計時間 最小)", use_container_width=True)
pressed_fairness = col2.button("⚖️ 公平重視で検索\n(最大時間 最小)", use_container_width=True)

# app.py のボタン押下後の処理ブロックを修正

# どちらかのボタンが押されたら計算を実行
if pressed_efficiency or pressed_fairness:
    results = []
    progress_bar = st.progress(0)
    total_candidates = len(logic.ALL_ROUTES) * 10 # 候補数（概算）
    
    # 全駅を候補としてスキャンするのは重いので、
    # 簡易的に「山手線・中央線・地下鉄主要駅」など候補を絞るか、
    # 以前のように graph.keys() を使う
    candidate_stations = list(data.STATION_LOCATIONS.keys())
    
    for idx, candidate in enumerate(candidate_stations):
        member_results = []
        is_reachable = True
        
        # 各メンバーについて計算
        for m in members_data:
            # logic.py の RAPTOR関数を呼び出す
            # 戻り値は [{transfers:0, time:30, details:...}, {transfers:1, time:25...}] のリスト
            routes = logic.find_routes_raptor(m["current"], candidate)
            
            if not routes:
                is_reachable = False
                break
            
            # 複数のルートから、モードに合わせて最適な1つを選ぶ
            # 効率重視なら「時間最小」、公平重視なら...（今回はシンプルに時間最小を採用）
            best_route = min(routes, key=lambda x: x["total_time"])
            member_results.append({
                "name": m["name"],
                "route": best_route
            })

        if is_reachable:
            # 全員の時間を集計
            times = [r["route"]["total_time"] for r in member_results]
            sum_time = sum(times)
            max_time = max(times)
            
            # 詳細テキストの作成
            details_text = []
            for mr in member_results:
                r = mr["route"]
                lines_str = []
                
                # 待ち時間を含めた詳細表示
                for seg in r["path_details"]:
                    wait_str = f"(待`{int(seg['wait'])}分`)" if seg['wait'] > 0 else ""
                    lines_str.append(f"{wait_str} 🚃 **【{seg['line']}】** （{seg['start']} → {seg['end']}） `{int(seg['time'])}分`")
                    lines_str.append("↓")
                
                # 最後の↓を削除
                if lines_str: lines_str.pop()
                
                details_text.append(
                    f"##### 👤 {mr['name']} `{int(r['total_time'])}分` (乗換{r['transfers']}回)\n\n" + 
                    "  \n".join(lines_str)
                )

            results.append({
                "station": candidate,
                "total_time": sum_time,
                "max_time": max_time,
                "details": details_text
            })
            
        if idx % 10 == 0:
            progress_bar.progress(min((idx + 1) / len(candidate_stations), 1.0))
            
    progress_bar.progress(1.0)

    # --- 結果表示（以前と同じ）---
    if results:
        if pressed_efficiency:
            results.sort(key=lambda x: x["total_time"])
            mode_name = "効率重視"
        else:
            results.sort(key=lambda x: (x["max_time"], x["total_time"]))
            mode_name = "公平重視"

        best = results[0]
        
        st.success(f"👑 最適な集合場所: **{best['station']}** ({mode_name})")
        
        col1, col2 = st.columns(2)
        col1.metric("全員の移動時間合計", f"{best['total_time']:.1f} 分")
        col2.metric("最大移動時間", f"{best['max_time']:.1f} 分")
        
        with st.expander("詳細経路を見る", expanded=True):
            st.markdown(f"### 📍 集合場所: {best['station']}")
            st.markdown("---")
            for d in best["details"]:
                st.markdown(d)
                st.markdown("---")
    else:
        st.error("経路が見つかりませんでした。")