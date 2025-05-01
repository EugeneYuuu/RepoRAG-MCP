import os
import json
import hashlib
import time
from typing import Dict, Set, Tuple
from pathlib import Path

"""
@Author: EugeneYu
@Data: 2025/4/6
@Desc: 增量构建代码库
"""

class IncrementalBuilder:
    def __init__(self, repo_path: str, cache_dir: str = ".build_cache"):
        self.repo_path = os.path.abspath(repo_path)
        self.cache_dir = cache_dir
        repo_name = os.path.basename(self.repo_path)
        self.cache_file = os.path.join(cache_dir, f"{repo_name}_file_state.json")
        self._ensure_cache_dir()
        
    def _ensure_cache_dir(self):
        os.makedirs(self.cache_dir, exist_ok=True)
        
    def _calculate_file_hash(self, file_path: str) -> str:
        hash_md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    
    def _get_file_info(self, file_path: str) -> Tuple[float, str]:
        mtime = os.path.getmtime(file_path)
        file_hash = self._calculate_file_hash(file_path)
        return mtime, file_hash
    
    def _load_cache(self) -> Dict[str, Tuple[float, str]]:
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    data = json.load(f)
                    if isinstance(data, dict) and 'files' in data:
                        cache_data = data
                    else:
                        cache_data = {
                            'files': data,
                            'deleted_files': []
                        }
                return {
                    'files': {os.path.relpath(k, self.repo_path): tuple(v) 
                             for k, v in cache_data['files'].items()},
                    'deleted_files': set(cache_data.get('deleted_files', []))
                }
            except Exception as e:
                print(f"Warning: Failed to load cache file: {e}")
                return {'files': {}, 'deleted_files': set()}
        return {'files': {}, 'deleted_files': set()}
    
    def _save_cache(self, cache: Dict):
        try:
            abs_cache = {
                'files': {os.path.join(self.repo_path, k): list(v) 
                         for k, v in cache['files'].items()},
                'deleted_files': list(cache['deleted_files'])
            }
            with open(self.cache_file, 'w') as f:
                json.dump(abs_cache, f, indent=2)
        except Exception as e:
            print(f"Warning: Failed to save cache file: {e}")
    
    def _get_all_code_files(self) -> Set[str]:
        code_extensions = {
            '.py',     # Python
            '.js',     # JavaScript
            '.jsx',    # React JSX
            '.ts',     # TypeScript
            '.tsx',    # React TSX
            '.java',   # Java
            '.kt',     # Kotlin
            '.kts',    # Kotlin Script
            '.c',      # C
            '.cpp',    # C++
            '.h',      # C/C++ header
            '.hpp',    # C++ header
            '.cs',     # C#
            '.go',     # Go
            '.rb',     # Ruby
            '.php',    # PHP
            '.rs',     # Rust
            '.xml',    # XML
            '.swift',  # Swift
            '.objc',   # Objective-C
            '.scala',  # Scala
        }
        code_files = set()
        file_count = 0
        
        for root, _, files in os.walk(self.repo_path):
            if '.git' in root or 'node_modules' in root:
                continue
            for file in files:
                if os.path.splitext(file)[1].lower() in code_extensions:
                    rel_path = os.path.relpath(os.path.join(root, file), self.repo_path)
                    code_files.add(rel_path)
                    file_count += 1
        
        print(f"Found {file_count} code files in repository")
        return code_files
    
    def get_changed_files(self) -> Set[str]:
        cache = self._load_cache()
        current_files = self._get_all_code_files()
        changed_files = set()
        new_files = []
        modified_files = []
        deleted_files = []
        
        for rel_path in current_files:
            try:
                abs_path = os.path.join(self.repo_path, rel_path)
                current_mtime, current_hash = self._get_file_info(abs_path)
                if rel_path not in cache['files']:
                    new_files.append(rel_path)
                    changed_files.add(abs_path)
                else:
                    cached_mtime, cached_hash = cache['files'][rel_path]
                    if current_mtime > cached_mtime or current_hash != cached_hash:
                        modified_files.append(rel_path)
                        changed_files.add(abs_path)
            except Exception as e:
                print(f"Warning: Failed to process {rel_path}: {e}")
                changed_files.add(os.path.join(self.repo_path, rel_path))
        
        newly_deleted_files = set()
        for rel_path in cache['files']:
            if rel_path not in current_files and rel_path not in cache['deleted_files']:
                deleted_files.append(rel_path)
                newly_deleted_files.add(rel_path)
        
        cache['deleted_files'].update(newly_deleted_files)
        self._save_cache(cache)
        
        if new_files or modified_files or deleted_files:
            print("\nRepository changes detected:")
            if new_files:
                print("\nNew files:")
                for file in new_files:
                    print(f"  + {file}")
            if modified_files:
                print("\nModified files:")
                for file in modified_files:
                    print(f"  * {file}")
            if deleted_files:
                print("\nDeleted files:")
                for file in deleted_files:
                    print(f"  - {file}")
            print()
        
        return changed_files
    
    def update_cache(self, processed_files: Set[str]):
        cache = self._load_cache()
        
        for abs_path in processed_files:
            try:
                rel_path = os.path.relpath(abs_path, self.repo_path)
                cache['files'][rel_path] = self._get_file_info(abs_path)
            except Exception as e:
                print(f"Warning: Failed to update cache for {abs_path}: {e}")
        
        self._save_cache(cache) 