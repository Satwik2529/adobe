from flask import Flask, redirect, make_response, abort
import threading
from werkzeug.serving import make_server
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="{lang}">
<head>
    <title>{title}</title>
    <meta name="description" content="{desc}">
    {canonical}
    {robots}
    {extra_head}
</head>
<body>
    <h1>{h1}</h1>
    {content}
    {links}
    {extra_body}
</body>
</html>
"""

def render_page(title="Test", desc="", h1="Heading", content="", links="", canonical="", robots="", extra_head="", extra_body="", lang="en"):
    return HTML_TEMPLATE.format(
        title=title, desc=desc, h1=h1, content=content, links=links, 
        canonical=f'<link rel="canonical" href="{canonical}">' if canonical else "",
        robots=f'<meta name="robots" content="{robots}">' if robots else "",
        extra_head=extra_head, extra_body=extra_body, lang=lang
    )

@app.route('/')
def index():
    links = """
    <a href="/about">About</a>
    <a href="/products">Products</a>
    <a href="/redirect">Redirect</a>
    <a href="/404">Not Found</a>
    <a href="/500">Server Error</a>
    <a href="/about#team">About Team</a>
    <a href="https://external.com">External</a>
    <a href="/private">Private Area</a>
    <a href="/article">Article</a>
    <a href="/malformed">Malformed JSON</a>
    <a href="/image.png">Image</a>
    <a href="/redirect_chain_1">Redirect Chain</a>
    <a href="/noindex_page">Noindex Page</a>
    <a href="/missing_title">Missing Title</a>
    <a href="/missing_h1">Missing H1</a>
    <a href="/canonical_broken">Canonical Broken</a>
    <a href="/exact_dup_1">Exact Dup 1</a>
    <a href="/exact_dup_2">Exact Dup 2</a>
    <a href="/thin_content">Thin Content</a>
    <a href="/broken_link_source">Broken Link Source</a>
    <a href="/fresh_article">Fresh Article</a>
    <a href="/stale_article">Stale Article</a>
    <a href="/missing_date_article">Missing Date Article</a>
    <a href="/invalid_date">Invalid Date</a>
    <a href="/impossible_date">Impossible Date</a>
    <a href="/future_date">Future Date</a>
    <a href="/contradictory_dates">Contradictory Dates</a>
    <a href="/meta_jsonld_conflict">Meta JSONLD Conflict</a>
    <a href="/same_instant_diff_tz">Same Instant Diff TZ</a>
    <a href="/date_only_vs_datetime">Date Only vs Datetime</a>
    <a href="/stale_product">Stale Product</a>
    <a href="/unknown_old_date">Unknown Old Date</a>
    <a href="/evergreen_old_date">Evergreen Old Date</a>
    """
    extra_head = """
    <meta property="og:title" content="Home OG">
    <meta name="twitter:card" content="summary">
    """
    return render_page(title="Home", desc="Home Page", h1="Welcome", links=links, extra_head=extra_head)

@app.route('/about')
def about():
    links = '<a href="/">Home</a> <a href="/about">About Self</a>'
    return render_page(title="About", desc="About Us", h1="About", links=links)

@app.route('/products')
def products():
    links = '<a href="/products/a">Product A</a> <a href="/products/b">Product B</a>'
    return render_page(title="Products", h1="Our Products", links=links)

@app.route('/products/a')
def product_a():
    extra_head = '<script type="application/ld+json">{"@type": "Product", "name": "Product A"}</script>'
    return render_page(title="Product A", h1="A", extra_head=extra_head)

@app.route('/products/b')
def product_b():
    return render_page(title="Product B", h1="B")

@app.route('/article')
def article():
    extra_head = """
    <meta property="article:published_time" content="2023-01-01T00:00:00Z">
    <meta property="article:modified_time" content="2023-01-02T00:00:00Z">
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "Article",
          "headline": "Test Article",
          "datePublished": "2023-01-01"
        }
      ]
    }
    </script>
    <script type="application/ld+json">
    [{"@type": "Person", "name": "Author"}]
    </script>
    """
    extra_body = """
    <h2>Subheading</h2>
    <img src="/img1.png" alt="An image">
    <img src="/img2.png">
    """
    return render_page(title="Article", h1="Article Title", extra_head=extra_head, extra_body=extra_body)

@app.route('/malformed')
def malformed():
    extra_head = '<script type="application/ld+json">{bad json}</script>'
    return render_page(title="Malformed", h1="Malformed", extra_head=extra_head)

@app.route('/redirect')
def redir():
    return redirect('/products/a', code=301)

@app.route('/robots.txt')
def robots():
    txt = "User-agent: *\nDisallow: /private\n"
    resp = make_response(txt)
    resp.headers['Content-Type'] = 'text/plain'
    return resp

@app.route('/private')
def private():
    return "This should not be crawled."

@app.route('/404')
def not_found():
    abort(404)

@app.route('/500')
def server_error():
    abort(500)

@app.route('/redirect_chain_1')
def redirect_chain_1():
    return redirect('/redirect_chain_2', code=301)

@app.route('/redirect_chain_2')
def redirect_chain_2():
    return redirect('/chained_destination', code=302)

@app.route('/chained_destination')
def chained_destination():
    return render_page(title="Chained", h1="Chained")

@app.route('/noindex_page')
def noindex_page():
    return render_page(title="Noindex", h1="Noindex", robots="noindex, nofollow")

@app.route('/missing_title')
def missing_title():
    return render_page(title="", h1="Missing Title", content="This page has no title.")

@app.route('/missing_h1')
def missing_h1():
    return render_page(title="Missing H1", h1="", content="This page has no H1.")

@app.route('/canonical_broken')
def canonical_broken():
    return render_page(title="Broken Canonical", h1="Broken Canonical", canonical="/404")

@app.route('/exact_dup_1')
def exact_dup_1():
    return render_page(title="Dup 1", h1="Duplicate", content="This is exactly the same content duplicated.")

@app.route('/exact_dup_2')
def exact_dup_2():
    return render_page(title="Dup 2", h1="Duplicate", content="This is exactly the same content duplicated.")

@app.route('/thin_content')
def thin_content():
    return render_page(title="Thin", h1="Thin", content="Short")

@app.route('/broken_link_source')
def broken_link_source():
    links = '<a href="/404">Broken Target</a>'
    return render_page(title="Broken Links", h1="Broken Links", links=links)

@app.route('/fresh_article')
def fresh_article():
    extra_head = """
    <script type="application/ld+json">{"@type": "Article", "datePublished": "2025-01-01"}</script>
    """
    return render_page(title="Fresh Article", h1="Fresh", extra_head=extra_head)

@app.route('/stale_article')
def stale_article():
    extra_head = """
    <script type="application/ld+json">{"@type": "Article", "datePublished": "2020-01-01"}</script>
    """
    return render_page(title="Stale Article", h1="Stale", extra_head=extra_head)

@app.route('/missing_date_article')
def missing_date_article():
    extra_head = '<script type="application/ld+json">{"@type": "Article"}</script>'
    return render_page(title="Missing Date Article", h1="Missing Date", extra_head=extra_head)

@app.route('/invalid_date')
def invalid_date():
    extra_head = '<script type="application/ld+json">{"@type": "Article", "datePublished": "yesterday"}</script>'
    return render_page(title="Invalid Date", h1="Invalid", extra_head=extra_head)

@app.route('/impossible_date')
def impossible_date():
    extra_head = '<script type="application/ld+json">{"@type": "Article", "datePublished": "2024-02-30"}</script>'
    return render_page(title="Impossible Date", h1="Impossible", extra_head=extra_head)

@app.route('/future_date')
def future_date():
    extra_head = '<script type="application/ld+json">{"@type": "Article", "datePublished": "2099-01-01"}</script>'
    return render_page(title="Future Date", h1="Future", extra_head=extra_head)

@app.route('/contradictory_dates')
def contradictory_dates():
    # Published after modified by a year
    extra_head = """
    <script type="application/ld+json">{"@type": "Article", "datePublished": "2024-01-01", "dateModified": "2023-01-01"}</script>
    """
    return render_page(title="Contradictory Dates", h1="Contradictory", extra_head=extra_head)

@app.route('/meta_jsonld_conflict')
def meta_jsonld_conflict():
    # Genuinely different dates
    extra_head = """
    <meta property="article:published_time" content="2024-01-01T00:00:00Z">
    <script type="application/ld+json">{"@type": "Article", "datePublished": "2024-03-15T00:00:00Z"}</script>
    """
    return render_page(title="Meta JSONLD Conflict", h1="Conflict", extra_head=extra_head)

@app.route('/same_instant_diff_tz')
def same_instant_diff_tz():
    # Same instant
    extra_head = """
    <meta property="article:published_time" content="2024-01-01T05:00:00-05:00">
    <script type="application/ld+json">{"@type": "Article", "datePublished": "2024-01-01T10:00:00Z"}</script>
    """
    return render_page(title="Same Instant", h1="Same Instant", extra_head=extra_head)

@app.route('/date_only_vs_datetime')
def date_only_vs_datetime():
    # Same UTC calendar day
    extra_head = """
    <meta property="article:published_time" content="2024-01-01">
    <script type="application/ld+json">{"@type": "Article", "datePublished": "2024-01-01T14:30:00Z"}</script>
    """
    return render_page(title="Date Only Vs Datetime", h1="Date Only Vs Datetime", extra_head=extra_head)

@app.route('/stale_product')
def stale_product():
    extra_head = """
    <script type="application/ld+json">{"@type": "Product", "datePublished": "2019-01-01"}</script>
    """
    return render_page(title="Stale Product", h1="Stale Product", extra_head=extra_head)

@app.route('/unknown_old_date')
def unknown_old_date():
    extra_head = '<script type="application/ld+json">{"@type": "WebPage", "datePublished": "2010-01-01"}</script>'
    return render_page(title="Unknown Old", h1="Unknown Old", extra_head=extra_head)

@app.route('/evergreen_old_date')
def evergreen_old_date():
    extra_head = '<script type="application/ld+json">{"@type": "WebPage", "datePublished": "2015-01-01"}</script>'
    return render_page(title="Evergreen Old", h1="Evergreen Old", extra_head=extra_head)


@app.route('/image.png')
def image():
    resp = make_response(b"fake image data")
    resp.headers['Content-Type'] = 'image/png'
    return resp

class FixtureServerThread(threading.Thread):
    def __init__(self, port=5000):
        threading.Thread.__init__(self)
        self.port = port
        self.server = make_server('127.0.0.1', self.port, app)
        self.ctx = app.app_context()
        self.ctx.push()

    def run(self):
        self.server.serve_forever()

    def shutdown(self):
        self.server.shutdown()

def start_server(port=5000):
    server = FixtureServerThread(port)
    server.start()
    time.sleep(1) # wait for server to start
    return server

@app.route('/phase7_e2e')
def phase7_e2e():
    extra_head = '<script type="application/ld+json">{"@type": "Article", "datePublished": "2023-01-01T12:00:00Z"}</script>'
    extra_body = '<img src="test.jpg" alt="">\n<!-- No links, making this a dead-end -->'
    return render_page(title="Test Page", h1="Main Heading", extra_head=extra_head, extra_body=extra_body)

if __name__ == '__main__':
    app.run(port=5000)
