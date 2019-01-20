#!/usr/bin/env python

import math 
import os
import asyncio
import async_timeout
import ssl

import numpy as np
import pandas as pd
import aiohttp

import geopandas as gpd
from shapely.geometry import Point
from shapely.geometry import LineString


def graph2gdf(graph):
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
    

def generate_grids(streets, **kwargs):
    '''creates 1d grid along with street segments 

    Arguments:
        streets: GeoDataFrame
            geodataframe of street segments
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
    
    Returns:
        grid_gdf: GeoDataFrame 
            geodataframe for grid points (output)

    Example:
        $ grid_gdf = generate_grids(street_gdf, distance=10)
    '''
    r = streets\
        .apply(lambda x: _generate_grids_row(x, **kwargs), axis=1)\
        .sum()
    grid_gdf = gpd.GeoDataFrame(r)
    
    # add metadata url
    grid_gdf['metadata_url'] = grid_gdf.apply(_metadata_url, axis=1)
    print(f"{len(grid_gdf)} grid points created")
    return grid_gdf
            

def identify_gsv_locations(grid_gdf):
    ''' create observataion points which have gsv images'''
    responses = _retrieve_metadata(grid_gdf)
    res_df = pd.DataFrame.from_records(responses)
    res_df = res_df[res_df['status'] == 'OK']
    res_df['geometry']  = res_df.apply(
        lambda r: Point(r['location']['lng'], r['location']['lat']), 
        axis=1)
    res_df = res_df.drop_duplicates(subset="pano_id").reset_index()
    res_df = gpd.GeoDataFrame(res_df).drop(columns=['location', 'status'])
    print(f"{len(res_df)} observation points retrieved.")
    return res_df


def make_gsv_urls(gsv_points, **kwargs):
    ''' create image urls for each heading '''
    res = gsv_points.apply(
        lambda x: _make_gsv_urls_row(x, **kwargs), 
        axis=1).sum()
    urls = pd.DataFrame.from_records(res)
    print(f"Total {len(urls)} urls created.")
    return urls

 
def download_gsvs(gsv_df, save_dir='', key=''):
    ''' asynchrounously retrieve gsv images'''
    key = os.environ['GSV_API_KEY']
    
    async def download_coroutine(session, gsv):
        url = gsv['gsv_url'] + "&key=" + key
        filename = os.path.join(save_dir, gsv['gsv_name'])

        with async_timeout.timeout(10):
            async with session.get(url) as response:
                with open(filename, 'wb') as f_handle:
                    while True:
                        chunk = await response.content.read(1024)
                        if not chunk:
                            break
                        f_handle.write(chunk)
                return await response.release()

    async def fetch_all(gsvs, loop):
        async with aiohttp.ClientSession(loop=loop) as session:
            for gsv in gsvs:
                await download_coroutine(session, gsv)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(fetch_all(gsv_df.to_records(), loop))


def _make_gsv_urls_row(gsv_point, **kwargs):
    npics = kwargs.get('npics', 6)

    fov = 360.0 / npics
    headings = [ang * fov for ang in range(0, int(360 / fov))]
    records = list()
    for heading in headings:
        record = {
            'gsv_url': _image_url(gsv_point, heading, **kwargs),
            'gsv_name': _image_name(gsv_point, heading, **kwargs),
            'pano_id': gsv_point['pano_id']}
        records.append(record)
    return records


def _image_url(gsv_point, heading, **kwargs):
    ''' construct a url for retrieving gsv metadata 
    at obs point location'''

    npics = kwargs.get('npics', 6)
    size = kwargs.get('size', 400)
    pad = kwargs.get('pad', 0)

    lat = gsv_point.geometry.y
    lng = gsv_point.geometry.x
    base = "https://maps.googleapis.com/maps/api/streetview?pitch=-5"
    size = "size={}x{}".format(size, size)
    heading = "heading={}".format(heading)
    fov = "fov={}".format(360.0 / npics + 2 * pad)
    latlng = "location={},{}".format(lat, lng)
    source = "source=outdoor"
    url = "{}&{}&{}&{}&{}&{}".format(
        base, size, heading, fov, latlng, source)
    return url


def _image_name(gsv_point, heading, **kwargs):
    prefix = kwargs.get('prefix', 'image')
    return "{}_{}_{:d}.{}".format(
        prefix, 
        gsv_point['index'], 
        int(heading), 
        "jpg")


def _retrieve_metadata(grid_gdf):
    ''' asynchronous collecting gsv info nearby grid points'''
    urls = list(grid_gdf['metadata_url'])
    key = os.environ['GSV_API_KEY']

    async def fetch(session, url):
        url = "{}&key={}".format(url, key)
        async with session.get(url, ssl=ssl.SSLContext()) as response:
            return await response.json()

    async def fetch_all(urls, loop):
        async with aiohttp.ClientSession(loop=loop) as session:
            results = await asyncio.gather(
                *[fetch(session, url) for url in urls], 
                return_exceptions=True)
            return results

    loop = asyncio.get_event_loop()
    res = loop.run_until_complete(fetch_all(urls, loop))
    return res


def _generate_grids_row(segment, **kwargs):
    ''' for each street segment, add observation points at fixed distance 
    and add both of the ends if necessary'''

    distance = kwargs.get('distance', 10.0)
    normalized = kwargs.get('normalized', False)
    seg_end = kwargs.get('seg_end', True)
    end_gap_dist = kwargs.get('eng_gap_dist', 0.001)
    segment_id  = kwargs.get('segment_id', 'osmid')

    points = list()  # output

    # whether normalized or not, points are created in normalized manner
    length = segment.length
    if normalized:
        length = 1.0
    step = distance / length
    n_full_step = math.floor(1.0/step) # number of full step
    offset = 0.5 * (1 - step * n_full_step)

    points_added = 0
    current_dist = offset

    # add segment start point if seg_end
    if seg_end:
        points.append({
            'segment_id':segment[segment_id], 
            'point_id': points_added,
            'seg_end': 1,
            'geometry':segment.geometry.interpolate(0, normalized=True)
        })
        points_added += 1

    # add internal points
    while(current_dist < 1 - end_gap_dist):
        if current_dist > end_gap_dist:
            points.append({
                    'segment_id':segment[segment_id], 
                    'point_id': points_added,
                    'seg_end': 0,
                    'geometry':segment.geometry.interpolate(
                        current_dist, normalized=True)
            })
        current_dist += step
        points_added += 1

    # add segment end point if seg_end
    if seg_end:
        points.append({
            'segment_id':segment[segment_id], 
            'point_id': points_added,
            'seg_end': -1,
            'geometry':segment.geometry.interpolate(1, normalized=True)
        })
        points_added += 1

    return points


def _metadata_url(obs_point):
        ''' construct a url for retrieving gsv metadata 
        at obs point location'''
        lat = obs_point.geometry.y
        lng = obs_point.geometry.x
        base = "https://maps.googleapis.com/maps/api/streetview/metadata?"
        latlng = "location={},{}".format(lat, lng)
        source = "source=outdoor"
        url = "{}&{}&{}".format(base, latlng, source)
        return url