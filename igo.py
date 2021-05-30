"""
iGo is a module that lets you create igraphs ("intelligent graphs"). What makes them intelligent is
that their edges have an attribute called itime ("intelligent time"), which takes into account the 
length, the maximum driving speed and the current traffic data of a road, plus the time it takes to
turn depending on the angle and the side of this turn.

The module contains all the functions and data structures needed for acquiring and storing data
(the street network graph and the traffic data), building igraphs, searching ipaths ("intelligent 
paths"), and plotting different information into a map. Moreover, it also contains some utility
functions to convert between geocodable names, nodes, and coordinates. All the coordinates used
by the user of the module should use the Coordinates named tuple, which is in longitude-latitude
order.
"""

import collections
import csv
from datetime import datetime
import math
import os
import pickle
import re
import statistics
import urllib

import networkx
import osmnx
import shapely.geometry
import staticmap

Coordinates = collections.namedtuple("Coordinates", "longitude latitude")
Highway = collections.namedtuple("Highway", "description coordinates_list")
Congestion = collections.namedtuple("Congestion", "datetime current_state planned_state")


def file_exists(filename):
    """Returns True if the file with the specified filename is an existing regular file, or False
    otherwise.
    """
    return os.path.isfile(filename)


def save_data(data, filename):
    """Saves the object 'data' to a file with the specified filename."""
    with open(filename, "wb") as file:
        pickle.dump(data, file)


def load_data(filename):
    """Returns an object that has previously been stored in a file with the specified filename.

    Precondition: The file exists and is a pickled representation of the object.
    """
    with open(filename, "rb") as file:
        data = pickle.load(file)
        return data


def is_in_place(coordinates, place):
    """Returns True if the coordinates are inside the boundaries of the specified place.
    
    Precondition: 'place' is a geocodable string by the Nominatim API.
    """
    # The coordinates must be converted to a shapely.geometry.Point to use .intersects().
    point = shapely.geometry.Point(coordinates.longitude, coordinates.latitude)

    # Retrieve 'place' from the Nominatim API as a GeoDataFrame and take its geometry as a polygon 
    # constructed from a list of coordinates.
    shape = osmnx.geocode_to_gdf(place).loc[0, "geometry"] 

    # Return True if the point is inside the shape's boundary.
    return shape.intersects(point) 


# The regex is compiled outside to not repeat computations.
coordinates_regex = re.compile(r'-?[1-9][0-9]*(\.[0-9]+)?[,\s]\s*-?[1-9][0-9]*(\.[0-9]+)?')
separator_regex = re.compile(r'[,\s]\s*')
def name_to_coordinates(name, place, coordinates_order="lng-lat"):
    """Returns the coordinates given a string 'name', which can either be a geocodable string by
    the Nominatim API or a string representing a pair of coordinates. If the coordinates include a
    decimal part, a dot '.' must be used as a decimal separator. The pair of coordinates can be
    optionally separated by a comma ','.

    In case that 'name' is a pair of coordinates, 'coordinates_order' indicates their order, which
    by default is longitude-latitude ("lng-lat"). To use latitude-longitude order, set this
    parameter to "lat-lng".
    
    The obtained coordinates should be inside the boundaries of the place specified with the
    parameter 'place'.

    ValueError is raised if the Nominatim API can not find the given name, or if the obtained
    coordinates are not inside the boundaries of the specified place.

    Usage examples, with place="Barcelona":
     - name="Facultat de Nàutica"  -> Coordinates(longitude=2.184639040777029, latitude=41.382300799999996)
     - name="2.18511 41.38248"     -> Coordinates(longitude=2.18511, latitude=41.38248)
     - name="2.18511,    41.38248" -> Coordinates(longitude=2.18511, latitude=41.38248)
     - name="2 41"                 -> ValueError: The obtained coordinates Coordinates(longitude=2.0, latitude=41.0) are not inside the boundaries of 'Barcelona'.
     - name="Calldetenes"          -> ValueError: The obtained coordinates Coordinates(longitude=2.2834318, latitude=41.9257651) are not inside the boundaries of 'Barcelona'.
     - name="41.38248 2.18511"     -> ValueError: The obtained coordinates Coordinates(longitude=41.38248, latitude=2.18511) are not inside the boundaries of 'Barcelona'.
     - name="prprpr"               -> ValueError: Nominatim could not query 'prprpr, Barcelona'.

     Precondition: coordinates_order is either "lng-lat" (default) or "lat-lng".
    """
    # Use regex to know if 'name' is a string representing a pair of coordinates or a literal place name.
    if coordinates_regex.fullmatch(name):
        # Also use regex to split the pair of coordinates.
        lng, lat = re.split(separator_regex, name)
        lng, lat = float(lng), float(lat)

        # Swap the coordinates if specified.
        if coordinates_order == "lat-lng":
            lat, lng = lng, lat
    else:
        query = name + ", " + place
        
        # geocoder.geocode raise a ValueError if Nominatim does not find the place.
        try:
            lat, lng = osmnx.geocoder.geocode(query)
        except ValueError:
            raise ValueError("Nominatim could not query '" + query + "'.")
    
    coordinates = Coordinates(lng, lat)
    if not is_in_place(coordinates, place):
        raise ValueError("The obtained coordinates " + str(coordinates)
                         + " are not inside the boundaries of '" + str(place) + "'.")
    
    return coordinates


