from flask import current_app
import time

from cetic_recsys.db import get_es, get_fos_from_db, get_papers_from_db
from cetic_recsys.rank import graph_similarity


def recommend_tfidf(target_ids):
    start_time = time.time()
    es = get_es()

    target_elastic_ids = []
    for target_id in target_ids:
        res = es.search(index=current_app.config['ES_INDEX'], body={
            'size': 1,
            'query': {
                'match': {
                    'paper_id': target_id
                }
            }
        })

        target_elastic_ids.append(res['hits']['hits'][0]['_id'])

    target_docs = [{'_index': current_app.config['ES_INDEX'], '_id': target_id, 'fields': ['title', 'abstract']}
                   for target_id in target_elastic_ids]

    results = es.search(index=current_app.config['ES_INDEX'], body={
        'size': 100,
        'query': {
            'more_like_this': {
                'fields': ['title^2', 'abstract'],
                'like': target_docs,
                'max_query_terms': 100,
                'max_doc_freq': 1000000
            }
        }
    })

    current_app.logger.info('recommend_bm25 finished in %.2f s' % (time.time() - start_time))

    return [result['_source']['paper_id']
            for result in results['hits']['hits']
            if result['_source']['paper_id'] not in target_ids]


def recommend_cit_jaccard(target_ids):
    start_time = time.time()
    size = 100 + len(target_ids)
    es = get_es()
    target_ids_set = set(target_ids)
    target_papers = get_papers_from_db(target_ids_set, False, False)

    target_cit_ids_set = set()
    for target_paper in target_papers:
        target_cit_ids_set.update(target_paper['citation_ids'] + target_paper['reference_ids'])

    nb_cit = min(len(target_cit_ids_set), 250)
    target_cit_ids_list = list(target_cit_ids_set)[:nb_cit]
    should_queries = []
    for cit_id in target_cit_ids_list:
        should_queries.append({'terms': {'linked_papers': [cit_id]}})

    results = es.search(index=current_app.config['ES_INDEX'], body={
        'size': size,
        'query': {
            'function_score': {
                'query': {
                    'bool': {
                        'should': should_queries,
                        'minimum_should_match': 1
                    }
                },
                'script_score': {
                    'script': '1 / (' + str(nb_cit) + ' + doc["linked_papers"].size() - _score)'
                },
                'score_mode': 'multiply'
            }
        }
    })

    results = [result['_source']['paper_id']
               for result in results['hits']['hits']
               if result['_source']['paper_id'] not in target_ids]
    nb_res = min(len(results), 100)

    current_app.logger.info('recommend_cit_jaccard finished in %.2f s' % (time.time() - start_time))

    return results[:nb_res]


def recommend_fos_jaccard(target_ids):
    start_time = time.time()
    size = 100 + len(target_ids)
    es = get_es()
    target_ids_set = set(target_ids)
    target_papers = get_papers_from_db(target_ids_set, True, False)

    target_fos_set = set()
    for target_paper in target_papers:
        target_fos_set.update([fos['name'].lower() for fos in target_paper['fos']])

    nb_fos = min(len(target_fos_set), 50)
    target_fos_list = list(target_fos_set)[:nb_fos]
    should_queries = []
    for fos in target_fos_list:
        should_queries.append({'terms': {'fos.keyword': [fos]}})

    results = es.search(index=current_app.config['ES_INDEX'], body={
        'size': size,
        'query': {
            'function_score': {
                'query': {
                    'bool': {
                        'should': should_queries,
                        'minimum_should_match': 1
                    }
                },
                'script_score': {
                    'script': '1 / (' + str(nb_fos) + ' + doc["fos.keyword"].size() - _score)'
                },
                'score_mode': 'multiply'
            }
        }
    })

    results = [result['_source']['paper_id']
            for result in results['hits']['hits']
            if result['_source']['paper_id'] not in target_ids]
    nb_res = min(len(results), 100)

    current_app.logger.info('recommend_fos_jaccard finished in %.2f s' % (time.time() - start_time))

    return results[:nb_res]


