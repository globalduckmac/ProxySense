"""
DNS utilities for domain and nameserver checking.
"""
import asyncio
from typing import List, Tuple, Optional
import dns.resolver
import dns.exception
import logging

from backend.config import settings

logger = logging.getLogger(__name__)


async def resolve_domain(domain: str, record_type: str = "A", 
                        dns_servers: Optional[List[str]] = None,
                        timeout: int = 5) -> Tuple[List[str], Optional[str]]:
    """Resolve a domain to get DNS records."""
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = timeout
        resolver.lifetime = timeout
        
        if dns_servers:
            resolver.nameservers = dns_servers
        
        # Run DNS resolution in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        answers = await loop.run_in_executor(
            None, 
            lambda: resolver.resolve(domain, record_type)
        )
        
        records = [str(answer) for answer in answers]
        return records, None
    
    except dns.resolver.NXDOMAIN:
        return [], "Domain does not exist"
    except dns.resolver.NoAnswer:
        return [], f"No {record_type} records found"
    except dns.resolver.Timeout:
        return [], "DNS query timeout"
    except Exception as e:
        return [], f"DNS resolution error: {str(e)}"


async def get_nameservers(domain: str, dns_servers: Optional[List[str]] = None,
                         timeout: int = 5) -> Tuple[List[str], Optional[str]]:
    """Get nameservers for a domain."""
    ns_records, error = await resolve_domain(
        domain, "NS", dns_servers, timeout
    )
    
    if error:
        return [], error
    
    # Clean up NS records (remove trailing dots)
    nameservers = [ns.rstrip('.') for ns in ns_records]
    return nameservers, None


async def check_domain_ns(domain: str, ns_policy: str,
                         dns_servers: Optional[List[str]] = None,
                         timeout: int = 5) -> Tuple[List[str], bool, Optional[str]]:
    """Check if domain's nameservers match the policy."""
    nameservers, error = await get_nameservers(domain, dns_servers, timeout)
    
    if error:
        return [], False, error
    
    if not nameservers:
        return [], False, "No nameservers found"
    
    # Check if any nameserver contains the policy substring
    policy_match = any(ns_policy.lower() in ns.lower() for ns in nameservers)
    
    if not policy_match:
        error_msg = f"None of the nameservers contain '{ns_policy}'"
        return nameservers, False, error_msg
    
    return nameservers, True, None


async def get_domain_ip(domain: str, dns_servers: Optional[List[str]] = None,
                       timeout: int = 5) -> Tuple[List[str], Optional[str]]:
    """Get A records (IPv4 addresses) for a domain."""
    return await resolve_domain(domain, "A", dns_servers, timeout)


async def verify_domain_points_to_server(domain: str, server_ip: str,
                                        dns_servers: Optional[List[str]] = None,
                                        timeout: int = 5) -> Tuple[bool, str]:
    """Verify that a domain points to a specific server IP."""
    ip_addresses, error = await get_domain_ip(domain, dns_servers, timeout)
    
    if error:
        return False, f"DNS resolution failed: {error}"
    
    if not ip_addresses:
        return False, "No A records found for domain"
    
    if server_ip in ip_addresses:
        return True, f"Domain points to server IP {server_ip}"
    else:
        return False, f"Domain points to {', '.join(ip_addresses)}, not {server_ip}"


async def check_mx_records(domain: str, dns_servers: Optional[List[str]] = None,
                          timeout: int = 5) -> Tuple[List[str], Optional[str]]:
    """Get MX records for a domain."""
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = timeout
        resolver.lifetime = timeout
        
        if dns_servers:
            resolver.nameservers = dns_servers
        
        loop = asyncio.get_event_loop()
        answers = await loop.run_in_executor(
            None,
            lambda: resolver.resolve(domain, "MX")
        )
        
        mx_records = []
        for answer in answers:
            priority = answer.preference
            exchange = str(answer.exchange).rstrip('.')
            mx_records.append(f"{priority} {exchange}")
        
        return mx_records, None
    
    except dns.resolver.NXDOMAIN:
        return [], "Domain does not exist"
    except dns.resolver.NoAnswer:
        return [], "No MX records found"
    except dns.resolver.Timeout:
        return [], "DNS query timeout"
    except Exception as e:
        return [], f"MX query error: {str(e)}"


async def check_txt_records(domain: str, dns_servers: Optional[List[str]] = None,
                           timeout: int = 5) -> Tuple[List[str], Optional[str]]:
    """Get TXT records for a domain."""
    try:
        resolver = dns.resolver.Resolver()
        resolver.timeout = timeout
        resolver.lifetime = timeout
        
        if dns_servers:
            resolver.nameservers = dns_servers
        
        loop = asyncio.get_event_loop()
        answers = await loop.run_in_executor(
            None,
            lambda: resolver.resolve(domain, "TXT")
        )
        
        txt_records = []
        for answer in answers:
            # TXT records can have multiple strings
            record_text = ''.join([text.decode() if isinstance(text, bytes) else str(text) 
                                 for text in answer.strings])
            txt_records.append(record_text)
        
        return txt_records, None
    
    except dns.resolver.NXDOMAIN:
        return [], "Domain does not exist"
    except dns.resolver.NoAnswer:
        return [], "No TXT records found"
    except dns.resolver.Timeout:
        return [], "DNS query timeout"
    except Exception as e:
        return [], f"TXT query error: {str(e)}"


class DNSChecker:
    """DNS checking utilities."""
    
    def __init__(self, dns_servers: Optional[List[str]] = None, timeout: int = 5):
        self.dns_servers = dns_servers or settings.dns_servers_list
        self.timeout = timeout
    
    async def comprehensive_check(self, domain: str) -> dict:
        """Perform comprehensive DNS checks on a domain."""
        results = {
            "domain": domain,
            "a_records": [],
            "aaaa_records": [],
            "ns_records": [],
            "mx_records": [],
            "txt_records": [],
            "errors": {}
        }
        
        # Check A records
        a_records, a_error = await resolve_domain(
            domain, "A", self.dns_servers, self.timeout
        )
        results["a_records"] = a_records
        if a_error:
            results["errors"]["a_records"] = a_error
        
        # Check AAAA records (IPv6)
        aaaa_records, aaaa_error = await resolve_domain(
            domain, "AAAA", self.dns_servers, self.timeout
        )
        results["aaaa_records"] = aaaa_records
        if aaaa_error:
            results["errors"]["aaaa_records"] = aaaa_error
        
        # Check NS records
        ns_records, ns_error = await get_nameservers(
            domain, self.dns_servers, self.timeout
        )
        results["ns_records"] = ns_records
        if ns_error:
            results["errors"]["ns_records"] = ns_error
        
        # Check MX records
        mx_records, mx_error = await check_mx_records(
            domain, self.dns_servers, self.timeout
        )
        results["mx_records"] = mx_records
        if mx_error:
            results["errors"]["mx_records"] = mx_error
        
        # Check TXT records
        txt_records, txt_error = await check_txt_records(
            domain, self.dns_servers, self.timeout
        )
        results["txt_records"] = txt_records
        if txt_error:
            results["errors"]["txt_records"] = txt_error
        
        return results
