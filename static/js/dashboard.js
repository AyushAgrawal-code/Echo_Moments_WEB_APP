// EchoMoments Dashboard JavaScript

// DOM Elements
const mobileMenuBtn = document.getElementById('mobileMenuBtn');
const mobileSidebar = document.getElementById('mobileSidebar');
const copyToast = document.getElementById('copyToast');

// Mobile Menu Toggle
if (mobileMenuBtn && mobileSidebar) {
    mobileMenuBtn.addEventListener('click', function() {
        mobileSidebar.classList.toggle('active');
        
        // Update icon
        const icon = mobileMenuBtn.querySelector('i');
        if (mobileSidebar.classList.contains('active')) {
            icon.className = 'fas fa-times';
        } else {
            icon.className = 'fas fa-bars';
        }
    });

    // Close sidebar when clicking outside
    mobileSidebar.addEventListener('click', function(e) {
        if (e.target === mobileSidebar) {
            mobileSidebar.classList.remove('active');
            mobileMenuBtn.querySelector('i').className = 'fas fa-bars';
        }
    });
}

// Copy Event Code Function
async function copyEventCode(code) {
    try {
        await navigator.clipboard.writeText(code);
        showToast('Code copied to clipboard!');
        
        // Add success feedback to button
        const copyBtns = document.querySelectorAll('.copy-btn');
        copyBtns.forEach(btn => {
            if (btn.onclick && btn.onclick.toString().includes(code)) {
                const originalHTML = btn.innerHTML;
                btn.innerHTML = '<i class="fas fa-check"></i>';
                btn.style.color = '#10b981';
                
                setTimeout(() => {
                    btn.innerHTML = originalHTML;
                    btn.style.color = '';
                }, 2000);
            }
        });
    } catch (err) {
        console.error('Failed to copy code:', err);
        showToast('Failed to copy code', 'error');
    }
}

// Show Toast Notification
function showToast(message, type = 'success') {
    if (copyToast) {
        copyToast.textContent = message;
        copyToast.classList.add('show');
        
        if (type === 'error') {
            copyToast.style.background = '#dc2626';
        } else {
            copyToast.style.background = 'var(--echo-emerald)';
        }
        
        setTimeout(() => {
            copyToast.classList.remove('show');
        }, 3000);
    }
}

// Event Handlers
function handleViewProfile() {
    // Replace with your profile page URL
    window.location.href = '/profile/';
    console.log('Navigate to profile page');
}

function handleHostEvent() {
    // Replace with your create event URL
    window.location.href = '/events/create/';
    console.log('Navigate to create event page');
}

function handleJoinEvent() {
    // Replace with your join event URL or modal
    const eventCode = prompt('Enter event code:');
    if (eventCode) {
        window.location.href = `/events/join/${eventCode}/`;
    }
    console.log('Join event with code:', eventCode);
}

function handleUploadPhotos() {
    // Replace with your upload photos URL
    window.location.href = '/photos/upload/';
    console.log('Navigate to upload photos page');
}

function handleOpenEvent(eventCode) {
    // Replace with your event detail URL
    window.location.href = `/events/${eventCode}/`;
    console.log('Open event:', eventCode);
}

function handleLogout() {
    if (confirm('Are you sure you want to logout?')) {
        // Replace with your logout URL
        window.location.href = '/logout/';
    }
}

// Animation on Scroll
function observeElements() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, observerOptions);

    // Observe elements with animation classes
    const animatedElements = document.querySelectorAll('.animate-slide-up, .animate-fade-in');
    animatedElements.forEach(el => {
        // Initial state for intersection observer
        el.style.opacity = '0';
        el.style.transform = 'translateY(30px)';
        el.style.transition = 'all 0.6s ease-out';
        
        observer.observe(el);
    });
}

