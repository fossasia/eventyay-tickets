from venueless.celery_app import app
from venueless.core.tasks import WorldTask
from venueless.graphs.report import ReportGenerator


@app.task(base=WorldTask)
def generate_report(world, input=None):
    cf = ReportGenerator(world).build(input)
    return cf.file.url
