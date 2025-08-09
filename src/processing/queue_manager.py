import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database.models import ProcessingQueue, ProcessingStatus, Contract, CityContract
from ..database.connection import db_manager

class QueueManager:
    """
    Manages the processing queue for batch operations and manual selection
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def add_to_queue(self, task_type: str, target_id: str, 
                    config_data: Dict[str, Any] = None,
                    priority: int = 0, manually_selected: bool = False,
                    selected_by: str = None) -> int:
        """
        Add a task to the processing queue
        
        Args:
            task_type: Type of task ("ai_analysis", "traditional_scrape", "pdf_download")
            target_id: Identifier for the target (contract ID, URL, etc.)
            config_data: Task-specific configuration
            priority: Priority level (higher = more important)
            manually_selected: Whether this was manually selected by user
            selected_by: Username who selected this task
            
        Returns:
            Queue item ID
        """
        with db_manager.get_session() as session:
            queue_item = ProcessingQueue(
                task_type=task_type,
                target_id=target_id,
                config_data=config_data or {},
                priority=priority,
                manually_selected=manually_selected,
                selected_by=selected_by,
                status=ProcessingStatus.PENDING
            )
            
            session.add(queue_item)
            session.commit()
            
            self.logger.info(f"Added to queue: {task_type} for {target_id} (priority: {priority})")
            return queue_item.id
    
    def get_pending_tasks(self, task_type: str = None, limit: int = 10) -> List[ProcessingQueue]:
        """Get pending tasks from the queue"""
        with db_manager.get_session() as session:
            query = session.query(ProcessingQueue).filter(
                ProcessingQueue.status == ProcessingStatus.PENDING
            )
            
            if task_type:
                query = query.filter(ProcessingQueue.task_type == task_type)
            
            # Order by priority (desc) then created_at (asc)
            query = query.order_by(
                ProcessingQueue.priority.desc(),
                ProcessingQueue.created_at.asc()
            )
            
            if limit:
                query = query.limit(limit)
            
            return query.all()
    
    def mark_task_started(self, queue_id: int) -> bool:
        """Mark a task as started"""
        with db_manager.get_session() as session:
            task = session.query(ProcessingQueue).filter(ProcessingQueue.id == queue_id).first()
            if task:
                task.status = ProcessingStatus.IN_PROGRESS
                task.started_at = datetime.utcnow()
                session.commit()
                return True
            return False
    
    def mark_task_completed(self, queue_id: int) -> bool:
        """Mark a task as completed"""
        with db_manager.get_session() as session:
            task = session.query(ProcessingQueue).filter(ProcessingQueue.id == queue_id).first()
            if task:
                task.status = ProcessingStatus.COMPLETED
                task.completed_at = datetime.utcnow()
                session.commit()
                return True
            return False
    
    def mark_task_failed(self, queue_id: int, error_message: str) -> bool:
        """Mark a task as failed"""
        with db_manager.get_session() as session:
            task = session.query(ProcessingQueue).filter(ProcessingQueue.id == queue_id).first()
            if task:
                task.status = ProcessingStatus.FAILED
                task.error_message = error_message
                task.retry_count += 1
                
                # If we haven't exceeded max retries, reset to pending
                if task.retry_count <= task.max_retries:
                    task.status = ProcessingStatus.PENDING
                    task.started_at = None
                    self.logger.info(f"Task {queue_id} failed, will retry ({task.retry_count}/{task.max_retries})")
                else:
                    self.logger.error(f"Task {queue_id} failed permanently after {task.retry_count} retries")
                
                session.commit()
                return True
            return False
    
    def get_manual_selection_candidates(self, limit: int = 20) -> List[Dict[str, Any]]:
        """
        Get contracts that are good candidates for manual AI processing selection
        
        Returns contracts that are:
        1. In target geographic region
        2. Have high HVAC relevance
        3. Haven't been processed yet
        """
        with db_manager.get_session() as session:
            # Get contracts that haven't been queued for AI analysis yet
            subquery = session.query(ProcessingQueue.target_id).filter(
                ProcessingQueue.task_type == 'ai_analysis'
            ).subquery()
            
            contracts = session.query(Contract).filter(
                Contract.processing_status == ProcessingStatus.PENDING,
                Contract.hvac_relevance_score > 0,
                Contract.in_target_region == True,
                ~Contract.id.in_(subquery)  # Not already queued
            ).order_by(
                Contract.hvac_relevance_score.desc(),
                Contract.discovered_at.desc()
            ).limit(limit).all()
            
            # Convert to dictionaries with additional info
            candidates = []
            for contract in contracts:
                candidates.append({
                    'id': contract.id,
                    'title': contract.title,
                    'agency': contract.agency,
                    'location': contract.location,
                    'estimated_value': contract.estimated_value,
                    'hvac_relevance_score': contract.hvac_relevance_score,
                    'matching_keywords': contract.matching_keywords,
                    'discovered_at': contract.discovered_at.isoformat(),
                    'source_url': contract.source_url
                })
            
            return candidates
    
    def queue_selected_contracts_for_ai(self, contract_ids: List[int], 
                                      selected_by: str) -> int:
        """
        Queue manually selected contracts for AI processing
        
        Args:
            contract_ids: List of contract IDs to process
            selected_by: Username who made the selection
            
        Returns:
            Number of contracts queued
        """
        queued_count = 0
        
        for contract_id in contract_ids:
            # Add to queue with high priority since manually selected
            self.add_to_queue(
                task_type="ai_analysis",
                target_id=str(contract_id),
                config_data={"contract_id": contract_id},
                priority=10,  # High priority for manual selections
                manually_selected=True,
                selected_by=selected_by
            )
            queued_count += 1
        
        self.logger.info(f"Queued {queued_count} contracts for AI processing (selected by {selected_by})")
        return queued_count
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get overall queue status"""
        with db_manager.get_session() as session:
            status_counts = session.query(
                ProcessingQueue.status,
                ProcessingQueue.task_type,
                func.count(ProcessingQueue.id)
            ).group_by(
                ProcessingQueue.status,
                ProcessingQueue.task_type
            ).all()
            
            # Organize results
            result = {
                "total_tasks": 0,
                "by_status": {},
                "by_type": {},
                "manual_selections": 0
            }
            
            for status, task_type, count in status_counts:
                result["total_tasks"] += count
                
                if status.value not in result["by_status"]:
                    result["by_status"][status.value] = 0
                result["by_status"][status.value] += count
                
                if task_type not in result["by_type"]:
                    result["by_type"][task_type] = {}
                if status.value not in result["by_type"][task_type]:
                    result["by_type"][task_type][status.value] = 0
                result["by_type"][task_type][status.value] += count
            
            # Count manual selections
            manual_count = session.query(ProcessingQueue).filter(
                ProcessingQueue.manually_selected == True
            ).count()
            result["manual_selections"] = manual_count
            
            return result
    
    def cleanup_old_tasks(self, days_old: int = 7) -> int:
        """Clean up old completed/failed tasks"""
        with db_manager.get_session() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            deleted = session.query(ProcessingQueue).filter(
                ProcessingQueue.status.in_([ProcessingStatus.COMPLETED, ProcessingStatus.FAILED]),
                ProcessingQueue.completed_at < cutoff_date
            ).delete()
            
            session.commit()
            
            self.logger.info(f"Cleaned up {deleted} old tasks")
            return deleted