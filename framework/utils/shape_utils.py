import math
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.TopAbs import TopAbs_VERTEX, TopAbs_SHELL, TopAbs_FACE
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRep import BRep_Tool

class ShapeUtils:
    @staticmethod
    def get_bounding_box(shape):
        bbox = Bnd_Box()
        brepbndlib.Add(shape, bbox)
        return bbox

    @staticmethod
    def count_subshapes(shape):
        num_shells = 0
        num_faces = 0

        shell_explorer = TopExp_Explorer(shape, TopAbs_SHELL)
        while shell_explorer.More():
            num_shells += 1
            shell_explorer.Next()

        face_explorer = TopExp_Explorer(shape, TopAbs_FACE)
        while face_explorer.More():
            num_faces += 1
            face_explorer.Next()

        return num_shells, num_faces

    @staticmethod
    def get_shape_size(shape):
        bbox = ShapeUtils.get_bounding_box(shape)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        diagonal = math.sqrt((xmax - xmin) ** 2 + (ymax - ymin) ** 2 + (zmax - zmin) ** 2)
        return diagonal

    @staticmethod
    def get_vertices(shape):
        vertices = []
        explorer = TopExp_Explorer(shape, TopAbs_VERTEX)
        while explorer.More():
            vertex = explorer.Current()
            point = BRep_Tool.Pnt(vertex)
            vertices.append((point.X(), point.Y(), point.Z()))
            explorer.Next()
        return vertices

    @staticmethod
    def are_connected(shape1, shape2):
        size1 = ShapeUtils.get_shape_size(shape1)
        size2 = ShapeUtils.get_shape_size(shape2)
        avg_size = (size1 + size2) / 2
        multiplier = 0.0001
        tolerance = min(avg_size * multiplier, 0.1)

        dist_tool = BRepExtrema_DistShapeShape(shape1, shape2)
        if dist_tool.IsDone():
            if dist_tool.Value() <= tolerance:
                return True

        vertices1 = ShapeUtils.get_vertices(shape1)
        vertices2 = ShapeUtils.get_vertices(shape2)

        for v1 in vertices1:
            for v2 in vertices2:
                dist = math.sqrt((v1[0] - v2[0]) ** 2 +
                                 (v1[1] - v2[1]) ** 2 +
                                 (v1[2] - v2[2]) ** 2)
                if dist <= tolerance:
                    return True

        return False
