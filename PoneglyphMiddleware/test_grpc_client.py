#!/usr/bin/env python3
"""
Cliente gRPC para el middleware Poneglyph
"""

import base64
import grpc
import poneglyph_pb2
import poneglyph_pb2_grpc
import time

def get_encoded_scripts():
    """Scripts MapReduce codificados en base64 como los usa el sistema Java"""
    
    map_script = """#!/usr/bin/env python3
import sys

for line in sys.stdin:
    line = line.strip()
    if line:
        words = line.split()
        for word in words:
            word = word.lower().strip('.,!?;:"()[]{}')
            if word:
                print(f"{word}\\t1")
"""
    
    reduce_script = """#!/usr/bin/env python3
import sys

current_word = None
current_count = 0

for line in sys.stdin:
    line = line.strip()
    if '\\t' in line:
        word, count = line.split('\\t', 1)
        try:
            count = int(count)
        except ValueError:
            continue
        
        if current_word == word:
            current_count += count
        else:
            if current_word:
                print(f"{current_word}\\t{current_count}")
            current_word = word
            current_count = count

if current_word:
    print(f"{current_word}\\t{current_count}")
"""
    
    # Codificar como base64 como lo hace el sistema Java
    map_encoded = base64.b64encode(map_script.encode('utf-8'))
    reduce_encoded = base64.b64encode(reduce_script.encode('utf-8'))
    
    return map_encoded, reduce_encoded

def test_grpc_middleware():
    """Probar el middleware gRPC"""
    
    # Conectar al servidor gRPC
    channel = grpc.insecure_channel('localhost:50051')
    
    # Crear clientes para los diferentes servicios
    job_client = poneglyph_pb2_grpc.JobManagementServiceStub(channel)
    worker_client = poneglyph_pb2_grpc.WorkerManagementServiceStub(channel)
    task_client = poneglyph_pb2_grpc.TaskDistributionServiceStub(channel)
    
    print("🚀 Iniciando pruebas del middleware gRPC...")
    
    try:
        # Test 1: Registrar un worker
        print("\\n1. Registrando worker...")
        worker_request = poneglyph_pb2.RegisterWorkerRequest(
            worker_name="test-worker-grpc",
            capacity=10,
            capabilities=["MAP", "REDUCE"],
            location="localhost"
        )
        
        worker_response = worker_client.RegisterWorker(worker_request)
        print(f"✅ Worker registrado: {worker_response.worker_id}")
        print(f"   Mensaje: {worker_response.message}")
        
        # Test 2: Enviar un job
        print("\\n2. Enviando job MapReduce...")
        
        # Obtener scripts
        map_script, reduce_script = get_encoded_scripts()
        
        # Datos de entrada
        input_text = "one fish two fish red fish blue fish\\ngreen fish yellow fish"
        
        job_request = poneglyph_pb2.SubmitJobRequest(
            job_id="test_grpc_job_001",
            input_text=input_text,
            split_size=1000,
            reducers=1,
            map_script=map_script,
            reduce_script=reduce_script,
            priority=poneglyph_pb2.PRIORITY_NORMAL
        )
        
        job_response = job_client.SubmitJob(job_request)
        
        if job_response.success:
            print(f"✅ Job enviado exitosamente: {job_response.job_id}")
            print(f"   Tareas MAP estimadas: {job_response.estimated_map_tasks}")
            print(f"   Mensaje: {job_response.message}")
            
            # Test 3: Verificar estado del job
            print("\\n3. Verificando estado del job...")
            
            for i in range(5):
                time.sleep(2)
                
                status_request = poneglyph_pb2.JobStatusRequest(job_id=job_response.job_id)
                status_response = job_client.GetJobStatus(status_request)
                
                print(f"   Estado: {status_response.state}")
                print(f"   Progreso: {status_response.progress_percentage:.1f}%")
                print(f"   MAP: {status_response.maps_completed}/{status_response.maps_total}")
                print(f"   REDUCE: {status_response.reduces_completed}/{status_response.reduces_total}")
                
                if status_response.progress_percentage >= 100:
                    break
                    
            # Test 4: Worker solicita una tarea
            print("\\n4. Worker solicita tarea...")
            
            task_request = poneglyph_pb2.TaskRequest(
                worker_id=worker_response.worker_id,
                preferred_task_types=["MAP"]
            )
            
            task_response = task_client.RequestTask(task_request)
            
            if task_response.has_task:
                print(f"✅ Tarea asignada: {task_response.task.task_id}")
                print(f"   Tipo: {task_response.task.type}")
                print(f"   Job ID: {task_response.task.job_id}")
                
                # Simular completar la tarea
                print("\\n5. Completando tarea...")
                
                completion_request = poneglyph_pb2.TaskCompletionRequest(
                    worker_id=worker_response.worker_id,
                    task_id=task_response.task.task_id,
                    job_id=task_response.task.job_id,
                    task_type=task_response.task.type,
                    result=poneglyph_pb2.TaskResult(
                        success=True,
                        result_data=b'fish\\t6\\nred\\t1\\nblue\\t1\\ngreen\\t1\\nyellow\\t1\\none\\t1\\ntwo\\t1',
                        error_message=""
                    ),
                    execution_time_ms=1500
                )
                
                completion_response = task_client.CompleteTask(completion_request)
                
                if completion_response.acknowledged:
                    print("✅ Tarea completada exitosamente")
                    print(f"   Mensaje: {completion_response.message}")
                else:
                    print("❌ Error completando tarea")
            else:
                print("ℹ️  No hay tareas disponibles")
            
            # Test 6: Estado final del job
            print("\\n6. Estado final del job...")
            final_status = job_client.GetJobStatus(poneglyph_pb2.JobStatusRequest(job_id=job_response.job_id))
            print(f"   Estado final: {final_status.state}")
            print(f"   Progreso final: {final_status.progress_percentage:.1f}%")
        
        else:
            print(f"❌ Error enviando job: {job_response.message}")
    
    except Exception as e:
        print(f"❌ Error durante las pruebas: {e}")
    
    finally:
        channel.close()
        print("\\n🏁 Pruebas completadas")

if __name__ == '__main__':
    test_grpc_middleware()
