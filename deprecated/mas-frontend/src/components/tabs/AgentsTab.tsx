import { useState } from 'react';

interface AgentStatus {
  type: string;
  name: string;
  status: 'idle' | 'active' | 'thinking';
  currentTask?: string;
}

export function AgentsTab() {
  const [agents] = useState<AgentStatus[]>([
    { type: 'principal', name: 'Principal', status: 'idle' },
    { type: 'theorist', name: 'Theorist', status: 'idle' },
    { type: 'experimentalist', name: 'Experimentalist', status: 'idle' },
    { type: 'analyst', name: 'Analyst', status: 'idle' },
    { type: 'writer', name: 'Writer', status: 'idle' },
  ]);

  const statusColors = {
    idle: 'bg-gray-100 text-gray-600',
    active: 'bg-green-100 text-green-700',
    thinking: 'bg-blue-100 text-blue-700',
  };

  return (
    <div className="space-y-2">
      {agents.map((agent) => (
        <div
          key={agent.type}
          className="p-3 bg-gray-50 rounded-lg flex items-center justify-between"
        >
          <div>
            <div className="font-medium text-gray-900">{agent.name}</div>
            {agent.currentTask && (
              <div className="text-xs text-gray-500">{agent.currentTask}</div>
            )}
          </div>
          <span className={`px-2 py-1 rounded text-xs font-medium ${statusColors[agent.status]}`}>
            {agent.status}
          </span>
        </div>
      ))}
    </div>
  );
}
