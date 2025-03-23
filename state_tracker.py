from typing import Dict, Any, Optional, List
import json
import time

class StateTracker:
    """
    Отслеживает состояние между вызовами функций и сохраняет историю взаимодействия.
    """
    
    def __init__(self, session_id: str = None, ttl: int = 3600):
        """
        Инициализирует трекер состояния.
        
        Args:
            session_id: Уникальный идентификатор сессии
            ttl: Время жизни состояния в секундах (по умолчанию 1 час)
        """
        self.session_id = session_id or f"session_{int(time.time())}"
        self.ttl = ttl
        self.created_at = time.time()
        self.last_updated = self.created_at
        self._state: Dict[str, Any] = {}
        self._history: List[Dict[str, Any]] = []
    
    def update(self, key: str, value: Any) -> None:
        """Обновляет значение в состоянии."""
        self._state[key] = value
        self.last_updated = time.time()
    
    def get(self, key: str, default: Any = None) -> Any:
        """Получает значение из состояния."""
        return self._state.get(key, default)
    
    def merge(self, data: Dict[str, Any]) -> None:
        """Объединяет словарь с текущим состоянием."""
        self._state.update(data)
        self.last_updated = time.time()
    
    def clear(self) -> None:
        """Очищает состояние."""
        self._state = {}
        self.last_updated = time.time()
    
    def add_to_history(self, entry_type: str, data: Dict[str, Any]) -> None:
        """Добавляет запись в историю."""
        self._history.append({
            "type": entry_type,
            "timestamp": time.time(),
            "data": data
        })
    
    def get_history(self, entry_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получает историю взаимодействия, опционально фильтруя по типу."""
        if entry_type is None:
            return self._history
        
        return [entry for entry in self._history if entry["type"] == entry_type]
    
    def is_expired(self) -> bool:
        """Проверяет, истекло ли время жизни состояния."""
        return (time.time() - self.last_updated) > self.ttl
    
    def to_json(self) -> str:
        """Сериализует состояние в JSON."""
        return json.dumps({
            "session_id": self.session_id,
            "created_at": self.created_at,
            "last_updated": self.last_updated,
            "state": self._state,
            "history": self._history
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'StateTracker':
        """Создает экземпляр из JSON-строки."""
        data = json.loads(json_str)
        tracker = cls(session_id=data["session_id"])
        tracker.created_at = data["created_at"]
        tracker.last_updated = data["last_updated"]
        tracker._state = data["state"]
        tracker._history = data["history"]
        return tracker
