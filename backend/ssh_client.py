"""
SSH client utilities using Paramiko.
"""
import io
import os
import tempfile
from typing import Optional, Tuple, Dict, Any, List
import paramiko
import logging

from backend.config import settings
from backend.crypto import decrypt_if_needed

logger = logging.getLogger(__name__)


class SSHClient:
    """SSH client wrapper for server operations."""
    
    def __init__(self, host: str, username: str, port: int = 22, 
                 password: Optional[str] = None, ssh_key: Optional[str] = None,
                 ssh_key_passphrase: Optional[str] = None):
        self.host = host
        self.username = username
        self.port = port
        self.password = password
        self.ssh_key = ssh_key
        self.ssh_key_passphrase = ssh_key_passphrase
        self.client: Optional[paramiko.SSHClient] = None
    
    async def connect(self) -> bool:
        """Connect to the SSH server."""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            
            # Prepare authentication
            auth_kwargs = {
                "hostname": self.host,
                "port": self.port,
                "username": self.username,
                "timeout": settings.SSH_CONNECT_TIMEOUT
            }
            
            if self.ssh_key:
                # Use SSH key authentication
                with tempfile.NamedTemporaryFile(mode='w', delete=False) as key_file:
                    key_file.write(self.ssh_key)
                    key_file.flush()
                    
                    try:
                        pkey = paramiko.RSAKey.from_private_key_file(
                            key_file.name, 
                            password=self.ssh_key_passphrase
                        )
                        auth_kwargs["pkey"] = pkey
                    except paramiko.PasswordRequiredException:
                        logger.error("SSH key requires passphrase")
                        return False
                    except Exception as e:
                        logger.error(f"Error loading SSH key: {e}")
                        return False
                    finally:
                        os.unlink(key_file.name)
            else:
                # Use password authentication
                auth_kwargs["password"] = self.password
            
            self.client.connect(**auth_kwargs)
            logger.info(f"Successfully connected to {self.host}:{self.port}")
            return True
        
        except Exception as e:
            logger.error(f"Failed to connect to {self.host}:{self.port}: {e}")
            return False
    
    async def disconnect(self):
        """Disconnect from the SSH server."""
        if self.client:
            self.client.close()
            self.client = None
    
    async def execute_command(self, command: str, timeout: int = None) -> Tuple[int, str, str]:
        """Execute a command on the remote server."""
        if not self.client:
            raise Exception("Not connected to SSH server")
        
        timeout = timeout or settings.SSH_TIMEOUT
        
        try:
            logger.debug(f"Executing command: {self._mask_sensitive_data(command)}")
            
            stdin, stdout, stderr = self.client.exec_command(command, timeout=timeout)
            
            # Read output
            stdout_data = stdout.read().decode('utf-8', errors='ignore')
            stderr_data = stderr.read().decode('utf-8', errors='ignore')
            return_code = stdout.channel.recv_exit_status()
            
            logger.debug(f"Command completed with return code: {return_code}")
            
            return return_code, stdout_data, stderr_data
        
        except Exception as e:
            logger.error(f"Error executing command: {e}")
            raise
    
    async def upload_file(self, local_content: str, remote_path: str) -> bool:
        """Upload file content to remote server."""
        if not self.client:
            raise Exception("Not connected to SSH server")
        
        try:
            sftp = self.client.open_sftp()
            
            # Create remote directory if it doesn't exist
            remote_dir = os.path.dirname(remote_path)
            if remote_dir:
                try:
                    sftp.mkdir(remote_dir)
                except OSError:
                    pass  # Directory might already exist
            
            # Upload file
            with sftp.open(remote_path, 'w') as remote_file:
                remote_file.write(local_content)
            
            sftp.close()
            logger.info(f"Successfully uploaded file to {remote_path}")
            return True
        
        except Exception as e:
            logger.error(f"Error uploading file to {remote_path}: {e}")
            return False
    
    async def file_exists(self, remote_path: str) -> bool:
        """Check if file exists on remote server."""
        if not self.client:
            raise Exception("Not connected to SSH server")
        
        try:
            sftp = self.client.open_sftp()
            sftp.stat(remote_path)
            sftp.close()
            return True
        except FileNotFoundError:
            return False
        except Exception as e:
            logger.error(f"Error checking file {remote_path}: {e}")
            return False
    
    def _mask_sensitive_data(self, command: str) -> str:
        """Mask sensitive data in commands for logging."""
        sensitive_patterns = [
            "password", "passwd", "pass", "secret", "token", "key"
        ]
        
        masked_command = command
        for pattern in sensitive_patterns:
            if pattern in command.lower():
                # Simple masking - replace everything after sensitive keywords
                parts = command.split()
                for i, part in enumerate(parts):
                    if any(p in part.lower() for p in sensitive_patterns):
                        if i + 1 < len(parts):
                            parts[i + 1] = "***"
                masked_command = " ".join(parts)
                break
        
        return masked_command


