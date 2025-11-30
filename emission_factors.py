import pandas as pd
import os
from difflib import SequenceMatcher

# Define paths
DATASET_DIR = 'Datasets'

def load_emission_factors():
    """Load all emission factors from processed CSV files"""
    energy_factors = pd.read_csv(os.path.join(DATASET_DIR, 'energy_uci_daily.csv'))
    food_factors = pd.read_csv(os.path.join(DATASET_DIR, 'food_emission_factors.csv'))
    travel_factors = pd.read_csv(os.path.join(DATASET_DIR, 'travel_emission_factors.csv'))
    purchase_factors = pd.read_csv(os.path.join(DATASET_DIR, 'purchase_emission_factors.csv'))
    
    return energy_factors, food_factors, travel_factors, purchase_factors

def similarity(a, b):
    """Calculate similarity between two strings"""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def get_energy_co2(description, energy_kwh):
    """
    Get CO2 emissions for energy consumption based on description
    For now, we use a fixed emission factor for electricity
    """
    # In a more sophisticated implementation, we would match the description
    # to specific energy sources, but for now we use a fixed factor
    # Based on the UCI dataset, household electricity averages around 0.39 kg CO2/kWh
    electricity_emission_factor = 0.39  # kg CO2 per kWh
    return energy_kwh * electricity_emission_factor

def get_food_co2(description, food_weight_kg):
    """
    Get CO2 emissions for food consumption based on description
    Uses substring matching to find the best match in food emission factors
    """
    try:
        food_factors = pd.read_csv(os.path.join(DATASET_DIR, 'food_emission_factors.csv'))
    except FileNotFoundError:
        # Return a default value if the file is not found
        return food_weight_kg * 2.0  # Default emission factor
    
    best_match = None
    best_similarity = 0
    
    # Find the best matching food item based on description
    for _, row in food_factors.iterrows():
        food_item = row['food_item']
        # Check if the food item is mentioned in the description
        if food_item.lower() in description.lower():
            return food_weight_kg * row['co2_per_kg']
        # Calculate similarity for potential fuzzy matching
        sim = similarity(description, food_item)
        if sim > best_similarity and sim > 0.6:  # Threshold for similarity
            best_similarity = sim
            best_match = row
    
    # If we found a similar item, use its emission factor
    if best_match is not None:
        return food_weight_kg * best_match['co2_per_kg']
    
    # Default emission factor if no match found
    return food_weight_kg * 2.0

def get_travel_co2(description, distance_km):
    """
    Get CO2 emissions for travel based on description
    Uses substring matching to find the best match in travel emission factors
    """
    try:
        travel_factors = pd.read_csv(os.path.join(DATASET_DIR, 'travel_emission_factors.csv'))
    except FileNotFoundError:
        # Return a default value if the file is not found
        return distance_km * 0.15  # Default emission factor
    
    best_match = None
    best_similarity = 0
    
    # Find the best matching travel mode based on description
    for _, row in travel_factors.iterrows():
        travel_mode = row['travel_mode']
        # Check if the travel mode is mentioned in the description
        if travel_mode.lower() in description.lower():
            return distance_km * row['co2_per_km']
        # Calculate similarity for potential fuzzy matching
        sim = similarity(description, travel_mode)
        if sim > best_similarity and sim > 0.6:  # Threshold for similarity
            best_similarity = sim
            best_match = row
    
    # If we found a similar item, use its emission factor
    if best_match is not None:
        return distance_km * best_match['co2_per_km']
    
    # Default emission factor if no match found
    return distance_km * 0.15

def get_purchase_co2(description, quantity):
    """
    Get CO2 emissions for purchases based on description
    Uses substring matching to find the best match in purchase emission factors
    """
    try:
        purchase_factors = pd.read_csv(os.path.join(DATASET_DIR, 'purchase_emission_factors.csv'))
    except FileNotFoundError:
        # Return a default value if the file is not found
        return quantity * 10.0  # Default emission factor
    
    best_match = None
    best_similarity = 0
    
    # Find the best matching product category based on description
    for _, row in purchase_factors.iterrows():
        product_category = row['product_category']
        # Check if the product category is mentioned in the description
        if product_category.lower() in description.lower():
            return quantity * row['co2_per_item']
        # Calculate similarity for potential fuzzy matching
        sim = similarity(description, product_category)
        if sim > best_similarity and sim > 0.6:  # Threshold for similarity
            best_similarity = sim
            best_match = row
    
    # If we found a similar item, use its emission factor
    if best_match is not None:
        return quantity * best_match['co2_per_item']
    
    # Default emission factor if no match found
    return quantity * 10.0