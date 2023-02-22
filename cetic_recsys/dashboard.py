from flask import Blueprint, render_template, g, request, flash, session

from cetic_recsys.db import get_papers_from_db

bp = Blueprint('dashboard', __name__)


@bp.route('/dashboard')
def show():
    if session['recommend_results']:
        papers = get_papers_from_db(session['recommend_results'])
    else:
        papers = []
        flash('no results', category='error')

    authors = {}
    venues = {}
    fos_dict = {}
    years = {}
    for paper in papers:
        if 'authors' in paper:
            for author in paper['authors']:
                if author['id'] in authors:
                    authors[author['id']]['n_occ'] += 1
                    authors[author['id']]['n_cit'] += paper['n_citation']
                else:
                    author['n_occ'] = 1
                    author['n_cit'] = paper['n_citation']
                    authors[author['id']] = author

        if 'venue' in paper:
            if paper['venue']['id'] in venues:
                venues[paper['venue']['id']]['n_occ'] += 1
                venues[paper['venue']['id']]['n_cit'] += paper['n_citation']
            else:
                paper['venue']['n_occ'] = 1
                paper['venue']['n_cit'] = paper['n_citation']
                venues[paper['venue']['id']] = paper['venue']

        if 'fos' in paper:
            for fos in paper['fos']:
                if fos['id'] in fos_dict:
                    fos_dict[fos['id']]['n_occ'] += 1
                    fos_dict[fos['id']]['n_cit'] += paper['n_citation']
                else:
                    fos['n_occ'] = 1
                    fos['n_cit'] = paper['n_citation']
                    fos_dict[fos['id']] = fos

        if 'year' in paper:
            if paper['year'] in years:
                years[paper['year']]['n_occ'] += 1
            else:
                years[paper['year']] = {'year': paper['year'], 'n_occ': 1}

    author_list = sorted(authors.values(), key=lambda e: e['n_occ'], reverse=True)
    venue_list = sorted(venues.values(), key=lambda e: e['n_occ'], reverse=True)
    fos_list = sorted(fos_dict.values(), key=lambda e: e['n_occ'], reverse=True)
    year_list = sorted(years.values(), key=lambda e: e['year'], reverse=True)

    return render_template('dashboard.html',
                           authors=author_list,
                           venues=venue_list,
                           fos_list=fos_list,
                           years=year_list)
