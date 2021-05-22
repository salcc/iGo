import math
import statistics
import collections
import pickle
import re
import os
import urllib
import csv
import osmnx
import staticmap
import networkx
import shapely.geometry

Coordinates = collections.namedtuple("Coordinates", "latitude longitude")
Highway = collections.namedtuple("Highway", "description coordinates_list")
Congestion = collections.namedtuple("Congestion", "datetime current_state planned_state")

coordinates_regex = re.compile(r"-?[1-9][0-9]*(\.[0-9]+)?[,\s]\s*-?[1-9][0-9]*(\.[0-9]+)?")
separator_regex = re.compile(r"[,\s]\s*")


def file_exists(filename):
    return os.path.isfile(filename)


def save_data(data, filename):
    with open(filename, "wb") as file:
        pickle.dump(data, file)


def load_data(filename):
    with open(filename, "rb") as file:
        data = pickle.load(file)
        return data


def is_in_place(coordinates, place):
    gdf = osmnx.geocode_to_gdf(place)
    shape = gdf.loc[0, "geometry"]
    point = shapely.geometry.Point(coordinates.longitude, coordinates.latitude)
    return shape.intersects(point)


def name_to_coordinates(name, place):
    if coordinates_regex.fullmatch(name):
        lat, lng = re.split(separator_regex, name)
        lat, lng = float(lat), float(lng)
    else:
        lat, lng = osmnx.geocoder.geocode(name + ", " + place)
    coordinates = Coordinates(lat, lng)
    if not is_in_place(coordinates, place):
        raise Exception
    return coordinates


def coordinates_to_node(graph, coordinates):
    # return osmnx.get_nearest_node(graph, coordinates)
    return osmnx.distance.nearest_nodes(graph, coordinates.longitude, coordinates.latitude)


def node_to_coordinates(graph, node_id):
    return Coordinates(graph.nodes[node_id]["x"], graph.nodes[node_id]["y"])


def path_to_coordinates(graph, path):
    path_coordinates = []
    for node in path:
        path_coordinates.append(node_to_coordinates(graph, node))
    return path_coordinates


def download_graph(place):
    graph = osmnx.graph_from_place(place, network_type="drive", simplify=True)
    graph.remove_edges_from(networkx.selfloop_edges(graph))
    graph = osmnx.bearing.add_edge_bearings(graph)
    graph = osmnx.utils_graph.get_digraph(graph, weight="length")
    return graph


def download_highways(highways_url):
    with urllib.request.urlopen(highways_url) as response:
        lines = [line.decode("utf-8") for line in response.readlines()]
        reader = csv.reader(lines, delimiter=",", quotechar="\"")
        next(reader)  # ignore first line with description
        highways = {}
        for line in reader:
            way_id, description, coordinates_str = line
            way_id = int(way_id)
            all_coordinate_list = list(map(float, coordinates_str.split(",")))
            coordinates_list = []
            for i in range(0, len(all_coordinate_list), 2):
                coordinates_list.append(Coordinates(all_coordinate_list[i + 1], all_coordinate_list[i]))
            highways[way_id] = Highway(description, coordinates_list)
        return highways


def download_congestions(congestions_url):
    with urllib.request.urlopen(congestions_url) as response:
        lines = [line.decode("utf-8") for line in response.readlines()]
        reader = csv.reader(lines, delimiter="#", quotechar="\"")
        congestions = {}
        for line in reader:
            way_id, datetime, current_state, planned_state = map(int, line)
            congestions[way_id] = Congestion(datetime, current_state, planned_state)
        return congestions


def set_default_itime(graph):
    for node1, node2, edge_data in graph.edges(data=True):
        if "maxspeed" in edge_data:
            if type(edge_data["maxspeed"]) is list:
                maxspeeds = [float(maxspeed) for maxspeed in edge_data["maxspeed"]]
                edge_data["maxspeed"] = statistics.mean(maxspeeds)
            else:
                edge_data["maxspeed"] = float(edge_data["maxspeed"])
        else:
            edge_data["maxspeed"] = 30  # https://www.barcelona.cat/mobilitat/ca/barcelona-ciutat-30

        edge_data["maxspeed"] *= 1000 / 3600
        graph[node1][node2]["itime"] = edge_data["length"] / edge_data["maxspeed"]


