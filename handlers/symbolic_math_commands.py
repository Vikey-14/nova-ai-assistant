import sympy as sp
from sympy import (
    symbols, diff, integrate, solve, sympify, simplify, limit, Symbol, Matrix,
    factor, degree, sqrt, cancel, expand, trigsimp, expand_log, logcombine, expand_trig
)
import re

# ✅ Lazy import to avoid circular dependency
def get_utils():
    from utils import _speak_multilang, logger, gui_callback
    return _speak_multilang, logger, gui_callback


def handle_symbolic_math(command: str):
    _speak_multilang, logger, gui_callback = get_utils()

    try:
        command = command.lower()
        # ✅ Extract user-requested variable via "wrt" if present
        override_match = re.search(r"wrt\s+([a-zA-Z\u03B1-\u03C9]+)", command)

        expr = extract_expression(command)
        sym_expr = sympify(expr)

        free_syms = list(sym_expr.free_symbols)

        if override_match:
            var = Symbol(override_match.group(1))
        else:
            var = free_syms[0] if free_syms else symbols('x')  # Fallback to 'x' if none found

        # Initialize
        result = None
        solution_en = solution_hi = solution_fr = solution_es = solution_de = ""

        # 🎯 Differentiation
        if "differentiate" in command or "derivative" in command:
            try:
                expr = extract_expression(command)
                sym_expr = sympify(expr)
                result = diff(sym_expr, var)

                # 🔍 Try to break down term-by-term for visible GUI steps
                stepwise = f"📘 Steps:\n1. Expression: {expr}\n2. Differentiate term-by-term:\n"
                try:
                    if sym_expr.is_Add:
                        for term in sym_expr.args:
                            d_term = diff(term, var)
                            stepwise += f"   d/d{var}({term}) = {d_term}\n"
                    elif sym_expr.is_Mul or sym_expr.is_Pow or sym_expr.is_Function:
                        d_term = diff(sym_expr, var)
                        stepwise += f"   Applied chain/product rule where necessary\n"
                        stepwise += f"   d/d{var}({expr}) = {d_term}\n"
                    else:
                        d_term = diff(sym_expr, var)
                        stepwise += f"   d/d{var}({expr}) = {d_term}\n"
                except Exception as e:
                    stepwise += f"   Couldn't generate term-wise breakdown: {e}\n"

                stepwise += f"3. Final result: {result}"

                # 🌍 Multilingual summaries
                solution_en = (
                    f"Step 1: You asked to differentiate the expression: {expr}\n"
                    f"Step 2: We calculated the derivative with respect to {var}\n"
                    f"Result: {result}"
                )
                solution_hi = (
                    f"चरण 1: आपने {expr} का अवकलन करने को कहा\n"
                    f"चरण 2: हमने {var} के सापेक्ष इसका अवकलज निकाला\n"
                    f"परिणाम: {result}"
                )
                solution_fr = (
                    f"Étape 1 : Vous avez demandé de dériver l'expression : {expr}\n"
                    f"Étape 2 : Nous avons calculé la dérivée par rapport à {var}\n"
                    f"Résultat : {result}"
                )
                solution_es = (
                    f"Paso 1: Pediste derivar la expresión: {expr}\n"
                    f"Paso 2: Calculamos la derivada con respecto a {var}\n"
                    f"Resultado: {result}"
                )
                solution_de = (
                    f"Schritt 1: Du hast darum gebeten, den Ausdruck {expr} zu differenzieren\n"
                    f"Schritt 2: Wir haben die Ableitung bezüglich {var} berechnet\n"
                    f"Ergebnis: {result}"
                )

                _speak_multilang(
                    f"The answer is: {result}. You’ll find the full solution in the output below.",
                    hi=f"उत्तर है: {result}। पूरा समाधान नीचे आउटपुट में है।",
                    fr=f"La réponse est : {result}. La solution complète est ci-dessous.",
                    es=f"La respuesta es: {result}. La solución completa está abajo.",
                    de=f"Die Antwort ist: {result}. Die vollständige Lösung steht unten.",
                    log_command="Differentiation"
                )
                if gui_callback:
                    gui_callback(result=result, solution_en=solution_en, stepwise=stepwise)

            except Exception as e:
                _speak_multilang(
                    "The result is: Unable to differentiate. You’ll find the explanation in the output below.",
                    hi="परिणाम: अवकलन नहीं किया जा सका। विवरण नीचे आउटपुट में है।",
                    fr="Le résultat est : échec de la dérivation. Voir les détails ci-dessous.",
                    es="El resultado es: no se pudo derivar. Explicación abajo.",
                    de="Das Ergebnis ist: nicht ableitbar. Details unten.",
                    log_command=f"Differentiation error: {str(e)}"
                )
                if gui_callback:
                    gui_callback(
                        result="❌ Error",
                        solution_en="Differentiation failed due to an invalid expression or unsupported symbolic form.",
                        stepwise=f"⚠️ Error: {str(e)}"
                    )

        # ∫ Integration (definite or indefinite)
        elif "integrate" in command or "integral" in command:
            try:
                expr, a, b = extract_bounds(command)
                sym_expr = sympify(expr)

                stepwise = ""
                solution_en = solution_hi = solution_fr = solution_es = solution_de = ""

                if a is not None and b is not None:
                    # ✅ Definite Integral
                    result = integrate(sym_expr, (var, a, b))
                    antiderivative = integrate(sym_expr, var)
                    F_upper = antiderivative.subs(var, b)
                    F_lower = antiderivative.subs(var, a)
                    difference = F_upper - F_lower

                    stepwise = (
                        f"📘 Steps:\n"
                        f"1. Expression: {expr}\n"
                        f"2. Definite integral:\n"
                        f"   ∫₍{a}₎⁽{b}⁾ {sym_expr} d{var} = [{antiderivative}]₍{a}₎⁽{b}⁾ = ({F_upper}) - ({F_lower}) = {difference}\n"
                        f"3. Final result: {result}"
                    )

                    solution_en = (
                        f"Step 1: You asked to integrate the expression: {expr}\n"
                        f"Step 2: We integrated it from {a} to {b} with respect to {var}\n"
                        f"Result: {result}"
                    )
                    solution_hi = (
                        f"चरण 1: आपने {expr} को इंटीग्रेट करने को कहा\n"
                        f"चरण 2: हमने इसे {a} से {b} तक {var} के सापेक्ष इंटीग्रेट किया\n"
                        f"परिणाम: {result}"
                    )
                    solution_fr = (
                        f"Étape 1 : Vous avez demandé d'intégrer l'expression : {expr}\n"
                        f"Étape 2 : Intégrée de {a} à {b} par rapport à {var}\n"
                        f"Résultat : {result}"
                    )
                    solution_es = (
                        f"Paso 1: Pediste integrar: {expr}\n"
                        f"Paso 2: Integramos de {a} a {b} respecto a {var}\n"
                        f"Resultado: {result}"
                    )
                    solution_de = (
                        f"Schritt 1: Du wolltest {expr} integrieren\n"
                        f"Schritt 2: Wir integrierten von {a} bis {b} nach {var}\n"
                        f"Ergebnis: {result}"
                    )

                else:
                    # ✅ Indefinite Integral
                    result = integrate(sym_expr, var)
                    stepwise = f"📘 Steps:\n1. Expression: {expr}\n2. Indefinite integral term-by-term:\n"

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
                        f"Step 1: You asked to integrate the expression: {expr}\n"
                        f"Step 2: We performed an indefinite integral with respect to {var}\n"
                        f"Result: {result}"
                    )
                    solution_hi = (
                        f"चरण 1: आपने {expr} को इंटीग्रेट करने को कहा\n"
                        f"चरण 2: हमने इसे {var} के सापेक्ष अनिश्चित रूप से इंटीग्रेट किया\n"
                        f"परिणाम: {result}"
                    )
                    solution_fr = (
                        f"Étape 1 : Vous avez demandé d'intégrer l'expression : {expr}\n"
                        f"Étape 2 : Intégrale indéfinie par rapport à {var}\n"
                        f"Résultat : {result}"
                    )
                    solution_es = (
                        f"Paso 1: Pediste integrar: {expr}\n"
                        f"Paso 2: Integral indefinida respecto a {var}\n"
                        f"Resultado: {result}"
                    )
                    solution_de = (
                        f"Schritt 1: Du wolltest {expr} integrieren\n"
                        f"Schritt 2: Wir führten eine unbestimmte Integration bezüglich {var} durch\n"
                        f"Ergebnis: {result}"
                    )

                _speak_multilang(
                    f"The answer is: {result}. You’ll find the full solution in the output below.",
                    hi=f"उत्तर है: {result}। पूरा समाधान नीचे आउटपुट में है।",
                    fr=f"La réponse est : {result}. La solution complète est ci-dessous.",
                    es=f"La respuesta es: {result}. La solución completa está abajo.",
                    de=f"Die Antwort ist: {result}. Die vollständige Lösung steht unten.",
                    log_command="Integration"
                )
                if gui_callback:
                    gui_callback(result=result, solution_en=solution_en, stepwise=stepwise)

            except Exception as e:
                _speak_multilang(
                    "The result is: Unable to integrate. You’ll find the explanation in the output below.",
                    hi="परिणाम: इंटीग्रेट नहीं किया जा सका। विवरण नीचे आउटपुट में है।",
                    fr="Le résultat est : échec de l'intégration. Voir les détails ci-dessous.",
                    es="El resultado es: no se pudo integrar. Explicación abajo.",
                    de="Das Ergebnis ist: nicht integrierbar. Details unten.",
                    log_command=f"Integration error: {str(e)}"
                )
                if gui_callback:
                    gui_callback(
                        result="❌ Error",
                        solution_en="Integration failed due to an invalid expression or unsupported symbolic form.",
                        stepwise=f"⚠️ Error: {str(e)}"
                    )

        # 🧮 Simplification
        elif "simplify" in command:
            try:
                expr = extract_expression(command)
                sym_expr = sympify(expr)

                # 🔍 Auto-detect symbolic variable (if any)
                free_symbols = sym_expr.free_symbols
                var = sorted(free_symbols, key=str)[0] if free_symbols else None

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

                # 🌍 Translations
                solution_en = (
                    f"Step 1: You asked to simplify the expression: {expr}\n"
                    f"Step 2: We applied identities and simplification rules\n"
                    f"Result: {simplified}"
                )
                solution_hi = (
                    f"चरण 1: आपने इस समीकरण को सरल बनाने को कहा: {expr}\n"
                    f"चरण 2: हमने पहचान और नियमों के माध्यम से इसे सरल किया\n"
                    f"परिणाम: {simplified}"
                )
                solution_fr = (
                    f"Étape 1 : Vous avez demandé de simplifier l'expression : {expr}\n"
                    f"Étape 2 : Nous avons appliqué des identités et des règles\n"
                    f"Résultat: {simplified}"
                )
                solution_es = (
                    f"Paso 1: Pediste simplificar la expresión: {expr}\n"
                    f"Paso 2: Aplicamos identidades y reglas\n"
                    f"Resultado: {simplified}"
                )
                solution_de = (
                    f"Schritt 1: Du hast darum gebeten, den Ausdruck zu vereinfachen: {expr}\n"
                    f"Schritt 2: Wir haben Identitäten und Regeln angewendet\n"
                    f"Ergebnis: {simplified}"
                )

                if gui_callback:
                    gui_callback(result=str(simplified), solution_en=solution_en, stepwise=stepwise)

                _speak_multilang(
                    f"The answer is {simplified}. You’ll find the full steps in the output below.",
                    hi=f"उत्तर है {simplified}। पूरा समाधान नीचे आउटपुट में दिखाया गया है।",
                    fr=f"La réponse est {simplified}. La solution complète est affichée ci-dessous.",
                    es=f"La respuesta es {simplified}. La solución completa se muestra a continuación.",
                    de=f"Die Antwort ist {simplified}. Die vollständige Lösung steht unten."
                )

            except Exception as e:
                logger.error(f"[❌ SIMPLIFY FAILED] {e}")
                _speak_multilang(
                    "I couldn't simplify the expression. Please check your input.",
                    hi="मैं इस समीकरण को सरल नहीं कर सकी। कृपया इनपुट जांचें।",
                    fr="Je n'ai pas pu simplifier l'expression. Veuillez vérifier votre saisie.",
                    es="No pude simplificar la expresión. Por favor, verifica tu entrada.",
                    de="Ich konnte den Ausdruck nicht vereinfachen. Bitte überprüfe deine Eingabe.",
                    log_command="Simplification failed"
                )
                gui_callback(
                    result="❌ Error",
                    solution_en="An error occurred while simplifying. Make sure the expression is valid and uses correct syntax.",
                    stepwise="⚠️ Error: Could not simplify the input. Ensure the expression is valid and uses recognizable mathematical format."
                )

        # 🚦 Limit
        elif "limit" in command and "approaches" in command:
            try:
                expr, point = extract_limit_info(command)
                sym_expr = sympify(expr)

                # 🔍 Auto-detect variable used in the expression
                free_symbols = sym_expr.free_symbols
                if not free_symbols:
                    raise ValueError("No variable found for limit.")
                var = sorted(free_symbols, key=str)[0]

                result = limit(sym_expr, var, point)

                # 🧠 Step-by-step derivation
                steps = [f"1. Original expression:\n   {sym_expr}"]

                # 2️⃣ Direct substitution
                substituted = sym_expr.subs(var, point)
                steps.append(f"2. Substituting {var} = {point}:")
                steps.append(f"   → {substituted}")

                # 3️⃣ Indeterminate form check
                indeterminate = substituted.has(sp.nan) or substituted == sp.zoo
                if indeterminate:
                    steps.append("3. The substitution gave an indeterminate form like 0/0 or ∞/∞.")
                else:
                    steps.append("3. The substitution gave a valid finite result.")

                # 4️⃣ Trigonometric simplification
                trig_simplified = trigsimp(sym_expr)
                if trig_simplified != sym_expr:
                    steps.append("4. Applying trigonometric identities:")
                    steps.append(f"   → {trig_simplified}")
                else:
                    steps.append("4. No trigonometric identity simplification applied.")

                # 5️⃣ Logarithmic simplification
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

                # 6️⃣ Factoring (for removable discontinuities)
                factored = factor(sym_expr)
                if factored != sym_expr:
                    steps.append("6. Applying algebraic factoring:")
                    steps.append(f"   → {factored}")
                    simplified = cancel(factored)
                    steps.append("7. Cancelling common terms (if any):")
                    steps.append(f"   → {simplified}")
                    steps.append(f"8. Substituting {var} = {point} again:")
                    steps.append(f"   → {simplified.subs(var, point)}")
                else:
                    steps.append("6. No factoring or cancellation applied.")

                # 9️⃣ Final result
                steps.append(f"9. ✅ Final limit result:\n   {result}")
                stepwise = "📘 Steps:\n" + "\n".join(steps)

                # 🌍 Multilingual Summary
                solution_en = (
                    f"Step 1: You asked to evaluate the limit of: {sym_expr} as {var} → {point}\n"
                    f"Step 2: We applied substitutions and simplifications\n"
                    f"Result: {result}"
                )
                solution_hi = (
                    f"चरण 1: आपने {sym_expr} का {var} → {point} पर सीमांक मान मांगा\n"
                    f"चरण 2: हमने इसे सरल किया और मान निकाला\n"
                    f"परिणाम: {result}"
                )
                solution_fr = (
                    f"Étape 1 : Vous avez demandé la limite de : {sym_expr} lorsque {var} → {point}\n"
                    f"Étape 2 : Substitué et simplifié si nécessaire\n"
                    f"Résultat: {result}"
                )
                solution_es = (
                    f"Paso 1: Pediste el límite de: {sym_expr} cuando {var} → {point}\n"
                    f"Paso 2: Sustituimos y simplificamos cuando fue necesario\n"
                    f"Resultado: {result}"
                )
                solution_de = (
                    f"Schritt 1: Du hast den Grenzwert von {sym_expr} für {var} → {point} angefordert\n"
                    f"Schritt 2: Wir haben vereinfacht und berechnet\n"
                    f"Ergebnis: {result}"
                )

                if gui_callback:
                    gui_callback(result=result, solution_en=solution_en, stepwise=stepwise)

                _speak_multilang(
                    f"The answer is {result}. You’ll find the full solution in the output below.",
                    hi=f"उत्तर है {result}। पूरा समाधान नीचे आउटपुट में दिखाया गया है।",
                    fr=f"La réponse est {result}. La solution complète est affichée ci-dessous.",
                    es=f"La respuesta es {result}. La solución completa se muestra a continuación.",
                    de=f"Die Antwort ist {result}. Die vollständige Lösung steht unten."
                )

            except Exception as e:
                _speak_multilang(
                    "I couldn't evaluate the limit. Please check your input.",
                    hi="मैं सीमांक मान की गणना नहीं कर पाई। कृपया इनपुट जांचें।",
                    fr="Je n'ai pas pu évaluer la limite. Veuillez vérifier votre saisie.",
                    es="No pude evaluar el límite. Por favor, verifica tu entrada.",
                    de="Ich konnte den Grenzwert nicht berechnen. Bitte überprüfe deine Eingabe.",
                    log_command="Limit failed"
                )
                gui_callback(
                    result="❌ Error",
                    solution_en="An error occurred while evaluating the limit. Make sure the expression is valid and uses only one variable.",
                    stepwise="⚠️ Error: Could not compute limit. Ensure expression is valid and uses a single symbolic variable."
                )

        # 🧩 Solve Equations
        elif "solve" in command or "find x" in command:
            try:
                expr = extract_expression(command)
                sym_expr = sympify(expr)

                # 🔍 Auto-detect variable from expression
                free_symbols = sym_expr.free_symbols
                if not free_symbols:
                    raise ValueError("No variable found to solve for.")
                var = sorted(free_symbols, key=str)[0]

                # 🧠 Pre-simplification
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

                # 🌍 Translated Summary
                solution_en = (
                    f"Step 1: You asked to solve the equation: {expr} = 0\n"
                    f"Step 2: We simplified using trigonometric/log rules (if applicable)\n"
                    f"Result: {result}"
                )
                solution_hi = (
                    f"चरण 1: आपने समीकरण हल करने को कहा: {expr} = 0\n"
                    f"चरण 2: हमने त्रिकोणमितीय/लघुगणकीय नियमों का उपयोग किया (यदि लागू हो)\n"
                    f"परिणाम: {result}"
                )
                solution_fr = (
                    f"Étape 1 : Vous avez demandé à résoudre l'équation : {expr} = 0\n"
                    f"Étape 2 : Nous avons appliqué les règles trig/log si nécessaire\n"
                    f"Résultat : {result}"
                )
                solution_es = (
                    f"Paso 1: Pediste resolver la ecuación: {expr} = 0\n"
                    f"Paso 2: Aplicamos reglas trigonométricas/logarítmicas si correspondía\n"
                    f"Resultado: {result}"
                )
                solution_de = (
                    f"Schritt 1: Du hast gebeten, die Gleichung zu lösen: {expr} = 0\n"
                    f"Schritt 2: Wir haben trigonometrische/logarithmische Regeln angewendet\n"
                    f"Ergebnis: {result}"
                )

                gui_callback(result=result, solution_en=solution_en, stepwise=stepwise)

                _speak_multilang(
                    f"The answer is {result}. You’ll find the full solution in the output below.",
                    hi=f"उत्तर है {result}। पूरा समाधान नीचे आउटपुट में दिखाया गया है।",
                    fr=f"La réponse est {result}. La solution complète est affichée ci-dessous.",
                    es=f"La respuesta es {result}. La solución completa se muestra a continuación.",
                    de=f"Die Antwort ist {result}. Die vollständige Lösung steht unten."
                )

            except Exception as e:
                _speak_multilang(
                    "I couldn't solve the equation. Please check your input.",
                    hi="मैं समीकरण हल नहीं कर पाई। कृपया इनपुट जांचें।",
                    fr="Je n'ai pas pu résoudre l'équation. Veuillez vérifier votre saisie.",
                    es="No pude resolver la ecuación. Por favor, verifica tu entrada.",
                    de="Ich konnte die Gleichung nicht lösen. Bitte überprüfe deine Eingabe.",
                    log_command="Solve failed"
                )
                gui_callback(
                    result="❌ Error",
                    solution_en="An error occurred while solving the equation. Please make sure it's a valid symbolic expression like 'x^2 - 4 = 0'.",
                    stepwise="⚠️ Error: Could not solve the given equation. Ensure it is a valid expression in one variable."
                )

        # 🔁 Matrix Operations – Inverse of a Matrix
        elif "inverse of matrix" in command or "matrix inverse" in command:
            try:
                matrix_data = extract_matrix(command)
                matrix_data = [[sympify(cell) for cell in row] for row in matrix_data]
                A = Matrix(matrix_data)

                # ✅ Check square matrix
                rows, cols = A.shape
                if rows != cols:
                    raise ValueError("Matrix must be square to find its inverse.")

                determinant = trigsimp(logcombine(A.det(), force=True))
                if determinant == 0:
                    raise ValueError("Matrix is not invertible (determinant = 0).")

                cofactor = A.cofactor_matrix()
                adjugate = cofactor.transpose()
                inverse_matrix = trigsimp(logcombine(A.inv(), force=True))

                # 🧠 Matrix formatter
                def format_matrix(M):
                    return "\n".join([
                        "   | " + "  ".join(str(trigsimp(logcombine(c, force=True))) for c in row) + " |"
                        for row in M.tolist()
                    ])

                # 🔍 Det expansion (only for 2x2 or 3x3)
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
                    det_steps += f"   Final determinant = {determinant}\n"

                # 🔎 Cofactor calculation (all cells with minors)
                cofactor_steps = ""
                for i in range(rows):
                    for j in range(cols):
                        minor = A.minor_submatrix(i, j)
                        sign = (-1) ** (i + j)
                        cofactor_val = sign * minor.det()
                        cofactor_val = trigsimp(logcombine(cofactor_val, force=True))
                        cofactor_steps += f"   C[{i+1},{j+1}] = (-1)^({i+1}+{j+1}) × det({minor.tolist()}) = {cofactor_val}\n"

                # 📘 Full breakdown for popup
                steps_text = (
                    f"📘 Steps:\n\n"
                    f"1. Original matrix:\n{format_matrix(A)}\n\n"
                    f"2. Determinant Calculation:\n{det_steps or '   Determinant computed'}\n"
                    f"   det(A) = {determinant}\n\n"
                    f"3. Compute all cofactors:\n{cofactor_steps}\n"
                    f"   Cofactor Matrix =\n{format_matrix(cofactor)}\n\n"
                    f"4. Transpose of cofactor matrix → adjugate:\n{format_matrix(adjugate)}\n\n"
                    f"5. Apply inverse formula:\n"
                    f"   A⁻¹ = (1 / {determinant}) × adjugate\n\n"
                    f"6. Final Result:\n{format_matrix(inverse_matrix)}"
                )

                _speak_multilang(
                    f"The answer is {inverse_matrix.tolist()}. You’ll find the full solution in the output below.",
                    hi=f"उत्तर है {inverse_matrix.tolist()}। पूरा समाधान नीचे आउटपुट में दिखाया गया है।",
                    fr=f"La réponse est {inverse_matrix.tolist()}. La solution complète est affichée ci-dessous.",
                    es=f"La respuesta es {inverse_matrix.tolist()}. La solución completa se muestra a continuación.",
                    de=f"Die Antwort ist {inverse_matrix.tolist()}. Die vollständige Lösung steht unten.",
                    log_command="Matrix inverse calculated"
                )

                gui_callback(
                    result=str(inverse_matrix.tolist()),
                    solution_en="Matrix inverse computed using adjugate / determinant.",
                    stepwise=steps_text
                )

            except Exception as e:
                _speak_multilang(
                    "The result is: Unable to calculate. You’ll find the explanation in the output below.",
                    hi="परिणाम: इनवर्स निकालना संभव नहीं है। विवरण नीचे आउटपुट में है।",
                    fr="Le résultat est : inverse impossible à calculer. Voir les détails ci-dessous.",
                    es="El resultado es: no se pudo calcular la inversa. Ver detalles abajo.",
                    de="Das Ergebnis ist: Inverse nicht berechenbar. Details unten.",
                    log_command=f"Matrix inverse failed: {str(e)}"
                )
                gui_callback(
                    result="❌ Not Invertible",
                    solution_en="Matrix inverse not possible.",
                    stepwise=f"📘 Steps:\n\n❌ Error: Matrix inverse not possible.\nReason: {str(e)}"
                )

        # 🔁 Matrix Operations - Transpose of a Matrix
        elif "transpose of matrix" in command or "matrix transpose" in command:
            try:
                matrix_data = extract_matrix(command)
                matrix_data = [[sympify(cell) for cell in row] for row in matrix_data]
                A = Matrix(matrix_data)
                result = A.T

                # 🧠 Matrix formatter (with trig/log simplification)
                def format_matrix(M):
                    return "\n".join([
                        "   | " + "  ".join(str(trigsimp(logcombine(c, force=True))) for c in row) + " |"
                        for row in M.tolist()
                    ])

                # 📘 Step-by-step explanation in English (for GUI)
                steps = [f"1. Original matrix:\n{format_matrix(A)}\n"]
                rows, cols = A.shape
                for i in range(rows):
                    row_values = [str(trigsimp(logcombine(A[i, j], force=True))) for j in range(cols)]
                    steps.append(f"   Row {i + 1}: {'  '.join(row_values)}")

                steps.append("\n2. Swap rows with columns:")
                for i in range(cols):
                    col_values = [str(trigsimp(logcombine(A[j, i], force=True))) for j in range(rows)]
                    steps.append(f"   New Row {i + 1} (was Column {i + 1}): {'  '.join(col_values)}")

                steps.append(f"\n3. Final transposed matrix:\n{format_matrix(result)}")
                stepwise = "📘 Steps:\n" + "\n".join(steps)

                result_str = str(result.tolist())

                solution_en = (
                    f"Step 1: You asked for the transpose of the matrix: {matrix_data}\n"
                    f"Step 2: We swapped rows and columns\n"
                    f"Result: {result_str}"
                )

                _speak_multilang(
                    f"The answer is {result.tolist()}. You’ll find the full steps in the output below.",
                    hi=f"उत्तर है {result.tolist()}। पूरा विवरण नीचे आउटपुट में है।",
                    fr=f"La réponse est {result.tolist()}. Voir les étapes ci-dessous.",
                    es=f"La respuesta es {result.tolist()}. Consulta los pasos abajo.",
                    de=f"Die Antwort ist {result.tolist()}. Die vollständigen Schritte findest du unten.",
                    log_command="Matrix transpose calculated"
                )

                gui_callback(result=result_str, solution_en=solution_en, stepwise=stepwise)

            except Exception as e:
                _speak_multilang(
                    "Sorry, I couldn't calculate the transpose.",
                    hi="क्षमा करें, मैं ट्रांसपोज़ की गणना नहीं कर सकी।",
                    fr="Désolé, je n'ai pas pu calculer la transposée.",
                    es="Lo siento, no pude calcular la transpuesta.",
                    de="Entschuldigung, ich konnte die Transponierte nicht berechnen.",
                    log_command=f"Matrix transpose failed: {str(e)}"
                )
                gui_callback(
                    result="❌ Transpose Failed",
                    solution_en="Matrix transpose failed.",
                    stepwise=f"📘 Steps:\n\n❌ Error: Matrix transpose failed.\nReason: {str(e)}"
                )

        # 🔢 Determinant of a Matrix
        elif "determinant of matrix" in command or "matrix determinant" in command:
            try:
                matrix_data = extract_matrix(command)
                matrix_data = [[sympify(cell) for cell in row] for row in matrix_data]
                matrix = Matrix(matrix_data)
                result = matrix.det()

                # 📐 Matrix visual display (with simplification)
                def format_matrix_grid(mat):
                    rows = ["  " + "  ".join(str(trigsimp(logcombine(cell, force=True))) for cell in row)
                            for row in mat.tolist()]
                    return f"⎡ {rows[0]} ⎤\n" + \
                           "\n".join([f"⎢ {row} ⎥" for row in rows[1:-1]]) + \
                           f"\n⎣ {rows[-1]} ⎦"

                visual_matrix = format_matrix_grid(matrix)

                # 📘 Step-by-step breakdown
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
                    steps.append(f"\n   Compute each term:")
                    steps.append(f"     ei − fh = ({e}×{i}) − ({f}×{h}) = {e*i} − {f*h} = {ei_fh}")
                    steps.append(f"     di − fg = ({d}×{i}) − ({f}×{g}) = {d*i} − {f*g} = {di_fg}")
                    steps.append(f"     dh − eg = ({d}×{h}) − ({e}×{g}) = {d*h} − {e*g} = {dh_eg}")
                    steps.append(f"\n   Plug into formula:")
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

                gui_callback(result=result, solution_en=solution_en, stepwise=stepwise)

                _speak_multilang(
                    f"The answer is {result}. You’ll find the full solution in the output below.",
                    hi=f"उत्तर है {result}। पूरा समाधान नीचे आउटपुट में दिखाया गया है।",
                    fr=f"La réponse est {result}. La solution complète est affichée ci-dessous.",
                    es=f"La respuesta es {result}. La solución completa se muestra a continuación.",
                    de=f"Die Antwort ist {result}. Die vollständige Lösung steht unten.",
                    log_command="Matrix determinant calculated"
                )

            except Exception as e:
                _speak_multilang(
                    "I couldn't compute the determinant. Please make sure you gave a valid square matrix.",
                    hi="मैं डिटर्मिनेंट नहीं निकाल पाई। कृपया सुनिश्चित करें कि आपने एक वैध स्क्वेयर मैट्रिक्स दिया है।",
                    fr="Je n'ai pas pu calculer le déterminant. Vérifiez que la matrice est carrée.",
                    es="No pude calcular el determinante. Asegúrate de que la matriz sea cuadrada.",
                    de="Ich konnte die Determinante nicht berechnen. Bitte stelle sicher, dass die Matrix quadratisch ist.",
                    log_command="Matrix determinant failed"
                )
                gui_callback(
                    result="❌ Error",
                    solution_en="An error occurred. Make sure your matrix is square (e.g., 2x2 or 3x3). Determinant can only be calculated for square matrices.",
                    stepwise="⚠️ Error: Determinant undefined for non-square matrices. Please enter a valid square matrix like 2x2 or 3x3."
                )

        # 🔁 Matrix Operations – Matrix Multiplication
        elif "multiply" in command and "with" in command:
            try:
                m1, m2 = extract_two_matrices(command)

                # ✅ Support symbolic trig/log expressions in matrix entries
                m1 = [[trigsimp(logcombine(sympify(cell), force=True)) for cell in row] for row in m1]
                m2 = [[trigsimp(logcombine(sympify(cell), force=True)) for cell in row] for row in m2]

                A = Matrix(m1)
                B = Matrix(m2)

                # ❌ Dimension check
                if A.shape[1] != B.shape[0]:
                    raise ValueError("Number of columns in A must equal number of rows in B for multiplication.")

                result = A * B
                rows_A, cols_A = A.shape
                _, cols_B = B.shape

                # 🧠 Build detailed step-by-step explanation
                steps = [
                    f"📘 Steps:\n\n1. Original matrices:",
                    f"   A = {A.tolist()}",
                    f"   B = {B.tolist()}",
                    f"\n2. Matrix multiplication rule:",
                    f"   C[i][j] = sum(A[i][k] * B[k][j])\n",
                    f"3. Compute each cell C[i][j] step-by-step:"
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

                _speak_multilang(
                    f"The answer is {result.tolist()}. You’ll find the full solution in the output below.",
                    hi=f"उत्तर है {result.tolist()}। पूरा समाधान नीचे आउटपुट में दिखाया गया है।",
                    fr=f"La réponse est {result.tolist()}. La solution complète est affichée ci-dessous.",
                    es=f"La respuesta es {result.tolist()}. La solución completa se muestra a continuación.",
                    de=f"Die Antwort ist {result.tolist()}. Die vollständige Lösung steht unten.",
                    log_command="Matrix multiplication successful"
                )

                solution_en = (
                    f"Step 1: You asked to multiply matrices:\n  A = {m1}\n  B = {m2}\n"
                    f"Step 2: We applied the matrix multiplication rules.\n"
                    f"Result: {result.tolist()}"
                )
                gui_callback(result=str(result.tolist()), solution_en=solution_en, stepwise=stepwise)

            except Exception as e:
                _speak_multilang(
                    "Matrix multiplication failed. Please make sure dimensions are correct.",
                    hi="मैट्रिक्स गुणा विफल रहा। कृपया सुनिश्चित करें कि आकार सही हैं।",
                    fr="Échec de la multiplication. Vérifiez les dimensions.",
                    es="Falló la multiplicación de matrices. Verifica las dimensiones.",
                    de="Matrixmultiplikation fehlgeschlagen. Überprüfen Sie die Dimensionen.",
                    log_command=f"Matrix multiplication failed: {str(e)}"
                )
                gui_callback(
                    result="❌ Error",
                    solution_en="Matrix multiplication is not possible. The number of columns in A must equal the number of rows in B.",
                    stepwise=f"⚠️ Error: {str(e)}"
                )

        # 🔁 Matrix Operations – Rank of a Matrix
        elif "rank of matrix" in command:
            try:
                matrix_data = extract_matrix(command)

                # ✅ Support symbolic trig/log expressions in matrix entries
                matrix_data = [
                    [trigsimp(logcombine(sympify(cell), force=True)) for cell in row]
                    for row in matrix_data
                ]

                A = Matrix(matrix_data)
                original = A.tolist()

                steps = []
                steps.append("📘 Steps:\n")
                steps.append("1. Original matrix:")
                steps.append("   A =")
                for row in original:
                    steps.append(f"   {row}")

                # ✅ Manual row reduction with scalar multiplication shown
                steps.append("\n2. Perform row operations to get Row Echelon Form:")

                B = Matrix(A)
                m, n = B.shape
                row = 0

                for col in range(n):
                    if row >= m:
                        break

                    # Find pivot
                    if B[row, col] == 0:
                        for r in range(row + 1, m):
                            if B[r, col] != 0:
                                B.row_swap(row, r)
                                steps.append(f"   R{row+1} ↔ R{r+1}  (Swapped to make pivot non-zero)")
                                break

                    pivot = B[row, col]

                    if pivot != 0:
                        # Make pivot = 1
                        if pivot != 1:
                            old_row = B.row(row)
                            B.row_op(row, lambda v, j: v / pivot)
                            new_row = B.row(row)
                            steps.append(f"   R{row+1} → R{row+1} / {pivot}  (Make pivot = 1)")
                            steps.append(f"     ⇒ {pivot} × {old_row.tolist()[0]} = {[(pivot * v).evalf() for v in old_row]}")
                            steps.append(f"     ⇒ {[(pivot * v).evalf() for v in old_row]} ÷ {pivot} = {new_row.tolist()[0]}")

                        # Eliminate other rows in the same column
                        for r in range(m):
                            if r != row and B[r, col] != 0:
                                factor = B[r, col]
                                orig_r = B.row(r)
                                base_row = B.row(row)
                                multiplied = [(factor * v).evalf() for v in base_row]
                                B.row_op(r, lambda v, j: v - factor * B[row, j])
                                new_r = B.row(r)
                                steps.append(f"   R{r+1} → R{r+1} - ({factor})×R{row+1}")
                                steps.append(f"     ⇒ {factor} × {base_row.tolist()[0]} = {multiplied}")
                                steps.append(f"     ⇒ {orig_r.tolist()[0]} - {multiplied} = {new_r.tolist()[0]}")

                        row += 1

                steps.append("\n3. Row Echelon Form:")
                for row in B.tolist():
                    steps.append(f"   {row}")

                non_zero_rows = sum(1 for row in B.tolist() if any(val != 0 for val in row))
                steps.append(f"\n4. Number of non-zero rows: {non_zero_rows} ⇒ Rank = {non_zero_rows}")
                steps.append(f"\n✅ Final Answer: Rank = {non_zero_rows}")

                stepwise = "\n".join(steps)

                solution_en = (
                    f"Step 1: You asked for the rank of matrix: {matrix_data}\n"
                    f"Step 2: We applied row reduction method to count non-zero rows\n"
                    f"Result: {non_zero_rows}"
                )

                if gui_callback:
                    gui_callback(result=f"Rank = {non_zero_rows}", solution_en=solution_en, stepwise=stepwise)

                _speak_multilang(
                    f"The rank is {non_zero_rows}. You’ll find the full steps in the output below.",
                    hi=f"रैंक {non_zero_rows} है। पूरा समाधान नीचे आउटपुट में दिखाया गया है।",
                    fr=f"Le rang est {non_zero_rows}. Les étapes sont ci-dessous.",
                    es=f"El rango es {non_zero_rows}. Consulta los pasos abajo.",
                    de=f"Der Rang ist {non_zero_rows}. Die vollständigen Schritte findest du unten.",
                    log_command="Matrix rank calculation"
                )

            except Exception as e:
                _speak_multilang(
                    "Matrix rank calculation failed. Please check your input.",
                    hi="मैट्रिक्स रैंक की गणना विफल रही। कृपया इनपुट जांचें।",
                    fr="Le calcul du rang de la matrice a échoué. Vérifiez l'entrée.",
                    es="Error al calcular el rango de la matriz. Verifique su entrada.",
                    de="Rangberechnung fehlgeschlagen. Bitte Eingabe prüfen.",
                    log_command=f"Matrix rank calculation failed: {str(e)}"
                )
                if gui_callback:
                    gui_callback(
                        result="❌ Error",
                        solution_en="Matrix rank calculation failed due to invalid input or unsupported symbolic values.",
                        stepwise=f"⚠️ Error: {str(e)}"
                    )

        # 🔁 Matrix Operations – Eigenvalues of a Matrix
        elif "eigenvalues of matrix" in command:
            try:
                matrix_data = extract_matrix(command)

                # ✅ Support trig + log expressions in matrix entries
                matrix_data = [
                    [trigsimp(logcombine(sympify(cell), force=True)) for cell in row]
                    for row in matrix_data
                ]

                A = Matrix(matrix_data)

                # ✅ Square matrix check
                if A.shape[0] != A.shape[1]:
                    raise ValueError("Matrix must be square to compute eigenvalues.")

                n = A.shape[0]
                λ = Symbol('λ')
                I = Matrix.eye(n)
                A_lambda_I = A - λ * I
                char_poly = A_lambda_I.det()
                eigenvals = solve(char_poly, λ)
                eigenvals_rounded = [round(float(ev.evalf()), 2) for ev in eigenvals]

                # 🧾 Matrix formatting
                def format_matrix(M):
                    return "\n   | " + " |\n   | ".join("  ".join(str(el) for el in row) for row in M.tolist()) + " |"

                # 🧠 Verbose cofactor expansion for 3×3
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

                # 📘 Begin step-by-step output
                solution_steps = f"📘 Steps:\n\n1. Original Matrix:\n{format_matrix(A)}\n\n"
                solution_steps += f"2. Construct (A - λI):\n{format_matrix(A_lambda_I)}\n\n"

                if n == 2:
                    a, b = A[0, 0], A[0, 1]
                    c, d = A[1, 0], A[1, 1]
                    trace = a + d
                    determinant = a * d - b * c

                    solution_steps += (
                        f"3. Compute determinant of (A - λI):\n"
                        f"   = ({a}−λ)({d}−λ) − ({b})×({c})\n"
                        f"   = ({a}×{d}) − ({a}×λ) − ({d}×λ) + λ² − ({b}×{c})\n"
                        f"   = {a*d} − {a}λ − {d}λ + λ² − {b*c}\n"
                        f"   = λ² − ({trace})λ + ({determinant})\n\n"
                        f"4. Solve characteristic equation:\n"
                        f"   λ² − {trace}λ + {determinant} = 0\n"
                    )

                elif n == 3:
                    solution_steps += "3. Compute determinant of (A - λI) using cofactor expansion:\n"
                    solution_steps += cofactor_expansion_3x3_verbose(A_lambda_I) + "\n\n"
                    solution_steps += (
                        "4. Expand characteristic polynomial:\n"
                        f"   = {char_poly.expand()}\n"
                        f"   Solve: {char_poly} = 0\n"
                    )
                else:
                    raise ValueError("Currently only 2×2 and 3×3 matrices are supported for step-by-step derivation.")

                solution_steps += f"\n✅ Final Answer:\nEigenvalues = {eigenvals_rounded}"

                # 🌍 Multilingual summaries (keep speak); popup text is in solution_steps
                _speak_multilang(
                    f"The eigenvalues are {eigenvals_rounded}. You’ll find the full solution in the output below.",
                    hi=f"विशेष गुणांक हैं {eigenvals_rounded}। पूरा हल नीचे आउटपुट में है।",
                    fr=f"Les valeurs propres sont {eigenvals_rounded}. Voir la solution complète ci-dessous.",
                    es=f"Los eigenvalores son {eigenvals_rounded}. La solución completa está abajo.",
                    de=f"Die Eigenwerte sind {eigenvals_rounded}. Die vollständige Lösung steht unten."
                )

                gui_callback(
                    result=str(eigenvals_rounded),
                    solution_en="Eigenvalues (rounded to 2 decimals) computed via characteristic polynomial.",
                    stepwise=solution_steps
                )

            except Exception as e:
                error_msg = str(e)
                _speak_multilang(
                    "Sorry, I couldn't compute the eigenvalues. Please make sure it's a 2×2 or 3×3 square matrix.",
                    hi="क्षमा करें, मैं विशेष गुणांक की गणना नहीं कर सकी। कृपया सुनिश्चित करें कि मैट्रिक्स 2×2 या 3×3 की वर्गाकार हो।",
                    fr="Désolé, je n'ai pas pu calculer les valeurs propres. Assurez-vous que la matrice est carrée (2×2 ou 3×3).",
                    es="Lo siento, no pude calcular los eigenvalores. Asegúrese de que la matriz sea cuadrada (2×2 o 3×3).",
                    de="Entschuldigung, ich konnte die Eigenwerte nicht berechnen. Bitte stellen Sie sicher, dass die Matrix quadratisch ist (2×2 oder 3×3).",
                    log_command=error_msg
                )

                gui_callback(
                    result="❌ Error",
                    solution_en="Matrix eigenvalue computation failed. Ensure your matrix is 2×2 or 3×3 and all elements are valid expressions.",
                    stepwise=f"⚠️ Error: {str(e)}"
                )

        # 🔁 Matrix Operations – Identity of a Matrix
        elif "is identity matrix" in command or "check if identity matrix" in command or "whether identity matrix" in command:
            try:
                matrix_data = extract_matrix(command)

                # ✅ Step 0: Convert cells to symbolic and simplify trig/log
                matrix_data = [[trigsimp(logcombine(sympify(cell))) for cell in row] for row in matrix_data]
                A = Matrix(matrix_data)

                # ✅ Step 1: Matrix must be square
                if A.shape[0] != A.shape[1]:
                    raise ValueError("Matrix must be square to check identity.")

                n = A.shape[0]
                I = Matrix.eye(n)

                # ✅ Step 2: Analyze each element
                diag_issues = []
                off_diag_issues = []
                for i in range(n):
                    for j in range(n):
                        value = A[i, j]
                        if i == j and value != 1:
                            diag_issues.append(f"⛔ A[{i+1},{j+1}] = {value} ≠ 1 (Diagonal)")
                        elif i != j and value != 0:
                            off_diag_issues.append(f"⛔ A[{i+1},{j+1}] = {value} ≠ 0 (Off-Diagonal)")

                is_identity = not diag_issues and not off_diag_issues

                # 🧠 Matrix formatter
                def format_matrix(M):
                    return "\n".join(["   | " + "  ".join(f"{item}" for item in row) + " |" for row in M.tolist()])

                # ✅ Detailed explanation output
                if is_identity:
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
                        f"5. Therefore, the matrix meets all criteria for an identity matrix.\n\n"
                        f"✅ Final Result:\nThe given matrix **is** an identity matrix ✅"
                    )
                    result = "Yes"
                else:
                    mismatches = "\n".join(diag_issues + off_diag_issues)
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
                        f"5. The matrix does not meet identity matrix conditions.\n\n"
                        f"❌ Final Result:\nThe given matrix **is NOT** an identity matrix."
                    )
                    result = "No"

                _speak_multilang(
                    f"The result is: {result}. You’ll find the full solution in the output below.",
                    hi=f"परिणाम है: {result}. पूरा समाधान नीचे आउटपुट में है।",
                    fr=f"Le résultat est : {result}. La solution complète est ci-dessous.",
                    es=f"El resultado es: {result}. La solución completa está en la salida a continuación.",
                    de=f"Das Ergebnis ist: {result}. Die vollständige Lösung steht unten.",
                    log_command="Identity Matrix Check"
                )
                gui_callback(result=result, solution_en="Identity matrix check", stepwise=steps_text)

            except Exception as e:
                _speak_multilang(
                    "The result is: Unable to determine. You’ll find the explanation in the output below.",
                    hi="परिणाम: निर्धारित नहीं किया जा सका। विवरण नीचे आउटपुट में है।",
                    fr="Le résultat est : indéterminé. Voir les détails ci-dessous.",
                    es="El resultado es: no se pudo determinar. La explicación está abajo.",
                    de="Das Ergebnis ist: nicht bestimmbar. Details unten.",
                    log_command="Identity matrix check failed: " + str(e)
                )
                gui_callback(
                    result="❌ Error",
                    solution_en="Identity matrix check failed due to invalid input or unsupported symbolic values.",
                    stepwise=f"⚠️ Error: {str(e)}"
                )

        # 🔢 Matrix Operations – Matrix Raised to a Power
        elif "to the power" in command:
            try:
                matrix_data, power = extract_matrix_and_power(command)

                # ✅ Apply trig + log simplification on each matrix element
                matrix_data = [[trigsimp(logcombine(sympify(cell))) for cell in row] for row in matrix_data]

                A = Matrix(matrix_data)

                # ✅ Rule: Only square matrices allow self-multiplication
                rows, cols = A.shape
                if rows != cols:
                    raise ValueError("Matrix power is only defined when the matrix can be multiplied with itself — i.e., it must be square (n×n).")

                if not isinstance(power, int):
                    raise ValueError("Power must be a whole number (integer) like 2, 3, or 5.")

                # 🧠 Matrix formatter
                def format_matrix(M):
                    return "\n".join(["   | " + "  ".join(str(c) for c in row) + " |" for row in M.tolist()])

                # ✅ Perform exponentiation
                result = A ** power

                # 🧮 Math steps (only for power 2 or 3)
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

                # 📘 Full solution text
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

                _speak_multilang(
                    f"The answer is:\n{format_matrix(result)}\nYou’ll find the full solution in the output below.",
                    hi=f"उत्तर है:\n{format_matrix(result)}\nपूरा समाधान नीचे आउटपुट में है।",
                    fr=f"La réponse est :\n{format_matrix(result)}\nLa solution complète est ci-dessous.",
                    es=f"La respuesta es:\n{format_matrix(result)}\nLa solución completa está abajo.",
                    de=f"Die Antwort ist:\n{format_matrix(result)}\nDie vollständige Lösung steht unten.",
                    log_command=f"Matrix Power A^{power}"
                )

                if gui_callback:
                    gui_callback(result=f"A^{power}", solution_en="Matrix power", stepwise=steps_text)

            except Exception as e:
                user_friendly_reason = str(e)
                if "square" in user_friendly_reason:
                    user_friendly_reason = "Matrix power is only defined when the matrix can be multiplied with itself — i.e., it must be square (same number of rows and columns)."
                elif "integer" in user_friendly_reason:
                    user_friendly_reason = "Power must be a whole number (integer) like 2, 3, or 5."

                _speak_multilang(
                    "The result is: Unable to calculate. You’ll find the explanation in the output below.",
                    hi="परिणाम: गणना संभव नहीं है। विवरण नीचे आउटपुट में है।",
                    fr="Le résultat est : échec du calcul. Voir les détails ci-dessous.",
                    es="El resultado es: no se pudo calcular. Explicación abajo.",
                    de="Das Ergebnis ist: nicht berechenbar. Details unten.",
                    log_command=f"Matrix Power Failure: {str(e)}"
                )

                if gui_callback:
                    gui_callback(
                        result="❌ Unable to calculate",
                        solution_en="Could not compute matrix power.",
                        stepwise=f"⚠️ Error: {str(e)}\n\nReason: {user_friendly_reason}"
                    )

        # 🔢 Matrix Operations – Trace of a Matrix
        elif "trace of matrix" in command:
            try:
                matrix_data = extract_matrix(command)

                # ✅ Apply trig + log simplification on each matrix element
                matrix_data = [[trigsimp(logcombine(sympify(cell))) for cell in row] for row in matrix_data]

                A = Matrix(matrix_data)

                # ✅ Rule: Only square matrices can have a trace
                rows, cols = A.shape
                if rows != cols:
                    raise ValueError("Matrix must be square to compute trace.")

                # 🧠 Matrix formatter
                def format_matrix(M):
                    return "\n".join(["   | " + "  ".join(str(c) for c in row) + " |" for row in M.tolist()])

                # 🧮 Compute trace and steps
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

                result = str(trace_val)

                _speak_multilang(
                    f"The answer is {result}. You’ll find the full solution in the output below.",
                    hi=f"उत्तर है {result}। पूरा समाधान नीचे आउटपुट में है।",
                    fr=f"La réponse est {result}. La solution complète est ci-dessous.",
                    es=f"La respuesta es {result}. La solución completa está abajo.",
                    de=f"Die Antwort ist {result}. Die vollständige Lösung steht unten.",
                    log_command="Trace of Matrix"
                )

                gui_callback(result=result, solution_en="Trace of matrix", stepwise=steps_text)

            except Exception as e:
                reason = str(e)
                if "square" in reason:
                    user_friendly = f"Matrix must be square to compute trace.\nYou provided a {rows}×{cols} matrix (rows ≠ columns), so trace is undefined."
                elif "parse" in reason or "list" in reason:
                    user_friendly = "Couldn't parse the matrix format.\nMake sure the matrix looks like [[1,2],[3,4]] — a list of lists."
                else:
                    user_friendly = reason

                _speak_multilang(
                    "The result is: Unable to determine. You’ll find the explanation in the output below.",
                    hi="परिणाम: निर्धारित नहीं किया जा सका। विवरण नीचे आउटपुट में है।",
                    fr="Le résultat est : indéterminé. Voir les détails ci-dessous.",
                    es="El resultado es: no se pudo determinar. La explicación está abajo.",
                    de="Das Ergebnis ist: nicht bestimmbar. Details unten.",
                    log_command="Trace Matrix Failure: " + reason
                )

                gui_callback(
                    result="❌ Unable to determine",
                    solution_en="Could not compute matrix trace.",
                    stepwise=f"📘 Steps:\n\n❌ Error: {user_friendly}\n\n⚠️ Raw error: {reason}"
                )

        # 🔢 Matrix Operations – Cofactor of a Matrix
        elif "cofactor of matrix" in command:
            try:
                matrix_data = extract_matrix(command)

                # ✅ Enable symbolic trig and log expressions
                matrix_data = [[trigsimp(logcombine(sympify(cell))) for cell in row] for row in matrix_data]

                A = Matrix(matrix_data)

                rows, cols = A.shape
                if rows != cols:
                    raise ValueError("Cofactor matrix is only defined for square matrices.")

                n = rows

                # 🧠 Matrix formatter
                def format_matrix(M):
                    return "\n".join(["   | " + "  ".join(f"{item}" for item in row) + " |" for row in M.tolist()])

                # Step-by-step cofactor calculation
                cofactor_matrix = []
                explanation = ""

                explanation += f"📘 Steps:\n\n"
                explanation += f"1. Original Matrix:\n{format_matrix(A)}\n\n"
                explanation += f"2. Rule:\n"
                explanation += f"   ✅ Cofactor is defined for square matrices only.\n"
                explanation += f"   This is a {n}×{n} square matrix.\n\n"
                explanation += f"   Formula used:\n"
                explanation += f"   C[i,j] = (−1)^(i+j) × M[i,j]\n"
                explanation += f"   where M[i,j] is the minor of element A[i,j]\n\n"
                explanation += f"3. Cofactor Calculation:\n\n"

                for i in range(n):
                    row_cofactor = []
                    for j in range(n):
                        sign = (-1) ** (i + j)
                        minor = A.minor_submatrix(i, j).det()
                        cofactor = sign * minor
                        sign_str = "+1" if sign == 1 else "-1"
                        explanation += f"   C[{i+1},{j+1}] = ({sign_str}) × Minor of A[{i+1},{j+1}] = ({sign_str}) × {minor} = {cofactor}\n"
                        row_cofactor.append(cofactor)
                    cofactor_matrix.append(row_cofactor)
                    explanation += "\n"

                C = Matrix(cofactor_matrix)

                explanation += f"4. Final Cofactor Matrix:\n{format_matrix(C)}\n\n"
                explanation += f"✅ Final Answer:\nThe cofactor matrix is:\n{format_matrix(C)}"

                _speak_multilang(
                    f"The answer is:\n{format_matrix(C)}\nYou’ll find the full solution in the output below.",
                    hi=f"उत्तर है:\n{format_matrix(C)}\nपूरा समाधान नीचे आउटपुट में है।",
                    fr=f"La réponse est :\n{format_matrix(C)}\nLa solution complète est ci-dessous.",
                    es=f"La respuesta es:\n{format_matrix(C)}\nLa solución completa está abajo.",
                    de=f"Die Antwort ist:\n{format_matrix(C)}\nDie vollständige Lösung steht unten.",
                    log_command="Cofactor of Matrix"
                )
                gui_callback(result="Cofactor Matrix", solution_en="Cofactor matrix computed.", stepwise=explanation)

            except Exception as e:
                _speak_multilang(
                    "The result is: Unable to calculate. You’ll find the explanation in the output below.",
                    hi="परिणाम: गणना संभव नहीं है। विवरण नीचे आउटपुट में है।",
                    fr="Le résultat est : échec du calcul. Voir les détails ci-dessous.",
                    es="El resultado es: no se pudo calcular. Explicación abajo.",
                    de="Das Ergebnis ist: nicht berechenbar. Details unten.",
                    log_command=f"Cofactor matrix failure: {str(e)}"
                )
                gui_callback(
                    result="❌ Unable to calculate",
                    solution_en="Could not compute cofactor matrix.",
                    stepwise=f"📘 Steps:\n\n❌ Error: Could not compute cofactor matrix.\nReason: {str(e)}"
                )

        # 🔄 Matrix Operations – Adjoint of a Matrix
        elif "adjoint of matrix" in command or "adjugate of matrix" in command:
            try:
                matrix_data = extract_matrix(command)

                # ✅ Add symbolic trig/log handling
                matrix_data = [[trigsimp(logcombine(sympify(cell))) for cell in row] for row in matrix_data]

                A = Matrix(matrix_data)

                rows, cols = A.shape
                if rows != cols:
                    raise ValueError("Adjoint matrix is only defined for square matrices.")

                n = rows

                # 🧠 Matrix formatter
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
                        cofactor = sign * minor
                        sign_str = "+1" if sign == 1 else "−1"
                        explanation += f"   C[{i+1},{j+1}] = ({sign_str}) × Minor of A[{i+1},{j+1}] = ({sign_str}) × {minor} = {cofactor}\n"
                        row_cofactor.append(cofactor)
                    cofactor_matrix.append(row_cofactor)
                    explanation += "\n"

                C = Matrix(cofactor_matrix)
                explanation += f"   Cofactor Matrix:\n{format_matrix(C)}\n\n"

                # Step 2 – Transpose
                adjoint_matrix = C.transpose()
                explanation += f"4. Step 2 – Transpose of Cofactor Matrix:\n"
                explanation += f"   We flip the matrix across its diagonal.\n\n"
                explanation += f"   Original Cofactor:\n{format_matrix(C)}\n\n"
                explanation += f"   Transposed Matrix:\n{format_matrix(adjoint_matrix)}\n\n"

                explanation += f"✅ Final Answer:\nThe adjoint (adjugate) matrix is:\n{format_matrix(adjoint_matrix)}"

                _speak_multilang(
                    f"The answer is:\n{format_matrix(adjoint_matrix)}\nYou’ll find the full solution in the output below.",
                    hi=f"उत्तर है:\n{format_matrix(adjoint_matrix)}\nपूरा समाधान नीचे आउटपुट में है।",
                    fr=f"La réponse est :\n{format_matrix(adjoint_matrix)}\nLa solution complète est ci-dessous.",
                    es=f"La respuesta es:\n{format_matrix(adjoint_matrix)}\nLa solución completa está abajo.",
                    de=f"Die Antwort ist:\n{format_matrix(adjoint_matrix)}\nDie vollständige Lösung steht unten.",
                    log_command="Adjoint of Matrix"
                )

                gui_callback(result="Adjoint Matrix", solution_en="Adjoint (adjugate) matrix computed.", stepwise=explanation)

            except Exception as e:
                _speak_multilang(
                    "The result is: Unable to calculate. You’ll find the explanation in the output below.",
                    hi="परिणाम: गणना संभव नहीं है। विवरण नीचे आउटपुट में है।",
                    fr="Le résultat est : échec du calcul. Voir les détails ci-dessous.",
                    es="El resultado es: no se pudo calcular. Explicación abajo.",
                    de="Das Ergebnis ist: nicht berechenbar. Details unten.",
                    log_command=f"Adjoint Failure: {str(e)}"
                )
                gui_callback(
                    result="❌ Unable to calculate",
                    solution_en="Could not compute adjoint matrix.",
                    stepwise=f"📘 Steps:\n\n❌ Error: Could not compute adjoint matrix.\nReason: {str(e)}"
                )

        # 🔢 Matrix Operations – Minor of a Matrix
        elif "minor of matrix" in command:
            try:
                matrix_data = extract_matrix(command)

                # ✅ Add support for trig/log expressions
                matrix_data = [[trigsimp(logcombine(sympify(cell))) for cell in row] for row in matrix_data]

                A = Matrix(matrix_data)
                rows, cols = A.shape
                if rows != cols:
                    raise ValueError("Minor matrix is only defined for square matrices.")

                n = rows

                # 🧠 Matrix formatter
                def format_matrix(M):
                    return "\n".join(["   | " + "  ".join(f"{item}" for item in row) + " |" for row in M.tolist()])

                # Step-by-step minor calculation
                minor_matrix = []
                explanation = ""

                explanation += f"📘 Steps:\n\n"
                explanation += f"1. Original Matrix:\n{format_matrix(A)}\n\n"
                explanation += f"2. Rule:\n"
                explanation += f"   ✅ Minor is defined for square matrices only.\n"
                explanation += f"   This is a {n}×{n} square matrix.\n\n"
                explanation += f"   Formula used:\n"
                explanation += f"   M[i,j] = Determinant of the submatrix formed by deleting row i and column j.\n\n"
                explanation += f"3. Minor Calculation:\n\n"

                for i in range(n):
                    row_minor = []
                    for j in range(n):
                        sub = A.minor_submatrix(i, j)
                        minor = sub.det()
                        formatted_sub = format_matrix(sub)

                        explanation += f"   M[{i+1},{j+1}] = Minor of A[{i+1},{j+1}]:\n"
                        explanation += f"{formatted_sub}\n"
                        explanation += f"     → Determinant = {minor}\n\n"

                        row_minor.append(minor)
                    minor_matrix.append(row_minor)

                M = Matrix(minor_matrix)

                explanation += f"4. Final Minor Matrix:\n{format_matrix(M)}\n\n"
                explanation += f"✅ Final Answer:\nThe minor matrix is:\n{format_matrix(M)}"

                _speak_multilang(
                    f"The answer is:\n{format_matrix(M)}\nYou’ll find the full solution in the output below.",
                    hi=f"उत्तर है:\n{format_matrix(M)}\nपूरा समाधान नीचे आउटपुट में है।",
                    fr=f"La réponse est :\n{format_matrix(M)}\nLa solution complète est ci-dessous.",
                    es=f"La respuesta es:\n{format_matrix(M)}\nLa solución completa está abajo.",
                    de=f"Die Antwort ist:\n{format_matrix(M)}\nDie vollständige Lösung steht unten.",
                    log_command="Minor of Matrix"
                )

                if gui_callback:
                    gui_callback(result="Minor Matrix", solution_en="Minor matrix computed.", stepwise=explanation)

            except Exception as e:
                reason = str(e)
                if "square" in reason:
                    reason = "Minor matrix is only defined for square matrices (like 2×2, 3×3, etc.)"
                elif "shape" in reason or "list index" in reason:
                    reason = "Invalid matrix format. Please check your input."

                _speak_multilang(
                    "The result is: Unable to calculate. You’ll find the explanation in the output below.",
                    hi="परिणाम: गणना संभव नहीं है। विवरण नीचे आउटपुट में है।",
                    fr="Le résultat est : échec du calcul. Voir les détails ci-dessous.",
                    es="El resultado es: no se pudo calcular. Explicación abajo.",
                    de="Das Ergebnis ist: nicht berechenbar. Details unten.",
                    log_command=f"Minor matrix failure: {str(e)}"
                )

                if gui_callback:
                    gui_callback(
                        result="❌ Unable to calculate",
                        solution_en="Could not compute minor matrix.",
                        stepwise=f"📘 Steps:\n\n❌ Error: Could not compute minor matrix.\nReason: {reason}"
                    )

    except Exception as e:
        # Best-effort final catch — speak & (optionally) you could also raise a generic popup if desired.
        logger.error(f"❌ Error during symbolic math handling: {e}")
        _speak_multilang(
            "Sorry, something went wrong while solving the math expression.",
            hi="माफ़ कीजिए, गणितीय समीकरण हल करते समय कुछ त्रुटि हुई।",
            fr="Désolé, une erreur s'est produite lors de la résolution de l'expression mathématique.",
            es="Lo siento, ocurrió un error al resolver la expresión matemática.",
            de="Entschuldigung, beim Lösen des mathematischen Ausdrucks ist ein Fehler aufgetreten."
        )


