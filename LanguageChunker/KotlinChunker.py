from typing import List, Tuple, Dict, Any
import re

from LanguageChunker.TreeSitterLanguage import TreeSitterLanguage

"""
@Author: EugeneYu
@Data: 2025/4/5
@Desc: 
"""

class KotlinChunker(TreeSitterLanguage):

    def __init__(self):
        super().__init__("kotlin")
        self.query = self.create_query("""
            (class_declaration) @class
            (function_declaration) @function
        """)
        # 添加导入语句查询
        self.query_imports = self.create_query("""
            (import_header) @import
        """)
        # 添加引用/变量使用查询
        self.query_references = self.create_query("""
            (simple_identifier) @identifier
        """)

    def extract_imports(self, tree, code_bytes):
        """提取代码中的所有导入信息"""
        imports = []
        import_captures = self.query_imports.captures(tree.root_node)
        
        for capture in import_captures:
            import_node = capture[0]
            import_text = self._get_node_text(import_node, code_bytes)
            
            # 处理import语句，提取包路径
            matches = re.search(r'import\s+(.+?)(?:\s+as\s+.+)?$', import_text)
            if matches:
                package_path = matches.group(1).strip()
                imports.append(package_path)
                
        return imports

    def extract_references(self, code_node, code_bytes):
        """提取节点中引用的标识符"""
        references = set()
        identifier_captures = self.query_references.captures(code_node)
        for capture in identifier_captures:
            identifier_node = capture[0]
            identifier = self._get_node_text(identifier_node, code_bytes)
            
            # 排除Kotlin关键字
            keywords = {"val", "var", "fun", "class", "object", "interface", "override", "private", "public", 
                       "protected", "internal", "return", "if", "else", "when", "true", "false", "null", "this", "super"}
            if identifier and identifier not in keywords:
                references.add(identifier)
                
        return list(references)

    def chunk_code(self, code: str) -> List[Tuple[str, Dict[str, Any]]]:
        chunks = []
        code_bytes = code.encode('utf-8')
        tree = self.parser.parse(code_bytes)
        
        # 提取所有导入信息
        all_imports = self.extract_imports(tree, code_bytes)

        captures = self.query.captures(tree.root_node)
        
        for node, node_type in captures:
            code_content = self._get_node_text(node, code_bytes)
            start_line, end_line = self._get_node_lines(node)
            
            # 提取引用
            references = self.extract_references(node, code_bytes)
            
            name = "Unknown"
            if node_type == "class":
                for child in node.children:
                    if child.type == "simple_identifier":
                        name = self._get_node_text(child, code_bytes)
                        break

                meta = {
                    "content": code_content,
                    "start_line": start_line + 1,
                    "end_line": end_line + 1,
                    "chunk_type": "class",
                    "name": name,
                    "language": "kotlin",
                    "imports": all_imports,
                    "references": references
                }
                chunks.append((code_content, meta))
                
            elif node_type == "function":
                for child in node.children:
                    if child.type == "simple_identifier":
                        name = self._get_node_text(child, code_bytes)
                        break
                
                parent_class = None
                is_method = False
                parent = node.parent
                while parent:
                    if parent.type == "class_declaration":
                        is_method = True
                        for child in parent.children:
                            if child.type == "simple_identifier":
                                parent_class = self._get_node_text(child, code_bytes)
                                break
                        break
                    parent = parent.parent
                
                meta = {
                    "content": code_content,
                    "start_line": start_line + 1,
                    "end_line": end_line + 1,
                    "chunk_type": "method" if is_method else "function",
                    "name": name,
                    "parent": parent_class,
                    "language": "kotlin",
                    "imports": all_imports,
                    "references": references
                }
                chunks.append((code_content, meta))

        return chunks
