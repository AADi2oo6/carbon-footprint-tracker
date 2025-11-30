from pygooglenews import GoogleNews
from datetime import datetime
import time
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, get_user_model, decorators, forms as auth_forms
from django.contrib import messages
from django.http import JsonResponse
from django.db.models import Sum
from django.db import models
from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm, ChallengeForm
from .models import Profile, Activity, Emission, Community, Challenge, UserChallenge, User, UserAchievement
import json
from datetime import date, timedelta
import random
from .map_assets.map_generator import generate_india_heatmap_from_profiles
import requests
import os
import pickle
import sys
import pandas as pd
from sklearn.preprocessing import StandardScaler

# Add the project directory to the Python path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

# Import the data extractor module
from ml_pipeline.data_extractor import get_user_features

def get_user_summary_data(user):
    """
    Calculates the summary data (this month's emissions, last month's, and improvement)
    for a given user.
    """
    today = date.today()
    this_month_start = today.replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    # Get total emissions for the current month
    this_month_emissions = Emission.objects.filter(
        activity__user=user, 
        activity__timestamp__gte=this_month_start
    ).aggregate(total=Sum('co2_equivalent_kg'))['total'] or 0

    # Get total emissions for the previous month
    last_month_emissions = Emission.objects.filter(
        activity__user=user,
        activity__timestamp__gte=last_month_start,
        activity__timestamp__lte=last_month_end
    ).aggregate(total=Sum('co2_equivalent_kg'))['total'] or 0
    
    # Calculate the percentage improvement
    improvement = 0
    if last_month_emissions > 0:
        # Improvement is the reduction from last month
        improvement = round(((last_month_emissions - this_month_emissions) / last_month_emissions) * 100)
    
    return {
        'this_month': round(this_month_emissions / 1000, 1), # Convert kg to tons
        'last_month': round(last_month_emissions / 1000, 1), # Convert kg to tons
        'improvement': improvement,
    }


# --- (register view remains the same) ---
def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f"Welcome, {user.first_name}! Your account has been created.")
            return redirect('tracker-home')
    else:
        form = UserRegisterForm()
    return render(request, 'tracker/register.html', {'form': form})

# --- HELPER FUNCTION FOR RANKING ---
def get_leaderboard_and_rank(current_user=None):
    thirty_days_ago = date.today() - timedelta(days=30)
    all_users = User.objects.all()
    leaderboard_data = []

    for user in all_users:
        emissions = Emission.objects.filter(
            activity__user=user,
            activity__timestamp__gte=thirty_days_ago
        ).aggregate(total=Sum('co2_equivalent_kg'))

        total_emissions = emissions['total'] or 0
        leaderboard_data.append({
            'user_id': user.id,
            'username': user.username,
            'emission': total_emissions,
        })

    # Sort by emissions (lowest first), users with 0 at the end
    leaderboard_data.sort(key=lambda x: (x['emission'] == 0, x['emission']))

    user_rank = "N/A"
    if current_user:
        for i, data in enumerate(leaderboard_data):
            if data['user_id'] == current_user.id:
                user_rank = i + 1
                break

    total_users = len(leaderboard_data)

    # Format for the leaderboard
    leaderboard = []
    for i, data in enumerate(leaderboard_data[:5]):  # Get top 5
        rank_icon = '🏆'
        if i == 0: rank_icon = '🥇'
        elif i == 1: rank_icon = '🥈'
        elif i == 2: rank_icon = '🥉'
        else: rank_icon = f'{i+1}'

        leaderboard.append({
            'rank_icon': rank_icon,
            'user': data['username'],
            'emission': f"{data['emission']:.1f} kg",
            'reduction': 'N/A'
        })

    # New: Compose a dict for rank out of total, used by the profile page
    ranking_data = {
        "city": {"rank": "N/A", "total": "N/A"},
        "state": {"rank": "N/A", "total": "N/A"},
        "country": {"rank": user_rank, "total": total_users}
    }

    # Default return is compatible: leaderboard, user_rank, ranking_data for profile use
    return leaderboard, user_rank, ranking_data