def haversine(coordinates1, coordinates2):
    """Returns the great-circle distance between two points on the Earth surface, given their
    coordinates.

    To calculate the result, the function uses the haversine formula.
    """
    lng1, lat1 = math.radians(coordinates1.longitude), math.radians(coordinates1.latitude)
    lng2, lat2 = math.radians(coordinates2.longitude), math.radians(coordinates2.latitude)
    d = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lng2 - lng1) / 2) ** 2
    return 2 * 6371008.8 * math.asin(math.sqrt(d))


def coordinates_to_node(graph, coordinates):
    """Returns the node of the graph that is closest to the given coordinates.

    Precondition: All the nodes of the graph have two attributes 'x' and 'y', which indicate
    their longitude and latitude, respectively.

    Note: If several nodes are at the same distance, only one of them is returned.
    """
    nearest_node = None
    nearest_distance = float("inf")

    for node in graph.nodes():
        distance = haversine(node_to_coordinates(graph, node), coordinates)
        if distance < nearest_distance:
            nearest_distance = distance
            nearest_node = node

    return nearest_node


def node_to_coordinates(graph, node_id):
    """Returns the Coordinates of the node of the graph identified by 'node_id'.

    Precondition: The node has two attributes 'x' and 'y', which indicate its longitude and
    latitude, respectively.
    """
    return Coordinates(graph.nodes[node_id]["x"], graph.nodes[node_id]["y"])


def nodes_to_coordinates_list(graph, node_list):
    """Returns a list of Coordinates given a list of nodes of the graph.

    Precondition: The nodes have two attributes 'x' and 'y', which indicate their longitude and
    latitude, respectively.
    """
    return [node_to_coordinates(graph, node) for node in node_list]


def build_default_graph(place):
    """Downloads and returns the graph built from the drivable roads within the boundaries of the
    specified place. The data is downloaded from OpenStreetMap.
    
    The returned graph is directed, does not have parallel edges nor self-loops edges, and is
    strongly connected.
    
    The nodes are identified by an integer value and have several attributes. The important ones
    for iGo are 'x' and 'y', the longitude and latitude of the node respectively.

    The edges have several attributes too. The important ones for iGo are 'length', the length of
    the street in meters; 'maxspeed', the maximum speed of the street in km/h (if there is a speed
    change in that street, it is a list of all the values), and 'bearing', the angle in degrees
    (clockwise) between north and the geodesic line from the origin node to the destination node of
    the edge.

    Precondition: 'place' is a geocodable string by the Nominatim API.
    """
    # Download the graph of the drivable roads and simplify it.
    graph = osmnx.graph_from_place(place, network_type="drive", simplify=True)

    # Remove self-loop edges, as they should not exist.
    graph.remove_edges_from(networkx.selfloop_edges(graph))

    # Add the 'bearing' attribute to all the edges.
    graph = osmnx.bearing.add_edge_bearings(graph)

    # Remove parallel edges, choosing between them by minimizing its length attribute.
    graph = osmnx.utils_graph.get_digraph(graph, weight="length")

    # The downloaded graph is not strongly connected due to cuts in the boundaries (in the case of
    # Barcelona, it has more than 200 strongly connected components (SCCs)!) This makes it 
    # impossible to find a path between some nodes (if they are in different SCCs). Fortunately, 
    # all the SCCs are very small (<10 nodes) except for the main one (>8000 nodes). With the
    # following line, the graph is overwritten to only be this main SCC.
    graph = graph.subgraph(max(networkx.strongly_connected_components(graph), key=len)).copy()
    
    return graph


