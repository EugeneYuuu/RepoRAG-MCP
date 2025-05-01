from typing import List, Tuple, Dict, Any
import re

from LanguageChunker.TreeSitterLanguage import TreeSitterLanguage

"""
@Author: EugeneYu
@Data: 2025/4/5
@Desc: 
"""

class JavaChunker(TreeSitterLanguage):

    def __init__(self):
        super().__init__("java")
        self.query = self.create_query("""
            (class_declaration
              name: (identifier) @class_name) @class

            (method_declaration
              name: (identifier) @method_name) @method

            (constructor_declaration
              name: (identifier) @constructor_name) @constructor
        """)
        # 添加导入语句查询
        self.query_imports = self.create_query("""
            (import_declaration) @import
            (package_declaration) @package
        """)
        # 添加引用/变量使用查询
        self.query_references = self.create_query("""
            (identifier) @identifier
        """)

    def extract_imports(self, tree, code_bytes):
        """提取代码中的所有导入信息"""
        imports = []
        package_prefix = ""
        
        import_captures = self.query_imports.captures(tree.root_node)
        for capture in import_captures:
            node, node_type = capture
            
            if node_type == "package":
                # 提取包声明
                package_text = self._get_node_text(node, code_bytes)
                package_match = re.search(r'package\s+([^;]+);', package_text)
                if package_match:
                    package_prefix = package_match.group(1).strip()
            
            elif node_type == "import":
                # 提取导入语句
                import_text = self._get_node_text(node, code_bytes)
                import_match = re.search(r'import\s+(?:static\s+)?([^;]+);', import_text)
                if import_match:
                    import_path = import_match.group(1).strip()
                    imports.append(import_path)
                
        return imports

    def extract_references(self, code_node, code_bytes):
        """提取节点中引用的标识符"""
        references = set()
        identifier_captures = self.query_references.captures(code_node)
        for capture in identifier_captures:
            identifier_node = capture[0]
            identifier = self._get_node_text(identifier_node, code_bytes)
            
            # 排除Java关键字和常见标识符
            keywords = {"public", "private", "protected", "class", "interface", "extends", "implements", 
                      "return", "if", "else", "for", "while", "try", "catch", "finally", "throw", "throws",
                      "new", "this", "super", "static", "final", "void", "true", "false", "null"}
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
        i = 0
        while i < len(captures):
            node = captures[i][0]
            node_type = captures[i][1]

            if node_type == "class":
                # Get class name from the next capture
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
                        "language" : "java",
                        "imports" : all_imports,
                        "references" : references
                    }

                    chunks.append((meta["content"], meta))
                    i += 2
                else:
                    i += 1

            elif node_type == "method":
                # Get method name from the next capture
                if i + 1 < len(captures) and captures[i + 1][1] == "method_name":
                    name_node = captures[i + 1][0]
                    method_name = self._get_node_text(name_node, code_bytes)

                    # Find parent class
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
                        "language" : "java",
                        "imports" : all_imports,
                        "references" : references
                    }

                    chunks.append((meta["content"], meta))
                    i += 2
                else:
                    i += 1

            elif node_type == "constructor":
                if i + 1 < len(captures) and captures[i + 1][1] == "constructor_name":
                    name_node = captures[i + 1][0]
                    constructor_name = self._get_node_text(name_node, code_bytes)

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
                    
                    # 提取构造函数中的引用
                    references = self.extract_references(node, code_bytes)

                    meta = {
                        "content": self._get_node_text(node, code_bytes),
                        "start_line": start_line + 1,
                        "end_line": end_line + 1,
                        "chunk_type": "constructor",
                        "name": constructor_name,
                        "parent": parent_class,
                        "language": "java",
                        "imports" : all_imports,
                        "references" : references
                    }

                    chunks.append((meta["content"], meta))
                    i += 2
                else:
                    i += 1
            else:
                i += 1

        return chunks
