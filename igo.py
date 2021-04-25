import collections
import pickle
import osmnx
import os
import urllib
import csv
import staticmap

PLACE = 'Barcelona, Catalonia'
GRAPH_FILENAME = 'barcelona.graph'
SIZE = 800
HIGHWAYS_FILENAME = 'highways.csv'
HIGHWAYS_URL = 'https://opendata-ajuntament.barcelona.cat/data/dataset/1090983a-1c40-4609-8620-14ad49aae3ab/resource/1d6c814c-70ef-4147-aa16-a49ddb952f72/download/transit_relacio_trams.csv'
CONGESTIONS_URL = 'https://opendata-ajuntament.barcelona.cat/data/dataset/8319c2b1-4c21-4962-9acd-6db4c5ff1148/resource/2d456eb5-4ea6-4f68-9794-2f3f1a58a933/download'

Coordinate = collections.namedtuple('Coordinate', 'longitude latitude')
Highway = collections.namedtuple('Highway', 'description coordinates')
Congestion = collections.namedtuple('Congestion', 'datetime current_state planned_state')


def file_exists(filename):
    return os.path.isfile(filename)


def save_data(data, filename):
    with open(filename, 'wb') as file:
        pickle.dump(data, file)


def load_data(filename):
    with open(filename, 'rb') as file:
        data = pickle.load(file)
        return data


def download_graph(PLACE):
    graph = osmnx.graph_from_place(PLACE, network_type='drive', simplify=True)
    graph = osmnx.utils_graph.get_digraph(graph, weight='length')
    return graph


def download_highways(HIGHWAYS_URL):
    with urllib.request.urlopen(HIGHWAYS_URL) as response:
        lines = [line.decode('utf-8') for line in response.readlines()]
        reader = csv.reader(lines, delimiter=',', quotechar='"')
        next(reader)  # ignore first line with description
        highways = {}
        for line in reader:
            way_id, description, coordinates_as_str = line
            way_id = int(way_id)
            coordinate_list = list(map(float, coordinates_as_str.split(',')))
            coordinates = []
            for i in range(0, len(coordinate_list), 2):
                coordinates.append(Coordinate(coordinate_list[i], coordinate_list[i + 1]))
            highways[way_id] = Highway(description, coordinates)
        return highways


def plot_highways(highways, output_filename, SIZE):
    map = staticmap.StaticMap(SIZE, SIZE)
    for way_id, highway in highways.items():
        highway_line = staticmap.Line(highway.coordinates, 'black', 2)
        map.add_line(highway_line)
    map_image = map.render()
    map_image.save(output_filename)


def download_congestions(CONGESTIONS_URL):
    with urllib.request.urlopen(CONGESTIONS_URL) as response:
        lines = [line.decode('utf-8') for line in response.readlines()]
        reader = csv.reader(lines, delimiter='#', quotechar='"')
        congestions = {}
        for line in reader:
            way_id, datetime, current_state, planned_state = map(int, line)
            congestions[way_id] = Congestion(datetime, current_state, planned_state)
        return congestions


def plot_congestions(highways, congestions, output_filename, SIZE):
    map = staticmap.StaticMap(SIZE, SIZE)
    for way_id, highway in highways.items():
        congestion_state = congestions[way_id].current_state
        congestion_colors = ['#a9a9a9', '#2e8b57', '#7cfc00', '#ffa500', '#ff4500', '#bb0202', '#510101']
        congestion_line = staticmap.Line(highway.coordinates, congestion_colors[congestion_state], 2)
        map.add_line(congestion_line)
    map_image = map.render()
    map_image.save(output_filename)


def icolor(ispeed, min_ispeed, max_ispeed):
    range = min_ispeed - max_ispeed
    if range == 0:
        value = 0.5
    else:
        value = (ispeed - min_ispeed) / range
    hue = ((1 - value) * 120)
    return 'hsl({},100%,50%)'.format(hue)


def plot_igraph(igraph, output_filename, SIZE):
    min_ispeed, max_ispeed = float('inf'), 0
    for node1, node2, edge_data in igraph.edges(data=True):
        ispeed = edge_data['length'] / edge_data['itime']
        if ispeed < min_ispeed:
            min_ispeed = ispeed
        if ispeed > max_ispeed:
            max_ispeed = ispeed

    map = staticmap.StaticMap(SIZE, SIZE)
    for node1, node2, edge_data in igraph.edges(data=True):
        ispeed = edge_data['length'] / edge_data['itime']
        line = staticmap.Line([node_to_coordinates(igraph, node1), node_to_coordinates(igraph, node2)],
                              icolor(ispeed, min_ispeed, max_ispeed), 2)
        map.add_line(line)
    map_image = map.render()
    map_image.save(output_filename)


def build_igraph(graph, highways, congestions):
    for node1, node2, edge_data in graph.edges(data=True):
        graph[node1][node2]['itime'] = graph[node1][node2]['length']  # stub
    return graph


def node_to_coordinates(graph, node_id):
    return Coordinate(graph.nodes[node_id]['x'], graph.nodes[node_id]['y'])


def get_shortest_path_with_itimes(igraph, origin, destination, PLACE):
    origin_coordinates = osmnx.geocoder.geocode(origin + ', ' + PLACE)
    destination_coordinates = osmnx.geocoder.geocode(destination + ', ' + PLACE)

    origin_node = osmnx.get_nearest_node(igraph, origin_coordinates)
    destination_node = osmnx.get_nearest_node(igraph, destination_coordinates)

    ipath = osmnx.distance.shortest_path(igraph, origin_node, destination_node, weight='length')
    ipath = [node_to_coordinates(igraph, id) for id in ipath]
    return ipath


def plot_path(ipath, output_filename, SIZE):
    map = staticmap.StaticMap(SIZE, SIZE)
    icon_origin = staticmap.IconMarker(ipath[0], './icons/origin.png', 10, 32)
    icon_destination = staticmap.IconMarker(ipath[-1], './icons/destination.png', 10, 32)
    path_line = staticmap.Line(ipath, 'black', 2)
    map.add_line(path_line)
    map.add_marker(icon_origin)
    map.add_marker(icon_destination)
    map_image = map.render()
    map_image.save(output_filename)


def test():
    # load the graph, or download it if it does not exist
    if file_exists(GRAPH_FILENAME):
        graph = load_data(GRAPH_FILENAME)
    else:
        graph = download_graph(PLACE)
        save_data(graph, GRAPH_FILENAME)

    # load the highways, or download them if they do not exist
    if file_exists(HIGHWAYS_FILENAME):
        highways = load_data(HIGHWAYS_FILENAME)
    else:
        highways = download_highways(HIGHWAYS_URL)
        save_data(highways, HIGHWAYS_FILENAME)
    # plot the highways into a PNG image
    plot_highways(highways, 'highways.png', SIZE)

    # download congestions (we download them every time because they are updated every 5 minutes)
    congestions = download_congestions(CONGESTIONS_URL)
    # plot the congestions into a PNG image
    plot_congestions(highways, congestions, 'congestions.png', SIZE)

    # get the 'intelligent graph' version of the graph (taking into account the congestions of the highways)
    igraph = build_igraph(graph, highways, congestions)
    # plot the igraph into a PNG image
    plot_igraph(igraph, 'igraph.png', SIZE)

    # get 'intelligent path' between two addresses
    ipath = get_shortest_path_with_itimes(igraph, "Campus Nord", "Sagrada Família", PLACE)
    # plot the path into a PNG image
    plot_path(ipath, 'path.png', SIZE)


test()
