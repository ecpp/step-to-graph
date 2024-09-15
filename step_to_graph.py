import os
import networkx as nx
from OCC.Core.STEPControl import STEPControl_Reader
from OCC.Core.IFSelect import IFSelect_RetDone
from OCC.Core.TopAbs import TopAbs_FACE, TopAbs_SOLID, TopAbs_SHELL, TopAbs_EDGE, TopAbs_VERTEX
from OCC.Core.TopoDS import TopoDS_Iterator, TopoDS_Shape
from OCC.Core.Bnd import Bnd_Box
from OCC.Core.BRepBndLib import brepbndlib
from OCC.Core.TopExp import TopExp_Explorer
from OCC.Core.BRepExtrema import BRepExtrema_DistShapeShape
from OCC.Core.BRep import BRep_Tool
from tqdm import tqdm
import re
import json
from openai import OpenAI
import multiprocessing
from colorama import init, Fore, Style
import argparse
import logging
from OCC.Core.TDocStd import TDocStd_Document
from OCC.Core.XCAFDoc import XCAFDoc_DocumentTool
from OCC.Core.STEPCAFControl import STEPCAFControl_Reader
from OCC.Core.TDF import TDF_LabelSequence, TDF_Label
from OCC.Core.TopLoc import TopLoc_Location
from OCC.Core.BRepBuilderAPI import BRepBuilderAPI_Transform
from OCC.Core.IFSelect import IFSelect_RetDone
import matplotlib.pyplot as plt

init()

def create_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI API key not found in environment variables")
    return OpenAI(api_key=api_key)

def read_step_file(filename):
    """
    Read the STEP file and returns a list of parts with their exact names.

    Returns:
        List of tuples: [(name, shape), ...]
    """
    if not os.path.isfile(filename):
        raise FileNotFoundError(f"{filename} not found.")

    doc = TDocStd_Document("pythonocc-doc-step-import")
    shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())

    step_reader = STEPCAFControl_Reader()
    step_reader.SetNameMode(True)

    status = step_reader.ReadFile(filename)
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
        # print("Name :", name)  # Debugging line

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
            shape_disp = BRepBuilderAPI_Transform(shape, loc_accumulated.Transformation()).Shape()
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

    # Convert output_shapes dictionary to a list of (name, shape) tuples
    parts = [(name, shape) for shape, name in output_shapes.items()]
    # Since shapes are keys, and dictionaries are unordered, let's sort parts for consistency
    parts.sort(key=lambda x: x[0])  # Sort by name
    # Also return the main shape (assembly)
    main_shape = None
    if step_reader.NbRootsForTransfer() > 0:
        # Transfer all roots
        ok = step_reader.Transfer(doc)
        if not ok:
            raise ValueError("Transfer failed")
        
        # Get the main shape (assembly) from the document
        shape_tool = XCAFDoc_DocumentTool.ShapeTool(doc.Main())
        labels = TDF_LabelSequence()
        shape_tool.GetFreeShapes(labels)
        
        if labels.Length() > 0:
            main_shape = shape_tool.GetShape(labels.Value(1))
        else:
            raise ValueError("No shapes found in the transferred document")
    else:
        raise ValueError("No root shapes found in the STEP file")

    return parts, main_shape

def generate_metadata(product_names, filename):
    """
    Generate metadata based on the extracted product names using AI.
    """
    client = create_openai_client()

    # Prepare the prompt for the AI
    prompt = f"Based on the following list of product names from a STEP file named '{filename}', generate a JSON metadata that includes:\n"
    prompt += "If none of the component names make sense, or too generic, ignore everything and return an empty JSON object.\n"
    prompt += "1. A brief description of what this assembly might be (json key description)\n"
    prompt += "2. Potential categories or tags for the assembly (json key categories)\n"
    prompt += "3. Estimated complexity (low, medium, high) (json key complexity)\n"
    prompt += "4. Possible industry or application (json key industry)\n"
    prompt += "5. Simplified names of components, for example if 'shaft_holder001' is a component, the name should be 'shaft_holder' or if it does not make sense do not include it (json key components)\n"
    prompt += "Product names: " + ", ".join(product_names)
    prompt += "\nProvide the response as a JSON object."

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful assistant that generates metadata for CAD assemblies."},
                {"role": "user", "content": prompt}
            ]
        )

        content = response.choices[0].message.content.strip()

        # Remove Markdown code block syntax if present
        content = re.sub(r'^```json\n|\n```$', '', content, flags=re.MULTILINE)

        try:
            metadata = json.loads(content)
            if metadata == {}:
                return None
            return metadata
        except json.JSONDecodeError as json_error:
            print(f"JSON parsing error: {str(json_error)}")
            print(f"Failed to parse JSON from content: {content}")
            return None

    except Exception as e:
        print(f"Error generating metadata: {str(e)}")
        return None

