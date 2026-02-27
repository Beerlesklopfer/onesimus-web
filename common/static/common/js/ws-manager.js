// SPDX-FileCopyrightText: 2025-2026 Jörg Bernau <joerg.bernau@onesimus.io>
// SPDX-License-Identifier: MIT

/**
 * WebSocket Manager
 * Handles WebSocket connections for real-time updates
 */

class WebSocketManager {
    constructor() {
        this.socket = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 3000;
        this.connected = false;
        this.url = this.getWebSocketUrl();
    }

    /**
     * Determine WebSocket URL
     */
    getWebSocketUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        return `${protocol}//${window.location.host}/ws/notifications/`;
    }

    /**
     * Connect to WebSocket
     */
    connect() {
        console.log('Connecting to WebSocket:', this.url);

        try {
            this.socket = new WebSocket(this.url);

            this.socket.onopen = (event) => {
                console.log('WebSocket connected');
                this.connected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus(true);
            };

            this.socket.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };

            this.socket.onerror = (event) => {
                console.error('WebSocket error:', event);
                this.updateConnectionStatus(false);
            };

            this.socket.onclose = (event) => {
                console.warn('WebSocket disconnected');
                this.connected = false;
                this.updateConnectionStatus(false);
                this.attemptReconnect();
            };
        } catch (error) {
            console.error('Error creating WebSocket:', error);
            this.updateConnectionStatus(false);
            this.attemptReconnect();
        }
    }

    /**
     * Handle incoming WebSocket messages
     */
    handleMessage(data) {
        const { type, message, data: msgData } = data;

        // Dispatch custom event for components to listen
        document.dispatchEvent(new CustomEvent('ws-message', {
            detail: { type, message, data: msgData }
        }));

        // Log message type
        console.log('WebSocket message:', type, message);
    }

    /**
     * Send message to WebSocket
     */
    send(message) {
        if (this.connected && this.socket && this.socket.readyState === WebSocket.OPEN) {
            this.socket.send(JSON.stringify(message));
        } else {
            console.warn('WebSocket not connected, queueing message:', message);
        }
    }

    /**
     * Attempt to reconnect
     */
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Reconnecting in ${this.reconnectDelay}ms (attempt ${this.reconnectAttempts})`);

            setTimeout(() => {
                this.connect();
            }, this.reconnectDelay);
        } else {
            console.error('Max reconnection attempts reached');
        }
    }

    /**
     * Update connection status in UI
     */
    updateConnectionStatus(isConnected) {
        const statusElement = document.getElementById('connection-status');
        const statusText = document.getElementById('connection-text');

        if (statusElement && statusText) {
            const dot = statusElement.querySelector('.status-dot');
            if (isConnected) {
                dot?.classList.remove('offline');
                dot?.classList.add('online');
                statusText.textContent = 'Connected';
                statusText.classList.remove('text-muted');
                statusText.classList.add('text-success');
            } else {
                dot?.classList.remove('online');
                dot?.classList.add('offline');
                statusText.textContent = 'Disconnected';
                statusText.classList.add('text-muted');
                statusText.classList.remove('text-success');
            }
        }
    }

    /**
     * Subscribe to a specific update channel
     */
    subscribe(channel, callback) {
        document.addEventListener('ws-message', (event) => {
            if (event.detail.type === channel) {
                callback(event.detail.data);
            }
        });
    }

    /**
     * Disconnect WebSocket
     */
    disconnect() {
        if (this.socket) {
            this.socket.close();
            this.socket = null;
            this.connected = false;
            this.updateConnectionStatus(false);
        }
    }
}

// Initialize WebSocket Manager on page load
let wsManager = null;

document.addEventListener('DOMContentLoaded', () => {
    wsManager = new WebSocketManager();
    wsManager.connect();
});

// Clean up on page unload
window.addEventListener('beforeunload', () => {
    if (wsManager) {
        wsManager.disconnect();
    }
});
