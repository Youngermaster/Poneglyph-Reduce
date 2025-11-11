package core;

import model.Task;
import model.TaskType;
import model.Worker;
import telemetry.MqttClientManager;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

/**
 * Scheduler inteligente que asigna tareas basándose en recursos y carga de workers.
 * Mantiene compatibilidad con el scheduler original pero agrega inteligencia de balanceo.
 */
public class SmartScheduler extends Scheduler {
    private final Map<String, Worker> workers;
    private final MqttClientManager mqtt;

    // Cola organizada por prioridad para diferentes tipos de tareas
    private final BlockingQueue<Task> mapTasks = new LinkedBlockingQueue<>();
    private final BlockingQueue<Task> reduceTasks = new LinkedBlockingQueue<>();

    // Tracking de asignaciones para métricas y tolerancia a fallos
    private final Map<String, Long> taskAssignmentTimes = new ConcurrentHashMap<>();
    private final Map<String, TaskAssignment> assignedTasks = new ConcurrentHashMap<>(); // taskId -> assignment info
    private final ScheduledExecutorService faultToleranceExecutor = Executors.newScheduledThreadPool(2);
    
    // Configuración de timeouts
    private static final long TASK_TIMEOUT_MS = 300_000; // 5 minutos
    private static final long WORKER_TIMEOUT_MS = 120_000; // 2 minutos 
    private static final long FAULT_CHECK_INTERVAL_MS = 30_000; // 30 segundos
    
    // Clase interna para tracking de asignaciones
    private static class TaskAssignment {
        final String taskId;
        final String workerId; 
        final long assignedTime;
        final Task task;
        
        TaskAssignment(String taskId, String workerId, Task task) {
            this.taskId = taskId;
            this.workerId = workerId;
            this.assignedTime = System.currentTimeMillis();
            this.task = task;
        }
        
        boolean isTimedOut() {
            return (System.currentTimeMillis() - assignedTime) > TASK_TIMEOUT_MS;
        }
    }

    public SmartScheduler(BlockingQueue<Task> pending, Map<String, Worker> workers, MqttClientManager mqtt) {
        super(pending);
        this.workers = workers;
        this.mqtt = mqtt;
        
        // Iniciar threads de tolerancia a fallos
        startFaultToleranceSystem();
    }
    
    /**
     * Inicia el sistema de tolerancia a fallos con verificaciones periódicas.
     */
    private void startFaultToleranceSystem() {
        // Thread para detectar tareas colgadas y workers muertos
        faultToleranceExecutor.scheduleWithFixedDelay(this::checkForFailedTasks, 
                FAULT_CHECK_INTERVAL_MS, FAULT_CHECK_INTERVAL_MS, TimeUnit.MILLISECONDS);
                
        // Thread para limpieza de workers inactivos
        faultToleranceExecutor.scheduleWithFixedDelay(this::cleanupDeadWorkers,
                WORKER_TIMEOUT_MS, WORKER_TIMEOUT_MS, TimeUnit.MILLISECONDS);
    }
    
    /**
     * Verifica tareas colgadas y las re-encola.
     */
    private void checkForFailedTasks() {
        List<TaskAssignment> failedTasks = new ArrayList<>();
        long currentTime = System.currentTimeMillis();
        
        // Encontrar tareas que han excedido el timeout
        assignedTasks.values().removeIf(assignment -> {
            if (assignment.isTimedOut()) {
                failedTasks.add(assignment);
                return true; // Remover de assignedTasks
            }
            return false;
        });
        
        // Re-encolar tareas fallidas
        for (TaskAssignment failedTask : failedTasks) {
            System.out.println("[FAULT TOLERANCE] Task " + failedTask.taskId + 
                " timed out (worker: " + failedTask.workerId + "), re-queueing...");
            
            // Actualizar métricas del worker
            Worker worker = workers.get(failedTask.workerId);
            if (worker != null) {
                worker.onTaskFailed();
            }
            
            // Re-encolar la tarea
            enqueue(failedTask.task);
            
            // Limpiar tracking
            taskAssignmentTimes.remove(failedTask.taskId);
            
            // Publicar evento de recuperación
            if (mqtt != null) {
                mqtt.publishJson("gridmr/scheduler/task/recovered", Map.of(
                    "taskId", failedTask.taskId,
                    "workerId", failedTask.workerId, 
                    "timeoutMs", currentTime - failedTask.assignedTime,
                    "reason", "timeout",
                    "ts", currentTime
                ));
            }
        }
        
        if (!failedTasks.isEmpty()) {
            System.out.println("[FAULT TOLERANCE] Recovered " + failedTasks.size() + " failed tasks");
        }
    }
    