def get_bounding_box(shape):
    bbox = Bnd_Box()
    brepbndlib.Add(shape, bbox)
    return bbox

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

def get_shape_size(shape):
    bbox = Bnd_Box()
    brepbndlib.Add(shape, bbox)
    xmin, ymin, zmin, xmax, ymax, zmax = bbox.Get()
    diagonal = ((xmax - xmin) ** 2 + (ymax - ymin) ** 2 + (zmax - zmin) ** 2) ** 0.5
    return diagonal

def are_connected(shape1, shape2):
    """
    Check if two shapes are connected or in close proximity.

    :param shape1: First shape to check
    :param shape2: Second shape to check
    :return: True if shapes are connected, False otherwise
    """
    # Calculate dynamic tolerance based on shape sizes
    size1 = get_shape_size(shape1)
    size2 = get_shape_size(shape2)
    avg_size = (size1 + size2) / 2
    multiplier = 0.0001
    tolerance = min(avg_size * multiplier, 0.1)  # 0.01% of average size, max 0.1 mm

    dist_tool = BRepExtrema_DistShapeShape(shape1, shape2)
    if dist_tool.IsDone():
        if dist_tool.Value() <= tolerance:
            return True

    # If not touching, check if any vertices are close to each other
    def get_vertices(shape):
        vertices = []
        explorer = TopExp_Explorer(shape, TopAbs_VERTEX)
        while explorer.More():
            vertex = explorer.Current()
            point = BRep_Tool.Pnt(vertex)
            vertices.append((point.X(), point.Y(), point.Z()))
            explorer.Next()
        return vertices

    vertices1 = get_vertices(shape1)
    vertices2 = get_vertices(shape2)

    for v1 in vertices1:
        for v2 in vertices2:
            dist = ((v1[0] - v2[0]) ** 2 + (v1[1] - v2[1]) ** 2 + (v1[2] - v2[2]) ** 2) ** 0.5
            if dist <= tolerance:
                return True

    return False

def create_assembly_graph(parts, filename, pbar):
    G = nx.Graph()

    for name, shape in parts:
        G.add_node(name)

    for i, (name1, shape1) in enumerate(parts):
        for name2, shape2 in parts[i + 1:]:
            if are_connected(shape1, shape2):
                G.add_edge(name1, name2)
            pbar.update(1)

    return G

def save_graph(G, output_file):
    plt.figure(figsize=(20, 20))
    pos = nx.spring_layout(G, k=0.5, iterations=50)
    nx.draw(G, pos, with_labels=False, node_color='lightblue',
            node_size=3000, font_size=8, font_weight='bold')

    # Draw node labels
    nx.draw_networkx_labels(G, pos, font_size=6, font_weight='bold')

    plt.title("Assembly Graph", fontsize=16)
    plt.axis('off')
    plt.tight_layout()

    # Save as PDF
    plt.savefig(f"{output_file}.pdf", format="pdf", dpi=300, bbox_inches='tight')
    plt.close()

