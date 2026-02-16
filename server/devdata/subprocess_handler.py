"""PostgreSQL backup and restore subprocess handler.

Provides async execution of pg_dump and pg_restore commands with progress tracking.
"""

import asyncio
import gzip
import hashlib
import inspect
import os
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional, Tuple
from urllib.parse import urlparse

from server.logging_config import get_logger

logger = get_logger(name=__name__)


@dataclass
class SubprocessResult:
    """Result from subprocess execution."""
    success: bool
    return_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    output_file: Optional[Path] = None
    file_size: Optional[int] = None


class PostgresBackupHandler:
    """Handler for PostgreSQL backup and restore operations."""

    def __init__(self, postgres_url: str):
        """Initialize with PostgreSQL connection URL.

        Args:
            postgres_url: PostgreSQL connection URL (postgresql+asyncpg://...)
        """
        self.postgres_url = postgres_url
        self._tool_cache: dict[str, str] = {}
        self._parse_connection_params()

    def _parse_connection_params(self) -> None:
        """Parse connection parameters from URL."""
        # Remove the +asyncpg part for pg_dump/pg_restore
        url = self.postgres_url.replace('+asyncpg', '')
        parsed = urlparse(url)

        self.host = parsed.hostname or 'localhost'
        self.port = parsed.port or 5432
        self.database = parsed.path.lstrip('/') if parsed.path else 'postgres'
        self.username = parsed.username
        self.password = parsed.password

    def _get_env(self) -> dict:
        """Get environment variables for subprocess."""
        env = os.environ.copy()
        if self.password:
            env['PGPASSWORD'] = self.password
        return env

    async def _emit_progress(
        self,
        progress_callback: Optional[Callable[[str, int], Any]],
        step: str,
        percent: int,
    ) -> None:
        """Safely emit progress for sync or async callbacks."""
        if not progress_callback:
            return

        try:
            maybe_awaitable = progress_callback(step, percent)
            if inspect.isawaitable(maybe_awaitable):
                await maybe_awaitable
        except Exception as error:
            logger.warning("Progress callback failed: {}", error)

    def _get_tool_candidates(self, tool_name: str) -> list[str]:
        """Build candidate executable paths for pg_dump/pg_restore."""
        env_var = "POSTGRES_PG_DUMP_PATH" if tool_name == "pg_dump" else "POSTGRES_PG_RESTORE_PATH"
        candidates: list[str] = []

        # Explicit override wins.
        override = os.getenv(env_var)
        if override:
            candidates.append(override)

        # PATH resolution next.
        resolved = shutil.which(tool_name)
        if resolved:
            candidates.append(resolved)

        # Homebrew common locations (Apple Silicon + Intel).
        brew_roots = ["/opt/homebrew", "/usr/local"]
        for root in brew_roots:
            candidates.append(f"{root}/opt/libpq/bin/{tool_name}")
            for major in ("17", "16", "15", "14"):
                candidates.append(f"{root}/opt/postgresql@{major}/bin/{tool_name}")

        # De-duplicate while preserving order.
        deduped: list[str] = []
        seen: set[str] = set()
        for candidate in candidates:
            if candidate not in seen:
                deduped.append(candidate)
                seen.add(candidate)
        return deduped

    async def _resolve_tool(self, tool_name: str) -> str:
        """Resolve a working executable for pg_dump/pg_restore."""
        if tool_name in self._tool_cache:
            return self._tool_cache[tool_name]

        diagnostics: list[str] = []

        for candidate in self._get_tool_candidates(tool_name):
            if not Path(candidate).exists():
                diagnostics.append(f"{candidate}: not found")
                continue
            if not os.access(candidate, os.X_OK):
                diagnostics.append(f"{candidate}: not executable")
                continue

            try:
                process = await asyncio.create_subprocess_exec(
                    candidate, "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()
            except Exception as error:
                diagnostics.append(f"{candidate}: probe error - {error}")
                continue

            out_text = stdout.decode("utf-8", errors="replace").strip()
            err_text = stderr.decode("utf-8", errors="replace").strip()
            if process.returncode == 0:
                self._tool_cache[tool_name] = candidate
                logger.info("Resolved {} executable: {} ({})", tool_name, candidate, out_text or "version ok")
                return candidate

            diagnostics.append(
                f"{candidate}: exited {process.returncode} ({err_text or out_text or 'unknown error'})"
            )

        diagnostic_text = "\n".join(diagnostics[-8:])
        raise RuntimeError(
            f"No working '{tool_name}' executable found.\n"
            f"Set POSTGRES_{tool_name.upper()}_PATH to a valid binary path.\n"
            f"Diagnostics:\n{diagnostic_text}"
        )

    async def execute_pg_dump(
        self,
        output_path: Path,
        compress: bool = True,
        parallel_jobs: int = 4,
        progress_callback: Optional[Callable[[str, int], Any]] = None
    ) -> SubprocessResult:
        """Execute pg_dump to create a database backup.

        Args:
            output_path: Path where the backup file will be saved
            compress: Whether to compress the backup with gzip
            parallel_jobs: Number of parallel jobs for dumping (only used with directory format)
            progress_callback: Optional callback for progress updates (step, percent)

        Returns:
            SubprocessResult with execution details
        """
        start_time = datetime.now(timezone.utc)

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Use directory format for parallel processing
        # This creates a directory with multiple files that can be written in parallel
        use_directory_format = parallel_jobs > 1
        pg_dump_bin = await self._resolve_tool("pg_dump")

        # Build pg_dump command
        cmd = [
            pg_dump_bin,
            '--host', self.host,
            '--port', str(self.port),
            '--username', self.username,
            '--dbname', self.database,
            '--verbose',
            '--no-password',  # Use PGPASSWORD env var
        ]

        if use_directory_format:
            # Directory format for parallel processing
            cmd.extend([
                '--format=directory',
                '--jobs', str(parallel_jobs),
                '--file', str(output_path),
            ])
            if compress:
                cmd.append('--compress=6')  # Compression level 0-9
        else:
            # Custom format (single file)
            cmd.extend([
                '--format=custom',
                '--file', str(output_path),
            ])

        logger.info(f"Starting pg_dump backup with {pg_dump_bin} to {output_path}")
        if progress_callback:
            await self._emit_progress(progress_callback, "Initializing backup...", 0)

        try:
            # Execute pg_dump
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=self._get_env(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Collect output with progress tracking
            stdout_lines = []
            stderr_lines = []
            table_count = 0

            async def read_stream(stream, lines_list, is_stderr=False):
                nonlocal table_count
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    line_str = line.decode('utf-8', errors='replace').strip()
                    lines_list.append(line_str)

                    # Track progress from verbose output
                    if is_stderr and progress_callback:
                        if 'dumping contents of table' in line_str.lower():
                            table_count += 1
                            # Estimate progress (rough approximation)
                            await self._emit_progress(
                                progress_callback,
                                f"Dumping table {table_count}...",
                                min(90, table_count * 2),
                            )

            # Read both stdout and stderr concurrently
            await asyncio.gather(
                read_stream(process.stdout, stdout_lines, False),
                read_stream(process.stderr, stderr_lines, True)
            )

            # Wait for process to complete
            return_code = await process.wait()

            if return_code == 0:
                final_path = output_path

                # Calculate total size
                if use_directory_format:
                    # For directory format, calculate total size of all files
                    file_size = sum(
                        f.stat().st_size
                        for f in output_path.rglob('*')
                        if f.is_file()
                    )
                else:
                    # For single file format, optionally compress
                    if compress and not use_directory_format:
                        if progress_callback:
                            await self._emit_progress(progress_callback, "Compressing backup...", 95)

                        compressed_path = Path(str(output_path) + '.gz')
                        with open(output_path, 'rb') as f_in:
                            with gzip.open(compressed_path, 'wb', compresslevel=6) as f_out:
                                shutil.copyfileobj(f_in, f_out)

                        # Remove uncompressed file
                        output_path.unlink()
                        final_path = compressed_path

                    file_size = final_path.stat().st_size

                if progress_callback:
                    await self._emit_progress(progress_callback, "Backup completed", 100)

                logger.info(f"Backup successful: {final_path} ({file_size / 1024 / 1024:.2f} MB)")
            else:
                logger.error(f"pg_dump failed with return code {return_code}")
                final_path = None
                file_size = None

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            return SubprocessResult(
                success=(return_code == 0),
                return_code=return_code,
                stdout='\n'.join(stdout_lines),
                stderr='\n'.join(stderr_lines),
                duration_seconds=duration,
                output_file=final_path,
                file_size=file_size
            )

        except Exception as e:
            logger.error(f"Error executing pg_dump: {e}")
            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            return SubprocessResult(
                success=False,
                return_code=-1,
                stdout='',
                stderr=str(e),
                duration_seconds=duration
            )

    async def execute_pg_restore(
        self,
        backup_path: Path,
        clean: bool = True,
        parallel_jobs: int = 4,
        progress_callback: Optional[Callable[[str, int], Any]] = None
    ) -> SubprocessResult:
        """Execute pg_restore to restore a database backup.

        Args:
            backup_path: Path to the backup file or directory
            clean: Whether to clean (drop) database objects before recreating
            parallel_jobs: Number of parallel jobs for restoring
            progress_callback: Optional callback for progress updates (step, percent)

        Returns:
            SubprocessResult with execution details
        """
        start_time = datetime.now(timezone.utc)

        # Check if backup file exists
        if not backup_path.exists():
            return SubprocessResult(
                success=False,
                return_code=-1,
                stdout='',
                stderr=f"Backup file not found: {backup_path}",
                duration_seconds=0
            )

        # Check if backup is directory format
        is_directory_format = backup_path.is_dir()

        # Decompress if needed (only for single file format)
        actual_backup_path = backup_path
        temp_path = None

        if not is_directory_format and backup_path.suffix == '.gz':
            if progress_callback:
                await self._emit_progress(progress_callback, "Decompressing backup...", 5)

            temp_path = backup_path.with_suffix('')
            with gzip.open(backup_path, 'rb') as f_in:
                with open(temp_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            actual_backup_path = temp_path

        # Build pg_restore command
        pg_restore_bin = await self._resolve_tool("pg_restore")
        cmd = [
            pg_restore_bin,
            '--host', self.host,
            '--port', str(self.port),
            '--username', self.username,
            '--dbname', self.database,
            '--verbose',
            '--no-password',  # Use PGPASSWORD env var
        ]

        # Add parallel jobs for better performance
        if parallel_jobs > 1:
            cmd.extend(['--jobs', str(parallel_jobs)])

        if clean:
            cmd.extend(['--clean', '--if-exists'])

        cmd.append(str(actual_backup_path))

        logger.info(f"Starting pg_restore with {pg_restore_bin} from {backup_path}")
        if progress_callback:
            await self._emit_progress(progress_callback, "Initializing restore...", 10)

        try:
            # Execute pg_restore
            process = await asyncio.create_subprocess_exec(
                *cmd,
                env=self._get_env(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Collect output with progress tracking
            stdout_lines = []
            stderr_lines = []
            object_count = 0

            async def read_stream(stream, lines_list, is_stderr=False):
                nonlocal object_count
                while True:
                    line = await stream.readline()
                    if not line:
                        break
                    line_str = line.decode('utf-8', errors='replace').strip()
                    lines_list.append(line_str)

                    # Track progress from verbose output
                    if is_stderr and progress_callback:
                        if any(keyword in line_str.lower() for keyword in ['creating', 'processing', 'restoring']):
                            object_count += 1
                            # Estimate progress
                            await self._emit_progress(
                                progress_callback,
                                f"Restoring object {object_count}...",
                                min(90, 10 + object_count),
                            )

            # Read both stdout and stderr concurrently
            await asyncio.gather(
                read_stream(process.stdout, stdout_lines, False),
                read_stream(process.stderr, stderr_lines, True)
            )

            # Wait for process to complete
            return_code = await process.wait()

            # Clean up temp file if we created one
            if temp_path and temp_path.exists():
                temp_path.unlink()

            if return_code == 0:
                if progress_callback:
                    await self._emit_progress(progress_callback, "Restore completed", 100)
                logger.info(f"Restore successful from {backup_path}")
            else:
                logger.error(f"pg_restore failed with return code {return_code}")

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            return SubprocessResult(
                success=(return_code == 0),
                return_code=return_code,
                stdout='\n'.join(stdout_lines),
                stderr='\n'.join(stderr_lines),
                duration_seconds=duration
            )

        except Exception as e:
            logger.error(f"Error executing pg_restore: {e}")

            # Clean up temp file on error
            if temp_path and temp_path.exists():
                temp_path.unlink()

            duration = (datetime.now(timezone.utc) - start_time).total_seconds()

            return SubprocessResult(
                success=False,
                return_code=-1,
                stdout='',
                stderr=str(e),
                duration_seconds=duration
            )

    async def calculate_checksum(self, file_path: Path) -> str:
        """Calculate SHA256 checksum of a file or directory.

        Args:
            file_path: Path to the file or directory

        Returns:
            Hexadecimal checksum string
        """
        sha256_hash = hashlib.sha256()

        def read_path():
            if file_path.is_dir():
                # Deterministic checksum for pg_dump directory format:
                # include relative file names + file contents in sorted order.
                for item in sorted(p for p in file_path.rglob("*") if p.is_file()):
                    rel_path = item.relative_to(file_path).as_posix().encode("utf-8")
                    sha256_hash.update(rel_path)
                    sha256_hash.update(b"\0")
                    with open(item, "rb") as f:
                        for byte_block in iter(lambda: f.read(4096), b""):
                            sha256_hash.update(byte_block)
            else:
                with open(file_path, "rb") as f:
                    for byte_block in iter(lambda: f.read(4096), b""):
                        sha256_hash.update(byte_block)

        # Run file reading in executor to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, read_path)

        return sha256_hash.hexdigest()

    async def verify_pg_tools(self) -> Tuple[bool, str]:
        """Verify that pg_dump and pg_restore are available.

        Returns:
            Tuple of (success, message)
        """
        tools_available = True
        messages: list[str] = []

        for tool in ["pg_dump", "pg_restore"]:
            try:
                resolved_tool = await self._resolve_tool(tool)
                process = await asyncio.create_subprocess_exec(
                    resolved_tool, "--version",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await process.communicate()
                version_text = stdout.decode("utf-8", errors="replace").strip() or stderr.decode(
                    "utf-8", errors="replace"
                ).strip()
                if process.returncode != 0:
                    tools_available = False
                    messages.append(
                        f"{tool}: BROKEN ({resolved_tool}) -> exit {process.returncode}: {version_text or 'unknown'}"
                    )
                else:
                    messages.append(f"{tool}: {version_text} [{resolved_tool}]")
            except Exception as error:
                tools_available = False
                messages.append(f"{tool}: ERROR - {error}")

        return tools_available, "\n".join(messages)
