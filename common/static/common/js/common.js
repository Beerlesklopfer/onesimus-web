// SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
// SPDX-License-Identifier: MIT

/**
 * Common JavaScript Utilities
 */

/**
 * Show toast notification
 */
function showNotification(message, type = 'info', duration = 3000) {
    const notification = document.createElement('div');
    notification.className = `alert alert-${type} notification`;
    notification.textContent = message;
    notification.style.position = 'fixed';
    notification.style.top = '20px';
    notification.style.right = '20px';
    notification.style.zIndex = '9999';
    notification.style.minWidth = '300px';
    notification.style.animation = 'slideIn 0.3s ease-out';

    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-in';
        setTimeout(() => {
            notification.remove();
        }, 300);
    }, duration);
}

/**
 * Show error notification
 */
function showError(message) {
    showNotification(message, 'error', 5000);
    console.error(message);
}

/**
 * Show success notification
 */
function showSuccess(message) {
    showNotification(message, 'success', 3000);
}

/**
 * Show loading spinner
 */
function showLoader(message = 'Loading...') {
    const loader = document.createElement('div');
    loader.className = 'modal-backdrop show';
    loader.id = 'loader-backdrop';
    loader.innerHTML = `
        <div class="flex-col flex-center gap-md">
            <div class="spinner"></div>
            <p>${message}</p>
        </div>
    `;
    document.body.appendChild(loader);
    return loader;
}

/**
 * Hide loader
 */
function hideLoader() {
    const loader = document.getElementById('loader-backdrop');
    if (loader) {
        loader.remove();
    }
}

/**
 * Debounce function
 */
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

/**
 * Format date to readable string
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString();
}

/**
 * Format bytes to human readable
 */
function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round((bytes / Math.pow(k, i)) * 100) / 100 + ' ' + sizes[i];
}

/**
 * Format duration to human readable
 */
function formatDuration(seconds) {
    if (seconds < 60) return Math.round(seconds) + 's';
    if (seconds < 3600) return Math.round(seconds / 60) + 'm';
    if (seconds < 86400) return Math.round(seconds / 3600) + 'h';
    return Math.round(seconds / 86400) + 'd';
}

/**
 * Copy text to clipboard
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showSuccess('Copied to clipboard');
    }).catch(() => {
        showError('Failed to copy to clipboard');
    });
}

/**
 * Make API request with CSRF token
 */
async function fetchWithCSRF(url, options = {}) {
    const csrfToken = document.querySelector('[name=csrfmiddlewaretoken]')?.value ||
                      document.cookie.split('; ').find(row => row.startsWith('csrftoken='))?.split('=')[1];

    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };

    if (csrfToken) {
        headers['X-CSRFToken'] = csrfToken;
    }

    try {
        const response = await fetch(url, {
            ...options,
            headers,
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        return response;
    } catch (error) {
        showError(`Request failed: ${error.message}`);
        throw error;
    }
}

/**
 * HTMX Event Handlers
 */

// Show loader when HTMX request starts
document.addEventListener('htmx:xhr:loadstart', function() {
    // Only show for longer requests
    setTimeout(() => {
        if (document.body.classList.contains('htmx-request')) {
            // Could show subtle loading indicator here
        }
    }, 500);
});

// Hide loader when HTMX request completes
document.addEventListener('htmx:afterSettle', function() {
    // Remove loading indicator if needed
});

// Handle HTMX errors
document.addEventListener('htmx:responseError', function(evt) {
    showError('Request failed. Please try again.');
    console.error('HTMX Error:', evt);
});

/**
 * Initialize common features
 */
document.addEventListener('DOMContentLoaded', function() {
    // Initialize collapsible sections
    initializeCollapsibles();

    // Initialize tooltips
    initializeTooltips();

    // HTMX indicator styling
    htmx.config.indicatorStyle = 'custom';
});

/**
 * Initialize collapsible sections
 */
function initializeCollapsibles() {
    const collapsibles = document.querySelectorAll('[data-collapsible]');
    collapsibles.forEach(collapsible => {
        const toggle = collapsible.querySelector('[data-toggle-collapsible]');
        if (toggle) {
            toggle.addEventListener('click', function(e) {
                e.preventDefault();
                collapsible.classList.toggle('collapsed');
            });
        }
    });
}

/**
 * Initialize tooltips
 */
function initializeTooltips() {
    const tooltips = document.querySelectorAll('[data-tooltip]');
    tooltips.forEach(element => {
        element.classList.add('tooltip');
        const tooltip = document.createElement('span');
        tooltip.className = 'tooltip-text';
        tooltip.textContent = element.getAttribute('data-tooltip');
        element.appendChild(tooltip);
    });
}

/**
 * CSS Animations
 */
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }

    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }

    .notification {
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }

    .htmx-swapping .htmx-settling {
        opacity: 0;
        transition: opacity 200ms ease-out;
    }

    .htmx-settling {
        opacity: 1;
        transition: opacity 200ms ease-in;
    }
`;
document.head.appendChild(style);

// Export functions for use in other scripts
window.Onesimus = {
    showNotification,
    showError,
    showSuccess,
    showLoader,
    hideLoader,
    debounce,
    formatDate,
    formatBytes,
    formatDuration,
    copyToClipboard,
    fetchWithCSRF,
};
