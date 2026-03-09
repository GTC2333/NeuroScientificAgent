// MAS Chat Component - Research Agent Chat Interface
import { useState, useEffect, useRef } from 'react';
import { masApi } from '../../services/mas-api';

const AGENT_ROLES = [
  { id: 'principal', name: 'Principal Investigator', icon: '👑', color: 'bg-purple-600' },
  { id: 'theorist', name: 'Theorist', icon: '📚', color: 'bg-blue-600' },
  { id: 'experimentalist', name: 'Experimentalist', icon: '🔬', color: 'bg-green-600' },
  { id: 'analyst', name: 'Analyst', icon: '📊', color: 'bg-orange-600' },
  { id: 'writer', name: 'Writer', icon: '✍️', color: 'bg-pink-600' },
];

export function MasChat({ sessionId }) {
  const [message, setMessage] = useState('');
  const [agentType, setAgentType] = useState('principal');
  const [selectedSkills, setSelectedSkills] = useState([]);
  const [skills, setSkills] = useState([]);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showSkills, setShowSkills] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    masApi.getSkills().then(setSkills).catch(console.error);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!message.trim() || loading) return;

    const userMsg = { role: 'user', content: message };
    setMessages(prev => [...prev, userMsg]);
    const msgToSend = message;
    setMessage('');
    setLoading(true);

    try {
      const response = await masApi.sendMessage(msgToSend, agentType, sessionId, selectedSkills);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: response.reply,
        agent: response.agent_type,
      }]);
    } catch (error) {
      setMessages(prev => [...prev, {
        role: 'error',
        content: `Error: ${error.message}`,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const toggleSkill = (skillId) => {
    setSelectedSkills(prev =>
      prev.includes(skillId)
        ? prev.filter(s => s !== skillId)
        : [...prev, skillId]
    );
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div className="flex flex-col h-full bg-gray-900">
      {/* Agent Selection */}
      <div className="p-3 border-b border-gray-700">
        <div className="flex gap-2 flex-wrap">
          {AGENT_ROLES.map(agent => (
            <button
              key={agent.id}
              onClick={() => setAgentType(agent.id)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                agentType === agent.id
                  ? `${agent.color} text-white`
                  : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
              }`}
            >
              {agent.icon} {agent.name}
            </button>
          ))}
        </div>
      </div>

      {/* Skills Toggle */}
      {skills.length > 0 && (
        <div className="px-3 py-2 border-b border-gray-700">
          <button
            onClick={() => setShowSkills(!showSkills)}
            className="text-sm text-gray-400 hover:text-white flex items-center gap-1"
          >
            <span>{showSkills ? '▼' : '▶'}</span>
            Skills ({selectedSkills.length}/{skills.length})
          </button>

          {showSkills && (
            <div className="mt-2 flex gap-2 flex-wrap">
              {skills.map(skill => (
                <button
                  key={skill.id || skill.name}
                  onClick={() => toggleSkill(skill.id || skill.name)}
                  className={`px-2 py-1 rounded text-xs transition-colors ${
                    selectedSkills.includes(skill.id || skill.name)
                      ? 'bg-green-600 text-white'
                      : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                  }`}
                >
                  {skill.name}
                </button>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-gray-500 mt-8">
            <p className="text-lg mb-2">🔬 MAS Research Assistant</p>
            <p className="text-sm">Select an agent role and send a message to start your research</p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] rounded-lg p-3 ${
              msg.role === 'user'
                ? 'bg-blue-600 text-white'
                : msg.role === 'error'
                ? 'bg-red-600 text-white'
                : 'bg-gray-700 text-gray-100'
            }`}>
              {msg.agent && (
                <span className="text-xs opacity-75 block mb-1">
                  {AGENT_ROLES.find(a => a.id === msg.agent)?.icon || ''} {msg.agent}
                </span>
              )}
              <div className="whitespace-pre-wrap">{msg.content}</div>
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-gray-700 rounded-lg p-3">
              <span className="animate-pulse text-gray-300">Thinking...</span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-4 border-t border-gray-700">
        <div className="flex gap-2">
          <textarea
            value={message}
            onChange={(e) => setMessage(e.target.value)}
            onKeyPress={handleKeyPress}
            placeholder="Ask the research team..."
            rows={1}
            className="flex-1 bg-gray-700 text-white rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            style={{ minHeight: '40px', maxHeight: '120px' }}
          />
          <button
            onClick={sendMessage}
            disabled={loading || !message.trim()}
            className="bg-blue-600 hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg px-4 py-2 font-medium"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