    /**
     * Limpia workers que no han enviado heartbeat recientemente.
     */
    private void cleanupDeadWorkers() {
        long currentTime = System.currentTimeMillis();
        List<String> deadWorkers = new ArrayList<>();
        
        workers.entrySet().removeIf(entry -> {
            Worker worker = entry.getValue();
            if ((currentTime - worker.lastHeartbeat) > WORKER_TIMEOUT_MS && !worker.isHealthy()) {
                deadWorkers.add(entry.getKey());
                return true;
            }
            return false;
        });
        
        // Re-encolar tareas de workers muertos
        for (String deadWorkerId : deadWorkers) {
            List<TaskAssignment> deadWorkerTasks = assignedTasks.values().stream()
                .filter(assignment -> deadWorkerId.equals(assignment.workerId))
                .toList();
                
            for (TaskAssignment deadTask : deadWorkerTasks) {
                System.out.println("[FAULT TOLERANCE] Worker " + deadWorkerId + 
                    " is dead, recovering task " + deadTask.taskId);
                    
                enqueue(deadTask.task);
                assignedTasks.remove(deadTask.taskId);
                taskAssignmentTimes.remove(deadTask.taskId);
                
                if (mqtt != null) {
                    mqtt.publishJson("gridmr/scheduler/task/recovered", Map.of(
                        "taskId", deadTask.taskId,
                        "workerId", deadWorkerId,
                        "reason", "dead_worker", 
                        "ts", currentTime
                    ));
                }
            }
            
            System.out.println("[FAULT TOLERANCE] Removed dead worker " + deadWorkerId + 
                ", recovered " + deadWorkerTasks.size() + " tasks");
        }
    }

    @Override
    public void enqueue(Task task) {
        // Separar tareas por tipo para mejor manejo
        if (task.type == TaskType.MAP) {
            mapTasks.offer(task);
        } else if (task.type == TaskType.REDUCE) {
            reduceTasks.offer(task);
        }

        // Publicar métrica de tarea encolada
        if (mqtt != null) {
            mqtt.publishJson("gridmr/scheduler/task/queued", Map.of(
                    "taskId", task.taskId,
                    "jobId", task.jobId,
                    "type", task.type.toString(),
                    "queueSizes", Map.of(
                            "map", mapTasks.size(),
                            "reduce", reduceTasks.size()
                    ),
                    "ts", System.currentTimeMillis()
            ));
        }
    }

    @Override
    public void enqueueAll(List<Task> tasks) {
        // Usar nuestro método enqueue para cada tarea
        for (Task task : tasks) {
            enqueue(task);
        }
    }

    /**
     * Selecciona el mejor worker para una tarea basándose en métricas de carga.
     */
    public Worker selectBestWorker(TaskType taskType) {
        List<Worker> availableWorkers = workers.values().stream()
                .filter(Worker::canAcceptTask)
                .sorted(Comparator.comparingDouble(Worker::getLoadScore))
                .limit(3) // Considerar solo los 3 mejores para evitar siempre el mismo
                .toList();

        if (availableWorkers.isEmpty()) {
            return null;
        }

        // Si hay empate en los top workers, usar round-robin simple
        Worker selected = availableWorkers.get(0);

        // Log de la selección para debugging
        System.out.println("[SMART SCHEDULER] Selected worker " + selected.workerId +
                " (score: " + String.format("%.3f", selected.getLoadScore()) +
                ", load: " + selected.activeTasks + "/" + selected.capacity + ")");

        return selected;
    }

    /**
     * Intenta asignar la próxima tarea al worker solicitante.
     * Si el worker no es óptimo, puede devolver null para que espere.
     */
    public Task getNextTaskForWorker(String workerId) {
        Worker requestingWorker = workers.get(workerId);
        System.out.println("[SMART SCHEDULER] Worker " + workerId + " request. Found: " + (requestingWorker != null));

        if (requestingWorker == null) {
            System.out.println("[SMART SCHEDULER] Worker " + workerId + " not found in registry");
            return null;
        }

        if (!requestingWorker.canAcceptTask()) {
            System.out.println("[SMART SCHEDULER] Worker " + workerId + " cannot accept task (health: " +
                    requestingWorker.isHealthy() + ", tasks: " + requestingWorker.activeTasks +
                    "/" + requestingWorker.capacity + ")");
            return null;
        }

        // Priorizar REDUCE sobre MAP para completar trabajos más rápido
        Task task = reduceTasks.poll();
        if (task == null) {
            task = mapTasks.poll();
        }

        System.out.println("[SMART SCHEDULER] Queue sizes - MAP: " + mapTasks.size() +
                ", REDUCE: " + reduceTasks.size() + ", Task assigned: " + (task != null));

        if (task != null) {
            // Seleccionar el mejor worker para esta tarea
            Worker bestWorker = selectBestWorker(task.type);

            // Si el worker solicitante no es el mejor, considerar dársela de todos modos
            // si la diferencia no es muy grande (evitar starvation)
            boolean assignToRequester = false;

            if (bestWorker == null) {
                // No hay workers disponibles, devolver tarea a cola
                if (task.type == TaskType.MAP) {
                    mapTasks.offer(task);
                } else {
                    reduceTasks.offer(task);
                }
                return null;
            }

            if (bestWorker.workerId.equals(workerId)) {
                assignToRequester = true;
            } else {
                // Calcular diferencia de score
                double scoreDiff = requestingWorker.getLoadScore() - bestWorker.getLoadScore();
                // Si la diferencia es pequeña (< 0.2), asignar al solicitante para evitar starvation
                if (scoreDiff < 0.2) {
                    assignToRequester = true;
                }
            }

            if (assignToRequester) {
                // Asignar tarea y actualizar métricas
                requestingWorker.onTaskAssigned();
                long assignmentTime = System.currentTimeMillis();
                taskAssignmentTimes.put(task.taskId, assignmentTime);
                
                // NUEVO: Registrar asignación para fault tolerance
                assignedTasks.put(task.taskId, new TaskAssignment(task.taskId, workerId, task));

                // Publicar métrica de asignación
                if (mqtt != null) {
                    mqtt.publishJson("gridmr/scheduler/task/assigned", Map.of(
                            "taskId", task.taskId,
                            "workerId", workerId,
                            "workerLoad", requestingWorker.activeTasks,
                            "workerCapacity", requestingWorker.capacity,
                            "workerScore", requestingWorker.getLoadScore(),
                            "ts", assignmentTime
                    ));
                }

                return task;
            } else {
                // Devolver tarea a cola y que el worker espere
                if (task.type == TaskType.MAP) {
                    mapTasks.offer(task);
                } else {
                    reduceTasks.offer(task);
                }
                return null;
            }
        }

        return null;
    }

