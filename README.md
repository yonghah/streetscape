# streetscape

Streetscape helps to sample google street views in a city. You can get Google street views in a city by place name, bounding box, center and radius, and so on. 

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
```
4218 sampled locations in Haywards Heath, UK.

![image](https://user-images.githubusercontent.com/3218468/30554144-84fdc53e-9c71-11e7-8ef0-f490f2792206.png)

```python
# save 4 streeet views from each observation point 
ss.get_street_views_from_df(obs, "output_dir", pic_per_obs=4)
```
