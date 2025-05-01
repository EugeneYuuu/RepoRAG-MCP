import glob
import os
import argparse
import subprocess
import tempfile
import time
from incrementalBuilder import IncrementalBuilder

"""
@Author: EugeneYu
@Data: 2025/4/5
@Desc: 本地仓库代码RAG流程
"""

def run_command(command, description=None):
    if description:
        print(f"\n{'-'*80}\n{description}\n{'-'*80}")
    
    print(f"Running: {command}")
    start_time = time.time()
    
    try:
        result = subprocess.run(command, shell=True, check=True, text=True, 
                               capture_output=True)
        
        print(result.stdout)
        if result.stderr:
            print(f"Stderr: {result.stderr}")
            
        elapsed = time.time() - start_time
        print(f"Command completed in {elapsed:.2f} seconds")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Command failed with exit code {e.returncode}")
        print(f"Stdout: {e.stdout}")
        print(f"Stderr: {e.stderr}")
        return False

def process_local_repository(repo_path, model="sentence-transformers/all-MiniLM-L6-v2", incremental=True):
    os.makedirs("artifacts", exist_ok=True)
    os.makedirs("artifacts/curated", exist_ok=True)
    os.makedirs("artifacts/chunks", exist_ok=True)
    os.makedirs("artifacts/vector_stores", exist_ok=True)
    
    repo_path = os.path.abspath(repo_path)
    repo_name = os.path.basename(repo_path)
    
    print(f"Processing local repository: {repo_path}")
    print(f"Repository name: {repo_name}")
    
    builder = IncrementalBuilder(repo_path)
    changed_files = builder.get_changed_files() if incremental else set()
    
    if incremental and not changed_files:
        print("No files have changed since last build. Skipping processing.")
        return True
    
    if incremental:
        print(f"Found {len(changed_files)} changed files:")
        for file in changed_files:
            print(f"  - {os.path.relpath(file, repo_path)}")
    
    # 定义处理步骤
    steps = {
        "curate": "Curate code files",
        "chunk": "Create Tree-Sitter based code chunks",
        "vectorize": "Create vector embeddings"
    }
    
    # 1. 代码数据清洗
    cmd = f"python codeCurator.py --input {repo_path}"
    if incremental:
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as temp_file:
            for file in changed_files:
                temp_file.write(f"{file}\n")
            temp_file_path = temp_file.name

        cmd += f" --files-list {temp_file_path}"

    if not run_command(cmd, steps["curate"]):
        print("Code curation failed. Aborting.")
        if incremental:
            os.unlink(temp_file_path)
        return False

    if incremental:
        os.unlink(temp_file_path)

    curated_path = os.path.join("artifacts", "curated", repo_name)
    if not os.path.exists(curated_path):
        print(f"Curated directory not found at {curated_path}. Aborting.")
        return False
    
    # 2. 语法树解析分块
    cmd = f"python codeChunker.py --input {curated_path}"
    if incremental:
        cmd += " --incremental"
    
    if not run_command(cmd, steps["chunk"]):
        print("AST chunking failed. Aborting.")
        return False
    
    chunk_pattern = f"artifacts/chunks/{repo_name}_code_chunks_ast.jsonl"
    chunk_files = glob.glob(chunk_pattern)
    
    if not chunk_files:
        print(f"Chunks file not found matching pattern {chunk_pattern}. Aborting.")
        return False
    
    chunks_file = chunk_files[0]
    
    # 3. 向量化
    model_short = model.split('/')[-1] if '/' in model else model
    cmd = f"python codeVectorize.py --input {chunks_file} --model {model}"
    if incremental:
        cmd += " --incremental"
    
    if not run_command(cmd, steps["vectorize"]):
        print("Vectorization failed. Aborting.")
        return False
    
    if incremental:
        builder.update_cache(changed_files)
    
    collection_name = f"code_{repo_name}_code_chunks_ast_{model_short}"
    if len(collection_name) > 63:
        collection_name = collection_name[:63]
    
    print("\nProcess completed successfully!")
    print(f"Repository: {repo_name}")
    print(f"Chunks file: {chunks_file}")
    print(f"Collection name: {collection_name}")

    return True
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--path", "-p", help="本地仓库路径")
    parser.add_argument("--model", "-m", default="sentence-transformers/all-MiniLM-L6-v2",
                       help="MiniLM")
    parser.add_argument("--no-incremental", action="store_true")
    
    args = parser.parse_args()
    
    if args.path:
        process_local_repository(args.path, args.model, not args.no_incremental)
    else:
        parser.print_help() 