# def recommend_personalized_pagerank(target_ids):
#     target_ids_set = set(target_ids)
#     driver = get_neo4j()
#
#     limit = 100 + len(target_ids)
#
#     with driver.session() as session:
#         try:
#             session.run("CALL gds.graph.create('undirected_citations','Paper', "
#                         "{ CITES: { orientation: 'UNDIRECTED' }})")
#         except:
#             print("undirected_citations already create")
#
#         results = session.run("""WITH $target_ids AS target_ids
#                               UNWIND target_ids AS target_id
#                               WITH DISTINCT target_id
#                               MATCH (target:Paper {paper_id: target_id})
#                               USING INDEX target:Paper(paper_id)
#                               WITH [(target)] AS target_nodes
#                               CALL gds.pageRank.stream('undirected_citations', {
#                               maxIterations: 20,
#                               dampingFactor: 0.85,
#                               sourceNodes: target_nodes})
#                               YIELD nodeId, score
#                               RETURN gds.util.asNode(nodeId).paper_id AS paper_id
#                               ORDER BY score DESC LIMIT $limit""",
#                               target_ids=target_ids_set, limit=limit).records()
#
#     return [result['paper_id'] for result in results if int(result['paper_id']) not in target_ids_set]


# def recommend_jaccard(target_ids):
#     driver = get_neo4j()
#     target_ids_set = set(target_ids)
#
#     with driver.session() as session:
#         candidate_score_tuples = []
#         for target_id in target_ids_set:
#             current_tuples = session.run("""WITH $target_id AS target_id
#                                          MATCH (target:Paper {paper_id: target_id})--(n:Paper)
#                                          USING INDEX target:Paper(paper_id)
#                                          WITH target, collect(id(n)) AS target_n
#                                          MATCH (target)-[*..2]-(candidate:Paper)
#                                          WITH target_n, candidate
#                                          MATCH (candidate)--(n:Paper)
#                                          WITH target_n, candidate, collect(id(n)) AS candidate_n
#                                          RETURN candidate.paper_id AS paper_id,
#                                                 gds.alpha.similarity.jaccard(target_n, candidate_n) AS score """,
#                                          target_id=target_id).records()
#
#             candidate_score_tuples += current_tuples
#
#     # recommend top papers
#     candidate_scores = {}
#     for candidate_score_tuple in candidate_score_tuples:
#         if candidate_score_tuple['paper_id'] not in candidate_scores:
#             candidate_scores[candidate_score_tuple['paper_id']] = candidate_score_tuple['score']
#         else:
#             candidate_scores[candidate_score_tuple['paper_id']] += candidate_score_tuple['score']
#
#     for target_id in target_ids_set:
#         candidate_scores.pop(target_id, '')
#
#     candidates = sorted(candidate_scores.items(), key=lambda c: c[1], reverse=True)
#     size = min(100, len(candidates))
#
#     return [c[0] for c in candidates[:size]]


def recommend_jaccard(target_ids):
    start_time = time.time()
    target_ids_set = set(target_ids)
    target_papers = get_papers_from_db(target_ids_set, False, False)

    one_hop_ids_set = set()
    for target_paper in target_papers:
        one_hop_ids_set.update(target_paper['citation_ids'] + target_paper['reference_ids'])
    one_hop_ids_set.difference_update(target_ids_set)
    candidates = get_papers_from_db(one_hop_ids_set, False, False)
    current_app.logger.info('one_hop_ids_set : %d in %.2f s' % (len(one_hop_ids_set), time.time() - start_time))

    two_hop_ids_set = set()
    for one_hop_paper in candidates:
        two_hop_ids_set.update(one_hop_paper['citation_ids'] + one_hop_paper['reference_ids'])
    two_hop_ids_set.difference_update(one_hop_ids_set)
    two_hop_ids_set.difference_update(target_ids_set)
    candidates += get_papers_from_db(two_hop_ids_set, False, False)
    current_app.logger.info('two_hop_ids_set : %d in %.2f s' % (len(two_hop_ids_set), time.time() - start_time))
    current_app.logger.info('candidates ' + str(len(candidates)))

    candidate_score_tuples = []
    for candidate in candidates:
        score = sum([graph_similarity(candidate, target_paper) for target_paper in target_papers])
        candidate_score_tuples.append((candidate['id'], score))

    candidate_score_tuples.sort(key=lambda c: c[1], reverse=True)
    size = min(100, len(candidates))

    current_app.logger.info('recommend_jaccard finished in %.2f s' % (time.time() - start_time))

    return [c[0] for c in candidate_score_tuples[:size]]


