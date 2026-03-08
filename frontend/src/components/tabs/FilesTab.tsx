import { useState } from 'react';

interface FileItem {
  name: string;
  type: 'file' | 'folder';
  size?: number;
  modified?: string;
}

export function FilesTab() {
  const [files] = useState<FileItem[]>([
    { name: 'research/', type: 'folder' },
    { name: 'experiments/', type: 'folder' },
    { name: 'analysis/', type: 'folder' },
    { name: 'config.yaml', type: 'file', size: 1024, modified: '2024-01-15' },
    { name: 'results.json', type: 'file', size: 2048, modified: '2024-01-15' },
  ]);
  const [currentPath, setCurrentPath] = useState<string[]>([]);

  const getIcon = (type: string) => {
    return type === 'folder' ? '📁' : '📄';
  };

  return (
    <div className="space-y-2">
      {/* Breadcrumb */}
      <div className="text-xs text-gray-500 flex gap-1">
        <button onClick={() => setCurrentPath([])} className="hover:text-blue-600">
          root
        </button>
        {currentPath.map((segment, i) => (
          <span key={i}>
            /<button onClick={() => setCurrentPath(currentPath.slice(0, i + 1))} className="hover:text-blue-600">{segment}</button>
          </span>
        ))}
      </div>

      {/* File list */}
      <div className="space-y-1">
        {files.map((file) => (
          <div
            key={file.name}
            className="flex items-center gap-2 p-2 hover:bg-gray-100 rounded cursor-pointer"
          >
            <span>{getIcon(file.type)}</span>
            <span className="flex-1 text-sm text-gray-700">{file.name}</span>
            {file.size && <span className="text-xs text-gray-400">{file.size}B</span>}
          </div>
        ))}
      </div>
    </div>
  );
}
