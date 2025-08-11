"""
Tests for the CLI interface.
"""

import tempfile
from io import StringIO
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from idgi.cli import create_parser


class TestCLI(TestCase):
    """Test cases for CLI functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = create_parser()
        self.temp_dir = Path(tempfile.mkdtemp())

        # Create a simple test project
        (self.temp_dir / "test_module.py").write_text("""
class TestClass:
    def test_method(self):
        pass

def test_function():
    return 42
""")

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_parser_creation(self):
        """Test that parser is created correctly."""
        self.assertIsNotNone(self.parser)
        self.assertEqual(self.parser.prog, "idgi")

    def test_scan_command_parsing(self):
        """Test parsing of scan command arguments."""
        args = self.parser.parse_args(["scan", str(self.temp_dir)])

        self.assertEqual(args.command, "scan")
        self.assertEqual(args.directory, str(self.temp_dir))
        self.assertTrue(args.recursive)  # Default should be True

    def test_scan_command_with_options(self):
        """Test scan command with various options."""
        args = self.parser.parse_args(
            [
                "scan",
                str(self.temp_dir),
                "--exclude",
                "venv",
                "--exclude",
                "*.pyc",
                "--no-recursive",
                "--show-packages",
                "--show-errors",
            ]
        )

        self.assertEqual(args.exclude, ["venv", "*.pyc"])
        self.assertFalse(args.recursive)
        self.assertTrue(args.show_packages)
        self.assertTrue(args.show_errors)

    def test_graph_command_parsing(self):
        """Test parsing of graph command arguments."""
        args = self.parser.parse_args(
            [
                "graph",
                str(self.temp_dir),
                "--type",
                "imports",
                "--format",
                "tree",
                "--interactive",
            ]
        )

        self.assertEqual(args.command, "graph")
        self.assertEqual(args.type, "imports")
        self.assertEqual(args.format, "tree")
        self.assertTrue(args.interactive)

    def test_graph_command_with_output(self):
        """Test graph command with output file."""
        output_file = self.temp_dir / "output.svg"

        args = self.parser.parse_args(
            [
                "graph",
                str(self.temp_dir),
                "--output",
                str(output_file),
                "--max-nodes",
                "50",
                "--depth",
                "2",
            ]
        )

        self.assertEqual(args.output, str(output_file))
        self.assertEqual(args.max_nodes, 50)
        self.assertEqual(args.depth, 2)

    def test_search_command_parsing(self):
        """Test parsing of search command arguments."""
        args = self.parser.parse_args(
            ["search", "TestClass", str(self.temp_dir), "--limit", "100"]
        )

        self.assertEqual(args.command, "search")
        self.assertEqual(args.term, "TestClass")
        self.assertEqual(args.directory, str(self.temp_dir))
        self.assertEqual(args.limit, 100)

    def test_export_command_parsing(self):
        """Test parsing of export command arguments."""
        args = self.parser.parse_args(
            [
                "export",
                str(self.temp_dir),
                "--output",
                str(self.temp_dir / "exports"),
                "--format",
                "svg",
                "--format",
                "json",
                "--types",
                "imports",
                "--types",
                "classes",
            ]
        )

        self.assertEqual(args.command, "export")
        self.assertEqual(args.format, ["svg", "json"])
        self.assertEqual(args.types, ["imports", "classes"])

    def test_invalid_graph_type(self):
        """Test handling of invalid graph types."""
        # This should raise SystemExit due to invalid choice
        with self.assertRaises(SystemExit):
            self.parser.parse_args(
                ["graph", str(self.temp_dir), "--type", "invalid_type"]
            )

    def test_help_output(self):
        """Test that help output is generated correctly."""
        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            try:
                self.parser.parse_args(["--help"])
            except SystemExit:
                pass  # argparse calls sys.exit() after printing help

            help_output = fake_stdout.getvalue()
            self.assertIn("idgi", help_output)
            self.assertIn("scan", help_output)
            self.assertIn("graph", help_output)
            self.assertIn("search", help_output)
            self.assertIn("export", help_output)

    def test_subcommand_help(self):
        """Test help output for subcommands."""
        with patch("sys.stdout", new=StringIO()) as fake_stdout:
            try:
                self.parser.parse_args(["scan", "--help"])
            except SystemExit:
                pass

            help_output = fake_stdout.getvalue()
            self.assertIn("scan", help_output)
            self.assertIn("directory", help_output)

    def test_default_values(self):
        """Test that default values are set correctly."""
        args = self.parser.parse_args(["scan", str(self.temp_dir)])

        self.assertEqual(args.workers, 4)  # Default worker count
        self.assertFalse(args.verbose)  # Default verbose setting
        self.assertTrue(args.recursive)  # Default recursive setting

    def test_verbose_flag(self):
        """Test verbose flag parsing."""
        args = self.parser.parse_args(["--verbose", "scan", str(self.temp_dir)])
        self.assertTrue(args.verbose)

        args = self.parser.parse_args(["-v", "scan", str(self.temp_dir)])
        self.assertTrue(args.verbose)

    def test_workers_option(self):
        """Test workers option parsing."""
        args = self.parser.parse_args(["--workers", "8", "scan", str(self.temp_dir)])
        self.assertEqual(args.workers, 8)

    def test_no_command(self):
        """Test behavior when no command is provided."""
        args = self.parser.parse_args([])
        self.assertIsNone(args.command)

    def test_export_default_formats(self):
        """Test default export formats."""
        args = self.parser.parse_args(
            ["export", str(self.temp_dir), "--output", str(self.temp_dir / "exports")]
        )

        # Defaults are now handled at runtime, not parse time
        self.assertIsNone(args.format)
        self.assertIsNone(args.types)

    def test_graph_stats_option(self):
        """Test graph stats option."""
        args = self.parser.parse_args(["graph", str(self.temp_dir), "--stats"])

        self.assertTrue(args.stats)

    def test_all_graph_types_supported(self):
        """Test that all graph types are supported in CLI."""
        from idgi.graph.builder import GraphType

        # Get choices from parser
        graph_parser = None
        for action in self.parser._subparsers._actions:
            if (
                hasattr(action, "choices")
                and action.choices
                and "graph" in action.choices
            ):
                graph_parser = action.choices["graph"]
                break

        self.assertIsNotNone(graph_parser)

        # Find the --type argument
        type_choices = None
        for action in graph_parser._actions:
            if hasattr(action, "dest") and action.dest == "type":
                type_choices = action.choices
                break

        self.assertIsNotNone(type_choices)

        # Check that all GraphType values are supported
        graph_type_values = [t.value for t in GraphType]
        for graph_type in graph_type_values:
            self.assertIn(graph_type, type_choices)