def download_highways(highways_url):
    """Downloads a file from the specified 'highways_url', which contains information about some of
    the main street sections of Barcelona. 
    
    Each line represents a highway specified with an ID which is an integer, its name or
    description and a list of pairs of longitude-latitude coordinates, all this separated by commas.
    These coordinates are the points that define the highway in a map.

    This information is stored and returned as a dictionary from way ID to Highway (a named tuple
    with two attributes: 'description' and 'coordinates_list').
    """
    with urllib.request.urlopen(highways_url) as response:
        lines = [line.decode("utf-8") for line in response.readlines()]
        reader = csv.reader(lines, delimiter=",", quotechar="\"")
        next(reader)  # Ignore first line with description.

        highways = {}
        for line in reader:
            way_id, description, coordinates_str = line
            way_id = int(way_id)  # Way IDs are originally read as strings.
            all_coordinate_list = list(map(float, coordinates_str.split(",")))
            coordinates_list = []
            for i in range(0, len(all_coordinate_list), 2):
                # Save pairs of Coordinates.
                coordinates_list.append(Coordinates(all_coordinate_list[i], all_coordinate_list[i + 1]))
            highways[way_id] = Highway(description, coordinates_list)
        
        return highways


def build_highway_paths(graph, highways):
    """Returns a dictionary from way ID to list of nodes of the graph. Each list of nodes represents
    the respective highway from the parameter 'highways'. This function converts each Highway to
    to a list of nodes.

    Preconditions: 
     - 'highways' is a dictionary from way ID to Highway.
     - Every node has two attributes 'x' and 'y', which indicate their longitude and latitude,
       respectively.
     - Every edge has the attribute 'length', in meters.
    """
    highway_paths = {}
    for way_id, highway in highways.items():
        highway_paths[way_id] = []
        for i in range(len(highway.coordinates_list) - 1):
            node1 = coordinates_to_node(graph, highway.coordinates_list[i])
            node2 = coordinates_to_node(graph, highway.coordinates_list[i + 1])
            if i > 0:
                highway_paths[way_id].pop()  # Avoid repeated nodes from concatenatig paths.
            highway_paths[way_id].extend(osmnx.distance.shortest_path(graph, node1, node2, weight="length"))
    return highway_paths


def set_default_itime(graph):
    """Sets the default 'itime' attribute for every edge in the specified graph. It represents how
    much time is needed in seconds to go across an edge, which in this case is a section of the 
    public road of Barcelona. The length and the maximum allowed speed of the section are the only
    things taken into account to compute this value.

    The edge attribute 'maxspeed' is the maximum allowed speed for a vehicle driving in the section
    of road that the edge represents and it is given in km/h. If an edge has more than one maxspeed,
    it is assumed to be its mean.

    If an edge does not have a maximum speed, it is assumed by default that it is 30 km/h based on 
    the 'Barcelona 30 City' initiative that Barcelona is following, which makes it have more than
    50% of its streets with a 30 km/h restriction and a prediction for the end of 2021 for this
    being a 75%. More info: https://www.barcelona.cat/mobilitat/en/barcelona-30-city.

    In order to have the 'itime' in seconds, 'maxspeed' is converted to m/s for all the edges.

    Preconditions: 
     - Every edge has the attribute 'length', in meters.
     - If an edge has the attribute 'maxspeed', it is in km/h.
    """
    for node1, node2, edge_data in graph.edges(data=True):
        if "maxspeed" in edge_data:
            if type(edge_data["maxspeed"]) is not list:
                edge_data["maxspeed"] = float(edge_data["maxspeed"])  # 'maxspeed' is originally a string.
            else:  # The edges that have more than one 'maxspeed'.
                maxspeeds = [float(maxspeed) for maxspeed in edge_data["maxspeed"]]
                edge_data["maxspeed"] = statistics.mean(maxspeeds)
        else:
            edge_data["maxspeed"] = 30

        edge_data["maxspeed"] *= 1000 / 3600  # Convert from km/h to m/s.
        graph[node1][node2]["itime"] = edge_data["length"] / edge_data["maxspeed"]


def bearing_itime(igraph, predecessor, node, successor):
    """Returns the time cost in seconds of going through two adjacent edges depending on the angle
    they form given three inodes: predecessor (the source), node (the one both edges have in common) 
    and successor (the destination), and also depending on if the turn given by this angle is done
    to the left or to the right.

    This value is computed using a piecewise function from the angle between the two edges, which is
    first calculated from the edge attribute 'bearing'. This angle goes from -180 to 180 degrees,
    where the sign indicates the orientation (left or right). However, the mathematical function is 
    evaluated on the absolute value of it. Moreover, the point where it changes is 50, which is
    considered a frontier between turning and going straight with a slight curve. A graph of the
    mathematical function can be seen here: https://www.geogebra.org/calculator/fdnnamqy.

    This function evaluated on the most remarkable angles has the following values:
    angle |   0   |   45   |   50   |   90   |   135   |   180   |
    itime |   0   |  1.72  |  3.22  |  7.61  |   9.00  |  9.81   |

    The result is multiplied by the side factor, which is 1 if the turn is to the right (unmodified) 
    and 1.5 if the turn is of more than 15 degrees to the left, since it is slower to turn left 
    than it is to turn right.

    Preconditions: 
     - 'predecessor', 'node', and 'successor' are inodes of the igraph.
     - The edges connecting the inodes have a valid 'bearing' attribute.
    """
    # Calculate the angle between both edges and normalize it between -180 and 180 degrees.
    bearing = igraph[node][successor]["bearing"] - igraph[predecessor][node]["bearing"]
    if bearing < -180:
        bearing += 360
    elif bearing > 180:
        bearing -= 360

    # Calculate the side factor.
    side_factor = 1
    if bearing < -15:  # -15 is 15 degrees to the left.
        side_factor = 1.5

    # Get the absolute value.
    if bearing < 0:
        bearing = -bearing

    # Compute the cost differently depending on the bearing.
    if bearing < 50:
        bearing_cost = math.exp(bearing / 45) - 1
    else:
        bearing_cost = math.log((bearing - 45) ** 2)

    return bearing_cost * side_factor


