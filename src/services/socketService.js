// src/services/socketService.js
import { io } from "socket.io-client";
import { useState, useEffect, useCallback } from 'react';

// Create a socket instance
const createSocket = () => {
  const API_URL = process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000';

  // Use the full API URL directly instead of constructing a WebSocket URL
  // Socket.IO client will automatically handle the protocol conversion
  return io(API_URL, {
    // Increase timeout values for very long-running operations
    pingTimeout: 60000, // 60 seconds
    pingInterval: 10000, // 10 seconds - more frequent pings

    // Improve reconnection settings for persistent connections
    reconnection: true,
    reconnectionAttempts: Infinity, // Keep trying to reconnect indefinitely
    reconnectionDelay: 1000, // Start with a 1 second delay
    reconnectionDelayMax: 10000, // Cap at 10 seconds for faster reconnection

    // Connection timeout
    timeout: 20000, // 20 seconds connection timeout

    // Force WebSocket transport only to prevent transport switching issues
    transports: ['websocket'],

    // Path configuration
    path: '/socket.io/',

    // Connection behavior
    autoConnect: true,

    // SSL/TLS configuration for secure connections
    secure: API_URL.startsWith('https'),
    rejectUnauthorized: false, // Allow self-signed certificates

    // Additional headers for CORS and authentication
    extraHeaders: {
      'Origin': window.location.origin,
      'X-Client-Version': '1.0.0'
    }
  });
};

// Singleton socket instance
let socket;

// Get the socket instance (creates it if it doesn't exist)
export const getSocket = () => {
  if (!socket) {
    socket = createSocket();
  }
  return socket;
};

