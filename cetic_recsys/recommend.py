from flask import Blueprint, render_template, g, request, flash, session, current_app
import time

from cetic_recsys.db import get_papers_from_db
from cetic_recsys.recommend_methods import recommend_tfidf, recommend_cit_jaccard, \
    recommend_fos_jaccard
from cetic_recsys.utilities import format_papers, update_session
from cetic_recsys.rank import get_rank

bp = Blueprint('recommend', __name__)


@bp.route('/recommend', methods=('GET', 'POST'))
def recommend():
    if request.method == 'POST':
        if 'recommend_inputs' in session and session['recommend_inputs']:

            # update recommend input
            current_app.logger.debug('request.form ' + str(request.form))

            if 'method' in request.form:
                if request.form['method'] == 'fos_jaccard':
                    recommend_method = recommend_fos_jaccard
                else:
                    recommend_method = recommend_tfidf
            else:
                recommend_method = recommend_tfidf

            if session['recommend_inputs']:
                start_time = time.time()
                try:
                    recommend_results = [paper_id for paper_id in recommend_method(session['recommend_inputs'])]
                    update_session(session, 'recommend_results', recommend_results)
                    papers = get_papers_from_db(session['recommend_results'])
                    flash(str(len(papers)) + ' papers recommended in {0:.2f} s'.format(time.time() - start_time),
                          category='success')
                except Exception as e:
                    current_app.logger.exception('Error with %s', recommend_method.__name__, exc_info=e)
                    papers = []
                    flash('unable to perform recommendation, try again', category='error')
            else:
                papers = []
                flash('invalid paper id', category='error')

            if 'keep' not in request.form or not request.form['keep']:
                update_session(session, 'recommend_inputs', [])
        else:
            papers = []
            flash('no id', category='error')

        return render_template('exploit.html',
                               papers=format_papers(papers),
                               rank_weights=session['rank_weights'])
    else:
        papers = get_papers_from_db(session['recommend_inputs'])

        if not papers:
            flash('no input', category='error')

        return render_template('recommend.html', papers=format_papers(papers))


@bp.route('/remove_input', methods=['POST'])
def remove_input():
    current_app.logger.debug('request.form ' + str(request.form))

    if 'id' in request.form:
        recommend_inputs = [ref_id for ref_id in session['recommend_inputs'] if ref_id != int(request.form['id'])]
        update_session(session, 'recommend_inputs', recommend_inputs)

    papers = get_papers_from_db(session['recommend_inputs'])

    if not papers:
        flash('no input', category='error')

    return render_template('recommend.html', papers=format_papers(papers))