@decorators.login_required
def myprofile(request):
    Profile.objects.get_or_create(user=request.user)

    if request.method == 'POST':
        u_form = UserUpdateForm(request.POST, instance=request.user)
        p_form = ProfileUpdateForm(request.POST, instance=request.user.profile)
        if u_form.is_valid() and p_form.is_valid():
            u_form.save()
            p_form.save()
            messages.success(request, 'Your profile has been updated successfully!')
            return redirect('myprofile')
    else:
        u_form = UserUpdateForm(instance=request.user)
        p_form = ProfileUpdateForm(instance=request.user.profile)

    today = date.today()
    start_of_month = today.replace(day=1)
    
    monthly_emissions = Emission.objects.filter(
        activity__user=request.user, 
        activity__timestamp__gte=start_of_month
    ).aggregate(total=Sum('co2_equivalent_kg'))
    total_footprint_this_month = monthly_emissions['total'] or 0

    # We assume get_leaderboard_and_rank is defined elsewhere in this file
    _, user_rank, _ = get_leaderboard_and_rank(request.user) # Get current user's rank

    # --- UPDATED: Pie chart now shows all-time data breakdown ---
    category_data_query = Emission.objects.filter(activity__user=request.user).values('activity__category').annotate(total=Sum('co2_equivalent_kg'))
    category_data = {'labels': [item['activity__category'].capitalize() for item in category_data_query], 'data': [item['total'] for item in category_data_query]}
    
    trends_data = {'labels': [], 'data': []}
    for i in range(5, -1, -1):
        month_start = (today.replace(day=1) - timedelta(days=i*30)).replace(day=1)
        month_end = (month_start + timedelta(days=35)).replace(day=1) - timedelta(days=1)
        month_emissions = Emission.objects.filter(activity__user=request.user, activity__timestamp__range=[month_start, month_end]).aggregate(total=Sum('co2_equivalent_kg'))
        trends_data['labels'].append(month_start.strftime("%b %Y"))
        trends_data['data'].append(round(month_emissions['total'] or 0, 2))
        
    user_budget = request.user.profile.carbon_budget_kg
    carbon_budget = {'limit': user_budget, 'used': round(total_footprint_this_month, 2), 'percentage': min(100, round((total_footprint_this_month / user_budget) * 100)) if user_budget > 0 else 100}
    
    actionable_insights = [{"text": "Switching one car trip to public transit could save ~15kg CO₂e.", "icon": "fas fa-bus"}]
    
    active_days = Activity.objects.filter(user=request.user).dates('timestamp', 'day')
    streak_data_for_chart = {"active_days": [d.strftime("%Y-%m-%d") for d in active_days]}

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'total_footprint_this_month': round(total_footprint_this_month, 2),
        'ranking_data': user_rank, 
        'category_data_json': json.dumps(category_data),
        'trends_data_json': json.dumps(trends_data),
        'streak_data_json': json.dumps(streak_data_for_chart),
        'carbon_budget': carbon_budget,
        'actionable_insights': actionable_insights,
    }
    return render(request, 'tracker/myprofile.html', context)

