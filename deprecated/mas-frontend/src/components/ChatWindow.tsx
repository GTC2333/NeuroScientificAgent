import { useState, useCallback } from 'react';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { useStore } from '../store/useStore';
import type { SessionStore } from '../store/useStore';
import { api } from '../services/api';
import type { Message, Session } from '../types';

export function ChatWindow() {
  const currentSessionId = useStore((state: SessionStore) => state.currentSessionId);
  const sessions = useStore((state: SessionStore) => state.sessions);
  const addMessage = useStore((state: SessionStore) => state.addMessage);
  const [loading, setLoading] = useState(false);

  const currentSession = sessions.find((s: Session) => s.id === currentSessionId);
  const messages = currentSession?.messages || [];

  const handleSend = useCallback(async (text: string) => {
    if (!currentSessionId) return;

    const userMessage: Message = {
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };
    addMessage(currentSessionId, userMessage);
    setLoading(true);

    try {
      console.log('[ChatWindow] Sending message:', text);
      const response = await api.sendMessage({
        message: text,
        agent_type: currentSession?.agents[0] || 'principal',
        history: messages,
        session_id: currentSessionId,
        selected_skills: currentSession?.skills,
      });

      console.log('[ChatWindow] Response received:', response);

      // Check if response is an error
      if (response.reply?.startsWith('Error:')) {
        const errorMsg: Message = {
          role: 'assistant',
          content: response.reply,
          timestamp: new Date().toISOString(),
        };
        addMessage(currentSessionId, errorMsg);
        console.error('[ChatWindow] Backend error:', response.reply);
      } else {
        const assistantMessage: Message = {
          role: 'assistant',
          content: response.reply || 'No response received',
          timestamp: new Date().toISOString(),
        };
        addMessage(currentSessionId, assistantMessage);
      }
    } catch (err) {
      console.error('[ChatWindow] Error:', err);
      const errorMsg = err instanceof Error ? err.message : String(err);
      const errorMessage: Message = {
        role: 'assistant',
        content: `Error: ${errorMsg}\n\nPlease check the backend terminal for details.`,
        timestamp: new Date().toISOString(),
      };
      addMessage(currentSessionId, errorMessage);
    } finally {
      setLoading(false);
    }
  }, [currentSessionId, currentSession, messages, addMessage]);

  // Skills quick bar
  const skills = currentSession?.skills || [];

  return (
    <div className="flex-1 flex flex-col bg-gray-50">
      {/* Skills Quick Bar */}
      {skills.length > 0 && (
        <div className="px-4 py-2 bg-white border-b border-gray-200 flex items-center gap-2 overflow-x-auto">
          <span className="text-xs text-gray-500 shrink-0">Skills:</span>
          {skills.map((skill) => (
            <span
              key={skill}
              className="px-2 py-1 text-xs bg-blue-100 text-blue-700 rounded-full shrink-0"
            >
              {skill}
            </span>
          ))}
        </div>
      )}
      <MessageList messages={messages} />
      <MessageInput onSend={handleSend} disabled={loading} />
    </div>
  );
}
