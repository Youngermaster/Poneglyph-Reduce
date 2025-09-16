import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { 
  Users, 
  Activity, 
  List, 
  Cpu, 
  CheckCircle,
  Clock,
  Zap,
  Target,
  TrendingUp,
  AlertCircle
} from "lucide-react";

interface WorkerDetail {
  id: string;
  name: string;
  isHealthy: boolean;
  activeTasks: number;
  capacity: number;
  completedTasks: number;
  loadPercentage: number;
  loadScore: number;
  avgTaskTime: number;
  cpuUsage: number;
  memoryUsage: number;
  lastHeartbeat: number;
  status: string;
}

interface SchedulerStats {
  healthyWorkers: number;
  totalWorkers: number;
  totalActiveTasks: number;
  totalCapacity: number;
  queueSizes: {
    map: number;
    reduce: number;
  };
  avgWorkerLoad: number;
  workers: WorkerDetail[];
  algorithm: string;
}

interface SmartSchedulerViewProps {
  schedulerStats: SchedulerStats | null;
  isLoading: boolean;
  error: string | null;
  lastUpdate: Date | null;
}

export function SmartSchedulerView({ 
  schedulerStats, 
  isLoading, 
  error, 
  lastUpdate 
}: SmartSchedulerViewProps) {
  // Show error state
  if (error) {
    return (
      <Alert className="mb-4 border-red-200 bg-red-50">
        <AlertCircle className="h-4 w-4" />
        <AlertDescription className="text-red-800">
          Scheduler Connection Error: {error}
        </AlertDescription>
      </Alert>
    );
  }

  // Show loading state
  if (isLoading || !schedulerStats) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <Activity className="h-8 w-8 animate-spin mx-auto mb-2" />
          <p className="text-muted-foreground">Loading Smart Scheduler data...</p>
        </div>
      </div>
    );
  }

  const totalPendingTasks = schedulerStats.queueSizes.map + schedulerStats.queueSizes.reduce;
  const utilizationRate = schedulerStats.totalCapacity > 0 ? (schedulerStats.totalActiveTasks / schedulerStats.totalCapacity) * 100 : 0;

  // Helper function to format time ago
  const timeAgo = (timestamp: number) => {
    const diff = Date.now() - timestamp;
    const minutes = Math.floor(diff / 60000);
    if (minutes < 1) return "Just now";
    if (minutes === 1) return "1 minute ago";
    return `${minutes} minutes ago`;
  };

  return (
    <div className="space-y-4">
      {/* Scheduler Overview Cards - Same style as main dashboard */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Active Workers</CardTitle>
            <Users className="h-4 w-4 text-blue-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-blue-600">
              {schedulerStats.healthyWorkers}
            </div>
            <p className="text-xs text-muted-foreground">
              of {schedulerStats.totalWorkers} total
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Queue Size</CardTitle>
            <List className="h-4 w-4 text-orange-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-orange-600">
              {totalPendingTasks}
            </div>
            <p className="text-xs text-muted-foreground">
              {schedulerStats.queueSizes.map} MAP, {schedulerStats.queueSizes.reduce} REDUCE
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Utilization</CardTitle>
            <TrendingUp className="h-4 w-4 text-green-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-green-600">
              {utilizationRate.toFixed(0)}%
            </div>
            <p className="text-xs text-muted-foreground">
              {schedulerStats.totalActiveTasks} / {schedulerStats.totalCapacity} capacity
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Avg Load</CardTitle>
            <Target className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-purple-600">
              {schedulerStats.avgWorkerLoad.toFixed(0)}%
            </div>
            <p className="text-xs text-muted-foreground">
              Smart balancing active
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Worker Cards - Same grid style as JobCard */}
      <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-4">
        {schedulerStats.workers.map((worker) => (
          <Card key={worker.id} className="hover:shadow-md transition-shadow">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-lg font-medium">{worker.name}</CardTitle>
              <div className="flex items-center gap-2">
                <Badge 
                  variant={
                    worker.status === "HEALTHY" ? (worker.activeTasks > 0 ? "default" : "secondary") : "destructive"
                  }
                >
                  {worker.status === "HEALTHY" ? (worker.activeTasks > 0 ? "ACTIVE" : "IDLE") : "OFFLINE"}
                </Badge>
                {worker.activeTasks > 0 && (
                  <Zap className="h-4 w-4 text-yellow-500" />
                )}
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {/* Active Tasks */}
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Activity className="h-4 w-4" />
                    Active Tasks
                  </span>
                  <span className="text-lg font-bold">
                    {worker.activeTasks}/{worker.capacity}
                  </span>
                </div>
                
                {/* Progress bar for task utilization */}
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div 
                    className={`h-2 rounded-full transition-all duration-300 ${
                      worker.activeTasks > 0 ? "bg-blue-600" : 
                      worker.status === "HEALTHY" ? "bg-gray-400" : 
                      "bg-red-600"
                    }`}
                    style={{ width: `${worker.loadPercentage}%` }}
                  ></div>
                </div>

                {/* Completed Tasks */}
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 text-sm text-muted-foreground">
                    <CheckCircle className="h-4 w-4" />
                    Completed
                  </span>
                  <span className="text-sm font-semibold text-green-600">
                    {worker.completedTasks}
                  </span>
                </div>

                {/* System Resources */}
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <div className="flex items-center gap-1 text-muted-foreground">
                      <Cpu className="h-3 w-3" />
                      CPU
                    </div>
                    <div className="font-semibold">{worker.cpuUsage.toFixed(0)}%</div>
                  </div>
                  <div>
                    <div className="flex items-center gap-1 text-muted-foreground">
                      <Activity className="h-3 w-3" />
                      Memory
                    </div>
                    <div className="font-semibold">{worker.memoryUsage.toFixed(0)}%</div>
                  </div>
                </div>

                {/* Performance Metrics */}
                <div className="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <div className="text-muted-foreground">Avg Task Time</div>
                    <div className="font-semibold">{worker.avgTaskTime.toFixed(0)}ms</div>
                  </div>
                  <div>
                    <div className="text-muted-foreground">Load Score</div>
                    <div className="font-semibold">{worker.loadScore.toFixed(2)}</div>
                  </div>
                </div>

                {/* Last Seen */}
                <div className="pt-2 border-t flex items-center justify-between text-xs">
                  <span className="text-muted-foreground">ID: {worker.id.split('-')[1]}</span>
                  <span className="flex items-center gap-1 text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {timeAgo(worker.lastHeartbeat)}
                  </span>
                </div>
              </div>
            </CardContent>
          </Card>
        ))}

        {schedulerStats.workers.length === 0 && (
          <Card className="col-span-full">
            <CardContent className="flex items-center justify-center h-32">
              <div className="text-center text-muted-foreground">
                <Users className="h-8 w-8 mx-auto mb-2" />
                <p>No workers registered. Scale up workers to see them here.</p>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Algorithm Info Card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Zap className="h-5 w-5 text-yellow-500" />
            Smart Scheduler Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 text-sm">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-blue-500" />
              <span>Updated: {lastUpdate ? lastUpdate.toLocaleTimeString() : 'Never'}</span>
            </div>
            <div className="flex items-center gap-2">
              <Target className="h-4 w-4 text-green-500" />
              <span>Algorithm: Hybrid Load Balancing</span>
            </div>
            <div className="flex items-center gap-2">
              <TrendingUp className="h-4 w-4 text-purple-500" />
              <span>Mode: Real-time Distribution</span>
            </div>
          </div>
          
          <div className="mt-4 p-3 bg-muted rounded-lg">
            <h4 className="font-semibold text-sm mb-2">Scheduling Strategy</h4>
            <p className="text-xs text-muted-foreground">
              {schedulerStats.algorithm ? schedulerStats.algorithm : "Smart Scheduler (Hybrid: 50% Load + 30% Resources + 20% Performance)"}. 
              Includes starvation prevention and automatic load balancing across all workers.
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}