def recommend_discern(target_ids):
    start_time = time.time()

    target_fos_ids = set()
    target_papers = get_papers_from_db(target_ids, False, False)
    current_app.logger.debug(target_ids)

    for target_paper in target_papers:
        target_fos_ids.update(target_paper['fos_ids'])
    current_app.logger.info('target_fos_ids : %d in %.2f s' % (len(target_fos_ids), time.time() - start_time))

    candidate_ids = set()
    for fos_id in target_fos_ids:
        fos = get_fos_from_db(fos_id, True)
        if len(fos['paper_ids']) < 10000:
            candidate_ids.update(paper_id for paper_id in fos['paper_ids'])
    current_app.logger.info('candidate_ids : %d in %.2f s' % (len(candidate_ids), time.time() - start_time))

    candidate_neighbors = {}
    candidate_papers = get_papers_from_db(candidate_ids, False, False)
    for candidate_paper in candidate_papers:
        candidate_id = candidate_paper['id']
        if candidate_paper['reference_ids']:
            candidate_neighbors[candidate_id] = [n for n in candidate_paper['reference_ids'] if n in candidate_ids]
            candidate_neighbors[candidate_id].append(candidate_id)
        else:
            candidate_neighbors[candidate_id] = [candidate_id]

    # for candidate_id in candidate_ids:
    #     candidate = get_paper_from_db(candidate_id)
    #     neighbors = candidate['references']
    #     candidate_neighbors[candidate_id] = [n for n in neighbors if n in candidate_ids]
    #     candidate_neighbors[candidate_id].append(candidate_id)
    current_app.logger.info('candidate_neighbors : %d in %.2f s' %
                            (len([c for c in candidate_neighbors.values() if len(c) > 1]), time.time() - start_time))

    candidates = vertex_reinforced_random_walk(candidate_neighbors, set(target_ids))
    candidates.sort(key=lambda c: c[1], reverse=True)
    size = min(100, len(candidates))

    current_app.logger.info('recommend_discern finished in %.2f s' % (time.time() - start_time))

    return [c[0] for c in candidates[:size]]


def vertex_reinforced_random_walk(neighbors, target_ids, alpha_c=0.25, lambda_c=0.9, n_iter=100):
    p_star = 1 / len(neighbors)  # number of nodes

    p_0_uv = {}
    for u in neighbors.keys():
        p_0_uv[u] = {}
        node_degree = len(neighbors[u])
        for v in neighbors[u]:
            p_0_uv[u][v] = alpha_c / node_degree
        p_0_uv[u][u] = 1 - alpha_c

    # init for first iter
    p_t_u = dict([(node, p_star) for node in neighbors.keys()])
    p_t_uv = p_0_uv
    for i in range(n_iter):
        d_t_u = {}
        for u in neighbors.keys():
            d_t_u[u] = sum([p_0_uv[u][v] * p_t_u[v] for v in neighbors[u]])

        p_t1_u = {}
        for u in neighbors.keys():
            p_t1_u[u] = sum([p_t_uv[u][v] * p_t_u[u] for v in neighbors[u]])

        p_t1_uv = {}
        for u in neighbors.keys():
            p_t1_uv[u] = {}
            for v in neighbors[u]:
                p_t1_uv[u][v] = (1 - lambda_c) * p_star + lambda_c * p_0_uv[u][v] * p_t_u[v] / d_t_u[u]

        p_t_u = p_t1_u
        p_t_uv = p_t1_uv

    return [(p, v) for p, v in p_t_u.items() if p not in target_ids]
