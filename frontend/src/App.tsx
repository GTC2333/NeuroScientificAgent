import { Routes, Route, useNavigate, useParams } from 'react-router-dom';
import { useEffect } from 'react';
import { useStore } from './store/useStore';
import type { SessionStore } from './store/useStore';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ChatWindow } from './components/ChatWindow';
import { InspectorPanel } from './components/InspectorPanel';

function SessionPage() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const setCurrentSession = useStore((state: SessionStore) => state.setCurrentSession);
  const sessions = useStore((state: SessionStore) => state.sessions);

  useEffect(() => {
    if (sessionId) {
      // Check if session exists in store
      const exists = sessions.some(s => s.id === sessionId);
      if (exists) {
        setCurrentSession(sessionId);
      }
    }
  }, [sessionId, sessions, setCurrentSession]);

  return (
    <div className="flex-1 flex">
      <ChatWindow />
      <InspectorPanel />
    </div>
  );
}

function HomePage() {
  const sessions = useStore((state: SessionStore) => state.sessions);
  const navigate = useNavigate();

  // Redirect to first session if any sessions exist
  useEffect(() => {
    if (sessions.length > 0) {
      navigate(`/${sessions[0].id}`, { replace: true });
    }
  }, [sessions, navigate]);

  // Show empty state if no sessions
  return (
    <div className="flex-1 flex items-center justify-center">
      <p className="text-gray-500">Select or create a session to start</p>
    </div>
  );
}

function App() {
  return (
    <div className="h-screen flex flex-col bg-gray-50">
      <Header />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar />

        <main className="flex-1 flex">
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/:sessionId" element={<SessionPage />} />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default App;
