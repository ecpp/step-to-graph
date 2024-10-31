from contextlib import contextmanager
import gc
import sys
import os
@contextmanager
def suppress_output():
    """
    A context manager that suppresses all output to stdout and stderr,
    including output from C extensions and other lower-level libraries.
    """
    with open(os.devnull, 'w') as devnull:
        # Flush any existing output
        sys.stdout.flush()
        sys.stderr.flush()
        
        # Save the original file descriptors
        original_stdout_fd = os.dup(1)
        original_stderr_fd = os.dup(2)

        try:
            # Redirect stdout and stderr to devnull
            os.dup2(devnull.fileno(), 1)
            os.dup2(devnull.fileno(), 2)
            
            # Also redirect sys.stdout and sys.stderr
            sys.stdout = open(os.devnull, 'w')
            sys.stderr = open(os.devnull, 'w')
            
            yield
        finally:
            # Restore the original file descriptors
            os.dup2(original_stdout_fd, 1)
            os.dup2(original_stderr_fd, 2)
            
            # Close the duplicated file descriptors
            os.close(original_stdout_fd)
            os.close(original_stderr_fd)
            
            # Restore sys.stdout and sys.stderr
            sys.stdout = sys.__stdout__
            sys.stderr = sys.__stderr__