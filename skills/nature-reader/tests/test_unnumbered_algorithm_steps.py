import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from algorithm_source_steps import source_statement_count
from extract_pdf_bundle import classify_block

source = '''Algorithm 2 Contextualizer
Input: a graph
Output: a string
# initialize s
s ← [ ]
for v in Vc do
s ← s + Nmap(v, N(v))
end for
s ← Sort(s)
s ← Concat(s)'''
assert classify_block(source) == 'algorithm'
assert source_statement_count(source) == 6
assert source_statement_count('Algorithm 2 is discussed below. Output: results.') == 0
assert source_statement_count('Algorithm 1\n1: prepare\n2: rotate') == 2
print('unnumbered algorithm statement tests passed')

pnc = '''Algorithm 1: Partitioning algorithm
Input: graph G
Output: partition H
Initialisations: h(v) = GNNv(G), h(G) = GNNG(G), V1 = V , SH
0 = ∅
t ← 1
while Vt 6= ∅ do
kt ∼ pθ(kt|SH
t−1, G) // sample maximum vertex count
Initialise SV
0 = ∅
while i = 1 ≤ kt and N(SV
i−1) 6= ∅ do
vti ∼ pθ(v|SV
i−1, kt, SH
t−1, G) // sample new vertex
SV
i = SV
i−1 ∪ {vti
}
end
Ht = SV
i
SH
t = SH
t−1 ∪ {Ht}
t ← t + 1
end
H = SH
t'''
assert source_statement_count(pnc) == 14
