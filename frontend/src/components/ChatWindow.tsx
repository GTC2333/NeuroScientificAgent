import { useState, useCallback } from 'react';
import { MessageList } from './MessageList';
import { MessageInput } from './MessageInput';
import { api } from '../services/api';
import type { Message, AgentType } from '../types';

interface ChatWindowProps {
  agentType: AgentType;
}

export function ChatWindow({ agentType }: ChatWindowProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: 'Welcome to the Multi-Agent Scientific Operating System. I\'m the Principal Investigator agent. How can I assist with your research today?',
    },
  ]);
  const [loading, setLoading] = useState(false);

  const handleSend = useCallback(async (text: string) => {
    const userMessage: Message = { role: 'user', content: text };
    setMessages((prev) => [...prev, userMessage]);
    setLoading(true);

    try {
      const response = await api.sendMessage({
        message: text,
        agent_type: agentType,
      });

      const assistantMessage: Message = { role: 'assistant', content: response.reply };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      const errorMessage: Message = {
        role: 'assistant',
        content: 'Error: Could not connect to backend. Please ensure the backend is running on port 8000.',
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setLoading(false);
    }
  }, [agentType]);

  return (
    <div className="flex-1 flex flex-col bg-gray-50">
      <MessageList messages={messages} />
      <MessageInput onSend={handleSend} disabled={loading} />
    </div>
  );
}