def save_hierarchical_graph(shape, output_file):
    G = nx.DiGraph()

    shell_explorer = TopExp_Explorer(shape, TopAbs_SHELL)
    face_explorer = TopExp_Explorer(shape, TopAbs_FACE)
    edge_explorer = TopExp_Explorer(shape, TopAbs_EDGE)

    shell_nodes = []
    face_nodes = []
    edge_nodes = []

    # Add shells to the graph
    while shell_explorer.More():
        shell = shell_explorer.Current()
        shell_id = f"Shell_{len(shell_nodes)}"
        G.add_node(shell_id, label=shell_id, shape_type="SHELL")
        shell_nodes.append((shell_id, shell))
        shell_explorer.Next()

    # Add faces to the graph and connect them to shells
    for shell_id, shell in shell_nodes:
        face_explorer.Init(shell, TopAbs_FACE)
        while face_explorer.More():
            face = face_explorer.Current()
            face_id = f"Face_{len(face_nodes)}"
            G.add_node(face_id, label=face_id, shape_type="FACE")
            face_nodes.append((face_id, face))
            G.add_edge(shell_id, face_id)
            face_explorer.Next()

    # Add edges to the graph and connect them to faces
    for face_id, face in face_nodes:
        edge_explorer.Init(face, TopAbs_EDGE)
        while edge_explorer.More():
            edge = edge_explorer.Current()
            edge_id = f"Edge_{len(edge_nodes)}"
            G.add_node(edge_id, label=edge_id, shape_type="EDGE")
            edge_nodes.append((edge_id, edge))
            G.add_edge(face_id, edge_id)
            edge_explorer.Next()

    # Save the graph as GraphML
    nx.write_graphml(G, output_file)

