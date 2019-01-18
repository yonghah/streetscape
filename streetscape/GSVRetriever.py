import pandas as pd
import os
import asyncio
import aiohttp
import async_timeout
import ssl


class GSVRetriever:
    ''' retrive gsv images from identified locations'''
    
    def __init__(self, prefix='image'):
        self.key = None
        self.prefix = prefix
        self.npics = 4
        self.size = 400
        self.pad = 0
    
    def create_urls(self, gsv_points, npics=6, size=400, pad=0):
        ''' create image urls for each heading '''
        self.npics = npics
        self.size = size
        self.pad = pad
        res = gsv_points.apply(lambda x: self._create_urls_row(x), axis=1).sum()
        return pd.DataFrame.from_records(res)
    
    def _create_urls_row(self, gsv_point):
        fov = 360.0 / self.npics
        headings = [ang * fov for ang in range(0, int(360 / fov))]
        records = list()
        for heading in headings:
            record = {
                'gsv_url':self._image_url(gsv_point, heading),
                'gsv_name': self._image_name(gsv_point, heading),
                'pano_id': gsv_point['pano_id']}
            records.append(record)
        return records
    
    def _image_url(self, gsv_point, heading):
        ''' construct a url for retrieving gsv metadata 
        at obs point location'''
        lat = gsv_point.geometry.y
        lng = gsv_point.geometry.x
        base = "https://maps.googleapis.com/maps/api/streetview?pitch=-5"
        size = "size={}x{}".format(self.size, self.size)
        heading = "heading={}".format(heading)
        fov = "fov={}".format(360.0 / self.npics + 2 * self.pad)
        latlng = "location={},{}".format(lat, lng)
        source = "source=outdoor"
        url = "{}&{}&{}&{}&{}&{}".format(base, size, heading, fov, latlng, source)
        return url

    def _image_name(self, gsv_point, heading):
        return "{}_{}_{:d}.{}".format(
            self.prefix, 
            gsv_point['index'], 
            int(heading), 
            "jpg")
    
    def retrieve_images(self, gsv_df, save_dir='', key=''):
        ''' asynchrounously retrieve gsv images'''
        if key:
            self.key = key
        else:
            self.key = os.environ['GSV_API_KEY']
        async def download_coroutine(session, gsv):
            url = gsv['gsv_url'] + "&key=" + self.key
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