/**
 * Centralized logging utility
 *
 * Usage:
 *   import logger from './utils/logger';
 *   logger.debug('API', 'Request:', url);
 *   logger.info('Auth', 'User logged in');
 *   logger.warn('WebSocket', 'Connection unstable');
 *   logger.error('API', 'Request failed:', error);
 *
 * Control via localStorage:
 *   localStorage.setItem('log-level', 'debug');  // Show all logs
 *   localStorage.setItem('log-level', 'info');   // Show info, warn, error
 *   localStorage.setItem('log-level', 'warn');   // Show warn, error only
 *   localStorage.setItem('log-level', 'error');  // Show errors only
 *   localStorage.setItem('log-level', 'none');   // Disable all logs
 */

const LOG_LEVELS = {
  debug: 0,
  info: 1,
  warn: 2,
  error: 3,
  none: 4,
};

// Default to 'warn' in production, 'debug' in development
const DEFAULT_LEVEL = import.meta.env.PROD ? 'warn' : 'debug';

class Logger {
  constructor() {
    this.level = this.getLogLevel();
  }

  getLogLevel() {
    const stored = localStorage.getItem('log-level');
    return stored && LOG_LEVELS[stored] !== undefined ? stored : DEFAULT_LEVEL;
  }

  shouldLog(level) {
    return LOG_LEVELS[level] >= LOG_LEVELS[this.level];
  }

  formatMessage(category, ...args) {
    return [`[${category}]`, ...args];
  }

  debug(category, ...args) {
    if (this.shouldLog('debug')) {
      console.log(...this.formatMessage(category, ...args));
    }
  }

  info(category, ...args) {
    if (this.shouldLog('info')) {
      console.info(...this.formatMessage(category, ...args));
    }
  }

  warn(category, ...args) {
    if (this.shouldLog('warn')) {
      console.warn(...this.formatMessage(category, ...args));
    }
  }

  error(category, ...args) {
    if (this.shouldLog('error')) {
      console.error(...this.formatMessage(category, ...args));
    }
  }

  // Special method for API requests (more detailed in debug mode)
  apiRequest(method, url, hasToken) {
    if (this.shouldLog('debug')) {
      console.log(`[API] ${method} ${url}`, hasToken ? '🔑' : '🔓');
    }
  }

  // Special method for API responses (more detailed in debug mode)
  apiResponse(method, url, status, error = null) {
    if (error) {
      if (this.shouldLog('error')) {
        console.error(`[API] ${method} ${url} → ${status} ❌`, error);
      }
    } else if (this.shouldLog('debug')) {
      console.log(`[API] ${method} ${url} → ${status} ✓`);
    }
  }

  // Special method for WebSocket events
  wsEvent(event, ...args) {
    if (this.shouldLog('debug')) {
      console.log(`[WS] ${event}`, ...args);
    }
  }

  // Utility to change log level at runtime
  setLevel(level) {
    if (LOG_LEVELS[level] !== undefined) {
      this.level = level;
      localStorage.setItem('log-level', level);
      console.info(`[Logger] Log level set to: ${level}`);
    } else {
      console.warn(`[Logger] Invalid log level: ${level}`);
    }
  }
}

const logger = new Logger();

// Expose to window for easy debugging
if (typeof window !== 'undefined') {
  window.logger = logger;
}

export default logger;
