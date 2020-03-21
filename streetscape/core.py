#!/usr/bin/env python

import math 
import os
import asyncio
import async_timeout
import ssl
import warnings

import numpy as np
import pandas as pd
import aiohttp

import geopandas as gpd
from shapely.geometry import Point
from shapely.geometry import LineString



def graph2gdf(graph):
    '''convert osmnx graph to geodataframe
    Args:
        graph (NetworkX.graph): street network from osmnx
    Returns:
        converted (GeoDataFrame): street geodataframe
    '''
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

    Arg:
        streets (GeoDataFrame): geodataframe of street segments
        **distance (float): distance between grid 
        **normalized (bool): If True, distance is relative value; 
            otherwise absolute.
            When normalized is True, distance should be [0,1]
        **seg_end (bool): if true, force to include both ends of a segment
        **end_gap_dist (float): gap threshold between grid point and seg_end
        **segment_id (string): name of column contains street segment id
    
    Returns:
        grid_gdf (GeoDataFrame): geodataframe for grid points (output)

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
            

def identify_gsv_locations(grid_gdf, max_conn=50, max_sem=10, timeout=0):
    ''' create observataion points which have gsv images
    Arguments:
        grid_gdf (GeoDataFrame): GeoDataFrame for grid points
        max_conn (int): number of maximum concurrent connections
        timeout (int): seconds until timeout. 0 unlimted.
    Returns:
        res_df (GeoDataFrame): point dataset
    To do:
        logging;
        separate this function into two so that a user can verify
        the retrieved result;
        timeout argument;
    '''
    responses = retrieve_metadata(grid_gdf, max_conn, max_sem, timeout)
    res_df = pd.DataFrame.from_records(responses)
    res_df = res_df[res_df['status'] == 'OK']
    res_df['geometry']  = res_df.apply(
        lambda r: Point(r['location']['lng'], r['location']['lat']), 
        axis=1)
    res_df = res_df.drop_duplicates(subset="pano_id").reset_index()
    res_df = gpd.GeoDataFrame(res_df).drop(columns=['location'])
    print(f"{len(res_df)} observation points retrieved.")
    return res_df


def make_gsv_urls(gsv_points, **kwargs):
    ''' create image urls for each heading 
    Args:
        gsv_points (GeoDataFrame): location of gsv shots
        **npics (int): number of pictures at each location (default 6)
        **size (int): size of image (image is square)
        **pad (int): overlapped angle betweeen adjacent image
        **prefix (str): default prefix for image name (default 'image')
    Returns:
        urls (DataFrame): dataframe for google map API url
    '''
    res = gsv_points.apply(
        lambda x: _make_gsv_urls_row(x, **kwargs), 
        axis=1).sum()
    urls = pd.DataFrame.from_records(res)
    print(f"Total {len(urls)} urls created.")
    return urls

 
def download_gsvs(gsv_df, save_dir='', max_conn=50, max_sem=10, timeout=0):
    ''' asynchrounously retrieve gsv images
    Args:
        gsv_df (DataFrame): dataframe for download urls for each image
        save_dir (str): directory for downloaded images
        max_conn (int): number of concurrent connections
        max_sem (int): maximum number of semaphores
        timeout (int): maximum total running time (0 unlimited)
    '''
    key = os.environ['GSV_API_KEY']
    
    async def fetch(session, gsv, sem):
        url = gsv['gsv_url'] + "&key=" + key
        filename = os.path.join(save_dir, gsv['gsv_name'])

        async with session.get(url) as response:
            async with sem:
                with open(filename, 'wb') as f_handle:
                    while True:
                        chunk = await response.content.read(1024)
                        if not chunk:
                            break
                        f_handle.write(chunk)
                return await response.release()

    async def fetch_all(gsvs, loop):
        conn = aiohttp.TCPConnector(limit=max_conn)
        timeout_c = aiohttp.ClientTimeout(total=timeout)  
        sem = asyncio.Semaphore(max_sem)

        async with aiohttp.ClientSession(
            loop=loop, connector=conn, timeout=timeout_c) as session:
            
            tasks = list()
            for gsv in gsvs:
                task = asyncio.ensure_future(fetch(session, gsv, sem))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
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


def retrieve_metadata(grid_gdf, max_conn, max_sem, timeout):
    ''' asynchronous collecting gsv info nearby grid points'''
    urls = list(grid_gdf['metadata_url'])
    key = os.environ['GSV_API_KEY']

    async def fetch(session, url, sem):
        url = "{}&key={}".format(url, key)
        async with sem:
            async with session.get(url, ssl=ssl.SSLContext()) as response:
                return await response.json()

    async def fetch_all(urls, loop):
        conn = aiohttp.TCPConnector(limit=max_conn)
        timeout_c = aiohttp.ClientTimeout(total=timeout)  # unlimited
        sem = asyncio.Semaphore(max_sem)

        async with aiohttp.ClientSession(
            loop=loop, connector=conn, timeout=timeout_c) as session:

            tasks = list()
            for url in urls:
                task = asyncio.ensure_future(fetch(session, url, sem))
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            return results

    loop = asyncio.get_event_loop()
    responses = loop.run_until_complete(fetch_all(urls, loop))
    records = _filter_errors(responses)
    
    return records


def _filter_errors(responses):
    records = []
    errors = []
    for res in responses:
        if type(res) == dict:
            records.append(res)
        else:
            errors.append(res)
    if len(errors) > 0:
        print(f'{len(errors)} connection errors')
    return records


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