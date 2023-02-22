import json
import psycopg2
import psycopg2.extras
from flask import current_app, g
from elasticsearch import Elasticsearch


def get_db():
    if 'cursor' not in g:
        g.connection = psycopg2.connect(host=current_app.config['DB_SERVER'],
                                        port=current_app.config['DB_PORT'],
                                        database=current_app.config['DB_NAME'],
                                        user=current_app.config['DB_USER'],
                                        password=current_app.config['DB_PASSWORD'])

        g.cursor = g.connection.cursor(cursor_factory=psycopg2.extras.DictCursor)

    return g.cursor


def get_es():
    return Elasticsearch([{'host': current_app.config['ES_SERVER'],
                           'port': current_app.config['ES_PORT']}],
                         timeout=30, max_retries=10, retry_on_timeout=True)


# def get_neo4j():
#     return GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "dblp_v12"), encrypted=False)


def close_db(e=None):
    cursor = g.pop('cursor', None)
    connection = g.pop('cursor', None)

    if cursor:
        cursor.close()

    if connection:
        connection.close()


def init_app(app):
    app.teardown_appcontext(close_db)


def construct_non_paper(row_dict):
    non_paper = dict(row_dict)

    if 'paper_ids' in non_paper:
        if non_paper['paper_ids']:
            non_paper['paper_ids'] = json.loads(non_paper['paper_ids'])
        else:
            non_paper['paper_ids'] = []

    return non_paper


def get_author_from_db(author_id, with_linked_ids=False):
    cursor = get_db()

    if with_linked_ids:
        cursor.execute("""SELECT id, name, org, paper_ids FROM author WHERE id = %s""", (author_id,))
    else:
        cursor.execute("""SELECT id, name, org FROM author WHERE id = %s""", (author_id,))

    if cursor.rowcount:
        return construct_non_paper(cursor.fetchone())
    else:
        raise ValueError


def get_fos_from_db(fos_id, with_linked_ids=False):
    cursor = get_db()

    if with_linked_ids:
        cursor.execute("""SELECT id, name, paper_ids FROM fos WHERE id = %s""", (fos_id,))
    else:
        cursor.execute("""SELECT id, name FROM fos WHERE id = %s""", (fos_id,))

    if cursor.rowcount:
        return construct_non_paper(cursor.fetchone())
    else:
        raise ValueError


def get_venue_from_db(venue_id, with_linked_ids=False):
    cursor = get_db()

    if with_linked_ids:
        cursor.execute("""SELECT id, name, type, paper_ids FROM venue WHERE id = %s""", (venue_id,))
    else:
        cursor.execute("""SELECT id, name, type FROM venue WHERE id = %s""", (venue_id,))

    if cursor.rowcount:
        return construct_non_paper(cursor.fetchone())
    else:
        raise ValueError


def construct_paper(row_dict, with_linked_entities):
    paper = dict(row_dict)

    if not paper['abstract']:
        paper['abstract'] = ''

    if paper['reference_ids']:
        paper['reference_ids'] = json.loads(paper['reference_ids'])
    else:
        paper['reference_ids'] = []

    if paper['citation_ids']:
        paper['citation_ids'] = json.loads(paper['citation_ids'])
    else:
        paper['citation_ids'] = []

    if paper['author_ids']:
        paper['author_ids'] = json.loads(paper['author_ids'])
    else:
        paper['author_ids'] = []

    if paper['fos_ids']:
        paper['fos_ids'] = json.loads(paper['fos_ids'])
    else:
        paper['fos_ids'] = []

    if with_linked_entities:
        paper['authors'] = [get_author_from_db(author_id) for author_id in paper['author_ids']]
        paper['fos'] = [get_fos_from_db(fos_id) for fos_id in paper['fos_ids']]
        if paper['venue_id']:
            paper['venue'] = get_venue_from_db(paper['venue_id'])

    return paper


