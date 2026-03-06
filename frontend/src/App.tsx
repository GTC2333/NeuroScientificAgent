import { useState } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { ChatWindow } from './components/ChatWindow';
import { TaskPanel } from './components/TaskPanel';
import type { AgentType } from './types';

function App() {
  const [currentAgent, setCurrentAgent] = useState<AgentType>('principal');

  return (
    <div className="h-screen flex flex-col">
      <Header currentAgent={currentAgent} onAgentChange={setCurrentAgent} />

      <div className="flex-1 flex overflow-hidden">
        <Sidebar />

        <ChatWindow agentType={currentAgent} />

        <TaskPanel />
      </div>
    </div>
  );
}

export default App;
