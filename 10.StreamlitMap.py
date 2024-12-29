import streamlit as st
import geopandas as gpd
import folium
from streamlit_folium import folium_static
import numpy as np
from io import BytesIO
import os
import requests
import tempfile
import dropbox


# Initialize session state to track if the map is loaded
if 'map_loaded' not in st.session_state:
    st.session_state['map_loaded'] = False

def reset_map():
    st.session_state['map_loaded'] = False


######### User Interface
st.title('Hip Hop Exposure Map')

st.subheader("Introduction:")

st.markdown("""
    The map below shows the amount of Hip Hop played over radio across geographies in the US.
            
    ###### Data was compiled from:
    1. an archived FCC dataset of engineering information about antennas registered in 1997
    2. Broadcasting & Cable yearbooks, a discontinued publication that provided information about radio stations (digitized from paper copies stored in the Harvard Business School Library) 
                
    ###### There are three geographies available to view:
    1. ***Radio Station Broadcast Range***: This map shows the broadcast range of every radio station and the concentration of Hip Hop played
    2. ***County***: This map shows a Hip Hop exposure score for every county
    3. ***Census Tract***: This map shows the same for every census tract
            
    ###### There are two types of data available:
    1. ***1997 Hip Hop Exposure***: A score of the concentration of Hip Hop played over radio in 1997 in a given geography
    2. ***Year of Initial Exposure***: The year that the tract or station was first exposed to Hip Hop
    """)

st.subheader("Select Data Options:")

# Geography Selection
geography_data_type = st.radio(
    "Choose the geographic area to view:",
    ('Radio Station Broadcast Range', 'County', 'Census Tract'),
    on_change=reset_map
)

# 97 Exposure or Initial Exposure Selection
exposure_data_type = st.radio(
    "Choose the type of exposure to display:",
    ('1997 Hip Hop Exposure', 'Year of Initial Exposure'),
    on_change=reset_map
)

# Hip Hop Definition Selection
hh_definition = st.multiselect(
    'Choose genres from Broadcasting & Cable to include as "Hip Hop" in exposure score:',
    ['Hip Hop', 'Black', 'Urban Contemporary'],
    on_change=reset_map
)

custom_order = ['Hip Hop', 'Black', 'Urban Contemporary']
hh_definition = sorted(hh_definition, key=lambda x: custom_order.index(x))
hh_definition_suffix = '_'.join(hh_definition)
hh_definition_col_name = "HH_conc_" + hh_definition_suffix

# Census Exposure Score selection
tract_data_options = {}
if geography_data_type in ['Census Tract', 'County'] and exposure_data_type == '1997 Hip Hop Exposure':
    st.subheader("1997 Census Data Options:")

    if 'Census Tract' == geography_data_type:
        st.markdown(f"""
            ###### How the exposure score is calculated:
            1. Calculating a Hip Hop concentration for every radio station:
                - The genres of music played by each station are identified
                - The Hip Hop concentration of a station is defined as the fraction of Hip Hop genres to all genres
            2. Calculating a Hip Hop exposure score for every census tract:
                - The population centroid of each tract is identified
                - The broadcast range of every radio station is identified
                - The stations whose broadcast range reaches the tract's population centroid are compiled
                - The tract's Hip Hop exposure score is calculated as either the sum or average of the Hip Hop concentration of all stations
                - The score can be weighted by each station's rating (a measure of how many listeners a station has)
                - Scores are normalized to a scale of 0 to 1
        """)
    if 'County' == geography_data_type:
        st.markdown(f"""
            ###### How the exposure score is calculated:
            1. Calculating a Hip Hop concentration for every radio station:
                - The genres of music played by each station are identified
                - The Hip Hop concentration of a station is defined as the fraction of Hip Hop genres to all genres
            2. Calculating a Hip Hop exposure score for every census tract:
                - The population centroid of each tract is identified
                - The broadcast range of every radio station is identified
                - The stations whose broadcast range reaches the tract's population centroid are compiled
                - The tract's Hip Hop exposure score is calculated as either the sum or average of the Hip Hop concentration of all stations
                - The score can be weighted by each station's rating (a measure of how many listeners a station has)
                - Scores are normalized to a scale of 0 to 1
            3. Calculating a county's exposure score:
                - The county's exposure score is calculated as the sum of average of all stations that reach a tract in the county
        """)

    st.markdown('###### Exposure Score Options:')

    tract_data_options['agg_type'] = st.radio(
        "Choose whether to sum or average:",
        ('Average', 'Sum'),
        on_change=reset_map
    )
    tract_data_options['weight'] = st.radio(
        "Choose whether to weight by radio station rating:",
        ('Non-Weighted', 'Weighted'),
        on_change=reset_map
    )
    st.markdown('_Note: Rating data is only available for half of the census tracts and a minority of counties_')

