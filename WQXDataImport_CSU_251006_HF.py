# WQXDataImport_CSU.py
# This script is used to import water quality data from the Environmental Protection Agency (EPA) Water Quality Exchange (WQX) 3.0 Beta.
# The script will use a designated URL to access the WQX.
# Two separate data sets will be downloaded, one for historical water quality sample data and one for sample location data.
# The two separate data sets will be merged into a single dataset, then pre-processed in preparation for import into the CSU Water Quality Analytical Tool.
# This process is based on an ArcGIS Model Builder model developed by SGM Inc. (Eidan Willis, Jonathan Holt, Haley Farwell).

import os
import pathlib
import re
import requests
import zipfile

import dash
from dash import Dash, html, dcc, callback, Output, Input, dash_table
import pandas as pd
import geopandas as gpd
from dash.dependencies import Input, Output, State
from shapefile_functions import add_shapefile_data
import json
import plotly.express as px
from datetime import datetime
import numpy as np
import plotly.graph_objects as go
from difflib import get_close_matches

def WQXDataImport():

    key_analytes = [
        "Conductivity",
        "Specific conductance",  # USGS variant
        "Escherichia coli", 
        "Flow",
        "Stream flow, instantaneous",  # USGS variant
        "Flow rate, instantaneous",
        "Stream flow",
        "Temperature",
        "Temperature, water",  # USGS variant
        "Hardness, Ca, Mg",
        "Hardness as CaCO3",
        "Arsenic", 
        "Iron", 
        "pH", 
        "Selenium", 
        "Total Suspended Solids",
        "Total suspended solids",
        "Total dissolved solids",
        "Total Dissolved Solids",
        "Turbidity", 
        "Aluminum", 
        "Manganese", 
        "Nitrogen",
        "Total Nitrogen",
        "Nitrate",
        "Nitrite",
        "Nitrate + Nitrite",
        "Nitrite + Nitrate",
        "Ammonia-nitrogen",
        "Inorganic nitrogen (nitrate and nitrite)",
        "Organic nitrogen",
        "Total Kjeldahl nitrogen",
        "Ammonia",
        "Ammonia and ammonium",  # Exact case match for USGS data
        "Phosphorus",
        "Total Phosphorus",
        "Ammonium",
        "Orthophosphate",
        "Phosphate-phosphorus",
        "Uranium",
        "Sulfate",
        "Cadmium", 
        "Lead", 
        "Calcium", 
        "Cobalt", 
        "Copper", 
        "Zinc", 
        "Magnesium", 
        "Potassium", 
        "Silver", 
        "Salinity",
        "Sodium", 
        "Dissolved oxygen",
        "Dissolved Oxygen (DO)",
        "Dissolved oxygen saturation",  # Add this - appears in data
        "Oxygen"
    ]

    # List of sites to select
    select_sites = ["ARKANSAS RIVER NEAR PORTLAND, CO.",
                    "ARKANSAS RIVER AT PORTLAND, CO.",
                    "ARKANSAS R. @ PORTLAND @ HWY 120",
                    "Arkansas - Portland USGS",
                    "BESSEMER DITCH AT ST. CHARLES WD NEAR PUEBLO CO",
                    "Rusler Soil Health - Bessemer",
                    "ARKANSAS RIVER ABOVE PUEBLO RESERVOIR",
                    #"GOLF COURSE WASH ABV PUEBLO RESERVOIR",
                    "PUEBLO RESERVOIR",
                    "PUEBLO RESERVOIR [BOTTOM]",
                    "PUEBLO RESERVOIR SITE 1 BOTTOM",
                    "PUEBLO RESERVOIR SITE 1 TOP",
                    "PUEBLO RESERVOIR SITE 2 TOP",
                    "PUEBLO RESERVOIR SITE 2B",
                    "PUEBLO RESERVOIR SITE 3 TOP",
                    "PUEBLO RESERVOIR SITE 3B",
                    "PUEBLO RESERVOIR SITE 4B",
                    "PUEBLO RESERVOIR SITE 5C",
                    "PUEBLO RESERVOIR SITE 6C",
                    "PUEBLO RESERVOIR SITE 7B",
                    "ARKANSAS RIVER ABOVE PUEBLO, CO.",
                    "Pueblo Reservoir, Pueblo County, CO, USA",
                    "ARKANSAS RIVER BELOW MOFFAT STREET AT PUEBLO, CO.",
                    "CITYPUEBLO_WWD, station:CITYPUEBLO_WWD_UPSTRM_24RWMOFFAT",
                    "Arkansas - By Moffat Street",
                    "ARKANSAS R ABV RUNYON LAKE @ MOFFAT ST",
                    "FOUNTAIN CREEK AT PUEBLO, CO.",
                    "FOUNTAIN CREEK AT MOUTH NEAR PUEBLO",
                    "SALT CREEK AT HWY 50",
                    "CATLIN CANAL AT MILE 0.1, NEAR FOWLER, CO.",
                    "ST. CHARLES RIVER AT VINELAND, CO.",
                    "ST. CHARLES RIVER AT MOUTH NEAR PUEBLO, CO.",
                    "ARKSANSAS R. AT ST CHARLES MESA DIVER. AT PUEBLO,CO",
                    "ST. CHARLES RIVER AT 27TH LANE NR PUEBLO, CO",
                    "ARKANSAS RIVER NEAR AVONDALE",
                    "ARKANSAS R AT AVONDALE, CO.",
                    #"ARKSANSAS RIVER AT HWY 209 NEAR AVONDALE",
                    "HUERFANO RIVER NEAR BOONE, CO.",
                    "ARKANSAS RIVER NEAR ROCKY FORD, CO.",
                    "ARKANSAS RIVER BL ROCKY FORD HIGHLINE HEADGATE",
                    "ARKANSAS RIVER AT HWY 266 NEAR ROCKY FORD CO.",
                    "ARKANSAS RIVER AT HWY 71 NEAR ROCKY FORD, CO.",
                    "ROCKY FORD CANAL AT MILE 1.2, NR MANZANOLA, CO.",
                    "Amity Canal @ Santa Fe Trl",
                    "FORT LYON STORAGE CA AT MI 1.7 NR ROCKY FORD CO.",
                    "FORT LYON CANAL NEAR LAS ANIMAS, CO",
                    "FORT LYON STORAGE CANAL NEAR CHERAW, CO",
                    "FORT LYON CANAL NEAR BIG BEND, CO",
                    "FORT LYON CANAL NEAR CASA, CO",
                    "FORT LYON CANAL NEAR LA JUNTA, CO",
                    "FORT LYON CANAL NEAR LAS ANIMAS, CO",
                    #"Gageby Cr - S of Ft Lyon Canal",
                    "ARKANSAS RIVER BL ROCKY FORD HIGHLINE HEADGATE",
                    "ARKANSAS RIVER NEAR NEPESTA, CO.",
                    "ARKANSAS RIVER AT NEPESTA, CO.",
                    "Arkansas - Nepesta",
                    "ARKANSAS R. NEAR NEPESTA @ HWY 50 RD 613",
                    "APISHAPA RIVER NEAR FOWLER, CO.",
                    "APISHAPA RIVER AT HIGHWAY 50 NEAR FOWLER, COLO.",
                    "ARKANSAS RIVER AT CATLIN DAM, NEAR FOWLER, CO.",
                    "HOLBROOK CANAL AT MILE 3.4, NEAR ROCKY FORD, CO.",
                    "HOLBROOK LAKE",
                    "HOLBROOK RESERVOIR CANAL OUTLET",
                    "LAKE MEREDITH OUTLET AT HWY 71 NR ORDWAY, CO",    
                    "LAKE MEREDITH - TOP",
                    "LAKE MEREDITH CANAL INLET",
                    "LAKE MEREDITH OUTLET AT HWY 71 NR ORDWAAY, CO",
                    "LAKE MEREDITH SITE 1 LOWER",
                    "LAKE MEREDITH SITE 1 TOP",
                    "LAKE MEREDITH SITE 2 LOWER",
                    "LAKE MEREDITH SITE 2 UPPER",
                    "MEREDITH RESERVOIR",  
                    "TIMPAS CREEK AT MOUTH NEAR SWINK, CO.",
                    "TIMPAS CREEK AT HIGHWAY 50 AT SWINK, CO.",
                    "CROOKED ARROYO NEAR SWINK, CO.",
                    "CROOKED ARROYO NEAR LA JUNTA, CO.",
                    "CROOKED ARROYO AT HIGHWAY 50 NEAR LA JUNTA, COLO.",
                    "ARKANSAS RIVER AT LA JUNTA, CO",
                    "LAS ANIMAS CONSOL DI AT MI 1.3 NR LAS ANIMAS CO.",
                    "HORSE CREEK AT MOUTH NEAR LAS ANIMAS, COLO.",
                    "HORSE CREEK NEAR LAS ANIMAS, CO",
                    "HORSE CREEK NEAR CHERAW, CO",
                    "ADOBE CREEK AT HWY 194 NR LAS ANIMAS, CO",
                    "ARKANSAS RIVER AT LAS ANIMAS, CO.",
                    "PURGATOIRE RIVER NEAR LAS ANIMAS, CO",
                    "PURGATOIRE RIVER AT NINEMILE DAM, NR HIGBEE, CO.",
                    "SPG W OF PURGATOIRE R AT HWY 101 NR LAS ANIMAS, CO",
                    "JOHN MARTIN RESERVOIR",
                    "Arkansas - John Martin Res Outlet",
                    "JOHN MARTIN RESERVOIR SITE 1 TOP",
                    "JOHN MARTIN RESERVOIR SITE 1 BOTTOM",
                    "JOHN MARTIN RESERVOIR SITE 2 TOP",
                    "JOHN MARTIN RESERVOIR SITE 2 BOTTOM",
                    "ARKANSAS RIVER BELOW JOHN MARTIN RESERVOIR, CO.",
                    "John Martin Reservoir",
                    "John Martin Reservoir Center",
                    "Arkansas River, John Martin Reservoir downstream",
                    "John Martin Reservoir NR Dam Upper",
                    "John Martin Reservoir North shoreline",
                    "John Martin Reservoir, Bent County, CO, USA",
                    "ARKANSAS RIVER AT LAMAR, CO",
                    "Lamar Ditch - Lamar Greenbelt",
                    "Lamar Canal near n13thst Lamar",
                    "ARKANSAS RIVER NEAR GRANADA, CO.",
                    "ARKANSAS @ GRANADA GAGE",
                    "ARKANSAS R. @ HOLLY @ HWY89",
                    "BUFFALO CANAL RETURN FLOW DITCH"]

    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    print("WD identified as: " + script_dir)
    
    # URLs for beta format (direct CSV download, no zip)
    beta_stations_URL = "https://www.waterqualitydata.us/wqx3/Station/search?countrycode=US&statecode=US%3A08&bBox=-105.027483%2C37.706810%2C-102.076646%2C39.237325&sampleMedia=Water&sampleMedia=water&sampleMedia=Other&startDateLo=10-01-1990&mimeType=csv&providers=NWIS&providers=STORET"
    beta_results_URL = "https://www.waterqualitydata.us/wqx3/Result/search?countrycode=US&statecode=US%3A08&bBox=-105.027483%2C37.706810%2C-102.076646%2C39.237325&sampleMedia=Water&sampleMedia=water&sampleMedia=Other&startDateLo=10-01-1990&mimeType=csv&dataProfile=fullPhysChem&providers=NWIS&providers=STORET"
        
    today_str = datetime.today().strftime("%Y%m%d") 
    outputfile_name = f"CSU_EPAWQData_Beta_19901001-{today_str}_parsed.csv"

    # Download BETA format files directly as CSV
    print("Downloading beta stations data...")
    beta_stations_path = os.path.join(script_dir, "beta_station.csv")
    
    response = requests.get(beta_stations_URL, stream=True)
    with open(beta_stations_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    print("✓ Stations downloaded")
    
    print("Downloading beta results data...")
    beta_results_path = os.path.join(script_dir, "beta_result.csv")
    
    response = requests.get(beta_results_URL, stream=True)
    with open(beta_results_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    print("✓ Results downloaded")

    # Read CSVs
    print("Reading data files...")
    beta_stations_df = pd.read_csv(beta_stations_path, low_memory=False)
    beta_results_df = pd.read_csv(beta_results_path, low_memory=False)

    # Create lookup table for coordinates from stations
    lookup = beta_stations_df.drop_duplicates("Location_Name").set_index("Location_Name")[
        ["Location_LatitudeStandardized", "Location_LongitudeStandardized"]
    ]

    # Fill coordinates in results where null using lookup table
    beta_results_df["Location_LatitudeStandardized"] = beta_results_df["Location_LatitudeStandardized"].fillna(
        beta_results_df["Location_Name"].map(lookup["Location_LatitudeStandardized"])
    )

    beta_results_df["Location_LongitudeStandardized"] = beta_results_df["Location_LongitudeStandardized"].fillna(
        beta_results_df["Location_Name"].map(lookup["Location_LongitudeStandardized"])
    )

    # Filter by selected sites
    print("Filtering by selected sites...")

    def find_matching_sites(df, target_sites, threshold=0.85):
        """
        Find sites that closely match the target list using fuzzy matching.
        
        Parameters:
        - df: DataFrame with 'Location_Name' column
        - target_sites: List of site names to match
        - threshold: Similarity threshold (0-1), default 0.85
        """
        unique_locations = df['Location_Name'].unique()
        matched_sites = set()
        
        # Normalize for better matching
        def normalize(s):
            if pd.isna(s):
                return ""
            # Convert to lowercase, remove extra spaces, remove trailing periods
            return ' '.join(str(s).lower().strip().rstrip('.').split())
        
        normalized_targets = {normalize(site): site for site in target_sites}
        normalized_locations = {normalize(loc): loc for loc in unique_locations}
        
        # First pass: exact matches after normalization
        for norm_loc, original_loc in normalized_locations.items():
            if norm_loc in normalized_targets:
                matched_sites.add(original_loc)
                print(f"  ✓ Exact match: {original_loc}")
        
        # Second pass: fuzzy matches for unmatched targets
        unmatched_targets = set(normalized_targets.keys()) - set(normalize(site) for site in matched_sites)
        
        for norm_target in unmatched_targets:
            matches = get_close_matches(norm_target, normalized_locations.keys(), n=1, cutoff=threshold)
            if matches:
                original_loc = normalized_locations[matches[0]]
                matched_sites.add(original_loc)
                print(f"  ≈ Fuzzy match: {original_loc} (for '{normalized_targets[norm_target]}')")
        
        return list(matched_sites)

    # Get matching sites
    matching_sites = find_matching_sites(beta_results_df, select_sites, threshold=0.85)
    print(f"\nFound {len(matching_sites)} matching sites out of {len(select_sites)} requested")

    # Filter the dataframe
    filtered_df = beta_results_df[beta_results_df["Location_Name"].isin(matching_sites)].copy()
    print(f"Found {len(filtered_df)} records from selected sites")

    # Process result values
    filtered_df["Result_Measure"] = pd.to_numeric(filtered_df["Result_Measure"], errors='coerce')
    filtered_df["FullCharacteristicName"] = filtered_df["Result_SampleFraction"].astype(str) + " " + filtered_df["Result_Characteristic"].astype(str)
    
    # Fix spelling errors
    filtered_df["Result_SampleFraction"] = filtered_df["Result_SampleFraction"].replace("Total Recovrble", "Total Recoverable")
    filtered_df["Result_Characteristic"] = filtered_df["Result_Characteristic"].replace("Total suspended solids", "Total Suspended Solids")

    # Clean up fraction assignments for characteristics that shouldn't have fractions
    no_fraction_characteristics = [
        "pH", 
        "Temperature, water", 
        "Hardness, Ca, Mg", 
        "Turbidity",
        "Conductivity",
        "Flow",
        "Escherichia coli",
        "Dissolved oxygen",
        "Salinity"
    ]

    for characteristic in no_fraction_characteristics:
        mask = filtered_df["Result_Characteristic"] == characteristic
        filtered_df.loc[mask, "Result_SampleFraction"] = ""

    # Update FullCharacteristicName after cleaning fractions
    filtered_df["FullCharacteristicName"] = filtered_df["Result_SampleFraction"].astype(str) + " " + filtered_df["Result_Characteristic"].astype(str)
    filtered_df["FullCharacteristicName"] = filtered_df["FullCharacteristicName"].str.strip()
    filtered_df["FullCharacteristicName"] = filtered_df["FullCharacteristicName"].str.replace("nan ", "")

    # Drop NAs
    filtered_df = filtered_df.dropna(subset=["Location_LatitudeStandardized", "Location_LongitudeStandardized"])
    filtered_df = filtered_df.reset_index(drop=True)

    # Add Acute and Chronic columns
    filtered_df["Acute"] = ""
    filtered_df["Chronic"] = ""

    # Define the criteria mapping
    criteria_mapping = {
        ("Selenium", "Dissolved"): {"Acute": 18.5, "Chronic": 4.6},
        ("Iron", "Total"): {"Acute": "", "Chronic": 1000},
        ("Arsenic", "Dissolved"): {"Acute": 340, "Chronic": ""},
        ("Arsenic", "Total"): {"Acute": "", "Chronic": 7.6}
    }

    # Apply the criteria mapping
    for (characteristic, fraction), values in criteria_mapping.items():
        mask = (filtered_df["Result_Characteristic"] == characteristic) & (filtered_df["Result_SampleFraction"] == fraction)
        if values["Acute"] != "":
            filtered_df.loc[mask, "Acute"] = values["Acute"]
        if values["Chronic"] != "":
            filtered_df.loc[mask, "Chronic"] = values["Chronic"]

    # Filter by key analytes - using case-insensitive matching
    print("Filtering by key analytes...")

    # Normalize the key analytes list (lowercase, strip spaces)
    normalized_key_analytes = [analyte.lower().strip() for analyte in key_analytes]

    # Create a normalized column for comparison
    filtered_df['_temp_normalized'] = filtered_df['Result_Characteristic'].str.lower().str.strip()

    # Filter - keep rows where the normalized characteristic contains any key analyte
    def matches_key_analyte(char_name):
        if pd.isna(char_name):
            return False
        for key_analyte in normalized_key_analytes:
            if key_analyte in char_name:
                return True
        return False

    filtered_df = filtered_df[filtered_df['_temp_normalized'].apply(matches_key_analyte)].copy()

    # Drop the temporary column
    filtered_df = filtered_df.drop(columns=['_temp_normalized'])

    print(f"After filtering by key analytes: {len(filtered_df)} records")

    # Fix naming of flow
    filtered_df['Result_Characteristic'] = filtered_df['Result_Characteristic'].replace({
        "Stream flow, instantaneous": "Flow",
        "Flow rate, instantaneous": "Flow",
        "Stream flow": "Flow"
    })

    # Sort alphabetically by Result_Characteristic column
    filtered_df = filtered_df.sort_values(by='Result_Characteristic', key=lambda x: x.str.lower())

    # Save to CSV
    print(f"Saving to {outputfile_name}...")
    filtered_df.to_csv(outputfile_name, index=False)
    
    print(f"✓ Complete! Processed {len(filtered_df)} records.")
    print(f"✓ Output file: {outputfile_name}")
    
    return outputfile_name

if __name__ == "__main__":
    WQXDataImport()