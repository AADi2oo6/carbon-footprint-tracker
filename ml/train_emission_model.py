

import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split, GridSearchCV
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.metrics import r2_score
import joblib


# Using the updated larger dataset file
df = pd.read_csv("BEIS___Synthetic_Carbon_Dataset.csv")

print(f"Dataset loaded with {len(df)} rows")

# Features (inputs) and Target (output)
X = df[["category", "subtype", "value"]]
y = df["co2e"]


# Add polynomial features for better fitting
X_enhanced = X.copy()
X_enhanced['value_squared'] = X_enhanced['value'] ** 2
X_enhanced['value_log'] = np.log1p(X_enhanced['value'])  # log(1+x) to handle zero values


# Encode categorical features and scale numerical features
preprocessor = ColumnTransformer(
    transformers=[
        ("cat", OneHotEncoder(handle_unknown="ignore"), ["category", "subtype"]),
        ("num", StandardScaler(), ["value", "value_squared", "value_log"])
    ]
)

# Try multiple advanced models
models_to_try = {
    'RandomForest': RandomForestRegressor(n_estimators=100, random_state=42, n_jobs=-1),
    'GradientBoosting': GradientBoostingRegressor(n_estimators=100, random_state=42)
}

best_score = 0
best_model = None
best_model_name = ""

print("Training multiple models...")

# Split the data once for consistency
X_train, X_test, y_train, y_test = train_test_split(X_enhanced, y, test_size=0.2, random_state=42)

for name, model in models_to_try.items():
    # Create pipeline
    pipeline = Pipeline([
        ("preprocessor", preprocessor),
        ("regressor", model)
    ])
    
    # Train model
    pipeline.fit(X_train, y_train)
    
    # Evaluate model
    score = pipeline.score(X_test, y_test)
    print(f"{name} R² Score: {score:.4f}")
    
    if score > best_score:
        best_score = score
        best_model = pipeline
        best_model_name = name

print(f"\nBest model: {best_model_name} with R² Score: {best_score:.4f}")


param_grid = {}
if best_model_name == 'RandomForest':
    # Hyperparameter tuning for Random Forest
    param_grid = {
        'regressor__n_estimators': [100, 200],
        'regressor__max_depth': [10, 20, None],
        'regressor__min_samples_split': [2, 5]
    }
elif best_model_name == 'GradientBoosting':
    # Hyperparameter tuning for Gradient Boosting
    param_grid = {
        'regressor__n_estimators': [100, 200],
        'regressor__max_depth': [3, 5],
        'regressor__learning_rate': [0.1, 0.05]
    }

if best_model_name in ['RandomForest', 'GradientBoosting'] and param_grid:
    print(f"\nFine-tuning {best_model_name}...")
    grid_search = GridSearchCV(
        best_model, 
        param_grid, 
        cv=3, 
        scoring='r2', 
        n_jobs=-1, 
        verbose=0
    )
    
    grid_search.fit(X_train, y_train)
    tuned_model = grid_search.best_estimator_
    tuned_score = tuned_model.score(X_test, y_test)
    
    print(f"Tuned {best_model_name} R² Score: {tuned_score:.4f}")
    print(f"Best parameters: {grid_search.best_params_}")
    
    # Use tuned model if it's better
    if tuned_score > best_score:
        best_model = tuned_model
        best_score = tuned_score
        print("Using tuned model!")


# Make predictions on test set
if best_model is not None:
    y_pred = best_model.predict(X_test)

    # Calculate final R² score
    final_r2 = r2_score(y_test, y_pred)
    print(f"\n Final Model R² Score: {final_r2:.4f}")
else:
    print("\n No model was successfully trained")
    final_r2 = 0

# Save to the correct location to replace the existing model
if best_model is not None:
    joblib.dump(best_model, "models/hybrid_emission_model.pkl")
    print(" Model saved as 'models/hybrid_emission_model.pkl'")
else:
    print(" No model to save")