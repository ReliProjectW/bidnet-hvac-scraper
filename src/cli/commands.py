import click
import json
import logging
from typing import List, Dict, Any
from tabulate import tabulate
from datetime import datetime

from ..scraper.hybrid_scraper import HybridScraper
from ..processing.queue_manager import QueueManager
from ..database.connection import db_manager
from ..database.models import Contract, ProcessingStatus, PlanDownload
from ..pdf.downloader import PDFDownloader
from config import Config

# Global instances
hybrid_scraper = HybridScraper()
queue_manager = QueueManager()
pdf_downloader = PDFDownloader()

@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging')
def cli(debug):
    """BidNet HVAC Hybrid Scraper - AI + Traditional approach"""
    level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

@cli.command()
@click.option('--save-patterns', is_flag=True, help='Save discovered patterns to database')
def discover_patterns(save_patterns):
    """Phase 1: Use AI to discover BidNet structure patterns"""
    click.echo("🎯 Phase 1: AI Discovery of BidNet Patterns")
    click.echo("This will use Browser Use + Claude to analyze BidNet (~$10-20)")
    
    if not click.confirm('Proceed with AI analysis?'):
        return
    
    credentials = {
        'username': Config.USERNAME,
        'password': Config.PASSWORD
    }
    
    if not credentials['username'] or not credentials['password']:
        click.echo("❌ Please set BIDNET_USERNAME and BIDNET_PASSWORD environment variables")
        return
    
    try:
        patterns = hybrid_scraper.discover_bidnet_patterns(credentials)
        
        click.echo("✅ Pattern discovery completed!")
        click.echo(f"💰 Estimated cost: ${patterns.get('analysis_cost', 10.0):.2f}")
        
        # Display key findings
        click.echo("\n📊 Key Findings:")
        if patterns.get('contract_listing'):
            click.echo(f"  • Contract selector: {patterns['contract_listing'].get('contract_item_selector', 'Not found')}")
            click.echo(f"  • Title selector: {patterns['contract_listing'].get('title_selector', 'Not found')}")
        
        click.echo(f"  • Estimated contracts available: {patterns.get('estimated_contracts_available', 'Unknown')}")
        click.echo(f"  • Analysis confidence: {patterns.get('analysis_confidence', 0):.0%}")
        
        if save_patterns:
            click.echo("💾 Patterns saved to database for future use")
        
    except Exception as e:
        click.echo(f"❌ Pattern discovery failed: {e}")

@cli.command()
@click.option('--use-ai-patterns/--no-ai-patterns', default=True, help='Use AI-discovered patterns')
@click.option('--limit', default=50, help='Maximum contracts to find')
def search_contracts(use_ai_patterns, limit):
    """Phase 2: Search for contracts using fast traditional scraping"""
    click.echo("⚡ Phase 2: Traditional Scraping with AI Patterns")
    
    try:
        contracts = hybrid_scraper.search_contracts_traditional(use_ai_patterns)
        
        click.echo(f"✅ Found {len(contracts)} contracts")
        
        # Display summary by region
        region_counts = {}
        for contract in contracts:
            region = contract.raw_data.get('geographic_region', 'unknown')
            region_counts[region] = region_counts.get(region, 0) + 1
        
        click.echo("\n📍 Geographic Distribution:")
        for region, count in sorted(region_counts.items()):
            click.echo(f"  • {region}: {count} contracts")
        
        # Show top contracts
        click.echo("\n🏆 Top HVAC Contracts:")
        top_contracts = sorted(contracts, key=lambda x: x.hvac_relevance_score or 0, reverse=True)[:5]
        
        for i, contract in enumerate(top_contracts, 1):
            click.echo(f"\n{i}. {contract.title[:80]}...")
            click.echo(f"   Agency: {contract.agency}")
            click.echo(f"   Location: {contract.location}")
            click.echo(f"   HVAC Score: {contract.hvac_relevance_score}")
    
    except Exception as e:
        click.echo(f"❌ Contract search failed: {e}")

