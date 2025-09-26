# -*- coding: utf-8 -*-
import sympy as sp
from sympy import (
    symbols, diff, integrate, solve, sympify, simplify, limit, Symbol, Matrix,
    factor, degree, sqrt, cancel, trigsimp, expand_log, logcombine, oo
)
import re

# ✅ Lazy import to avoid circular dependency and to use your say_show helper
def get_utils():
    # _speak_multilang, logger, gui_callback are still loaded by say_show internally if needed
    from utils import logger  # keep logger available here
    from say_show import say_show  
    return logger, say_show


def handle_symbolic_math(command: str):
    logger, say_show = get_utils()

    try:
        lowered = command.lower()

        # ✅ Extract user-requested variable via "wrt" if present (from original text)
        override_match = re.search(r"\bwrt\s+([a-zA-Z\u03B1-\u03C9]+)\b", command)

        # Parse the main expression once (from the original, not lowered)
        sym_expr = extract_expression(command)

        # Variable selection
        free_syms = list(sym_expr.free_symbols)
        if override_match:
            var = Symbol(override_match.group(1))
        else:
            var = free_syms[0] if free_syms else symbols('x')  # Fallback to 'x'

        # Initialize (popup content is English-only)
        result = None
        solution_en = ""

        # 🎯 Differentiation
        if ("differentiate" in lowered) or ("derivative" in lowered):
            try:
                sym_expr = extract_expression(command)
                result = diff(sym_expr, var)

                stepwise = f"📘 Steps:\n1. Expression: {sym_expr}\n2. Differentiate term-by-term:\n"
                try:
                    if sym_expr.is_Add:
                        for term in sym_expr.args:
                            d_term = diff(term, var)
                            stepwise += f"   d/d{var}({term}) = {d_term}\n"
                    elif sym_expr.is_Mul or sym_expr.is_Pow or sym_expr.is_Function:
                        d_term = diff(sym_expr, var)
                        stepwise += "   Applied chain/product rule where necessary\n"
                        stepwise += f"   d/d{var}({sym_expr}) = {d_term}\n"
                    else:
                        d_term = diff(sym_expr, var)
                        stepwise += f"   d/d{var}({sym_expr}) = {d_term}\n"
                except Exception as e:
                    stepwise += f"   Couldn't generate term-wise breakdown: {e}\n"

                stepwise += f"3. Final result: {result}"

                solution_en = (
                    f"Step 1: You asked to differentiate the expression: {sym_expr}\n"
                    f"Step 2: We calculated the derivative with respect to {var}\n"
                    f"Result: {result}"
                )

                say_show(
                    speak_args=(f"The answer is: {result}. You'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"उत्तर है: {result}। समाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"La réponse est : {result}. Vous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"La respuesta es: {result}. Encontrarás la solución en la ventana emergente de solución.",
                        de=f"Die Antwort ist: {result}. Die Lösung findest du im Lösungspopup.",
                        log_command="Differentiation",
                    ),
                    gui_kwargs=dict(result=result, solution_en=solution_en, stepwise=stepwise)
                )

            except Exception as e:
                say_show(
                    speak_args=("Unable to differentiate. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="अवकलन नहीं किया जा सका। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Échec de la dérivation. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="No se pudo derivar. Encontrarás la explicación en la ventana emergente de solución.",
                        de="Nicht ableitbar. Die Erläuterung findest du im Lösungspopup.",
                        log_command=f"Differentiation error: {str(e)}",
                    ),
                    gui_kwargs=dict(
                        result="❌ Error",
                        solution_en="Differentiation failed due to an invalid expression or unsupported symbolic form.",
                        stepwise=f"⚠️ Error: {str(e)}"
                    )
                )

        # ∫ Integration (definite or indefinite)
        elif ("integrate" in lowered) or ("integral" in lowered):
            try:
                expr_bounds, a, b, parsed_var = extract_bounds(command)
                sym_expr = expr_bounds
                if parsed_var is not None:
                    var = parsed_var  # respect explicit var in bounds phrase

                if a is not None and b is not None:
                    # ✅ Definite Integral
                    result = integrate(sym_expr, (var, a, b))
                    antiderivative = integrate(sym_expr, var)
                    F_upper = antiderivative.subs(var, b)
                    F_lower = antiderivative.subs(var, a)
                    difference = F_upper - F_lower

                    stepwise = (
                        f"📘 Steps:\n"
                        f"1. Expression: {sym_expr}\n"
                        f"2. Definite integral:\n"
                        f"   ∫₍{a}₎⁽{b}⁾ {sym_expr} d{var} = [{antiderivative}]₍{a}₎⁽{b}⁾ = ({F_upper}) - ({F_lower}) = {difference}\n"
                        f"3. Final result: {result}"
                    )

                    solution_en = (
                        f"Step 1: You asked to integrate the expression: {sym_expr}\n"
                        f"Step 2: We integrated it from {a} to {b} with respect to {var}\n"
                        f"Result: {result}"
                    )

                else:
                    # ✅ Indefinite Integral
                    result = integrate(sym_expr, var)
                    stepwise = f"📘 Steps:\n1. Expression: {sym_expr}\n2. Indefinite integral term-by-term:\n"

                    try:
                        if sym_expr.is_Add:
                            for term in sym_expr.args:
                                i_term = integrate(term, var)
                                stepwise += f"   ∫ {term} d{var} = {i_term}\n"
                        else:
                            i_term = integrate(sym_expr, var)
                            stepwise += f"   ∫ {sym_expr} d{var} = {i_term}\n"
                    except Exception as e:
                        stepwise += f"   Couldn't break into terms: {e}\n"

                    stepwise += f"3. Final result: {result}"

                    solution_en = (
                        f"Step 1: You asked to integrate the expression: {sym_expr}\n"
                        f"Step 2: We performed an indefinite integral with respect to {var}\n"
                        f"Result: {result}"
                    )

                say_show(
                    speak_args=(f"The answer is: {result}. You'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"उत्तर है: {result}। समाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"La réponse est : {result}. Vous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"La respuesta es: {result}. Encontrarás la solución en la ventana emergente de solución.",
                        de=f"Die Antwort ist: {result}. Die Lösung findest du im Lösungspopup.",
                        log_command="Integration",
                    ),
                    gui_kwargs=dict(result=result, solution_en=solution_en, stepwise=stepwise)
                )

            except Exception as e:
                say_show(
                    speak_args=("Unable to integrate. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="इंटीग्रेट नहीं किया जा सका। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Échec de l'intégration. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="No se pudo integrar. Encontrarás la explicación en la ventana emergente de solución.",
                        de="Nicht integrierbar. Die Erläuterung findest du im Lösungspopup.",
                        log_command=f"Integration error: {str(e)}",
                    ),
                    gui_kwargs=dict(
                        result="❌ Error",
                        solution_en="Integration failed due to an invalid expression or unsupported symbolic form.",
                        stepwise=f"⚠️ Error: {str(e)}"
                    )
                )

        # 🧮 Simplification
        elif "simplify" in lowered:
            try:
                sym_expr = extract_expression(command)

                simplified = simplify(sym_expr)

                steps = [f"1. Original expression:\n   {sym_expr}"]

                # 2️⃣ Trigonometric simplification
                trig_attempt = trigsimp(sym_expr)
                if trig_attempt != sym_expr:
                    steps.append("2. Applying trigonometric identities:")
                    steps.append(f"   → {trig_attempt}")
                else:
                    steps.append("2. No trigonometric identity simplification applied.")

                # 3️⃣ Logarithmic simplification
                log_expanded = expand_log(sym_expr, force=True)
                log_combined = logcombine(sym_expr, force=True)
                if log_combined != sym_expr:
                    steps.append("3. Combining logarithmic terms:")
                    steps.append(f"   → {log_combined}")
                elif log_expanded != sym_expr:
                    steps.append("3. Expanding logarithmic terms:")
                    steps.append(f"   → {log_expanded}")
                else:
                    steps.append("3. No logarithmic simplification applied.")

                # 4️⃣ Factorization
                factored = factor(sym_expr)
                if factored != sym_expr:
                    steps.append("4. Factoring the expression:")
                    steps.append(f"   → {factored}")
                else:
                    steps.append("4. No factoring applied.")

                # 5️⃣ Cancelling common terms (rational expressions)
                canceled = cancel(sym_expr)
                if canceled != sym_expr and canceled != factored:
                    steps.append("5. Cancelling common terms:")
                    steps.append(f"   → {canceled}")
                else:
                    steps.append("5. No common term cancellation needed.")

                # 6️⃣ Final result
                steps.append(f"6. ✅ Final simplified result:\n   {simplified}")
                stepwise = "📘 Steps:\n" + "\n".join(steps)

                solution_en = (
                    f"Step 1: You asked to simplify the expression: {sym_expr}\n"
                    f"Step 2: We applied identities and simplification rules\n"
                    f"Result: {simplified}"
                )

                say_show(
                    speak_args=(f"The answer is {simplified}. You'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"उत्तर है {simplified}। समाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"La réponse est {simplified}. Vous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"La respuesta es {simplified}. Encontrarás la solución en la ventana emergente de solución.",
                        de=f"Die Antwort ist {simplified}. Die Lösung findest du im Lösungspopup.",
                        log_command="Simplify",
                    ),
                    gui_kwargs=dict(result=str(simplified), solution_en=solution_en, stepwise=stepwise)
                )

            except Exception as e:
                try:
                    logger.error(f"[❌ SIMPLIFY FAILED] {e}")
                except Exception:
                    pass
                say_show(
                    speak_args=("I couldn't simplify the expression. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="मैं इस समीकरण को सरल नहीं कर सकी। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Je n'ai pas pu simplifier l'expression. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="No pude simplificar la expresión. Encontrarás la solución en la ventana emergente de solución.",
                        de="Ich konnte den Ausdruck nicht vereinfachen. Die Erläuterung findest du im Lösungspopup.",
                        log_command="Simplification failed",
                    ),
                    gui_kwargs=dict(
                        result="❌ Error",
                        solution_en="An error occurred while simplifying. Make sure the expression is valid and uses correct syntax.",
                        stepwise="⚠️ Error: Could not simplify the input. Ensure the expression is valid and uses recognizable mathematical format."
                    )
                )

        # 🚦 Limit
        elif ("limit" in lowered) and ("approaches" in lowered):
            try:
                sym_expr, var, point = extract_limit_info(command)
                result = limit(sym_expr, var, point)

                steps = [f"1. Original expression:\n   {sym_expr}"]

                substituted = sym_expr.subs(var, point)
                steps.append(f"2. Substituting {var} = {point}:")
                steps.append(f"   → {substituted}")

                indeterminate = substituted.has(sp.nan) or substituted == sp.zoo
                if indeterminate:
                    steps.append("3. The substitution gave an indeterminate form like 0/0 or ∞/∞.")
                else:
                    steps.append("3. The substitution gave a valid finite result.")

                trig_simplified = trigsimp(sym_expr)
                if trig_simplified != sym_expr:
                    steps.append("4. Applying trigonometric identities:")
                    steps.append(f"   → {trig_simplified}")
                else:
                    steps.append("4. No trigonometric identity simplification applied.")

                log_expanded = expand_log(sym_expr, force=True)
                log_combined = logcombine(sym_expr, force=True)
                if log_combined != sym_expr:
                    steps.append("5. Combining logarithmic terms:")
                    steps.append(f"   → {log_combined}")
                elif log_expanded != sym_expr:
                    steps.append("5. Expanding logarithmic terms:")
                    steps.append(f"   → {log_expanded}")
                else:
                    steps.append("5. No logarithmic simplification applied.")

                factored = factor(sym_expr)
                if factored != sym_expr:
                    steps.append("6. Applying algebraic factoring:")
                    steps.append(f"   → {factored}")
                    simplified_r = cancel(factored)
                    steps.append("7. Cancelling common terms (if any):")
                    steps.append(f"   → {simplified_r}")
                    steps.append(f"8. Substituting {var} = {point} again:")
                    steps.append(f"   → {simplified_r.subs(var, point)}")
                else:
                    steps.append("6. No factoring or cancellation applied.")

                steps.append(f"9. ✅ Final limit result:\n   {result}")
                stepwise = "📘 Steps:\n" + "\n".join(steps)

                solution_en = (
                    f"Step 1: You asked to evaluate the limit of: {sym_expr} as {var} → {point}\n"
                    f"Step 2: We applied substitutions and simplifications\n"
                    f"Result: {result}"
                )

                say_show(
                    speak_args=(f"The answer is {result}. You'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"उत्तर है {result}। समाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"La réponse est {result}. Vous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"La respuesta es {result}. Encontrarás la solución en la ventana emergente de solución.",
                        de=f"Die Antwort ist {result}. Die Lösung findest du im Lösungspopup.",
                        log_command="Limit",
                    ),
                    gui_kwargs=dict(result=result, solution_en=solution_en, stepwise=stepwise)
                )

            except Exception as e:
                say_show(
                    speak_args=("I couldn't evaluate the limit. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="मैं सीमांक मान की गणना नहीं कर पाई। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Je n'ai pas pu évaluer la limite. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="No pude evaluar el límite. Encontrarás la explicación en la ventana emergente de solución.",
                        de="Ich konnte den Grenzwert nicht berechnen. Die Erläuterung findest du im Lösungspopup.",
                        log_command="Limit failed",
                    ),
                    gui_kwargs=dict(
                        result="❌ Error",
                        solution_en="An error occurred while evaluating the limit. Make sure the expression is valid and uses only one variable.",
                        stepwise=f"⚠️ Error: Could not compute limit. Reason: {str(e)}"
                    )
                )

        # 🧩 Solve Equations
        elif ("solve" in lowered) or ("find x" in lowered):
            try:
                sym_expr = extract_expression(command)

                free_symbols = sym_expr.free_symbols
                if not free_symbols:
                    raise ValueError("No variable found to solve for.")
                var = sorted(free_symbols, key=str)[0]

                steps = [f"1. Original expression:\n   {sym_expr} = 0"]

                trig_simplified = trigsimp(sym_expr)
                if trig_simplified != sym_expr:
                    steps.append("2. Applied trigonometric identities:")
                    steps.append(f"   → {trig_simplified}")
                    sym_expr = trig_simplified
                else:
                    steps.append("2. No trigonometric simplification applied.")

                log_combined = logcombine(sym_expr, force=True)
                if log_combined != sym_expr:
                    steps.append("3. Combined logarithmic terms:")
                    steps.append(f"   → {log_combined}")
                    sym_expr = log_combined
                else:
                    log_expanded = expand_log(sym_expr, force=True)
                    if log_expanded != sym_expr:
                        steps.append("3. Expanded logarithmic terms:")
                        steps.append(f"   → {log_expanded}")
                        sym_expr = log_expanded
                    else:
                        steps.append("3. No logarithmic simplification applied.")

                result = solve(sym_expr, var)

                deg = degree(sym_expr, gen=var)
                a = sym_expr.coeff(var, 2)
                b = sym_expr.coeff(var, 1)
                c = sym_expr.coeff(var, 0)

                if deg == 2 and a != 0:
                    steps.append(f"4. This is a quadratic equation: a{var}² + b{var} + c = 0")
                    steps.append(f"   Identified: a = {a}, b = {b}, c = {c}")
                    steps.append("5. Using the quadratic formula:")
                    steps.append(f"   {var} = [-b ± √(b² - 4ac)] / 2a")

                    b_squared = b**2
                    four_ac = 4 * a * c
                    discriminant = b_squared - four_ac
                    sqrt_discriminant = sqrt(discriminant)
                    two_a = 2 * a

                    steps.append("6. Substitute values:")
                    steps.append(f"   {var} = [-({b}) ± √(({b})² - 4×{a}×{c})] / (2×{a})")
                    steps.append(f"   = [{-b} ± √({b_squared} - {four_ac})] / {two_a}")
                    steps.append(f"   = [{-b} ± √({discriminant})] / {two_a}")
                    steps.append(f"   = [{-b} ± {sqrt_discriminant}] / {two_a}")
                    steps.append(f"7. ✅ Final result: {result}")

                elif deg == 1:
                    steps.append(f"4. This is a linear equation of the form a{var} + b = 0")
                    steps.append(f"5. Solving directly gives: {var} = {result[0]}")
                    steps.append(f"6. ✅ Final result: {result}")

                elif deg == 3:
                    steps.append("4. This is a cubic equation. Attempting symbolic solving.")
                    steps.append(f"5. ✅ Final result: {result}")

                else:
                    steps.append("4. Solving symbolically using SymPy.")
                    steps.append(f"5. ✅ Final result: {result}")

                stepwise = "📘 Steps:\n" + "\n".join(steps)

                solution_en = (
                    f"Step 1: You asked to solve the equation: {sym_expr} = 0\n"
                    f"Step 2: We simplified using trigonometric/log rules (if applicable)\n"
                    f"Result: {result}"
                )

                say_show(
                    speak_args=(f"The answer is {result}. You'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"उत्तर है {result}। समाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"La réponse est {result}. Vous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"La respuesta es {result}. Encontrarás la solución en la ventana emergente de solución.",
                        de=f"Die Antwort ist {result}. Die Lösung findest du im Lösungspopup.",
                        log_command="Solve",
                    ),
                    gui_kwargs=dict(result=result, solution_en=solution_en, stepwise=stepwise)
                )

            except Exception as e:
                say_show(
                    speak_args=("I couldn't solve the equation. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="मैं समीकरण हल नहीं कर पाई। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Je n'ai pas pu résoudre l'équation. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="No pude resolver la ecuación. Encontrarás la explicación en la ventana emergente de solución.",
                        de="Ich konnte die Gleichung nicht lösen. Die Erläuterung findest du im Lösungspopup.",
                        log_command="Solve failed",
                    ),
                    gui_kwargs=dict(
                        result="❌ Error",
                        solution_en="An error occurred while solving the equation. Please make sure it's a valid symbolic expression like 'x^2 - 4 = 0'.",
                        stepwise="⚠️ Error: Could not solve the given equation. Ensure it is a valid expression in one variable."
                    )
                )

        # 🔁 Matrix Operations – Inverse of a Matrix
        elif ("inverse of matrix" in lowered) or ("matrix inverse" in lowered):
            try:
                matrix_data = extract_matrix(command)
                A = Matrix(matrix_data)

                rows, cols = A.shape
                if rows != cols:
                    raise ValueError("Matrix must be square to find its inverse.")

                determinant = A.det()
                if determinant == 0:
                    raise ValueError("Matrix is not invertible (determinant = 0).")

                cofactor = A.cofactor_matrix()
                adjugate = cofactor.transpose()
                inverse_matrix = A.inv()

                def fmt_cell(c): return str(trigsimp(logcombine(c, force=True)))
                def format_matrix(M):
                    return "\n".join([
                        "   | " + "  ".join(fmt_cell(c) for c in row) + " |"
                        for row in M.tolist()
                    ])

                det_steps = ""
                if A.shape == (2, 2):
                    a, b = A[0, 0], A[0, 1]
                    c, d = A[1, 0], A[1, 1]
                    det_raw = a * d - b * c
                    det_simplified = trigsimp(logcombine(det_raw, force=True))
                    det_steps = f"   det(A) = {a}×{d} − {b}×{c} = {a*d} − {b*c} = {det_simplified}\n"
                elif A.shape == (3, 3):
                    det_steps = "   Cofactor expansion along row 1:\n"
                    for j in range(3):
                        minor = A.minor_submatrix(0, j)
                        sign = (-1) ** (0 + j)
                        det_minor = minor.det()
                        term = f"{sign}×{A[0, j]}×det({minor.tolist()}) = {sign}×{A[0,j]}×{trigsimp(logcombine(det_minor, force=True))}"
                        det_steps += f"   → {term}\n"
                    det_steps += f"   Final determinant = {trigsimp(logcombine(determinant, force=True))}\n"

                cofactor_steps = ""
                for i in range(rows):
                    for j in range(cols):
                        minor = A.minor_submatrix(i, j)
                        sign = (-1) ** (i + j)
                        cofactor_val = sign * minor.det()
                        cofactor_val = trigsimp(logcombine(cofactor_val, force=True))
                        cofactor_steps += f"   C[{i+1},{j+1}] = (-1)^({i+1}+{j+1}) × det({minor.tolist()}) = {cofactor_val}\n"

                steps_text = (
                    f"📘 Steps:\n\n"
                    f"1. Original matrix:\n{format_matrix(A)}\n\n"
                    f"2. Determinant Calculation:\n{det_steps or '   Determinant computed'}\n"
                    f"   det(A) = {trigsimp(logcombine(determinant, force=True))}\n\n"
                    f"3. Compute all cofactors:\n{cofactor_steps}\n"
                    f"   Cofactor Matrix =\n{format_matrix(cofactor)}\n\n"
                    f"4. Transpose of cofactor matrix → adjugate:\n{format_matrix(adjugate)}\n\n"
                    f"5. Apply inverse formula:\n"
                    f"   A⁻¹ = (1 / {trigsimp(logcombine(determinant, force=True))}) × adjugate\n\n"
                    f"6. Final Result:\n{format_matrix(inverse_matrix)}"
                )

                say_show(
                    speak_args=(f"The answer is {inverse_matrix.tolist()}. You'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"उत्तर है {inverse_matrix.tolist()}। समाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"La réponse est {inverse_matrix.tolist()}. Vous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"La respuesta es {inverse_matrix.tolist()}. Encontrarás la solución en la ventana emergente de solución.",
                        de=f"Die Antwort ist {inverse_matrix.tolist()}. Die Lösung findest du im Lösungspopup.",
                        log_command="Matrix inverse calculated",
                    ),
                    gui_kwargs=dict(
                        result=str(inverse_matrix.tolist()),
                        solution_en="Matrix inverse computed using adjugate / determinant.",
                        stepwise=steps_text
                    )
                )

            except Exception as e:
                say_show(
                    speak_args=("Unable to calculate. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="गणना संभव नहीं है। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Échec du calcul. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="No se pudo calcular. Encontrarás la solución en la ventana emergente de solución.",
                        de="Nicht berechenbar. Die Erläuterung findest du im Lösungspopup.",
                        log_command=f"Matrix inverse failed: {str(e)}",
                    ),
                    gui_kwargs=dict(
                        result="❌ Not Invertible",
                        solution_en="Matrix inverse not possible.",
                        stepwise=f"📘 Steps:\n\n❌ Error: Matrix inverse not possible.\nReason: {str(e)}"
                    )
                )

        # 🔁 Matrix Operations - Transpose of a Matrix
        elif ("transpose of matrix" in lowered) or ("matrix transpose" in lowered):
            try:
                matrix_data = extract_matrix(command)
                A = Matrix(matrix_data)
                result = A.T

                def fmt_cell(c): return str(trigsimp(logcombine(c, force=True)))
                def format_matrix(M):
                    return "\n".join([
                        "   | " + "  ".join(fmt_cell(c) for c in row) + " |"
                        for row in M.tolist()
                    ])

                steps = [f"1. Original matrix:\n{format_matrix(A)}\n"]
                rows, cols = A.shape
                for i in range(rows):
                    row_values = [fmt_cell(A[i, j]) for j in range(cols)]
                    steps.append(f"   Row {i + 1}: {'  '.join(row_values)}")

                steps.append("\n2. Swap rows with columns:")
                for i in range(cols):
                    col_values = [fmt_cell(A[j, i]) for j in range(rows)]
                    steps.append(f"   New Row {i + 1} (was Column {i + 1}): {'  '.join(col_values)}")

                steps.append(f"\n3. Final transposed matrix:\n{format_matrix(result)}")
                stepwise = "📘 Steps:\n" + "\n".join(steps)

                result_str = str(result.tolist())

                solution_en = (
                    f"Step 1: You asked for the transpose of the matrix: {matrix_data}\n"
                    f"Step 2: We swapped rows and columns\n"
                    f"Result: {result_str}"
                )

                say_show(
                    speak_args=(f"The answer is {result.tolist()}. You'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"उत्तर है {result.tolist()}। समाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"La réponse est {result.tolist()}. Vous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"La respuesta es {result.tolist()}. Encontrarás la solución en la ventana emergente de solución.",
                        de=f"Die Antwort ist {result.tolist()}. Die Lösung findest du im Lösungspopup.",
                        log_command="Matrix transpose calculated",
                    ),
                    gui_kwargs=dict(result=result_str, solution_en=solution_en, stepwise=stepwise)
                )

            except Exception as e:
                say_show(
                    speak_args=("Sorry, I couldn't calculate the transpose. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="क्षमा करें, मैं ट्रांसपोज़ की गणना नहीं कर सकी। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Désolé, je n'ai pas pu calculer la transposée. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="Lo siento, no pude calcular la transpuesta. Encontrarás la explicación en la ventana emergente de solución.",
                        de="Entschuldigung, ich konnte die Transponierte nicht berechnen. Die Erläuterung findest du im Lösungspopup.",
                        log_command=f"Matrix transpose failed: {str(e)}",
                    ),
                    gui_kwargs=dict(
                        result="❌ Transpose Failed",
                        solution_en="Matrix transpose failed.",
                        stepwise=f"📘 Steps:\n\n❌ Error: Matrix transpose failed.\nReason: {str(e)}"
                    )
                )

        # 🔢 Determinant of a Matrix
        elif ("determinant of matrix" in lowered) or ("matrix determinant" in lowered):
            try:
                matrix_data = extract_matrix(command)
                matrix = Matrix(matrix_data)
                result = matrix.det()

                def fmt_cell(c): return str(trigsimp(logcombine(c, force=True)))
                def format_matrix_grid(mat):
                    rows = ["  " + "  ".join(fmt_cell(cell) for cell in row)
                            for row in mat.tolist()]
                    return f"⎡ {rows[0]} ⎤\n" + \
                           "\n".join([f"⎢ {row} ⎥" for row in rows[1:-1]]) + \
                           f"\n⎣ {rows[-1]} ⎦"

                visual_matrix = format_matrix_grid(matrix)
                steps = [f"1. Original matrix A:\n{visual_matrix}"]

                if matrix.shape == (2, 2):
                    a, b = matrix[0, 0], matrix[0, 1]
                    c, d = matrix[1, 0], matrix[1, 1]
                    steps.append("2. Formula for 2x2 determinant: det(A) = ad − bc")
                    steps.append(f"   a = {a}, b = {b}, c = {c}, d = {d}")
                    steps.append(f"   det(A) = ({a})×({d}) − ({b})×({c}) = {a*d} − {b*c} = {result}")

                elif matrix.shape == (3, 3):
                    a, b, c = matrix[0, 0], matrix[0, 1], matrix[0, 2]
                    d, e, f = matrix[1, 0], matrix[1, 1], matrix[1, 2]
                    g, h, i = matrix[2, 0], matrix[2, 1], matrix[2, 2]

                    ei_fh = e*i - f*h
                    di_fg = d*i - f*g
                    dh_eg = d*h - e*g

                    steps.append("2. Apply cofactor expansion along the first row:")
                    steps.append("   Formula: det(A) = a(ei − fh) − b(di − fg) + c(dh − eg)")
                    steps.append(f"   Let: a = {a}, b = {b}, c = {c}")
                    steps.append(f"        d = {d}, e = {e}, f = {f}")
                    steps.append(f"        g = {g}, h = {h}, i = {i}")
                    steps.append("\n   Compute each term:")
                    steps.append(f"     ei − fh = ({e}×{i}) − ({f}×{h}) = {e*i} − {f*h} = {ei_fh}")
                    steps.append(f"     di − fg = ({d}×{i}) − ({f}×{g}) = {d*i} − {f*g} = {di_fg}")
                    steps.append(f"     dh − eg = ({d}×{h}) − ({e}×{g}) = {d*h} − {e*g} = {dh_eg}")
                    steps.append("\n   Plug into formula:")
                    steps.append(f"     = {a}×({ei_fh}) − {b}×({di_fg}) + {c}×({dh_eg})")
                    steps.append(f"     = {a*ei_fh} − {b*di_fg} + {c*dh_eg} = {result}")

                else:
                    steps.append("2. For larger matrices, determinant is computed using Laplace expansion or row reduction.")
                    steps.append(f"   Result: det(A) = {result}")

                steps.append(f"\n3. ✅ Final result: det(A) = {result}")
                stepwise = "📘 Steps:\n" + "\n".join(steps)

                solution_en = (
                    f"Step 1: You asked for the determinant of matrix: {matrix_data}\n"
                    f"Step 2: We calculated it using cofactor expansion or formula.\n"
                    f"Result: {result}"
                )

                say_show(
                    speak_args=(f"The answer is {result}. You'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"उत्तर है {result}। समाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"La réponse est {result}. Vous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"La respuesta es {result}. Encontrarás la solución en la ventana emergente de solución.",
                        de=f"Die Antwort ist {result}. Die Lösung findest du im Lösungspopup.",
                        log_command="Matrix determinant calculated",
                    ),
                    gui_kwargs=dict(result=result, solution_en=solution_en, stepwise=stepwise)
                )

            except Exception as e:
                say_show(
                    speak_args=("I couldn't compute the determinant. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="मैं डिटर्मिनेंट नहीं निकाल पाई। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Je n'ai pas pu calculer le déterminant. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="No pude calcular el determinante. Encontrarás la explicación en la ventana emergente de solución.",
                        de="Ich konnte die Determinante nicht berechnen. Die Erläuterung findest du im Lösungspopup.",
                        log_command="Matrix determinant failed",
                    ),
                    gui_kwargs=dict(
                        result="❌ Error",
                        solution_en="An error occurred. Make sure your matrix is square (e.g., 2x2 or 3x3). Determinant can only be calculated for square matrices.",
                        stepwise="⚠️ Error: Determinant undefined for non-square matrices. Please enter a valid square matrix like 2x2 or 3x3."
                    )
                )

        # 🔁 Matrix Operations – Matrix Multiplication
        elif ("multiply" in lowered) and ("with" in lowered):
            try:
                m1, m2 = extract_two_matrices(command)

                # Only format when printing; keep objects symbolic
                A = Matrix(m1)
                B = Matrix(m2)

                if A.shape[1] != B.shape[0]:
                    raise ValueError("Number of columns in A must equal number of rows in B for multiplication.")

                result = A * B
                rows_A, cols_A = A.shape
                _, cols_B = B.shape

                steps = [
                    "📘 Steps:\n\n1. Original matrices:",
                    f"   A = {A.tolist()}",
                    f"   B = {B.tolist()}",
                    "\n2. Matrix multiplication rule:",
                    "   C[i][j] = sum(A[i][k] * B[k][j])\n",
                    "3. Compute each cell C[i][j] step-by-step:"
                ]

                for i in range(rows_A):
                    for j in range(cols_B):
                        term_symbols = []
                        term_numbers = []
                        cell_sum = 0
                        for k in range(cols_A):
                            a = A[i, k]
                            b = B[k, j]
                            term_symbols.append(f"A[{i+1}][{k+1}]×B[{k+1}][{j+1}]")
                            term_numbers.append(f"{a}×{b}")
                            cell_sum += a * b

                        steps.append(f"   C[{i+1}][{j+1}] = {' + '.join(term_symbols)}")
                        steps.append(f"               = {' + '.join(term_numbers)}")
                        steps.append(f"               = {cell_sum}")

                steps.append(f"\n4. Final Result:\n   {result.tolist()}")
                stepwise = "\n".join(steps)

                solution_en = (
                    f"Step 1: You asked to multiply matrices:\n  A = {m1}\n  B = {m2}\n"
                    f"Step 2: We applied the matrix multiplication rules.\n"
                    f"Result: {result.tolist()}"
                )

                say_show(
                    speak_args=(f"The answer is {result.tolist()}. You'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"उत्तर है {result.tolist()}। समाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"La réponse est {result.tolist()}. Vous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"La respuesta es {result.tolist()}. Encontrarás la solución en la ventana emergente de solución.",
                        de=f"Die Antwort ist {result.tolist()}. Die Lösung findest du im Lösungspopup.",
                        log_command="Matrix multiplication successful",
                    ),
                    gui_kwargs=dict(result=str(result.tolist()), solution_en=solution_en, stepwise=stepwise)
                )

            except Exception as e:
                say_show(
                    speak_args=("Matrix multiplication failed. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="मैट्रिक्स गुणा विफल रहा। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Échec de la multiplication. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="Falló la multiplicación de matrices. Encontrarás la solución en la ventana emergente de solución.",
                        de="Matrixmultiplikation fehlgeschlagen. Die Erläuterung findest du im Lösungspopup.",
                        log_command=f"Matrix multiplication failed: {str(e)}",
                    ),
                    gui_kwargs=dict(
                        result="❌ Error",
                        solution_en="Matrix multiplication is not possible. The number of columns in A must equal the number of rows in B.",
                        stepwise=f"⚠️ Error: {str(e)}"
                    )
                )

        # 🔁 Matrix Operations – Rank of a Matrix
        elif "rank of matrix" in lowered:
            try:
                matrix_data = extract_matrix(command)
                A = Matrix(matrix_data)
                original = A.tolist()

                steps = []
                steps.append("📘 Steps:\n")
                steps.append("1. Original matrix:")
                steps.append("   A =")
                for r in original:
                    steps.append(f"   {r}")

                steps.append("\n2. Perform row operations to get Row Echelon Form:")

                B = Matrix(A)
                m, n = B.shape
                row_i = 0

                for col in range(n):
                    if row_i >= m:
                        break

                    if B[row_i, col] == 0:
                        for r in range(row_i + 1, m):
                            if B[r, col] != 0:
                                B.row_swap(row_i, r)
                                steps.append(f"   R{row_i+1} ↔ R{r+1}  (Swapped to make pivot non-zero)")
                                break

                    pivot = B[row_i, col]

                    if pivot != 0:
                        if pivot != 1:
                            old_row = B.row(row_i)
                            B.row_op(row_i, lambda v, j: v / pivot)
                            new_row = B.row(row_i)
                            steps.append(f"   R{row_i+1} → R{row_i+1} / {pivot}  (Make pivot = 1)")
                            steps.append(f"     ⇒ {pivot} × {old_row.tolist()[0]} = {[(pivot * v).evalf() for v in old_row]}")
                            steps.append(f"     ⇒ {[(pivot * v).evalf() for v in old_row]} ÷ {pivot} = {new_row.tolist()[0]}")

                        for r in range(m):
                            if r != row_i and B[r, col] != 0:
                                factor_v = B[r, col]
                                orig_r = B.row(r)
                                base_row = B.row(row_i)
                                multiplied = [(factor_v * v).evalf() for v in base_row]
                                B.row_op(r, lambda v, j: v - factor_v * B[row_i, j])
                                new_r = B.row(r)
                                steps.append(f"   R{r+1} → R{r+1} - ({factor_v})×R{row_i+1}")
                                steps.append(f"     ⇒ {factor_v} × {base_row.tolist()[0]} = {multiplied}")
                                steps.append(f"     ⇒ {orig_r.tolist()[0]} - {multiplied} = {new_r.tolist()[0]}")

                        row_i += 1

                steps.append("\n3. Row Echelon Form:")
                for r in B.tolist():
                    steps.append(f"   {r}")

                non_zero_rows = sum(1 for r in B.tolist() if any(val != 0 for val in r))
                steps.append(f"\n4. Number of non-zero rows: {non_zero_rows} ⇒ Rank = {non_zero_rows}")
                steps.append(f"\n✅ Final Answer: Rank = {non_zero_rows}")

                stepwise = "\n".join(steps)

                solution_en = (
                    f"Step 1: You asked for the rank of matrix: {matrix_data}\n"
                    f"Step 2: We applied row reduction method to count non-zero rows\n"
                    f"Result: {non_zero_rows}"
                )

                say_show(
                    speak_args=(f"The rank is {non_zero_rows}. You'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"रैंक {non_zero_rows} है। समाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"Le rang est {non_zero_rows}. Vous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"El rango es {non_zero_rows}. Encontrarás la solución en la ventana emergente de solución.",
                        de=f"Der Rang ist {non_zero_rows}. Die Lösung findest du im Lösungspopup.",
                        log_command="Matrix rank calculation",
                    ),
                    gui_kwargs=dict(result=f"Rank = {non_zero_rows}", solution_en=solution_en, stepwise=stepwise)
                )

            except Exception as e:
                say_show(
                    speak_args=("Matrix rank calculation failed. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="मैट्रिक्स रैंक की गणना विफल रही। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Le calcul du rang de la matrice a échoué. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="Error al calcular el rango de la matriz. Encontrarás la explicación en la ventana emergente de solución.",
                        de="Rangberechnung fehlgeschlagen. Die Erläuterung findest du im Lösungspopup.",
                        log_command=f"Matrix rank calculation failed: {str(e)}",
                    ),
                    gui_kwargs=dict(
                        result="❌ Error",
                        solution_en="Matrix rank calculation failed due to invalid input or unsupported symbolic values.",
                        stepwise=f"⚠️ Error: {str(e)}"
                    )
                )

        # 🔁 Matrix Operations – Eigenvalues of a Matrix
        elif "eigenvalues of matrix" in lowered:
            try:
                matrix_data = extract_matrix(command)
                A = Matrix(matrix_data)

                if A.shape[0] != A.shape[1]:
                    raise ValueError("Matrix must be square to compute eigenvalues.")

                n = A.shape[0]
                λ = Symbol('λ')
                I = Matrix.eye(n)
                A_lambda_I = A - λ * I
                char_poly = A_lambda_I.det()
                eigenvals = solve(char_poly, λ)
                eigenvals_rounded = [round(float(ev.evalf()), 2) for ev in eigenvals]

                def format_matrix(M):
                    return "\n   | " + " |\n   | ".join("  ".join(str(el) for el in row) for row in M.tolist()) + " |"

                def cofactor_expansion_3x3_verbose(M):
                    a11, a12, a13 = M[0, 0], M[0, 1], M[0, 2]
                    a21, a22, a23 = M[1, 0], M[1, 1], M[1, 2]
                    a31, a32, a33 = M[2, 0], M[2, 1], M[2, 2]
                    term1_raw = f"({a11})[( {a22} )( {a33} ) − ( {a23} )( {a32} )]"
                    term2_raw = f"− ({a12})[( {a21} )( {a33} ) − ( {a23} )( {a31} )]"
                    term3_raw = f"+ ({a13})[( {a21} )( {a32} ) − ( {a22} )( {a31} )]"
                    minor1 = (a22 * a33) - (a23 * a32)
                    minor2 = (a21 * a33) - (a23 * a31)
                    minor3 = (a21 * a32) - (a22 * a31)
                    return (
                        f"   = {term1_raw}\n"
                        f"     {term2_raw}\n"
                        f"     {term3_raw}\n\n"
                        f"   = ({a11})[{minor1}] − ({a12})[{minor2}] + ({a13})[{minor3}]"
                    )

                solution_steps = f"📘 Steps:\n\n1. Original Matrix:\n{format_matrix(A)}\n\n"
                solution_steps += f"2. Construct (A − λI):\n{format_matrix(A_lambda_I)}\n\n"

                if n == 2:
                    a, b = A[0, 0], A[0, 1]
                    c, d = A[1, 0], A[1, 1]
                    trace = a + d
                    determinant = a * d - b * c
                    solution_steps += (
                        f"3. Compute determinant of (A − λI):\n"
                        f"   = ({a}−λ)({d}−λ) − ({b})({c})\n"
                        f"   = λ² − ({trace})λ + ({determinant})\n\n"
                        f"4. Solve characteristic equation:\n"
                        f"   λ² − {trace}λ + {determinant} = 0\n"
                    )
                elif n == 3:
                    solution_steps += "3. Compute determinant of (A − λI) using cofactor expansion:\n"
                    solution_steps += cofactor_expansion_3x3_verbose(A_lambda_I) + "\n\n"
                    solution_steps += (
                        "4. Expand characteristic polynomial:\n"
                        f"   = " + str(char_poly.expand()) + "\n"
                        f"   Solve: {char_poly} = 0\n"
                    )
                else:
                    solution_steps += "3. Characteristic polynomial formed; solving numerically for larger matrices.\n"

                solution_steps += f"\n✅ Final Answer:\nEigenvalues = {eigenvals_rounded}"

                say_show(
                    speak_args=(f"The eigenvalues are {eigenvals_rounded}. You'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"विशेष गुणांक हैं {eigenvals_rounded}। समाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"Les valeurs propres sont {eigenvals_rounded}. Vous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"Los eigenvalores son {eigenvals_rounded}. Encontrarás la solución en la ventana emergente de solución.",
                        de=f"Die Eigenwerte sind {eigenvals_rounded}. Die Lösung findest du im Lösungspopup.",
                        log_command="Eigenvalues",
                    ),
                    gui_kwargs=dict(
                        result=str(eigenvals_rounded),
                        solution_en="Eigenvalues (rounded to 2 decimals) computed via characteristic polynomial.",
                        stepwise=solution_steps
                    )
                )

            except Exception as e:
                say_show(
                    speak_args=("Sorry, I couldn't compute the eigenvalues. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="क्षमा करें, मैं विशेष गुणांक की गणना नहीं कर सकी। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Désolé, je n'ai pas pu calculer les valeurs propres. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="Lo siento, no pude calcular los eigenvalores. Encontrarás la solución en la ventana emergente de solución.",
                        de="Entschuldigung, ich konnte die Eigenwerte nicht berechnen. Die Erläuterung findest du im Lösungspopup.",
                        log_command=str(e),
                    ),
                    gui_kwargs=dict(
                        result="❌ Error",
                        solution_en="Matrix eigenvalue computation failed. Ensure your matrix is square and elements are valid expressions.",
                        stepwise=f"⚠️ Error: {str(e)}"
                    )
                )

        # 🔁 Identity Matrix Check
        elif ("is identity matrix" in lowered) or ("check if identity matrix" in lowered) or ("whether identity matrix" in lowered):
            try:
                matrix_data = extract_matrix(command)
                A = Matrix(matrix_data)

                if A.shape[0] != A.shape[1]:
                    raise ValueError("Matrix must be square to check identity.")

                n = A.shape[0]

                diag_issues, off_diag_issues = [], []
                for i in range(n):
                    for j in range(n):
                        value = A[i, j]
                        if i == j and value != 1:
                            diag_issues.append(f"⛔ A[{i+1},{j+1}] = {value} ≠ 1 (Diagonal)")
                        elif i != j and value != 0:
                            off_diag_issues.append(f"⛔ A[{i+1},{j+1}] = {value} ≠ 0 (Off-Diagonal)")

                def format_matrix(M):
                    return "\n".join(["   | " + "  ".join(f"{item}" for item in row) + " |" for row in M.tolist()])

                if not diag_issues and not off_diag_issues:
                    steps_text = (
                        f"🌟 Identity Matrix Check\n"
                        f"📘 Steps:\n\n"
                        f"1. Original Matrix:\n{format_matrix(A)}\n\n"
                        f"2. Check if matrix is square:\n"
                        f"   ✅ It is a {n}x{n} square matrix.\n\n"
                        f"3. Check diagonal elements (should be 1):\n"
                        f"   ✅ All diagonal elements are 1.\n\n"
                        f"4. Check off-diagonal elements (should be 0):\n"
                        f"   ✅ All off-diagonal elements are 0.\n\n"
                        f"✅ Final Result:\nThe given matrix **is** an identity matrix ✅"
                    )
                    result_text = "Yes"
                else:
                    steps_text = (
                        f"🌟 Identity Matrix Check\n"
                        f"📘 Steps:\n\n"
                        f"1. Original Matrix:\n{format_matrix(A)}\n\n"
                        f"2. Check if matrix is square:\n"
                        f"   ✅ It is a {n}x{n} square matrix.\n\n"
                        f"3. Check diagonal elements (should be 1):\n"
                        f"   {'✅ OK' if not diag_issues else '❌ Issues Found:'}\n"
                        f"   " + ("\n   ".join(diag_issues) if diag_issues else "") + "\n\n"
                        f"4. Check off-diagonal elements (should be 0):\n"
                        f"   {'✅ OK' if not off_diag_issues else '❌ Issues Found:'}\n"
                        f"   " + ("\n   ".join(off_diag_issues) if off_diag_issues else "") + "\n\n"
                        f"❌ Final Result:\nThe given matrix **is NOT** an identity matrix."
                    )
                    result_text = "No"

                say_show(
                    speak_args=(f"The result is: {result_text}. You'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"परिणाम है: {result_text}। समाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"Le résultat est : {result_text}. Vous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"El resultado es: {result_text}. Encontrarás la solución en la ventana emergente de solución.",
                        de=f"Das Ergebnis ist: {result_text}. Die Lösung findest du im Lösungspopup.",
                        log_command="Identity Matrix Check",
                    ),
                    gui_kwargs=dict(result=result_text, solution_en="Identity matrix check", stepwise=steps_text)
                )

            except Exception as e:
                say_show(
                    speak_args=("Unable to determine. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="निर्धारित नहीं किया जा सका। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Indéterminé. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="No se pudo determinar. Encontrarás la explicación en la ventana emergente de solución.",
                        de="Nicht bestimmbar. Die Erläuterung findest du im Lösungspopup.",
                        log_command="Identity matrix check failed",
                    ),
                    gui_kwargs=dict(
                        result="❌ Error",
                        solution_en="Identity matrix check failed due to invalid input or unsupported symbolic values.",
                        stepwise=f"⚠️ Error: {str(e)}"
                    )
                )

        # 🔢 Matrix Power
        elif "to the power" in lowered:
            try:
                matrix_data, power = extract_matrix_and_power(command)
                A = Matrix(matrix_data)

                rows, cols = A.shape
                if rows != cols:
                    raise ValueError("Matrix power is only defined when the matrix can be multiplied with itself — i.e., it must be square (n×n).")
                if not isinstance(power, int):
                    raise ValueError("Power must be a whole number (integer) like 2, 3, or 5.")

                def format_matrix(M):
                    return "\n".join(["   | " + "  ".join(str(c) for c in row) + " |" for row in M.tolist()])

                result = A ** power

                math_steps = ""
                if power == 2:
                    math_steps += "Step-by-step multiplication for A² = A × A:\n\n"
                    for i in range(rows):
                        for j in range(cols):
                            computed = [f"{A[i, k]}×{A[k, j]}" for k in range(cols)]
                            math_steps += f"   [A²]({i+1},{j+1}) = {' + '.join(computed)} = {result[i,j]}\n"
                    math_steps += "\n"
                elif power == 3:
                    math_steps += "Step-by-step multiplication for A³ = A × A × A:\n\n"
                    A2 = A ** 2
                    for i in range(rows):
                        for j in range(cols):
                            computed = [f"{A2[i, k]}×{A[k, j]}" for k in range(cols)]
                            math_steps += f"   [A³]({i+1},{j+1}) = {' + '.join(computed)} = {result[i,j]}\n"
                    math_steps += "\n"

                steps_text = (
                    f"📘 Steps:\n\n"
                    f"1. Original Matrix (A):\n{format_matrix(A)}\n\n"
                    f"2. Requested Power:\n"
                    f"   Compute A^{power}\n\n"
                    f"3. Matrix Power Rule:\n"
                    f"   A^{power} means multiplying A by itself {power} times\n\n"
                    f"4. Performed Multiplication:\n{math_steps if math_steps else '   (Step-by-step math skipped for higher power)'}\n"
                    f"5. Final Result:\n{format_matrix(result)}\n\n"
                    f"✅ Final Answer:\nMatrix raised to power {power} is:\n{format_matrix(result)}"
                )

                say_show(
                    speak_args=(f"The answer is:\n{format_matrix(result)}\nYou'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"उत्तर है:\n{format_matrix(result)}\nसमाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"La réponse est :\n{format_matrix(result)}\nVous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"La respuesta es:\n{format_matrix(result)}\nEncontrarás la solución en la ventana emergente de solución.",
                        de=f"Die Antwort ist:\n{format_matrix(result)}\nDie Lösung findest du im Lösungspopup.",
                        log_command=f"Matrix Power A^{power}",
                    ),
                    gui_kwargs=dict(result=f"A^{power}", solution_en="Matrix power", stepwise=steps_text)
                )

            except Exception as e:
                user_friendly_reason = str(e)
                if "square" in user_friendly_reason:
                    user_friendly_reason = "Matrix power is only defined when the matrix can be multiplied with itself — i.e., it must be square (same number of rows and columns)."
                elif "integer" in user_friendly_reason:
                    user_friendly_reason = "Power must be a whole number (integer) like 2, 3, or 5."

                say_show(
                    speak_args=("Unable to calculate. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="गणना संभव नहीं है। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Échec du calcul. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="No se pudo calcular. Encontrarás la solución en la ventana emergente de solución.",
                        de="Nicht berechenbar. Die Erläuterung findest du im Lösungspopup.",
                        log_command=f"Matrix Power Failure: {str(e)}",
                    ),
                    gui_kwargs=dict(
                        result="❌ Unable to calculate",
                        solution_en="Could not compute matrix power.",
                        stepwise=f"⚠️ Error: {str(e)}\n\nReason: {user_friendly_reason}"
                    )
                )

        # 🔢 Trace of a Matrix
        elif "trace of matrix" in lowered:
            try:
                matrix_data = extract_matrix(command)
                A = Matrix(matrix_data)

                rows, cols = A.shape
                if rows != cols:
                    raise ValueError("Matrix must be square to compute trace.")

                def format_matrix(M):
                    return "\n".join(["   | " + "  ".join(str(c) for c in row) + " |" for row in M.tolist()])

                trace_val = sum(A[i, i] for i in range(rows))
                diag_steps = "\n".join([f"   A[{i+1},{i+1}] = {A[i,i]}" for i in range(rows)])
                trace_sum_expr = " + ".join(str(A[i,i]) for i in range(rows))

                steps_text = (
                    f"📘 Steps:\n\n"
                    f"1. Original Matrix:\n{format_matrix(A)}\n\n"
                    f"2. Rule:\n"
                    f"   ✅ Matrix must be square. This is a {rows}×{cols} square matrix.\n\n"
                    f"3. Diagonal Elements:\n{diag_steps}\n\n"
                    f"4. Trace Calculation:\n"
                    f"   Trace = {trace_sum_expr} = {trace_val}\n\n"
                    f"✅ Final Answer:\n"
                    f"The trace of the matrix is: {trace_val}"
                )

                result_text = str(trace_val)

                say_show(
                    speak_args=(f"The answer is {result_text}. You'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"उत्तर है {result_text}। समाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"La réponse est {result_text}. Vous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"La respuesta es {result_text}. Encontrarás la solución en la ventana emergente de solución.",
                        de=f"Die Antwort ist {result_text}. Die Lösung findest du im Lösungspopup.",
                        log_command="Trace of Matrix",
                    ),
                    gui_kwargs=dict(result=result_text, solution_en="Trace of matrix", stepwise=steps_text)
                )

            except Exception as e:
                extra = ""
                try:
                    rows, cols = A.shape
                    if rows != cols:
                        extra = f"\n\nNote: Matrix must be square. You provided {rows}×{cols}."
                except Exception:
                    pass

                say_show(
                    speak_args=("Unable to determine. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="निर्धारित नहीं किया जा सका। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Impossible de déterminer. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="No se pudo determinar. Encontrarás la explicación en la ventana emergente de solución.",
                        de="Nicht bestimmbar. Die Erläuterung findest du im Lösungspopup.",
                        log_command="Trace Matrix Failure",
                    ),
                    gui_kwargs=dict(
                        result="❌ Unable to determine",
                        solution_en="Could not compute matrix trace.",
                        stepwise=f"📘 Steps:\n\n❌ Error: {str(e)}{extra}"
                    )
                )

        # 🔢 Cofactor of a Matrix
        elif "cofactor of matrix" in lowered:
            try:
                matrix_data = extract_matrix(command)
                A = Matrix(matrix_data)

                rows, cols = A.shape
                if rows != cols:
                    raise ValueError("Cofactor matrix is only defined for square matrices.")
                n = rows

                def format_matrix(M):
                    return "\n".join(["   | " + "  ".join(f"{item}" for item in row) + " |" for row in M.tolist()])

                cofactor_matrix = []
                explanation = ""
                explanation += f"📘 Steps:\n\n"
                explanation += f"1. Original Matrix:\n{format_matrix(A)}\n\n"
                explanation += f"2. Rule:\n"
                explanation += f"   ✅ Cofactor is defined for square matrices only.\n"
                explanation += f"   This is a {n}×{n} square matrix.\n\n"
                explanation += f"   Formula:\n"
                explanation += f"   C[i,j] = (−1)^(i+j) × M[i,j]\n"
                explanation += f"   where M[i,j] is the minor of element A[i,j]\n\n"
                explanation += f"3. Cofactor Calculation:\n\n"

                for i in range(n):
                    row_cofactor = []
                    for j in range(n):
                        sign = (-1) ** (i + j)
                        minor = A.minor_submatrix(i, j).det()
                        cofactor_val = sign * minor
                        sign_str = "+1" if sign == 1 else "-1"
                        explanation += f"   C[{i+1},{j+1}] = ({sign_str}) × Minor of A[{i+1},{j+1}] = ({sign_str}) × {minor} = {cofactor_val}\n"
                        row_cofactor.append(cofactor_val)
                    cofactor_matrix.append(row_cofactor)
                    explanation += "\n"

                C = Matrix(cofactor_matrix)
                explanation += f"4. Final Cofactor Matrix:\n{format_matrix(C)}\n\n"
                explanation += f"✅ Final Answer:\nThe cofactor matrix is:\n{format_matrix(C)}"

                say_show(
                    speak_args=(f"The answer is:\n{format_matrix(C)}\nYou'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"उत्तर है:\n{format_matrix(C)}\nसमाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"La réponse est :\n{format_matrix(C)}\nVous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"La respuesta es:\n{format_matrix(C)}\nEncontrarás la solución en la ventana emergente de solución.",
                        de=f"Die Antwort ist:\n{format_matrix(C)}\nDie Lösung findest du im Lösungspopup.",
                        log_command="Cofactor of Matrix",
                    ),
                    gui_kwargs=dict(result="Cofactor Matrix", solution_en="Cofactor matrix computed.", stepwise=explanation)
                )

            except Exception as e:
                say_show(
                    speak_args=("Unable to calculate. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="गणना संभव नहीं है। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Échec du calcul. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="No se pudo calcular. Encontrarás la solución en la ventana emergente de solución.",
                        de="Nicht berechenbar. Die Erläuterung findest du im Lösungspopup.",
                        log_command=f"Cofactor matrix failure: {str(e)}",
                    ),
                    gui_kwargs=dict(
                        result="❌ Unable to calculate",
                        solution_en="Could not compute cofactor matrix.",
                        stepwise=f"📘 Steps:\n\n❌ Error: Could not compute cofactor matrix.\nReason: {str(e)}"
                    )
                )

        # 🔄 Matrix Operations – Adjoint of a Matrix
        elif ("adjoint of matrix" in lowered) or ("adjugate of matrix" in lowered):
            try:
                matrix_data = extract_matrix(command)
                A = Matrix(matrix_data)

                rows, cols = A.shape
                if rows != cols:
                    raise ValueError("Adjoint matrix is only defined for square matrices.")

                n = rows

                def format_matrix(M):
                    return "\n".join(["   | " + "  ".join(f"{item}" for item in row) + " |" for row in M.tolist()])

                explanation = f"📘 Steps:\n\n"
                explanation += f"1. Original Matrix:\n{format_matrix(A)}\n\n"
                explanation += f"2. Rule:\n"
                explanation += f"   ✅ Adjoint is defined only for square matrices.\n"
                explanation += f"   This is a {n}×{n} square matrix.\n\n"
                explanation += f"3. Step 1 – Compute Cofactor Matrix:\n"

                cofactor_matrix = []
                for i in range(n):
                    row_cofactor = []
                    for j in range(n):
                        sign = (-1) ** (i + j)
                        minor = A.minor_submatrix(i, j).det()
                        cofactor_val = sign * minor
                        sign_str = "+1" if sign == 1 else "−1"
                        explanation += f"   C[{i+1},{j+1}] = ({sign_str}) × Minor of A[{i+1},{j+1}] = ({sign_str}) × {minor} = {cofactor_val}\n"
                        row_cofactor.append(cofactor_val)
                    cofactor_matrix.append(row_cofactor)
                    explanation += "\n"

                C = Matrix(cofactor_matrix)
                explanation += f"   Cofactor Matrix:\n{format_matrix(C)}\n\n"

                # Step 2 – Transpose
                adjoint_matrix = C.transpose()
                explanation += f"4. Step 2 – Transpose of Cofactor Matrix:\n"
                explanation += f"   We flip the matrix across its diagonal.\n\n"
                explanation += f"   Original Cofactor:\n{format_matrix(C)}\n\n"
                explanation += f"   Transposed Matrix (Adjoint/Adjugate):\n{format_matrix(adjoint_matrix)}\n\n"
                explanation += f"✅ Final Answer:\nThe adjoint (adjugate) matrix is:\n{format_matrix(adjoint_matrix)}"

                say_show(
                    speak_args=(f"The answer is:\n{format_matrix(adjoint_matrix)}\nYou'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"उत्तर है:\n{format_matrix(adjoint_matrix)}\nसमाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"La réponse est :\n{format_matrix(adjoint_matrix)}\nVous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"La respuesta es:\n{format_matrix(adjoint_matrix)}\nEncontrarás la solución en la ventana emergente de solución.",
                        de=f"Die Antwort ist:\n{format_matrix(adjoint_matrix)}\nDie Lösung findest du im Lösungspopup.",
                        log_command="Adjoint of Matrix",
                    ),
                    gui_kwargs=dict(result="Adjoint Matrix", solution_en="Adjoint (adjugate) matrix computed.", stepwise=explanation)
                )

            except Exception as e:
                say_show(
                    speak_args=("Unable to calculate. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="गणना संभव नहीं है। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Échec du calcul. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="No se pudo calcular. Encontrarás la solución en la ventana emergente de solución.",
                        de="Nicht berechenbar. Die Erläuterung findest du im Lösungspopup.",
                        log_command=f"Adjoint Failure: {str(e)}",
                    ),
                    gui_kwargs=dict(
                        result="❌ Unable to calculate",
                        solution_en="Could not compute adjoint matrix.",
                        stepwise=f"📘 Steps:\n\n❌ Error: Could not compute adjoint matrix.\nReason: {str(e)}"
                    )
                )

        # 🔢 Matrix Operations – Minor of a Matrix
        elif "minor of matrix" in lowered:
            try:
                matrix_data = extract_matrix(command)
                A = Matrix(matrix_data)

                rows, cols = A.shape
                if rows != cols:
                    raise ValueError("Minor matrix is only defined for square matrices.")
                n = rows

                def format_matrix(M):
                    return "\n".join(["   | " + "  ".join(f"{item}" for item in row) + " |" for row in M.tolist()])

                minor_matrix = []
                explanation = ""
                explanation += f"📘 Steps:\n\n"
                explanation += f"1. Original Matrix:\n{format_matrix(A)}\n\n"
                explanation += f"2. Rule:\n"
                explanation += f"   ✅ Minor is defined for square matrices only.\n"
                explanation += f"   This is a {n}×{n} square matrix.\n\n"
                explanation += f"   Formula:\n"
                explanation += f"   M[i,j] = Determinant of the submatrix formed by deleting row i and column j.\n\n"
                explanation += f"3. Minor Calculation:\n\n"

                for i in range(n):
                    row_minor = []
                    for j in range(n):
                        sub = A.minor_submatrix(i, j)
                        minor_val = sub.det()
                        formatted_sub = format_matrix(sub)
                        explanation += f"   M[{i+1},{j+1}] = Minor of A[{i+1},{j+1}]:\n"
                        explanation += f"{formatted_sub}\n"
                        explanation += f"     → Determinant = {minor_val}\n\n"
                        row_minor.append(minor_val)
                    minor_matrix.append(row_minor)

                M = Matrix(minor_matrix)
                explanation += f"4. Final Minor Matrix:\n{format_matrix(M)}\n\n"
                explanation += f"✅ Final Answer:\nThe minor matrix is:\n{format_matrix(M)}"

                say_show(
                    speak_args=(f"The answer is:\n{format_matrix(M)}\nYou'll find the solution in the solution popup.",),
                    speak_kwargs=dict(
                        hi=f"उत्तर है:\n{format_matrix(M)}\nसमाधान आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr=f"La réponse est :\n{format_matrix(M)}\nVous trouverez la solution dans la fenêtre contextuelle de solution.",
                        es=f"La respuesta es:\n{format_matrix(M)}\nEncontrarás la solución en la ventana emergente de solución.",
                        de=f"Die Antwort ist:\n{format_matrix(M)}\nDie Lösung findest du im Lösungspopup.",
                        log_command="Minor of Matrix",
                    ),
                    gui_kwargs=dict(result="Minor Matrix", solution_en="Minor matrix computed.", stepwise=explanation)
                )

            except Exception as e:
                say_show(
                    speak_args=("Unable to calculate. You'll find the explanation in the solution popup.",),
                    speak_kwargs=dict(
                        hi="गणना संभव नहीं है। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                        fr="Échec du calcul. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                        es="No se pudo calcular. Encontrarás la solución en la ventana emergente de solución.",
                        de="Nicht berechenbar. Die Erläuterung findest du im Lösungspopup.",
                        log_command=f"Minor matrix failure: {str(e)}",
                    ),
                    gui_kwargs=dict(
                        result="❌ Unable to calculate",
                        solution_en="Could not compute minor matrix.",
                        stepwise=f"📘 Steps:\n\n❌ Error: Could not compute minor matrix.\nReason: {str(e)}"
                    )
                )

        else:
            # ❓ Unknown command
            say_show(
                speak_args=("Sorry, I couldn't understand the request. You'll find the explanation in the solution popup.",),
                speak_kwargs=dict(
                    hi="क्षमा करें, मैं अनुरोध समझ नहीं सकी। विवरण आपको सॉल्यूशन पॉप-अप में मिलेगा।",
                    fr="Désolé, je n'ai pas compris la demande. Vous trouverez l'explication dans la fenêtre contextuelle de solution.",
                    es="Lo siento, no entendí la solicitud. Encontrarás la solución en la ventana emergente de solución.",
                    de="Entschuldigung, ich habe die Anfrage nicht verstanden. Die Erläuterung findest du im Lösungspopup.",
                    log_command="Unknown command",
                ),
                gui_kwargs=dict(
                    result="❔ Unknown",
                    solution_en="Unknown command.",
                    stepwise="Please use keywords like integrate, differentiate, simplify, solve, limit approaches, determinant of matrix, transpose of matrix, etc."
                )
            )

    except Exception as e:
        # Best-effort final catch — speak first, then optional popup
        try:
            logger.error(f"❌ Error during symbolic math handling: {e}")
        except Exception:
            pass
        say_show(
            speak_args=("Sorry, something went wrong while solving the math expression.",),
            speak_kwargs=dict(
                hi="माफ़ कीजिए, गणितीय समीकरण हल करते समय कुछ त्रुटि हुई।",
                fr="Désolé, une erreur s'est produite lors de la résolution de l'expression mathématique.",
                es="Lo siento, ocurrió un error al resolver la expresión matemática.",
                de="Entschuldigung, beim Lösen des mathematischen Ausdrucks ist ein Fehler aufgetreten.",
            ),
            gui_kwargs=dict(
                result="❌ Error",
                solution_en="An unexpected error occurred while handling the request.",
                stepwise=f"⚠️ Error: {str(e)}"
            )
        )