def home(request):
    today = date.today()
    selected_date_str = request.GET.get('dateFilter', today.strftime("%Y-%m-%d"))
    selected_category = request.GET.get('categoryFilter', 'all')

    # --- NEW: Fetch emissions data for charts ---
    # Base query for user's emissions
    base_query = Activity.objects.filter(user=request.user)
    
    # Apply filters if they exist
    if selected_date_str:
        selected_date = datetime.strptime(selected_date_str, "%Y-%m-%d").date()
        base_query = base_query.filter(timestamp__date=selected_date)
        
    if selected_category != 'all':
        base_query = base_query.filter(category=selected_category)

    # Get emissions for the selected criteria
    activities_with_emissions = base_query.select_related('emission').order_by('-timestamp')
    
    # --- NEW: Summary Stats ---
    # Today
    today_start = today
    today_emissions = base_query.filter(timestamp__date=today_start).aggregate(total=Sum('emission__co2_equivalent_kg'))['total'] or 0

    # Yesterday
    yesterday = today - timedelta(days=1)
    yesterday_emissions = base_query.filter(timestamp__date=yesterday).aggregate(total=Sum('emission__co2_equivalent_kg'))['total'] or 0

    # This Month
    this_month_start = today.replace(day=1)
    this_month_emissions = base_query.filter(timestamp__date__gte=this_month_start).aggregate(total=Sum('emission__co2_equivalent_kg'))['total'] or 0

    # Last Month
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)
    last_month_emissions = base_query.filter(timestamp__date__gte=last_month_start, timestamp__date__lte=last_month_end).aggregate(total=Sum('emission__co2_equivalent_kg'))['total'] or 0

    # --- NEW: Carbon Budget Calculation ---
    # Using hardcoded limits for now. In a real app, these would be user-configurable.
    daily_limit = 15 # kg CO2e
    monthly_limit = 450 # kg CO2e
    
    daily_budget_percentage = round((today_emissions / daily_limit) * 100) if daily_limit > 0 else 0
    monthly_budget_percentage = round((this_month_emissions / monthly_limit) * 100) if monthly_limit > 0 else 0

    # --- NEW: Location-based events ---
    # Get the user's location from their profile, default to "Delhi" if not set
    try:
        search_location = request.user.profile.location or "Delhi"
    except:
        search_location = "Delhi"
    
    # --- NEW: AI-powered daily tip ---
    ai_tip_content = "Log activities regularly to track your carbon footprint accurately."
    try:
        # Make a request to the n8n webhook
        response = requests.post(
            'https://n8n-cft-production.up.railway.app/webhook/cft-daily-tip',
            json={"user_id": request.user.id},
            timeout=5  # Don't hang the page load if n8n is slow/unavailable
        )
        if response.status_code == 200:
            ai_response = response.json()
            ai_tip_content = ai_response.get("tip", ai_tip_content)
    except requests.exceptions.RequestException as e:
        # If n8n is down or there's a network error, we just log it and use the default tip
        print(f"Could not connect to n8n workflow: {e}")
    
    # Get KMeans clustering insights
    cluster_id = 1  # Default cluster
    eco_tip = "Keep up the good work on reducing your carbon footprint!"  # Default tip
    dynamic_suggestions = []  # Default empty suggestions
    
    try:
        # Try to get insights from our ML API
        from ml_pipeline.data_extractor import get_user_features
        from sklearn.preprocessing import StandardScaler
        import pickle
        import os
        import pandas as pd
        
        # Extract features for the current user
        user_features = get_user_features(request.user)
        
        # Prepare features for prediction (exclude user_id)
        feature_columns = [col for col in user_features.keys() if col != 'user_id']
        user_feature_values = [user_features[col] for col in feature_columns]
        
        # Convert to DataFrame for consistency with training
        X = pd.DataFrame([user_feature_values], columns=feature_columns)
        
        # Handle any missing values
        X = X.fillna(0)
        
        # Load the scaler and model
        model_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'ml_models')
        
        scaler_path = os.path.join(model_dir, 'scaler.pkl')
        kmeans_path = os.path.join(model_dir, 'kmeans.pkl')
        
        if os.path.exists(scaler_path) and os.path.exists(kmeans_path):
            with open(scaler_path, 'rb') as f:
                scaler = pickle.load(f)
            
            with open(kmeans_path, 'rb') as f:
                kmeans = pickle.load(f)
            
            # Scale the features
            X_scaled = scaler.transform(X)
            
            # Predict cluster
            cluster_id = int(kmeans.predict(X_scaled)[0])
            
            # Get cluster center for this cluster and inverse transform it
            cluster_centers_scaled = kmeans.cluster_centers_
            cluster_center_scaled = cluster_centers_scaled[cluster_id].reshape(1, -1)
            cluster_center_unscaled = scaler.inverse_transform(cluster_center_scaled)
            
            # Convert cluster center to dictionary
            cluster_center_dict = {}
            for i, col in enumerate(feature_columns):
                cluster_center_dict[col] = float(cluster_center_unscaled[0][i])
            
            # Generate dynamic suggestions
            dynamic_suggestions = calculate_dynamic_suggestions(user_features, cluster_center_dict, cluster_id)
            
            # For backward compatibility, keep the old eco_tip format
            eco_tips = {
                0: "You're doing great! Try reducing meat consumption for even better results.",
                1: "Good effort! Consider using public transportation more often.",
                2: "You're making progress! Focus on reducing energy consumption at home.",
                3: "Keep going! Small changes in daily habits can make a big difference."
            }
            
            # Get the appropriate eco tip
            eco_tip = eco_tips.get(cluster_id, "Keep up the good work on reducing your carbon footprint!")
        else:
            print("Model files not found!")
    except Exception as e:
        print(f"Error getting clustering insights: {e}")
        import traceback
        traceback.print_exc()
        # Use default values if there's an error

    total_users = User.objects.count()
    country_comparison = {'user_country_name': 'India', 'user_country_flag': 'https://flagcdn.com/w40/in.png', 'user_value': 1.9, 'global_value': 4.7}
    max_val = max(country_comparison['user_value'], country_comparison['global_value'], 1) * 1.1
    country_comparison['user_percentage'] = (country_comparison['user_value'] / max_val) * 100
    country_comparison['global_percentage'] = (country_comparison['global_value'] / max_val) * 100

    # --- REAL RECENT BADGES ---
    recent_badges_query = UserAchievement.objects.order_by('-date_earned')[:3]
    recent_badges = [{'icon': b.achievement.icon, 'name': b.achievement.name} for b in recent_badges_query]
    if not recent_badges:
        recent_badges = [{'icon': '🌟', 'name': 'Welcome!'}]

    # --- REAL LEADERBOARD & RANK ---
    leaderboard, user_rank,_ = get_leaderboard_and_rank(request.user if request.user.is_authenticated else None)

     # --- NEW: GENERATE THE HEATMAP ---
    # 1. Get all user profiles that have a location defined
    all_profiles_with_location = Profile.objects.filter(location__isnull=False).exclude(location__exact='')
    # 2. Call the map generator function with the profile data
    india_map_html = generate_india_heatmap_from_profiles(all_profiles_with_location)

    local_events = []
    try:
        gn = GoogleNews(lang='en', country='IN')
        news = gn.search(f"({search_location}) AND (tree plantation OR cleanliness drive OR environment OR sustainable OR eco-friendly)")
        
        # Loop through the top 5 entries
        for entry in news['entries'][:5]:
            # Convert the published date into a more readable format
            published_datetime = datetime.fromtimestamp(time.mktime(entry.published_parsed))
            
            local_events.append({
                'title': entry.title,
                'link': entry.link,
                'published': published_datetime.strftime('%d %b, %Y')
            })
            
    except Exception as e:
        print(f"Could not fetch Google News: {e}")
        # If the search fails, the local_events list will remain empty.


    emissions_breakdown = {
        'labels': ['Transport', 'Housing', 'Food', 'Shopping'],
        'data': [40, 35, 15, 10],
        'colors': ['#EF4444', '#F59E0B', '#10B981', '#3B82F6'],
    }
    context = {
        'global_stats': {'totalUsers': total_users, 'co2Saved': 847, 'countriesCount': 67},
        'country_comparison': country_comparison,
        'recent_badges': recent_badges,
        'leaderboard': leaderboard,
        'summary_data': {'this_month': round(this_month_emissions, 2), 'last_month': round(last_month_emissions, 2), 'improvement': round(last_month_emissions, 2)-round(this_month_emissions, 2), 'rank': user_rank}, # Use real rank

        'emissions_table_data': zip(
        emissions_breakdown['labels'],
        emissions_breakdown['data'],
        emissions_breakdown['colors']),
        'emissions_data_json': json.dumps({'labels': [], 'data': []}),
        'daily_challenge': {'text': 'Log your first activity!', 'impact': ''},
        'insights': {
            'tip': {'icon': '💡', 'title': "Today's Eco Tip", 'content':ai_tip_content , 'impact': 'Potential save: 2.3kg CO2'},
            'weather': {'icon': '☀️', 'title': "Weather Advice", 'content': 'Perfect day for cycling!', 'impact': 'Air quality: Good'},
        },
        # Pass the new list of events to the template
        'local_events': local_events,
        'india_map_html': india_map_html,
        # Pass clustering insights
        'cluster_id': cluster_id,
        'eco_tip': eco_tip,
        'dynamic_suggestions': dynamic_suggestions,  # New dynamic suggestions
    }
    return render(request, 'tracker/home.html', context)

