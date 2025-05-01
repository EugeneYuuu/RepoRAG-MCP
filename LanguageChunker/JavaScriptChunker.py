from typing import List, Tuple, Dict, Any
import re

from LanguageChunker.TreeSitterLanguage import TreeSitterLanguage

"""
@Author: EugeneYu
@Data: 2025/4/5
@Desc: 
"""


class JavaScriptChunker(TreeSitterLanguage):

    def __init__(self):
        super().__init__("javascript")
        self.query_function = self.create_query("""
            (function_declaration
              name: (identifier) @function_name) @function

            (method_definition
              name: (property_identifier) @method_name) @method

            (arrow_function
              parameter: (identifier) @param_name) @arrow_function

            (class_declaration
              name: (identifier) @class_name) @class
        """)
        # 添加导入语句查询
        self.query_imports = self.create_query("""
            (import_statement) @import
            (import_specifier
              name: (identifier) @import_name)
            (import_clause
              (identifier) @import_default)
            (namespace_import
              (identifier) @namespace_import)
        """)
        # 添加引用/变量使用查询
        self.query_references = self.create_query("""
            (identifier) @identifier
        """)

    def extract_imports(self, tree, code_bytes):
        """提取代码中的所有导入信息"""
        imports = []
        import_captures = self.query_imports.captures(tree.root_node)
        
        current_source = None
        for i, capture in enumerate(import_captures):
            node, node_type = capture
            
            if node_type == "import":
                # 找到import语句的源
                import_text = self._get_node_text(node, code_bytes)
                source_match = re.search(r'from\s+[\'"](.+?)[\'"]', import_text)
                if source_match:
                    current_source = source_match.group(1)
            
            elif node_type in ["import_name", "import_default", "namespace_import"] and current_source:
                import_name = self._get_node_text(node, code_bytes)
                imports.append(f"{current_source}.{import_name}")
                
        return imports

    def extract_references(self, code_node, code_bytes):
        """提取节点中引用的标识符"""
        references = set()
        # 获取节点内的所有标识符
        identifier_captures = self.query_references.captures(code_node)
        for capture in identifier_captures:
            identifier_node = capture[0]
            identifier = self._get_node_text(identifier_node, code_bytes)
            # 排除一些常见的JavaScript关键字
            keywords = {"function", "return", "const", "let", "var", "if", "else", "for", "while", "try", "catch", "this", "class", "true", "false", "null", "undefined"}
            if identifier and identifier not in keywords:
                references.add(identifier)
        return list(references)

    def chunk_code(self, code: str) -> List[Tuple[str, Dict[str, Any]]]:
        chunks = []
        code_bytes = code.encode('utf-8')
        tree = self.parser.parse(code_bytes)
        
        # 提取所有导入信息
        all_imports = self.extract_imports(tree, code_bytes)

        captures = self.query_function.captures(tree.root_node)
        i = 0
        while i < len(captures):
            node = captures[i][0]
            node_type = captures[i][1]

            if node_type == "function":
                # Get function name from the next capture
                if i + 1 < len(captures) and captures[i + 1][1] == "function_name":
                    name_node = captures[i + 1][0]
                    function_name = self._get_node_text(name_node, code_bytes)
                    start_line, end_line = self._get_node_lines(node)
                    
                    # 提取函数中的引用
                    references = self.extract_references(node, code_bytes)

                    meta = {
                        "content" : self._get_node_text(node, code_bytes),
                        "start_line" : start_line + 1,
                        "end_line" : end_line + 1,
                        "chunk_type" : "function",
                        "name" : function_name,
                        "language" : "javascript",
                        "imports" : all_imports,
                        "references" : references
                    }

                    chunks.append((meta["content"], meta))

                    i += 2
                else:
                    i += 1

            elif node_type == "method":
                if i + 1 < len(captures) and captures[i + 1][1] == "method_name":
                    name_node = captures[i + 1][0]
                    method_name = self._get_node_text(name_node, code_bytes)

                    parent_class = None
                    parent = node.parent
                    while parent:
                        if parent.type == "class_declaration":
                            for j, cap in enumerate(captures):
                                if cap[0] == parent and cap[1] == "class":
                                    if j + 1 < len(captures) and captures[j + 1][1] == "class_name":
                                        class_name_node = captures[j + 1][0]
                                        parent_class = self._get_node_text(class_name_node, code_bytes)
                            break
                        parent = parent.parent

                    start_line, end_line = self._get_node_lines(node)
                    
                    # 提取方法中的引用
                    references = self.extract_references(node, code_bytes)

                    meta = {
                        "content" : self._get_node_text(node, code_bytes),
                        "start_line" : start_line + 1,
                        "end_line" : end_line + 1,
                        "chunk_type" : "method",
                        "name" : method_name,
                        "parent" : parent_class,
                        "language" : "javascript",
                        "imports" : all_imports,
                        "references" : references
                    }

                    chunks.append((meta["content"], meta))
                    i += 2
                else:
                    i += 1

            elif node_type == "class":
                if i + 1 < len(captures) and captures[i + 1][1] == "class_name":
                    name_node = captures[i + 1][0]
                    class_name = self._get_node_text(name_node, code_bytes)
                    start_line, end_line = self._get_node_lines(node)
                    
                    # 提取类中的引用
                    references = self.extract_references(node, code_bytes)

                    meta = {
                        "content" : self._get_node_text(node, code_bytes),
                        "start_line" : start_line + 1,
                        "end_line" : end_line + 1,
                        "chunk_type" : "class",
                        "name" : class_name,
                        "language" : "javascript",
                        "imports" : all_imports,
                        "references" : references
                    }

                    chunks.append((meta["content"], meta))
                    i += 2
                else:
                    i += 1

            elif node_type == "arrow_function":
                if i + 1 < len(captures) and captures[i + 1][1] == "param_name":
                    name_node = captures[i + 1][0]
                    param_name = self._get_node_text(name_node, code_bytes)
                    start_line, end_line = self._get_node_lines(node)
                    
                    # 提取箭头函数中的引用
                    references = self.extract_references(node, code_bytes)

                    meta = {
                        "content" : self._get_node_text(node, code_bytes),
                        "start_line" : start_line + 1,
                        "end_line" : end_line + 1,
                        "chunk_type" : "arrow_function",
                        "name" : f"arrow_function({param_name})",
                        "language" : "javascript",
                        "imports" : all_imports,
                        "references" : references
                    }

                    chunks.append((meta["content"], meta))
                    i += 2
                else:
                    start_line, end_line = self._get_node_lines(node)
                    
                    # 提取匿名箭头函数中的引用
                    references = self.extract_references(node, code_bytes)

                    meta = {
                        "content" : self._get_node_text(node, code_bytes),
                        "start_line" : start_line + 1,
                        "end_line" : end_line + 1,
                        "chunk_type" : "arrow_function",
                        "name" : "anonymous_arrow_function",
                        "language" : "javascript",
                        "imports" : all_imports,
                        "references" : references
                    }
                    chunks.append((meta["content"], meta))
                    i += 1
            else:
                i += 1

        return chunks
