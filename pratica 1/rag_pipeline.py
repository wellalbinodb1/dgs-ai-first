"""
Pipeline de RAG — NovaTech Logística  |  Exercício 1.3 — Tech Lead
Vector store: numpy/sklearn (100% local, sem rede, sem ChromaDB ONNX)
Embeddings: TF-IDF com bi-gramas e sublinear_tf
Chunking: por seção semântica (títulos Markdown)
"""

import re, json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DOCS_DIR        = Path("/mnt/user-data/uploads")
MIN_CHUNK_CHARS = 60
TOP_K           = 5

DOCS = {
    "POL-001":     "POL-001-politica-devolucao.md",
    "PROC-042-v1": "PROC-042-frete-especial-v1.md",
    "PROC-042-v2": "PROC-042-v2-frete-especial-revisado.md",
    "SLA-2024":    "SLA-2024-tabela-sla-clientes.md",
    "FAQ":         "FAQ-atendimento.md",
}

# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class Chunk:
    chunk_id: str
    doc_id:   str
    section:  str
    text:     str
    metadata: dict = field(default_factory=dict)

    @property
    def embed_text(self) -> str:
        """Texto com prefixo contextual para embedding."""
        return f"[{self.doc_id} | {self.section}]\n{self.text}"

# ──────────────────────────────────────────────────────────────────────────────
# INGESTÃO E CHUNKING SEMÂNTICO
# ──────────────────────────────────────────────────────────────────────────────
def parse_sections(text: str) -> List[tuple]:
    """Divide documento Markdown por seções ## e ###."""
    sections, cur_title, cur_lines = [], "Cabeçalho", []
    for line in text.split("\n"):
        if re.match(r'^#{1,3} ', line):
            content = "\n".join(cur_lines).strip()
            if content and len(content) >= MIN_CHUNK_CHARS:
                sections.append((cur_title, content))
            cur_title = re.sub(r'^#+\s*', '', line).strip()
            cur_lines = []
        else:
            cur_lines.append(line)
    content = "\n".join(cur_lines).strip()
    if content and len(content) >= MIN_CHUNK_CHARS:
        sections.append((cur_title, content))
    return sections

def ingest(docs: dict) -> List[Chunk]:
    chunks = []
    for doc_id, fname in docs.items():
        fp = DOCS_DIR / fname
        if not fp.exists():
            print(f"  [AVISO] Não encontrado: {fp}"); continue
        sections = parse_sections(fp.read_text(encoding="utf-8"))
        print(f"  {doc_id:15s}: {len(sections):2d} chunks")
        for i, (sec, content) in enumerate(sections):
            chunks.append(Chunk(
                chunk_id = f"{doc_id}_{i:03d}",
                doc_id   = doc_id,
                section  = sec,
                text     = content,
                metadata = {
                    "doc_id":     doc_id,
                    "section":    sec,
                    "fonte_tier": "informal" if doc_id == "FAQ" else "normativo",
                    "status":     "superseded" if doc_id == "PROC-042-v1" else "ativo",
                }
            ))
    print(f"\n  Total: {len(chunks)} chunks\n")
    return chunks

