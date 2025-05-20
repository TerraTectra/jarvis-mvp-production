import os
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import re
from collections import defaultdict

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('ci_analytics')

# Constants
DATA_DIR = Path(__file__).parent / 'data'
ANALYTICS_FILE = DATA_DIR / 'analytics.json'
LOG_DIR = Path(__file__).parent / 'logs'
PIPELINE_LOGS = LOG_DIR / 'pipeline_events.log'

# Ensure directories exist
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Common error patterns to track
ERROR_PATTERNS = [
    (r'error', 'Error'),
    (r'fail', 'Failure'),
    (r'timeout', 'Timeout'),
    (r'critical', 'Critical'),
    (r'exception', 'Exception'),
    (r'warning', 'Warning')
]

class PipelineAnalytics:
    def __init__(self):
        self.analytics = self._load_analytics()
        self._ensure_default_structure()
    
    def _ensure_default_structure(self):
        """Ensure the analytics data structure is properly initialized."""
        if 'pipeline_runs' not in self.analytics:
            self.analytics['pipeline_runs'] = []
        if 'error_stats' not in self.analytics:
            self.analytics['error_stats'] = {}
        if 'metrics' not in self.analytics:
            self.analytics['metrics'] = {
                'total_runs': 0,
                'successful_runs': 0,
                'failed_runs': 0,
                'avg_duration': 0,
                'total_duration': 0,
                'runs_by_day': {},
                'error_counts': {}
            }
    
    def _load_analytics(self) -> dict:
        """Load analytics data from JSON file."""
        try:
            if ANALYTICS_FILE.exists():
                with open(ANALYTICS_FILE, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load analytics: {e}")
        return {}
    
    def save_analytics(self):
        """Save analytics data to JSON file."""
        try:
            with open(ANALYTICS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.analytics, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save analytics: {e}")
    
    def process_pipeline_run(self, pipeline_data: dict):
        """Process a new pipeline run and update analytics."""
        try:
            # Add timestamp if not present
            if 'timestamp' not in pipeline_data:
                pipeline_data['timestamp'] = datetime.utcnow().isoformat()
            
            # Calculate duration if start and end times are available
            if 'start_time' in pipeline_data and 'end_time' in pipeline_data:
                start = datetime.fromisoformat(pipeline_data['start_time'])
                end = datetime.fromisoformat(pipeline_data['end_time'])
                duration = (end - start).total_seconds()
                pipeline_data['duration_seconds'] = duration
                
                # Update metrics
                self.analytics['metrics']['total_runs'] += 1
                if pipeline_data.get('status') == 'success':
                    self.analytics['metrics']['successful_runs'] += 1
                else:
                    self.analytics['metrics']['failed_runs'] += 1
                
                # Update duration metrics
                total_duration = self.analytics['metrics'].get('total_duration', 0) + duration
                self.analytics['metrics']['total_duration'] = total_duration
                self.analytics['metrics']['avg_duration'] = total_duration / self.analytics['metrics']['total_runs']
                
                # Update runs by day
                date_str = start.strftime('%Y-%m-%d')
                if date_str not in self.analytics['metrics']['runs_by_day']:
                    self.analytics['metrics']['runs_by_day'][date_str] = 0
                self.analytics['metrics']['runs_by_day'][date_str] += 1
            
            # Process errors if any
            if 'logs' in pipeline_data:
                self._process_errors(pipeline_data['logs'])
            
            # Add to pipeline runs (keep last 1000 runs)
            self.analytics['pipeline_runs'].append(pipeline_data)
            self.analytics['pipeline_runs'] = self.analytics['pipeline_runs'][-1000:]
            
            # Save analytics
            self.save_analytics()
            return True
        except Exception as e:
            logger.error(f"Error processing pipeline run: {e}")
            return False
    
    def _process_errors(self, logs: str):
        """Process logs to extract and count error patterns."""
        if 'error_stats' not in self.analytics:
            self.analytics['error_stats'] = {}
        
        for pattern, error_type in ERROR_PATTERNS:
            count = len(re.findall(pattern, logs, re.IGNORECASE))
            if count > 0:
                if error_type not in self.analytics['error_stats']:
                    self.analytics['error_stats'][error_type] = 0
                self.analytics['error_stats'][error_type] += count
    
    def get_daily_report(self) -> dict:
        """Generate a daily report of pipeline metrics."""
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        
        # Filter runs from the last 24 hours
        recent_runs = [
            run for run in self.analytics.get('pipeline_runs', [])
            if datetime.fromisoformat(run['timestamp']) >= yesterday
        ]
        
        # Calculate metrics
        successful = sum(1 for run in recent_runs if run.get('status') == 'success')
        failed = len(recent_runs) - successful
        avg_duration = sum(
            run.get('duration_seconds', 0) for run in recent_runs
        ) / len(recent_runs) if recent_runs else 0
        
        # Get top errors
        top_errors = sorted(
            self.analytics.get('error_stats', {}).items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return {
            'date': now.strftime('%Y-%m-%d'),
            'total_runs': len(recent_runs),
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / len(recent_runs)) * 100 if recent_runs else 0,
            'avg_duration_seconds': round(avg_duration, 2),
            'top_errors': dict(top_errors)
        }
    
    def get_weekly_report(self) -> dict:
        """Generate a weekly report of pipeline metrics."""
        now = datetime.utcnow()
        week_ago = now - timedelta(days=7)
        
        # Filter runs from the last 7 days
        recent_runs = [
            run for run in self.analytics.get('pipeline_runs', [])
            if datetime.fromisoformat(run['timestamp']) >= week_ago
        ]
        
        # Group by day
        runs_by_day = defaultdict(list)
        for run in recent_runs:
            day = datetime.fromisoformat(run['timestamp']).strftime('%Y-%m-%d')
            runs_by_day[day].append(run)
        
        # Calculate metrics
        successful = sum(1 for run in recent_runs if run.get('status') == 'success')
        failed = len(recent_runs) - successful
        avg_duration = sum(
            run.get('duration_seconds', 0) for run in recent_runs
        ) / len(recent_runs) if recent_runs else 0
        
        # Get daily metrics
        daily_metrics = {}
        for day, runs in runs_by_day.items():
            day_success = sum(1 for r in runs if r.get('status') == 'success')
            day_failed = len(runs) - day_success
            daily_metrics[day] = {
                'total': len(runs),
                'successful': day_success,
                'failed': day_failed,
                'success_rate': (day_success / len(runs)) * 100 if runs else 0
            }
        
        # Get top errors
        top_errors = sorted(
            self.analytics.get('error_stats', {}).items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        return {
            'start_date': week_ago.strftime('%Y-%m-%d'),
            'end_date': now.strftime('%Y-%m-%d'),
            'total_runs': len(recent_runs),
            'successful': successful,
            'failed': failed,
            'success_rate': (successful / len(recent_runs)) * 100 if recent_runs else 0,
            'avg_duration_seconds': round(avg_duration, 2),
            'daily_metrics': daily_metrics,
            'top_errors': dict(top_errors)
        }

# Singleton instance
analytics = PipelineAnalytics()

def generate_daily_report() -> dict:
    """Generate and return a daily report."""
    return analytics.get_daily_report()

def generate_weekly_report() -> dict:
    """Generate and return a weekly report."""
    return analytics.get_weekly_report()

def update_analytics(pipeline_data: dict) -> bool:
    """Update analytics with new pipeline data."""
    return analytics.process_pipeline_run(pipeline_data)

if __name__ == "__main__":
    # Example usage
    sample_run = {
        'pipeline_id': 'test_123',
        'status': 'success',
        'start_time': (datetime.utcnow() - timedelta(minutes=5)).isoformat(),
        'end_time': datetime.utcnow().isoformat(),
        'logs': 'Some error occurred here. This is a test warning.'
    }
    
    update_analytics(sample_run)
    print("Daily Report:", json.dumps(generate_daily_report(), indent=2))
    print("\nWeekly Report:", json.dumps(generate_weekly_report(), indent=2))
