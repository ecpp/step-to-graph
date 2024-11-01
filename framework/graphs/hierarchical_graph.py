import networkx as nx
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_SHELL, TopAbs_FACE, TopAbs_EDGE
import logging
class HierarchicalGraph:
    def __init__(self, shape):
        self.shape = shape
        self.graph = nx.DiGraph()

    def create(self):
        shell_explorer = TopExp_Explorer(self.shape, TopAbs_SHELL)

        shell_nodes = []
        face_nodes = []
        edge_nodes = []

        while shell_explorer.More():
            shell = shell_explorer.Current()
            shell_id = f"Shell_{len(shell_nodes)}"
            self.graph.add_node(shell_id, label=shell_id, shape_type="SHELL")
            shell_nodes.append((shell_id, shell))
            shell_explorer.Next()

        for shell_id, shell in shell_nodes:
            face_explorer = TopExp_Explorer(shell, TopAbs_FACE)
            while face_explorer.More():
                face = face_explorer.Current()
                face_id = f"Face_{len(face_nodes)}"
                self.graph.add_node(face_id, label=face_id, shape_type="FACE")
                face_nodes.append((face_id, face))
                self.graph.add_edge(shell_id, face_id)
                face_explorer.Next()

        for face_id, face in face_nodes:
            edge_explorer = TopExp_Explorer(face, TopAbs_EDGE)
            while edge_explorer.More():
                edge = edge_explorer.Current()
                edge_id = f"Edge_{len(edge_nodes)}"
                self.graph.add_node(edge_id, label=edge_id, shape_type="EDGE")
                edge_nodes.append((edge_id, edge))
                self.graph.add_edge(face_id, edge_id)
                edge_explorer.Next()

    def save_graphml(self, output_file):
        nx.write_graphml(self.graph, output_file)
