"""
Tests for the export functionality.
"""

import tempfile
from pathlib import Path
from unittest import TestCase

import networkx as nx

from idgi.export.formats import GraphExporter


class TestGraphExporter(TestCase):
    """Test cases for GraphExporter."""

    def setUp(self):
        """Set up test fixtures."""
        self.exporter = GraphExporter()
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create a simple test graph
        self.test_graph = nx.DiGraph()
        self.test_graph.add_node("node1", type="module", lines_of_code=100)
        self.test_graph.add_node("node2", type="class", methods=5)
        self.test_graph.add_node("node3", type="function", is_async=False)
        self.test_graph.add_edge("node1", "node2", relationship="contains")
        self.test_graph.add_edge("node2", "node3", relationship="calls")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_supported_formats(self):
        """Test that supported formats are correctly identified."""
        formats = GraphExporter.list_formats()

        expected_formats = {"svg", "png", "pdf", "dot", "json", "gml", "graphml"}
        self.assertTrue(expected_formats.issubset(set(formats.keys())))

        # Test format checking
        self.assertTrue(GraphExporter.is_format_supported("json"))
        self.assertTrue(GraphExporter.is_format_supported("svg"))
        self.assertFalse(GraphExporter.is_format_supported("unknown_format"))

    def test_export_json(self):
        """Test JSON export functionality."""
        output_file = self.temp_dir / "test_graph.json"

        success = self.exporter.export(
            graph=self.test_graph, output_path=output_file, format_type="json"
        )

        self.assertTrue(success)
        self.assertTrue(output_file.exists())

        # Check that the JSON file contains expected data
        import json

        with open(output_file, "r") as f:
            data = json.load(f)

        self.assertIn("nodes", data)
        self.assertIn("links", data)
        self.assertEqual(len(data["nodes"]), 3)
        self.assertEqual(len(data["links"]), 2)

    def test_export_dot(self):
        """Test DOT format export."""
        output_file = self.temp_dir / "test_graph.dot"

        success = self.exporter.export(
            graph=self.test_graph,
            output_path=output_file,
            format_type="dot",
            title="Test Graph",
        )

        self.assertTrue(success)
        self.assertTrue(output_file.exists())

        # Check that the DOT file contains expected content
        content = output_file.read_text()
        self.assertIn("digraph G {", content)
        self.assertIn('label="Test Graph"', content)
        self.assertIn("node1", content)
        self.assertIn("node2", content)
        self.assertIn("node3", content)

    def test_export_gml(self):
        """Test GML format export."""
        output_file = self.temp_dir / "test_graph.gml"

        success = self.exporter.export(
            graph=self.test_graph,
            output_path=output_file,
            format_type="gml",
            include_attributes=True,
        )

        self.assertTrue(success)
        self.assertTrue(output_file.exists())

        # Verify GML file can be read back
        loaded_graph = nx.read_gml(output_file)
        self.assertEqual(len(loaded_graph.nodes()), 3)
        self.assertEqual(len(loaded_graph.edges()), 2)

    def test_export_graphml(self):
        """Test GraphML format export."""
        output_file = self.temp_dir / "test_graph.graphml"

        success = self.exporter.export(
            graph=self.test_graph,
            output_path=output_file,
            format_type="graphml",
            include_attributes=True,
        )

        self.assertTrue(success)
        self.assertTrue(output_file.exists())

        # Verify GraphML file can be read back
        loaded_graph = nx.read_graphml(output_file)
        self.assertEqual(len(loaded_graph.nodes()), 3)
        self.assertEqual(len(loaded_graph.edges()), 2)

    def test_export_without_attributes(self):
        """Test export without node/edge attributes."""
        output_file = self.temp_dir / "test_graph_no_attrs.json"

        success = self.exporter.export(
            graph=self.test_graph,
            output_path=output_file,
            format_type="json",
            include_attributes=False,
        )

        self.assertTrue(success)

        # Check that attributes are not included
        import json

        with open(output_file, "r") as f:
            data = json.load(f)

        # Nodes should only have 'id' field
        for node in data["nodes"]:
            self.assertEqual(set(node.keys()), {"id"})

    def test_max_nodes_limitation(self):
        """Test that max_nodes parameter limits export size."""
        # Create a larger graph
        large_graph = nx.DiGraph()
        for i in range(100):
            large_graph.add_node(f"node_{i}", type="test")

        output_file = self.temp_dir / "limited_graph.json"

        success = self.exporter.export(
            graph=large_graph, output_path=output_file, format_type="json", max_nodes=10
        )

        self.assertTrue(success)

        # Check that output is limited
        import json

        with open(output_file, "r") as f:
            data = json.load(f)

        self.assertLessEqual(len(data["nodes"]), 10)

    def test_format_inference_from_extension(self):
        """Test that format is inferred from file extension."""
        output_file = self.temp_dir / "test_graph.json"

        # Don't specify format_type - should be inferred
        success = self.exporter.export(graph=self.test_graph, output_path=output_file)

        self.assertTrue(success)
        self.assertTrue(output_file.exists())

    def test_invalid_format(self):
        """Test handling of invalid export format."""
        output_file = self.temp_dir / "test_graph.invalid"

        with self.assertRaises(ValueError):
            self.exporter.export(
                graph=self.test_graph,
                output_path=output_file,
                format_type="invalid_format",
            )

    def test_empty_graph_export(self):
        """Test export of empty graph."""
        empty_graph = nx.DiGraph()
        output_file = self.temp_dir / "empty_graph.json"

        success = self.exporter.export(
            graph=empty_graph, output_path=output_file, format_type="json"
        )

        self.assertTrue(success)
        self.assertTrue(output_file.exists())

        # Check that empty graph exports correctly
        import json

        with open(output_file, "r") as f:
            data = json.load(f)

        self.assertEqual(len(data["nodes"]), 0)
        self.assertEqual(len(data["links"]), 0)

    def test_node_color_customization(self):
        """Test custom node colors in visual exports."""
        output_file = self.temp_dir / "colored_graph.dot"

        custom_colors = {
            "module": "lightblue",
            "class": "lightcoral",
            "function": "lightyellow",
        }

        success = self.exporter.export(
            graph=self.test_graph,
            output_path=output_file,
            format_type="dot",
            node_colors=custom_colors,
        )

        self.assertTrue(success)

        # Check that custom colors are used in DOT output
        content = output_file.read_text()
        self.assertIn("lightblue", content)
        self.assertIn("lightcoral", content)

    def test_dot_string_escaping(self):
        """Test proper escaping of strings in DOT format."""
        # Create graph with special characters
        special_graph = nx.DiGraph()
        special_graph.add_node('node"with"quotes', type="test")
        special_graph.add_node("node\nwith\nnewlines", type="test")
        special_graph.add_edge(
            'node"with"quotes', "node\nwith\nnewlines", relationship='test"relation'
        )

        output_file = self.temp_dir / "special_chars.dot"

        success = self.exporter.export(
            graph=special_graph, output_path=output_file, format_type="dot"
        )

        self.assertTrue(success)

        # Check that special characters are properly escaped
        content = output_file.read_text()
        self.assertIn('\\"', content)  # Escaped quotes
        self.assertIn("\\n", content)  # Escaped newlines
