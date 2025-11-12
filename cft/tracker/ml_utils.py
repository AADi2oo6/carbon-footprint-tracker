import joblib
import pandas as pd
import numpy as np
import os
import json
from django.conf import settings

# Load the model when the module is imported
# Fix the model path - it should be in the models directory
model_path = os.path.join(settings.BASE_DIR, '..', 'models', 'hybrid_emission_model.pkl')
model = None

# Load state-specific factors
state_factors_path = os.path.join(settings.BASE_DIR, '..', 'ml', 'state_factors.json')
state_factors = {}

try:
    with open(state_factors_path, 'r') as f:
        state_factors = json.load(f)
    print(f"✅ State factors loaded successfully from {state_factors_path}")
except Exception as e:
    print(f"❌ Error loading state factors from {state_factors_path}: {e}")
    state_factors = {}

def load_model():
    """Load the pre-trained ML model"""
    global model
    if model is None:
        try:
            model = joblib.load(model_path)
            print(f"✅ Model loaded successfully from {model_path}")
        except Exception as e:
            print(f"❌ Error loading model from {model_path}: {e}")
            model = None
    return model

def get_state_from_location(location):
    """
    Extract state from location string
    This is a simple implementation - you might want to enhance this with more sophisticated
    geocoding or location parsing
    """
    if not location:
        return "Default"
    
    # List of Indian states and union territories
    indian_states = [
        "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", 
        "Delhi", "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", 
        "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", 
        "Meghalaya", "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", 
        "Sikkim", "Tamil Nadu", "Telangana", "Tripura", "Uttar Pradesh", 
        "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", 
        "Chandigarh", "Dadra and Nagar Haveli", "Daman and Diu", 
        "Lakshadweep", "Puducherry"
    ]
    
    # Try to find a state name in the location string
    for state in indian_states:
        if state.lower() in location.lower():
            return state
    
    return "Default"

def get_state_factors(state):
    """
    Get emission factors for a specific state
    """
    return state_factors.get(state, state_factors.get("Default", {
        "grid_kgCO2_per_kWh": 0.71,
        "transport_multiplier": 1.00,
        "food_multiplier": 1.00,
        "consumption_multiplier": 1.00
    }))

def predict_emission(category, subtype, value, user_location=None):
    """
    Predict carbon emission using the ML model with state-specific factors
    
    Args:
        category (str): Activity category (transport, energy, food, consumption)
        subtype (str): Specific subtype (e.g., car-gasoline, train, red-meat, clothing)
        value (float): Numeric value (distance, kWh, servings, or INR)
        user_location (str): User's location to determine state-specific factors
        
    Returns:
        float: Predicted CO2e in kilograms
    """
    print(f"🔍 predict_emission called with category='{category}', subtype='{subtype}', value={value}, location='{user_location}'")
    
    # Get state-specific factors
    state = get_state_from_location(user_location)
    factors = get_state_factors(state)
    print(f"📍 User location: {user_location}, State: {state}")
    print(f"📊 State factors: {factors}")
    
    # Load the model if not already loaded
    model = load_model()
    
    if model is not None:
        try:
            # Prepare the data with the same feature engineering as training
            data = pd.DataFrame({
                'category': [category],
                'subtype': [subtype],
                'value': [value]
            })
            
            print(f"📊 Input data: {data.to_dict()}")
            
            # Apply the same feature engineering as in training
            data_enhanced = data.copy()
            data_enhanced['value_squared'] = data_enhanced['value'] ** 2
            data_enhanced['value_log'] = np.log1p(data_enhanced['value'])
            
            print(f"📈 Enhanced data: {data_enhanced.to_dict()}")
            
            # Make prediction
            prediction = model.predict(data_enhanced)
            base_result = float(prediction[0])
            print(f"✅ ML Model base prediction: {base_result} kg CO2e")
            
            # Apply state-specific factors
            adjusted_result = base_result
            if category == 'energy' and subtype == 'electricity':
                # For electricity, use the state-specific grid emission factor
                adjusted_result = value * factors["grid_kgCO2_per_kWh"]
                print(f"⚡ Energy adjustment: {value} kWh * {factors['grid_kgCO2_per_kWh']} kgCO2/kWh = {adjusted_result} kg CO2e")
            elif category == 'transport':
                # Apply transport multiplier
                adjusted_result = base_result * factors["transport_multiplier"]
                print(f"🚗 Transport adjustment: {base_result} * {factors['transport_multiplier']} = {adjusted_result} kg CO2e")
            elif category == 'food':
                # Apply food multiplier
                adjusted_result = base_result * factors["food_multiplier"]
                print(f"🍽️ Food adjustment: {base_result} * {factors['food_multiplier']} = {adjusted_result} kg CO2e")
            elif category == 'consumption':
                # Apply consumption multiplier
                adjusted_result = base_result * factors["consumption_multiplier"]
                print(f"🛍️ Consumption adjustment: {base_result} * {factors['consumption_multiplier']} = {adjusted_result} kg CO2e")
            
            print(f"✅ Final adjusted prediction: {adjusted_result} kg CO2e")
            return adjusted_result
            
        except Exception as e:
            print(f"❌ Error making prediction with ML model: {e}")
            # Fallback to calculation if model prediction fails
            fallback_result = fallback_calculation(category, subtype, value, factors)
            print(f"🔄 Fallback calculation result: {fallback_result} kg CO2e")
            return fallback_result
    else:
        # Fallback to calculation if model loading fails
        print("⚠️ Model not loaded, using fallback calculation")
        fallback_result = fallback_calculation(category, subtype, value, factors)
        print(f"🔄 Fallback calculation result: {fallback_result} kg CO2e")
        return fallback_result

