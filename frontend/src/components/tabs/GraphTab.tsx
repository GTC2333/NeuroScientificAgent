import { useNodesState, useEdgesState } from '@xyflow/react';
import { ReactFlow, Background, Controls } from '@xyflow/react';
import '@xyflow/react/dist/style.css';

// Grid layout constants
const GRID_SPACING = 150;
const CENTER_X = 250;
const LEFT_X = 100;
const RIGHT_X = 400;
const START_Y = 0;
const LEVEL_1_Y = GRID_SPACING;
const LEVEL_2_Y = GRID_SPACING * 2;

const initialNodes = [
  { id: '1', position: { x: CENTER_X, y: START_Y }, data: { label: 'Principal' }, type: 'input' },
  { id: '2', position: { x: LEFT_X, y: LEVEL_1_Y }, data: { label: 'Theorist' } },
  { id: '3', position: { x: CENTER_X, y: LEVEL_1_Y }, data: { label: 'Experimentalist' } },
  { id: '4', position: { x: RIGHT_X, y: LEVEL_1_Y }, data: { label: 'Analyst' } },
  { id: '5', position: { x: CENTER_X, y: LEVEL_2_Y }, data: { label: 'Writer' }, type: 'output' },
];

const initialEdges = [
  { id: 'e1-2', source: '1', target: '2', animated: true },
  { id: 'e1-3', source: '1', target: '3', animated: true },
  { id: 'e1-4', source: '1', target: '4', animated: true },
  { id: 'e2-5', source: '2', target: '5' },
  { id: 'e3-5', source: '3', target: '5' },
  { id: 'e4-5', source: '4', target: '5' },
];

export function GraphTab() {
  const [nodes, , onNodesChange] = useNodesState(initialNodes);
  const [edges, , onEdgesChange] = useEdgesState(initialEdges);

  return (
    <div className="h-64 w-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        fitView
        attributionPosition="bottom-left"
      >
        <Background />
        <Controls />
      </ReactFlow>
    </div>
  );
}
