"""
Import daily flow and specific conductance data from USGS NWIS for Arkansas River sites
This complements the WQX water quality data with continuous monitoring data

USGS Parameter Codes:
- 00060 = Discharge (flow) in cubic feet per second (cfs)
- 00095 = Specific conductance in microsiemens per centimeter (µS/cm @ 25°C)
"""

import pandas as pd
import requests
from datetime import datetime
import os
import glob

def get_usgs_daily_data(site_number, parameter_codes, start_date="1990-10-01", end_date=None):
    """Get daily data from USGS NWIS for specified parameters"""
    if end_date is None:
        end_date = datetime.today().strftime("%Y-%m-%d")
    
    base_url = "https://waterservices.usgs.gov/nwis/dv/"
    
    params = {
        'format': 'json',
        'sites': site_number,
        'startDT': start_date,
        'endDT': end_date,
        'parameterCd': ','.join(parameter_codes),
        'statCd': '00003',
        'siteStatus': 'all'
    }
    
    print(f"  Requesting data for site {site_number}...")
    
    try:
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        if 'value' not in data or 'timeSeries' not in data['value']:
            print(f"    ✗ No data returned")
            return pd.DataFrame()
        
        time_series = data['value']['timeSeries']
        if len(time_series) == 0:
            print(f"    ✗ No data available")
            return pd.DataFrame()
        
        site_info = time_series[0]['sourceInfo']
        site_name = site_info.get('siteName', 'Unknown')
        site_code = site_info.get('siteCode', [{}])[0].get('value', site_number)

        param_data = {}
        for ts in time_series:
            variable = ts['variable']
            param_code = variable['variableCode'][0]['value']
            param_name = variable['variableDescription']
            
            if 'values' in ts and len(ts['values']) > 0:
                values = ts['values'][0]['value']
                param_data[param_code] = {'name': param_name, 'values': values}
                print(f"    ✓ {param_name}: {len(values)} records")

        if len(param_data) == 0:
            return pd.DataFrame()
        
        # Get ALL unique dates from ALL parameters (not just first parameter)
        all_dates = set()
        for param_code, param_info in param_data.items():
            for val in param_info['values']:
                all_dates.add(val['dateTime'][:10])
        
        dates = sorted(list(all_dates))
        print(f"    📅 Total unique dates: {len(dates)}")
        
        df_dict = {
            'Date': dates,
            'Site_Number': [site_code] * len(dates),
            'Site_Name': [site_name] * len(dates)
        }
        
        col_name_map = {'00060': 'Flow_cfs', '00095': 'SpCond_uScm'}
        
        for param_code, param_info in param_data.items():
            col_name = col_name_map.get(param_code, f'Param_{param_code}')
            value_dict = {}
            for val in param_info['values']:
                date = val['dateTime'][:10]
                value = float(val['value']) if val['value'] not in ['-999999', '-999999.0'] else None
                value_dict[date] = value
            df_dict[col_name] = [value_dict.get(date) for date in dates]
        
        df = pd.DataFrame(df_dict)
        df['Date'] = pd.to_datetime(df['Date'])
        return df
        
    except Exception as e:
        print(f"    ✗ Error: {e}")
        return pd.DataFrame()

