// frontend/src/components/tabs/HelpTab.tsx
export function HelpTab() {
  return (
    <div className="space-y-4">
      <h3 className="font-semibold text-gray-800">Help</h3>

      <div className="space-y-3 text-sm">
        <div>
          <h4 className="font-medium text-gray-700">Quick Start</h4>
          <p className="text-gray-600 mt-1">
            Create a new session, select agents and skills, then start chatting.
          </p>
        </div>

        <div>
          <h4 className="font-medium text-gray-700">Agent Roles</h4>
          <ul className="list-disc list-inside text-gray-600 mt-1 space-y-1">
            <li><strong>Principal:</strong> Project coordination</li>
            <li><strong>Theorist:</strong> Hypothesis generation</li>
            <li><strong>Experimentalist:</strong> Experiment design</li>
            <li><strong>Analyst:</strong> Data analysis</li>
            <li><strong>Writer:</strong> Documentation</li>
          </ul>
        </div>

        <div>
          <h4 className="font-medium text-gray-700">Keyboard Shortcuts</h4>
          <ul className="list-disc list-inside text-gray-600 mt-1 space-y-1">
            <li><kbd>Ctrl</kbd> + <kbd>Enter</kbd>: Send message</li>
            <li><kbd>Ctrl</kbd> + <kbd>N</kbd>: New session</li>
          </ul>
        </div>
      </div>
    </div>
  );
}