// Hook for using socket.io in React components
export const useSocket = () => {
  const [isConnected, setIsConnected] = useState(false);
  const [connectionAttempts, setConnectionAttempts] = useState(0);
  const [lastError, setLastError] = useState(null);
  const [reconnecting, setReconnecting] = useState(false);

  useEffect(() => {
    const socket = getSocket();

    // Set up event listeners with enhanced logging
    socket.on('connect', () => {
      console.log('Socket connected successfully:', socket.id);
      console.log('Socket transport:', socket.io.engine.transport.name);
      setIsConnected(true);
      setReconnecting(false);
      setConnectionAttempts(0);
      setLastError(null);
    });

    socket.on('disconnect', (reason) => {
      console.log('Socket disconnected, reason:', reason);
      setIsConnected(false);

      // If the server closed the connection, attempt to reconnect manually
      if (reason === 'io server disconnect' || reason === 'transport close') {
        console.log('Server disconnected the socket, attempting to reconnect...');
        setReconnecting(true);

        // Small delay before reconnecting
        setTimeout(() => {
          socket.connect();
        }, 1000);
      }
    });

    socket.on('connect_error', (error) => {
      console.error('Socket connection error:', error);
      console.error('Socket connection error details:', error.message);
      setIsConnected(false);
      setLastError(error.message);
      setConnectionAttempts(prev => prev + 1);
      setReconnecting(true);

      // Log additional connection details for debugging
      console.log('Connection attempts:', connectionAttempts + 1);
      console.log('Current transport:', socket.io.engine?.transport?.name || 'none');
      console.log('Available transports:', socket.io.engine?.transports || []);

      // If we've tried multiple times with websocket, try polling as a fallback
      if (connectionAttempts > 3 && socket.io.opts.transports[0] === 'websocket') {
        console.log('Multiple websocket connection failures, adding polling transport as fallback');
        socket.io.opts.transports = ['websocket', 'polling'];
      }
    });

    // Track reconnection attempts
    socket.on('reconnect_attempt', (attemptNumber) => {
      console.log(`Socket reconnection attempt ${attemptNumber}`);
      setReconnecting(true);
      setConnectionAttempts(attemptNumber);
    });

    // Track successful reconnection
    socket.on('reconnect', (attemptNumber) => {
      console.log(`Socket reconnected after ${attemptNumber} attempts`);
      setIsConnected(true);
      setReconnecting(false);
    });

    // Track reconnection errors
    socket.on('reconnect_error', (error) => {
      console.error('Socket reconnection error:', error);
      setLastError(error.message);
    });

    // Track reconnection failures
    socket.on('reconnect_failed', () => {
      console.error('Socket reconnection failed after all attempts');
      setReconnecting(false);
    });

    // Connect if not already connected
    if (!socket.connected) {
      console.log('Initiating socket connection...');
      socket.connect();
    } else {
      console.log('Socket already connected:', socket.id);
      setIsConnected(true);
    }

    // Clean up event listeners on unmount
    return () => {
      console.log('Cleaning up socket event listeners');
      socket.off('connect');
      socket.off('disconnect');
      socket.off('connect_error');
      socket.off('reconnect_attempt');
      socket.off('reconnect');
      socket.off('reconnect_error');
      socket.off('reconnect_failed');
    };
  }, [connectionAttempts]);

  // Function to emit events with enhanced error handling and acknowledgment
  const emit = useCallback((event, data, callback) => {
    const socket = getSocket();

    // If socket is connected, emit the event
    if (socket && socket.connected) {
      console.log(`Emitting event: ${event}`, data);

      // For important events, use acknowledgment callback to ensure delivery
      // and add timeout handling
      if (['query_case', 'generate_report', 'keep_alive'].includes(event)) {
        // Create a timeout for acknowledgment
        const ackTimeout = setTimeout(() => {
          console.warn(`No acknowledgment received for ${event} after 10 seconds`);
          if (callback) callback({ error: 'Acknowledgment timeout' });
        }, 10000);

        // Emit with acknowledgment callback
        socket.emit(event, data, (response) => {
          // Clear the timeout since we got a response
          clearTimeout(ackTimeout);
          console.log(`Server acknowledged ${event}:`, response);
          if (callback) callback(response);
        });
      } else {
        // For non-critical events, just emit normally
        socket.emit(event, data, callback);
      }
      return true;
    }

    // If socket is reconnecting, wait and try again
    if (socket && socket.io && socket.io.reconnecting) {
      console.warn(`Socket reconnecting, queuing event: ${event}`);

      // Wait for reconnection and then try again
      const reconnectListener = () => {
        console.log(`Socket reconnected, emitting queued event: ${event}`);
        socket.emit(event, data, callback);
        socket.off('reconnect', reconnectListener);
      };

      socket.on('reconnect', reconnectListener);
      return true;
    }

    // If socket is not connected and not reconnecting, log error
    console.warn('Socket not connected, cannot emit event:', event);
    if (callback) callback({ error: 'Socket not connected' });
    return false;
  }, []);

  // Function to subscribe to events
  const on = useCallback((event, callback) => {
    const socket = getSocket();
    socket.on(event, callback);

    // Return a function to unsubscribe
    return () => {
      socket.off(event, callback);
    };
  }, []);

  // Function to unsubscribe from events
  const off = useCallback((event, callback) => {
    const socket = getSocket();
    socket.off(event, callback);
  }, []);

  // Function to manually reconnect
  const reconnect = useCallback(() => {
    const socket = getSocket();
    console.log('Manually reconnecting socket...');
    setReconnecting(true);

    // Disconnect first if already connected or connecting
    if (socket.connected || socket.connecting) {
      socket.disconnect();
    }

    // Small delay before reconnecting
    setTimeout(() => {
      socket.connect();
    }, 500);
  }, []);

  return {
    socket: getSocket(),
    isConnected,
    connectionAttempts,
    lastError,
    reconnecting,
    reconnect,
    emit,
    on,
    off
  };
};

// Export a function to disconnect the socket
export const disconnectSocket = () => {
  if (socket) {
    socket.disconnect();
  }
};

export default getSocket;
