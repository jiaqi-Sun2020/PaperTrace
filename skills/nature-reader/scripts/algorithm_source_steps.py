"""Count inspectable statements in numbered or unnumbered source pseudocode.

Line numbers in a compiled reader are navigational when the PDF has no line
numbers. Count assignments and control statements from immutable extraction;
never trust a completion-authored count as source evidence.
"""
import re

def source_statement_count(source: str) -> int:
    numbers = [int(x) for x in re.findall(r'(?m)^\s*(\d+)\s*:', source)]
    if numbers:
        return max(numbers)
    if not re.search(r'(?m)^\s*(?:Input|Require):', source) or not re.search(r'(?m)^\s*(?:Output|Ensure):', source):
        return 0
    assignments = source.count('←')
    if assignments >= 2 and re.search(r'(?m)^\s*while\b', source):
        # PDF text often puts a superscript/subscript on the following line.
        # Join only an assignment's left-hand identifier, not arbitrary prose.
        logical = re.sub(r'(?m)^([A-Za-z][A-Za-z0-9]*)\n([a-z0-9]+)\s*=', r'\1_\2 =', source)
        return len(re.findall(
            r'(?m)^\s*(?:Initialisations:|Initialise\b|while\b|end\s*$|[A-Za-z][A-Za-z0-9_]*\s*(?:←|∼|=))',
            logical,
        ))
    controls = len(re.findall(r'(?m)^\s*(?:for\b|if\b|else\s*$|end\s+(?:if|for)\s*$|repeat\s*$|until\b)', source))
    selections = len(re.findall(r'(?m)^\s*=\s*arg\s+max\b', source))
    return assignments + controls + selections if assignments >= 2 else 0
