from flask import Blueprint, render_template, g, request, flash, session, current_app
from cetic_recsys.db import search_in_db, get_papers_from_db

from cetic_recsys.utilities import format_papers, update_session

bp = Blueprint('search', __name__)


@bp.route('/search', methods=['GET', 'POST'])
def search():
    if request.method == 'POST':
        query = request.form['searched_text'].lower()
        try:
            papers = get_papers_from_db(search_in_db(query))
            search_results = [paper['id'] for paper in papers]
            update_session(session, 'search_results', search_results)

            if not papers:
                flash('no result', category='error')
            else:
                flash(str(len(search_results)) + ' papers found', category='success')
        except Exception as e:
            current_app.logger.exception('Error with %s', search_in_db.__name__, exc_info=e)
            papers = []
            flash('unable to perform search, try again', category='error')
    else:
        if session['search_results']:
            # papers = [get_paper_from_db(paper_id) for paper_id in session['search_results']]
            papers = get_papers_from_db(session['search_results'])
        else:
            papers = []
            flash('no results', category='error')

    return render_template('search.html', papers=format_papers(papers))


@bp.route('/add_from_search', methods=['POST'])
def add():
    current_app.logger.debug('request.form ' + str(request.form))

    if 'id' in request.form:
        new_inputs = []
        for e in request.form.getlist('id'):
            new_inputs.append(e)
        update_session(session, 'recommend_inputs', session['recommend_inputs'] + new_inputs)
        flash(str(len(new_inputs)) + ' inputs added', category='success')
    else:
        flash('no input added', category='error')

    papers = get_papers_from_db(session['search_results'])

    return render_template('search.html', papers=format_papers(papers))


@bp.route('/save_from_search', methods=['POST'])
def save():
    current_app.logger.debug('request.form', request.form)

    if 'id' in request.form:
        new_saves = []
        for e in request.form.getlist('id'):
            new_saves.append(e)
        update_session(session, 'save_results', session['save_results'] + new_saves)
        flash(str(len(new_saves)) + ' papers saved', category='success')
    else:
        flash('no paper saved', category='error')

    papers = get_papers_from_db(session['search_results'])

    return render_template('search.html', papers=format_papers(papers))


@bp.route('/delete_from_search', methods=['POST'])
def delete():
    current_app.logger.debug('request.form', request.form)

    if 'id' in request.form:
        paper_ids_to_del = set([int(paper_id) for paper_id in request.form.getlist('id')])
        search_results = [paper_id for paper_id in session['search_results']
                          if paper_id not in paper_ids_to_del]
        update_session(session, 'search_results', search_results)
        flash(str(len(paper_ids_to_del)) + ' papers deleted from search', category='success')
    else:
        flash('no paper deleted from search', category='error')

    papers = get_papers_from_db(session['search_results'])

    return render_template('search.html', papers=format_papers(papers))