# ──────────────────────────────────────────────────────────────────────────────
# VECTOR STORE LOCAL (numpy + TF-IDF)
# ──────────────────────────────────────────────────────────────────────────────
class VectorStore:
    """
    Vector store minimalista usando TF-IDF (1-2 gramas, sublinear_tf=True).

    Por que TF-IDF e não sentence-transformers?
    - Ambiente offline: huggingface.co e os CDNs de modelos estão bloqueados.
    - TF-IDF captura bem vocabulário técnico específico de domínio (ANTT, CT-e,
      frete especial, Gold/Silver) sem precisar de fine-tuning.
    - Limitação conhecida: não captura sinônimos nem paráfrases semânticas.
      Em produção, trocar por all-MiniLM-L6-v2 ou text-embedding-ada-002.
    """
    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            sublinear_tf=True,
            max_features=8000,
            min_df=1,
        )
        self.matrix    = None
        self.chunks: List[Chunk] = []

    def fit(self, chunks: List[Chunk]):
        self.chunks = chunks
        texts       = [c.embed_text for c in chunks]
        self.matrix = self.vectorizer.fit_transform(texts)
        print(f"  Vocabulário TF-IDF: {len(self.vectorizer.vocabulary_):,} termos")
        print(f"  Matriz: {self.matrix.shape[0]} chunks × {self.matrix.shape[1]} features\n")

    def query(self, query: str, top_k: int = TOP_K,
              filter_superseded: bool = True) -> List[dict]:
        q_vec  = self.vectorizer.transform([query])
        scores = cosine_similarity(q_vec, self.matrix).flatten()

        ranked = np.argsort(scores)[::-1]
        results = []
        for idx in ranked:
            chunk = self.chunks[idx]
            if filter_superseded and chunk.metadata["status"] == "superseded":
                continue
            results.append({
                "chunk_id":   chunk.chunk_id,
                "doc_id":     chunk.doc_id,
                "section":    chunk.section,
                "fonte_tier": chunk.metadata["fonte_tier"],
                "status":     chunk.metadata["status"],
                "text":       chunk.text,
                "score":      round(float(scores[idx]), 4),
            })
            if len(results) == top_k:
                break
        return results

# ──────────────────────────────────────────────────────────────────────────────
# MONTAGEM DO PROMPT
# ──────────────────────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """Você é o Assistente de Atendimento da NovaTech, empresa de logística.
Responda perguntas da equipe de atendimento com base EXCLUSIVAMENTE nos trechos fornecidos.

REGRAS:
1. Cite sempre a fonte (documento + seção) de cada informação.
2. Nunca invente prazos, valores ou procedimentos não presentes nos trechos.
3. Quando não encontrar: "Não encontrei na documentação. Recomendo escalar para o supervisor."
4. Responda em português formal e direto.
5. EXCEÇÕES SÃO PRIORIDADE: se um trecho proíbe ou restringe algo, essa restrição é a
   resposta principal — não a omita nem minimize.
6. Se a pergunta contém peso ou valor específico, aplique a fórmula e mostre o cálculo.

