from flask import current_app
import scipy as sp
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import time

from cetic_recsys.db import get_papers_from_db

from cetic_recsys.utilities import normalize_scores_dict


class GraphComparator:
    def __init__(self, papers):
        self.paper_dict = {paper['id']: paper for paper in papers}
        self.score_dict = {paper['id']: {} for paper in papers}
        self.compare_func = graph_similarity

    def get_score(self, paper1_id, paper2_id):
        if paper1_id in self.score_dict[paper2_id]:
            return self.score_dict[paper1_id][paper2_id]
        else:
            score = self.compare_func(self.paper_dict[paper1_id], self.paper_dict[paper2_id])
            self.score_dict[paper1_id][paper2_id] = score
            self.score_dict[paper2_id][paper1_id] = score
            return score


class ContentComparator:
    def __init__(self, papers):
        self.score_dict = {paper['id']: {} for paper in papers}

        corpus = [paper['title'] + ' ' + paper['abstract'] for paper in papers]
        vectorizer = TfidfVectorizer(stop_words='english').fit(corpus)
        tfidf_vectors = [vectorizer.transform([document]) for document in corpus]
        tfidf_array = sp.sparse.vstack(tfidf_vectors)
        score_array = cosine_similarity(tfidf_array, tfidf_array)

        for paper1, scores in zip(papers, score_array.tolist()):
            for paper2, score in zip(papers, scores):
                self.score_dict[paper1['id']][paper2['id']] = score

    def get_score(self, paper1_id, paper2_id):
        return self.score_dict[paper1_id][paper2_id]


def graph_similarity(paper1, paper2):
    set1 = set(paper1['citation_ids'] + paper1['reference_ids'])
    set2 = set(paper2['citation_ids'] + paper2['reference_ids'])

    union = set1.union(set2)
    intersection = set1.intersection(set2)

    if union:
        return len(intersection) / len(union)
    else:
        return 0


def compute_similar_scores(input_papers, rec_papers, comparator):
    scores = {}

    for rec_paper in rec_papers:
        current_score = sum([comparator.get_score(rec_paper['id'], input_paper['id']) for input_paper in input_papers])
        scores[rec_paper['id']] = current_score / len(input_papers)

    return scores


def compute_popularity_scores(rec_papers):
    scores = {}

    for rec_paper in rec_papers:
        if 'citation_ids' in rec_paper:
            scores[rec_paper['id']] = 1 / (1 + len(rec_paper['citation_ids']))
        else:
            scores[rec_paper['id']] = 1

    return scores


def compute_recency_scores(rec_papers):
    scores = {}

    for rec_paper in rec_papers:
        scores[rec_paper['id']] = 1 / (2021 - rec_paper['year'])

    return scores


def get_rank(input_ids, rec_ids, rank_weights):
    start = time.time()
    input_ids_set = set(input_ids)
    rec_ids_set = set(rec_ids)
    input_papers = get_papers_from_db(input_ids_set, False, False)
    rec_papers = get_papers_from_db(rec_ids_set, False, False)
    rec_ids_scores = {}
    content_comparator = ContentComparator(input_papers + rec_papers)
    graph_comparator = GraphComparator(input_papers + rec_papers)
    current_app.logger.debug('loading papers ' + str(time.time() - start))

    # compute accuracy and novelty scores
    popularity_scores = normalize_scores_dict(compute_popularity_scores(rec_papers))
    recency_scores = normalize_scores_dict(compute_recency_scores(rec_papers))
    similar_content_scores = normalize_scores_dict(compute_similar_scores(input_papers, rec_papers, content_comparator))
    similar_graph_scores = normalize_scores_dict(compute_similar_scores(input_papers, rec_papers, graph_comparator))

    for rec_id in rec_ids_set:
        partial_score = rank_weights['similarity_profile_content'] * similar_content_scores[rec_id]
        partial_score += rank_weights['similarity_profile_graph'] * similar_graph_scores[rec_id]
        partial_score += rank_weights['novelty_popularity'] * popularity_scores[rec_id]
        partial_score += rank_weights['novelty_year'] * recency_scores[rec_id]
        rec_ids_scores[rec_id] = partial_score
    current_app.logger.debug('compute accuracy and novelty scores ' + str(time.time() - start))

    # integrate diversity scores
    best_id = max(rec_ids_scores.items(), key=lambda e: e[1])[0]

    diversity_content_ranked_ids = compute_diversity_ranking(rec_ids_set, best_id, content_comparator)
    diversity_content_scores = normalize_scores_dict(
        {rec_id: 1 / (i + 1) for i, rec_id in enumerate(diversity_content_ranked_ids)})

    diversity_graph_ranked_ids = compute_diversity_ranking(rec_ids_set, best_id, graph_comparator)
    diversity_graph_scores = normalize_scores_dict(
        {rec_id: 1 / (i + 1) for i, rec_id in enumerate(diversity_graph_ranked_ids)})

    for rec_id in rec_ids_set:
        rec_ids_scores[rec_id] += rank_weights['similarity_infra_content'] * diversity_content_scores[rec_id]
        rec_ids_scores[rec_id] += rank_weights['similarity_infra_graph'] * diversity_graph_scores[rec_id]
    current_app.logger.debug('compute diversity scores ' + str(time.time() - start))

    ranked_rec_ids = [rec_id for rec_id, _ in sorted(rec_ids_scores.items(), key=lambda e: e[1], reverse=True)]

    return ranked_rec_ids


def compute_diversity_ranking(rec_ids, best_id, comparator):
    # greedy approach
    ranked_rec_ids = [best_id]
    rec_ids_stack = set(rec_ids)
    rec_ids_stack.remove(best_id)

    while rec_ids_stack:
        id_score_tuples = []
        for rec_id in rec_ids_stack:
            candidate_score = sum([1 - comparator.get_score(rec_id, other_id) for other_id in rec_ids_stack
                                   if other_id != rec_id])
            id_score_tuples.append((rec_id, candidate_score))

        current_best_id = max(id_score_tuples, key=lambda e: e[1])[0]
        ranked_rec_ids.append(current_best_id)
        rec_ids_stack.remove(current_best_id)

    return ranked_rec_ids
