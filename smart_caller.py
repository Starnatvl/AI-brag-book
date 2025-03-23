import inspect
import json
from typing import Dict, List, Any, Callable, Optional, Union
from pydantic import BaseModel, create_model, ValidationError
import logging
import time
from functools import lru_cache

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("smart_caller")

class FunctionSchema(BaseModel):
    """Схема функции для регистрации."""
    name: str
    description: str
    parameters: Dict[str, Any]
    required_params: List[str] = []
    context_requirements: List[str] = []
    priority: int = 5  # Приоритет вызова (1-10)
    cooldown: float = 0.0  # Время между повторными вызовами

class FunctionRegistry:
    """Реестр функций для управления доступными функциями."""
    
    def __init__(self):
        self._functions: Dict[str, Callable] = {}
        self._schemas: Dict[str, FunctionSchema] = {}
        self._last_called: Dict[str, float] = {}
        self._call_count: Dict[str, int] = {}
    
    def register(self, 
                func: Optional[Callable] = None, 
                *, 
                name: Optional[str] = None,
                description: Optional[str] = None,
                priority: int = 5,
                cooldown: float = 0.0):
        """Декоратор для регистрации функции."""
        
        def decorator(func):
            func_name = name or func.__name__
            func_doc = description or func.__doc__ or "No description provided"
            
            # Получаем сигнатуру функции для автоматического построения схемы
            sig = inspect.signature(func)
            params = {}
            required = []
            
            for param_name, param in sig.parameters.items():
                if param.annotation == inspect.Parameter.empty:
                    param_type = {"type": "string"}
                else:
                    param_type = self._get_type_schema(param.annotation)
                
                has_default = param.default != inspect.Parameter.empty
                if not has_default:
                    required.append(param_name)
                
                params[param_name] = {
                    **param_type,
                    "description": f"Parameter {param_name}" 
                }
            
            schema = FunctionSchema(
                name=func_name,
                description=func_doc,
                parameters={"type": "object", "properties": params},
                required_params=required,
                priority=priority,
                cooldown=cooldown
            )
            
            self._functions[func_name] = func
            self._schemas[func_name] = schema
            self._call_count[func_name] = 0
            logger.info(f"Registered function: {func_name}")
            
            return func
        
        if func is None:
            return decorator
        return decorator(func)
    
    def _get_type_schema(self, annotation):
        """Преобразует аннотацию типа Python в JSON-схему."""
        if annotation == str:
            return {"type": "string"}
        elif annotation == int:
            return {"type": "integer"}
        elif annotation == float:
            return {"type": "number"}
        elif annotation == bool:
            return {"type": "boolean"}
        elif annotation == List[str]:
            return {"type": "array", "items": {"type": "string"}}
        elif annotation == List[int]:
            return {"type": "array", "items": {"type": "integer"}}
        elif annotation == Dict[str, Any]:
            return {"type": "object"}
        else:
            return {"type": "string"}
    
    def get_function(self, name: str) -> Optional[Callable]:
        """Получить функцию по имени."""
        return self._functions.get(name)
    
    def get_schema(self, name: str) -> Optional[FunctionSchema]:
        """Получить схему функции по имени."""
        return self._schemas.get(name)
    
    def get_all_schemas(self) -> List[FunctionSchema]:
        """Получить все схемы функций."""
        return list(self._schemas.values())
    
    def filter_functions(self, context: Dict[str, Any]) -> List[str]:
        """Фильтрует функции на основе контекста и приоритета."""
        available_functions = []
        
        for name, schema in self._schemas.items():
            # Проверка требований контекста
            context_met = all(req in context for req in schema.context_requirements)
            
            # Проверка времени ожидания
            current_time = time.time()
            last_call_time = self._last_called.get(name, 0)
            cooldown_passed = (current_time - last_call_time) >= schema.cooldown
            
            if context_met and cooldown_passed:
                available_functions.append(name)
        
        # Сортировка по приоритету (по убыванию)
        return sorted(available_functions, 
                     key=lambda f: self._schemas[f].priority, 
                     reverse=True)
    
    def log_call(self, name: str):
        """Записать вызов функции."""
        self._last_called[name] = time.time()
        self._call_count[name] = self._call_count.get(name, 0) + 1


