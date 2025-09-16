from .models import Activity, UserAchievement
from datetime import date, timedelta

def global_context(request):
    if not request.user.is_authenticated:
        return {}

    # --- REAL STREAK CALCULATION ---
    active_days_query = Activity.objects.filter(user=request.user).dates('timestamp', 'day', order='DESC')
    active_days = {d.strftime("%Y-%m-%d") for d in active_days_query}
    
    total_active = len(active_days)
    max_streak = 0
    current_streak = 0
    
    today = date.today()
    # Check a reasonable period back in time to calculate the streak
    for i in range(365): 
        check_date = today - timedelta(days=i)
        if check_date.strftime("%Y-%m-%d") in active_days:
            current_streak += 1
        else:
            if current_streak > max_streak:
                max_streak = current_streak
            # Optimization: if we're past the oldest activity and streak is 0, we can stop.
            if i > total_active * 2 and current_streak == 0:
                 break
            current_streak = 0

    if current_streak > max_streak:
        max_streak = current_streak

    streak_data = {
        "total_active": total_active,
        "max_streak": max_streak,
    }

    # --- REAL ACHIEVEMENT DATA ---
    earned_achievements_query = UserAchievement.objects.filter(user=request.user).select_related('achievement')
    global_achievements = [
        {
            'name': item.achievement.name,
            'description': item.achievement.description,
            'icon': item.achievement.icon,
            'tier': item.achievement.tier
        } 
        for item in earned_achievements_query
    ]
    # If a new user has no achievements, show a welcoming default message.
    if not global_achievements:
        global_achievements.append({
            'name': 'Welcome!',
            'description': 'Start logging activities to earn your first badge.',
            'icon': 'fas fa-star',
            'tier': 'bronze'
        })

    return {
        'global_streak_data': streak_data,
        'global_achievements': global_achievements,
    }