else:
    tract_data_options['agg_type'] = 'Average'
    tract_data_options['weight'] = 'Non-Weighted'

######### Identify the map file

# Generate file name for the map
hh_definition_joined = '_'.join(hh_definition) if hh_definition else "None"
map_name = f"{geography_data_type}_{exposure_data_type}_{hh_definition_joined}_{tract_data_options['agg_type']}_{tract_data_options['weight']}.html"

# Dropbox API access token
DROPBOX_ACCESS_TOKEN = "sl.u.AFeQnCh3zIUtDAWHzBpb2fP_oVHyPedSDHv5mG_U3g-EELDAwPXLF8IHkvZ3wGRlPl1ZSGM93S93KXnLbvp4HBprrqYMfn2kYqyebNg6OXwEQamBWVT7CxDGzuAytyBFohd8e1cKFIblw-KYotm8--B1a8lnbTofgfZ3MgTcj_u_zYpNK541KaW0a9SPIIrHiuRKRYUUXHolJS7AGIhmMC6FyFBabwDWir30gRszKFmvebZJwXEW5N9-fGCDIPsgg8xNbrMo0yvyKqr1wjnCgjZhlJiYnjgXI5TaxOh8kO4SaHNydfsW5p4lt16f1EtP8G6hef8qnpZmqVnjEfebEbWYEa7lhCd9tdI0aWTWhVbczprSJhrn8-yF6OjNZ-C4kBOW16Ge5u7ULvPnE0YMv9EohAP8oUkmeA8jmunWy2cBAjh5-eLYyrocgy3H8daUgB1sgYXPjLIsNRgkqVBBzkPl5B48UwbcVyr-znC2VcXacZ-4qA_xJPL951E06JCoP4hCoItSsPHHUWHw7Ox1Xty_L3f0GsBEktkYV9Ie5dejavrcP1y0HMfI1qP3UhgAWaRR0I7tLPSwUm9Bt_uI-4yvuN-XiQ-2t7y8stwGYp2rHUGDSgXW-iLLG13sKBZs_889Zh5WlTVm620Ap_TNsl5QGAqqVHkVHct_u4SjecECsRf24i3sCu29D8rKPY1gLBA17mHoNTUGo8DDT-ikUyiO6E5lWxN2DwgdAWxSk_q47ojE33rzQnq3gJ61bjnSjwjr6S9iRihTyU97Pr8rjyAhT5FRfr8bhUEMmlJW6ptYP2te1QZ7ohJEAptmG8E5eqG3vmGqd76aNcKj1ldVYyo1w7_wc9J68bB_KtNg0G2_ArPIbMAMO8pyFZHlOQ8MwCTNyclXgtj39BYSh_MqLU-nDvZAqQ1ZYE2T7Z5pPtlv5x1-1dCSTgLFKRAA4IGeMIZHFF31jyrCrZuTYDdLzwykjGiAgvUiN2cAPJjiwJcwHq83uy2p85gIo-Ol7UXtyuLorpwQmfbzUi4wTKcaaIkd3mx8KBHhhIsPmPQVxSBwD2qJ3l2TW62hxPUXRWMYeJtK6lHk9Y1sZpFaEGQENTW7OzR7nzF2W4X0XEnYcpAMuvhewl8Dbkrx2dLKRZsNmGi2h4bVwq2g9YDKlpeqQXbF0ik5WZHGF1gU5Qfev4dIxX_XH8Q0Qvsnh4M2FVg9sxBCIG2eygaQ3kHVpe82e_2PJq394mrkQzVN3QBj_CAqM_GtGmYvcTVKmUL9iZRp0dAg6-KTG3OkFo3bJRsqtE_tZtsUxJZWu6_734GnefCWc_0Jj7s0YXyzxGJ0RFKW1YTmcrDnNfq9qEeFBOnizwAViAImqcG6-7yz_qm_zkIYAObX0kCiO0iXsnYER1jKFG-sycgxBIIELz-_1owb_-DwL9iQs1qvslJk2pCMLOwxzg"
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)

