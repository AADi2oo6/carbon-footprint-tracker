import pandas as pd
import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
import pickle
import os
import sys

# Add the project directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'cft'))

# Set up Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cft.settings')
import django
django.setup()

from ml_pipeline.data_extractor import get_all_user_features

def load_real_emission_factors():
    """
    Load real emission factors from the Datasets folder
    """
    dataset_dir = os.path.join(os.path.dirname(__file__), '..', 'Datasets')
    
    # Load real emission factors
    food_factors = pd.read_csv(os.path.join(dataset_dir, 'food_emission_factors.csv'))
    travel_factors = pd.read_csv(os.path.join(dataset_dir, 'travel_emission_factors.csv'))
    purchase_factors = pd.read_csv(os.path.join(dataset_dir, 'purchase_emission_factors.csv'))
    
    # Load energy data and calculate average emission factor
    energy_data = pd.read_csv(os.path.join(dataset_dir, 'energy_uci_daily.csv'))
    # Assume average electricity emission factor is around 0.39 kg CO2/kWh based on the data
    avg_energy_factor = 0.39
    
    return food_factors, travel_factors, purchase_factors, avg_energy_factor

def generate_synthetic_user_data(n_users=20000):
    """
    Generate synthetic user data based on real emission factors to create distinct clusters
    """
    print(f"Generating {n_users} synthetic users based on real emission factors...")
    
    # Load real emission factors
    food_factors, travel_factors, purchase_factors, avg_energy_factor = load_real_emission_factors()
    
    # Define cluster distributions
    cluster_distribution = {
        0: 0.4,  # 40% low impact users
        1: 0.3,  # 30% moderate transport users
        2: 0.2,  # 20% high energy users
        3: 0.1   # 10% high overall impact users
    }
    
    all_synthetic_data = []
    
    for cluster_id, proportion in cluster_distribution.items():
        n_cluster_users = int(n_users * proportion)
        print(f"Generating {n_cluster_users} users for Cluster {cluster_id}")
        
        for i in range(n_cluster_users):
            user_id = cluster_id * 10000 + i
            
            if cluster_id == 0:  # Low impact users
                # Low emissions across all categories
                total_recent_emissions = np.random.uniform(10, 150)
                recent_activities_count = np.random.randint(3, 15)
                avg_emissions_per_activity = total_recent_emissions / recent_activities_count if recent_activities_count > 0 else np.random.uniform(1, 10)
                
                # Generate category-specific emissions based on real factors but low values
                transport_emissions = np.random.uniform(0, 30)
                energy_emissions = np.random.uniform(0, 30)
                food_emissions = np.random.uniform(0, 30)
                consumption_emissions = np.random.uniform(0, 30)
                active_days = np.random.randint(1, 10)
                
            elif cluster_id == 1:  # Moderate transport users
                # Higher transport emissions, moderate in other areas
                total_recent_emissions = np.random.uniform(200, 1000)
                recent_activities_count = np.random.randint(10, 30)
                avg_emissions_per_activity = total_recent_emissions / recent_activities_count if recent_activities_count > 0 else np.random.uniform(15, 50)
                
                # Higher transport emissions based on real travel factors
                transport_emissions = np.random.uniform(100, 500)
                energy_emissions = np.random.uniform(20, 150)
                food_emissions = np.random.uniform(20, 100)
                consumption_emissions = np.random.uniform(10, 100)
                active_days = np.random.randint(5, 20)
                
            elif cluster_id == 2:  # High energy users
                # High energy consumption, moderate in other areas
                total_recent_emissions = np.random.uniform(800, 3000)
                recent_activities_count = np.random.randint(8, 25)
                avg_emissions_per_activity = total_recent_emissions / recent_activities_count if recent_activities_count > 0 else np.random.uniform(50, 200)
                
                # High energy emissions based on real energy factors
                transport_emissions = np.random.uniform(50, 300)
                energy_emissions = np.random.uniform(500, 2000)
                food_emissions = np.random.uniform(50, 200)
                consumption_emissions = np.random.uniform(50, 300)
                active_days = np.random.randint(5, 25)
                
            else:  # cluster_id == 3, High overall impact users
                # High emissions across all categories
                total_recent_emissions = np.random.uniform(2000, 10000)
                recent_activities_count = np.random.randint(20, 60)
                avg_emissions_per_activity = total_recent_emissions / recent_activities_count if recent_activities_count > 0 else np.random.uniform(100, 300)
                
                # High emissions in all categories based on real factors
                transport_emissions = np.random.uniform(500, 3000)
                energy_emissions = np.random.uniform(800, 3000)
                food_emissions = np.random.uniform(300, 1500)
                consumption_emissions = np.random.uniform(500, 3000)
                active_days = np.random.randint(10, 30)
            
            user_data = {
                'user_id': user_id,
                'total_recent_emissions': total_recent_emissions,
                'recent_activities_count': recent_activities_count,
                'avg_emissions_per_activity': avg_emissions_per_activity,
                'transport_emissions': transport_emissions,
                'energy_emissions': energy_emissions,
                'food_emissions': food_emissions,
                'consumption_emissions': consumption_emissions,
                'active_days': active_days,
            }
            all_synthetic_data.append(user_data)
    
    # Save synthetic data to CSV
    synthetic_df = pd.DataFrame(all_synthetic_data)
    model_dir = os.path.join(os.path.dirname(__file__), '..', 'ml_models')
    os.makedirs(model_dir, exist_ok=True)
    
    synthetic_data_path = os.path.join(model_dir, 'synthetic_training_data.csv')
    synthetic_df.to_csv(synthetic_data_path, index=False)
    print(f"Synthetic training data saved to: {synthetic_data_path}")
    
    return synthetic_df

