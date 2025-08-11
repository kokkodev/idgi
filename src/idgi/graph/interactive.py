"""
Interactive terminal-based graph navigation and exploration.
"""

from typing import Dict, List, Optional

import networkx as nx
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from .visualizer import ASCIIGraphVisualizer


class InteractiveGraphExplorer:
    """
    Interactive terminal interface for exploring graphs.
    """

    def __init__(self, graph: nx.DiGraph, graph_type: str = "graph"):
        """
        Initialize the interactive explorer.

        Args:
            graph: NetworkX directed graph to explore
            graph_type: Type description of the graph (for display)
        """
        self.graph = graph
        self.graph_type = graph_type
        self.console = Console()
        self.visualizer = ASCIIGraphVisualizer(self.console)

        self.current_node: Optional[str] = None
        self.visited_nodes: List[str] = []
        self.bookmarks: Dict[str, str] = {}
        self.search_history: List[str] = []

        # Find initial node (prefer nodes with high connectivity)
        if graph.nodes():
            centrality = nx.degree_centrality(graph)
            self.current_node = max(centrality.items(), key=lambda x: x[1])[0]

    def run(self) -> None:
        """Start the interactive exploration session."""
        self.console.print(
            Panel.fit(
                f"Interactive {self.graph_type.title()} Explorer\n\n"
                f"Nodes: {len(self.graph.nodes())} | Edges: {len(self.graph.edges())}\n"
                "Type 'help' for commands",
                title="🔍 idgi Interactive Mode",
            )
        )

        if not self.graph.nodes():
            self.console.print("[red]No nodes in graph to explore[/red]")
            return

        self.console.print(f"Starting at: [cyan]{self.current_node}[/cyan]")

        while True:
            try:
                command = (
                    Prompt.ask(
                        f"\n[bold]({self._get_current_context()})[/bold]", default=""
                    )
                    .strip()
                    .lower()
                )

                if not command:
                    self._show_current_node()
                    continue

                if not self._handle_command(command):
                    break

            except KeyboardInterrupt:
                self.console.print("\n[yellow]Exiting...[/yellow]")
                break
            except Exception as e:
                self.console.print(f"[red]Error: {e}[/red]")

    def _handle_command(self, command: str) -> bool:
        """
        Handle user commands.

        Args:
            command: Command string from user

        Returns:
            False if should exit, True to continue
        """
        parts = command.split(maxsplit=1)
        cmd = parts[0]
        args = parts[1] if len(parts) > 1 else ""

        if cmd in ["exit", "quit", "q"]:
            return False
        elif cmd in ["help", "h", "?"]:
            self._show_help()
        elif cmd in ["show", "display", "s"]:
            self._show_current_node()
        elif cmd in ["neighbors", "n"]:
            self._show_neighbors()
        elif cmd in ["goto", "g"]:
            self._goto_node(args)
        elif cmd in ["back", "b"]:
            self._go_back()
        elif cmd in ["search", "find", "f"]:
            self._search_nodes(args)
        elif cmd in ["filter", "fl"]:
            self._filter_view(args)
        elif cmd in ["tree", "t"]:
            self._show_tree_view(int(args) if args.isdigit() else 3)
        elif cmd in ["network", "net"]:
            self._show_network_view()
        elif cmd in ["stats", "statistics"]:
            self._show_statistics()
        elif cmd in ["bookmark", "bm"]:
            self._manage_bookmarks(args)
        elif cmd in ["history", "hist"]:
            self._show_history()
        elif cmd in ["centrality", "cent"]:
            self._show_centrality()
        elif cmd in ["path", "p"]:
            self._find_path(args)
        elif cmd in ["subgraph", "sub"]:
            self._show_subgraph(int(args) if args.isdigit() else 2)
        else:
            # Try to interpret as node name
            if self._node_exists(command):
                self._goto_node(command)
            else:
                self.console.print(f"[red]Unknown command: {command}[/red]")
                self.console.print("Type 'help' for available commands")

        return True

    def _show_help(self) -> None:
        """Display help information."""
        help_table = Table(title="Interactive Commands")
        help_table.add_column("Command", style="cyan")
        help_table.add_column("Alias", style="blue")
        help_table.add_column("Description", style="white")

        commands = [
            ("show", "s", "Display current node details"),
            ("neighbors", "n", "Show connected nodes"),
            ("goto <node>", "g", "Navigate to specific node"),
            ("back", "b", "Go back to previous node"),
            ("search <term>", "f", "Search for nodes containing term"),
            ("tree [depth]", "t", "Show tree view (default depth: 3)"),
            ("network", "net", "Show network overview"),
            ("stats", "", "Display graph statistics"),
            ("centrality", "cent", "Show most important nodes"),
            ("path <target>", "p", "Find shortest path to target node"),
            ("subgraph [depth]", "sub", "Show subgraph around current node"),
            ("bookmark <name>", "bm", "Manage bookmarks (add/list/goto)"),
            ("history", "hist", "Show visited nodes"),
            ("filter <type>", "fl", "Filter nodes by type"),
            ("help", "h/?", "Show this help"),
            ("exit", "q", "Exit interactive mode"),
        ]

        for command, alias, desc in commands:
            help_table.add_row(command, alias, desc)

        self.console.print(help_table)

    def _show_current_node(self) -> None:
        """Display detailed information about the current node."""
        if not self.current_node:
            self.console.print("[red]No current node[/red]")
            return

        node_data = self.graph.nodes[self.current_node]

        # Create info panel
        info_lines = [f"[bold]Node:[/bold] {self.current_node}"]

        # Add node attributes
        for key, value in node_data.items():
            if key != "type":
                info_lines.append(
                    f"[bold]{key.replace('_', ' ').title()}:[/bold] {value}"
                )

        # Add connectivity info
        in_degree = self.graph.in_degree(self.current_node)
        out_degree = self.graph.out_degree(self.current_node)
        info_lines.append(f"[bold]Connections:[/bold] {in_degree} in, {out_degree} out")

        self.console.print(Panel("\n".join(info_lines), title="Current Node"))

        # Show immediate neighbors
        self._show_neighbors_brief()

    def _show_neighbors(self) -> None:
        """Show detailed view of neighboring nodes."""
        if not self.current_node:
            return

        # Incoming connections
        predecessors = list(self.graph.predecessors(self.current_node))
        if predecessors:
            pred_table = Table(title="← Incoming Connections")
            pred_table.add_column("Node", style="cyan")
            pred_table.add_column("Type", style="blue")
            pred_table.add_column("Relationship", style="green")

            for pred in predecessors:
                node_type = self.graph.nodes[pred].get("type", "unknown")
                relationship = self.graph.edges[pred, self.current_node].get(
                    "relationship", "-"
                )
                pred_table.add_row(pred, node_type, relationship)

            self.console.print(pred_table)

        # Outgoing connections
        successors = list(self.graph.successors(self.current_node))
        if successors:
            succ_table = Table(title="→ Outgoing Connections")
            succ_table.add_column("Node", style="cyan")
            succ_table.add_column("Type", style="blue")
            succ_table.add_column("Relationship", style="green")

            for succ in successors:
                node_type = self.graph.nodes[succ].get("type", "unknown")
                relationship = self.graph.edges[self.current_node, succ].get(
                    "relationship", "-"
                )
                succ_table.add_row(succ, node_type, relationship)

            self.console.print(succ_table)

        if not predecessors and not successors:
            self.console.print("[yellow]No connections found[/yellow]")

    def _show_neighbors_brief(self) -> None:
        """Show brief neighbor information."""
        if not self.current_node:
            return

        predecessors = list(self.graph.predecessors(self.current_node))
        successors = list(self.graph.successors(self.current_node))

        if predecessors:
            pred_text = ", ".join(predecessors[:5])
            if len(predecessors) > 5:
                pred_text += f" ... (+{len(predecessors) - 5} more)"
            self.console.print(f"[dim]← From:[/dim] {pred_text}")

        if successors:
            succ_text = ", ".join(successors[:5])
            if len(successors) > 5:
                succ_text += f" ... (+{len(successors) - 5} more)"
            self.console.print(f"[dim]→ To:[/dim] {succ_text}")

    def _goto_node(self, node_name: str) -> None:
        """Navigate to a specific node."""
        if not node_name:
            self.console.print("[red]Please specify a node name[/red]")
            return

        # Try to find exact match first
        if node_name in self.graph.nodes():
            self._navigate_to(node_name)
            return

        # Try partial matching
        matches = [
            node for node in self.graph.nodes() if node_name.lower() in node.lower()
        ]

        if not matches:
            self.console.print(f"[red]No node found matching '{node_name}'[/red]")
            return
        elif len(matches) == 1:
            self._navigate_to(matches[0])
            return
        else:
            # Multiple matches - show options
            self.console.print(f"Multiple matches for '{node_name}':")
            for i, match in enumerate(matches[:10], 1):
                self.console.print(f"  {i}. {match}")

            if len(matches) > 10:
                self.console.print(f"  ... and {len(matches) - 10} more")

            try:
                choice = Prompt.ask("Select node number (or 0 to cancel)", default="0")
                choice_num = int(choice)
                if 1 <= choice_num <= min(len(matches), 10):
                    self._navigate_to(matches[choice_num - 1])
            except (ValueError, IndexError):
                self.console.print("[yellow]Invalid selection[/yellow]")

    def _navigate_to(self, node_name: str) -> None:
        """Navigate to a node and update history."""
        if self.current_node:
            self.visited_nodes.append(self.current_node)

        self.current_node = node_name
        self.console.print(f"[green]Moved to:[/green] [cyan]{node_name}[/cyan]")
        self._show_current_node()

    def _go_back(self) -> None:
        """Go back to the previous node."""
        if not self.visited_nodes:
            self.console.print("[yellow]No previous node[/yellow]")
            return

        previous = self.visited_nodes.pop()
        self.current_node = previous
        self.console.print(f"[green]Back to:[/green] [cyan]{previous}[/cyan]")
        self._show_current_node()

    def _search_nodes(self, search_term: str) -> None:
        """Search for nodes matching a term."""
        if not search_term:
            search_term = Prompt.ask("Enter search term")

        self.search_history.append(search_term)
        matches = [
            node for node in self.graph.nodes() if search_term.lower() in node.lower()
        ]

        if not matches:
            self.console.print(f"[red]No nodes found matching '{search_term}'[/red]")
            return

        search_table = Table(title=f"Search Results: '{search_term}'")
        search_table.add_column("#", style="dim")
        search_table.add_column("Node", style="cyan")
        search_table.add_column("Type", style="blue")
        search_table.add_column("Connections", style="yellow")

        for i, node in enumerate(matches[:20], 1):
            node_type = self.graph.nodes[node].get("type", "unknown")
            connections = self.graph.in_degree(node) + self.graph.out_degree(node)
            search_table.add_row(str(i), node, node_type, str(connections))

        if len(matches) > 20:
            search_table.add_row("...", f"({len(matches) - 20} more)", "", "")

        self.console.print(search_table)

        # Offer to navigate to result
        if matches:
            try:
                choice = Prompt.ask(
                    "Navigate to result # (or press Enter to continue)", default=""
                )
                if choice.isdigit():
                    choice_num = int(choice)
                    if 1 <= choice_num <= min(len(matches), 20):
                        self._navigate_to(matches[choice_num - 1])
            except ValueError:
                pass

    def _show_tree_view(self, depth: int) -> None:
        """Show tree view from current node."""
        if not self.current_node:
            return

        tree_output = self.visualizer.visualize_tree(
            self.graph, self.current_node, max_depth=depth
        )
        self.console.print(tree_output)

    def _show_network_view(self) -> None:
        """Show network overview."""
        network_output = self.visualizer.visualize_network(self.graph)
        self.console.print(network_output)

    def _show_statistics(self) -> None:
        """Show graph statistics."""
        stats_output = self.visualizer.create_summary_table(self.graph)
        self.console.print(stats_output)

    def _show_centrality(self) -> None:
        """Show most important nodes."""
        centrality_output = self.visualizer.find_important_nodes(self.graph)
        self.console.print(centrality_output)

    def _find_path(self, target: str) -> None:
        """Find shortest path to target node."""
        if not target:
            target = Prompt.ask("Enter target node")

        if target not in self.graph.nodes():
            self.console.print(f"[red]Node '{target}' not found[/red]")
            return

        if not self.current_node:
            self.console.print("[red]No current node[/red]")
            return

        try:
            path = nx.shortest_path(self.graph, self.current_node, target)
            path_length = len(path) - 1

            self.console.print(f"[green]Shortest path ({path_length} steps):[/green]")

            for i, node in enumerate(path):
                if i == 0:
                    self.console.print(f"  [cyan]{node}[/cyan] (start)")
                elif i == len(path) - 1:
                    self.console.print(f"  [cyan]{node}[/cyan] (target)")
                else:
                    self.console.print(f"  [cyan]{node}[/cyan]")

                if i < len(path) - 1:
                    relationship = self.graph.edges[path[i], path[i + 1]].get(
                        "relationship", ""
                    )
                    arrow = f" --{relationship}-->" if relationship else " -->"
                    self.console.print(f"   {arrow}")

        except nx.NetworkXNoPath:
            self.console.print(
                f"[red]No path found from {self.current_node} to {target}[/red]"
            )
        except Exception as e:
            self.console.print(f"[red]Error finding path: {e}[/red]")

    def _show_subgraph(self, depth: int) -> None:
        """Show subgraph around current node."""
        if not self.current_node:
            return

        # This is a simplified version - in practice you'd use the GraphBuilder's get_subgraph method
        neighbors = set([self.current_node])
        current_level = set([self.current_node])

        for _ in range(depth):
            next_level = set()
            for node in current_level:
                next_level.update(self.graph.predecessors(node))
                next_level.update(self.graph.successors(node))
            current_level = next_level - neighbors
            neighbors.update(current_level)

        subgraph = self.graph.subgraph(neighbors)

        self.console.print(
            f"[blue]Subgraph around {self.current_node} (depth {depth}):[/blue]"
        )
        network_output = self.visualizer.visualize_network(subgraph, max_nodes=50)
        self.console.print(network_output)

    def _manage_bookmarks(self, args: str) -> None:
        """Manage bookmarks."""
        if not args:
            if self.bookmarks:
                bookmark_table = Table(title="Bookmarks")
                bookmark_table.add_column("Name", style="cyan")
                bookmark_table.add_column("Node", style="white")

                for name, node in self.bookmarks.items():
                    bookmark_table.add_row(name, node)

                self.console.print(bookmark_table)
            else:
                self.console.print("[yellow]No bookmarks saved[/yellow]")
            return

        parts = args.split(maxsplit=1)
        action = parts[0]

        if action == "add":
            if len(parts) < 2:
                name = Prompt.ask("Bookmark name")
            else:
                name = parts[1]

            if self.current_node:
                self.bookmarks[name] = self.current_node
                self.console.print(
                    f"[green]Bookmarked {self.current_node} as '{name}'[/green]"
                )
            else:
                self.console.print("[red]No current node to bookmark[/red]")

        elif action in self.bookmarks:
            # Go to bookmark
            self._navigate_to(self.bookmarks[action])
        else:
            self.console.print(f"[red]Unknown bookmark action or name: {action}[/red]")

    def _show_history(self) -> None:
        """Show navigation history."""
        if not self.visited_nodes:
            self.console.print("[yellow]No history[/yellow]")
            return

        history_table = Table(title="Navigation History")
        history_table.add_column("#", style="dim")
        history_table.add_column("Node", style="cyan")

        for i, node in enumerate(reversed(self.visited_nodes[-10:]), 1):
            history_table.add_row(str(i), node)

        self.console.print(history_table)

    def _filter_view(self, node_type: str) -> None:
        """Filter view by node type."""
        if not node_type:
            # Show available types
            types = set()
            for node in self.graph.nodes():
                node_data = self.graph.nodes[node]
                types.add(node_data.get("type", "unknown"))

            self.console.print(f"Available types: {', '.join(sorted(types))}")
            return

        matching_nodes = [
            node
            for node in self.graph.nodes()
            if self.graph.nodes[node].get("type", "unknown") == node_type
        ]

        if not matching_nodes:
            self.console.print(f"[red]No nodes of type '{node_type}'[/red]")
            return

        filter_table = Table(title=f"Nodes of type '{node_type}'")
        filter_table.add_column("Node", style="cyan")
        filter_table.add_column("Connections", style="yellow")

        for node in sorted(matching_nodes)[:50]:  # Limit display
            connections = self.graph.in_degree(node) + self.graph.out_degree(node)
            filter_table.add_row(node, str(connections))

        if len(matching_nodes) > 50:
            filter_table.add_row(f"... and {len(matching_nodes) - 50} more", "")

        self.console.print(filter_table)

    def _node_exists(self, node_name: str) -> bool:
        """Check if a node exists in the graph."""
        return node_name in self.graph.nodes()

    def _get_current_context(self) -> str:
        """Get current context for prompt."""
        if not self.current_node:
            return "no node"

        node_type = self.graph.nodes[self.current_node].get("type", "")
        short_name = (
            self.current_node.split(".")[-1]
            if "." in self.current_node
            else self.current_node
        )

        if len(short_name) > 20:
            short_name = short_name[:17] + "..."

        context = f"{short_name}"
        if node_type:
            context = f"{node_type}:{context}"

        return context
