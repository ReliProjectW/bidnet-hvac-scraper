import os
import logging
import requests
from typing import List, Dict, Any, Optional
from pathlib import Path
from datetime import datetime
import hashlib

from ..database.models import PlanDownload, ProcessingStatus, Contract
from ..database.connection import db_manager
from config import Config

class PDFDownloader:
    """
    Download and manage PDF plans from city websites
    Layer 3: Plan Downloads
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.download_dir = Path(Config.DATA_DIR) / "plans"
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        # Download settings
        self.max_file_size_mb = Config.MAX_PDF_SIZE_MB
        self.timeout = Config.DOWNLOAD_TIMEOUT
        
        # Session for downloads
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
    
    def download_contract_plans(self, contract_id: int, plan_urls: List[str]) -> List[Dict[str, Any]]:
        """
        Download PDF plans for a specific contract
        
        Args:
            contract_id: Database ID of the contract
            plan_urls: List of URLs to download
            
        Returns:
            List of download results
        """
        self.logger.info(f"📁 Downloading plans for contract {contract_id}")
        
        results = []
        
        with db_manager.get_session() as session:
            contract = session.query(Contract).filter(Contract.id == contract_id).first()
            if not contract:
                raise ValueError(f"Contract {contract_id} not found")
            
            # Create contract-specific directory
            contract_dir = self.download_dir / f"contract_{contract_id}"
            contract_dir.mkdir(exist_ok=True)
            
            for i, url in enumerate(plan_urls, 1):
                try:
                    result = self._download_single_pdf(
                        contract_id, url, contract_dir, f"plan_{i}"
                    )
                    results.append(result)
                    
                    if result['success']:
                        # Create database record
                        plan_download = PlanDownload(
                            contract_id=contract_id,
                            filename=result['filename'],
                            original_url=url,
                            file_path=result['file_path'],
                            file_size_mb=result['file_size_mb'],
                            download_status=ProcessingStatus.COMPLETED,
                            download_date=datetime.utcnow()
                        )
                        session.add(plan_download)
                    
                except Exception as e:
                    self.logger.error(f"Failed to download {url}: {e}")
                    results.append({
                        'success': False,
                        'url': url,
                        'error': str(e)
                    })
            
            session.commit()
        
        successful = sum(1 for r in results if r['success'])
        self.logger.info(f"✅ Downloaded {successful}/{len(results)} plans for contract {contract_id}")
        
        return results
    
    def _download_single_pdf(self, contract_id: int, url: str, 
                           download_dir: Path, filename_prefix: str) -> Dict[str, Any]:
        """Download a single PDF file"""
        try:
            self.logger.info(f"⬇️  Downloading: {url}")
            
            # Make request with streaming
            response = self.session.get(url, stream=True, timeout=self.timeout)
            response.raise_for_status()
            
            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'pdf' not in content_type and not url.lower().endswith('.pdf'):
                # Try to detect PDF by content
                first_chunk = next(response.iter_content(chunk_size=1024), b'')
                if not first_chunk.startswith(b'%PDF'):
                    self.logger.warning(f"⚠️  URL may not be a PDF: {url}")
            
            # Generate filename
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            filename = f"{filename_prefix}_{url_hash}.pdf"
            file_path = download_dir / filename
            
            # Check file size from headers
            content_length = response.headers.get('content-length')
            if content_length:
                size_mb = int(content_length) / (1024 * 1024)
                if size_mb > self.max_file_size_mb:
                    return {
                        'success': False,
                        'url': url,
                        'error': f'File too large: {size_mb:.1f}MB (max: {self.max_file_size_mb}MB)'
                    }
            
            # Download file
            total_size = 0
            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)
                        
                        # Check size during download
                        if total_size > self.max_file_size_mb * 1024 * 1024:
                            f.close()
                            file_path.unlink()  # Delete partial file
                            return {
                                'success': False,
                                'url': url,
                                'error': f'File too large during download (>{self.max_file_size_mb}MB)'
                            }
            
            file_size_mb = total_size / (1024 * 1024)
            
            self.logger.info(f"✅ Downloaded {filename} ({file_size_mb:.1f}MB)")
            
            return {
                'success': True,
                'url': url,
                'filename': filename,
                'file_path': str(file_path),
                'file_size_mb': file_size_mb
            }
            
        except requests.exceptions.Timeout:
            return {
                'success': False,
                'url': url,
                'error': f'Download timeout ({self.timeout}s)'
            }
        except requests.exceptions.RequestException as e:
            return {
                'success': False,
                'url': url,
                'error': f'Request failed: {str(e)}'
            }
        except Exception as e:
            return {
                'success': False,
                'url': url,
                'error': f'Unexpected error: {str(e)}'
            }
    
    def extract_pdf_text(self, plan_download_id: int) -> bool:
        """Extract text from downloaded PDF"""
        try:
            import PyPDF2
            import pdfplumber
        except ImportError:
            self.logger.error("PDF processing libraries not installed")
            return False
        
        with db_manager.get_session() as session:
            plan = session.query(PlanDownload).filter(PlanDownload.id == plan_download_id).first()
            if not plan:
                return False
            
            if not os.path.exists(plan.file_path):
                self.logger.error(f"PDF file not found: {plan.file_path}")
                return False
            
            try:
                # Try pdfplumber first (better text extraction)
                with pdfplumber.open(plan.file_path) as pdf:
                    text_content = ""
                    for page in pdf.pages[:10]:  # Limit to first 10 pages
                        page_text = page.extract_text()
                        if page_text:
                            text_content += page_text + "\n\n"
                
                if not text_content.strip():
                    # Fallback to PyPDF2
                    with open(plan.file_path, 'rb') as f:
                        pdf_reader = PyPDF2.PdfReader(f)
                        text_content = ""
                        for page_num, page in enumerate(pdf_reader.pages[:10]):
                            text_content += page.extract_text() + "\n\n"
                
                # Store extracted text
                plan.text_content = text_content[:50000]  # Limit text size
                plan.pdf_extracted = True
                session.commit()
                
                self.logger.info(f"✅ Extracted text from {plan.filename} ({len(text_content)} chars)")
                return True
                
            except Exception as e:
                self.logger.error(f"Failed to extract text from {plan.filename}: {e}")
                return False
    
    def get_download_summary(self, contract_id: int = None) -> Dict[str, Any]:
        """Get download summary statistics"""
        with db_manager.get_session() as session:
            query = session.query(PlanDownload)
            
            if contract_id:
                query = query.filter(PlanDownload.contract_id == contract_id)
            
            all_downloads = query.all()
            
            total_size = sum(d.file_size_mb or 0 for d in all_downloads)
            successful = sum(1 for d in all_downloads if d.download_status == ProcessingStatus.COMPLETED)
            
            return {
                'total_downloads': len(all_downloads),
                'successful_downloads': successful,
                'failed_downloads': len(all_downloads) - successful,
                'total_size_mb': total_size,
                'text_extracted': sum(1 for d in all_downloads if d.pdf_extracted),
                'avg_file_size_mb': total_size / max(len(all_downloads), 1)
            }
    
    def cleanup_old_files(self, days_old: int = 30) -> int:
        """Clean up old downloaded files"""
        from datetime import timedelta
        
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        cleaned_count = 0
        
        with db_manager.get_session() as session:
            old_downloads = session.query(PlanDownload).filter(
                PlanDownload.download_date < cutoff_date
            ).all()
            
            for download in old_downloads:
                try:
                    if os.path.exists(download.file_path):
                        os.unlink(download.file_path)
                        cleaned_count += 1
                    
                    session.delete(download)
                except Exception as e:
                    self.logger.warning(f"Failed to cleanup {download.filename}: {e}")
            
            session.commit()
        
        self.logger.info(f"🧹 Cleaned up {cleaned_count} old files")
        return cleaned_count