import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { Task } from '../types';

export function TaskPanel() {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data = await api.getTasks('running');
        setTasks(data);
      } catch (err) {
        console.error('Failed to load tasks:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const statusColors = {
    pending: 'bg-gray-100 text-gray-600',
    running: 'bg-yellow-100 text-yellow-700',
    completed: 'bg-green-100 text-green-700',
    failed: 'bg-red-100 text-red-700',
  };

  if (loading) {
    return (
      <aside className="w-80 bg-white border-l border-gray-200 p-4">
        <div className="text-gray-500">Loading...</div>
      </aside>
    );
  }

  return (
    <aside className="w-80 bg-white border-l border-gray-200 p-4 overflow-y-auto">
      <h3 className="text-xs font-semibold text-gray-500 uppercase mb-3">Active Tasks</h3>

      {tasks.length === 0 ? (
        <div className="text-gray-500 text-sm">No active tasks</div>
      ) : (
        <div className="space-y-3">
          {tasks.map((task) => (
            <div key={task.id} className="p-3 border border-gray-200 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="font-medium text-sm">{task.name}</span>
                <span className={`text-xs px-2 py-0.5 rounded ${statusColors[task.status]}`}>
                  {task.status}
                </span>
              </div>
              <div className="text-xs text-gray-500">
                Agent: {task.agent}
              </div>
            </div>
          ))}
        </div>
      )}
    </aside>
  );
}
