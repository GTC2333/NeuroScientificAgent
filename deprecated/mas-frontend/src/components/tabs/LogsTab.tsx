import { useState, useRef, useEffect, useCallback } from 'react';
import { api, LogEntry, LogLevel } from '../../services/api';

export function LogsTab() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filter, setFilter] = useState<LogLevel | 'all'>('all');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const logsEndRef = useRef<HTMLDivElement>(null);
  const refreshIntervalRef = useRef<number | null>(null);

  const fetchLogs = useCallback(async () => {
    const level = filter === 'all' ? undefined : filter;
    const fetchedLogs = await api.getLogs(level, 50); // 限制50条
    setLogs(fetchedLogs);
  }, [filter]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  useEffect(() => {
    if (autoRefresh) {
      refreshIntervalRef.current = window.setInterval(fetchLogs, 3000);
    }
    return () => {
      if (refreshIntervalRef.current) {
        clearInterval(refreshIntervalRef.current);
      }
    };
  }, [autoRefresh, fetchLogs]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const levelColors: Record<LogLevel, string> = {
    info: 'text-blue-600',
    warn: 'text-yellow-600',
    error: 'text-red-600',
    all: 'text-gray-600',
  };

  const filteredLogs = filter === 'all' ? logs : logs.filter(l => l.level === filter);

  return (
    <div className="flex flex-col h-full">
      {/* 简化的 Controls */}
      <div className="flex gap-2 mb-2 items-center flex-wrap">
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
        <button
          onClick={() => setAutoRefresh(!autoRefresh)}
          className={`px-2 py-1 text-xs rounded ml-auto ${
            autoRefresh ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-600'
          }`}
        >
          {autoRefresh ? 'Auto' : 'Paused'}
        </button>
      </div>

      {/* 说明 */}
      <div className="text-xs text-gray-500 mb-2 bg-gray-50 p-2 rounded">
        显示 MAS 业务日志。Claude Code 日志请使用终端查看。
      </div>

      {/* Log entries */}
      <div className="flex-1 overflow-auto font-mono text-xs space-y-1">
        {filteredLogs.length === 0 ? (
          <div className="text-gray-400 text-center py-4">No logs yet</div>
        ) : (
          filteredLogs.map((log) => (
            <div key={log.id} className="flex gap-2">
              <span className="text-gray-400">{log.timestamp}</span>
              <span className={`font-medium ${levelColors[log.level]}`}>[{log.level.toUpperCase()}]</span>
              {log.source && <span className="text-gray-500">[{log.source}]</span>}
              <span className="text-gray-700">{log.message}</span>
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>
    </div>
  );
}
