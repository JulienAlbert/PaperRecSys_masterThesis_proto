from flask import Blueprint, render_template, g, request, flash, session, current_app
from pybtex.database import parse_string

from cetic_recsys.db import search_from_bibtex, get_papers_from_db
from cetic_recsys.utilities import format_papers, update_session

bp = Blueprint('load', __name__)


@bp.route('/load', methods=['GET', 'POST'])
def load():
    if request.method == 'POST':
        found_paper_ids = set()
        nb_parsed_records = 0

        if request.form['bibtex_query']:
            try:
                bib_data = parse_string(request.form['bibtex_query'], 'bibtex')
            except Exception as e:
                current_app.logger.exception('Error with %s', parse_string.__name__, exc_info=e)
                bib_data = []
                flash('unable to parse bibtex', category='error')

            try:
                nb_parsed_records = len(bib_data.entries)
                for entry in bib_data.entries.values():
                    found_paper_id = None

                    if 'doi' in entry.fields:
                        try:
                            found_paper_id = search_from_bibtex(entry.fields['doi'])
                        except Exception as e:
                            current_app.logger.exception('Error with %s on %s', search_from_bibtex.__name__, 'doi',
                                                         exc_info=e)
                            continue

                    if ('doi' not in entry.fields or not found_paper_id) and 'title' in entry.fields:
                        try:
                            found_paper_id = search_from_bibtex(entry.fields['title'])
                        except Exception as e:
                            current_app.logger.exception('Error with %s on %s', search_from_bibtex.__name__, 'title',
                                                         exc_info=e)
                            continue

                    if found_paper_id:
                        found_paper_ids.add(found_paper_id[0])
            except:
                flash('unable to parse bibtex', category='error')

        papers = get_papers_from_db(found_paper_ids)
        session['load_results'] = [paper['id'] for paper in papers]

        if not papers:
            flash('no result', category='error')
        else:
            flash(str(nb_parsed_records) + ' records parsed and ' + str(len(found_paper_ids)) + ' papers found',
                  category='success')
    else:
        if session['load_results']:
            papers = get_papers_from_db(session['load_results'])
        else:
            papers = []
            flash('no result', category='error')

    return render_template('load.html', papers=format_papers(papers))


@bp.route('/add_from_load', methods=['POST'])
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

    papers = get_papers_from_db(session['load_results'])

    return render_template('load.html', papers=format_papers(papers))


@bp.route('/save_from_load', methods=['POST'])
def save():
    current_app.logger.debug('request.form ' + str(request.form))

    if 'id' in request.form:
        new_saves = []
        for e in request.form.getlist('id'):
            new_saves.append(e)
        update_session(session, 'save_results', session['save_results'] + new_saves)
        flash(str(len(new_saves)) + ' papers saved', category='success')
    else:
        flash('no paper saved', category='error')

    papers = get_papers_from_db(session['load_results'])

    return render_template('load.html', papers=format_papers(papers))


@bp.route('/delete_from_load', methods=['POST'])
def delete():
    current_app.logger.debug('request.form ' + str(request.form))

    if 'id' in request.form:
        paper_ids_to_del = set([int(paper_id) for paper_id in request.form.getlist('id')])
        load_results = [paper_id for paper_id in session['load_results']
                                   if paper_id not in paper_ids_to_del]
        update_session(session, 'load_results', load_results)
        flash(str(len(paper_ids_to_del)) + ' papers deleted from load', category='success')
    else:
        flash('no paper deleted from load', category='error')

    papers = get_papers_from_db(session['load_results'])

    return render_template('load.html', papers=format_papers(papers))
