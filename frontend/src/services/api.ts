import axios from 'axios';
import type { ChatRequest, ChatResponse, Agent, Skill, Task } from '../types';

const API_BASE = '/api';

export const api = {
  // Chat
  async sendMessage(request: ChatRequest): Promise<ChatResponse> {
    const response = await axios.post<ChatResponse>(`${API_BASE}/chat`, request);
    return response.data;
  },

  async *streamMessage(request: ChatRequest): AsyncGenerator<string> {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(request),
    });

    const reader = response.body?.getReader();
    if (!reader) return;

    const decoder = new TextDecoder();
    let buffer = '';

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
            if (data.text) yield data.text;
            if (data.done) return;
          } catch {
            // Skip invalid JSON
          }
        }
      }
    }
  },

  // Agents
  async getAgents(): Promise<Agent[]> {
    const response = await axios.get<Agent[]>(`${API_BASE}/agents`);
    return response.data;
  },

  // Skills
  async getSkills(): Promise<Skill[]> {
    const response = await axios.get<Skill[]>(`${API_BASE}/skills`);
    return response.data;
  },

  // Tasks
  async getTasks(status?: string): Promise<Task[]> {
    const url = status ? `${API_BASE}/tasks?status=${status}` : `${API_BASE}/tasks`;
    const response = await axios.get<Task[]>(url);
    return response.data;
  },

  async createTask(task: { name: string; description: string; agent: string }): Promise<Task> {
    const response = await axios.post<Task>(`${API_BASE}/tasks`, task);
    return response.data;
  },
};
