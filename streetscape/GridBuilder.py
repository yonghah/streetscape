import math 
import numpy as np
import pandas as pd
import os
import asyncio
import aiohttp
import ssl
from shapely.geometry import Point, LineString
import geopandas as gpd


class GridBuilder:
    ''' class Grid creates 1d grid along with street segments geodataframe'''
    
    def __init__(self):
        self.distance = 10
        self.normalized = False
        self.seg_end = True
        self.gdf = None
        self.end_gap_dist = 0.001 # gap threshold for seg_end
        self.segment_id = 'osmid'
        self.grid_gdf = None
    
    def create(self, gdf):
        ''' create grid geodataframe'''
        self.gdf = gdf
        r = self.gdf\
            .apply(self._create_grid_row, axis=1)\
            .sum()
        self.grid_gdf = gpd.GeoDataFrame(r)
        
        # add metadata url
        self.grid_gdf['metadata_url'] = self.grid_gdf.apply(self._metadata_url, axis=1)
        
        print(f"{len(self.grid_gdf)} grid points created")
        return self.grid_gdf
        
    def graph2gdf(self, graph):
        streets = []
        for edge in graph.edges(data=True):
            street = {**{'osm_u': edge[0], 'osm_v': edge[1]}, **edge[2]}
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
    
    def _create_grid_row(self, segment):
        ''' for each street segment, add observation points at fixed distance 
        and add both of the ends if necessary'''
    
        points = list()  # output

        # whether normalized or not, points are created in normalized manner
        length = segment.length
        if self.normalized:
            length = 1.0
        step = self.distance / length
        n_full_step = math.floor(1.0/step) # number of full step
        offset = 0.5 * (1 - step * n_full_step)

        points_added = 0
        current_dist = offset

        # add segment start point if seg_end
        if self.seg_end:
            points.append({
                'segment_id':segment[self.segment_id], 
                'point_id': points_added,
                'seg_end': 1,
                'geometry':segment.geometry.interpolate(0, normalized=True)
            })
            points_added += 1

        # add internal points
        while(current_dist < 1 - self.end_gap_dist):
            if current_dist > self.end_gap_dist:
                points.append({
                        'segment_id':segment[self.segment_id], 
                        'point_id': points_added,
                        'seg_end': 0,
                        'geometry':segment.geometry.interpolate(current_dist, normalized=True)
                })
            current_dist += step
            points_added += 1

        # add segment end point if seg_end
        if self.seg_end:
            points.append({
                'segment_id':segment[self.segment_id], 
                'point_id': points_added,
                'seg_end': -1,
                'geometry':segment.geometry.interpolate(1, normalized=True)
            })
            points_added += 1

        return points
    
    def _metadata_url(self, obs_point):
        ''' construct a url for retrieving gsv metadata 
        at obs point location'''
        lat = obs_point.geometry.y
        lng = obs_point.geometry.x
        base = "https://maps.googleapis.com/maps/api/streetview/metadata?"
        latlng = "location={},{}".format(lat, lng)
        key = "key={}".format(api_key)
        source = "source=outdoor"
        url = "{}&{}&{}".format(base, latlng, source)
        return url