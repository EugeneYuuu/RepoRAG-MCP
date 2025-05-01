import os
import json
import hashlib
import argparse
import re
from typing import List, Dict, Any, Tuple, Set
import importlib.util

from LanguageChunker.JavaChunker import JavaChunker
from LanguageChunker.JavaScriptChunker import JavaScriptChunker
from LanguageChunker.KotlinChunker import KotlinChunker
from LanguageChunker.PythonChunker import PythonChunker
from LanguageChunker.ObjectiveCChunker import ObjectiveCChunker
"""
@Author: EugeneYu
@Data: 2025/4/4
@Desc: 针对不同语言进行语法树解析分块
"""

class CodeChunker:

    def __init__(self, input_dir: str, incremental: bool = False):

        self.input_dir = input_dir
        self.incremental = incremental

        self.repo_name = os.path.basename(input_dir)
        self.output_file = f"artifacts/chunks/{self.repo_name}_code_chunks_ast.jsonl"
        
        self.existing_chunks = {}
        if incremental and os.path.exists(self.output_file):
            self._load_existing_chunks()

        self.has_tree_sitter = self._check_tree_sitter()

        self.chunkers = {
            "py": PythonChunker(),
            "python": PythonChunker(),
            "js": JavaScriptChunker(),
            "javascript": JavaScriptChunker(),
            "java": JavaChunker(),
            "kt": KotlinChunker(),
            "kotlin": KotlinChunker(),
            "objc": ObjectiveCChunker(),
        }

    def _check_tree_sitter(self) -> bool:
        try:
            spec = importlib.util.find_spec("tree_sitter")
            return spec is not None
        except ImportError:
            return False

    def _generate_uid(self, file_path: str, chunk_id: str = "") -> str:
        content = f"{file_path}:{chunk_id}"
        return hashlib.md5(content.encode()).hexdigest()

    def extract_code_info(self, content: str) -> Dict:
        info = {
            'language': 'unknown',
            'filename': '',
            'filepath': '',
        }

        filename_match = re.search(r'# (.+)', content)
        if filename_match:
            info['filename'] = filename_match.group(1)

        filepath_match = re.search(r'File path: `(.+)`', content)
        if filepath_match:
            info['filepath'] = filepath_match.group(1)

        language_match = re.search(r'Programming language: (.+)', content)
        if language_match:
            info['language'] = language_match.group(1)

        return info

    def extract_code_content(self, content: str) -> str:
        matches = re.search(r'```[\w]*\n(.*?)\n```', content, re.DOTALL)
        if matches:
            return matches.group(1)
        return content

    def chunk_code_by_language(self, code: str, language: str) -> List[Tuple[str, Dict[str, Any]]]:
        if language not in self.chunkers:
            raise ValueError(f"Unsupported language: {language}. Supported languages: {list(self.chunkers.keys())}")

        return self.chunkers[language].chunk_code(code)

    def process_file(self, file_path: str) -> List[Dict[str, Any]]:
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()

            code_info = self.extract_code_info(content)

            code_content = self.extract_code_content(content)

            file_uid = self._generate_uid(file_path)

            code_chunks = self.chunk_code_by_language(code_content, code_info['language'])

            result = []
            for i, (chunk_text, chunk_meta) in enumerate(code_chunks):
                if not chunk_text.strip():
                    continue

                chunk_id = f"{code_info['filename']}:{chunk_meta.get('chunk_type', 'unknown')}:{i}"
                chunk_uid = self._generate_uid(file_path, chunk_id)

                # 元数据映射
                chunk_data = {
                    'id': chunk_uid,
                    'text': chunk_meta.get('content', chunk_text),
                    'source': file_path,
                    'filename': code_info['filename'],
                    'filepath': code_info['filepath'],
                    'language': code_info['language'],
                    'repository': self.repo_name,
                    'chunk_index': i,
                    'type': chunk_meta.get('chunk_type', 'unknown'),
                    'code_type': chunk_meta.get('chunk_type', 'unknown'),
                    'name': chunk_meta.get('name', ''),
                    'parent': chunk_meta.get('parent', None),
                    'dependencies': chunk_meta.get('dependencies', []),
                    'methods': chunk_meta.get('methods', []),
                    'start_line': chunk_meta.get('start_line', 0),
                    'end_line': chunk_meta.get('end_line', 0),
                    'imports': chunk_meta.get('imports', []),
                    'references': chunk_meta.get('references', [])
                }
                result.append(chunk_data)

            print(f"Processed {file_path}: {len(result)} chunks")
            return result

        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            return []

    def process_directory(self) -> List[Dict[str, Any]]:
        all_chunks = []
        file_count = 0

        for root, _, files in os.walk(self.input_dir):
            for file in files:
                if file.endswith('.md'):
                    file_path = os.path.join(root, file)
                    if os.path.basename(file_path) == "_repo_metadata.md":
                        continue
                    chunks = self.process_file(file_path)
                    all_chunks.extend(chunks)
                    file_count += 1

        print(f"\nProcessed {file_count} files with a total of {len(all_chunks)} chunks.")
        return all_chunks

    def _load_existing_chunks(self):
        try:
            with open(self.output_file, 'r', encoding='utf-8') as f:
                for line in f:
                    chunk = json.loads(line)
                    source = chunk.get('source', '')
                    if source:
                        if source not in self.existing_chunks:
                            self.existing_chunks[source] = []
                        self.existing_chunks[source].append(chunk)
        except Exception as e:
            print(f"Warning: Failed to load existing chunks: {e}")
            self.existing_chunks = {}

    def save_jsonl(self, chunks: List[Dict[str, Any]], processed_files: Set[str] = None) -> None:
        output_dir = os.path.dirname(self.output_file)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)

        if self.incremental and processed_files:
            final_chunks = []
            
            for source, file_chunks in self.existing_chunks.items():
                if source not in processed_files:
                    final_chunks.extend(file_chunks)
            
            final_chunks.extend(chunks)
            chunks = final_chunks

        with open(self.output_file, 'w', encoding='utf-8') as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + '\n')

        print(f"Saved {len(chunks)} chunks to {self.output_file}")

    def run(self) -> None:
        chunks = self.process_directory()
        processed_files = {chunk['source'] for chunk in chunks}
        self.save_jsonl(chunks, processed_files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", required=True)
    parser.add_argument("--incremental", action="store_true")

    args = parser.parse_args()
    
    chunker = CodeChunker(args.input, args.incremental)
    chunker.run()