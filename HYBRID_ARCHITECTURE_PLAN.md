# 🤖 Hybrid AI + Traditional Scraper Architecture Plan

## 🎯 PROJECT OVERVIEW

**Current Status**: Phase 1 Complete - BidNet HVAC scraper working perfectly (53/53 contracts extracted)

**Next Goal**: Implement hybrid AI + traditional approach for comprehensive HVAC contract discovery

## 🏗️ SYSTEM ARCHITECTURE

### Phase 1: ✅ COMPLETED - BidNet Foundation
- **BidNet Direct scraper** (100% working)
- **Playwright automation** with authentication
- **Smart pagination** with validation
- **Clean data extraction** (Excel/CSV output)

### Phase 2: 🚀 HYBRID AI SYSTEM (Next Implementation)

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   BidNet        │    │  AI Pattern      │    │  City RFP       │
│   Scraper       │───▶│  Discovery       │───▶│  Scrapers       │
│   (Working)     │    │  Agent           │    │  (Generated)    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   SQLite        │    │  Manual          │    │  PDF Download   │
│   Database      │    │  Selection       │    │  & Processing   │
│   (Tracking)    │    │  Interface       │    │  System         │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## 📋 IMPLEMENTATION ROADMAP

### Phase 2A: Geographic Filtering & Database Setup
```python
# 1. Extend existing BidNet scraper with LA region filtering
# 2. Set up SQLite database for contract tracking
# 3. Add geographic boundary validation (LA to Mexico border)
```

**Key Components**:
- Geographic boundary definitions (LA County, Orange County, San Diego, etc.)
- SQLite schema for contracts, cities, processing status
- Integration layer with existing BidNet scraper

### Phase 2B: AI Pattern Discovery System
```python
# 1. AI agent for discovering city RFP site patterns
# 2. Pattern storage and validation system  
# 3. Automated city scraper generation
```

**Key Components**:
- AI agent integration (OpenAI/Anthropic API)
- Pattern discovery prompts and validation
- Dynamic scraper code generation and testing
- Cost tracking and credit management

### Phase 2C: Multi-Layer Extraction Pipeline
```python
# 1. BidNet → City RFP site navigation
# 2. PDF document discovery and download
# 3. Document processing and data extraction
```

**Key Components**:
- URL following from BidNet to city sites
- PDF detection and download automation
- Document parsing and content extraction
- Data consolidation and deduplication

### Phase 3: 🔮 FUTURE - Auto-Healing System
```python
# 1. Site change detection
# 2. Automatic pattern re-discovery  
# 3. Self-healing scraper updates
```

## 💰 COST OPTIMIZATION STRATEGY

### Credit Conservation Approach:
1. **Manual Selection Interface**: User selects contracts for deep processing
2. **Batch Processing**: Process multiple contracts in single AI calls
3. **Pattern Caching**: Store discovered patterns for reuse
4. **Fallback Layers**: Traditional scrapers before AI assistance

### Estimated Costs:
- **Phase 2 Setup**: ~$10-20 (one-time pattern discovery)
- **Daily Operations**: ~$1-5 (batch processing selected contracts)
- **Site Changes**: ~$5-10 (quarterly pattern updates)

## 🗂️ FILE STRUCTURE PLAN

```
bidnet-hvac-scraper/
├── bidnet_hvac_scraper_complete.py    # ✅ Working BidNet scraper
├── hybrid_system/
│   ├── __init__.py
│   ├── ai_agent.py                    # AI pattern discovery
│   ├── pattern_storage.py             # Pattern database
│   ├── city_scraper_generator.py      # Dynamic scraper creation
│   ├── geographic_filter.py           # LA region boundaries
│   ├── manual_selection_ui.py         # Contract selection interface
│   ├── pdf_processor.py               # Document handling
│   └── cost_tracker.py               # Credit management
├── database/
│   ├── schema.sql                     # SQLite database schema
│   └── migrations/                    # Database updates
├── scrapers/
│   ├── generated/                     # AI-generated city scrapers
│   └── templates/                     # Scraper templates
└── config/
    ├── geographic_boundaries.json     # LA region definitions
    └── ai_prompts.json                # Pattern discovery prompts
```

## 🎯 SUCCESS METRICS

### Phase 2 Goals:
- [ ] Geographic filtering working (LA region contracts only)
- [ ] SQLite database tracking all contracts and processing status
- [ ] AI pattern discovery for 5-10 city websites
- [ ] Manual selection interface for cost control
- [ ] Multi-layer extraction: BidNet → City → PDF

### Quality Targets:
- **Geographic Accuracy**: 95%+ contracts within LA region boundaries
- **Cost Efficiency**: <$5/day for comprehensive processing
- **Data Quality**: Zero duplicates, validated contract information
- **Processing Speed**: <30 seconds per contract (including AI analysis)

## 🔧 TECHNICAL CONSIDERATIONS

### Integration Points:
1. **Preserve existing BidNet scraper** (don't modify - it works!)
2. **Extend with geographic filtering** layer
3. **Add database persistence** for tracking
4. **Build AI system** as separate module
5. **Create orchestration layer** for full pipeline

### Error Handling:
- Fallback to traditional scrapers when AI fails
- Graceful degradation when city sites are unavailable  
- Cost limits and automatic shutoffs
- Manual override capabilities

## 🚀 NEXT STEPS FOR IMPLEMENTATION

1. **Start with geographic filtering** - extend BidNet scraper results
2. **Set up SQLite database** - track contracts and processing status  
3. **Build manual selection interface** - cost-effective contract processing
4. **Implement AI pattern discovery** - start with 1-2 city websites
5. **Create multi-layer extraction** - BidNet → City → PDF pipeline

**Priority**: Build incrementally on the solid BidNet foundation without breaking existing functionality.