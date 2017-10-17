#!/usr/bin/env python

import os
import requests
import geopandas as gpd
from shapely.geometry import Point, LineString
import networkx as nx
import osmnx as ox


def get_street_views(lid, lat, lng, save_dir, fov=20, pad=2):
    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    api_key = os.environ['GSV_API_KEY']
    headings = [ang * fov for ang in range(0, int(360 / fov))]
    for heading in headings:
        base = "https://maps.googleapis.com/maps/api/streetview?size=640x640"
        latlng = "location={},{}".format(lat, lng)
        view = "heading={}&fov={}".format(heading, fov + 2 * pad)
        key = "key={}".format(api_key)
        pitch = "pitch=-5"
        url = "{}&{}&{}&{}&{}".format(base, latlng, view, pitch, key)
        output = os.path.join(save_dir,
                              "LOC_{}_h{}.jpg".format(lid, heading))
        if os.path.exists(output):
            os.remove(output)
        res = requests.get(url)
        with open(output, 'wb') as image_file:
            image_file.write(res.content)


def get_street_views_from_df(df, save_dir="output", geom="obs_point",
                             pic_per_obs=4, pad=2):
    fov = 360.0 / pic_per_obs;
    def apply_obs_gsv(row):
        lid = row.name
        lat = row[geom].y
        lng = row[geom].x
        get_street_views(lid, lat, lng, save_dir, fov, pad)

    df.apply(apply_obs_gsv, axis=1)


def create_observation_points(city):
    if issubclass(type(city), nx.Graph):
        graph = city
    elif issubclass(type(city), str):
        graph = ox.graph_from_place(city)
    line_df = convert_graph_to_gdf(graph).assign(
        obs_point=lambda x: x.geometry.interpolate(0.5, normalized=True))
    pdf = gpd.GeoDataFrame(line_df['obs_point'],
                           geometry='obs_point',
                           crs={'init':'epsg:4326'})
    return pdf


def convert_graph_to_gdf(graph):
    streets = []
    for edge in graph.edges(data=True):
        street = merge_dicts({'osm_u':edge[0], 'osm_v': edge[1]}, edge[2])
        streets.append(street)
    for street in streets:
        if 'geometry' not in street:
            u = Point(graph.node[street['osm_u']]['x'],
                      graph.node[street['osm_u']]['y'])
            v = Point(graph.node[street['osm_v']]['x'],
                      graph.node[street['osm_v']]['y'])
            street['geometry'] = LineString([u, v])
    converted = gpd.GeoDataFrame(streets)[
        ['osmid', 'name', 'length', 'geometry']]
    return converted


def merge_dicts(*dict_args):
    """
    Given any number of dicts, shallow copy and merge into a new dict,
    precedence goes to key value pairs in latter dicts.
    """
    result = {}
    for dictionary in dict_args:
        result.update(dictionary)
    return result

