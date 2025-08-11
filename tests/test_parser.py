"""
Tests for the Python AST parser module.
"""

import tempfile
from pathlib import Path
from unittest import TestCase

from idgi.core.parser import BatchParser, PythonASTParser


class TestPythonASTParser(TestCase):
    """Test cases for PythonASTParser."""

    def setUp(self):
        """Set up test fixtures."""
        self.parser = PythonASTParser()
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def _create_test_file(self, content: str) -> Path:
        """Create a temporary Python file with given content."""
        test_file = self.temp_dir / "test.py"
        test_file.write_text(content)
        return test_file

    def test_parse_imports(self):
        """Test parsing of import statements."""
        content = """
import os
import sys as system
from pathlib import Path
from typing import Dict, List
"""

        test_file = self._create_test_file(content)
        module_info = self.parser.parse_file(test_file)

        self.assertEqual(len(module_info.imports), 4)

        # Test regular import
        os_import = next(imp for imp in module_info.imports if imp.module == "os")
        self.assertFalse(os_import.is_from_import)
        self.assertEqual(os_import.names, ["os"])

        # Test aliased import
        sys_import = next(imp for imp in module_info.imports if imp.module == "sys")
        self.assertEqual(sys_import.aliases, {"sys": "system"})

        # Test from import
        pathlib_import = next(
            imp for imp in module_info.imports if imp.module == "pathlib"
        )
        self.assertTrue(pathlib_import.is_from_import)
        self.assertEqual(pathlib_import.names, ["Path"])

    def test_parse_functions(self):
        """Test parsing of function definitions."""
        content = '''
def simple_function():
    """A simple function."""
    return 42

async def async_function(arg1, arg2="default"):
    """An async function."""
    await some_coroutine()

@decorator
def decorated_function():
    pass
'''

        test_file = self._create_test_file(content)
        module_info = self.parser.parse_file(test_file)

        self.assertEqual(len(module_info.functions), 3)

        # Test simple function
        simple_func = next(
            f for f in module_info.functions if f.name == "simple_function"
        )
        self.assertFalse(simple_func.is_async)
        self.assertEqual(simple_func.docstring, "A simple function.")

        # Test async function
        async_func = next(
            f for f in module_info.functions if f.name == "async_function"
        )
        self.assertTrue(async_func.is_async)
        self.assertEqual(len(async_func.args), 2)

        # Test decorated function
        decorated_func = next(
            f for f in module_info.functions if f.name == "decorated_function"
        )
        self.assertEqual(len(decorated_func.decorators), 1)

    def test_parse_classes(self):
        """Test parsing of class definitions."""
        content = '''
class BaseClass:
    """Base class."""

    def method1(self):
        pass

class DerivedClass(BaseClass):
    """Derived class."""

    def __init__(self, value):
        self.value = value

    def method2(self):
        return self.value

    class NestedClass:
        pass

@dataclass
class DecoratedClass:
    value: int
'''

        test_file = self._create_test_file(content)
        module_info = self.parser.parse_file(test_file)

        self.assertEqual(len(module_info.classes), 3)

        # Test base class
        base_class = next(c for c in module_info.classes if c.name == "BaseClass")
        self.assertEqual(base_class.docstring, "Base class.")
        self.assertEqual(len(base_class.methods), 1)
        self.assertEqual(len(base_class.bases), 0)

        # Test derived class
        derived_class = next(c for c in module_info.classes if c.name == "DerivedClass")
        self.assertEqual(len(derived_class.bases), 1)
        self.assertEqual(derived_class.bases[0], "BaseClass")
        self.assertEqual(len(derived_class.methods), 2)
        self.assertEqual(len(derived_class.nested_classes), 1)

        # Test decorated class
        decorated_class = next(
            c for c in module_info.classes if c.name == "DecoratedClass"
        )
        self.assertEqual(len(decorated_class.decorators), 1)

    def test_parse_global_variables(self):
        """Test parsing of global variable assignments."""
        content = """
CONSTANT = 42
variable = "value"
x, y = 1, 2

class SomeClass:
    class_var = "not global"
"""

        test_file = self._create_test_file(content)
        module_info = self.parser.parse_file(test_file)

        # Should find global variables but not class variables
        global_vars = set(module_info.global_variables)
        self.assertIn("CONSTANT", global_vars)
        self.assertIn("variable", global_vars)
        self.assertNotIn("class_var", global_vars)

    def test_function_calls(self):
        """Test detection of function calls."""
        content = """
def my_function():
    print("hello")
    os.path.join("/", "path")
    some_function()
    return len([1, 2, 3])
"""

        test_file = self._create_test_file(content)
        module_info = self.parser.parse_file(test_file)

        func = module_info.functions[0]
        calls = set(func.calls)

        self.assertIn("print", calls)
        self.assertIn("os.path.join", calls)
        self.assertIn("some_function", calls)
        self.assertIn("len", calls)

    def test_syntax_error_handling(self):
        """Test handling of syntax errors."""
        content = """
def broken_function(
    # Missing closing parenthesis
    pass
"""

        test_file = self._create_test_file(content)
        module_info = self.parser.parse_file(test_file)

        self.assertGreater(len(module_info.syntax_errors), 0)
        self.assertEqual(
            len(module_info.functions), 0
        )  # Should not parse functions due to error


