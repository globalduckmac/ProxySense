"""
Nginx configuration templates and generation utilities.
"""
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class NginxConfig:
    """Nginx configuration generator."""
    
    @staticmethod
    def generate_domain_config(domain: str, upstream_targets: List[Dict[str, Any]], 
                              ssl: bool = False, server_name_aliases: Optional[List[str]] = None) -> str:
        """Generate Nginx configuration for a domain."""
        
        # Prepare upstream configuration
        upstream_name = f"upstream_{domain.replace('.', '_').replace('-', '_')}"
        upstream_config = NginxConfig._generate_upstream(upstream_name, upstream_targets)
        
        # Prepare server names
        server_names = [domain]
        if server_name_aliases:
            server_names.extend(server_name_aliases)
        server_names_str = " ".join(server_names)
        
        if ssl:
            config = NginxConfig._generate_ssl_config(
                domain, server_names_str, upstream_name, upstream_config
            )
        else:
            config = NginxConfig._generate_http_config(
                domain, server_names_str, upstream_name, upstream_config
            )
        
        return config
    
    @staticmethod
    def _generate_upstream(upstream_name: str, targets: List[Dict[str, Any]]) -> str:
        """Generate upstream configuration block."""
        if not targets:
            raise ValueError("At least one upstream target is required")
        
        upstream_config = f"upstream {upstream_name} {{\n"
        upstream_config += "    # Load balancing method: round-robin (default)\n"
        upstream_config += "    # least_conn;  # Uncomment for least connections\n"
        upstream_config += "    # ip_hash;     # Uncomment for session persistence\n\n"
        
        for target in targets:
            host = target.get("host", "localhost")
            port = target.get("port", 80)
            weight = target.get("weight", 1)
            
            if weight > 1:
                upstream_config += f"    server {host}:{port} weight={weight};\n"
            else:
                upstream_config += f"    server {host}:{port};\n"
        
        upstream_config += "}\n\n"
        return upstream_config
    
    @staticmethod
    def _extract_first_upstream_target(upstream_config: str) -> str:
        """Extract the first upstream target for direct proxy_pass."""
        # Parse upstream config to find the first server line
        lines = upstream_config.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('server ') and ':' in line:
                # Extract IP:port from "server IP:PORT;" or "server IP:PORT weight=N;"
                server_part = line.split('server ')[1]
                if ';' in server_part:
                    server_part = server_part.split(';')[0]
                if ' weight=' in server_part:
                    server_part = server_part.split(' weight=')[0]
                return server_part.strip()
        # Fallback to localhost:80 if no upstream found
        return "localhost:80"
    
    @staticmethod
    def _generate_http_config(domain: str, server_names: str, upstream_name: str, upstream_config: str) -> str:
        """Generate HTTP-only configuration."""
        # Extract first upstream target for direct proxy_pass
        upstream_target = NginxConfig._extract_first_upstream_target(upstream_config)
        
        config = f"""server {{
    listen 80;
    listen [::]:80;
    server_name {domain};
    # Важно: не добавляйте здесь default_server, иначе возникнет конфликт с другими конфигурациями

    access_log /var/log/nginx/{domain}.access.log;
    error_log /var/log/nginx/{domain}.error.log;

    # Proxy settings for HTTP traffic
    location / {{
        proxy_pass http://{upstream_target};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        set $conn "";
        if ($http_upgrade = "websocket") {{
            set $conn "upgrade";
        }}
        proxy_set_header Connection $conn;
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }}
    
    # Additional security headers
    # add_header X-Frame-Options "SAMEORIGIN" always;
    # add_header X-Content-Type-Options "nosniff" always;
    # add_header X-XSS-Protection "1; mode=block" always;
    # add_header Referrer-Policy "no-referrer-when-downgrade" always;
    
    # Deny access to hidden files
    location ~ /\\. {{
        deny all;
        access_log off;
        log_not_found off;
    }}
}}
"""
        return config
    
    @staticmethod
    def _generate_ssl_config(domain: str, server_names: str, upstream_name: str, upstream_config: str) -> str:
        """Generate HTTPS configuration with SSL."""
        # Extract first upstream target for direct proxy_pass
        upstream_target = NginxConfig._extract_first_upstream_target(upstream_config)
        
        # Add www.domain.com to server names for SSL config
        domain_with_www = f"{domain} www.{domain}"
        
        config = f"""#############################################
# HTTP для {domain} – проксирование на порт 
#############################################
server {{
    listen 80;
    server_name {domain_with_www};

    location / {{
        proxy_http_version 1.1;
        proxy_pass http://{upstream_target};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;

        # Условно задаём заголовок Connection, используя переменную $conn
        set $conn "";
        if ($http_upgrade = "websocket") {{
            set $conn "upgrade";
        }}
        proxy_set_header Connection $conn;

        proxy_read_timeout 90;
    }}
}}

##########################################################
# HTTPS для {domain} – проксирование на порт 
##########################################################
server {{
    listen 443 ssl;
    server_name {domain_with_www};

    ssl_certificate     /etc/letsencrypt/live/{domain}/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/{domain}/privkey.pem;
    include             /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam         /etc/letsencrypt/ssl-dhparams.pem;

    location / {{
        proxy_http_version 1.1;
        proxy_pass http://{upstream_target};
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header Upgrade $http_upgrade;

        # Условно задаём заголовок Connection, используя переменную $conn
        set $conn "";
        if ($http_upgrade = "websocket") {{
            set $conn "upgrade";
        }}
        proxy_set_header Connection $conn;

        proxy_read_timeout 90;
    }}
}}
"""
        return config
    
    @staticmethod
    def generate_dhparam_command() -> str:
        """Generate command to create DH parameters."""
        return "sudo openssl dhparam -out /etc/nginx/dhparam.pem 2048"
    
    @staticmethod
    def generate_certbot_command(domain: str, email: str) -> str:
        """Generate certbot command for SSL certificate."""
        return f"sudo certbot --nginx -d {domain} --email {email} --agree-tos --non-interactive"
    
    @staticmethod
    def validate_config_command() -> str:
        """Generate command to validate Nginx configuration."""
        return "sudo nginx -t"
    
    @staticmethod
    def reload_command() -> str:
        """Generate command to reload Nginx."""
        return "sudo systemctl reload nginx"
    
    @staticmethod
    def get_config_file_path(domain: str) -> str:
        """Get the configuration file path for a domain."""
        return f"/etc/nginx/sites-available/{domain}.conf"
    
    @staticmethod
    def get_enabled_link_path(domain: str) -> str:
        """Get the enabled symlink path for a domain."""
        return f"/etc/nginx/sites-enabled/{domain}.conf"
    
    @staticmethod
    def generate_enable_site_command(domain: str) -> str:
        """Generate command to enable a site."""
        available_path = NginxConfig.get_config_file_path(domain)
        enabled_path = NginxConfig.get_enabled_link_path(domain)
        return f"sudo ln -sf {available_path} {enabled_path}"
    
    @staticmethod
    def generate_disable_site_command(domain: str) -> str:
        """Generate command to disable a site."""
        enabled_path = NginxConfig.get_enabled_link_path(domain)
        return f"sudo rm -f {enabled_path}"


