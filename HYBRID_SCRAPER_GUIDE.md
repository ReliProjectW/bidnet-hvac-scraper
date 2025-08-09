# BidNet HVAC Hybrid Scraper Guide

## Overview

This is a sophisticated 3-phase hybrid AI + traditional scraping system designed to efficiently extract HVAC contracts from BidNet while conserving credits through smart geographic filtering and batch processing.

## Architecture

### Phase 1: AI Discovery (One-Time)
- **Cost**: $10-20 one-time
- **Purpose**: Use Browser Use + Claude to discover BidNet structure
- **Output**: Reliable Python/Selenium patterns for Phase 2

### Phase 2: Traditional Scraping (Daily Production)
- **Cost**: Nearly free
- **Purpose**: Fast daily scraping using AI-discovered patterns
- **Features**: Geographic filtering, cookie-based auth

### Phase 3: Auto-Healing (As Needed)
- **Cost**: $5-10 every few months
- **Purpose**: Re-analyze when sites change
- **Trigger**: Automatic when scraping fails

## Key Features

### 🎯 Geographic Filtering
- **Target Region**: LA region + south to Mexico border
- **Counties**: Los Angeles, Orange, San Diego, Riverside, San Bernardino, Imperial, Ventura
- **Benefit**: Conserves AI credits by filtering out irrelevant contracts

### 🤖 Multi-Layer Data Extraction
1. **BidNet Contract Listings** → Extract basic contract info
2. **Individual Contract Details** → Follow RFP links to city websites  
3. **Plan Downloads** → Download PDF plans (100-200MB each)

### 🏗️ Multi-Platform City Handling
- **City Websites**: Custom scrapers for each city
- **PlanetBids**: Standardized platform handling
- **Self-Learning**: AI discovers new platform patterns
- **Registration Support**: Handles login requirements

### 📊 Batch Processing & Manual Selection
- **Manual Selection**: Choose specific contracts for AI processing
- **Batch Processing**: Process 3-5 contracts at once
- **Cost Control**: Track and limit AI spending
- **Queue System**: Prioritize high-value contracts

## Database Schema

### Core Tables
- **`contracts`**: Main contract information
- **`city_contracts`**: City-specific details and RFP links
- **`plan_downloads`**: Downloaded PDF files
- **`city_platforms`**: AI-discovered platform patterns
- **`processing_queue`**: Task management and batch processing
- **`ai_analysis_logs`**: Cost tracking and performance monitoring

### Status Tracking
- **Processing Status**: PENDING → IN_PROGRESS → COMPLETED/FAILED
- **Geographic Region**: Automatic classification by region
- **HVAC Relevance**: Scoring system for contract relevance

## Installation & Setup

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Environment Configuration
Create `.env` file:
```env
BIDNET_USERNAME=your_username
BIDNET_PASSWORD=your_password
```

### 3. Initialize Database
```bash
python -c \"from src.database.connection import db_manager; print('Database initialized')\"
```

## Usage Guide

### CLI Commands

#### Phase 1: Discover BidNet Patterns (One-Time)
```bash
python hybrid_cli.py discover-patterns --save-patterns
```
- **Cost**: ~$10-20
- **Run**: Once initially, then monthly updates
- **Output**: AI-discovered CSS selectors and patterns

#### Phase 2: Search for Contracts
```bash
python hybrid_cli.py search-contracts --use-ai-patterns --limit 100
```
- **Cost**: Nearly free (traditional scraping)
- **Run**: Daily
- **Features**: Geographic filtering, HVAC relevance scoring

#### Manual Selection & Batch Processing
```bash
# See candidates for AI processing
python hybrid_cli.py show-candidates --limit 20

# Queue selected contracts (by ID)
python hybrid_cli.py process-selected 123 456 789 --selected-by \"your_name\"

# Process AI batch (costs ~$3 per contract)
python hybrid_cli.py process-ai-batch --batch-size 3
```

#### System Monitoring
```bash
# Queue status
python hybrid_cli.py queue-status

# Overall system status
python hybrid_cli.py system-status

# Download summary
python hybrid_cli.py download-summary
```

#### PDF Plan Downloads
```bash
# Download plans for a specific contract
python hybrid_cli.py download-plans 123 \"https://city.gov/plans.pdf\" \"https://city.gov/specs.pdf\"

# View download statistics
python hybrid_cli.py download-summary --contract-id 123
```

### Testing & Development
```bash
# Run system tests (includes AI processing confirmation)
python hybrid_cli.py test-system

# Export contracts to JSON
python hybrid_cli.py export-contracts contracts_backup.json
```

