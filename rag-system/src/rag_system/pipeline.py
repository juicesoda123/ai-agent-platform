"""RAG Pipeline -- 串联检索 + 生成 。"""

from rag_system.loader import DocumentLoader, Document
from rag_system.chunker import TextChunker
from rag_system.embedder import Embedder
from rag_system.vector_store import VectorStore
from openai import AsyncOpenAI

class RAGPipeline:
    """完整 RAG 问答管道"""

    def __init__(
            self,
            llm_client: AsyncOpenAI,
            llm_model: str,
            embedder: Embedder,
    ):
        self.llm_client = llm_client
        self.llm_model = llm_model
        self.embedder = embedder
        self.store = VectorStore(embedder)
    
    def load_documents(self, directory: str, chunk_size: int = 500, chunk_overlap: int = 100) -> None:
        """加载文档，切块，入库"""
        loader = DocumentLoader(directory)
        documents = loader.load_all()
        if not documents:
            print("没有加载到任何文档！")
            return
        print(f"加载: {len(documents)} 篇文档")


        chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        chunks = chunker.chunk(documents)
        print(f"切块: {len(chunks)} 个 chunk")

        self.store.add_documents(chunks)
        print(f"入库完成，当前总文档数: {self.store.count()}")

    async def ask(self, question: str, top_k: int = 3) -> str:
        """提问 -> 检索 -> 拼Prompt -> LLM 生成回答"""
        # 1. 检索相关文档
        results = self.store.query(question, top_k=top_k)
        if not results:
            print("没有相关文档，无法回答！")
            return "抱歉，我没有找到相关信息。"
        
        # 2. 拼接 context
        context_parts = []
        for i, doc in enumerate(results):
            src = doc.metadata.get("source", "?")
            context_parts.append(f"[{src}] {doc.content}")
        context = "\n\n".join(context_parts)

        # 3. 构造 Prompt
         # 3. 构造 Prompt
        prompt = f"""根据以下参考资料回答问题。如果资料中没有相关信息，请如实说不知道。

{context}

问题：{question}

请用中文回答，并在回答末尾注明参考了哪份资料。"""
        
        # 4. 调用LLM生成回答
        response = await self.llm_client.chat.completions.create(
            model = self.llm_model,
            messages = [
                {"role": "system", "content": "你是一个知识渊博的助手，善于根据提供的资料回答问题。"},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content
        