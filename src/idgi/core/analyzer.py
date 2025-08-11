"""
High-level code analysis that combines scanning and parsing to build comprehensive views of codebases.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from .parser import BatchParser, ModuleInfo
from .scanner import DirectoryScanner, ScanResult


@dataclass
class AnalysisResult:
    """Complete analysis result of a Python codebase."""

    # Scanning results
    scan_result: ScanResult

    # Parsed module information
    modules: Dict[Path, ModuleInfo] = field(default_factory=dict)

    # Dependency graphs
    import_graph: Dict[str, Set[str]] = field(default_factory=dict)
    inheritance_graph: Dict[str, Set[str]] = field(default_factory=dict)
    call_graph: Dict[str, Set[str]] = field(default_factory=dict)

    # Statistics
    total_classes: int = 0
    total_functions: int = 0
    total_imports: int = 0

    # Error tracking
    parsing_errors: List[Tuple[Path, str]] = field(default_factory=list)


class CodebaseAnalyzer:
    """
    High-level analyzer that coordinates scanning and parsing to provide
    comprehensive analysis of Python codebases.
    """

    def __init__(
        self,
        exclude_patterns: Optional[List[str]] = None,
        include_patterns: Optional[List[str]] = None,
        max_workers: int = 4,
    ):
        """
        Initialize the codebase analyzer.

        Args:
            exclude_patterns: Patterns to exclude during scanning
            include_patterns: Patterns to include during scanning
            max_workers: Maximum number of parallel workers
        """
        self.scanner = DirectoryScanner(
            exclude_patterns=exclude_patterns,
            include_patterns=include_patterns,
            max_workers=max_workers,
        )
        self.batch_parser = BatchParser()
        self.max_workers = max_workers
        self.logger = logging.getLogger(__name__)

    def analyze(self, root_path: Path, recursive: bool = True) -> AnalysisResult:
        """
        Perform complete analysis of a codebase.

        Args:
            root_path: Root directory to analyze
            recursive: Whether to analyze recursively

        Returns:
            AnalysisResult containing all analysis information
        """
        self.logger.info(f"Starting analysis of {root_path}")

        # Step 1: Scan directory for Python files
        scan_result = self.scanner.scan(root_path, recursive)
        self.logger.info(f"Found {scan_result.total_files} Python files")

        # Step 2: Parse all Python files
        modules = self._parse_modules_parallel(scan_result.python_files)
        self.logger.info(f"Parsed {len(modules)} modules")

        # Step 3: Build dependency graphs
        import_graph = self.batch_parser.get_import_graph(modules)
        inheritance_graph = self.batch_parser.get_inheritance_graph(modules)
        call_graph = self._build_call_graph(modules)

        # Step 4: Calculate statistics
        total_classes, total_functions, total_imports = self._calculate_statistics(
            modules
        )

        # Step 5: Collect parsing errors
        parsing_errors = []
        for file_path, module_info in modules.items():
            for error in module_info.syntax_errors:
                parsing_errors.append((file_path, error))

        result = AnalysisResult(
            scan_result=scan_result,
            modules=modules,
            import_graph=import_graph,
            inheritance_graph=inheritance_graph,
            call_graph=call_graph,
            total_classes=total_classes,
            total_functions=total_functions,
            total_imports=total_imports,
            parsing_errors=parsing_errors,
        )

        self.logger.info(
            f"Analysis complete: {total_classes} classes, {total_functions} functions"
        )
        return result

    def _parse_modules_parallel(self, file_paths: List[Path]) -> Dict[Path, ModuleInfo]:
        """Parse modules in parallel for better performance."""
        modules = {}

        # For small numbers of files, don't use parallelization
        if len(file_paths) < 20:
            return self.batch_parser.parse_files(file_paths)

        # Split files into chunks for parallel processing
        chunk_size = max(1, len(file_paths) // self.max_workers)
        file_chunks = [
            file_paths[i : i + chunk_size]
            for i in range(0, len(file_paths), chunk_size)
        ]

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_chunk = {
                executor.submit(self.batch_parser.parse_files, chunk): chunk
                for chunk in file_chunks
            }

            for future in as_completed(future_to_chunk):
                try:
                    chunk_results = future.result()
                    modules.update(chunk_results)
                except Exception as e:
                    chunk = future_to_chunk[future]
                    self.logger.error(
                        f"Error parsing chunk with {len(chunk)} files: {e}"
                    )

        return modules

    def _build_call_graph(self, modules: Dict[Path, ModuleInfo]) -> Dict[str, Set[str]]:
        """
        Build a function call graph from parsed modules.

        Args:
            modules: Dictionary of parsed modules

        Returns:
            Dictionary mapping function names to sets of called functions
        """
        call_graph = {}

        for file_path, module_info in modules.items():
            module_name = self._path_to_module_name(file_path)

            # Add module-level functions
            for func_info in module_info.functions:
                func_full_name = f"{module_name}.{func_info.name}"
                call_graph[func_full_name] = set(func_info.calls)

            # Add class methods
            for class_info in module_info.classes:
                for method_info in class_info.methods:
                    method_full_name = (
                        f"{module_name}.{class_info.name}.{method_info.name}"
                    )
                    call_graph[method_full_name] = set(method_info.calls)

                # Handle nested classes
                for nested_class in class_info.nested_classes:
                    for method_info in nested_class.methods:
                        method_full_name = (
                            f"{module_name}.{class_info.name}."
                            f"{nested_class.name}.{method_info.name}"
                        )
                        call_graph[method_full_name] = set(method_info.calls)

        return call_graph

    def _calculate_statistics(
        self, modules: Dict[Path, ModuleInfo]
    ) -> Tuple[int, int, int]:
        """Calculate overall statistics from parsed modules."""
        total_classes = 0
        total_functions = 0
        total_imports = 0

        for module_info in modules.values():
            total_functions += len(module_info.functions)
            total_imports += len(module_info.imports)

            for class_info in module_info.classes:
                total_classes += 1
                total_functions += len(class_info.methods)

                # Count nested classes
                def count_nested(cls):
                    count = len(cls.nested_classes)
                    for nested in cls.nested_classes:
                        count += count_nested(nested)
                        count += len(nested.methods)
                    return count

                total_classes += count_nested(class_info)

        return total_classes, total_functions, total_imports

    def find_circular_imports(self, analysis_result: AnalysisResult) -> List[List[str]]:
        """
        Find circular import dependencies in the codebase.

        Args:
            analysis_result: Result from analyze() method

        Returns:
            List of circular dependency chains
        """
        import_graph = analysis_result.import_graph
        cycles = []
        visited = set()
        rec_stack = set()

        def dfs(node: str, path: List[str]) -> None:
            if node in rec_stack:
                # Found a cycle
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                cycles.append(cycle)
                return

            if node in visited:
                return

            visited.add(node)
            rec_stack.add(node)

            for neighbor in import_graph.get(node, set()):
                if neighbor in import_graph:  # Only follow imports we know about
                    dfs(neighbor, path + [node])

            rec_stack.remove(node)

        for module in import_graph:
            if module not in visited:
                dfs(module, [])

        return cycles

    def find_unused_imports(
        self, analysis_result: AnalysisResult
    ) -> Dict[Path, List[str]]:
        """
        Find potentially unused imports in modules.

        Args:
            analysis_result: Result from analyze() method

        Returns:
            Dictionary mapping file paths to lists of unused import names
        """
        unused_imports = {}

        for file_path, module_info in analysis_result.modules.items():
            unused_in_module = []

            for import_info in module_info.imports:
                # This is a simple heuristic - in a real implementation,
                # you'd need to check if the imported names are actually used
                # For now, we'll mark imports as unused if they're not referenced
                # in function calls or class definitions

                all_names = set()

                # Collect all names used in the module
                for func_info in module_info.functions:
                    all_names.update(func_info.calls)

                for class_info in module_info.classes:
                    all_names.update(class_info.bases)
                    for method in class_info.methods:
                        all_names.update(method.calls)

                # Check if any imported names are used
                imported_names = set(import_info.names)
                if import_info.aliases:
                    imported_names.update(import_info.aliases.values())

                if not imported_names.intersection(all_names):
                    unused_in_module.append(import_info.module)

            if unused_in_module:
                unused_imports[file_path] = unused_in_module

        return unused_imports

    def get_complexity_metrics(
        self, analysis_result: AnalysisResult
    ) -> Dict[str, Dict[str, int]]:
        """
        Calculate complexity metrics for the codebase.

        Args:
            analysis_result: Result from analyze() method

        Returns:
            Dictionary with complexity metrics per module
        """
        metrics = {}

        for file_path, module_info in analysis_result.modules.items():
            module_name = self._path_to_module_name(file_path)

            # Calculate various metrics
            module_metrics = {
                "lines_of_code": module_info.line_count,
                "num_functions": len(module_info.functions),
                "num_classes": len(module_info.classes),
                "num_imports": len(module_info.imports),
                "cyclomatic_complexity": self._estimate_complexity(module_info),
                "avg_function_length": self._avg_function_length(module_info),
            }

            metrics[module_name] = module_metrics

        return metrics

    def _estimate_complexity(self, module_info: ModuleInfo) -> int:
        """Estimate cyclomatic complexity (simplified)."""
        # This is a very simplified estimate - real cyclomatic complexity
        # would require analyzing control flow structures
        complexity = 1  # Base complexity

        for func_info in module_info.functions:
            complexity += len(func_info.calls) // 10  # Rough estimate

        for class_info in module_info.classes:
            for method in class_info.methods:
                complexity += len(method.calls) // 10

        return complexity

    def _avg_function_length(self, module_info: ModuleInfo) -> float:
        """Calculate average function length in lines."""
        total_length = 0
        total_functions = 0

        for func_info in module_info.functions:
            total_length += func_info.line_end - func_info.line_start + 1
            total_functions += 1

        for class_info in module_info.classes:
            for method in class_info.methods:
                total_length += method.line_end - method.line_start + 1
                total_functions += 1

        return total_length / total_functions if total_functions > 0 else 0.0

    @staticmethod
    def _path_to_module_name(file_path: Path) -> str:
        """Convert a file path to a module name."""
        if file_path.name == "__init__.py":
            return str(file_path.parent).replace("/", ".").replace("\\", ".")
        else:
            return str(file_path.with_suffix("")).replace("/", ".").replace("\\", ".")
