import os
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_SHELL
from OCC.Core.TopoDS import TopoDS_Iterator, TopoDS_Shape
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TDF import TDF_LabelSequence, TDF_Label
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform

class StepFile:
    def __init__(self, filename):
        self.filename = filename
        self.parts = []
        self.main_shape = None

    def read(self):
        if not os.path.isfile(self.filename):
            raise FileNotFoundError(f"{self.filename} not found.")

        doc = TDocStd_Document("pythonocc-doc-step-import")
        shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())

        step_reader = STEPCAFControl_Reader()
        step_reader.SetNameMode(True)

        status = step_reader.ReadFile(self.filename)
        if status != IFSelect_RetDone:
            raise ValueError("Error parsing STEP file")

        ok = step_reader.Transfer(doc)
        if not ok:
            raise ValueError("Transfer failed")

        output_shapes = {}
        locs = []

        def _get_sub_shapes(lab, loc):
            l_subss = TDF_LabelSequence()
            shape_tool.GetSubShapes(lab, l_subss)
            l_comps = TDF_LabelSequence()
            shape_tool.GetComponents(lab, l_comps)
            name = lab.GetLabelName()

            if shape_tool.IsAssembly(lab):
                l_c = TDF_LabelSequence()
                shape_tool.GetComponents(lab, l_c)
                for i in range(l_c.Length()):
                    label = l_c.Value(i + 1)
                    if shape_tool.IsReference(label):
                        label_reference = TDF_Label()
                        shape_tool.GetReferredShape(label, label_reference)
                        loc = shape_tool.GetLocation(label)
                        locs.append(loc)
                        _get_sub_shapes(label_reference, loc)
                        locs.pop()

            elif shape_tool.IsSimpleShape(lab):
                shape = shape_tool.GetShape(lab)
                loc_accumulated = TopLoc_Location()
                for l in locs:
                    loc_accumulated = loc_accumulated.Multiplied(l)
                shape_disp = BRepBuilderAPI_Transform(
                    shape, loc_accumulated.Transformation()).Shape()
                if shape_disp not in output_shapes:
                    output_shapes[shape_disp] = lab.GetLabelName()
                for i in range(l_subss.Length()):
                    lab_subs = l_subss.Value(i + 1)
                    shape_sub = shape_tool.GetShape(lab_subs)
                    shape_to_disp = BRepBuilderAPI_Transform(
                        shape_sub, loc_accumulated.Transformation()
                    ).Shape()
                    if shape_to_disp not in output_shapes:
                        output_shapes[shape_to_disp] = lab_subs.GetLabelName()

        def _get_shapes():
            labels = TDF_LabelSequence()
            shape_tool.GetFreeShapes(labels)
            for i in range(labels.Length()):
                root_item = labels.Value(i + 1)
                _get_sub_shapes(root_item, None)

        _get_shapes()

        self.parts = [(name, shape) for shape, name in output_shapes.items()]
        self.parts.sort(key=lambda x: x[0])

        shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
        labels = TDF_LabelSequence()
        shape_tool.GetFreeShapes(labels)

        if labels.Length() > 0:
            self.main_shape = shape_tool.GetShape(labels.Value(1))
        else:
            raise ValueError("No shapes found in the transferred document")

        return self.parts, self.main_shape
