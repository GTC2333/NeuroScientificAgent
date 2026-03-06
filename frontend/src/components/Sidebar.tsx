import { useEffect, useState } from 'react';
import { api } from '../services/api';
import type { Agent, Skill } from '../types';

export function Sidebar() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      try {
        const [agentsData, skillsData] = await Promise.all([
          api.getAgents(),
          api.getSkills(),
        ]);
        setAgents(agentsData);
        setSkills(skillsData.slice(0, 5));
      } catch (err) {
        console.error('Failed to load sidebar data:', err);
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <aside className="w-72 bg-white border-r border-gray-200 p-4">
        <div className="text-gray-500">Loading...</div>
      </aside>
    );
  }

  return (
    <aside className="w-72 bg-white border-r border-gray-200 p-4 overflow-y-auto">
      <section className="mb-6">
        <h3 className="text-xs font-semibold text-gray-500 uppercase mb-3">Available Agents</h3>
        <div className="space-y-2">
          {agents.map((agent) => (
            <div key={agent.type} className="p-3 border border-gray-200 rounded-lg hover:border-blue-400 cursor-pointer">
              <h4 className="font-medium text-sm text-gray-900">{agent.name}</h4>
              <p className="text-xs text-gray-500 mt-1">{agent.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section>
        <h3 className="text-xs font-semibold text-gray-500 uppercase mb-3">Available Skills</h3>
        <div className="space-y-2">
          {skills.map((skill) => (
            <div key={skill.name} className="p-3 border border-gray-200 rounded-lg hover:border-blue-400 cursor-pointer">
              <h4 className="font-medium text-sm text-gray-900">{skill.name}</h4>
              <p className="text-xs text-gray-500 mt-1">{skill.description}</p>
            </div>
          ))}
        </div>
      </section>
    </aside>
  );
}
