# Third Party
import flask
import flask_bootstrap
import wtforms
import wtforms.csrf.session
import wtforms.ext.sqlalchemy.fields
# Local
import oracle

app = flask.Flask(__name__)
flask_bootstrap.Bootstrap(app)
app.debug = True
app.secret_key = 'asdfp98ydlkasdfy8p9dfayh90sdgy879'

six = oracle.SixDegrees()


class BaseForm(wtforms.Form):
    class Meta:
        csrf = True
        csrf_class = wtforms.csrf.session.SessionCSRF
        csrf_secret = 'wePac4brutus+EguphenehET7UxECrAp'

        @property
        def csrf_context(self):
            return flask.session

QuerySelectField = wtforms.ext.sqlalchemy.fields.QuerySelectField


class SearchForm(BaseForm):
    start_name = QuerySelectField(query_factory=six.all_characters)
    end_name = QuerySelectField(query_factory=six.all_characters)


@app.route('/', methods=['GET', 'POST'])
def index():
    search_form = SearchForm(flask.request.form)
    if flask.request.method == 'POST' and search_form.validate():
        start_name = search_form.start_name.data
        end_name = search_form.end_name.data
        return flask.redirect(flask.url_for('results', start_name=start_name,
                                            end_name=end_name))
    return flask.render_template('index.html', search_form=search_form)


@app.route('/results/<start_name>/<end_name>')
def results(start_name, end_name):
    full_link = six.find_connection(start_name, end_name)
    return flask.render_template('results.html', end_name=end_name,
                                 full_link=full_link)


if __name__ == '__main__':
    app.run()
