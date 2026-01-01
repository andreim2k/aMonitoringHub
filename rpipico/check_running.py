"""
Check what's currently running on the Pico
"""
import sys
import json
import time

print(json.dumps({"status": "running_check"}))

# Get list of modules
print(json.dumps({"loaded_modules": list(sys.modules.keys())}))

# Try to check memory
try:
    import gc
    gc.collect()
    mem_free = gc.mem_free()
    mem_alloc = gc.mem_alloc()
    print(json.dumps({
        "memory": {
            "free": mem_free,
            "allocated": mem_alloc,
            "total": mem_free + mem_alloc
        }
    }))
except:
    pass

print(json.dumps({"status": "check_complete"}))
