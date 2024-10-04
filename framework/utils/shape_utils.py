import math
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.TopAbs import TopAbs_SHELL, TopAbs_FACE, TopAbs_EDGE, TopAbs_VERTEX
from OCC.Core.BRep import BRep_Tool
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Extend.TopologyUtils import TopologyExplorer

class ShapeUtils:
    @staticmethod
    def get_bounding_box(shape):
        bbox = Bnd_Box()
        brepbndlib.Add(shape, bbox)
        return bbox

    @staticmethod
    def get_tolerance(shape):
        # Example: Tolerance based on shape size
        bbox = ShapeUtils.get_bounding_box(shape)
        xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
        diagonal = math.sqrt((xmax - xmin) ** 2 + (ymax - ymin) ** 2 + (zmax - zmin) ** 2)
        return min(diagonal * 0.0001, 0.1)

    @staticmethod
    def are_connected(shape1, shape2):
        size1 = ShapeUtils.get_shape_size(shape1)
        size2 = ShapeUtils.get_shape_size(shape2)
        avg_size = (size1 + size2) / 2
        multiplier = 0.0001
        tolerance = min(avg_size * multiplier, 0.1)

        # First attempt using distance tool
        dist_tool = BRepExtrema_DistShapeShape(shape1, shape2)
        if dist_tool.IsDone() and dist_tool.Value() <= tolerance:
            return True

        # Fallback to vertex distance
        vertices1 = ShapeUtils.get_vertices(shape1)
        vertices2 = ShapeUtils.get_vertices(shape2)

        for v1 in vertices1:
            for v2 in vertices2:
                dist = math.sqrt(
                    (v1[0] - v2[0]) ** 2 +
                    (v1[1] - v2[1]) ** 2 +
                    (v1[2] - v2[2]) ** 2
                )
                if dist <= tolerance:
                    return True

        return False

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