import os
import tempfile
import subprocess

from tree_sitter import Language, Parser
from typing import List, Tuple, Dict, Any

"""
@Author: EugeneYu
@Data: 2025/4/5
@Desc: 特定语言的 Tree-sitter 解析器的基类
"""

class TreeSitterLanguage:

    def __init__(self, language_name: str):
        self.language_name = language_name
        self.parser = None
        self.language = None
        self._setup_parser()

    def _setup_parser(self):
        languages_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tree-sitter-languages")
        os.makedirs(languages_dir, exist_ok=True)

        language_repos = {
            "python": "https://github.com/tree-sitter/tree-sitter-python",
            "javascript": "https://github.com/tree-sitter/tree-sitter-javascript",
            "java": "https://github.com/tree-sitter/tree-sitter-java",
            "kotlin": "https://github.com/fwcd/tree-sitter-kotlin",
            "objc": "https://github.com/jiyee/tree-sitter-objc",
        }

        if self.language_name not in language_repos:
            raise ValueError(f"Unsupported language: {self.language_name}")

        lib_path = os.path.join(languages_dir, f"{self.language_name}.so")
        
        if not os.path.exists(lib_path):
            repo_url = language_repos[self.language_name]
            with tempfile.TemporaryDirectory() as tmp_dir:
                subprocess.run(["git", "clone", repo_url, tmp_dir], check=True)
                
                if self.language_name == "typescript":
                    ts_dir = os.path.join(tmp_dir, "typescript")
                    tsx_dir = os.path.join(tmp_dir, "tsx")
                    Language.build_library(
                        lib_path,
                        [ts_dir, tsx_dir]
                    )
                else:
                    # Build the language library
                    Language.build_library(
                        lib_path,
                        [tmp_dir]
                    )
        
        self.language = Language(lib_path, self.language_name)
        
        self.parser = Parser()
        self.parser.set_language(self.language)

    def chunk_code(self, code: str) -> List[Tuple[str, Dict[str, Any]]]:
        raise NotImplementedError("Subclasses must implement this method")

    def _get_node_text(self, node, code_bytes):
        return code_bytes[node.start_byte:node.end_byte].decode('utf-8')

    def _get_node_lines(self, node):
        return node.start_point[0], node.end_point[0]

    def create_query(self, query_string):
        return self.language.query(query_string)