def get_papers_from_db(paper_ids, with_linked_entities=True, keep_order=True):
    cursor = get_db()

    if paper_ids:
        list_of_values = '(' + '),('.join([str(paper_id) for paper_id in paper_ids]) + '))'
        # cursor.execute("""SELECT * FROM paper WHERE id = ANY (VALUES %s)""", (list_of_values,))
        # ugly way of doing...
        query = "SELECT * FROM paper WHERE id = ANY (VALUES " + list_of_values
        cursor.execute(query)

        if cursor.rowcount:
            unordered_papers = [construct_paper(row, with_linked_entities) for row in cursor.fetchall()]
        else:
            raise ValueError

        if keep_order:
            papers_dict = {paper['id']: paper for paper in unordered_papers}
            return [papers_dict[paper_id] for paper_id in paper_ids]
        else:
            return unordered_papers
    else:
        return []


def get_paper_from_db(paper_id, with_linked_entities=True):
    cursor = get_db()
    cursor.execute("""SELECT * FROM paper WHERE id = %s""", (paper_id,))

    if cursor.rowcount:
        return construct_paper(cursor.fetchone(), with_linked_entities)
    else:
        raise ValueError


def get_random_paper_from_db():
    es = get_es()

    results = es.search(index='dblp_v12', body={
        "size": 10,
        "query": {
            "function_score": {
                "functions": [{
                    "random_score": {
                        "seed": "1518707649"
                    }
                }]
            }
        }
    })

    return [result['_source']['paper_id'] for result in results['hits']['hits']]


def search_in_db(query):
    es = get_es()

    results = es.search(index='dblp_v12', body={
        'size': 10,
        'query': {
            'multi_match': {
                'query': query,
                'type': 'best_fields',
                'fields': ['title^3', 'abstract', 'doi^5']
            }
        }
    })

    return [result['_source']['paper_id'] for result in results['hits']['hits']]


def search_from_bibtex(query):
    es = get_es()

    results = es.search(index='dblp_v12', body={
        'size': 1,
        'query': {
            'multi_match': {
                'query': query,
                'type': 'best_fields',
                'fields': ['title^3', 'abstract', 'doi^5']
            }
        }
    })

    return [result['_source']['paper_id'] for result in results['hits']['hits']]


# def get_citing_paper_ids(target_id):
#     target_id = target_id
#     driver = get_neo4j()
#
#     with driver.session() as session:
#         try:
#             results = session.run("""WITH $target_id as target_id
#                               MATCH (target:Paper {paper_id: target_id})<-[:CITES]-(paper:Paper)
#                               USING INDEX target:Paper(paper_id)
#                               RETURN paper.paper_id as paper_id""",
#                               target_id=target_id).records()
#
#             return [result['paper_id'] for result in results]
#         except:
#             return []


# def get_cited_paper_ids(target_id):
#     target_id = target_id
#     driver = get_neo4j()
#
#     with driver.session() as session:
#         try:
#             results = session.run("""WITH $target_id as target_id
#                                   MATCH (target:Paper {paper_id: target_id})-[:CITES]->(paper:Paper)
#                                   USING INDEX target:Paper(paper_id)
#                                   RETURN paper.paper_id as paper_id""",
#                                   target_id=target_id).records()
#
#             return [int(result['paper_id']) for result in results]
#         except:
#             return []


# def get_linked_paper_ids(target_id):
#     target_id = target_id
#     driver = get_neo4j()
#
#     with driver.session() as session:
#         try:
#             results = session.run("""WITH $target_id as target_id
#                                   MATCH (target:Paper {paper_id: target_id})-[:CITES]-(paper:Paper)
#                                   USING INDEX target:Paper(paper_id)
#                                   RETURN DISTINCT paper.paper_id as paper_id""",
#                                   target_id=target_id).records()
#
#             return [result['paper_id'] for result in results]
#         except:
#             return []