class ParameterBuilder:
    """Создает и валидирует параметры для вызова функций."""
    
    def __init__(self, registry: FunctionRegistry):
        self.registry = registry
    
    def build_parameters(self, function_name: str, params_data: Dict[str, Any]) -> Dict[str, Any]:
        """Строит и валидирует параметры для функции."""
        schema = self.registry.get_schema(function_name)
        if not schema:
            raise ValueError(f"Unknown function: {function_name}")
        
        # Проверяем обязательные параметры
        for req_param in schema.required_params:
            if req_param not in params_data:
                raise ValueError(f"Missing required parameter: {req_param}")
        
        # Создаем Pydantic-модель для валидации
        properties = schema.parameters.get("properties", {})
        field_definitions = {}
        
        for name, prop in properties.items():
            field_type = self._json_type_to_python(prop.get("type", "string"))
            is_required = name in schema.required_params
            
            if is_required:
                field_definitions[name] = (field_type, ...)
            else:
                field_definitions[name] = (field_type, None)
        
        # Создаем модель динамически
        model = create_model(f"{function_name}Params", **field_definitions)
        
        try:
            # Валидируем параметры
            validated = model(**params_data)
            return validated.model_dump()
        except ValidationError as e:
            logger.error(f"Parameter validation error: {e}")
            raise ValueError(f"Invalid parameters: {e}")
    
    def _json_type_to_python(self, json_type: str):
        """Преобразует JSON-тип в тип Python."""
        type_map = {
            "string": str,
            "integer": int,
            "number": float,
            "boolean": bool,
            "array": list,
            "object": dict
        }
        return type_map.get(json_type, str)


class SmartCaller:
    """Основной класс фреймворка для умного вызова функций."""
    
    def __init__(self):
        self.registry = FunctionRegistry()
        self.param_builder = ParameterBuilder(self.registry)
        self._results_cache = {}
    
    def register_function(self, *args, **kwargs):
        """Регистрирует функцию в реестре."""
        return self.registry.register(*args, **kwargs)
    
    @lru_cache(maxsize=128)
    def get_function_descriptions(self) -> List[Dict[str, Any]]:
        """Получает описания функций для LLM."""
        schemas = self.registry.get_all_schemas()
        return [
            {
                "type": "function",
                "function": {
                    "name": schema.name,
                    "description": schema.description,
                    "parameters": schema.parameters
                }
            }
            for schema in schemas
        ]
    
    def prepare_for_llm(self, context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Подготавливает описания функций для LLM с учетом контекста."""
        if context is None:
            context = {}
            
        available_functions = self.registry.filter_functions(context)
        all_descriptions = self.get_function_descriptions()
        
        # Фильтруем только доступные функции
        return [
            desc for desc in all_descriptions
            if desc["function"]["name"] in available_functions
        ]
    
    def execute_function_call(self, 
                            call_data: Dict[str, Any], 
                            context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Выполняет вызов функции на основе данных от LLM."""
        if context is None:
            context = {}
            
        function_name = call_data.get("name")
        function_args = call_data.get("arguments", "{}")
        
        if isinstance(function_args, str):
            try:
                function_args = json.loads(function_args)
            except json.JSONDecodeError:
                function_args = {}
        
        # Получаем функцию
        func = self.registry.get_function(function_name)
        if not func:
            return {
                "error": f"Unknown function: {function_name}",
                "success": False
            }
        
        # Проверяем, доступна ли функция в текущем контексте
        available_functions = self.registry.filter_functions(context)
        if function_name not in available_functions:
            return {
                "error": f"Function {function_name} is not available in current context",
                "success": False
            }
        
        try:
            # Строим и валидируем параметры
            validated_params = self.param_builder.build_parameters(
                function_name, function_args)
            
            # Записываем вызов
            self.registry.log_call(function_name)
            
            # Выполняем функцию
            start_time = time.time()
            result = func(**validated_params)
            execution_time = time.time() - start_time
            
            # Формируем и кэшируем результат
            response = {
                "result": result,
                "execution_time": execution_time,
                "success": True
            }
            
            cache_key = f"{function_name}:{json.dumps(validated_params, sort_keys=True)}"
            self._results_cache[cache_key] = response
            
            return response
            
        except Exception as e:
            logger.error(f"Error executing function {function_name}: {e}")
            return {
                "error": str(e),
                "success": False
            }
    
    def get_cached_result(self, function_name: str, params: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Получает кэшированный результат вызова функции."""
        cache_key = f"{function_name}:{json.dumps(params, sort_keys=True)}"
        return self._results_cache.get(cache_key)

# Создаем глобальный экземпляр SmartCaller
smart_caller = SmartCaller()
