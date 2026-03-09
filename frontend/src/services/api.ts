import axios, { AxiosError } from 'axios';
import type { ChatRequest, ChatResponse, Agent, Skill, Task } from '../types';

const API_BASE = '/api';

// Log levels
export type LogLevel = 'info' | 'warn' | 'error' | 'all';

export interface LogEntry {
  id: string;
  timestamp: string;
  level: LogLevel;
  message: string;
  source?: string;
}

// Global error handler
const handleError = (error: unknown, context: string): string => {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError;
    if (axiosError.response) {
      const msg = `[${context}] Server error: ${axiosError.response.status} - ${JSON.stringify(axiosError.response.data)}`;
      console.error(msg);
      return msg;
    } else if (axiosError.request) {
      const msg = `[${context}] Network error: ${axiosError.message}`;
      console.error(msg);
      return msg;
    }
  }
  const msg = `[${context}] Error: ${error instanceof Error ? error.message : String(error)}`;
  console.error(msg);
  return msg;
};

export const api = {
  // Chat
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    try {
      console.log('[API] Sending request:', request);
      const response = await axios.post<ChatResponse>(`${API_BASE}/chat`, request);
      console.log('[API] Response:', response.data);
      return response.data;
    } catch (error) {
      const msg = handleError(error, 'sendMessage');
      throw new Error(msg);
    }
  },

  async *streamMessage(request: ChatRequest): AsyncGenerator<string> {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    if (!response.ok) {
      const errorText = await response.text();
      yield `[Error] ${response.status}: ${errorText}`;
      return;
    }

    const reader = response.body?.getReader();
    if (!reader) {
      yield '[Error] No response body';
      return;
    }

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.error) {
                yield `[Error] ${data.error}`;
              }
              if (data.text) yield data.text;
              if (data.done) return;
            } catch {
              // Skip invalid JSON
            }
          }
        }
      }
    } catch (error) {
      yield `[Error] Stream interrupted: ${error instanceof Error ? error.message : String(error)}`;
    }
  },

  // Logs
  async getLogs(level?: LogLevel, limit = 100): Promise<LogEntry[]> {
    try {
      const params = new URLSearchParams();
      if (level && level !== 'all') params.set('level', level);
      params.set('limit', String(limit));
      const response = await axios.get<LogEntry[]>(`${API_BASE}/logs?${params}`);
      return response.data;
    } catch (error) {
      handleError(error, 'getLogs');
      return [];
    }
  },

  async addLog(entry: Omit<LogEntry, 'id' | 'timestamp'>): Promise<void> {
    try {
      await axios.post(`${API_BASE}/logs`, entry);
    } catch (error) {
      handleError(error, 'addLog');
    }
  },

  async clearLogs(): Promise<void> {
    try {
      await axios.delete(`${API_BASE}/logs`);
    } catch (error) {
      handleError(error, 'clearLogs');
    }
  },

  // Agents
  async getAgents(): Promise<Agent[]> {
    try {
      const response = await axios.get<Agent[]>(`${API_BASE}/agents`);
      return response.data;
    } catch (error) {
      handleError(error, 'getAgents');
      return [];
    }
  },

  // Skills
  async getSkills(): Promise<Skill[]> {
    try {
      const response = await axios.get<Skill[]>(`${API_BASE}/skills`);
      return response.data;
    } catch (error) {
      handleError(error, 'getSkills');
      return [];
    }
  },

  // Tasks
  async getTasks(status?: string): Promise<Task[]> {
    try {
      const url = status ? `${API_BASE}/tasks?status=${status}` : `${API_BASE}/tasks`;
      const response = await axios.get<Task[]>(url);
      return response.data;
    } catch (error) {
      handleError(error, 'getTasks');
      return [];
    }
  },

  async createTask(task: { name: string; description: string; agent: string }): Promise<Task> {
    try {
      const response = await axios.post<Task>(`${API_BASE}/tasks`, task);
      return response.data;
    } catch (error) {
      throw new Error(handleError(error, 'createTask'));
    }
  },
};
