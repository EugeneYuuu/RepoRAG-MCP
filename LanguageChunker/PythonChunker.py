from typing import List, Tuple, Dict, Any
from LanguageChunker.TreeSitterLanguage import TreeSitterLanguage

"""
@Author: EugeneYu
@Data: 2025/4/5
@Desc: 
"""


class PythonChunker(TreeSitterLanguage):

    def __init__(self):
        super().__init__("python")
        self.query_class = self.create_query("""
            (class_definition
              name: (identifier) @class_name) @class
        """)
        self.query_function = self.create_query("""
            (function_definition
              name: (identifier) @function_name) @function
        """)
        self.query_method = self.create_query("""
            (class_definition
              body: (block 
                (function_definition
                  name: (identifier) @method_name) @method))
        """)
        # 添加导入语句查询
        self.query_imports = self.create_query("""
            (import_statement) @import
            (import_from_statement) @import_from
        """)
        # 添加引用/变量使用查询
        self.query_references = self.create_query("""
            (identifier) @identifier
        """)

    def extract_imports(self, node, code_bytes):
        """提取节点中的导入信息"""
        imports = []
        import_text = self._get_node_text(node, code_bytes)
        if node.type == "import_statement":
            # 处理 import xxx 形式
            parts = import_text.replace("import", "").strip().split(",")
            for part in parts:
                part = part.strip()
                if part:
                    imports.append(part)
        elif node.type == "import_from_statement":
            # 处理 from xxx import yyy 形式
            parts = import_text.split("import")
            if len(parts) > 1:
                module = parts[0].replace("from", "").strip()
                items = parts[1].strip().split(",")
                for item in items:
                    item = item.strip()
                    if item:
                        imports.append(f"{module}.{item}")
        return imports

    def extract_references(self, code_node, code_bytes):
        """提取节点中引用的标识符"""
        references = set()
        # 获取节点内的所有标识符
        identifier_captures = self.query_references.captures(code_node)
        for capture in identifier_captures:
            identifier_node = capture[0]
            identifier = self._get_node_text(identifier_node, code_bytes)
            # 排除一些常见的Python关键字
            keywords = {"self", "None", "True", "False", "if", "else", "for", "while", "try", "except", "def", "class", "return", "with", "as"}
            if identifier and identifier not in keywords:
                references.add(identifier)
        return list(references)

    def chunk_code(self, code: str) -> List[Tuple[str, Dict[str, Any]]]:
        chunks = []
        code_bytes = code.encode('utf-8')
        tree = self.parser.parse(code_bytes)
        
        # 提取全局导入语句
        all_imports = []
        import_captures = self.query_imports.captures(tree.root_node)
        for capture in import_captures:
            import_node = capture[0]
            imports = self.extract_imports(import_node, code_bytes)
            all_imports.extend(imports)

        # Find classes
        class_captures = self.query_class.captures(tree.root_node)
        for i in range(0, len(class_captures), 2):
            if i + 1 >= len(class_captures):
                continue

            class_node = class_captures[i][0]
            class_name_node = class_captures[i + 1][0]
            class_name = self._get_node_text(class_name_node, code_bytes)
            start_line, end_line = self._get_node_lines(class_node)
            
            # 提取类中的引用
            references = self.extract_references(class_node, code_bytes)

            meta = {
                "content" : self._get_node_text(class_node, code_bytes),
                "start_line" : start_line + 1,  # 1-indexed
                "end_line" : end_line + 1,  # 1-indexed
                "chunk_type" : "class",
                "name" : class_name,
                "language" : "python",
                "imports" : all_imports,
                "references" : references
            }

            chunks.append((meta["content"], meta))

        function_captures = self.query_function.captures(tree.root_node)
        for i in range(0, len(function_captures), 2):
            if i + 1 >= len(function_captures):
                continue

            function_node = function_captures[i][0]
            function_name_node = function_captures[i + 1][0]

            is_method = False
            parent = function_node.parent
            while parent:
                if parent.type == "class_definition":
                    is_method = True
                    break
                parent = parent.parent

            if not is_method:
                function_name = self._get_node_text(function_name_node, code_bytes)
                start_line, end_line = self._get_node_lines(function_node)
                
                # 提取函数中的引用
                references = self.extract_references(function_node, code_bytes)

                meta = {
                    "content" : self._get_node_text(function_node, code_bytes),
                    "start_line" : start_line + 1,  # 1-indexed
                    "end_line" : end_line + 1,  # 1-indexed
                    "chunk_type" : "function",
                    "name" : function_name,
                    "language" : "python",
                    "imports" : all_imports,
                    "references" : references
                }

                chunks.append((meta["content"], meta))

        method_captures = self.query_method.captures(tree.root_node)
        for i in range(0, len(method_captures), 2):
            if i + 1 >= len(method_captures):
                continue

            method_node = method_captures[i][0]
            method_name_node = method_captures[i + 1][0]
            method_name = self._get_node_text(method_name_node, code_bytes)

            parent_class = None
            parent = method_node.parent
            while parent:
                if parent.type == "class_definition":
                    for cap in class_captures:
                        if cap[0] == parent:
                            class_name_idx = class_captures.index(cap) + 1
                            if class_name_idx < len(class_captures):
                                class_name_node = class_captures[class_name_idx][0]
                                parent_class = self._get_node_text(class_name_node, code_bytes)
                    break
                parent = parent.parent

            start_line, end_line = self._get_node_lines(method_node)
            
            # 提取方法中的引用
            references = self.extract_references(method_node, code_bytes)

            meta = {
                "content" : self._get_node_text(method_node, code_bytes),
                "start_line" : start_line + 1,  # 1-indexed
                "end_line" : end_line + 1,  # 1-indexed
                "chunk_type" : "method",
                "name" : method_name,
                "parent" : parent_class,
                "language" : "python",
                "imports" : all_imports,
                "references" : references
            }

            chunks.append((meta["content"], meta))

        return chunks