# ---------- Helper Parsers (hardened & consistent) ----------

def _sympify_list_literal(list_literal: str):
    """
    Safely parse a Python-list-like literal with sympy elements using sympify.
    Returns a nested Python list of SymPy objects. Raises ValueError on shape issues.
    """
    try:
        obj = sympify(list_literal, evaluate=False)
    except Exception:
        raise ValueError("Couldn't parse matrix. Use [[1,2],[3,4]] (symbols like sin(x), log(x), pi are okay).")

    # Ensure it's a 2D list-like
    if not isinstance(obj, (list, tuple)) or len(obj) == 0:
        raise ValueError("Matrix must be a non-empty list of rows like [[...], [...]].")

    rows = []
    row_len = None
    for row in obj:
        if not isinstance(row, (list, tuple)) or len(row) == 0:
            raise ValueError("Each matrix row must be a non-empty list.")
        if row_len is None:
            row_len = len(row)
        elif len(row) != row_len:
            raise ValueError("All rows in the matrix must have the same length.")
        rows.append([sympify(cell) for cell in row])
    return rows


def extract_matrix(command: str) -> list:
    """Extract a single matrix from free-form text like: [[1, 2], [3, 4]] safely."""
    matches = re.findall(r"\[\s*\[.*?\]\s*\]", command, flags=re.DOTALL)
    if not matches:
        raise ValueError("Couldn't parse matrix. Use [[1,2],[3,4]] (symbols like sin(x), log(x), pi are okay).")
    return _sympify_list_literal(matches[0])


