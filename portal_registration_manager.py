#!/usr/bin/env python3
"""
Portal Registration Manager
===========================

Interactive interface for managing portal registrations and credentials.
Handles the manual registration workflow and credential management.

Features:
- View cities needing registration
- Manage portal credentials
- Test credential validity
- Track registration flags and resolution
- Guided registration workflow
"""

import sys
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm, IntPrompt
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich import print as rprint

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database.connection import DatabaseManager
from src.database.models import (
    CityPortal, PortalCredential, RegistrationFlag, PortalPattern,
    PortalType, AccountStatus, FlagStatus, ProcessingStatus
)
from src.portal.detector import PortalDetector
from src.portal.credential_manager import CredentialManager

console = Console()

class PortalRegistrationManager:
    """Interactive interface for portal registration management"""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.detector = PortalDetector()
        self.credential_manager = CredentialManager()
        
        console.print("🔐 Portal Registration Manager initialized")
    
    def run(self):
        """Run the interactive registration management interface"""
        console.print("\n🔐 [bold cyan]Portal Registration Manager[/bold cyan]")
        console.print("Manage city portal registrations and credentials\n")
        
        while True:
            try:
                self._show_main_menu()
                choice = Prompt.ask("Select option", choices=["1", "2", "3", "4", "5", "6", "7", "8", "q"])
                
                if choice == "q":
                    console.print("👋 Goodbye!")
                    break
                elif choice == "1":
                    self._show_registration_flags()
                elif choice == "2":
                    self._detect_new_portals()
                elif choice == "3":
                    self._manage_credentials()
                elif choice == "4":
                    self._test_credentials()
                elif choice == "5":
                    self._guided_registration()
                elif choice == "6":
                    self._resolve_flags()
                elif choice == "7":
                    self._show_portal_summary()
                elif choice == "8":
                    self._export_registration_list()
                    
            except KeyboardInterrupt:
                console.print("\n👋 Goodbye!")
                break
            except Exception as e:
                console.print(f"[red]❌ Error: {e}[/red]")
                
            if choice != "q":
                input("\nPress Enter to continue...")
    
    def _show_main_menu(self):
        """Display the main menu options"""
        console.print("\n[bold]📋 Portal Registration Manager[/bold]")
        console.print("1. 🚩 View registration flags (cities needing action)")
        console.print("2. 🔍 Detect new city portals")
        console.print("3. 🔐 Manage portal credentials")
        console.print("4. 🧪 Test stored credentials") 
        console.print("5. 📝 Guided registration workflow")
        console.print("6. ✅ Resolve registration flags")
        console.print("7. 📊 Show portal summary")
        console.print("8. 📄 Export registration task list")
        console.print("q. ❌ Quit")
    
    def _show_registration_flags(self):
        """Show cities that need manual registration"""
        console.print("\n[bold]🚩 Cities Needing Registration[/bold]")
        
        with self.db.get_session() as session:
            flags = session.query(RegistrationFlag).filter_by(
                resolution_status=FlagStatus.PENDING
            ).order_by(RegistrationFlag.priority_score.desc()).all()
            
            if not flags:
                console.print("[green]✅ No pending registration flags![/green]")
                return
            
            # Create table
            table = Table(title=f"Registration Flags ({len(flags)} pending)")
            table.add_column("Priority", width=8, justify="center")
            table.add_column("City", min_width=15, max_width=20)
            table.add_column("Portal Type", width=12)
            table.add_column("Reason", min_width=15, max_width=25)
            table.add_column("Contracts", width=9, justify="center")
            table.add_column("Effort", width=8, justify="center")
            table.add_column("Flagged", width=10)
            table.add_column("Actions", width=15)
            
            for flag in flags:
                priority_stars = "⭐" * min(int(flag.priority_score / 20), 5)
                portal_type = flag.portal_type.value if flag.portal_type else "unknown"
                effort_hours = f"{flag.estimated_manual_hours:.1f}h"
                flagged_days = (datetime.utcnow() - flag.flagged_date).days
                
                # Action indicators
                actions = []
                if flag.portal_url:
                    actions.append("🌐")
                if flag.contract_count > 0:
                    actions.append(f"📋{flag.contract_count}")
                
                table.add_row(
                    priority_stars,
                    flag.city_name,
                    portal_type,
                    flag.flag_reason.replace('_', ' ').title(),
                    str(flag.contract_count) if flag.contract_count else "0",
                    effort_hours,
                    f"{flagged_days}d ago",
                    " ".join(actions)
                )
            
            console.print(table)
            
            # Show total effort estimate
            total_hours = sum(f.estimated_manual_hours for f in flags)
            console.print(f"\n💼 Total estimated manual effort: {total_hours:.1f} hours")
            
            # Show prioritization suggestions
            high_priority = [f for f in flags if f.priority_score >= 70]
            if high_priority:
                console.print(f"\n🎯 Recommended to tackle first: {len(high_priority)} high-priority cities")
                for flag in high_priority[:3]:
                    console.print(f"   • {flag.city_name} ({flag.portal_type.value if flag.portal_type else 'unknown'})")
    
    def _detect_new_portals(self):
        """Run portal detection on new cities"""
        console.print("\n[bold]🔍 Detect New City Portals[/bold]")
        
        # Sample LA region cities for testing
        test_cities = [
            {'city_name': 'Los Angeles', 'website_url': 'https://www.lacity.org/business/contracting-procurement'},
            {'city_name': 'San Diego', 'website_url': 'https://www.sandiego.gov/purchasing-contracting'},
            {'city_name': 'Anaheim', 'website_url': 'https://www.anaheim.net/1316/Procurement'},
            {'city_name': 'Santa Monica', 'website_url': 'https://www.santamonica.gov/business/procurement'},
            {'city_name': 'Long Beach', 'website_url': 'https://www.longbeach.gov/finance/business-operations/purchasing/'},
            {'city_name': 'Pasadena', 'website_url': 'https://www.cityofpasadena.net/finance/purchasing/'}
        ]
        
        console.print(f"Testing portal detection on {len(test_cities)} LA region cities...")
        
        if Confirm.ask("Run portal detection?"):
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Detecting portals...", total=len(test_cities))
                
                results = []
                for city_data in test_cities:
                    progress.update(task, description=f"Analyzing {city_data['city_name']}")
                    
                    result = self.detector.detect_city_portal(
                        city_data['city_name'],
                        city_data['website_url']
                    )
                    results.append(result)
                    
                    progress.advance(task)
            
            # Show results
            console.print("\n[bold]🔍 Detection Results[/bold]")
            
            detection_table = Table(title="Portal Detection Results")
            detection_table.add_column("City", min_width=15)
            detection_table.add_column("Portal Type", width=12)
            detection_table.add_column("Registration", width=12, justify="center")
            detection_table.add_column("Confidence", width=10, justify="center")
            detection_table.add_column("Status", width=10)
            
            for result in results:
                portal_type = result.get('portal_type', PortalType.NONE).value
                registration = "🔐 Required" if result.get('registration_required', False) else "🌐 Open"
                confidence = f"{result.get('detection_confidence', 0.0):.1%}"
                
                status = "✅ New" if 'from_cache' not in result else "📋 Cached"
                if 'errors' in result and result['errors']:
                    status = "❌ Error"
                
                detection_table.add_row(
                    result['city_name'],
                    portal_type,
                    registration,
                    confidence,
                    status
                )
            
            console.print(detection_table)
            
            # Summary
            new_registrations = sum(1 for r in results if r.get('registration_required', False) and 'from_cache' not in r)
            console.print(f"\n📊 Found {new_registrations} cities requiring new registrations")
    
    def _manage_credentials(self):
        """Manage stored portal credentials"""
        console.print("\n[bold]🔐 Manage Portal Credentials[/bold]")
        
        while True:
            console.print("\n[bold]Credential Management:[/bold]")
            console.print("1. 📋 List stored credentials")
            console.print("2. ➕ Add new credentials")
            console.print("3. ✏️ Edit existing credentials")
            console.print("4. 🗑️ Delete credentials")
            console.print("5. ⬅️ Back to main menu")
            
            choice = Prompt.ask("Select option", choices=["1", "2", "3", "4", "5"])
            
            if choice == "5":
                break
            elif choice == "1":
                self._list_stored_credentials()
            elif choice == "2":
                self._add_new_credentials()
            elif choice == "3":
                self._edit_credentials()
            elif choice == "4":
                self._delete_credentials()
    
    def _list_stored_credentials(self):
        """List all stored credentials"""
        console.print("\n[bold]📋 Stored Credentials[/bold]")
        
        with self.db.get_session() as session:
            credentials = session.query(PortalCredential).order_by(PortalCredential.city_name).all()
            
            if not credentials:
                console.print("[yellow]No credentials stored yet[/yellow]")
                return
            
            cred_table = Table(title=f"Stored Credentials ({len(credentials)})")
            cred_table.add_column("City", min_width=15)
            cred_table.add_column("Portal Type", width=12)
            cred_table.add_column("Username", min_width=15)
            cred_table.add_column("Status", width=12)
            cred_table.add_column("Last Verified", width=12)
            cred_table.add_column("Registered", width=10)
            
            for cred in credentials:
                status_color = {
                    AccountStatus.REGISTERED: "green",
                    AccountStatus.PENDING: "yellow", 
                    AccountStatus.FAILED: "red",
                    AccountStatus.NEEDS_REGISTRATION: "cyan"
                }.get(cred.verification_status, "white")
                
                last_verified = "Never" if not cred.last_verified else cred.last_verified.strftime("%m-%d %H:%M")
                registered = cred.registration_date.strftime("%m-%d-%Y") if cred.registration_date else "Unknown"
                
                cred_table.add_row(
                    cred.city_name,
                    cred.portal_type.value,
                    cred.username or "N/A",
                    f"[{status_color}]{cred.verification_status.value}[/{status_color}]",
                    last_verified,
                    registered
                )
            
            console.print(cred_table)
    
    def _add_new_credentials(self):
        """Add new credentials interactively"""
        console.print("\n[bold]➕ Add New Credentials[/bold]")
        
        # Get city name
        city_name = Prompt.ask("City name")
        
        # Get portal type
        portal_types = [pt.value for pt in PortalType if pt != PortalType.NONE]
        portal_type_str = Prompt.ask("Portal type", choices=portal_types)
        portal_type = PortalType(portal_type_str)
        
        # Get credentials
        username = Prompt.ask("Username")
        password = Prompt.ask("Password", password=True)
        email = Prompt.ask("Email (optional)", default="")
        
        # Business info (optional)
        if Confirm.ask("Add business information?", default=False):
            business_info = {
                'business_name': Prompt.ask("Business name", default=""),
                'business_address': Prompt.ask("Business address", default=""),
                'business_phone': Prompt.ask("Business phone", default=""),
                'tax_id': Prompt.ask("Tax ID", default="")
            }
        else:
            business_info = None
        
        # Store credentials
        success = self.credential_manager.store_credentials(
            city_name=city_name,
            portal_type=portal_type,
            username=username,
            password=password,
            email=email if email else None,
            business_info=business_info
        )
        
        if success:
            console.print(f"[green]✅ Credentials stored for {city_name}[/green]")
            
            # Ask if user wants to test credentials
            if Confirm.ask("Test credentials now?", default=True):
                result = self.credential_manager.verify_credentials(city_name, portal_type)
                if result['success']:
                    console.print("[green]✅ Credentials verified successfully![/green]")
                else:
                    console.print(f"[red]❌ Credential verification failed: {result['error']}[/red]")
        else:
            console.print("[red]❌ Failed to store credentials[/red]")
    
    def _edit_credentials(self):
        """Edit existing credentials"""
        console.print("\n[bold]✏️ Edit Credentials[/bold]")
        
        with self.db.get_session() as session:
            credentials = session.query(PortalCredential).order_by(PortalCredential.city_name).all()
            
            if not credentials:
                console.print("[yellow]No credentials to edit[/yellow]")
                return
            
            # Show list for selection
            console.print("Select credentials to edit:")
            for i, cred in enumerate(credentials, 1):
                console.print(f"{i}. {cred.city_name} ({cred.portal_type.value})")
            
            try:
                choice = IntPrompt.ask("Select number", default=1)
                if 1 <= choice <= len(credentials):
                    selected_cred = credentials[choice - 1]
                    
                    # Get current credentials
                    current = self.credential_manager.get_credentials(selected_cred.city_name, selected_cred.portal_type)
                    
                    if current:
                        # Edit fields
                        new_username = Prompt.ask("Username", default=current['username'])
                        new_password = Prompt.ask("Password", password=True, default="[keep current]")
                        new_email = Prompt.ask("Email", default=current.get('email', ''))
                        
                        # Update credentials
                        success = self.credential_manager.store_credentials(
                            city_name=selected_cred.city_name,
                            portal_type=selected_cred.portal_type,
                            username=new_username,
                            password=current['password'] if new_password == "[keep current]" else new_password,
                            email=new_email if new_email else None
                        )
                        
                        if success:
                            console.print("[green]✅ Credentials updated[/green]")
                        else:
                            console.print("[red]❌ Failed to update credentials[/red]")
                    else:
                        console.print("[red]❌ Could not retrieve current credentials[/red]")
                else:
                    console.print("[red]❌ Invalid selection[/red]")
            except ValueError:
                console.print("[red]❌ Invalid input[/red]")
    
    def _delete_credentials(self):
        """Delete credentials"""
        console.print("\n[bold]🗑️ Delete Credentials[/bold]")
        
        with self.db.get_session() as session:
            credentials = session.query(PortalCredential).order_by(PortalCredential.city_name).all()
            
            if not credentials:
                console.print("[yellow]No credentials to delete[/yellow]")
                return
            
            # Show list for selection
            console.print("Select credentials to delete:")
            for i, cred in enumerate(credentials, 1):
                console.print(f"{i}. {cred.city_name} ({cred.portal_type.value})")
            
            try:
                choice = IntPrompt.ask("Select number", default=1)
                if 1 <= choice <= len(credentials):
                    selected_cred = credentials[choice - 1]
                    
                    if Confirm.ask(f"Delete credentials for {selected_cred.city_name}?", default=False):
                        success = self.credential_manager.delete_credentials(
                            selected_cred.city_name, 
                            selected_cred.portal_type
                        )
                        
                        if success:
                            console.print("[green]✅ Credentials deleted[/green]")
                        else:
                            console.print("[red]❌ Failed to delete credentials[/red]")
                else:
                    console.print("[red]❌ Invalid selection[/red]")
            except ValueError:
                console.print("[red]❌ Invalid input[/red]")
    
    def _test_credentials(self):
        """Test stored credentials"""
        console.print("\n[bold]🧪 Test Stored Credentials[/bold]")
        
        if Confirm.ask("Test all stored credentials?", default=True):
            console.print("Testing all credentials (this may take a while)...")
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Testing credentials...", total=None)
                
                results = self.credential_manager.test_all_credentials()
                progress.update(task, completed=1, total=1)
            
            # Show results
            console.print("\n[bold]🧪 Credential Test Results[/bold]")
            
            test_table = Table(title="Credential Verification")
            test_table.add_column("City", min_width=15)
            test_table.add_column("Portal Type", width=12)
            test_table.add_column("Result", width=8, justify="center")
            test_table.add_column("Error", min_width=20, max_width=40)
            
            successful = 0
            for result in results:
                status = "✅" if result['success'] else "❌"
                error = result.get('error', '') or ''
                
                if result['success']:
                    successful += 1
                
                test_table.add_row(
                    result['city_name'],
                    result['portal_type'],
                    status,
                    error[:37] + "..." if len(error) > 40 else error
                )
            
            console.print(test_table)
            console.print(f"\n📊 Results: {successful}/{len(results)} credentials verified successfully")
    
    def _guided_registration(self):
        """Guided workflow for manual portal registration"""
        console.print("\n[bold]📝 Guided Registration Workflow[/bold]")
        
        with self.db.get_session() as session:
            # Get highest priority flag
            flag = session.query(RegistrationFlag).filter_by(
                resolution_status=FlagStatus.PENDING
            ).order_by(RegistrationFlag.priority_score.desc()).first()
            
            if not flag:
                console.print("[green]✅ No registration flags to process![/green]")
                return
            
            # Show flag details
            panel_content = f"""
[bold]City:[/bold] {flag.city_name}
[bold]Portal Type:[/bold] {flag.portal_type.value if flag.portal_type else 'Unknown'}
[bold]Portal URL:[/bold] {flag.portal_url or 'Not detected'}
[bold]Priority Score:[/bold] {flag.priority_score}/100
[bold]Reason:[/bold] {flag.flag_reason.replace('_', ' ').title()}
[bold]Estimated Effort:[/bold] {flag.estimated_manual_hours} hours
[bold]Contracts Affected:[/bold] {flag.contract_count or 0}

{flag.flag_description or 'Registration required to access RFP documents'}
            """
            
            console.print(Panel(panel_content, title="🎯 Next Registration Task", expand=False))
            
            if Confirm.ask("Would you like to work on this registration?", default=True):
                # Guide through registration process
                console.print("\n[bold]📋 Registration Steps:[/bold]")
                console.print("1. 🌐 Open the portal URL in your browser")
                console.print("2. 📝 Complete the registration form")
                console.print("3. ✉️ Verify your email (if required)")
                console.print("4. 🔐 Return here to store credentials")
                
                if flag.portal_url:
                    console.print(f"\n[bold cyan]Portal URL:[/bold cyan] {flag.portal_url}")
                    
                    if Confirm.ask("Open URL in browser?", default=True):
                        import webbrowser
                        webbrowser.open(flag.portal_url)
                
                console.print("\n[dim]Complete the registration process, then return here...[/dim]")
                
                if Confirm.ask("Have you completed the registration?", default=False):
                    # Store credentials
                    self._add_new_credentials()
                    
                    # Mark flag as resolved
                    flag.resolution_status = FlagStatus.RESOLVED
                    flag.resolved_date = datetime.utcnow()
                    flag.resolved_by = "guided_workflow"
                    flag.resolution_notes = "Registration completed via guided workflow"
                    
                    session.commit()
                    
                    console.print("[green]✅ Registration flag marked as resolved![/green]")
    
    def _resolve_flags(self):
        """Resolve registration flags"""
        console.print("\n[bold]✅ Resolve Registration Flags[/bold]")
        
        with self.db.get_session() as session:
            flags = session.query(RegistrationFlag).filter_by(
                resolution_status=FlagStatus.PENDING
            ).order_by(RegistrationFlag.priority_score.desc()).all()
            
            if not flags:
                console.print("[green]✅ No flags to resolve![/green]")
                return
            
            # Show flags for selection
            console.print("Select flag to resolve:")
            for i, flag in enumerate(flags, 1):
                console.print(f"{i}. {flag.city_name} - {flag.flag_reason.replace('_', ' ').title()}")
            
            try:
                choice = IntPrompt.ask("Select number", default=1)
                if 1 <= choice <= len(flags):
                    selected_flag = flags[choice - 1]
                    
                    console.print(f"\n[bold]Resolving flag for {selected_flag.city_name}[/bold]")
                    
                    resolution_options = [
                        ("resolved", "✅ Successfully resolved"),
                        ("manual_required", "🔧 Requires ongoing manual work"),
                        ("abandoned", "❌ Abandoned (not worth effort)")
                    ]
                    
                    console.print("Resolution status:")
                    for i, (status, desc) in enumerate(resolution_options, 1):
                        console.print(f"{i}. {desc}")
                    
                    status_choice = IntPrompt.ask("Select status", default=1)
                    if 1 <= status_choice <= len(resolution_options):
                        new_status = resolution_options[status_choice - 1][0]
                        
                        notes = Prompt.ask("Resolution notes (optional)", default="")
                        
                        # Update flag
                        selected_flag.resolution_status = FlagStatus(new_status)
                        selected_flag.resolved_date = datetime.utcnow()
                        selected_flag.resolved_by = "manual_resolution"
                        selected_flag.resolution_notes = notes
                        
                        session.commit()
                        
                        console.print(f"[green]✅ Flag resolved with status: {new_status}[/green]")
            
            except ValueError:
                console.print("[red]❌ Invalid input[/red]")
    
    def _show_portal_summary(self):
        """Show comprehensive portal summary"""
        console.print("\n[bold]📊 Portal System Summary[/bold]")
        
        # Get summaries from different components
        detection_summary = self.detector.get_detection_summary()
        credential_summary = self.credential_manager.get_credentials_summary()
        
        with self.db.get_session() as session:
            from sqlalchemy import func
            
            # Flag summary
            flag_counts = session.query(
                RegistrationFlag.resolution_status,
                func.count(RegistrationFlag.id)
            ).group_by(RegistrationFlag.resolution_status).all()
            
            # Portal summary
            summary_table = Table(title="System Overview")
            summary_table.add_column("Category", style="bold")
            summary_table.add_column("Metric", min_width=20)
            summary_table.add_column("Value", justify="right", style="green")
            
            # Detection stats
            summary_table.add_row("🔍 Detection", "Cities analyzed", str(detection_summary.get('total_cities', 0)))
            summary_table.add_row("", "Requiring registration", str(detection_summary.get('registration_required', 0)))
            
            # Portal type breakdown
            for portal_type, count in detection_summary.get('portal_types', {}).items():
                summary_table.add_row("", f"  {portal_type.title()}", str(count))
            
            # Credential stats
            summary_table.add_row("🔐 Credentials", "Total stored", str(credential_summary.get('total_credentials', 0)))
            summary_table.add_row("", "Encryption enabled", "✅" if credential_summary.get('encryption_enabled') else "❌")
            
            for status, count in credential_summary.get('status_counts', {}).items():
                summary_table.add_row("", f"  {status.replace('_', ' ').title()}", str(count))
            
            # Flag stats
            summary_table.add_row("🚩 Flags", "Total created", str(sum(count for _, count in flag_counts)))
            
            for status, count in flag_counts:
                summary_table.add_row("", f"  {status.value.replace('_', ' ').title()}", str(count))
            
            console.print(summary_table)
            
            # Show recommendations
            console.print("\n[bold]🎯 Recommendations[/bold]")
            
            pending_flags = detection_summary.get('pending_flags', 0)
            if pending_flags > 0:
                console.print(f"• Complete {pending_flags} pending registrations")
            
            unverified = credential_summary.get('status_counts', {}).get('pending', 0)
            if unverified > 0:
                console.print(f"• Verify {unverified} untested credentials")
            
            if pending_flags == 0 and unverified == 0:
                console.print("• ✅ System is fully configured!")
    
    def _export_registration_list(self):
        """Export registration task list for external tracking"""
        console.print("\n[bold]📄 Export Registration Task List[/bold]")
        
        with self.db.get_session() as session:
            flags = session.query(RegistrationFlag).filter_by(
                resolution_status=FlagStatus.PENDING
            ).order_by(RegistrationFlag.priority_score.desc()).all()
            
            if not flags:
                console.print("[green]✅ No pending registrations to export![/green]")
                return
            
            # Create export data
            export_data = []
            for flag in flags:
                export_data.append({
                    'City': flag.city_name,
                    'Portal_Type': flag.portal_type.value if flag.portal_type else 'Unknown',
                    'Portal_URL': flag.portal_url or '',
                    'Priority_Score': flag.priority_score,
                    'Estimated_Hours': flag.estimated_manual_hours,
                    'Contract_Count': flag.contract_count or 0,
                    'Contract_Value': flag.total_contract_value or '',
                    'Reason': flag.flag_reason,
                    'Description': flag.flag_description or '',
                    'Flagged_Date': flag.flagged_date.strftime('%Y-%m-%d'),
                })
            
            # Save to file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"data/registration_tasks_{timestamp}.csv"
            
            try:
                import pandas as pd
                df = pd.DataFrame(export_data)
                df.to_csv(filename, index=False)
                
                console.print(f"[green]✅ Registration task list exported to: {filename}[/green]")
                console.print(f"📊 {len(export_data)} tasks exported")
                
            except ImportError:
                console.print("[red]❌ pandas not available - cannot export CSV[/red]")
            except Exception as e:
                console.print(f"[red]❌ Export failed: {e}[/red]")

def main():
    """Run the portal registration manager"""
    try:
        manager = PortalRegistrationManager()
        manager.run()
    except Exception as e:
        console.print(f"[red]❌ Error: {e}[/red]")
        sys.exit(1)

if __name__ == "__main__":
    main()