@decorators.login_required
def activity(request):
    """
    Renders the activity logging page, handles form submissions for new activities,
    and manages the activity history display, filtering, editing, and deletion.
    """
    if request.method == 'POST':
        is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        # FIX: Build redirect URL from GET params if available, otherwise default.
        # This ensures redirects work for all POST actions (create, update, delete).
        date_filter_for_redirect = request.GET.get('dateFilter', date.today().strftime("%Y-%m-%d"))
        category_filter_for_redirect = request.GET.get('categoryFilter', 'all')
        redirect_url = f"{request.path}?dateFilter={date_filter_for_redirect}&categoryFilter={category_filter_for_redirect}"


        action = request.POST.get('action')

        # Handle activity UPDATES
        if action == 'update':
            try:
                activity_id = request.POST.get('activity_id')
                activity_to_update = Activity.objects.get(id=activity_id, user=request.user)
                
                # For simplicity, we're only allowing the footprint and description to be edited.
                # A more complex implementation might re-calculate based on new value/unit.
                new_footprint_val = float(request.POST.get('footprint'))
                new_description = request.POST.get('description')

                activity_to_update.description = new_description
                activity_to_update.emission.co2_equivalent_kg = round(new_footprint_val, 2)
                activity_to_update.emission.save()
                activity_to_update.save()
                if is_ajax:
                    return JsonResponse({'success': True, 'activity': {'id': activity_to_update.id, 'description': new_description, 'footprint': new_footprint_val}})
                else:
                    messages.success(request, 'Activity updated successfully!')
            except (Activity.DoesNotExist, ValueError, TypeError):
                error_message = 'There was an error updating the activity.'
                if is_ajax: return JsonResponse({'success': False, 'error': error_message})
                else: messages.error(request, error_message)
            return redirect(redirect_url)

        # Handle activity DELETION
        if action == 'delete':
            try:
                activity_id = request.POST.get('activity_id')
                activity_to_delete = Activity.objects.get(id=activity_id, user=request.user)
                activity_to_delete.delete()
                if is_ajax:
                    return JsonResponse({'success': True, 'deleted_id': activity_id})
                else:
                    messages.success(request, 'Activity deleted successfully!')
            except Activity.DoesNotExist:
                error_message = 'Activity not found or you do not have permission to delete it.'
                if is_ajax: return JsonResponse({'success': False, 'error': error_message})
                else: messages.error(request, error_message)
            return redirect(redirect_url)

        # Handle activity CREATION (existing logic)
        category = request.POST.get('category')
        
        # Import the emission factor functions that use real datasets
        from emission_factors import get_energy_co2, get_food_co2, get_travel_co2, get_purchase_co2

        try:
            if category == 'transport':
                mode = request.POST.get('transportMode')
                distance = float(request.POST.get('distance'))
                # Use real emission factors from datasets
                footprint = get_travel_co2(mode, distance)
                description = f"Travel: {mode.replace('-', ' ').title()} - {distance} km"
                new_activity = Activity.objects.create(user=request.user, category='transport', description=description, value=distance, unit='km')
            
            elif category == 'energy':
                units = float(request.POST.get('electricityUnits'))
                # Use real emission factors from datasets
                footprint = get_energy_co2("electricity", units)
                description = f"Energy: Manual Entry - {units} kWh"
                new_activity = Activity.objects.create(user=request.user, category='energy', description=description, value=units, unit='kWh')

            elif category == 'food':
                diet_type = request.POST.get('dietType')
                quantity = float(request.POST.get('foodQuantity', 1))
                # Use real emission factors from datasets
                footprint = get_food_co2(diet_type, quantity)
                description = f"Food: {diet_type.replace('-', ' ').title()} ({quantity} servings)"
                new_activity = Activity.objects.create(user=request.user, category='food', description=description, value=quantity, unit='serving')

            elif category == 'consumption':
                purchase_cat = request.POST.get('purchaseCategory')
                amount = float(request.POST.get('purchaseAmount'))
                # Convert INR to a USD-equivalent for consistent emission factor application
                # Using an approximate conversion rate (e.g., 1 USD = 83 INR)
                INR_TO_USD_RATE = 1 / 83 
                amount_in_usd_equivalent = amount * INR_TO_USD_RATE
                # Use real emission factors from datasets
                footprint = get_purchase_co2(purchase_cat, amount_in_usd_equivalent)
                description = f"Purchase: {purchase_cat.replace('-', ' ').title()} - ₹{amount:,.2f}"
                new_activity = Activity.objects.create(user=request.user, category='consumption', description=description, value=amount, unit='INR')
            
            # Common emission creation for all new activities
            final_footprint = round(footprint, 2)
            Emission.objects.create(activity=new_activity, co2_equivalent_kg=final_footprint)

            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'activity': {
                        'id': new_activity.id,
                        'category': new_activity.category,
                        'category_display': new_activity.get_category_display(),
                        'description': new_activity.description,
                        'date': new_activity.timestamp.strftime('%Y-%m-%d'),
                        'footprint': final_footprint,
                    }
                })
            else:
                messages.success(request, 'Activity logged successfully!')

        except (ValueError, TypeError):
            error_message = 'Invalid data submitted. Please check your inputs.'
            if is_ajax:
                return JsonResponse({'success': False, 'error': error_message})
            else:
                messages.error(request, error_message)
        
        return redirect(redirect_url)

    # --- GET request logic ---
    # Filtering
    today = date.today()
    selected_date_str = request.GET.get('dateFilter', today.strftime("%Y-%m-%d"))
    selected_category = request.GET.get('categoryFilter', 'all')

    try:
        selected_date = date.fromisoformat(selected_date_str)
        activities = Activity.objects.filter(user=request.user, timestamp__date=selected_date).order_by('-timestamp')
        if selected_category != 'all':
            activities = activities.filter(category=selected_category)
    except (ValueError, TypeError):
        selected_date_str = today.strftime("%Y-%m-%d")
        activities = Activity.objects.none()
        messages.error(request, "Invalid date format provided.")

    # --- NEW: Calculate emission stats ---
    from django.db.models import Sum
    yesterday = today - timedelta(days=1)

    # Create a new base query for calculating stats that ignores the date/category filters
    base_query = Activity.objects.filter(user=request.user)
    
    # Today and Yesterday's totals
    today_emissions = base_query.filter(timestamp__date=today).aggregate(total=Sum('emission__co2_equivalent_kg'))['total'] or 0
    yesterday_emissions = base_query.filter(timestamp__date=yesterday).aggregate(total=Sum('emission__co2_equivalent_kg'))['total'] or 0

    # Monthly totals
    this_month_start = today.replace(day=1)
    last_month_end = this_month_start - timedelta(days=1)
    last_month_start = last_month_end.replace(day=1)

    this_month_emissions = base_query.filter(timestamp__date__gte=this_month_start).aggregate(total=Sum('emission__co2_equivalent_kg'))['total'] or 0
    last_month_emissions = base_query.filter(timestamp__date__gte=last_month_start, timestamp__date__lte=last_month_end).aggregate(total=Sum('emission__co2_equivalent_kg'))['total'] or 0

    # --- NEW: Carbon Budget Calculation ---
    # Using hardcoded limits for now. In a real app, these would be user-configurable.
    daily_limit = 15 # kg CO2e
    monthly_limit = 450 # kg CO2e
    
    daily_budget_percentage = round((today_emissions / daily_limit) * 100) if daily_limit > 0 else 0
    monthly_budget_percentage = round((this_month_emissions / monthly_limit) * 100) if monthly_limit > 0 else 0

    context = {
        'today_str': today.strftime("%Y-%m-%d"), # For default value in date picker
        'yesterday_str': yesterday.strftime("%Y-%m-%d"),
        'activities': activities,
        'selected_date': selected_date_str,
        'selected_category': selected_category,
        'emission_stats': {
            'today': round(today_emissions, 2),
            'yesterday': round(yesterday_emissions, 2),
            'this_month': round(this_month_emissions, 2),
            'last_month': round(last_month_emissions, 2),
        },
        'daily_budget': {
            'used': round(today_emissions, 2),
            'limit': daily_limit,
            'percentage': min(daily_budget_percentage, 100) # Cap at 100% for visual
        },
        'monthly_budget': {
            'used': round(this_month_emissions, 2),
            'limit': monthly_limit,
            'percentage': min(monthly_budget_percentage, 100) # Cap at 100% for visual
        }
    }
    return render(request, 'tracker/activity.html', context)

