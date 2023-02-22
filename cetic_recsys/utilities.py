def format_paper(paper):
    formatted_ref = {'id': paper['id'],
                     'title': paper['title'],
                     'year': paper['year'],
                     'n_citation': paper['n_citation'],
                     'page_start': paper['page_start'],
                     'page_end': paper['page_end'],
                     'doc_type': paper['doc_type'],
                     'publisher': paper['publisher'],
                     'volume': paper['volume'],
                     'issue': paper['issue'],
                     'doi': paper['doi'],
                     'abstract': paper['abstract']}

    if 'venue' in paper:
        formatted_ref['venue'] = (paper['venue']['name']).title()

    authors = []
    if 'authors' in paper:
        for author in paper['authors']:
            authors.append(author['name'])
    formatted_ref['authors'] = " ; ".join(authors)

    fos_list = []
    if 'fos' in paper:
        for fos in paper['fos']:
            fos_list.append(fos['name'])
    formatted_ref['fos'] = ", ".join(fos_list)

    if 'reference_ids' in paper:
        formatted_ref['n_reference'] = len(paper['reference_ids'])
    else:
        formatted_ref['n_reference'] = 0

    return formatted_ref


def format_papers(papers):
    return [format_paper(ref) for ref in papers]


def update_session(session, field, values):
    if field in session:
        if field == 'rank_weights' and isinstance(values, dict):
            for k, v in values.items():
                if k in session[field]:
                    session[field][k] = int(v)
        elif isinstance(values, list):
            int_casted_values = [int(value) for value in values]
            added_values = set()
            unique_values = []
            for value in int_casted_values:
                if value not in added_values:
                    unique_values.append(value)
                    added_values.add(value)
            session[field] = unique_values
        else:
            raise TypeError
    else:
        raise KeyError


def reset_session(session):
    session['load_results'] = []
    session['search_results'] = []
    session['recommend_results'] = []
    session['recommend_inputs'] = []
    session['save_results'] = []
    session['rank_weights'] = dict([('similarity_profile_content', 0),
                                    ('similarity_profile_graph', 0),
                                    ('similarity_infra_content', 0),
                                    ('similarity_infra_graph', 0),
                                    ('novelty_year', 0),
                                    ('novelty_popularity', 0)])


def is_valid_session(session):
    if not is_valid_int_list_field(session, 'load_results'):
        return False
    if not is_valid_int_list_field(session, 'search_results'):
        return False
    if not is_valid_int_list_field(session, 'recommend_results'):
        return False
    if not is_valid_int_list_field(session, 'recommend_inputs'):
        return False
    if not is_valid_int_list_field(session, 'save_results'):
        return False

    if 'rank_weights' not in session:
        return False
    elif not is_valid_int_weight(session['rank_weights'], 'similarity_profile_content'):
        return False
    elif not is_valid_int_weight(session['rank_weights'], 'similarity_profile_graph'):
        return False
    elif not is_valid_int_weight(session['rank_weights'], 'similarity_infra_content'):
        return False
    elif not is_valid_int_weight(session['rank_weights'], 'similarity_infra_graph'):
        return False
    elif not is_valid_int_weight(session['rank_weights'], 'novelty_year'):
        return False
    elif not is_valid_int_weight(session['rank_weights'], 'novelty_popularity'):
        return False

    return True


def is_valid_int_list_field(session, field):
    if field not in session:
        return False
    elif [e for e in session[field] if not isinstance(e, int)]:
        return False

    return True


def is_valid_int_weight(rank_weights, weight):
    if weight not in rank_weights:
        return False
    elif not isinstance(rank_weights[weight], int):
        return False

    return True


def normalize_scores_dict(scores_dict):
    min_score = min(scores_dict.values())
    max_score = max(scores_dict.values())

    if min_score < max_score:
        return {key: (score-min_score) / (max_score-min_score) for key, score in scores_dict.items()}
    else:
        return {key: 0 for key in scores_dict.keys()}
