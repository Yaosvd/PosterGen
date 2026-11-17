"""Local, auditable lexical features and bounded CPU KMeans; no model requests."""
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from threadpoolctl import threadpool_limits

from src.rubrics.storage import immutable
from utils.persistence import digest

ALGORITHM_VERSION = 'tfidf_kmeans_semantic_review_v1'


def runtime_identity():
    return {'algorithm': ALGORITHM_VERSION,
            'packages': {name: version(name) for name in ('scikit-learn', 'numpy', 'scipy', 'threadpoolctl')},
            'features': {'lowercase': True, 'norm': 'l2', 'smooth_idf': True, 'dtype': 'float64'},
            'kmeans': {'n_init': 10, 'max_iter': 100, 'tol': 0.0001,
                       'init': 'k-means++', 'algorithm': 'lloyd', 'cpu_threads': 1}}


def validate_settings(settings):
    if set(settings) != {'analyzer', 'ngram_range', 'max_features', 'sublinear_tf'}:
        raise ValueError('Unsupported TF-IDF settings')
    ngrams = settings['ngram_range']
    if (settings['analyzer'] != 'char' or not isinstance(ngrams, list) or len(ngrams) != 2 or
            any(type(n) is not int for n in ngrams) or not 1 <= ngrams[0] <= ngrams[1] <= 5 or
            type(settings['max_features']) is not int or not 1 <= settings['max_features'] <= 65536 or
            type(settings['sublinear_tf']) is not bool):
        raise ValueError('Invalid bounded character TF-IDF configuration')


def fit_texts(texts, document_ids, settings, receipt):
    """Fit one shared space per corpus, retaining vocabulary, IDF and sparse rows.

    Empty corpora are valid. Nonempty documents with no retained features stop the
    job explicitly: silently dropping such evidence could cause false convergence.
    Recomputing on resume must match the immutable receipt under the same runtime.
    """
    validate_settings(settings)
    if len(texts) != len(document_ids) or len(set(document_ids)) != len(document_ids):
        raise ValueError('TF-IDF document identities must be unique and aligned')
    if any(not isinstance(t, str) or not any(c.isalnum() for c in t) for t in texts):
        raise ValueError('TF-IDF documents must contain textual evidence')
    identity = {'runtime': runtime_identity(), 'settings': settings,
                'documents': [{'id': key, 'text_digest': digest(text)} for key, text in zip(document_ids, texts)]}
    if not texts:
        immutable(Path(receipt), {**identity, 'vocabulary': {}, 'idf': [], 'matrix': None})
        return None
    vectorizer = TfidfVectorizer(analyzer='char', ngram_range=tuple(settings['ngram_range']),
        max_features=settings['max_features'], sublinear_tf=settings['sublinear_tf'],
        lowercase=True, norm='l2', smooth_idf=True, dtype=np.float64)
    try:
        matrix = vectorizer.fit_transform(texts).tocsr()
    except ValueError as exc:
        raise ValueError('TF-IDF cannot represent this corpus; no evidence was discarded') from exc
    matrix.sort_indices()
    zero = np.flatnonzero(np.diff(matrix.indptr) == 0)
    if len(zero):
        raise ValueError('TF-IDF zero-feature documents; adjust feature settings before retry: ' +
                         ', '.join(str(document_ids[i]) for i in zero[:10]))
    if not np.isfinite(matrix.data).all():
        raise ValueError('TF-IDF contains nonfinite features')
    immutable(Path(receipt), {**identity, 'vocabulary': {k: int(v) for k, v in vectorizer.vocabulary_.items()},
        'idf': vectorizer.idf_.tolist(), 'matrix': {'shape': list(matrix.shape),
            'data': matrix.data.tolist(), 'indices': matrix.indices.tolist(), 'indptr': matrix.indptr.tolist()}})
    return matrix


def clusters(vectors, requested, seed):
    """Sparse Euclidean KMeans on L2 features, with deterministic group ordering."""
    if type(requested) is not int or requested < 1:
        raise ValueError('KMeans requires a positive cluster count')
    if vectors is None or (isinstance(vectors, list) and not vectors):
        return []
    sparse = hasattr(vectors, 'indptr')
    if sparse:
        x = vectors
        if not np.isfinite(x.data).all() or np.any(np.diff(x.indptr) == 0):
            raise ValueError('KMeans requires finite nonzero vectors')
        unique = {sha256(x.indices[x.indptr[i]:x.indptr[i+1]].tobytes() +
                         x.data[x.indptr[i]:x.indptr[i+1]].tobytes()).digest() for i in range(x.shape[0])}
    else:
        if any(type(v) not in (int, float) for row in vectors for v in row):
            raise ValueError('KMeans vectors must be numeric')
        x = np.asarray(vectors, dtype=float)
        if x.ndim != 2 or not np.isfinite(x).all():
            raise ValueError('KMeans requires finite rectangular vectors')
        lengths = np.linalg.norm(x, axis=1)
        if not np.isfinite(lengths).all() or np.any(lengths == 0):
            raise ValueError('KMeans requires finite nonzero vectors')
        x = x / lengths[:, None]
        unique = {row.tobytes() for row in x}
    count = min(requested, len(unique))
    if count == 1:
        return [list(range(x.shape[0]))]
    with threadpool_limits(limits=1):
        labels = KMeans(n_clusters=count, random_state=seed, n_init=10, init='k-means++',
                        max_iter=100, tol=0.0001, algorithm='lloyd').fit_predict(x)
    groups = [np.flatnonzero(labels == label).tolist() for label in sorted(set(labels))]
    return sorted(groups, key=lambda members: members[0])
