import os
import logging

def setup_logging(output_folder):
    log_file = os.path.join(output_folder, 'processing_log.txt')
    logging.basicConfig(filename=log_file, level=logging.DEBUG,
                        format='%(asctime)s - %(levelname)s - %(message)s')
