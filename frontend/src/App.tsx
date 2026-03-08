import { useStore } from './store/useStore';
import type { SessionStore } from './store/useStore';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ChatWindow } from './components/ChatWindow';
import { SessionCreationPanel } from './components/SessionCreationPanel';
import { InspectorPanel } from './components/InspectorPanel';

function App() {
  const currentSessionId = useStore((state: SessionStore) => state.currentSessionId);

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      <Header />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar />

        <main className="flex-1 flex">
          {currentSessionId ? (
            <div className="flex-1 flex">
              <ChatWindow />
              <InspectorPanel />
            </div>
          ) : (
            <SessionCreationPanel />
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
