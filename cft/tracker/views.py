from django.shortcuts import render, redirect
from django.contrib.auth import login, get_user_model, decorators
from django.contrib import messages
from .forms import UserRegisterForm, UserUpdateForm, ProfileUpdateForm
import json
from datetime import date, timedelta
from django.db.models import Sum
from .models import Profile, Activity, Emission, UserAchievement, User

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
    
    # Format for the template
    leaderboard = []
    for i, data in enumerate(leaderboard_data[:5]): # Get top 5
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
    
    return leaderboard, user_rank


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

    _, user_rank = get_leaderboard_and_rank(request.user) # Get current user's rank

    category_data_query = Emission.objects.filter(activity__user=request.user, activity__timestamp__gte=start_of_month).values('activity__category').annotate(total=Sum('co2_equivalent_kg'))
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

    # Pass the user_rank in a dictionary for the ranking card
    ranking_data = {'country': {'rank': user_rank}}

    context = {
        'u_form': u_form,
        'p_form': p_form,
        'total_footprint_this_month': round(total_footprint_this_month, 2),
        'ranking_data_json': json.dumps(ranking_data), # Pass rank to JS
        'category_data_json': json.dumps(category_data),
        'trends_data_json': json.dumps(trends_data),
        'streak_data_json': json.dumps(streak_data_for_chart),
        'carbon_budget': carbon_budget,
        'actionable_insights': actionable_insights,
    }
    return render(request, 'tracker/myprofile.html', context)


def home(request):
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
    leaderboard, user_rank = get_leaderboard_and_rank(request.user if request.user.is_authenticated else None)

    context = {
        'global_stats': {'totalUsers': total_users, 'co2Saved': 847, 'countriesCount': 67},
        'country_comparison': country_comparison,
        'recent_badges': recent_badges,
        'leaderboard': leaderboard,
        'summary_data': {'this_month': 0, 'last_month': 0, 'improvement': 0, 'rank': user_rank}, # Use real rank
        'emissions_table_data': [],
        'emissions_data_json': json.dumps({'labels': [], 'data': []}),
        'daily_challenge': {'text': 'Log your first activity!', 'impact': ''},
        'insights': {
            'tip': {'icon': '💡', 'title': "Today's Eco Tip", 'content': 'Replace 1 car trip with biking today', 'impact': 'Potential save: 2.3kg CO2'},
            'weather': {'icon': '☀️', 'title': "Weather Advice", 'content': 'Perfect day for cycling!', 'impact': 'Air quality: Good'},
            'events': {'icon': '🌱', 'title': "Local Events", 'content': 'Tree planting drive this Saturday', 'impact': 'Green Park 10AM'},
        }
    }
    return render(request, 'tracker/home.html', context)

def logactivity(request):
    data = {
        "name" :[1,2,3,4],
    }
    return render(request,'tracker/logactivity.html',data)