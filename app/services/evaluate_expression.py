import math
import logging
from typing import Dict, Any, Union

logger = logging.getLogger(__name__)

class EvaluateExpressionService:
    def evaluate(self, expression: str, variables: Dict[str, Any]) -> Union[int, float]:
        """
        Safely evaluate a mathematical expression with given variables.
        
        Args:
            expression: The string expression to evaluate
            variables: Dictionary of variable names and their values
            
        Returns:
            The numeric result of the evaluation
            
        Raises:
            ValueError: If the expression is invalid or contains forbidden operations
        """
        logger.info(f"Starting expression evaluation")
        logger.info(f"Expression: {expression}")
        logger.info(f"Variables provided: {variables}")
        
        # Define allowed functions and constants
        allowed_names = {
            "abs": abs,
            "round": round,
            "min": min,
            "max": max,
            "sum": sum,
            "pow": pow,
            # Math constants
            "pi": math.pi,
            "e": math.e,
            # Math functions
            "sqrt": math.sqrt,
            "sin": math.sin,
            "cos": math.cos,
            "tan": math.tan,
            "log": math.log,
            "log10": math.log10,
            "exp": math.exp,
            "ceil": math.ceil,
            "floor": math.floor,
        }
        
        # Add uppercase aliases for common functions (e.g., MAX, MIN, SQRT)
        # to make the service more user-friendly for formula-style expressions.
        aliases = {k.upper(): v for k, v in allowed_names.items()}
        
        # Merge with variables provided by user
        # Filter out variables that might conflict with built-ins if necessary,
        # but here we allow overriding for flexibility.
        safe_dict = {**allowed_names, **aliases, **variables}
        
        logger.debug(f"Available functions: {list(allowed_names.keys())}")
        logger.debug(f"Available uppercase aliases: {list(aliases.keys())}")
        logger.debug(f"Total symbols in evaluation context: {len(safe_dict)}")
        
        try:
            logger.debug(f"Evaluating expression with safe context...")
            # Use eval with restricted globals and no locals
            # Setting __builtins__ to empty dict for security
            result = eval(expression, {"__builtins__": {}}, safe_dict)
            
            logger.debug(f"Raw evaluation result: {result} (type: {type(result).__name__})")
            
            if not isinstance(result, (int, float)):
                # Handle cases where result is not a number
                if hasattr(result, "__float__"):
                    result = float(result)
                    logger.debug(f"Converted result to float: {result}")
                else:
                    logger.error(f"Result is not a number: {type(result).__name__} = {result}")
                    raise ValueError(f"Result is not a number: {type(result).__name__}")
            
            logger.info(f"Expression evaluation successful. Result: {result}")
            return result
        except SyntaxError as e:
            logger.error(f"Syntax error in expression '{expression}' with variables {variables}: {e}")
            logger.error(f"Syntax error details: {type(e).__name__} - {str(e)}")
            raise ValueError(f"Syntax error in expression: {str(e)}")
        except NameError as e:
            logger.error(f"Undefined variable/function in expression '{expression}' with variables {variables}: {e}")
            logger.error(f"Available variables: {list(variables.keys())}")
            logger.error(f"NameError details: {type(e).__name__} - {str(e)}")
            raise ValueError(f"Undefined variable or function: {str(e)}")
        except ZeroDivisionError:
            logger.error(f"Division by zero in expression '{expression}' with variables {variables}")
            raise ValueError("Division by zero")
        except Exception as e:
            logger.error(f"Unexpected error evaluating expression '{expression}' with variables {variables}")
            logger.error(f"Error type: {type(e).__name__}, Error message: {str(e)}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise ValueError(f"Evaluation error: {str(e)}")

evaluate_expression = EvaluateExpressionService()