def build_igraph_with_bearings(graph):
    """Returns a new graph built from the given one so that it is possible to search for a shortest 
    path taking into account the time it takes to turn. In order to do this, the original graph 
    topology is modified. 
    
    The main idea is that, when an edge enters a node and there is more than one exiting edge,
    going to one or another has a certain bearing cost attributed to the physical angle they form.
    To add this cost, each node of the graph is expanded to multiple "inodes" of different type, and 
    new edges are added between them, while the original ones are still maintained. A graph made of
    inodes is called an igraph, which stands for "intelligent graph".

    An igraph has four types of inodes: In, Out, Source, and Destination; and three types of edges:
    real, bearing and path-ends edges.

    One In inode with ID 'I_node_predecessor' is created for every edge entering a node coming from
    a predecessor node. Similarly, one Out inode with ID 'O_node_successor' is created for every
    edge exiting a node to a successor node.

    Furthermore, for every node of the given graph, one Source inode with ID 'S_node' and one
    Destination inode with ID 'D_node' are created. Every path searched in the returned igraph must
    start from a Source inode and end in a Destination inode.

    All the inodes have an attribute named 'metanode' which stores the node ID from the original
    node they come from.

    Real edges are made from the original edges of the graph, which represent the physical streets.
    They go from Out to In inodes, and their their 'itime' and 'length' attributes remain untouched.
    For example, an edge 3 -> 7 from the given graph, would be converted to 'O_3_7' -> 'I_7_3'.
    
    Bearing edges are created from each In inode to every Out inode of a same metanode, forming
    every possible choice of exiting a node once one has entered it. The 'itime' of the bearing
    edges is the cost in seconds of turning from one real edge to another, and it is calculated by
    the bearing_itime function.
    
    Path-ends edges are the ones that connect with the Source and Destination inodes. For each
    metanode, its Source inode is connected to all its Out inodes, and similarly, all its In inodes
    are connected to its Destination inode. The path-ends edges have all itime 0, as they do not
    imply a real cost.

    The Source and Destination inodes exist to avoid adding the bearing cost at the beginning and
    at the end of the path. Because of that, it is not possible to enter a Source inode, nor to exit
    a Destination one.

    The result of doing all this in a small graph can be seen in the following link:
    https://i.imgur.com/hTJ3lVJ.png

    Preconditions:
     - Every node has two attributes 'x' and 'y', which indicate their longitude and latitude,
       respectively.
     - Every edge has the attribute 'length', in meters.
     - Every edge has the attribute 'bearing', in degrees, representing the angle between north and
       the geodesic line from the origin node to the destination node.
     - No self-loop edges exist in the graph.
    """
    # Create a new directed graph from scratch.
    igraph_with_bearings = networkx.DiGraph()

    # Iterate for every node of the given graph, which is only used to read information and is not modified.
    for node, node_data in graph.nodes(data=True):
        in_nodes, out_nodes = [], []

        # Add In inodes.
        for predecessor in graph.predecessors(node):
            id = "I_" + str(node) + "_" + str(predecessor)
            igraph_with_bearings.add_node(id, x=node_data["x"], y=node_data["y"], metanode=node)
            in_nodes.append((id, predecessor))

        # Add Out inodes.
        for successor in graph.successors(node):
            id = "O_" + str(node) + "_" + str(successor)
            igraph_with_bearings.add_node(id, x=node_data["x"], y=node_data["y"], metanode=node)
            out_nodes.append((id, successor))

        # Add bearing edges (In -> Out), with the itime associated to turning.
        for in_node, predecessor in in_nodes:
            for out_node, successor in out_nodes:
                igraph_with_bearings.add_edge(in_node, out_node, itime=bearing_itime(graph, predecessor, node, successor))

        # Add the Source inode, and connect it to every Out inode (Source -> Out).
        igraph_with_bearings.add_node("S_" + str(node), x=node_data["x"], y=node_data["y"], metanode=node)
        for out_node, predecessor in out_nodes:
            igraph_with_bearings.add_edge("S_" + str(node), out_node, itime=0)

        # Add the Destination inode, and connect it to every In inode (In -> Destination).
        igraph_with_bearings.add_node("D_" + str(node), x=node_data["x"], y=node_data["y"], metanode=node)
        for in_node, successor in in_nodes:
            igraph_with_bearings.add_edge(in_node, "D_" + str(node), itime=0)

    # Add the real edges of the graph (Out -> In). Their 'itime' and 'length' attributes are maintained.
    for node1, node2, edge_data in graph.edges(data=True):
        igraph_with_bearings.add_edge("O_" + str(node1) + "_" + str(node2), "I_" + str(node2) + "_" + str(node1),
                                      itime=edge_data["itime"], length=edge_data["length"])

    return igraph_with_bearings


