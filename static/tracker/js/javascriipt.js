// DOM Elements
const motivationalQuotes = [
    { text: "Your journey to a greener tomorrow starts today", author: "EcoTracker Team" },
    { text: "Be the change you wish to see in the world", author: "Mahatma Gandhi" },
    { text: "The Earth does not belong to us; we belong to the Earth", author: "Chief Seattle" },
    { text: "Small acts, when multiplied by millions of people, can transform the world", author: "Howard Zinn" },
    { text: "There is no planet B", author: "Anonymous" }
];

let currentQuoteIndex = 0;

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeCounters();
    initializeChart();
    startQuoteRotation();
    initializeToggleButtons();
    simulateActivityFeed();
    addInteractiveEffects();
});

// Counter Animation Function
function animateCounter(element, target, duration = 2000) {
    const start = 0;
    const increment = target / (duration / 16);
    let current = start;
    
    const timer = setInterval(() => {
        current += increment;
        if (current >= target) {
            current = target;
            clearInterval(timer);
        }
        element.textContent = Math.floor(current).toLocaleString();
    }, 16);
}

// Initialize all counters
function initializeCounters() {
    const counters = [
        { id: 'totalUsers', target: 15847 },
        { id: 'co2Saved', target: 847 },
        { id: 'countriesCount', target: 67 }
    ];
    
    // Intersection Observer for counters
    const observerOptions = {
        threshold: 0.5,
        rootMargin: '0px 0px -100px 0px'
    };
    
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const element = entry.target;
                const target = parseInt(element.dataset.target);
                animateCounter(element, target);
                observer.unobserve(element);
            }
        });
    }, observerOptions);
    
    counters.forEach(counter => {
        const element = document.getElementById(counter.id);
        if (element) {
            observer.observe(element);
        }
    });
}

// Initialize Pie Chart
function initializeChart() {
    const ctx = document.getElementById('emissionsChart');
    if (!ctx) return;
    
    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Transport', 'Housing', 'Food', 'Shopping'],
            datasets: [{
                data: [40, 35, 15, 10],
                backgroundColor: ['#EF4444', '#F59E0B', '#10B981', '#3B82F6'],
                borderWidth: 0,
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return context.label + ': ' + context.parsed + '%';
                        }
                    }
                }
            },
            onHover: (event, elements) => {
                event.native.target.style.cursor = elements.length > 0 ? 'pointer' : 'default';
            },
            onClick: (event, elements) => {
                if (elements.length > 0) {
                    const index = elements[0].index;
                    const labels = ['Transport', 'Housing', 'Food', 'Shopping'];
                    alert(`Clicked on ${labels[index]} category! Here you could show detailed breakdown.`);
                }
            }
        }
    });
}

// Quote Rotation
function startQuoteRotation() {
    const quoteElement = document.getElementById('motivationalQuote');
    const authorElement = document.querySelector('.quote-author');
    
    if (!quoteElement || !authorElement) return;
    
    setInterval(() => {
        // Fade out
        quoteElement.style.opacity = '0';
        authorElement.style.opacity = '0';
        
        setTimeout(() => {
            currentQuoteIndex = (currentQuoteIndex + 1) % motivationalQuotes.length;
            const quote = motivationalQuotes[currentQuoteIndex];
            
            quoteElement.textContent = quote.text;
            authorElement.textContent = `- ${quote.author}`;
            
            // Fade in
            quoteElement.style.opacity = '1';
            authorElement.style.opacity = '1';
        }, 300);
    }, 5000);
    
    // Add smooth transition
    quoteElement.style.transition = 'opacity 0.3s ease';
    authorElement.style.transition = 'opacity 0.3s ease';
}

// Toggle Button Functionality
function initializeToggleButtons() {
    const toggleButtons = document.querySelectorAll('.toggle-btn');
    
    toggleButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Remove active class from all buttons
            toggleButtons.forEach(btn => btn.classList.remove('active'));
            // Add active class to clicked button
            button.classList.add('active');
            
            // Here you would typically update the map view
            const view = button.dataset.view;
            console.log(`Switching to ${view} view`);
        });
    });
}