def import_arkansas_river_usgs_data():
    """Import daily flow and specific conductance data"""
    
    usgs_sites = {
        '07094500': 'Arkansas River at Parkdale, CO',
        '07099970': 'Arkansas River at Moffat Street at Pueblo, CO',
        '07099971': 'Arkansas River Below Moffat Street at Pueblo, CO',
        '07099400': 'Arkansas River above Pueblo, CO',
        '07099969': 'Arkansas R. at ST Charles Mesa Diver. at Pueblo, CO',
        '07109500': 'Arkansas River near Avondale, CO',
        '07124000': 'Arkansas River at Las Animas, CO',
        '07120500': 'Arkansas River near Rocky Ford, CO',
        '07123000': 'Arkansas River at La Junta, CO',
        '07119700': 'Arkansas River at Catlin Dam, Near Fowler, CO.',  
        '07130500': 'Arkansas River below John Martin Reservoir, CO',
        '07133000': 'Arkansas River at Lamar, CO',
        '07134180': 'Arkansas River near Granada, CO',
        '07106500': 'Fountain Creek at Pueblo, CO.'
    }
    
    parameter_codes = ['00060', '00095']
    
    print("="*80)
    print("USGS DAILY DATA IMPORT")
    print("="*80)
    print(f"\nFetching Flow (00060) and Specific Conductance (00095)")
    print(f"Date range: 1990-10-01 to {datetime.today().strftime('%Y-%m-%d')}\n")
    
    all_data = []
    for site_num, site_name in usgs_sites.items():
        print(f"\n{site_name} ({site_num}):")
        df = get_usgs_daily_data(site_num, parameter_codes, start_date="1990-10-01")
        if not df.empty:
            all_data.append(df)
    
    if len(all_data) == 0:
        print("\n✗ No data retrieved")
        return None
    
    combined_df = pd.concat(all_data, ignore_index=True)
    combined_df = combined_df.sort_values(['Site_Number', 'Date']).reset_index(drop=True)
    
    today_str = datetime.today().strftime("%Y%m%d")
    output_file = f"USGS_DailyData_Arkansas_19901001-{today_str}.csv"
    combined_df.to_csv(output_file, index=False)
    
    print("\n" + "="*80)
    print(f"✓ Total records: {len(combined_df):,}")
    print(f"✓ Output: {output_file}")
    
    # Create site mapping
    unique_sites = combined_df[['Site_Number', 'Site_Name']].drop_duplicates()
    
    print("\n" + "="*80)
    print("DEBUG: Sites found in USGS data:")
    print("="*80)
    for _, row in unique_sites.iterrows():
        print(f"Site Number: {row['Site_Number']}")
        print(f"Site Name: {row['Site_Name']}")
        print()

    wqx_mapping = {
        '07094500': 'ARKANSAS RIVER AT PARKDALE, CO.',
        '07099970': 'ARKANSAS RIVER AT MOFFAT STREET AT PUEBLO, CO',
        '07099971': 'ARKANSAS RIVER BELOW MOFFAT STREET AT PUEBLO, CO',
        '07099400': 'ARKANSAS RIVER ABOVE PUEBLO, CO',
        '07099969': 'ARKANSAS R. AT ST CHARLES MESA DIVER. AT PUEBLO, CO',
        '07109500': 'ARKANSAS RIVER NEAR AVONDALE, CO.',
        '07124000': 'ARKANSAS RIVER AT LAS ANIMAS, CO.',
        '07120500': 'ARKANSAS RIVER NEAR ROCKY FORD, CO.',
        '07123000': 'ARKANSAS RIVER AT LA JUNTA, CO',
        '07119700': 'ARKANSAS RIVER AT CATLIN DAM, NEAR FOWLER, CO.',
        '07130500': 'ARKANSAS RIVER BELOW JOHN MARTIN RESERVOIR, CO.',
        '07133000': 'ARKANSAS RIVER AT LAMAR, CO',
        '07134180': 'ARKANSAS RIVER NEAR GRANADA, CO.',
        '07106500': 'FOUNTAIN CREEK AT PUEBLO, CO.'
    }


    print("="*80)
    print("DEBUG: Applying WQX mapping:")
    print("="*80)
    for site_num in unique_sites['Site_Number'].unique():
        wqx_name = wqx_mapping.get(site_num, 'NOT FOUND')
        print(f"{site_num} → {wqx_name}")

    
    unique_sites['WQX_Site_Name'] = unique_sites['Site_Number'].map(wqx_mapping)

    print("\n" + "="*80)
    print("DEBUG: Final mapping table:")
    print("="*80)
    print(unique_sites.to_string())
    print()

    mapping_file = output_file.replace('.csv', '_SiteMapping.csv')
    unique_sites.to_csv(mapping_file, index=False)
    print(f"✓ Mapping: {mapping_file}")
    print("="*80)
    
    return combined_df

if __name__ == "__main__":
    import_arkansas_river_usgs_data()