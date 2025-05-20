#!/usr/bin/env python3
"""
Script to set up daily cron job for CI/CD analytics.
This should be run during deployment or setup.
"""
import os
import sys
from crontab import CronTab
from pathlib import Path

def setup_cron_job():
    """Set up the daily cron job for analytics."""
    try:
        # Get the path to the cron_daily.sh script
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cron_daily.sh')
        
        # Make sure the script is executable
        os.chmod(script_path, 0o755)
        
        # Get the Python path
        python_path = sys.executable
        
        # Set up the cron job to run daily at 9:00 AM
        cron = CronTab(user=True)
        
        # Remove any existing jobs with the same comment
        cron.remove_all(comment='jarvis_ci_analytics')
        
        # Add new job
        job = cron.new(
            command=f'cd {os.path.dirname(script_path)} && {script_path}',
            comment='jarvis_ci_analytics'
        )
        job.hour.on(9)
        job.minute.on(0)
        
        # Write the cron job
        cron.write()
        print("✅ Successfully set up daily analytics cron job at 9:00 AM")
        return True
        
    except Exception as e:
        print(f"❌ Failed to set up cron job: {e}")
        return False

if __name__ == "__main__":
    setup_cron_job()