@cli.command()
@click.option('--limit', default=20, help='Number of candidates to show')
def show_candidates(limit):
    """Show contracts that are good candidates for AI processing"""
    click.echo("🎯 Manual Selection Candidates")
    
    candidates = hybrid_scraper.get_manual_selection_candidates(limit)
    
    if not candidates:
        click.echo("No candidates found. Run search-contracts first.")
        return
    
    # Display candidates in a table
    table_data = []
    for i, candidate in enumerate(candidates, 1):
        table_data.append([
            i,
            candidate['id'],
            candidate['title'][:50] + '...' if len(candidate['title']) > 50 else candidate['title'],
            candidate['agency'][:30] + '...' if len(candidate['agency']) > 30 else candidate['agency'],
            candidate['location'],
            f"{candidate['hvac_relevance_score']:.1f}",
            candidate.get('estimated_value', 'N/A')
        ])
    
    headers = ['#', 'ID', 'Title', 'Agency', 'Location', 'HVAC Score', 'Value']
    click.echo(tabulate(table_data, headers=headers, tablefmt='grid'))
    
    click.echo(f"\nShowing {len(candidates)} candidates")
    click.echo("💡 Use 'process-selected' command to queue specific contracts for AI processing")

@cli.command()
@click.argument('contract_ids', nargs=-1, type=int, required=True)
@click.option('--selected-by', default='manual', help='Who selected these contracts')
def process_selected(contract_ids, selected_by):
    """Queue selected contracts for AI processing"""
    click.echo(f"🤖 Queuing {len(contract_ids)} contracts for AI processing")
    
    # Estimate cost
    estimated_cost = len(contract_ids) * 3.0  # ~$3 per contract
    click.echo(f"💰 Estimated cost: ${estimated_cost:.2f}")
    
    if not click.confirm('Proceed with AI processing?'):
        return
    
    try:
        queued_count = hybrid_scraper.process_city_contracts(list(contract_ids), selected_by)
        click.echo(f"✅ Queued {queued_count} contracts for processing")
        
    except Exception as e:
        click.echo(f"❌ Failed to queue contracts: {e}")

@cli.command()
@click.option('--batch-size', default=3, help='Number of contracts to process in this batch')
def process_ai_batch(batch_size):
    """Process a batch of contracts with AI analysis"""
    click.echo(f"🤖 Processing AI batch (size: {batch_size})")
    
    try:
        results = hybrid_scraper.process_ai_queue_batch(batch_size)
        
        click.echo(f"✅ Batch completed!")
        click.echo(f"  • Processed: {results['processed']}")
        click.echo(f"  • Successful: {results['successful']}")
        click.echo(f"  • Failed: {results['failed']}")
        click.echo(f"  • Cost: ${results['total_cost']:.2f}")
        
        # Show successful contracts
        if results['contracts']:
            click.echo("\n📋 Processed Contracts:")
            for contract in results['contracts']:
                click.echo(f"  • Contract {contract['contract_id']}: {contract['city_name']}")
                
    except Exception as e:
        click.echo(f"❌ Batch processing failed: {e}")

@cli.command()
def queue_status():
    """Show processing queue status"""
    status = queue_manager.get_queue_status()
    
    click.echo("📊 Queue Status")
    click.echo(f"Total tasks: {status['total_tasks']}")
    click.echo(f"Manual selections: {status['manual_selections']}")
    
    click.echo("\n📈 By Status:")
    for status_name, count in status['by_status'].items():
        click.echo(f"  • {status_name}: {count}")
    
    click.echo("\n🔧 By Task Type:")
    for task_type, statuses in status['by_type'].items():
        click.echo(f"  {task_type}:")
        for status_name, count in statuses.items():
            click.echo(f"    - {status_name}: {count}")

@cli.command()
def system_status():
    """Show overall system status"""
    status = hybrid_scraper.get_system_status()
    
    click.echo("🖥️  System Status")
    click.echo(f"Last updated: {status['last_updated']}")
    
    click.echo("\n📊 Contracts by Status:")
    for status_name, count in status['contract_counts'].items():
        click.echo(f"  • {status_name}: {count}")
    
    click.echo(f"\n🏙️  City platforms discovered: {status['city_platforms_discovered']}")
    
    cost = status['cost_summary']
    click.echo(f"\n💰 Cost Summary:")
    click.echo(f"  • Total AI cost: ${cost['total_ai_cost']:.2f}")
    click.echo(f"  • Contracts processed: {cost['contracts_processed']}")
    click.echo(f"  • Cost per contract: ${cost['cost_per_contract']:.2f}")
    click.echo(f"  • Est. monthly cost: ${cost['estimated_monthly_cost']:.2f}")