def extract_two_matrices(command: str) -> tuple:
    """Extract two matrices for multiplication safely."""
    matches = re.findall(r"\[\s*\[.*?\]\s*\]", command, flags=re.DOTALL)
    if len(matches) < 2:
        raise ValueError("Please provide two matrices to multiply.")
    mat1 = _sympify_list_literal(matches[0])
    mat2 = _sympify_list_literal(matches[1])
    return mat1, mat2


def extract_matrix_and_power(command: str) -> tuple:
    """Extract a matrix and an integer power from text like: '[[...]] to the power 3' safely."""
    matches = re.findall(r"\[\s*\[.*?\]\s*\]", command, flags=re.DOTALL)
    if not matches:
        raise ValueError("Couldn't parse matrix power. Example: matrix [[1,2],[3,4]] to the power 3.")
    power_match = re.findall(r"power\s+([+-]?\d+)\b", command, flags=re.IGNORECASE)
    if not power_match:
        raise ValueError("Couldn't detect power value. Use 'to the power X'.")
    power = int(power_match[0])
    matrix = _sympify_list_literal(matches[0])
    return matrix, power


def extract_expression(command: str):
    """Extract a SymPy expression; supports '^' -> '**' translation."""
    try:
        m = re.search(r"(integrate|differentiate|derivative|simplify|solve|limit)?\s*(of)?\s*(.*)", command, re.IGNORECASE)
        expr_text = m.group(3).strip() if m else command
        expr_text = expr_text.replace("^", "**")
        return sympify(expr_text)
    except Exception:
        raise ValueError("Couldn't parse expression. Please provide a valid math expression.")


