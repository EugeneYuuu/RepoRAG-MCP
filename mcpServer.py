from mcp.server.fastmcp import FastMCP
import chromadb
from sentence_transformers import SentenceTransformer
import argparse
from typing import List, Dict, Any
from dataclasses import dataclass


"""
@Author: EugeneYu
@Data: 2025/4/6
@Desc: 
"""

@dataclass
class SearchResult:
    code: str
    metadata: Dict[str, Any]
    similarity_score: float
    references: List[str] = None

mcp = FastMCP("Repository MCP")

client: chromadb.PersistentClient
collection: chromadb.Collection
model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")


def _execute_search(query_embedding: List[float], n_results: int = 25, where_clause: Dict = None) -> List[SearchResult]:
    """执行基础搜索并格式化结果"""
    search_params = {
        "query_embeddings": [query_embedding],
        "n_results": n_results,
        "include": ["documents", "metadatas", "distances"]
    }
    
    if where_clause:
        search_params["where"] = where_clause
    
    results = collection.query(**search_params)
    
    formatted_results = []
    for i in range(len(results["documents"][0])):
        result = SearchResult(
            code=results["documents"][0][i],
            metadata=results["metadatas"][0][i],
            similarity_score=1 - results["distances"][0][i]
        )
        formatted_results.append(result)
    
    return formatted_results

@mcp.tool()
def search_by_core_keywords(query: str, code_type: str = "", n_results: int = 25) -> List[SearchResult]:
    """
    使用核心关键词进行初始搜索。当发现相关关键词时，也要调用此方法，而不是从本地搜索。
    
    Args:
        query: 核心关键词组合
        n_results: 返回结果数量
        code_type: 指定的代码类型
    
    Returns:
        最相关的代码片段列表
    """
    query_embedding = model.encode(query).tolist()
    
    where_clause = {}
    if code_type:
        where_clause["code_type"] = code_type
    
    return _execute_search(query_embedding, n_results, where_clause)


@mcp.tool()
def search_by_reference(file_path: str, class_name: str, n_results: int = 15) -> List[SearchResult]:
    """
    基于文件路径或类名搜索相关引用
    发现相关文件时，不要从本地去查找相关文件，而是调用此方法
    
    Args:
        file_path: 文件路径
        class_name: 类名
        n_results: 返回结果数量
    
    Returns:
        相关引用的代码片段列表
    """
    where_clause = {}
    if file_path:
        where_clause["file_path"] = {"$contains": file_path}
    if class_name:
        where_clause["code"] = {"$contains": class_name}
    
    query = f"{file_path} {class_name}".strip()
    query_embedding = model.encode(query).tolist()
    
    results = _execute_search(query_embedding, n_results, where_clause)
    
    # 添加引用信息
    for result in results:
        result.references = []
        if "imports" in result.metadata:
            result.references.extend(result.metadata["imports"])
        if "references" in result.metadata:
            result.references.extend(result.metadata["references"])
    
    return results


@mcp.tool()
def search_specific_details(query: str, context_file_path: str, context_class: str, n_results: int = 15) -> List[SearchResult]:
    """
    在关键词搜索中发现相关上下文后，使用此方法对搜索问题和上下文信息进行补充搜索

    Args:
        query: 具体的搜索问题
        context_file_path: 上下文文件路径
        context_class: 上下文类名
        n_results: 返回结果数量
    
    Returns:
        补充搜索结果列表
    """
    where_clause = {}
    if context_file_path:
        where_clause["file_path"] = {"$contains": context_file_path}
    if context_class:
        where_clause["code"] = {"$contains": context_class}
    
    query_embedding = model.encode(query).tolist()
    return _execute_search(query_embedding, n_results, where_clause)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='RepoRAG-MCP')
    parser.add_argument('--chromadb-path', '-d', type=str, required=True,
                        default="artifacts/vector_stores/chroma_db")
    parser.add_argument('--collection-name', '-c', type=str, required=True)
    
    args = parser.parse_args()
    
    client = chromadb.PersistentClient(path=args.chromadb_path)
    collection = client.get_collection(args.collection_name)
    
    mcp.run() 