@decorators.login_required
def community_view(request):
    """
    Displays a list of all communities.
    Separates them into communities the user has joined and those they haven't.
    """
    all_communities = Community.objects.annotate(member_count=models.Count('members')).order_by('-member_count', 'name')
    user_communities = request.user.communities.annotate(member_count=models.Count('members')).order_by('name')
    
    # Get a list of community IDs the user is a member of for easy checking in the template
    user_community_ids = list(user_communities.values_list('id', flat=True))

    context = {
        'all_communities': all_communities, # For the main list
        'user_communities': user_communities,
        'user_community_ids': user_community_ids,
    }
    return render(request, 'tracker/community.html', context)

@decorators.login_required
def community_detail_view(request, pk):
    community = Community.objects.get(pk=pk)
    context = {'community': community}
    return render(request, 'tracker/community_detail.html', context)

@decorators.login_required
def challenges_view(request):
    """
    Displays a list of all challenges from all communities.
    Separates them into active and completed challenges.
    """
    if request.method == 'POST':
        # This part handles the form submission for creating a new challenge
        form = ChallengeForm(request.POST)
        if form.is_valid():
            # Ensure the creator is a member of the community they are creating a challenge for
            community = form.cleaned_data['community']
            if request.user in community.members.all():
                form.save()
                messages.success(request, 'New challenge has been created successfully!')
            else:
                messages.error(request, 'You can only create challenges for communities you are a member of.')
            return redirect('challenges')
        # If form is invalid, it will fall through and be re-rendered with errors

    today = date.today()
    active_challenges = Challenge.objects.filter(end_date__gte=today).select_related('community').order_by('end_date')
    completed_challenges = Challenge.objects.filter(end_date__lt=today).select_related('community').order_by('-end_date')

    joined_challenges = []
    if request.user.is_authenticated:
        # Get the user's progress for all challenges they've joined
        user_challenges_progress = {
            uc.challenge_id: uc for uc in UserChallenge.objects.filter(user=request.user)
        }

        # Attach user-specific data directly to each active challenge object
        for challenge in active_challenges:
            user_challenge = user_challenges_progress.get(challenge.id)
            if user_challenge:
                challenge.user_progress = user_challenge.progress
                challenge.is_joined = True
                challenge.is_completed = user_challenge.is_completed
                challenge.progress_percentage = min(round((user_challenge.progress / challenge.goal) * 100), 100) if challenge.goal > 0 else 0
            else:
                challenge.is_joined = False
            if challenge.is_joined:
                joined_challenges.append(challenge)

    # Prepare the form for the GET request
    challenge_form = ChallengeForm()
    if request.user.is_authenticated:
        challenge_form.fields['community'].queryset = request.user.communities.all()

    context = {
        'active_challenges': active_challenges,
        'completed_challenges': completed_challenges,
        'joined_challenges': joined_challenges,
        'challenge_form': challenge_form,
    }
    return render(request, 'tracker/challenges.html', context)