def _sympify_bound(s: str):
    s = s.strip()
    low = s.lower()
    if low in ("infinity", "+infinity", "inf", "+inf", "∞", "+∞"):
        return oo
    if low in ("-infinity", "-inf", "-∞"):
        return -oo
    return sympify(s)


def extract_bounds(command: str):
    """
    Parse definite integral bounds: supports forms like
    'integrate <expr> wrt x from a to b' or 'integrate <expr> from a to b'
    Returns (expr, a, b, var_or_none)
    """
    try:
        text = command.replace("^", "**")
        # Capture var (optional) after 'wrt' or 'with respect to'
        var_match = re.search(r"\b(wrt|with\s+respect\s+to)\s+([a-zA-Z\u03B1-\u03C9]+)\b", text, flags=re.IGNORECASE)
        var = Symbol(var_match.group(2)) if var_match else None

        if " from " not in text.lower() or " to " not in text.lower():
            # fallback to indefinite
            return extract_expression(command), None, None, var

        before_from, after_from = re.split(r"\bfrom\b", text, maxsplit=1, flags=re.IGNORECASE)
        # Extract expression after 'integrate' (if present)
        expr_part = re.split(r"\bintegrate\b", before_from, maxsplit=1, flags=re.IGNORECASE)
        expr_text = (expr_part[1] if len(expr_part) > 1 else before_from).strip()
        expr = sympify(expr_text)

        a_str, b_str = re.split(r"\bto\b", after_from, maxsplit=1, flags=re.IGNORECASE)
        a = _sympify_bound(a_str)
        b = _sympify_bound(b_str)
        return expr, a, b, var
    except Exception:
        # Fallback to indefinite integral parse
        return extract_expression(command), None, None, None


