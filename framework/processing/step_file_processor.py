import os
import logging
import multiprocessing
import json
import re
from colorama import Fore, Style
from tqdm import tqdm
from OCC.Core.AIS import AIS_Shape
import gc
from OCC.Core.TopAbs import TopAbs_SOLID, TopAbs_COMPOUND, TopAbs_SHELL, TopAbs_FACE
import time
from processing.step_file import StepFile
from graphs.assembly_graph import AssemblyGraph
from graphs.hierarchical_graph import HierarchicalGraph
from metadata.metadata_generator import MetadataGenerator
from utils.shape_utils import ShapeUtils

class StepFileProcessor:
    def __init__(self, file_path, output_folder, skip_existing, generate_metadata_flag,
                 generate_assembly, generate_hierarchical, save_pdf, save_html,
                 no_self_connections, generate_stats, images, only_full_assembly, display=None):
        self.file_path = file_path
        self.output_folder = output_folder
        self.skip_existing = skip_existing
        self.generate_metadata_flag = generate_metadata_flag
        self.generate_assembly = generate_assembly
        self.generate_hierarchical = generate_hierarchical
        self.save_pdf = save_pdf
        self.save_html = save_html
        self.no_self_connections = no_self_connections
        self.generate_stats = generate_stats
        self.images = images
        self.only_full_assembly = only_full_assembly
        self.filename = os.path.basename(file_path)
        self.name_without_extension = os.path.splitext(self.filename)[0]
        self.subfolder = os.path.join(self.output_folder, self.name_without_extension)
        if not os.path.exists(self.subfolder):
            os.makedirs(self.subfolder)
        self.parts = []
        self.shape = None
        self.display = display

    def process(self):
        try:
            logging.info(f"Reading STEP file: {self.filename}")
            step_file = StepFile(self.file_path)
            self.parts, self.shape = step_file.read()

            statistics = {}
            images_folder = os.path.join(self.subfolder, "images")
            if self.images:
                if not os.path.exists(images_folder):
                    os.makedirs(images_folder)
                self.extract_images(self.shape, images_folder)

            if self.generate_assembly:
                # Add validation before creating assembly graph
                if not self.parts:
                    logging.error(f"No valid parts found in {self.filename}")
                    error_msg = f"{Fore.RED} Error processing {self.filename}: No valid parts found{Style.RESET_ALL}"
                    return error_msg
                
                valid_parts = [(name, shape) for name, shape in self.parts if shape is not None]
                if not valid_parts:
                    logging.error(f"No valid parts found in {self.filename}")
                    error_msg = f"{Fore.RED} Error processing {self.filename}: No valid parts found{Style.RESET_ALL}"
                    return error_msg
                
                assembly_graph_path = os.path.join(self.subfolder, f"{self.name_without_extension}_assembly.graphml")
                if self.skip_existing and os.path.exists(assembly_graph_path):
                    logging.info(f"Skipped assembly graph for {self.filename} (already exists)")
                    skip_msg = f"{Fore.YELLOW} {self.filename} assembly graph already exists, skipping{Style.RESET_ALL}"
                    if self.generate_stats:
                        statistics['assembly'] = {'status': 'skipped'}
                    return skip_msg

                logging.info(f"Creating assembly graph for {self.filename}")
                total_comparisons = len(self.parts) * (len(self.parts) - 1) // 2
                with tqdm(total=total_comparisons, desc=f"{Fore.CYAN}{self.filename}{Style.RESET_ALL}",
                          unit="comp", leave=False, position=multiprocessing.current_process()._identity[0] - 1) as pbar:
                    assembly_graph = AssemblyGraph(self.parts, self.filename, no_self_connections=self.no_self_connections, images_folder=images_folder)
                    assembly_graph.create(pbar)
                    logging.info(f"Saving assembly graph for {self.filename}")
                    assembly_graph.save_graphml(assembly_graph_path)

                    if self.save_pdf:
                        logging.info(f"Saving assembly graph as PDF for {self.filename}")
                        assembly_graph.save_pdf(os.path.join(self.subfolder, f"{self.name_without_extension}_assembly"))

                    if self.save_html:
                        logging.info(f"Saving assembly graph as HTML for {self.filename}")
                        assembly_graph.save_html(os.path.join(self.subfolder, f"{self.name_without_extension}_assembly.html"))

                if self.generate_stats:
                    statistics['assembly'] = {
                        'nodes': assembly_graph.graph.number_of_nodes(),
                        'edges': assembly_graph.graph.number_of_edges(),
                        'named_parts': len([p for p in self.parts if p[0]]),
                        'unnamed_parts': len([p for p in self.parts if not p[0]])
                    }

            if self.generate_hierarchical:
                hierarchical_graph_path = os.path.join(self.subfolder, f"{self.name_without_extension}_hierarchical.graphml")
                if self.skip_existing and os.path.exists(hierarchical_graph_path):
                    logging.info(f"Skipped hierarchical graph for {self.filename} (already exists)")
                    skip_msg = f"{Fore.YELLOW} {self.filename} hierarchical graph already exists, skipping{Style.RESET_ALL}"
                    if self.generate_stats:
                        statistics['hierarchical'] = {'status': 'skipped'}
                    return skip_msg

                logging.info(f"Creating hierarchical graph for {self.filename}")
                hierarchical_graph = HierarchicalGraph(self.shape)
                hierarchical_graph.create()
                logging.info(f"Saving hierarchical graph for {self.filename}")
                hierarchical_graph.save_graphml(hierarchical_graph_path)

                if self.generate_stats:
                    statistics['hierarchical'] = {
                        'nodes': hierarchical_graph.graph.number_of_nodes(),
                        'edges': hierarchical_graph.graph.number_of_edges(),
                        'shells': self._count_graph_nodes_by_type(hierarchical_graph.graph, 'SHELL'),
                        'faces': self._count_graph_nodes_by_type(hierarchical_graph.graph, 'FACE'),
                        'edges_graph': self._count_graph_nodes_by_type(hierarchical_graph.graph, 'EDGE')
                    }

            if self.generate_metadata_flag and len(self.parts) > 3:
                logging.info(f"Generating metadata for {self.filename}")
                product_names = [part[0] for part in self.parts if part[0]]
                metadata_generator = MetadataGenerator()
                metadata = metadata_generator.generate(product_names, self.filename, images_folder)
                if metadata:
                    metadata_path = os.path.join(self.subfolder, f"{self.name_without_extension}_metadata.json")
                    with open(metadata_path, 'w') as f:
                        json.dump(metadata, f, indent=2)

                    if self.generate_stats:
                        statistics['metadata'] = {
                            'generated': True,
                            'metadata_file': metadata_path
                        }

            if self.generate_stats:
                stats_path = os.path.join(self.subfolder, f"{self.name_without_extension}_statistics.json")
                with open(stats_path, 'w') as f:
                    json.dump(statistics, f, indent=2)

            logging.info(f"Finished processing {self.filename}")
            success_msg = f"{Fore.GREEN} {self.filename} processed successfully{Style.RESET_ALL}"
            return success_msg

        except Exception as e:
            logging.error(f"Error processing {self.filename}: {str(e)}")
            error_msg = f"{Fore.RED} Error processing {self.filename}: {str(e)}{Style.RESET_ALL}"
            return error_msg

    def _count_graph_nodes_by_type(self, graph, node_type):
        return len([n for n, attr in graph.nodes(data=True) if attr.get('shape_type') == node_type])

    def extract_images(self, shape, output_folder):
        try:
            full_assembly_path = os.path.join(output_folder, f"{self.name_without_extension}_full_assembly.png")
            if os.path.exists(full_assembly_path):
                logging.info(f"Full assembly image already exists, skipping image extraction: {full_assembly_path}")
                return

            # Clear display before starting
            self.display.Context.RemoveAll(True)

            # Extract individual parts first
            if not self.only_full_assembly:
                for i, (part_name, part_shape) in enumerate(self.parts):
                    if not ShapeUtils.is_valid_shape_type(part_shape):
                        continue
                    ais_shape = None
                    try:
                        self.display.Context.RemoveAll(True)
                        
                        ais_shape = AIS_Shape(part_shape)
                        self.display.Context.Display(ais_shape, True)
                        self.display.FitAll()
                        self.display.View.Redraw()
                        
                        safe_part_name = re.sub(r'[^\w\-_\. ]', '_', part_name) if part_name else f"unnamed_part_{i+1}"
                        
                        image_path = os.path.join(output_folder, f"{safe_part_name}.png")
                        self.display.View.Dump(image_path)

                        timeout = 10
                        start_time = time.time()
                        while not os.path.exists(image_path) or os.path.getsize(image_path) == 0:
                            time.sleep(0.1)
                            if time.time() - start_time > timeout:
                                raise TimeoutError(f"Timeout waiting for image to be saved: {image_path}")
                        
                        logging.info(f"Saved part image: {image_path}")
                    finally:
                        if ais_shape:
                            self.display.Context.Remove(ais_shape, True)
                            del ais_shape
                            gc.collect()
                        
                    time.sleep(0.1)

            # Extract full assembly last
            ais_shape = None
            try:
                self.display.Context.RemoveAll(True)
                ais_shape = AIS_Shape(shape)
                self.display.Context.Display(ais_shape, True)
                self.display.FitAll()
                
                self.display.View.Dump(full_assembly_path)
                logging.info(f"Saved full assembly image: {full_assembly_path}")
            finally:
                if ais_shape:
                    self.display.Context.Remove(ais_shape, True)
                    del ais_shape
                    gc.collect()
            
        finally:
            gc.collect()