def build_static_igraph(graph):
    """Returns an igraph ("intelligent graph") built from the given graph. All the edges of the
    igraph have an attribute called 'itime' which indicate the time needed to traverse that edge.
    Moreover, the topology of the given graph is modified to account for the cost of turning.

    To see further information about the 'itime' and the bearings, see the documentation of
    set_default_itime and build_igraph_with_bearings.

    Preconditions:
     - Every node has two attributes 'x' and 'y', which indicate their longitude and latitude,
       respectively.
     - Every edge has the attribute 'length', in meters.
     - Every edge has the attribute 'bearing', in degrees, representing the angle between north and
       the geodesic line from the origin node to the destination node.
     - If an edge has the attribute 'maxspeed', it is in km/h.
     - No self-loop edges exist in the graph.
    """
    set_default_itime(graph)
    return build_igraph_with_bearings(graph)


def download_congestions(congestions_url):
    """Downloads a file from the specified 'congestions_url', which contains information about the
    current traffic in some of the main street sections of Barcelona. The data is updated every
    five minutes.

    Each line represents a highway specified with its ID, the datetime in format YYYYmmddHHMMSS of
    the last update, the current congestion, and the one that is expected in 15 minutes, all
    separated by '#'. The states are coded with integers from 0 to 6 with the following meanings:
    no data (0), very fluid (1), fluid (2), dense (3), very dense (4), congested (5), closed (6).

    This information is stored and returned as a dictionary from way ID to Congestion (a named tuple
    with three attributes: 'datetime' (a Python datetime.datetime object), 'current_state' and
    'planned_state').
    """
    with urllib.request.urlopen(congestions_url) as response:
        lines = [line.decode("utf-8") for line in response.readlines()]
        reader = csv.reader(lines, delimiter="#", quotechar="\"")

        congestions = {}
        for line in reader:
            way_id, update_datetime, current_state, planned_state = line
            way_id, current_state, planned_state = int(way_id), int(current_state), int(planned_state)
            update_datetime = datetime.strptime(update_datetime, "%Y%m%d%H%M%S")
            congestions[way_id] = Congestion(update_datetime, current_state, planned_state)

        return congestions


def congestion_function(congestion_state):
    """Returns the value that represents the factor that is applied to the needed time to drive 
    across a road taking into account the traffic congestions. This value is the evaluation the
    following function on the congestion_state: https://www.geogebra.org/calculator/sy4cy7zy.
    
    The congestion_state should be a real number between 1 and 5.

    Table of values of the congestion_function:
    state  |   1   |    2   |    3   |    4   |   5   |
    factor |   1   |  1.14  |  1.70  |  3.32  |  8.44 |
    """
    return math.exp((congestion_state - 1) ** 2 / 7.5)


