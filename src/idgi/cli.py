"""
Main CLI interface for idgi.
"""

import argparse
import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from .core.analyzer import CodebaseAnalyzer
from .export.formats import GraphExporter, export_analysis_results
from .graph.builder import GraphBuilder, GraphType
from .graph.interactive import InteractiveGraphExplorer
from .graph.visualizer import ASCIIGraphVisualizer


def setup_logging(verbose: bool = False) -> None:
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO

    logging.basicConfig(
        level=level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=Console(stderr=True), show_path=False)],
    )


def cmd_scan(args) -> None:
    """Handle scan subcommand."""
    console = Console()

    root_path = Path(args.directory).resolve()
    if not root_path.exists():
        console.print(f"[red]Directory not found: {root_path}[/red]")
        sys.exit(1)

    # Setup analyzer
    analyzer = CodebaseAnalyzer(exclude_patterns=args.exclude, max_workers=args.workers)

    # Perform analysis with progress indicator
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        scan_task = progress.add_task("Scanning codebase...", total=None)

        try:
            analysis_result = analyzer.analyze(root_path, recursive=args.recursive)
        except Exception as e:
            console.print(f"[red]Analysis failed: {e}[/red]")
            sys.exit(1)

        progress.remove_task(scan_task)

    # Display results
    scan_result = analysis_result.scan_result

    # Create summary table
    summary_table = Table(title="Scan Results")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Count", style="white")

    summary_table.add_row("Python files", str(scan_result.total_files))
    summary_table.add_row("Total lines", f"{scan_result.total_lines:,}")
    summary_table.add_row("Packages", str(len(scan_result.packages)))
    summary_table.add_row("Classes", str(analysis_result.total_classes))
    summary_table.add_row("Functions", str(analysis_result.total_functions))
    summary_table.add_row("Import statements", str(analysis_result.total_imports))

    if scan_result.errors:
        summary_table.add_row("Errors", f"[red]{len(scan_result.errors)}[/red]")

    console.print(summary_table)

    # Show package breakdown if requested
    if args.show_packages:
        console.print("\n")
        package_table = Table(title="Package Breakdown")
        package_table.add_column("Package", style="cyan")
        package_table.add_column("Modules", style="white")

        for package_name, modules in sorted(scan_result.packages.items()):
            package_table.add_row(package_name, str(len(modules)))

        console.print(package_table)

    # Show errors if any
    if scan_result.errors and args.show_errors:
        console.print("\n")
        error_table = Table(title="Errors")
        error_table.add_column("File", style="red")
        error_table.add_column("Error", style="white")

        for file_path, error in scan_result.errors[:10]:  # Show first 10 errors
            error_table.add_row(str(file_path), error)

        if len(scan_result.errors) > 10:
            error_table.add_row(
                "...", f"and {len(scan_result.errors) - 10} more errors"
            )

        console.print(error_table)


def cmd_graph(args) -> None:
    """Handle graph subcommand."""
    console = Console()

    root_path = Path(args.directory).resolve()
    if not root_path.exists():
        console.print(f"[red]Directory not found: {root_path}[/red]")
        sys.exit(1)

    # Setup analyzer
    analyzer = CodebaseAnalyzer(exclude_patterns=args.exclude, max_workers=args.workers)

    # Perform analysis
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing codebase...", total=None)

        try:
            analysis_result = analyzer.analyze(root_path, recursive=True)
        except Exception as e:
            console.print(f"[red]Analysis failed: {e}[/red]")
            sys.exit(1)

        progress.remove_task(task)

    # Build graph
    try:
        graph_type = GraphType(args.type)
    except ValueError:
        console.print(f"[red]Invalid graph type: {args.type}[/red]")
        console.print(f"Available types: {', '.join([t.value for t in GraphType])}")
        sys.exit(1)

    builder = GraphBuilder(analysis_result)
    graph = builder.build_graph(graph_type, max_nodes=args.max_nodes)

    if len(graph.nodes()) == 0:
        console.print("[yellow]No data found for this graph type[/yellow]")
        return

    # Handle interactive mode
    if args.interactive:
        explorer = InteractiveGraphExplorer(graph, args.type)
        explorer.run()
        return

    # Handle output file
    if args.output:
        exporter = GraphExporter()
        output_path = Path(args.output)

        success = exporter.export(
            graph=graph,
            output_path=output_path,
            title=f"{args.type.title()} Graph",
            max_nodes=args.max_nodes,
        )

        if success:
            console.print(f"[green]Graph exported to {output_path}[/green]")
        else:
            console.print("[red]Export failed[/red]")
            sys.exit(1)

        return

    # Show ASCII visualization
    visualizer = ASCIIGraphVisualizer(console)

    if args.format == "tree":
        output = visualizer.visualize_tree(graph, max_depth=args.depth)
    elif args.format == "network":
        output = visualizer.visualize_network(graph, max_nodes=args.max_nodes or 50)
    elif args.format == "hierarchy":
        output = visualizer.visualize_hierarchy(
            graph, title=f"{args.type.title()} Hierarchy"
        )
    else:
        output = visualizer.visualize_network(graph, max_nodes=args.max_nodes or 50)

    console.print(output)

    # Show statistics if requested
    if args.stats:
        stats_output = visualizer.create_summary_table(graph)
        console.print(stats_output)

        important_nodes = visualizer.find_important_nodes(graph, limit=10)
        console.print(important_nodes)


