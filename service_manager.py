#!/usr/bin/env python3
"""
Background service manager for Bibliome.
Manages firehose ingester and Bluesky automation as background services.
"""

import os
import sys
import time
import signal
import asyncio
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
import psutil
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('service_manager.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ServiceManager:
    """Manages background services for Bibliome."""
    
    def __init__(self, setup_signals=True):
        self.services = {
            'firehose_ingester': {
                'script': 'ingester.py',
                'process': None,
                'restart_count': 0,
                'enabled': True,
                'description': 'AT-Proto firehose monitor'
            },
            'bluesky_automation': {
                'script': 'bluesky_automation.py',
                'process': None,
                'restart_count': 0,
                'enabled': os.getenv('BLUESKY_AUTOMATION_ENABLED', 'false').lower() == 'true',
                'description': 'Bluesky automation service'
            },
            'bibliome_scanner': {
                'script': 'bibliome_scanner.py',
                'process': None,
                'restart_count': 0,
                'enabled': os.getenv('BIBLIOME_SCANNER_ENABLED', 'false').lower() == 'true',
                'description': 'Bibliome network scanner'
            }
        }
        self.running = True
        if setup_signals:
            self.setup_signal_handlers()
        
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, shutting down service manager...")
            self.running = False
            self.stop_all_services()
            sys.exit(0)
        
        signal.signal(signal.SIGTERM, signal_handler)
        signal.signal(signal.SIGINT, signal_handler)
    
    def start_service(self, service_name: str) -> bool:
        """Start a specific service."""
        if service_name not in self.services:
            logger.error(f"Unknown service: {service_name}")
            return False
        
        service = self.services[service_name]
        
        if not service['enabled']:
            logger.info(f"Service {service_name} is disabled, skipping start")
            return False
        
        if service['process'] and service['process'].poll() is None:
            logger.warning(f"Service {service_name} is already running")
            return True
        
        try:
            script_path = Path(__file__).parent / service['script']
            if not script_path.exists():
                logger.error(f"Service script not found: {script_path}")
                return False
            
            # Start the service process
            service['process'] = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=Path(__file__).parent,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0  # Unbuffered
            )
            
            # Give it a moment to start
            time.sleep(2)
            
            if service['process'].poll() is None:
                logger.info(f"Service {service_name} started successfully (PID: {service['process'].pid})")
                return True
            else:
                # Process exited immediately
                stdout, stderr = service['process'].communicate()
                logger.error(f"Service {service_name} failed to start:")
                logger.error(f"STDOUT: {stdout.decode()}")
                logger.error(f"STDERR: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start service {service_name}: {e}")
            return False
    
    def stop_service(self, service_name: str) -> bool:
        """Stop a specific service."""
        if service_name not in self.services:
            logger.error(f"Unknown service: {service_name}")
            return False
        
        service = self.services[service_name]
        
        if not service['process'] or service['process'].poll() is not None:
            logger.info(f"Service {service_name} is not running")
            return True
        
        try:
            # Try graceful shutdown first
            service['process'].terminate()
            
            # Wait up to 10 seconds for graceful shutdown
            try:
                service['process'].wait(timeout=10)
                logger.info(f"Service {service_name} stopped gracefully")
                return True
            except subprocess.TimeoutExpired:
                # Force kill if necessary
                service['process'].kill()
                service['process'].wait()
                logger.warning(f"Service {service_name} force killed")
                return True
                
        except Exception as e:
            logger.error(f"Failed to stop service {service_name}: {e}")
            return False
    
    def restart_service(self, service_name: str) -> bool:
        """Restart a specific service."""
        logger.info(f"Restarting service {service_name}")
        
        if not self.stop_service(service_name):
            logger.error(f"Failed to stop service {service_name} for restart")
            return False
        
        # Increment restart count
        self.services[service_name]['restart_count'] += 1
        
        time.sleep(3)  # Wait before restart
        
        return self.start_service(service_name)
    
    def check_service_health(self, service_name: str) -> Dict[str, any]:
        """Check the health of a service."""
        service = self.services[service_name]
        
        status_info = {
            'name': service_name,
            'enabled': service['enabled'],
            'description': service['description'],
            'restart_count': service['restart_count'],
            'running': False,
            'pid': None,
            'memory_mb': None,
            'cpu_percent': None,
            'uptime_seconds': None,
            'status': 'stopped'
        }
        
        if not service['enabled']:
            status_info['status'] = 'disabled'
            return status_info
        
        if service['process'] and service['process'].poll() is None:
            status_info['running'] = True
            status_info['pid'] = service['process'].pid
            status_info['status'] = 'running'
            
            try:
                # Get process info using psutil
                proc = psutil.Process(service['process'].pid)
                status_info['memory_mb'] = round(proc.memory_info().rss / 1024 / 1024, 2)
                status_info['cpu_percent'] = round(proc.cpu_percent(), 2)
                
                # Calculate uptime
                create_time = proc.create_time()
                uptime_seconds = time.time() - create_time
                status_info['uptime_seconds'] = round(uptime_seconds, 2)
                
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                status_info['status'] = 'failed'
                status_info['running'] = False
        
        return status_info
    
    def start_all_services(self):
        """Start all enabled services."""
        logger.info("Starting all enabled services...")
        
        for service_name in self.services:
            if self.services[service_name]['enabled']:
                self.start_service(service_name)
            else:
                logger.info(f"Skipping disabled service: {service_name}")
    
    def stop_all_services(self):
        """Stop all running services."""
        logger.info("Stopping all services...")
        
        for service_name in self.services:
            self.stop_service(service_name)
    
    def print_status(self):
        """Print status of all services."""
        print("\n" + "="*60)
        print(f"Bibliome Service Manager Status - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        for service_name in self.services:
            status = self.check_service_health(service_name)
            
            print(f"\nService: {status['name']}")
            print(f"  Description: {status['description']}")
            print(f"  Status: {status['status']}")
            print(f"  Enabled: {status['enabled']}")
            
            if status['running']:
                print(f"  PID: {status['pid']}")
                print(f"  Uptime: {status['uptime_seconds']:.1f} seconds")
                print(f"  Memory: {status['memory_mb']} MB")
                print(f"  CPU: {status['cpu_percent']}%")
            
            print(f"  Restart Count: {status['restart_count']}")
        
        print("\n" + "="*60 + "\n")
    
    async def monitor_loop(self):
        """Main monitoring loop."""
        logger.info("Service manager started")
        
        # Start all enabled services
        self.start_all_services()
        
        check_interval = 30  # Check every 30 seconds
        status_interval = 300  # Print status every 5 minutes
        last_status_print = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check and restart failed services
                for service_name in self.services:
                    service = self.services[service_name]
                    
                    if not service['enabled']:
                        continue
                    
                    # Check if process died
                    if service['process'] and service['process'].poll() is not None:
                        # Process has exited
                        exit_code = service['process'].returncode
                        logger.warning(f"Service {service_name} exited with code {exit_code}")
                        
                        # Auto-restart with exponential backoff
                        restart_count = service['restart_count']
                        if restart_count < 5:  # Max 5 restart attempts
                            delay = min(60, 5 * (2 ** restart_count))  # Exponential backoff, max 60s
                            logger.info(f"Restarting {service_name} in {delay} seconds (attempt {restart_count + 1})")
                            await asyncio.sleep(delay)
                            
                            if self.running:  # Check if we're still supposed to run
                                self.restart_service(service_name)
                        else:
                            logger.error(f"Service {service_name} has failed too many times, giving up")
                            service['enabled'] = False
                
                # Print status periodically
                if current_time - last_status_print >= status_interval:
                    self.print_status()
                    last_status_print = current_time
                
                # Read and print logs from services
                for service_name, service in self.services.items():
                    if service['process'] and service['process'].poll() is None:
                        # Non-blocking read from stdout and stderr
                        for line in iter(service['process'].stdout.readline, b''):
                            print(f"[{service_name}] {line.decode().strip()}")
                        for line in iter(service['process'].stderr.readline, b''):
                            print(f"[{service_name}-error] {line.decode().strip()}", file=sys.stderr)

                await asyncio.sleep(check_interval)
                
            except Exception as e:
                logger.error(f"Error in monitor loop: {e}")
                await asyncio.sleep(check_interval)
    
    async def run(self):
        """Run the service manager."""
        try:
            await self.monitor_loop()
        except KeyboardInterrupt:
            logger.info("Service manager interrupted by user")
        finally:
            self.stop_all_services()
            logger.info("Service manager stopped")


def main():
    """Main entry point."""
    if len(sys.argv) > 1:
        command = sys.argv[1].lower()
        manager = ServiceManager()
        
        if command == 'status':
            manager.print_status()
            return
        elif command == 'start':
            if len(sys.argv) > 2:
                service_name = sys.argv[2]
                if manager.start_service(service_name):
                    print(f"Service {service_name} started successfully")
                else:
                    print(f"Failed to start service {service_name}")
                    sys.exit(1)
            else:
                manager.start_all_services()
                print("All enabled services started")
            return
        elif command == 'stop':
            if len(sys.argv) > 2:
                service_name = sys.argv[2]
                if manager.stop_service(service_name):
                    print(f"Service {service_name} stopped successfully")
                else:
                    print(f"Failed to stop service {service_name}")
                    sys.exit(1)
            else:
                manager.stop_all_services()
                print("All services stopped")
            return
        elif command == 'restart':
            if len(sys.argv) > 2:
                service_name = sys.argv[2]
                if manager.restart_service(service_name):
                    print(f"Service {service_name} restarted successfully")
                else:
                    print(f"Failed to restart service {service_name}")
                    sys.exit(1)
            else:
                manager.stop_all_services()
                time.sleep(3)
                manager.start_all_services()
                print("All services restarted")
            return
        else:
            print("Usage: python service_manager.py [status|start|stop|restart] [service_name]")
            sys.exit(1)
    
    # No command provided - run the monitor loop
    manager = ServiceManager()
    asyncio.run(manager.run())


if __name__ == "__main__":
    main()
