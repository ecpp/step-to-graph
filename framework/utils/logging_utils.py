import os
import logging
import psutil

def setup_logging(output_folder):
    log_file = os.path.join(output_folder, 'processing_log.txt')
    logging.basicConfig(filename=log_file, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

def log_process_memory():
    # Get the current process
    current_process = psutil.Process(os.getpid())
    
    # Get all child processes
    total_mem = 0
    processes = [current_process]
    try:
        processes.extend(current_process.children(recursive=True))
    except psutil.NoSuchProcess:
        pass  # Handle case where child process ended during collection
    
    # Sum memory for all processes
    for proc in processes:
        try:
            total_mem += proc.memory_info().rss / (1024 * 1024)  # Convert to MB
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    if total_mem > 20000:
        logging.warning(f"Total memory usage exceeded 20000 MB: {total_mem:.2f} MB")
    else:
        logging.info(f"Total memory usage: {total_mem:.2f} MB")
