"""
Export functionality for graphs to various formats (SVG, PNG, etc.).
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Union

import networkx as nx

from ..core.analyzer import AnalysisResult
from ..graph.visualizer import HAS_GRAPHVIZ, GraphvizRenderer


class GraphExporter:
    """
    Handles exporting graphs to various formats.
    """

    SUPPORTED_FORMATS = {
        "svg": "Scalable Vector Graphics",
        "png": "Portable Network Graphics",
        "pdf": "Portable Document Format",
        "dot": "Graphviz DOT format",
        "json": "JSON graph data",
        "gml": "Graph Modeling Language",
        "graphml": "GraphML format",
    }

    def __init__(self) -> None:
        """Initialize the exporter."""
        self.graphviz_renderer = None
        if HAS_GRAPHVIZ:
            self.graphviz_renderer = GraphvizRenderer()

    def export(
        self,
        graph: nx.DiGraph,
        output_path: Union[str, Path],
        format_type: Optional[str] = None,
        title: Optional[str] = None,
        layout: str = "dot",
        node_colors: Optional[Dict[str, str]] = None,
        max_nodes: Optional[int] = None,
        include_attributes: bool = True,
    ) -> bool:
        """
        Export graph to specified format.

        Args:
            graph: NetworkX directed graph to export
            output_path: Output file path
            format_type: Export format (if None, inferred from file extension)
            title: Graph title for visual formats
            layout: Layout algorithm for visual formats
            node_colors: Custom node colors for visual formats
            max_nodes: Maximum nodes to include (for large graphs)
            include_attributes: Whether to include node/edge attributes

        Returns:
            True if export successful, False otherwise
        """
        output_path = Path(output_path)

        if format_type is None:
            format_type = output_path.suffix.lstrip(".")

        if format_type not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported format: {format_type}. Supported: {list(self.SUPPORTED_FORMATS.keys())}"
            )

        # Limit graph size if requested
        export_graph = self._limit_graph_size(graph, max_nodes) if max_nodes else graph

        try:
            if format_type in ["svg", "png", "pdf"]:
                return self._export_visual(
                    export_graph, output_path, format_type, title, layout, node_colors
                )
            elif format_type == "dot":
                return self._export_dot(export_graph, output_path, title)
            elif format_type == "json":
                return self._export_json(export_graph, output_path, include_attributes)
            elif format_type == "gml":
                return self._export_gml(export_graph, output_path, include_attributes)
            elif format_type == "graphml":
                return self._export_graphml(
                    export_graph, output_path, include_attributes
                )
            else:
                raise ValueError(
                    f"Export method not implemented for format: {format_type}"
                )

        except Exception as e:
            print(f"Export failed: {e}")
            return False

    def _export_visual(
        self,
        graph: nx.DiGraph,
        output_path: Path,
        format_type: str,
        title: Optional[str],
        layout: str,
        node_colors: Optional[Dict[str, str]],
    ) -> bool:
        """Export to visual formats using Graphviz."""
        if not self.graphviz_renderer:
            raise RuntimeError(
                "Graphviz not available. Install with: pip install graphviz"
            )

        # Render graph
        output_data = self.graphviz_renderer.render_graph(
            graph=graph,
            output_format=format_type,
            layout=layout,
            title=title,
            node_colors=node_colors,
        )

        # Write to file
        if format_type == "svg":
            # SVG is text format
            output_path.write_text(output_data, encoding="utf-8")
        else:
            # PNG, PDF are binary formats
            output_path.write_bytes(
                output_data.encode("utf-8")
                if isinstance(output_data, str)
                else output_data
            )

        return True

    def _export_dot(
        self, graph: nx.DiGraph, output_path: Path, title: Optional[str]
    ) -> bool:
        """Export to Graphviz DOT format."""
        dot_content = self._generate_dot_content(graph, title)
        output_path.write_text(dot_content, encoding="utf-8")
        return True

    def _export_json(
        self, graph: nx.DiGraph, output_path: Path, include_attributes: bool
    ) -> bool:
        """Export to JSON format."""
        if include_attributes:
            graph_data = nx.node_link_data(graph)
        else:
            # Create simplified version without attributes
            graph_data = {
                "directed": True,
                "nodes": [{"id": node} for node in graph.nodes()],
                "links": [{"source": u, "target": v} for u, v in graph.edges()],
            }

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(graph_data, f, indent=2, default=str)

        return True

    def _export_gml(
        self, graph: nx.DiGraph, output_path: Path, include_attributes: bool
    ) -> bool:
        """Export to GML format."""
        # Clean graph attributes for GML compatibility
        export_graph = graph.copy()

        if not include_attributes:
            # Remove all attributes
            for node in export_graph.nodes():
                export_graph.nodes[node].clear()
            for u, v in export_graph.edges():
                export_graph.edges[u, v].clear()
        else:
            # Ensure all attributes are JSON-serializable strings
            for node in export_graph.nodes():
                for key, value in list(export_graph.nodes[node].items()):
                    if not isinstance(value, (str, int, float, bool)):
                        export_graph.nodes[node][key] = str(value)

            for u, v in export_graph.edges():
                for key, value in list(export_graph.edges[u, v].items()):
                    if not isinstance(value, (str, int, float, bool)):
                        export_graph.edges[u, v][key] = str(value)

        nx.write_gml(export_graph, output_path)
        return True

    def _export_graphml(
        self, graph: nx.DiGraph, output_path: Path, include_attributes: bool
    ) -> bool:
        """Export to GraphML format."""
        export_graph = graph.copy()

        if not include_attributes:
            # Remove all attributes
            for node in export_graph.nodes():
                export_graph.nodes[node].clear()
            for u, v in export_graph.edges():
                export_graph.edges[u, v].clear()
        else:
            # Ensure all attributes are strings for GraphML compatibility
            for node in export_graph.nodes():
                for key, value in list(export_graph.nodes[node].items()):
                    export_graph.nodes[node][key] = str(value)

            for u, v in export_graph.edges():
                for key, value in list(export_graph.edges[u, v].items()):
                    export_graph.edges[u, v][key] = str(value)

        nx.write_graphml(export_graph, output_path)
        return True

    def _limit_graph_size(self, graph: nx.DiGraph, max_nodes: int) -> nx.DiGraph:
        """Limit graph to most important nodes."""
        if len(list(graph.nodes())) <= max_nodes:
            return graph

        # Use degree centrality to select most important nodes
        try:
            centrality = nx.degree_centrality(graph)
            top_nodes = sorted(centrality.items(), key=lambda x: x[1], reverse=True)[
                :max_nodes
            ]
            selected_nodes = [node for node, _ in top_nodes]
            return graph.subgraph(selected_nodes).copy()
        except Exception:
            # Fallback: select first max_nodes
            return graph.subgraph(list(graph.nodes())[:max_nodes]).copy()

    def _generate_dot_content(
        self, graph: nx.DiGraph, title: Optional[str] = None
    ) -> str:
        """Generate DOT format content."""
        lines = ["digraph G {"]

        if title:
            lines.append(f'  label="{title}";')
            lines.append('  labelloc="t";')

        # Add default graph attributes
        lines.append('  rankdir="TB";')
        lines.append('  node [shape=box, style="rounded,filled", fillcolor=lightblue];')
        lines.append("  edge [fontsize=8];")
        lines.append("")

        # Add nodes
        for node in graph.nodes():
            node_data = graph.nodes[node]
            label = self._escape_dot_string(str(node))

            # Add node attributes
            attrs = [f'label="{label}"']

            node_type = node_data.get("type")
            if node_type:
                color = self._get_type_color(node_type)
                attrs.append(f'fillcolor="{color}"')

            if node_data.get("external", False):
                attrs.append('style="dashed,filled"')

            attrs_str = ", ".join(attrs)
            node_id = self._escape_dot_id(node)
            lines.append(f"  {node_id} [{attrs_str}];")

        lines.append("")

        # Add edges
        for source, target in graph.edges():
            edge_data = graph.edges[source, target]
            relationship = edge_data.get("relationship", "")

            source_id = self._escape_dot_id(source)
            target_id = self._escape_dot_id(target)

            attrs = []
            if relationship:
                attrs.append(f'label="{self._escape_dot_string(relationship)}"')

            # Style edges based on relationship
            if relationship == "inherits_from":
                attrs.extend(["color=blue", "arrowhead=empty"])
            elif relationship == "imports":
                attrs.extend(["color=green", "style=dashed"])
            elif relationship == "calls":
                attrs.append("color=red")

            attrs_str = f" [{', '.join(attrs)}]" if attrs else ""
            lines.append(f"  {source_id} -> {target_id}{attrs_str};")

        lines.append("}")
        return "\n".join(lines)

    def _get_type_color(self, node_type: str) -> str:
        """Get color for node type."""
        type_colors = {
            "module": "lightblue",
            "internal_module": "lightgreen",
            "external_module": "lightgray",
            "class": "lightcoral",
            "function": "lightyellow",
            "method": "lightcyan",
        }
        return type_colors.get(node_type, "lightgray")

    def _escape_dot_string(self, text: str) -> str:
        """Escape string for DOT format."""
        return text.replace('"', '\\"').replace("\n", "\\n")

    def _escape_dot_id(self, node_id: str) -> str:
        """Escape node ID for DOT format."""
        # Simple approach: quote if contains special characters
        if any(c in node_id for c in " .-/\\()[]{}"):
            return f'"{self._escape_dot_string(node_id)}"'
        return node_id

    @classmethod
    def list_formats(cls) -> Dict[str, str]:
        """List supported export formats."""
        return cls.SUPPORTED_FORMATS.copy()

    @classmethod
    def is_format_supported(cls, format_type: str) -> bool:
        """Check if format is supported."""
        return format_type in cls.SUPPORTED_FORMATS


def export_analysis_results(
    analysis_result: AnalysisResult,
    output_dir: Union[str, Path],
    formats: Optional[List[str]] = None,
    graph_types: Optional[List[str]] = None,
) -> Dict[str, bool]:
    """
    Export multiple graph types from analysis results.

    Args:
        analysis_result: AnalysisResult object from CodebaseAnalyzer
        output_dir: Directory to save exports
        formats: List of formats to export (default: ['svg', 'json'])
        graph_types: List of graph types to export (default: all)

    Returns:
        Dictionary mapping export file names to success status
    """
    from ..graph.builder import GraphBuilder, GraphType

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if formats is None:
        formats = ["svg", "json"]

    if graph_types is None:
        graph_types = ["imports", "inheritance", "calls", "modules"]

    builder = GraphBuilder(analysis_result)
    exporter = GraphExporter()
    results = {}

    for graph_type_name in graph_types:
        try:
            graph_type = GraphType(graph_type_name)
            graph = builder.build_graph(
                graph_type, max_nodes=100
            )  # Limit for performance

            for format_type in formats:
                filename = f"{graph_type_name}_graph.{format_type}"
                output_path = output_dir / filename

                success = exporter.export(
                    graph=graph,
                    output_path=output_path,
                    format_type=format_type,
                    title=f"{graph_type_name.title()} Graph",
                )

                results[filename] = success

        except Exception as e:
            print(f"Failed to export {graph_type_name} graph: {e}")
            for format_type in formats:
                filename = f"{graph_type_name}_graph.{format_type}"
                results[filename] = False

    return results