## Cost Management

### Estimated Costs
- **Phase 1 Discovery**: $10-20 (one-time per site)
- **City Platform Analysis**: $3-5 per new city
- **Auto-Healing**: $5-10 (every few months when sites change)
- **Daily Scraping**: Nearly free (traditional methods)

### Cost Tracking Features
- Real-time cost tracking in CLI
- Per-contract cost breakdown
- Monthly cost estimates
- AI usage logs in database

### Credit Conservation Strategies
1. **Geographic Filtering**: Only process relevant regions
2. **Manual Selection**: Choose high-value contracts
3. **Batch Processing**: Process multiple contracts efficiently
4. **Pattern Reuse**: Reuse AI discoveries for similar sites
5. **Fallback Logic**: Only use AI when traditional scraping fails

## Self-Learning System

### AI Pattern Discovery
1. **Initial Analysis**: AI discovers site structure
2. **Pattern Storage**: Save CSS selectors and workflows
3. **Traditional Scraping**: Use patterns for fast scraping
4. **Failure Detection**: Monitor for scraping failures
5. **Auto-Healing**: Re-analyze changed sites
6. **Pattern Updates**: Update stored patterns

### City Platform Library
- **Automatic Discovery**: AI learns new city platforms
- **Registration Handling**: Manages login requirements
- **Success Rate Tracking**: Monitor platform reliability  
- **Pattern Optimization**: Improve selectors over time

## File Organization

```
src/
├── database/           # SQLAlchemy models and connection
├── geographic/         # Geographic filtering system
├── ai_agents/          # Browser Use + Claude integration
├── processing/         # Queue management and batch processing
├── scraper/            # Hybrid scraping system
├── pdf/               # PDF download and processing
├── cli/               # Command-line interface
└── utils/             # Utility functions

data/
├── bidnet_scraper.db  # SQLite database
├── plans/             # Downloaded PDF plans
└── processed/         # Excel/CSV exports
```

## Advanced Features

### Auto-Healing Workflow
1. **Failure Detection**: Traditional scraper fails
2. **Error Analysis**: Classify failure type
3. **AI Re-Analysis**: Browser Use + Claude re-examine site
4. **Pattern Update**: Update stored CSS selectors
5. **Retry Scraping**: Use new patterns
6. **Success Validation**: Verify fixes work

### Multi-Platform Support
- **BidNet Direct**: Primary source platform
- **City Websites**: Individual city RFP pages
- **PlanetBids**: Standardized bidding platform
- **Custom Platforms**: AI discovers unique city systems

### Quality Assurance
- **HVAC Relevance Scoring**: Filter non-HVAC contracts
- **Geographic Validation**: Verify locations are in target region
- **Duplicate Detection**: Avoid processing same contract twice
- **Error Recovery**: Retry failed operations with different strategies

## Troubleshooting

### Common Issues

#### \"No contracts found\"
- Check BidNet credentials
- Verify geographic filters aren't too restrictive
- Run `discover-patterns` to update selectors

#### \"AI processing failed\"
- Check API keys and permissions
- Verify target URLs are accessible
- Review error logs in database

#### \"Download failed\"
- Check file size limits (200MB default)
- Verify PDF URLs are valid
- Check disk space

### Debug Commands
```bash
# Test authentication
python main.py --test-auth

# View detailed logs
tail -f logs/bidnet_scraper.log

# Check database contents
python -c \"from src.database.connection import db_manager; print('DB OK')\"
```

## Future Enhancements

### Planned Features
1. **Web Dashboard**: Visual interface for contract management
2. **Email Notifications**: Alerts for new high-value contracts
3. **Advanced Filtering**: ML-based contract classification
4. **API Integration**: RESTful API for external systems
5. **Mobile App**: Mobile interface for field teams

### Integration Possibilities
- **CRM Systems**: Export to customer management tools
- **Estimation Software**: Import contract data for bidding
- **Calendar Systems**: Track bid deadlines
- **Document Management**: Organize downloaded plans

## Support & Maintenance

### Regular Maintenance
- **Weekly**: Review failed downloads and AI errors
- **Monthly**: Update AI patterns if needed
- **Quarterly**: Clean up old files and optimize database

### Monitoring
- Track daily contract discovery rates
- Monitor AI cost per contract
- Review geographic filtering accuracy
- Validate HVAC relevance scoring

This hybrid approach provides the best of both worlds: AI intelligence for discovery and adaptation, combined with fast traditional scraping for daily operations. The system is designed to be cost-effective, self-learning, and maintainable over time.