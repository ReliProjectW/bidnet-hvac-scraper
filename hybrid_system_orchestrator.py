#!/usr/bin/env python3
"""
Hybrid System Orchestrator
==========================

Main orchestrator for the Phase 2 Hybrid AI System that combines:
1. Working BidNet scraper (Phase 1) - COMPLETED ✅
2. Geographic filtering for LA region 
3. Manual selection interface for cost control
4. AI pattern discovery for city RFP websites
5. Multi-layer extraction pipeline: BidNet → City RFP → PDF

This script provides a unified interface to run all Phase 2 components.
"""

import sys
import os
import argparse
import logging
from datetime import datetime
from typing import Dict, Any

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from hybrid_bidnet_scraper import HybridBidNetScraper
from manual_selection_interface import ManualSelectionInterface
from src.ai_agents.pattern_discovery_agent import PatternDiscoveryAgent
from src.processing.multi_layer_extractor import MultiLayerExtractor
from src.database.connection import DatabaseManager

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HybridSystemOrchestrator:
    """Main orchestrator for the Hybrid AI System"""
    
    def __init__(self):
        self.hybrid_scraper = HybridBidNetScraper()
        self.selection_interface = ManualSelectionInterface()
        self.ai_agent = PatternDiscoveryAgent()
        self.multi_layer_extractor = MultiLayerExtractor()
        self.db = DatabaseManager()
        
        logger.info("🤖 Hybrid System Orchestrator initialized")
    
    def run_full_pipeline(self, max_contracts: int = 10, cost_limit: float = 5.0) -> Dict[str, Any]:
        """
        Run the complete hybrid pipeline:
        1. Extract and filter BidNet contracts
        2. Process selected contracts through multi-layer extraction
        3. Generate comprehensive reports
        
        Args:
            max_contracts: Maximum contracts to process with AI
            cost_limit: Maximum cost limit for AI processing
            
        Returns:
            Complete pipeline results
        """
        logger.info("🚀 Starting Full Hybrid Pipeline")
        
        pipeline_results = {
            'phase_1_bidnet': {},
            'phase_2_selection': {},
            'phase_3_multilayer': {},
            'total_cost': 0.0,
            'success': True,
            'errors': []
        }
        
        try:
            # Phase 1: BidNet extraction with geographic filtering
            logger.info("📥 Phase 1: BidNet extraction with geographic filtering")
            bidnet_results = self.hybrid_scraper.run_hybrid_extraction()
            pipeline_results['phase_1_bidnet'] = bidnet_results
            
            if bidnet_results['in_region'] == 0:
                logger.warning("⚠️ No contracts found in LA region - ending pipeline")
                return pipeline_results
            
            # Phase 2: Multi-layer extraction of selected contracts
            logger.info("🏗️ Phase 2: Multi-layer extraction")
            multilayer_results = self.multi_layer_extractor.process_selected_contracts(
                max_contracts=max_contracts,
                cost_limit=cost_limit
            )
            pipeline_results['phase_3_multilayer'] = multilayer_results
            pipeline_results['total_cost'] = multilayer_results.get('total_cost', 0.0)
            
            # Phase 3: Generate comprehensive report
            logger.info("📊 Phase 3: Generating final report")
            report_file = self.multi_layer_extractor.generate_extraction_report()
            pipeline_results['report_file'] = report_file
            
            logger.info("🎉 Full Hybrid Pipeline completed successfully!")
            
        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}")
            pipeline_results['success'] = False
            pipeline_results['errors'].append(str(e))
        
        return pipeline_results
    
    def run_interactive_session(self):
        """Run interactive session with menu options"""
        while True:
            self._show_main_menu()
            choice = input("\nSelect option (1-6, q): ").strip().lower()
            
            if choice == 'q':
                print("👋 Goodbye!")
                break
                
            try:
                if choice == '1':
                    self._run_bidnet_extraction()
                elif choice == '2':
                    self._run_manual_selection()
                elif choice == '3':
                    self._run_ai_discovery()
                elif choice == '4':
                    self._run_multilayer_extraction()
                elif choice == '5':
                    self._run_full_pipeline_interactive()
                elif choice == '6':
                    self._show_system_status()
                else:
                    print("❌ Invalid option")
                    
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
            
            input("\nPress Enter to continue...")
    
    def _show_main_menu(self):
        """Display the main menu"""
        print("\n" + "="*60)
        print("🤖 HYBRID AI SYSTEM - PHASE 2")
        print("="*60)
        print("1. 📥 Run BidNet extraction with geographic filtering")
        print("2. 🎯 Manual contract selection interface")
        print("3. 🧠 AI pattern discovery for city websites") 
        print("4. 🏗️ Multi-layer extraction (selected contracts)")
        print("5. 🚀 Run complete hybrid pipeline")
        print("6. 📊 Show system status")
        print("q. ❌ Quit")
        print("="*60)
    
    def _run_bidnet_extraction(self):
        """Run BidNet extraction with geographic filtering"""
        print("\n🔄 Running BidNet extraction with geographic filtering...")
        
        try:
            results = self.hybrid_scraper.run_hybrid_extraction()
            
            print("\n" + "="*50)
            print("📊 BIDNET EXTRACTION RESULTS")
            print("="*50)
            print(f"Total contracts found: {results['total_found']}")
            print(f"In LA region: {results['in_region']}")
            print(f"Out of region: {results['out_of_region']}")
            print(f"Saved to database: {results['saved_to_db']}")
            
            if results['errors']:
                print(f"Errors: {len(results['errors'])}")
            
            print("✅ BidNet extraction completed!")
            
        except Exception as e:
            print(f"❌ BidNet extraction failed: {e}")
    
    def _run_manual_selection(self):
        """Run manual contract selection interface"""
        print("\n🎯 Starting manual contract selection interface...")
        
        try:
            self.selection_interface.run()
        except Exception as e:
            print(f"❌ Manual selection failed: {e}")
    
    def _run_ai_discovery(self):
        """Run AI pattern discovery for sample city websites"""
        print("\n🧠 Running AI pattern discovery...")
        
        # Sample LA region cities for testing
        test_cities = [
            {'city_name': 'Los Angeles', 'website_url': 'https://www.lacity.org/business/contracting-procurement'},
            {'city_name': 'Santa Monica', 'website_url': 'https://www.santamonica.gov/business/procurement'},
            {'city_name': 'Pasadena', 'website_url': 'https://www.cityofpasadena.net/finance/purchasing/'}
        ]
        
        cost_limit = float(input("Enter cost limit for AI analysis ($): ") or "2.0")
        
        try:
            results = self.ai_agent.batch_analyze_cities(test_cities, max_cost=cost_limit)
            
            print("\n" + "="*50) 
            print("🧠 AI PATTERN DISCOVERY RESULTS")
            print("="*50)
            
            total_cost = 0.0
            successful = 0
            
            for result in results:
                status = "✅ SUCCESS" if result['success'] else "❌ FAILED"
                cost = result.get('cost_estimate', 0.0)
                total_cost += cost
                
                if result['success']:
                    successful += 1
                    patterns = result.get('patterns', {})
                    selectors = len(patterns.get('selectors', {}))
                    print(f"{status}: {result['city_name']} - {selectors} patterns, ${cost:.2f}")
                else:
                    print(f"{status}: {result['city_name']} - {result.get('error', 'Unknown error')}")
            
            print("="*50)
            print(f"Total cities analyzed: {len(results)}")
            print(f"Successful analyses: {successful}")
            print(f"Total cost: ${total_cost:.2f}")
            
        except Exception as e:
            print(f"❌ AI discovery failed: {e}")
    
    def _run_multilayer_extraction(self):
        """Run multi-layer extraction on selected contracts"""
        print("\n🏗️ Running multi-layer extraction...")
        
        try:
            max_contracts = int(input("Max contracts to process: ") or "5")
            cost_limit = float(input("Cost limit ($): ") or "3.0")
            
            results = self.multi_layer_extractor.process_selected_contracts(
                max_contracts=max_contracts,
                cost_limit=cost_limit
            )
            
            print("\n" + "="*50)
            print("🏗️ MULTI-LAYER EXTRACTION RESULTS") 
            print("="*50)
            print(f"Contracts processed: {results['contracts_processed']}")
            print(f"City details extracted: {results['city_details_extracted']}")
            print(f"PDFs downloaded: {results['pdfs_downloaded']}")
            print(f"Success rate: {results['success_rate']:.1%}")
            print(f"Total cost: ${results.get('total_cost', 0.0):.2f}")
            
            if results['errors']:
                print(f"Errors: {len(results['errors'])}")
            
        except Exception as e:
            print(f"❌ Multi-layer extraction failed: {e}")
    
    def _run_full_pipeline_interactive(self):
        """Run complete pipeline with user input"""
        print("\n🚀 Running complete hybrid pipeline...")
        
        try:
            max_contracts = int(input("Max contracts for AI processing: ") or "10")
            cost_limit = float(input("Cost limit for AI processing ($): ") or "5.0")
            
            print(f"\n🔄 Starting pipeline (max: {max_contracts} contracts, limit: ${cost_limit:.2f})")
            
            results = self.run_full_pipeline(max_contracts=max_contracts, cost_limit=cost_limit)
            
            print("\n" + "="*60)
            print("🎉 COMPLETE HYBRID PIPELINE RESULTS")
            print("="*60)
            
            # Phase 1 results
            phase1 = results.get('phase_1_bidnet', {})
            print(f"📥 BidNet Phase:")
            print(f"  • Total found: {phase1.get('total_found', 0)}")
            print(f"  • In LA region: {phase1.get('in_region', 0)}")
            print(f"  • Saved to DB: {phase1.get('saved_to_db', 0)}")
            
            # Phase 3 results
            phase3 = results.get('phase_3_multilayer', {})
            print(f"\n🏗️ Multi-layer Phase:")
            print(f"  • Contracts processed: {phase3.get('contracts_processed', 0)}")
            print(f"  • City details: {phase3.get('city_details_extracted', 0)}")
            print(f"  • PDFs downloaded: {phase3.get('pdfs_downloaded', 0)}")
            
            print(f"\n💰 Total cost: ${results.get('total_cost', 0.0):.2f}")
            
            if 'report_file' in results:
                print(f"📊 Report saved: {results['report_file']}")
            
            if results.get('errors'):
                print(f"\n⚠️ Errors encountered: {len(results['errors'])}")
            
        except Exception as e:
            print(f"❌ Full pipeline failed: {e}")
    
    def _show_system_status(self):
        """Show current system status"""
        print("\n📊 System Status")
        print("="*40)
        
        try:
            with self.db.get_session() as session:
                from src.database.models import Contract, ProcessingQueue, CityPlatform, ProcessingStatus
                
                # Database statistics
                total_contracts = session.query(Contract).count()
                pending_queue = session.query(ProcessingQueue).filter(
                    ProcessingQueue.status == ProcessingStatus.PENDING
                ).count()
                city_platforms = session.query(CityPlatform).count()
                
                print(f"📋 Total contracts in database: {total_contracts}")
                print(f"⏳ Pending in processing queue: {pending_queue}")
                print(f"🏛️ City platforms discovered: {city_platforms}")
                
                # AI analysis status
                ai_cost = self.ai_agent.get_session_cost_summary()
                print(f"🤖 Session AI cost: ${ai_cost['total_cost']:.2f}")
                print(f"🧠 AI provider: {ai_cost['ai_provider']}/{ai_cost['model']}")
                
        except Exception as e:
            print(f"❌ Could not retrieve status: {e}")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Hybrid AI System Orchestrator")
    parser.add_argument('--mode', choices=['interactive', 'full', 'bidnet', 'extract'], 
                       default='interactive', help='Operation mode')
    parser.add_argument('--max-contracts', type=int, default=10, 
                       help='Maximum contracts for AI processing')
    parser.add_argument('--cost-limit', type=float, default=5.0,
                       help='Cost limit for AI processing')
    
    args = parser.parse_args()
    
    try:
        orchestrator = HybridSystemOrchestrator()
        
        if args.mode == 'interactive':
            orchestrator.run_interactive_session()
        elif args.mode == 'full':
            results = orchestrator.run_full_pipeline(args.max_contracts, args.cost_limit)
            print(f"\n🎉 Pipeline completed! Cost: ${results.get('total_cost', 0.0):.2f}")
        elif args.mode == 'bidnet':
            results = orchestrator.hybrid_scraper.run_hybrid_extraction()
            print(f"✅ BidNet extraction: {results['in_region']} contracts in LA region")
        elif args.mode == 'extract':
            results = orchestrator.multi_layer_extractor.process_selected_contracts(
                args.max_contracts, args.cost_limit
            )
            print(f"🏗️ Extraction: {results['contracts_processed']} processed, ${results.get('total_cost', 0.0):.2f}")
        
    except Exception as e:
        logger.error(f"❌ System failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()