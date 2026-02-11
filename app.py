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
    LINE_SPEEDS = {
        "JR": 55.0, "JR山手線": 45.0, "JR中央線(快速)": 65.0, 
        "JR埼京線": 60.0, "Subway": 35.0, "都営大江戸線": 30.0
    }
    STOP_PENALTY = 1.0 

    for line_name, stations in data.TOKYO_LINES.items():
        speed = LINE_SPEEDS.get(line_name)
        if not speed: speed = LINE_SPEEDS["JR"] if "JR" in line_name else LINE_SPEEDS["Subway"]

        for i in range(len(stations) - 1):
            st1, st2 = stations[i], stations[i+1]
            if st1 not in graph: graph[st1] = {}
            if st2 not in graph: graph[st2] = {}
            
            travel_time = 3.0
            if st1 in data.STATION_LOCATIONS and st2 in data.STATION_LOCATIONS:
                loc1 = data.STATION_LOCATIONS[st1]
                loc2 = data.STATION_LOCATIONS[st2]
                dist_km = calculate_distance_km(loc1[0], loc1[1], loc2[0], loc2[1])
                calc_time = (dist_km * 1.2 / speed) * 60 + STOP_PENALTY
                travel_time = max(calc_time, 1.0)
            
            graph[st1][st2] = min(graph[st1].get(st2, float('inf')), travel_time)
            graph[st2][st1] = min(graph[st2].get(st1, float('inf')), travel_time)

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
    queue = [(0, start_node, [start_node])]
    visited = {}

    while queue:
        cost, current_node, path = heapq.heappop(queue)
        if current_node == end_node: return cost, path
        if current_node in visited and visited[current_node] <= cost: continue
        visited[current_node] = cost

        if current_node in graph:
            for neighbor, weight in graph[current_node].items():
                new_cost = cost + weight
                heapq.heappush(queue, (new_cost, neighbor, path + [neighbor]))
    return float('inf'), []

# --- 4. UI ---
def get_shortest_path(graph, start_node, end_node):
    # 乗り換え抵抗（分）: ホーム移動や電車待ち時間として加算
    TRANSFER_PENALTY = 5.0

    if start_node == end_node: return 0, [start_node]
    
    # 優先度付きキュー: (経過時間, 現在地, 経路リスト, 直前の路線名)
    # スタート地点では「直前の路線」は None
    queue = [(0, start_node, [start_node], None)]
    
    # 訪問済み記録: (ノード, 到着した路線) -> 最短時間
    # 同じ駅でも「銀座線で来た場合」と「JRで来た場合」で次の展開が違うため区別する
    visited = {}

    while queue:
        cost, current_node, path, prev_line = heapq.heappop(queue)
        
        if current_node == end_node: return cost, path
        
        # 既により早いルートでこの駅・この路線で到着しているならスキップ
        state_key = (current_node, prev_line)
        if state_key in visited and visited[state_key] <= cost:
            continue
        visited[state_key] = cost

        if current_node in graph:
            for neighbor, weight in graph[current_node].items():
                # 次の移動で使う路線を判定
                next_line = get_connecting_line_name(current_node, neighbor)
                
                # 追加コストの計算
                added_cost = 0
                
                # 路線が変わる場合（乗り換え）の判定
                if prev_line is not None and next_line != prev_line:
                    # 1. 電車同士の乗り換え（例: 山手線 -> 中央線）
                    if prev_line != "徒歩" and next_line != "徒歩":
                        added_cost = TRANSFER_PENALTY
                    
                    # 2. 徒歩から電車への乗り換え（例: 徒歩移動 -> 銀座線）
                    #    ※改札入り、ホームへ降り、電車を待つ時間
                    elif prev_line == "徒歩" and next_line != "徒歩":
                        added_cost = TRANSFER_PENALTY
                        
                    # 3. 電車から徒歩へ（例: 山手線 -> 徒歩移動）
                    #    ※降りて歩き出すだけなのでペナルティなし（歩行時間はweightに含まれる）
                    else:
                        added_cost = 0
                
                new_cost = cost + weight + added_cost
                
                # キューに追加
                heapq.heappush(queue, (new_cost, neighbor, path + [neighbor], next_line))

    return float('inf'), []

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
    total_candidates = len(all_candidate_stations)

    for idx, candidate in enumerate(all_candidate_stations):
        individual_times = []
        details = []
        is_reachable = True

        for m in members_data:
            # 経路計算
            t1, path1 = get_shortest_path(station_graph, m["current"], candidate)
            t2, path2 = get_shortest_path(station_graph, candidate, m["next"])
            
            if t1 == float('inf') or t2 == float('inf'):
                is_reachable = False
                break
            
            total_t = t1 + t2
            individual_times.append(total_t)
            
            # 経路文字列の生成
            route_str_1 = format_route_display(path1, station_graph)
            route_str_2 = format_route_display(path2, station_graph)
            
            # 【修正】 セミコロンを削除してスペースのみにする
            member_detail = (
                f"##### 👤 {m['name']} `{int(total_t)}分`\n\n"
                f"**往路** `{int(t1)}分`  \n"
                f"{route_str_1}  \n\n" 
                f"**復路** `{int(t2)}分`  \n"
                f"{route_str_2}"
            )
            details.append(member_detail)

        if is_reachable:
            sum_time = sum(individual_times)
            max_time = max(individual_times)
            results.append({
                "station": candidate,
                "total_time": sum_time,
                "max_time": max_time,
                "details": details
            })
        
        if idx % 10 == 0:
            progress_bar.progress((idx + 1) / total_candidates)
    
    progress_bar.progress(1.0)

    if results:
        # ソートロジック
        if pressed_efficiency:
            results.sort(key=lambda x: x["total_time"])
            mode_name = "効率重視"
            metric_label = "全員の移動時間合計"
            metric_val = results[0]['total_time']
            sub_metric = f"最大移動: {results[0]['max_time']:.1f} 分"
        else:
            results.sort(key=lambda x: (x["max_time"], x["total_time"]))
            mode_name = "公平重視"
            metric_label = "一番遠い人の移動時間"
            metric_val = results[0]['max_time']
            sub_metric = f"合計時間: {results[0]['total_time']:.1f} 分"

        best = results[0]
        
        st.success(f"👑 最適な集合場所: **{best['station']}** ({mode_name})")
        
        col1, col2 = st.columns(2)
        col1.metric(metric_label, f"{metric_val:.1f} 分")
        col2.metric("参考指標", sub_metric)
        
        with st.expander("詳細経路を見る", expanded=True):
            st.markdown(f"### 📍 集合場所: {best['station']}")
            st.markdown("---")
            for d in best["details"]:
                st.markdown(d)
                st.markdown("---")
        
        st.write("#### 🥈 その他の候補")
        for r in results[1:6]:
            if pressed_efficiency:
                st.write(f"**{r['station']}**: 合計 {r['total_time']:.1f} 分 (最大 {r['max_time']:.1f} 分)")
            else:
                st.write(f"**{r['station']}**: 最大 {r['max_time']:.1f} 分 (合計 {r['total_time']:.1f} 分)")
            
    else:
        st.error("経路が見つかりませんでした。")