def build_dynamic_igraph(igraph, highway_paths, congestions):
    """Returns a new igraph built from the given one but with modified 'itime' edge attributes that
    now take into account the current traffic data available, which is given by the congestions and
    the highway paths.
    
    Precondition: 'highway_paths' is a dictionary from way ID to list of nodes of the graph, and
    'congestions' is a dictionary from way ID to Congestion. The IDs relate both dictionaries.
    Note: 'highway_paths' has lists of nodes (integer IDs), not inodes (string IDs). This allows the
    function to use directly the value returned by build_highway_paths.
    """
    # Make a copy of the igraph, so the function can be called several times without modifying it.
    igraph = igraph.copy()

    # Iterate over the highway paths and compute the congestion of every edge.
    for way_id, highway_path in highway_paths.items():
        congestion_state = congestions[way_id].current_state

        # Suppose that if there is no data, there is no traffic and hence it is very fluid. 
        if congestion_state == 0:
            congestion_state = 1
        
        # Iterate over the edges of the highway path.
        for i in range(len(highway_path) - 1):
            # Convert from node ID to inode ID.
            inode1 = "O_" + str(highway_path[i]) + "_" + str(highway_path[i + 1])
            inode2 = "I_" + str(highway_path[i + 1]) + "_" + str(highway_path[i])
            
            # Add an edge attribute called 'congestions', which is a list with all the congestion
            # states of the edge because, due to data inaccuracies, some edges are assigned more
            # than one congestion state.
            if "congestions" not in igraph[inode1][inode2]:
                igraph[inode1][inode2]["congestions"] = [congestion_state]
            else:
                igraph[inode1][inode2]["congestions"].append(congestion_state)

    # Calculate the itime of all the edges of the igraph.
    for inode1, inode2 in igraph.edges():
        if "congestions" in igraph[inode1][inode2]:
            edge_congestions = igraph[inode1][inode2]["congestions"]
            
            if 6 in edge_congestions:
                # If 6 is assigned to the edge, the road is closed, so its itime is infinity.
                igraph[inode1][inode2]["itime"] = float("inf")
            else:
                # Multiply the itime of the edge by the factor returned by the congestion_function,
                # calculated given the mean of all the congestions that have been assigned to the edge.
                igraph[inode1][inode2]["itime"] *= congestion_function(statistics.mean(edge_congestions))

    return igraph


def get_ipath(igraph, source_coordinates, destination_coordinates):
    """Returns the shortest intelligently searched path in an igraph, from the specified source 
    coordinates to the specified destination coordinates, or None if there is no path.
    
    The path is searched minimizing the edge attribute 'itime', that takes into account the length,
    the maximum driving speed and the current traffic data of a road, plus the time it takes to turn
    depending on the angle and the side of this turn.
    """
    # Convert the source and destination coordinates to a Source and Destination inodes, respectively.
    source = "S_" + str(igraph.nodes[coordinates_to_node(igraph, source_coordinates)]["metanode"])
    destination = "D_" + str(igraph.nodes[coordinates_to_node(igraph, destination_coordinates)]["metanode"])

    # Use [source] and [destination] to avoid OSMnx to iterate the characters of the inode IDs.
    # Since a list is passed, it returns a list too, but it always has length one.
    ipath = osmnx.distance.shortest_path(igraph, [source], [destination], weight="itime")[0]

    # Return None if no path is found (if the source and destination inodes are in different SCCs).
    if not ipath:
        return None

    # Return None if the only way of going from the source to the destination is through a closed road.
    for i in range(len(ipath) - 1):
        if igraph[ipath[i]][ipath[i + 1]]["itime"] is float("inf"):
            return None

    # Convert the inodes back to coordinates and return the path.
    return [source_coordinates] + [node_to_coordinates(igraph, id) for id in ipath] + [destination_coordinates]


def get_highways_plot(graph, highway_paths, size):
    """Returns a square StaticMap of the specified size (in pixels) with the highways plotted with
    2px black lines using the coordinates of the highway_paths nodes.
    
    Preconditions:
     - 'highway_paths' is a dictionary from way ID to list of nodes of the graph.
     - Every node has two attributes 'x' and 'y', which indicate their longitude and latitude,
       respectively.
     - 'size' is a positive integer that indicates the dimensions in pixels of the map.
    """
    # Create an empty square map of the given size.
    map = staticmap.StaticMap(size, size)

    for path in highway_paths.values():
        # Draw a 2px line using the coordinates of the highway_paths nodes.
        highway_line = staticmap.Line(nodes_to_coordinates_list(graph, path), "black", 2)
        map.add_line(highway_line)

    return map


def get_congestions_plot(graph, highway_paths, congestions, size):
    """Returns a square StaticMap of the specified size with the highway_paths plotted with 2px
    lines of different colors depending on their associated congestion state, which is given by
    the specified congestions parameter. A highway and its congestion are related by their way IDs,
    and they are plotted using the coordinates of the highway_paths nodes.

    The chosen colors for each state from 0 to 6 are:
    Gray, Forest Green, Lawn Green, Orange, Orange Red, Dark Red, and Dark Maroon, respectively.

    Preconditions: 
     - 'highway_paths' is a dictionary from way ID to list of nodes of the graph, and 'congestions'
        is a dictionary from way ID to Congestion. The IDs relate both dictionaries.
     - Every node has two attributes 'x' and 'y', which indicate their longitude and latitude,
       respectively.
     - 'size' is a positive integer that indicates the dimensions in pixels of the map.
    """
    # Create an empty square map of the given size.
    map = staticmap.StaticMap(size, size)

    for way_id, path in highway_paths.items():
        # Every highway_path has a corresponding congestion from the way_id relation.
        congestion_state = congestions[way_id].current_state

        # A list is used to relate the congestion_state to the color that is used to paint the lines.
        congestion_colors = ["#a9a9a9", "#228b22", "#7cfc00", "#ffa500", "#ff4500", "#bb0202", "#510101"]

        # Draw a 2px line of the corresponding color using the coordinates of the highway_paths nodes.
        congestion_line = staticmap.Line(nodes_to_coordinates_list(graph, path), congestion_colors[congestion_state], 2)
        map.add_line(congestion_line)

    return map


