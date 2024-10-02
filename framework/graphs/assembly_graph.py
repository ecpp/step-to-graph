import networkx as nx
import matplotlib.pyplot as plt
from tqdm import tqdm

from utils.shape_utils import ShapeUtils

class AssemblyGraph:
    def __init__(self, parts, filename):
        self.parts = parts
        self.filename = filename
        self.graph = nx.Graph()

    def create(self, pbar):
        for name, shape in self.parts:
            self.graph.add_node(name)

        for i, (name1, shape1) in enumerate(self.parts):
            for name2, shape2 in self.parts[i + 1:]:
                if ShapeUtils.are_connected(shape1, shape2):
                    self.graph.add_edge(name1, name2)
                pbar.update(1)

    def save_graphml(self, output_file):
        nx.write_graphml(self.graph, output_file)

    def save_pdf(self, output_file):
        plt.figure(figsize=(20, 20))
        pos = nx.spring_layout(self.graph, k=0.5, iterations=50)
        nx.draw(self.graph, pos, with_labels=False, node_color='lightblue',
                node_size=3000, font_size=8, font_weight='bold')

        nx.draw_networkx_labels(self.graph, pos, font_size=6, font_weight='bold')

        plt.title("Assembly Graph", fontsize=16)
        plt.axis('off')
        plt.tight_layout()

        plt.savefig(f"{output_file}.pdf", format="pdf",
                    dpi=300, bbox_inches='tight')
        plt.close()
