import pandas as pd
from django.contrib.auth.models import User
from django.db.models import Sum, Count
from datetime import datetime, timedelta
import sys
import os

# Add the project directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'cft'))

# Now we can import the models
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'cft.settings')
import django
django.setup()

from tracker.models import Activity, Emission

def get_user_features(user):
    """
    Extract features for a single user based on their activities and emissions
    Returns a dictionary of features
    """
    # Get all activities for the user
    user_activities = Activity.objects.filter(user=user)
    user_emissions = Emission.objects.filter(activity__user=user)
    
    # Feature 1: Total emissions in the last 30 days
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_emissions = user_emissions.filter(
        activity__timestamp__gte=thirty_days_ago
    ).aggregate(total=Sum('co2_equivalent_kg'))['total']
    total_recent_emissions = recent_emissions if recent_emissions else 0
    
    # Feature 2: Number of activities in the last 30 days
    recent_activities_count = user_activities.filter(
        timestamp__gte=thirty_days_ago
    ).count()
    
    # Feature 3: Average emissions per activity
    avg_emissions_per_activity = 0
    if recent_activities_count > 0:
        avg_emissions_per_activity = total_recent_emissions / recent_activities_count
    
    # Feature 4: Emissions by category (last 30 days)
    category_emissions = user_emissions.filter(
        activity__timestamp__gte=thirty_days_ago
    ).values('activity__category').annotate(
        total=Sum('co2_equivalent_kg')
    )
    
    # Initialize category features
    transport_emissions = 0
    energy_emissions = 0
    food_emissions = 0
    consumption_emissions = 0
    
    # Assign emissions to categories
    for item in category_emissions:
        category = item['activity__category']
        total = item['total'] if item['total'] else 0
        
        if category == 'transport':
            transport_emissions = total
        elif category == 'energy':
            energy_emissions = total
        elif category == 'food':
            food_emissions = total
        elif category == 'consumption':
            consumption_emissions = total
    
    # Feature 5: Days with activities (consistency)
    active_days = user_activities.filter(
        timestamp__gte=thirty_days_ago
    ).dates('timestamp', 'day').count()
    
    # Compile features into a dictionary
    features = {
        'user_id': user.id,
        'total_recent_emissions': total_recent_emissions,
        'recent_activities_count': recent_activities_count,
        'avg_emissions_per_activity': avg_emissions_per_activity,
        'transport_emissions': transport_emissions,
        'energy_emissions': energy_emissions,
        'food_emissions': food_emissions,
        'consumption_emissions': consumption_emissions,
        'active_days': active_days,
    }
    
    return features

def get_all_user_features():
    """
    Extract features for all users in the system
    Returns a pandas DataFrame with user features
    """
    # Get all users
    all_users = User.objects.all()
    
    # Collect features for all users
    features_list = []
    
    for user in all_users:
        user_features = get_user_features(user)
        features_list.append(user_features)
    
    # Convert to DataFrame
    features_df = pd.DataFrame(features_list)
    
    return features_df