This is UV astral python package manager based project, no pip.
use uv add "lib" or uv run file.py to perform operations.



Some of the pattern that need to be followed everywhere.

- Typesafe code, use pydantic schema.
- Proper error and exception handling 
- Never write code which does silent error bypass. The error should be raised.
- Always have a clear debate between when to use asynchronous vs concurrent