# Corrected folder path in Dropbox
DROPBOX_FOLDER_PATH = "/jamie foxx/Will Moller Work/Data/Current Work/Exports/Maps"

# Function to list files in the Dropbox folder
def list_files_in_dropbox(folder_path):
    try:
        entries = dbx.files_list_folder(folder_path).entries
        return [entry.name for entry in entries if isinstance(entry, dropbox.files.FileMetadata)]
    except dropbox.exceptions.ApiError as e:
        st.error(f"Failed to list files in Dropbox folder: {str(e)}")
        return []

# Function to download a file from Dropbox
def download_from_dropbox(file_path, local_path):
    try:
        metadata, res = dbx.files_download(path=file_path)
        with open(local_path, "wb") as f:
            f.write(res.content)
    except Exception as e:
        raise Exception(f"Failed to download file: {str(e)}")

# Update paths for Dropbox
dropbox_map_path = f"{DROPBOX_FOLDER_PATH}/{map_name}"
local_map_path = tempfile.NamedTemporaryFile(delete=False, suffix=".html").name

######### Load Map
if st.button("Load Map"):
    with st.spinner("Downloading and loading map..."):
        try:
            # List available files in Dropbox folder
            available_files = list_files_in_dropbox(DROPBOX_FOLDER_PATH)

            if map_name not in available_files:
                st.error(f"Map file '{map_name}' not found in Dropbox.")
            else:
                # Download file from Dropbox
                download_from_dropbox(dropbox_map_path, local_map_path)
                st.session_state['map_loaded'] = True
        except Exception as e:
            st.error(f"Failed to load map: {str(e)}")

# Display the map
if st.session_state['map_loaded']:
    with st.spinner(f"Rendering map: {map_name}"):
        try:
            with open(local_map_path, 'r', encoding='utf-8') as file:
                map_html = file.read()
            st.components.v1.html(map_html, height=600, scrolling=True)

        except Exception as e:
            st.error(f"An error occurred while rendering the map: {str(e)}")    

        # Add legend
        if exposure_data_type == '1997 Hip Hop Exposure':
            radio_legend_html = '''
            <div style="
                width: 100%;
                background-color: white;
                border: 2px solid black;
                padding: 10px;
                font-size: 14px;
                line-height: 1.5;
                text-align: left;
                margin-bottom: 5mm;
            ">
                <b>Legend</b><br>
                <b>1997 Hip Hop Exposure:</b><br>
                <i style="background: rgba(255, 0, 0, 1); width: 20px; height: 10px; display: inline-block;"></i> High Hip Hop Exposure (Reddish)<br>
                <i style="background: rgba(255, 0, 0, 0.5); width: 20px; height: 10px; display: inline-block;"></i> Moderate Hip Hop Exposure (Transparent Reddish)<br>
                <i style="background: rgba(255, 0, 0, 0); border: 1px solid black; width: 20px; height: 10px; display: inline-block;"></i> No Hip Hop Exposure (Transparent)<br>
            </div>
            '''

            st.markdown(radio_legend_html, unsafe_allow_html=True)