# 🔢 Extract one matrix from command
def extract_matrix(command: str) -> list:
    import re
    from sympy import sympify

    try:
        matrix_str = re.findall(r"\[\[.*?\]\]", command)[0]
        raw_matrix = eval(matrix_str)  # Don't use ast.literal_eval for symbolic
        return [[sympify(cell) for cell in row] for row in raw_matrix]
    except Exception:
        raise ValueError("Couldn't parse matrix. Make sure it's like [[1,2],[3,4]] or uses symbols like sin(x), log(x), pi.")


# 🔁 Extract two matrices for multiplication
def extract_two_matrices(command: str) -> tuple:
    import re
    from sympy import sympify

    try:
        matrix_matches = re.findall(r"\[\[.*?\]\]", command)
        if len(matrix_matches) < 2:
            raise ValueError("Please provide two matrices to multiply.")
        mat1 = eval(matrix_matches[0])
        mat2 = eval(matrix_matches[1])
        mat1 = [[sympify(cell) for cell in row] for row in mat1]
        mat2 = [[sympify(cell) for cell in row] for row in mat2]
        return mat1, mat2
    except Exception:
        raise ValueError("Couldn't parse both matrices correctly. Include symbolic functions like sin(x) inside double brackets.")


# 🔼 Extract matrix and power
def extract_matrix_and_power(command: str) -> tuple:
    import re
    from sympy import sympify

    try:
        matrix_str = re.findall(r"\[\[.*?\]\]", command)[0]
        power_match = re.findall(r"power\s+(\d+)", command)
        if not power_match:
            raise ValueError("Couldn't detect power value. Use 'to the power X'")
        power = int(power_match[0])
        raw_matrix = eval(matrix_str)
        matrix = [[sympify(cell) for cell in row] for row in raw_matrix]
        return matrix, power
    except Exception:
        raise ValueError("Couldn't parse matrix power. Example: matrix [[1,2],[3,4]] to the power 3 or [[sin(x),e],[log(x),pi]]^2")


