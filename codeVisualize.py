import os
import argparse
import numpy as np
import plotly.graph_objects as go
import chromadb
from umap import UMAP
import webbrowser
import random
from sklearn.cluster import KMeans

"""
@Author: EugeneYu
@Data: 2025/4/4
@Desc: 将高维的Embedding数据进行可视化
"""

class EmbeddingVisualizer:
    def __init__(
            self,
            db_directory: str,
            collection_name: str,
            max_points: int = 2000,
            random_seed: int = 42,
            n_clusters: int = 10,
            outlier_threshold: float = 3.0
    ):

        self.db_directory = db_directory
        self.collection_name = collection_name
        visualization_dir = "artifacts/visualizations"
        self.output_file = f"{visualization_dir}/visualization_{collection_name}_{random_seed}_{max_points}_{n_clusters}_{outlier_threshold}.html"
        self.max_points = max_points
        self.random_seed = random_seed
        self.n_clusters = n_clusters
        self.outlier_threshold = outlier_threshold

        random.seed(self.random_seed)
        np.random.seed(self.random_seed)

        print(f"Connecting to ChromaDB at {db_directory}")
        self.client = chromadb.PersistentClient(path=db_directory)

        try:
            self.collection = self.client.get_collection(name=collection_name)
            print(f"Found collection: {collection_name} with {self.collection.count()} documents")
        except Exception as e:
            print(f"Error accessing collection: {e}")
            raise

    def get_embeddings(self):
        print("Retrieving embeddings from ChromaDB...")

        try:
            result = self.collection.get(
                include=['embeddings', 'documents', 'metadatas']
            )
        except IndexError as e:
            print(f"Error accessing embeddings: {e}")
            print("Trying alternative approach with IDs...")

            all_ids = self.collection.get(include=[])['ids']
            print(f"Found {len(all_ids)} IDs in the collection")

            batch_size = 100
            all_embeddings = []
            all_documents = []
            all_metadatas = []
            valid_ids = []

            for i in range(0, len(all_ids), batch_size):
                batch_ids = all_ids[i:i + batch_size]
                try:
                    batch_result = self.collection.get(
                        ids=batch_ids,
                        include=['embeddings', 'documents', 'metadatas']
                    )

                    for j, id_val in enumerate(batch_ids):
                        if j < len(batch_result['embeddings']):
                            all_embeddings.append(batch_result['embeddings'][j])
                            all_documents.append(batch_result['documents'][j])
                            all_metadatas.append(batch_result['metadatas'][j])
                            valid_ids.append(id_val)

                    print(f"Processed batch {i // batch_size + 1}/{(len(all_ids) + batch_size - 1) // batch_size}")
                except Exception as batch_error:
                    print(f"Error in batch {i // batch_size + 1}: {batch_error}")
                    continue

            embeddings = np.array(all_embeddings) if all_embeddings else np.array([])
            documents = all_documents
            metadatas = all_metadatas
            ids = valid_ids
        else:
            embeddings = np.array(result['embeddings'])
            documents = result['documents']
            metadatas = result['metadatas']
            ids = result['ids']

        if len(embeddings) == 0:
            raise ValueError(
                "No embeddings could be retrieved from the collection. The collection may be empty or corrupted.")

        print(f"Retrieved {len(embeddings)} embeddings with {embeddings.shape[1]} dimensions")

        if len(embeddings) > self.max_points:
            print(f"Sampling {self.max_points} out of {len(embeddings)} points for visualization")
            indices = np.random.choice(len(embeddings), self.max_points, replace=False)
            embeddings = embeddings[indices]
            documents = [documents[i] for i in indices]
            metadatas = [metadatas[i] for i in indices]
            ids = [ids[i] for i in indices]

        return embeddings, documents, metadatas, ids

    def reduce_dimensions(self, embeddings):
        print("Reducing dimensions using UMAP...")

        reducer_3d = UMAP(n_components=3, random_state=self.random_seed, n_neighbors=15, min_dist=0.1)
        embeddings_3d = reducer_3d.fit_transform(embeddings)
        print(f"Reduced dimensions from {embeddings.shape[1]} to 3")

        reducer_2d = UMAP(n_components=2, random_state=self.random_seed, n_neighbors=15, min_dist=0.1)
        embeddings_2d = reducer_2d.fit_transform(embeddings)
        print(f"Reduced dimensions from {embeddings.shape[1]} to 2")

        return embeddings_2d, embeddings_3d

    def cluster_embeddings(self, embeddings):
        print(f"Clustering embeddings into {self.n_clusters} groups...")
        kmeans = KMeans(n_clusters=self.n_clusters, random_state=self.random_seed)
        clusters = kmeans.fit_predict(embeddings)
        return clusters

    def filter_outliers(self, embeddings_2d, embeddings_3d, documents, metadatas, ids, clusters):

        print(f"Filtering outliers with threshold {self.outlier_threshold}...")

        z_scores_3d = np.zeros_like(embeddings_3d)
        for dim in range(3):
            mean = np.mean(embeddings_3d[:, dim])
            std = np.std(embeddings_3d[:, dim])
            if std > 0:
                z_scores_3d[:, dim] = np.abs((embeddings_3d[:, dim] - mean) / std)

        max_z_scores_3d = np.max(z_scores_3d, axis=1)
        outliers_3d = max_z_scores_3d > self.outlier_threshold

        z_scores_2d = np.zeros_like(embeddings_2d)
        for dim in range(2):
            mean = np.mean(embeddings_2d[:, dim])
            std = np.std(embeddings_2d[:, dim])
            if std > 0:
                z_scores_2d[:, dim] = np.abs((embeddings_2d[:, dim] - mean) / std)

        max_z_scores_2d = np.max(z_scores_2d, axis=1)
        outliers_2d = max_z_scores_2d > self.outlier_threshold

        outliers = outliers_2d | outliers_3d

        num_outliers = np.sum(outliers)
        print(f"Filtered out {num_outliers} outliers ({num_outliers / len(outliers) * 100:.1f}% of points)")

        keep_indices = ~outliers
        embeddings_2d_filtered = embeddings_2d[keep_indices]
        embeddings_3d_filtered = embeddings_3d[keep_indices]
        documents_filtered = [doc for i, doc in enumerate(documents) if keep_indices[i]]
        metadatas_filtered = [meta for i, meta in enumerate(metadatas) if keep_indices[i]]
        ids_filtered = [id for i, id in enumerate(ids) if keep_indices[i]]
        clusters_filtered = clusters[keep_indices]

        return embeddings_2d_filtered, embeddings_3d_filtered, documents_filtered, metadatas_filtered, ids_filtered, clusters_filtered

    def create_visualization(self, embeddings_2d, embeddings_3d, documents, metadatas, ids, clusters, original_dims):
        print("Creating visualization with 2D/3D toggle...")

        colors = [
            '#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd',
            '#8c564b', '#e377c2', '#7f7f7f', '#bcbd22', '#17becf',
            '#aec7e8', '#ffbb78', '#98df8a', '#ff9896', '#c5b0d5'
        ]

        hover_texts = []
        for i in range(len(documents)):
            source_path = metadatas[i]['source']
            filename = os.path.basename(source_path)

            doc_preview = documents[i][:200] + "..." if len(documents[i]) > 200 else documents[i]
            doc_preview = doc_preview.replace("\n", "<br>")

            hover_text = f"<b>ID:</b> {ids[i]}<br><b>File:</b> {filename}<br><b>Preview:</b><br>{doc_preview}"
            hover_texts.append(hover_text)

        fig = go.Figure()

        for cluster_id in range(self.n_clusters):
            cluster_indices = np.where(clusters == cluster_id)[0]

            fig.add_trace(go.Scatter3d(
                x=embeddings_3d[cluster_indices, 0],
                y=embeddings_3d[cluster_indices, 1],
                z=embeddings_3d[cluster_indices, 2],
                mode='markers',
                marker=dict(
                    size=5,
                    color=colors[cluster_id % len(colors)],
                    opacity=0.7,
                ),
                text=[hover_texts[i] for i in cluster_indices],
                hoverinfo='text',
                name=f'Cluster {cluster_id}',
                scene='scene',
                visible=True
            ))

        for cluster_id in range(self.n_clusters):
            cluster_indices = np.where(clusters == cluster_id)[0]

            fig.add_trace(go.Scatter(
                x=embeddings_2d[cluster_indices, 0],
                y=embeddings_2d[cluster_indices, 1],
                mode='markers',
                marker=dict(
                    size=8,
                    color=colors[cluster_id % len(colors)],
                    opacity=0.7,
                ),
                text=[hover_texts[i] for i in cluster_indices],
                hoverinfo='text',
                name=f'Cluster {cluster_id}',
                visible=False
            ))

        button_3d = dict(
            label="3D View",
            method="update",
            args=[
                {"visible": [True] * self.n_clusters + [False] * self.n_clusters},
                {"scene": {"xaxis": {"title": "UMAP Dimension 1"},
                           "yaxis": {"title": "UMAP Dimension 2"},
                           "zaxis": {"title": "UMAP Dimension 3"}},
                 "xaxis": {"title": ""},
                 "yaxis": {"title": ""},
                 "title": {
                     "text": f"3D Visualization of {self.collection_name} Embeddings (Original Dimensions: {original_dims})",
                     "y": 0.95,
                     "x": 0.5,
                     "xanchor": "center",
                     "yanchor": "top",
                     "font": {"size": 24}}}
            ]
        )

        button_2d = dict(
            label="2D View",
            method="update",
            args=[
                {"visible": [False] * self.n_clusters + [True] * self.n_clusters},
                {"xaxis": {"title": "UMAP Dimension 1"},
                 "yaxis": {"title": "UMAP Dimension 2"},
                 "scene": {"xaxis": {"title": ""},
                           "yaxis": {"title": ""},
                           "zaxis": {"title": ""}},
                 "title": {
                     "text": f"2D Visualization of {self.collection_name} Embeddings (Original Dimensions: {original_dims})",
                     "y": 0.95,
                     "x": 0.5,
                     "xanchor": "center",
                     "yanchor": "top",
                     "font": {"size": 24}}}
            ]
        )

        fig.update_layout(
            updatemenus=[dict(
                type="buttons",
                direction="right",
                x=0.1,  # Move buttons to the left side
                y=1.1,  # Keep at the same height
                showactive=True,
                buttons=[button_3d, button_2d]
            )]
        )

        fig.update_layout(
            title=dict(
                text=f"3D Visualization of {self.collection_name} Embeddings (Original Dimensions: {original_dims})",
                y=0.95,  # Position slightly higher
                x=0.5,
                xanchor='center',
                yanchor='top',
                font=dict(size=24)
            ),
            scene=dict(
                xaxis_title='UMAP Dimension 1',
                yaxis_title='UMAP Dimension 2',
                zaxis_title='UMAP Dimension 3'
            ),
            xaxis_title='',
            yaxis_title='',
            legend=dict(
                x=0.85,
                y=1,
                traceorder="normal",
                font=dict(
                    family="sans-serif",
                    size=12,
                    color="black"
                ),
            ),
            margin=dict(l=0, r=0, b=0, t=150),
            template="plotly_white"
        )

        return fig

    def save_and_open_visualization(self, fig):
        print(f"Saving visualization to {self.output_file}...")
        os.makedirs(os.path.dirname(self.output_file), exist_ok=True)
        if os.path.exists(self.output_file):
            os.remove(self.output_file)
        fig.write_html(self.output_file, auto_open=False)

        # Open in browser
        abs_path = os.path.abspath(self.output_file)
        print(f"Opening visualization in web browser: {abs_path}")
        webbrowser.open('file://' + abs_path)

    def run(self):
        embeddings, documents, metadatas, ids = self.get_embeddings()

        original_dims = embeddings.shape[1]

        embeddings_2d, embeddings_3d = self.reduce_dimensions(embeddings)

        clusters = self.cluster_embeddings(embeddings)

        embeddings_2d, embeddings_3d, documents, metadatas, ids, clusters = self.filter_outliers(
            embeddings_2d, embeddings_3d, documents, metadatas, ids, clusters
        )

        fig = self.create_visualization(embeddings_2d, embeddings_3d, documents, metadatas, ids, clusters,
                                        original_dims)

        self.save_and_open_visualization(fig)
        print("Visualization complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", "-d", default="artifacts/vector_stores/chroma_db")
    parser.add_argument("--collection-name", "-c",
                        help="Name of the collection in ChromaDB")
    parser.add_argument("--max-points", "-m", type=int, default=2000)
    parser.add_argument("--seed", "-s", type=int, default=42)
    parser.add_argument("--clusters", "-k", type=int, default=10,
                        help="Number of clusters for coloring")
    parser.add_argument("--outlier-threshold", "-o", type=float, default=3.0,
                        help="Z-score threshold for outlier removal; lower values remove more outliers")

    args = parser.parse_args()

    visualizer = EmbeddingVisualizer(
        db_directory=args.db,
        collection_name=args.collection_name,
        max_points=args.max_points,
        random_seed=args.seed,
        n_clusters=args.clusters,
        outlier_threshold=args.outlier_threshold
    )
    visualizer.run()