import data
import math

# --- 1. データ構造の最適化 (Report 3.1) ---
class Route:
    def __init__(self, line_name, stations):
        self.line_name = line_name
        self.stations = stations
        # 設定の取得（なければデフォルト）
        conf = data.LINE_CONFIG.get(line_name, {"speed_kmh": 40.0, "interval_min": 8})
        self.speed_kmh = conf["speed_kmh"]
        self.interval = conf["interval_min"]

def calculate_distance_km(lat1, lon1, lat2, lon2):
    dy = (lat1 - lat2) * 111.0
    dx = (lon1 - lon2) * 91.0
    return math.sqrt(dx**2 + dy**2)

def calculate_travel_time(route, start_idx, end_idx):
    """2駅間の移動時間を座標から計算"""
    total_time = 0.0
    stations = route.stations
    
    # 駅間を1つずつ足し合わせる
    step = 1 if end_idx > start_idx else -1
    for i in range(start_idx, end_idx, step):
        s1 = stations[i]
        s2 = stations[i + step]
        if s1 in data.STATION_LOCATIONS and s2 in data.STATION_LOCATIONS:
            loc1 = data.STATION_LOCATIONS[s1]
            loc2 = data.STATION_LOCATIONS[s2]
            dist = calculate_distance_km(loc1[0], loc1[1], loc2[0], loc2[1])
            # 時間 = (距離*1.2 / 時速)*60 + 停車ロス(1分)
            t = (dist * 1.2 / route.speed_kmh) * 60 + 1.0
            total_time += max(t, 1.0)
    return total_time

# データを「路線オブジェクト」のリストに変換
ALL_ROUTES = []
for line, stations in data.TOKYO_LINES.items():
    ALL_ROUTES.append(Route(line, stations))

# 駅名 -> 所属する路線のインデックスリスト（逆引き辞書）
STATION_TO_ROUTES = {}
for r_idx, route in enumerate(ALL_ROUTES):
    for s_idx, station in enumerate(route.stations):
        if station not in STATION_TO_ROUTES: STATION_TO_ROUTES[station] = []
        STATION_TO_ROUTES[station].append((r_idx, s_idx))


# --- 2. アルゴリズムの刷新: RAPTOR Lite (Report 2.2) ---
def find_routes_raptor(start_node, end_node, max_transfers=4):
    """
    ラウンドベース探索により、(乗り換え回数, 所要時間) のパレート最適解を探す。
    """
    if start_node == end_node:
        return []

    # best_arrival[k][station] = k回の乗り換えでstationに着く最短時間
    # 初期値は無限大
    best_arrivals = [{s: float('inf') for s in data.STATION_LOCATIONS} for _ in range(max_transfers + 1)]
    best_arrivals[0][start_node] = 0
    
    # 経路復元用: parent[k][station] = (前の駅, 利用した路線, 乗車時間, 待ち時間)
    parents = [{} for _ in range(max_transfers + 1)]

    # 探索対象の駅（最初はスタート駅のみ）
    marked_stations = {start_node}

    # ラウンド（乗り換え回数）ごとのループ
    for k in range(1, max_transfers + 1):
        # 前のラウンドの結果をコピー（少なくとも前回と同じ時間は達成できる）
        for s, t in best_arrivals[k-1].items():
            best_arrivals[k][s] = t

        # 今回スキャンする路線を特定（マークされた駅を通る路線のみ）
        queue_routes = {} # {route_idx: start_station_idx}
        for s in marked_stations:
            if s not in STATION_TO_ROUTES: continue
            for r_idx, s_idx in STATION_TO_ROUTES[s]:
                # その路線をまだスキャン予定がない、またはもっと手前から乗れる場合
                if r_idx not in queue_routes or s_idx < queue_routes[r_idx]:
                    queue_routes[r_idx] = s_idx

        next_marked_stations = set()

        # 路線ごとのスキャン（ここがRAPTORの高速性の肝）
        for r_idx, start_s_idx in queue_routes.items():
            route = ALL_ROUTES[r_idx]
            current_trip_start_time = float('inf') # 乗車した時刻（乗車駅までの時間 + 待ち時間）
            boarding_station = None
            
            # 始点以降の駅を順に走査
            for i in range(start_s_idx, len(route.stations)):
                s_curr = route.stations[i]
                
                # A. 降車判定: 電車に乗っていれば、現在の駅への到着時間を計算して更新
                if current_trip_start_time != float('inf'):
                    travel_t = calculate_travel_time(route, route.stations.index(boarding_station), i)
                    arrival_t = current_trip_start_time + travel_t
                    
                    # 既存の記録より早ければ更新
                    if arrival_t < best_arrivals[k][s_curr]:
                        best_arrivals[k][s_curr] = arrival_t
                        parents[k][s_curr] = {
                            "prev_station": boarding_station,
                            "line": route.line_name,
                            "move_time": travel_t,
                            "wait_time": (current_trip_start_time - best_arrivals[k-1][boarding_station])
                        }
                        next_marked_stations.add(s_curr)

                # B. 乗車判定: 前のラウンドでこの駅に到達済みなら、ここから乗車可能
                prev_t = best_arrivals[k-1][s_curr]
                if prev_t != float('inf'):
                    # 待ち時間コスト = 間隔/2 + 2分（ホーム移動）
                    wait_cost = (route.interval / 2.0) + 2.0
                    # 乗り換え（または始発）コスト込みの出発時間をセット
                    # もし既に乗っている電車の方が早ければ乗り換えない（スルー）
                    if prev_t + wait_cost < current_trip_start_time: # ここは簡易的な比較
                        current_trip_start_time = prev_t + wait_cost
                        boarding_station = s_curr

        # 徒歩乗換の処理（フットパス）はここでやるが、今回は簡易化のため省略
        # 次のラウンドへ
        marked_stations = next_marked_stations
        if not marked_stations: break

    # --- 結果の整形 ---
    # k=1...max_transfers の中で、end_nodeに到達できたものを抽出
    results = []
    min_time_so_far = float('inf')

    # 乗り換え回数が少ない順に見る
    for k in range(1, max_transfers + 1):
        t = best_arrivals[k][end_node]
        if t == float('inf'): continue
        
        # パレート最適性のチェック（乗り換えが増えるなら、時間は減っていないと意味がない）
        if t < min_time_so_far:
            min_time_so_far = t
            # 経路復元
            path_details = reconstruct_path(parents, k, end_node)
            results.append({
                "transfers": k - 1, # k=1は乗車1回=乗換0回
                "total_time": t,
                "path_details": path_details
            })

    return results

def reconstruct_path(parents, k, current_node):
    path = []
    curr = current_node
    depth = k
    
    while depth > 0:
        p_info = parents[depth].get(curr)
        if not p_info: break
        
        prev = p_info["prev_station"]
        path.insert(0, {
            "line": p_info["line"],
            "start": prev,
            "end": curr,
            "time": p_info["move_time"],
            "wait": p_info["wait_time"]
        })
        curr = prev
        depth -= 1
    return path