def icolor(ispeed, min_ispeed, max_ispeed):
    """This is an auxiliary function of get_igraph_plot. It returns a string representing a color
    in HSL (hue, saturation, lightness) format, where the hue of the color is directly proportional
    to the given ispeed. min_ispeed and max_ispeed are the minimum and maximum different than zero
    ispeed values of the igraph.

    The returned icolor is computed with the proportion between the specified ispeed and the range 
    of the igraph ispeeds, which should be the same for all the calls to the function in a single 
    igraph plot. However, if the ispeed is zero (closed road) "black" is returned, and if the range 
    is zero (same ispeed in all the igraph) "yellow" is returned.

    The icolor ranges from red (hue = 0 degrees), to represent the slowest streets, to medium spring
    green (hue = 160 degrees), for the fastest ones. In between, it goes through gradient shades of 
    orange, yellow, and green. All HSL colors returned have 100% saturation, and 50% lightness.

    Precondition: 0 < min_ispeed <= ispeed <= max_ispeed, or ispeed = 0, to represent a closed road.
    """
    if ispeed == 0:  # The road is closed.
        return "black"

    ispeed_range = max_ispeed - min_ispeed

    if ispeed_range == 0:  # All the ispeeds are the same.
        return "yellow"

    proportion = (ispeed - min_ispeed) / ispeed_range

    hue = proportion * 160  # 160 is the hue of medium spring green, the color of the fastest ispeed.

    # Return the color in HSL format.
    return "hsl({},100%,50%)".format(round(hue, 2))


def get_igraph_plot(igraph, size):
    """Returns a square StaticMap of the specified size with all the edges of the igraph plotted
    with 2px lines. Each line is painted with an 'icolor' that represents the ispeed of that street
    proportionally to the rest of ispeeds of the igraph. If a road is closed, it is painted black.
    For further information about how the color is determined, see the icolor function.

    Precondition: 'size' is a positive integer that indicates the dimensions in pixels of the map.
    """
    # Calculate min_ispeed and max_ispeed, which are needed for the icolor function.
    min_ispeed, max_ispeed = float("inf"), 0
    for inode1, inode2, edge_data in igraph.edges(data=True):
        if "length" in edge_data:
            ispeed = edge_data["length"] / edge_data["itime"]
            if ispeed != 0:  # min_ispeed and max_ispeed must not be 0.
                if ispeed < min_ispeed:
                    min_ispeed = ispeed
                if ispeed > max_ispeed:
                    max_ispeed = ispeed

    # Create an empty square map of the given size.
    map = staticmap.StaticMap(size, size)

    # Draw all the edges into the map using 2px lines of the computed icolor.
    for inode1, inode2, edge_data in igraph.edges(data=True):
        if "length" in edge_data:
            ispeed = edge_data["length"] / edge_data["itime"]
            iline = staticmap.Line([node_to_coordinates(igraph, inode1), node_to_coordinates(igraph, inode2)],
                                   icolor(ispeed, min_ispeed, max_ispeed), 2)
            map.add_line(iline)

    return map


def get_ipath_plot(ipath, size):
    """Returns a square StaticMap of the specified size with the specified ipath plotted with 5px
    Dodger Blue lines except for those that connect the source and destination to the rest of the 
    path, which are Light Blue. A different color is used to show the actual given coordinates
    compared to the ones of their nearest inode that has been used to find the path. Moreover, a
    green marker icon is added at the source of the path, and a red one at its destination.

    Preconditions: 
     - 'ipath' is a list of Coordinates that contain at least the source and destination.
     - 'size' is a positive integer that indicates the dimensions in pixels of the map.
    """
    # Create an empty square map of the given size.
    map = staticmap.StaticMap(size, size)

    # Draw the line from the source coordinates to the first inode of the path with a 5px Light Blue line.
    start_line = staticmap.Line(ipath[:2], "LightBlue", 5)
    map.add_line(start_line)

    # Draw the path with 5px Dodger Blue lines.
    path_lines = staticmap.Line(ipath[1:-1], "DodgerBlue", 5)
    map.add_line(path_lines)

    # Draw the line from the last inode of the path to the destination coordinates with a 5px Light Blue line.
    end_line = staticmap.Line(ipath[-2:], "LightBlue", 5)
    map.add_line(end_line)

    # Add the source and destination markers into the map.
    source_icon = staticmap.IconMarker(ipath[0], "./icons/source.png", 10, 32)
    destination_icon = staticmap.IconMarker(ipath[-1], "./icons/destination.png", 10, 32)
    map.add_marker(source_icon)
    map.add_marker(destination_icon)

    return map


