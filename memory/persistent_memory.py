"""Persistent memory storage for CLIBOT sessions."""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional

class PersistentMemory:
    """Persistent memory that survives across sessions."""
    
    def __init__(self, storage_path: str = '~/.llmah/memory.json'):
        self.storage_path = Path(storage_path).expanduser()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()
    
    def _load(self) -> Dict[str, Any]:
        """Load memory from disk."""
        if not self.storage_path.exists():
            return {
                'version': '1.0',
                'created': datetime.now().isoformat(),
                'last_modified': datetime.now().isoformat(),
                'preferences': {},
                'history': [],
                'knowledge': {},
                'tags': []
            }
        
        try:
            with open(self.storage_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return self._get_default()
    
    def _get_default(self) -> Dict[str, Any]:
        """Get default memory structure."""
        return {
            'version': '1.0',
            'created': datetime.now().isoformat(),
            'last_modified': datetime.now().isoformat(),
            'preferences': {},
            'history': [],
            'knowledge': {},
            'tags': []
        }
    
    def _save(self):
        """Save memory to disk."""
        self._data['last_modified'] = datetime.now().isoformat()
        
        fd = os.open(self.storage_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except:
            os.close(fd)
            raise
    
    def add_history_entry(self, request: str, response: Dict[str, Any], success: bool = True):
        """Add a history entry."""
        entry = {
            'timestamp': datetime.now().isoformat(),
            'request': request[:500],
            'success': success,
            'response_summary': str(response)[:500]
        }
        self._data['history'].append(entry)
        
        if len(self._data['history']) > 1000:
            self._data['history'] = self._data['history'][-1000:]
        
        self._save()
    
    def get_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent history entries."""
        return self._data['history'][-limit:]
    
    def search_history(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search history by query."""
        query_lower = query.lower()
        results = [
            entry for entry in self._data['history']
            if query_lower in entry['request'].lower()
        ]
        return results[-limit:]
    
    def set_preference(self, key: str, value: Any):
        """Set a user preference."""
        self._data['preferences'][key] = value
        self._save()
    
    def get_preference(self, key: str, default: Any = None) -> Any:
        """Get a user preference."""
        return self._data['preferences'].get(key, default)
    
    def add_knowledge(self, key: str, value: Any, category: str = 'general'):
        """Add knowledge to memory."""
        if category not in self._data['knowledge']:
            self._data['knowledge'][category] = {}
        self._data['knowledge'][category][key] = {
            'value': value,
            'added': datetime.now().isoformat()
        }
        self._save()
    
    def get_knowledge(self, key: str, category: str = 'general') -> Optional[Any]:
        """Get knowledge from memory."""
        if category in self._data['knowledge'] and key in self._data['knowledge'][category]:
            return self._data['knowledge'][category][key]['value']
        return None
    
    def get_category_knowledge(self, category: str) -> Dict[str, Any]:
        """Get all knowledge in a category."""
        return self._data['knowledge'].get(category, {})
    
    def add_tag(self, tag: str):
        """Add a tag."""
        if tag not in self._data['tags']:
            self._data['tags'].append(tag)
            self._save()
    
    def get_tags(self) -> List[str]:
        """Get all tags."""
        return self._data['tags']
    
    def clear_history(self):
        """Clear all history."""
        self._data['history'] = []
        self._save()
    
    def clear_knowledge(self, category: Optional[str] = None):
        """Clear knowledge, optionally by category."""
        if category:
            if category in self._data['knowledge']:
                del self._data['knowledge'][category]
        else:
            self._data['knowledge'] = {}
        self._save()
    
    def export(self, export_path: str):
        """Export memory to a file."""
        export_path = Path(export_path).expanduser()
        export_path.parent.mkdir(parents=True, exist_ok=True)
        
        fd = os.open(export_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        try:
            with os.fdopen(fd, 'w') as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except:
            os.close(fd)
            raise
    
    def import_memory(self, import_path: str, merge: bool = True):
        """Import memory from a file."""
        import_path = Path(import_path).expanduser()
        if not import_path.exists():
            raise FileNotFoundError(f'Import file not found: {import_path}')
        
        with open(import_path, 'r', encoding='utf-8') as f:
            imported_data = json.load(f)
        
        if merge:
            self._data['history'].extend(imported_data.get('history', []))
            self._data['preferences'].update(imported_data.get('preferences', {}))
            for category, knowledge in imported_data.get('knowledge', {}).items():
                if category not in self._data['knowledge']:
                    self._data['knowledge'][category] = {}
                self._data['knowledge'][category].update(knowledge)
            self._data['tags'] = list(set(self._data['tags'] + imported_data.get('tags', [])))
        else:
            self._data = imported_data
        
        self._save()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics."""
        return {
            'version': self._data['version'],
            'created': self._data['created'],
            'last_modified': self._data['last_modified'],
            'history_count': len(self._data['history']),
            'preferences_count': len(self._data['preferences']),
            'knowledge_categories': len(self._data['knowledge']),
            'knowledge_items': sum(len(v) for v in self._data['knowledge'].values()),
            'tags_count': len(self._data['tags'])
        }
