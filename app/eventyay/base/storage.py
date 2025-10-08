from django.contrib.staticfiles.storage import ManifestStaticFilesStorage

class NoMapManifestStaticFilesStorage(ManifestStaticFilesStorage):
    def post_process(self, paths, dry_run=False, **options):
        # Filter out .map files before processing
        filtered = {k: v for k, v in paths.items() if not k.endswith('.map')}
        return super().post_process(filtered, dry_run, **options)