def build_graph(graph):
    default_graph = graph.subgraph(max(networkx.strongly_connected_components(graph), key=len)).copy()
    set_default_itime(default_graph)
    return default_graph


def get_highway_paths(graph, highways):
    highway_paths = {}
    for way_id, highway in highways.items():
        highway_paths[way_id] = []
        for i in range(len(highway.coordinates_list) - 1):
            coordinates1 = Coordinates(highway.coordinates_list[i].latitude, highway.coordinates_list[i].longitude)
            node1 = coordinates_to_node(graph, coordinates1)
            coordinates2 = Coordinates(highway.coordinates_list[i + 1].latitude, highway.coordinates_list[i + 1].longitude)
            node2 = coordinates_to_node(graph, coordinates2)
            if i > 0:
                highway_paths[way_id].pop()  # we do this to avoid repeated nodes in the path
            highway_paths[way_id].extend(osmnx.distance.shortest_path(graph, node1, node2, weight="length"))
    return highway_paths


def congestion_function(congestion_state):
    return math.exp((congestion_state - 1) ** 2 / 7.5)


def build_igraph_with_congestions(graph, highway_paths, congestions):
    igraph = graph.copy()
    for way_id, highway_path in highway_paths.items():
        congestion_state = congestions[way_id].current_state
        for i in range(len(highway_path) - 1):
            if "congestions" not in igraph[highway_path[i]][highway_path[i + 1]]:
                igraph[highway_path[i]][highway_path[i + 1]]["congestions"] = [congestion_state]
            else:
                if congestion_state == 0:
                    congestion_state = 1
                igraph[highway_path[i]][highway_path[i + 1]]["congestions"].append(congestion_state)
    
    for node1, node2, edge_data in igraph.edges(data=True):
        if "congestions" in igraph[node1][node2]:
            edge_congestions = igraph[node1][node2]["congestions"]
            if 6 in edge_congestions:
                igraph[node1][node2]["itime"] = float("inf")
            else:
                igraph[node1][node2]["itime"] *= congestion_function(statistics.mean(edge_congestions))
            
    return igraph


def bearing_itime(igraph, predecessor, node, successor):
    # return 0
    
    bearing = igraph[node][successor]["bearing"] - igraph[predecessor][node]["bearing"]
    if bearing < -180:
        bearing += 360
    elif bearing > 180:
        bearing -= 360
    
    side_factor = 1
    if bearing < -15:
        side_factor = 1.5
    
    if bearing < 0:
        bearing = -bearing
    
    if bearing < 50:
        bearing_cost = math.exp(bearing / 45) - 1
    else:
        bearing_cost = math.log((bearing - 45) ** 2)

    # print("b(p,n)=", igraph[predecessor][node]["bearing"], " b(n,s)=",igraph[node][successor]["bearing"], " B=", bearing,
    #       " F=", side_factor, " C=", bearing_cost * side_factor, sep="")
    # print((igraph.nodes[predecessor]["y"], igraph.nodes[predecessor]["x"]),
    #       (igraph.nodes[node]["y"], igraph.nodes[node]["x"]),
    #       (igraph.nodes[successor]["y"], igraph.nodes[successor]["x"]))
    # print()

    return bearing_cost * side_factor