@decorators.login_required
def join_community(request, pk):
    if request.method == 'POST':
        community = get_object_or_404(Community, pk=pk)
        community.members.add(request.user)
        messages.success(request, f"You have successfully joined the {community.name} community!")
    return redirect('community')

@decorators.login_required
def leave_community(request, pk):
    if request.method == 'POST':
        community = get_object_or_404(Community, pk=pk)
        community.members.remove(request.user)
        messages.success(request, f"You have left the {community.name} community.")
    return redirect('community')

@decorators.login_required
def join_challenge(request, pk):
    if request.method == 'POST':
        challenge = get_object_or_404(Challenge, pk=pk)
        # Create a UserChallenge entry if it doesn't exist
        UserChallenge.objects.get_or_create(user=request.user, challenge=challenge)
        messages.success(request, f"You have joined the challenge: {challenge.title}!")
    return redirect('challenges')

def calculate_dynamic_suggestions(user_features, cluster_center, cluster_id):
    """
    Generate dynamic, personalized CO₂-reduction suggestions based on user features and cluster center
    """
    suggestions = []
    
    # Define emission factors (kg CO2e per unit)
    emission_factors = {
        'transport': 0.15,  # Average for various transport modes (kg/km)
        'energy': 0.39,     # Electricity (kg/kWh)
        'food': 2.5,        # Average for various foods (kg/meal)
        'consumption': 0.2  # Average for purchases (kg/USD, converted from INR)
    }
    
    # Convert INR to USD for consumption calculations
    inr_to_usd_rate = 1 / 83
    
    # Compare user features with cluster center to generate suggestions
    
    # 1. Transport emissions comparison
    user_transport = user_features.get('transport_emissions', 0)
    cluster_transport = cluster_center.get('transport_emissions', 0)
    transport_diff = user_transport - cluster_transport
    
    # Always provide suggestions for high transport emissions, regardless of cluster comparison
    if user_transport > 50:  # If user has significant transport emissions
        # Calculate potential savings
        potential_km_reduction = user_transport * 0.2  # Suggest 20% reduction
        potential_savings = potential_km_reduction * emission_factors['transport']
        
        suggestions.append({
            "type": "transport",
            "message": f"Consider using public transport for {potential_km_reduction:.0f} km to save {potential_savings:.1f} kg CO₂.",
            "savings_kg": round(potential_savings, 2),
            "action": "travel_less"
        })
    elif transport_diff > 0 and cluster_transport > 0:
        # User has higher transport emissions than cluster average
        transport_ratio = transport_diff / cluster_transport
        if transport_ratio > 0.1:  # More than 10% above cluster
            # Calculate potential savings
            potential_km_reduction = transport_diff / emission_factors['transport']
            potential_savings = transport_diff
            
            suggestions.append({
                "type": "transport",
                "message": f"Reduce car travel by {potential_km_reduction:.0f} km to save {potential_savings:.1f} kg CO₂.",
                "savings_kg": round(potential_savings, 2),
                "action": "travel_less"
            })
        else:
            suggestions.append({
                "type": "transport",
                "message": "Your travel emissions are already close to cluster average—good job!",
                "savings_kg": 0,
                "action": "maintain"
            })
    elif transport_diff <= 0 and cluster_transport > 0:
        suggestions.append({
            "type": "transport",
            "message": "Your travel emissions are already below cluster average—great job!",
            "savings_kg": 0,
            "action": "maintain"
        })
    else:
        suggestions.append({
            "type": "transport",
            "message": "No transport data available for comparison.",
            "savings_kg": 0,
            "action": "no_data"
        })
    
    # 2. Energy emissions comparison
    user_energy = user_features.get('energy_emissions', 0)
    cluster_energy = cluster_center.get('energy_emissions', 0)
    energy_diff = user_energy - cluster_energy
    
    # Always provide suggestions for high energy emissions
    if user_energy > 200:  # If user has significant energy emissions
        # Calculate potential savings
        potential_kwh_reduction = user_energy * 0.15  # Suggest 15% reduction
        potential_savings = potential_kwh_reduction * emission_factors['energy']
        
        suggestions.append({
            "type": "energy",
            "message": f"Reduce energy use by {potential_kwh_reduction:.0f} kWh to save {potential_savings:.1f} kg CO₂.",
            "savings_kg": round(potential_savings, 2),
            "action": "save_energy"
        })
    elif energy_diff > 0 and cluster_energy > 0:
        energy_ratio = energy_diff / cluster_energy
        if energy_ratio > 0.1:  # More than 10% above cluster
            # Calculate potential savings
            potential_kwh_reduction = energy_diff / emission_factors['energy']
            potential_savings = energy_diff
            
            suggestions.append({
                "type": "energy",
                "message": f"Reduce energy use by {potential_kwh_reduction:.0f} kWh to save {potential_savings:.1f} kg CO₂.",
                "savings_kg": round(potential_savings, 2),
                "action": "save_energy"
            })
        else:
            suggestions.append({
                "type": "energy",
                "message": "Your energy emissions are already close to cluster average—good job!",
                "savings_kg": 0,
                "action": "maintain"
            })
    elif energy_diff <= 0 and cluster_energy > 0:
        suggestions.append({
            "type": "energy",
            "message": "Your energy emissions are already below cluster average—great job!",
            "savings_kg": 0,
            "action": "maintain"
        })
    else:
        suggestions.append({
            "type": "energy",
            "message": "No energy data available for comparison.",
            "savings_kg": 0,
            "action": "no_data"
        })
    
    # 3. Food emissions comparison
    user_food = user_features.get('food_emissions', 0)
    cluster_food = cluster_center.get('food_emissions', 0)
    food_diff = user_food - cluster_food
    
    # Always provide suggestions for high food emissions
    if user_food > 100:  # If user has significant food emissions
        # Calculate potential savings
        potential_meals_reduction = user_food / emission_factors['food'] * 0.2  # Suggest reducing 20% of meals
        potential_savings = potential_meals_reduction * emission_factors['food']
        
        suggestions.append({
            "type": "food",
            "message": f"Replace {potential_meals_reduction:.0f} high-emission meals this week to save {potential_savings:.1f} kg CO₂.",
            "savings_kg": round(potential_savings, 2),
            "action": "eat_less_meat"
        })
    elif food_diff > 0 and cluster_food > 0:
        food_ratio = food_diff / cluster_food
        if food_ratio > 0.1:  # More than 10% above cluster
            # Calculate potential savings
            potential_meals_reduction = food_diff / emission_factors['food']
            potential_savings = food_diff
            
            suggestions.append({
                "type": "food",
                "message": f"Replace {potential_meals_reduction:.0f} high-emission meals this week to save {potential_savings:.1f} kg CO₂.",
                "savings_kg": round(potential_savings, 2),
                "action": "eat_less_meat"
            })
        else:
            suggestions.append({
                "type": "food",
                "message": "Your food emissions are already close to cluster average—good job!",
                "savings_kg": 0,
                "action": "maintain"
            })
    elif food_diff <= 0 and cluster_food > 0:
        suggestions.append({
            "type": "food",
            "message": "Your food emissions are already below cluster average—great job!",
            "savings_kg": 0,
            "action": "maintain"
        })
    else:
        suggestions.append({
            "type": "food",
            "message": "No food data available for comparison.",
            "savings_kg": 0,
            "action": "no_data"
        })
    
    # 4. Consumption emissions comparison
    user_consumption = user_features.get('consumption_emissions', 0)
    cluster_consumption = cluster_center.get('consumption_emissions', 0)
    consumption_diff = user_consumption - cluster_consumption
    
    # Always provide suggestions for high consumption emissions
    if user_consumption > 200:  # If user has significant consumption emissions
        # Calculate potential savings
        potential_inr_reduction = user_consumption / (emission_factors['consumption'] * inr_to_usd_rate) * 0.2  # Suggest reducing 20%
        potential_savings = user_consumption * 0.2
        
        suggestions.append({
            "type": "consumption",
            "message": f"Delay non-essential purchases worth ₹{potential_inr_reduction:,.0f} to avoid {potential_savings:.1f} kg CO₂.",
            "savings_kg": round(potential_savings, 2),
            "action": "buy_less"
        })
    elif consumption_diff > 0 and cluster_consumption > 0:
        consumption_ratio = consumption_diff / cluster_consumption
        if consumption_ratio > 0.1:  # More than 10% above cluster
            # Calculate potential savings
            potential_inr_reduction = consumption_diff / (emission_factors['consumption'] * inr_to_usd_rate)
            potential_savings = consumption_diff
            
            suggestions.append({
                "type": "consumption",
                "message": f"Delay non-essential purchases worth ₹{potential_inr_reduction:,.0f} to avoid {potential_savings:.1f} kg CO₂.",
                "savings_kg": round(potential_savings, 2),
                "action": "buy_less"
            })
        else:
            suggestions.append({
                "type": "consumption",
                "message": "Your consumption emissions are already close to cluster average—good job!",
                "savings_kg": 0,
                "action": "maintain"
            })
    elif consumption_diff <= 0 and cluster_consumption > 0:
        suggestions.append({
            "type": "consumption",
            "message": "Your consumption emissions are already below cluster average—great job!",
            "savings_kg": 0,
            "action": "maintain"
        })
    else:
        suggestions.append({
            "type": "consumption",
            "message": "No consumption data available for comparison.",
            "savings_kg": 0,
            "action": "no_data"
        })
    
    return suggestions

