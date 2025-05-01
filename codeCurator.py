import os
import glob
import json
import argparse
import shutil

"""
@Author: EugeneYu
@Data: 2025/4/4
@Desc: 代码数据预处理
"""

class CodeCurator:
    def __init__(self, input_dir, specific_files=None):

        self.input_dir = input_dir
        self.output_dir = os.path.join("artifacts", "curated")
        self.specific_files = specific_files
        
        self.repo_name = os.path.basename(input_dir)
        
        metadata_file = os.path.join(input_dir, "repo_metadata.json")
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                self.metadata = json.load(f)
        else:
            self.metadata = {"name": self.repo_name}
            
        self.ignore_patterns = [
            '**/.git/**',            # Git repository info
            '**/.github/**',         # GitHub workflows etc.
            '**/.gradle/**',         # Gradle build system cache
            '**/gradle/**',          # Gradle wrapper files
            '**/gradlew',            # Gradle wrapper script
            '**/gradlew.bat',        # Gradle wrapper script for Windows
            '**/node_modules/**',    # Node.js packages
            '**/__pycache__/**',     # Python cache
            '**/build/**',           # Build artifacts
            '**/dist/**',            # Distribution artifacts
            '**/target/**',          # Java/Rust build target
            '**/.DS_Store',          # macOS metadata
            '**/*.min.js',           # Minified JS
            '**/*.min.css',          # Minified CSS
            '**/*.map',              # Source maps
            '**/*.pyc',              # Python compiled files
            '**/*.jar',              # Java archives
            '**/*.class',            # Java class files
            '**/*.so',               # Shared libraries
            '**/*.dll',              # Dynamic link libraries
            '**/*.exe',              # Executables
            '**/*.bin',              # Binary files
            '**/venv/**',            # Python virtual environments
            '**/.env/**',            # Environment files
            '**/.idea/**',           # IntelliJ IDEA files
            '**/.vscode/**',         # VSCode files
            '**/*.md',               # Markdown files (usually README)
            '**/*.txt',              # Text files (usually LICENSE)
            '**/LICENSE*',           # License files
            '**/.settings/**',       # Eclipse settings
            '**/.classpath',         # Eclipse classpath
            '**/.project',           # Eclipse project
            '**/CMakeFiles/**',      # CMake build files
            '**/CMakeCache.txt',     # CMake cache
            '**/cmake-build-*/**',   # CMake build directories
            '**/vendor/**',          # Dependencies in many languages
            '**/out/**',             # Output directories
            '**/bin/**',             # Binary output directories
            '**/obj/**',             # Object file directories
            '**/.vs/**',             # Visual Studio files
            '**/tmp/**',             # Temporary files
            '**/temp/**',            # Temporary files
            '**/*.lock',             # Lock files
            '**/package-lock.json',  # NPM lock file
            '**/yarn.lock',          # Yarn lock file
            '**/Pods/**',            # CocoaPods dependencies
            '**/.bundle/**',         # Ruby bundle
            '**/logs/**',            # Log files
            '**/*.log',              # Log files
        ]
        
        self.code_extensions = [
            '.py',     # Python
            '.js',     # JavaScript
            '.jsx',    # React JSX
            '.ts',     # TypeScript
            '.tsx',    # React TSX
            '.java',   # Java
            '.c',      # C
            '.cpp',    # C++
            '.h',      # C/C++ header
            '.hpp',    # C++ header
            '.cs',     # C#
            '.go',     # Go
            '.rb',     # Ruby
            '.php',    # PHP
            '.rs',     # Rust
            '.swift',  # Swift
            '.kt',     # Kotlin
            '.scala',  # Scala
            '.sh',     # Shell scripts
            '.bash',   # Bash scripts
            '.sql',    # SQL
            '.r',      # R
            '.html',   # HTML
            '.css',    # CSS
            '.sass',   # Sass
            '.scss',   # SCSS
            '.yaml',   # YAML
            '.yml',    # YAML alternative
            '.json',   # JSON
            '.xml',    # XML
            '.toml',   # TOML config
            '.ini',    # INI config
            '.conf',   # Config files
        ]
    
    def should_ignore(self, filepath):
        rel_path = os.path.relpath(filepath, start=self.input_dir)
        
        basename = os.path.basename(filepath)
        if basename.startswith('.'):
            return True
        
        if (rel_path.startswith('.idea') or
            rel_path.startswith('gradle') or
            '.gradle' in rel_path or
            '/build/' in filepath or
            '/build' == filepath.rstrip('/').split('/')[-1] or
            '/node_modules/' in filepath or
            '/.git/' in filepath):
            return True

        parts = rel_path.split(os.sep)
        if parts:
            # 排除文件名，只检查目录部分
            directory_parts = parts[:-1]
        else:
            directory_parts = parts

        for part in directory_parts:
            if part.lower().startswith('android') :
                return True
            if part.lower().startswith('emulator') :
                return True
            if part.lower().startswith('build-tools') :
                return True

        for pattern in self.ignore_patterns:
            if glob.fnmatch.fnmatch(rel_path, pattern):
                return True
        
        _, ext = os.path.splitext(filepath)
        return ext.lower() not in self.code_extensions
    
    def estimate_language(self, filepath):
        _, ext = os.path.splitext(filepath)
        ext = ext.lower()
        
        language_map = {
            '.py': 'python',
            '.js': 'javascript',
            '.jsx': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript',
            '.java': 'java',
            '.c': 'c',
            '.cpp': 'cpp',
            '.h': 'c',
            '.hpp': 'cpp',
            '.cs': 'csharp',
            '.go': 'go',
            '.rb': 'ruby',
            '.php': 'php',
            '.rs': 'rust',
            '.swift': 'swift',
            '.kt': 'kotlin',
            '.scala': 'scala',
            '.sh': 'bash',
            '.bash': 'bash',
            '.sql': 'sql',
            '.r': 'r',
            '.html': 'html',
            '.css': 'css',
            '.sass': 'sass',
            '.scss': 'scss',
            '.yaml': 'yaml',
            '.yml': 'yaml',
            '.json': 'json',
            '.xml': 'xml',
            '.toml': 'toml',
            '.ini': 'ini',
            '.conf': 'config',
        }
        
        return language_map.get(ext, 'unknown')
    
    def process_file(self, filepath):
        try:
            if self.should_ignore(filepath):
                return False
            
            rel_path = os.path.relpath(filepath, self.input_dir)
            output_path = os.path.join(self.output_dir, self.repo_name, rel_path)
            
            output_path = output_path + '.md'
            
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            language = self.estimate_language(filepath)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(f"# {os.path.basename(filepath)}\n\n")
                f.write(f"File path: `{rel_path}`\n\n")
                f.write(f"Programming language: {language}\n\n")
                f.write("```" + language + "\n")
                f.write(content)
                f.write("\n```\n")
            
            print(f"Processed: {filepath} -> {output_path}")
            return True
        except Exception as e:
            print(f"Error processing {filepath}: {e}")
            return False

    def process_directory(self):
        repo_output_dir = os.path.join(self.output_dir, self.repo_name)
        os.makedirs(repo_output_dir, exist_ok=True)
        
        processed_files = []
        
        if self.specific_files:
            for filepath in self.specific_files:
                if os.path.exists(filepath):
                    if self.process_file(filepath):
                        processed_files.append(filepath)
                else:
                    print(f"Warning: File not found: {filepath}")
        else:
            for root, _, files in os.walk(self.input_dir):
                for file in files:
                    filepath = os.path.join(root, file)
                    if self.process_file(filepath):
                        processed_files.append(filepath)
        
        return processed_files


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--files', nargs='*', help='Specific files to process (for incremental builds)')
    parser.add_argument('--files-list', help='Path to a file containing list of files to process')
    args = parser.parse_args()

    specific_files = None
    if args.files:
        specific_files = args.files
    elif args.files_list:
        with open(args.files_list, 'r') as f:
            specific_files = [line.strip() for line in f if line.strip()]

    curator = CodeCurator(args.input, specific_files)
    processed_files = curator.process_directory()

    print(f"\nProcessed {len(processed_files)} files:")