@cli.command()
@click.confirmation_option(prompt='Are you sure you want to test with real AI analysis?')
def test_system():
    """Run system tests with a small batch"""
    click.echo("🧪 System Test Mode")
    
    # Step 1: Search for a few contracts
    click.echo("\n1. Testing contract search...")
    try:
        contracts = hybrid_scraper.search_contracts_traditional(use_ai_patterns=False)
        click.echo(f"   ✅ Found {len(contracts)} contracts")
        
        if len(contracts) < 5:
            click.echo("   ⚠️  Found fewer than 5 contracts. Check search functionality.")
            return
        
    except Exception as e:
        click.echo(f"   ❌ Search failed: {e}")
        return
    
    # Step 2: Get candidates
    click.echo("\n2. Testing candidate selection...")
    candidates = hybrid_scraper.get_manual_selection_candidates(5)
    if candidates:
        click.echo(f"   ✅ Found {len(candidates)} candidates")
    else:
        click.echo("   ❌ No candidates found")
        return
    
    # Step 3: Process one with AI (with confirmation)
    click.echo("\n3. Testing AI processing...")
    if click.confirm(f'Process 1 contract with AI (~$3 cost)?'):
        try:
            test_ids = [candidates[0]['id']]
            queued = hybrid_scraper.process_city_contracts(test_ids, "system_test")
            click.echo(f"   ✅ Queued {queued} contracts")
            
            # Process the batch
            results = hybrid_scraper.process_ai_queue_batch(1)
            if results['successful'] > 0:
                click.echo(f"   ✅ AI processing successful (${results['total_cost']:.2f})")
            else:
                click.echo(f"   ❌ AI processing failed")
            
        except Exception as e:
            click.echo(f"   ❌ AI processing error: {e}")
    
    click.echo("\n✅ System test completed!")

@cli.command()
@click.argument('output_file', default='contracts_export.json')
def export_contracts(output_file):
    """Export contracts to JSON file"""
    with db_manager.get_session() as session:
        contracts = session.query(Contract).filter(
            Contract.processing_status.in_([ProcessingStatus.PENDING, ProcessingStatus.COMPLETED])
        ).all()
        
        export_data = []
        for contract in contracts:
            export_data.append({
                'id': contract.id,
                'title': contract.title,
                'agency': contract.agency,
                'location': contract.location,
                'estimated_value': contract.estimated_value,
                'hvac_relevance_score': contract.hvac_relevance_score,
                'geographic_region': contract.geographic_region.value if contract.geographic_region else None,
                'source_url': contract.source_url,
                'discovered_at': contract.discovered_at.isoformat(),
                'processing_status': contract.processing_status.value
            })
        
        with open(output_file, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        click.echo(f"✅ Exported {len(export_data)} contracts to {output_file}")

@cli.command()
@click.argument('contract_id', type=int)
@click.argument('plan_urls', nargs=-1, required=True)
def download_plans(contract_id, plan_urls):
    """Download PDF plans for a specific contract"""
    click.echo(f"📁 Downloading {len(plan_urls)} plans for contract {contract_id}")
    
    try:
        results = pdf_downloader.download_contract_plans(contract_id, list(plan_urls))
        
        successful = sum(1 for r in results if r['success'])
        total_size = sum(r.get('file_size_mb', 0) for r in results if r['success'])
        
        click.echo(f"✅ Downloaded {successful}/{len(results)} plans")
        click.echo(f"📊 Total size: {total_size:.1f} MB")
        
        if successful < len(results):
            click.echo("\n❌ Failed downloads:")
            for result in results:
                if not result['success']:
                    click.echo(f"  • {result['url']}: {result['error']}")
    
    except Exception as e:
        click.echo(f"❌ Download failed: {e}")

@cli.command()
@click.option('--contract-id', type=int, help='Show downloads for specific contract')
def download_summary(contract_id):
    """Show download summary statistics"""
    summary = pdf_downloader.get_download_summary(contract_id)
    
    click.echo("📁 Download Summary")
    if contract_id:
        click.echo(f"Contract ID: {contract_id}")
    
    click.echo(f"Total downloads: {summary['total_downloads']}")
    click.echo(f"Successful: {summary['successful_downloads']}")
    click.echo(f"Failed: {summary['failed_downloads']}")
    click.echo(f"Total size: {summary['total_size_mb']:.1f} MB")
    click.echo(f"Text extracted: {summary['text_extracted']} files")
    click.echo(f"Average file size: {summary['avg_file_size_mb']:.1f} MB")

if __name__ == '__main__':
    cli()