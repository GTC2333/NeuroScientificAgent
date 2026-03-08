import { useState, useRef, useEffect } from 'react';

interface LogEntry {
  id: string;
  timestamp: string;
  level: 'info' | 'warn' | 'error';
  message: string;
  source?: string;
}

export function LogsTab() {
  const [logs] = useState<LogEntry[]>([
    { id: '1', timestamp: '10:30:15', level: 'info', message: 'Session started', source: 'system' },
    { id: '2', timestamp: '10:30:16', level: 'info', message: 'Principal agent initialized', source: 'principal' },
    { id: '3', timestamp: '10:30:18', level: 'info', message: 'Task: literature review', source: 'principal' },
  ]);
  const [filter, setFilter] = useState<'all' | 'info' | 'warn' | 'error'>('all');
  const logsEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const levelColors = {
    info: 'text-blue-600',
    warn: 'text-yellow-600',
    error: 'text-red-600',
  };

  const filteredLogs = filter === 'all' ? logs : logs.filter(l => l.level === filter);

  return (
    <div className="flex flex-col h-full">
      {/* Filter buttons */}
      <div className="flex gap-2 mb-2">
        {(['all', 'info', 'warn', 'error'] as const).map((level) => (
          <button
            key={level}
            onClick={() => setFilter(level)}
            className={`px-2 py-1 text-xs rounded ${
              filter === level ? 'bg-gray-800 text-white' : 'bg-gray-100 text-gray-600'
            }`}
          >
            {level}
          </button>
        ))}
      </div>

      {/* Log entries */}
      <div className="flex-1 overflow-auto font-mono text-xs space-y-1">
        {filteredLogs.map((log) => (
          <div key={log.id} className="flex gap-2">
            <span className="text-gray-400">{log.timestamp}</span>
            <span className={`font-medium ${levelColors[log.level]}`}>[{log.level.toUpperCase()}]</span>
            {log.source && <span className="text-gray-500">[{log.source}]</span>}
            <span className="text-gray-700">{log.message}</span>
          </div>
        ))}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
}