class TestBatchParser(TestCase):
    """Test cases for BatchParser."""

    def setUp(self):
        """Set up test fixtures."""
        self.batch_parser = BatchParser()
        self.temp_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_parse_multiple_files(self):
        """Test parsing multiple files."""
        # Create test files
        file1 = self.temp_dir / "module1.py"
        file1.write_text("def func1(): pass")

        file2 = self.temp_dir / "module2.py"
        file2.write_text("class Class2: pass")

        results = self.batch_parser.parse_files([file1, file2])

        self.assertEqual(len(results), 2)
        self.assertIn(file1, results)
        self.assertIn(file2, results)

        # Check that functions and classes were parsed
        self.assertEqual(len(results[file1].functions), 1)
        self.assertEqual(len(results[file2].classes), 1)

    def test_import_graph_generation(self):
        """Test generation of import dependency graph."""
        # Create files with imports
        file1 = self.temp_dir / "module1.py"
        file1.write_text("""
import os
from module2 import func2
""")

        file2 = self.temp_dir / "module2.py"
        file2.write_text("""
import sys
def func2(): pass
""")

        results = self.batch_parser.parse_files([file1, file2])
        import_graph = self.batch_parser.get_import_graph(results)

        # Check import relationships
        # Find the actual module keys (they have full paths)
        module1_key = next(k for k in import_graph.keys() if k.endswith("module1"))
        module2_key = next(k for k in import_graph.keys() if k.endswith("module2"))

        module1_imports = import_graph.get(module1_key, set())
        self.assertIn("os", module1_imports)
        self.assertIn("module2", module1_imports)

        module2_imports = import_graph.get(module2_key, set())
        self.assertIn("sys", module2_imports)

    def test_inheritance_graph_generation(self):
        """Test generation of class inheritance graph."""
        file1 = self.temp_dir / "classes.py"
        file1.write_text("""
class BaseClass:
    pass

class DerivedClass(BaseClass):
    pass

class AnotherDerived(BaseClass, object):
    pass
""")

        results = self.batch_parser.parse_files([file1])
        inheritance_graph = self.batch_parser.get_inheritance_graph(results)

        # Check inheritance relationships
        self.assertIn("DerivedClass", inheritance_graph)
        self.assertIn("BaseClass", inheritance_graph["DerivedClass"])

        self.assertIn("AnotherDerived", inheritance_graph)
        derived_bases = inheritance_graph["AnotherDerived"]
        self.assertIn("BaseClass", derived_bases)
        self.assertIn("object", derived_bases)
