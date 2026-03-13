import jwt from 'jsonwebtoken';
import bcrypt from 'bcrypt';
import { userDb } from '../database/db.js';
import { IS_PLATFORM } from '../constants/config.js';

// Default platform user credentials
const PLATFORM_DEFAULT_USERNAME = 'admin';
const PLATFORM_DEFAULT_PASSWORD = 'admin';

// Get JWT secret from environment or use default (for development)
const JWT_SECRET = process.env.JWT_SECRET || 'claude-ui-dev-secret-change-in-production';

// Helper to get or create default platform user
const getOrCreatePlatformUser = () => {
  let user = userDb.getFirstUser();
  if (user) {
    return user;
  }
  // Create default user if none exists in platform mode
  console.log('[INFO] Platform mode: Creating default user');
  const passwordHash = bcrypt.hashSync(PLATFORM_DEFAULT_PASSWORD, 12);
  user = userDb.createUser(PLATFORM_DEFAULT_USERNAME, passwordHash);
  console.log('[INFO] Platform mode: Default user created (username: admin, password: admin)');
  return user;
};

// Optional API key middleware
const validateApiKey = (req, res, next) => {
  // Skip API key validation if not configured
  if (!process.env.API_KEY) {
    return next();
  }
  
  const apiKey = req.headers['x-api-key'];
  if (apiKey !== process.env.API_KEY) {
    return res.status(401).json({ error: 'Invalid API key' });
  }
  next();
};

// JWT authentication middleware
const authenticateToken = async (req, res, next) => {
  // Platform mode: use single database user (auto-create if needed)
  if (IS_PLATFORM) {
    try {
      const user = getOrCreatePlatformUser();
      req.user = user;
      return next();
    } catch (error) {
      console.error('Platform mode error:', error);
      return res.status(500).json({ error: 'Platform mode: Failed to get/create user' });
    }
  }

  // Normal OSS JWT validation
  const authHeader = req.headers['authorization'];
  let token = authHeader && authHeader.split(' ')[1]; // Bearer TOKEN

  // Also check query param for SSE endpoints (EventSource can't set headers)
  if (!token && req.query.token) {
    token = req.query.token;
  }

  if (!token) {
    return res.status(401).json({ error: 'Access denied. No token provided.' });
  }

  try {
    const decoded = jwt.verify(token, JWT_SECRET);

    // Verify user still exists and is active
    const user = userDb.getUserById(decoded.userId);
    if (!user) {
      return res.status(401).json({ error: 'Invalid token. User not found.' });
    }

    req.user = user;
    next();
  } catch (error) {
    console.error('Token verification error:', error);
    return res.status(403).json({ error: 'Invalid token' });
  }
};

// Generate JWT token (never expires)
const generateToken = (user) => {
  return jwt.sign(
    { 
      userId: user.id, 
      username: user.username 
    },
    JWT_SECRET
    // No expiration - token lasts forever
  );
};

// WebSocket authentication function
const authenticateWebSocket = (token) => {
  // Platform mode: bypass token validation, use default user (auto-create if needed)
  if (IS_PLATFORM) {
    try {
      const user = getOrCreatePlatformUser();
      return { userId: user.id, username: user.username };
    } catch (error) {
      console.error('Platform mode WebSocket error:', error);
      return null;
    }
  }

  // Normal OSS JWT validation
  if (!token) {
    return null;
  }

  try {
    const decoded = jwt.verify(token, JWT_SECRET);
    return decoded;
  } catch (error) {
    console.error('WebSocket token verification error:', error);
    return null;
  }
};

export {
  validateApiKey,
  authenticateToken,
  generateToken,
  authenticateWebSocket,
  JWT_SECRET
};