def cmd_search(args) -> None:
    """Handle search subcommand."""
    console = Console()

    root_path = Path(args.directory).resolve()
    if not root_path.exists():
        console.print(f"[red]Directory not found: {root_path}[/red]")
        sys.exit(1)

    # Setup analyzer
    analyzer = CodebaseAnalyzer(exclude_patterns=args.exclude)

    # Perform analysis
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing codebase...", total=None)
        analysis_result = analyzer.analyze(root_path)
        progress.remove_task(task)

    # Search through modules
    results = []
    search_term = args.term.lower()

    for file_path, module_info in analysis_result.modules.items():
        # Search in module name
        module_name = str(file_path.stem)
        if search_term in module_name.lower():
            results.append(("module", module_name, str(file_path), ""))

        # Search in classes
        for class_info in module_info.classes:
            if search_term in class_info.name.lower():
                results.append(
                    (
                        "class",
                        class_info.name,
                        str(file_path),
                        f"Line {class_info.line_start}",
                    )
                )

        # Search in functions
        for func_info in module_info.functions:
            if search_term in func_info.name.lower():
                results.append(
                    (
                        "function",
                        func_info.name,
                        str(file_path),
                        f"Line {func_info.line_start}",
                    )
                )

        # Search in methods
        for class_info in module_info.classes:
            for method_info in class_info.methods:
                if search_term in method_info.name.lower():
                    results.append(
                        (
                            "method",
                            f"{class_info.name}.{method_info.name}",
                            str(file_path),
                            f"Line {method_info.line_start}",
                        )
                    )

    if not results:
        console.print(f"[yellow]No results found for '{args.term}'[/yellow]")
        return

    # Display results
    search_table = Table(title=f"Search Results for '{args.term}'")
    search_table.add_column("Type", style="cyan")
    search_table.add_column("Name", style="white")
    search_table.add_column("File", style="blue")
    search_table.add_column("Location", style="green")

    for result_type, name, file_path, location in sorted(results)[: args.limit]:
        # Shorten file path for display
        short_path = (
            str(Path(file_path).relative_to(root_path))
            if len(file_path) > 50
            else file_path
        )
        search_table.add_row(result_type, name, short_path, location)

    if len(results) > args.limit:
        search_table.add_row(
            "...", f"({len(results) - args.limit} more results)", "", ""
        )

    console.print(search_table)


