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

class PortalType(enum.Enum):
    PLANETBIDS = "planetbids"
    BIDSYNC = "bidsync" 
    DEMANDSTAR = "demandstar"
    PUBLICPURCHASE = "publicpurchase"
    CIVICBID = "civicbid"
    CUSTOM = "custom"
    NONE = "none"  # No portal required

class AccountStatus(enum.Enum):
    REGISTERED = "registered"
    NEEDS_REGISTRATION = "needs_registration" 
    PENDING = "pending"
    FAILED = "failed"
    MANUAL_REQUIRED = "manual_required"

class FlagStatus(enum.Enum):
    PENDING = "pending"
    RESOLVED = "resolved"
    MANUAL_REQUIRED = "manual_required"
    ABANDONED = "abandoned"

class ExtractionFlagType(enum.Enum):
    """Progressive harvest flag categories"""
    PORTAL_REGISTRATION_NEEDED = "portal_registration_needed"
    NAVIGATION_FAILED = "navigation_failed"
    ACCESS_DENIED = "access_denied"
    NO_RFP_FOUND = "no_rfp_found"
    TECHNICAL_ERROR = "technical_error"
    SUCCESS = "success"

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

class CityPortal(Base):
    """Track portal requirements for each city"""
    __tablename__ = "city_portals"
    
    city_name = Column(String(100), primary_key=True)
    portal_type = Column(Enum(PortalType), nullable=False)
    portal_url = Column(String(500))
    registration_required = Column(Boolean, default=False)
    account_status = Column(Enum(AccountStatus), default=AccountStatus.NEEDS_REGISTRATION)
    
    # Discovery metadata
    detected_date = Column(DateTime, default=datetime.utcnow)
    last_verified = Column(DateTime)
    detection_confidence = Column(Float, default=0.0)  # AI confidence in detection
    
    # Portal-specific info
    registration_url = Column(String(500))
    login_url = Column(String(500))
    portal_subdomain = Column(String(100))  # e.g., "losangeles" in losangeles.planetbids.com
    
    # Processing tracking
    successful_logins = Column(Integer, default=0)
    failed_login_attempts = Column(Integer, default=0)
    last_successful_login = Column(DateTime)
    
    # Notes and requirements
    registration_notes = Column(Text)  # Special requirements, forms needed, etc.
    business_license_required = Column(Boolean, default=False)
    insurance_required = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PortalCredential(Base):
    """Securely store portal login credentials"""
    __tablename__ = "portal_credentials"
    
    portal_key = Column(String(200), primary_key=True)  # e.g., "losangeles_planetbids"
    city_name = Column(String(100), nullable=False)
    portal_type = Column(Enum(PortalType), nullable=False)
    
    # Credentials (should be encrypted in production)
    username = Column(String(100))
    password_encrypted = Column(String(500))  # Store encrypted passwords
    email = Column(String(200))
    
    # Registration info
    registration_date = Column(DateTime)
    registration_method = Column(String(50))  # "manual", "automated", "imported"
    registered_by = Column(String(100))  # Who registered this account
    
    # Verification tracking
    last_verified = Column(DateTime)
    verification_status = Column(Enum(AccountStatus), default=AccountStatus.PENDING)
    verification_error = Column(Text)
    
    # Business info (often required for registration)
    business_name = Column(String(200))
    business_address = Column(Text)
    business_phone = Column(String(50))
    tax_id = Column(String(50))
    
    # Security and recovery
    security_questions = Column(JSON)  # Store Q&A for account recovery
    backup_email = Column(String(200))
    password_last_changed = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class RegistrationFlag(Base):
    """Track manual intervention needs for portal access"""
    __tablename__ = "registration_flags"
    
    id = Column(Integer, primary_key=True)
    city_name = Column(String(100), nullable=False)
    portal_type = Column(Enum(PortalType))
    portal_url = Column(String(500))
    
    # Flag details
    flag_reason = Column(String(100))  # "registration_needed", "login_failed", "access_denied"
    flag_description = Column(Text)
    priority_score = Column(Integer, default=0)  # Higher = more urgent
    estimated_manual_hours = Column(Float, default=1.0)
    
    # Context information
    contract_count = Column(Integer, default=0)  # How many contracts affected
    total_contract_value = Column(String(100))  # Estimated value of affected contracts
    last_attempt_date = Column(DateTime)
    error_details = Column(JSON)  # Technical error information
    screenshot_path = Column(String(500))  # Path to error screenshot
    
    # Resolution tracking
    flagged_date = Column(DateTime, default=datetime.utcnow)
    resolution_status = Column(Enum(FlagStatus), default=FlagStatus.PENDING)
    resolved_date = Column(DateTime)
    resolved_by = Column(String(100))
    resolution_notes = Column(Text)
    
    # Follow-up actions
    next_retry_date = Column(DateTime)
    max_retries = Column(Integer, default=3)
    current_retry_count = Column(Integer, default=0)

