# streetscape
collect panoramic street views in a city

### Set up

#### 1. Clone repository
```
git clone git@github.com:yonghah/streetscape.git
cd streetscape
```

#### 2. Install package
```
pip install .
```

#### 3. Set GSV_API_KEY
```
export GSV_API_KEY=YOUR_GOOGLE_STREET_VIEW_API_KEY
```

### Use
```
import streetscape as ss
# get all street midpoints in a city 
obs = ss.create_observation_points('Haywards Heath, UK')
# save 4 streeet views in each observation points 
ss.get_street_views_from_df(obs, "output_dir", pic_per_obs=4)
```
