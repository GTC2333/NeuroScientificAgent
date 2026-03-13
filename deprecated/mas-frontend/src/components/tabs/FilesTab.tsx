export function FilesTab() {
  return (
    <div className="p-4">
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-4">
        <h3 className="font-medium text-blue-800 mb-2">文件操作</h3>
        <p className="text-sm text-blue-700">
          文件操作已集成到 Claude Code 工具中。
        </p>
        <ul className="text-sm text-blue-600 mt-2 space-y-1">
          <li>• <code>Read</code> - 读取文件内容</li>
          <li>• <code>Glob</code> - 搜索文件</li>
          <li>• <code>Grep</code> - 文件内容搜索</li>
          <li>• <code>Edit</code> - 编辑文件</li>
          <li>• <code>Write</code> - 写入文件</li>
        </ul>
      </div>
      <p className="text-xs text-gray-500">
        请在聊天窗口中使用以上工具进行文件操作。
      </p>
    </div>
  );
}
