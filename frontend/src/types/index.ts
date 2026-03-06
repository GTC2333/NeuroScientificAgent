export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

export interface ChatRequest {
  message: string;
  agent_type: AgentType;
  history?: Message[];
}

export interface ChatResponse {
  reply: string;
  agent_type: string;
  task_id?: string;
}

export type AgentType = 'principal' | 'theorist' | 'experimentalist' | 'analyst' | 'writer';

export interface Agent {
  type: AgentType;
  name: string;
  description: string;
}

export interface Skill {
  name: string;
  description: string;
  category: string;
  path: string;
}

export interface Task {
  id: string;
  name: string;
  description: string;
  agent: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  dependencies: string[];
  result?: string;
  created_at: string;
  updated_at: string;
}
