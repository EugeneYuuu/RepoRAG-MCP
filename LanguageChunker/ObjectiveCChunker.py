from typing import List, Tuple, Dict, Any
import re

from LanguageChunker.TreeSitterLanguage import TreeSitterLanguage

"""
@Author: EugeneYu
@Data: 2025/4/5
@Desc: 
"""

class ObjectiveCChunker(TreeSitterLanguage):

    def __init__(self):
        super().__init__("objc")
        self.query = self.create_query("""
            (class_interface
              name: (identifier) @class_name) @class_interface
              
            (category_interface
              name: (identifier) @category_class_name
              category: (identifier) @category_name) @category_interface
              
            (protocol_declaration
              name: (identifier) @protocol_name) @protocol
              
            (class_implementation
              name: (identifier) @impl_class_name) @class_implementation
              
            (category_implementation
              name: (identifier) @category_impl_class_name
              category: (identifier) @category_impl_name) @category_implementation
              
            (method_declaration) @method
        """)
        # 添加导入语句查询
        # self.query_imports = self.create_query("""
        #     (import_declaration) @import
        #     (include) @include
        #     (preprocessor_include) @include
        # """)
        # 添加引用/变量使用查询
        self.query_references = self.create_query("""
            (identifier) @identifier
        """)

    def extract_imports(self, tree, code_bytes):
        """提取代码中的所有导入信息"""
        imports = []
        import_captures = self.query_imports.captures(tree.root_node)
        
        for capture in import_captures:
            node, node_type = capture
            
            if node_type == "import":
                # 处理 #import 语句
                import_text = self._get_node_text(node, code_bytes)
                import_match = re.search(r'#import\s+[<"](.+?)[>"]', import_text)
                if import_match:
                    import_path = import_match.group(1).strip()
                    imports.append(import_path)
            
            elif node_type == "include":
                # 处理 #include 语句
                include_text = self._get_node_text(node, code_bytes)
                include_match = re.search(r'#include\s+[<"](.+?)[>"]', include_text)
                if include_match:
                    include_path = include_match.group(1).strip()
                    imports.append(include_path)
                
        return imports

    def extract_references(self, code_node, code_bytes):
        """提取节点中引用的标识符"""
        references = set()
        identifier_captures = self.query_references.captures(code_node)
        for capture in identifier_captures:
            identifier_node = capture[0]
            identifier = self._get_node_text(identifier_node, code_bytes)
            
            # 排除Objective-C关键字和常见标识符
            keywords = {"self", "super", "nil", "Nil", "NULL", "YES", "NO", "id", "instancetype", 
                       "void", "BOOL", "return", "if", "else", "for", "while", "case", "break", "default",
                       "class", "interface", "implementation", "protocol", "property", "synthesize", "dynamic"}
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

            if node_type == "class_interface":
                if i + 1 < len(captures) and captures[i + 1][1] == "class_name":
                    name_node = captures[i + 1][0]
                    class_name = self._get_node_text(name_node, code_bytes)
                    start_line, end_line = self._get_node_lines(node)
                    
                    # 提取类接口中的引用
                    references = self.extract_references(node, code_bytes)
                    
                    meta = {
                        "content": self._get_node_text(node, code_bytes),
                        "start_line": start_line + 1,
                        "end_line": end_line + 1,
                        "chunk_type": "class_interface",
                        "name": class_name,
                        "language": "objc",
                        "imports": all_imports,
                        "references": references
                    }
                    
                    chunks.append((meta["content"], meta))
                    i += 2
                else:
                    i += 1
                    
            elif node_type == "category_interface":
                class_name = None
                category_name = None
                
                if i + 1 < len(captures) and captures[i + 1][1] == "category_class_name":
                    class_name_node = captures[i + 1][0]
                    class_name = self._get_node_text(class_name_node, code_bytes)
                
                if i + 2 < len(captures) and captures[i + 2][1] == "category_name":
                    category_name_node = captures[i + 2][0]
                    category_name = self._get_node_text(category_name_node, code_bytes)
                
                if class_name:
                    start_line, end_line = self._get_node_lines(node)
                    
                    # 提取分类接口中的引用
                    references = self.extract_references(node, code_bytes)
                    
                    meta = {
                        "content": self._get_node_text(node, code_bytes),
                        "start_line": start_line + 1,
                        "end_line": end_line + 1,
                        "chunk_type": "category_interface",
                        "name": class_name,
                        "category": category_name,
                        "language": "objc",
                        "imports": all_imports,
                        "references": references
                    }
                    
                    chunks.append((meta["content"], meta))
                    i += 3 if category_name else 2
                else:
                    i += 1
                    
            elif node_type == "protocol":
                if i + 1 < len(captures) and captures[i + 1][1] == "protocol_name":
                    name_node = captures[i + 1][0]
                    protocol_name = self._get_node_text(name_node, code_bytes)
                    start_line, end_line = self._get_node_lines(node)
                    
                    # 提取协议中的引用
                    references = self.extract_references(node, code_bytes)
                    
                    meta = {
                        "content": self._get_node_text(node, code_bytes),
                        "start_line": start_line + 1,
                        "end_line": end_line + 1,
                        "chunk_type": "protocol",
                        "name": protocol_name,
                        "language": "objc",
                        "imports": all_imports,
                        "references": references
                    }
                    
                    chunks.append((meta["content"], meta))
                    i += 2
                else:
                    i += 1
                    
            elif node_type == "class_implementation":
                if i + 1 < len(captures) and captures[i + 1][1] == "impl_class_name":
                    name_node = captures[i + 1][0]
                    class_name = self._get_node_text(name_node, code_bytes)
                    start_line, end_line = self._get_node_lines(node)
                    
                    # 提取类实现中的引用
                    references = self.extract_references(node, code_bytes)
                    
                    meta = {
                        "content": self._get_node_text(node, code_bytes),
                        "start_line": start_line + 1,
                        "end_line": end_line + 1,
                        "chunk_type": "class_implementation",
                        "name": class_name,
                        "language": "objc",
                        "imports": all_imports,
                        "references": references
                    }
                    
                    chunks.append((meta["content"], meta))
                    i += 2
                else:
                    i += 1
                    
            elif node_type == "category_implementation":
                class_name = None
                category_name = None
                
                if i + 1 < len(captures) and captures[i + 1][1] == "category_impl_class_name":
                    class_name_node = captures[i + 1][0]
                    class_name = self._get_node_text(class_name_node, code_bytes)
                
                if i + 2 < len(captures) and captures[i + 2][1] == "category_impl_name":
                    category_name_node = captures[i + 2][0]
                    category_name = self._get_node_text(category_name_node, code_bytes)
                
                if class_name:
                    start_line, end_line = self._get_node_lines(node)
                    
                    # 提取分类实现中的引用
                    references = self.extract_references(node, code_bytes)
                    
                    meta = {
                        "content": self._get_node_text(node, code_bytes),
                        "start_line": start_line + 1,
                        "end_line": end_line + 1,
                        "chunk_type": "category_implementation",
                        "name": class_name,
                        "category": category_name,
                        "language": "objc",
                        "imports": all_imports,
                        "references": references
                    }
                    
                    chunks.append((meta["content"], meta))
                    i += 3 if category_name else 2
                else:
                    i += 1
                    
            elif node_type == "method":
                method_content = self._get_node_text(node, code_bytes)
                start_line, end_line = self._get_node_lines(node)
                
                # 提取方法中的引用
                references = self.extract_references(node, code_bytes)
                
                # Extract method scope
                method_scope = None
                for child in node.children:
                    if child.type == "class_scope":
                        method_scope = "+"
                        break
                    elif child.type == "instance_scope":
                        method_scope = "-"
                        break
                
                method_name = "Unknown"
                found_scope = False
                for child in node.children:
                    if found_scope and child.type == "identifier":
                        method_name = self._get_node_text(child, code_bytes)
                        break
                    
                    if child.type in ["class_scope", "instance_scope"]:
                        found_scope = True
                
                parent_class = None
                parent_category = None
                parent = node.parent
                
                while parent:
                    if parent.type in ["class_interface", "class_implementation"]:
                        # Find parent class name
                        for j, cap in enumerate(captures):
                            if cap[0] == parent and cap[1] in ["class_interface", "class_implementation"]:
                                if j + 1 < len(captures) and captures[j + 1][1] in ["class_name", "impl_class_name"]:
                                    class_name_node = captures[j + 1][0]
                                    parent_class = self._get_node_text(class_name_node, code_bytes)
                                break
                        break
                    elif parent.type in ["category_interface", "category_implementation"]:
                        # Find parent class and category names
                        for j, cap in enumerate(captures):
                            if cap[0] == parent and cap[1] in ["category_interface", "category_implementation"]:
                                if j + 1 < len(captures) and captures[j + 1][1] in ["category_class_name", "category_impl_class_name"]:
                                    class_name_node = captures[j + 1][0]
                                    parent_class = self._get_node_text(class_name_node, code_bytes)
                                
                                if j + 2 < len(captures) and captures[j + 2][1] in ["category_name", "category_impl_name"]:
                                    category_name_node = captures[j + 2][0]
                                    parent_category = self._get_node_text(category_name_node, code_bytes)
                                break
                        break
                    parent = parent.parent
                
                meta = {
                    "content": method_content,
                    "start_line": start_line + 1,
                    "end_line": end_line + 1,
                    "chunk_type": "method",
                    "name": method_name,
                    "scope": method_scope,
                    "parent": parent_class,
                    "category": parent_category,
                    "language": "objc",
                    "imports": all_imports,
                    "references": references
                }
                
                chunks.append((method_content, meta))
                i += 1
            else:
                i += 1

        return chunks 