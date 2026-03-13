import { useEffect, useRef } from 'react';
import type { Message } from '../types';

interface MessageListProps {
  messages: Message[];
}

export function MessageList({ messages }: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    containerRef.current?.scrollTo(0, containerRef.current.scrollHeight);
  }, [messages]);

  return (
    <div ref={containerRef} className="flex-1 overflow-y-auto p-6 space-y-4">
      {messages.length === 0 && (
        <div className="text-center text-gray-500 py-8">
          Start a conversation with the research agent...
        </div>
      )}

      {messages.map((message, index) => (
        <div
          key={index}
          className={`max-w-[70%] p-4 rounded-xl ${
            message.role === 'user'
              ? 'ml-auto bg-blue-600 text-white'
              : 'mr-auto bg-white border border-gray-200'
          }`}
        >
          <div className="text-xs opacity-70 mb-1">
            {message.role === 'user' ? 'You' : 'Assistant'}
          </div>
          <div className="whitespace-pre-wrap">{message.content}</div>
        </div>
      ))}
    </div>
  );
}
