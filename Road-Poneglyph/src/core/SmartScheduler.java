package core;

import model.Task;
import model.TaskType;
import model.Worker;
import telemetry.MqttClientManager;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.BlockingQueue;
import java.util.concurrent.LinkedBlockingQueue;

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
    
    // Tracking de asignaciones para métricas
    private final Map<String, Long> taskAssignmentTimes = new ConcurrentHashMap<>();

    public SmartScheduler(BlockingQueue<Task> pending, Map<String, Worker> workers, MqttClientManager mqtt) {
        super(pending);
        this.workers = workers;
        this.mqtt = mqtt;
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
                taskAssignmentTimes.put(task.taskId, System.currentTimeMillis());
                
                // Publicar métrica de asignación
                if (mqtt != null) {
                    mqtt.publishJson("gridmr/scheduler/task/assigned", Map.of(
                        "taskId", task.taskId,
                        "workerId", workerId,
                        "workerLoad", requestingWorker.activeTasks,
                        "workerCapacity", requestingWorker.capacity,
                        "workerScore", requestingWorker.getLoadScore(),
                        "ts", System.currentTimeMillis()
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
        
        return Map.of(
            "healthyWorkers", healthyWorkers,
            "totalWorkers", workers.size(),
            "totalActiveTasks", totalActiveTasks,
            "totalCapacity", totalCapacity,
            "queueSizes", Map.of(
                "map", mapTasks.size(),
                "reduce", reduceTasks.size()
            ),
            "avgWorkerLoad", totalCapacity > 0 ? (double) totalActiveTasks / totalCapacity : 0.0
        );
    }
}