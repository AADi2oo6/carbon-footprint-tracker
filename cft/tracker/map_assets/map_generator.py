import geopandas as gpd
import pandas as pd
import folium
import os

# Get the absolute path to the directory this script is in
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SHAPEFILE_PATH = os.path.join(BASE_DIR, "Indian_States.shp")

def generate_india_heatmap_from_profiles(profiles):
    """
    Generates an interactive Folium heatmap of India by extracting state names
    from the Profile model's 'location' field (e.g., "City, State").

    Args:
        profiles (QuerySet): A Django QuerySet of the Profile model.

    Returns:
        str: A string containing the HTML representation of the Folium map,
             or an error message string if an issue occurs.
    """
    if not os.path.exists(SHAPEFILE_PATH):
        return "<p style='color:red; text-align:center;'>Error: Shapefile not found.</p>"

    try:
        # 1. Load the Geospatial Data
        india_gdf = gpd.read_file(SHAPEFILE_PATH).to_crs(epsg=4326)

        # 2. Process User Profiles to Get State Counts
        state_list = []
        for profile in profiles:
            if profile.location and ',' in profile.location:
                try:
                    # Split "City, State" and take the state part.
                    # .strip() removes any accidental leading/trailing whitespace.
                    state = profile.location.split(',')[1].strip()
                    state_list.append(state)
                except IndexError:
                    # This will skip any locations that don't fit the format.
                    pass
        
        if not state_list:
            # Handle case with no users or no valid locations
            user_df = pd.DataFrame(columns=['state', 'user_count'])
        else:
            # Create a DataFrame and count users per state
            user_df = pd.DataFrame(state_list, columns=['state'])
            user_df = user_df.groupby('state').size().reset_index(name='user_count')

        # 3. Merge Geospatial Data with User Data
        merged_gdf = india_gdf.merge(user_df, left_on='st_nm', right_on='state', how='left')
        merged_gdf['user_count'] = merged_gdf['user_count'].fillna(0).astype(int)

        # 4. Create the Interactive Map with Folium
        india_map = folium.Map(location=[22.5937, 78.9629], zoom_start=5, tiles="CartoDB positron")

        choropleth = folium.Choropleth(
            geo_data=merged_gdf,
            data=merged_gdf,
            columns=['st_nm', 'user_count'],
            key_on='feature.properties.st_nm',
            fill_color='Greens',
            fill_opacity=0.8,
            line_opacity=0.3,
            legend_name='Number of Users',
            highlight=True,
        ).add_to(india_map)
        
        # 5. Add Tooltips
        folium.features.GeoJsonTooltip(
            fields=['st_nm', 'user_count'],
            aliases=['State:', 'Users:'],
            style=("background-color: white; color: #333333; font-family: arial; font-size: 12px; padding: 10px;")
        ).add_to(choropleth.geojson)

        # 6. Return the Map as an HTML String
        return india_map._repr_html_()

    except Exception as e:
        return f"<p style='color:red; text-align:center;'>An error occurred: {e}</p>"

