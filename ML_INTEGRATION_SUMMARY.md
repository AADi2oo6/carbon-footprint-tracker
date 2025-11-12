# ML Model Integration Summary

## Overview
Integrated a pre-trained ML model (`hybrid_emission_model.pkl`) into the existing Django web app to predict carbon emissions for user activities.

## Implementation Details

### 1. Created ML Utility Module
- **File**: `cft/tracker/ml_utils.py`
- **Functions**:
  - `load_model()`: Loads the pre-trained ML model
  - `predict_emission()`: Predicts carbon emissions using the ML model
  - `fallback_calculation()`: Provides manual calculation when ML model fails

### 2. Modified Activity View
- **File**: `cft/tracker/views.py`
- **Changes**:
  - Added import for `predict_emission` function
  - Replaced hardcoded emission factors with ML model predictions
  - Maintained fallback to manual calculation for compatibility

### 3. Form Field Mapping
The HTML forms already provided the required fields that match the model's expected inputs:

| Category | Subtype Input Field | Value Input Field | Example |
|----------|-------------------|------------------|---------|
| transport | transportMode | distance | Car (Gasoline), 25 km |
| energy | electricityUnits | electricityUnits | 150 kWh |
| food | dietType | foodQuantity | Red Meat, 2 servings |
| consumption | purchaseCategory | purchaseAmount | Electronics, ₹5000 |

## Current Status
- The ML model integration is implemented
- Due to scikit-learn version compatibility issues, the system is currently using the fallback calculation method
- The fallback method provides reasonable emission estimates using hardcoded factors

## Model Information
- **File**: `cft/hybrid_emission_model.pkl`
- **Type**: RandomForestRegressor
- **Input Features**:
  - category (string): "transport", "energy", "food", "consumption"
  - subtype (string): e.g., "car-gasoline", "train", "red-meat", "clothing"
  - value (float): numeric (distance, kWh, servings, or INR)
- **Output**: Predicted CO2e (float, in kilograms)

## Next Steps
1. Resolve scikit-learn version compatibility issues
2. Retrain the model with the current version of scikit-learn
3. Test the ML model predictions with sample data
4. Monitor accuracy and adjust as needed