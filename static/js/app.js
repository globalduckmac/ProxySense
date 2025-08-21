/**
 * Reverse Proxy & Monitor - Main Application JavaScript
 */

// Global application state
const App = {
    currentUser: null,
    authToken: null,
    notifications: [],
    activeModals: new Set(),
    sseConnections: new Map()
};

// Initialize application when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    initializeApp();
});

/**
 * Initialize the application
 */
function initializeApp() {
    // Load authentication token from cookies
    App.authToken = getCookie('access_token');
    
    // Initialize notification system
    initializeNotifications();
    
    // Initialize modal handlers
    initializeModals();
    
    // Initialize form handlers
    initializeForms();
    
    // Initialize real-time features
    initializeRealTimeUpdates();
    
    // Initialize server status monitoring for servers page
    if (window.location.pathname === '/servers') {
        initializeServerStatusUpdates();
    }
    
    // Auto-close alerts after 5 seconds
    autoCloseAlerts();
    
    console.log('Reverse Proxy & Monitor initialized');
}

/**
 * Authentication and Token Management
 */
function getAuthToken() {
    return App.authToken || getCookie('access_token');
}

function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) {
        return parts.pop().split(';').shift();
    }
    return null;
}

function setCookie(name, value, days = 30) {
    const expires = new Date();
    expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
    document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/`;
}

function deleteCookie(name) {
    document.cookie = `${name}=;expires=Thu, 01 Jan 1970 00:00:01 GMT;path=/`;
}

/**
 * HTTP Request Utilities
 */
async function apiRequest(url, options = {}) {
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json'
        },
        credentials: 'include'  // Include cookies for authentication
    };
    
    const mergedOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    };
    
    try {
        const response = await fetch(url, mergedOptions);
        
        if (response.status === 401) {
            // Unauthorized - redirect to login
            window.location.href = '/auth/login';
            return null;
        }
        
        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
        }
        
        const contentType = response.headers.get('content-type');
        if (contentType && contentType.includes('application/json')) {
            return await response.json();
        }
        
        return await response.text();
    } catch (error) {
        console.error('API Request failed:', error);
        throw error;
    }
}

/**
 * Notification System
 */
function initializeNotifications() {
    // Create notification container if it doesn't exist
    if (!document.getElementById('alert-container')) {
        const container = document.createElement('div');
        container.id = 'alert-container';
        container.className = 'alert-container';
        document.body.appendChild(container);
    }
}

function showNotification(message, type = 'info', duration = 5000) {
    const container = document.getElementById('alert-container');
    if (!container) return;
    
    const alert = document.createElement('div');
    alert.className = `alert ${type}`;
    alert.innerHTML = `
        <span>${message}</span>
        <button onclick="closeNotification(this)" style="background:none;border:none;color:inherit;float:right;font-size:1.2em;cursor:pointer;">&times;</button>
    `;
    
    container.appendChild(alert);
    App.notifications.push(alert);
    
    // Auto-remove after duration
    if (duration > 0) {
        setTimeout(() => {
            closeNotification(alert);
        }, duration);
    }
    
    return alert;
}

function closeNotification(element) {
    const alert = element.closest ? element.closest('.alert') : element;
    if (alert && alert.parentNode) {
        alert.style.transform = 'translateX(100%)';
        setTimeout(() => {
            alert.remove();
            const index = App.notifications.indexOf(alert);
            if (index > -1) {
                App.notifications.splice(index, 1);
            }
        }, 300);
    }
}

function autoCloseAlerts() {
    setInterval(() => {
        const alerts = document.querySelectorAll('.alert');
        alerts.forEach(alert => {
            if (alert.dataset.autoClose !== 'false') {
                const age = Date.now() - (alert.dataset.created || Date.now());
                if (age > 5000) {
                    closeNotification(alert);
                }
            }
        });
    }, 1000);
}

/**
 * Loading States
 */
function showLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = 'flex';
    }
}

function hideLoading() {
    const overlay = document.getElementById('loading-overlay');
    if (overlay) {
        overlay.style.display = 'none';
    }
}

/**
 * Modal Management
 */
function initializeModals() {
    // Close modals when clicking outside
    document.addEventListener('click', function(event) {
        if (event.target.classList.contains('modal')) {
            const modalId = event.target.id;
            if (modalId) {
                closeModal(modalId);
            }
        }
    });
    
    // Close modals on Escape key
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            const visibleModals = document.querySelectorAll('.modal[style*="flex"]');
            visibleModals.forEach(modal => {
                closeModal(modal.id);
            });
        }
    });
}

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'flex';
        App.activeModals.add(modalId);
        
        // Focus first input in modal
        const firstInput = modal.querySelector('input, select, textarea');
        if (firstInput) {
            setTimeout(() => firstInput.focus(), 100);
        }
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
        App.activeModals.delete(modalId);
        
        // Clear any SSE connections for this modal
        if (App.sseConnections.has(modalId)) {
            App.sseConnections.get(modalId).close();
            App.sseConnections.delete(modalId);
        }
    }
}

/**
 * Task Progress Modal
 */
function openTaskProgressModal(taskId, taskName) {
    const modal = document.getElementById('task-modal');
    if (!modal) return;
    
    const title = document.getElementById('task-modal-title');
    const progress = document.getElementById('task-progress');
    const status = document.getElementById('task-status');
    const logs = document.getElementById('task-logs');
    
    if (title) title.textContent = taskName || 'Task Progress';
    if (progress) progress.style.width = '0%';
    if (status) status.textContent = 'Initializing...';
    if (logs) logs.innerHTML = '';
    
    modal.style.display = 'flex';
    
    // Start SSE connection for real-time updates
    startTaskProgressSSE(taskId);
}

function closeTaskModal() {
    closeModal('task-modal');
}

function startTaskProgressSSE(taskId) {
    const modal = document.getElementById('task-modal');
    if (!modal) return;
    
    const eventSource = new EventSource(`/api/tasks/${taskId}/stream`);
    App.sseConnections.set('task-modal', eventSource);
    
    const progress = document.getElementById('task-progress');
    const status = document.getElementById('task-status');
    const logs = document.getElementById('task-logs');
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            if (data.type === 'status') {
                // Update task status and progress
                if (progress) progress.style.width = `${data.progress || 0}%`;
                if (status) status.textContent = data.status || 'Unknown';
                
                // Close modal if task is completed
                if (data.status === 'completed' || data.status === 'failed') {
                    setTimeout(() => {
                        closeTaskModal();
                        if (data.status === 'completed') {
                            showNotification('Task completed successfully', 'success');
                        } else {
                            showNotification('Task failed: ' + (data.error_message || 'Unknown error'), 'error');
                        }
                    }, 2000);
                }
            } else if (data.type === 'error') {
                showNotification('Task stream error: ' + data.message, 'error');
                closeTaskModal();
            } else {
                // Regular log entry
                if (logs) {
                    const logEntry = document.createElement('div');
                    logEntry.className = `log-entry log-${(data.level || 'info').toLowerCase()}`;
                    
                    const timestamp = new Date(data.timestamp).toLocaleTimeString();
                    logEntry.innerHTML = `
                        <div class="log-header">
                            <span class="log-timestamp">[${timestamp}]</span>
                            <span class="log-level">${data.level || 'INFO'}</span>
                            <span class="log-source">(${data.source || 'system'})</span>
                        </div>
                        <div class="log-message">${data.message || ''}</div>
                        ${data.stdout ? `<div class="log-stdout"><pre>${data.stdout}</pre></div>` : ''}
                        ${data.stderr ? `<div class="log-stderr"><pre>${data.stderr}</pre></div>` : ''}
                        ${data.return_code !== null ? `<div class="log-return-code">Exit code: ${data.return_code}</div>` : ''}
                    `;
                    
                    logs.appendChild(logEntry);
                    logs.scrollTop = logs.scrollHeight; // Auto-scroll to bottom
                }
            }
        } catch (error) {
            console.error('Error parsing SSE message:', error);
        }
    };
    
    eventSource.onerror = function(event) {
        console.error('SSE connection error:', event);
        eventSource.close();
        App.sseConnections.delete('task-modal');
    };
}

/**
 * Form Utilities
 */
function initializeForms() {
    // Handle form submissions with loading states
    document.addEventListener('submit', function(event) {
        const form = event.target;
        if (form.tagName === 'FORM' && !form.dataset.noLoading) {
            const submitButton = form.querySelector('[type="submit"]');
            if (submitButton) {
                const originalText = submitButton.textContent;
                submitButton.disabled = true;
                submitButton.textContent = 'Please wait...';
                
                // Re-enable button after 10 seconds as a failsafe
                setTimeout(() => {
                    submitButton.disabled = false;
                    submitButton.textContent = originalText;
                }, 10000);
            }
        }
    });
}

function resetForm(formId) {
    const form = document.getElementById(formId);
    if (form) {
        form.reset();
        
        // Clear any validation states
        const inputs = form.querySelectorAll('.form-input, .form-select, .form-textarea');
        inputs.forEach(input => {
            input.classList.remove('is-invalid', 'is-valid');
        });
        
        // Re-enable submit button
        const submitButton = form.querySelector('[type="submit"]');
        if (submitButton) {
            submitButton.disabled = false;
        }
    }
}

function validateForm(form) {
    let isValid = true;
    const requiredFields = form.querySelectorAll('[required]');
    
    requiredFields.forEach(field => {
        if (!field.value.trim()) {
            field.classList.add('is-invalid');
            isValid = false;
        } else {
            field.classList.remove('is-invalid');
            field.classList.add('is-valid');
        }
    });
    
    // Email validation
    const emailFields = form.querySelectorAll('input[type="email"]');
    emailFields.forEach(field => {
        if (field.value && !isValidEmail(field.value)) {
            field.classList.add('is-invalid');
            isValid = false;
        }
    });
    
    // URL validation
    const urlFields = form.querySelectorAll('input[type="url"]');
    urlFields.forEach(field => {
        if (field.value && !isValidURL(field.value)) {
            field.classList.add('is-invalid');
            isValid = false;
        }
    });
    
    return isValid;
}

function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

function isValidURL(url) {
    try {
        new URL(url);
        return true;
    } catch (e) {
        return false;
    }
}

/**
 * Real-time Updates
 */
function initializeRealTimeUpdates() {
    // Initialize dashboard real-time updates if on dashboard
    if (window.location.pathname === '/') {
        startDashboardUpdates();
    }
    
    // Initialize server status updates if on servers page
    if (window.location.pathname === '/servers') {
        startServerStatusUpdates();
    }
}

function startDashboardUpdates() {
    // Update dashboard stats every 30 seconds
    setInterval(async () => {
        try {
            const data = await apiRequest('/api/ui/dashboard/stats');
            if (data) {
                updateDashboardStats(data);
            }
        } catch (error) {
            console.error('Failed to update dashboard stats:', error);
        }
    }, 30000);
}

function updateDashboardStats(data) {
    // Update server stats
    const serverStats = document.querySelector('.stat-card .stat-number');
    if (serverStats && data.servers) {
        serverStats.textContent = `${data.servers.online}/${data.servers.total}`;
    }
    
    // Update other stats as needed
    // This would be expanded based on the actual dashboard structure
}

function startServerStatusUpdates() {
    // Update server statuses every 60 seconds
    setInterval(async () => {
        try {
            const servers = await apiRequest('/api/servers/');
            if (servers) {
                updateServerCards(servers);
            }
        } catch (error) {
            console.error('Failed to update server statuses:', error);
        }
    }, 60000);
}

function updateServerCards(servers) {
    servers.forEach(server => {
        const serverCard = document.querySelector(`[data-server-id="${server.id}"]`);
        if (serverCard) {
            const statusElement = serverCard.querySelector('.server-status');
            if (statusElement) {
                // Update status classes
                statusElement.className = `server-status status-${server.status}`;
                
                // Update status icon and text
                const statusIcon = statusElement.querySelector('svg');
                const statusText = statusElement.querySelector('.status-text');
                
                if (statusIcon && statusText) {
                    updateStatusIcon(statusIcon, server.status);
                    statusText.textContent = server.status.charAt(0).toUpperCase() + server.status.slice(1);
                }
            }
        }
    });
}

function updateStatusIcon(iconElement, status) {
    let iconPath = '';
    
    switch (status) {
        case 'ok':
            iconPath = 'M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41z';
            break;
        case 'unreachable':
            iconPath = 'M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z';
            break;
        default:
            iconPath = 'M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 18c-4.41 0-8-3.59-8-8s3.59-8 8-8 8 3.59 8 8-3.59 8-8 8z';
    }
    
    iconElement.innerHTML = `<path d="${iconPath}"/>`;
}

/**
 * Data Formatting Utilities
 */
function formatBytes(bytes, decimals = 2) {
    if (bytes === 0) return '0 Bytes';
    
    const k = 1024;
    const dm = decimals < 0 ? 0 : decimals;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB', 'PB'];
    
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    
    return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
}

function formatDuration(seconds) {
    const units = [
        { name: 'year', seconds: 31536000 },
        { name: 'month', seconds: 2628000 },
        { name: 'week', seconds: 604800 },
        { name: 'day', seconds: 86400 },
        { name: 'hour', seconds: 3600 },
        { name: 'minute', seconds: 60 },
        { name: 'second', seconds: 1 }
    ];
    
    for (const unit of units) {
        const count = Math.floor(seconds / unit.seconds);
        if (count >= 1) {
            return `${count} ${unit.name}${count > 1 ? 's' : ''}`;
        }
    }
    
    return '0 seconds';
}

function formatDate(dateString, options = {}) {
    const date = new Date(dateString);
    const defaultOptions = {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    
    return date.toLocaleDateString('en-US', { ...defaultOptions, ...options });
}

function formatPercentage(value, decimals = 1) {
    if (typeof value !== 'number') return 'N/A';
    return `${value.toFixed(decimals)}%`;
}

/**
 * Search and Filter Utilities
 */
function debounce(func, wait, immediate) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            timeout = null;
            if (!immediate) func(...args);
        };
        const callNow = immediate && !timeout;
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
        if (callNow) func(...args);
    };
}

function setupSearch(inputId, targetSelector, searchAttribute = 'data-name') {
    const searchInput = document.getElementById(inputId);
    if (!searchInput) return;
    
    const debouncedSearch = debounce((searchTerm) => {
        const items = document.querySelectorAll(targetSelector);
        items.forEach(item => {
            const searchValue = item.getAttribute(searchAttribute)?.toLowerCase() || '';
            const matches = searchValue.includes(searchTerm.toLowerCase());
            item.style.display = matches ? '' : 'none';
        });
    }, 300);
    
    searchInput.addEventListener('input', (e) => {
        debouncedSearch(e.target.value);
    });
}

/**
 * Chart and Visualization Utilities
 */
function createMiniChart(canvasId, data, options = {}) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return null;
    
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    
    // Clear canvas
    ctx.clearRect(0, 0, width, height);
    
    if (!data || data.length === 0) {
        // Draw "No Data" message
        ctx.fillStyle = '#6c757d';
        ctx.font = '12px sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('No Data', width / 2, height / 2);
        return null;
    }
    
    // Default options
    const defaultOptions = {
        color: '#007bff',
        backgroundColor: 'rgba(0, 123, 255, 0.1)',
        lineWidth: 2,
        showFill: true,
        showPoints: false
    };
    
    const config = { ...defaultOptions, ...options };
    
    // Calculate scaling
    const maxValue = Math.max(...data);
    const minValue = Math.min(...data);
    const range = maxValue - minValue || 1;
    
    const xStep = width / (data.length - 1);
    const yScale = height / range;
    
    // Draw filled area
    if (config.showFill) {
        ctx.beginPath();
        ctx.moveTo(0, height);
        
        data.forEach((value, index) => {
            const x = index * xStep;
            const y = height - ((value - minValue) * yScale);
            
            if (index === 0) {
                ctx.lineTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        });
        
        ctx.lineTo(width, height);
        ctx.closePath();
        ctx.fillStyle = config.backgroundColor;
        ctx.fill();
    }
    
    // Draw line
    ctx.beginPath();
    data.forEach((value, index) => {
        const x = index * xStep;
        const y = height - ((value - minValue) * yScale);
        
        if (index === 0) {
            ctx.moveTo(x, y);
        } else {
            ctx.lineTo(x, y);
        }
    });
    
    ctx.strokeStyle = config.color;
    ctx.lineWidth = config.lineWidth;
    ctx.stroke();
    
    // Draw points
    if (config.showPoints) {
        data.forEach((value, index) => {
            const x = index * xStep;
            const y = height - ((value - minValue) * yScale);
            
            ctx.beginPath();
            ctx.arc(x, y, 2, 0, 2 * Math.PI);
            ctx.fillStyle = config.color;
            ctx.fill();
        });
    }
    
    return {
        canvas,
        data,
        config,
        update: (newData) => createMiniChart(canvasId, newData, config)
    };
}

/**
 * Clipboard Utilities
 */
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showNotification('Copied to clipboard', 'success', 2000);
        return true;
    } catch (error) {
        console.error('Failed to copy to clipboard:', error);
        
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = text;
        textArea.style.position = 'fixed';
        textArea.style.left = '-999999px';
        textArea.style.top = '-999999px';
        document.body.appendChild(textArea);
        textArea.focus();
        textArea.select();
        
        try {
            const successful = document.execCommand('copy');
            if (successful) {
                showNotification('Copied to clipboard', 'success', 2000);
            } else {
                showNotification('Failed to copy to clipboard', 'error');
            }
            return successful;
        } catch (err) {
            showNotification('Failed to copy to clipboard', 'error');
            return false;
        } finally {
            document.body.removeChild(textArea);
        }
    }
}

/**
 * Export/Download Utilities
 */
function downloadJSON(data, filename) {
    const blob = new Blob([JSON.stringify(data, null, 2)], { 
        type: 'application/json' 
    });
    downloadBlob(blob, filename);
}

function downloadText(text, filename) {
    const blob = new Blob([text], { type: 'text/plain' });
    downloadBlob(blob, filename);
}

function downloadBlob(blob, filename) {
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
}

/**
 * Local Storage Utilities
 */
function saveToLocalStorage(key, data) {
    try {
        localStorage.setItem(key, JSON.stringify(data));
        return true;
    } catch (error) {
        console.error('Failed to save to localStorage:', error);
        return false;
    }
}

function loadFromLocalStorage(key, defaultValue = null) {
    try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : defaultValue;
    } catch (error) {
        console.error('Failed to load from localStorage:', error);
        return defaultValue;
    }
}

function removeFromLocalStorage(key) {
    try {
        localStorage.removeItem(key);
        return true;
    } catch (error) {
        console.error('Failed to remove from localStorage:', error);
        return false;
    }
}

/**
 * Upstream Management Functions
 */
function openUpstreamModal(upstreamId = null) {
    const modal = document.getElementById('upstream-modal');
    const form = document.getElementById('upstream-form');
    const title = document.getElementById('upstream-modal-title');
    
    if (!modal || !form || !title) {
        console.error('Upstream modal elements not found');
        return;
    }
    
    // Reset form
    form.reset();
    clearTargets();
    
    if (upstreamId) {
        title.textContent = 'Edit Upstream';
        loadUpstreamData(upstreamId);
    } else {
        title.textContent = 'Add Upstream';
        addTarget(); // Add one default target
    }
    
    modal.style.display = 'block';
    App.activeModals.add('upstream-modal');
}

function closeUpstreamModal() {
    const modal = document.getElementById('upstream-modal');
    if (modal) {
        modal.style.display = 'none';
        App.activeModals.delete('upstream-modal');
    }
}

function addTarget() {
    const container = document.getElementById('targets-container');
    if (!container) return;
    
    const targetCount = container.children.length;
    const targetHtml = `
        <div class="target-item">
            <div class="form-row">
                <div class="form-group">
                    <label>Host</label>
                    <input type="text" name="targets[${targetCount}][host]" placeholder="192.168.1.100" required>
                </div>
                <div class="form-group">
                    <label>Port</label>
                    <input type="number" name="targets[${targetCount}][port]" placeholder="80" min="1" max="65535" required>
                </div>
                <div class="form-group">
                    <label>Weight</label>
                    <input type="number" name="targets[${targetCount}][weight]" value="1" min="1" max="100">
                </div>
                <div class="form-group">
                    <button type="button" class="btn btn-danger btn-sm" onclick="removeTarget(this)">Remove</button>
                </div>
            </div>
        </div>
    `;
    
    container.insertAdjacentHTML('beforeend', targetHtml);
}

function removeTarget(button) {
    const targetItem = button.closest('.target-item');
    if (targetItem) {
        targetItem.remove();
        reindexTargets();
    }
}

function clearTargets() {
    const container = document.getElementById('targets-container');
    if (container) {
        container.innerHTML = '';
    }
}

function reindexTargets() {
    const container = document.getElementById('targets-container');
    if (!container) return;
    
    const targets = container.querySelectorAll('.target-item');
    targets.forEach((target, index) => {
        const inputs = target.querySelectorAll('input[name^="targets"]');
        inputs.forEach(input => {
            const name = input.name;
            const field = name.match(/\[(\w+)\]$/)[1];
            input.name = `targets[${index}][${field}]`;
        });
    });
}

async function saveUpstream() {
    const form = document.getElementById('upstream-form');
    if (!form) return;
    
    const formData = new FormData(form);
    const data = {
        name: formData.get('name'),
        targets: []
    };
    
    // Collect targets
    const container = document.getElementById('targets-container');
    const targets = container.querySelectorAll('.target-item');
    
    targets.forEach((target, index) => {
        const host = target.querySelector(`input[name="targets[${index}][host]"]`)?.value;
        const port = parseInt(target.querySelector(`input[name="targets[${index}][port]"]`)?.value);
        const weight = parseInt(target.querySelector(`input[name="targets[${index}][weight]"]`)?.value) || 1;
        
        if (host && port) {
            data.targets.push({ host, port, weight });
        }
    });
    
    if (data.targets.length === 0) {
        showNotification('At least one target is required', 'error');
        return;
    }
    
    try {
        showLoading('Saving upstream...');
        
        const response = await apiRequest('/api/upstreams/', {
            method: 'POST',
            body: JSON.stringify(data)
        });
        
        if (response) {
            showNotification('Upstream saved successfully', 'success');
            closeUpstreamModal();
            // Reload page to show new upstream
            window.location.reload();
        }
    } catch (error) {
        showNotification(`Failed to save upstream: ${error.message}`, 'error');
    } finally {
        hideLoading();
    }
}

async function deleteUpstream(upstreamId) {
    if (!confirm('Are you sure you want to delete this upstream?')) {
        return;
    }
    
    try {
        showLoading('Deleting upstream...');
        
        const response = await apiRequest(`/api/upstreams/${upstreamId}`, {
            method: 'DELETE'
        });
        
        if (response !== null) {
            showNotification('Upstream deleted successfully', 'success');
            // Remove the upstream card from the page
            const upstreamCard = document.querySelector(`[data-upstream-id="${upstreamId}"]`);
            if (upstreamCard) {
                upstreamCard.remove();
            }
        }
    } catch (error) {
        showNotification(`Failed to delete upstream: ${error.message}`, 'error');
    } finally {
        hideLoading();
    }
}

function filterUpstreams() {
    const searchInput = document.getElementById('upstream-search');
    const searchTerm = searchInput.value.toLowerCase();
    const upstreamCards = document.querySelectorAll('.upstream-card');
    
    upstreamCards.forEach(card => {
        const name = card.getAttribute('data-name') || '';
        const matches = name.includes(searchTerm);
        card.style.display = matches ? '' : 'none';
    });
}

/**
 * Server Management Functions  
 */
function openServerModal(serverId = null) {
    const modal = document.getElementById('server-modal');
    const form = document.getElementById('server-form');
    const title = document.getElementById('server-modal-title');
    
    if (!modal || !form || !title) {
        console.error('Server modal elements not found');
        return;
    }
    
    // Reset form
    form.reset();
    
    if (serverId) {
        title.textContent = 'Edit Server';
        loadServerData(serverId);
    } else {
        title.textContent = 'Add Server';
    }
    
    modal.style.display = 'block';
    App.activeModals.add('server-modal');
}

function closeServerModal() {
    const modal = document.getElementById('server-modal');
    if (modal) {
        modal.style.display = 'none';
        App.activeModals.delete('server-modal');
    }
}

/**
 * Error Handling
 */
window.addEventListener('error', function(event) {
    console.error('Global error:', event.error);
    
    // Don't show notifications for every error to avoid spam
    if (event.error && event.error.message && !event.error.message.includes('Script error')) {
        showNotification('An unexpected error occurred', 'error');
    }
});

window.addEventListener('unhandledrejection', function(event) {
    console.error('Unhandled promise rejection:', event.reason);
    
    if (event.reason && event.reason.message) {
        showNotification('Operation failed: ' + event.reason.message, 'error');
    }
});

/**
 * Page Visibility and Focus Management
 */
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        // Page is hidden, pause non-essential updates
        console.log('Page hidden, pausing updates');
    } else {
        // Page is visible, resume updates
        console.log('Page visible, resuming updates');
        
        // Refresh data if page was hidden for more than 5 minutes
        const lastUpdate = loadFromLocalStorage('lastUpdate');
        if (!lastUpdate || Date.now() - lastUpdate > 300000) {
            location.reload();
        }
    }
});

/**
 * Keyboard Shortcuts
 */
document.addEventListener('keydown', function(event) {
    // Ctrl/Cmd + K for search
    if ((event.ctrlKey || event.metaKey) && event.key === 'k') {
        event.preventDefault();
        const searchInput = document.querySelector('input[type="search"], input[placeholder*="search" i]');
        if (searchInput) {
            searchInput.focus();
        }
    }
    
    // Escape to close modals
    if (event.key === 'Escape') {
        const visibleModals = Array.from(App.activeModals);
        if (visibleModals.length > 0) {
            closeModal(visibleModals[visibleModals.length - 1]);
        }
    }
});

/**
 * Cleanup on page unload
 */
window.addEventListener('beforeunload', function() {
    // Close all SSE connections
    App.sseConnections.forEach((connection) => {
        connection.close();
    });
    App.sseConnections.clear();
    
    // Save last update time
    saveToLocalStorage('lastUpdate', Date.now());
});

// Expose utilities globally for use in templates
window.App = App;
window.apiRequest = apiRequest;
window.showNotification = showNotification;
window.hideLoading = hideLoading;
window.showLoading = showLoading;
window.openModal = openModal;
window.closeModal = closeModal;
window.openTaskProgressModal = openTaskProgressModal;
window.closeTaskModal = closeTaskModal;
window.getAuthToken = getAuthToken;
window.copyToClipboard = copyToClipboard;
window.downloadJSON = downloadJSON;
window.downloadText = downloadText;
window.formatBytes = formatBytes;
window.formatDuration = formatDuration;
window.formatDate = formatDate;
window.formatPercentage = formatPercentage;
window.createMiniChart = createMiniChart;

// Server status update functions
function initializeServerStatusUpdates() {
    // Update server statuses every 10 seconds
    setInterval(async () => {
        try {
            const data = await apiRequest('/api/servers/status');
            if (data && data.servers) {
                updateServerStatuses(data.servers);
            }
        } catch (error) {
            console.error('Failed to update server statuses:', error);
        }
    }, 10000);
}

function updateServerStatuses(servers) {
    servers.forEach(server => {
        // Update status badge
        const serverCard = document.querySelector(`[data-server-id="${server.id}"]`);
        if (serverCard) {
            const statusBadge = serverCard.querySelector('.status-badge');
            if (statusBadge) {
                statusBadge.className = `status-badge status-${server.status}`;
                statusBadge.textContent = server.status.charAt(0).toUpperCase() + server.status.slice(1);
            }
        }
        
        // Update last check time
        const lastCheckElement = document.getElementById(`last-check-${server.id}`);
        if (lastCheckElement && server.last_check_at) {
            const checkTime = new Date(server.last_check_at);
            lastCheckElement.textContent = checkTime.toLocaleTimeString();
        }
    });
}
