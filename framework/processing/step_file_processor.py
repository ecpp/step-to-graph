import os
import logging
import multiprocessing
import json
import re
import platform
from colorama import Fore, Style
from tqdm import tqdm
from OCC.Core.AIS import AIS_Shape
from OCC.Display.SimpleGui import init_display
from OCC.Extend.DataExchange import read_step_file
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_SOLID, TopAbs_COMPOUND
import time
import gc

from processing.step_file import StepFile
from graphs.assembly_graph import AssemblyGraph
from graphs.hierarchical_graph import HierarchicalGraph
from metadata.metadata_generator import MetadataGenerator
from utils.output_utils import suppress_output
try:
    from pyvirtualdisplay import Display
except ImportError:
    Display = None


class StepFileProcessor:
    def __init__(self, file_path, output_folder, skip_existing, generate_metadata_flag,
                 generate_assembly, generate_hierarchical, save_pdf, save_html,
                 no_self_connections, generate_stats, images, images_metadata, headless=None):
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
        self.images_metadata = images_metadata
        self.filename = os.path.basename(file_path)
        self.name_without_extension = os.path.splitext(self.filename)[0]
        self.subfolder = os.path.join(self.output_folder, self.name_without_extension)
        if not os.path.exists(self.subfolder):
            os.makedirs(self.subfolder)
        self.parts = []
        self.shape = None
        self.headless = self.determine_headless_mode(headless)

    def determine_headless_mode(self, headless_arg):
        """
        Determines whether to run in headless mode based on user input and environment.
        """
        # If headless is explicitly set, use it
        if headless_arg is not None:
            return headless_arg

        # Automatic detection
        system = platform.system()
        if system == 'Linux':
            # Check if DISPLAY environment variable is set
            if not os.getenv('DISPLAY'):
                logging.info("Running in headless mode")
                return True
        # For other systems (e.g., Windows), assume display is available
        logging.info("Running with display")
        return False

    def process(self):
        try:
            logging.info(f"Reading STEP file: {self.filename}")
            step_file = StepFile(self.file_path)
            self.parts, self.shape = step_file.read()
            logging.info(f"STEP file read complete for {self.filename}")

            statistics = {}
            images_folder = os.path.join(self.subfolder, "images")
            if self.images:
                if not os.path.exists(images_folder):
                    os.makedirs(images_folder)
                self.extract_images(self.shape, images_folder)

            if self.generate_assembly:
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
                metadata_generator = MetadataGenerator(images_metadata=self.images_metadata)
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
        """
        Extracts images of the assembly and individual parts.
        Supports headless operation on Linux servers.
        """
        display_manager = None
        display = None
        logging.info(f"Extracting images started for {self.filename}")
        
        try:
            if self.headless:
                if Display is None:
                    logging.error("pyvirtualdisplay is not installed. Unable to run in headless mode.")
                    raise ImportError("pyvirtualdisplay is required for headless mode.")
                try:
                    display_manager = Display(visible=0, size=(800, 600))
                    display_manager.start()
                    logging.info("Initialized virtual display for headless operation.")
                except Exception as e:
                    logging.error(f"Failed to initialize virtual display: {e}")
                    raise

            
            display, start_display, add_menu, add_function_to_menu = init_display()
            
            logging.debug(f"Initialized display for {self.filename}")
            
            # Save full assembly image
            display.Context.RemoveAll(True)
            ais_shape = AIS_Shape(shape)
            display.Context.Display(ais_shape, True)
            display.FitAll()
            
            full_assembly_path = os.path.join(output_folder, f"{self.name_without_extension}_full_assembly.png")
            display.View.Dump(full_assembly_path)
            logging.info(f"Saved full assembly image: {full_assembly_path}")
            
            # Extract individual part images
            for i, (part_name, part_shape) in enumerate(self.parts):
                if part_shape.ShapeType() in [TopAbs_SOLID, TopAbs_COMPOUND]:
                    display.Context.RemoveAll(True)
                    ais_part = AIS_Shape(part_shape)
                    display.Context.Display(ais_part, True)
                    display.FitAll()
                    
                    safe_part_name = re.sub(r'[^\w\-_\. ]', '_', part_name) if part_name else f"unnamed_part_{i+1}"
                    image_path = os.path.join(output_folder, f"{safe_part_name}.png")
                    
                    counter = 1
                    while os.path.exists(image_path):
                        image_path = os.path.join(output_folder, f"{safe_part_name}_{counter}.png")
                        counter += 1
                    
                    display.View.Dump(image_path)
                    logging.info(f"Saved part image: {image_path}")
                    display.Context.Remove(ais_part, True)
                    del ais_part

        except Exception as e:
            logging.error(f"Error during image extraction for {self.filename}: {str(e)}")
            raise
        
        finally:
            try:

                if display_manager:
                    display_manager.stop()
                    del display_manager
                
                
            except Exception as e:
                logging.error(f"Error during display cleanup: {str(e)}")
            
            logging.info(f"Finished extracting images for {self.filename}")