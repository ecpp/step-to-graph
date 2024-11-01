import os
import argparse
import logging
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
    parser.add_argument("--generate-metadata", action="store_true",
                        help="Generate metadata using OpenAI GPT")
    parser.add_argument("--images-metadata", action="store_true",
                        help="Generate metadata from images if it is not possible to generate using part names")
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
    parser.add_argument("--headless", action="store_true",
                        help="Run in headless mode")
    args = parser.parse_args()

    step_files_folder = args.input
    output_folder = args.output
    skip_existing = not args.process_all

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

    if args.save_pdf and not args.assembly:
        parser.error("Save PDF option requires assembly graph generation")

    if args.save_html and not args.assembly:
        parser.error("Save HTML option requires assembly graph generation")
        
    if args.images_metadata and not args.images:
        parser.error("Images metadata option requires images extraction")

    try:
        process_step_files(
            step_files_folder,
            output_folder,
            skip_existing,
            args.generate_metadata,
            args.assembly,
            args.hierarchical,
            args.save_pdf,
            args.save_html,
            no_self_connections=args.no_self_connections,
            generate_stats=args.stats,
            images=args.images,
            images_metadata=args.images_metadata,
            headless=args.headless
        )
    except KeyboardInterrupt:
        logging.info("Process interrupted by user. Exiting gracefully...")
        print(
            f"\n{Fore.YELLOW}Process interrupted by user. Exiting gracefully...{Style.RESET_ALL}")
    finally:
        logging.info("Cleanup complete. Exiting.")
        print(f"\n{Fore.YELLOW}Cleanup complete. Exiting.{Style.RESET_ALL}")