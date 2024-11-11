import os
import argparse
import logging
import multiprocessing
from colorama import init, Fore, Style

from workers import process_step_files
from utils.logging_utils import setup_logging

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process STEP files and create assembly graphs.")
    parser.add_argument("--input", required=True,
                        help="Folder containing STEP files")
    parser.add_argument("--output", required=True,
                        help="Folder to save output files")
    parser.add_argument("--process-all", action="store_true",
                        help="Process all files, including those already processed")
    parser.add_argument("--processes", type=int, default=max(1, multiprocessing.cpu_count() // 2),
                        help="Number of processes to use (default: number of CPUs / 2, minimum 1)")
    parser.add_argument("--max-performance", action="store_true",
                        help="Use all available CPU cores for maximum performance")
    parser.add_argument("--generate-metadata", action="store_true",
                        help="Generate metadata using OpenAI GPT")
    parser.add_argument("--log", action="store_true", help="Enable logging")
    parser.add_argument("--assembly", action="store_true",
                        help="Generate assembly graph")
    parser.add_argument("--save-pdf", action="store_true",
                        help="Save assembly graph as PDF (only works with --assembly)")
    parser.add_argument("--save-html", action="store_true",
                        help="Save assembly graph as interactive HTML (only works with --assembly)")
    parser.add_argument("--hierarchical", action="store_true",
                        help="Generate hierarchical graph")
    parser.add_argument("--no-self-connections", action="store_true",
                        help="Disable self-connections in the assembly graph")
    parser.add_argument("--stats", action="store_true",
                        help="Generate statistics for STEP files")
    parser.add_argument("--images", action="store_true",
                        help="Save images of parts in the assembly graph")
    parser.add_argument("--only-full-assembly", action="store_true",
                        help="Only save full assembly image")

    args = parser.parse_args()

    step_files_folder = args.input
    output_folder = args.output
    skip_existing = not args.process_all
    if args.max_performance:
        num_processes = multiprocessing.cpu_count()
        print(
            f"{Fore.YELLOW}Warning: Using all {num_processes} CPU cores. This may affect system responsiveness.{Style.RESET_ALL}")
    else:
        num_processes = int(args.processes)

    if args.generate_metadata:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "OpenAI API key not found in environment variables")

    if args.log:
        setup_logging(output_folder)
        logging.info("Logging enabled")
    else:
        logging.disable(logging.CRITICAL)

    if not (args.assembly or args.hierarchical):
        parser.error(
            "At least one of --assembly or --hierarchical must be specified")

    if args.save_pdf and not args.assembly:
        parser.error("Save PDF option requires assembly graph generation")

    if args.save_html and not args.assembly:
        parser.error("Save HTML option requires assembly graph generation")
        
    if args.only_full_assembly and not args.images:
        parser.error("Only full assembly option requires image generation")

    try:
        process_step_files(
            step_files_folder,
            output_folder,
            skip_existing,
            num_processes,
            args.generate_metadata,
            args.assembly,
            args.hierarchical,
            args.save_pdf,
            args.save_html,  # Pass the new argument
            no_self_connections=args.no_self_connections,
            generate_stats=args.stats,
            images=args.images,
            only_full_assembly=args.only_full_assembly
        )
    except KeyboardInterrupt:
        logging.info("Process interrupted by user. Exiting gracefully...")
        print(
            f"\n{Fore.YELLOW}Process interrupted by user. Exiting gracefully...{Style.RESET_ALL}")
    finally:
        logging.info("Cleanup complete. Exiting.")
        print(f"\n{Fore.YELLOW}Cleanup complete. Exiting.{Style.RESET_ALL}")