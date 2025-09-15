export interface JobCreated {
  splitSize: number;
  jobId: string;
  reducers: number;
  ts: number;
  maps: number;
}

export interface MapCompleted {
  mapsCompleted: number;
  ts: number;
  taskId: string;
  added: number;
}

export interface ReduceCompleted {
  ts: number;
  taskId: string;
  reducesCompleted: number;
}

export interface ShufflePartitions {
  sizes: number[];
  ts: number;
}

export interface JobState {
  ts: number;
  state: "RUNNING" | "SUCCEEDED" | "FAILED" | "PENDING";
}

export interface WorkerNode {
  id: string;
  type: "master" | "worker";
  status: "online" | "offline" | "busy";
  lastSeen: number;
  currentTask?: string;
}

export interface JobProgress {
  jobId: string;
  totalMaps: number;
  completedMaps: number;
  totalReduces: number;
  completedReduces: number;
  state: JobState["state"];
  startTime: number;
  endTime?: number;
}

export type MqttMessage =
  | { type: "job/created"; data: JobCreated }
  | { type: "map/completed"; data: MapCompleted }
  | { type: "reduce/completed"; data: ReduceCompleted }
  | { type: "shuffle/partitions"; data: ShufflePartitions }
  | { type: "job/state"; data: JobState };
