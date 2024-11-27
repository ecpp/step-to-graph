import os
import logging
import multiprocessing
from concurrent.futures import ProcessPoolExecutor, as_completed
from colorama import Fore, Style
from tqdm import tqdm
from OCC.Display.SimpleGui import init_display
from processing.step_file_processor import StepFileProcessor
from utils.logging_utils import setup_logging, log_process_memory
import signal
import gc
import psutil

class DisplayManager:
    """
    Manages display instances for each worker process.
    Ensures that only one display is initialized per process.
    """
    _display = None
    _start_display = None
    _add_menu = None
    _add_function_to_menu = None
    _lock = multiprocessing.Lock()

    @classmethod
    def initialize(cls, output_folder):
        with cls._lock:
            if cls._display is None:
                cls._display, cls._start_display, cls._add_menu, cls._add_function_to_menu = init_display(size=(320, 240))
                logging.info("Display initialized for process.")

    @classmethod
    def get_display(cls):
        if cls._display is None:
            raise RuntimeError("Display not initialized. Call initialize() first.")
        return cls._display

    @classmethod
    def clear_display(cls):
        if cls._display:
            cls._display.Context.RemoveAll(True)
            cls._display.Repaint()
            cls._display.ResetView()


def worker_init(output_folder, images):
    """
    Initialize the worker process by setting up logging and display.
    """
    setup_logging(output_folder)
    if images:
        DisplayManager.initialize(output_folder)

def process_single_file(args):
    """
    Process a single STEP file using the StepFileProcessor.
    """
    try:
        file_path, output_folder, skip_existing, generate_metadata_flag, generate_assembly, generate_hierarchical, save_pdf, save_html, no_self_connections, generate_stats, images, only_full_assembly = args

        process_id = multiprocessing.current_process().pid
        logging.info(f"Process {process_id} started processing {file_path}")

        # Get the display for this process
        if images:
            display = DisplayManager.get_display()
        else:
            display = None
        
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
            only_full_assembly=only_full_assembly,
            display=display  # Pass the process-specific display
        )

        result = processor.process()
        del processor
        if display:
            DisplayManager.clear_display()
        return result
    except Exception as e:
        logging.error(f"Error processing file {file_path}: {e}")
        return None
    finally:
        log_process_memory()
        gc.collect()

class WorkBatch:
    def __init__(self, files, max_batch_size=100_000_000):  # 100MB default
        self.files = []
        self.current_size = 0
        self.max_batch_size = max_batch_size
        
    def add_file(self, file_path):
        file_size = os.path.getsize(file_path)
        if self.current_size + file_size <= self.max_batch_size:
            self.files.append(file_path)
            self.current_size += file_size
            return True
        return False

def create_batches(files, max_batch_size):
    batches = []
    current_batch = WorkBatch(max_batch_size)
    
    for file in files:
        if not current_batch.add_file(file):
            batches.append(current_batch.files)
            current_batch = WorkBatch(max_batch_size)
            current_batch.add_file(file)
    
    if current_batch.files:
        batches.append(current_batch.files)
    return batches

def process_batch(batch_args):
    """Process multiple files in a single process"""
    files, output_folder, *args = batch_args
    results = []
    
    try:
        display = DisplayManager.get_display() if args[-2] else None  # images flag
        for file in files:
            try:
                processor = StepFileProcessor(file, output_folder, *args[:-1], display)
                result = processor.process()
                results.append((file, result))
                del processor
                gc.collect()
            except Exception as e:
                results.append((file, None))
                logging.error(f"Error processing {file}: {e}")
    finally:
        if display:
            DisplayManager.clear_display()
        
    return results

def process_step_files_optimized(folder_path, output_folder, **kwargs):
    # Get system information for adaptive processing
    cpu_count = multiprocessing.cpu_count()
    available_memory = psutil.virtual_memory().available
    num_processes = min(kwargs.get('num_processes', cpu_count), cpu_count)
    
    # Calculate optimal batch size based on available memory
    memory_per_process = available_memory / (num_processes)
    batch_size = memory_per_process / 2  # Allow for processing overhead
    
    step_files = [
        os.path.join(folder_path, f) 
        for f in os.listdir(folder_path) 
        if f.lower().endswith(('.step', '.stp'))
    ]
    
    batches = create_batches(step_files, batch_size)
    
    with ProcessPoolExecutor(
        max_workers=num_processes,
        initializer=worker_init,
        initargs=(output_folder, kwargs.get('images', False))
    ) as executor:
        futures = []
        for batch in batches:
            batch_args = (batch, output_folder, *kwargs.values())
            futures.append(executor.submit(process_batch, batch_args))
            
        for future in tqdm(as_completed(futures), total=len(batches)):
            try:
                results = future.result()
                # Process results as needed
            except Exception as e:
                logging.error(f"Batch processing failed: {e}")

def process_step_files(folder_path, output_folder, skip_existing, num_processes, generate_metadata_flag, generate_assembly, generate_hierarchical, save_pdf, save_html, no_self_connections, generate_stats, images, only_full_assembly):
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
                no_self_connections, generate_stats, images, only_full_assembly
            ) 
            for file_path in step_files
        ]

        results = []
        executor = ProcessPoolExecutor(max_workers=num_processes, initializer=worker_init, initargs=(output_folder, images))
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
