# BidNet HVAC Contract Scraper

Python web scraper for automatically finding HVAC contracts on BidNet Direct in Southern California.

## Phase 1: Project Setup & Authentication ✅

### Prerequisites

- Python 3.8+
- Chrome browser (for Selenium WebDriver)
- BidNet Direct account credentials

### Setup Instructions

1. **Clone/Download the project** (already done)

2. **Install dependencies:**
   ```bash
   # Activate virtual environment
   source venv/bin/activate
   
   # Dependencies are already installed, but if needed:
   pip install -r requirements.txt
   ```

3. **Configure credentials:**
   ```bash
   # Copy example environment file
   cp .env.example .env
   
   # Edit .env and add your BidNet Direct credentials
   nano .env
   ```

4. **Test authentication:**
   ```bash
   python main.py --test-auth
   ```

### Project Structure

```
bidnet-hvac-scraper/
├── main.py              # Main entry point
├── config.py            # Configuration settings
├── requirements.txt     # Python dependencies
├── .env.example         # Environment variables template
├── src/
│   ├── auth/           # Authentication module
│   │   └── bidnet_auth.py
│   ├── scraper/        # Web scraping (Phase 2)
│   ├── pdf_parser/     # PDF processing (Phase 4)
│   └── utils/          # Utility functions
├── data/
│   ├── raw/            # Raw scraped data
│   └── processed/      # Processed contract data
├── logs/               # Application logs
└── tests/              # Unit tests
```

### Current Features

- ✅ Project structure setup
- ✅ Virtual environment with dependencies
- ✅ Configuration management
- ✅ BidNet Direct SAML/SSO authentication
- ✅ Logging system
- ✅ Command-line interface

### Usage

```bash
# Test authentication
python main.py --test-auth

# Show help
python main.py --help
```

### Target Search Criteria

**Locations:** Los Angeles, Orange County, San Bernardino, Riverside, San Diego, Ventura, Imperial Counties

**Keywords:** 
- HVAC unit replacements
- Heat pump replacements  
- Package unit replacements
- Mini-split replacements
- School HVAC projects

### Next Phases

- **Phase 2:** Search and filtering functionality
- **Phase 3:** PDF download handling (100-200MB files)
- **Phase 4:** Plan analysis with OCR

### Troubleshooting

1. **ChromeDriver issues:** Make sure Chrome browser is installed
2. **Authentication fails:** Verify credentials in .env file
3. **SSL errors:** May need to install certificates or use --disable-ssl-verification flag

### Notes

- Uses Selenium for SAML/SSO authentication
- Designed for defensive security - contract discovery only
- Handles large PDF files (100-200MB)
- Focuses on Southern California HVAC opportunities