# 🧠 Extract expression from command (robust version)
def extract_expression(command: str) -> Symbol:
    import re
    try:
        # ✅ Try to find common math patterns using regex
        match = re.search(r"(integrate|differentiate|derivative|simplify|solve|limit)?\s*(of)?\s*(.*)", command, re.IGNORECASE)
        expr = match.group(3).strip() if match else command
        expr = expr.replace("^", "**")
        return sympify(expr)
    except Exception:
        raise ValueError("Couldn't parse expression. Please provide a valid math expression.")


# 🔢 Bounds parser for definite integrals
def extract_bounds(command: str):
    try:
        expr_part = command.split("from")[0]
        bounds_part = command.split("from")[1]

        expr = sympify(expr_part.split("integrate")[-1].strip().replace("^", "**"))
        a = float(bounds_part.split("to")[0].strip())
        b = float(bounds_part.split("to")[1].strip())
        return expr, a, b
    except Exception:
        return extract_expression(command), None, None


# 🚦 Limit expression parser
def extract_limit_info(command: str):
    try:
        expr_raw = command.split("limit of", 1)[-1].split("as")[0].strip()
        expr = sympify(expr_raw.replace("^", "**"))

        approach_part = command.split("approaches")[-1].strip()
        if "infinity" in approach_part or "∞" in approach_part:
            point = float("inf")
        elif "-infinity" in approach_part or "-∞" in approach_part:
            point = float("-inf")
        else:
            point = float(approach_part)

        return expr, point
    except Exception:
        raise ValueError("Couldn't extract limit expression or point")
