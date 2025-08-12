# idgi

A command-line tool for exploring and visualizing large Python codebases.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9+-blue.svg)

## Installation

### Install with uv

```bash
uv add idgi
```

### Install with pip

```bash
pip install idgi
```

### Prerequisites

- Python 3.9 or higher

### Optional: Graphviz for Visual Exports

For SVG/PNG export functionality, install Graphviz:

```bash
# macOS
brew install graphviz

# Ubuntu/Debian
sudo apt-get install graphviz
```

### Install from Source (Development)

```bash
git clone https://github.com/kokkodev/idgi.git
cd idgi
uv sync
```

## Getting Started

Once installed, you can start exploring any Python codebase:

```bash
# Analyze your project
idgi scan ./your_project

# Visualize dependencies
idgi graph --type imports ./your_project

# Search for specific code elements
idgi search "MyClass" ./your_project
```

## Quick Start

### 1. Scan a Project

```bash
# Basic scan
idgi scan ./my_project

# Scan with exclusions
idgi scan ./my_project --exclude venv --exclude tests
```

### 2. Visualize Dependencies

```bash
# Show import dependencies as ASCII tree
idgi graph --type imports ./my_project

# Interactive exploration mode
idgi graph --type imports --interactive ./my_project

# Export to SVG (using graph command)
idgi graph --type imports --output dependencies.svg ./my_project

# Or use export command for multiple formats
idgi export --output ./graphs --format svg --types imports ./my_project

# Show class inheritance hierarchy
idgi graph --type inheritance --format hierarchy ./my_project
```

### 3. Search Code Elements

```bash
# Search for classes, functions, or modules
idgi search "DataLoader" ./my_project

# Limit results
idgi search "test" ./my_project --limit 20
```

### 4. Export Multiple Formats

```bash
# Export all graph types to multiple formats
idgi export ./my_project --output ./graphs --format svg --format json

# Export specific graph types
idgi export ./my_project --output ./graphs --types imports --types inheritance
```

## Usage Guide

### Commands

#### `scan` - Analyze Codebase Structure

Recursively scans a directory to analyze Python files and packages.

```bash
idgi scan [OPTIONS] DIRECTORY

Options:
  --exclude PATTERN          Exclude files/directories matching pattern
  --no-recursive             Don't scan recursively
  --show-packages            Show package breakdown
  --show-errors              Show parsing errors
```

**Example Output:**
```
┌─────────────────┬─────────┐
│ Metric          │ Count   │
├─────────────────┼─────────┤
│ Python files    │ 1,247   │
│ Total lines     │ 45,123  │
│ Packages        │ 23      │
│ Classes         │ 156     │
│ Functions       │ 489     │
│ Import statements│ 234    │
└─────────────────┴─────────┘
```

#### `graph` - Generate and Display Graphs

Creates various types of dependency and relationship graphs.

```bash
idgi graph [OPTIONS] DIRECTORY

Options:
  --type {imports,inheritance,calls,modules,classes,functions}
                             Type of graph to generate (default: imports)
  --format {tree,network,hierarchy}
                             Display format (default: network)
  --interactive, -i          Interactive exploration mode
  --output OUTPUT            Output file (exports to file instead of display)
  --max-nodes N              Maximum nodes to display
  --depth N                  Tree depth for tree format (default: 3)
  --stats                    Show graph statistics
  --exclude EXCLUDE          Patterns to exclude
```

**Graph Types:**

- **imports**: Module dependency graph showing import relationships
- **inheritance**: Class inheritance hierarchy
- **calls**: Function call relationships
- **modules**: High-level module overview
- **classes**: Class-focused relationship graph
- **functions**: Function and method relationships

#### `search` - Find Code Elements

Search for specific classes, functions, or modules by name.

```bash
idgi search [OPTIONS] TERM DIRECTORY

Options:
  --limit N                  Maximum results to show
  --exclude EXCLUDE          Patterns to exclude
```

#### `export` - Export Graphs to Files

Export multiple graph types to various file formats.