def cmd_export(args) -> None:
    """Handle export subcommand."""
    console = Console()

    root_path = Path(args.directory).resolve()
    if not root_path.exists():
        console.print(f"[red]Directory not found: {root_path}[/red]")
        sys.exit(1)

    output_dir = Path(args.output)

    # Handle default values for format and types if not provided
    formats = args.format if args.format else ["svg", "json"]
    graph_types = args.types if args.types else ["imports", "inheritance", "calls"]

    # Setup analyzer
    analyzer = CodebaseAnalyzer(exclude_patterns=args.exclude)

    # Perform analysis
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Analyzing codebase...", total=None)
        analysis_result = analyzer.analyze(root_path)
        progress.update(task, description="Exporting graphs...")

        # Export graphs
        results = export_analysis_results(
            analysis_result=analysis_result,
            output_dir=output_dir,
            formats=formats,
            graph_types=graph_types,
        )

        progress.remove_task(task)

    # Display results
    export_table = Table(title="Export Results")
    export_table.add_column("File", style="cyan")
    export_table.add_column("Status", style="white")

    for filename, success in results.items():
        status = "[green]✓ Success[/green]" if success else "[red]✗ Failed[/red]"
        export_table.add_row(filename, status)

    console.print(export_table)

    successful_exports = sum(1 for success in results.values() if success)
    console.print(
        f"\n[green]{successful_exports}/{len(results)} exports completed successfully[/green]"
    )

    if successful_exports > 0:
        console.print(f"Files saved to: [cyan]{output_dir}[/cyan]")


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="idgi",
        description="Explore and visualize large Python codebases",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  idgi scan ./my_project
  idgi graph --type imports --interactive ./my_project
  idgi search "DataLoader" ./my_project
  idgi export --format svg png --output ./graphs ./my_project
        """,
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument(
        "--workers", type=int, default=4, help="Number of worker processes"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Scan subcommand
    scan_parser = subparsers.add_parser(
        "scan", help="Scan directory and analyze Python files"
    )
    scan_parser.add_argument("directory", help="Directory to scan")
    scan_parser.add_argument("--exclude", action="append", help="Patterns to exclude")
    scan_parser.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Don't scan recursively",
    )
    scan_parser.add_argument(
        "--show-packages", action="store_true", help="Show package breakdown"
    )
    scan_parser.add_argument(
        "--show-errors", action="store_true", help="Show parsing errors"
    )

    # Graph subcommand
    graph_parser = subparsers.add_parser("graph", help="Generate and display graphs")
    graph_parser.add_argument("directory", help="Directory to analyze")
    graph_parser.add_argument(
        "--type",
        choices=[t.value for t in GraphType],
        default="imports",
        help="Type of graph to generate",
    )
    graph_parser.add_argument(
        "--format",
        choices=["tree", "network", "hierarchy"],
        default="network",
        help="Display format",
    )
    graph_parser.add_argument(
        "--output", help="Output file (exports to file instead of display)"
    )
    graph_parser.add_argument(
        "--interactive", "-i", action="store_true", help="Interactive exploration mode"
    )
    graph_parser.add_argument("--max-nodes", type=int, help="Maximum nodes to display")
    graph_parser.add_argument(
        "--depth", type=int, default=3, help="Tree depth for tree format"
    )
    graph_parser.add_argument(
        "--stats", action="store_true", help="Show graph statistics"
    )
    graph_parser.add_argument("--exclude", action="append", help="Patterns to exclude")

    # Search subcommand
    search_parser = subparsers.add_parser(
        "search", help="Search for classes, functions, modules"
    )
    search_parser.add_argument("term", help="Search term")
    search_parser.add_argument("directory", help="Directory to search")
    search_parser.add_argument(
        "--limit", type=int, default=50, help="Maximum results to show"
    )
    search_parser.add_argument("--exclude", action="append", help="Patterns to exclude")

    # Export subcommand
    export_parser = subparsers.add_parser("export", help="Export graphs to files")
    export_parser.add_argument("directory", help="Directory to analyze")
    export_parser.add_argument("--output", required=True, help="Output directory")
    export_parser.add_argument(
        "--format",
        action="append",
        choices=["svg", "png", "pdf", "json", "dot", "gml", "graphml"],
        help="Export formats",
    )
    export_parser.add_argument(
        "--types",
        action="append",
        choices=[t.value for t in GraphType],
        help="Graph types to export",
    )
    export_parser.add_argument("--exclude", action="append", help="Patterns to exclude")

    return parser


def main() -> None:
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    if not args.command:
        parser.print_help()
        sys.exit(1)

    console = Console()

    try:
        if args.command == "scan":
            cmd_scan(args)
        elif args.command == "graph":
            cmd_graph(args)
        elif args.command == "search":
            cmd_search(args)
        elif args.command == "export":
            cmd_export(args)
        else:
            console.print(f"[red]Unknown command: {args.command}[/red]")
            parser.print_help()
            sys.exit(1)

    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted by user[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        if args.verbose:
            console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    main()
