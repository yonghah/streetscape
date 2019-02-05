# Streetscape

Streetscape helps to retrieve google street views in a city. 

![image_all](https://user-images.githubusercontent.com/3218468/35771925-e17728e8-0902-11e8-9a3a-3eeadb302764.png)

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

See the notebooke in the sample directory:
https://github.com/yonghah/streetscape/blob/master/sample/example.ipynb