def setup_logging(output_folder):
    log_file = os.path.join(output_folder, 'processing_log.txt')
    logging.basicConfig(filename=log_file, level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s')

def worker_init(output_folder):
    setup_logging(output_folder)

def process_single_file(args):
    file_path, output_folder, skip_existing, generate_metadata_flag, generate_assembly, generate_hierarchical, save_pdf = args

    filename = os.path.basename(file_path)
    process_id = multiprocessing.current_process().pid

    logging.info(f"Process {process_id} started processing {filename}")

    name_without_extension = os.path.splitext(filename)[0]
    subfolder = os.path.join(output_folder, name_without_extension)

    if not os.path.exists(subfolder):
        os.makedirs(subfolder)

    try:
        logging.info(f"Process {process_id} reading STEP file: {filename}")
        parts, shape = read_step_file(file_path)

        if generate_assembly:
            if skip_existing:
                if os.path.exists(f"{subfolder}/{name_without_extension}_assembly.graphml"):
                    logging.info(f"Process {process_id} skipped assembly graph for {filename} (already exists)")
                    return f"{Fore.YELLOW} {filename} assembly graph already exists, skipping{Style.RESET_ALL}"
            logging.info(f"Process {process_id} creating assembly graph for {filename}")
            # Create assembly graph with progress bar
            total_comparisons = len(parts) * (len(parts) - 1) // 2
            with tqdm(total=total_comparisons, desc=f"{Fore.CYAN}{filename}{Style.RESET_ALL}",
                      unit="comp", leave=False, position=multiprocessing.current_process()._identity[0] - 1) as pbar:
                graph = create_assembly_graph(parts, filename, pbar)

            logging.info(f"Process {process_id} saving assembly graph for {filename}")
            nx.write_graphml(graph, f"{subfolder}/{name_without_extension}_assembly.graphml")

            if save_pdf:
                logging.info(f"Process {process_id} saving assembly graph as PDF for {filename}")
                save_graph(graph, f"{subfolder}/{name_without_extension}_assembly")

        if generate_hierarchical:
            if skip_existing:
                if os.path.exists(f"{subfolder}/{name_without_extension}_hierarchical.graphml"):
                    logging.info(f"Process {process_id} skipped hierarchical graph for {filename} (already exists)")
                    return f"{Fore.YELLOW} {filename} hierarchical graph already exists, skipping{Style.RESET_ALL}"
            # Save hierarchical graph
            logging.info(f"Process {process_id} saving hierarchical graph for {filename}")
            save_hierarchical_graph(shape, f"{subfolder}/{name_without_extension}_hierarchical.graphml")

        # Generate metadata if the flag is set
        metadata = None
        if generate_metadata_flag and len(parts) > 3:
            logging.info(f"Process {process_id} generating metadata for {filename}")
            product_names = [part[0] for part in parts]
            metadata = generate_metadata(product_names, filename)

        # Save metadata
        if metadata:
            logging.info(f"Process {process_id} saving metadata for {filename}")
            with open(f"{subfolder}/{name_without_extension}_metadata.json", 'w') as f:
                json.dump(metadata, f, indent=2)

        logging.info(f"Process {process_id} finished processing {filename}")
        return f"{Fore.GREEN}✔ {filename} processed successfully{Style.RESET_ALL}"

    except Exception as e:
        logging.error(f"Process {process_id} encountered an error processing {filename}: {str(e)}")
        return f"{Fore.RED} Error processing {filename}: {str(e)}{Style.RESET_ALL}"

def process_step_files(folder_path, output_folder, skip_existing, num_processes, generate_metadata_flag, generate_assembly, generate_hierarchical, save_pdf):
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    setup_logging(output_folder)

    logging.info(f"Starting to process files in {folder_path}")

    step_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) if f.lower().endswith(('.step', '.stp'))]

    print(f"{Fore.YELLOW}Processing {Fore.RED}{len(step_files)}{Style.RESET_ALL} files using {Fore.RED}{num_processes}{Style.RESET_ALL} processes{Style.RESET_ALL}")

    args_list = [(file_path, output_folder, skip_existing, generate_metadata_flag, generate_assembly, generate_hierarchical, save_pdf) for file_path in step_files]

    with multiprocessing.Pool(processes=num_processes, initializer=worker_init, initargs=(output_folder,)) as pool:
        results = list(tqdm(pool.imap(process_single_file, args_list), total=len(step_files), desc="Overall Progress"))

    logging.info("Finished processing all files")

    # Print results
    for result in results:
        print(result)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process STEP files and create assembly graphs.")
    parser.add_argument("step_files_folder", help="Folder containing STEP files")
    parser.add_argument("output_folder", help="Folder to save output files")
    parser.add_argument("--process-all", action="store_true", help="Process all files, including those already processed")
    parser.add_argument("--processes", type=int, default=max(1, multiprocessing.cpu_count() // 2),
                        help="Number of processes to use (default: number of CPUs / 2, minimum 1)")
    parser.add_argument("--max-performance", action="store_true",
                        help="Use all available CPU cores for maximum performance")
    parser.add_argument("--generate-metadata", action="store_true",
                        help="Generate metadata using OpenAI GPT")
    parser.add_argument("--log", action="store_true", help="Enable logging")
    parser.add_argument("--assembly", action="store_true", help="Generate assembly graph")
    parser.add_argument("--save-pdf", action="store_true", help="Save assembly graph as PDF (only works with --assembly)")
    parser.add_argument("--hierarchical", action="store_true", help="Generate hierarchical graph")
    args = parser.parse_args()

    step_files_folder = args.step_files_folder
    output_folder = args.output_folder
    skip_existing = not args.process_all  # Invert the flag
    if args.max_performance:
        num_processes = multiprocessing.cpu_count()
        print(f"{Fore.YELLOW}Warning: Using all {num_processes} CPU cores. This may affect system responsiveness.{Style.RESET_ALL}")
    else:
        num_processes = int(args.processes)

    if args.generate_metadata:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OpenAI API key not found in environment variables")

    if args.log:
        setup_logging(output_folder)
        logging.info("Logging enabled")
    else:
        logging.disable(logging.CRITICAL)  # Disable logging if not requested

    if not (args.assembly or args.hierarchical):
        parser.error("At least one of --assembly or --hierarchical must be specified")
        
    if args.save_pdf and not args.assembly:
        parser.error("Save PDF option requires assembly graph generation")

    try:
        process_step_files(step_files_folder, output_folder, skip_existing, num_processes, args.generate_metadata, args.assembly, args.hierarchical, args.save_pdf)
    except KeyboardInterrupt:
        logging.info("Process interrupted by user. Exiting gracefully...")
        print(f"\n{Fore.YELLOW}Process interrupted by user. Exiting gracefully...{Style.RESET_ALL}")
    finally:
        logging.info("Cleanup complete. Exiting.")
        print(f"\n{Fore.YELLOW}Cleanup complete. Exiting.{Style.RESET_ALL}")
