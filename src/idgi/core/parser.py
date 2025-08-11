"""
Python AST parsing for extracting classes, functions, imports, and other code elements.
"""

import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Union


@dataclass
class ImportInfo:
    """Information about an import statement."""

    module: str
    names: List[
        str
    ]  # For 'from x import y', this is ['y']. For 'import x', this is ['x']
    aliases: Dict[str, str] = field(default_factory=dict)  # name -> alias mapping
    is_from_import: bool = False
    line_number: int = 0


@dataclass
class FunctionInfo:
    """Information about a function definition."""

    name: str
    line_start: int
    line_end: int
    args: List[str] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    is_async: bool = False
    is_method: bool = False
    parent_class: Optional[str] = None
    calls: List[str] = field(
        default_factory=list
    )  # Functions called within this function


@dataclass
class ClassInfo:
    """Information about a class definition."""

    name: str
    line_start: int
    line_end: int
    bases: List[str] = field(default_factory=list)  # Base classes
    methods: List[FunctionInfo] = field(default_factory=list)
    decorators: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    nested_classes: List["ClassInfo"] = field(default_factory=list)


@dataclass
class ModuleInfo:
    """Complete information about a Python module."""

    file_path: Path
    imports: List[ImportInfo] = field(default_factory=list)
    classes: List[ClassInfo] = field(default_factory=list)
    functions: List[FunctionInfo] = field(default_factory=list)
    global_variables: List[str] = field(default_factory=list)
    docstring: Optional[str] = None
    line_count: int = 0
    syntax_errors: List[str] = field(default_factory=list)


