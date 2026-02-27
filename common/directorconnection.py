"""
Bareos Director Connection Wrapper

Supports two transport modes (configured via the Setting model):
  1. Unix domain socket  — director.socket_path  (preferred)
  2. TCP/IP              — director.host + director.port  (fallback)

Configuration keys (set via Django admin → Application Settings):
  director.socket_path   str   path to the Unix socket (default: /run/bareos/web.sock)
  director.host          str   hostname / IP for TCP fallback (default: localhost)
  director.port          int   TCP port for TCP fallback (default: 9101)
  director.password      str   bconsole password (used when auth is required)
  director.timeout       int   socket timeout in seconds (default: 30)
"""

import json
import socket
import time
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Default Unix socket path the Bareos Director exposes for Onesimus web
_DEFAULT_SOCKET_PATH = '/run/bareos/web.sock'


class DirectorConnectionError(Exception):
    """Raised when the Director connection fails."""
    pass


class DirectorConnection:
    """
    Wrapper for Bareos Director JSON-RPC communication.

    Transport is selected automatically:
    - If *socket_path* is given (or director.socket_path is set), a
      Unix domain socket is used.
    - Otherwise falls back to TCP (host + port).
    """

    def __init__(
        self,
        socket_path: Optional[str] = None,
        host: Optional[str] = None,
        port: int = 9101,
        password: str = '',
        timeout: int = 30,
    ):
        """
        Args:
            socket_path: Path to the Unix domain socket (takes priority over TCP).
            host:        Director hostname/IP (used only when socket_path is None).
            port:        Director TCP port (used only when socket_path is None).
            password:    bconsole password (sent during auth handshake if required).
            timeout:     Socket timeout in seconds.
        """
        self.socket_path = socket_path
        self.host = host or 'localhost'
        self.port = port
        self.password = password
        self.timeout = timeout

        self._socket: Optional[socket.socket] = None
        self.connected: bool = False
        self.authenticated: bool = False

    # ── Connection lifecycle ───────────────────────────────────────────

    @property
    def transport_label(self) -> str:
        """Human-readable description of the active transport."""
        if self.socket_path:
            return f'unix:{self.socket_path}'
        return f'tcp:{self.host}:{self.port}'

    def connect(self) -> bool:
        """
        Open the socket connection.

        Returns True on success, False on failure (error is logged).
        """
        try:
            if self.socket_path:
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect(self.socket_path)
                logger.info('Connected to Director via Unix socket %s', self.socket_path)
            else:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(self.timeout)
                sock.connect((self.host, self.port))
                logger.info('Connected to Director via TCP %s:%s', self.host, self.port)

            self._socket = sock
            self.connected = True
            return True

        except (socket.error, OSError) as exc:
            logger.error('Failed to connect to Director (%s): %s', self.transport_label, exc)
            self.connected = False
            return False

    def disconnect(self):
        """Close the socket and reset state."""
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
            self._socket = None
        self.connected = False
        self.authenticated = False

    def reconnect(self) -> bool:
        """Disconnect and re-connect."""
        self.disconnect()
        return self.connect()

    # ── Low-level I/O ──────────────────────────────────────────────────

    def send_command(self, command: str) -> Optional[Dict[str, Any]]:
        """
        Send a single Bareos console command and return the parsed JSON response.

        Returns None on error (error is logged).
        """
        if not self.connected or self._socket is None:
            raise DirectorConnectionError('Not connected to Director')

        try:
            self._socket.sendall(command.encode('utf-8') + b'\n')

            chunks = []
            while True:
                try:
                    chunk = self._socket.recv(4096)
                    if not chunk:
                        break
                    chunks.append(chunk)
                except socket.timeout:
                    break

            raw = b''.join(chunks)
            if raw:
                try:
                    return json.loads(raw.decode('utf-8', errors='replace'))
                except json.JSONDecodeError as exc:
                    logger.error('Failed to parse Director JSON response: %s', exc)
                    return None
            return None

        except (socket.error, OSError) as exc:
            logger.error('Socket error during send_command: %s', exc)
            self.connected = False
            return None

    # ── High-level commands ────────────────────────────────────────────

    def test_connection(self) -> bool:
        """Ping the Director with a lightweight command. Returns True if alive."""
        try:
            resp = self.send_command('status dir')
            return resp is not None
        except DirectorConnectionError:
            return False

    def list_jobs(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        resp = self.send_command(f'llist jobs limit={limit} offset={offset}')
        return resp.get('jobs', []) if isinstance(resp, dict) else []

    def list_clients(self) -> List[Dict[str, Any]]:
        resp = self.send_command('llist clients')
        return resp.get('clients', []) if isinstance(resp, dict) else []

    def list_schedules(self) -> List[Dict[str, Any]]:
        resp = self.send_command('llist schedules')
        return resp.get('schedules', []) if isinstance(resp, dict) else []

    def list_pools(self) -> List[Dict[str, Any]]:
        resp = self.send_command('llist pools')
        return resp.get('pools', []) if isinstance(resp, dict) else []

    def get_job_details(self, job_id: int) -> Optional[Dict[str, Any]]:
        resp = self.send_command(f'llist jobid={job_id}')
        if isinstance(resp, dict):
            jobs = resp.get('jobs', [])
            return jobs[0] if jobs else None
        return None

    def get_client_status(self, client_name: str) -> Optional[Dict[str, Any]]:
        return self.send_command(f'status client="{client_name}"')

    def run_job(self, job_name: str, client: str = '', priority: int = 10,
                now: bool = True) -> Optional[int]:
        cmd = f'run job="{job_name}" priority={priority}'
        if client:
            cmd += f' client="{client}"'
        if now:
            cmd += ' yes'
        resp = self.send_command(cmd)
        return resp.get('jobid') if isinstance(resp, dict) else None

    def cancel_job(self, job_id: int) -> bool:
        return self.send_command(f'cancel jobid={job_id}') is not None

    def reload(self) -> bool:
        return self.send_command('reload') is not None

    def restore(self, client_name: str, job_id: int, where: str = '/',
                replace_mode: str = 'always') -> bool:
        cmd = f'restore client="{client_name}" jobid={job_id} where="{where}"'
        return self.send_command(cmd) is not None

    def bvfs_update(self, job_id: int) -> bool:
        return self.send_command(f'bvfs_update jobid={job_id}') is not None

    def bvfs_list_dirs(self, path_id: int = 1) -> List[Dict[str, Any]]:
        resp = self.send_command(f'bvfs_lsdirs pathid={path_id}')
        return resp.get('directories', []) if isinstance(resp, dict) else []

    def bvfs_list_files(self, path_id: int = 1) -> List[Dict[str, Any]]:
        resp = self.send_command(f'bvfs_lsfiles pathid={path_id}')
        return resp.get('files', []) if isinstance(resp, dict) else []


# ── Global connection factory ──────────────────────────────────────────────

_director_instance: Optional[DirectorConnection] = None


def build_director_connection() -> DirectorConnection:
    """
    Create a DirectorConnection from the database Setting model.

    Reads:
      director.socket_path  → Unix socket (takes priority)
      director.host         → TCP host fallback
      director.port         → TCP port fallback
      director.password     → password
      director.timeout      → timeout
    """
    # Import here to avoid circular imports at module load time
    from .models import Setting

    socket_path = Setting.get('director.socket_path', default=_DEFAULT_SOCKET_PATH)
    host        = Setting.get('director.host',        default='localhost')
    port        = int(Setting.get('director.port',    default=9101))
    password    = Setting.get('director.password',    default='')
    timeout     = int(Setting.get('director.timeout', default=30))

    return DirectorConnection(
        socket_path=socket_path,
        host=host,
        port=port,
        password=password,
        timeout=timeout,
    )


def get_director_connection() -> DirectorConnection:
    """
    Return the global DirectorConnection, creating and connecting it if needed.

    Raises DirectorConnectionError if the connection cannot be established.
    """
    global _director_instance

    if _director_instance is not None and _director_instance.connected:
        return _director_instance

    _director_instance = build_director_connection()
    if not _director_instance.connect():
        raise DirectorConnectionError(
            f'Failed to connect to Director via {_director_instance.transport_label}'
        )
    return _director_instance


def close_director_connection():
    """Close and discard the global Director connection."""
    global _director_instance
    if _director_instance:
        _director_instance.disconnect()
        _director_instance = None
