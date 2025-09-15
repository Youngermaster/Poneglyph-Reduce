package model;

public class Worker {
    public String workerId;
    public String name;
    public int capacity;
    public long lastHeartbeat = System.currentTimeMillis();
    
    // Métricas de rendimiento
    public int activeTasks = 0;
    public int completedTasks = 0;
    public double avgTaskTimeMs = 0.0;
    public long totalTaskTimeMs = 0;
    
    // Recursos del sistema (reportados por el worker)
    public double cpuUsage = 0.0;     // 0.0 - 1.0
    public double memoryUsage = 0.0;  // 0.0 - 1.0
    
    /**
     * Calcula un score de carga para este worker.
     * Score más bajo = mejor candidato para asignar tareas.
     */
    public double getLoadScore() {
        if (capacity <= 0) return Double.MAX_VALUE;
        
        double loadFactor = (double) activeTasks / capacity;
        double resourceFactor = (cpuUsage + memoryUsage) / 2.0;
        double performanceFactor = avgTaskTimeMs > 0 ? avgTaskTimeMs / 10000.0 : 0.1; // Normalizar a ~10s
        
        // Pesos: carga actual (50%), recursos (30%), rendimiento (20%)
        return loadFactor * 0.5 + resourceFactor * 0.3 + performanceFactor * 0.2;
    }
    
    /**
     * Verifica si el worker está saludable (heartbeat reciente).
     */
    public boolean isHealthy() {
        return (System.currentTimeMillis() - lastHeartbeat) < 30000; // 30 segundos
    }
    
    /**
     * Verifica si el worker puede tomar más tareas.
     */
    public boolean canAcceptTask() {
        return isHealthy() && activeTasks < capacity;
    }
    
    /**
     * Actualiza métricas cuando se completa una tarea.
     */
    public void onTaskCompleted(long taskDurationMs) {
        activeTasks = Math.max(0, activeTasks - 1);
        completedTasks++;
        totalTaskTimeMs += taskDurationMs;
        avgTaskTimeMs = (double) totalTaskTimeMs / completedTasks;
    }
    
    /**
     * Incrementa el contador de tareas activas.
     */
    public void onTaskAssigned() {
        activeTasks++;
    }
}