def build_igraph_with_bearings(igraph):
    igraph_with_bearings = networkx.DiGraph()
    igraph_with_bearings.graph["crs"] = igraph.graph["crs"]
    for node, node_data in igraph.nodes(data=True):
        in_nodes, out_nodes = [], []
        for predecessor in igraph.predecessors(node):
            # I_3_2: vèrtex de 3, entrant des de 2 (in)
            id = "I_" + str(node) + "_" + str(predecessor)
            igraph_with_bearings.add_node(id, x=node_data["x"], y=node_data["y"], metanode=node)
            in_nodes.append((id, predecessor))
        for successor in igraph.successors(node):
            # O_0_1, vèrtex de 0, sortint cap a 1  (out)
            id = "O_" + str(node) + "_" + str(successor)
            igraph_with_bearings.add_node(id, x=node_data["x"], y=node_data["y"], metanode=node)
            out_nodes.append((id, successor))
        for in_node, predecessor in in_nodes:
            for out_node, successor in out_nodes:
                igraph_with_bearings.add_edge(in_node, out_node, itime=bearing_itime(igraph, predecessor, node, successor))

        igraph_with_bearings.add_node("S_" + str(node), x=node_data["x"], y=node_data["y"], metanode=node)
        for in_node, predecessor in in_nodes:
            igraph_with_bearings.add_edge("S_" + str(node), in_node, itime=0)
        igraph_with_bearings.add_node("D_" + str(node), x=node_data["x"], y=node_data["y"], metanode=node)
        for out_node, successor in out_nodes:
            igraph_with_bearings.add_edge(out_node, "D_" + str(node), itime=0)

    # real edges
    for node1, node2, edge_data in igraph.edges(data=True):
        igraph_with_bearings.add_edge("O_" + str(node1) + "_" + str(node2), "I_" + str(node2) + "_" + str(node1),
                                      itime=edge_data["itime"], length=edge_data["length"])

    return igraph_with_bearings


def build_igraph(graph, highway_paths, congestions):
    igraph = build_igraph_with_congestions(graph, highway_paths, congestions)
    igraph = build_igraph_with_bearings(igraph)
    return igraph


def get_ipath(igraph, source, destination):
    source = "S_" + str(igraph.nodes[coordinates_to_node(igraph, source)]["metanode"])
    destination = "D_" + str(igraph.nodes[coordinates_to_node(igraph, destination)]["metanode"])
    ipath = osmnx.distance.shortest_path(igraph, [source], [destination], weight="itime")[0]
    ipath_itime = 0  # probablement ho traurem
    for i in range(len(ipath) - 1):
        ipath_itime += igraph[ipath[i]][ipath[i + 1]]["itime"]
    if ipath_itime == float("inf"):
        return None
    return [node_to_coordinates(igraph, id) for id in ipath]


def get_highways_plot(graph, highways, size):
    map = staticmap.StaticMap(size, size)
    for way_id, path in highways.items():
        highway_line = staticmap.Line(path_to_coordinates(graph, path), "red", 2)
        map.add_line(highway_line)
    return map


def get_congestions_plot(graph, highways, congestions, size):
    map = staticmap.StaticMap(size, size)
    for way_id, path in highways.items():
        congestion_state = congestions[way_id].current_state
        congestion_colors = ["#a9a9a9", "#228b22", "#7cfc00", "#ffa500", "#ff4500", "#bb0202", "#510101"]
        congestion_line = staticmap.Line(path_to_coordinates(graph, path), congestion_colors[congestion_state], 2)
        map.add_line(congestion_line)
    return map


def icolor(ispeed, min_ispeed, max_ispeed):
    if ispeed == 0:
        return "black"
    ispeed_range = max_ispeed - min_ispeed
    if ispeed_range == 0:
        value = 0.5
    else:
        value = (ispeed - min_ispeed) / ispeed_range
    hue = value * 160
    return "hsl({},100%,50%)".format(round(hue, 2))


def get_igraph_plot(igraph, size):
    min_ispeed, max_ispeed = float("inf"), 0
    for node1, node2, edge_data in igraph.edges(data=True):
        if "length" in edge_data:
            ispeed = edge_data["length"] / edge_data["itime"]
            if ispeed != 0:
                if ispeed < min_ispeed:
                    min_ispeed = ispeed
                if ispeed > max_ispeed:
                    max_ispeed = ispeed

    map = staticmap.StaticMap(size, size)
    for node1, node2, edge_data in igraph.edges(data=True):
        if "length" in edge_data:
            ispeed = edge_data["length"] / edge_data["itime"]
            iline = staticmap.Line([node_to_coordinates(igraph, node1), node_to_coordinates(igraph, node2)],
                                   icolor(ispeed, min_ispeed, max_ispeed), 2)
            map.add_line(iline)

    return map


