import base64, json, sys, time, os
import urllib.request
import argparse
from urllib.error import URLError, HTTPError

MASTER = os.getenv("MASTER", "http://localhost:8080")

def b64(path):
    """Encode file content to base64"""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("ascii")

def post(url, data):
    """Send POST request with JSON data"""
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"),
                                 headers={"Content-Type":"application/json"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read().decode())

def get_text(url):
    """Get text response from URL"""
    with urllib.request.urlopen(url) as resp:
        return resp.read().decode()

def validate_example_structure(example_dir):
    """Validate that example directory has required files"""
    required_files = ["map.py", "reduce.py", "data.txt"]
    missing_files = []
    
    for file in required_files:
        file_path = os.path.join(example_dir, file)
        if not os.path.exists(file_path):
            missing_files.append(file)
    
    if missing_files:
        print(f"Error: Missing required files in {example_dir}:")
        for file in missing_files:
            print(f"   - {file}")
        return False
    
    return True

def submit_mapreduce_job(example_dir, job_id=None, split_size=64, reducers=2):
    """Submit a MapReduce job from an example directory"""
    
    # Validate structure
    if not validate_example_structure(example_dir):
        return False
    
    # Generate job ID if not provided
    if not job_id:
        example_name = os.path.basename(os.path.abspath(example_dir))
        timestamp = int(time.time())
        job_id = f"{example_name}-{timestamp}"
    
    print(f" Submitting MapReduce job: {job_id}")
    print(f" Example directory: {example_dir}")
    
    try:
        # Read scripts
        map_path = os.path.join(example_dir, "map.py")
        reduce_path = os.path.join(example_dir, "reduce.py")
        data_path = os.path.join(example_dir, "data.txt")
        
        print(f"Loading map script: {map_path}")
        map_b64 = b64(map_path)
        
        print(f"Loading reduce script: {reduce_path}")
        reduce_b64 = b64(reduce_path)
        
        print(f"Loading data file: {data_path}")
        with open(data_path, 'r', encoding='utf-8') as f:
            input_text = f.read()
        
        input_text=input_text*1000  # Aumentar tamaño para demo
        
        # Usar split_size fijo para tamaños grandes
        if split_size == 64:  # Si es el default pequeño
            split_size = 2048  # 2KB fijo - bueno para demos
            
        data_size = len(input_text)
        estimated_tasks = data_size // split_size
        
        print(f"Original data size: {len(input_text)//1000} characters")
        print(f"Expanded data size: {data_size} characters (x1000 for demo)")
        print(f"Split size: {split_size} bytes (fixed)")
        print(f"Estimated tasks: ~{estimated_tasks}")
        print(f"Reducers: {reducers}")
        # Create job payload
        job = {
            "job_id": job_id,
            "input_text": input_text,
            "split_size": split_size,
            "reducers": reducers,
            "format": "text",
            "map_script_b64": map_b64,
            "reduce_script_b64": reduce_b64
        }
        
        # Submit job
        print(f"Submitting to master: {MASTER}")
        r = post(f"{MASTER}/api/jobs", job)
        print(f"Job submitted successfully: {r}")
        
        # Monitor job progress
        print(f"\nMonitoring job progress...")
        while True:
            try:
                st = json.loads(get_text(f"{MASTER}/api/jobs/status?job_id={job_id}"))
                status_str = f"Status: {st['state']}"
                if 'maps_completed' in st and 'maps_total' in st:
                    status_str += f" | Maps: {st['maps_completed']}/{st['maps_total']}"
                if 'reduces_completed' in st and 'reduces_total' in st:
                    status_str += f" | Reduces: {st['reduces_completed']}/{st['reduces_total']}"
                
                print(status_str)
                
                if st["state"] in ("SUCCEEDED", "FAILED"):
                    break
                time.sleep(2)
            except Exception as e:
                print(f" Error checking status: {e}")
                break
        
        # Get results
        if st["state"] == "SUCCEEDED":
            print(f"\nJob completed successfully!")
            try:
                result = get_text(f"{MASTER}/api/jobs/result?job_id={job_id}")
                print(f"\nRESULTS:")
                print("=" * 50)
                print(result)
                print("=" * 50)
                return True
            except Exception as e:
                print(f"Error retrieving results: {e}")
                return False
        else:
            print(f"\nJob failed with state: {st['state']}")
            return False
            
    except FileNotFoundError as e:
        print(f"File not found: {e}")
        return False
    except URLError as e:
        print(f"Connection error: {e}")
        print(f"   Make sure the master is running at: {MASTER}")
        return False
    except HTTPError as e:
        print(f"HTTP error: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Submit MapReduce jobs to Poneglyph cluster')
    parser.add_argument('example_dir', help='Path to example directory containing map.py, reduce.py, and data.txt')
    parser.add_argument('--job-id', help='Custom job ID (default: auto-generated)')
    parser.add_argument('--split-size', type=int, default=64, help='Split size in bytes (default: 64)')
    parser.add_argument('--reducers', type=int, default=2, help='Number of reducers (default: 2)')
    parser.add_argument('--master', help='Master URL (default: from MASTER env var or http://localhost:8080)')
    
    args = parser.parse_args()
    
    # Override master URL if provided
    if args.master:
        MASTER = args.master
    
    print(f"Using master: {MASTER}")
    
    success = submit_mapreduce_job(
        example_dir=args.example_dir,
        job_id=args.job_id,
        split_size=args.split_size,
        reducers=args.reducers
    )
    
    if success:
        print(f"\nJob completed successfully!")
        sys.exit(0)
    else:
        print(f"\nJob failed!")
        sys.exit(1)
