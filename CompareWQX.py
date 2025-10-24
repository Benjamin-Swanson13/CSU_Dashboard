
#Compare old EPA WQX CSV results to CSU beta WQX CSV results
#to see if lat/long coordinates and Location Identifer match for same locations

import pandas as pd
import numpy as np
import os

def compare_wqx_csvs(tolerance=0.0001, output_file="matched_locations.csv"):
    """
    Compare lat/long coordinates between CSU beta and old WQX results.
    
    Parameters:
    -----------
    tolerance : float
        Maximum distance in degrees to consider a match (default 0.0001 ≈ 11 meters)
    output_file : str
        Name of output CSV file
    """
    
    # Get script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # File paths
    beta_path = os.path.join(script_dir, "CSU_Result_beta_20251006_HF.csv")
    old_path = os.path.join(script_dir, "resultphyschem_WQX_old.csv")
    
    # Read both CSVs
    print("Reading CSV files...")
    beta_df = pd.read_csv(beta_path)
    old_df = pd.read_csv(old_path)
    
    # Column names
    beta_lat = "Location_LatitudeStandardized"
    beta_long = "Location_LongitudeStandardized"
    beta_name = "Location_Name"
    beta_id = "Location_Identifier"
    
    old_lat = "ActivityLocation/LatitudeMeasure"
    old_long = "ActivityLocation/LongitudeMeasure"
    old_name = "MonitoringLocationName"
    old_id = "MonitoringLocationIdentifier"
    
    # Drop rows with missing coordinates
    beta_df = beta_df.dropna(subset=[beta_lat, beta_long])
    old_df = old_df.dropna(subset=[old_lat, old_long])
    
    # Convert to numeric
    beta_df[beta_lat] = pd.to_numeric(beta_df[beta_lat], errors='coerce')
    beta_df[beta_long] = pd.to_numeric(beta_df[beta_long], errors='coerce')
    old_df[old_lat] = pd.to_numeric(old_df[old_lat], errors='coerce')
    old_df[old_long] = pd.to_numeric(old_df[old_long], errors='coerce')
    
    # Drop any rows that couldn't be converted
    beta_df = beta_df.dropna(subset=[beta_lat, beta_long])
    old_df = old_df.dropna(subset=[old_lat, old_long])
    
    # Get unique locations from each dataset
    beta_locations = beta_df[[beta_name, beta_id, beta_lat, beta_long]].drop_duplicates()
    old_locations = old_df[[old_name, old_id, old_lat, old_long]].drop_duplicates()
    
    print(f"Beta CSV: {len(beta_locations)} unique locations with valid coordinates")
    print(f"Old CSV: {len(old_locations)} unique locations with valid coordinates")
    
    matches = []
    
    # Compare each location in beta to all locations in old
    print("\nComparing locations...")
    for idx1, row1 in beta_locations.iterrows():
        lat1 = row1[beta_lat]
        lon1 = row1[beta_long]
        name1 = row1[beta_name]
        id1 = row1[beta_id]
        
        for idx2, row2 in old_locations.iterrows():
            lat2 = row2[old_lat]
            lon2 = row2[old_long]
            name2 = row2[old_name]
            id2 = row2[old_id]
            
            # Calculate distance (simple Euclidean distance in degrees)
            distance = np.sqrt((lat1 - lat2)**2 + (lon1 - lon2)**2)
            
            if distance <= tolerance:
                matches.append({
                    'Beta_Location_Name': name1,
                    'Beta_Location_Identifier': id1,
                    'Beta_Lat': lat1,
                    'Beta_Long': lon1,
                    'Old_MonitoringLocationName': name2,
                    'Old_MonitoringLocationIdentifier': id2,
                    'Old_Lat': lat2,
                    'Old_Long': lon2,
                    'Distance_Degrees': distance,
                    'Distance_Meters': distance * 111000,  # Approximate conversion
                    'Names_Match': str(name1).strip().upper() == str(name2).strip().upper(),
                    'IDs_Match': str(id1).strip().upper() == str(id2).strip().upper()
                })
    
    # Create results DataFrame
    results_df = pd.DataFrame(matches)
    
    # Find unique sites in each dataset
    if len(results_df) > 0:
        matched_beta_names = set(results_df['Beta_Location_Name'].unique())
        matched_old_names = set(results_df['Old_MonitoringLocationName'].unique())
    else:
        matched_beta_names = set()
        matched_old_names = set()
    
    all_beta_names = set(beta_locations[beta_name].unique())
    all_old_names = set(old_locations[old_name].unique())
    
    unique_to_beta = all_beta_names - matched_beta_names
    unique_to_old = all_old_names - matched_old_names
    
    # Create dataframes for unique sites
    beta_unique_df = beta_locations[beta_locations[beta_name].isin(unique_to_beta)].copy()
    beta_unique_df = beta_unique_df.rename(columns={
        beta_name: 'Location_Name',
        beta_id: 'Location_Identifier',
        beta_lat: 'Latitude',
        beta_long: 'Longitude'
    })
    
    old_unique_df = old_locations[old_locations[old_name].isin(unique_to_old)].copy()
    old_unique_df = old_unique_df.rename(columns={
        old_name: 'Location_Name',
        old_id: 'Location_Identifier',
        old_lat: 'Latitude',
        old_long: 'Longitude'
    })
    
    # Save unique sites to separate CSVs
    beta_unique_path = os.path.join(script_dir, "unique_to_beta.csv")
    old_unique_path = os.path.join(script_dir, "unique_to_old.csv")
    
    beta_unique_df.to_csv(beta_unique_path, index=False)
    old_unique_df.to_csv(old_unique_path, index=False)
    
    if len(results_df) > 0:
        # Sort by distance
        results_df = results_df.sort_values('Distance_Degrees')
        
        # Save to CSV
        output_path = os.path.join(script_dir, output_file)
        results_df.to_csv(output_path, index=False)
        
        print(f"\n✓ Found {len(results_df)} matches!")
        print(f"✓ Saved to: {output_path}")
        
        # Print summary statistics
        exact_name_matches = results_df['Names_Match'].sum()
        different_names = len(results_df) - exact_name_matches
        
        print(f"\nMatched Sites Summary:")
        print(f"  - Exact name matches: {exact_name_matches}")
        print(f"  - Different names (same location): {different_names}")
        print(f"  - Exact ID matches: {results_df['IDs_Match'].sum()}")
        print(f"  - Different IDs (same location): {(~results_df['IDs_Match']).sum()}")
        print(f"  - Average distance: {results_df['Distance_Meters'].mean():.2f} meters")
        print(f"  - Max distance: {results_df['Distance_Meters'].max():.2f} meters")
        
        # Show first few matches with different names or IDs
        if different_names > 0:
            print(f"\nSample matches with different names:")
            diff_names = results_df[~results_df['Names_Match']].head(10)
            for _, row in diff_names.iterrows():
                print(f"  • Beta: '{row['Beta_Location_Name']}' (ID: {row['Beta_Location_Identifier']})")
                print(f"    Old:  '{row['Old_MonitoringLocationName']}' (ID: {row['Old_MonitoringLocationIdentifier']})")
                print(f"    Distance: {row['Distance_Meters']:.2f} meters")
                print(f"    IDs Match: {row['IDs_Match']}\n")
    else:
        print("\n✗ No matches found within tolerance distance")
        print(f"  Try increasing tolerance (current: {tolerance} degrees)")
    
    # Print unique sites summary
    print(f"\n{'='*60}")
    print(f"UNIQUE SITES ANALYSIS")
    print(f"{'='*60}")
    print(f"\nSites unique to BETA (not in old): {len(unique_to_beta)}")
    print(f"✓ Saved to: {beta_unique_path}")
    if len(unique_to_beta) > 0:
        print(f"\nFirst 10 unique beta sites:")
        for _, row in beta_unique_df.head(10).iterrows():
            print(f"  - {row['Location_Name']} (ID: {row['Location_Identifier']})")
    
    print(f"\nSites unique to OLD (not in beta): {len(unique_to_old)}")
    print(f"✓ Saved to: {old_unique_path}")
    if len(unique_to_old) > 0:
        print(f"\nFirst 10 unique old sites:")
        for _, row in old_unique_df.head(10).iterrows():
            print(f"  - {row['Location_Name']} (ID: {row['Location_Identifier']})")
    
    print(f"\n{'='*60}")
    print(f"OVERALL SUMMARY")
    print(f"{'='*60}")
    print(f"Total unique locations in Beta: {len(all_beta_names)}")
    print(f"Total unique locations in Old: {len(all_old_names)}")
    print(f"Matched locations: {len(matched_beta_names)}")
    print(f"Unique to Beta: {len(unique_to_beta)}")
    print(f"Unique to Old: {len(unique_to_old)}")
    
    return results_df

if __name__ == "__main__":
    # Run with default tolerance (0.0001 degrees ≈ 11 meters)
    results = compare_wqx_csvs(tolerance=0.0001)
    
    # Or try with looser tolerance if needed:
    # results = compare_wqx_csvs(tolerance=0.001)  # ≈ 111 meters