def get_path_plot(ipath, size):
    map = staticmap.StaticMap(size, size)
    source_icon = staticmap.IconMarker(ipath[0], "./icons/source.png", 10, 32)
    destination_icon = staticmap.IconMarker(ipath[-1], "./icons/destination.png", 10, 32)
    path_line = staticmap.Line(ipath, "ForestGreen", 3)
    map.add_line(path_line)
    map.add_marker(source_icon)
    map.add_marker(destination_icon)
    return map


def get_location_plot(location, size):
    map = staticmap.StaticMap(size, size)
    location_icon = staticmap.IconMarker(location, "icons/source.png", 10, 32)
    map.add_marker(location_icon)
    return map


def save_image(map, output_filename):
    map_image = map.render()
    map_image.save(output_filename)


def test():
    PLACE = "Barcelona, Barcelonés, Barcelona, Catalonia"
    GRAPH_FILENAME = "graph.dat"
    HIGHWAYS_FILENAME = "highways.dat"
    SIZE = 1200
    HIGHWAYS_URL = "https://opendata-ajuntament.barcelona.cat/data/dataset/1090983a-1c40-4609-8620-14ad49aae3ab/resource/" \
                   "1d6c814c-70ef-4147-aa16-a49ddb952f72/download/transit_relacio_trams.csv"
    CONGESTIONS_URL = "https://opendata-ajuntament.barcelona.cat/data/dataset/8319c2b1-4c21-4962-9acd-6db4c5ff1148/resource/" \
                      "2d456eb5-4ea6-4f68-9794-2f3f1a58a933/download"

    # load the graph, or download and set times it if it does not exist
    if file_exists(GRAPH_FILENAME):
        graph = load_data(GRAPH_FILENAME)
        print("We found a wild graph!! :D")
    else:
        print("There is no graph :(")
        graph = download_graph(PLACE)
        print("We've downloaded it!")
        graph = build_graph(graph)
        save_data(graph, GRAPH_FILENAME)
        print("And we've built it! :)")

    # load the highways, or download them and translate them to node paths if they do not exist
    if file_exists(HIGHWAYS_FILENAME):
        print("We have the highways!! :D")
        highways = load_data(HIGHWAYS_FILENAME)
    else:
        print("The highways haven't been found :(")
        highways = download_highways(HIGHWAYS_URL)
        print("We've downloaded them!")
        highways = get_highway_paths(graph, highways)
        save_data(highways, HIGHWAYS_FILENAME)
        print("Processing finished!")
    # plot the highways into a PNG image
    save_image(get_highways_plot(graph, highways, SIZE), "highways.png")
    print("Highways have been plotted into a precious map :)")

    # download congestions (we download them every time because they are updated every 5 minutes)
    congestions = download_congestions(CONGESTIONS_URL)
    # plot the congestions into a PNG image
    save_image(get_congestions_plot(graph, highways, congestions, SIZE), "congestions.png")
    print("Congestions downloaded and plotted into a very beautiful image :)")

    # get the "intelligent graph" version of the graph (taking into account the congestions of the highways)
    igraph = build_igraph(graph, highways, congestions)
    print("The igraph have been built!!! The mean IQ of the planet has increased by 3 points ^-^")
    # plot the igraph into a PNG image
    save_image(get_igraph_plot(igraph, SIZE), "igraph.png")
    print("We now have the most intelligent graph ever plotted into a marvelous PNG image UwU")

    # get "intelligent path" between two addresses
    source = name_to_coordinates("Trinitat Nova", PLACE)
    destination = name_to_coordinates("Port Vell", PLACE)
    ipath = get_ipath(igraph, source, destination)
    # plot the path into a PNG image
    save_image(get_path_plot(ipath, SIZE), "ipath.png")
    print("path.")


if __name__ == "__main__":
    test()
