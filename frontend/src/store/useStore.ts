import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { Session, Message, AgentType } from '../types';

// Generate a valid UUID for Claude Code session
function generateUUID(): string {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export interface SessionStore {
  sessions: Session[];
  currentSessionId: string | null;

  // Actions
  createSession: (title: string, agents?: AgentType[], skills?: string[]) => string;
  deleteSession: (id: string) => void;
  renameSession: (id: string, title: string) => void;
  setCurrentSession: (id: string | null) => void;
  addMessage: (sessionId: string, message: Message) => void;
  getCurrentSession: () => Session | null;
}

export const useStore = create<SessionStore>()(
  persist(
    (set, get) => ({
      sessions: [],
      currentSessionId: null,

      createSession: (title, agents = ['principal'], skills = []) => {
        const id = generateUUID();
        const now = new Date().toISOString();
        const newSession: Session = {
          id,
          title: title || 'New Research',
          agents,
          skills,
          messages: [],
          createdAt: now,
          updatedAt: now,
        };
        set((state) => ({
          sessions: [newSession, ...state.sessions],
          currentSessionId: id,
        }));
        return id;
      },

      deleteSession: (id) => {
        set((state) => ({
          sessions: state.sessions.filter((s) => s.id !== id),
          currentSessionId: state.currentSessionId === id ? null : state.currentSessionId,
        }));
      },

      renameSession: (id, title) => {
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === id ? { ...s, title, updatedAt: new Date().toISOString() } : s
          ),
        }));
      },

      setCurrentSession: (id) => {
        set({ currentSessionId: id });
      },

      addMessage: (sessionId, message) => {
        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === sessionId
              ? { ...s, messages: [...s.messages, message], updatedAt: new Date().toISOString() }
              : s
          ),
        }));
      },

      getCurrentSession: () => {
        const state = get();
        return state.sessions.find((s) => s.id === state.currentSessionId) || null;
      },
    }),
    {
      name: 'mas-sessions',
    }
  )
);
