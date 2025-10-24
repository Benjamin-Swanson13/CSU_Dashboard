"""
Diagnostic script to find why "ARKANSAS RIVER BELOW JOHN MARTIN RESERVOIR, CO." is missing
Run this after your import to see where the data gets filtered out
"""
usgs_sites = {
        '07099970': 'Arkansas River at Moffat Street at Pueblo, CO',
        '381515104351900': 'Fountain Creek at Mouth Near Pueblo',
        '07099400': 'Arkansas River above Pueblo, CO',
        '07099970': 'Arkansas River below Pueblo Reservoir, CO',
        '07109500': 'Arkansas River near Avondale, CO',
        '07124000': 'Arkansas River at Las Animas, Co.',
        '07130500': 'Arkansas River below John Martin Reservoir, Co.',  
        '07123000': 'Arkansas River at LA Junta, CO',
        '07119700': 'Arkansas River at Catlin Dam, Near Fowler, Co.',
        '07133000': 'Arkansas River at Lamar, CO',
        '07120500': 'Arkansas River near Rocky Ford, CO',
    }


import pandas as pd

# Read your parsed CSV
parsed_csv = "CSU_EPAWQData_Beta_19901001-20251013_parsed.csv"  # Use your actual filename
df = pd.read_csv(parsed_csv, dtype=str)

print("="*80)
print("SITE DIAGNOSTIC: ARKANSAS RIVER BELOW JOHN MARTIN RESERVOIR")
print("="*80)

# 1. Check if site exists in the parsed data
target_site = "ARKANSAS RIVER BELOW JOHN MARTIN RESERVOIR, CO."
print(f"\n1. CHECKING FOR EXACT MATCH:")
print(f"   Target: '{target_site}'")

exact_match = df[df['Location_Name'] == target_site]
print(f"   Found {len(exact_match)} records with exact match")

if len(exact_match) > 0:
    print("   ✓ Site EXISTS in parsed data!")
    print(f"\n   Sample record:")
    print(exact_match[['Location_Name', 'Result_Characteristic', 'Activity_StartDate']].head(3))
else:
    print("   ✗ Site NOT found with exact match")
    
    # Try fuzzy matching
    print(f"\n2. CHECKING FOR SIMILAR NAMES:")
    john_martin_sites = df[df['Location_Name'].str.contains('JOHN MARTIN', case=False, na=False)]
    arkansas_below_sites = df[df['Location_Name'].str.contains('ARKANSAS.*BELOW', case=False, na=False)]
    
    print(f"\n   Sites containing 'JOHN MARTIN':")
    if len(john_martin_sites) > 0:
        unique_names = john_martin_sites['Location_Name'].unique()
        for name in unique_names:
            count = (john_martin_sites['Location_Name'] == name).sum()
            print(f"      - {name}: {count} records")
    else:
        print("      None found")
    
    print(f"\n   Sites containing 'ARKANSAS' and 'BELOW':")
    if len(arkansas_below_sites) > 0:
        unique_names = arkansas_below_sites['Location_Name'].unique()
        for name in unique_names:
            count = (arkansas_below_sites['Location_Name'] == name).sum()
            print(f"      - {name}: {count} records")
    else:
        print("      None found")

# 3. Check the RAW downloaded data (before parsing)
print(f"\n3. CHECKING RAW DOWNLOADED DATA:")
try:
    raw_results = pd.read_csv("beta_result.csv", dtype=str, low_memory=False)
    raw_match = raw_results[raw_results['Location_Name'] == target_site]
    print(f"   Found {len(raw_match)} records in RAW data")
    
    if len(raw_match) > 0:
        print("   ✓ Site EXISTS in raw data - checking what happened during import...")
        
        # Check characteristics before filtering
        print(f"\n   Characteristics in raw data for this site:")
        char_counts = raw_match['Result_Characteristic'].value_counts()
        print(char_counts.head(20))
        
        # Check coordinates
        print(f"\n   Coordinates:")
        print(f"   Latitude: {raw_match['Location_LatitudeStandardized'].iloc[0]}")
        print(f"   Longitude: {raw_match['Location_LongitudeStandardized'].iloc[0]}")
        
        # Check if it has any key analytes
        key_analytes = ["conductivity", "escherichia coli", "flow", "temperature",
                       "hardness", "arsenic", "iron", "ph", "selenium"]
        
        print(f"\n   Checking for key analytes:")
        for analyte in key_analytes:
            mask = raw_match['Result_Characteristic'].str.lower().str.contains(analyte, na=False)
            count = mask.sum()
            if count > 0:
                print(f"      ✓ {analyte}: {count} records")
        
    else:
        print("   ✗ Site NOT in raw data - check if it's in your select_sites list")
        
        # Check for similar names in raw data
        print(f"\n   Checking for similar names in raw data...")
        john_martin_raw = raw_results[raw_results['Location_Name'].str.contains('JOHN MARTIN', case=False, na=False)]
        if len(john_martin_raw) > 0:
            print(f"\n   Found {len(john_martin_raw)} records with 'JOHN MARTIN':")
            unique_names = john_martin_raw['Location_Name'].unique()
            for name in unique_names[:10]:  # Show first 10
                print(f"      - {name}")
        
except FileNotFoundError:
    print("   ⚠ Raw data file 'beta_result.csv' not found - run import first")

# 4. Check your select_sites list
print(f"\n4. CHECKING SELECT_SITES LIST:")
select_sites_sample = [
    "ARKANSAS RIVER BELOW JOHN MARTIN RESERVOIR, CO.",
    "John Martin Reservoir",
    "Arkansas - John Martin Res Outlet",
]

print("   Sites in your list related to John Martin:")
for site in select_sites_sample:
    print(f"      - {site}")

# 5. Check characteristics distribution in parsed data
print(f"\n5. OVERALL PARSED DATA CHECK:")
print(f"   Total records: {len(df)}")
print(f"   Unique sites: {df['Location_Name'].nunique()}")
print(f"\n   Top 10 characteristics:")
print(df['Result_Characteristic'].value_counts().head(10))

print("\n" + "="*80)
print("DIAGNOSTIC COMPLETE")
print("="*80)

# Recommendations
print("\nRECOMMENDATIONS:")
print("1. If site exists in RAW but not PARSED:")
print("   → Check if characteristics match your key_analytes list")
print("   → Check if coordinates are valid (not null)")
print("\n2. If site has different name in raw data:")
print("   → Add the EXACT name from raw data to select_sites list")
print("\n3. If site not in raw data at all:")
print("   → Site may not be in your bounding box")
print("   → Check site coordinates: 38.0664, -102.932")