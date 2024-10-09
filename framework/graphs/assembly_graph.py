import networkx as nx
from rtree import index
import matplotlib.pyplot as plt
from tqdm import tqdm
from pyvis.network import Network  # Added import for HTML visualization

from utils.shape_utils import ShapeUtils

class AssemblyGraph:
    def __init__(self, parts, filename, no_self_connections=False):
        self.parts = parts
        self.filename = filename
        self.graph = nx.Graph()
        self.no_self_connections = no_self_connections
        
        p = index.Property()
        p.dimension = 3
        self.idx = index.Index(properties=p)

        # Precompute bounding boxes and insert into R-tree
        self.bounding_boxes = {}
        for i, (name, shape) in enumerate(self.parts):
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
            self.idx.insert(i, bbox_coords)

    def create(self, pbar):
        # Add all nodes first
        for name, _ in self.parts:
            self.graph.add_node(name)

        # Iterate through each part and find potential connections
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

            # Query the R-tree for possible overlapping shapes
            possible_matches = list(self.idx.intersection(expanded_bbox, objects=False))

            for j in possible_matches:
                if j <= i:
                    continue  # Avoid duplicate checks and self-comparison

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
        Saves the assembly graph as an interactive HTML file with movable nodes.
        """
        net = Network(height='750px', width='100%', notebook=False)
        net.from_nx(self.graph)
        net.show_buttons(filter_=['physics'])  # Optional: Adds physics controls
        net.save_graph(output_file)