// Smooth scroll for anchor links
function initSmoothScroll() {
    const links = document.querySelectorAll('a[href^="#"]');
    links.forEach(link => {
        link.addEventListener('click', function(e) {
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
}

// Real-time Updates (WebSocket or Polling)
function initRealTimeUpdates() {
    // Example: Poll for new notifications every 30 seconds
    setInterval(() => {
        fetchNotifications();
    }, 30000);
}

async function fetchNotifications() {
    try {
        const response = await fetch(window.ECHO_NOTIFICATIONS_URL || "/accounts/notifications/");

        if (!response.ok) {
            console.error("API error:", response.status);
            return;
        }

        const data = await response.json();
        updateNotifications(data.notifications);

    } catch (error) {
        console.error('Error fetching notifications:', error);
    }
}


function updateNotifications(notifications) {
    const container = document.querySelector('.notifications');
    if (!container) return;
    const badge = document.querySelector('.card-title .badge-destructive');
    const unreadCount = notifications.filter(item => !item.is_read).length;
    if (badge) {
        badge.textContent = String(unreadCount);
        badge.style.display = unreadCount > 0 ? 'inline-flex' : 'none';
    }
    container.replaceChildren();
    notifications.forEach(item => {
        const row = document.createElement('div');
        row.className = `notification-item ${item.is_read ? '' : 'unread'}`;
        const icon = document.createElement('div');
        icon.className = `notification-icon ${item.type || 'event'}`;
        const glyph = document.createElement('i');
        glyph.className = `fas fa-${getNotificationIcon(item.type)}`;
        icon.appendChild(glyph);
        const body = document.createElement('div');
        body.className = 'notification-content';
        [['notification-title', item.title], ['notification-message', item.message], ['notification-time', formatTime(item.created_at)]].forEach(([className, value]) => {
            const text = document.createElement('p');
            text.className = className;
            text.textContent = value || '';
            body.appendChild(text);
        });
        row.append(icon, body);
        if (!item.is_read) {
            const dot = document.createElement('div');
            dot.className = 'notification-dot';
            row.appendChild(dot);
        }
        container.appendChild(row);
    });
}
function getNotificationIcon(type) {
    switch (type) {
        case 'photo': return 'image';
        case 'event': return 'calendar';
        case 'user': return 'users';
        default: return 'bell';
    }
}

function formatTime(timestamp) {
    const now = new Date();
    const time = new Date(timestamp);
    const diff = now - time;
    
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    
    if (minutes < 1) return 'Just now';
    if (minutes < 60) return `${minutes} minute${minutes > 1 ? 's' : ''} ago`;
    if (hours < 24) return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    return `${days} day${days > 1 ? 's' : ''} ago`;
}

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', function() {
    console.log('EchoMoments Dashboard initialized');
    
    // Initialize features
    observeElements();
    initSmoothScroll();
    initRealTimeUpdates();
    
    // Add loading states
    const cards = document.querySelectorAll('.echo-card');
    cards.forEach(card => {
        card.addEventListener('click', function() {
            // Add loading state to clicked cards if needed
            this.style.opacity = '0.7';
            setTimeout(() => {
                this.style.opacity = '1';
            }, 200);
        });
    });
    
    // Initialize tooltips (if needed)
    const tooltipElements = document.querySelectorAll('[title]');
    tooltipElements.forEach(el => {
        el.addEventListener('mouseenter', function() {
            // Custom tooltip logic here
        });
    });
});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // ESC to close mobile menu
    if (e.key === 'Escape' && mobileSidebar && mobileSidebar.classList.contains('active')) {
        mobileSidebar.classList.remove('active');
        mobileMenuBtn.querySelector('i').className = 'fas fa-bars';
    }
    
    // Quick navigation shortcuts
    if (e.ctrlKey || e.metaKey) {
        switch (e.key) {
            case 'h':
                e.preventDefault();
                handleHostEvent();
                break;
            case 'j':
                e.preventDefault();
                handleJoinEvent();
                break;
            case 'u':
                e.preventDefault();
                handleUploadPhotos();
                break;
        }
    }
});

// Window resize handler
window.addEventListener('resize', function() {
    // Close mobile menu on resize to desktop
    if (window.innerWidth >= 1024 && mobileSidebar && mobileSidebar.classList.contains('active')) {
        mobileSidebar.classList.remove('active');
        mobileMenuBtn.querySelector('i').className = 'fas fa-bars';
    }
});

// Export functions for Django template use
window.EchoMomentsDashboard = {
    copyEventCode,
    handleViewProfile,
    handleHostEvent,
    handleJoinEvent,
    handleUploadPhotos,
    handleOpenEvent,
    handleLogout,
    showToast,
    updateNotifications
};

// document.addEventListener("DOMContentLoaded", () => {
    
//     function sortEvents(containerSelector, sortType) {
//         const container = document.querySelector(containerSelector);
//         if (!container) return;

//         let items = Array.from(container.querySelectorAll(".event-item"));

//         items.sort((a, b) => {
//             const dateA = new Date(a.querySelector(".event-date").textContent);
//             const dateB = new Date(b.querySelector(".event-date").textContent);

//             switch(sortType) {
//                 case "-event_date":    // Newest first
//                     return dateB - dateA;
//                 case "event_date":     // Oldest first
//                     return dateA - dateB;
//                 case "upcoming":       // Future events first
//                     return dateA - new Date();
//                 case "past":           // Past events
//                     return new Date() - dateA;
//                 default:
//                     return 0;
//             }
//         });

//         items.forEach(item => container.appendChild(item));
//     }

//     // Hosted Events Sorting
//     const hostedSort = document.getElementById("hostedSort");
//     if (hostedSort) {
//         hostedSort.addEventListener("change", () => {
//             sortEvents(".events-card .events-list", hostedSort.value);
//         });
//     }

//     // Joined Events Sorting
//     const joinedSort = document.getElementById("joinedSort");
//     if (joinedSort) {
//         joinedSort.addEventListener("change", () => {
//             sortEvents(".events-card:nth-of-type(2) .events-list", joinedSort.value);
//         });
//     }

// });




