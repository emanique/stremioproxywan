"""Discover the Stremio HTTPS identity from the certificate actually served on LAN.

Never treat the unverified SAN as trust. The candidate hostname is separately
verified against the TLS certificate chain with the configured CA.
"""
import ipaddress
import re
import socket
import ssl
import subprocess

DNS_SAN = re.compile(r"DNS:([A-Za-z0-9*.-]+)")
MAX_OUTPUT = 32768


class DiscoveryError(RuntimeError):
    pass


def _resolve_ipv4(host):
    try:
        addresses = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)
    except OSError as exc:
        raise DiscoveryError(f"Cannot resolve Stremio LAN host {host}: {exc}") from exc
    if not addresses:
        raise DiscoveryError(f"No IPv4 address for Stremio LAN host: {host}")
    return addresses[0][4][0]


def _openssl(args, *, data=None):
    try:
        result = subprocess.run(
            ["openssl", *args], input=data, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DiscoveryError(f"OpenSSL failed: {exc}") from exc
    return result


def _san_names(host, port):
    result = _openssl(["s_client", "-connect", f"{host}:{port}", "-showcerts"], data=b"")
    match = re.search(br"-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----", result.stdout, re.S)
    if not match:
        raise DiscoveryError("Stremio LAN endpoint did not present a certificate")
    cert = _openssl(["x509", "-noout", "-ext", "subjectAltName"], data=match.group(0))
    if cert.returncode:
        raise DiscoveryError("Cannot inspect backend certificate SAN")
    return DNS_SAN.findall(cert.stdout.decode("ascii", "replace"))


def candidate_from_sans(ip, sans):
    """Match Stremio wildcard: IP octets hyphenated + wildcard suffix.

    Exact DNS SANs are supported too, but a nonmatching wildcard must not be
    treated as authorization to connect to an arbitrary name.
    """
    ip = str(ipaddress.IPv4Address(ip))
    label = ip.replace(".", "-")
    for entry in sans:
        value = entry.lower().rstrip(".")
        if value.startswith("*.") and re.fullmatch(r"\*\.[a-z0-9.-]+", value):
            return label + value[1:]
    for entry in sans:
        value = entry.lower().rstrip(".")
        if "*" not in value and re.fullmatch(r"[a-z0-9][a-z0-9.-]+", value):
            return value
    raise DiscoveryError("No usable DNS subjectAltName in backend TLS certificate")


def discover_backend(lan_host, port, ca_file):
    """Return (resolved LAN IP, verified backend SNI).

    A DNS name for lan_host may track DHCP changes; a literal IP cannot.
    ssl.create_default_context verifies the chain AND hostname against CA.
    """
    ip = _resolve_ipv4(lan_host)
    san = _san_names(ip, int(port))
    name = candidate_from_sans(ip, san)
    try:
        context = ssl.create_default_context(cafile=ca_file)
        with socket.create_connection((ip, int(port)), timeout=7) as sock:
            with context.wrap_socket(sock, server_hostname=name) as secure:
                secure.do_handshake()
    except (OSError, ssl.SSLError, ValueError) as exc:
        raise DiscoveryError(
            f"Cannot verify Stremio TLS for {ip}:{port}, identity {name}: {exc}"
        ) from exc
    return ip, name
