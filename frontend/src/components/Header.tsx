import type { AgentType } from '../types';

interface HeaderProps {
  currentAgent: AgentType;
  onAgentChange: (agent: AgentType) => void;
}

const agents: { type: AgentType; label: string }[] = [
  { type: 'principal', label: 'PI' },
  { type: 'theorist', label: 'Theorist' },
  { type: 'experimentalist', label: 'Experimentalist' },
  { type: 'analyst', label: 'Analyst' },
  { type: 'writer', label: 'Writer' },
];

export function Header({ currentAgent, onAgentChange }: HeaderProps) {
  return (
    <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
      <div className="flex items-center gap-2">
        <span className="text-2xl">🔬</span>
        <h1 className="text-xl font-semibold text-gray-900">MAS - Research Agent</h1>
      </div>

      <div className="flex gap-2">
        {agents.map((agent) => (
          <button
            key={agent.type}
            onClick={() => onAgentChange(agent.type)}
            className={`px-3 py-1.5 text-sm rounded-md border transition-colors ${
              currentAgent === agent.type
                ? 'bg-blue-600 text-white border-blue-600'
                : 'bg-white text-gray-700 border-gray-200 hover:border-blue-400'
            }`}
          >
            {agent.label}
          </button>
        ))}
      </div>
    </header>
  );
}