class PortalPattern(Base):
    """Store successful portal navigation patterns for reuse"""
    __tablename__ = "portal_patterns"
    
    id = Column(Integer, primary_key=True)
    portal_type = Column(Enum(PortalType), nullable=False)
    pattern_name = Column(String(100))  # e.g., "planetbids_generic_v1"
    
    # Navigation patterns
    login_selectors = Column(JSON)  # CSS selectors for login form
    navigation_flow = Column(JSON)  # Step-by-step navigation instructions
    document_selectors = Column(JSON)  # How to find downloadable documents
    search_patterns = Column(JSON)  # How to search for specific RFPs
    
    # Success tracking
    success_rate = Column(Float, default=0.0)
    total_attempts = Column(Integer, default=0)
    successful_attempts = Column(Integer, default=0)
    last_successful_use = Column(DateTime)
    
    # Pattern metadata
    created_from_city = Column(String(100))  # Which city this pattern was learned from
    works_with_cities = Column(JSON)  # List of cities where this pattern works
    pattern_confidence = Column(Float, default=0.0)
    
    # Versioning and updates
    pattern_version = Column(String(20), default="1.0")
    replaced_by_pattern_id = Column(Integer)  # If pattern was updated
    is_active = Column(Boolean, default=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PortalSession(Base):
    """Track portal login sessions and activity"""
    __tablename__ = "portal_sessions"
    
    id = Column(Integer, primary_key=True)
    portal_key = Column(String(200), nullable=False)  # References portal_credentials
    session_start = Column(DateTime, default=datetime.utcnow)
    session_end = Column(DateTime)
    
    # Session details
    login_successful = Column(Boolean, default=False)
    documents_accessed = Column(Integer, default=0)
    documents_downloaded = Column(Integer, default=0)
    contracts_processed = Column(Integer, default=0)
    
    # Technical details
    user_agent = Column(String(500))
    session_cookies = Column(JSON)  # Store session cookies for reuse
    ip_address = Column(String(50))
    
    # Error tracking
    errors_encountered = Column(JSON)
    session_status = Column(Enum(ProcessingStatus), default=ProcessingStatus.IN_PROGRESS)
    error_message = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)

class ExtractionAttempt(Base):
    """Track progressive harvest extraction attempts"""
    __tablename__ = "extraction_attempts"
    
    id = Column(Integer, primary_key=True)
    contract_id = Column(Integer, ForeignKey("contracts.id"), nullable=False)
    
    # Attempt details
    attempt_date = Column(DateTime, default=datetime.utcnow)
    extraction_flag_type = Column(Enum(ExtractionFlagType), nullable=False)
    
    # URLs and navigation
    target_url = Column(String(500))  # City RFP page URL
    rfp_page_found = Column(Boolean, default=False)
    documents_found_count = Column(Integer, default=0)
    documents_downloaded_count = Column(Integer, default=0)
    
    # Flag details
    flag_reason = Column(String(500))  # Specific reason for flag
    flag_description = Column(Text)    # Detailed description
    technical_details = Column(JSON)   # Error messages, selectors tried, etc.
    
    # Portal detection results
    portal_type = Column(Enum(PortalType))
    portal_url = Column(String(500))
    registration_required = Column(Boolean, default=False)
    
    # Success data (if successful)
    pdf_files_found = Column(JSON)     # List of found PDF files
    pdf_download_paths = Column(JSON)  # Local paths of downloaded files
    extracted_data = Column(JSON)      # Any additional data extracted
    
    # Processing metadata
    ai_cost_estimate = Column(Float, default=0.0)
    processing_time_seconds = Column(Float)
    retry_count = Column(Integer, default=0)
    
    # Priority for resolution (1-100, higher = more urgent)
    resolution_priority = Column(Integer, default=50)
    
    # Relationships
    contract = relationship("Contract")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)