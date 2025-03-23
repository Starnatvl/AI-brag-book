import json
from typing import Dict, List, Any, Optional, Union
import openai
from tenacity import retry, stop_after_attempt, wait_exponential
from .smart_caller import smart_caller, logger

class OpenAIAdapter:
    """Адаптер для работы с OpenAI API."""
    
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        self.client = openai.OpenAI(api_key=api_key)
        self.model = model
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def chat_completion_with_functions(self, 
                                      messages: List[Dict[str, str]], context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Выполняет запрос к OpenAI API с поддержкой function calling.
        
        Args:
            messages: Список сообщений в формате OpenAI
            context: Контекст для фильтрации доступных функций
        
        Returns:
            Результат вызова API
        """
        if context is None:
            context = {}
        
        # Получаем описания доступных функций
        function_descriptions = smart_caller.prepare_for_llm(context)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=function_descriptions,
                tool_choice="auto"
            )
            
            return self._process_response(response, context)
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return {
                "content": f"Error: {str(e)}",
                "function_call": None
            }
    
    def _process_response(self, response, context: Dict[str, Any]) -> Dict[str, Any]:
        """Обрабатывает ответ от OpenAI API."""
        message = response.choices[0].message
        
        # Проверяем, содержит ли ответ вызов функции
        function_call = None
        if message.tool_calls:
            tool_call = message.tool_calls[0]
            try:
                function_call = {
                    "name": tool_call.function.name,
                    "arguments": tool_call.function.arguments
                }
                
                # Выполняем вызов функции
                result = smart_caller.execute_function_call(function_call, context)
                
                # Если результат успешный, обогащаем контент
                if result.get("success", False):
                    return {
                        "content": message.content or "",
                        "function_call": function_call,
                        "function_result": result.get("result")
                    }
                else:
                    # Если ошибка, возвращаем сообщение об ошибке
                    return {
                        "content": message.content or "",
                        "function_call": function_call,
                        "error": result.get("error")
                    }
                    
            except Exception as e:
                logger.error(f"Error processing function call: {e}")
                return {
                    "content": message.content or "",
                    "function_call": function_call,
                    "error": str(e)
                }
        
        # Если нет вызова функции, просто возвращаем текстовый ответ
        return {
            "content": message.content or "",
            "function_call": None
        }


class YandexGPTAdapter:
    """Адаптер для работы с YandexGPT API."""
    
    def __init__(self, api_key: str, folder_id: str, model: str = "yandexgpt"):
        self.api_key = api_key
        self.folder_id = folder_id
        self.model = model
        # Здесь будет код для инициализации клиента YandexGPT
        
    def chat_completion_with_functions(self, 
                                      messages: List[Dict[str, str]], 
                                      context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Выполняет запрос к YandexGPT API с поддержкой function calling.
        
        Args:
            messages: Список сообщений
            context: Контекст для фильтрации доступных функций
        
        Returns:
            Результат вызова API
        """
        # Реализация для YandexGPT аналогична OpenAI, 
        # но с учетом специфики API Яндекса
        # ...
        
        # Заглушка для примера
        return {
            "content": "Ответ от YandexGPT",
            "function_call": None
        }
