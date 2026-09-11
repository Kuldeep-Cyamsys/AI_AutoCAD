import ast
import math
import operator


def evaluate(expression: str) -> float:
    operations = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
    tree = ast.parse(expression, mode="eval")
    if len(list(ast.walk(tree))) > 80:
        raise ValueError("Calculation is too complex")

    def visit(node):
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            value = float(node.value)
        elif isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            value = visit(node.operand) * (-1 if isinstance(node.op, ast.USub) else 1)
        elif isinstance(node, ast.BinOp) and type(node.op) in operations:
            value = operations[type(node.op)](visit(node.left), visit(node.right))
        else:
            raise ValueError("Use only numbers, parentheses, +, -, *, and / in calculations")
        if not math.isfinite(value) or abs(value) > 1e12:
            raise ValueError("Calculation is outside the supported numeric range")
        return value

    try:
        return visit(tree.body)
    except (ZeroDivisionError, OverflowError) as error:
        raise ValueError("Invalid arithmetic") from error


def verify_calculations(response):
    for calculation in response.calculations:
        try:
            actual = evaluate(calculation.expression)
        except SyntaxError as error:
            raise ValueError("Invalid calculation expression") from error
        if not math.isclose(actual, calculation.result, rel_tol=1e-6, abs_tol=1e-6):
            raise ValueError(f"{calculation.label}: {calculation.expression} equals {actual}, not {calculation.result}. Correct the calculation and any affected dimensions.")
    return response
