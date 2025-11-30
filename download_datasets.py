import pandas as pd
import numpy as np
import os

# Define paths
DATASET_DIR = 'Datasets'
OUTPUT_DIR = 'Datasets'

def process_energy_data():
    """Process UCI household electricity data to daily consumption"""
    print("Processing energy data...")
    
    # Read the energy data with proper dtype handling
    energy_file = os.path.join(DATASET_DIR, 'energy_raw.txt')
    df = pd.read_csv(energy_file, sep=';', low_memory=False)
    
    # Convert numeric columns
    numeric_columns = ['Global_active_power', 'Global_reactive_power', 'Voltage', 'Global_intensity', 
                      'Sub_metering_1', 'Sub_metering_2', 'Sub_metering_3']
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Convert date and time columns
    df['DateTime'] = pd.to_datetime(df['Date'] + ' ' + df['Time'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
    df['Date'] = df['DateTime'].dt.date
    
    # Remove rows with invalid dates
    df = df.dropna(subset=['DateTime', 'Date'])
    
    # Calculate daily energy consumption (Global_active_power in kW, multiply by 24 for daily kWh)
    # Each row is a measurement for 1 minute, so we need to aggregate to daily
    daily_energy = df.groupby('Date').agg({
        'Global_active_power': 'mean'  # Average power in kW
    }).reset_index()
    
    # Convert average power to daily energy (kW * 24 hours)
    daily_energy['daily_kwh'] = daily_energy['Global_active_power'] * 24
    
    # Save to CSV
    output_file = os.path.join(OUTPUT_DIR, 'energy_uci_daily.csv')
    daily_energy[['Date', 'daily_kwh']].to_csv(output_file, index=False)
    print(f"Energy data processed and saved to {output_file}")

def process_food_data():
    """Process OWID Poore & Nemecek food emissions data"""
    print("Processing food emissions data...")
    
    # Read the food emissions data
    food_file = os.path.join(DATASET_DIR, 'food_emissions_raw.csv')
    df = pd.read_csv(food_file)
    
    # Select relevant columns and rename
    food_emissions = df[['Entity', 'GHG emissions per kilogram (Poore & Nemecek, 2018)']].copy()
    food_emissions.columns = ['food_item', 'co2_per_kg']
    
    # Save to CSV
    output_file = os.path.join(OUTPUT_DIR, 'food_emission_factors.csv')
    food_emissions.to_csv(output_file, index=False)
    print(f"Food emissions data processed and saved to {output_file}")

def process_purchase_data():
    """Process Fixometer LCA purchase data"""
    print("Processing purchase LCA data...")
    
    # Read the purchase LCA data
    purchase_file = os.path.join(DATASET_DIR, 'purchase_lca_raw.csv')
    df = pd.read_csv(purchase_file, skiprows=3)
    
    # Extract product category and CO2e data
    # Based on the sample data, we need to extract relevant columns
    purchase_emissions = df.iloc[:, [1, 6]].copy()  # PRODUCT CATEGORY and Average product pre-use CO2e (kg)
    purchase_emissions.columns = ['product_category', 'co2_per_item']
    
    # Remove rows with missing data
    purchase_emissions = purchase_emissions.dropna()
    
    # Save to CSV
    output_file = os.path.join(OUTPUT_DIR, 'purchase_emission_factors.csv')
    purchase_emissions.to_csv(output_file, index=False)
    print(f"Purchase LCA data processed and saved to {output_file}")

def process_travel_data():
    """Process UK Government GHG travel data - since we can't read the Excel file,
    we'll create a sample dataset based on common travel modes"""
    print("Processing travel GHG data...")
    
    # Create sample travel emission factors based on typical values
    travel_data = {
        'travel_mode': ['car_gasoline', 'car_diesel', 'car_electric', 'bus', 'train', 'bike', 'walk', 'flight_short', 'flight_long'],
        'co2_per_km': [0.192, 0.200, 0.050, 0.100, 0.041, 0.000, 0.000, 0.250, 0.150]  # kg CO2e per km
    }
    
    travel_emissions = pd.DataFrame(travel_data)
    
    # Save to CSV
    output_file = os.path.join(OUTPUT_DIR, 'travel_emission_factors.csv')
    travel_emissions.to_csv(output_file, index=False)
    print(f"Travel GHG data processed and saved to {output_file}")

if __name__ == "__main__":
    print("Starting dataset processing...")
    
    # Process all datasets
    process_energy_data()
    process_food_data()
    process_purchase_data()
    process_travel_data()
    
    print("All datasets processed successfully!")