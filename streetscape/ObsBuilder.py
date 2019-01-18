import math 
import pandas as pd
import os
import asyncio
import aiohttp
import ssl
from shapely.geometry import Point
import geopandas as gpd


class ObsBuilder:
    ''' identify the locations of gsv views from grid point gdf'''
    def __init__(self):
        self.grid = None
        self.key = None
        
    def create(self, grid_gdf, key=''):
        ''' create observataion points which have gsv images'''
        self.grid = grid_gdf
        if key:
            self.key = key
        else:
            self.key = os.environ['GSV_API_KEY']
        responses = self._retrieve_metadata(self.grid)
        res_df = pd.DataFrame.from_records(responses)
        res_df = res_df[res_df['status'] == 'OK']
        res_df['geometry']  = res_df.apply(lambda r: Point(r['location']['lng'], r['location']['lat']), axis=1)
        res_df = res_df.drop_duplicates(subset="pano_id").reset_index()
        res_df = gpd.GeoDataFrame(res_df).drop(columns=['location', 'status'])
        print(f"{len(res_df)} observation points retrieved.")
        return res_df
    
    def _retrieve_metadata(self, grid_gdf):
        ''' asynchronous collecting gsv info nearby grid points'''
        urls = list(grid_gdf['metadata_url'])

        async def fetch(session, url):
            url = url + "&key=" + self.key
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


