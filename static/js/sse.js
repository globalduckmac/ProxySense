/**
 * Server-Sent Events (SSE) handling for real-time updates
 */

// SSE connection management
const SSE = {
    connections: new Map(),
    retryTimeouts: new Map()
};

/**
 * Start SSE connection for dashboard updates
 */
function startDashboardSSE() {
    if (SSE.connections.has('dashboard')) {
        SSE.connections.get('dashboard').close();
    }
    
    const eventSource = new EventSource('/api/ui/dashboard/stream');
    SSE.connections.set('dashboard', eventSource);
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            updateDashboardStats(data);
        } catch (e) {
            console.error('Failed to parse dashboard data:', e);
        }
    };
    
    eventSource.onerror = function(event) {
        console.warn('Dashboard SSE connection error, will retry in 5 seconds');
        eventSource.close();
        SSE.connections.delete('dashboard');
        
        // Retry after 5 seconds
        setTimeout(() => {
            if (!SSE.connections.has('dashboard')) {
                startDashboardSSE();
            }
        }, 5000);
    };
    
    eventSource.onopen = function(event) {
        console.log('Dashboard SSE connection established');
    };
}

/**
 * Update dashboard statistics display
 */
function updateDashboardStats(stats) {
    // Update server stats
    const serverStats = document.querySelector('.stat-card .stat-number');
    if (serverStats && stats.total_servers !== undefined) {
        serverStats.textContent = `${stats.online_servers}/${stats.total_servers}`;
    }
    
    // Update domain stats
    const domainStats = document.querySelectorAll('.stat-card .stat-number')[1];
    if (domainStats && stats.ssl_domains !== undefined) {
        domainStats.textContent = `${stats.ssl_domains}/${stats.total_domains}`;
    }
    
    // Update alerts
    const alertStats = document.querySelectorAll('.stat-card .stat-number')[2];
    if (alertStats && stats.unresolved_alerts !== undefined) {
        alertStats.textContent = stats.unresolved_alerts;
    }
    
    // Update overview section if present
    const overviewItems = document.querySelectorAll('.overview-value');
    if (overviewItems.length >= 4) {
        overviewItems[0].textContent = stats.total_servers;
        overviewItems[1].textContent = stats.online_servers;
        overviewItems[2].textContent = stats.total_domains;
        overviewItems[3].textContent = stats.ssl_domains;
    }
}

/**
 * Start task progress SSE
 */
function startTaskProgressSSE(taskId) {
    const connectionKey = `task-${taskId}`;
    
    if (SSE.connections.has(connectionKey)) {
        SSE.connections.get(connectionKey).close();
    }
    
    const eventSource = new EventSource(`/api/tasks/${taskId}/stream`);
    SSE.connections.set(connectionKey, eventSource);
    
    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            updateTaskProgress(data);
        } catch (e) {
            console.error('Failed to parse task data:', e);
        }
    };
    
    eventSource.onerror = function(event) {
        console.warn('Task SSE connection error');
        eventSource.close();
        SSE.connections.delete(connectionKey);
    };
}

/**
 * Update task progress modal
 */
function updateTaskProgress(data) {
    const progress = document.getElementById('task-progress');
    const status = document.getElementById('task-status');
    const logs = document.getElementById('task-logs');
    
    if (progress && data.progress !== undefined) {
        progress.style.width = `${data.progress}%`;
    }
    
    if (status && data.status) {
        // Map status values to user-friendly text
        const statusMap = {
            'PENDING': 'Pending...',
            'RUNNING': 'Running...',
            'COMPLETED': 'Completed ✓',
            'FAILED': 'Failed ✗',
            'pending': 'Pending...',
            'running': 'Running...',
            'completed': 'Completed ✓',
            'failed': 'Failed ✗'
        };
        status.textContent = statusMap[data.status] || data.status;
    }
    
    // Handle different log formats
    if (logs && (data.log || data.message)) {
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        
        if (data.message) {
            // Full log entry format
            const timestamp = data.timestamp ? new Date(data.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
            logEntry.innerHTML = `
                <span class="log-timestamp">[${timestamp}]</span>
                <span class="log-level">${data.level || 'INFO'}</span>
                <span class="log-message">${data.message}</span>
            `;
        } else if (data.log) {
            // Simple log format
            logEntry.textContent = data.log;
        }
        
        logs.appendChild(logEntry);
        logs.scrollTop = logs.scrollHeight;
    }
    
    // Close modal if task is complete
    if (data.status === 'COMPLETED' || data.status === 'FAILED' || 
        data.status === 'completed' || data.status === 'failed') {
        setTimeout(() => {
            closeTaskModal();
            if (data.status === 'COMPLETED' || data.status === 'completed') {
                showNotification('Task completed successfully', 'success');
            } else {
                showNotification('Task failed', 'error');
            }
        }, 2000);
    }
}

/**
 * Close task progress modal
 */
function closeTaskModal() {
    const modal = document.getElementById('task-modal');
    if (modal) {
        modal.style.display = 'none';
        
        // Close any task SSE connections
        for (const [key, connection] of SSE.connections.entries()) {
            if (key.startsWith('task-')) {
                connection.close();
                SSE.connections.delete(key);
            }
        }
    }
}

/**
 * Stop all SSE connections
 */
function stopAllSSE() {
    for (const [key, connection] of SSE.connections.entries()) {
        connection.close();
    }
    SSE.connections.clear();
    
    for (const timeout of SSE.retryTimeouts.values()) {
        clearTimeout(timeout);
    }
    SSE.retryTimeouts.clear();
}

// Auto-start dashboard SSE if on dashboard page
document.addEventListener('DOMContentLoaded', function() {
    if (window.location.pathname === '/' || window.location.pathname === '/dashboard') {
        startDashboardSSE();
    }
});

// Stop SSE connections when page is hidden
document.addEventListener('visibilitychange', function() {
    if (document.hidden) {
        console.log('Page hidden, pausing updates');
        stopAllSSE();
    } else {
        console.log('Page visible, resuming updates');
        if (window.location.pathname === '/' || window.location.pathname === '/dashboard') {
            startDashboardSSE();
        }
    }
});

// Export functions for global access
window.startDashboardSSE = startDashboardSSE;
window.startTaskProgressSSE = startTaskProgressSSE;
window.closeTaskModal = closeTaskModal;
window.updateDashboardStats = updateDashboardStats;