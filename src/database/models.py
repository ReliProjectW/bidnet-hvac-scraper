import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, Enum, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class ProcessingStatus(enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class SourceType(enum.Enum):
    BIDNET = "bidnet"
    CITY_WEBSITE = "city_website"
    PLANET_BIDS = "planet_bids"
    OTHER = "other"

class GeographicRegion(enum.Enum):
    LOS_ANGELES = "los_angeles"
    ORANGE = "orange"
    SAN_DIEGO = "san_diego"
    RIVERSIDE = "riverside"
    SAN_BERNARDINO = "san_bernardino"
    IMPERIAL = "imperial"
    VENTURA = "ventura"
    OUT_OF_REGION = "out_of_region"

class Contract(Base):
    __tablename__ = "contracts"
    
    id = Column(Integer, primary_key=True)
    external_id = Column(String(255), unique=True, nullable=False)
    source_type = Column(Enum(SourceType), nullable=False)
    source_url = Column(String(500))
    
    # Basic contract info
    title = Column(Text, nullable=False)
    agency = Column(String(255))
    description = Column(Text)
    
    # Geographic data
    location = Column(String(255))
    geographic_region = Column(Enum(GeographicRegion))
    coordinates = Column(String(50))  # "lat,lng" format
    
    # Financial info
    estimated_value = Column(String(100))
    estimated_value_numeric = Column(Float)
    
    # Dates
    posted_date = Column(DateTime)
    due_date = Column(DateTime)
    open_date = Column(DateTime)
    
    # HVAC relevance
    hvac_relevance_score = Column(Float, default=0.0)
    matching_keywords = Column(JSON)  # List of matching HVAC keywords
    
    # Processing tracking
    processing_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    discovered_at = Column(DateTime, default=datetime.utcnow)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Raw data for debugging/reprocessing
    raw_data = Column(JSON)
    
    # Relationships
    city_contract = relationship("CityContract", back_populates="contract", uselist=False)
    plan_downloads = relationship("PlanDownload", back_populates="contract")

class CityContract(Base):
    __tablename__ = "city_contracts"
    
    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    
    # City-specific info
    city_name = Column(String(100), nullable=False)
    rfp_url = Column(String(500))
    city_platform = Column(String(100))  # e.g., "planet_bids", "city_website"
    
    # Authentication requirements
    requires_registration = Column(Boolean, default=False)
    login_credentials_stored = Column(Boolean, default=False)
    
    # Processing status
    detail_extraction_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    last_scraped = Column(DateTime)
    
    # City-specific data
    contact_info = Column(JSON)
    additional_details = Column(JSON)
    
    # AI patterns for future use
    extraction_patterns = Column(JSON)  # Stored CSS selectors/patterns for fast scraping
    last_pattern_update = Column(DateTime)
    
    # Relationship
    contract = relationship("Contract", back_populates="city_contract")

class PlanDownload(Base):
    __tablename__ = "plan_downloads"
    
    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    
    # File info
    filename = Column(String(255), nullable=False)
    original_url = Column(String(500))
    file_path = Column(String(500))  # Local storage path
    file_size_mb = Column(Float)
    
    # Download status
    download_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    download_date = Column(DateTime)
    
    # File processing
    pdf_extracted = Column(Boolean, default=False)
    text_content = Column(Text)  # Extracted PDF text
    
    # Relationship
    contract = relationship("Contract", back_populates="plan_downloads")

class CityPlatform(Base):
    __tablename__ = "city_platforms"
    
    id = Column(Integer, primary_key=True)
    city_name = Column(String(100), nullable=False, unique=True)
    platform_type = Column(String(100))  # planet_bids, city_website, etc.
    base_url = Column(String(255))
    
    # Authentication
    requires_registration = Column(Boolean, default=False)
    login_url = Column(String(255))
    has_credentials = Column(Boolean, default=False)
    
    # AI-discovered patterns
    search_selectors = Column(JSON)  # CSS selectors for searching
    contract_selectors = Column(JSON)  # CSS selectors for contract data
    download_patterns = Column(JSON)  # Patterns for PDF downloads
    
    # Self-learning metadata
    last_ai_analysis = Column(DateTime)
    success_rate = Column(Float, default=0.0)
    total_scrapes = Column(Integer, default=0)
    successful_scrapes = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class AIAnalysisLog(Base):
    __tablename__ = "ai_analysis_logs"
    
    id = Column(Integer, primary_key=True)
    
    # What was analyzed
    target_type = Column(String(50))  # "city_platform", "bidnet", "contract_page"
    target_id = Column(String(255))  # External ID or URL
    
    # AI analysis metadata
    analysis_date = Column(DateTime, default=datetime.utcnow)
    ai_model_used = Column(String(100))  # e.g., "claude-3.5-sonnet"
    cost_estimate = Column(Float)  # Estimated cost in dollars
    
    # Results
    patterns_discovered = Column(JSON)
    success = Column(Boolean, default=False)
    error_message = Column(Text)
    
    # Performance tracking
    contracts_found = Column(Integer, default=0)
    extraction_accuracy = Column(Float)  # If measurable
    
class ProcessingQueue(Base):
    __tablename__ = "processing_queue"
    
    id = Column(Integer, primary_key=True)
    
    # Queue item info
    task_type = Column(String(50))  # "ai_analysis", "traditional_scrape", "pdf_download"
    target_id = Column(String(255))  # Contract ID, URL, etc.
    priority = Column(Integer, default=0)  # Higher = more priority
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    # Status
    status = Column(Enum(ProcessingStatus), default=ProcessingStatus.PENDING)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Configuration
    config_data = Column(JSON)  # Task-specific configuration
    
    # Manual selection support
    manually_selected = Column(Boolean, default=False)
    selected_by = Column(String(100))  # User who selected this task