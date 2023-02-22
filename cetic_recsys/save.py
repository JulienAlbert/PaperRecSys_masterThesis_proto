from flask import Blueprint, render_template, g, request, flash, session, current_app
from pybtex.database import BibliographyData, Entry, Person

from cetic_recsys.db import get_papers_from_db
from cetic_recsys.utilities import format_papers, update_session

bp = Blueprint('save', __name__)

PAPER_TYPE = {'journal': 'article',
              'dataset': 'misc',
              'book': 'book',
              'repository': 'misc',
              'bookchapter': 'inbook',
              'patent': 'misc',
              'conference': 'proceedings'}


@bp.route('/save')
def show():
    if session['save_results']:
        papers = get_papers_from_db(session['save_results'])
    else:
        papers = []
        flash('no results', category='error')

    return render_template('save.html', papers=format_papers(papers), export_bibtex=None)


@bp.route('/delete_from_save', methods=['POST'])
def delete():
    current_app.logger.debug('request.form ' + str(request.form))

    if 'id' in request.form:
        paper_ids_to_del = set([int(paper_id) for paper_id in request.form.getlist('id')])
        save_results = [paper_id for paper_id in session['save_results']
                        if paper_id not in paper_ids_to_del]
        update_session(session, 'save_results', save_results)
        flash(str(len(paper_ids_to_del)) + ' papers deleted from save', category='success')
    else:
        flash('no paper deleted from save', category='error')

    papers = get_papers_from_db(session['save_results'])

    return render_template('save.html', papers=format_papers(papers), export_bibtex=None)


@bp.route('/export', methods=['POST'])
def export():
    current_app.logger.debug('request.form ' + str(request.form))

    paper_ids_to_export = []
    if 'id' in request.form:
        for paper_id in request.form.getlist('id'):
            paper_ids_to_export.append(int(paper_id))
        flash(str(len(paper_ids_to_export)) + ' papers exported', category='success')
    else:
        flash('no paper exported', category='error')

    papers_to_export = get_papers_from_db(paper_ids_to_export)

    bib_data = BibliographyData()
    for paper in papers_to_export:
        key = paper['id']

        if paper['doc_type']:
            type = PAPER_TYPE[paper['doc_type'].lower()]
        else:
            type = 'misc'

        fields = {}
        fields['title'] = paper['title']
        if paper['publisher']:
            fields['publisher'] = paper['publisher']
        if paper['year']:
            fields['year'] = str(paper['year'])
        if paper['doi']:
            fields['doi'] = paper['doi']
        if paper['abstract']:
            fields['abstract'] = paper['abstract']
        if paper['volume']:
            fields['volume'] = paper['volume']
        if paper['issue']:
            fields['number'] = paper['issue']

        if paper['page_start'] and paper['page_end']:
            fields['pages'] = paper['page_start'] + '--' + paper['page_end']
        elif paper['page_start']:
            fields['pages'] = paper['page_start']
        elif paper['page_end']:
            fields['pages'] = paper['page_end']

        if paper['venue']:
             venue = paper['venue']['name']

        if type == 'article':
            fields['journal'] = venue
        else:
            fields['booktitle'] = venue

        persons = {'author': []}
        if paper['authors']:
            for author in paper['authors']:
                persons['author'].append(Person(author['name']))

        entry = Entry(type_=type, fields=fields, persons=persons)

        bib_data.add_entry(str(key), entry)

    papers = get_papers_from_db(session['save_results'])

    return render_template('save.html', papers=format_papers(papers), export_bibtex=bib_data.to_string('bibtex'))
