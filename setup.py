from setuptools import setup

setup(name='streetscape',
      version='0.2.3',
      description='help to collect panoramic street view in a city',
      url='http://github.com/yonghah/streetscape',
      download_url='http://github.com/yonghah/streetscape/tarball/0.2.3',
      author='Yongha Hwang',
      author_email='ahgnoy@gmail.com',
      license='MIT',
      packages=['streetscape'],
      install_requires=[
          'geopandas',
          'aiohttp'
      ],
      zip_safe=False)
