import networkx as nx
from rtree import index
import matplotlib.pyplot as plt
from tqdm import tqdm
from pyvis.network import Network
import os
import logging

from utils.shape_utils import ShapeUtils

class AssemblyGraph:
    def __init__(self, parts, filename, no_self_connections=False, images_folder=None):
        self.parts = []
        self.filename = filename
        self.graph = nx.Graph()
        self.no_self_connections = no_self_connections
        self.images_folder = images_folder
        
        p = index.Property()
        p.dimension = 3
        self.idx = index.Index(properties=p)

        # Precompute bounding boxes and insert into R-tree
        self.bounding_boxes = {}
        
        # Filter out invalid parts and store valid ones with their indices
        valid_parts_with_index = []
        for i, (name, shape) in enumerate(parts):
            try:
                if shape is None:
                    logging.warning(f"Skipping part {name}: Shape is None")
                    continue
                    
                bbox = ShapeUtils.get_bounding_box(shape)
                bbox_coords = (
                    bbox.CornerMin().X(),
                    bbox.CornerMin().Y(),
                    bbox.CornerMin().Z(),
                    bbox.CornerMax().X(),
                    bbox.CornerMax().Y(),
                    bbox.CornerMax().Z()
                )
                self.bounding_boxes[name] = bbox_coords
                self.idx.insert(len(valid_parts_with_index), bbox_coords)  # Use new index
                valid_parts_with_index.append((name, shape))
            except ValueError as e:
                logging.warning(f"Skipping part {name}: {str(e)}")
                continue
            
        self.parts = valid_parts_with_index

    def create(self, pbar):
        if not self.parts:
            logging.warning(f"No valid parts found for {self.filename}")
            return

        # Add all nodes first
        for name, _ in self.parts:
            self.graph.add_node(name)

        # Iterate through valid parts only
        for i, (name1, shape1) in enumerate(self.parts):
            bbox1 = self.bounding_boxes[name1]
            tolerance = ShapeUtils.get_tolerance(shape1)

            # Expand the bounding box by tolerance for searching
            expanded_bbox = (
                bbox1[0] - tolerance,
                bbox1[1] - tolerance,
                bbox1[2] - tolerance,
                bbox1[3] + tolerance,
                bbox1[4] + tolerance,
                bbox1[5] + tolerance
            )

            # Query the R-tree for possible overlapping shapes using correct indices
            possible_matches = list(self.idx.intersection(expanded_bbox))

            for j in possible_matches:
                if j <= i:
                    continue  # Avoid duplicate checks and self-comparison

                if j >= len(self.parts):  # Add safety check
                    continue

                name2, shape2 = self.parts[j]
                
                if self.no_self_connections and name1 == name2:
                    continue
                
                if ShapeUtils.are_connected(shape1, shape2):
                    self.graph.add_edge(name1, name2)
                pbar.update(1)

    def save_graphml(self, output_file):
        nx.write_graphml(self.graph, output_file)

    def save_pdf(self, output_file):
        plt.figure(figsize=(20, 20))
        pos = nx.kamada_kawai_layout(self.graph)
        nx.draw(self.graph, pos, with_labels=False, node_color='lightblue',
                node_size=3000, font_size=8, font_weight='bold')

        nx.draw_networkx_labels(self.graph, pos, font_size=6, font_weight='bold')

        plt.title("Assembly Graph", fontsize=16)
        plt.axis('off')
        plt.tight_layout()

        plt.savefig(f"{output_file}.pdf", format="pdf",
                    dpi=300, bbox_inches='tight')
        plt.close()
    
    def save_html(self, output_file):
        """
        Saves the assembly graph as an interactive HTML file with movable nodes and images.
        """
        net = Network(height='750px', width='100%', notebook=False)
        net.show_buttons(filter_=['physics'])

        if self.images_folder:
            for node_name in self.graph.nodes:
                image_filename = f"{node_name}.png"
                image_path = os.path.join(self.images_folder, image_filename)
                if os.path.exists(image_path):
                    net.add_node(
                        node_name,
                        label=node_name,
                        shape='image',
                        image=f"file://{os.path.abspath(image_path)}",
                        size=30
                    )
                else:
                    net.add_node(
                        node_name,
                        label=node_name,
                        shape='dot',
                        size=30
                    )
        else:
            for node_name in self.graph.nodes:
                net.add_node(
                    node_name,
                    label=node_name,
                    shape='dot',
                    size=30
                )

        for source, target in self.graph.edges:
            net.add_edge(source, target)

        net.save_graph(output_file)
