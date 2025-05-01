import os
import json
import argparse
from typing import List, Dict, Any, Set
from tqdm import tqdm
import chromadb
from sentence_transformers import SentenceTransformer
from datetime import datetime

"""
@Author: EugeneYu
@Data: 2025/4/4
@Desc: 对分块代码进行向量化存储
"""

class CodeVectorizer:
    def __init__(
        self,
        input_file: str,
        db_directory: str,
        model_name: str,
        batch_size: int = 32,
        incremental: bool = False
    ):
        self.input_file = input_file
        self.db_directory = db_directory
        self.incremental = incremental
        collection_base_name = os.path.basename(input_file).replace('.jsonl', '')
        
        model_short_name = model_name.split('/')[-1] if '/' in model_name else model_name
        collection_name = f"code_{collection_base_name}_{model_short_name}"
        
        if len(collection_name) > 63:
            collection_name = collection_name[:63]
        
        self.collection_name = collection_name
        print(f"Collection name: {self.collection_name} ({len(self.collection_name)} chars)")
        
        print(f"Initializing ChromaDB at {db_directory}")
        self.client = chromadb.PersistentClient(path=db_directory)
        
        try:
            if incremental:
                self.collection = self.client.get_collection(
                    name=self.collection_name,
                    embedding_function=CustomEmbeddingFunction(model_name)
                )
                print(f"Using existing collection: {self.collection_name}")
            else:
                try:
                    self.client.delete_collection(name=self.collection_name)
                    print(f"Deleted existing collection: {self.collection_name}")
                except Exception as e:
                    print(f"No existing collection to delete: {e}")
                
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    embedding_function=CustomEmbeddingFunction(model_name),
                    metadata={"hnsw:space": "cosine"}
                )
                print(f"Created new collection: {self.collection_name}")
        except Exception as e:
            print(f"Error with collection: {e}")
            self.collection = self.client.create_collection(
                name=self.collection_name,
                embedding_function=CustomEmbeddingFunction(model_name),
                metadata={"hnsw:space": "cosine"}
            )
            print(f"Created new collection as fallback: {self.collection_name}")
        
        collections_file = "artifacts/vector_stores/collections.txt"
        os.makedirs(os.path.dirname(collections_file), exist_ok=True)
        with open(collections_file, 'a+', encoding='utf-8') as f:
            f.seek(0)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"{self.collection_name} ({timestamp}) - Original model: {model_name}\n")
        
        self.batch_size = batch_size
        
        print(f"Using model: {model_name}")
        self.model = SentenceTransformer(model_name)
        print(f"Model loaded: {model_name} (embedding dimension: {self.model.get_sentence_embedding_dimension()})")
        
    def get_existing_chunk_sources(self) -> Set[str]:
        if not self.incremental:
            return set()
            
        try:
            result = self.collection.get()
            sources = set()
            for metadata in result['metadatas']:
                if metadata and 'source' in metadata:
                    sources.add(metadata['source'])
            return sources
        except Exception as e:
            print(f"Warning: Failed to get existing chunk sources: {e}")
            return set()

    def load_chunks(self) -> List[Dict[str, Any]]:
        chunks = []
        
        print(f"Loading chunks from {self.input_file}")
        with open(self.input_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    chunk = json.loads(line)
                    chunks.append(chunk)
        
        print(f"Loaded {len(chunks)} chunks")
        return chunks
    
    def process_and_store_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        if not chunks:
            print("No chunks to process")
            return

        existing_sources = self.get_existing_chunk_sources() if self.incremental else set()
        
        if self.incremental:
            new_sources = {chunk['source'] for chunk in chunks}
            
            if existing_sources and new_sources:
                chunk_ids_to_delete = []
                result = self.collection.get()
                for i, metadata in enumerate(result['metadatas']):
                    if metadata and 'source' in metadata and metadata['source'] in new_sources:
                        chunk_ids_to_delete.append(result['ids'][i])
                
                if chunk_ids_to_delete:
                    print(f"Removing {len(chunk_ids_to_delete)} existing chunks for modified files")
                    # Batch the deletion operations to avoid ChromaDB's limit of 41,666 embeddings
                    delete_batch_size = 40000  # Setting a safe batch size below the limit
                    for i in range(0, len(chunk_ids_to_delete), delete_batch_size):
                        batch_ids = chunk_ids_to_delete[i:i+delete_batch_size]
                        print(f"Deleting batch {i//delete_batch_size + 1} with {len(batch_ids)} chunks")
                        self.collection.delete(ids=batch_ids)

        chunk_ids = [chunk['id'] for chunk in chunks]
        texts = [chunk['text'] for chunk in chunks]
        
        metadatas = []
        for chunk in chunks:
            def safe_get(d, key, default):
                value = d.get(key, default)
                return default if value is None else value

            # 将列表转换为JSON字符串
            imports = safe_get(chunk, 'imports', [])
            if imports:
                imports_str = json.dumps(imports)
            else:
                imports_str = ""
                
            references = safe_get(chunk, 'references', [])
            if references:
                references_str = json.dumps(references)
            else:
                references_str = ""

            metadata = {
                'source': safe_get(chunk, 'source', ''),
                'language': safe_get(chunk, 'language', 'unknown'),
                'filename': safe_get(chunk, 'filename', ''),
                'filepath': safe_get(chunk, 'filepath', ''),
                'repository': safe_get(chunk, 'repository', safe_get(chunk, 'repo', '')),
                'chunk_index': safe_get(chunk, 'chunk_index', 0),
                'type': safe_get(chunk, 'type', 'unknown'),
                'code_type': safe_get(chunk, 'code_type', 'unknown'),
                'name': safe_get(chunk, 'name', ''),
                'parent': safe_get(chunk, 'parent', ''),
                'start_line': safe_get(chunk, 'start_line', 0),
                'end_line': safe_get(chunk, 'end_line', 0),
                'references': references_str
            }
            metadatas.append(metadata)
        
        print(f"Processing {len(chunks)} chunks in batches of {self.batch_size}")
        
        for i in tqdm(range(0, len(chunks), self.batch_size)):
            batch_ids = chunk_ids[i:i+self.batch_size]
            batch_texts = texts[i:i+self.batch_size]
            batch_metadatas = metadatas[i:i+self.batch_size]
            
            self.collection.add(
                ids=batch_ids,
                documents=batch_texts,
                metadatas=batch_metadatas
            )
        
        print(f"Successfully stored {len(chunks)} chunks in ChromaDB")
        
        collection_count = self.collection.count()
        print(f"Total documents in collection: {collection_count}")
        
    def run(self) -> None:
        chunks = self.load_chunks()
        self.process_and_store_chunks(chunks)
        print(f"Vector database created successfully at: {os.path.abspath(self.db_directory)}")
        print("You can now query the database using ChromaDB's query API.")


class CustomEmbeddingFunction:

    def __init__(self, model_name: str = "sentence-transformers/all-MiniLM-L6-v2"):
        self.model = SentenceTransformer(model_name)
        
    def __call__(self, input: List[str]) -> List[List[float]]:
        embeddings = self.model.encode(input)
        return embeddings.tolist()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i")
    parser.add_argument("--db", "-d", default="artifacts/vector_stores/chroma_db")
    parser.add_argument("--model", "-m", default="sentence-transformers/all-MiniLM-L6-v2",
                        help="MiniLM")
    parser.add_argument("--batch-size", "-b", type=int, default=32)
    parser.add_argument("--incremental", action="store_true")
    
    args = parser.parse_args()
    
    vectorizer = CodeVectorizer(
        input_file=args.input,
        db_directory=args.db,
        model_name=args.model,
        batch_size=args.batch_size,
        incremental=args.incremental
    )
    vectorizer.run()