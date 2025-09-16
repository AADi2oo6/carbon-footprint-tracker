from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# 1. Profile Model (Extends the User Model)
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    location = models.CharField(max_length=100, blank=True, null=True, help_text="e.g., Mumbai, India")
    carbon_budget_kg = models.FloatField(default=500.0, help_text="User's personal monthly CO2 budget in kg")

    def __str__(self):
        return f'{self.user.username} Profile'

# 2. Activity Model (The Core of the App)
class Activity(models.Model):
    ACTIVITY_CATEGORIES = [
        ('transport', 'Transportation'),
        ('energy', 'Home Energy'),
        ('food', 'Food & Diet'),
        ('consumption', 'Consumption'),
        ('waste', 'Waste'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=20, choices=ACTIVITY_CATEGORIES)
    description = models.CharField(max_length=255)
    value = models.FloatField(help_text="e.g., distance in km, energy in kWh, quantity of items")
    unit = models.CharField(max_length=50, help_text="e.g., 'km', 'kWh', 'serving'")
    timestamp = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.user.username} - {self.description} on {self.timestamp.strftime('%Y-%m-%d')}"

# 3. Emission Model (The Result of an Activity)
class Emission(models.Model):
    activity = models.OneToOneField(Activity, on_delete=models.CASCADE)
    co2_equivalent_kg = models.FloatField()
    calculation_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Emission for {self.activity.description}: {self.co2_equivalent_kg} kg CO2e"

# 4. Achievement Model (Defines all possible badges)
class Achievement(models.Model):
    TIER_CHOICES = [
        ('bronze', 'Bronze'),
        ('silver', 'Silver'),
        ('gold', 'Gold'),
    ]
    name = models.CharField(max_length=100)
    description = models.TextField()
    icon = models.CharField(max_length=50, help_text="e.g., 'fas fa-leaf'")
    tier = models.CharField(max_length=10, choices=TIER_CHOICES, default='bronze')
    condition_key = models.CharField(max_length=100, unique=True, help_text="A unique key for the unlocking logic")

    def __str__(self):
        return f"{self.name} ({self.tier.capitalize()})"

# 5. UserAchievement Model (Tracks earned badges)
class UserAchievement(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    achievement = models.ForeignKey(Achievement, on_delete=models.CASCADE)
    date_earned = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Ensures a user can only earn each achievement once
        unique_together = ('user', 'achievement')

    def __str__(self):
        return f"{self.user.username} earned {self.achievement.name}"

class Community(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    community_type = models.CharField(max_length=50, choices=[('University', 'University'), ('Company', 'Company'), ('City', 'City')])
    members = models.ManyToManyField(User, related_name='communities', blank=True)

    def __str__(self):
        return self.name

class Challenge(models.Model):
    community = models.ForeignKey(Community, on_delete=models.CASCADE, related_name='challenges')
    title = models.CharField(max_length=200)
    description = models.TextField()
    goal = models.FloatField(default=0)
    unit = models.CharField(max_length=50, default='units', help_text="e.g., 'km', 'days', 'kg'")
    reward_achievement = models.ForeignKey(Achievement, on_delete=models.SET_NULL, null=True, blank=True)
    end_date = models.DateField()
    participants = models.ManyToManyField(User, through='UserChallenge', related_name='challenges_joined')

    def __str__(self):
        return self.title

# 7. UserChallenge Model (Tracks user progress in a challenge)
class UserChallenge(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE)
    progress = models.FloatField(default=0)
    is_completed = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'challenge')

    def __str__(self):
        return f"{self.user.username} in {self.challenge.title}"