// Simulate Live Activity Feed
function simulateActivityFeed() {
    const activities = [
        { icon: '🚴', text: 'User***23 cycled 5km (saved 1.2kg CO2)', time: '2min ago' },
        { icon: '🌱', text: 'User***67 planted a tree', time: '5min ago' },
        { icon: '🚌', text: 'User***91 used public transport', time: '8min ago' },
        { icon: '💡', text: 'User***45 switched to LED bulbs', time: '12min ago' },
        { icon: '🚗', text: 'User***12 carpooled to work', time: '15min ago' },
        { icon: '♻️', text: 'User***78 recycled 5kg waste', time: '18min ago' }
    ];
    
    const feedContainer = document.querySelector('.feed-container');
    if (!feedContainer) return;
    
    let currentIndex = 4;
    
    setInterval(() => {
        // Create new activity
        const newActivity = activities[Math.floor(Math.random() * activities.length)];
        const activityElement = document.createElement('div');
        activityElement.className = 'feed-item';
        activityElement.innerHTML = `
            <span class="activity-icon">${newActivity.icon}</span>
            <span class="activity-text">${newActivity.text}</span>
            <span class="activity-time">Just now</span>
        `;
        
        // Add to top of feed
        feedContainer.insertBefore(activityElement, feedContainer.firstChild);
        
        // Remove last item if too many
        const items = feedContainer.querySelectorAll('.feed-item');
        if (items.length > 6) {
            feedContainer.removeChild(feedContainer.lastChild);
        }
        
        // Update time stamps
        items.forEach((item, index) => {
            const timeElement = item.querySelector('.activity-time');
            if (index === 0) {
                timeElement.textContent = 'Just now';
            } else {
                timeElement.textContent = `${index * 3 + 2}min ago`;
            }
        });
        
    }, 15000); // New activity every 15 seconds
}

// Add Interactive Effects
function addInteractiveEffects() {
    // Smooth scrolling for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Add hover effects to metric cards
    const metricCards = document.querySelectorAll('.metric-card, .stat-card, .insight-card');
    metricCards.forEach(card => {
        card.addEventListener('mouseenter', function() {
            this.style.transform = 'translateY(-8px) scale(1.02)';
        });
        
        card.addEventListener('mouseleave', function() {
            this.style.transform = 'translateY(0) scale(1)';
        });
    });
    
    // Progress bar animations on scroll
    const progressBars = document.querySelectorAll('.progress-fill');
    const progressObserver = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const width = entry.target.style.width;
                entry.target.style.width = '0%';
                setTimeout(() => {
                    entry.target.style.width = width;
                }, 200);
            }
        });
    }, { threshold: 0.5 });
    
    progressBars.forEach(bar => progressObserver.observe(bar));
    
    // Button click animations
    document.querySelectorAll('button').forEach(button => {
        button.addEventListener('click', function(e) {
            // Create ripple effect
            const rect = this.getBoundingClientRect();
            const ripple = document.createElement('span');
            const size = Math.max(rect.width, rect.height);
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;
            
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = x + 'px';
            ripple.style.top = y + 'px';
            ripple.classList.add('ripple');
            
            this.appendChild(ripple);
            
            setTimeout(() => {
                ripple.remove();
            }, 600);
        });
    });
    
    // Category item interactions
    document.querySelectorAll('.category-item').forEach(item => {
        item.addEventListener('click', function() {
            const categoryName = this.querySelector('.category-name').textContent;
            alert(`Showing detailed breakdown for ${categoryName} category`);
        });
    });
    
    // Leaderboard row hover effects
    document.querySelectorAll('.leaderboard-row').forEach(row => {
        row.addEventListener('click', function() {
            const username = this.querySelector('.username').textContent;
            alert(`Viewing profile of ${username}`);
        });
    });
}

// Add CSS for ripple effect
const style = document.createElement('style');
style.textContent = `
    button {
        position: relative;
        overflow: hidden;
    }
    
    .ripple {
        position: absolute;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.6);
        transform: scale(0);
        animation: rippleAnimation 0.6s linear;
        pointer-events: none;
    }
    
    @keyframes rippleAnimation {
        to {
            transform: scale(4);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);

// Utility Functions
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Window resize handler
window.addEventListener('resize', debounce(() => {
    // Recalculate chart dimensions if needed
    const chart = Chart.getChart('emissionsChart');
    if (chart) {
        chart.resize();
    }
}, 250));

// Service Worker Registration for PWA capabilities
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('/sw.js')
            .then(registration => {
                console.log('SW registered: ', registration);
            })
            .catch(registrationError => {
                console.log('SW registration failed: ', registrationError);
            });
    });
}