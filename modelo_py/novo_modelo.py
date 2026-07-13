import networkx as nx
import osmnx as ox
import geopandas as gpd
import scipy.spatial as spatial
import os

ox.settings.log_console = True
ox.settings.use_cache = True

class FloodRouting:
    def __init__(self, north, south, east, west, history_shp_path, Q=10.0):
        self.Q = Q
        print("Obtendo o grafo...")
        
    
        current_dir = os.path.dirname(os.path.abspath(__file__))
        graph_file = os.path.join(current_dir, "grafo_cache_expanded.graphml")
        if os.path.exists(graph_file):
            print("Carregando grafo salvo localmente...")
            self.graph = ox.load_graphml(graph_file)
        else:
            self.graph = ox.graph_from_bbox(bbox=(west, south, east, north), network_type='drive')
            ox.save_graphml(self.graph, graph_file)
            
        self.nodes_proj, self.edges_proj = ox.graph_to_gdfs(self.graph, nodes=True, edges=True)
        self.edges_crs = self.edges_proj.crs
        
        print(f"Carregando histórico de {history_shp_path}...")
        self.history_gdf = gpd.read_file(history_shp_path)
        
        if 'CONDICAO' in self.history_gdf.columns:
            self.history_gdf = self.history_gdf[self.history_gdf['CONDICAO'] == 'INTRANSITAVEL']
            print(f"Total de pontos INTRANSITÁVEIS filtrados no histórico: {len(self.history_gdf)}")
            
        self.history_gdf = self.history_gdf.to_crs(self.edges_crs)
        self.historical_points_proj = [(geom.x, geom.y) for geom in self.history_gdf.geometry if geom is not None]
        
        nx.set_edge_attributes(self.graph, 0, 'h')
        self._precompute_h()

    def _precompute_h(self):
        if not self.historical_points_proj:
            return
            
        hist_tree = spatial.cKDTree(self.historical_points_proj)
        for u, v, key, data in self.graph.edges(keys=True, data=True):
            if 'geometry' in data:
                edge_pt = (data['geometry'].centroid.x, data['geometry'].centroid.y)
            else:
                x = (self.graph.nodes[u]['x'] + self.graph.nodes[v]['x']) / 2
                y = (self.graph.nodes[u]['y'] + self.graph.nodes[v]['y']) / 2
                edge_pt = (x, y)
                
            # count past floods near this edge (0.0018 degrees is approx 200 metros)
            h_count = len(hist_tree.query_ball_point(edge_pt, r=0.0018))
            self.graph[u][v][key]['h'] = h_count

    def find_best_path(self, origin_coord, dest_coord, current_flooded_points, model_type="proposed", chuva=True):
        from geopy import distance as geopy_dist
        orig_node = ox.distance.nearest_nodes(self.graph, origin_coord[1], origin_coord[0])
        dest_node = ox.distance.nearest_nodes(self.graph, dest_coord[1], dest_coord[0])
        
        use_real_time = model_type in ["proposed", "real_time_only"]
        use_history = model_type in ["proposed", "historical_only"]
        
        # Modelo matemático do ERMAC 2026: Histórico só afeta o peso se estiver chovendo
        if model_type == "proposed" and not chuva:
            use_history = False
            
        G_valid = self.graph.copy()
        edges_to_remove = []
        
        for u, v, key, data in G_valid.edges(keys=True, data=True):
            is_flooded = False
            
            if use_real_time and current_flooded_points:
                pts_to_check = []
                if 'geometry' in data:
                    for coord in list(data['geometry'].coords):
                        pts_to_check.append((coord[1], coord[0])) # lat, lon
                else:
                    x1, y1 = G_valid.nodes[u]['x'], G_valid.nodes[u]['y']
                    x2, y2 = G_valid.nodes[v]['x'], G_valid.nodes[v]['y']
                    pts_to_check.extend([(y1, x1), (y2, x2), ((y1+y2)/2, (x1+x2)/2)])
                
                # Checar buffer de 200m inspirado no rainfall_routing.py
                for p in pts_to_check:
                    for q in current_flooded_points:
                        if geopy_dist.great_circle(p, q).meters < 200:
                            is_flooded = True
                            break
                    if is_flooded:
                        break
                        
            # Variável b(e) conforme o modelo matemático: infinito se alagado, 1 caso contrário
            b_e = float('inf') if is_flooded else 1.0
            
            if b_e == float('inf'):
                # Remover a aresta com peso infinito garante que o A* não a utilize
                edges_to_remove.append((u, v, key))
                continue
                
            # Calcular o peso w(e) 
            l_e = data.get('length', 1.0)
            h_e = data.get('h', 0) if use_history else 0
            
            # w(e) = b(e) * (1 + h(e)/Q) * l(e)
            w_e = b_e * (1.0 + (h_e / self.Q)) * l_e
            G_valid[u][v][key]['weight'] = w_e

        G_valid.remove_edges_from(edges_to_remove)
        
        def heuristic(u, v):
            u_node = self.graph.nodes[u]
            v_node = self.graph.nodes[v]
            return ox.distance.great_circle(u_node['y'], u_node['x'], v_node['y'], v_node['x'])

        if model_type == "standard":
            try:
                return nx.astar_path(self.graph, orig_node, dest_node, heuristic=heuristic, weight='length')
            except nx.NetworkXNoPath:
                return None

        try:
            return nx.astar_path(G_valid, orig_node, dest_node, heuristic=heuristic, weight='weight')
        except nx.NetworkXNoPath:
            return None

