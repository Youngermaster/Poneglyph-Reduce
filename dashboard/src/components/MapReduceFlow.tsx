import React, { useMemo, useCallback } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
  addEdge,
  ConnectionMode,
} from "reactflow";
import type { Node, Edge, Connection } from "reactflow";
import "reactflow/dist/style.css";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { JobProgress } from "../types/mqtt";

interface MapReduceFlowProps {
  jobs: Map<string, JobProgress>;
}

export const MapReduceFlow = ({ jobs }: MapReduceFlowProps) => {
  const { nodes: initialNodes, edges: initialEdges } = useMemo(() => {
    const nodes: Node[] = [
      {
        id: "master",
        type: "default",
        position: { x: 400, y: 50 },
        data: {
          label: (
            <div className="text-center">
              <Badge className="bg-blue-500 mb-1">Master</Badge>
              <div className="text-xs">Coordinator</div>
            </div>
          ),
        },
        style: {
          background: "#3b82f6",
          color: "white",
          border: "2px solid #1e40af",
          borderRadius: "8px",
          padding: "10px",
        },
      },
    ];

    const edges: Edge[] = [];

    // Get the most recent active job
    const activeJobs = Array.from(jobs.values()).filter(
      (job) => job.state === "RUNNING"
    );
    const latestJob =
      activeJobs.length > 0
        ? activeJobs[activeJobs.length - 1]
        : Array.from(jobs.values())[jobs.size - 1];

    if (latestJob) {
      // Add mapper nodes
      for (let i = 0; i < Math.min(latestJob.totalMaps, 8); i++) {
        const isCompleted = i < latestJob.completedMaps;
        nodes.push({
          id: `mapper-${i}`,
          type: "default",
          position: { x: 50 + i * 100, y: 200 },
          data: {
            label: (
              <div className="text-center">
                <Badge className={isCompleted ? "bg-green-500" : "bg-gray-400"}>
                  M{i}
                </Badge>
                <div className="text-xs">
                  {isCompleted ? "Done" : "Pending"}
                </div>
              </div>
            ),
          },
          style: {
            background: isCompleted ? "#10b981" : "#6b7280",
            color: "white",
            border: `2px solid ${isCompleted ? "#059669" : "#4b5563"}`,
            borderRadius: "8px",
            padding: "8px",
          },
        });

        // Edge from master to mapper
        edges.push({
          id: `master-mapper-${i}`,
          source: "master",
          target: `mapper-${i}`,
          type: "smoothstep",
          animated: !isCompleted,
          style: { stroke: isCompleted ? "#10b981" : "#6b7280" },
        });
      }

      // Add shuffle node
      const shuffleCompleted = latestJob.completedMaps === latestJob.totalMaps;
      nodes.push({
        id: "shuffle",
        type: "default",
        position: { x: 400, y: 350 },
        data: {
          label: (
            <div className="text-center">
              <Badge
                className={shuffleCompleted ? "bg-purple-500" : "bg-gray-400"}
              >
                Shuffle
              </Badge>
              <div className="text-xs">Partitioning</div>
            </div>
          ),
        },
        style: {
          background: shuffleCompleted ? "#8b5cf6" : "#6b7280",
          color: "white",
          border: `2px solid ${shuffleCompleted ? "#7c3aed" : "#4b5563"}`,
          borderRadius: "8px",
          padding: "10px",
        },
      });

      // Edges from mappers to shuffle
      for (let i = 0; i < Math.min(latestJob.totalMaps, 8); i++) {
        const isMapCompleted = i < latestJob.completedMaps;
        edges.push({
          id: `mapper-${i}-shuffle`,
          source: `mapper-${i}`,
          target: "shuffle",
          type: "smoothstep",
          animated: isMapCompleted && !shuffleCompleted,
          style: { stroke: isMapCompleted ? "#8b5cf6" : "#6b7280" },
        });
      }

      // Add reducer nodes
      for (let i = 0; i < latestJob.totalReduces; i++) {
        const isCompleted = i < latestJob.completedReduces;
        nodes.push({
          id: `reducer-${i}`,
          type: "default",
          position: { x: 300 + i * 200, y: 500 },
          data: {
            label: (
              <div className="text-center">
                <Badge
                  className={isCompleted ? "bg-orange-500" : "bg-gray-400"}
                >
                  R{i}
                </Badge>
                <div className="text-xs">
                  {isCompleted ? "Done" : "Pending"}
                </div>
              </div>
            ),
          },
          style: {
            background: isCompleted ? "#f97316" : "#6b7280",
            color: "white",
            border: `2px solid ${isCompleted ? "#ea580c" : "#4b5563"}`,
            borderRadius: "8px",
            padding: "8px",
          },
        });

        // Edge from shuffle to reducer
        edges.push({
          id: `shuffle-reducer-${i}`,
          source: "shuffle",
          target: `reducer-${i}`,
          type: "smoothstep",
          animated: shuffleCompleted && !isCompleted,
          style: { stroke: shuffleCompleted ? "#f97316" : "#6b7280" },
        });
      }
    }

    return { nodes, edges };
  }, [jobs]);

  const [nodes, setNodes, onNodesChange] = useNodesState(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  const onConnect = useCallback(
    (params: Connection) => setEdges((eds) => addEdge(params, eds)),
    [setEdges]
  );

  // Update nodes and edges when jobs change
  React.useEffect(() => {
    setNodes(initialNodes);
    setEdges(initialEdges);
  }, [initialNodes, initialEdges, setNodes, setEdges]);

  return (
    <Card className="h-[600px]">
      <CardHeader>
        <CardTitle className="text-lg">MapReduce Flow Visualization</CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <div className="h-[520px] w-full">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            connectionMode={ConnectionMode.Loose}
            fitView
            attributionPosition="bottom-left"
          >
            <Background />
            <Controls />
            <MiniMap
              nodeColor={(node) => {
                if (node.id === "master") return "#3b82f6";
                if (node.id.startsWith("mapper"))
                  return (node.style?.background as string) || "#6b7280";
                if (node.id === "shuffle")
                  return (node.style?.background as string) || "#6b7280";
                if (node.id.startsWith("reducer"))
                  return (node.style?.background as string) || "#6b7280";
                return "#6b7280";
              }}
              className="bg-background border border-border"
            />
          </ReactFlow>
        </div>
      </CardContent>
    </Card>
  );
};
