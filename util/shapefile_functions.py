import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
import os

# Helper function to add shapefile data from a file path, sets the original coordinate system and then reprojects to WGS 84 for mapping
# Originally written by Cooper (Intern) and/or Mary Evans 
def add_shapefile_data(filepath):

    # Load shapefile data using geopandas
    shapefile = gpd.read_file(filepath)

    # Set the original coordinate system from .prj file
    original_crs = shapefile.crs

    if original_crs == None:
        original_crs = 'EPSG:26913'  # NAD 1983 / UTM zone 13N

    shapefile.set_crs(original_crs, inplace=True)
    # Reproject to WGS 84 (EPSG:4326), best for mapbox maps
    shapefile = shapefile.to_crs('EPSG:4326')

    # Set up the lat/lon columns by finding the centroid of each polygon
    shapefile['lat'] = shapefile.geometry.apply(lambda x: x.centroid.y)
    shapefile['lon'] = shapefile.geometry.apply(lambda x: x.centroid.x)
    return shapefile

# Helper function to add shapefile to map by setting up the lon/lat coordinates for each polygon
# Originally written by Cooper (Intern) and/or Mary Evans 
def add_shapefile_to_map(gdf, map, name, color, fill_input):

    # Initialize lists to store the flattened longitude and latitude coordinates
    lon_flat = []
    lat_flat = []

    # Iterate over each row in the GeoDataFrame
    for _, row in gdf.iterrows():
        geom = row.geometry
        if geom.geom_type == 'Polygon':
            # If the geometry is a Polygon, extract its exterior coordinates
            lon, lat = list(geom.exterior.xy[0]), list(geom.exterior.xy[1])
            # Add the coordinates to the lists, followed by None to break the line
            lon_flat.extend(lon + [None])  # Add None to break the line
            lat_flat.extend(lat + [None])  # Add None to break the line
        elif geom.geom_type == 'MultiPolygon':
            # If the geometry is a MultiPolygon, iterate over each Polygon in the MultiPolygon
            for polygon in geom.geoms:
                lon, lat = list(polygon.exterior.xy[0]), list(polygon.exterior.xy[1])
                # Add the coordinates to the lists, followed by None to break the line
                lon_flat.extend(lon + [None])  # Add None to break the line
                lat_flat.extend(lat + [None])  # Add None to break the line

    # Create a single trace with broken lines to represent the polygons
    line = go.Scattermapbox(
        lon=lon_flat,
        lat=lat_flat,
        mode='lines',
        line=dict(width=2, color=color),
        name=name,
        fill = fill_input
    )

    # Add the trace to the mapbox figure
    map.add_trace(line)

# Helper function to add directory of shapefiles to map
def add_shapefiles(dir, map, color, fill=None):
    directory = os.fsdecode(dir)
        
    for file in os.listdir(directory):
        filename = os.fsdecode(file)
        if filename.endswith(".shp"): 
            shapefile = add_shapefile_data(os.path.join(directory, filename))
            add_shapefile_to_map(shapefile, map, filename, color, fill)
            continue
        else:
            continue