if __name__ == "__main__":
    import folium
    
    # Exemplo rápido para gerar os mapas isoladamente sem a tabela
    print("Rodando exemplo rápido de demonstração do modelo")
    
    north_limit, south_limit = -23.510, -23.610
    east_limit, west_limit = -46.560, -46.650
    current_dir = os.path.dirname(os.path.abspath(__file__))
    shp_file = os.path.join(current_dir, "Alag-Inun_2015-2025.shp")
    
    model = FloodRouting(north_limit, south_limit, east_limit, west_limit, shp_file, Q=10.0)
    
    # Origem e destino de exemplo 
    origin = (-23.57035611475849, -46.60791785483021)
    destination = (-23.56785094906498, -46.604854772077694)
    
    # =========================================================================
    # ESCOLHA DE PONTOS DE ALAGAMENTO
    # Descomente a opção que deseja utilizar:
    # =========================================================================
    
    # OPÇÃO 1: AUTOMÁTICO (Pega os 4 piores pontos do histórico na rota)
    # -------------------------------------------------------------------------
    # std_route_temp = model.find_best_path(origin, destination, [], model_type="standard", chuva=False)
    # current_floods = []
    # if std_route_temp:
    #     historico_rota = []
    #     for i in range(len(std_route_temp) - 1):
    #         u, v = std_route_temp[i], std_route_temp[i+1]
    #         data = min(model.graph[u][v].values(), key=lambda d: d.get('length', float('inf')))
    #         h_val = data.get('h', 0)
    #         if h_val > 0:
    #             if 'geometry' in data:
    #                 lat, lon = data['geometry'].centroid.y, data['geometry'].centroid.x
    #             else:
    #                 lat = (model.graph.nodes[u]['y'] + model.graph.nodes[v]['y']) / 2
    #                 lon = (model.graph.nodes[u]['x'] + model.graph.nodes[v]['x']) / 2
    #             historico_rota.append(((lat, lon), h_val))
                
    #     historico_rota.sort(key=lambda x: x[1], reverse=True)
    #     current_floods = [item[0] for item in historico_rota[:4]]
    # -------------------------------------------------------------------------

    # OPÇÃO 2: MANUAL (Digite as coordenadas e apague/comente a Opção 1)
    # -------------------------------------------------------------------------
    current_floods = [
        (-23.56821, -46.60765),
        # (-23.56821, -46.60765),
        # (-23.55577, -46.64950), # comentar as linhas para testar 1, 2 ou 3 pontos
    ]
    # -------------------------------------------------------------------------
    
    FLAG_CHUVA = True
    
    # Calculando as 4 rotas
    print("\nCalculando as 4 rotas simultâneas...")
    proposed_route = model.find_best_path(origin, destination, current_floods, model_type="proposed", chuva=FLAG_CHUVA)
    rt_route = model.find_best_path(origin, destination, current_floods, model_type="real_time_only", chuva=FLAG_CHUVA)
    hist_route = model.find_best_path(origin, destination, current_floods, model_type="historical_only", chuva=FLAG_CHUVA)
    std_route = model.find_best_path(origin, destination, current_floods, model_type="standard", chuva=FLAG_CHUVA)
    
    # Função auxiliar para calcular distância da rota
    def calc_dist(rota):
        if not rota: return "Bloqueado"
        dist = 0
        for i in range(len(rota)-1):
            u, v = rota[i], rota[i+1]
            data = min(model.graph[u][v].values(), key=lambda d: d.get('length', float('inf')))
            dist += data.get('length', 0)
        return f"{dist/1000:.2f} km"

    # Desenhando os mapas e Imprimindo Legenda
    rotas = []
    cores = []
    
    print("\n" + "="*60)
    print("LEGENDA E RESULTADOS DAS ROTAS (Distância Percorrida):")
    print("="*60)
    
    if std_route:
        rotas.append(std_route)
        cores.append('gray')
        print(f"■ CINZA    - Modelo Padrão         : {calc_dist(std_route)}")
    if hist_route:
        rotas.append(hist_route)
        cores.append('blue')
        print(f"■ AZUL     - Apenas Histórico      : {calc_dist(hist_route)}")
    if rt_route:
        rotas.append(rt_route)
        cores.append('orange')
        print(f"■ LARANJA  - Apenas Tempo Real     : {calc_dist(rt_route)}")
    if proposed_route:
        rotas.append(proposed_route)
        cores.append('red')
        print(f"■ VERMELHA - Modelo Proposto       : {calc_dist(proposed_route)}")
    print("="*60)
        
    if rotas:
        print("\nGerando os arquivos HTML...")
        centro_lat = (origin[0] + destination[0]) / 2
        centro_lon = (origin[1] + destination[1]) / 2
        
        # Mapa 1: Sem Buffer
        m1 = folium.Map(location=[centro_lat, centro_lon], zoom_start=14, tiles="CartoDB voyager")
        # Mapa 2: Com Buffer
        m2 = folium.Map(location=[centro_lat, centro_lon], zoom_start=14, tiles="CartoDB voyager")
        # Mapa 3: HeatMap Histórico
        m3 = folium.Map(location=[centro_lat, centro_lon], zoom_start=14, tiles="CartoDB voyager")
        
        from folium.plugins import HeatMap
        # Adiciona o mapa de calor com base nos pontos históricos filtrados (lat, lon)
        heat_data = [[p[1], p[0]] for p in model.historical_points_proj]
        HeatMap(heat_data, radius=15, blur=10, min_opacity=0.3, max_val=1.0).add_to(m3)
        
        offsets = [(0.0, 0.0), (0.00003, 0.00003), (-0.00003, -0.00003), (-0.00006, 0.00000)]
        
        for rota, cor, offset in zip(rotas, cores, offsets):
            # Rotas com as cores originais (Padrão, Histórico, RT, ERMAC) para todos os mapas
            coords_rota = [
                (model.graph.nodes[node]['y'] + offset[0], 
                 model.graph.nodes[node]['x'] + offset[1]) 
                for node in rota
            ]
            folium.PolyLine(coords_rota, color=cor, weight=5, opacity=0.9).add_to(m1)
            folium.PolyLine(coords_rota, color=cor, weight=5, opacity=0.9).add_to(m2)
            folium.PolyLine(coords_rota, color=cor, weight=5, opacity=0.9).add_to(m3)
            
        # Marcadores Origem e Destino
        for m in [m1, m2, m3]:
            folium.Marker(location=[origin[0], origin[1]], popup="Origem", icon=folium.Icon(color="red", icon="play")).add_to(m)
            folium.Marker(location=[destination[0], destination[1]], popup="Destino", icon=folium.Icon(color="green", icon="flag")).add_to(m)
        
        # Pontos de Alagamento
        for alag in current_floods:
            # Mapa 1 (Apenas Marcador)
            folium.Marker(location=[alag[0], alag[1]], popup="Ponto Crítico", icon=folium.Icon(color="black", icon="times", prefix="fa")).add_to(m1)
            # Mapa 2 e 3 (Marcador + Raio)
            for m in [m2, m3]:
                folium.Marker(location=[alag[0], alag[1]], popup="Ponto Crítico", icon=folium.Icon(color="black", icon="times", prefix="fa")).add_to(m)
                folium.Circle(location=[alag[0], alag[1]], radius=200, color='red', fill=True, fill_color='red', fill_opacity=0.2).add_to(m)
            
        m1.save(os.path.join(current_dir, "exemplo_novo_modelo_map.html"))
        m2.save(os.path.join(current_dir, "exemplo_novo_modelo_map_buffer.html"))
        m3.save(os.path.join(current_dir, "exemplo_novo_modelo_map_historico.html"))
        print("\nPronto! Mapas de exemplo gerados com sucesso na sua pasta:")
        print("1. exemplo_novo_modelo_map.html")
        print("2. exemplo_novo_modelo_map_buffer.html")
        print("3. exemplo_novo_modelo_map_historico.html")
