// MAS API Service - Communication with MAS Backend
const API_BASE = '/api';

export const masApi = {
  // Chat with agents
  async sendMessage(message, agentType = 'principal', sessionId = null, skills = []) {
    const response = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        agent_type: agentType,
        session_id: sessionId,
        selected_skills: skills,
      }),
    });
    if (!response.ok) {
      throw new Error(`API Error: ${response.status} ${response.statusText}`);
    }
    return response.json();
  },

  // Streaming chat
  async *streamMessage(message, agentType = 'principal', sessionId = null, skills = []) {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        agent_type: agentType,
        session_id: sessionId,
        selected_skills: skills,
      }),
    });

    if (!response.ok) {
      yield `[Error] ${response.status}: ${response.statusText}`;
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
      yield `[Error] Stream interrupted: ${error.message}`;
    }
  },

  // Get available agents
  async getAgents() {
    const response = await fetch(`${API_BASE}/agents`);
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    return response.json();
  },

  // Get available skills
  async getSkills() {
    const response = await fetch(`${API_BASE}/skills`);
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    return response.json();
  },

  // Get tasks
  async getTasks(status) {
    const url = status ? `${API_BASE}/tasks?status=${status}` : `${API_BASE}/tasks`;
    const response = await fetch(url);
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    return response.json();
  },

  // Create task
  async createTask(name, description, agent) {
    const response = await fetch(`${API_BASE}/tasks`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, description, agent }),
    });
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    return response.json();
  },

  // Get sessions
  async getSessions() {
    const response = await fetch(`${API_BASE}/sessions`);
    if (!response.ok) {
      throw new Error(`API Error: ${response.status}`);
    }
    return response.json();
  },
};
