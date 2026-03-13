# Logging System

## Overview

The application uses a centralized logging utility (`src/utils/logger.js`) that provides:
- **Hierarchical log levels** (debug → info → warn → error)
- **Production-safe defaults** (minimal logs in production, verbose in development)
- **Runtime control** via `localStorage`
- **Specialized logging methods** for common patterns (API, WebSocket)

## Quick Start

### Import and Use

```javascript
import logger from './utils/logger';

// Basic logging
logger.debug('Component', 'Value changed:', value);
logger.info('Auth', 'User logged in:', username);
logger.warn('API', 'Slow response time');
logger.error('Network', 'Request failed:', error);

// Specialized API logging
logger.apiRequest('GET', '/api/projects', hasToken);
logger.apiResponse('GET', '/api/projects', 200);
logger.apiResponse('POST', '/api/sessions', 500, 'Internal Server Error');

// WebSocket events
logger.wsEvent('connected', { url });
logger.wsEvent('message', data);
```

## Log Levels

| Level | When to Use | Examples |
|-------|-------------|----------|
| `debug` | Detailed flow information | Variable values, function calls, state changes |
| `info` | Important events | User actions, successful operations |
| `warn` | Unusual situations | Slow responses, missing data, fallback behavior |
| `error` | Failures | Request failures, exceptions, crashes |

## Runtime Control

### Via Browser Console

```javascript
// Show all logs (including debug)
logger.setLevel('debug');

// Production mode (warnings and errors only)
logger.setLevel('warn');

// Errors only
logger.setLevel('error');

// Disable all logging
logger.setLevel('none');
```

### Via localStorage

```javascript
// Persists across page reloads
localStorage.setItem('log-level', 'debug');
```

### Check Current Level

```javascript
logger.level  // Returns current log level
```

## Default Behavior

- **Development** (`npm run dev`): Log level = `debug` (all logs visible)
- **Production** (`npm run build`): Log level = `warn` (only warnings and errors)

## Migration Guide

### Replace console.log

```javascript
// Before
console.log('[API DEBUG] authenticatedFetch:', url);

// After
logger.debug('API', 'Authenticated fetch:', url);
```

### Replace console.error

```javascript
// Before
console.error('WebSocket error:', error);

// After
logger.error('WebSocket', 'Connection error:', error);
```

### API Requests

```javascript
// Before
console.log('[API] GET /api/projects hasToken:', !!token);
fetch(url).then(res => {
  console.log('[API] Response:', res.status);
});

// After
logger.apiRequest('GET', '/api/projects', !!token);
fetch(url).then(res => {
  logger.apiResponse('GET', '/api/projects', res.status);
});
```

## Best Practices

1. **Always provide a category** (first argument): Use component/module name
2. **Be concise in production**: Avoid logging in hot paths unless necessary
3. **Use appropriate levels**: Don't use `error` for non-errors
4. **Include context**: Log relevant variables that help debugging
5. **Avoid PII**: Never log passwords, tokens (except first few chars), or sensitive data

## Examples by Component

### API Client

```javascript
import logger from './logger';

export const authenticatedFetch = (url, options = {}) => {
  const method = options.method || 'GET';
  logger.apiRequest(method, url, hasAuth);

  return fetch(url, options)
    .then(res => {
      logger.apiResponse(method, url, res.status, !res.ok ? res.statusText : null);
      return res;
    })
    .catch(error => {
      logger.error('API', `${method} ${url} failed:`, error.message);
      throw error;
    });
};
```

### WebSocket Handler

```javascript
import logger from './logger';

ws.onopen = () => {
  logger.wsEvent('connected', { url: ws.url });
};

ws.onmessage = (event) => {
  logger.wsEvent('message', JSON.parse(event.data));
};

ws.onerror = (error) => {
  logger.error('WebSocket', 'Connection error:', error);
};
```

### Component Lifecycle

```javascript
import logger from './logger';

useEffect(() => {
  logger.debug('ProjectList', 'Loading projects...');

  api.projects().then(projects => {
    logger.info('ProjectList', `Loaded ${projects.length} projects`);
  }).catch(error => {
    logger.error('ProjectList', 'Failed to load projects:', error);
  });
}, []);
```

## Debugging Tips

### Enable verbose logging temporarily

```javascript
// In browser console
logger.setLevel('debug');
// Reproduce the issue
// Check logs
logger.setLevel('warn');  // Restore default
```

### Filter logs by category

```javascript
// Browser DevTools → Console → Filter
[API]       // Only API logs
[WebSocket] // Only WebSocket logs
[Auth]      // Only auth logs
```

### Performance debugging

```javascript
logger.debug('Component', 'Render start');
// ... expensive operation ...
logger.debug('Component', 'Render end');
```

## Future Enhancements

- [ ] Remote logging service integration
- [ ] Log aggregation and analytics
- [ ] Structured logging (JSON format)
- [ ] Performance metrics (timing, memory)
- [ ] User session tracking
