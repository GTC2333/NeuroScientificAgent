import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { IS_PLATFORM } from '../../../constants/config';
import { api } from '../../../utils/api';
import { AUTH_ERROR_MESSAGES, AUTH_TOKEN_STORAGE_KEY } from '../constants';
import type {
  AuthContextValue,
  AuthProviderProps,
  AuthSessionPayload,
  AuthStatusPayload,
  AuthUser,
  AuthUserPayload,
  OnboardingStatusPayload,
} from '../types';
import { parseJsonSafely, resolveApiErrorMessage } from '../utils';

const AuthContext = createContext<AuthContextValue | null>(null);

const readStoredToken = (): string | null => localStorage.getItem(AUTH_TOKEN_STORAGE_KEY);

const persistToken = (token: string) => {
  localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
};

const clearStoredToken = () => {
  localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
};

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }

  return context;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [token, setToken] = useState<string | null>(() => readStoredToken());
  const [isLoading, setIsLoading] = useState(true);
  const [needsSetup, setNeedsSetup] = useState(false);
  const [hasCompletedOnboarding, setHasCompletedOnboarding] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const setSession = useCallback((nextUser: AuthUser, nextToken: string) => {
    console.log('[Auth DEBUG] setSession called', { nextUser, tokenPrefix: nextToken?.substring(0, 20) });
    setUser(nextUser);
    setToken(nextToken);
    persistToken(nextToken);
  }, []);

  const clearSession = useCallback(() => {
    console.log('[Auth DEBUG] clearSession called', new Error().stack);
    setUser(null);
    setToken(null);
    clearStoredToken();
  }, []);

  const checkOnboardingStatus = useCallback(async () => {
    try {
      const response = await api.user.onboardingStatus();
      if (!response.ok) {
        return;
      }

      const payload = await parseJsonSafely<OnboardingStatusPayload>(response);
      setHasCompletedOnboarding(Boolean(payload?.hasCompletedOnboarding));
    } catch (caughtError) {
      console.error('Error checking onboarding status:', caughtError);
      // Fail open to avoid blocking access on transient onboarding status errors.
      setHasCompletedOnboarding(true);
    }
  }, []);

  const refreshOnboardingStatus = useCallback(async () => {
    await checkOnboardingStatus();
  }, [checkOnboardingStatus]);

  const checkAuthStatus = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);
      console.log('[Auth DEBUG] checkAuthStatus START, token exists:', !!token);

      const statusResponse = await api.auth.status();
      const statusPayload = await parseJsonSafely<AuthStatusPayload>(statusResponse);
      console.log('[Auth DEBUG] auth/status response:', statusPayload);

      if (statusPayload?.needsSetup) {
        console.log('[Auth DEBUG] needsSetup=true, showing SetupForm');
        setNeedsSetup(true);
        return;
      }

      setNeedsSetup(false);

      if (!token) {
        console.log('[Auth DEBUG] no token, skipping user fetch');
        return;
      }

      console.log('[Auth DEBUG] fetching /api/auth/me with token:', token?.substring(0, 20));
      const userResponse = await api.auth.user();
      console.log('[Auth DEBUG] /api/auth/me response status:', userResponse.status, 'ok:', userResponse.ok);
      if (!userResponse.ok) {
        const errorBody = await userResponse.clone().text();
        console.log('[Auth DEBUG] /api/auth/me FAILED, body:', errorBody, '→ clearSession');
        clearSession();
        return;
      }

      const userPayload = await parseJsonSafely<AuthUserPayload>(userResponse);
      console.log('[Auth DEBUG] /api/auth/me payload:', userPayload);
      if (!userPayload?.user) {
        console.log('[Auth DEBUG] no user in payload → clearSession');
        clearSession();
        return;
      }

      setUser(userPayload.user);
      await checkOnboardingStatus();
    } catch (caughtError) {
      console.error('[Auth DEBUG] checkAuthStatus EXCEPTION:', caughtError);
      setError(AUTH_ERROR_MESSAGES.authStatusCheckFailed);
    } finally {
      setIsLoading(false);
    }
  }, [checkOnboardingStatus, clearSession, token]);

  useEffect(() => {
    console.log('[Auth DEBUG] useEffect triggered (checkAuthStatus/checkOnboardingStatus changed)');
    if (IS_PLATFORM) {
      setUser({ username: 'platform-user' });
      setNeedsSetup(false);
      void checkOnboardingStatus().finally(() => {
        setIsLoading(false);
      });
      return;
    }

    void checkAuthStatus();
  }, [checkAuthStatus, checkOnboardingStatus]);

  const login = useCallback<AuthContextValue['login']>(
    async (username, password) => {
      try {
        setError(null);
        console.log('[Auth DEBUG] login() called for user:', username);
        const response = await api.auth.login(username, password);
        console.log('[Auth DEBUG] login response status:', response.status, 'ok:', response.ok);
        const payload = await parseJsonSafely<AuthSessionPayload>(response);
        console.log('[Auth DEBUG] login payload:', { token: payload?.token?.substring(0, 20), user: payload?.user });

        if (!response.ok || !payload?.token || !payload.user) {
          const message = resolveApiErrorMessage(payload, AUTH_ERROR_MESSAGES.loginFailed);
          console.log('[Auth DEBUG] login FAILED:', message);
          setError(message);
          return { success: false, error: message };
        }

        console.log('[Auth DEBUG] login SUCCESS, calling setSession');
        setSession(payload.user, payload.token);
        setNeedsSetup(false);
        await checkOnboardingStatus();
        console.log('[Auth DEBUG] login complete, returning success');
        return { success: true };
      } catch (caughtError) {
        console.error('[Auth DEBUG] login EXCEPTION:', caughtError);
        setError(AUTH_ERROR_MESSAGES.networkError);
        return { success: false, error: AUTH_ERROR_MESSAGES.networkError };
      }
    },
    [checkOnboardingStatus, setSession],
  );

  const register = useCallback<AuthContextValue['register']>(
    async (username, password) => {
      try {
        setError(null);
        const response = await api.auth.register(username, password);
        const payload = await parseJsonSafely<AuthSessionPayload>(response);

        if (!response.ok || !payload?.token || !payload.user) {
          const message = resolveApiErrorMessage(payload, AUTH_ERROR_MESSAGES.registrationFailed);
          setError(message);
          return { success: false, error: message };
        }

        setSession(payload.user, payload.token);
        setNeedsSetup(false);
        await checkOnboardingStatus();
        return { success: true };
      } catch (caughtError) {
        console.error('Registration error:', caughtError);
        setError(AUTH_ERROR_MESSAGES.networkError);
        return { success: false, error: AUTH_ERROR_MESSAGES.networkError };
      }
    },
    [checkOnboardingStatus, setSession],
  );

  const logout = useCallback(() => {
    const tokenToInvalidate = token;
    clearSession();

    if (tokenToInvalidate) {
      void api.auth.logout().catch((caughtError: unknown) => {
        console.error('Logout endpoint error:', caughtError);
      });
    }
  }, [clearSession, token]);

  const contextValue = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      isLoading,
      needsSetup,
      hasCompletedOnboarding,
      error,
      login,
      register,
      logout,
      refreshOnboardingStatus,
    }),
    [
      error,
      hasCompletedOnboarding,
      isLoading,
      login,
      logout,
      needsSetup,
      refreshOnboardingStatus,
      register,
      token,
      user,
    ],
  );

  return <AuthContext.Provider value={contextValue}>{children}</AuthContext.Provider>;
}
