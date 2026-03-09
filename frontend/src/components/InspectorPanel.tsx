import { useState } from 'react';
import { GraphTab } from './tabs/GraphTab';
import { AgentsTab } from './tabs/AgentsTab';
import { FilesTab } from './tabs/FilesTab';
import { LogsTab } from './tabs/LogsTab';
import { SettingsTab } from './tabs/SettingsTab';
import { HelpTab } from './tabs/HelpTab';

type Tab = 'graph' | 'agents' | 'files' | 'logs' | 'settings' | 'help';

export function InspectorPanel() {
  const [activeTab, setActiveTab] = useState<Tab>('graph');
  const [isCollapsed, setIsCollapsed] = useState(false);

  const tabs: { id: Tab; label: string }[] = [
    { id: 'graph', label: 'Graph' },
    { id: 'agents', label: 'Agents' },
    { id: 'files', label: 'Files' },
    { id: 'logs', label: 'Logs' },
    { id: 'settings', label: 'Settings' },
    { id: 'help', label: 'Help' },
  ];

  if (isCollapsed) {
    return (
      <button
        onClick={() => setIsCollapsed(false)}
        className="w-10 bg-gray-100 border-l border-gray-200 flex flex-col items-center py-4 gap-2"
      >
        <span className="text-xs text-gray-500 rotate-90">Inspector</span>
      </button>
    );
  }

  return (
    <div className="w-80 bg-white border-l border-gray-200 flex flex-col">
      <div className="flex border-b border-gray-200">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex-1 py-2 text-sm font-medium ${
              activeTab === tab.id
                ? 'text-blue-600 border-b-2 border-blue-600'
                : 'text-gray-500 hover:text-gray-700'
            }`}
          >
            {tab.label}
          </button>
        ))}
        <button
          onClick={() => setIsCollapsed(true)}
          className="px-2 text-gray-400 hover:text-gray-600"
        >
          ×
        </button>
      </div>
      <div className="flex-1 overflow-auto p-4">
        {activeTab === 'graph' && <GraphTab />}
        {activeTab === 'agents' && <AgentsTab />}
        {activeTab === 'files' && <FilesTab />}
        {activeTab === 'logs' && <LogsTab />}
        {activeTab === 'settings' && <SettingsTab />}
        {activeTab === 'help' && <HelpTab />}
      </div>
    </div>
  );
}
