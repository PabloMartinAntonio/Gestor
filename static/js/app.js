// Task Manager JavaScript

// Dark mode functionality
function toggleDarkMode() {
    const html = document.documentElement;
    const themeIcon = document.getElementById('theme-icon');
    const currentTheme = html.getAttribute('data-bs-theme');
    
    if (currentTheme === 'dark') {
        html.setAttribute('data-bs-theme', 'light');
        themeIcon.className = 'fas fa-moon';
        localStorage.setItem('theme', 'light');
    } else {
        html.setAttribute('data-bs-theme', 'dark');
        themeIcon.className = 'fas fa-sun';
        localStorage.setItem('theme', 'dark');
    }
}

// Initialize theme on page load
document.addEventListener('DOMContentLoaded', function() {
    const savedTheme = localStorage.getItem('theme');
    const html = document.documentElement;
    const themeIcon = document.getElementById('theme-icon');
    
    // Set theme based on saved preference or system preference
    if (savedTheme) {
        html.setAttribute('data-bs-theme', savedTheme);
        if (savedTheme === 'dark') {
            themeIcon.className = 'fas fa-sun';
        } else {
            themeIcon.className = 'fas fa-moon';
        }
    } else if (window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches) {
        html.setAttribute('data-bs-theme', 'dark');
        themeIcon.className = 'fas fa-sun';
        localStorage.setItem('theme', 'dark');
    }
    
    // Form validation
    const forms = document.querySelectorAll('form');
    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            // Date validation for task forms
            const startDate = form.querySelector('#start_date');
            const endDate = form.querySelector('#end_date');
            
            if (startDate && endDate && startDate.value && endDate.value) {
                if (new Date(startDate.value) > new Date(endDate.value)) {
                    e.preventDefault();
                    showAlert('Start date cannot be after end date', 'error');
                    return false;
                }
            }
            
            // Password confirmation validation
            const password = form.querySelector('#password');
            const confirmPassword = form.querySelector('#confirm_password');
            
            if (password && confirmPassword) {
                if (password.value !== confirmPassword.value) {
                    e.preventDefault();
                    showAlert('Passwords do not match', 'error');
                    return false;
                }
            }
        });
    });
    
    // Auto-dismiss alerts after 5 seconds
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
        setTimeout(() => {
            if (alert && alert.parentNode) {
                alert.style.opacity = '0';
                setTimeout(() => {
                    if (alert.parentNode) {
                        alert.parentNode.removeChild(alert);
                    }
                }, 300);
            }
        }, 5000);
    });
    
    // Add loading state to buttons on form submission
    forms.forEach(form => {
        form.addEventListener('submit', function() {
            const submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn) {
                submitBtn.disabled = true;
                const originalText = submitBtn.innerHTML;
                submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Loading...';
                
                // Re-enable button after 3 seconds as fallback
                setTimeout(() => {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalText;
                }, 3000);
            }
        });
    });
    
    // Smooth scroll for anchor links
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
    
    // Add animation classes to cards
    const cards = document.querySelectorAll('.task-card');
    cards.forEach((card, index) => {
        card.style.animationDelay = `${index * 0.1}s`;
    });
    
    // Add status classes to task cards based on status
    cards.forEach(card => {
        const statusBadge = card.querySelector('.badge.bg-warning, .badge.bg-info, .badge.bg-success');
        if (statusBadge) {
            if (statusBadge.classList.contains('bg-warning')) {
                card.classList.add('status-pending');
            } else if (statusBadge.classList.contains('bg-info')) {
                card.classList.add('status-in-progress');
            } else if (statusBadge.classList.contains('bg-success')) {
                card.classList.add('status-completed');
            }
        }
    });
    
    // Add priority classes to task cards
    cards.forEach(card => {
        const priorityBadge = card.querySelector('.badge.bg-danger, .badge.bg-primary, .badge.bg-secondary');
        if (priorityBadge) {
            if (priorityBadge.classList.contains('bg-danger')) {
                card.classList.add('priority-high');
            } else if (priorityBadge.classList.contains('bg-primary')) {
                card.classList.add('priority-medium');
            } else if (priorityBadge.classList.contains('bg-secondary')) {
                card.classList.add('priority-low');
            }
        }
    });
});

// Utility function to show alerts
function showAlert(message, type = 'info') {
    const alertDiv = document.createElement('div');
    alertDiv.className = `alert alert-${type === 'error' ? 'danger' : type} alert-dismissible fade show`;
    alertDiv.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    const container = document.querySelector('.container');
    if (container) {
        container.insertBefore(alertDiv, container.firstChild);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alertDiv && alertDiv.parentNode) {
                alertDiv.style.opacity = '0';
                setTimeout(() => {
                    if (alertDiv.parentNode) {
                        alertDiv.parentNode.removeChild(alertDiv);
                    }
                }, 300);
            }
        }, 5000);
    }
}

// Confirm dialog for delete actions
document.addEventListener('click', function(e) {
    if (e.target.closest('form[onsubmit*="confirm"]')) {
        const form = e.target.closest('form');
        if (form && form.getAttribute('onsubmit').includes('confirm')) {
            e.preventDefault();
            if (confirm('Are you sure you want to delete this task? This action cannot be undone.')) {
                form.submit();
            }
        }
    }
});

// Keyboard shortcuts
document.addEventListener('keydown', function(e) {
    // Ctrl/Cmd + D for dark mode toggle
    if ((e.ctrlKey || e.metaKey) && e.key === 'd') {
        e.preventDefault();
        toggleDarkMode();
    }
    
    // Escape key to close modals/dropdowns
    if (e.key === 'Escape') {
        const openDropdowns = document.querySelectorAll('.dropdown-menu.show');
        openDropdowns.forEach(dropdown => {
            dropdown.classList.remove('show');
        });
    }
});

// Listen for system theme changes
if (window.matchMedia) {
    window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', function(e) {
        if (!localStorage.getItem('theme')) {
            const html = document.documentElement;
            const themeIcon = document.getElementById('theme-icon');
            
            if (e.matches) {
                html.setAttribute('data-bs-theme', 'dark');
                themeIcon.className = 'fas fa-sun';
            } else {
                html.setAttribute('data-bs-theme', 'light');
                themeIcon.className = 'fas fa-moon';
            }
        }
    });
}

// Add ripple effect to buttons
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('btn')) {
        const button = e.target;
        const ripple = document.createElement('span');
        const rect = button.getBoundingClientRect();
        const size = Math.max(rect.width, rect.height);
        const x = e.clientX - rect.left - size / 2;
        const y = e.clientY - rect.top - size / 2;
        
        ripple.style.cssText = `
            position: absolute;
            width: ${size}px;
            height: ${size}px;
            left: ${x}px;
            top: ${y}px;
            background: rgba(255, 255, 255, 0.3);
            border-radius: 50%;
            transform: scale(0);
            animation: ripple 0.6s linear;
            pointer-events: none;
        `;
        
        button.style.position = 'relative';
        button.style.overflow = 'hidden';
        button.appendChild(ripple);
        
        setTimeout(() => {
            if (ripple.parentNode) {
                ripple.parentNode.removeChild(ripple);
            }
        }, 600);
    }
});

// Add CSS for ripple animation
const style = document.createElement('style');
style.textContent = `
    @keyframes ripple {
        to {
            transform: scale(4);
            opacity: 0;
        }
    }
`;
document.head.appendChild(style);
