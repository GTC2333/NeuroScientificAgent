import { useSandboxState, SandboxStatus } from '../../hooks/useSandboxState';

function getStatusColor(status: SandboxStatus): string {
  switch (status) {
    case 'running':
      return 'bg-green-500';
    case 'stopped':
      return 'bg-amber-500';
    case 'error':
      return 'bg-red-500';
    case 'creating':
    case 'rebuilding':
      return 'bg-blue-500 animate-pulse';
    default:
      return 'bg-gray-400';
  }
}

function getStatusText(status: SandboxStatus): string {
  switch (status) {
    case 'running':
      return 'Sandbox Running';
    case 'stopped':
      return 'Sandbox Stopped';
    case 'error':
      return 'Sandbox Error';
    case 'creating':
      return 'Creating...';
    case 'rebuilding':
      return 'Rebuilding...';
    default:
      return 'No Sandbox';
  }
}

export default function SandboxControls() {
  const { status, error, createSandbox, rebuildSandbox, startSandbox, sandbox } = useSandboxState();

  const isLoading = status === 'creating' || status === 'rebuilding';

  return (
    <div className="flex items-center gap-2">
      {/* Status indicator */}
      <div className="flex items-center gap-1.5 text-sm">
        <span className={`h-2 w-2 rounded-full ${getStatusColor(status)}`} />
        <span className="text-muted-foreground">{getStatusText(status)}</span>
        {error && <span className="text-red-500 text-xs">({error})</span>}
      </div>

      {/* Action buttons */}
      {status === 'none' && (
        <button
          onClick={createSandbox}
          disabled={isLoading}
          className="rounded-md bg-green-600 px-3 py-1 text-sm text-white hover:bg-green-700 disabled:opacity-50"
        >
          Create Sandbox
        </button>
      )}

      {status === 'running' && (
        <button
          onClick={rebuildSandbox}
          disabled={isLoading}
          className="rounded-md bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
        >
          Rebuild
        </button>
      )}

      {status === 'stopped' && (
        <>
          <button
            onClick={startSandbox}
            disabled={isLoading}
            className="rounded-md bg-green-600 px-3 py-1 text-sm text-white hover:bg-green-700 disabled:opacity-50"
          >
            Start
          </button>
          <button
            onClick={rebuildSandbox}
            disabled={isLoading}
            className="rounded-md bg-blue-600 px-3 py-1 text-sm text-white hover:bg-blue-700 disabled:opacity-50"
          >
            Rebuild
          </button>
        </>
      )}

      {status === 'error' && (
        <button
          onClick={createSandbox}
          disabled={isLoading}
          className="rounded-md bg-red-600 px-3 py-1 text-sm text-white hover:bg-red-700 disabled:opacity-50"
        >
          Retry
        </button>
      )}

      {(status === 'creating' || status === 'rebuilding') && (
        <span className="text-sm text-muted-foreground">Please wait...</span>
      )}
    </div>
  );
}
