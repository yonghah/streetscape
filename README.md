# Streetscape

Streetscape helps to retrieve google street views in a city. 

### Set up

#### Install streetscape
Prerequistes: 
- aiohttp
- geopandas


```
pip install streetscape
```

#### Set environment variable GSV_API_KEY
linux and macosx
```
export GSV_API_KEY=YOUR_GOOGLE_STREET_VIEW_API_KEY
```
windows
```
set GSV_API_KEY=YOUR_GOOGLE_STREET_VIEW_API_KEY
```

### Use

Steps:
- get street lines (osmnx, tiger)
- create 1D grid points along with street lines 
- check whether gsv exists on each observation points and get panoID
- retrieve gsv images from each observation point

