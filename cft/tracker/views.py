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
    this_month_emissions=0
    last_month_emissions = 0

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
    search_location = "India" # Default location for logged-out users
    if request.user.is_authenticated and request.user.profile.location:
        search_location = request.user.profile.location
        # Monthly totals
        this_month_start = today.replace(day=1)
        last_month_end = this_month_start - timedelta(days=1)
        last_month_start = last_month_end.replace(day=1)

        this_month_emissions = Activity.objects.filter(user=request.user, timestamp__date__gte=this_month_start).aggregate(total=Sum('emission__co2_equivalent_kg'))['total'] or 0
        last_month_emissions = Activity.objects.filter(user=request.user, timestamp__date__gte=last_month_start, timestamp__date__lte=last_month_end).aggregate(total=Sum('emission__co2_equivalent_kg'))['total'] or 0

        
    ai_tip_content='Replace 1 car trip with biking today'
    if request.user.is_authenticated:
        n8n_webhook_url = "http://localhost:5678/webhook/0881df72-c41b-46bf-9734-532d27e239b9" # <-- MAKE SURE THIS IS YOUR PRODUCTION URL
        payload = {'user_id': request.user.id}
        
        try:
            response = requests.post(n8n_webhook_url, json=payload, timeout=10)
            
            # Check if the request was successful
            if response.status_code == 200:
                response_data = response.json()
                
                # CORRECTED LOGIC:
                # Check if the response is a dictionary and not empty
                if isinstance(response_data, dict) and response_data:
                    # Get the first key from the dictionary, which is our AI tip
                    ai_tip_content = list(response_data.keys())[0]
                    print(":::::::::::::::::::::::::::::::::::::")
                    
                    print(list(response_data.keys()))

        except requests.exceptions.RequestException as e:
            # If n8n is down or there's a network error, we just log it and use the default tip
            print(f"Could not connect to n8n workflow: {e}")

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
        # A simple placeholder for emission factor calculation.
        # In a real app, this would be a more complex lookup from a dedicated model or configuration file.
        EMISSION_FACTORS = {
            'travel': {'car-gasoline': 0.25, 'bus': 0.1, 'flight-short': 0.2, 'car-electric': 0.05, 'train': 0.04, 'motorcycle': 0.1, 'bicycle': 0, 'walking': 0, 'flight-long': 0.25},
            'energy': {'electricity': 0.39},
            'food': {'red-meat': 7.1, 'white-meat': 2.5, 'fish': 1.5, 'vegetarian': 1.0, 'vegan': 0.7, 'other': 1.2},
            'purchases': {'clothing': 0.1, 'electronics': 0.5, 'home-goods': 0.3, 'services': 0.05, 'other': 0.2}
        }

        try:
            if category == 'transport':
                mode = request.POST.get('transportMode')
                distance = float(request.POST.get('distance'))
                footprint = distance * EMISSION_FACTORS['travel'].get(mode, 0.15)
                description = f"Travel: {mode.replace('-', ' ').title()} - {distance} km"
                new_activity = Activity.objects.create(user=request.user, category='transport', description=description, value=distance, unit='km')
            
            elif category == 'energy':
                units = float(request.POST.get('electricityUnits'))
                footprint = units * EMISSION_FACTORS['energy']['electricity']
                description = f"Energy: Manual Entry - {units} kWh"
                new_activity = Activity.objects.create(user=request.user, category='energy', description=description, value=units, unit='kWh')

            elif category == 'food':
                diet_type = request.POST.get('dietType')
                quantity = float(request.POST.get('foodQuantity', 1))
                footprint = quantity * EMISSION_FACTORS['food'].get(diet_type, 1.0)
                description = f"Food: {diet_type.replace('-', ' ').title()} ({quantity} servings)"
                new_activity = Activity.objects.create(user=request.user, category='food', description=description, value=quantity, unit='serving')

            elif category == 'consumption':
                purchase_cat = request.POST.get('purchaseCategory')
                amount = float(request.POST.get('purchaseAmount'))
                # Convert INR to a USD-equivalent for consistent emission factor application
                # Using an approximate conversion rate (e.g., 1 USD = 83 INR)
                INR_TO_USD_RATE = 1 / 83 
                amount_in_usd_equivalent = amount * INR_TO_USD_RATE
                footprint = amount_in_usd_equivalent * EMISSION_FACTORS['purchases'].get(purchase_cat, 0.2)
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