```bash
idgi export [OPTIONS] DIRECTORY

Options:
  --output DIR               Output directory (required)
  --format {svg,png,pdf,json,dot,gml,graphml}
                             Export formats (can be specified multiple times)
  --types {imports,inheritance,calls,modules,classes,functions}
                             Graph types to export
  --exclude EXCLUDE          Patterns to exclude
```

**Supported Export Formats:**

| Format | Description | Use Case |
|--------|-------------|----------|
| SVG | Scalable Vector Graphics | Web display, documentation |
| PNG | Portable Network Graphics | Reports, presentations |
| PDF | Portable Document Format | Printing, formal documents |
| JSON | Structured data | Further analysis, web apps |
| DOT | Graphviz source | Custom styling, editing |
| GML | Graph Modeling Language | Academic research |
| GraphML | XML-based graph format | Tool interoperability |

### Interactive Mode

The interactive mode provides a terminal-based interface for exploring graphs:

```bash
idgi graph --type imports --interactive ./my_project
```

**Interactive Commands:**

| Command | Alias | Description |
|---------|-------|-------------|
| `show` | `s` | Display current node details |
| `neighbors` | `n` | Show connected nodes |
| `goto <node>` | `g` | Navigate to specific node |
| `back` | `b` | Go back to previous node |
| `search <term>` | `f` | Search for nodes containing term |
| `tree [depth]` | `t` | Show tree view |
| `path <target>` | `p` | Find shortest path to target |
| `bookmark <name>` | `bm` | Manage bookmarks |
| `stats` | | Display graph statistics |
| `help` | `h` | Show all commands |

### Filtering and Exclusions

idgi automatically excludes common directories and files that are typically not relevant for code analysis:

**Default Exclusions:**
- Python cache: `__pycache__`, `*.pyc`, `*.pyo`, `*.pyd`
- Virtual environments: `venv`, `env`, `.venv`, `virtualenv`
- Version control: `.git`, `.svn`, `.hg`
- IDE files: `.vscode`, `.idea`, `*.swp`
- Build artifacts: `build`, `dist`, `*.egg-info`

**Custom Exclusions:**
```bash
# Exclude additional patterns
idgi scan ./project --exclude tests --exclude "temp_*" --exclude docs

# Use regex patterns (wrap in forward slashes)
idgi scan ./project --exclude "/test.*\.py/"
```

## Architecture Overview

idgi follows a modular architecture with clear separation of concerns:

```
idgi/
├── core/           # Core analysis functionality
│   ├── scanner.py  # Directory scanning and file discovery
│   ├── parser.py   # Python AST parsing
│   └── analyzer.py # High-level codebase analysis
├── graph/          # Graph generation and visualization
│   ├── builder.py  # NetworkX graph construction
│   ├── visualizer.py # ASCII and Graphviz rendering
│   └── interactive.py # Terminal-based exploration
├── export/         # Export functionality
│   └── formats.py  # Multi-format export support
├── utils/          # Utility modules
│   ├── filters.py  # Path filtering and exclusions
│   └── cache.py    # Performance caching
└── cli.py          # Command-line interface
```

**Performance Tips:**

```bash
# Use verbose output for debugging
idgi scan ./project --verbose

# Limit graph size for better performance
idgi graph --type imports --max-nodes 100 ./project

# Use exclusion patterns for focused analysis
idgi scan ./project --exclude tests --exclude docs
```

## Examples

### Analyzing a Django Project

```bash
# Scan Django project excluding common non-code directories
idgi scan ./myproject --exclude venv --exclude static --exclude media

# Show model inheritance hierarchy
idgi graph --type inheritance ./myproject --format hierarchy

# Find all views
idgi search "View" ./myproject --limit 30

# Export comprehensive analysis
idgi export ./myproject --output ./analysis \
  --format svg --format json --types imports --types inheritance --types calls
```

### Large Codebase Analysis

```bash
# Scan with exclusions
idgi scan ./large_project --exclude "test_*"

# Interactive exploration starting with imports
idgi graph --type imports --interactive ./large_project --max-nodes 200

# Export key relationships only
idgi export ./large_project --output ./docs \
  --types imports --types modules --format svg
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
