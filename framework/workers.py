import os
import logging
import multiprocessing
from colorama import init, Fore, Style
from tqdm import tqdm
from multiprocessing import Pool
from functools import partial

from processing.step_file_processor import StepFileProcessor
from utils.logging_utils import setup_logging

def worker_init(output_folder):
    setup_logging(output_folder)

def process_single_file(args):
    file_path, output_folder, skip_existing, generate_metadata_flag, generate_assembly, generate_hierarchical, save_pdf, save_html, no_self_connections, generate_stats, images, images_metadata, headless = args

    process_id = multiprocessing.current_process().pid

    logging.info(f"Process {process_id} started processing {file_path}")

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
        images_metadata=images_metadata,
        headless=headless
    )

    result = processor.process()
    logging.info(f"Processing complete for {file_path}")
    return result

def process_step_files(folder_path, output_folder, skip_existing, num_processes,
                       generate_metadata_flag, generate_assembly, generate_hierarchical,
                       save_pdf, save_html, no_self_connections, generate_stats,
                       images, images_metadata, headless):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    setup_logging(output_folder)

    logging.info(f"Starting to process files in {folder_path}")

    step_files = [os.path.join(folder_path, f) for f in os.listdir(
        folder_path) if f.lower().endswith(('.step', '.stp'))]

    print(f"{Fore.YELLOW}Processing {Fore.RED}{len(step_files)}{Style.RESET_ALL} files using {Fore.RED}{num_processes}{Style.RESET_ALL} processes{Style.RESET_ALL}")

    args_list = [
        (file_path, output_folder, skip_existing, generate_metadata_flag,
         generate_assembly, generate_hierarchical, save_pdf, save_html,
         no_self_connections, generate_stats, images, images_metadata, headless)
        for file_path in step_files
    ]

    results = []
    with Pool(processes=num_processes, initializer=worker_init, initargs=(output_folder,)) as pool:
        try:
            for result in tqdm(pool.imap_unordered(process_single_file, args_list),
                               total=len(step_files), desc="Overall Progress"):
                results.append(result)
        except Exception as e:
            logging.error(f"Error during multiprocessing: {e}")
        finally:
            pool.close()
            pool.join()

    logging.info("Finished processing all files")

    for res in results:
        print(res)
