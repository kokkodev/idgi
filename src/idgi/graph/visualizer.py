"""
Graph visualization for terminal (ASCII) output and Graphviz export.
"""

from io import StringIO
from typing import Any, Dict, Optional, Set, cast

import networkx as nx
from rich.console import Console
from rich.table import Table
from rich.tree import Tree

try:
    import graphviz

    HAS_GRAPHVIZ = True
except ImportError:
    HAS_GRAPHVIZ = False


class ASCIIGraphVisualizer:
    """
    Creates ASCII art representations of graphs for terminal display.
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize the visualizer.

        Args:
            console: Rich console for styled output (optional)
        """
        self.console = console or Console()

    def visualize_tree(
        self,
        graph: nx.DiGraph,
        root_node: Optional[str] = None,
        max_depth: int = 3,
        max_children: int = 10,
    ) -> str:
        """
        Visualize a directed graph as a tree structure.

        Args:
            graph: NetworkX directed graph
            root_node: Root node to start from (if None, finds best root)
            max_depth: Maximum depth to display
            max_children: Maximum children per node to show

        Returns:
            String representation of the tree
        """
        if not graph.nodes():
            return "Empty graph"

        # Find root node if not specified
        if root_node is None:
            root_node = self._find_root_node(graph)

        if root_node not in graph.nodes():
            root_node = list(graph.nodes())[0]

        # Build tree structure
        tree = Tree(f"[bold blue]{self._format_node(root_node, graph)}[/bold blue]")
        self._add_tree_children(
            tree, graph, root_node, max_depth - 1, max_children, set()
        )

        # Render to string
        string_io = StringIO()
        console = Console(file=string_io, width=120)
        console.print(tree)
        return string_io.getvalue()

    def visualize_network(
        self, graph: nx.DiGraph, layout: str = "spring", max_nodes: int = 50
    ) -> str:
        """
        Create ASCII network visualization.

        Args:
            graph: NetworkX directed graph
            layout: Layout algorithm (not used in ASCII, for compatibility)
            max_nodes: Maximum nodes to display

        Returns:
            String representation of the network
        """
        if len(graph.nodes()) > max_nodes:
            # Show only most connected nodes
            centrality = nx.degree_centrality(graph)
            top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[
                :max_nodes
            ]
            subgraph = graph.subgraph([node for node, _ in top_nodes])
        else:
            subgraph = graph

        output = StringIO()
        output.write(
            f"Network Graph ({len(subgraph.nodes())} nodes, {len(subgraph.edges())} edges)\n"
        )
        output.write("=" * 60 + "\n\n")

        # Group nodes by type if available
        node_types: Dict[str, list[str]] = {}
        for node in subgraph.nodes():
            node_type = subgraph.nodes[node].get("type", "unknown")
            if node_type not in node_types:
                node_types[node_type] = []
            node_types[node_type].append(node)

        for node_type, nodes in node_types.items():
            output.write(f"[{node_type.upper()}]\n")
            for node in sorted(nodes)[:20]:  # Limit per type
                # Show connections
                in_degree = subgraph.in_degree(node)
                out_degree = subgraph.out_degree(node)

                connections = []
                if out_degree > 0:
                    successors = list(subgraph.successors(node))[:5]  # Limit display
                    connections.append(f"→ {', '.join(successors)}")

                if in_degree > 0:
                    predecessors = list(subgraph.predecessors(node))[
                        :5
                    ]  # Limit display
                    connections.append(f"← {', '.join(predecessors)}")

                connection_str = " | ".join(connections) if connections else "isolated"
                output.write(
                    f"  {node:30} (in:{in_degree:2}, out:{out_degree:2}) {connection_str}\n"
                )

            output.write("\n")

        return output.getvalue()

    def visualize_hierarchy(self, graph: nx.DiGraph, title: str = "Hierarchy") -> str:
        """
        Visualize as a hierarchy with indentation.

        Args:
            graph: NetworkX directed graph
            title: Title for the hierarchy

        Returns:
            String representation of the hierarchy
        """
        output = StringIO()
        output.write(f"{title}\n")
        output.write("=" * len(title) + "\n\n")

        # Find root nodes (nodes with no predecessors)
        roots = [node for node in graph.nodes() if graph.in_degree(node) == 0]

        if not roots:
            # Graph has cycles, pick nodes with lowest in-degree
            min_in_degree = min(graph.in_degree(node) for node in graph.nodes())
            roots = [
                node for node in graph.nodes() if graph.in_degree(node) == min_in_degree
            ]

        visited: Set[str] = set()

        for root in sorted(roots):
            if root not in visited:
                self._write_hierarchy_node(output, graph, root, 0, visited)

        # Handle remaining nodes (in case of disconnected components)
        remaining = set(graph.nodes()) - visited
        if remaining:
            output.write("\n[Disconnected Components]\n")
            for node in sorted(remaining):
                if node not in visited:
                    self._write_hierarchy_node(output, graph, node, 0, visited)

        return output.getvalue()

    def create_summary_table(self, graph: nx.DiGraph) -> str:
        """
        Create a summary table of graph statistics.

        Args:
            graph: NetworkX directed graph

        Returns:
            String representation of the summary table
        """
        table = Table(title="Graph Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        # Basic metrics
        num_nodes = len(graph.nodes())
        num_edges = len(graph.edges())

        table.add_row("Nodes", str(num_nodes))
        table.add_row("Edges", str(num_edges))

        if num_nodes > 0:
            # Density
            density = nx.density(graph)
            table.add_row("Density", f"{density:.3f}")

            # Connected components
            try:
                num_components = nx.number_weakly_connected_components(graph)
                table.add_row("Connected Components", str(num_components))

                # Cycles
                cycles = list(nx.simple_cycles(graph))
                table.add_row("Cycles", str(len(cycles)))
            except Exception:
                pass

            # Node types (if available)
            node_types: Dict[str, int] = {}
            for node in graph.nodes():
                node_type = graph.nodes[node].get("type", "unknown")
                node_types[node_type] = node_types.get(node_type, 0) + 1

            for node_type, count in sorted(node_types.items()):
                table.add_row(f"{node_type.title()} Nodes", str(count))

        string_io = StringIO()
        console = Console(file=string_io)
        console.print(table)
        return string_io.getvalue()

    def find_important_nodes(self, graph: nx.DiGraph, limit: int = 10) -> str:
        """
        Find and display the most important nodes in the graph.

        Args:
            graph: NetworkX directed graph
            limit: Maximum number of nodes to show

        Returns:
            String representation of important nodes
        """
        if len(graph.nodes()) == 0:
            return "No nodes in graph"

        table = Table(title=f"Top {limit} Most Important Nodes")
        table.add_column("Rank", style="cyan")
        table.add_column("Node", style="white")
        table.add_column("In-Degree", style="green")
        table.add_column("Out-Degree", style="red")
        table.add_column("Total Degree", style="yellow")

        # Calculate centrality metrics
        try:
            degree_centrality = nx.degree_centrality(graph)
            # Sort by total degree (centrality)
            sorted_nodes = sorted(
                degree_centrality.items(), key=lambda x: x[1], reverse=True
            )
        except Exception:
            # Fallback to simple degree count
            degrees = [(node, graph.degree(node)) for node in graph.nodes()]
            sorted_nodes = sorted(degrees, key=lambda x: x[1], reverse=True)

        for i, (node, _) in enumerate(sorted_nodes[:limit], 1):
            in_deg = graph.in_degree(node)
            out_deg = graph.out_degree(node)
            total_deg = in_deg + out_deg

            table.add_row(
                str(i),
                self._format_node_name(node),
                str(in_deg),
                str(out_deg),
                str(total_deg),
            )

        string_io = StringIO()
        console = Console(file=string_io)
        console.print(table)
        return string_io.getvalue()

    def _find_root_node(self, graph: nx.DiGraph) -> str:
        """Find the best root node for tree visualization."""
        # Prefer nodes with no incoming edges
        roots = [node for node in graph.nodes() if graph.in_degree(node) == 0]

        if roots:
            # If multiple roots, pick the one with most outgoing connections
            return cast(str, max(roots, key=lambda n: graph.out_degree(n)))

        # If no clear root, pick node with highest out-degree
        return cast(str, max(graph.nodes(), key=lambda n: graph.out_degree(n)))

    def _add_tree_children(
        self,
        tree: Tree,
        graph: nx.DiGraph,
        node: str,
        depth: int,
        max_children: int,
        visited: Set[str],
    ) -> None:
        """Recursively add children to tree visualization."""
        if depth <= 0 or node in visited:
            return

        visited.add(node)
        children = list(graph.successors(node))[:max_children]

        for child in children:
            child_label = self._format_node(child, graph)

            if child in visited:
                # Show circular reference
                child_tree = tree.add(f"[dim]{child_label} (circular)[/dim]")
            else:
                child_tree = tree.add(child_label)
                self._add_tree_children(
                    child_tree, graph, child, depth - 1, max_children, visited
                )

        # Show if there are more children
        if len(list(graph.successors(node))) > max_children:
            remaining = len(list(graph.successors(node))) - max_children
            tree.add(f"[dim]... and {remaining} more[/dim]")

    def _format_node(self, node: str, graph: nx.DiGraph) -> str:
        """Format a node for display with additional information."""
        node_data = graph.nodes[node]

        # Basic node name
        display_name = self._format_node_name(node)

        # Add type information if available
        node_type = node_data.get("type")
        if node_type:
            display_name = f"[{node_type}] {display_name}"

        # Add additional info based on type
        if node_type == "class":
            methods = node_data.get("methods", 0)
            if methods:
                display_name += f" ({methods} methods)"
        elif node_type == "function":
            is_async = node_data.get("is_async", False)
            if is_async:
                display_name = f"async {display_name}"
        elif node_type in ["module", "internal_module"]:
            loc = node_data.get("lines_of_code", 0)
            if loc:
                display_name += f" ({loc} lines)"

        return display_name

    def _format_node_name(self, node: str, max_length: int = 40) -> str:
        """Format node name for display, truncating if too long."""
        if len(node) <= max_length:
            return node

        # Try to show the most relevant part
        if "." in node:
            parts = node.split(".")
            if len(parts[-1]) <= max_length - 3:
                return f"...{parts[-1]}"

        # Truncate with ellipsis
        return node[: max_length - 3] + "..."

    def _write_hierarchy_node(
        self,
        output: StringIO,
        graph: nx.DiGraph,
        node: str,
        indent: int,
        visited: Set[str],
    ) -> None:
        """Write a node and its children to hierarchy output."""
        if node in visited:
            return

        visited.add(node)

        # Write current node
        indent_str = "  " * indent
        node_info = self._format_node(node, graph)
        output.write(f"{indent_str}{node_info}\n")

        # Write children
        children = sorted(graph.successors(node))
        for child in children:
            self._write_hierarchy_node(output, graph, child, indent + 1, visited)


class GraphvizRenderer:
    """
    Renders graphs using Graphviz for high-quality output.
    """

    def __init__(self) -> None:
        """Initialize the Graphviz renderer."""
        if not HAS_GRAPHVIZ:
            raise ImportError(
                "Graphviz is not installed. Install with: pip install graphviz"
            )

        self.default_node_attrs = {
            "shape": "box",
            "style": "rounded,filled",
            "fillcolor": "lightblue",
            "fontname": "Arial",
            "fontsize": "10",
        }

        self.default_edge_attrs = {"fontname": "Arial", "fontsize": "8"}

    def render_graph(
        self,
        graph: nx.DiGraph,
        output_format: str = "svg",
        layout: str = "dot",
        title: Optional[str] = None,
        node_colors: Optional[Dict[str, str]] = None,
        max_label_length: int = 30,
    ) -> str:
        """
        Render graph using Graphviz.

        Args:
            graph: NetworkX directed graph
            output_format: Output format ('svg', 'png', 'pdf', etc.)
            layout: Graphviz layout engine ('dot', 'neato', 'fdp', etc.)
            title: Graph title
            node_colors: Dictionary mapping node types to colors
            max_label_length: Maximum label length before truncation

        Returns:
            Rendered graph as string (or bytes for binary formats)
        """
        dot = graphviz.Digraph(engine=layout)
        dot.attr(rankdir="TB", splines="ortho")

        if title:
            dot.attr(label=title, labelloc="t", fontsize="16", fontname="Arial Bold")

        # Set default colors for node types
        type_colors = {
            "module": "lightblue",
            "internal_module": "lightgreen",
            "external_module": "lightgray",
            "class": "lightcoral",
            "function": "lightyellow",
            "method": "lightcyan",
        }
        if node_colors:
            type_colors.update(node_colors)

        # Add nodes
        for node in graph.nodes():
            node_data = graph.nodes[node]
            node_type = node_data.get("type", "unknown")

            # Format label
            label = self._format_graphviz_label(node, node_data, max_label_length)

            # Set node attributes
            attrs = self.default_node_attrs.copy()
            attrs["fillcolor"] = type_colors.get(node_type, "lightgray")
            attrs["label"] = label

            # Add special styling based on node properties
            if node_data.get("external", False):
                attrs["style"] = "dashed,filled"
            elif node_data.get("has_errors", False):
                attrs["fillcolor"] = "lightpink"

            dot.node(node, **attrs)

        # Add edges
        for source, target in graph.edges():
            edge_data = graph.edges[source, target]
            relationship = edge_data.get("relationship", "")

            edge_attrs = self.default_edge_attrs.copy()
            if relationship:
                edge_attrs["label"] = relationship

            # Style edges based on relationship type
            if relationship == "inherits_from":
                edge_attrs["color"] = "blue"
                edge_attrs["arrowhead"] = "empty"
            elif relationship == "imports":
                edge_attrs["color"] = "green"
                edge_attrs["style"] = "dashed"
            elif relationship == "calls":
                edge_attrs["color"] = "red"

            dot.edge(source, target, **edge_attrs)

        return cast(
            str,
            dot.pipe(
                format=output_format,
                encoding="utf-8" if output_format in ["svg", "dot"] else None,
            ),
        )

    def _format_graphviz_label(
        self, node: str, node_data: Dict[str, str], max_length: int
    ) -> str:
        """Format node label for Graphviz display."""
        # Start with node name
        name = node
        if len(name) > max_length:
            # Try to keep the most relevant part
            if "." in name:
                parts = name.split(".")
                name = parts[-1]
                if len(name) > max_length:
                    name = name[: max_length - 3] + "..."
            else:
                name = name[: max_length - 3] + "..."

        # Add type prefix
        node_type = node_data.get("type", "")
        if node_type:
            label = f"[{node_type}]\\n{name}"
        else:
            label = name

        # Add additional information
        info_lines = []

        if node_type == "class":
            methods = node_data.get("methods", 0)
            if methods:
                info_lines.append(f"{methods} methods")
        elif node_type in ["module", "internal_module"]:
            loc = node_data.get("lines_of_code", 0)
            classes = node_data.get("num_classes", 0)
            functions = node_data.get("num_functions", 0)

            if loc:
                info_lines.append(f"{loc} lines")
            if classes:
                info_lines.append(f"{classes} classes")
            if functions:
                info_lines.append(f"{functions} functions")
        elif node_type == "function":
            if node_data.get("is_async", False):
                info_lines.append("async")
            args: Any = node_data.get("args", [])
            if isinstance(args, list):
                if args:
                    info_lines.append(f"({len(args)} args)")

        if info_lines:
            label += "\\n" + "\\n".join(info_lines)

        return label