@decorators.login_required
def api_insights(request):
    """
    API endpoint that returns user insights based on ML clustering with dynamic suggestions
    """
    try:
        # Extract features for the current user
        user_features = get_user_features(request.user)
        
        # Prepare features for prediction (exclude user_id)
        feature_columns = [col for col in user_features.keys() if col != 'user_id']
        user_feature_values = [user_features[col] for col in feature_columns]
        
        # Convert to DataFrame for consistency with training
        X = pd.DataFrame([user_feature_values], columns=feature_columns)
        
        # Handle any missing values
        X = X.fillna(0)
        
        # Load the scaler and model
        model_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'ml_models')
        
        scaler_path = os.path.join(model_dir, 'scaler.pkl')
        with open(scaler_path, 'rb') as f:
            scaler = pickle.load(f)
        
        kmeans_path = os.path.join(model_dir, 'kmeans.pkl')
        with open(kmeans_path, 'rb') as f:
            kmeans = pickle.load(f)
        
        # Scale the features
        X_scaled = scaler.transform(X)
        
        # Predict cluster
        cluster_id = kmeans.predict(X_scaled)[0]
        
        # Get cluster center for this cluster and inverse transform it
        cluster_centers_scaled = kmeans.cluster_centers_
        cluster_center_scaled = cluster_centers_scaled[cluster_id].reshape(1, -1)
        cluster_center_unscaled = scaler.inverse_transform(cluster_center_scaled)
        
        # Convert cluster center to dictionary
        cluster_center_dict = {}
        for i, col in enumerate(feature_columns):
            cluster_center_dict[col] = float(cluster_center_unscaled[0][i])
        
        # Generate dynamic suggestions
        suggestions = calculate_dynamic_suggestions(user_features, cluster_center_dict, cluster_id)
        
        # Return JSON response
        return JsonResponse({
            'cluster_id': int(cluster_id),
            'suggestions': suggestions,
            'features': user_features,
            'cluster_center': cluster_center_dict
        })
    
    except Exception as e:
        return JsonResponse({
            'error': str(e)
        }, status=500)
