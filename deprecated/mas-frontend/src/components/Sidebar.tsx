// frontend/src/components/Sidebar.tsx
import { useStore, SessionStore } from '../store/useStore';
import { useNavigate } from 'react-router-dom';

export function Sidebar() {
  const sessions = useStore((state: SessionStore) => state.sessions);
  const currentSessionId = useStore((state: SessionStore) => state.currentSessionId);
  const createSession = useStore((state: SessionStore) => state.createSession);
  const deleteSession = useStore((state: SessionStore) => state.deleteSession);
  const navigate = useNavigate();

  const handleNewSession = () => {
    const newSessionId = createSession('New Research', ['principal'], []);
    navigate(`/${newSessionId}`);
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString() + ' ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <div className="w-64 bg-gray-100 border-r border-gray-200 flex flex-col">
      <div className="p-4">
        <button
          onClick={handleNewSession}
          className="w-full bg-blue-600 text-white py-2 px-4 rounded-lg hover:bg-blue-700 transition-colors"
        >
          + New Session
        </button>
      </div>

      <div className="flex-1 overflow-auto">
        <div className="px-4 py-2">
          <h3 className="text-xs font-semibold text-gray-500 uppercase tracking-wider">
            Sessions ({sessions.length})
          </h3>
        </div>

        <div className="space-y-1 px-2">
          {sessions.map((session) => (
            <div
              key={session.id}
              className={`group flex items-center justify-between p-2 rounded-lg cursor-pointer ${
                session.id === currentSessionId
                  ? 'bg-blue-100 text-blue-800'
                  : 'hover:bg-gray-200 text-gray-700'
              }`}
              onClick={() => navigate(`/${session.id}`)}
            >
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{session.title}</p>
                <p className="text-xs text-gray-500">{formatDate(session.updatedAt)}</p>
              </div>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  deleteSession(session.id);
                  if (session.id === currentSessionId) {
                    navigate('/');
                  }
                }}
                className="opacity-0 group-hover:opacity-100 p-1 hover:bg-red-100 rounded text-red-600"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
