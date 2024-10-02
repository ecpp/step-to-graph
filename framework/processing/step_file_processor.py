import os
import logging
import multiprocessing
import json
import re
from colorama import Fore, Style
from tqdm import tqdm

from processing.step_file import StepFile
from graphs.assembly_graph import AssemblyGraph
from graphs.hierarchical_graph import HierarchicalGraph
from metadata.metadata_generator import MetadataGenerator

class StepFileProcessor:
    def __init__(self, file_path, output_folder, skip_existing, generate_metadata_flag, generate_assembly, generate_hierarchical, save_pdf):
        self.file_path = file_path
        self.output_folder = output_folder
        self.skip_existing = skip_existing
        self.generate_metadata_flag = generate_metadata_flag
        self.generate_assembly = generate_assembly
        self.generate_hierarchical = generate_hierarchical
        self.save_pdf = save_pdf
        self.filename = os.path.basename(file_path)
        self.name_without_extension = os.path.splitext(self.filename)[0]
        self.subfolder = os.path.join(self.output_folder, self.name_without_extension)
        if not os.path.exists(self.subfolder):
            os.makedirs(self.subfolder)
        self.parts = []
        self.shape = None

    def process(self):
        try:
            logging.info(f"Reading STEP file: {self.filename}")
            step_file = StepFile(self.file_path)
            self.parts, self.shape = step_file.read()

            if self.generate_assembly:
                if self.skip_existing and os.path.exists(f"{self.subfolder}/{self.name_without_extension}_assembly.graphml"):
                    logging.info(f"Skipped assembly graph for {self.filename} (already exists)")
                    return f"{Fore.YELLOW} {self.filename} assembly graph already exists, skipping{Style.RESET_ALL}"

                logging.info(f"Creating assembly graph for {self.filename}")
                total_comparisons = len(self.parts) * (len(self.parts) - 1) // 2
                with tqdm(total=total_comparisons, desc=f"{Fore.CYAN}{self.filename}{Style.RESET_ALL}",
                          unit="comp", leave=False, position=multiprocessing.current_process()._identity[0] - 1) as pbar:
                    assembly_graph = AssemblyGraph(self.parts, self.filename)
                    assembly_graph.create(pbar)
                    logging.info(f"Saving assembly graph for {self.filename}")
                    assembly_graph.save_graphml(f"{self.subfolder}/{self.name_without_extension}_assembly.graphml")

                    if self.save_pdf:
                        logging.info(f"Saving assembly graph as PDF for {self.filename}")
                        assembly_graph.save_pdf(f"{self.subfolder}/{self.name_without_extension}_assembly")

            if self.generate_hierarchical:
                if self.skip_existing and os.path.exists(f"{self.subfolder}/{self.name_without_extension}_hierarchical.graphml"):
                    logging.info(f"Skipped hierarchical graph for {self.filename} (already exists)")
                    return f"{Fore.YELLOW} {self.filename} hierarchical graph already exists, skipping{Style.RESET_ALL}"

                logging.info(f"Creating hierarchical graph for {self.filename}")
                hierarchical_graph = HierarchicalGraph(self.shape)
                hierarchical_graph.create()
                logging.info(f"Saving hierarchical graph for {self.filename}")
                hierarchical_graph.save_graphml(f"{self.subfolder}/{self.name_without_extension}_hierarchical.graphml")

            if self.generate_metadata_flag and len(self.parts) > 3:
                logging.info(f"Generating metadata for {self.filename}")
                product_names = [part[0] for part in self.parts]
                metadata_generator = MetadataGenerator()
                metadata = metadata_generator.generate(product_names, self.filename)
                if metadata:
                    with open(f"{self.subfolder}/{self.name_without_extension}_metadata.json", 'w') as f:
                        json.dump(metadata, f, indent=2)

            logging.info(f"Finished processing {self.filename}")
            return f"{Fore.GREEN} {self.filename} processed successfully{Style.RESET_ALL}"

        except Exception as e:
            logging.error(f"Error processing {self.filename}: {str(e)}")
            return f"{Fore.RED} Error processing {self.filename}: {str(e)}{Style.RESET_ALL}"
