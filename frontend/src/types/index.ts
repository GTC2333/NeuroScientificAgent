export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp?: string;
}

export interface ChatRequest {
  message: string;
  agent_type: AgentType;
  history?: Message[];
  session_id?: string;        // for Global Memory
  selected_skills?: string[]; // for Skills Hot-swap
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

export interface Session {
  id: string;
  title: string;
  agents: AgentType[];
  skills: string[];
  messages: Message[];
  createdAt: string;
  updatedAt: string;
}

export const AGENTS: Agent[] = [
  { type: 'principal', name: 'Principal', description: 'Project coordination and hypothesis validation' },
  { type: 'theorist', name: 'Theorist', description: 'Hypothesis generation and theoretical modeling' },
  { type: 'experimentalist', name: 'Experimentalist', description: 'Experiment design and execution' },
  { type: 'analyst', name: 'Analyst', description: 'Data analysis and visualization' },
  { type: 'writer', name: 'Writer', description: 'Documentation and paper drafting' },
];

export const SKILLS = [
  { id: 'literature', name: 'Literature Search', category: 'research' },
  { id: 'data_analysis', name: 'Data Analysis', category: 'analysis' },
  { id: 'python', name: 'Python Execution', category: 'tool' },
  { id: 'paper_writing', name: 'Paper Writing', category: 'writing' },
];
