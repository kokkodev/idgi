"""
NetworkX graph construction for different types of code relationships.
"""

from enum import Enum
from typing import Dict, List, Optional

import networkx as nx

from ..core.analyzer import AnalysisResult
from ..core.parser import ClassInfo, FunctionInfo, ModuleInfo


class GraphType(Enum):
    """Types of graphs that can be built."""

    IMPORTS = "imports"
    INHERITANCE = "inheritance"
    CALLS = "calls"
    MODULES = "modules"
    CLASSES = "classes"
    FUNCTIONS = "functions"


class GraphBuilder:
    """
    Builds NetworkX graphs from codebase analysis results.
    """

    def __init__(self, analysis_result: AnalysisResult):
        """
        Initialize graph builder with analysis results.

        Args:
            analysis_result: Results from CodebaseAnalyzer
        """
        self.analysis_result = analysis_result

    def build_graph(
        self,
        graph_type: GraphType,
        include_external: bool = False,
        max_nodes: Optional[int] = None,
    ) -> nx.DiGraph:
        """
        Build a specific type of graph.

        Args:
            graph_type: Type of graph to build
            include_external: Whether to include external dependencies
            max_nodes: Maximum number of nodes to include (for large graphs)

        Returns:
            NetworkX directed graph
        """
        if graph_type == GraphType.IMPORTS:
            return self._build_import_graph(include_external, max_nodes)
        elif graph_type == GraphType.INHERITANCE:
            return self._build_inheritance_graph(max_nodes)
        elif graph_type == GraphType.CALLS:
            return self._build_call_graph(max_nodes)
        elif graph_type == GraphType.MODULES:
            return self._build_module_graph(max_nodes)
        elif graph_type == GraphType.CLASSES:
            return self._build_class_graph(max_nodes)
        elif graph_type == GraphType.FUNCTIONS:
            return self._build_function_graph(max_nodes)
        else:
            raise ValueError(f"Unknown graph type: {graph_type}")

    def _build_import_graph(
        self, include_external: bool = False, max_nodes: Optional[int] = None
    ) -> nx.DiGraph:
        """Build module import dependency graph."""
        graph = nx.DiGraph()
        import_graph = self.analysis_result.import_graph

        # Add all modules as nodes first
        internal_modules = set(import_graph.keys())

        for module in internal_modules:
            graph.add_node(module, type="internal_module", external=False)

        # Add edges for imports
        edge_count = 0
        for module, imports in import_graph.items():
            if max_nodes and edge_count >= max_nodes:
                break

            for imported_module in imports:
                # Try to resolve relative imports to full module names
                resolved_module = self._resolve_import(
                    module, imported_module, internal_modules
                )

                if include_external or resolved_module in internal_modules:
                    if resolved_module not in graph:
                        graph.add_node(
                            resolved_module,
                            type="external_module"
                            if resolved_module not in internal_modules
                            else "internal_module",
                            external=resolved_module not in internal_modules,
                        )

                    graph.add_edge(module, resolved_module, relationship="imports")
                    edge_count += 1

        # Add node attributes
        for node in graph.nodes():
            if node in internal_modules:
                module_info = self._get_module_info_by_name(node)
                if module_info:
                    graph.nodes[node].update(
                        {
                            "lines_of_code": module_info.line_count,
                            "num_classes": len(module_info.classes),
                            "num_functions": len(module_info.functions),
                            "num_imports": len(module_info.imports),
                        }
                    )

        return graph

    def _build_inheritance_graph(self, max_nodes: Optional[int] = None) -> nx.DiGraph:
        """Build class inheritance graph."""
        graph = nx.DiGraph()
        inheritance_graph = self.analysis_result.inheritance_graph

        node_count = 0
        for class_name, base_classes in inheritance_graph.items():
            if max_nodes and node_count >= max_nodes:
                break

            # Add class node
            if class_name not in graph:
                class_info = self._find_class_info(class_name)
                graph.add_node(
                    class_name,
                    type="class",
                    methods=len(class_info.methods) if class_info else 0,
                    docstring=class_info.docstring if class_info else None,
                    line_start=class_info.line_start if class_info else 0,
                    line_end=class_info.line_end if class_info else 0,
                )
                node_count += 1

            # Add inheritance relationships
            for base_class in base_classes:
                if base_class not in graph:
                    base_info = self._find_class_info(base_class)
                    graph.add_node(
                        base_class,
                        type="class",
                        methods=len(base_info.methods) if base_info else 0,
                        docstring=base_info.docstring if base_info else None,
                        external=base_info is None,
                    )
                    node_count += 1

                graph.add_edge(class_name, base_class, relationship="inherits_from")

        return graph

    def _build_call_graph(self, max_nodes: Optional[int] = None) -> nx.DiGraph:
        """Build function call graph."""
        graph = nx.DiGraph()
        call_graph = self.analysis_result.call_graph

        node_count = 0
        for function_name, called_functions in call_graph.items():
            if max_nodes and node_count >= max_nodes:
                break

            # Add function node
            if function_name not in graph:
                func_info = self._find_function_info(function_name)
                graph.add_node(
                    function_name,
                    type="function",
                    is_method=func_info.is_method if func_info else False,
                    is_async=func_info.is_async if func_info else False,
                    line_start=func_info.line_start if func_info else 0,
                    line_end=func_info.line_end if func_info else 0,
                    docstring=func_info.docstring if func_info else None,
                )
                node_count += 1

            # Add call relationships
            for called_function in called_functions:
                if called_function not in graph:
                    called_info = self._find_function_info(called_function)
                    graph.add_node(
                        called_function,
                        type="function",
                        external=called_info is None,
                        is_method=called_info.is_method if called_info else False,
                        is_async=called_info.is_async if called_info else False,
                    )
                    node_count += 1

                graph.add_edge(function_name, called_function, relationship="calls")

        return graph

    def _build_module_graph(self, max_nodes: Optional[int] = None) -> nx.DiGraph:
        """Build high-level module relationship graph."""
        graph = nx.DiGraph()

        node_count = 0
        for file_path, module_info in self.analysis_result.modules.items():
            if max_nodes and node_count >= max_nodes:
                break

            module_name = self._path_to_module_name(file_path)

            graph.add_node(
                module_name,
                type="module",
                file_path=str(file_path),
                lines_of_code=module_info.line_count,
                num_classes=len(module_info.classes),
                num_functions=len(module_info.functions),
                num_imports=len(module_info.imports),
                docstring=module_info.docstring,
                has_errors=bool(module_info.syntax_errors),
            )
            node_count += 1

        # Add relationships based on imports
        for module, imports in self.analysis_result.import_graph.items():
            for imported_module in imports:
                if module in graph.nodes() and imported_module in graph.nodes():
                    graph.add_edge(module, imported_module, relationship="depends_on")

        return graph

    def _build_class_graph(self, max_nodes: Optional[int] = None) -> nx.DiGraph:
        """Build graph focused on class relationships."""
        graph = nx.DiGraph()

        node_count = 0
        # Add all classes from all modules
        for file_path, module_info in self.analysis_result.modules.items():
            if max_nodes and node_count >= max_nodes:
                break

            module_name = self._path_to_module_name(file_path)

            for class_info in module_info.classes:
                full_class_name = f"{module_name}.{class_info.name}"

                graph.add_node(
                    full_class_name,
                    type="class",
                    module=module_name,
                    name=class_info.name,
                    methods=len(class_info.methods),
                    docstring=class_info.docstring,
                    line_start=class_info.line_start,
                    line_end=class_info.line_end,
                    decorators=class_info.decorators,
                )
                node_count += 1

                # Add inheritance relationships
                for base_class in class_info.bases:
                    # Try to resolve base class to full name
                    resolved_base = self._resolve_class_name(base_class, module_info)
                    if resolved_base and resolved_base in graph.nodes():
                        graph.add_edge(
                            full_class_name, resolved_base, relationship="inherits_from"
                        )

        return graph

    def _build_function_graph(self, max_nodes: Optional[int] = None) -> nx.DiGraph:
        """Build graph focused on function relationships."""
        graph = nx.DiGraph()

        node_count = 0
        # Add all functions from all modules
        for file_path, module_info in self.analysis_result.modules.items():
            if max_nodes and node_count >= max_nodes:
                break

            module_name = self._path_to_module_name(file_path)

            # Add module-level functions
            for func_info in module_info.functions:
                full_func_name = f"{module_name}.{func_info.name}"

                graph.add_node(
                    full_func_name,
                    type="function",
                    module=module_name,
                    name=func_info.name,
                    is_async=func_info.is_async,
                    args=func_info.args,
                    decorators=func_info.decorators,
                    docstring=func_info.docstring,
                    line_start=func_info.line_start,
                    line_end=func_info.line_end,
                )
                node_count += 1

            # Add methods from classes
            for class_info in module_info.classes:
                for method_info in class_info.methods:
                    full_method_name = (
                        f"{module_name}.{class_info.name}.{method_info.name}"
                    )

                    graph.add_node(
                        full_method_name,
                        type="method",
                        module=module_name,
                        class_name=class_info.name,
                        name=method_info.name,
                        is_async=method_info.is_async,
                        args=method_info.args,
                        decorators=method_info.decorators,
                        docstring=method_info.docstring,
                        line_start=method_info.line_start,
                        line_end=method_info.line_end,
                    )
                    node_count += 1

        # Add call relationships from the call graph
        for caller, callees in self.analysis_result.call_graph.items():
            if caller in graph.nodes():
                for callee in callees:
                    if callee in graph.nodes():
                        graph.add_edge(caller, callee, relationship="calls")

        return graph

    def get_subgraph(
        self, graph: nx.DiGraph, center_node: str, depth: int = 2
    ) -> nx.DiGraph:
        """
        Extract a subgraph centered on a specific node.

        Args:
            graph: Original graph
            center_node: Node to center the subgraph on
            depth: Maximum depth to include from center

        Returns:
            Subgraph containing nodes within specified depth
        """
        if center_node not in graph:
            raise ValueError(f"Node '{center_node}' not found in graph")

        # Get nodes within specified depth
        nodes_to_include = {center_node}
        current_level = {center_node}

        for _ in range(depth):
            next_level = set()
            for node in current_level:
                # Add predecessors and successors
                next_level.update(graph.predecessors(node))
                next_level.update(graph.successors(node))

            current_level = next_level - nodes_to_include
            nodes_to_include.update(current_level)

        return graph.subgraph(nodes_to_include).copy()

    def find_strongly_connected_components(self, graph: nx.DiGraph) -> List[List[str]]:
        """Find strongly connected components (cycles) in the graph."""
        return [
            list(component) for component in nx.strongly_connected_components(graph)
        ]

    def calculate_centrality_metrics(
        self, graph: nx.DiGraph
    ) -> Dict[str, Dict[str, float]]:
        """Calculate various centrality metrics for graph nodes."""
        metrics = {}

        try:
            degree_centrality = nx.degree_centrality(graph)
            in_degree_centrality = nx.in_degree_centrality(graph)
            out_degree_centrality = nx.out_degree_centrality(graph)

            # For large graphs, these might be expensive
            if len(graph.nodes()) < 1000:
                betweenness_centrality = nx.betweenness_centrality(graph)
                closeness_centrality = nx.closeness_centrality(graph)
                pagerank = nx.pagerank(graph)
            else:
                betweenness_centrality = {}
                closeness_centrality = {}
                pagerank = {}

            for node in graph.nodes():
                metrics[node] = {
                    "degree_centrality": degree_centrality.get(node, 0.0),
                    "in_degree_centrality": in_degree_centrality.get(node, 0.0),
                    "out_degree_centrality": out_degree_centrality.get(node, 0.0),
                    "betweenness_centrality": betweenness_centrality.get(node, 0.0),
                    "closeness_centrality": closeness_centrality.get(node, 0.0),
                    "pagerank": pagerank.get(node, 0.0),
                }

        except Exception:
            # Fallback for disconnected graphs or other issues
            for node in graph.nodes():
                metrics[node] = {
                    "degree_centrality": 0.0,
                    "in_degree_centrality": 0.0,
                    "out_degree_centrality": 0.0,
                    "betweenness_centrality": 0.0,
                    "closeness_centrality": 0.0,
                    "pagerank": 0.0,
                }

        return metrics

    def _get_module_info_by_name(self, module_name: str) -> Optional[ModuleInfo]:
        """Find ModuleInfo by module name."""
        for file_path, module_info in self.analysis_result.modules.items():
            if self._path_to_module_name(file_path) == module_name:
                return module_info
        return None

    def _find_class_info(self, class_name: str) -> Optional[ClassInfo]:
        """Find ClassInfo by class name (may include module prefix)."""
        for module_info in self.analysis_result.modules.values():
            for class_info in module_info.classes:
                if class_info.name == class_name or class_name.endswith(
                    f".{class_info.name}"
                ):
                    return class_info
        return None

    def _find_function_info(self, function_name: str) -> Optional[FunctionInfo]:
        """Find FunctionInfo by function name (may include module/class prefix)."""
        for module_info in self.analysis_result.modules.values():
            # Check module-level functions
            for func_info in module_info.functions:
                if func_info.name == function_name or function_name.endswith(
                    f".{func_info.name}"
                ):
                    return func_info

            # Check class methods
            for class_info in module_info.classes:
                for method_info in class_info.methods:
                    if method_info.name == function_name or function_name.endswith(
                        f".{method_info.name}"
                    ):
                        return method_info

        return None

    def _resolve_class_name(
        self, class_name: str, module_info: ModuleInfo
    ) -> Optional[str]:
        """Resolve a class name to its full name based on imports."""
        # This is a simplified resolution - a full implementation would
        # need to handle various import scenarios
        for import_info in module_info.imports:
            if class_name in import_info.names:
                return f"{import_info.module}.{class_name}"

        return class_name

    def _resolve_import(
        self, importing_module: str, imported_module: str, internal_modules: set
    ) -> str:
        """Resolve an import name to a full module name if possible."""
        # If it's already a full module name, return it
        if imported_module in internal_modules:
            return imported_module

        # Try to find a matching internal module by suffix
        # For example, if importing_module is "path.to.module1" and imported_module is "module2"
        # We look for any internal module ending with "module2"
        for internal_module in internal_modules:
            if internal_module.endswith("." + imported_module):
                return internal_module

        # If not found, return the original import name (likely external)
        return imported_module

    @staticmethod
    def _path_to_module_name(file_path) -> str:
        """Convert a file path to a module name."""
        path_str = str(file_path)
        if path_str.endswith("__init__.py"):
            return str(file_path.parent).replace("/", ".").replace("\\", ".")
        else:
            return str(file_path.with_suffix("")).replace("/", ".").replace("\\", ".")