def get_location_plot(location_coordinates, size):
    """"Returns a square StaticMap of the specified size that shows the surroundings of the
    specified location coordinates. A green marker is added at the exact point represented by
    this given coordinates.

    Precondition: 'size' is a positive integer that indicates the dimensions in pixels of the map.
    """
    # Create an empty square map of the given size.
    map = staticmap.StaticMap(size, size)

    # Add the marker into the map, centered in the location coordinates.
    location_icon = staticmap.IconMarker(location_coordinates, "icons/source.png", 10, 32)
    map.add_marker(location_icon)

    return map


def save_map_as_image(map, filename):
    """Saves the StaticMap 'map' as an image with the specified filename. The image format used is
    determined by the filename extension.

    Precondition: the map is not empty (it has some kind of point, line, polygon or marker in it).
    """
    map_image = map.render()
    map_image.save(filename)


def _test():
    """This function is used to test the module and should not be used by other modules."""
    # Constants.
    PLACE = "Barcelona, Barcelonés, Barcelona, Catalonia"
    DEFAULT_GRAPH_FILENAME = "graph.dat"
    STATIC_IGRAPH_FILENAME = "static_igraph.dat"
    HIGHWAYS_FILENAME = "highways.dat"
    SIZE = 1200
    HIGHWAYS_URL = "https://opendata-ajuntament.barcelona.cat/data/dataset/1090983a-1c40-4609-8620-14ad49aae3ab/resource/" \
                   "1d6c814c-70ef-4147-aa16-a49ddb952f72/download/transit_relacio_trams.csv"
    CONGESTIONS_URL = "https://opendata-ajuntament.barcelona.cat/data/dataset/8319c2b1-4c21-4962-9acd-6db4c5ff1148/resource/" \
                      "2d456eb5-4ea6-4f68-9794-2f3f1a58a933/download"

    # Load the default graph, or build it if it does not exist and save it for later use.
    if file_exists(DEFAULT_GRAPH_FILENAME):
        graph = load_data(DEFAULT_GRAPH_FILENAME)
    else:
        graph = build_default_graph(PLACE)
        save_data(graph, DEFAULT_GRAPH_FILENAME)

    print("Default graph loaded!")

    # Load the highway paths, or build them if they do not exist and save them for later use.
    if file_exists(HIGHWAYS_FILENAME):
        highway_paths = load_data(HIGHWAYS_FILENAME)
    else:
        highways = download_highways(HIGHWAYS_URL)
        highway_paths = build_highway_paths(graph, highways)
        save_data(highway_paths, HIGHWAYS_FILENAME)

    # Plot the highways into a PNG image.
    save_map_as_image(get_highways_plot(graph, highway_paths, SIZE), "highways.png")

    print("Highway paths loaded and plotted!")

    # Load the static igraph, or build it if it does not exist and save it for later use.
    if file_exists(STATIC_IGRAPH_FILENAME):
        igraph = load_data(STATIC_IGRAPH_FILENAME)
    else:
        igraph = build_static_igraph(graph)
        save_data(igraph, STATIC_IGRAPH_FILENAME)

    print("Static igraph loaded!")

    # Download congestions (they are downloaded every time because they are updated every 5 minutes).
    congestions = download_congestions(CONGESTIONS_URL)

    # Plot the congestions into a PNG image.
    save_map_as_image(get_congestions_plot(graph, highway_paths, congestions, SIZE), "congestions.png")

    print("Congestion data downloaded and plotted!")

    # Get the dynamic version of the igraph (taking into account the congestions of the highways).
    igraph = build_dynamic_igraph(igraph, highway_paths, congestions)

    # Plot the igraph into a PNG image.
    save_map_as_image(get_igraph_plot(igraph, SIZE), "igraph.png")

    print("Dynamic igraph loaded and plotted!")

    # Get the ipath between two addresses.
    source = "Casa de l'Aigua"
    destination = "Platja de Sant Sebastià"
    ipath = get_ipath(igraph, name_to_coordinates(source, PLACE), name_to_coordinates(destination, PLACE))

    # Plot the ipath into a PNG image.
    save_map_as_image(get_ipath_plot(ipath, SIZE), "ipath.png")

    print("Path from", source, "to", destination, "found and plotted!")


# This is only executed when the file is explicitly executed (with "python3 igo.py").
if __name__ == "__main__":
    _test()
