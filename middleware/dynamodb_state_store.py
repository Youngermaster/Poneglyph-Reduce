"""
DynamoDB State Store Implementation
Provides persistent storage for jobs and worker data using AWS DynamoDB
"""

import os
import time
import json
from typing import Dict, Optional, Any, List

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    boto3 = None


class DynamoDBStateStore:
    def __init__(self):
        self.region = os.getenv("AWS_REGION", "us-east-1")
        self.workers_table_name = os.getenv("WORKERS_TABLE", "poneglyph-workers")
        self.jobs_table_name = os.getenv("JOBS_TABLE", "poneglyph-jobs")
        self.tasks_table_name = os.getenv("TASKS_TABLE", "poneglyph-tasks")
        
        self._dynamodb = None
        self._workers_table = None
        self._jobs_table = None
        self._tasks_table = None
        
        # Fallback storage for when DynamoDB is unavailable
        self._workers: Dict[str, Dict[str, Any]] = {}
        self._jobs: Dict[str, Dict[str, Any]] = {}
        self._tasks: Dict[str, Dict[str, Any]] = {}
        
        self._initialize_dynamodb()

    def _initialize_dynamodb(self):
        """Initialize DynamoDB connection and tables"""
        if not boto3:
            print("DynamoDBStateStore: boto3 not available, using fallback storage")
            return
        
        try:
            self._dynamodb = boto3.resource('dynamodb', region_name=self.region)
            
            # Initialize table references
            self._workers_table = self._dynamodb.Table(self.workers_table_name)
            self._jobs_table = self._dynamodb.Table(self.jobs_table_name)
            self._tasks_table = self._dynamodb.Table(self.tasks_table_name)
            
            # Test connection
            self._workers_table.load()
            self._jobs_table.load()
            self._tasks_table.load()
            
            print(f"DynamoDBStateStore: Connected to DynamoDB in {self.region}")
            print(f"  Workers table: {self.workers_table_name}")
            print(f"  Jobs table: {self.jobs_table_name}")
            print(f"  Tasks table: {self.tasks_table_name}")
            
        except NoCredentialsError:
            print("DynamoDBStateStore: AWS credentials not found, using fallback storage")
            self._dynamodb = None
        except ClientError as e:
            print(f"DynamoDBStateStore: DynamoDB error ({e}), using fallback storage")
            self._dynamodb = None
        except Exception as e:
            print(f"DynamoDBStateStore: Initialization error ({e}), using fallback storage")
            self._dynamodb = None

    def create_tables_if_not_exist(self):
        """Create DynamoDB tables if they don't exist"""
        if not self._dynamodb:
            print("DynamoDB not available, cannot create tables")
            return False
        
        try:
            # Workers table schema
            self._create_table_if_not_exists(
                table_name=self.workers_table_name,
                key_schema=[
                    {'AttributeName': 'worker_id', 'KeyType': 'HASH'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'worker_id', 'AttributeType': 'S'}
                ]
            )
            
            # Jobs table schema
            self._create_table_if_not_exists(
                table_name=self.jobs_table_name,
                key_schema=[
                    {'AttributeName': 'job_id', 'KeyType': 'HASH'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'job_id', 'AttributeType': 'S'}
                ]
            )
            
            # Tasks table schema
            self._create_table_if_not_exists(
                table_name=self.tasks_table_name,
                key_schema=[
                    {'AttributeName': 'task_id', 'KeyType': 'HASH'},
                    {'AttributeName': 'job_id', 'KeyType': 'RANGE'}
                ],
                attribute_definitions=[
                    {'AttributeName': 'task_id', 'AttributeType': 'S'},
                    {'AttributeName': 'job_id', 'AttributeType': 'S'}
                ]
            )
            
            print("DynamoDB tables verified/created successfully")
            return True
            
        except Exception as e:
            print(f"Error creating DynamoDB tables: {e}")
            return False

    def _create_table_if_not_exists(self, table_name: str, key_schema: List[Dict], attribute_definitions: List[Dict]):
        """Create a DynamoDB table if it doesn't exist"""
        try:
            table = self._dynamodb.Table(table_name)
            table.load()
            print(f"Table {table_name} already exists")
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceNotFoundException':
                print(f"Creating table {table_name}...")
                table = self._dynamodb.create_table(
                    TableName=table_name,
                    KeySchema=key_schema,
                    AttributeDefinitions=attribute_definitions,
                    BillingMode='PAY_PER_REQUEST'  # On-demand pricing
                )
                table.wait_until_exists()
                print(f"Table {table_name} created successfully")
            else:
                raise

    # Worker operations
    def upsert_worker(self, worker_id: str, info: Dict[str, Any]):
        """Store or update worker information"""
        now = int(time.time() * 1000)
        info = dict(info)
        info["last_heartbeat"] = now
        info["updated_at"] = now
        
        if self._dynamodb and self._workers_table:
            try:
                # Prepare item for DynamoDB
                item = {"worker_id": worker_id}
                for key, value in info.items():
                    # Convert lists to JSON strings for DynamoDB
                    if isinstance(value, list):
                        item[key] = json.dumps(value)
                    else:
                        item[key] = str(value)
                
                self._workers_table.put_item(Item=item)
            except Exception as e:
                print(f"DynamoDB worker upsert failed: {e}, using fallback")
                self._workers[worker_id] = info
        else:
            self._workers[worker_id] = info

    def get_worker(self, worker_id: str) -> Optional[Dict[str, Any]]:
        """Get worker information"""
        if self._dynamodb and self._workers_table:
            try:
                response = self._workers_table.get_item(Key={"worker_id": worker_id})
                if 'Item' in response:
                    item = response['Item']
                    # Convert back from DynamoDB format
                    result = {}
                    for key, value in item.items():
                        if key == 'worker_id':
                            result[key] = value
                        else:
                            # Try to parse as JSON (for lists), otherwise keep as string
                            try:
                                result[key] = json.loads(value)
                            except (json.JSONDecodeError, TypeError):
                                result[key] = value
                    return result
                return None
            except Exception as e:
                print(f"DynamoDB worker get failed: {e}, using fallback")
                return self._workers.get(worker_id)
        else:
            return self._workers.get(worker_id)

    def get_all_workers(self) -> Dict[str, Dict[str, Any]]:
        """Get all workers"""
        if self._dynamodb and self._workers_table:
            try:
                response = self._workers_table.scan()
                result = {}
                for item in response.get('Items', []):
                    worker_id = item['worker_id']
                    worker_data = {}
                    for key, value in item.items():
                        if key != 'worker_id':
                            try:
                                worker_data[key] = json.loads(value)
                            except (json.JSONDecodeError, TypeError):
                                worker_data[key] = value
                    result[worker_id] = worker_data
                return result
            except Exception as e:
                print(f"DynamoDB workers scan failed: {e}, using fallback")
                return dict(self._workers)
        else:
            return dict(self._workers)

    def delete_worker(self, worker_id: str):
        """Delete worker (soft delete by marking as deleted)"""
        worker = self.get_worker(worker_id)
        if worker:
            worker['status'] = 'DELETED'
            worker['deleted_at'] = int(time.time() * 1000)
            self.upsert_worker(worker_id, worker)

    # Job operations
    def upsert_job(self, job_id: str, info: Dict[str, Any]):
        """Store or update job information"""
        now = int(time.time() * 1000)
        info = dict(info)
        info["updated_at"] = now
        
        if self._dynamodb and self._jobs_table:
            try:
                # Prepare item for DynamoDB
                item = {"job_id": job_id}
                for key, value in info.items():
                    if isinstance(value, list):
                        item[key] = json.dumps(value)
                    elif isinstance(value, dict):
                        item[key] = json.dumps(value)
                    else:
                        item[key] = str(value)
                
                self._jobs_table.put_item(Item=item)
            except Exception as e:
                print(f"DynamoDB job upsert failed: {e}, using fallback")
                self._jobs[job_id] = info
        else:
            self._jobs[job_id] = info

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job information"""
        if self._dynamodb and self._jobs_table:
            try:
                response = self._jobs_table.get_item(Key={"job_id": job_id})
                if 'Item' in response:
                    item = response['Item']
                    result = {}
                    for key, value in item.items():
                        if key == 'job_id':
                            result[key] = value
                        else:
                            try:
                                result[key] = json.loads(value)
                            except (json.JSONDecodeError, TypeError):
                                result[key] = value
                    return result
                return None
            except Exception as e:
                print(f"DynamoDB job get failed: {e}, using fallback")
                return self._jobs.get(job_id)
        else:
            return self._jobs.get(job_id)

    def get_jobs_by_state(self, state: str) -> List[Dict[str, Any]]:
        """Get all jobs in a specific state"""
        all_jobs = []
        
        if self._dynamodb and self._jobs_table:
            try:
                # In production, you'd use a GSI (Global Secondary Index) for efficient querying by state
                response = self._jobs_table.scan(
                    FilterExpression="attribute_exists(#state) AND #state = :state",
                    ExpressionAttributeNames={"#state": "state"},
                    ExpressionAttributeValues={":state": state}
                )
                
                for item in response.get('Items', []):
                    job_data = {}
                    for key, value in item.items():
                        try:
                            job_data[key] = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            job_data[key] = value
                    all_jobs.append(job_data)
                    
            except Exception as e:
                print(f"DynamoDB jobs scan failed: {e}, using fallback")
                all_jobs = [job for job in self._jobs.values() if job.get('state') == state]
        else:
            all_jobs = [job for job in self._jobs.values() if job.get('state') == state]
        
        return all_jobs

    # Task operations
    def upsert_task(self, task_id: str, job_id: str, info: Dict[str, Any]):
        """Store or update task information"""
        now = int(time.time() * 1000)
        info = dict(info)
        info["updated_at"] = now
        
        if self._dynamodb and self._tasks_table:
            try:
                item = {"task_id": task_id, "job_id": job_id}
                for key, value in info.items():
                    if isinstance(value, (list, dict)):
                        item[key] = json.dumps(value)
                    else:
                        item[key] = str(value)
                
                self._tasks_table.put_item(Item=item)
            except Exception as e:
                print(f"DynamoDB task upsert failed: {e}, using fallback")
                self._tasks[f"{task_id}#{job_id}"] = info
        else:
            self._tasks[f"{task_id}#{job_id}"] = info

    def get_task(self, task_id: str, job_id: str) -> Optional[Dict[str, Any]]:
        """Get task information"""
        if self._dynamodb and self._tasks_table:
            try:
                response = self._tasks_table.get_item(
                    Key={"task_id": task_id, "job_id": job_id}
                )
                if 'Item' in response:
                    item = response['Item']
                    result = {}
                    for key, value in item.items():
                        if key in ['task_id', 'job_id']:
                            result[key] = value
                        else:
                            try:
                                result[key] = json.loads(value)
                            except (json.JSONDecodeError, TypeError):
                                result[key] = value
                    return result
                return None
            except Exception as e:
                print(f"DynamoDB task get failed: {e}, using fallback")
                return self._tasks.get(f"{task_id}#{job_id}")
        else:
            return self._tasks.get(f"{task_id}#{job_id}")

    def get_tasks_by_job(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all tasks for a specific job"""
        tasks = []
        
        if self._dynamodb and self._tasks_table:
            try:
                response = self._tasks_table.query(
                    IndexName='job-id-index',  # Would need to create this GSI
                    KeyConditionExpression="job_id = :job_id",
                    ExpressionAttributeValues={":job_id": job_id}
                )
                
                for item in response.get('Items', []):
                    task_data = {}
                    for key, value in item.items():
                        try:
                            task_data[key] = json.loads(value)
                        except (json.JSONDecodeError, TypeError):
                            task_data[key] = value
                    tasks.append(task_data)
                    
            except Exception as e:
                print(f"DynamoDB tasks query failed: {e}, using fallback")
                tasks = [task for key, task in self._tasks.items() if key.endswith(f"#{job_id}")]
        else:
            tasks = [task for key, task in self._tasks.items() if key.endswith(f"#{job_id}")]
        
        return tasks

    def cleanup_old_workers(self, ttl_seconds: int = 300):
        """Clean up workers that haven't sent heartbeats within TTL"""
        cutoff_time = int(time.time() * 1000) - (ttl_seconds * 1000)
        
        all_workers = self.get_all_workers()
        cleaned_count = 0
        
        for worker_id, worker_data in all_workers.items():
            last_heartbeat = int(worker_data.get('last_heartbeat', 0))
            if last_heartbeat < cutoff_time and worker_data.get('status') != 'DELETED':
                print(f"Cleaning up stale worker: {worker_id}")
                self.delete_worker(worker_id)
                cleaned_count += 1
        
        return cleaned_count

    def get_cluster_stats(self) -> Dict[str, Any]:
        """Get cluster statistics"""
        all_workers = self.get_all_workers()
        active_workers = [w for w in all_workers.values() if w.get('status') not in ['DELETED', 'OFFLINE']]
        
        # Get job statistics
        running_jobs = self.get_jobs_by_state('JOB_RUNNING')
        pending_jobs = self.get_jobs_by_state('JOB_PENDING')
        
        return {
            'total_workers': len(all_workers),
            'active_workers': len(active_workers),
            'running_jobs': len(running_jobs),
            'pending_jobs': len(pending_jobs),
            'timestamp': int(time.time() * 1000)
        }