def train_clustering_model():
    """
    Train a KMeans clustering model on all user features
    """
    # Extract features for all real users
    print("Extracting features for all users...")
    real_features_df = get_all_user_features()
    
    # Generate synthetic diverse user data based on real emission factors
    print("Generating synthetic user data based on real emission factors...")
    synthetic_features_df = generate_synthetic_user_data(n_users=20000)
    
    # Combine real and synthetic data
    features_df = pd.concat([real_features_df, synthetic_features_df], ignore_index=True)
    
    print(f"Combined features for {len(features_df)} users ({len(real_features_df)} real, {len(synthetic_features_df)} synthetic)")
    
    # Prepare features for clustering (exclude user_id)
    feature_columns = [col for col in features_df.columns if col != 'user_id']
    X = features_df[feature_columns]
    
    # Handle any missing values
    X = X.fillna(0)
    
    # Standardize the features
    print("Standardizing features...")
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    # Train KMeans model with 4 clusters
    print("Training KMeans model...")
    kmeans = KMeans(n_clusters=4, random_state=42, n_init=10)
    cluster_labels = kmeans.fit_predict(X_scaled)
    
    # Add cluster labels to the dataframe
    features_df['cluster_id'] = cluster_labels
    
    # Save the scaler and model
    print("Saving models...")
    model_dir = os.path.join(os.path.dirname(__file__), '..', 'ml_models')
    os.makedirs(model_dir, exist_ok=True)
    
    # Save scaler
    scaler_path = os.path.join(model_dir, 'scaler.pkl')
    with open(scaler_path, 'wb') as f:
        pickle.dump(scaler, f)
    
    # Save KMeans model
    kmeans_path = os.path.join(model_dir, 'kmeans.pkl')
    with open(kmeans_path, 'wb') as f:
        pickle.dump(kmeans, f)
    
    # Save user clusters to CSV (only real users)
    user_clusters_path = os.path.join(model_dir, 'user_clusters.csv')
    real_users_df = features_df[features_df['user_id'] < 10000]  # Assuming real user IDs are < 10000
    real_users_df[['user_id', 'cluster_id']].to_csv(user_clusters_path, index=False)
    
    print(f"Model training completed!")
    print(f"Scaler saved to: {scaler_path}")
    print(f"KMeans model saved to: {kmeans_path}")
    print(f"User clusters saved to: {user_clusters_path}")
    
    # Print cluster statistics
    print("\nCluster Statistics:")
    for i in range(4):
        count = sum(cluster_labels == i)
        print(f"  Cluster {i}: {count} users")

if __name__ == "__main__":
    train_clustering_model()