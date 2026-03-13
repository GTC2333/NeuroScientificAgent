// frontend/src/components/tabs/SettingsTab.tsx
import { useState } from 'react';

export function SettingsTab() {
  const [apiEndpoint, setApiEndpoint] = useState('http://localhost:9000');
  const [theme, setTheme] = useState<'light' | 'dark'>('light');
  const [autoSave, setAutoSave] = useState(true);

  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-gray-800">Settings</h3>

      <div className="space-y-3">
        <div>
          <label className="block text-sm font-medium text-gray-700">API Endpoint</label>
          <input
            type="text"
            value={apiEndpoint}
            onChange={(e) => setApiEndpoint(e.target.value)}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500 sm:text-sm"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700">Theme</label>
          <select
            value={theme}
            onChange={(e) => setTheme(e.target.value as 'light' | 'dark')}
            className="mt-1 block w-full rounded-md border-gray-300 shadow-sm"
          >
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </div>

        <div className="flex items-center">
          <input
            id="auto-save"
            type="checkbox"
            checked={autoSave}
            onChange={(e) => setAutoSave(e.target.checked)}
            className="h-4 w-4 rounded border-gray-300 text-blue-600"
          />
          <label htmlFor="auto-save" className="ml-2 block text-sm text-gray-700">
            Auto-save sessions
          </label>
        </div>
      </div>
    </div>
  );
}