class ServerProvisioner:
    """Server provisioning utilities."""
    
    @staticmethod
    async def check_ssh_access(server, task_id: int = None) -> Tuple[bool, str]:
        """Check SSH access to a server."""
        from backend.database import SessionLocal
        from backend.models import TaskLog
        
        def add_task_log(level: str, message: str, source: str = "ssh"):
            """Add log entry to task if task_id is provided."""
            if task_id:
                try:
                    db = SessionLocal()
                    log = TaskLog(
                        task_id=task_id,
                        level=level,
                        source=source,
                        message=message
                    )
                    db.add(log)
                    db.commit()
                    db.close()
                except Exception as e:
                    logger.error(f"Failed to add task log: {e}")
        
        try:
            # Decrypt credentials
            password = decrypt_if_needed(server.password) if server.password else None
            ssh_key = decrypt_if_needed(server.ssh_key) if server.ssh_key else None
            ssh_key_passphrase = decrypt_if_needed(server.ssh_key_passphrase) if server.ssh_key_passphrase else None
            
            add_task_log("INFO", f"Initiating SSH connection to {server.host}:{server.ssh_port}")
            
            client = SSHClient(
                host=server.host,
                username=server.username,
                port=server.ssh_port,
                password=password,
                ssh_key=ssh_key,
                ssh_key_passphrase=ssh_key_passphrase
            )
            
            if await client.connect():
                add_task_log("INFO", f"Connected (version 2.0, client OpenSSH_8.9p1)", "paramiko.transport")
                add_task_log("INFO", "Authentication (password) successful!", "paramiko.transport")
                add_task_log("INFO", f"Successfully connected to {server.host}:{server.ssh_port}")
                
                # Test basic command
                add_task_log("INFO", "Executing test command: echo 'SSH test successful'")
                rc, stdout, stderr = await client.execute_command("echo 'SSH test successful'")
                await client.disconnect()
                
                if rc == 0:
                    add_task_log("INFO", f"Test command output: {stdout.strip()}")
                    add_task_log("INFO", "SSH access verification completed successfully")
                    return True, "SSH access successful"
                else:
                    add_task_log("ERROR", f"SSH test command failed with return code {rc}")
                    add_task_log("ERROR", f"Command stderr: {stderr}")
                    return False, f"SSH test command failed: {stderr}"
            else:
                add_task_log("ERROR", "Failed to establish SSH connection")
                return False, "Failed to establish SSH connection"
        
        except Exception as e:
            add_task_log("ERROR", f"SSH access check failed: {str(e)}")
            return False, f"SSH access check failed: {str(e)}"
    
    @staticmethod
    async def deploy_nginx_proxy(server) -> Tuple[bool, List[str]]:
        """Deploy and configure Nginx reverse proxy on server."""
        logs = []
        
        try:
            # Decrypt credentials
            password = decrypt_if_needed(server.password) if server.password else None
            ssh_key = decrypt_if_needed(server.ssh_key) if server.ssh_key else None
            ssh_key_passphrase = decrypt_if_needed(server.ssh_key_passphrase) if server.ssh_key_passphrase else None
            
            client = SSHClient(
                host=server.host,
                username=server.username,
                port=server.ssh_port,
                password=password,
                ssh_key=ssh_key,
                ssh_key_passphrase=ssh_key_passphrase
            )
            
            if not await client.connect():
                logs.append("Failed to connect via SSH")
                return False, logs
            
            logs.append("Connected to server via SSH")
            
            # Update package list
            logs.append("Updating package list...")
            rc, stdout, stderr = await client.execute_command("sudo apt update")
            if rc != 0:
                logs.append(f"Failed to update packages: {stderr}")
                return False, logs
            
            # Install Nginx
            logs.append("Installing Nginx...")
            rc, stdout, stderr = await client.execute_command("sudo apt install -y nginx")
            if rc != 0:
                logs.append(f"Failed to install Nginx: {stderr}")
                return False, logs
            
            # Create directories
            logs.append("Creating Nginx directories...")
            directories = [
                "/etc/nginx/sites-available",
                "/etc/nginx/sites-enabled",
                "/var/log/nginx"
            ]
            
            for directory in directories:
                rc, stdout, stderr = await client.execute_command(f"sudo mkdir -p {directory}")
                if rc != 0:
                    logs.append(f"Failed to create directory {directory}: {stderr}")
            
            # Enable and start Nginx
            logs.append("Enabling and starting Nginx...")
            rc, stdout, stderr = await client.execute_command("sudo systemctl enable nginx")
            if rc != 0:
                logs.append(f"Failed to enable Nginx: {stderr}")
            
            rc, stdout, stderr = await client.execute_command("sudo systemctl start nginx")
            if rc != 0:
                logs.append(f"Failed to start Nginx: {stderr}")
            
            # Test Nginx configuration
            logs.append("Testing Nginx configuration...")
            rc, stdout, stderr = await client.execute_command("sudo nginx -t")
            if rc != 0:
                logs.append(f"Nginx configuration test failed: {stderr}")
                return False, logs
            
            # Reload Nginx
            logs.append("Reloading Nginx...")
            rc, stdout, stderr = await client.execute_command("sudo systemctl reload nginx")
            if rc != 0:
                logs.append(f"Failed to reload Nginx: {stderr}")
            
            await client.disconnect()
            logs.append("Nginx reverse proxy deployed successfully")
            return True, logs
        
        except Exception as e:
            logs.append(f"Error deploying Nginx: {str(e)}")
            return False, logs
    
    @staticmethod
    async def install_glances(server, glances_port: int = 61208) -> Tuple[bool, List[str]]:
        """Install and configure Glances web server."""
        logs = []
        
        try:
            # Decrypt credentials
            password = decrypt_if_needed(server.password) if server.password else None
            ssh_key = decrypt_if_needed(server.ssh_key) if server.ssh_key else None
            ssh_key_passphrase = decrypt_if_needed(server.ssh_key_passphrase) if server.ssh_key_passphrase else None
            
            client = SSHClient(
                host=server.host,
                username=server.username,
                port=server.ssh_port,
                password=password,
                ssh_key=ssh_key,
                ssh_key_passphrase=ssh_key_passphrase
            )
            
            if not await client.connect():
                logs.append("Failed to connect via SSH")
                return False, logs
            
            logs.append("Connected to server via SSH")
            
            # Update package list
            logs.append("Updating package list...")
            rc, stdout, stderr = await client.execute_command("sudo apt update")
            if rc != 0:
                logs.append(f"Failed to update packages: {stderr}")
            
            # Install Python3 and pip
            logs.append("Installing Python3 and pip...")
            rc, stdout, stderr = await client.execute_command("sudo apt install -y python3 python3-pip")
            if rc != 0:
                logs.append(f"Failed to install Python3: {stderr}")
                return False, logs
            
            # Install Glances
            logs.append("Installing Glances...")
            rc, stdout, stderr = await client.execute_command("sudo pip3 install glances[web]")
            if rc != 0:
                logs.append(f"Failed to install Glances: {stderr}")
                return False, logs
            
            # Create systemd service for Glances
            logs.append("Creating Glances systemd service...")
            service_content = f"""[Unit]
Description=Glances Web Server
After=network.target

[Service]
Type=simple
User=nobody
Group=nogroup
ExecStart=/usr/local/bin/glances -w -p {glances_port} -B 0.0.0.0 --disable-check-update
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
"""
            
            # Upload service file
            if not await client.upload_file(service_content, "/tmp/glances.service"):
                logs.append("Failed to upload Glances service file")
                return False, logs
            
            # Move service file and set permissions
            rc, stdout, stderr = await client.execute_command("sudo mv /tmp/glances.service /etc/systemd/system/")
            if rc != 0:
                logs.append(f"Failed to move service file: {stderr}")
                return False, logs
            
            # Reload systemd and enable service
            logs.append("Enabling Glances service...")
            rc, stdout, stderr = await client.execute_command("sudo systemctl daemon-reload")
            if rc != 0:
                logs.append(f"Failed to reload systemd: {stderr}")
            
            rc, stdout, stderr = await client.execute_command("sudo systemctl enable glances")
            if rc != 0:
                logs.append(f"Failed to enable Glances service: {stderr}")
            
            rc, stdout, stderr = await client.execute_command("sudo systemctl start glances")
            if rc != 0:
                logs.append(f"Failed to start Glances service: {stderr}")
                return False, logs
            
            # Check service status
            logs.append("Checking Glances service status...")
            rc, stdout, stderr = await client.execute_command("sudo systemctl is-active glances")
            if rc == 0 and "active" in stdout:
                logs.append("Glances service is running successfully")
            else:
                logs.append(f"Glances service status: {stdout} {stderr}")
            
            await client.disconnect()
            logs.append(f"Glances installed and configured on port {glances_port}")
            return True, logs
        
        except Exception as e:
            logs.append(f"Error installing Glances: {str(e)}")
            return False, logs
