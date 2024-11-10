import os
import logging
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from colorama import Fore, Style
from tqdm import tqdm
from OCC.Display.SimpleGui import init_display
from processing.step_file_processor import StepFileProcessor
from utils.logging_utils import setup_logging
import gc
from functools import lru_cache
import signal

# Remove the global variables
# Instead, create a process-specific cached display initializer
@lru_cache(maxsize=None)
def get_process_display():
    """
    Creates and caches a display instance per process.
    The lru_cache decorator ensures one display per process since the cache is process-specific.
    """
    return init_display()

def worker_init(output_folder):
    """
    Initialize the worker process by setting up logging.
    """
    setup_logging(output_folder)
    # Pre-warm the display cache for this process
    get_process_display()

def process_single_file(args):
    """
    Process a single STEP file using the StepFileProcessor.
    """
    file_path, output_folder, skip_existing, generate_metadata_flag, generate_assembly, generate_hierarchical, save_pdf, save_html, no_self_connections, generate_stats, images, headless = args

    process_id = multiprocessing.current_process().pid

    logging.info(f"Process {process_id} started processing {file_path}")

    # Get the cached display for this process
    display, start_display, add_menu, add_function_to_menu = get_process_display()
    
    processor = StepFileProcessor(
        file_path=file_path,
        output_folder=output_folder,
        skip_existing=skip_existing,
        generate_metadata_flag=generate_metadata_flag,
        generate_assembly=generate_assembly,
        generate_hierarchical=generate_hierarchical,
        save_pdf=save_pdf,
        save_html=save_html,
        no_self_connections=no_self_connections,
        generate_stats=generate_stats,
        images=images,
        headless=headless,
        display=display  # Pass the process-specific display
    )

    result = processor.process()
    gc.collect()
    return result

def process_step_files(folder_path, output_folder, skip_existing, num_processes, generate_metadata_flag, generate_assembly, generate_hierarchical, save_pdf, save_html, no_self_connections, generate_stats, images, headless):
    """
    Process all STEP files in the specified folder using concurrent futures.
    """
    executor = None
    termination_event = multiprocessing.Event()
    
    def signal_handler(signum, frame):
        print(f"\n{Fore.RED}Ctrl+C detected. Forcefully shutting down...{Style.RESET_ALL}")
        termination_event.set()
        if executor:
            # Cancel all pending tasks
            for future in future_to_file.keys():
                future.cancel()
            # Forcefully shutdown the executor without waiting
            executor._processes.clear()
            executor.shutdown(wait=False)
            # Terminate all processes in the pool
            for process in multiprocessing.active_children():
                process.terminate()
                process.join(timeout=1)
                if process.is_alive():
                    process.kill()  # Force kill if still alive
        print(f"\n{Fore.GREEN}Cleanup complete. Exiting.{Style.RESET_ALL}")
        os._exit(1)  # Force exit the program
    
    # Set up signal handler
    original_sigint_handler = signal.signal(signal.SIGINT, signal_handler)
    
    try:
        if not os.path.exists(output_folder):
            os.makedirs(output_folder)

        setup_logging(output_folder)

        logging.info(f"Starting to process files in {folder_path}")

        step_files = [
            os.path.join(folder_path, f) 
            for f in os.listdir(folder_path) 
            if f.lower().endswith(('.step', '.stp'))
        ]

        print(f"{Fore.YELLOW}Processing {Fore.RED}{len(step_files)}{Style.RESET_ALL} files using {Fore.RED}{num_processes}{Style.RESET_ALL} processes{Style.RESET_ALL}")

        args_list = [
            (
                file_path, output_folder, skip_existing, generate_metadata_flag,
                generate_assembly, generate_hierarchical, save_pdf, save_html,
                no_self_connections, generate_stats, images, headless
            ) 
            for file_path in step_files
        ]

        results = []
        executor = ProcessPoolExecutor(max_workers=num_processes, initializer=worker_init, initargs=(output_folder,))
        # Submit all tasks to the executor
        future_to_file = {executor.submit(process_single_file, args): args[0] for args in args_list}
        
        # Use tqdm to display a progress bar
        for future in tqdm(as_completed(future_to_file), total=len(step_files), desc="Overall Progress"):
            if termination_event.is_set():
                break
            
            file = future_to_file[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as exc:
                logging.error(f"{file} generated an exception: {exc}")
    
    finally:
        # Restore original signal handler
        signal.signal(signal.SIGINT, original_sigint_handler)
        if executor:
            executor.shutdown(wait=False)
        
        if termination_event.is_set():
            logging.info("Processing interrupted by user")
        else:
            logging.info("Finished processing all files")

