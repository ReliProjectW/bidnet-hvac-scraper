#!/usr/bin/env python3
"""
Manual Contract Selection Interface
==================================

Cost-effective interface for selecting contracts for AI processing.
Allows users to review and select specific contracts before expensive 
AI pattern discovery and deep extraction.

Key features:
- Browse contracts by region and priority
- Preview contract details before selection
- Batch selection for cost optimization
- Processing queue management
- Cost estimation and tracking
"""

import sys
import os
import argparse
from datetime import datetime
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.connection import DatabaseManager
from src.database.models import Contract, ProcessingQueue, ProcessingStatus, GeographicRegion
from src.geographic.filter import GeographicFilter

console = Console()

class ManualSelectionInterface:
    """Interactive interface for manual contract selection"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.geo_filter = GeographicFilter()
        
    def run(self):
        """Run the interactive selection interface"""
        console.print("\n🤖 [bold cyan]Manual Contract Selection Interface[/bold cyan]")
        console.print("Select contracts for AI processing to optimize costs\n")
        
        while True:
            try:
                self._show_main_menu()
                choice = Prompt.ask("Select option", choices=["1", "2", "3", "4", "5", "6", "q"])
                
                if choice == "q":
                    console.print("👋 Goodbye!")
                    break
                elif choice == "1":
                    self._browse_contracts_by_region()
                elif choice == "2":
                    self._search_contracts()
                elif choice == "3":
                    self._review_selected_contracts()
                elif choice == "4":
                    self._show_cost_estimates()
                elif choice == "5":
                    self._process_selected_contracts()
                elif choice == "6":
                    self._show_processing_status()
                    
            except KeyboardInterrupt:
                console.print("\n👋 Goodbye!")
                break
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")
    
    def _show_main_menu(self):
        """Display the main menu options"""
        console.print("\n[bold]📋 Main Menu[/bold]")
        console.print("1. 🗺️  Browse contracts by region")
        console.print("2. 🔍 Search contracts") 
        console.print("3. 📝 Review selected contracts")
        console.print("4. 💰 Show cost estimates")
        console.print("5. 🚀 Process selected contracts")
        console.print("6. 📊 Show processing status")
        console.print("q. ❌ Quit")
    
    def _browse_contracts_by_region(self):
        """Browse contracts organized by geographic region"""
        console.print("\n[bold]🗺️ Browse Contracts by Region[/bold]")
        
        with self.db.get_session() as session:
            # Get contract counts by region
            region_counts = self._get_contract_counts_by_region(session)
            
            if not region_counts:
                console.print("[yellow]No contracts found in database[/yellow]")
                return
            
            # Show region summary
            table = Table(title="Contract Counts by Region")
            table.add_column("Region", style="cyan")
            table.add_column("Contracts", justify="right", style="green")
            table.add_column("Priority", justify="center")
            
            region_choices = []
            for region, count in region_counts.items():
                priority = self.geo_filter.get_region_priority_score(GeographicRegion(region))
                table.add_row(region.replace('_', ' ').title(), str(count), f"⭐" * (priority // 2))
                region_choices.append(region)
            
            console.print(table)
            
            if not region_choices:
                return
            
            # Let user select a region to browse
            region_choice = Prompt.ask(
                "Select region to browse",
                choices=region_choices + ["back"],
                default="back"
            )
            
            if region_choice != "back":
                self._browse_region_contracts(session, region_choice)
    
    def _browse_region_contracts(self, session, region: str):
        """Browse contracts within a specific region"""
        console.print(f"\n[bold]📋 Contracts in {region.replace('_', ' ').title()}[/bold]")
        
        # Get contracts for this region
        contracts = session.query(Contract).filter(
            Contract.geographic_region == GeographicRegion(region)
        ).order_by(Contract.discovered_at.desc()).limit(20).all()
        
        if not contracts:
            console.print("[yellow]No contracts found for this region[/yellow]")
            return
        
        # Display contracts table
        table = Table(title=f"Recent Contracts - {region.replace('_', ' ').title()}")
        table.add_column("ID", width=6)
        table.add_column("Title", min_width=30, max_width=50)
        table.add_column("Agency", min_width=20, max_width=30)
        table.add_column("Location", min_width=15, max_width=25)
        table.add_column("Status", width=12)
        table.add_column("Selected", width=8, justify="center")
        
        contract_ids = []
        for contract in contracts:
            # Check if already in processing queue
            is_selected = self._is_contract_selected(session, contract.id)
            status_color = self._get_status_color(contract.processing_status)
            
            table.add_row(
                str(contract.id),
                contract.title[:47] + "..." if len(contract.title) > 50 else contract.title,
                contract.agency[:27] + "..." if len(contract.agency) > 30 else contract.agency,
                contract.location[:22] + "..." if len(contract.location) > 25 else contract.location,
                f"[{status_color}]{contract.processing_status.value}[/{status_color}]",
                "✅" if is_selected else "⭕"
            )
            contract_ids.append(str(contract.id))
        
        console.print(table)
        
        # Contract selection menu
        self._contract_selection_menu(session, contracts, contract_ids)
    
    def _contract_selection_menu(self, session, contracts: List[Contract], contract_ids: List[str]):
        """Handle contract selection operations"""
        while True:
            console.print("\n[bold]Contract Actions:[/bold]")
            console.print("• Enter contract ID(s) to select/deselect (comma-separated)")
            console.print("• 'details <id>' to view contract details")
            console.print("• 'all' to select all contracts")
            console.print("• 'none' to deselect all contracts")
            console.print("• 'back' to return to region menu")
            
            action = Prompt.ask("Action").strip().lower()
            
            if action == "back":
                break
            elif action == "all":
                self._select_all_contracts(session, contracts)
            elif action == "none":
                self._deselect_all_contracts(session, contracts)
            elif action.startswith("details "):
                try:
                    contract_id = int(action.split()[1])
                    self._show_contract_details(session, contract_id)
                except (IndexError, ValueError):
                    console.print("[red]Invalid contract ID format[/red]")
            else:
                # Parse contract ID selection
                try:
                    selected_ids = [int(id.strip()) for id in action.split(",")]
                    self._toggle_contract_selection(session, selected_ids)
                except ValueError:
                    console.print("[red]Invalid format. Use comma-separated numbers or commands[/red]")
    
    def _toggle_contract_selection(self, session, contract_ids: List[int]):
        """Toggle selection status for given contract IDs"""
        for contract_id in contract_ids:
            contract = session.query(Contract).get(contract_id)
            if not contract:
                console.print(f"[red]Contract {contract_id} not found[/red]")
                continue
            
            # Check if already selected
            existing = session.query(ProcessingQueue).filter(
                ProcessingQueue.target_id == str(contract_id),
                ProcessingQueue.task_type == "ai_analysis",
                ProcessingQueue.status == ProcessingStatus.PENDING
            ).first()
            
            if existing:
                # Remove from queue
                session.delete(existing)
                console.print(f"[yellow]Deselected contract {contract_id}: {contract.title[:50]}[/yellow]")
            else:
                # Add to queue
                queue_item = ProcessingQueue(
                    task_type="ai_analysis",
                    target_id=str(contract_id),
                    priority=self.geo_filter.get_region_priority_score(contract.geographic_region),
                    status=ProcessingStatus.PENDING,
                    manually_selected=True,
                    selected_by="manual_interface",
                    config_data={"contract_title": contract.title}
                )
                session.add(queue_item)
                console.print(f"[green]Selected contract {contract_id}: {contract.title[:50]}[/green]")
        
        session.commit()
    
    def _select_all_contracts(self, session, contracts: List[Contract]):
        """Select all contracts in the current list"""
        if Confirm.ask(f"Select all {len(contracts)} contracts for processing?"):
            contract_ids = [contract.id for contract in contracts]
            self._toggle_contract_selection(session, contract_ids)
    
    def _deselect_all_contracts(self, session, contracts: List[Contract]):
        """Deselect all contracts in the current list"""
        if Confirm.ask("Remove all contracts from processing queue?"):
            for contract in contracts:
                existing = session.query(ProcessingQueue).filter(
                    ProcessingQueue.target_id == str(contract.id),
                    ProcessingQueue.task_type == "ai_analysis"
                ).first()
                if existing:
                    session.delete(existing)
            session.commit()
            console.print("[yellow]Cleared all selections[/yellow]")
    
    def _show_contract_details(self, session, contract_id: int):
        """Show detailed information for a specific contract"""
        contract = session.query(Contract).get(contract_id)
        if not contract:
            console.print(f"[red]Contract {contract_id} not found[/red]")
            return
        
        console.print(f"\n[bold cyan]📋 Contract Details - ID {contract_id}[/bold cyan]")
        
        details_table = Table(show_header=False, box=None)
        details_table.add_column("Field", style="bold", width=20)
        details_table.add_column("Value", style="")
        
        details_table.add_row("Title:", contract.title)
        details_table.add_row("Agency:", contract.agency or "N/A")
        details_table.add_row("Location:", contract.location or "N/A")
        details_table.add_row("Region:", contract.geographic_region.value.replace('_', ' ').title())
        details_table.add_row("Source:", contract.source_type.value.upper())
        details_table.add_row("Status:", contract.processing_status.value)
        details_table.add_row("Discovered:", contract.discovered_at.strftime("%Y-%m-%d %H:%M"))
        details_table.add_row("Source URL:", contract.source_url or "N/A")
        
        console.print(details_table)
        
        # Check if selected for processing
        is_selected = self._is_contract_selected(session, contract_id)
        if is_selected:
            console.print("[green]✅ Selected for AI processing[/green]")
        else:
            console.print("[yellow]⭕ Not selected for processing[/yellow]")
    
    def _search_contracts(self):
        """Search contracts by keyword"""
        console.print("\n[bold]🔍 Search Contracts[/bold]")
        
        search_term = Prompt.ask("Enter search term (title, agency, or location)")
        if not search_term:
            return
        
        with self.db.get_session() as session:
            # Search across multiple fields
            contracts = session.query(Contract).filter(
                Contract.title.contains(search_term) |
                Contract.agency.contains(search_term) |
                Contract.location.contains(search_term)
            ).order_by(Contract.discovered_at.desc()).limit(20).all()
            
            if not contracts:
                console.print(f"[yellow]No contracts found matching '{search_term}'[/yellow]")
                return
            
            console.print(f"\n[bold]📋 Search Results for '{search_term}'[/bold]")
            
            # Display results similar to region browsing
            table = Table(title=f"Search Results: {search_term}")
            table.add_column("ID", width=6)
            table.add_column("Title", min_width=30, max_width=50)
            table.add_column("Agency", min_width=20, max_width=30)
            table.add_column("Region", width=15)
            table.add_column("Selected", width=8, justify="center")
            
            contract_ids = []
            for contract in contracts:
                is_selected = self._is_contract_selected(session, contract.id)
                table.add_row(
                    str(contract.id),
                    contract.title[:47] + "..." if len(contract.title) > 50 else contract.title,
                    contract.agency[:27] + "..." if len(contract.agency) > 30 else contract.agency,
                    contract.geographic_region.value.replace('_', ' ').title(),
                    "✅" if is_selected else "⭕"
                )
                contract_ids.append(str(contract.id))
            
            console.print(table)
            self._contract_selection_menu(session, contracts, contract_ids)
    
    def _review_selected_contracts(self):
        """Review all currently selected contracts"""
        console.print("\n[bold]📝 Review Selected Contracts[/bold]")
        
        with self.db.get_session() as session:
            # Get all selected contracts
            queue_items = session.query(ProcessingQueue).filter(
                ProcessingQueue.task_type == "ai_analysis",
                ProcessingQueue.status == ProcessingStatus.PENDING,
                ProcessingQueue.manually_selected == True
            ).order_by(ProcessingQueue.priority.desc()).all()
            
            if not queue_items:
                console.print("[yellow]No contracts currently selected for processing[/yellow]")
                return
            
            console.print(f"[green]{len(queue_items)} contracts selected for AI processing[/green]\n")
            
            table = Table(title="Selected Contracts Queue")
            table.add_column("Queue ID", width=8)
            table.add_column("Contract ID", width=10)
            table.add_column("Title", min_width=30, max_width=50)
            table.add_column("Priority", width=8, justify="center")
            table.add_column("Selected At", width=12)
            
            for item in queue_items:
                contract = session.query(Contract).get(int(item.target_id))
                if contract:
                    table.add_row(
                        str(item.id),
                        item.target_id,
                        contract.title[:47] + "..." if len(contract.title) > 50 else contract.title,
                        str(item.priority),
                        item.created_at.strftime("%m-%d %H:%M")
                    )
            
            console.print(table)
            
            # Options to manage queue
            console.print("\n[bold]Queue Management:[/bold]")
            console.print("• 'clear' to clear all selections")
            console.print("• 'remove <queue_id>' to remove specific item")
            console.print("• 'process' to start AI processing")
            console.print("• 'back' to return to main menu")
            
            action = Prompt.ask("Action", default="back").strip().lower()
            
            if action == "clear":
                if Confirm.ask("Clear all selected contracts?"):
                    for item in queue_items:
                        session.delete(item)
                    session.commit()
                    console.print("[yellow]All selections cleared[/yellow]")
            elif action.startswith("remove "):
                try:
                    queue_id = int(action.split()[1])
                    item = session.query(ProcessingQueue).get(queue_id)
                    if item:
                        session.delete(item)
                        session.commit()
                        console.print(f"[yellow]Removed queue item {queue_id}[/yellow]")
                    else:
                        console.print("[red]Queue item not found[/red]")
                except (IndexError, ValueError):
                    console.print("[red]Invalid queue ID format[/red]")
            elif action == "process":
                console.print("[yellow]AI processing not yet implemented - coming in Phase 2B![/yellow]")
    
    def _show_cost_estimates(self):
        """Show estimated costs for selected contracts"""
        console.print("\n[bold]💰 Cost Estimates[/bold]")
        
        with self.db.get_session() as session:
            queue_count = session.query(ProcessingQueue).filter(
                ProcessingQueue.task_type == "ai_analysis",
                ProcessingQueue.status == ProcessingStatus.PENDING,
                ProcessingQueue.manually_selected == True
            ).count()
            
            if queue_count == 0:
                console.print("[yellow]No contracts selected for processing[/yellow]")
                return
            
            # Cost estimation (rough estimates)
            cost_per_analysis = 0.50  # ~$0.50 per contract analysis
            batch_discount = 0.8 if queue_count >= 10 else 1.0  # 20% discount for 10+
            
            estimated_cost = queue_count * cost_per_analysis * batch_discount
            
            cost_table = Table(title="Cost Estimation")
            cost_table.add_column("Item", style="bold")
            cost_table.add_column("Value", justify="right")
            
            cost_table.add_row("Selected contracts", str(queue_count))
            cost_table.add_row("Cost per analysis", f"${cost_per_analysis:.2f}")
            cost_table.add_row("Batch discount", f"{int((1-batch_discount)*100)}%")
            cost_table.add_row("Estimated total cost", f"[bold green]${estimated_cost:.2f}[/bold green]")
            
            console.print(cost_table)
            
            console.print(f"\n[dim]Note: Actual costs may vary based on contract complexity and AI model usage[/dim]")
    
    def _process_selected_contracts(self):
        """Start processing selected contracts (placeholder for Phase 2B)"""
        console.print("\n[bold]🚀 Process Selected Contracts[/bold]")
        console.print("[yellow]AI pattern discovery and processing will be implemented in Phase 2B[/yellow]")
        console.print("This interface is ready for the AI agent integration!")
    
    def _show_processing_status(self):
        """Show current processing status"""
        console.print("\n[bold]📊 Processing Status[/bold]")
        
        with self.db.get_session() as session:
            # Get processing statistics
            total_contracts = session.query(Contract).count()
            pending_queue = session.query(ProcessingQueue).filter(
                ProcessingQueue.status == ProcessingStatus.PENDING
            ).count()
            
            status_table = Table(title="System Status")
            status_table.add_column("Metric", style="bold")
            status_table.add_column("Count", justify="right", style="green")
            
            status_table.add_row("Total contracts in database", str(total_contracts))
            status_table.add_row("Pending in processing queue", str(pending_queue))
            status_table.add_row("AI analysis completed", "0 (Phase 2B)")
            status_table.add_row("PDF downloads completed", "0 (Phase 2C)")
            
            console.print(status_table)
    
    def _get_contract_counts_by_region(self, session) -> Dict[str, int]:
        """Get contract counts grouped by geographic region"""
        from sqlalchemy import func
        
        results = session.query(
            Contract.geographic_region,
            func.count(Contract.id)
        ).group_by(Contract.geographic_region).all()
        
        return {region.value: count for region, count in results}
    
    def _is_contract_selected(self, session, contract_id: int) -> bool:
        """Check if a contract is selected for processing"""
        return session.query(ProcessingQueue).filter(
            ProcessingQueue.target_id == str(contract_id),
            ProcessingQueue.task_type == "ai_analysis",
            ProcessingQueue.status == ProcessingStatus.PENDING
        ).first() is not None
    
    def _get_status_color(self, status: ProcessingStatus) -> str:
        """Get color for processing status"""
        colors = {
            ProcessingStatus.PENDING: "yellow",
            ProcessingStatus.IN_PROGRESS: "blue",
            ProcessingStatus.COMPLETED: "green",
            ProcessingStatus.FAILED: "red",
            ProcessingStatus.SKIPPED: "dim"
        }
        return colors.get(status, "white")

def main():
    """Run the manual selection interface"""
    parser = argparse.ArgumentParser(description="Manual Contract Selection Interface")
    args = parser.parse_args()
    
    try:
        interface = ManualSelectionInterface()
        interface.run()
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()