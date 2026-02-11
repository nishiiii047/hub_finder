import data
import math
from collections import defaultdict # 【追加】エラー防止用

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
        
        # デフォルト所要時間（座標がない場合の保険）
        t = 3.0 
        
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
    # 【修正1】同一駅の場合は適切な結果を返す
    if start_node == end_node:
        return [{
            "transfers": 0,
            "total_time": 0,
            "path_details": []
        }]

    # 【修正】defaultdictを使って、未知の駅キーが来ても無限大を返すようにする
    # best_arrivals[k][station]
    best_arrivals = [defaultdict(lambda: float('inf')) for _ in range(max_transfers + 1)]
    best_arrivals[0][start_node] = 0
    
    # 経路復元用
    parents = [{} for _ in range(max_transfers + 1)]

    # 探索対象の駅
    marked_stations = {start_node}

    # ラウンド（乗り換え回数）ごとのループ
    for k in range(1, max_transfers + 1):
        # 前のラウンドの結果をコピー
        # defaultdictなので、到達済みの駅だけコピーすればOK（効率的）
        for s, t in best_arrivals[k-1].items():
            best_arrivals[k][s] = t

        # 今回スキャンする路線を特定
        queue_routes = {} # {route_idx: start_station_idx}
        for s in marked_stations:
            if s not in STATION_TO_ROUTES: continue
            for r_idx, s_idx in STATION_TO_ROUTES[s]:
                if r_idx not in queue_routes or s_idx < queue_routes[r_idx]:
                    queue_routes[r_idx] = s_idx

        next_marked_stations = set()

        # 路線ごとのスキャン
        for r_idx, start_s_idx in queue_routes.items():
            route = ALL_ROUTES[r_idx]
            
            # === 【修正2】順方向スキャン ===
            current_trip_start_time = float('inf') 
            boarding_station = None
            boarding_idx = -1
            
            for i in range(start_s_idx, len(route.stations)):
                s_curr = route.stations[i]
                
                # A. 降車判定
                if current_trip_start_time != float('inf'):
                    travel_t = calculate_travel_time(route, boarding_idx, i)
                    arrival_t = current_trip_start_time + travel_t
                    
                    if arrival_t < best_arrivals[k][s_curr]:
                        best_arrivals[k][s_curr] = arrival_t
                        parents[k][s_curr] = {
                            "prev_station": boarding_station,
                            "line": route.line_name,
                            "move_time": travel_t,
                            "wait_time": (current_trip_start_time - best_arrivals[k-1][boarding_station])
                        }
                        next_marked_stations.add(s_curr)

                # B. 乗車判定
                prev_t = best_arrivals[k-1][s_curr]
                if prev_t != float('inf'):
                    wait_cost = (route.interval / 2.0) + 2.0
                    if prev_t + wait_cost < current_trip_start_time:
                        current_trip_start_time = prev_t + wait_cost
                        boarding_station = s_curr
                        boarding_idx = i
            
            # === 【修正2】逆方向スキャン ===
            current_trip_start_time = float('inf')
            boarding_station = None
            boarding_idx = -1
            
            for i in range(start_s_idx, -1, -1):
                s_curr = route.stations[i]
                
                # A. 降車判定
                if current_trip_start_time != float('inf'):
                    travel_t = calculate_travel_time(route, boarding_idx, i)
                    arrival_t = current_trip_start_time + travel_t
                    
                    if arrival_t < best_arrivals[k][s_curr]:
                        best_arrivals[k][s_curr] = arrival_t
                        parents[k][s_curr] = {
                            "prev_station": boarding_station,
                            "line": route.line_name,
                            "move_time": travel_t,
                            "wait_time": (current_trip_start_time - best_arrivals[k-1][boarding_station])
                        }
                        next_marked_stations.add(s_curr)

                # B. 乗車判定
                prev_t = best_arrivals[k-1][s_curr]
                if prev_t != float('inf'):
                    wait_cost = (route.interval / 2.0) + 2.0
                    if prev_t + wait_cost < current_trip_start_time:
                        current_trip_start_time = prev_t + wait_cost
                        boarding_station = s_curr
                        boarding_idx = i

        marked_stations = next_marked_stations
        if not marked_stations: break

    # --- 結果の整形 ---
    results = []
    min_time_so_far = float('inf')

    for k in range(1, max_transfers + 1):
        # end_node が到達不能なら inf が返る（エラーにならない）
        t = best_arrivals[k][end_node]
        if t == float('inf'): continue
        
        if t < min_time_so_far:
            min_time_so_far = t
            path_details = reconstruct_path(parents, k, end_node)
            results.append({
                "transfers": k - 1,
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