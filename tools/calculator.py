import sympy
from config import setup_logger

logger = setup_logger("Tool:Calc")

def calculate(expression: str) -> str:
    """
    Evaluates complex mathematical and symbolic expressions using SymPy.
    Supports calculus (diff, integrate), algebra (solve, simplify), and standard arithmetic.
    
    Args:
        expression: A string to evaluate (e.g., 'diff(sin(x), x)', 'solve(x**2 - 4, x)', '2**100').
    """
    logger.info(f"  [Tool] Calculating with SymPy: {expression}...")
    try:
        # SymPy's sympify converts a string into a symbolic expression
        # and we use evalf() for numerical result if applicable, or just str() for symbolic result
        res = sympy.sympify(expression)
        
        # If it's a symbolic expression with no variables, try to get a numeric value
        if hasattr(res, 'evalf') and not res.free_symbols:
            return str(res.evalf())
            
        return str(res)
    except Exception as e:
        logger.error(f"Calc Error: {e}")
        return f"SymPy Error: {str(e)}"
