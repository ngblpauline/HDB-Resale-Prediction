import streamlit as st
import pandas as pd
import joblib
from geopy.distance import geodesic
import folium
from streamlit_folium import folium_static

# Set Streamlit page layout to wide
st.set_page_config(layout="wide")

# Apply CSS to increase top padding for extra scroll space
st.markdown(
    """
    <style>
    /* Add extra padding at the top of the main content */
    .block-container {
        padding-top: 300px; /* Increase top padding to allow scrolling up */
        margin-top: 0;
        padding-bottom: 20px; /* Adjust as needed */
        box-sizing: border-box;
    }

    /* Ensure no elements are fixed at the top */
    header, .main > div:nth-of-type(1) {
        position: relative; /* Avoid fixed position to prevent overlap */
        top: 0;
    }

    /* Optional: Centralize main app content */
    .main {
        display: flex;
        justify-content: center;
        align-items: flex-start;
        flex-direction: column;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Load the saved model (includes both transformer and regressor)
estimator_xgb = joblib.load('trained_model.pkl')

# Load address data with latitudes and longitudes
addr_data = pd.read_csv('Extracted_postal_with_latlong.csv', low_memory=False)

# Global amenity column mapping
AMENITY_COLUMN_MAPPING = {
    'InlandAshScatteringGardensData.csv': ('NAME', 'Ash Scattering Garden'),
    'HawkerCentresData.csv': ('NAME', 'Hawker Centre'),
    'FuneralParloursData.csv': ('NAME', 'Funeral Parlour'),
    'SupermarketsData.csv': ('LIC_NAME', 'Supermarket'),
    'SportFacilitiesData.csv': ('SPORTS_CEN', 'Sport Facility'),
    'CrematoriaData.csv': ('NAME', 'Crematorium'),
    'AfterDeathFacilitiesData.csv': ('NAME', 'After Death Facility'),
    'TouristAttractionsData.csv': ('PAGETITLE', 'Tourist Attraction'),
    'PCNAccessPointsData.csv': ('FACILITY_N', 'PCN Access Point'),
    'ParksData.csv': ('NAME', 'Park'),
    'LibrariesData.csv': ('NAME', 'Library'),
    'FireStationsData.csv': ('NAME', 'Fire Station'),
    'EatingEstablishmentsData.csv': ('LIC_NAME', 'Eating Establishment'),
    'SingaporePoliceForceEstablishmentsData.csv': ('DEPARTMENT', 'Police Station'),
    'LTAMRTStationExitData.csv': ('STATION_NA', 'MRT Station Exit'),
    'Primary_Schools_Info.csv': ('BUILDING', 'Primary School')
}

def get_lat_long(postal_code):
    """Get latitude, longitude, block, and road name from postal code."""
    match = addr_data[addr_data['POSTAL_CODE'].astype(str) == str(postal_code)]
    if not match.empty:
        return match.iloc[0]['latitude'], match.iloc[0]['longitude'], match.iloc[0]['HOUSE_BLK_NO'], match.iloc[0]['ROAD_NAME']
    st.warning(f"No data found for postal code: {postal_code}.")
    return None, None, None, None

def calculate_distance(lat_long1, lat_long2):
    """Calculate geodesic distance between two lat/long pairs."""
    return geodesic(lat_long1, lat_long2).kilometers

def load_and_process_amenity_data(file_path, user_lat_long):
    """Load amenity data, calculate distances from user location, and find the nearest amenity."""
    data, lat_col, lon_col = load_amenity_data(file_path)
    if data is not None:
        data['distance'] = data.apply(
            lambda row: calculate_distance(user_lat_long, (row[lat_col], row[lon_col])), axis=1
        )
        nearest = data.loc[data['distance'].idxmin()]
        return {
            'Type of Amenity': AMENITY_COLUMN_MAPPING[file_path][1],
            'Nearest Amenity': nearest[AMENITY_COLUMN_MAPPING[file_path][0]],
            'Distance to nearest amenity(km)': round(nearest['distance'], 4),
            'Latitude': nearest[lat_col],
            'Longitude': nearest[lon_col]
        }
    return None

def load_amenity_data(file_path):
    """Load amenity data and find latitude and longitude columns."""
    data = pd.read_csv(file_path)
    lat_col = next((col for col in data.columns if 'lat' in col.lower()), None)
    lon_col = next((col for col in data.columns if 'lon' in col.lower() or 'long' in col.lower()), None)
    return (data, lat_col, lon_col) if lat_col and lon_col else (None, None, None)

def calculate_distances(user_lat, user_long):
    """Calculate minimum distances to all amenities from the user's location."""
    user_lat_long = (user_lat, user_long)
    return {
        f'distance to {file.replace(".csv", "")}': data.apply(
            lambda row: calculate_distance(user_lat_long, (row[lat_col], row[lon_col])), axis=1
        ).min()
        for file in AMENITY_COLUMN_MAPPING.keys()
        for data, lat_col, lon_col in [load_amenity_data(file)]
        if data is not None
    }

def get_nearest_amenities(user_lat, user_long):
    """Aggregate nearest amenities from various data files."""
    user_lat_long = (user_lat, user_long)
    nearest_amenities = [
        load_and_process_amenity_data(file, user_lat_long)
        for file in AMENITY_COLUMN_MAPPING.keys()
    ]
    nearest_amenities = [amenity for amenity in nearest_amenities if amenity is not None]
    nearest_amenities_df = pd.DataFrame(nearest_amenities).sort_values(by='Distance to nearest amenity(km)').reset_index(drop=True)
    nearest_amenities_df.index = nearest_amenities_df.index + 1  # Numbering starts from 1
    return nearest_amenities_df

def get_storey_category(storey):
    """Determine storey category based on storey number."""
    return next((category for max_storey, category in [(2, 1), (6, 2), (12, 3), (15, 4), (25, 5)] if storey <= max_storey), 6)

def create_map(user_lat, user_long, nearest_amenities_df, block, road_name):
    """Create a map with markers for the user's flat and nearest amenities."""
    map_osm = folium.Map(location=[user_lat, user_long], zoom_start=15)
    folium.Marker(
        [user_lat, user_long],
        popup=f"Flat Location: {block} {road_name}",
        icon=folium.Icon(color='blue', icon='home', prefix='fa')
    ).add_to(map_osm)

    for _, row in nearest_amenities_df.iterrows():
        folium.Marker(
            [row['Latitude'], row['Longitude']],
            popup=f"{row['Type of Amenity']}: {row['Nearest Amenity']}",
            icon=folium.Icon(color='red', icon='info-sign')
        ).add_to(map_osm)

    legend_html = """
    <div style="
    position: fixed; 
    bottom: 50px; left: 50px; width: 180px; height: 90px; 
    background-color: white; z-index:9999; font-size:14px;
    border:2px solid grey; padding: 10px;">
    <h4>Legend</h4>
    <i class="fa fa-home" style="color:blue"></i> Flat Location<br>
    <i class="fa fa-info-circle" style="color:red"></i> Nearest Amenities
    </div> 
    """
    map_osm.get_root().html.add_child(folium.Element(legend_html))
    return map_osm

# Streamlit UI
st.title("Resale Price Prediction App")
st.write("This app predicts the resale price of HDB flats in Singapore based on various inputs and amenities nearby.")

# Dropdown options
town_options = sorted(['YISHUN', 'ANG MO KIO', 'BEDOK', 'BISHAN', 'BUKIT BATOK', 'BUKIT MERAH',
                       'BUKIT PANJANG', 'BUKIT TIMAH', 'CENTRAL AREA', 'CHOA CHU KANG', 'GEYLANG',
                       'CLEMENTI', 'HOUGANG', 'JURONG EAST', 'JURONG WEST', 'KALLANG/WHAMPOA',
                       'MARINE PARADE', 'PASIR RIS', 'PUNGGOL', 'QUEENSTOWN', 'SEMBAWANG', 'SENGKANG',
                       'SERANGOON', 'TAMPINES', 'TOA PAYOH', 'WOODLANDS'])
flat_type_options = sorted(['2 ROOM', '3 ROOM', '4 ROOM', '5 ROOM', 'EXECUTIVE', 'MULTI-GENERATION', '1 ROOM'])
flat_model_options = sorted(['Model A', 'Improved', 'Simplified', 'New Generation', 'DBSS', 'Apartment',
                             'Maisonette', '2-room', 'Premium Apartment', '3Gen', 'Multi Generation',
                             'Adjoined flat', 'Standard', 'Model A-Maisonette', 'Model A2', 'Type S1',
                             'Type S2', 'Terrace', 'Premium Apartment Loft', 'Improved-Maisonette'])

# Form for user input
with st.form(key='user_input_form'):
    town = st.selectbox("Select Town", town_options)
    flat_type = st.selectbox("Select Flat Type", flat_type_options)
    floor_area_sqm = st.number_input("Enter Floor Area (sqm)", min_value=10, max_value=200, value=60)
    flat_model = st.selectbox("Select Flat Model", flat_model_options)
    remaining_lease_years = st.slider("Enter Remaining Lease Years", min_value=1, max_value=99, value=90)
    storey = st.slider("Enter Storey", min_value=1, max_value=50, value=10)
    postal_code = st.text_input("Enter Postal Code")
    submit_button = st.form_submit_button(label='Predict')

if submit_button:
    # Process the input and predict
    user_lat, user_long, block, road_name = get_lat_long(postal_code)
    
    if user_lat and user_long:
        distances = calculate_distances(user_lat, user_long)
        storey_category = get_storey_category(storey)

        # Create the DataFrame with input data for prediction
        raw_data = pd.DataFrame({
            'town': [town],
            'flat_type': [flat_type],
            'floor_area_sqm': [floor_area_sqm],
            'flat_model': [flat_model],
            'remaining_lease_years': [remaining_lease_years],
            'Storey Category': [storey_category],
            **{k: [v] for k, v in distances.items()}
        })

        # Get the transformer and regressor from the estimator
        transformer = estimator_xgb.named_steps['transform']
        regressor = estimator_xgb.named_steps['reg']

        # Transform the data and make predictions
        transformed_data = transformer.transform(raw_data)
        predicted_resale_price = regressor.predict(transformed_data)

        # Display the predicted resale price
        st.success(f"Predicted resale price: ${predicted_resale_price[0]:,.2f}")

        # Get the nearest amenities
        nearest_amenities_df = get_nearest_amenities(user_lat, user_long)

        # Create and display the map with the nearest amenities
        st.subheader("Map of the Location and Nearby Amenities")
        map_osm = create_map(user_lat, user_long, nearest_amenities_df, block, road_name)
        folium_static(map_osm)

        # Drop the Latitude and Longitude columns from the table
        nearest_amenities_df = nearest_amenities_df.drop(columns=['Latitude', 'Longitude'])

        # Display the table of nearest amenities and distances within a styled container
        st.subheader("Nearest Amenities and Distances")
        st.markdown('<div class="dataframe-container">', unsafe_allow_html=True)
        st.dataframe(nearest_amenities_df, height=600)  # Adjust height to display full table
        st.markdown('</div>', unsafe_allow_html=True)

    else:
        st.error("Unable to calculate distances without valid latitude and longitude.")


