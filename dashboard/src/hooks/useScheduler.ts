import { useEffect, useState, useCallback } from "react";

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

interface UseSchedulerReturn {
  schedulerStats: SchedulerStats | null;
  isLoading: boolean;
  error: string | null;
  lastUpdate: Date | null;
}

export const useScheduler = (): UseSchedulerReturn => {
  const [schedulerStats, setSchedulerStats] = useState<SchedulerStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null);

  const fetchSchedulerStats = useCallback(async () => {
    try {
      // Use localhost for development - matching the pattern from the existing code
      const response = await fetch('http://localhost:8080/api/scheduler/stats');
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      
      const data: SchedulerStats = await response.json();
      setSchedulerStats(data);
      setLastUpdate(new Date());
      setError(null);
      setIsLoading(false);
    } catch (err) {
      console.error('Failed to fetch scheduler stats:', err);
      setError(`Failed to fetch scheduler stats: ${err instanceof Error ? err.message : 'Unknown error'}`);
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Initial fetch
    fetchSchedulerStats();

    // Set up polling interval (every 3 seconds)
    const interval = setInterval(fetchSchedulerStats, 3000);

    // Cleanup interval on unmount
    return () => {
      clearInterval(interval);
    };
  }, [fetchSchedulerStats]);

  return {
    schedulerStats,
    isLoading,
    error,
    lastUpdate,
  };
};