def fallback_calculation(category, subtype, value, factors=None):
    """
    Fallback calculation method with state-specific factors if ML model fails
    """
    if factors is None:
        factors = {
            "grid_kgCO2_per_kWh": 0.71,
            "transport_multiplier": 1.00,
            "food_multiplier": 1.00,
            "consumption_multiplier": 1.00
        }
    
    EMISSION_FACTORS = {
        'transport': {
            'car-gasoline': 0.25, 
            'bus': 0.1, 
            'flight-short': 0.2, 
            'car-electric': 0.05, 
            'train': 0.04, 
            'motorcycle': 0.1, 
            'bicycle': 0, 
            'walking': 0, 
            'flight-long': 0.25
        },
        'energy': {
            'electricity': factors["grid_kgCO2_per_kWh"]  # Use state-specific factor
        },
        'food': {
            'red-meat': 7.1, 
            'white-meat': 2.5, 
            'fish': 1.5, 
            'vegetarian': 1.0, 
            'vegan': 0.7, 
            'other': 1.2
        },
        'consumption': {
            'clothing': 0.1, 
            'electronics': 0.5, 
            'home-goods': 0.3, 
            'services': 0.05, 
            'other': 0.2
        }
    }
    
    # Map categories to match the fallback factors
    category_mapping = {
        'transport': 'transport',
        'energy': 'energy',
        'food': 'food',
        'consumption': 'consumption'
    }
    
    mapped_category = category_mapping.get(category, category)
    
    if mapped_category in EMISSION_FACTORS:
        factor = EMISSION_FACTORS[mapped_category].get(subtype, 0.15)  # Default factor if subtype not found
        
        # Apply multipliers for state-specific adjustments
        if category == 'transport':
            factor = factor * factors["transport_multiplier"]
        elif category == 'food':
            factor = factor * factors["food_multiplier"]
        elif category == 'consumption':
            factor = factor * factors["consumption_multiplier"]
        
        result = value * factor
        print(f"🧮 Fallback calculation: {value} * {factor} = {result}")
        return result
    else:
        result = value * 0.15 * factors["consumption_multiplier"]  # Default factor if category not found
        print(f"🧮 Default fallback calculation: {value} * 0.15 * {factors['consumption_multiplier']} = {result}")
        return result