PRIORIDADE DE FONTES: POL / PROC / SLA (normativos) > FAQ (informal)."""

def build_prompt(query: str, hits: List[dict]) -> str:
    docs_text = ""
    for i, h in enumerate(hits, 1):
        label = " ⚠ [FONTE INFORMAL — verificar com normativo]" \
                if h["fonte_tier"] == "informal" else ""
        docs_text += (
            f"\n[Trecho {i} | {h['doc_id']} — '{h['section']}'"
            f" | similaridade: {h['score']}{label}]\n{h['text']}\n"
        )
    return (
        f"{SYSTEM_PROMPT}\n\n"
        f"<documentacao>{docs_text}\n</documentacao>\n\n"
        f"Pergunta do atendente: {query}"
    )

# ──────────────────────────────────────────────────────────────────────────────
# TESTES + GABARITO (Anexo B)
# ──────────────────────────────────────────────────────────────────────────────
GABARITO = {
    "Qual o prazo de devolução?": {
        "docs": ["POL-001"],
        "secoes_esperadas": ["Prazo geral", "Exceções"],
        "nota": "Deve recuperar seção 3.1 (prazo 7 dias) E 3.2 (exceções carga perigosa)"
    },
    "Posso devolver carga perigosa?": {
        "docs": ["POL-001"],
        "secoes_esperadas": ["Exceções"],
        "nota": "Deve recuperar seção 3.2 explicitando que NÃO pode pelo processo padrão"
    },
    "Qual o SLA do cliente Gold?": {
        "docs": ["SLA-2024"],
        "secoes_esperadas": ["Tabela de SLAs", "Classificação de clientes"],
        "nota": "Deve recuperar a tabela SLA com valores Gold (2h resposta, 24h resolução)"
    },
    "Qual o SLA do cliente Platinum?": {
        "docs": ["SLA-2024"],
        "secoes_esperadas": ["Classificação de clientes"],
        "nota": "Tier Platinum não existe — deve recuperar a seção que lista apenas 3 tiers"
    },
    "Qual o multiplicador de frete para o Sudeste?": {
        "docs": ["PROC-042-v2"],
        "secoes_esperadas": ["Multiplicadores regionais"],
        "nota": "Deve usar PROC-042-v2 (ativo), não v1 (superseded). v2: Sudeste=1.1, v1: Sudeste=1.0"
    },
}

def avaliar(hits: List[dict], gabarito: dict) -> dict:
    docs_ret = [h["doc_id"] for h in hits]
    secs_str = " | ".join(h["section"] for h in hits).lower()
    doc_ok   = any(g in docs_ret for g in gabarito["docs"])
    sec_ok   = any(s.lower() in secs_str for s in gabarito["secoes_esperadas"])
    return {
        "doc_correto_no_top5": doc_ok,
        "secao_relevante":     sec_ok,
        "top1_doc":            hits[0]["doc_id"] if hits else "",
        "top1_section":        hits[0]["section"] if hits else "",
        "top1_score":          hits[0]["score"] if hits else 0,
    }

# ──────────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 65)
    print("PIPELINE DE RAG — NovaTech Logística")
    print("Embeddings: TF-IDF local (sklearn) | Vector store: numpy")
    print("=" * 65)

    print("\n[1/3] INGESTÃO E CHUNKING SEMÂNTICO")
    chunks = ingest(DOCS)

    print("[2/3] EMBEDDINGS + INDEXAÇÃO")
    store = VectorStore()
    store.fit(chunks)

    print("[3/3] TESTES DE BUSCA\n")
    print("-" * 65)

    resultados = []
    acertos = 0

    for pergunta, gabarito in GABARITO.items():
        hits  = store.query(pergunta, top_k=TOP_K)
        aval  = avaliar(hits, gabarito)
        prom  = build_prompt(pergunta, hits[:3])
        ok    = aval["doc_correto_no_top5"]
        acertos += int(ok)

        print(f"\nPERGUNTA : {pergunta}")
        print(f"GABARITO : {gabarito['docs']} | seções: {gabarito['secoes_esperadas']}")
        print(f"RESULTADO: {'✓ CORRETO' if ok else '✗ FALHOU'}")
        print(f"  {'RANK':4} {'DOC':15} {'SEÇÃO':42} {'SCORE':7} {'TIER'}")
        print(f"  {'-'*4} {'-'*15} {'-'*42} {'-'*7} {'-'*9}")
        for i, h in enumerate(hits, 1):
            tag  = "✓" if h["doc_id"] in gabarito["docs"] else " "
            tier = "[FAQ]    " if h["fonte_tier"] == "informal" else "         "
            sup  = "[SUPERS.]" if h["status"] == "superseded" else "         "
            print(f"  {i:>3}. {tag} {h['doc_id']:15} {h['section'][:40]:42} {h['score']:.4f} {tier}{sup}")
        print(f"  Nota: {gabarito['nota']}")

        resultados.append({
            "pergunta":   pergunta,
            "gabarito":   gabarito,
            "hits":       [{k:v for k,v in h.items() if k != "text"} for h in hits],
            "avaliacao":  aval,
            "prompt":     prom,
        })

    print("\n" + "=" * 65)
    print(f"PLACAR FINAL: {acertos}/{len(GABARITO)} testes com doc correto no top-5")
    print("=" * 65)

    with open("/home/claude/resultados_rag.json", "w", encoding="utf-8") as f:
        json.dump(resultados, f, ensure_ascii=False, indent=2)
    print("\nResultados completos → /home/claude/resultados_rag.json")
    return resultados

if __name__ == "__main__":
    main()
