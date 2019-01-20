# -*- coding: utf-8 -*-

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
    ''' creates 1d grid along with street segments 

    Attributes:
        distance : float
            distance between grid 
        normalized : bool
            If True, distance is relative value; otherwise absolute.
            When normalized is True, distance should be [0,1]
        seg_end : bool
            if true, force to include both ends of a segment
        end_gap_dist : float
            gap threshold between grid point and seg_end
        segment_id: string
            name of column contains street segment id
        
        segment_gdf: GeoDataFrame 
            geodataframe for street segments (input)
        grid_gdf: GeoDataFrame 
            geodataframe for grid points (output)

    Methods:
        create(gdf)
            create grid geodataframe
        graph2gdf(graph)
            convert osmnx graph to geodataframe
    Example:
        $ gb = GribBuilder(distance=10.0)
        $ grid_gdf = gb.create(street_gdf)
    '''
    
    def __init__(self, 
                 distance=10.0, 
                 normalized=False, 
                 seg_end=True, 
                 end_gap_dist=0.001, 
                 segment_id = 'osmid'):

        self.distance = distance
        self.normalized = normalized
        self.seg_end = seg_end
        self.end_gap_dist = end_gap_dist
        self.segment_id = segment_id
        
        self.segment_gdf = None
        self.grid_gdf = None
    
    def create(self, gdf):
        ''' create grid geodataframe'''
        self.segment_gdf = gdf
        r = self.segment_gdf\
            .apply(self._create_grid_row, axis=1)\
            .sum()
        self.grid_gdf = gpd.GeoDataFrame(r)
        
        # add metadata url
        self.grid_gdf['metadata_url'] = self.grid_gdf.apply(self._metadata_url, axis=1)
        
        print(f"{len(self.grid_gdf)} grid points created")
        return self.grid_gdf
        
    def graph2gdf(self, graph):
        '''convert osmnx graph to geodataframe'''
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
        source = "source=outdoor"
        url = "{}&{}&{}".format(base, latlng, source)
        return url