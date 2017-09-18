# streetscape
collect panoramic street views in a city

### Set up

#### 1. Install osmnx
```
conda install -c conda-forge osmnx
```
Or 
```
pip install osmnx
```
See here for details:
https://github.com/gboeing/osmnx


#### 2. Install streetscape
```
pip install streetscape
```

#### 3. Set GSV_API_KEY
linux and macosx
```
export GSV_API_KEY=YOUR_GOOGLE_STREET_VIEW_API_KEY
```
windows
```
set GSV_API_KEY=YOUR_GOOGLE_STREET_VIEW_API_KEY
```

### Use
```python
import streetscape as ss
# get all street midpoints in a city 
obs = ss.create_observation_points('Haywards Heath, UK')
# save 4 streeet views in each observation points 
ss.get_street_views_from_df(obs, "output_dir", pic_per_obs=4)
```
