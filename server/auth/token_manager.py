"""Token manager thread pool.

Provides the shared ThreadPoolExecutor used for blocking token operations.
"""
from concurrent.futures import ThreadPoolExecutor

# Thread pool for blocking MSAL operations
_token_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="token_mgr")
