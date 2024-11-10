
import os
import logging
import multiprocessing
from colorama import Fore, Style
from tqdm import tqdm
from OCC.Display.SimpleGui import init_display
from processing.step_file_processor import StepFileProcessor
from utils.logging_utils import setup_logging

# Declare global variables to hold the display instances for each process
global_display = None
global_start_display = None
global_add_menu = None
global_add_function_to_menu = None

def worker_init(output_folder):
    setup_logging(output_folder)
    global global_display, global_start_display, global_add_menu, global_add_function_to_menu
    # Initialize a new display for each worker process
    global_display, global_start_display, global_add_menu, global_add_function_to_menu = init_display()

def process_single_file(args):
    file_path, output_folder, skip_existing, generate_metadata_flag, generate_assembly, generate_hierarchical, save_pdf, save_html, no_self_connections, generate_stats, images, headless = args

    process_id = multiprocessing.current_process().pid

    logging.info(f"Process {process_id} started processing {file_path}")

    # Access the global display initialized in worker_init
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
        display=global_display  # Pass the display to the processor
    )

    result = processor.process()
    return result

def process_step_files(folder_path, output_folder, skip_existing, num_processes, generate_metadata_flag, generate_assembly, generate_hierarchical, save_pdf, save_html, no_self_connections, generate_stats, images, headless):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    setup_logging(output_folder)

    logging.info(f"Starting to process files in {folder_path}")

    step_files = [os.path.join(folder_path, f) for f in os.listdir(
        folder_path) if f.lower().endswith(('.step', '.stp'))]

    print(f"{Fore.YELLOW}Processing {Fore.RED}{len(step_files)}{Style.RESET_ALL} files using {Fore.RED}{num_processes}{Style.RESET_ALL} processes{Style.RESET_ALL}")

    args_list = [(file_path, output_folder, skip_existing, generate_metadata_flag,
                  generate_assembly, generate_hierarchical, save_pdf, save_html, no_self_connections, generate_stats, images, headless) for file_path in step_files]  # Include generate_stats and images
    with multiprocessing.Pool(processes=num_processes, initializer=worker_init, initargs=(output_folder,)) as pool:
        results = list(tqdm(pool.imap(process_single_file, args_list),
                            total=len(step_files), desc="Overall Progress"))

    logging.info("Finished processing all files")

    for result in results:
        print(result)