class NginxDeployment:
    """Nginx deployment utilities."""
    
    @staticmethod
    def get_deployment_steps(domain: str, upstream_targets: List[Dict[str, Any]], 
                            ssl: bool = False, email: str = "") -> List[Dict[str, str]]:
        """Get deployment steps for a domain configuration."""
        steps = []
        
        # Step 1: Generate configuration
        steps.append({
            "name": "Generate Nginx configuration",
            "description": f"Generating Nginx configuration for {domain}",
            "type": "config_generation"
        })
        
        # Step 2: Upload configuration
        steps.append({
            "name": "Upload configuration",
            "description": f"Uploading configuration to {NginxConfig.get_config_file_path(domain)}",
            "type": "file_upload"
        })
        
        # Step 3: Enable site
        steps.append({
            "name": "Enable site",
            "description": f"Creating symlink to enable {domain}",
            "type": "command",
            "command": NginxConfig.generate_enable_site_command(domain)
        })
        
        # Step 4: Validate configuration
        steps.append({
            "name": "Validate configuration",
            "description": "Testing Nginx configuration syntax",
            "type": "command",
            "command": NginxConfig.validate_config_command()
        })
        
        # Step 5: SSL certificate (if needed)
        if ssl:
            if not email:
                raise ValueError("Email is required for SSL certificate generation")
            
            steps.append({
                "name": "Generate DH parameters",
                "description": "Generating Diffie-Hellman parameters for SSL",
                "type": "command",
                "command": NginxConfig.generate_dhparam_command()
            })
            
            steps.append({
                "name": "Obtain SSL certificate",
                "description": f"Obtaining Let's Encrypt certificate for {domain}",
                "type": "command",
                "command": NginxConfig.generate_certbot_command(domain, email)
            })
        
        # Step 6: Reload Nginx
        steps.append({
            "name": "Reload Nginx",
            "description": "Reloading Nginx to apply configuration",
            "type": "command",
            "command": NginxConfig.reload_command()
        })
        
        return steps
