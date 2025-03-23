from typing import Dict, Any, List, Optional

class ResponseMixer:
    """
    Объединяет результаты вызовов функций с ответом модели.
    """
    
    def __init__(self):
        self.formatting_templates = {
            "default": "{content}\n\n{function_result}",
            "table": "{content}\n\nРезультаты:\n{table_result}",
            "error": "{content}\n\nПроизошла ошибка: {error_message}"
        }
    
    def register_template(self, template_name: str, template: str) -> None:
        """Регистрирует новый шаблон форматирования."""
        self.formatting_templates[template_name] = template
    
    def mix(self, 
           model_response: Dict[str, Any], 
           function_result: Optional[Dict[str, Any]] = None,
           template: str = "default") -> str:
        """
        Объединяет ответ модели и результат вызова функции.
        
        Args:
            model_response: Ответ от LLM-модели
            function_result: Результат вызова функции (опционально)
            template: Имя шаблона для форматирования
        
        Returns:
            Отформатированный ответ
        """
        content = model_response.get("content", "")
        
        if function_result is None:
            return content
        
        if "error" in function_result:
            return self.formatting_templates["error"].format(
                content=content,
                error_message=function_result["error"]
            )
        
        template_str = self.formatting_templates.get(template, self.formatting_templates["default"])
        
        # Здесь можно добавить специальную обработку для различных типов результатов
        if template == "table" and isinstance(function_result.get("result"), list):
            table_result = self._format_as_table(function_result["result"])
            return template_str.format(
                content=content,
                table_result=table_result
            )
        
        return template_str.format(
            content=content,
            function_result=function_result.get("result", "")
        )
    
    def _format_as_table(self, data: List[Dict[str, Any]]) -> str:
        """Форматирует список словарей как текстовую таблицу."""
        if not data:
            return "Нет данных"
        
        # Получаем заголовки из первого элемента
        headers = list(data[0].keys())
        
        # Вычисляем ширину столбцов
        col_widths = [len(h) for h in headers]
        for row in data:
            for i, key in enumerate(headers):
                col_widths[i] = max(col_widths[i], len(str(row.get(key, ""))))
        
        # Строим заголовок таблицы
        header_row = " | ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
        separator = "-+-".join("-" * width for width in col_widths)
        
        # Строим строки данных
        data_rows = []
        for row in data:
            data_rows.append(" | ".join(
                str(row.get(key, "")).ljust(col_widths[i]) 
                for i, key in enumerate(headers)
            ))
        
        return "\n".join([header_row, separator] + data_rows)
