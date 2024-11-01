from contextlib import contextmanager
import sys
import os

@contextmanager
def suppress_output():
    """
    A simpler context manager that temporarily redirects stdout and stderr.
    """
    # Store the original stdout and stderr
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    
    try:
        # Redirect stdout and stderr to devnull
        with open(os.devnull, 'w') as devnull:
            sys.stdout = devnull
            sys.stderr = devnull
            yield
    finally:
        # Restore stdout and stderr
        sys.stdout = old_stdout
        sys.stderr = old_stderr