import { useState, useEffect, useCallback } from 'react';
import api from '../utils/api';

export type SandboxStatus = 'none' | 'creating' | 'running' | 'stopped' | 'error' | 'rebuilding';

interface SandboxState {
  status: SandboxStatus;
  sandbox: any | null;
  error: string | null;
}

export function useSandboxState() {
  const [state, setState] = useState<SandboxState>({
    status: 'none',
    sandbox: null,
    error: null,
  });

  const fetchStatus = useCallback(async () => {
    try {
      const sandboxes = await api.sandboxes.list();
      if (sandboxes && sandboxes.length > 0) {
        const sb = sandboxes[0]; // 1:1 model
        setState({
          status: sb.status === 'running' ? 'running' : 'stopped',
          sandbox: sb,
          error: null,
        });
      } else {
        setState({ status: 'none', sandbox: null, error: null });
      }
    } catch (err: any) {
      setState(prev => ({ ...prev, error: err.message }));
    }
  }, []);

  const createSandbox = useCallback(async () => {
    setState(prev => ({ ...prev, status: 'creating', error: null }));
    try {
      const sb = await api.sandboxes.create('default');
      setState({ status: 'running', sandbox: sb, error: null });
    } catch (err: any) {
      setState(prev => ({ ...prev, status: 'error', error: err.message }));
    }
  }, []);

  const rebuildSandbox = useCallback(async () => {
    setState(prev => ({ ...prev, status: 'rebuilding', error: null }));
    try {
      const sb = await api.sandboxes.rebuild();
      setState({ status: 'running', sandbox: sb, error: null });
    } catch (err: any) {
      setState(prev => ({ ...prev, status: 'error', error: err.message }));
    }
  }, []);

  const startSandbox = useCallback(async () => {
    if (!state.sandbox) return;
    try {
      await api.sandboxes.start(state.sandbox.id);
      await fetchStatus();
    } catch (err: any) {
      setState(prev => ({ ...prev, error: err.message }));
    }
  }, [state.sandbox, fetchStatus]);

  useEffect(() => {
    fetchStatus();
  }, [fetchStatus]);

  return {
    ...state,
    createSandbox,
    rebuildSandbox,
    startSandbox,
    refreshStatus: fetchStatus,
  };
}