def extract_limit_info(command: str):
    """
    Parse limit like:
    'limit of <expr> as x approaches 0'
    Returns (expr, var, point) with correct handling for ±infinity.
    """
    try:
        text = command.replace("^", "**")
        # Extract 'limit of <expr> as'
        if "limit of" not in text.lower() or " approaches " not in text.lower():
            raise ValueError("Couldn't extract limit expression or approach point.")
        expr_raw = re.split(r"\blimit\s+of\b", text, flags=re.IGNORECASE)[1]
        expr_raw = re.split(r"\bas\b", expr_raw, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        expr = sympify(expr_raw)

        # Extract var and approach value
        after_as = re.split(r"\bas\b", text, maxsplit=1, flags=re.IGNORECASE)[1]
        # forms: 'x approaches 0' or 'y → ∞'
        var_match = re.search(r"\b([a-zA-Z\u03B1-\u03C9]+)\b\s*(approaches|→)\s*(.+)$", after_as, flags=re.IGNORECASE)
        if not var_match:
            raise ValueError("Couldn't detect the variable or approach value.")
        var = Symbol(var_match.group(1))
        point_raw = var_match.group(3).strip()

        # map infinity tokens
        low = point_raw.lower()
        if any(tok in low for tok in ["infinity", "∞", "inf"]):
            point = -oo if any(tok in low for tok in ["-infinity", "-∞", "-inf"]) else oo
        else:
            point = sympify(point_raw)

        return expr, var, point
    except Exception:
        raise ValueError("Couldn't extract limit expression or approach point.")
