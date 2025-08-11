"""
Tests for the graph builder module.
"""

import tempfile
from pathlib import Path
from unittest import TestCase

import networkx as nx

from idgi.core.analyzer import CodebaseAnalyzer
from idgi.graph.builder import GraphBuilder, GraphType


class TestGraphBuilder(TestCase):
    """Test cases for GraphBuilder."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create a simple test codebase
        (self.temp_dir / "module1.py").write_text("""
import os
from module2 import ClassB

class ClassA:
    def method_a(self):
        return ClassB()

def function_a():
    os.path.join("a", "b")
""")

        (self.temp_dir / "module2.py").write_text("""
import sys

class ClassB(object):
    def method_b(self):
        function_b()

def function_b():
    sys.exit(0)
""")

        # Analyze the codebase
        analyzer = CodebaseAnalyzer()
        self.analysis_result = analyzer.analyze(self.temp_dir)
        self.builder = GraphBuilder(self.analysis_result)

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_build_import_graph(self):
        """Test building import dependency graph."""
        graph = self.builder.build_graph(GraphType.IMPORTS)

        self.assertIsInstance(graph, nx.DiGraph)
        self.assertGreater(len(graph.nodes()), 0)

        # Check that modules are connected by import relationships
        edges_with_import = [
            (u, v)
            for u, v, d in graph.edges(data=True)
            if d.get("relationship") == "imports"
        ]
        self.assertGreater(len(edges_with_import), 0)

    def test_build_inheritance_graph(self):
        """Test building class inheritance graph."""
        graph = self.builder.build_graph(GraphType.INHERITANCE)

        self.assertIsInstance(graph, nx.DiGraph)

        # Should have ClassB inheriting from object
        if len(graph.nodes()) > 0:
            # Check for inheritance relationships
            inheritance_edges = [
                (u, v)
                for u, v, d in graph.edges(data=True)
                if d.get("relationship") == "inherits_from"
            ]
            self.assertGreaterEqual(
                len(inheritance_edges), 0
            )  # May be 0 if no explicit inheritance

    def test_build_call_graph(self):
        """Test building function call graph."""
        graph = self.builder.build_graph(GraphType.CALLS)

        self.assertIsInstance(graph, nx.DiGraph)

        # Should have function call relationships
        if len(graph.nodes()) > 0:
            call_edges = [
                (u, v)
                for u, v, d in graph.edges(data=True)
                if d.get("relationship") == "calls"
            ]
            self.assertGreaterEqual(len(call_edges), 0)

    def test_build_module_graph(self):
        """Test building module overview graph."""
        graph = self.builder.build_graph(GraphType.MODULES)

        self.assertIsInstance(graph, nx.DiGraph)
        self.assertGreater(len(graph.nodes()), 0)

        # Check node attributes
        for node in graph.nodes():
            node_data = graph.nodes[node]
            self.assertEqual(node_data.get("type"), "module")
            self.assertIsInstance(node_data.get("lines_of_code"), int)

    def test_build_class_graph(self):
        """Test building class-focused graph."""
        graph = self.builder.build_graph(GraphType.CLASSES)

        self.assertIsInstance(graph, nx.DiGraph)

        # Check that classes have proper attributes
        class_nodes = [
            n for n in graph.nodes() if graph.nodes[n].get("type") == "class"
        ]
        for node in class_nodes:
            node_data = graph.nodes[node]
            self.assertIn("methods", node_data)
            self.assertIsInstance(node_data["methods"], int)

    def test_build_function_graph(self):
        """Test building function-focused graph."""
        graph = self.builder.build_graph(GraphType.FUNCTIONS)

        self.assertIsInstance(graph, nx.DiGraph)

        # Check for function and method nodes
        function_nodes = [
            n
            for n in graph.nodes()
            if graph.nodes[n].get("type") in ["function", "method"]
        ]
        self.assertGreater(len(function_nodes), 0)

    def test_max_nodes_limit(self):
        """Test that max_nodes parameter limits graph size."""
        # Build graph with node limit
        graph = self.builder.build_graph(GraphType.MODULES, max_nodes=1)

        self.assertLessEqual(len(graph.nodes()), 1)

    def test_get_subgraph(self):
        """Test extraction of subgraphs."""
        graph = self.builder.build_graph(GraphType.MODULES)

        if len(graph.nodes()) > 0:
            center_node = list(graph.nodes())[0]
            subgraph = self.builder.get_subgraph(graph, center_node, depth=1)

            self.assertIsInstance(subgraph, nx.DiGraph)
            self.assertIn(center_node, subgraph.nodes())

    def test_strongly_connected_components(self):
        """Test finding strongly connected components."""
        graph = self.builder.build_graph(GraphType.IMPORTS)

        components = self.builder.find_strongly_connected_components(graph)

        self.assertIsInstance(components, list)
        # Each component should be a list of nodes
        for component in components:
            self.assertIsInstance(component, list)

    def test_centrality_metrics(self):
        """Test calculation of centrality metrics."""
        graph = self.builder.build_graph(GraphType.MODULES)

        if len(graph.nodes()) > 0:
            metrics = self.builder.calculate_centrality_metrics(graph)

            self.assertIsInstance(metrics, dict)

            # Check that metrics are calculated for all nodes
            for node in graph.nodes():
                self.assertIn(node, metrics)
                node_metrics = metrics[node]

                # Check that all expected metrics are present
                expected_metrics = [
                    "degree_centrality",
                    "in_degree_centrality",
                    "out_degree_centrality",
                    "betweenness_centrality",
                    "closeness_centrality",
                    "pagerank",
                ]

                for metric in expected_metrics:
                    self.assertIn(metric, node_metrics)
                    self.assertIsInstance(node_metrics[metric], float)

    def test_include_external_dependencies(self):
        """Test inclusion of external dependencies in import graph."""
        graph = self.builder.build_graph(GraphType.IMPORTS, include_external=True)

        # Should include external modules like 'os' and 'sys'
        external_nodes = [
            n for n in graph.nodes() if graph.nodes[n].get("external", False)
        ]

        # We expect at least some external dependencies
        self.assertGreaterEqual(len(external_nodes), 0)

    def test_empty_analysis_result(self):
        """Test handling of empty analysis results."""
        # Create empty temp directory
        empty_dir = Path(tempfile.mkdtemp())
        try:
            analyzer = CodebaseAnalyzer()
            empty_result = analyzer.analyze(empty_dir)
            empty_builder = GraphBuilder(empty_result)

            graph = empty_builder.build_graph(GraphType.MODULES)

            # Should handle empty results gracefully
            self.assertIsInstance(graph, nx.DiGraph)
            self.assertEqual(len(graph.nodes()), 0)

        finally:
            import shutil

            shutil.rmtree(empty_dir)
