"""CRUD operations for Kwork projects."""
import json
from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from sqlalchemy import select, update, delete, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from loguru import logger

from . import models as db_models
from .kwork_models import KworkProject, ProjectSnapshot, ScrapeSession


class KworkCRUD:
    """Handles database operations for Kwork projects."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_project(self, kwork_id: Union[str, int]) -> Optional[KworkProject]:
        """Get a project by Kwork ID."""
        result = await self.session.execute(
            select(KworkProject)
            .filter(KworkProject.kwork_id == str(kwork_id))
            .options(selectinload(KworkProject.snapshots))
        )
        return result.scalars().first()
    
    async def get_project_by_url(self, url: str) -> Optional[KworkProject]:
        """Get a project by its URL."""
        result = await self.session.execute(
            select(KworkProject)
            .filter(KworkProject.url == url)
            .options(selectinload(KworkProject.snapshots))
        )
        return result.scalars().first()
    
    async def create_project(self, project_data: Dict[str, Any]) -> KworkProject:
        """Create a new project record."""
        # Extract Kwork ID from URL if not provided
        kwork_id = project_data.get('kwork_id')
        if not kwork_id and 'url' in project_data:
            # Extract ID from URL like /projects/1234567-title-here
            url_parts = project_data['url'].split('/')
            if len(url_parts) >= 2:
                kwork_id = url_parts[-1].split('-')[0]
        
        # Prepare project data
        project_dict = {
            'kwork_id': str(kwork_id) if kwork_id else None,
            'title': project_data.get('title'),
            'url': project_data.get('url'),
            'category': project_data.get('category'),
            'price': project_data.get('price'),
            'description': project_data.get('description'),
            'raw_data': project_data.get('raw_data', {}),
            'is_active': True,
            'is_processed': False,
        }
        
        # Parse date if provided
        if 'date_posted' in project_data and project_data['date_posted']:
            try:
                if isinstance(project_data['date_posted'], str):
                    project_dict['date_posted'] = datetime.fromisoformat(project_data['date_posted'])
                else:
                    project_dict['date_posted'] = project_data['date_posted']
            except (ValueError, TypeError) as e:
                logger.warning(f"Error parsing date_posted: {e}")
        
        # Create project
        project = KworkProject(**project_dict)
        self.session.add(project)
        
        # Create initial snapshot
        snapshot = ProjectSnapshot(
            project=project,
            price=project_data.get('price'),
            status='new',
            raw_data=project_data.get('raw_data', {})
        )
        self.session.add(snapshot)
        
        try:
            await self.session.commit()
            await self.session.refresh(project)
            logger.info(f"Created new project: {project.kwork_id} - {project.title}")
            return project
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating project: {e}")
            raise
    
    async def update_project(self, project: KworkProject, update_data: Dict[str, Any]) -> KworkProject:
        """Update an existing project and create a snapshot if needed."""
        from sqlalchemy import inspect
        
        # Track changes for snapshot
        changes = {}
        inspector = inspect(project)
        
        for key, value in update_data.items():
            if hasattr(project, key) and key not in ['updated_at', 'last_scraped_at']:
                old_value = getattr(project, key)
                if old_value != value:
                    changes[key] = {'old': old_value, 'new': value}
                    setattr(project, key, value)
        
        # Update timestamps
        project.updated_at = datetime.utcnow()
        project.last_scraped_at = datetime.utcnow()
        
        # Create snapshot if there are changes
        if changes:
            snapshot = ProjectSnapshot(
                project=project,
                price=update_data.get('price', project.price),
                status='updated',
                raw_data={
                    'changes': changes,
                    'previous_data': {c.key: getattr(project, c.key) for c in inspector.mapper.column_attrs}
                }
            )
            self.session.add(snapshot)
        
        try:
            await self.session.commit()
            await self.session.refresh(project)
            return project
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating project {project.kwork_id}: {e}")
            raise
    
    async def upsert_project(self, project_data: Dict[str, Any]) -> KworkProject:
        """Insert or update a project based on URL or Kwork ID."""
        project = None
        
        # Try to find existing project
        if 'url' in project_data and project_data['url']:
            project = await self.get_project_by_url(project_data['url'])
        
        if not project and 'kwork_id' in project_data and project_data['kwork_id']:
            project = await self.get_project(project_data['kwork_id'])
        
        if project:
            # Update existing project
            return await self.update_project(project, project_data)
        else:
            # Create new project
            return await self.create_project(project_data)
    
    async def create_scrape_session(self, max_pages: Optional[int] = None, 
                                  filters: Optional[Dict] = None) -> ScrapeSession:
        """Create a new scraping session."""
        session = ScrapeSession(
            start_time=datetime.utcnow(),
            status='running',
            max_pages=max_pages,
            filters=filters or {}
        )
        self.session.add(session)
        await self.session.commit()
        await self.session.refresh(session)
        return session
    
    async def update_scrape_session(self, session_id: int, **updates) -> ScrapeSession:
        """Update a scraping session."""
        result = await self.session.execute(
            select(ScrapeSession)
            .filter(ScrapeSession.id == session_id)
        )
        session = result.scalars().first()
        
        if not session:
            raise ValueError(f"Session {session_id} not found")
        
        for key, value in updates.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        if 'end_time' in updates and not session.end_time:
            session.end_time = datetime.utcnow()
        
        await self.session.commit()
        await self.session.refresh(session)
        return session
    
    async def get_active_projects_count(self) -> int:
        """Get count of active projects."""
        result = await self.session.execute(
            select(KworkProject)
            .filter(KworkProject.is_active == True)  # noqa: E712
        )
        return len(result.scalars().all())
    
    async def get_recent_projects(self, limit: int = 10) -> List[KworkProject]:
        """Get most recently updated projects."""
        result = await self.session.execute(
            select(KworkProject)
            .order_by(KworkProject.updated_at.desc())
            .limit(limit)
            .options(selectinload(KworkProject.snapshots))
        )
        return result.scalars().all()
