"""Analytics Hub for tracking module performance."""

from typing import Dict, Any, List
from datetime import datetime
import json
import os


class AnalyticsHub:
    """Central analytics and metrics tracking."""
    
    def __init__(self, log_file: str = 'analytics.jsonl'):
        self.log_file = log_file
        self.session_data = []
        
    def log(self, module_name: str, metrics: Dict[str, Any]):
        """Log module execution metrics."""
        record = {
            'timestamp': datetime.now().isoformat(),
            'module': module_name,
            **metrics
        }
        
        # Add to session
        self.session_data.append(record)
        
        # Append to file
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(record) + '\n')
    
    def get_performance(self, module_name: str = None, window_hours: int = 24) -> Dict[str, Any]:
        """Get performance metrics for a module."""
        if not os.path.exists(self.log_file):
            return {}
        
        # Load recent data
        from datetime import timedelta
        cutoff = datetime.now() - timedelta(hours=window_hours)
        
        data = []
        with open(self.log_file, 'r') as f:
            for line in f:
                record = json.loads(line.strip())
                record_time = datetime.fromisoformat(record['timestamp'])
                if record_time >= cutoff:
                    if module_name is None or record['module'] == module_name:
                        data.append(record)
        
        if not data:
            return {}
        
        # Compute aggregates
        successes = [r for r in data if r.get('success', False)]
        latencies = [r['latency'] for r in data if 'latency' in r]
        
        return {
            'total_runs': len(data),
            'success_count': len(successes),
            'success_rate': len(successes) / len(data) if data else 0,
            'avg_latency': sum(latencies) / len(latencies) if latencies else 0,
            'max_latency': max(latencies) if latencies else 0,
            'min_latency': min(latencies) if latencies else 0
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get stats for all modules."""
        if not os.path.exists(self.log_file):
            return {}
        
        # Get unique modules
        modules = set()
        with open(self.log_file, 'r') as f:
            for line in f:
                record = json.loads(line.strip())
                modules.add(record['module'])
        
        # Get stats for each
        return {mod: self.get_performance(mod) for mod in modules}