class PythonASTParser:
    """
    Parses Python source files using AST to extract structural information.
    """

    def __init__(self):
        self.current_class_stack: List[str] = []

    def parse_file(self, file_path: Path) -> ModuleInfo:
        """
        Parse a Python file and extract structural information.

        Args:
            file_path: Path to the Python file to parse

        Returns:
            ModuleInfo containing extracted information
        """
        module_info = ModuleInfo(file_path=file_path)

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                source_code = f.read()
                module_info.line_count = source_code.count("\n") + 1

        except Exception as e:
            module_info.syntax_errors.append(f"Error reading file: {str(e)}")
            return module_info

        try:
            tree = ast.parse(source_code, filename=str(file_path))
        except SyntaxError as e:
            module_info.syntax_errors.append(f"Syntax error: {str(e)}")
            return module_info
        except Exception as e:
            module_info.syntax_errors.append(f"Parse error: {str(e)}")
            return module_info

        # Extract module docstring
        module_info.docstring = ast.get_docstring(tree)

        # Visit all nodes in the AST
        self._visit_node(tree, module_info)

        return module_info

    def _visit_node(self, node: ast.AST, module_info: ModuleInfo) -> None:
        """Visit an AST node and extract relevant information."""

        if isinstance(node, ast.Import):
            self._process_import(node, module_info)

        elif isinstance(node, ast.ImportFrom):
            self._process_import_from(node, module_info)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_info = self._process_function(node, module_info)
            if self.current_class_stack:
                # This is a method
                func_info.is_method = True
                func_info.parent_class = self.current_class_stack[-1]
            else:
                # This is a top-level function
                module_info.functions.append(func_info)

        elif isinstance(node, ast.ClassDef):
            class_info = self._process_class(node, module_info)
            if self.current_class_stack:
                # This is a nested class
                # Find the parent class and add to its nested_classes
                parent_class = next(
                    (
                        c
                        for c in module_info.classes
                        if c.name == self.current_class_stack[-1]
                    ),
                    None,
                )
                if parent_class:
                    parent_class.nested_classes.append(class_info)
            else:
                # This is a top-level class
                module_info.classes.append(class_info)
            # Don't recursively visit child nodes for classes - _process_class handles this
            return

        elif isinstance(node, ast.Assign):
            self._process_assignment(node, module_info)

        # Recursively visit child nodes
        for child in ast.iter_child_nodes(node):
            self._visit_node(child, module_info)

    def _process_import(self, node: ast.Import, module_info: ModuleInfo) -> None:
        """Process an import statement."""
        for alias in node.names:
            import_info = ImportInfo(
                module=alias.name,
                names=[alias.name],
                line_number=node.lineno,
                is_from_import=False,
            )

            if alias.asname:
                import_info.aliases[alias.name] = alias.asname

            module_info.imports.append(import_info)

    def _process_import_from(
        self, node: ast.ImportFrom, module_info: ModuleInfo
    ) -> None:
        """Process a 'from ... import ...' statement."""
        if node.module is None:
            return

        names = []
        aliases = {}

        for alias in node.names:
            names.append(alias.name)
            if alias.asname:
                aliases[alias.name] = alias.asname

        import_info = ImportInfo(
            module=node.module,
            names=names,
            aliases=aliases,
            line_number=node.lineno,
            is_from_import=True,
        )

        module_info.imports.append(import_info)

    def _process_function(
        self,
        node: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        module_info: ModuleInfo,
    ) -> FunctionInfo:
        """Process a function definition."""

        func_info = FunctionInfo(
            name=node.name,
            line_start=node.lineno,
            line_end=getattr(node, "end_lineno", node.lineno),
            is_async=isinstance(node, ast.AsyncFunctionDef),
        )

        # Extract function arguments
        func_info.args = [arg.arg for arg in node.args.args]

        # Extract decorators
        func_info.decorators = [
            self._get_decorator_name(dec) for dec in node.decorator_list
        ]

        # Extract docstring
        func_info.docstring = ast.get_docstring(node)

        # Find function calls within this function
        func_info.calls = self._find_function_calls(node)

        return func_info

    def _process_class(self, node: ast.ClassDef, module_info: ModuleInfo) -> ClassInfo:
        """Process a class definition."""

        class_info = ClassInfo(
            name=node.name,
            line_start=node.lineno,
            line_end=getattr(node, "end_lineno", node.lineno),
        )

        # Extract base classes
        for base in node.bases:
            base_name = self._get_name_from_node(base)
            if base_name:
                class_info.bases.append(base_name)

        # Extract decorators
        class_info.decorators = [
            self._get_decorator_name(dec) for dec in node.decorator_list
        ]

        # Extract docstring
        class_info.docstring = ast.get_docstring(node)

        # Process methods and nested classes
        self.current_class_stack.append(node.name)

        for child in node.body:
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                method_info = self._process_function(child, module_info)
                method_info.is_method = True
                method_info.parent_class = node.name
                class_info.methods.append(method_info)

            elif isinstance(child, ast.ClassDef):
                nested_class = self._process_class(child, module_info)
                class_info.nested_classes.append(nested_class)
            else:
                # Process other child nodes (but not ClassDef as we handle them above)
                self._visit_node(child, module_info)

        self.current_class_stack.pop()

        return class_info

    def _process_assignment(self, node: ast.Assign, module_info: ModuleInfo) -> None:
        """Process variable assignments at module level."""
        if not self.current_class_stack:  # Only global variables
            for target in node.targets:
                if isinstance(target, ast.Name):
                    module_info.global_variables.append(target.id)

    def _get_decorator_name(self, decorator: ast.AST) -> str:
        """Extract decorator name from AST node."""
        if isinstance(decorator, ast.Name):
            return decorator.id
        elif isinstance(decorator, ast.Attribute):
            return self._get_name_from_node(decorator)
        elif isinstance(decorator, ast.Call):
            return self._get_name_from_node(decorator.func)
        else:
            return str(decorator)

    def _get_name_from_node(self, node: ast.AST) -> Optional[str]:
        """Extract name from various AST node types."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_name_from_node(node.value)
            if value:
                return f"{value}.{node.attr}"
            return node.attr
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        else:
            return None

    def _find_function_calls(self, func_node: ast.AST) -> List[str]:
        """Find all function calls within a function."""
        calls = []

        for node in ast.walk(func_node):
            if isinstance(node, ast.Call):
                call_name = self._get_name_from_node(node.func)
                if call_name:
                    calls.append(call_name)

        return calls


class BatchParser:
    """
    Parse multiple Python files efficiently.
    """

    def __init__(self):
        self.parser = PythonASTParser()

    def parse_files(self, file_paths: List[Path]) -> Dict[Path, ModuleInfo]:
        """
        Parse multiple Python files.

        Args:
            file_paths: List of Python files to parse

        Returns:
            Dictionary mapping file paths to ModuleInfo objects
        """
        results = {}

        for file_path in file_paths:
            try:
                module_info = self.parser.parse_file(file_path)
                results[file_path] = module_info
            except Exception as e:
                # Create a ModuleInfo with error information
                error_info = ModuleInfo(
                    file_path=file_path, syntax_errors=[f"Failed to parse: {str(e)}"]
                )
                results[file_path] = error_info

        return results

    def get_import_graph(self, modules: Dict[Path, ModuleInfo]) -> Dict[str, Set[str]]:
        """
        Build an import dependency graph from parsed modules.

        Args:
            modules: Dictionary of parsed modules

        Returns:
            Dictionary mapping module names to sets of imported modules
        """
        import_graph = {}

        for file_path, module_info in modules.items():
            module_name = self._path_to_module_name(file_path)
            imported_modules = set()

            for import_info in module_info.imports:
                imported_modules.add(import_info.module)

            import_graph[module_name] = imported_modules

        return import_graph

    def get_inheritance_graph(
        self, modules: Dict[Path, ModuleInfo]
    ) -> Dict[str, Set[str]]:
        """
        Build a class inheritance graph from parsed modules.

        Args:
            modules: Dictionary of parsed modules

        Returns:
            Dictionary mapping class names to sets of base classes
        """
        inheritance_graph = {}

        for module_info in modules.values():
            for class_info in module_info.classes:
                class_name = class_info.name
                base_classes = set(class_info.bases)
                inheritance_graph[class_name] = base_classes

                # Include nested classes
                for nested_class in class_info.nested_classes:
                    nested_name = f"{class_name}.{nested_class.name}"
                    nested_bases = set(nested_class.bases)
                    inheritance_graph[nested_name] = nested_bases

        return inheritance_graph

    @staticmethod
    def _path_to_module_name(file_path: Path) -> str:
        """Convert a file path to a module name."""
        if file_path.name == "__init__.py":
            return str(file_path.parent).replace("/", ".")
        else:
            return str(file_path.with_suffix("")).replace("/", ".")