    /**
     * Notifica cuando una tarea se completa para actualizar métricas.
     */
    public void onTaskCompleted(String taskId, String workerId) {
        Worker worker = workers.get(workerId);
        if (worker != null) {
            Long assignmentTime = taskAssignmentTimes.remove(taskId);
            if (assignmentTime != null) {
                long duration = System.currentTimeMillis() - assignmentTime;
                worker.onTaskCompleted(duration);

                // NUEVO: Limpiar tracking de fault tolerance
                assignedTasks.remove(taskId);

                // Publicar métrica de finalización
                if (mqtt != null) {
                    mqtt.publishJson("gridmr/scheduler/task/completed", Map.of(
                            "taskId", taskId,
                            "workerId", workerId,
                            "durationMs", duration,
                            "workerAvgTime", worker.avgTaskTimeMs,
                            "ts", System.currentTimeMillis()
                    ));
                }
            }
        }
    }
    


    /**
     * Obtiene estadísticas del scheduler para monitoreo.
     */
    public Map<String, Object> getSchedulerStats() {
        int healthyWorkers = (int) workers.values().stream().mapToLong(w -> w.isHealthy() ? 1 : 0).sum();
        int totalActiveTasks = workers.values().stream().mapToInt(w -> w.activeTasks).sum();
        int totalCapacity = workers.values().stream().mapToInt(w -> w.capacity).sum();

        // Crear información detallada de cada worker
        List<Map<String, Object>> workerDetails = new ArrayList<>();
        for (Map.Entry<String, Worker> entry : workers.entrySet()) {
            Worker worker = entry.getValue();
            Map<String, Object> workerInfo = new HashMap<>();
            workerInfo.put("id", entry.getKey());
            workerInfo.put("name", worker.name != null ? worker.name : entry.getKey());
            workerInfo.put("isHealthy", worker.isHealthy());
            workerInfo.put("activeTasks", worker.activeTasks);
            workerInfo.put("capacity", worker.capacity);
            workerInfo.put("completedTasks", worker.completedTasks);
            workerInfo.put("loadPercentage", worker.capacity > 0 ? (double) worker.activeTasks / worker.capacity * 100 : 0.0);
            workerInfo.put("loadScore", worker.getLoadScore());
            workerInfo.put("avgTaskTime", worker.avgTaskTimeMs);
            workerInfo.put("cpuUsage", worker.cpuUsage * 100);
            workerInfo.put("memoryUsage", worker.memoryUsage * 100);
            workerInfo.put("lastHeartbeat", worker.lastHeartbeat);
            workerInfo.put("status", worker.isHealthy() ? "HEALTHY" : "UNHEALTHY");
            workerDetails.add(workerInfo);
        }

        Map<String, Object> stats = new HashMap<>();
        stats.put("healthyWorkers", healthyWorkers);
        stats.put("totalWorkers", workers.size());
        stats.put("totalActiveTasks", totalActiveTasks);
        stats.put("totalCapacity", totalCapacity);
        stats.put("queueSizes", Map.of(
                "map", mapTasks.size(),
                "reduce", reduceTasks.size()
        ));
        stats.put("avgWorkerLoad", totalCapacity > 0 ? (double) totalActiveTasks / totalCapacity * 100 : 0.0);
        stats.put("workers", workerDetails);
        stats.put("algorithm", "Smart Scheduler (Hybrid: 50% Load + 30% Resources + 20% Performance)");
        
        return stats;
    }
}
