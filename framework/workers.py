import os
import logging
from colorama import init, Fore, Style
from tqdm import tqdm

from processing.step_file_processor import StepFileProcessor
from utils.logging_utils import setup_logging

def process_step_files(folder_path, output_folder, skip_existing,
                      generate_metadata_flag, generate_assembly, generate_hierarchical,
                      save_pdf, save_html, no_self_connections, generate_stats,
                      images, images_metadata, headless):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    setup_logging(output_folder)
    logging.info(f"Starting to process files in {folder_path}")

    step_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) 
                 if f.lower().endswith(('.step', '.stp'))]

    print(f"{Fore.YELLOW}Processing {Fore.RED}{len(step_files)}{Style.RESET_ALL} files{Style.RESET_ALL}")

    results = []
    for file_path in tqdm(step_files, desc="Overall Progress"):
        try:
            logging.info(f"Started processing {file_path}")
            
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
            results.append(result)
            logging.info(f"Processing complete for {file_path}")
            
        except Exception as e:
            logging.error(f"Error processing {file_path}: {e}")

    logging.info("Finished processing all files")

    for res in results:
        print(res)
